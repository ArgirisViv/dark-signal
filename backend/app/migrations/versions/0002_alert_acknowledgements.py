"""Add operational alert acknowledgement storage.

Revision ID: 0002_alert_acknowledgements
Revises: 0001_initial_schema
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_alert_acknowledgements"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_acknowledgements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("alert_id", sa.String(), nullable=False),
        sa.Column("acknowledged_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_alert_acknowledgements_tenant_id", "alert_acknowledgements", ["tenant_id"])
    op.create_index("ix_alert_acknowledgements_alert_id", "alert_acknowledgements", ["alert_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_acknowledgements_alert_id", table_name="alert_acknowledgements")
    op.drop_index("ix_alert_acknowledgements_tenant_id", table_name="alert_acknowledgements")
    op.drop_table("alert_acknowledgements")