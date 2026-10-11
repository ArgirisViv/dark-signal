from datetime import datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, BackgroundTasks
from typing import Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api import schemas
from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token, get_password_hash
from app.services.audit import record_event
from app.services.email import send_email
from app.services.email_templates import get_or_create_template, render_template
from app.services.tenants import get_or_create_default_tenant
from app.core.rbac import Role, normalize_role
from app.core.config import settings
from app.api.deps import require_roles

router = APIRouter()
logger = logging.getLogger(__name__)
LOGIN_ROLES = {Role.admin.value, Role.analyst.value, Role.viewer.value}

AUTH_RATE_LIMIT = 10
AUTH_RATE_WINDOW_SECONDS = 60
_auth_attempts = defaultdict(list)
RESET_TOKEN_TTL_MINUTES = 30
RESET_RATE_LIMIT = 3
RESET_RATE_WINDOW_SECONDS = 60
_reset_attempts = defaultdict(list)


def _enforce_auth_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=AUTH_RATE_WINDOW_SECONDS)
    recent = [t for t in _auth_attempts[client_ip] if t > window_start]
    if len(recent) >= AUTH_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts. Please try again later.",
        )
    recent.append(now)
    _auth_attempts[client_ip] = recent


def _enforce_reset_rate_limit(email: str):
    key = (email or "").strip().lower()
    if not key:
        return
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=RESET_RATE_WINDOW_SECONDS)
    recent = [t for t in _reset_attempts[key] if t > window_start]
    if len(recent) >= RESET_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many reset attempts. Please wait a minute and try again.",
        )
    recent.append(now)
    _reset_attempts[key] = recent


def _send_reset_email_safe(to_email: str, subject: str, body_text: str, body_html: Optional[str]) -> None:
    try:
        send_email(to_email, subject, body_text, body_html)
        logger.info("Password reset email queued for %s", to_email)
    except Exception as exc:
        logger.error("Failed to send reset email to %s: %s", to_email, exc)


def get_user_by_email(db: Session, email: str):
    normalized = (email or "").strip().lower()
    return db.query(User).filter(func.lower(User.email) == normalized).first()


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()




@router.post(
    "/token",
    response_model=schemas.Token,
    summary="Login and get access token",
    description="Authenticate a user with email/password and receive a bearer token.",
)
def login_for_access_token(
    form_data: schemas.TokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _enforce_auth_rate_limit(request)
    user = get_user_by_email(db, form_data.email)
    if (
        not user
        or normalize_role(user.role) not in LOGIN_ROLES
        or not verify_password(form_data.password, user.hashed_password)
    ):
        record_event(
            db,
            action="auth.login.failed",
            user_id=user.id if user else None,
            tenant_id=user.tenant_id if user else None,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    record_event(db, action="auth.login.success", user_id=user.id, tenant_id=user.tenant_id)
    db.commit()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.email,
            "role": normalize_role(user.role),
            "tenant_id": user.tenant_id,
        },
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/register",
    response_model=schemas.UserOut,
    summary="Register an application account",
    description="Create an application account. Administrator access is required.",
)
def register_user(
    u: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    normalized_email = str(u.email).strip().lower()
    role = normalize_role(u.role) or Role.viewer.value
    if role not in LOGIN_ROLES:
        raise HTTPException(status_code=422, detail=f"Unsupported role: {u.role}")
    existing = get_user_by_email(db, normalized_email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    hashed = get_password_hash(u.password)
    user = User(
        email=normalized_email,
        hashed_password=hashed,
        role=role,
        full_name=u.full_name,
        tenant_id=current_user.tenant_id,
    )
    db.add(user)
    try:
        db.flush()
        record_event(
            db,
            action=f"user.created:{user.id}",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        # Log full traceback to server logs for debugging
        logger.error("Failed to create user: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to create user. See server logs for details.")


@router.post(
    "/forgot-password",
    response_model=schemas.ForgotPasswordResponse,
    summary="Request password reset",
    description="Send password reset email if the account exists.",
)
def forgot_password(
    payload: schemas.ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    _enforce_auth_rate_limit(request)
    _enforce_reset_rate_limit(payload.email)
    user = get_user_by_email(db, payload.email)
    logger.info("Forgot password requested for %s (found=%s)", payload.email, bool(user))
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        raise HTTPException(status_code=503, detail="Email service is not configured")
    if user and normalize_role(user.role) in LOGIN_ROLES:
        token = token_urlsafe(32)
        user.reset_token_hash = _hash_token(token)
        user.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
        record_event(db, action="auth.password.reset.requested", user_id=user.id, tenant_id=user.tenant_id)
        db.commit()
        logger.info("Reset token stored for %s", user.email)
        base_url = settings.FRONTEND_BASE_URL or "http://localhost:3000"
        if base_url.endswith(":5174"):
            base_url = "http://localhost:3000"
        reset_url = f"{base_url}/reset-password?token={token}"
        template = get_or_create_template(db, "password_reset")
        context = {
            "app_name": settings.APP_NAME,
            "reset_url": reset_url,
            "expires_minutes": RESET_TOKEN_TTL_MINUTES,
        }
        subject = render_template(template.subject, context) or f"Reset your {settings.APP_NAME} password"
        body_text = render_template(template.body_text, context) or ""
        body_html = render_template(template.body_html, context)
        background_tasks.add_task(_send_reset_email_safe, user.email, subject, body_text, body_html)
    # Always return a generic response to avoid account enumeration.
    message = "If the account exists, a reset link has been sent. Check your inbox and spam."
    return {"message": message}


@router.post(
    "/reset-password",
    response_model=schemas.ResetPasswordResponse,
    summary="Reset password",
    description="Reset password using a valid reset token.",
)
def reset_password(
    payload: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    hashed = _hash_token(payload.token)
    now = datetime.utcnow()
    user = (
        db.query(User)
        .filter(User.reset_token_hash == hashed)
        .filter(User.reset_token_expires_at.isnot(None))
        .filter(User.reset_token_expires_at >= now)
        .filter(User.role.in_(sorted(LOGIN_ROLES)))
        .first()
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = get_password_hash(payload.password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    record_event(db, action="auth.password.reset.completed", user_id=user.id, tenant_id=user.tenant_id)
    db.commit()
    return {"message": "Password updated successfully."}


@router.post(
    "/bootstrap",
    response_model=schemas.UserOut,
    summary="Bootstrap admin user",
    description="Create the first admin user using a bootstrap token.",
)
def bootstrap_admin(
    payload: schemas.BootstrapRequest,
    request: Request,
    db: Session = Depends(get_db),
    bootstrap_token: Optional[str] = Header(default=None, alias="X-Bootstrap-Token"),
):
    _enforce_auth_rate_limit(request)
    if not settings.bootstrap_token:
        raise HTTPException(status_code=503, detail="Bootstrap token is not configured")

    provided = bootstrap_token or payload.token
    if not provided or provided != settings.bootstrap_token:
        raise HTTPException(status_code=403, detail="Invalid bootstrap token")

    existing_admin = db.query(User).filter(User.role == "admin").first()
    if existing_admin:
        raise HTTPException(status_code=409, detail="Admin already exists")

    normalized_email = str(payload.email).strip().lower()
    if db.query(User).filter(func.lower(User.email) == normalized_email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    default_tenant = get_or_create_default_tenant(db)
    admin = User(
        email=normalized_email,
        hashed_password=get_password_hash(payload.password),
        role="admin",
        full_name=payload.full_name,
        tenant_id=default_tenant.id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    record_event(db, action="auth.bootstrap.success", user_id=admin.id, tenant_id=admin.tenant_id)
    db.commit()
    return admin
