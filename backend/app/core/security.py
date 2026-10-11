from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import jwt
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt has a 72-byte input limit; only truncate when verifying bcrypt hashes
    scheme = pwd_context.identify(hashed_password)
    if scheme == "bcrypt":
        pwd = _truncate_for_bcrypt(plain_password)
    else:
        pwd = plain_password or ""
    return pwd_context.verify(pwd, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password or "")


def _truncate_for_bcrypt(password: str) -> str:
    """Truncate to 72 bytes for bcrypt compatibility only."""
    if password is None:
        return ""
    b = password.encode("utf-8")
    if len(b) > 72:
        logger.warning("Password longer than 72 bytes — truncating for bcrypt compatibility")
        b = b[:72]
    return b.decode("utf-8", errors="ignore")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
