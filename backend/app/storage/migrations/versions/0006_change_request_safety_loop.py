from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_change_request_safety_loop"
down_revision = "0005_config_change_payloads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_config_change_requests",
        sa.Column("baseline_snapshot_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("preflight_status", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("preflight_summary", sa.JSON(), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("risk_summary", sa.JSON(), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("preflight_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("verification_status", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("verification_snapshot_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("verification_summary", sa.JSON(), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_foreign_key(
        "fk_change_requests_baseline_snapshot_id",
        "device_config_change_requests",
        "device_config_snapshots",
        ["baseline_snapshot_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_change_requests_verification_snapshot_id",
        "device_config_change_requests",
        "device_config_snapshots",
        ["verification_snapshot_id"],
        ["id"],
    )
    op.create_index(
        "ix_device_config_change_requests_baseline_snapshot_id",
        "device_config_change_requests",
        ["baseline_snapshot_id"],
    )
    op.create_index(
        "ix_device_config_change_requests_preflight_status",
        "device_config_change_requests",
        ["preflight_status"],
    )
    op.create_index(
        "ix_device_config_change_requests_verification_status",
        "device_config_change_requests",
        ["verification_status"],
    )
    op.create_index(
        "ix_device_config_change_requests_verification_snapshot_id",
        "device_config_change_requests",
        ["verification_snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_config_change_requests_verification_snapshot_id",
        table_name="device_config_change_requests",
    )
    op.drop_index(
        "ix_device_config_change_requests_verification_status",
        table_name="device_config_change_requests",
    )
    op.drop_index(
        "ix_device_config_change_requests_preflight_status",
        table_name="device_config_change_requests",
    )
    op.drop_index(
        "ix_device_config_change_requests_baseline_snapshot_id",
        table_name="device_config_change_requests",
    )
    op.drop_constraint(
        "fk_change_requests_verification_snapshot_id",
        "device_config_change_requests",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_change_requests_baseline_snapshot_id",
        "device_config_change_requests",
        type_="foreignkey",
    )
    op.drop_column("device_config_change_requests", "verified_at")
    op.drop_column("device_config_change_requests", "verification_summary")
    op.drop_column("device_config_change_requests", "verification_snapshot_id")
    op.drop_column("device_config_change_requests", "verification_status")
    op.drop_column("device_config_change_requests", "preflight_generated_at")
    op.drop_column("device_config_change_requests", "risk_summary")
    op.drop_column("device_config_change_requests", "preflight_summary")
    op.drop_column("device_config_change_requests", "preflight_status")
    op.drop_column("device_config_change_requests", "baseline_snapshot_id")
