"use client";

import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  CheckCircle,
  ClipboardList,
  Database,
  FileClock,
  FilePenLine,
  Gauge,
  HardDrive,
  KeyRound,
  ListRestart,
  Maximize2,
  Minimize2,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  Router,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
  XCircle
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { LoginView, SessionHeader } from "@/components/auth";
import { Button, DatastoreSelect, EmptyState, FieldLabel, StatusBadge } from "@/components/ui";
import { api, formatApiError, formatRollbackBlocker } from "@/lib/api";
import { useSession } from "@/lib/session";
import type {
  AuditLogRead,
  ChangePreflightResponse,
  ChangeRequestRead,
  ChangeRiskSummary,
  ConfigSnapshot,
  Device,
  DeviceProfile,
  Permission,
  Role,
  SnapshotListResponse,
  TaskRead,
  UserRead
} from "@/lib/types";
import { PERM } from "@/lib/types";
import { cn } from "@/lib/utils";

type LoadState = "idle" | "loading" | "loaded" | "error";
type Tab = "devices" | "changes" | "admin" | "audit";
type DeviceListMode = "collapsed" | "compact" | "expanded";
type DeviceDetailMode = "operational" | "config";

export default function OperationsConsole() {
  const { state } = useSession();

  if (state === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        Loading…
      </div>
    );
  }

  if (state === "unauthenticated") {
    return <LoginView />;
  }

  return <AuthenticatedConsole />;
}

function AuthenticatedConsole() {
  const { hasPermission } = useSession();

  const tabs: { id: Tab; label: string; icon: React.ReactNode; perm: string }[] = [
    { id: "devices", label: "Devices", icon: <Router className="h-4 w-4" />, perm: PERM.DEVICE_READ },
    {
      id: "changes",
      label: "Changes",
      icon: <ClipboardList className="h-4 w-4" />,
      perm: PERM.DEVICE_CHANGE_SUBMIT
    },
    { id: "admin", label: "Admin", icon: <Users className="h-4 w-4" />, perm: PERM.USER_MANAGE },
    {
      id: "audit",
      label: "Audit",
      icon: <FileClock className="h-4 w-4" />,
      perm: PERM.AUDIT_READ_SUMMARY
    }
  ];

  const availableTabs = tabs.filter(({ perm }) => hasPermission(perm));
  const [tab, setTab] = useState<Tab>(() => availableTabs[0]?.id ?? "devices");

  return (
    <main className="flex min-h-screen min-h-dvh flex-col text-ink">
      {/* App bar */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-warm bg-canvas/95 px-4">
        <div className="flex items-center gap-4">
          <div>
            <p className="font-mono text-[11px] uppercase text-muted">Star Pulse</p>
          </div>
          <nav className="flex gap-1">
            {tabs.map(({ id, label, icon, perm }) =>
              hasPermission(perm) ? (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded px-3 py-1.5 text-sm transition",
                    tab === id
                      ? "bg-paper font-semibold text-ink"
                      : "text-muted hover:text-ink"
                  )}
                >
                  {icon}
                  {label}
                </button>
              ) : null
            )}
          </nav>
        </div>
        <SessionHeader />
      </div>

      <div className="min-h-0 flex-1 p-2 md:p-3">
        {availableTabs.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-20 text-center">
            <KeyRound className="h-8 w-8 text-muted" />
            <p className="text-sm text-muted">您的账号尚未分配任何权限。</p>
            <p className="text-xs text-muted">请联系管理员分配角色后重新登录。</p>
          </div>
        ) : (
          <>
            {tab === "devices" && hasPermission(PERM.DEVICE_READ) && <DevicesTab />}
            {tab === "changes" && hasPermission(PERM.DEVICE_CHANGE_SUBMIT) && <ChangesTab />}
            {tab === "admin" && hasPermission(PERM.USER_MANAGE) && <AdminTab />}
            {tab === "audit" && hasPermission(PERM.AUDIT_READ_SUMMARY) && <AuditTab />}
          </>
        )}
      </div>
    </main>
  );
}

// ── Devices Tab ────────────────────────────────────────────────────────────

