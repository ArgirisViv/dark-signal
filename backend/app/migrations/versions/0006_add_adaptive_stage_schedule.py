"""add adaptive program stage schedule and execution timestamps

Revision ID: 0006_adaptive_stage_schedule
Revises: 0005_template_metadata
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_adaptive_stage_schedule"
down_revision = "0005_template_metadata"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table("adaptive_programs"):
        op.create_table(
            "adaptive_programs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="created"),
            sa.Column("baseline_scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False),
            sa.Column("final_scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False),
            sa.Column("easier_scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False),
            sa.Column("same_scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False),
            sa.Column("harder_scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False),
            sa.Column("targeted_repetition_scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=True),
            sa.Column("slight_easier_scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=True),
            sa.Column("adaptive_rounds", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("adaptive_round_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source_scenario_ids", sa.JSON(), nullable=True),
            sa.Column("latest_summary", sa.JSON(), nullable=True),
            sa.Column("latest_campaigns", sa.JSON(), nullable=True),
            sa.Column("final_evaluation", sa.JSON(), nullable=True),
            sa.Column("baseline_scheduled_at", sa.DateTime(), nullable=True),
            sa.Column("adaptive_scheduled_at", sa.DateTime(), nullable=True),
            sa.Column("final_scheduled_at", sa.DateTime(), nullable=True),
            sa.Column("baseline_executed_at", sa.DateTime(), nullable=True),
            sa.Column("adaptive_executed_at", sa.DateTime(), nullable=True),
            sa.Column("final_executed_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_adaptive_programs_tenant_id", "adaptive_programs", ["tenant_id"])
        return

    existing_columns = {column["name"] for column in inspector.get_columns("adaptive_programs")}
    schedule_columns = (
        ("baseline_scheduled_at", sa.DateTime()),
        ("adaptive_scheduled_at", sa.DateTime()),
        ("final_scheduled_at", sa.DateTime()),
        ("baseline_executed_at", sa.DateTime()),
        ("adaptive_executed_at", sa.DateTime()),
        ("final_executed_at", sa.DateTime()),
        ("completed_at", sa.DateTime()),
    )
    for column_name, column_type in schedule_columns:
        if column_name not in existing_columns:
            op.add_column("adaptive_programs", sa.Column(column_name, column_type, nullable=True))


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("adaptive_programs"):
        return
    existing_columns = {column["name"] for column in inspector.get_columns("adaptive_programs")}
    for column_name in (
        "completed_at",
        "final_executed_at",
        "adaptive_executed_at",
        "baseline_executed_at",
        "final_scheduled_at",
        "adaptive_scheduled_at",
        "baseline_scheduled_at",
    ):
        if column_name in existing_columns:
            op.drop_column("adaptive_programs", column_name)
