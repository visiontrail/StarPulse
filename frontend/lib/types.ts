export type DeviceConnection = {
  host: string;
  port: number;
  protocol: string;
  username: string;
  credential_ref: string | null;
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