function DevicesTab() {
  const { hasPermission } = useSession();
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);
  const [profile, setProfile] = useState<DeviceProfile | null>(null);
  const [snapshots, setSnapshots] = useState<ConfigSnapshot[]>([]);
  const [datastore, setDatastore] = useState("running");
  const [lastTask, setLastTask] = useState<TaskRead | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [listMode, setListMode] = useState<DeviceListMode>("compact");
  const [detailMode, setDetailMode] = useState<DeviceDetailMode>("operational");
  const [deviceQuery, setDeviceQuery] = useState("");
  const [selectedObjectPath, setSelectedObjectPath] = useState("root");
  const [changeSummary, setChangeSummary] = useState("");
  const [changeReason, setChangeReason] = useState("");
  const [configBody, setConfigBody] = useState("");
  const [leafDrafts, setLeafDrafts] = useState<Record<string, string>>({});
  const [preflight, setPreflight] = useState<ChangePreflightResponse | null>(null);
  const [devicesState, setDevicesState] = useState<LoadState>("idle");
  const [profileState, setProfileState] = useState<LoadState>("idle");
  const [submitState, setSubmitState] = useState<LoadState>("idle");
  const [changeSubmitState, setChangeSubmitState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);

  const selectedDevice = useMemo(
    () => devices.find((d) => d.id === selectedDeviceId) ?? null,
    [devices, selectedDeviceId]
  );

  const filteredDevices = useMemo(() => {
    const query = deviceQuery.trim().toLowerCase();
    if (!query) return devices;
    return devices.filter((device) => {
      const connection = device.connection;
      return [
        device.name,
        device.status,
        device.group,
        device.serial_number,
        connection?.host,
        connection?.protocol,
        String(connection?.port ?? "")
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    });
  }, [deviceQuery, devices]);

  const loadDevices = useCallback(async () => {
    setDevicesState("loading");
    setError(null);
    try {
      const items = await api.listDevices();
      setDevices(items);
      setSelectedDeviceId((cur) => cur ?? items[0]?.id ?? null);
      setDevicesState("loaded");
    } catch (e) {
      setDevicesState("error");
      setError(errorMessage(e));
    }
  }, []);

  const loadProfile = useCallback(async (deviceId: number) => {
    setProfileState("loading");
    setError(null);
    try {
      const [prof, snap]: [DeviceProfile, SnapshotListResponse] = await Promise.all([
        api.getProfile(deviceId),
        api.listSnapshots(deviceId, 20)
      ]);
      setProfile(prof);
      setSnapshots(snap.items);
      setProfileState("loaded");
    } catch (e) {
      setProfileState("error");
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    void loadDevices();
  }, [loadDevices]);

  useEffect(() => {
    if (selectedDeviceId !== null) void loadProfile(selectedDeviceId);
    else { setProfile(null); setSnapshots([]); }
    setSelectedObjectPath("root");
    setPreflight(null);
    setLeafDrafts({});
  }, [loadProfile, selectedDeviceId]);

  const configTaskRunning = profile?.recent_tasks.some(
    (t) => t.task_type === "device.config_snapshot" && (t.status === "queued" || t.status === "running")
  );

  const canCollect = hasPermission(PERM.DEVICE_COLLECT);
  const canManage = hasPermission(PERM.DEVICE_MANAGE);
  const canSubmitChange = hasPermission(PERM.DEVICE_CHANGE_SUBMIT);
  const readyForChange = Boolean(profile?.onboarding_summary?.ready_for_change);

  async function submitSnapshot() {
    if (!selectedDeviceId || configTaskRunning || !canCollect) return;
    setSubmitState("loading");
    setError(null);
    try {
      const task = await api.collectSnapshot(selectedDeviceId, datastore);
      setLastTask(task);
      await loadProfile(selectedDeviceId);
      setSubmitState("loaded");
    } catch (e) {
      setSubmitState("error");
      setError(errorMessage(e));
    }
  }

  async function previewConfigChange() {
    if (!selectedDeviceId || !canSubmitChange) return;
    setChangeSubmitState("loading");
    setError(null);
    try {
      const result = await api.previewChangePreflight({
        device_id: selectedDeviceId,
        datastore,
        change_summary: changeSummary,
        config_body: configBody,
        reason: changeReason
      });
      setPreflight(result);
      setChangeSubmitState("loaded");
    } catch (e) {
      setChangeSubmitState("error");
      setError(errorMessage(e));
    }
  }

  async function submitConfigChange() {
    if (!selectedDeviceId || !canSubmitChange) return;
    if (!preflight?.passed) {
      await previewConfigChange();
      return;
    }
    setChangeSubmitState("loading");
    setError(null);
    try {
      await api.submitChangeRequest({
        device_id: selectedDeviceId,
        datastore,
        change_summary: changeSummary,
        config_body: configBody,
        reason: changeReason
      });
      setChangeSummary("");
      setChangeReason("");
      setConfigBody("");
      setLeafDrafts({});
      setPreflight(null);
      await loadProfile(selectedDeviceId);
      setChangeSubmitState("loaded");
    } catch (e) {
      setChangeSubmitState("error");
      setError(errorMessage(e));
    }
  }

  return (
    <div
      className={cn(
        "grid h-full min-h-0 w-full grid-rows-[minmax(12rem,32dvh)_minmax(0,1fr)] gap-2 lg:grid-rows-none xl:gap-3",
        listMode === "collapsed" && "lg:grid-cols-[64px_minmax(0,1fr)]",
        listMode === "compact" && "lg:grid-cols-[clamp(320px,24vw,440px)_minmax(0,1fr)]",
        listMode === "expanded" && "lg:grid-cols-[minmax(720px,76vw)_minmax(360px,1fr)]"
      )}
    >
      <DeviceInventoryPane
        mode={listMode}
        devices={filteredDevices}
        allDeviceCount={devices.length}
        selectedDeviceId={selectedDeviceId}
        query={deviceQuery}
        showCreate={showCreate}
        canManage={canManage}
        loading={devicesState === "loading"}
        error={devicesState === "error" ? error : null}
        onModeChange={setListMode}
        onQueryChange={setDeviceQuery}
        onToggleCreate={() => setShowCreate((value) => !value)}
        onRefresh={() => void loadDevices()}
        onSelect={setSelectedDeviceId}
        onCreateSuccess={async (deviceId) => {
          setShowCreate(false);
          await loadDevices();
          setSelectedDeviceId(deviceId);
        }}
      />

      <section className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded border border-warm bg-canvas/95">
        {selectedDevice === null && devicesState !== "loading" ? (
          <div className="flex min-h-0 flex-1 items-center justify-center p-4">
            <EmptyState icon={<HardDrive className="h-6 w-6" />} title="Select a device" />
          </div>
        ) : null}

        {selectedDevice !== null ? (
          <DeviceWorkspace
            device={selectedDevice}
            profile={profile}
            snapshots={snapshots}
            datastore={datastore}
            detailMode={detailMode}
            selectedPath={selectedObjectPath}
            loading={profileState === "loading"}
            error={error}
            canCollect={canCollect}
            canSubmitChange={canSubmitChange}
            canApprove={hasPermission(PERM.DEVICE_CHANGE_APPROVE)}
            readyForChange={readyForChange}
            submitBusy={submitState === "loading"}
            changeBusy={changeSubmitState === "loading"}
            configTaskRunning={Boolean(configTaskRunning)}
            lastTask={lastTask}
            changeSummary={changeSummary}
            changeReason={changeReason}
            configBody={configBody}
            leafDrafts={leafDrafts}
            preflight={preflight}
            onDetailModeChange={setDetailMode}
            onDatastoreChange={setDatastore}
            onRefresh={() => void loadProfile(selectedDevice.id)}
            onCollect={() => void submitSnapshot()}
            onSelectPath={setSelectedObjectPath}
            onChangeSummaryChange={(value) => {
              setChangeSummary(value);
              setPreflight(null);
            }}
            onChangeReasonChange={(value) => {
              setChangeReason(value);
              setPreflight(null);
            }}
            onConfigBodyChange={(value) => {
              setConfigBody(value);
              setPreflight(null);
            }}
            onLeafDraftChange={(path, value) => {
              setLeafDrafts((current) => ({ ...current, [path]: value }));
              setPreflight(null);
            }}
            onPreviewChange={() => void previewConfigChange()}
            onSubmitChange={() => void submitConfigChange()}
            onRollbackSuccess={() => { void loadProfile(selectedDeviceId!); }}
          />
        ) : null}
      </section>
    </div>
  );
}

function DeviceInventoryPane({
  mode,
  devices,
  allDeviceCount,
  selectedDeviceId,
  query,
  showCreate,
  canManage,
  loading,
  error,
  onModeChange,
  onQueryChange,
  onToggleCreate,
  onRefresh,
  onSelect,
  onCreateSuccess
}: {
  mode: DeviceListMode;
  devices: Device[];
  allDeviceCount: number;
  selectedDeviceId: number | null;
  query: string;
  showCreate: boolean;
  canManage: boolean;
  loading: boolean;
  error: string | null;
  onModeChange: (mode: DeviceListMode) => void;
  onQueryChange: (query: string) => void;
  onToggleCreate: () => void;
  onRefresh: () => void;
  onSelect: (deviceId: number) => void;
  onCreateSuccess: (deviceId: number) => Promise<void>;
}) {
  if (mode === "collapsed") {
    const selected = devices.find((device) => device.id === selectedDeviceId);
    return (
      <aside className="flex min-h-0 flex-col items-center gap-2 rounded border border-warm bg-canvas/95 py-3">
        <Button
          aria-label="Expand device list"
          title="Expand device list"
          onClick={() => onModeChange("compact")}
          className="h-9 w-9 px-0"
        >
          <PanelLeftOpen className="h-4 w-4" aria-hidden />
        </Button>
        <Button
          aria-label="Open full device list"
          title="Open full device list"
          onClick={() => onModeChange("expanded")}
          className="h-9 w-9 px-0 bg-paper"
        >
          <Maximize2 className="h-4 w-4" aria-hidden />
        </Button>
        <div className="my-1 h-px w-8 bg-warm" />
        <Button
          aria-label="Refresh devices"
          title="Refresh devices"
          onClick={onRefresh}
          busy={loading}
          className="h-9 w-9 px-0"
        >
          <RefreshCw className="h-4 w-4" aria-hidden />
        </Button>
        <div className="mt-auto flex min-h-0 w-full flex-col items-center gap-2 px-2">
          <StatusBadge status={selected?.status ?? "idle"} />
          <span className="font-mono text-[10px] text-muted">#{selectedDeviceId ?? "-"}</span>
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex min-h-0 flex-col rounded border border-warm bg-canvas/95">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-warm px-4">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">Device Inventory</h2>
          <p className="font-mono text-[11px] text-muted">{devices.length}/{allDeviceCount} visible</p>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            aria-label="Collapse device list"
            title="Collapse device list"
            onClick={() => onModeChange("collapsed")}
            className="h-9 w-9 px-0 bg-paper"
          >
            <PanelLeftClose className="h-4 w-4" aria-hidden />
          </Button>
          <Button
            aria-label={mode === "expanded" ? "Compact device list" : "Expand device list"}
            title={mode === "expanded" ? "Compact device list" : "Expand device list"}
            onClick={() => onModeChange(mode === "expanded" ? "compact" : "expanded")}
            className="h-9 w-9 px-0"
          >
            {mode === "expanded" ? (
              <Minimize2 className="h-4 w-4" aria-hidden />
            ) : (
              <Maximize2 className="h-4 w-4" aria-hidden />
            )}
          </Button>
          {canManage ? (
            <Button
              aria-label="Add device"
              title="Add device"
              onClick={onToggleCreate}
              className="h-9 w-9 px-0"
            >
              <Plus className="h-4 w-4" aria-hidden />
            </Button>
          ) : null}
          <Button
            aria-label="Refresh devices"
            title="Refresh devices"
            onClick={onRefresh}
            busy={loading}
            className="h-9 w-9 px-0"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </div>

      <div className="border-b border-warm p-3">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-muted" aria-hidden />
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search name, host, group, status"
            className="h-9 w-full rounded border border-warm bg-paper pl-8 pr-2 text-sm outline-none transition focus:border-warm-strong"
          />
        </label>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-3">
        {showCreate && canManage ? <CreateDeviceForm onSuccess={onCreateSuccess} /> : null}
        {loading ? <DeviceListSkeleton /> : null}
        {error ? <ErrorPanel message={error} onRetry={onRefresh} /> : null}
        {!loading && !error && allDeviceCount === 0 ? (
          <EmptyState icon={<Router className="h-6 w-6" />} title="No devices registered" />
        ) : null}
        {!loading && !error && allDeviceCount > 0 && devices.length === 0 ? (
          <EmptyState icon={<Search className="h-6 w-6" />} title="No matching devices" />
        ) : null}
        {devices.length > 0 && mode === "compact" ? (
          <div className="space-y-2">
            {devices.map((device) => (
              <DeviceListItem
                key={device.id}
                device={device}
                active={device.id === selectedDeviceId}
                onSelect={() => onSelect(device.id)}
              />
            ))}
          </div>
        ) : null}
        {devices.length > 0 && mode === "expanded" ? (
          <DeviceInventoryTable
            devices={devices}
            selectedDeviceId={selectedDeviceId}
            onSelect={onSelect}
          />
        ) : null}
      </div>
    </aside>
  );
}

function DeviceInventoryTable({
  devices,
  selectedDeviceId,
  onSelect
}: {
  devices: Device[];
  selectedDeviceId: number | null;
  onSelect: (deviceId: number) => void;
}) {
  return (
    <div className="overflow-x-auto rounded border border-warm">
      <table className="w-full min-w-[1180px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-warm bg-paper/70 text-left font-mono text-[11px] uppercase text-muted">
            <th className="px-3 py-2 font-medium">Device</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Endpoint</th>
            <th className="px-3 py-2 font-medium">Access</th>
            <th className="px-3 py-2 font-medium">Discovery</th>
            <th className="px-3 py-2 font-medium">Onboarding</th>
            <th className="px-3 py-2 font-medium">Baseline</th>
            <th className="px-3 py-2 font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => {
            const connection = device.connection;
            const discovery = device.last_discovery;
            const onboarding = device.onboarding_summary;
            return (
              <tr
                key={device.id}
                onClick={() => onSelect(device.id)}
                className={cn(
                  "cursor-pointer border-b border-warm/70 transition last:border-0 hover:bg-paper",
                  device.id === selectedDeviceId && "bg-surface-soft"
                )}
              >
                <td className="px-3 py-3">
                  <p className="max-w-[220px] truncate font-semibold">{device.name}</p>
                  <p className="mt-1 font-mono text-[11px] text-muted">#{device.id} · {device.group ?? "ungrouped"}</p>
                  <p className="mt-1 truncate font-mono text-[11px] text-muted">
                    SN {device.serial_number ?? "-"}
                  </p>
                </td>
                <td className="px-3 py-3"><StatusBadge status={device.status} /></td>
                <td className="px-3 py-3 font-mono text-xs text-muted">
                  {connection
                    ? `${connection.protocol}://${connection.host}:${connection.port}`
                    : "-"}
                </td>
                <td className="px-3 py-3 text-xs text-muted">
                  <p className="font-mono">{connection?.username ?? "-"}</p>
                  <p className="mt-1">{connection?.has_credential ? "credential referenced" : "credential missing"}</p>
                </td>
                <td className="px-3 py-3 text-xs text-muted">
                  <p>{discovery ? `${discovery.capabilities.length} caps` : "-"}</p>
                  <p className="mt-1">{discovery ? `${Object.keys(discovery.system_info).length} system keys` : "-"}</p>
                  <p className="mt-1">{discovery ? formatDate(discovery.discovered_at) : "-"}</p>
                </td>
                <td className="px-3 py-3 text-xs text-muted">
                  <div className="mb-2">
                    <StatusBadge status={onboarding ? (onboarding.ready_for_change ? "ready" : "blocked") : "not_started"} />
                  </div>
                  <p>{onboardingSteps(onboarding)}</p>
                  <p className="mt-1 truncate" title={onboardingDetail(onboarding)}>
                    {onboardingDetail(onboarding)}
                  </p>
                </td>
                <td className="px-3 py-3 text-xs text-muted">
                  <p className="font-mono">{digestShort(device.last_config_snapshot?.content_digest)}</p>
                  <p className="mt-1">{device.last_config_snapshot ? formatDate(device.last_config_snapshot.collected_at) : "-"}</p>
                </td>
                <td className="px-3 py-3 text-xs text-muted">{formatDate(device.updated_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DeviceWorkspace({
  device,
  profile,
  snapshots,
  datastore,
  detailMode,
  selectedPath,
  loading,
  error,
  canCollect,
  canSubmitChange,
  canApprove,
  readyForChange,
  submitBusy,
  changeBusy,
  configTaskRunning,
  lastTask,
  changeSummary,
  changeReason,
  configBody,
  leafDrafts,
  preflight,
  onDetailModeChange,
  onDatastoreChange,
  onRefresh,
  onCollect,
  onSelectPath,
  onChangeSummaryChange,
  onChangeReasonChange,
  onConfigBodyChange,
  onLeafDraftChange,
  onPreviewChange,
  onSubmitChange,
  onRollbackSuccess
}: {
  device: Device;
  profile: DeviceProfile | null;
  snapshots: ConfigSnapshot[];
  datastore: string;
  detailMode: DeviceDetailMode;
  selectedPath: string;
  loading: boolean;
  error: string | null;
  canCollect: boolean;
  canSubmitChange: boolean;
  canApprove: boolean;
  readyForChange: boolean;
  submitBusy: boolean;
  changeBusy: boolean;
  configTaskRunning: boolean;
  lastTask: TaskRead | null;
  changeSummary: string;
  changeReason: string;
  configBody: string;
  leafDrafts: Record<string, string>;
  preflight: ChangePreflightResponse | null;
  onDetailModeChange: (mode: DeviceDetailMode) => void;
  onDatastoreChange: (datastore: string) => void;
  onRefresh: () => void;
  onCollect: () => void;
  onSelectPath: (path: string) => void;
  onChangeSummaryChange: (value: string) => void;
  onChangeReasonChange: (value: string) => void;
  onConfigBodyChange: (value: string) => void;
  onLeafDraftChange: (path: string, value: string) => void;
  onPreviewChange: () => void;
  onSubmitChange: () => void;
  onRollbackSuccess: () => void;
}) {
  const operationalTree = useMemo(
    () => buildOperationalTree(device, profile, snapshots, lastTask),
    [device, lastTask, profile, snapshots]
  );
  const configTree = useMemo(
    () =>
      buildConfigTree({
        device,
        profile,
        datastore,
        snapshots,
        changeSummary,
        changeReason,
        configBody,
        leafDrafts,
        preflight
      }),
    [changeReason, changeSummary, configBody, datastore, device, leafDrafts, preflight, profile, snapshots]
  );
  const modeDisabledReason = readyForChange
    ? null
    : profile?.onboarding_summary?.blockers.join(", ") || "device onboarding is incomplete";

  function editTreeLeaf(path: string, value: string) {
    if (path.endsWith(".change_summary")) onChangeSummaryChange(value);
    else if (path.endsWith(".reason")) onChangeReasonChange(value);
    else if (path.endsWith(".config_body")) onConfigBodyChange(value);
    else onLeafDraftChange(path, value);
  }

  return (
    <>
      <header className="shrink-0 border-b border-warm px-4 py-3">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={profile?.status ?? device.status} />
              <span className="font-mono text-[11px] text-muted">{device.group ?? "ungrouped"}</span>
              <span className="font-mono text-[11px] text-muted">#{device.id}</span>
            </div>
            <h2 className="truncate text-2xl font-semibold">{device.name}</h2>
            <p className="mt-1 truncate font-mono text-xs text-muted">
              {device.connection
                ? `${device.connection.protocol}://${device.connection.host}:${device.connection.port}`
                : "connection unavailable"}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded border border-warm bg-paper p-1">
              <button
                onClick={() => onDetailModeChange("operational")}
                className={cn(
                  "inline-flex h-8 items-center gap-1.5 rounded px-2 text-xs font-medium transition",
                  detailMode === "operational" ? "bg-canvas text-ink shadow-panel" : "text-muted hover:text-ink"
                )}
              >
                <Gauge className="h-3.5 w-3.5" aria-hidden />
                NETCONF get
              </button>
              <button
                onClick={() => onDetailModeChange("config")}
                className={cn(
                  "inline-flex h-8 items-center gap-1.5 rounded px-2 text-xs font-medium transition",
                  detailMode === "config" ? "bg-canvas text-ink shadow-panel" : "text-muted hover:text-ink"
                )}
              >
                <FilePenLine className="h-3.5 w-3.5" aria-hidden />
                edit-config
              </button>
            </div>
            <DatastoreSelect value={datastore} onValueChange={onDatastoreChange} />
            <Button
              onClick={onCollect}
              disabled={!canCollect || submitBusy || configTaskRunning}
              busy={submitBusy}
              title={!canCollect ? "Requires device:collect permission" : undefined}
            >
              <Database className="h-4 w-4" aria-hidden />
              Collect
            </Button>
            <Button
              aria-label="Refresh profile"
              title="Refresh profile"
              onClick={onRefresh}
              busy={loading}
              className="h-9 w-9 px-0"
            >
              <RefreshCw className="h-4 w-4" aria-hidden />
            </Button>
          </div>
        </div>
      </header>

      {error ? (
        <div className="px-4 pt-4">
          <ErrorPanel message={error} onRetry={onRefresh} />
        </div>
      ) : null}

      {detailMode === "operational" ? (
        <div className="grid min-h-0 flex-1 gap-3 overflow-auto p-3 xl:grid-cols-[minmax(0,1fr)_clamp(320px,27vw,440px)]">
          <InfoPanel icon={<Settings2 />} title="NETCONF Object Tree">
            <ObjectTree
              data={operationalTree}
              selectedPath={selectedPath}
              onSelectPath={onSelectPath}
            />
          </InfoPanel>
          <aside className="space-y-3">
            <ReadOnlyPanel
              profile={profile}
              lastTask={lastTask}
              configTaskRunning={configTaskRunning}
            />
            <SnapshotTable
              snapshots={snapshots}
              canSubmitChange={canSubmitChange}
              canApprove={canApprove}
              deviceId={device.id}
              onStartChange={(snapshot) => onDatastoreChange(snapshot.datastore)}
              onRollbackSuccess={onRollbackSuccess}
            />
            <RecentTasks tasks={profile?.recent_tasks ?? []} />
          </aside>
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 gap-3 overflow-auto p-3 xl:grid-cols-[minmax(0,1fr)_clamp(360px,32vw,520px)]">
          <InfoPanel icon={<Settings2 />} title="Config Model Tree">
            <ObjectTree
              data={configTree}
              selectedPath={selectedPath}
              editable
              onSelectPath={onSelectPath}
              onLeafChange={editTreeLeaf}
              editablePath={(path) =>
                path.includes(".change_request.") || path.includes(".candidate_configuration.")
              }
            />
          </InfoPanel>
          <ConfigEditPanel
            device={device}
            datastore={datastore}
            canSubmitChange={canSubmitChange}
            disabledReason={modeDisabledReason}
            busy={changeBusy}
            changeSummary={changeSummary}
            changeReason={changeReason}
            configBody={configBody}
            preflight={preflight}
            onChangeSummaryChange={onChangeSummaryChange}
            onChangeReasonChange={onChangeReasonChange}
            onConfigBodyChange={onConfigBodyChange}
            onPreview={onPreviewChange}
            onSubmit={onSubmitChange}
          />
        </div>
      )}
    </>
  );
}

function ConfigEditPanel({
  device,
  datastore,
  canSubmitChange,
  disabledReason,
  busy,
  changeSummary,
  changeReason,
  configBody,
  preflight,
  onChangeSummaryChange,
  onChangeReasonChange,
  onConfigBodyChange,
  onPreview,
  onSubmit
}: {
  device: Device;
  datastore: string;
  canSubmitChange: boolean;
  disabledReason: string | null;
  busy: boolean;
  changeSummary: string;
  changeReason: string;
  configBody: string;
  preflight: ChangePreflightResponse | null;
  onChangeSummaryChange: (value: string) => void;
  onChangeReasonChange: (value: string) => void;
  onConfigBodyChange: (value: string) => void;
  onPreview: () => void;
  onSubmit: () => void;
}) {
  const blocked = !canSubmitChange || Boolean(disabledReason);
  const missingRequired = !changeSummary.trim() || !changeReason.trim() || !configBody.trim();
  return (
    <InfoPanel icon={<FilePenLine />} title="Change Control">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Metric label="Device" value={`#${device.id}`} />
          <Metric label="Datastore" value={datastore} />
        </div>
        <div>
          <FieldLabel>Change summary</FieldLabel>
          <input
            value={changeSummary}
            onChange={(event) => onChangeSummaryChange(event.target.value)}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm outline-none focus:border-warm-strong"
          />
        </div>
        <div>
          <FieldLabel>Reason</FieldLabel>
          <textarea
            value={changeReason}
            onChange={(event) => onChangeReasonChange(event.target.value)}
            rows={3}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm outline-none focus:border-warm-strong"
          />
        </div>
        <div>
          <FieldLabel>NETCONF payload</FieldLabel>
          <textarea
            value={configBody}
            onChange={(event) => onConfigBodyChange(event.target.value)}
            rows={12}
            spellCheck={false}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 font-mono text-xs outline-none focus:border-warm-strong"
          />
        </div>
        {preflight ? <PreflightSummary preflight={preflight} compact /> : null}
        {!canSubmitChange ? <p className="text-xs text-warn">Requires device change submission permission.</p> : null}
        {disabledReason ? <p className="text-xs text-warn">{disabledReason}</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={onPreview}
            busy={busy}
            disabled={blocked || missingRequired || busy}
          >
            <Sparkles className="h-4 w-4" aria-hidden />
            Preview
          </Button>
          <Button
            onClick={onSubmit}
            busy={busy}
            disabled={blocked || missingRequired || busy || !preflight?.passed}
          >
            <Send className="h-4 w-4" aria-hidden />
            Submit
          </Button>
        </div>
      </div>
    </InfoPanel>
  );
}

function ObjectTree({
  data,
  selectedPath,
  editable = false,
  onSelectPath,
  onLeafChange,
  editablePath
}: {
  data: unknown;
  selectedPath: string;
  editable?: boolean;
  onSelectPath: (path: string) => void;
  onLeafChange?: (path: string, value: string) => void;
  editablePath?: (path: string) => boolean;
}) {
  const [openPaths, setOpenPaths] = useState<Set<string>>(
    () => new Set(["root", "root.netconf_get", "root.netconf_edit_config"])
  );

  function toggle(path: string) {
    setOpenPaths((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function expandAll() {
    const paths = new Set<string>();
    collectObjectPaths(data, "root", paths);
    setOpenPaths(paths);
  }

  function collapseAll() {
    setOpenPaths(new Set(["root"]));
  }

  return (
    <div className="min-h-0">
      <div className="mb-3 flex items-center justify-between gap-2 border-b border-warm pb-3">
        <div className="min-w-0">
          <p className="truncate font-mono text-[11px] text-muted">{selectedPath}</p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <Button aria-label="Expand all" title="Expand all" onClick={expandAll} className="h-8 w-8 px-0 bg-paper">
            <ChevronsRight className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <Button aria-label="Collapse all" title="Collapse all" onClick={collapseAll} className="h-8 w-8 px-0 bg-paper">
            <ChevronsLeft className="h-3.5 w-3.5" aria-hidden />
          </Button>
        </div>
      </div>
      <div className="max-h-[64dvh] overflow-auto rounded border border-warm bg-paper/70 p-2">
        <TreeRows
          label="root"
          value={data}
          path="root"
          depth={0}
          openPaths={openPaths}
          selectedPath={selectedPath}
          editable={editable}
          editablePath={editablePath}
          onToggle={toggle}
          onSelectPath={onSelectPath}
          onLeafChange={onLeafChange}
        />
      </div>
    </div>
  );
}

function TreeRows({
  label,
  value,
  path,
  depth,
  openPaths,
  selectedPath,
  editable,
  editablePath,
  onToggle,
  onSelectPath,
  onLeafChange
}: {
  label: string;
  value: unknown;
  path: string;
  depth: number;
  openPaths: Set<string>;
  selectedPath: string;
  editable: boolean;
  editablePath?: (path: string) => boolean;
  onToggle: (path: string) => void;
  onSelectPath: (path: string) => void;
  onLeafChange?: (path: string, value: string) => void;
}) {
  const objectLike = isObjectLike(value);
  const open = openPaths.has(path);
  const entries = objectLike ? objectEntries(value) : [];
  const leafEditable = editable && !objectLike && (editablePath ? editablePath(path) : true);

  return (
    <div>
      <div
        className={cn(
          "grid min-h-9 grid-cols-[minmax(180px,0.8fr)_minmax(180px,1.2fr)] items-center gap-3 rounded px-2 text-sm transition",
          selectedPath === path ? "bg-canvas" : "hover:bg-canvas/70"
        )}
        style={{ paddingLeft: `${8 + depth * 18}px` }}
      >
        <button
          type="button"
          onClick={() => {
            onSelectPath(path);
            if (objectLike) onToggle(path);
          }}
          className="flex min-w-0 items-center gap-1.5 text-left"
        >
          {objectLike ? (
            open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />
          ) : (
            <span className="h-3.5 w-3.5 shrink-0" />
          )}
          <span className="truncate font-medium">{label}</span>
          <span className="shrink-0 rounded border border-warm bg-paper px-1.5 font-mono text-[10px] uppercase text-muted">
            {treeType(value)}
          </span>
        </button>
        <div className="min-w-0">
          {leafEditable ? (
            <input
              value={formatTreeValue(value)}
              onChange={(event) => onLeafChange?.(path, event.target.value)}
              className="h-8 w-full rounded border border-warm bg-canvas px-2 font-mono text-xs outline-none focus:border-warm-strong"
            />
          ) : (
            <p className="truncate font-mono text-xs text-muted" title={formatTreeValue(value)}>
              {objectLike ? `${entries.length} ${Array.isArray(value) ? "items" : "children"}` : formatTreeValue(value)}
            </p>
          )}
        </div>
      </div>
      {objectLike && open ? (
        <div>
          {entries.map(([childLabel, childValue]) => (
            <TreeRows
              key={`${path}.${childLabel}`}
              label={childLabel}
              value={childValue}
              path={`${path}.${childLabel}`}
              depth={depth + 1}
              openPaths={openPaths}
              selectedPath={selectedPath}
              editable={editable}
              editablePath={editablePath}
              onToggle={onToggle}
              onSelectPath={onSelectPath}
              onLeafChange={onLeafChange}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function buildOperationalTree(
  device: Device,
  profile: DeviceProfile | null,
  snapshots: ConfigSnapshot[],
  lastTask: TaskRead | null
) {
  const effectiveProfile = profile ?? device;
  return {
    netconf_get: {
      identity: {
        id: device.id,
        name: device.name,
        status: effectiveProfile.status,
        group: device.group,
        serial_number: effectiveProfile.serial_number
      },
      connection: sanitizeConnection(device.connection),
      server_capabilities: profile?.capabilities ?? device.last_discovery?.capabilities ?? [],
      yang_modules: parseYangCapabilities(profile?.capabilities ?? device.last_discovery?.capabilities ?? []),
      system_state: profile?.system_info ?? {},
      discovery: device.last_discovery,
      onboarding: profile?.onboarding_summary ?? device.onboarding_summary,
      config_snapshots: snapshots,
      recent_tasks: profile?.recent_tasks ?? device.recent_tasks,
      last_submitted_task: lastTask,
      safety: profile?.safety_summary ?? {}
    }
  };
}

function buildConfigTree({
  device,
  profile,
  datastore,
  snapshots,
  changeSummary,
  changeReason,
  configBody,
  leafDrafts,
  preflight
}: {
  device: Device;
  profile: DeviceProfile | null;
  datastore: string;
  snapshots: ConfigSnapshot[];
  changeSummary: string;
  changeReason: string;
  configBody: string;
  leafDrafts: Record<string, string>;
  preflight: ChangePreflightResponse | null;
}) {
  const latest = snapshots[0] ?? device.last_config_snapshot ?? null;
  return {
    netconf_edit_config: {
      target: {
        device_id: device.id,
        datastore,
        protocol: device.connection?.protocol ?? "netconf",
        endpoint: device.connection ? `${device.connection.host}:${device.connection.port}` : null
      },
      change_request: {
        change_summary: changeSummary,
        reason: changeReason
      },
      candidate_configuration: {
        config_body: configBody,
        edited_leaf_overrides: leafDrafts
      },
      model_context: {
        server_capabilities: profile?.capabilities ?? device.last_discovery?.capabilities ?? [],
        yang_modules: parseYangCapabilities(profile?.capabilities ?? device.last_discovery?.capabilities ?? []),
        latest_snapshot: latest,
        safety: profile?.safety_summary ?? {}
      },
      preflight: preflight ?? {
        status: "not_run",
        passed: false
      }
    }
  };
}

function sanitizeConnection(connection: Device["connection"]) {
  if (!connection) return null;
  return {
    protocol: connection.protocol,
    host: connection.host,
    port: connection.port,
    username: connection.username,
    credential: connection.has_credential ? "referenced" : "missing"
  };
}

function parseYangCapabilities(capabilities: string[]) {
  return capabilities.map((capability) => {
    const [base, query] = capability.split("?");
    const params = new URLSearchParams(query ?? "");
    const moduleName = params.get("module") ?? base.split(":").pop() ?? capability;
    return {
      module: moduleName,
      revision: params.get("revision"),
      namespace: base,
      features: params.get("features")?.split(",").filter(Boolean) ?? [],
      raw: capability
    };
  });
}

function isObjectLike(value: unknown): value is Record<string, unknown> | unknown[] {
  return value !== null && typeof value === "object";
}

function objectEntries(value: Record<string, unknown> | unknown[]) {
  if (Array.isArray(value)) return value.map((item, index) => [String(index), item] as const);
  return Object.entries(value);
}

function collectObjectPaths(value: unknown, path: string, paths: Set<string>) {
  if (!isObjectLike(value)) return;
  paths.add(path);
  for (const [label, child] of objectEntries(value)) {
    collectObjectPaths(child, `${path}.${label}`, paths);
  }
}

function treeType(value: unknown) {
  if (Array.isArray(value)) return "list";
  if (value === null) return "null";
  if (typeof value === "object") return "node";
  return typeof value;
}

function formatTreeValue(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

// ── Changes Tab ────────────────────────────────────────────────────────────

function ChangesTab() {
  const { hasPermission } = useSession();
  const [changes, setChanges] = useState<ChangeRequestRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canApprove = hasPermission(PERM.DEVICE_CHANGE_APPROVE);
  const canExecute = hasPermission(PERM.DEVICE_CHANGE_EXECUTE);
  const canSubmit = hasPermission(PERM.DEVICE_CHANGE_SUBMIT);

  const loadChanges = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.listChangeRequests();
      setChanges(resp.items);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadChanges();
  }, [loadChanges]);

  async function handleApprove(id: number) {
    try {
      await api.approveChangeRequest(id);
      await loadChanges();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function handleReject(id: number) {
    const note = window.prompt("Rejection reason:");
    if (!note) return;
    try {
      await api.rejectChangeRequest(id, note);
      await loadChanges();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function handleManualRollback(cr: ChangeRequestRead) {
    if (!cr.baseline_snapshot_id) {
      setError("No baseline snapshot is available for rollback.");
      return;
    }
    const reason = window.prompt("Rollback proposal reason:");
    if (!reason?.trim()) return;
    try {
      await api.submitRollback({
        device_id: cr.device_id,
        datastore: cr.datastore,
        change_summary: `Rollback proposal for change #${cr.id}`,
        reason,
        rollback_target_snapshot_id: cr.baseline_snapshot_id,
        rollback_of_change_id: cr.id
      });
      await loadChanges();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Change Requests</h2>
        <Button onClick={() => void loadChanges()} busy={loading} className="h-9 w-9 px-0">
          <RefreshCw className="h-4 w-4" aria-hidden />
        </Button>
      </div>

      {error ? <ErrorPanel message={error} onRetry={() => void loadChanges()} /> : null}

      {canSubmit ? (
        <InfoPanel icon={<Router />} title="Contextual Submission">
          <p className="text-sm text-muted">
            Open a device profile or snapshot to submit a normal change request.
          </p>
        </InfoPanel>
      ) : null}
      {canExecute && <DirectExecuteForm onSuccess={() => void loadChanges()} />}

      {changes.length === 0 && !loading ? (
        <EmptyState icon={<ClipboardList className="h-6 w-6" />} title="No change requests" />
      ) : null}

      <div className="space-y-3">
        {changes.map((cr) => (
          <div
            key={cr.id}
            id={`change-${cr.id}`}
            className="rounded border border-warm bg-canvas/95 p-4 scroll-mt-20"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={cr.status} />
                  {cr.direct_execute && (
                    <span className="rounded bg-warning/20 px-2 py-0.5 font-mono text-[11px] text-warning">
                      direct-execute
                    </span>
                  )}
                  {cr.is_rollback && (
                    <span className="rounded bg-info/20 px-2 py-0.5 font-mono text-[11px] text-info flex items-center gap-1">
                      <ListRestart className="h-3 w-3" /> rollback
                    </span>
                  )}
                  <span className="font-mono text-xs text-muted">#{cr.id}</span>
                </div>
                <p className="mt-1 text-sm font-semibold">{cr.change_summary}</p>
                <p className="mt-0.5 text-xs text-muted">
                  Device {cr.device_id} · {cr.datastore} · by{" "}
                  {cr.submitter?.display_name ?? "unknown"}
                </p>
                <p className="mt-0.5 text-xs text-muted">Reason: {cr.reason}</p>
                <div className="mt-2 grid gap-2 text-xs text-muted sm:grid-cols-3">
                  <Metric label="Approver" value={cr.approver?.display_name ?? "-"} />
                  <Metric label="Execution" value={cr.execution_task_id ?? "-"} />
                  <Metric label="Verification" value={cr.verification_status ?? "-"} />
                </div>
                <PreflightSummary preflight={changePreflightFromRequest(cr)} compact />
                {cr.verification_summary ? (
                  <p className="mt-2 text-xs text-muted">
                    {String(cr.verification_summary.error_message ?? "") ||
                      `Post-change snapshot ${cr.verification_snapshot_id ?? "-"}`}
                  </p>
                ) : null}

                {/* Rollback context card (Task 9.4) */}
                {cr.is_rollback && (
                  <div className="mt-3 rounded border border-info/30 bg-info/10 p-3 text-xs space-y-1">
                    <p className="font-semibold text-info flex items-center gap-1">
                      <ListRestart className="h-3.5 w-3.5" /> Rollback Context
                    </p>
                    {cr.rollback_of_change_id ? (
                      <p className="text-muted">
                        Origin change:{" "}
                        <a className="font-mono underline" href={`#change-${cr.rollback_of_change_id}`}>
                          #{cr.rollback_of_change_id}
                        </a>
                        {cr.rollback_of_change ? ` · ${cr.rollback_of_change.status}` : ""}
                      </p>
                    ) : null}
                    {cr.rollback_target_snapshot_id ? (
                      <p className="text-muted">Target snapshot: <span className="font-mono">#{cr.rollback_target_snapshot_id}</span>
                        {cr.rollback_target_snapshot ? ` · ${digestShort(cr.rollback_target_snapshot.content_digest)}` : ""}
                      </p>
                    ) : null}
                  </div>
                )}

                {/* verification_failed with pending proposal link (Task 9.3) */}
                {cr.status === "verification_failed" && !cr.is_rollback && cr.pending_rollback_proposal_id ? (
                  <div className="mt-3 rounded border border-warning/30 bg-warning/10 p-3 text-xs">
                    <p className="text-warning font-semibold flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" /> Verification failed — rollback proposed
                    </p>
                    <p className="mt-1 text-muted">
                      Auto-rollback proposal{" "}
                      <a
                        href={`#change-${cr.pending_rollback_proposal_id}`}
                        className="font-mono underline"
                      >
                        #{cr.pending_rollback_proposal_id}
                      </a>{" "}
                      is {cr.pending_rollback_proposal?.status ?? "pending_approval"}.
                    </p>
                  </div>
                ) : cr.status === "verification_failed" && !cr.is_rollback && !cr.pending_rollback_proposal_id ? (
                  <div className="mt-3 rounded border border-warning/30 bg-warning/10 p-3 text-xs">
                    <p className="text-warning font-semibold flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" /> Verification failed
                    </p>
                    {canApprove && cr.baseline_snapshot_id ? (
                      <Button
                        onClick={() => void handleManualRollback(cr)}
                        className="mt-2 h-8 px-2 text-xs bg-paper text-ink"
                      >
                        <ListRestart className="h-3.5 w-3.5" /> Propose Rollback
                      </Button>
                    ) : (
                      <p className="mt-1 text-muted">
                        No rollback proposal available (baseline snapshot may not be restorable).
                      </p>
                    )}
                  </div>
                ) : null}

                {/* Rollback verification_failed context (Task 9.5) */}
                {cr.status === "verification_failed" && cr.is_rollback && (
                  <div className="mt-3 rounded border border-error/30 bg-error/10 p-3 text-xs">
                    <p className="text-error font-semibold flex items-center gap-1">
                      <XCircle className="h-3.5 w-3.5" /> Rollback verification failed
                    </p>
                    <p className="mt-1 text-muted">No further automatic rollback will be proposed. Manual intervention required.</p>
                  </div>
                )}
              </div>
              {cr.status === "pending_approval" && canApprove && (
                <div className="flex gap-2">
                  <Button
                    onClick={() => void handleApprove(cr.id)}
                    className="h-8 px-2 text-xs"
                  >
                    <CheckCircle className="h-3.5 w-3.5" /> Approve
                  </Button>
                  <Button
                    onClick={() => void handleReject(cr.id)}
                    className="h-8 px-2 text-xs bg-paper text-error"
                  >
                    <XCircle className="h-3.5 w-3.5" /> Reject
                  </Button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChangeRequestForm({
  onSuccess,
  initialDeviceId,
  initialDatastore,
  disabledReason,
  compact = false
}: {
  onSuccess: () => void;
  initialDeviceId?: number;
  initialDatastore?: string;
  disabledReason?: string | null;
  compact?: boolean;
}) {
  const [deviceId, setDeviceId] = useState(initialDeviceId ? String(initialDeviceId) : "");
  const [datastore, setDatastore] = useState(initialDatastore ?? "running");
  const [summary, setSummary] = useState("");
  const [changeRef, setChangeRef] = useState("");
  const [configBody, setConfigBody] = useState("");
  const [reason, setReason] = useState("");
  const [preflight, setPreflight] = useState<ChangePreflightResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialDeviceId) {
      setDeviceId(String(initialDeviceId));
    }
  }, [initialDeviceId]);

  useEffect(() => {
    if (initialDatastore) setDatastore(initialDatastore);
  }, [initialDatastore]);

  useEffect(() => {
    setPreflight(null);
  }, [deviceId, datastore, summary, changeRef, configBody, reason]);

  async function preview() {
    const result = await api.previewChangePreflight({
      device_id: Number(deviceId),
      datastore,
      change_summary: summary,
      change_ref: changeRef.trim() || undefined,
      config_body: configBody,
      reason
    });
    setPreflight(result);
    if (!result.passed) {
      throw new Error(result.blockers.join(", ") || "Preflight failed");
    }
    return result;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (disabledReason) {
      setError(disabledReason);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (!preflight?.passed) {
        await preview();
        setLoading(false);
        return;
      }
      await api.submitChangeRequest({
        device_id: Number(deviceId),
        datastore,
        change_summary: summary,
        change_ref: changeRef.trim() || undefined,
        config_body: configBody,
        reason
      });
      setDeviceId(initialDeviceId ? String(initialDeviceId) : "");
      setSummary("");
      setChangeRef("");
      setConfigBody("");
      setReason("");
      setPreflight(null);
      onSuccess();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded border border-warm bg-canvas/95 p-4">
      <h3 className="mb-3 font-semibold text-sm">
        {compact ? "Request Config Change" : "Submit Change Request"}
      </h3>
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
        <div className={cn("grid gap-3", compact ? "" : "sm:grid-cols-2")}>
          {initialDeviceId ? (
            <Metric label="Device" value={`#${initialDeviceId}`} />
          ) : null}
          <div>
            <FieldLabel>Datastore</FieldLabel>
            <DatastoreSelect value={datastore} onValueChange={setDatastore} />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <FieldLabel>Change summary</FieldLabel>
            <input
              type="text"
              required
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <FieldLabel>Change ref</FieldLabel>
            <input
              type="text"
              value={changeRef}
              onChange={(e) => setChangeRef(e.target.value)}
              className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
            />
          </div>
        </div>
        <div>
          <FieldLabel>Config body</FieldLabel>
          <textarea
            required
            value={configBody}
            onChange={(e) => setConfigBody(e.target.value)}
            rows={4}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 font-mono text-xs"
          />
        </div>
        <div>
          <FieldLabel>Reason</FieldLabel>
          <textarea
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        {preflight ? <PreflightSummary preflight={preflight} /> : null}
        {disabledReason ? <p className="text-xs text-warn">{disabledReason}</p> : null}
        {error ? <p className="text-xs text-error">{error}</p> : null}
        <Button type="submit" busy={loading} disabled={Boolean(disabledReason)}>
          <Send className="h-4 w-4" />
          {preflight?.passed ? "Submit" : "Preview"}
        </Button>
      </form>
    </div>
  );
}

function DirectExecuteForm({ onSuccess }: { onSuccess: () => void }) {
  const [open, setOpen] = useState(false);
  const [deviceId, setDeviceId] = useState("");
  const [datastore, setDatastore] = useState("running");
  const [summary, setSummary] = useState("");
  const [configBody, setConfigBody] = useState("");
  const [reason, setReason] = useState("");
  const [preflight, setPreflight] = useState<ChangePreflightResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPreflight(null);
  }, [deviceId, datastore, summary, configBody, reason]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) { setError("Reason is required for direct execution"); return; }
    setLoading(true);
    setError(null);
    try {
      if (!preflight?.passed) {
        const result = await api.previewChangePreflight({
          device_id: Number(deviceId),
          datastore,
          change_summary: summary,
          config_body: configBody,
          reason
        });
        setPreflight(result);
        if (!result.passed) throw new Error(result.blockers.join(", ") || "Preflight failed");
        setLoading(false);
        return;
      }
      await api.directExecute({
        device_id: Number(deviceId),
        datastore,
        change_summary: summary,
        config_body: configBody,
        reason
      });
      setOpen(false);
      setSummary(""); setConfigBody(""); setReason(""); setDeviceId("");
      setPreflight(null);
      onSuccess();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)} className="text-sm">
        <Send className="h-4 w-4" /> Direct Execute
      </Button>
    );
  }

  return (
    <div className="rounded border border-warm bg-canvas/95 p-4">
      <h3 className="mb-3 font-semibold text-sm">Direct Execute (bypasses approval)</h3>
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <FieldLabel>Device ID</FieldLabel>
            <input
              type="number"
              required
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <FieldLabel>Datastore</FieldLabel>
            <DatastoreSelect value={datastore} onValueChange={setDatastore} />
          </div>
        </div>
        <div>
          <FieldLabel>Change summary</FieldLabel>
          <input
            type="text"
            required
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <FieldLabel>Config body</FieldLabel>
          <textarea
            required
            value={configBody}
            onChange={(e) => setConfigBody(e.target.value)}
            rows={4}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 font-mono text-xs"
          />
        </div>
        <div>
          <FieldLabel>Reason (required)</FieldLabel>
          <textarea
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        {preflight ? <PreflightSummary preflight={preflight} /> : null}
        {error ? <p className="text-xs text-error">{error}</p> : null}
        <div className="flex gap-2">
          <Button type="submit" busy={loading}>
            {preflight?.passed ? "Execute" : "Preview"}
          </Button>
          <Button type="button" onClick={() => setOpen(false)} className="bg-paper">Cancel</Button>
        </div>
      </form>
    </div>
  );
}

// ── Rollback Submit Form ──────────────────────────────────────────────────

function RollbackSubmitForm({
  snapshot,
  deviceId,
  onClose,
  onSuccess
}: {
  snapshot: ConfigSnapshot;
  deviceId: number;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [reason, setReason] = useState("");
  const [summary, setSummary] = useState(`Rollback to snapshot #${snapshot.id} (${digestShort(snapshot.content_digest)})`);
  const [preflight, setPreflight] = useState<ChangePreflightResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runPreflight() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.previewRollbackPreflight({
        device_id: deviceId,
        datastore: snapshot.datastore,
        reason,
        rollback_target_snapshot_id: snapshot.id
      });
      setPreflight(result);
      if (!result.passed) {
        const msgs = result.blockers.map((b) => formatRollbackBlocker(b));
        throw new Error(msgs.join("; "));
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) { setError("Reason is required"); return; }
    setLoading(true);
    setError(null);
    try {
      if (!preflight?.passed) {
        await runPreflight();
        setLoading(false);
        return;
      }
      await api.submitRollback({
        device_id: deviceId,
        datastore: snapshot.datastore,
        change_summary: summary,
        reason,
        rollback_target_snapshot_id: snapshot.id
      });
      onSuccess();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-4 rounded border border-warm bg-paper p-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold flex items-center gap-1.5">
          <ListRestart className="h-4 w-4" />
          Restore to Snapshot #{snapshot.id}
        </h4>
        <button onClick={onClose} className="text-muted hover:text-ink text-xs">✕ Cancel</button>
      </div>
      <div className="mb-3 grid grid-cols-2 gap-2 text-xs text-muted">
        <Metric label="Snapshot" value={`#${snapshot.id}`} />
        <Metric label="Datastore" value={snapshot.datastore} />
        <Metric label="Digest" value={digestShort(snapshot.content_digest)} />
        <Metric label="Collected" value={formatDate(snapshot.collected_at)} />
      </div>
      {!snapshot.rollback_eligible ? (
        <div className="rounded border border-error/20 bg-error/10 p-3 text-xs text-error">
          This snapshot cannot be restored: {snapshot.rollback_blocker ?? "normalized content unavailable"}
        </div>
      ) : (
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <div>
            <FieldLabel>Change summary</FieldLabel>
            <input
              type="text"
              required
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="mt-1 w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <FieldLabel>Reason (required)</FieldLabel>
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              placeholder="Why are you restoring this snapshot?"
              className="mt-1 w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
            />
          </div>
          {preflight ? (
            <div className="rounded border border-warm bg-canvas p-3 text-xs space-y-1">
              <div className="flex items-center gap-2">
                {preflight.passed ? (
                  <CheckCircle className="h-4 w-4 text-online" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-error" />
                )}
                <span className="font-medium">{preflight.passed ? "Preflight passed" : "Preflight blocked"}</span>
              </div>
              {preflight.blockers.length > 0 ? (
                <ul className="ml-6 space-y-0.5 text-error">
                  {preflight.blockers.map((b) => <li key={b}>{formatRollbackBlocker(b)}</li>)}
                </ul>
              ) : null}
              {preflight.payload ? (
                <Metric label="Payload digest" value={digestShort(preflight.payload.digest)} />
              ) : null}
              {preflight.risk_summary ? (
                <Metric label="Risk" value={String((preflight.risk_summary as ChangeRiskSummary).risk_level ?? "-")} />
              ) : null}
            </div>
          ) : null}
          {error ? <p className="text-xs text-error">{error}</p> : null}
          <Button type="submit" busy={loading}>
            {preflight?.passed ? <><CheckCircle className="h-4 w-4" /> Submit Rollback</> : <><Sparkles className="h-4 w-4" /> Preview Preflight</>}
          </Button>
        </form>
      )}
    </div>
  );
}

// ── Admin Tab ──────────────────────────────────────────────────────────────

function AdminTab() {
  const [users, setUsers] = useState<UserRead[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAdminData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextUsers, nextRoles, nextPermissions] = await Promise.all([
        api.listUsers(),
        api.listRoles(),
        api.listPermissions()
      ]);
      setUsers(nextUsers);
      setRoles(nextRoles);
      setPermissions(nextPermissions);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadAdminData(); }, [loadAdminData]);

  return (
    <div className="mx-auto grid max-w-6xl gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Access Control</h2>
          <Button onClick={() => void loadAdminData()} busy={loading} className="h-9 w-9 px-0">
            <RefreshCw className="h-4 w-4" aria-hidden />
          </Button>
        </div>
        {error ? <ErrorPanel message={error} onRetry={() => void loadAdminData()} /> : null}
        <CreateUserForm onSuccess={() => void loadAdminData()} />
        <div className="space-y-2">
          {users.map((u) => (
            <div key={u.id} className="rounded border border-warm bg-canvas/95 p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{u.display_name}</p>
                  <p className="text-xs text-muted">
                    {u.username} · {u.roles.map((r) => r.name).join(", ") || "no roles"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={u.is_active ? "online" : "offline"} />
                  <Button
                    onClick={() => void toggleUser(u)}
                    className="h-8 px-2 text-xs"
                  >
                    {u.is_active ? "Disable" : "Enable"}
                  </Button>
                </div>
              </div>
              <UserRoleControls
                user={u}
                roles={roles}
                onChange={() => void loadAdminData()}
              />
            </div>
          ))}
        </div>
      </div>
      <aside className="space-y-4">
        <RolePermissionEditor
          roles={roles}
          permissions={permissions}
          onChange={() => void loadAdminData()}
        />
        <div className="rounded border border-warm bg-canvas/95 p-4">
          <h3 className="mb-3 text-sm font-semibold">System Configuration</h3>
          <div className="space-y-2 text-xs text-muted">
            <p>JWT, CORS, cookie, audit retention</p>
            <StatusBadge status="ready" />
          </div>
        </div>
      </aside>
    </div>
  );

  async function toggleUser(user: UserRead) {
    setError(null);
    try {
      if (user.is_active) await api.disableUser(user.id);
      else await api.enableUser(user.id);
      await loadAdminData();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
}

function CreateUserForm({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.createUser({
        username,
        display_name: displayName,
        password
      });
      setUsername("");
      setDisplayName("");
      setPassword("");
      onSuccess();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded border border-warm bg-canvas/95 p-4">
      <h3 className="mb-3 text-sm font-semibold">Create User</h3>
      <form onSubmit={(e) => void handleSubmit(e)} className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
        <div>
          <FieldLabel>Username</FieldLabel>
          <input
            required
            minLength={2}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <FieldLabel>Display name</FieldLabel>
          <input
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <FieldLabel>Password</FieldLabel>
          <input
            required
            type="password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        <Button type="submit" busy={loading} className="mt-5">
          Create
        </Button>
      </form>
      {error ? <p className="mt-2 text-xs text-error">{error}</p> : null}
    </div>
  );
}

function UserRoleControls({
  user,
  roles,
  onChange
}: {
  user: UserRead;
  roles: Role[];
  onChange: () => void;
}) {
  const assignedRoleIds = new Set(user.roles.map((role) => role.id));
  const availableRoles = roles.filter((role) => !assignedRoleIds.has(role.id));
  const [roleId, setRoleId] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function assignSelectedRole() {
    if (!roleId) return;
    setError(null);
    try {
      await api.assignRole(user.id, Number(roleId));
      setRoleId("");
      onChange();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function removeRole(role: Role) {
    setError(null);
    try {
      await api.removeRole(user.id, role.id);
      onChange();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="mt-3 border-t border-warm pt-3">
      <div className="flex flex-wrap gap-2">
        {user.roles.map((role) => (
          <button
            key={role.id}
            onClick={() => void removeRole(role)}
            className="rounded border border-warm bg-paper px-2 py-1 font-mono text-[11px] text-muted hover:border-error hover:text-error"
          >
            {role.name} x
          </button>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <select
          value={roleId}
          onChange={(e) => setRoleId(e.target.value)}
          className="h-8 min-w-40 rounded border border-warm bg-paper px-2 text-sm"
        >
          <option value="">Role</option>
          {availableRoles.map((role) => (
            <option key={role.id} value={role.id}>{role.name}</option>
          ))}
        </select>
        <Button
          onClick={() => void assignSelectedRole()}
          disabled={!roleId}
          className="h-8 px-2 text-xs"
        >
          Assign
        </Button>
      </div>
      {error ? <p className="mt-2 text-xs text-error">{error}</p> : null}
    </div>
  );
}

function RolePermissionEditor({
  roles,
  permissions,
  onChange
}: {
  roles: Role[];
  permissions: Permission[];
  onChange: () => void;
}) {
  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null);
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedRole = roles.find((role) => role.id === selectedRoleId) ?? roles[0] ?? null;

  useEffect(() => {
    if (selectedRoleId !== null || roles.length === 0) return;
    setSelectedRoleId(roles[0].id);
  }, [roles, selectedRoleId]);

  useEffect(() => {
    if (!selectedRole) return;
    setSelectedPermissionIds(new Set(selectedRole.permissions.map((perm) => perm.id)));
  }, [selectedRole]);

  async function savePermissions() {
    if (!selectedRole) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateRolePermissions(selectedRole.id, Array.from(selectedPermissionIds));
      onChange();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  function togglePermission(permissionId: number) {
    setSelectedPermissionIds((current) => {
      const next = new Set(current);
      if (next.has(permissionId)) next.delete(permissionId);
      else next.add(permissionId);
      return next;
    });
  }

  return (
    <div className="rounded border border-warm bg-canvas/95 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Roles & Permissions</h3>
      </div>
      <select
        value={selectedRole?.id ?? ""}
        onChange={(e) => setSelectedRoleId(Number(e.target.value))}
        className="mt-3 h-9 w-full rounded border border-warm bg-paper px-2 text-sm"
      >
        {roles.map((role) => (
          <option key={role.id} value={role.id}>{role.name}</option>
        ))}
      </select>
      <div className="mt-3 max-h-[420px] space-y-2 overflow-auto pr-1">
        {permissions.map((permission) => (
          <label
            key={permission.id}
            className="flex items-center gap-2 rounded border border-warm bg-paper px-2 py-1.5 text-xs"
          >
            <input
              type="checkbox"
              checked={selectedPermissionIds.has(permission.id)}
              onChange={() => togglePermission(permission.id)}
            />
            <span className="font-mono">{permission.name}</span>
          </label>
        ))}
      </div>
      {error ? <p className="mt-2 text-xs text-error">{error}</p> : null}
      <Button
        onClick={() => void savePermissions()}
        busy={saving}
        disabled={!selectedRole}
        className="mt-3"
      >
        Save
      </Button>
    </div>
  );
}

// ── Audit Tab ──────────────────────────────────────────────────────────────

function AuditTab() {
  const { hasPermission } = useSession();
  const [logs, setLogs] = useState<AuditLogRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFullAudit = hasPermission(PERM.AUDIT_READ_FULL);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.listAuditLogs({ limit: 50 });
      setLogs(resp.items);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadLogs(); }, [loadLogs]);

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Audit Log</h2>
        <Button onClick={() => void loadLogs()} busy={loading} className="h-9 w-9 px-0">
          <RefreshCw className="h-4 w-4" aria-hidden />
        </Button>
      </div>
      {error ? <ErrorPanel message={error} onRetry={() => void loadLogs()} /> : null}
      {logs.length === 0 && !loading ? (
        <EmptyState icon={<FileClock className="h-6 w-6" />} title="No audit events" />
      ) : null}
      <div className="overflow-x-auto rounded border border-warm">
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-warm text-left font-mono text-[11px] uppercase text-muted">
              <th className="px-3 py-2 font-medium">Time</th>
              <th className="px-3 py-2 font-medium">Action</th>
              <th className="px-3 py-2 font-medium">Actor</th>
              <th className="px-3 py-2 font-medium">Target</th>
              <th className="px-3 py-2 font-medium">Permission</th>
              <th className="px-3 py-2 font-medium">Outcome</th>
              {hasFullAudit ? <th className="px-3 py-2 font-medium">Context</th> : null}
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-b border-warm/70 last:border-0">
                <td className="px-3 py-2 text-xs text-muted">{formatDate(log.created_at)}</td>
                <td className="px-3 py-2 font-mono text-xs">{log.action}</td>
                <td className="px-3 py-2 text-xs">{log.actor_user_id ?? "-"}</td>
                <td className="px-3 py-2 text-xs text-muted">{log.target_type ?? "-"}</td>
                <td className="px-3 py-2 font-mono text-xs text-muted">
                  {log.permission ?? "-"}
                </td>
                <td className="px-3 py-2">
                  <StatusBadge status={log.outcome} />
                </td>
                {hasFullAudit ? (
                  <td className="max-w-[320px] px-3 py-2">
                    <pre className="max-h-24 overflow-auto whitespace-pre-wrap break-words rounded bg-paper p-2 font-mono text-[11px] text-muted">
                      {Object.keys(log.metadata).length > 0
                        ? JSON.stringify(log.metadata, null, 2)
                        : "{}"}
                    </pre>
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Shared sub-components ──────────────────────────────────────────────────

function CreateDeviceForm({ onSuccess }: { onSuccess: (deviceId: number) => Promise<void> }) {
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("830");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const device = await api.createDevice({
        name,
        connection: {
          host,
          port: Number(port),
          username,
          password
        }
      });
      setName("");
      setHost("");
      setPort("830");
      setUsername("");
      setPassword("");
      await onSuccess(device.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="mb-3 rounded border border-warm bg-paper p-3">
      <div className="grid gap-2">
        <FieldLabel>New Device</FieldLabel>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="name"
          className="w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
        />
        <div className="grid grid-cols-[1fr_76px] gap-2">
          <input
            required
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="host"
            className="min-w-0 rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
          />
          <input
            required
            type="number"
            min={1}
            max={65535}
            value={port}
            onChange={(e) => setPort(e.target.value)}
            className="rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
          />
        </div>
        <input
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="username"
          className="w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="password"
          className="w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
        />
        {error ? <p className="text-xs text-error">{error}</p> : null}
        <Button type="submit" busy={loading} className="w-full">
          <Plus className="h-4 w-4" /> Add
        </Button>
      </div>
    </form>
  );
}

function PreflightSummary({
  preflight,
  compact = false
}: {
  preflight: ChangePreflightResponse | null;
  compact?: boolean;
}) {
  if (!preflight) return null;
  return (
    <div className="rounded border border-warm bg-paper p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <FieldLabel>Preflight</FieldLabel>
        <StatusBadge status={preflight.passed ? "passed" : "failed"} />
      </div>
      <div className={cn("mt-2 grid gap-2 text-xs", compact ? "" : "sm:grid-cols-2")}>
        <Metric
          label={preflight.mode === "rollback" ? "Current" : "Baseline"}
          value={preflight.baseline_snapshot?.id ?? "-"}
        />
        {preflight.mode === "rollback" ? (
          <Metric label="Target" value={preflight.rollback_target_snapshot?.id ?? "-"} />
        ) : null}
        <Metric label="Payload" value={preflight.payload ? `${preflight.payload.length} bytes` : "-"} />
        <Metric label="Risk" value={preflight.risk_summary?.risk_level ?? "-"} />
        <Metric label="Digest" value={digestShort(preflight.payload?.digest)} />
      </div>
      {preflight.blockers.length > 0 ? (
        <p className="mt-2 text-xs text-error">
          {preflight.blockers.map((b) => formatRollbackBlocker(b)).join(", ")}
        </p>
      ) : null}
    </div>
  );
}

function changePreflightFromRequest(cr: ChangeRequestRead): ChangePreflightResponse | null {
  if (!cr.preflight_status) return null;
  return {
    status: cr.preflight_status,
    passed: cr.preflight_status === "passed",
    device_id: cr.device_id,
    datastore: cr.datastore,
    generated_at: cr.preflight_generated_at ?? cr.created_at,
    baseline_snapshot: cr.baseline_snapshot,
    payload: null,
    blockers: Array.isArray(cr.preflight_summary?.blockers)
      ? (cr.preflight_summary.blockers as string[])
      : [],
    recommended_action: null,
    risk_summary: (cr.risk_summary as ChangePreflightResponse["risk_summary"]) ?? null,
    mode: cr.is_rollback ? "rollback" : "forward",
    rollback_target_snapshot: cr.rollback_target_snapshot ?? null
  };
}

function DeviceListItem({
  device, active, onSelect
}: { device: Device; active: boolean; onSelect: () => void }) {
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

function SnapshotTable({
  snapshots,
  canSubmitChange = false,
  canApprove = false,
  deviceId,
  onStartChange,
  onRollbackSuccess
}: {
  snapshots: ConfigSnapshot[];
  canSubmitChange?: boolean;
  canApprove?: boolean;
  deviceId?: number;
  onStartChange?: (snapshot: ConfigSnapshot) => void;
  onRollbackSuccess?: () => void;
}) {
  const [rollbackTarget, setRollbackTarget] = useState<ConfigSnapshot | null>(null);

  return (
    <InfoPanel icon={<FileClock />} title="Snapshots">
      {snapshots.length === 0 ? (
        <EmptyState icon={<Database className="h-6 w-6" />} title="No snapshots collected" />
      ) : (
        <>
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
                {snapshots.map((s) => (
                  <tr key={s.id} className="border-b border-warm/70 last:border-0">
                    <td className="py-3 pr-3 font-mono text-xs">{s.datastore}</td>
                    <td className="py-3 pr-3 text-muted">{formatDate(s.collected_at)}</td>
                    <td className="py-3 pr-3 font-mono text-xs">{digestShort(s.content_digest)}</td>
                    <td className="py-3 text-muted">
                      <div className="flex items-center justify-between gap-2">
                        <span>{diffLabel(s.diff_summary)}</span>
                        <div className="flex gap-1.5">
                          {canSubmitChange && onStartChange ? (
                            <Button
                              onClick={() => onStartChange(s)}
                              className="h-8 px-2 text-xs"
                            >
                              <Send className="h-3.5 w-3.5" /> Change
                            </Button>
                          ) : null}
                          {canApprove ? (
                            s.rollback_eligible ? (
                              <Button
                                onClick={() => setRollbackTarget(s)}
                                className="h-8 px-2 text-xs bg-paper border border-warm text-ink"
                                title="Restore to this snapshot"
                              >
                                <ListRestart className="h-3.5 w-3.5" /> Restore
                              </Button>
                            ) : (
                              <button
                                disabled
                                title={`Not restorable: ${s.rollback_blocker ?? "unknown"}`}
                                className="h-8 px-2 text-xs opacity-40 cursor-not-allowed flex items-center gap-1 rounded border border-warm"
                              >
                                <ListRestart className="h-3.5 w-3.5" /> Restore
                              </button>
                            )
                          ) : null}
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rollbackTarget && deviceId !== undefined ? (
            <RollbackSubmitForm
              snapshot={rollbackTarget}
              deviceId={deviceId}
              onClose={() => setRollbackTarget(null)}
              onSuccess={() => {
                setRollbackTarget(null);
                onRollbackSuccess?.();
              }}
            />
          ) : null}
        </>
      )}
    </InfoPanel>
  );
}

function ReadOnlyPanel({
  profile, lastTask, configTaskRunning
}: { profile: DeviceProfile | null; lastTask: TaskRead | null; configTaskRunning: boolean }) {
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
                <p className="mt-2 text-xs text-error">{task.error_code}: {task.error_message}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </InfoPanel>
  );
}

function InfoPanel({ icon, title, children }: {
  icon: React.ReactNode; title: string; children: React.ReactNode
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

function DeviceListSkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-24 animate-pulse rounded border border-warm bg-paper" />
      ))}
    </div>
  );
}

function ErrorPanel({ message, onRetry }: { message: string | null; onRetry: () => void }) {
  return (
    <div className="rounded border border-error/25 bg-error/10 p-4 text-error">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p className="break-words text-sm">{message ?? "Request failed"}</p>
        </div>
        <Button onClick={onRetry} className="h-8 bg-paper text-error">Retry</Button>
      </div>
    </div>
  );
}

function summaryValue(summary: Record<string, unknown> | undefined) {
  if (!summary) return "-";
  if (typeof summary.capability_count === "number") return `${summary.capability_count} caps`;
  return "ready";
}

function onboardingSteps(summary: Device["onboarding_summary"]) {
  if (!summary) return "-";
  return [
    `C ${compactStatus(summary.connection.status)}`,
    `D ${compactStatus(summary.discovery.status)}`,
    `B ${compactStatus(summary.baseline.status)}`
  ].join(" · ");
}

function onboardingDetail(summary: Device["onboarding_summary"]) {
  if (!summary) return "Profile unavailable";
  if (summary.blockers.length > 0) return summary.blockers.join(", ");
  if (summary.next_action) return summary.next_action.replaceAll("_", " ");
  return summary.ready_for_change ? "Ready for change" : "Waiting for onboarding";
}

function compactStatus(status: string) {
  return status.replaceAll("_", " ");
}

function digestShort(digest: string | undefined) {
  if (!digest) return "-";
  return digest.replace("sha256:", "").slice(0, 12);
}

function diffLabel(diff: Record<string, unknown>) {
  if (diff.previous_snapshot_id === null) return "first snapshot";
  return diff.changed ? "changed" : "unchanged";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit"
  }).format(new Date(value));
}

function errorMessage(caught: unknown) {
  return formatApiError(caught);
}
