from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="trainee")
    full_name = Column(String, nullable=True)
    department = Column(String, nullable=True)
    risk = Column(String, nullable=True)
    reset_token_hash = Column(String, nullable=True)
    reset_token_expires_at = Column(DateTime, nullable=True)