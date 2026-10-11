"""add LDAP directory integrations

Revision ID: 0008_directory_integrations
Revises: 0007_adaptive_campaign
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_directory_integrations"
down_revision = "0007_adaptive_campaign"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if sa.inspect(connection).has_table("directory_integrations"):
        return
    op.create_table(
        "directory_integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("server_url", sa.String(), nullable=False),
        sa.Column("base_dn", sa.String(), nullable=False),
        sa.Column("bind_dn", sa.String(), nullable=False),
        sa.Column("encrypted_bind_password", sa.Text(), nullable=True),
        sa.Column("user_filter", sa.String(), nullable=False),
        sa.Column("group_base_dn", sa.String(), nullable=True),
        sa.Column("group_filter", sa.String(), nullable=False),
        sa.Column("email_attribute", sa.String(), nullable=False),
        sa.Column("name_attribute", sa.String(), nullable=False),
        sa.Column("department_attribute", sa.String(), nullable=False),
        sa.Column("use_ssl", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("start_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verify_tls_certificate", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_test_status", sa.String(), nullable=True),
        sa.Column("last_test_message", sa.String(), nullable=True),
        sa.Column("last_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_directory_integration_tenant"),
    )
    op.create_index("ix_directory_integrations_tenant_id", "directory_integrations", ["tenant_id"])


def downgrade():
    op.drop_index("ix_directory_integrations_tenant_id", table_name="directory_integrations")
    op.drop_table("directory_integrations")
