from sqlalchemy.orm import Session
from app.models.tenant import Tenant


DEFAULT_TENANT_SLUG = "default"
DEFAULT_TENANT_NAME = "Default Workspace"


def get_or_create_default_tenant(db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == DEFAULT_TENANT_SLUG).first()
    if tenant:
        return tenant
    tenant = Tenant(name=DEFAULT_TENANT_NAME, slug=DEFAULT_TENANT_SLUG)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
