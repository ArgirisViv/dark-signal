"""link adaptive programs to campaigns

Revision ID: 0007_adaptive_campaign
Revises: 0006_adaptive_stage_schedule
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_adaptive_campaign"
down_revision = "0006_adaptive_stage_schedule"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = {column["name"] for column in inspector.get_columns("adaptive_programs")}

    if "campaign_id" not in existing_columns:
        op.add_column("adaptive_programs", sa.Column("campaign_id", sa.Integer(), nullable=True))

    programs = connection.execute(
        sa.text("SELECT id, baseline_scenario_id FROM adaptive_programs WHERE campaign_id IS NULL")
    ).mappings()
    for program in programs:
        campaign_id = connection.execute(
            sa.text("SELECT campaign_id FROM scenarios WHERE id = :scenario_id"),
            {"scenario_id": program["baseline_scenario_id"]},
        ).scalar()
        if campaign_id is not None:
            connection.execute(
                sa.text("UPDATE adaptive_programs SET campaign_id = :campaign_id WHERE id = :program_id"),
                {"campaign_id": campaign_id, "program_id": program["id"]},
            )

    inspector = sa.inspect(connection)
    existing_indexes = {index["name"] for index in inspector.get_indexes("adaptive_programs")}
    if "idx_adaptive_programs_campaign_id" not in existing_indexes:
        op.create_index("idx_adaptive_programs_campaign_id", "adaptive_programs", ["campaign_id"])

    existing_foreign_keys = {
        constraint.get("name")
        for constraint in inspector.get_foreign_keys("adaptive_programs")
    }
    if "fk_adaptive_programs_campaign_id_campaigns" not in existing_foreign_keys:
        if connection.dialect.name == "sqlite":
            with op.batch_alter_table("adaptive_programs") as batch_op:
                batch_op.create_foreign_key(
                    "fk_adaptive_programs_campaign_id_campaigns",
                    "campaigns",
                    ["campaign_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        else:
            op.create_foreign_key(
                "fk_adaptive_programs_campaign_id_campaigns",
                "adaptive_programs",
                "campaigns",
                ["campaign_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("adaptive_programs"):
        return

    existing_foreign_keys = {
        constraint.get("name")
        for constraint in inspector.get_foreign_keys("adaptive_programs")
    }
    if "fk_adaptive_programs_campaign_id_campaigns" in existing_foreign_keys:
        op.drop_constraint(
            "fk_adaptive_programs_campaign_id_campaigns",
            "adaptive_programs",
            type_="foreignkey",
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("adaptive_programs")}
    if "idx_adaptive_programs_campaign_id" in existing_indexes:
        op.drop_index("idx_adaptive_programs_campaign_id", table_name="adaptive_programs")

    existing_columns = {column["name"] for column in inspector.get_columns("adaptive_programs")}
    if "campaign_id" in existing_columns:
        op.drop_column("adaptive_programs", "campaign_id")
