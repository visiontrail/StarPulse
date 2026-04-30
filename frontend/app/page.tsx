"use client";

import {
  AlertTriangle,
  Database,
  FileClock,
  Gauge,
  HardDrive,
  KeyRound,
  ListRestart,
  RefreshCw,
  Router,
  ShieldCheck,
  Sparkles,
  TerminalSquare
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { ConfigSnapshot, Device, DeviceProfile, SnapshotListResponse, TaskRead } from "@/lib/types";
import { Button, DatastoreSelect, EmptyState, FieldLabel, StatusBadge } from "@/components/ui";
import { cn } from "@/lib/utils";

type LoadState = "idle" | "loading" | "loaded" | "error";

export default function OperationsConsole() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);
  const [profile, setProfile] = useState<DeviceProfile | null>(null);
  const [snapshots, setSnapshots] = useState<ConfigSnapshot[]>([]);
  const [datastore, setDatastore] = useState("running");
  const [lastTask, setLastTask] = useState<TaskRead | null>(null);
  const [devicesState, setDevicesState] = useState<LoadState>("idle");
  const [profileState, setProfileState] = useState<LoadState>("idle");
  const [submitState, setSubmitState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);

  const selectedDevice = useMemo(
    () => devices.find((device) => device.id === selectedDeviceId) ?? null,
    [devices, selectedDeviceId]
  );

  const loadDevices = useCallback(async () => {
    setDevicesState("loading");
    setError(null);
    try {
      const items = await api.listDevices();
      setDevices(items);
      setSelectedDeviceId((current) => current ?? items[0]?.id ?? null);
      setDevicesState("loaded");
    } catch (caught) {
      setDevicesState("error");
      setError(errorMessage(caught));
    }
  }, []);

  const loadProfile = useCallback(async (deviceId: number) => {
    setProfileState("loading");
    setError(null);
    try {
      const [profileResult, snapshotResult]: [DeviceProfile, SnapshotListResponse] =
        await Promise.all([api.getProfile(deviceId), api.listSnapshots(deviceId, 20)]);
      setProfile(profileResult);
      setSnapshots(snapshotResult.items);
      setProfileState("loaded");
    } catch (caught) {
      setProfileState("error");
      setError(errorMessage(caught));
    }
  }, []);

  useEffect(() => {
    void loadDevices();
  }, [loadDevices]);

  useEffect(() => {
    if (selectedDeviceId !== null) {
      void loadProfile(selectedDeviceId);
    } else {
      setProfile(null);
      setSnapshots([]);
    }
  }, [loadProfile, selectedDeviceId]);

  const configTaskRunning = profile?.recent_tasks.some(
    (task) =>
      task.task_type === "device.config_snapshot" &&
      (task.status === "queued" || task.status === "running")
  );

  async function submitSnapshot() {
    if (selectedDeviceId === null || configTaskRunning) {
      return;
    }
    setSubmitState("loading");
    setError(null);
    try {
      const task = await api.collectSnapshot(selectedDeviceId, datastore);
      setLastTask(task);
      await loadProfile(selectedDeviceId);
      setSubmitState("loaded");
    } catch (caught) {
      setSubmitState("error");
      setError(errorMessage(caught));
    }
  }

  return (
    <main className="min-h-screen p-4 text-ink md:p-6">
      <div className="mx-auto grid max-w-[1440px] gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="rounded border border-warm bg-canvas/95">
          <div className="flex h-16 items-center justify-between border-b border-warm px-4">
            <div>
              <p className="font-mono text-[11px] uppercase text-muted">Star Pulse</p>
              <h1 className="text-xl font-semibold">Operations</h1>
            </div>
            <Button
              aria-label="Refresh devices"
              title="Refresh devices"
              onClick={() => void loadDevices()}
              busy={devicesState === "loading"}
              className="h-9 w-9 px-0"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>

          <div className="p-3">
            {devicesState === "loading" ? <DeviceListSkeleton /> : null}
            {devicesState === "loaded" && devices.length === 0 ? (
              <EmptyState icon={<Router className="h-6 w-6" />} title="No devices registered" />
            ) : null}
            {devicesState === "error" ? (
              <ErrorPanel message={error} onRetry={() => void loadDevices()} />
            ) : null}
            {devices.length > 0 ? (
              <div className="space-y-2">
                {devices.map((device) => (
                  <DeviceListItem
                    key={device.id}
                    device={device}
                    active={device.id === selectedDeviceId}
                    onSelect={() => setSelectedDeviceId(device.id)}
                  />
                ))}
              </div>
            ) : null}
          </div>
        </aside>

        <section className="min-w-0 rounded border border-warm bg-canvas/95">
          {selectedDevice === null && devicesState !== "loading" ? (
            <div className="p-4">
              <EmptyState icon={<HardDrive className="h-6 w-6" />} title="Select a device" />
            </div>
          ) : null}

          {selectedDevice !== null ? (
            <>
              <header className="flex flex-col gap-4 border-b border-warm px-4 py-4 xl:flex-row xl:items-center xl:justify-between">
                <div className="min-w-0">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <StatusBadge status={profile?.status ?? selectedDevice.status} />
                    <span className="font-mono text-[11px] text-muted">
                      {selectedDevice.group ?? "ungrouped"}
                    </span>
                  </div>
                  <h2 className="truncate text-2xl font-semibold">{selectedDevice.name}</h2>
                  <p className="mt-1 font-mono text-xs text-muted">
                    {selectedDevice.connection
                      ? `${selectedDevice.connection.protocol}://${selectedDevice.connection.host}:${selectedDevice.connection.port}`
                      : "connection unavailable"}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <DatastoreSelect value={datastore} onValueChange={setDatastore} />
                  <Button
                    onClick={() => void submitSnapshot()}
                    disabled={submitState === "loading" || configTaskRunning}
                    busy={submitState === "loading"}
                  >
                    <Database className="h-4 w-4" aria-hidden="true" />
                    Collect
                  </Button>
                  <Button
                    aria-label="Refresh profile"
                    title="Refresh profile"
                    onClick={() => void loadProfile(selectedDevice.id)}
                    busy={profileState === "loading"}
                    className="h-9 w-9 px-0"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </div>
              </header>

              {error ? (
                <div className="px-4 pt-4">
                  <ErrorPanel message={error} onRetry={() => void loadProfile(selectedDevice.id)} />
                </div>
              ) : null}

              <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_380px]">
                <div className="space-y-4">
                  <ProfileGrid profile={profile} loading={profileState === "loading"} />
                  <SnapshotTable snapshots={snapshots} />
                </div>
                <div className="space-y-4">
                  <ReadOnlyPanel
                    profile={profile}
                    lastTask={lastTask}
                    configTaskRunning={Boolean(configTaskRunning)}
                  />
                  <RecentTasks tasks={profile?.recent_tasks ?? []} />
                </div>
              </div>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function DeviceListItem({
  device,
  active,
  onSelect
}: {
  device: Device;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full rounded border p-3 text-left transition",
        active
          ? "border-warm-strong bg-paper"
          : "border-transparent bg-transparent hover:border-warm hover:bg-paper/70"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{device.name}</p>
          <p className="mt-1 truncate font-mono text-[11px] text-muted">
            {device.group ?? "ungrouped"}
          </p>
        </div>
        <StatusBadge status={device.status} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
        <Metric label="Discovery" value={summaryValue(device.last_discovery?.summary)} />
        <Metric label="Snapshot" value={digestShort(device.last_config_snapshot?.content_digest)} />
      </div>
    </button>
  );
}

function ProfileGrid({ profile, loading }: { profile: DeviceProfile | null; loading: boolean }) {
  if (loading && profile === null) {
    return <PanelSkeleton />;
  }
  if (profile === null) {
    return <EmptyState icon={<Gauge className="h-6 w-6" />} title="Profile unavailable" />;
  }
  const connection = profile.connection;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <InfoPanel icon={<TerminalSquare />} title="Connection">
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label="Host" value={connection?.host ?? "-"} />
          <Metric label="Port" value={connection?.port ?? "-"} />
          <Metric label="Protocol" value={connection?.protocol ?? "-"} />
          <Metric label="User" value={connection?.username ?? "-"} />
          <Metric label="Credential" value={connection?.has_credential ? "referenced" : "missing"} />
          <Metric label="Serial" value={profile.serial_number ?? "-"} />
        </div>
      </InfoPanel>
      <InfoPanel icon={<Sparkles />} title="Discovery">
        <div className="grid gap-3">
          <Metric label="Capabilities" value={profile.capabilities.length} />
          <Metric label="System" value={Object.keys(profile.system_info).length} />
          <CodeList items={profile.capabilities.slice(0, 5)} empty="No capabilities" />
        </div>
      </InfoPanel>
    </div>
  );
}

function SnapshotTable({ snapshots }: { snapshots: ConfigSnapshot[] }) {
  return (
    <InfoPanel icon={<FileClock />} title="Snapshots">
      {snapshots.length === 0 ? (
        <EmptyState icon={<Database className="h-6 w-6" />} title="No snapshots collected" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-warm text-left font-mono text-[11px] uppercase text-muted">
                <th className="py-2 pr-3 font-medium">Datastore</th>
                <th className="py-2 pr-3 font-medium">Collected</th>
                <th className="py-2 pr-3 font-medium">Digest</th>
                <th className="py-2 font-medium">Diff</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((snapshot) => (
                <tr key={snapshot.id} className="border-b border-warm/70 last:border-0">
                  <td className="py-3 pr-3 font-mono text-xs">{snapshot.datastore}</td>
                  <td className="py-3 pr-3 text-muted">{formatDate(snapshot.collected_at)}</td>
                  <td className="py-3 pr-3 font-mono text-xs">{digestShort(snapshot.content_digest)}</td>
                  <td className="py-3 text-muted">{diffLabel(snapshot.diff_summary)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </InfoPanel>
  );
}

function ReadOnlyPanel({
  profile,
  lastTask,
  configTaskRunning
}: {
  profile: DeviceProfile | null;
  lastTask: TaskRead | null;
  configTaskRunning: boolean;
}) {
  return (
    <InfoPanel icon={<ShieldCheck />} title="Boundary">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Metric label="Full config" value={String(profile?.safety_summary.exposes_full_config ?? false)} />
          <Metric label="Credentials" value={String(profile?.safety_summary.exposes_credentials ?? false)} />
        </div>
        {configTaskRunning ? (
          <div className="rounded border border-info/20 bg-info/10 p-3 text-sm text-info">
            Collection task in progress
          </div>
        ) : null}
        {lastTask ? (
          <div className="rounded border border-warm bg-paper p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <FieldLabel>Last submitted</FieldLabel>
              <StatusBadge status={lastTask.status} />
            </div>
            <p className="break-all font-mono text-xs text-muted">{lastTask.task_id}</p>
          </div>
        ) : null}
      </div>
    </InfoPanel>
  );
}

function RecentTasks({ tasks }: { tasks: DeviceProfile["recent_tasks"] }) {
  return (
    <InfoPanel icon={<ListRestart />} title="Recent Tasks">
      {tasks.length === 0 ? (
        <EmptyState icon={<ListRestart className="h-6 w-6" />} title="No recent tasks" />
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <div key={task.task_id} className="rounded border border-warm bg-paper p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-mono text-xs">{task.task_type}</p>
                  <p className="mt-1 text-xs text-muted">{formatDate(task.updated_at)}</p>
                </div>
                <StatusBadge status={task.status} />
              </div>
              {task.status === "failed" ? (
                <p className="mt-2 text-xs text-error">
                  {task.error_code}: {task.error_message}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </InfoPanel>
  );
}

function InfoPanel({
  icon,
  title,
  children
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded border border-warm bg-surface/70 p-4">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-accent [&_svg]:h-4 [&_svg]:w-4">{icon}</span>
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <FieldLabel>{label}</FieldLabel>
      <p className="mt-1 truncate text-sm text-ink">{value}</p>
    </div>
  );
}

function CodeList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted">{empty}</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="max-w-full truncate rounded border border-warm bg-paper px-2 py-1 font-mono text-[11px] text-muted"
          title={item}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function DeviceListSkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2].map((item) => (
        <div key={item} className="h-24 animate-pulse rounded border border-warm bg-paper" />
      ))}
    </div>
  );
}

function PanelSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {[0, 1].map((item) => (
        <div key={item} className="h-44 animate-pulse rounded border border-warm bg-surface" />
      ))}
    </div>
  );
}

function ErrorPanel({ message, onRetry }: { message: string | null; onRetry: () => void }) {
  return (
    <div className="rounded border border-error/25 bg-error/10 p-4 text-error">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p className="break-words text-sm">{message ?? "Request failed"}</p>
        </div>
        <Button onClick={onRetry} className="h-8 bg-paper text-error">
          Retry
        </Button>
      </div>
    </div>
  );
}

function summaryValue(summary: Record<string, unknown> | undefined) {
  if (!summary) {
    return "-";
  }
  if (typeof summary.capability_count === "number") {
    return `${summary.capability_count} caps`;
  }
  return "ready";
}

function digestShort(digest: string | undefined) {
  if (!digest) {
    return "-";
  }
  return digest.replace("sha256:", "").slice(0, 12);
}

function diffLabel(diff: Record<string, unknown>) {
  if (diff.previous_snapshot_id === null) {
    return "first snapshot";
  }
  return diff.changed ? "changed" : "unchanged";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function errorMessage(caught: unknown) {
  return caught instanceof Error ? caught.message : "Request failed";
}
