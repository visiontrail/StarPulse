from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_device_config_snapshots"
down_revision = "0002_device_access_capability_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_config_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("source_task_id", sa.String(length=255), nullable=False),
        sa.Column("datastore", sa.String(length=64), nullable=False),
        sa.Column("content_digest", sa.String(length=128), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("diff_summary", sa.JSON(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_device_config_snapshots_device_id", "device_config_snapshots", ["device_id"]
    )
    op.create_index(
        "ix_device_config_snapshots_source_task_id",
        "device_config_snapshots",
        ["source_task_id"],
    )
    op.create_index(
        "ix_device_config_snapshots_datastore", "device_config_snapshots", ["datastore"]
    )
    op.create_index(
        "ix_device_config_snapshots_collected_at",
        "device_config_snapshots",
        ["collected_at"],
    )


def downgrade() -> None:
    op.drop_table("device_config_snapshots")
