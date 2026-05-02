from __future__ import annotations

# Permission constants
PERM_DEVICE_READ = "device:read"
PERM_DEVICE_COLLECT = "device:collect"
PERM_DEVICE_CHANGE_SUBMIT = "device:change:submit"
PERM_DEVICE_CHANGE_APPROVE = "device:change:approve"
PERM_DEVICE_CHANGE_EXECUTE = "device:change:execute"

PERM_TASK_READ = "task:read"
PERM_SNAPSHOT_READ = "snapshot:read"

PERM_AUDIT_READ_SUMMARY = "audit:read:summary"
PERM_AUDIT_READ_FULL = "audit:read:full"

PERM_USER_MANAGE = "user:manage"
PERM_ROLE_MANAGE = "role:manage"
PERM_SYSTEM_CONFIG = "system:config"

ALL_PERMISSIONS = [
    PERM_DEVICE_READ,
    PERM_DEVICE_COLLECT,
    PERM_DEVICE_CHANGE_SUBMIT,
    PERM_DEVICE_CHANGE_APPROVE,
    PERM_DEVICE_CHANGE_EXECUTE,
    PERM_TASK_READ,
    PERM_SNAPSHOT_READ,
    PERM_AUDIT_READ_SUMMARY,
    PERM_AUDIT_READ_FULL,
    PERM_USER_MANAGE,
    PERM_ROLE_MANAGE,
    PERM_SYSTEM_CONFIG,
]

# Role -> permission matrix
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer": [
        PERM_DEVICE_READ,
        PERM_TASK_READ,
        PERM_SNAPSHOT_READ,
        PERM_AUDIT_READ_SUMMARY,
    ],
    "operator": [
        PERM_DEVICE_READ,
        PERM_DEVICE_COLLECT,
        PERM_DEVICE_CHANGE_SUBMIT,
        PERM_TASK_READ,
        PERM_SNAPSHOT_READ,
        PERM_AUDIT_READ_SUMMARY,
    ],
    "approver": [
        PERM_DEVICE_READ,
        PERM_DEVICE_COLLECT,
        PERM_DEVICE_CHANGE_SUBMIT,
        PERM_DEVICE_CHANGE_APPROVE,
        PERM_DEVICE_CHANGE_EXECUTE,
        PERM_TASK_READ,
        PERM_SNAPSHOT_READ,
        PERM_AUDIT_READ_SUMMARY,
    ],
    "admin": [
        PERM_DEVICE_READ,
        PERM_DEVICE_COLLECT,
        PERM_DEVICE_CHANGE_SUBMIT,
        PERM_DEVICE_CHANGE_APPROVE,
        PERM_DEVICE_CHANGE_EXECUTE,
        PERM_TASK_READ,
        PERM_SNAPSHOT_READ,
        PERM_AUDIT_READ_SUMMARY,
        PERM_AUDIT_READ_FULL,
        PERM_USER_MANAGE,
        PERM_ROLE_MANAGE,
        PERM_SYSTEM_CONFIG,
    ],
}

# Audit action constants
class AuditAction:
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    REFRESH_FAILURE = "auth.refresh.failure"

    USER_CREATED = "admin.user.created"
    USER_DISABLED = "admin.user.disabled"
    USER_ENABLED = "admin.user.enabled"
    ROLE_ASSIGNED = "admin.role.assigned"
    ROLE_REMOVED = "admin.role.removed"
    ROLE_PERMISSION_CHANGED = "admin.role.permission_changed"

    CHANGE_SUBMITTED = "change.submitted"
    CHANGE_APPROVED = "change.approved"
    CHANGE_REJECTED = "change.rejected"
    CHANGE_DIRECT_EXECUTED = "change.direct_executed"
    CHANGE_EXEC_SUCCESS = "change.exec.success"
    CHANGE_EXEC_FAILURE = "change.exec.failure"

    PERMISSION_DENIED = "authz.permission_denied"
    VALIDATION_FAILED = "op.validation_failed"
    EXECUTION_FAILED = "op.execution_failed"


class AuditOutcome:
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
