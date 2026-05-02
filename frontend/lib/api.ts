import type {
  AuditLogListResponse,
  ChangeRequestListResponse,
  ChangeRequestRead,
  CurrentUser,
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

// ── Session state (in-memory access token) ────────────────────────────────

let _accessToken: string | null = null;
let _onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

export function onSessionExpired(cb: () => void): void {
  _onSessionExpired = cb;
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
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      cache: "no-store"
    });
    if (!res.ok) return false;
    const data = (await res.json()) as { access_token: string };
    _accessToken = data.access_token;
    return true;
  } catch {
    return false;
  }
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
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      cache: "no-store"
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token: string };
    _accessToken = data.access_token;
    const me = await request<CurrentUser>("/auth/me", undefined, false);
    return me;
  } catch {
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
  getProfile: (deviceId: number) => request<DeviceProfile>(`/devices/${deviceId}/profile`),
  listSnapshots: (deviceId: number, limit = 20) =>
    request<SnapshotListResponse>(`/devices/${deviceId}/config-snapshots?limit=${limit}`),
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

  // Change requests
  submitChangeRequest: (payload: {
    device_id: number;
    datastore: string;
    change_summary: string;
    change_ref?: string;
    reason: string;
  }) =>
    request<ChangeRequestRead>("/change-requests", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listChangeRequests: (status?: string) =>
    request<ChangeRequestListResponse>(
      `/change-requests${status ? `?status=${status}` : ""}`
    ),
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
