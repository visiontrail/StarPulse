from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_rollback_loop"
down_revision = "0006_change_request_safety_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_config_snapshots",
        sa.Column("normalized_content", sa.Text(), nullable=True),
    )

    op.add_column(
        "device_config_change_requests",
        sa.Column("is_rollback", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("rollback_of_change_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "device_config_change_requests",
        sa.Column("rollback_target_snapshot_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "device_config_change_payloads",
        sa.Column("body_digest", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "device_config_change_payloads",
        sa.Column("body_length", sa.Integer(), nullable=True),
    )
    op.add_column(
        "device_config_change_payloads",
        sa.Column("line_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "device_config_change_payloads",
        sa.Column("summary_source", sa.String(length=255), nullable=True),
    )

    op.create_index(
        "ix_device_config_change_requests_is_rollback",
        "device_config_change_requests",
        ["is_rollback"],
    )
    op.create_index(
        "ix_device_config_change_requests_rollback_of_change_id",
        "device_config_change_requests",
        ["rollback_of_change_id"],
    )
    op.create_index(
        "ix_device_config_change_requests_rollback_target_snapshot_id",
        "device_config_change_requests",
        ["rollback_target_snapshot_id"],
    )

    op.create_foreign_key(
        "fk_change_requests_rollback_of_change_id",
        "device_config_change_requests",
        "device_config_change_requests",
        ["rollback_of_change_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_change_requests_rollback_target_snapshot_id",
        "device_config_change_requests",
        "device_config_snapshots",
        ["rollback_target_snapshot_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_change_requests_rollback_target_snapshot_id",
        "device_config_change_requests",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_change_requests_rollback_of_change_id",
        "device_config_change_requests",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_device_config_change_requests_rollback_target_snapshot_id",
        table_name="device_config_change_requests",
    )
    op.drop_index(
        "ix_device_config_change_requests_rollback_of_change_id",
        table_name="device_config_change_requests",
    )
    op.drop_index(
        "ix_device_config_change_requests_is_rollback",
        table_name="device_config_change_requests",
    )
    op.drop_column("device_config_change_requests", "rollback_target_snapshot_id")
    op.drop_column("device_config_change_requests", "rollback_of_change_id")
    op.drop_column("device_config_change_requests", "is_rollback")
    op.drop_column("device_config_change_payloads", "summary_source")
    op.drop_column("device_config_change_payloads", "line_count")
    op.drop_column("device_config_change_payloads", "body_length")
    op.drop_column("device_config_change_payloads", "body_digest")
    op.drop_column("device_config_snapshots", "normalized_content")
