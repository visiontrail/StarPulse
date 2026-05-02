from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_auth_rbac_audit"
down_revision = "0003_device_config_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_permissions_name", "permissions", ["name"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), primary_key=True),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id"), primary_key=True),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    op.create_table(
        "device_config_change_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("datastore", sa.String(64), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("change_ref", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, default="pending_approval"),
        sa.Column("submitter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direct_execute", sa.Boolean(), nullable=False, default=False),
        sa.Column("direct_execute_reason", sa.Text(), nullable=True),
        sa.Column("executor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_task_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_device_config_change_requests_device_id",
        "device_config_change_requests",
        ["device_id"],
    )
    op.create_index(
        "ix_device_config_change_requests_status",
        "device_config_change_requests",
        ["status"],
    )
    op.create_index(
        "ix_device_config_change_requests_submitter_id",
        "device_config_change_requests",
        ["submitter_id"],
    )
    op.create_index(
        "ix_device_config_change_requests_execution_task_id",
        "device_config_change_requests",
        ["execution_task_id"],
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(255), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("permission", sa.String(128), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_outcome", "audit_logs", ["outcome"])
    op.create_index("ix_audit_logs_target_type", "audit_logs", ["target_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # Add actor_user_id and change_request_id to task_statuses
    op.add_column(
        "task_statuses",
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "task_statuses",
        sa.Column(
            "change_request_id",
            sa.Integer(),
            sa.ForeignKey("device_config_change_requests.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_task_statuses_actor_user_id", "task_statuses", ["actor_user_id"])
    op.create_index(
        "ix_task_statuses_change_request_id", "task_statuses", ["change_request_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_task_statuses_change_request_id", table_name="task_statuses")
    op.drop_index("ix_task_statuses_actor_user_id", table_name="task_statuses")
    op.drop_column("task_statuses", "change_request_id")
    op.drop_column("task_statuses", "actor_user_id")
    op.drop_table("audit_logs")
    op.drop_table("device_config_change_requests")
    op.drop_table("refresh_tokens")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
