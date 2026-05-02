// ── Auth / RBAC types ──────────────────────────────────────────────────────

export type Permission = {
  id: number;
  name: string;
  description: string | null;
};

export type Role = {
  id: number;
  name: string;
  description: string | null;
  permissions: Permission[];
};

export type UserSummary = {
  id: number;
  username: string;
  display_name: string;
};

export type UserRead = {
  id: number;
  username: string;
  display_name: string;
  is_active: boolean;
  roles: Role[];
  created_at: string;
  updated_at: string;
};

export type CurrentUser = {
  id: number;
  username: string;
  display_name: string;
  is_active: boolean;
  roles: string[];
  permissions: string[];
};

export type Session = {
  accessToken: string;
  user: CurrentUser;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: CurrentUser;
};

export type AuditLogRead = {
  id: number;
  actor_user_id: number | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  outcome: string;
  permission: string | null;
  ip_address: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type AuditLogListResponse = {
  items: AuditLogRead[];
  limit: number;
  offset: number;
};

export type ChangeRequestStatus =
  | "pending_approval"
  | "approved"
  | "rejected"
  | "executed"
  | string;

export type ChangeRequestRead = {
  id: number;
  device_id: number;
  datastore: string;
  change_summary: string;
  change_ref: string | null;
  reason: string;
  status: ChangeRequestStatus;
  submitter: UserSummary | null;
  approver: UserSummary | null;
  approval_note: string | null;
  approved_at: string | null;
  direct_execute: boolean;
  direct_execute_reason: string | null;
  execution_task_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ChangeRequestListResponse = {
  items: ChangeRequestRead[];
  limit: number;
  offset: number;
};

// ── Permissions constants (mirrors backend) ────────────────────────────────

export const PERM = {
  DEVICE_READ: "device:read",
  DEVICE_MANAGE: "device:manage",
  DEVICE_COLLECT: "device:collect",
  DEVICE_CHANGE_SUBMIT: "device:change:submit",
  DEVICE_CHANGE_APPROVE: "device:change:approve",
  DEVICE_CHANGE_EXECUTE: "device:change:execute",
  TASK_READ: "task:read",
  SNAPSHOT_READ: "snapshot:read",
  AUDIT_READ_SUMMARY: "audit:read:summary",
  AUDIT_READ_FULL: "audit:read:full",
  USER_MANAGE: "user:manage",
  ROLE_MANAGE: "role:manage",
  SYSTEM_CONFIG: "system:config",
} as const;

// ── Device / task types ────────────────────────────────────────────────────

export type DeviceConnection = {
  host: string;
  port: number;
  protocol: string;
  username: string;
  has_credential: boolean;
};

export type DeviceDiscovery = {
  source_task_id: string;
  capabilities: string[];
  system_info: Record<string, unknown>;
  discovered_at: string;
  summary: Record<string, unknown>;
};

export type ConfigSnapshot = {
  id: number;
  source_task_id: string;
  datastore: string;
  content_digest: string;
  collected_at: string;
  diff_summary: Record<string, unknown>;
  summary: Record<string, unknown>;
};

export type TaskSummary = {
  task_id: string;
  task_type: string;
  status: "queued" | "running" | "succeeded" | "failed" | string;
  actor_user_id: number | null;
  actor: UserSummary | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type Device = {
  id: number;
  name: string;
  serial_number: string | null;
  group: string | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  connection: DeviceConnection | null;
  last_discovery: DeviceDiscovery | null;
  last_config_snapshot: ConfigSnapshot | null;
  recent_tasks: TaskSummary[];
};

export type DeviceProfile = Device & {
  capabilities: string[];
  system_info: Record<string, unknown>;
  safety_summary: Record<string, unknown>;
};

export type TaskRead = TaskSummary & {
  device_id: number | null;
  result_summary: Record<string, unknown> | null;
  context: Record<string, unknown>;
  completed_at: string | null;
  metadata: Record<string, unknown>;
};

export type SnapshotListResponse = {
  items: ConfigSnapshot[];
  limit: number;
  offset: number;
};
