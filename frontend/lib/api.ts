import type {
  AuditLogListResponse,
  ChangePreflightResponse,
  ChangeRequestListResponse,
  ChangeRequestRead,
  CurrentUser,
  DeviceConnectionCreate,
  Device,
  DeviceProfile,
  LoginResponse,
  Permission,
  Role,
  SnapshotListResponse,
  TaskRead,
  UserRead
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  blockers: string[];
  detail: unknown;

  constructor(message: string, status: number, detail: unknown, blockers: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.blockers = blockers;
  }
}

const ROLLBACK_BLOCKER_MESSAGES: Record<string, string> = {
  CHANGE_IN_FLIGHT: "Another change is already in progress for this device/datastore. Wait for it to complete.",
  ROLLBACK_TARGET_NOT_RESTORABLE: "This snapshot cannot be used as a rollback target (normalized content not available).",
  ROLLBACK_NO_DIVERGENCE: "The device is already at the state of the target snapshot — no rollback needed.",
  ROLLBACK_ORIGIN_NOT_RECOVERABLE: "The origin change is not in a recoverable state (must be verification_failed or failed).",
};

export function formatRollbackBlocker(blocker: string): string {
  return ROLLBACK_BLOCKER_MESSAGES[blocker] ?? blocker;
}

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.blockers.length > 0) {
      return error.blockers.map((b) => ROLLBACK_BLOCKER_MESSAGES[b] ?? b).join("; ");
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Request failed";
}

// ── Session state (in-memory access token) ────────────────────────────────

let _accessToken: string | null = null;
let _onSessionExpired: (() => void) | null = null;
let _onSessionRefreshed: ((user: CurrentUser) => void) | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

export function onSessionExpired(cb: () => void): void {
  _onSessionExpired = cb;
}

export function onSessionRefreshed(cb: (user: CurrentUser) => void): void {
  _onSessionRefreshed = cb;
}

// ── Core fetch ─────────────────────────────────────────────────────────────

async function request<T>(
  path: string,
  init?: RequestInit,
  _retry = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined)
  };

  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store"
  });

  if (response.status === 401 && _retry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(path, init, false);
    }
    _onSessionExpired?.();
    throw new Error("Session expired");
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(
      errorMessage(detail) || `Request failed with ${response.status}`,
      response.status,
      detail,
      errorBlockers(detail)
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function readErrorDetail(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function errorMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "detail" in detail) {
    const value = (detail as { detail?: unknown }).detail;
    if (typeof value === "string") return value;
  }
  return null;
}

function errorBlockers(detail: unknown): string[] {
  const message = errorMessage(detail);
  const blockers =
    detail && typeof detail === "object" && "blockers" in detail
      ? (detail as { blockers?: unknown }).blockers
      : null;
  if (Array.isArray(blockers)) return blockers.filter((item) => typeof item === "string");
  const preflightPrefix = message?.startsWith("Rollback preflight failed: ")
    ? "Rollback preflight failed: "
    : message?.startsWith("Change preflight failed: ")
      ? "Change preflight failed: "
      : null;
  if (message && preflightPrefix) {
    return message
      .replace(preflightPrefix, "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function timeoutSignal(ms: number): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, clear: () => clearTimeout(id) };
}

async function tryRefresh(): Promise<boolean> {
  const { signal, clear } = timeoutSignal(8000);
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      signal
    });
    clear();
    if (!res.ok) return false;
    const data = (await res.json()) as { access_token: string };
    _accessToken = data.access_token;
    const me = await fetchCurrentUser();
    _onSessionRefreshed?.(me);
    return true;
  } catch {
    clear();
    return false;
  }
}

async function fetchCurrentUser(): Promise<CurrentUser> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  if (_accessToken) {
    headers.Authorization = `Bearer ${_accessToken}`;
  }
  const res = await fetch(`${API_BASE_URL}/auth/me`, {
    headers,
    credentials: "include",
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error("Unable to load current user");
  }
  return res.json() as Promise<CurrentUser>;
}

// ── Auth endpoints ─────────────────────────────────────────────────────────

async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password }),
    cache: "no-store"
  });
  if (!res.ok) {
    throw new Error("Invalid credentials");
  }
  return res.json() as Promise<LoginResponse>;
}

async function refreshSession(): Promise<CurrentUser | null> {
  const { signal, clear } = timeoutSignal(8000);
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      signal
    });
    clear();
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token: string };
    _accessToken = data.access_token;
    const me = await fetchCurrentUser();
    return me;
  } catch {
    clear();
    return null;
  }
}

async function logout(): Promise<void> {
  await request<void>("/auth/logout", { method: "POST" });
  _accessToken = null;
}

async function getMe(): Promise<CurrentUser> {
  return request<CurrentUser>("/auth/me");
}

// ── Device endpoints ───────────────────────────────────────────────────────

