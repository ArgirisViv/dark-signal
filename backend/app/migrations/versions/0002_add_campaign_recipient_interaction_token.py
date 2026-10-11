"""Add interaction token to campaign recipient snapshots.

Revision ID: 0002_add_campaign_recipient_interaction_token
Revises: 0001_initial_schema
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_campaign_token" 
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    columns = {
        column["name"]
        for column in inspector.get_columns("campaign_recipient_snapshots")
    }

    if "interaction_token" not in columns:
        op.add_column(
            "campaign_recipient_snapshots",
            sa.Column("interaction_token", sa.String(), nullable=True),
        ) 

def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    columns = {
        column["name"]
        for column in inspector.get_columns("campaign_recipient_snapshots")
    }

    if "interaction_token" in columns:
        op.drop_column(
            "campaign_recipient_snapshots",
            "interaction_token",
        ) 