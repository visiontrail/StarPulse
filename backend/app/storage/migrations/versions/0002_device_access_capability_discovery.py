from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_device_access_capability_discovery"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credential_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("credential_ref", sa.String(length=255), nullable=False),
        sa.Column("credential_type", sa.String(length=64), nullable=False),
        sa.Column("secret", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_credential_records_credential_ref",
        "credential_records",
        ["credential_ref"],
        unique=True,
    )

    with op.batch_alter_table("device_connection_configs") as batch_op:
        batch_op.add_column(sa.Column("credential_ref", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_device_connection_configs_credential_ref", ["credential_ref"])
        batch_op.drop_column("password_secret")

    with op.batch_alter_table("task_statuses") as batch_op:
        batch_op.add_column(sa.Column("device_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("result_summary", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("error_code", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("context", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_task_statuses_device_id_devices", "devices", ["device_id"], ["id"]
        )
        batch_op.create_index("ix_task_statuses_device_id", ["device_id"])

    op.create_table(
        "device_discovery_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("source_task_id", sa.String(length=255), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=True),
        sa.Column("system_info", sa.JSON(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index(
        "ix_device_discovery_results_source_task_id",
        "device_discovery_results",
        ["source_task_id"],
    )


def downgrade() -> None:
    op.drop_table("device_discovery_results")

    with op.batch_alter_table("task_statuses") as batch_op:
        batch_op.drop_index("ix_task_statuses_device_id")
        batch_op.drop_constraint("fk_task_statuses_device_id_devices", type_="foreignkey")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("context")
        batch_op.drop_column("error_message")
        batch_op.drop_column("error_code")
        batch_op.drop_column("result_summary")
        batch_op.drop_column("device_id")

    with op.batch_alter_table("device_connection_configs") as batch_op:
        batch_op.add_column(sa.Column("password_secret", sa.Text(), nullable=True))
        batch_op.drop_index("ix_device_connection_configs_credential_ref")
        batch_op.drop_column("credential_ref")

    op.drop_table("credential_records")