export const api = {
  login,
  logout,
  refreshSession,
  getMe,

  listDevices: () => request<Device[]>("/devices"),
  createDevice: (payload: {
    name: string;
    serial_number?: string | null;
    group?: string | null;
    status?: string;
    metadata?: Record<string, unknown>;
    connection?: DeviceConnectionCreate | null;
  }) =>
    request<Device>("/devices", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getProfile: (deviceId: number) => request<DeviceProfile>(`/devices/${deviceId}/profile`),
  submitConnectionTest: (deviceId: number) =>
    request<TaskRead>(`/devices/${deviceId}/connection-test`, { method: "POST" }),
  submitCapabilityDiscovery: (deviceId: number) =>
    request<TaskRead>(`/devices/${deviceId}/capability-discovery`, { method: "POST" }),
  listSnapshots: (deviceId: number, limit = 20) =>
    request<SnapshotListResponse>(`/devices/${deviceId}/config-snapshots?limit=${limit}`),
  getSnapshot: (deviceId: number, snapshotId: number) =>
    request<SnapshotListResponse["items"][number]>(
      `/devices/${deviceId}/config-snapshots/${snapshotId}`
    ),
  collectSnapshot: (deviceId: number, datastore: string) =>
    request<TaskRead>(`/devices/${deviceId}/config-snapshots`, {
      method: "POST",
      body: JSON.stringify({ datastore })
    }),

  // Admin
  listUsers: () => request<UserRead[]>("/admin/users"),
  listRoles: () => request<Role[]>("/admin/roles"),
  listPermissions: () => request<Permission[]>("/admin/permissions"),
  createUser: (payload: { username: string; display_name: string; password: string }) =>
    request<UserRead>("/admin/users", { method: "POST", body: JSON.stringify(payload) }),
  disableUser: (userId: number) =>
    request<UserRead>(`/admin/users/${userId}/disable`, { method: "POST" }),
  enableUser: (userId: number) =>
    request<UserRead>(`/admin/users/${userId}/enable`, { method: "POST" }),
  assignRole: (userId: number, roleId: number) =>
    request<UserRead>(`/admin/users/${userId}/roles`, {
      method: "POST",
      body: JSON.stringify({ role_id: roleId })
    }),
  removeRole: (userId: number, roleId: number) =>
    request<UserRead>(`/admin/users/${userId}/roles/${roleId}`, { method: "DELETE" }),
  updateRolePermissions: (roleId: number, permissionIds: number[]) =>
    request<Role>(`/admin/roles/${roleId}/permissions`, {
      method: "PUT",
      body: JSON.stringify({ permission_ids: permissionIds })
    }),

  // Change requests
  submitChangeRequest: (payload: {
    device_id: number;
    datastore: string;
    change_summary: string;
    change_ref?: string;
    config_body?: string;
    reason: string;
  }) =>
    request<ChangeRequestRead>("/change-requests", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  previewChangePreflight: (payload: {
    device_id: number;
    datastore: string;
    change_summary?: string;
    change_ref?: string;
    config_body?: string;
    reason: string;
    mode?: "forward" | "rollback";
    rollback_target_snapshot_id?: number;
    rollback_of_change_id?: number;
  }) =>
    request<ChangePreflightResponse>("/change-requests/preflight", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  previewRollbackPreflight: (payload: {
    device_id: number;
    datastore: string;
    reason: string;
    rollback_target_snapshot_id: number;
    rollback_of_change_id?: number;
  }) =>
    request<ChangePreflightResponse>("/change-requests/preflight", {
      method: "POST",
      body: JSON.stringify({ ...payload, mode: "rollback" })
    }),

  submitRollback: (payload: {
    device_id: number;
    datastore: string;
    change_summary: string;
    reason: string;
    rollback_target_snapshot_id: number;
    rollback_of_change_id?: number;
  }) =>
    request<ChangeRequestRead>("/change-requests/rollback", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  rollbackDirectExecute: (payload: {
    device_id: number;
    datastore: string;
    change_summary: string;
    reason: string;
    rollback_target_snapshot_id: number;
    rollback_of_change_id?: number;
  }) =>
    request<ChangeRequestRead>("/change-requests/rollback-execute", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  getRollbackProposal: (changeId: number) =>
    request<ChangeRequestRead>(`/change-requests/${changeId}`).then((cr) => {
      const proposalId = cr.pending_rollback_proposal_id;
      if (!proposalId) return null;
      return request<ChangeRequestRead>(`/change-requests/${proposalId}`);
    }),
  listChangeRequests: (status?: string) =>
    request<ChangeRequestListResponse>(
      `/change-requests${status ? `?status=${status}` : ""}`
    ),
  getChangeRequest: (id: number) => request<ChangeRequestRead>(`/change-requests/${id}`),
  approveChangeRequest: (id: number, note?: string) =>
    request<ChangeRequestRead>(`/change-requests/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ approval_note: note ?? null })
    }),
  rejectChangeRequest: (id: number, note: string) =>
    request<ChangeRequestRead>(`/change-requests/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ rejection_note: note })
    }),
  directExecute: (payload: {
    device_id: number;
    datastore: string;
    change_summary: string;
    change_ref?: string;
    config_body?: string;
    reason: string;
  }) =>
    request<ChangeRequestRead>("/change-requests/direct-execute", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  // Audit
  listAuditLogs: (params?: {
    action?: string;
    outcome?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.action) qs.set("action", params.action);
    if (params?.outcome) qs.set("outcome", params.outcome);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    return request<AuditLogListResponse>(`/audit/logs?${qs.toString()}`);
  }
};
