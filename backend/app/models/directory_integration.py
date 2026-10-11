from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.db.base import Base


class DirectoryIntegration(Base):
    __tablename__ = "directory_integrations"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_directory_integration_tenant"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    server_url = Column(String, nullable=False)
    base_dn = Column(String, nullable=False)
    bind_dn = Column(String, nullable=False)
    encrypted_bind_password = Column(Text, nullable=True)
    user_filter = Column(String, nullable=False, default="(&(objectClass=person)(mail=*))")
    group_base_dn = Column(String, nullable=True)
    group_filter = Column(String, nullable=False, default="(objectClass=group)")
    email_attribute = Column(String, nullable=False, default="mail")
    name_attribute = Column(String, nullable=False, default="displayName")
    department_attribute = Column(String, nullable=False, default="department")
    use_ssl = Column(Boolean, nullable=False, default=False)
    start_tls = Column(Boolean, nullable=False, default=True)
    verify_tls_certificate = Column(Boolean, nullable=False, default=True)
    last_test_status = Column(String, nullable=True)
    last_test_message = Column(String, nullable=True)
    last_test_at = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
