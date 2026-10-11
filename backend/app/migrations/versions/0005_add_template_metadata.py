"""add template training metadata

Revision ID: 0005_template_metadata
Revises: 0004_campaign_foreign_keys
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_template_metadata"
down_revision = "0004_campaign_foreign_keys"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    existing_columns = {
        column["name"]
        for column in sa.inspect(connection).get_columns("email_templates")
    }
    columns = (
        ("difficulty", sa.String(), "medium"),
        ("category", sa.String(), "General"),
        ("topic", sa.String(), "Security awareness"),
        ("psychological_technique", sa.String(), "urgency"),
    )
    for column_name, column_type, default in columns:
        if column_name not in existing_columns:
            op.add_column(
                "email_templates",
                sa.Column(
                    column_name,
                    column_type,
                    nullable=False,
                    server_default=default,
                ),
            )


def downgrade():
    op.drop_column("email_templates", "psychological_technique")
    op.drop_column("email_templates", "topic")
    op.drop_column("email_templates", "category")
    op.drop_column("email_templates", "difficulty")
