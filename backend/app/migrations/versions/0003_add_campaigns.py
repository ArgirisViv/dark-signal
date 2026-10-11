"""Add campaigns and campaign foreign keys.

Revision ID: 0003_add_campaigns
Revises: 0002_alert_acknowledgements, 0002_campaign_token
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_campaigns"
down_revision = ("0002_alert_acknowledgements", "0002_campaign_token")
branch_labels = None
depends_on = None


def _has_campaign_foreign_key(inspector, table_name: str) -> bool:
    return any(
        constraint.get("referred_table") == "campaigns"
        and constraint.get("constrained_columns") == ["campaign_id"]
        for constraint in inspector.get_foreign_keys(table_name)
    )


def _create_campaign_foreign_key(table_name: str, constraint_name: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_foreign_key(
                constraint_name,
                "campaigns",
                ["campaign_id"],
                ["id"],
                ondelete="SET NULL",
            )
        return
    op.create_foreign_key(
        constraint_name,
        table_name,
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table("campaigns"):
        op.create_table(
            "campaigns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="Draft"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("idx_campaigns_name", "campaigns", ["name"])
        op.create_index("idx_campaigns_status", "campaigns", ["status"])
        op.create_index("idx_campaigns_tenant_id", "campaigns", ["tenant_id"])

    for table_name, column_name, column_type, index_name in [
        ("scenarios", "campaign_id", sa.Integer(), "idx_scenarios_campaign_id"),
        ("events", "campaign_id", sa.Integer(), "idx_events_campaign_id"),
        ("campaign_recipient_snapshots", "campaign_id", sa.Integer(), "idx_campaign_snapshots_campaign_id"),
    ]:
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if column_name not in columns:
            op.add_column(table_name, sa.Column(column_name, column_type, nullable=True))
        existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, [column_name])

    inspector = sa.inspect(connection)
    for table_name, constraint_name in [
        ("scenarios", "fk_scenarios_campaign_id_campaigns"),
        ("events", "fk_events_campaign_id_campaigns"),
        ("campaign_recipient_snapshots", "fk_campaign_snapshots_campaign_id_campaigns"),
    ]:
        if not _has_campaign_foreign_key(inspector, table_name):
            _create_campaign_foreign_key(table_name, constraint_name)
            inspector = sa.inspect(connection)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    for table_name, column_name, index_name, constraint_name in [
        ("campaign_recipient_snapshots", "campaign_id", "idx_campaign_snapshots_campaign_id", "fk_campaign_snapshots_campaign_id_campaigns"),
        ("events", "campaign_id", "idx_events_campaign_id", "fk_events_campaign_id_campaigns"),
        ("scenarios", "campaign_id", "idx_scenarios_campaign_id", "fk_scenarios_campaign_id_campaigns"),
    ]:
        existing_foreign_keys = {
            constraint.get("name")
            for constraint in inspector.get_foreign_keys(table_name)
        }
        if constraint_name in existing_foreign_keys:
            op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table_name)
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if column_name in columns:
            op.drop_column(table_name, column_name)

    if inspector.has_table("campaigns"):
        op.drop_index("idx_campaigns_tenant_id", table_name="campaigns")
        op.drop_index("idx_campaigns_status", table_name="campaigns")
        op.drop_index("idx_campaigns_name", table_name="campaigns")
        op.drop_table("campaigns")
