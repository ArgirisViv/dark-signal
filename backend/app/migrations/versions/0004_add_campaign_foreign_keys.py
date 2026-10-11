"""Add campaign foreign-key constraints for databases already on revision 0003.

Revision ID: 0004_campaign_foreign_keys
Revises: 0003_add_campaigns
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_campaign_foreign_keys"
down_revision = "0003_add_campaigns"
branch_labels = None
depends_on = None


CONSTRAINTS = [
    ("scenarios", "fk_scenarios_campaign_id_campaigns"),
    ("events", "fk_events_campaign_id_campaigns"),
    ("campaign_recipient_snapshots", "fk_campaign_snapshots_campaign_id_campaigns"),
]


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
    for table_name, constraint_name in CONSTRAINTS:
        if not _has_campaign_foreign_key(inspector, table_name):
            _create_campaign_foreign_key(table_name, constraint_name)
            inspector = sa.inspect(connection)

    campaigns = sa.table(
        "campaigns",
        sa.column("id", sa.Integer),
        sa.column("tenant_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    scenarios = sa.table(
        "scenarios",
        sa.column("id", sa.Integer),
        sa.column("tenant_id", sa.Integer),
        sa.column("title", sa.String),
        sa.column("campaign_id", sa.Integer),
    )
    unassigned = connection.execute(
        sa.select(scenarios.c.id, scenarios.c.tenant_id, scenarios.c.title)
        .where(scenarios.c.campaign_id.is_(None))
    ).mappings()
    for scenario in unassigned:
        campaign_id = connection.execute(
            campaigns.insert()
            .values(
                tenant_id=scenario["tenant_id"],
                name=scenario["title"] or f"Legacy scenario {scenario['id']}",
                description="Migrated campaign for an existing scenario.",
                status="Draft",
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
            .returning(campaigns.c.id)
        ).scalar_one()
        connection.execute(
            scenarios.update()
            .where(scenarios.c.id == scenario["id"])
            .values(campaign_id=campaign_id)
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    for table_name, constraint_name in reversed(CONSTRAINTS):
        existing = {
            constraint.get("name")
            for constraint in inspector.get_foreign_keys(table_name)
        }
        if constraint_name in existing:
            op.drop_constraint(constraint_name, table_name, type_="foreignkey")
