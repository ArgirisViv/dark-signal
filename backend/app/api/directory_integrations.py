from datetime import datetime, timezone
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.rbac import Role
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.directory_integration import DirectoryIntegration
from app.models.user import User
from app.services.audit import record_event
from app.services.directory_integration import DirectoryConnectionError, encrypt_secret, fetch_recipients, list_groups, test_connection


router = APIRouter()


class DirectoryConfigUpdate(BaseModel):
    enabled: bool = False
    server_url: str = Field(..., min_length=8, max_length=300)
    base_dn: str = Field(..., min_length=3, max_length=500)
    bind_dn: str = Field(..., min_length=3, max_length=500)
    bind_password: Optional[str] = Field(default=None, max_length=500)
    user_filter: str = Field(default="(&(objectClass=person)(mail=*))", min_length=3, max_length=1000)
    group_base_dn: Optional[str] = Field(default=None, max_length=500)
    group_filter: str = Field(default="(objectClass=group)", min_length=3, max_length=1000)
    email_attribute: str = Field(default="mail", min_length=1, max_length=80)
    name_attribute: str = Field(default="displayName", min_length=1, max_length=80)
    department_attribute: str = Field(default="department", min_length=1, max_length=80)
    use_ssl: bool = False
    start_tls: bool = True
    verify_tls_certificate: bool = True

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith(("ldap://", "ldaps://")):
            raise ValueError("Server URL must start with ldap:// or ldaps://")
        return normalized


class DirectorySelection(BaseModel):
    group_dns: list[str] = Field(..., min_length=1, max_length=100)


def _serialize(config: DirectoryIntegration | None) -> dict:
    if not config:
        return {"configured": False, "enabled": False, "has_password": False, "status": "not_configured"}
    return {
        "configured": True,
        "enabled": config.enabled,
        "server_url": config.server_url,
        "base_dn": config.base_dn,
        "bind_dn": config.bind_dn,
        "has_password": bool(config.encrypted_bind_password),
        "user_filter": config.user_filter,
        "group_base_dn": config.group_base_dn,
        "group_filter": config.group_filter,
        "email_attribute": config.email_attribute,
        "name_attribute": config.name_attribute,
        "department_attribute": config.department_attribute,
        "use_ssl": config.use_ssl,
        "start_tls": config.start_tls,
        "verify_tls_certificate": config.verify_tls_certificate,
        "status": config.last_test_status or "not_tested",
        "last_test_message": config.last_test_message,
        "last_test_at": config.last_test_at,
        "last_sync_at": config.last_sync_at,
        "last_sync_count": config.last_sync_count,
    }


def _get_config(db: Session, tenant_id: int) -> DirectoryIntegration:
    config = db.query(DirectoryIntegration).filter(DirectoryIntegration.tenant_id == tenant_id).first()
    if not config:
        raise HTTPException(status_code=409, detail="LDAP directory is not configured.")
    return config


@router.get("/config")
def get_config(db: Session = Depends(get_db), current_user: User = Depends(require_roles(Role.admin))):
    return _serialize(db.query(DirectoryIntegration).filter(DirectoryIntegration.tenant_id == current_user.tenant_id).first())


@router.put("/config")
def save_config(payload: DirectoryConfigUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(Role.admin))):
    config = db.query(DirectoryIntegration).filter(DirectoryIntegration.tenant_id == current_user.tenant_id).first()
    if not config:
        config = DirectoryIntegration(tenant_id=current_user.tenant_id)
        db.add(config)
    for key, value in payload.model_dump(exclude={"bind_password"}).items():
        setattr(config, key, value.strip() if isinstance(value, str) else value)
    if payload.bind_password:
        config.encrypted_bind_password = encrypt_secret(payload.bind_password)
    if not config.encrypted_bind_password:
        raise HTTPException(status_code=422, detail="Bind password is required for the first configuration.")
    config.last_test_status = "not_tested"
    config.last_test_message = "Configuration changed. Test the connection before synchronizing."
    record_event(db, action="directory.configuration_updated", user_id=current_user.id, tenant_id=current_user.tenant_id)
    db.commit()
    db.refresh(config)
    return _serialize(config)


@router.post("/test")
def test_saved_config(db: Session = Depends(get_db), current_user: User = Depends(require_roles(Role.admin))):
    config = _get_config(db, current_user.tenant_id)
    config.last_test_at = datetime.now(timezone.utc)
    try:
        vendor = test_connection(config)
        config.last_test_status = "connected"
        config.last_test_message = f"Connection successful. {vendor}"
    except DirectoryConnectionError as exc:
        config.last_test_status = "failed"
        config.last_test_message = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.commit()
    return _serialize(config)


@router.get("/groups")
def groups(search: str = Query(default="", max_length=100), db: Session = Depends(get_db), current_user: User = Depends(require_roles(Role.admin))):
    config = _get_config(db, current_user.tenant_id)
    if not config.enabled or config.last_test_status != "connected":
        raise HTTPException(status_code=409, detail="Enable and test LDAP before browsing groups.")
    try:
        return {"items": list_groups(config, search)}
    except DirectoryConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/preview")
def preview(payload: DirectorySelection, db: Session = Depends(get_db), current_user: User = Depends(require_roles(Role.admin))):
    config = _get_config(db, current_user.tenant_id)
    if not config.enabled or config.last_test_status != "connected":
        raise HTTPException(status_code=409, detail="Enable and test LDAP before previewing recipients.")
    try:
        recipients = fetch_recipients(config, payload.group_dns)
    except DirectoryConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"count": len(recipients), "items": recipients[:500]}


@router.post("/import")
def import_recipients(payload: DirectorySelection, db: Session = Depends(get_db), current_user: User = Depends(require_roles(Role.admin))):
    config = _get_config(db, current_user.tenant_id)
    if not config.enabled or config.last_test_status != "connected":
        raise HTTPException(status_code=409, detail="Enable and test LDAP before importing recipients.")
    try:
        recipients = fetch_recipients(config, payload.group_dns)
    except DirectoryConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    created, skipped = [], []
    for item in recipients:
        existing = db.query(User).filter(func.lower(User.email) == item["email"]).first()
        if existing:
            skipped.append({"email": item["email"], "reason": "Recipient already exists"})
            continue
        user = User(
            tenant_id=current_user.tenant_id,
            email=item["email"],
            hashed_password=get_password_hash(secrets.token_urlsafe(24)),
            role=Role.trainee.value,
            full_name=item["full_name"],
            department=item["department"],
            risk="Low",
        )
        db.add(user)
        created.append({"email": item["email"], "full_name": item["full_name"]})
    config.last_sync_at = datetime.now(timezone.utc)
    config.last_sync_count = len(created)
    record_event(db, action=f"directory.recipients_imported:{len(created)}", user_id=current_user.id, tenant_id=current_user.tenant_id)
    db.commit()
    return {"created_count": len(created), "skipped_count": len(skipped), "created": created, "skipped": skipped}
