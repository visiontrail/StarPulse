from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_config_change_payloads"
down_revision = "0004_auth_rbac_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_config_change_payloads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "change_request_id",
            sa.Integer(),
            sa.ForeignKey("device_config_change_requests.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("config_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_device_config_change_payloads_change_request_id",
        "device_config_change_payloads",
        ["change_request_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_config_change_payloads_change_request_id",
        table_name="device_config_change_payloads",
    )
    op.drop_table("device_config_change_payloads")
