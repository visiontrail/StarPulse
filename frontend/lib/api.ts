import type { Device, DeviceProfile, SnapshotListResponse, TaskRead } from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listDevices: () => request<Device[]>("/devices"),
  getProfile: (deviceId: number) => request<DeviceProfile>(`/devices/${deviceId}/profile`),
  listSnapshots: (deviceId: number, limit = 20) =>
    request<SnapshotListResponse>(`/devices/${deviceId}/config-snapshots?limit=${limit}`),
  collectSnapshot: (deviceId: number, datastore: string) =>
    request<TaskRead>(`/devices/${deviceId}/config-snapshots`, {
      method: "POST",
      body: JSON.stringify({ datastore })
    })
};
