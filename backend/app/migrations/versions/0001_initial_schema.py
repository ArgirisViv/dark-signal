"""Initial application schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-21
"""
from alembic import op

from app.db.base import Base
from app.models import campaign_recipient_snapshot, email_template, event, scenario, tenant, training_assignment, training_module, user


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

BASELINE_TABLES = (
    "tenants",
    "users",
    "campaigns",
    "scenarios",
    "events",
    "email_templates",
    "training_modules",
    "training_assignments",
    "campaign_recipient_snapshots",
)


def upgrade() -> None:
    Base.metadata.create_all(
        bind=op.get_bind(),
        tables=[Base.metadata.tables[table_name] for table_name in BASELINE_TABLES],
    )


def downgrade() -> None:
    Base.metadata.drop_all(
        bind=op.get_bind(),
        tables=[Base.metadata.tables[table_name] for table_name in BASELINE_TABLES],
    )
