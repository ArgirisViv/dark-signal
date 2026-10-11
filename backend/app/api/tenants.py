import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.api import schemas
from app.api.deps import require_roles
from app.core.rbac import Role
from app.db.session import get_db
from app.models.tenant import Tenant

router = APIRouter(dependencies=[Depends(require_roles(Role.admin))])


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "tenant"


@router.get(
    "/",
    response_model=List[schemas.TenantOut],
    summary="List tenants",
    description="Return all tenants (admin only).",
)
def list_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).order_by(Tenant.created_at.asc()).all()


@router.post(
    "/",
    response_model=schemas.TenantOut,
    summary="Create tenant",
    description="Create a new tenant workspace.",
)
def create_tenant(payload: schemas.TenantCreate, db: Session = Depends(get_db)):
    slug = _slugify(payload.slug or payload.name)
    existing = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")
    tenant = Tenant(name=payload.name, slug=slug)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
