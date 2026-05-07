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
  GripVertical,
  HardDrive,
  KeyRound,
  ListRestart,
  Maximize2,
  Minimize2,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  RefreshCw,
  Router,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  Users,
  XCircle
} from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BrandMark } from "@/components/brand";
import { LoginView, SessionHeader } from "@/components/auth";
import { Button, DatastoreSelect, EmptyState, FieldLabel, StatusBadge } from "@/components/ui";
import { api, formatApiError, formatRollbackBlocker } from "@/lib/api";
import { useT, type TranslateFn } from "@/lib/i18n";
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
type RefreshOptions = { silent?: boolean };
type ConfigChangeAction =
  | "edit-leaf"
  | "add-leaf"
  | "delete-leaf"
  | "edit-instance"
  | "add-instance"
  | "delete-instance";

type ConfigChangeTarget = {
  action: ConfigChangeAction;
  path: string;
  label: string;
  currentValue?: unknown;
  schema?: YangNodeInfo | null;
};

type ConfigLeafRow = {
  path: string;
  label: string;
  relativePath: string;
  value: unknown;
  valueType: string;
  instanceLabel?: string;
  namespace?: string | null;
  schema?: YangNodeInfo | null;
};

type ConfigListTableColumn = {
  key: string;
  label: string;
};

type ConfigListTableCell = {
  path: string;
  label: string;
  value: unknown;
  valueType: string;
  schema?: YangNodeInfo | null;
};

type ConfigListTableRow = {
  path: string;
  label: string;
  value: unknown;
  cells: Record<string, ConfigListTableCell>;
};

type ConfigListTable = {
  columns: ConfigListTableColumn[];
  rows: ConfigListTableRow[];
};

type YangEnumOption = {
  name: string;
  value?: string | number | null;
  description?: string | null;
};

type YangNodeInfo = {
  name?: string;
  qname?: string;
  path?: string;
  absolute_path?: string;
  module?: string;
  namespace?: string;
  prefix?: string;
  kind?: string;
  node_type?: string;
  type?: string;
  base_type?: string;
  type_name?: string;
  description?: string | null;
  units?: string | null;
  default?: unknown;
  mandatory?: boolean;
  config?: boolean;
  status?: string;
  range?: string | null;
  length?: string | null;
  pattern?: string | null;
  key?: string | string[] | null;
  leafref_path?: string | null;
  enum_values?: Array<string | YangEnumOption>;
  values?: Array<string | YangEnumOption>;
  options?: Array<string | YangEnumOption>;
};

type YangSchemaIndex = {
  byPath: Map<string, YangNodeInfo>;
  byNamespacePath: Map<string, YangNodeInfo>;
  byName: Map<string, YangNodeInfo[]>;
};

const REALTIME_FAST_REFRESH_MS = 1500;
const REALTIME_NORMAL_REFRESH_MS = 4000;
const REALTIME_SLOW_REFRESH_MS = 8000;

export default function OperationsConsole() {
  const { state } = useSession();
  const t = useT();

  if (state === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        {t("app.loading")}
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
  const t = useT();

  const tabs: { id: Tab; label: string; icon: React.ReactNode; perm: string }[] = [
    { id: "devices", label: t("tab.devices"), icon: <Router className="h-4 w-4" />, perm: PERM.DEVICE_READ },
    {
      id: "changes",
      label: t("tab.changes"),
      icon: <ClipboardList className="h-4 w-4" />,
      perm: PERM.DEVICE_CHANGE_SUBMIT
    },
    { id: "admin", label: t("tab.admin"), icon: <Users className="h-4 w-4" />, perm: PERM.USER_MANAGE },
    {
      id: "audit",
      label: t("tab.audit"),
      icon: <FileClock className="h-4 w-4" />,
      perm: PERM.AUDIT_READ_SUMMARY
    }
  ];

  const availableTabs = tabs.filter(({ perm }) => hasPermission(perm));
  const [tab, setTab] = useState<Tab>(() => availableTabs[0]?.id ?? "devices");

  return (
    <main className="flex min-h-screen min-h-dvh flex-col text-ink">
      {/* App bar */}
      <div className="relative flex h-14 shrink-0 items-center justify-between border-b border-warm bg-canvas/95 px-4">
        <BrandMark className="h-9 w-[170px] sm:h-10 sm:w-[190px]" />
        <nav className="pointer-events-none absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 gap-1">
          {tabs.map(({ id, label, icon, perm }) =>
            hasPermission(perm) ? (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={cn(
                  "pointer-events-auto flex items-center gap-1.5 rounded px-3 py-1.5 text-sm transition",
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
        <div className="flex items-center gap-3">
          <SessionHeader />
        </div>
      </div>

      <div className="min-h-0 flex-1 p-2 md:p-3">
        {availableTabs.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-20 text-center">
            <KeyRound className="h-8 w-8 text-muted" />
            <p className="text-sm text-muted">{t("auth.noPermissionTitle")}</p>
            <p className="text-xs text-muted">{t("auth.noPermissionHint")}</p>
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
  const t = useT();
  const layoutRef = useRef<HTMLDivElement | null>(null);
  const selectedDeviceIdRef = useRef<number | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);
  const [profile, setProfile] = useState<DeviceProfile | null>(null);
  const [snapshots, setSnapshots] = useState<ConfigSnapshot[]>([]);
  const [datastore, setDatastore] = useState("running");
  const [lastTask, setLastTask] = useState<TaskRead | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [listMode, setListMode] = useState<DeviceListMode>("compact");
  const [leftWidth, setLeftWidth] = useState(320);
  const [rightWidth, setRightWidth] = useState(320);
  const [statusCollapsed, setStatusCollapsed] = useState(false);
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false);
  const [detailMode, setDetailMode] = useState<DeviceDetailMode>("operational");
  const [deviceQuery, setDeviceQuery] = useState("");
  const [selectedObjectPath, setSelectedObjectPath] = useState("root");
  const [changeSummary, setChangeSummary] = useState("");
  const [changeReason, setChangeReason] = useState("");
  const [configBody, setConfigBody] = useState("");
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

  useEffect(() => {
    selectedDeviceIdRef.current = selectedDeviceId;
  }, [selectedDeviceId]);

  const loadDevices = useCallback(async (options: RefreshOptions = {}) => {
    if (!options.silent) {
      setDevicesState("loading");
      setError(null);
    }
    try {
      const items = await api.listDevices();
      setDevices(items);
      setSelectedDeviceId((cur) =>
        cur !== null && items.some((item) => item.id === cur) ? cur : items[0]?.id ?? null
      );
      setDevicesState("loaded");
    } catch (e) {
      if (!options.silent) {
        setDevicesState("error");
        setError(errorMessage(e, t));
      }
    }
  }, [t]);

  const loadProfile = useCallback(async (deviceId: number, options: RefreshOptions = {}) => {
    if (!options.silent) {
      setProfileState("loading");
      setError(null);
    }
    try {
      const [prof, snap]: [DeviceProfile, SnapshotListResponse] = await Promise.all([
        api.getProfile(deviceId),
        api.listSnapshots(deviceId, 20)
      ]);
      const latestSnapshot = snap.items[0]
        ? await api.getSnapshot(deviceId, snap.items[0].id)
        : null;
      if (selectedDeviceIdRef.current !== deviceId) return;
      setProfile(prof);
      setSnapshots(latestSnapshot ? [latestSnapshot, ...snap.items.slice(1)] : snap.items);
      setProfileState("loaded");
    } catch (e) {
      if (!options.silent) {
        setProfileState("error");
        setError(errorMessage(e, t));
      }
    }
  }, [t]);

  useEffect(() => {
    void loadDevices();
  }, [loadDevices]);

  useEffect(() => {
    if (selectedDeviceId !== null) void loadProfile(selectedDeviceId);
    else { setProfile(null); setSnapshots([]); }
    setSelectedObjectPath("root");
    setPreflight(null);
  }, [loadProfile, selectedDeviceId]);

  useEffect(() => {
    if (selectedDeviceId === null) return;
    const snapshot = snapshots.find((item) => item.datastore === datastore);
    if (!snapshot || snapshot.config_tree !== undefined) return;
    let cancelled = false;
    api.getSnapshot(selectedDeviceId, snapshot.id)
      .then((detail) => {
        if (cancelled) return;
        setSnapshots((current) => current.map((item) => (item.id === detail.id ? detail : item)));
      })
      .catch(() => {
        if (cancelled) return;
        setSnapshots((current) =>
          current.map((item) => (item.id === snapshot.id ? { ...item, config_tree: null } : item))
        );
      });
    return () => {
      cancelled = true;
    };
  }, [datastore, selectedDeviceId, snapshots]);

  const configTaskRunning = profile?.recent_tasks.some(
    (t) => t.task_type === "device.config_snapshot" && (t.status === "queued" || t.status === "running")
  );
  const realtimeTaskActive = Boolean(
    profile?.recent_tasks.some((task) => isRealtimeActiveStatus(task.status)) ||
      (lastTask && isRealtimeActiveStatus(lastTask.status))
  );
  const profileRefreshMs = realtimeTaskActive ? REALTIME_FAST_REFRESH_MS : REALTIME_NORMAL_REFRESH_MS;

  useRealtimeRefresh(() => loadDevices({ silent: true }), REALTIME_NORMAL_REFRESH_MS);
  useRealtimeRefresh(
    () => {
      if (selectedDeviceId !== null) return loadProfile(selectedDeviceId, { silent: true });
    },
    selectedDeviceId === null ? null : profileRefreshMs
  );

  useEffect(() => {
    if (!lastTask || !profile) return;
    const refreshedTask = profile.recent_tasks.find((task) => task.task_id === lastTask.task_id);
    if (
      !refreshedTask ||
      (refreshedTask.status === lastTask.status && refreshedTask.updated_at === lastTask.updated_at)
    ) {
      return;
    }
    setLastTask((current) =>
      current && current.task_id === refreshedTask.task_id
        ? { ...current, ...refreshedTask }
        : current
    );
  }, [lastTask, profile]);

  const canCollect = hasPermission(PERM.DEVICE_COLLECT);
  const canManage = hasPermission(PERM.DEVICE_MANAGE);
  const canSubmitChange = hasPermission(PERM.DEVICE_CHANGE_SUBMIT);
  const readyForChange = Boolean(profile?.onboarding_summary?.ready_for_change);

  const handleListModeChange = useCallback((mode: DeviceListMode) => {
    setListMode(mode);
    if (mode === "compact") setLeftWidth((width) => Math.min(width, 440));
    if (mode === "expanded") setLeftWidth((width) => Math.max(width, 720));
  }, []);

  const startResize = useCallback((
    side: "left" | "right",
    event: React.PointerEvent<HTMLButtonElement>
  ) => {
    event.preventDefault();
    const startX = event.clientX;
    const startLeft = leftWidth;
    const startRight = rightWidth;
    const viewportWidth = layoutRef.current?.clientWidth ?? window.innerWidth;
    const maxSideWidth = Math.max(320, Math.min(900, viewportWidth - 520));
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    function move(moveEvent: PointerEvent) {
      const delta = moveEvent.clientX - startX;
      if (side === "left") {
        setListMode((mode) => (mode === "collapsed" ? "compact" : mode));
        setLeftWidth(clamp(startLeft + delta, 280, maxSideWidth));
      } else {
        setStatusCollapsed(false);
        setRightWidth(clamp(startRight - delta, 320, maxSideWidth));
      }
    }

    function stop() {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    }

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  }, [leftWidth, rightWidth]);

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
      setError(errorMessage(e, t));
    }
  }

  async function submitFullRefresh() {
    if (!selectedDeviceId || configTaskRunning) return;
    setSubmitState("loading");
    setError(null);
    try {
      await api.submitCapabilityDiscovery(selectedDeviceId);
      const task = await api.collectSnapshot(selectedDeviceId, datastore);
      setLastTask(task);
      await loadProfile(selectedDeviceId);
      setSubmitState("loaded");
    } catch (e) {
      setSubmitState("error");
      setError(errorMessage(e, t));
    }
  }

  async function initialCollect(deviceId: number) {
    try {
      await api.submitCapabilityDiscovery(deviceId);
      await api.collectSnapshot(deviceId, datastore);
      await loadProfile(deviceId);
    } catch {
      // Device was created — silently ignore collection errors
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
      setError(errorMessage(e, t));
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
      setPreflight(null);
      await loadProfile(selectedDeviceId);
      setChangeSubmitState("loaded");
    } catch (e) {
      setChangeSubmitState("error");
      setError(errorMessage(e, t));
    }
  }

  return (
    <div
      ref={layoutRef}
      className="flex h-full min-h-0 w-full flex-col gap-2 lg:grid lg:grid-rows-none lg:gap-0 xl:gap-0"
      style={{
        gridTemplateColumns: [
          listMode === "collapsed" ? "64px" : listMode === "expanded" ? "minmax(0,1fr)" : `${leftWidth}px`,
          listMode === "expanded" ? "0" : "10px",
          listMode === "expanded" ? "0" : (workspaceCollapsed ? "64px" : "minmax(360px,1fr)"),
          "10px",
          statusCollapsed ? "64px" : `${rightWidth}px`
        ].join(" ")
      }}
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
        onModeChange={handleListModeChange}
        onQueryChange={setDeviceQuery}
        onToggleCreate={() => setShowCreate((value) => !value)}
        onRefresh={() => void loadDevices()}
        onSelect={setSelectedDeviceId}
        onCreateSuccess={async (deviceId) => {
          setShowCreate(false);
          await loadDevices();
          setSelectedDeviceId(deviceId);
          void initialCollect(deviceId);
        }}
        onDelete={async (deviceId) => {
          await api.deleteDevice(deviceId);
          if (selectedDeviceId === deviceId) {
            setSelectedDeviceId(null);
            setProfile(null);
            setSnapshots([]);
          }
          await loadDevices();
        }}
      />

      <ResizeHandle
        label={t("devices.resizeList")}
        hidden={listMode === "collapsed" || listMode === "expanded"}
        onPointerDown={(event) => startResize("left", event)}
      />

      <section className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded border border-warm bg-canvas/95">
        {workspaceCollapsed ? (
          <CollapsedWorkspacePane
            device={selectedDevice}
            onExpand={() => setWorkspaceCollapsed(false)}
          />
        ) : null}

        {selectedDevice === null && devicesState !== "loading" ? (
          <div className="flex min-h-0 flex-1 items-center justify-center p-4">
            <EmptyState icon={<HardDrive className="h-6 w-6" />} title={t("devices.selectPrompt")} />
          </div>
        ) : null}

        {selectedDevice !== null && !workspaceCollapsed ? (
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
            readyForChange={readyForChange}
            submitBusy={submitState === "loading"}
            changeBusy={changeSubmitState === "loading"}
            configTaskRunning={Boolean(configTaskRunning)}
            lastTask={lastTask}
            changeSummary={changeSummary}
            changeReason={changeReason}
            configBody={configBody}
            preflight={preflight}
            onDetailModeChange={setDetailMode}
            onCollapseWorkspace={() => setWorkspaceCollapsed(true)}
            onDatastoreChange={setDatastore}
            onRefresh={() => void loadProfile(selectedDevice.id)}
            onFullRefresh={() => void submitFullRefresh()}
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
            onPreviewChange={() => void previewConfigChange()}
            onSubmitChange={() => void submitConfigChange()}
          />
        ) : null}
      </section>

      <ResizeHandle
        label={t("devices.resizeStatus")}
        hidden={statusCollapsed}
        onPointerDown={(event) => startResize("right", event)}
      />

      <DeviceStatusPane
        collapsed={statusCollapsed}
        profile={profile}
        snapshots={snapshots}
        lastTask={lastTask}
        configTaskRunning={Boolean(configTaskRunning)}
        canSubmitChange={canSubmitChange}
        canApprove={hasPermission(PERM.DEVICE_CHANGE_APPROVE)}
        deviceId={selectedDevice?.id}
        onToggleCollapsed={() => setStatusCollapsed((value) => !value)}
        onStartChange={(snapshot) => {
          setDatastore(snapshot.datastore);
          setDetailMode("config");
          setWorkspaceCollapsed(false);
        }}
        onRollbackSuccess={() => { if (selectedDeviceId !== null) void loadProfile(selectedDeviceId); }}
      />
    </div>
  );
}

function ResizeHandle({
  label,
  hidden,
  onPointerDown
}: {
  label: string;
  hidden?: boolean;
  onPointerDown: (event: React.PointerEvent<HTMLButtonElement>) => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onPointerDown={onPointerDown}
      className={cn(
        "hidden min-h-0 cursor-col-resize items-center justify-center rounded text-muted transition hover:bg-paper hover:text-accent focus:outline-none focus:ring-2 focus:ring-warm-strong lg:flex",
        hidden && "pointer-events-none opacity-0"
      )}
    >
      <GripVertical className="h-4 w-4" aria-hidden />
    </button>
  );
}

function CollapsedWorkspacePane({
  device,
  onExpand
}: {
  device: Device | null;
  onExpand: () => void;
}) {
  const t = useT();
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center gap-3 py-3">
      <Button
        aria-label={t("devices.expandWorkspace")}
        title={t("devices.expandWorkspace")}
        onClick={onExpand}
        className="h-9 w-9 px-0 bg-paper"
      >
        <Maximize2 className="h-4 w-4" aria-hidden />
      </Button>
      <div className="h-px w-8 bg-warm" />
      <div className="flex min-h-0 flex-1 items-center justify-center px-2">
        <p className="max-h-full [writing-mode:vertical-rl] truncate text-xs font-semibold text-muted">
          {device?.name ?? t("devices.workspace")}
        </p>
      </div>
    </div>
  );
}

function DeviceStatusPane({
  collapsed,
  profile,
  snapshots,
  lastTask,
  configTaskRunning,
  canSubmitChange,
  canApprove,
  deviceId,
  onToggleCollapsed,
  onStartChange,
  onRollbackSuccess
}: {
  collapsed: boolean;
  profile: DeviceProfile | null;
  snapshots: ConfigSnapshot[];
  lastTask: TaskRead | null;
  configTaskRunning: boolean;
  canSubmitChange: boolean;
  canApprove: boolean;
  deviceId?: number;
  onToggleCollapsed: () => void;
  onStartChange: (snapshot: ConfigSnapshot) => void;
  onRollbackSuccess: () => void;
}) {
  const t = useT();
  if (collapsed) {
    return (
      <aside className="flex min-h-0 flex-col items-center gap-3 rounded border border-warm bg-canvas/95 py-3">
        <Button
          aria-label={t("devices.expandStatus")}
          title={t("devices.expandStatus")}
          onClick={onToggleCollapsed}
          className="h-9 w-9 px-0 bg-paper"
        >
          <PanelRightOpen className="h-4 w-4" aria-hidden />
        </Button>
        <div className="h-px w-8 bg-warm" />
        <div className="flex min-h-0 flex-1 items-center justify-center px-2">
          <p className="[writing-mode:vertical-rl] text-xs font-semibold text-muted">
            {t("devices.statusHistory")}
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded border border-warm bg-canvas/95">
      <div className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-warm px-4">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{t("devices.statusHistory")}</h2>
          <p className="font-mono text-[11px] text-muted">{t("devices.statusSubtitle")}</p>
        </div>
        <Button
          aria-label={t("devices.collapseStatus")}
          title={t("devices.collapseStatus")}
          onClick={onToggleCollapsed}
          className="h-9 w-9 px-0 bg-paper"
        >
          <PanelRightClose className="h-4 w-4" aria-hidden />
        </Button>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        <ReadOnlyPanel
          profile={profile}
          lastTask={lastTask}
          configTaskRunning={configTaskRunning}
        />
        <SnapshotTable
          snapshots={snapshots}
          canSubmitChange={canSubmitChange}
          canApprove={canApprove}
          deviceId={deviceId}
          onStartChange={onStartChange}
          onRollbackSuccess={onRollbackSuccess}
        />
        <RecentTasks tasks={profile?.recent_tasks ?? []} />
      </div>
    </aside>
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
  onCreateSuccess,
  onDelete
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
  onDelete: (deviceId: number) => Promise<void>;
}) {
  const t = useT();
  if (mode === "collapsed") {
    const selected = devices.find((device) => device.id === selectedDeviceId);
    return (
      <aside className="flex min-h-0 flex-col items-center gap-2 rounded border border-warm bg-canvas/95 py-3">
        <Button
          aria-label={t("devices.expandList")}
          title={t("devices.expandList")}
          onClick={() => onModeChange("compact")}
          className="h-9 w-9 px-0"
        >
          <PanelLeftOpen className="h-4 w-4" aria-hidden />
        </Button>
        <Button
          aria-label={t("devices.openFullList")}
          title={t("devices.openFullList")}
          onClick={() => onModeChange("expanded")}
          className="h-9 w-9 px-0 bg-paper"
        >
          <Maximize2 className="h-4 w-4" aria-hidden />
        </Button>
        <div className="my-1 h-px w-8 bg-warm" />
        <Button
          aria-label={t("devices.refresh")}
          title={t("devices.refresh")}
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
          <h2 className="text-lg font-semibold">{t("devices.inventory")}</h2>
          <p className="font-mono text-[11px] text-muted">
            {t("devices.visibleCount", { visible: devices.length, total: allDeviceCount })}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            aria-label={t("devices.collapseList")}
            title={t("devices.collapseList")}
            onClick={() => onModeChange("collapsed")}
            className="h-9 w-9 px-0 bg-paper"
          >
            <PanelLeftClose className="h-4 w-4" aria-hidden />
          </Button>
          <Button
            aria-label={mode === "expanded" ? t("devices.compactList") : t("devices.expandList")}
            title={mode === "expanded" ? t("devices.compactList") : t("devices.expandList")}
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
              aria-label={t("devices.add")}
              title={t("devices.add")}
              onClick={onToggleCreate}
              className="h-9 w-9 px-0"
            >
              <Plus className="h-4 w-4" aria-hidden />
            </Button>
          ) : null}
          <Button
            aria-label={t("devices.refresh")}
            title={t("devices.refresh")}
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
            placeholder={t("devices.searchPlaceholder")}
            className="h-9 w-full rounded border border-warm bg-paper pl-8 pr-2 text-sm outline-none transition focus:border-warm-strong"
          />
        </label>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-3">
        {showCreate && canManage ? <CreateDeviceForm onSuccess={onCreateSuccess} /> : null}
        {loading ? <DeviceListSkeleton /> : null}
        {error ? <ErrorPanel message={error} onRetry={onRefresh} /> : null}
        {!loading && !error && allDeviceCount === 0 ? (
          <EmptyState icon={<Router className="h-6 w-6" />} title={t("devices.empty")} />
        ) : null}
        {!loading && !error && allDeviceCount > 0 && devices.length === 0 ? (
          <EmptyState icon={<Search className="h-6 w-6" />} title={t("devices.noMatches")} />
        ) : null}
        {devices.length > 0 && mode === "compact" ? (
          <div className="space-y-2">
            {devices.map((device) => (
              <DeviceListItem
                key={device.id}
                device={device}
                active={device.id === selectedDeviceId}
                canManage={canManage}
                showDelete={false}
                onSelect={() => onSelect(device.id)}
                onDelete={() => onDelete(device.id)}
              />
            ))}
          </div>
        ) : null}
        {devices.length > 0 && mode === "expanded" ? (
          <DeviceInventoryTable
            devices={devices}
            selectedDeviceId={selectedDeviceId}
            canManage={canManage}
            onSelect={onSelect}
            onDelete={onDelete}
          />
        ) : null}
      </div>
    </aside>
  );
}

function DeviceInventoryTable({
  devices,
  selectedDeviceId,
  canManage,
  onSelect,
  onDelete
}: {
  devices: Device[];
  selectedDeviceId: number | null;
  canManage: boolean;
  onSelect: (deviceId: number) => void;
  onDelete: (deviceId: number) => Promise<void>;
}) {
  const t = useT();
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function handleDelete(deviceId: number) {
    setDeletingId(deviceId);
    try {
      await onDelete(deviceId);
    } finally {
      setDeletingId(null);
      setConfirmingId(null);
    }
  }

  return (
    <div className="overflow-x-auto rounded border border-warm">
      <table className="w-full min-w-[1180px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-warm bg-paper/70 text-left font-mono text-[11px] uppercase text-muted">
            <th className="px-3 py-2 font-medium">{t("table.device")}</th>
            <th className="px-3 py-2 font-medium">{t("table.status")}</th>
            <th className="px-3 py-2 font-medium">{t("table.endpoint")}</th>
            <th className="px-3 py-2 font-medium">{t("table.access")}</th>
            <th className="px-3 py-2 font-medium">{t("table.discovery")}</th>
            <th className="px-3 py-2 font-medium">{t("table.onboarding")}</th>
            <th className="px-3 py-2 font-medium">{t("table.baseline")}</th>
            <th className="px-3 py-2 font-medium">{t("table.updated")}</th>
            {canManage ? <th className="px-3 py-2 font-medium">{t("table.actions")}</th> : null}
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
                  <p className="mt-1 font-mono text-[11px] text-muted">#{device.id} · {device.group ?? t("device.ungrouped")}</p>
                  <p className="mt-1 truncate font-mono text-[11px] text-muted">
                    {t("device.serialPrefix", { value: device.serial_number ?? "-" })}
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
                  <p className="mt-1">{connection?.has_credential ? t("device.credentialReferenced") : t("device.credentialMissing")}</p>
                </td>
                <td className="px-3 py-3 text-xs text-muted">
                  <p>{discovery ? t("device.capCount", { count: discovery.capabilities.length }) : "-"}</p>
                  <p className="mt-1">{discovery ? t("device.systemKeyCount", { count: Object.keys(discovery.system_info).length }) : "-"}</p>
                  <p className="mt-1">{discovery ? formatDate(discovery.discovered_at) : "-"}</p>
                </td>
                <td className="px-3 py-3 text-xs text-muted">
                  <div className="mb-2">
                    <StatusBadge status={onboarding ? (onboarding.ready_for_change ? "ready" : "blocked") : "not_started"} />
                  </div>
                  <p>{onboardingSteps(t, onboarding)}</p>
                  <p className="mt-1 truncate" title={onboardingDetail(t, onboarding)}>
                    {onboardingDetail(t, onboarding)}
                  </p>
                </td>
                <td className="px-3 py-3 text-xs text-muted">
                  <p className="font-mono">{digestShort(device.last_config_snapshot?.content_digest)}</p>
                  <p className="mt-1">{device.last_config_snapshot ? formatDate(device.last_config_snapshot.collected_at) : "-"}</p>
                </td>
                <td className="px-3 py-3 text-xs text-muted">{formatDate(device.updated_at)}</td>
                {canManage ? (
                  <td className="px-3 py-3 text-xs" onClick={(e) => e.stopPropagation()}>
                    {confirmingId === device.id ? (
                      <div className="flex items-center gap-1">
                        <span className="mr-1 text-[11px] font-medium text-red-500">{t("common.confirmDelete")}</span>
                        <Button
                          busy={deletingId === device.id}
                          onClick={() => void handleDelete(device.id)}
                          className="h-7 px-2 text-[11px] border-red-400 text-red-500 hover:bg-red-50"
                        >
                          <CheckCircle className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          onClick={() => setConfirmingId(null)}
                          className="h-7 px-2 text-[11px]"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ) : (
                      <Button
                        aria-label={t("devices.delete")}
                        title={t("devices.delete")}
                        onClick={() => setConfirmingId(device.id)}
                        className="h-7 w-7 px-0 text-muted hover:border-red-400 hover:text-red-500"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </td>
                ) : null}
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
  readyForChange,
  submitBusy,
  changeBusy,
  configTaskRunning,
  lastTask,
  changeSummary,
  changeReason,
  configBody,
  preflight,
  onDetailModeChange,
  onCollapseWorkspace,
  onDatastoreChange,
  onRefresh,
  onFullRefresh,
  onCollect,
  onSelectPath,
  onChangeSummaryChange,
  onChangeReasonChange,
  onConfigBodyChange,
  onPreviewChange,
  onSubmitChange
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
  readyForChange: boolean;
  submitBusy: boolean;
  changeBusy: boolean;
  configTaskRunning: boolean;
  lastTask: TaskRead | null;
  changeSummary: string;
  changeReason: string;
  configBody: string;
  preflight: ChangePreflightResponse | null;
  onDetailModeChange: (mode: DeviceDetailMode) => void;
  onCollapseWorkspace: () => void;
  onDatastoreChange: (datastore: string) => void;
  onRefresh: () => void;
  onFullRefresh: () => void;
  onCollect: () => void;
  onSelectPath: (path: string) => void;
  onChangeSummaryChange: (value: string) => void;
  onChangeReasonChange: (value: string) => void;
  onConfigBodyChange: (value: string) => void;
  onPreviewChange: () => void;
  onSubmitChange: () => void;
}) {
  const t = useT();
  const operationalTree = useMemo(
    () => buildOperationalTree(device, snapshots, datastore),
    [datastore, device, snapshots]
  );
  const configTree = useMemo(
    () => buildConfigTree(device, datastore, snapshots),
    [datastore, device, snapshots]
  );
  const yangSchemaIndex = useMemo(
    () => buildYangSchemaIndex(profile, snapshots),
    [profile, snapshots]
  );
  const [changeTarget, setChangeTarget] = useState<ConfigChangeTarget | null>(null);
  const modeDisabledReason = readyForChange
    ? null
    : profile?.onboarding_summary?.blockers.join(", ") || t("onboarding.incomplete");

  function openConfigChange(target: ConfigChangeTarget) {
    setChangeTarget(target);
    onChangeSummaryChange(defaultConfigChangeSummary(target));
    onChangeReasonChange("");
    onConfigBodyChange(buildConfigChangePayload(target.action, target.path, target.currentValue));
  }

  return (
    <>
      <header className="shrink-0 border-b border-warm px-4 py-3">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={profile?.status ?? device.status} />
              <span className="font-mono text-[11px] text-muted">{device.group ?? t("device.ungrouped")}</span>
              <span className="font-mono text-[11px] text-muted">#{device.id}</span>
            </div>
            <h2 className="truncate text-2xl font-semibold">{device.name}</h2>
            <p className="mt-1 truncate font-mono text-xs text-muted">
              {device.connection
                ? `${device.connection.protocol}://${device.connection.host}:${device.connection.port}`
                : t("workspace.connectionUnavailable")}
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            <div
              className="w-full shrink-0 rounded border border-warm bg-paper p-1 shadow-panel sm:w-[268px]"
              role="group"
              aria-label={t("workspace.viewModeLabel")}
            >
              <div className="grid grid-cols-2 gap-1">
                <button
                  onClick={() => onDetailModeChange("operational")}
                  className={cn(
                    "inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded px-2 text-xs font-medium transition",
                    detailMode === "operational" ? "bg-canvas text-ink shadow-panel" : "text-muted hover:text-ink"
                  )}
                >
                  <Gauge className="h-3.5 w-3.5" aria-hidden />
                  <span className="truncate">{t("workspace.readConfig")}</span>
                </button>
                <button
                  onClick={() => onDetailModeChange("config")}
                  className={cn(
                    "inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded px-2 text-xs font-medium transition",
                    detailMode === "config" ? "bg-canvas text-ink shadow-panel" : "text-muted hover:text-ink"
                  )}
                >
                  <FilePenLine className="h-3.5 w-3.5" aria-hidden />
                  <span className="truncate">{t("workspace.changeConfig")}</span>
                </button>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
              <DatastoreSelect value={datastore} onValueChange={onDatastoreChange} />
              <Button
                onClick={onCollect}
                disabled={!canCollect || submitBusy || configTaskRunning}
                busy={submitBusy}
                title={!canCollect ? t("workspace.collectMissingPerm") : undefined}
              >
                <Database className="h-4 w-4" aria-hidden />
                {t("workspace.collect")}
              </Button>
              <Button
                aria-label={t("workspace.fullRefresh")}
                title={t("workspace.fullRefresh")}
                onClick={onFullRefresh}
                disabled={configTaskRunning || submitBusy}
                busy={submitBusy}
                className="h-9 w-9 px-0"
              >
                <RefreshCw className="h-4 w-4" aria-hidden />
              </Button>

            </div>
          </div>
        </div>
      </header>

      {error ? (
        <div className="px-4 pt-4">
          <ErrorPanel message={error} onRetry={onRefresh} />
        </div>
      ) : null}

      {detailMode === "operational" ? (
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <InfoPanel icon={<Settings2 />} title={t("workspace.netconfTree")}>
            <ObjectTree
              data={operationalTree}
              selectedPath={selectedPath}
              onSelectPath={onSelectPath}
            />
          </InfoPanel>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <ConfigModelWorkspace
            data={configTree}
            schemaIndex={yangSchemaIndex}
            selectedPath={selectedPath}
            onSelectPath={onSelectPath}
            onOpenChange={openConfigChange}
          />
          {changeTarget ? (
            <ConfigChangeDialog
              device={device}
              datastore={datastore}
              target={changeTarget}
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
              onClose={() => setChangeTarget(null)}
              onPreview={onPreviewChange}
              onSubmit={onSubmitChange}
            />
          ) : null}
        </div>
      )}
    </>
  );
}

function ConfigModelWorkspace({
  data,
  schemaIndex,
  selectedPath,
  onSelectPath,
  onOpenChange
}: {
  data: Record<string, unknown>;
  schemaIndex: YangSchemaIndex;
  selectedPath: string;
  onSelectPath: (path: string) => void;
  onOpenChange: (target: ConfigChangeTarget) => void;
}) {
  const t = useT();
  const selectedValue = getTreeValueAtPath(data, selectedPath);
  const effectivePath = isObjectLike(selectedValue) ? selectedPath : "root";
  const effectiveValue = isObjectLike(selectedValue) ? selectedValue : data;
  const leafRows = useMemo(
    () => collectLeafRows(effectiveValue, effectivePath, data, schemaIndex),
    [data, effectivePath, effectiveValue, schemaIndex]
  );
  const isMultiInstance = Array.isArray(effectiveValue);
  const listTable = useMemo(
    () => (Array.isArray(effectiveValue) ? collectListTable(effectiveValue, effectivePath, data, schemaIndex) : null),
    [data, effectivePath, effectiveValue, schemaIndex]
  );
  const hasYangModel = schemaIndex.byPath.size + schemaIndex.byNamespacePath.size > 0;

  return (
    <div className="grid min-h-[520px] gap-3 xl:grid-cols-[minmax(260px,0.34fr)_minmax(0,1fr)]">
      <InfoPanel icon={<Settings2 />} title={t("workspace.configTree")}>
        <ParentObjectTree
          data={data}
          selectedPath={effectivePath}
          onSelectPath={onSelectPath}
        />
      </InfoPanel>

      <InfoPanel icon={<FilePenLine />} title="叶子节点表格">
        <div className="min-h-0 space-y-3">
          <div className="flex flex-col gap-2 border-b border-warm pb-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="truncate font-mono text-[11px] text-muted">{effectivePath}</p>
              <p className="mt-1 text-xs text-muted">
                {isMultiInstance ? "多实例列表" : t("tree.childrenCount", { count: leafRows.length })}
                {" · "}
                {hasYangModel ? "已关联 YANG 模型" : "未发现 YANG 模型元数据"}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {isMultiInstance ? (
                <Button
                  className="h-8 px-2 text-xs"
                  onClick={() =>
                    onOpenChange({
                      action: "add-instance",
                      path: `${effectivePath}.*`,
                      label: "新增实例",
                      currentValue: {},
                      schema: matchYangNode(schemaIndex, `${effectivePath}.*`, data)
                    })
                  }
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden />
                  新增实例
                </Button>
              ) : (
                <Button
                  className="h-8 px-2 text-xs"
                  onClick={() =>
                    onOpenChange({
                      action: "add-leaf",
                      path: `${effectivePath}.new_leaf`,
                      label: "新增叶子",
                      currentValue: "",
                      schema: null
                    })
                  }
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden />
                  新增叶子
                </Button>
              )}
            </div>
          </div>

          {isMultiInstance && listTable ? (
            <ListInstanceTable table={listTable} onOpenChange={onOpenChange} />
          ) : (
            <LeafDetailTable leafRows={leafRows} onOpenChange={onOpenChange} />
          )}
        </div>
      </InfoPanel>
    </div>
  );
}

function ListInstanceTable({
  table,
  onOpenChange
}: {
  table: ConfigListTable;
  onOpenChange: (target: ConfigChangeTarget) => void;
}) {
  const t = useT();

  return (
    <div className="overflow-auto rounded border border-warm bg-paper/70">
      <table className="min-w-full text-left text-xs">
        <thead className="sticky top-0 bg-paper text-muted">
          <tr className="border-b border-warm">
            <th className="w-16 min-w-16 px-3 py-2 font-medium">实例</th>
            {table.columns.map((column) => (
              <th key={column.key} className="min-w-44 px-3 py-2 font-medium">
                <span className="block truncate" title={column.label}>
                  {column.label}
                </span>
              </th>
            ))}
            <th className="min-w-20 px-3 py-2 text-right font-medium">{t("table.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row) => (
            <tr key={row.path} className="border-b border-warm/70 last:border-0 hover:bg-canvas/70">
              <td className="sticky left-0 z-10 w-16 min-w-16 border-r border-warm/70 bg-paper/95 px-3 py-2">
                <p className="font-mono text-[11px] font-medium text-ink">{row.label}</p>
              </td>
              {table.columns.map((column) => {
                const cell = row.cells[column.key];
                return (
                  <td key={`${row.path}.${column.key}`} className="max-w-64 px-3 py-2 align-top">
                    {cell ? (
                      <div className="min-w-0">
                        <p className="truncate font-mono text-[11px] text-muted" title={formatTreeValue(cell.value)}>
                          {formatTreeValue(cell.value) || "-"}
                        </p>
                        <span className="mt-1 inline-flex rounded border border-warm bg-canvas px-1.5 font-mono text-[10px] uppercase text-muted">
                          {displayYangType(cell.schema, cell.value)}
                        </span>
                      </div>
                    ) : (
                      <span className="font-mono text-[11px] text-muted">-</span>
                    )}
                  </td>
                );
              })}
              <td className="px-3 py-2">
                <div className="flex justify-end gap-1.5">
                  <Button
                    aria-label={`编辑实例 ${row.label}`}
                    title="编辑实例"
                    className="h-8 w-8 bg-canvas px-0"
                    onClick={() =>
                      onOpenChange({
                        action: "edit-instance",
                        path: row.path,
                        label: `编辑实例 ${row.label}`,
                        currentValue: row.value,
                        schema: null
                      })
                    }
                  >
                    <FilePenLine className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                  <Button
                    aria-label={`删除实例 ${row.label}`}
                    title="删除实例"
                    className="h-8 w-8 bg-canvas px-0 text-error"
                    onClick={() =>
                      onOpenChange({
                        action: "delete-instance",
                        path: row.path,
                        label: `删除实例 ${row.label}`,
                        currentValue: row.value,
                        schema: null
                      })
                    }
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
          {table.rows.length === 0 ? (
            <tr>
              <td colSpan={table.columns.length + 2} className="px-3 py-10">
                <EmptyState icon={<FilePenLine className="h-6 w-6" />} title="暂无实例" />
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function LeafDetailTable({
  leafRows,
  onOpenChange
}: {
  leafRows: ConfigLeafRow[];
  onOpenChange: (target: ConfigChangeTarget) => void;
}) {
  const t = useT();

  return (
    <div className="overflow-auto rounded border border-warm bg-paper/70">
      <table className="min-w-full text-left text-xs">
        <thead className="sticky top-0 bg-paper text-muted">
          <tr className="border-b border-warm">
            <th className="px-3 py-2 font-medium">叶子节点</th>
            <th className="px-3 py-2 font-medium">实例</th>
            <th className="px-3 py-2 font-medium">YANG 模型</th>
            <th className="px-3 py-2 font-medium">类型 / 约束</th>
            <th className="px-3 py-2 font-medium">当前值</th>
            <th className="px-3 py-2 text-right font-medium">{t("table.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {leafRows.map((row) => (
            <tr key={row.path} className="border-b border-warm/70 last:border-0 hover:bg-canvas/70">
              <td className="max-w-[280px] px-3 py-2">
                <p className="truncate font-medium text-ink" title={row.relativePath}>
                  {row.relativePath}
                </p>
                <p className="mt-0.5 truncate font-mono text-[10px] text-muted" title={row.path}>
                  {row.path}
                </p>
              </td>
              <td className="px-3 py-2 font-mono text-[11px] text-muted">
                {row.instanceLabel ?? "-"}
              </td>
              <td className="px-3 py-2">
                <div className="max-w-[220px]">
                  <p className="truncate font-mono text-[11px] text-ink" title={yangModuleLabel(row.schema)}>
                    {yangModuleLabel(row.schema)}
                  </p>
                  <p className="mt-0.5 truncate font-mono text-[10px] text-muted" title={row.schema?.namespace ?? row.namespace ?? ""}>
                    {row.schema?.kind ?? row.schema?.node_type ?? "leaf"}
                  </p>
                </div>
              </td>
              <td className="px-3 py-2">
                <div className="flex max-w-[260px] flex-wrap gap-1.5">
                  <span className="rounded border border-warm bg-canvas px-1.5 font-mono text-[10px] uppercase text-muted">
                    {displayYangType(row.schema, row.value)}
                  </span>
                  {yangConstraintBadges(row.schema).map((badge) => (
                    <span
                      key={badge}
                      className="rounded border border-warm bg-canvas px-1.5 font-mono text-[10px] text-muted"
                      title={badge}
                    >
                      {badge}
                    </span>
                  ))}
                </div>
              </td>
              <td className="max-w-[360px] px-3 py-2">
                <p className="truncate font-mono text-[11px] text-muted" title={formatTreeValue(row.value)}>
                  {formatTreeValue(row.value) || "-"}
                </p>
              </td>
              <td className="px-3 py-2">
                <div className="flex justify-end gap-1.5">
                  <Button
                    aria-label="修改叶子节点"
                    title="修改叶子节点"
                    className="h-8 w-8 bg-canvas px-0"
                    onClick={() =>
                      onOpenChange({
                        action: "edit-leaf",
                        path: row.path,
                        label: row.relativePath,
                        currentValue: row.value,
                        schema: row.schema ?? null
                      })
                    }
                  >
                    <FilePenLine className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                  <Button
                    aria-label="删除叶子节点"
                    title="删除叶子节点"
                    className="h-8 w-8 bg-canvas px-0 text-error"
                    onClick={() =>
                      onOpenChange({
                        action: "delete-leaf",
                        path: row.path,
                        label: row.relativePath,
                        currentValue: row.value,
                        schema: row.schema ?? null
                      })
                    }
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
          {leafRows.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-3 py-10">
                <EmptyState icon={<FilePenLine className="h-6 w-6" />} title="暂无叶子节点" />
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function ParentObjectTree({
  data,
  selectedPath,
  onSelectPath
}: {
  data: unknown;
  selectedPath: string;
  onSelectPath: (path: string) => void;
}) {
  const t = useT();
  const [openPaths, setOpenPaths] = useState<Set<string>>(
    () => new Set(["root", "root.data"])
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
        <p className="min-w-0 truncate font-mono text-[11px] text-muted">{selectedPath}</p>
        <div className="flex shrink-0 gap-1.5">
          <Button aria-label={t("common.expandAll")} title={t("common.expandAll")} onClick={expandAll} className="h-8 w-8 bg-paper px-0">
            <ChevronsRight className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <Button aria-label={t("common.collapseAll")} title={t("common.collapseAll")} onClick={collapseAll} className="h-8 w-8 bg-paper px-0">
            <ChevronsLeft className="h-3.5 w-3.5" aria-hidden />
          </Button>
        </div>
      </div>
      <div className="max-h-[64dvh] overflow-auto rounded border border-warm bg-paper/70 p-2">
        <ParentTreeRows
          label="root"
          value={data}
          path="root"
          depth={0}
          openPaths={openPaths}
          selectedPath={selectedPath}
          onToggle={toggle}
          onSelectPath={onSelectPath}
        />
      </div>
    </div>
  );
}

function ParentTreeRows({
  label,
  value,
  path,
  depth,
  openPaths,
  selectedPath,
  onToggle,
  onSelectPath
}: {
  label: string;
  value: unknown;
  path: string;
  depth: number;
  openPaths: Set<string>;
  selectedPath: string;
  onToggle: (path: string) => void;
  onSelectPath: (path: string) => void;
}) {
  const t = useT();
  if (!isObjectLike(value)) return null;
  const open = openPaths.has(path);
  const entries = objectEntries(value);
  const childParents = entries.filter(([, childValue]) => isObjectLike(childValue));
  const leafCount = countLeaves(value);

  return (
    <div>
      <div
        className={cn(
          "grid min-h-9 grid-cols-[minmax(140px,1fr)_auto] items-center gap-2 rounded px-2 text-sm transition",
          selectedPath === path ? "bg-canvas" : "hover:bg-canvas/70"
        )}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        <button
          type="button"
          onClick={() => {
            onSelectPath(path);
            if (childParents.length > 0) onToggle(path);
          }}
          className="flex min-w-0 items-center gap-1.5 text-left"
        >
          {childParents.length > 0 ? (
            open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />
          ) : (
            <span className="h-3.5 w-3.5 shrink-0" />
          )}
          <span className="truncate font-medium">{label}</span>
          <span className="shrink-0 rounded border border-warm bg-paper px-1.5 font-mono text-[10px] uppercase text-muted">
            {treeType(value)}
          </span>
        </button>
        <span className="font-mono text-[10px] text-muted">
          {t("tree.itemsCount", { count: leafCount })}
        </span>
      </div>
      {open && childParents.length > 0 ? (
        <div>
          {childParents.map(([childLabel, childValue]) => (
            <ParentTreeRows
              key={`${path}.${childLabel}`}
              label={childLabel}
              value={childValue}
              path={`${path}.${childLabel}`}
              depth={depth + 1}
              openPaths={openPaths}
              selectedPath={selectedPath}
              onToggle={onToggle}
              onSelectPath={onSelectPath}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ConfigChangeDialog({
  device,
  datastore,
  target,
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
  onClose,
  onPreview,
  onSubmit
}: {
  device: Device;
  datastore: string;
  target: ConfigChangeTarget;
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
  onClose: () => void;
  onPreview: () => void;
  onSubmit: () => void;
}) {
  const t = useT();
  const [targetPath, setTargetPath] = useState(target.path);
  const [targetValue, setTargetValue] = useState(formatTreeValue(target.currentValue));
  const blocked = !canSubmitChange || Boolean(disabledReason);
  const isDeleteAction = target.action === "delete-leaf" || target.action === "delete-instance";
  const missingRequired = !changeSummary.trim() || !changeReason.trim() || (!isDeleteAction && !configBody.trim());

  useEffect(() => {
    setTargetPath(target.path);
    const nextValue = formatInputValueForSchema(target.currentValue, target.schema);
    setTargetValue(nextValue);
  }, [target]);

  function updateGeneratedPayload(path: string, value: string) {
    if (target.action === "delete-leaf" || target.action === "delete-instance") {
      onConfigBodyChange(buildConfigChangePayload(target.action, path, target.currentValue));
      return;
    }
    onConfigBodyChange(buildConfigChangePayload(target.action, path, value));
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 p-3 backdrop-blur-sm">
      <div className="flex max-h-[92dvh] w-full max-w-3xl flex-col overflow-hidden rounded border border-warm bg-canvas shadow-2xl">
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-warm px-4 py-3">
          <div className="min-w-0">
            <p className="font-mono text-[11px] uppercase text-muted">{configChangeActionLabel(target.action)}</p>
            <h3 className="mt-1 truncate text-lg font-semibold">{t("change.controlTitle")}</h3>
            <p className="mt-1 truncate font-mono text-xs text-muted">{target.label}</p>
          </div>
          <Button aria-label={t("common.cancel")} title={t("common.cancel")} onClick={onClose} className="h-8 w-8 bg-paper px-0">
            <XCircle className="h-4 w-4" aria-hidden />
          </Button>
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-auto px-4 py-3">
          <div className="grid grid-cols-2 gap-3">
            <Metric label={t("common.device")} value={`#${device.id}`} />
            <Metric label={t("common.datastore")} value={datastore} />
          </div>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <div>
              <FieldLabel>目标路径</FieldLabel>
              <input
                value={targetPath}
                onChange={(event) => {
                  setTargetPath(event.target.value);
                  updateGeneratedPayload(event.target.value, targetValue);
                }}
                className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 font-mono text-xs outline-none focus:border-warm-strong"
              />
            </div>
            <div>
              <FieldLabel>YANG 类型</FieldLabel>
              <div className="mt-1 min-h-9 rounded border border-warm bg-paper px-2 py-1.5">
                <p className="truncate font-mono text-xs text-ink">
                  {displayYangType(target.schema, target.currentValue)}
                </p>
                <p className="mt-0.5 truncate font-mono text-[10px] text-muted" title={yangNodePathLabel(target.schema)}>
                  {yangNodePathLabel(target.schema)}
                </p>
              </div>
            </div>
          </div>
          <TypedYangValueEditor
            action={target.action}
            schema={target.schema}
            value={targetValue}
            currentValue={target.currentValue}
            onChange={(value) => {
              setTargetValue(value);
              updateGeneratedPayload(targetPath, value);
            }}
          />
          <div>
            <FieldLabel>{t("change.summary")}</FieldLabel>
            <input
              value={changeSummary}
              onChange={(event) => onChangeSummaryChange(event.target.value)}
              className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm outline-none focus:border-warm-strong"
            />
          </div>
          <div>
            <FieldLabel>{t("change.reason")}</FieldLabel>
            <textarea
              value={changeReason}
              onChange={(event) => onChangeReasonChange(event.target.value)}
              rows={3}
              className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm outline-none focus:border-warm-strong"
            />
          </div>
          <div className="rounded border border-warm bg-paper p-3">
            <div className="grid gap-2 text-xs text-muted sm:grid-cols-3">
              <Metric label="操作" value={configChangeActionLabel(target.action)} />
              <Metric label="模型" value={yangModuleLabel(target.schema)} />
              <Metric label="内部请求大小" value={`${configBody.length} bytes`} />
            </div>
          </div>
          {preflight ? <PreflightSummary preflight={preflight} compact /> : null}
          {!canSubmitChange ? <p className="text-xs text-warn">{t("change.requireSubmitPerm")}</p> : null}
          {disabledReason ? <p className="text-xs text-warn">{disabledReason}</p> : null}
        </div>

        <div className="flex shrink-0 flex-wrap justify-end gap-2 border-t border-warm px-4 py-3">
          <Button onClick={onClose} className="bg-paper">
            {t("common.cancel")}
          </Button>
          <Button
            onClick={onPreview}
            busy={busy}
            disabled={blocked || missingRequired || busy}
          >
            <Sparkles className="h-4 w-4" aria-hidden />
            {t("change.preview")}
          </Button>
          <Button
            onClick={onSubmit}
            busy={busy}
            disabled={blocked || missingRequired || busy || !preflight?.passed}
          >
            <Send className="h-4 w-4" aria-hidden />
            {t("change.submit")}
          </Button>
        </div>
      </div>
    </div>
  );
}

function TypedYangValueEditor({
  action,
  schema,
  value,
  currentValue,
  onChange
}: {
  action: ConfigChangeAction;
  schema?: YangNodeInfo | null;
  value: string;
  currentValue: unknown;
  onChange: (value: string) => void;
}) {
  const isDeleteAction = action === "delete-leaf" || action === "delete-instance";
  const yangType = normalizedYangType(schema, currentValue);
  const enumOptions = yangEnumOptions(schema);
  const range = yangRange(schema);
  const isInstance = action === "edit-instance" || action === "add-instance";

  if (isDeleteAction) {
    return (
      <div className="rounded border border-error/20 bg-error/10 p-3 text-xs text-error">
        删除操作不需要填写目标值；提交前仍会执行服务端预检。
      </div>
    );
  }

  if (isInstance) {
    return (
      <div>
        <FieldLabel>实例内容</FieldLabel>
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          rows={6}
          spellCheck={false}
          className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 font-mono text-xs outline-none focus:border-warm-strong"
        />
      </div>
    );
  }

  if (enumOptions.length > 0) {
    return (
      <div>
        <FieldLabel>目标值</FieldLabel>
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="mt-1 h-9 w-full rounded border border-warm bg-paper px-2 text-sm outline-none focus:border-warm-strong"
        >
          {enumOptions.map((option) => (
            <option key={option.name} value={option.name}>
              {option.name}{option.value !== undefined && option.value !== null ? ` (${option.value})` : ""}
            </option>
          ))}
        </select>
        <YangInputHint schema={schema} />
      </div>
    );
  }

  if (yangType === "boolean" || yangType === "bool") {
    return (
      <div>
        <FieldLabel>目标值</FieldLabel>
        <div className="mt-1 grid w-full max-w-xs grid-cols-2 gap-1 rounded border border-warm bg-paper p-1">
          {["true", "false"].map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => onChange(option)}
              className={cn(
                "h-8 rounded px-2 text-sm font-medium transition",
                value === option ? "bg-canvas text-ink shadow-panel" : "text-muted hover:text-ink"
              )}
            >
              {option}
            </button>
          ))}
        </div>
        <YangInputHint schema={schema} />
      </div>
    );
  }

  if (yangType === "empty") {
    return (
      <label className="flex items-center gap-2 rounded border border-warm bg-paper px-3 py-2 text-sm">
        <input
          type="checkbox"
          checked={value === "true" || value === ""}
          onChange={(event) => onChange(event.target.checked ? "true" : "false")}
          className="h-4 w-4"
        />
        <span>设置 presence leaf</span>
      </label>
    );
  }

  if (isNumericYangType(yangType)) {
    return (
      <div>
        <FieldLabel>目标值</FieldLabel>
        <input
          type="number"
          value={value}
          min={range?.min}
          max={range?.max}
          step={yangType === "decimal64" ? "any" : "1"}
          onChange={(event) => onChange(event.target.value)}
          className="mt-1 h-9 w-full rounded border border-warm bg-paper px-2 font-mono text-sm outline-none focus:border-warm-strong"
        />
        <YangInputHint schema={schema} />
      </div>
    );
  }

  return (
    <div>
      <FieldLabel>目标值</FieldLabel>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 h-9 w-full rounded border border-warm bg-paper px-2 font-mono text-sm outline-none focus:border-warm-strong"
      />
      <YangInputHint schema={schema} />
    </div>
  );
}

function YangInputHint({ schema }: { schema?: YangNodeInfo | null }) {
  const badges = yangConstraintBadges(schema);
  if (!schema && badges.length === 0) {
    return <p className="mt-1 text-xs text-muted">未匹配到 get-schema 节点定义，按当前值类型兜底。</p>;
  }
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {badges.map((badge) => (
        <span key={badge} className="rounded border border-warm bg-paper px-1.5 font-mono text-[10px] text-muted">
          {badge}
        </span>
      ))}
      {schema?.description ? (
        <span className="min-w-0 flex-1 truncate text-xs text-muted" title={schema.description}>
          {schema.description}
        </span>
      ) : null}
    </div>
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
  const t = useT();
  const [openPaths, setOpenPaths] = useState<Set<string>>(
    () => new Set(["root", "root.data"])
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
          <Button aria-label={t("common.expandAll")} title={t("common.expandAll")} onClick={expandAll} className="h-8 w-8 px-0 bg-paper">
            <ChevronsRight className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <Button aria-label={t("common.collapseAll")} title={t("common.collapseAll")} onClick={collapseAll} className="h-8 w-8 px-0 bg-paper">
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
  const t = useT();
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
              {objectLike
                ? Array.isArray(value)
                  ? t("tree.itemsCount", { count: entries.length })
                  : t("tree.childrenCount", { count: entries.length })
                : formatTreeValue(value)}
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

function unwrapNetconfTree(tree: Record<string, unknown>): Record<string, unknown> {
  const keys = Object.keys(tree);
  if (keys.length !== 1 || keys[0] === "unparsed_content" || keys[0] === "unavailable") {
    return tree;
  }
  const inner = tree[keys[0]];
  if (!inner || typeof inner !== "object" || Array.isArray(inner)) {
    return tree;
  }
  const innerObj = inner as Record<string, unknown>;
  // Unwrap rpc-reply (or any single root wrapper) that contains a "data" element,
  // returning the data children directly so the actual config modules are at the top level.
  if ("data" in innerObj) {
    const data = innerObj["data"];
    if (data && typeof data === "object" && !Array.isArray(data)) {
      return data as Record<string, unknown>;
    }
  }
  // Root element is itself the config container (e.g. <data> was the XML root).
  return innerObj;
}

function buildOperationalTree(
  device: Device,
  snapshots: ConfigSnapshot[],
  datastore: string
): Record<string, unknown> {
  const matchingSnapshot =
    snapshots.find((s) => s.datastore === datastore) ??
    (device.last_config_snapshot?.datastore === datastore ? device.last_config_snapshot : null);
  const latest = matchingSnapshot ?? snapshots[0] ?? device.last_config_snapshot ?? null;

  if (latest?.config_tree) {
    return unwrapNetconfTree(latest.config_tree);
  }

  return {
    unavailable: {
      reason: latest
        ? latest.config_tree === undefined
          ? "snapshot_not_yet_loaded"
          : "no_content"
        : "no_snapshot_collected",
      snapshot_id: latest?.id ?? null,
      datastore
    }
  };
}

function buildConfigTree(
  device: Device,
  datastore: string,
  snapshots: ConfigSnapshot[]
): Record<string, unknown> {
  const latestForDatastore =
    snapshots.find((snapshot) => snapshot.datastore === datastore) ??
    (device.last_config_snapshot?.datastore === datastore ? device.last_config_snapshot : null);
  const latest = latestForDatastore ?? snapshots[0] ?? device.last_config_snapshot ?? null;

  if (latest?.config_tree) {
    return unwrapNetconfTree(latest.config_tree);
  }

  return {
    unavailable: {
      reason: latest ? "snapshot_content_tree_not_loaded" : "no_config_snapshot_collected",
      snapshot_id: latest?.id ?? null,
      datastore
    }
  };
}

function buildYangSchemaIndex(profile: DeviceProfile | null, snapshots: ConfigSnapshot[]): YangSchemaIndex {
  const nodes = extractYangNodes(profile, snapshots);
  const byPath = new Map<string, YangNodeInfo>();
  const byNamespacePath = new Map<string, YangNodeInfo>();
  const byName = new Map<string, YangNodeInfo[]>();

  for (const node of nodes) {
    const normalizedPaths = [
      node.path,
      node.absolute_path,
      node.qname,
    ]
      .map((path) => normalizeYangPath(path))
      .filter(Boolean);
    for (const path of normalizedPaths) {
      byPath.set(path, node);
      if (node.namespace) byNamespacePath.set(`${node.namespace}|${path}`, node);
    }
    const name = normalizeYangName(node.name ?? node.qname ?? lastPathSegment(node.path ?? node.absolute_path));
    if (name) {
      const list = byName.get(name) ?? [];
      list.push(node);
      byName.set(name, list);
    }
  }

  return { byPath, byNamespacePath, byName };
}

function extractYangNodes(profile: DeviceProfile | null, snapshots: ConfigSnapshot[]): YangNodeInfo[] {
  const roots = [
    profile?.system_info,
    profile?.last_discovery?.summary,
    profile?.metadata,
    ...snapshots.map((snapshot) => snapshot.summary),
    ...snapshots.map((snapshot) => snapshot.diff_summary),
  ];
  const nodes: YangNodeInfo[] = [];
  const seen = new Set<string>();
  for (const root of roots) {
    collectYangNodes(root, nodes, seen);
  }
  return nodes;
}

function collectYangNodes(value: unknown, nodes: YangNodeInfo[], seen: Set<string>) {
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    for (const item of value) collectYangNodes(item, nodes, seen);
    return;
  }

  const record = value as Record<string, unknown>;
  if (looksLikeYangNode(record)) {
    const node = normalizeYangNode(record);
    const key = `${node.namespace ?? ""}|${node.path ?? node.absolute_path ?? ""}|${node.name ?? ""}|${node.type ?? ""}`;
    if (!seen.has(key)) {
      seen.add(key);
      nodes.push(node);
    }
  }

  for (const [key, child] of Object.entries(record)) {
    if (key === "raw" || key === "config_tree") continue;
    if (typeof child === "string" && mayContainYangSource(key, child)) {
      for (const parsedNode of parseYangModuleNodes(child)) {
        const nodeKey = `${parsedNode.namespace ?? ""}|${parsedNode.path ?? ""}|${parsedNode.name ?? ""}|${parsedNode.type ?? ""}`;
        if (!seen.has(nodeKey)) {
          seen.add(nodeKey);
          nodes.push(parsedNode);
        }
      }
      continue;
    }
    if (key === "nodes" && child && typeof child === "object" && !Array.isArray(child)) {
      for (const [nodePath, nodeValue] of Object.entries(child as Record<string, unknown>)) {
        if (nodeValue && typeof nodeValue === "object" && !Array.isArray(nodeValue)) {
          collectYangNodes({ ...(nodeValue as Record<string, unknown>), path: nodePath }, nodes, seen);
        }
      }
      continue;
    }
    collectYangNodes(child, nodes, seen);
  }
}

function mayContainYangSource(key: string, value: string): boolean {
  const loweredKey = key.toLowerCase();
  if (!loweredKey.includes("yang") && !loweredKey.includes("schema")) return false;
  return /\b(module|submodule)\s+[-\w.]+\s*\{/.test(value) && /\bnamespace\s+["'][^"']+["']\s*;/.test(value);
}

function parseYangModuleNodes(source: string): YangNodeInfo[] {
  const text = stripYangComments(source);
  const moduleName = matchYangString(text, /\bmodule\s+([-\w.]+)\s*\{/);
  const namespace = matchYangString(text, /\bnamespace\s+["']([^"']+)["']\s*;/);
  const prefix = matchYangString(text, /\bprefix\s+["']?([-\w.]+)["']?\s*;/);
  const rootStart = text.indexOf("{");
  const rootEnd = rootStart >= 0 ? findMatchingBrace(text, rootStart) : -1;
  if (rootStart < 0 || rootEnd < 0) return [];
  const body = text.slice(rootStart + 1, rootEnd);
  const nodes: YangNodeInfo[] = [];
  collectYangBlocks(body, {
    module: moduleName,
    namespace,
    prefix,
    parentPath: "",
    inheritedConfig: undefined,
    nodes,
  });
  return nodes;
}

function collectYangBlocks(
  text: string,
  context: {
    module?: string;
    namespace?: string;
    prefix?: string;
    parentPath: string;
    inheritedConfig?: boolean;
    nodes: YangNodeInfo[];
  }
) {
  const nodeRegex = /\b(container|list|leaf|leaf-list)\s+([-\w:.]+)\s*(\{|;)/g;
  let match: RegExpExecArray | null;
  while ((match = nodeRegex.exec(text)) !== null) {
    const kind = match[1];
    const name = normalizeYangName(match[2]);
    const startsBlock = match[3] === "{";
    const openIndex = text.indexOf("{", match.index);
    const closeIndex = startsBlock ? findMatchingBrace(text, openIndex) : -1;
    const body = startsBlock && closeIndex > openIndex ? text.slice(openIndex + 1, closeIndex) : "";
    const path = context.parentPath ? `${context.parentPath}/${name}` : `/${name}`;
    const config = parseYangBoolean(body, "config") ?? context.inheritedConfig;
    const node: YangNodeInfo = {
      name,
      path,
      module: context.module,
      namespace: context.namespace,
      prefix: context.prefix,
      kind,
      node_type: kind,
      type: parseYangType(body),
      enum_values: parseYangEnums(body),
      range: parseYangTypeArgument(body, "range"),
      length: parseYangTypeArgument(body, "length"),
      pattern: parseYangTypeArgument(body, "pattern"),
      units: matchYangString(body, /\bunits\s+["']?([^"';]+)["']?\s*;/),
      default: matchYangString(body, /\bdefault\s+["']?([^"';]+)["']?\s*;/),
      mandatory: parseYangBoolean(body, "mandatory"),
      config,
      status: matchYangString(body, /\bstatus\s+([-\w]+)\s*;/),
      description: matchYangString(body, /\bdescription\s+"([^"]*)"\s*;/),
      key: matchYangString(body, /\bkey\s+"([^"]+)"\s*;/),
    };
    context.nodes.push(node);
    if (body) {
      collectYangBlocks(body, {
        ...context,
        parentPath: path,
        inheritedConfig: config,
      });
    }
    if (closeIndex > match.index) nodeRegex.lastIndex = closeIndex + 1;
  }
}

function parseYangType(body: string): string | undefined {
  const typeMatch = /\btype\s+([-\w:.]+)\s*(\{|;)/.exec(body);
  return typeMatch ? normalizeYangName(typeMatch[1]) : undefined;
}

function parseYangEnums(body: string): YangEnumOption[] | undefined {
  const typeMatch = /\btype\s+enumeration\s*\{/.exec(body);
  if (!typeMatch) return undefined;
  const openIndex = body.indexOf("{", typeMatch.index);
  const closeIndex = findMatchingBrace(body, openIndex);
  if (closeIndex <= openIndex) return undefined;
  const typeBody = body.slice(openIndex + 1, closeIndex);
  const values: YangEnumOption[] = [];
  const enumRegex = /\benum\s+([-\w:.]+)\s*(\{|;)/g;
  let match: RegExpExecArray | null;
  while ((match = enumRegex.exec(typeBody)) !== null) {
    const name = normalizeYangName(match[1]);
    const blockStart = typeBody.indexOf("{", match.index);
    const blockEnd = match[2] === "{" ? findMatchingBrace(typeBody, blockStart) : -1;
    const enumBody = blockEnd > blockStart ? typeBody.slice(blockStart + 1, blockEnd) : "";
    values.push({
      name,
      value: matchYangString(enumBody, /\bvalue\s+(-?\d+)\s*;/) ?? null,
      description: matchYangString(enumBody, /\bdescription\s+"([^"]*)"\s*;/) ?? null,
    });
    if (blockEnd > match.index) enumRegex.lastIndex = blockEnd + 1;
  }
  return values.length > 0 ? values : undefined;
}

function parseYangTypeArgument(body: string, argument: "range" | "length" | "pattern"): string | undefined {
  const regex = new RegExp(`\\b${argument}\\s+["']?([^;"']+)["']?\\s*;`);
  return matchYangString(body, regex);
}

function parseYangBoolean(body: string, field: "mandatory" | "config"): boolean | undefined {
  const raw = matchYangString(body, new RegExp(`\\b${field}\\s+(true|false)\\s*;`));
  return raw === undefined ? undefined : raw === "true";
}

function stripYangComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
}

function findMatchingBrace(text: string, openIndex: number): number {
  if (openIndex < 0 || text[openIndex] !== "{") return -1;
  let depth = 0;
  let quote: string | null = null;
  for (let index = openIndex; index < text.length; index += 1) {
    const char = text[index];
    const prev = text[index - 1];
    if (quote) {
      if (char === quote && prev !== "\\") quote = null;
      continue;
    }
    if (char === "\"" || char === "'") {
      quote = char;
      continue;
    }
    if (char === "{") depth += 1;
    if (char === "}") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return -1;
}

function matchYangString(text: string, regex: RegExp): string | undefined {
  const match = regex.exec(text);
  return match?.[1]?.trim();
}

function looksLikeYangNode(record: Record<string, unknown>): boolean {
  const hasType = ["type", "base_type", "type_name"].some((key) => typeof record[key] === "string");
  const hasPath = ["path", "absolute_path", "qname", "name"].some((key) => typeof record[key] === "string");
  const kind = String(record.kind ?? record.node_type ?? "").toLowerCase();
  return hasPath && (hasType || ["leaf", "leaf-list", "container", "list"].includes(kind));
}

function normalizeYangNode(record: Record<string, unknown>): YangNodeInfo {
  const stringList = (value: unknown): Array<string | YangEnumOption> | undefined => {
    if (!Array.isArray(value)) return undefined;
    return value
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const obj = item as Record<string, unknown>;
          const name = String(obj.name ?? obj.label ?? obj.value ?? "");
          if (!name) return null;
          return {
            name,
            value: typeof obj.value === "string" || typeof obj.value === "number" ? obj.value : null,
            description: typeof obj.description === "string" ? obj.description : null,
          };
        }
        return null;
      })
      .filter(Boolean) as Array<string | YangEnumOption>;
  };

  return {
    name: asString(record.name) ?? normalizeYangName(asString(record.qname) ?? lastPathSegment(asString(record.path) ?? asString(record.absolute_path))),
    qname: asString(record.qname),
    path: asString(record.path),
    absolute_path: asString(record.absolute_path),
    module: asString(record.module) ?? asString(record.module_name),
    namespace: asString(record.namespace) ?? asString(record.xmlns) ?? asString(record.module_namespace),
    prefix: asString(record.prefix),
    kind: asString(record.kind) ?? asString(record.node_type),
    node_type: asString(record.node_type),
    type: asString(record.type) ?? asString(record.type_name) ?? asString(record.base_type),
    base_type: asString(record.base_type),
    type_name: asString(record.type_name),
    description: asString(record.description),
    units: asString(record.units),
    default: record.default,
    mandatory: asBoolean(record.mandatory),
    config: asBoolean(record.config),
    status: asString(record.status),
    range: asString(record.range),
    length: asString(record.length),
    pattern: asString(record.pattern),
    key: typeof record.key === "string" || Array.isArray(record.key) ? record.key as string | string[] : null,
    leafref_path: asString(record.leafref_path) ?? asString(record.path_arg),
    enum_values: stringList(record.enum_values ?? record.enums),
    values: stringList(record.values),
    options: stringList(record.options),
  };
}

function matchYangNode(
  index: YangSchemaIndex,
  path: string,
  root: unknown
): YangNodeInfo | null {
  const normalizedPath = normalizeUiPath(path);
  const namespace = namespaceForPath(root, path);
  if (namespace) {
    const direct = index.byNamespacePath.get(`${namespace}|${normalizedPath}`);
    if (direct) return direct;
  }
  const direct = index.byPath.get(normalizedPath);
  if (direct) return direct;

  for (const [schemaPath, node] of index.byPath.entries()) {
    if (normalizedPath.endsWith(schemaPath) || schemaPath.endsWith(normalizedPath)) {
      if (!namespace || !node.namespace || node.namespace === namespace) return node;
    }
  }

  const looseSuffixMatches = Array.from(index.byPath.entries())
    .filter(([schemaPath]) => schemaPath.split(".").length >= 2 && normalizedPath.endsWith(schemaPath))
    .map(([, node]) => node);
  const looseSuffixNode = uniqueYangNode(looseSuffixMatches);
  if (looseSuffixNode) return looseSuffixNode;

  const localName = lastPathSegment(path);
  const candidates = index.byName.get(normalizeYangName(localName)) ?? [];
  if (namespace) {
    const byNamespace = candidates.find((node) => node.namespace === namespace);
    if (byNamespace) return byNamespace;
  }
  const contextMatch = chooseYangNodeByContext(normalizedPath, candidates);
  if (contextMatch) return contextMatch;
  return candidates.length === 1 ? candidates[0] : null;
}

function uniqueYangNode(candidates: YangNodeInfo[]): YangNodeInfo | null {
  const keyed = new Map<string, YangNodeInfo>();
  for (const candidate of candidates) {
    const key = `${candidate.namespace ?? ""}|${candidate.path ?? ""}|${candidate.type ?? ""}|${candidate.kind ?? ""}`;
    keyed.set(key, candidate);
  }
  return keyed.size === 1 ? Array.from(keyed.values())[0] : null;
}

function chooseYangNodeByContext(normalizedPath: string, candidates: YangNodeInfo[]): YangNodeInfo | null {
  const leafCandidates = candidates.filter((node) => {
    const kind = (node.kind ?? node.node_type ?? "").toLowerCase();
    return kind === "leaf" || kind === "leaf-list" || (!kind && normalizedYangType(node) !== "node");
  });
  if (leafCandidates.length === 0) return null;

  const scored = leafCandidates
    .map((node) => ({ node, score: yangContextScore(normalizedPath, node) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score);
  if (scored.length === 0) return null;
  if (scored.length === 1 || scored[0].score > scored[1].score) return scored[0].node;
  return null;
}

function yangContextScore(normalizedPath: string, node: YangNodeInfo): number {
  let score = 0;
  const type = normalizedYangType(node);
  const schemaPath = normalizeYangPath(node.path ?? node.absolute_path ?? node.qname);
  if (schemaPath && normalizedPath.endsWith(schemaPath)) score += 80;
  if (normalizedPath.includes("public-key") || normalizedPath.includes("host-key")) {
    if (type.includes("asymmetric")) score += 40;
    if (type.includes("symmetric")) score -= 20;
  }
  if (normalizedPath.includes("symmetric") && type.includes("symmetric")) score += 30;
  if (normalizedPath.includes("certificate") && type.includes("cert")) score += 20;
  if (type && type !== "string") score += 5;
  return score;
}

function namespaceForPath(root: unknown, path: string): string | null {
  if (path === "root") return null;
  const segments = path.split(".").slice(1).filter((segment) => segment !== "*");
  let current = root;
  let namespace: string | null = null;
  for (const segment of segments) {
    if (!isObjectLike(current)) return namespace;
    if (!Array.isArray(current) && typeof (current as Record<string, unknown>)["_namespace"] === "string") {
      namespace = (current as Record<string, unknown>)["_namespace"] as string;
    }
    current = Array.isArray(current)
      ? current[Number(segment)]
      : (current as Record<string, unknown>)[segment];
  }
  return namespace;
}

function normalizeUiPath(path: string): string {
  return path
    .split(".")
    .filter((segment) => segment !== "root" && segment !== "data" && segment !== "rpc-reply")
    .filter((segment) => !/^\d+$/.test(segment) && segment !== "*")
    .filter((segment) => !segment.startsWith("_"))
    .map(normalizeYangName)
    .filter(Boolean)
    .join(".");
}

function normalizeYangPath(path: string | undefined | null): string {
  if (!path) return "";
  return path
    .replace(/\[[^\]]+\]/g, "")
    .split(/[/.]/)
    .map((part) => normalizeYangName(part.trim()))
    .filter((part) => part && part !== "root" && part !== "data" && part !== "rpc-reply")
    .join(".");
}

function normalizeYangName(name: string | undefined | null): string {
  if (!name) return "";
  return name.replace(/^.*:/, "").replace(/\[[^\]]+\]/g, "").trim();
}

function lastPathSegment(path: string | undefined | null): string {
  if (!path) return "";
  const segments = path.split(/[/.]/).filter(Boolean);
  return normalizeYangName(segments[segments.length - 1] ?? "");
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function normalizedYangType(schema: YangNodeInfo | null | undefined, currentValue?: unknown): string {
  const raw = schema?.base_type ?? schema?.type ?? schema?.type_name;
  if (raw) return raw.replace(/^.*:/, "").toLowerCase();
  if (typeof currentValue === "boolean") return "boolean";
  if (typeof currentValue === "number") return Number.isInteger(currentValue) ? "int32" : "decimal64";
  return treeType(currentValue);
}

function displayYangType(schema: YangNodeInfo | null | undefined, currentValue?: unknown): string {
  const type = schema?.type ?? schema?.type_name ?? schema?.base_type;
  if (type) return type;
  return treeType(currentValue);
}

function yangModuleLabel(schema: YangNodeInfo | null | undefined): string {
  if (!schema) return "未匹配";
  return schema.module ?? schema.prefix ?? schema.namespace ?? "YANG";
}

function yangNodePathLabel(schema: YangNodeInfo | null | undefined): string {
  if (!schema) return "未匹配 get-schema 节点";
  return schema.absolute_path ?? schema.path ?? schema.qname ?? schema.name ?? "YANG node";
}

function yangConstraintBadges(schema: YangNodeInfo | null | undefined): string[] {
  if (!schema) return [];
  const badges: string[] = [];
  if (schema.mandatory) badges.push("mandatory");
  if (schema.config === false) badges.push("read-only");
  if (schema.range) badges.push(`range ${schema.range}`);
  if (schema.length) badges.push(`length ${schema.length}`);
  if (schema.pattern) badges.push("pattern");
  if (schema.units) badges.push(schema.units);
  if (schema.default !== undefined && schema.default !== null) badges.push(`default ${formatTreeValue(schema.default)}`);
  const enumCount = yangEnumOptions(schema).length;
  if (enumCount > 0) badges.push(`${enumCount} enums`);
  return badges;
}

function yangEnumOptions(schema: YangNodeInfo | null | undefined): YangEnumOption[] {
  const options = schema?.enum_values ?? schema?.values ?? schema?.options ?? [];
  return options
    .map((option) =>
      typeof option === "string"
        ? { name: option }
        : { name: option.name, value: option.value, description: option.description }
    )
    .filter((option) => option.name);
}

function yangRange(schema: YangNodeInfo | null | undefined): { min?: string; max?: string } | null {
  const range = schema?.range;
  if (!range || range.includes("|")) return null;
  const [min, max] = range.split("..").map((part) => part.trim());
  if (!min && !max) return null;
  return {
    min: min && min !== "min" ? min : undefined,
    max: max && max !== "max" ? max : undefined,
  };
}

function isNumericYangType(type: string): boolean {
  return [
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "decimal64",
  ].includes(type);
}

function formatInputValueForSchema(value: unknown, schema?: YangNodeInfo | null): string {
  const enumOptions = yangEnumOptions(schema);
  if ((value === undefined || value === null || value === "") && enumOptions.length > 0) {
    return enumOptions[0]?.name ?? "";
  }
  const type = normalizedYangType(schema, value);
  if ((type === "boolean" || type === "bool") && typeof value !== "boolean") {
    return String(value).toLowerCase() === "false" ? "false" : "true";
  }
  return formatTreeValue(value);
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

function getTreeValueAtPath(data: unknown, path: string): unknown {
  if (path === "root") return data;
  const segments = path.split(".").slice(1);
  let current = data;
  for (const segment of segments) {
    if (!isObjectLike(current)) return undefined;
    current = Array.isArray(current)
      ? current[Number(segment)]
      : (current as Record<string, unknown>)[segment];
  }
  return current;
}

function collectLeafRows(
  value: unknown,
  basePath: string,
  root: unknown,
  schemaIndex: YangSchemaIndex
): ConfigLeafRow[] {
  const rows: ConfigLeafRow[] = [];

  function walk(node: unknown, path: string) {
    if (isInternalTreeMetadataPath(path, basePath)) return;
    if (!isObjectLike(node)) {
      const relativePath = path === basePath ? "." : path.slice(basePath.length + 1);
      const segments = relativePath.split(".");
      const instanceIndex = segments.findIndex((segment) => /^\d+$/.test(segment));
      const instanceLabel = instanceIndex >= 0 ? `#${Number(segments[instanceIndex]) + 1}` : undefined;
      const schema = matchYangNode(schemaIndex, path, root);
      const namespace = namespaceForPath(root, path);
      rows.push({
        path,
        label: segments[segments.length - 1] ?? path,
        relativePath,
        value: node,
        valueType: displayYangType(schema, node),
        instanceLabel,
        namespace,
        schema
      });
      return;
    }
    for (const [label, child] of objectEntries(node)) {
      if (isInternalTreeMetadataKey(label)) continue;
      walk(child, `${path}.${label}`);
    }
  }

  walk(value, basePath);
  return rows;
}

function isInternalTreeMetadataPath(path: string, basePath: string): boolean {
  const relativePath = path === basePath ? "." : path.slice(basePath.length + 1);
  return relativePath.split(".").some(isInternalTreeMetadataKey);
}

function isInternalTreeMetadataKey(key: string): boolean {
  return key === "_namespace" || key === "_attributes" || key === "_text";
}

function collectListTable(
  value: unknown[],
  basePath: string,
  root: unknown,
  schemaIndex: YangSchemaIndex
): ConfigListTable {
  const columns: ConfigListTableColumn[] = [];
  const seenColumns = new Set<string>();
  const rows = value.map((item, index): ConfigListTableRow => {
    const itemPath = `${basePath}.${index}`;
    const cells: Record<string, ConfigListTableCell> = {};
    const leafRows = collectLeafRows(item, itemPath, root, schemaIndex);

    for (const leaf of leafRows) {
      const key = leaf.relativePath === "." ? "." : leaf.relativePath;
      const label = key === "." ? "当前值" : key;
      if (!seenColumns.has(key)) {
        seenColumns.add(key);
        columns.push({ key, label });
      }
      cells[key] = {
        path: leaf.path,
        label,
        value: leaf.value,
        valueType: leaf.valueType,
        schema: leaf.schema
      };
    }

    return {
      path: itemPath,
      label: String(index + 1),
      value: item,
      cells
    };
  });

  return { columns, rows };
}

function countLeaves(value: unknown): number {
  if (!isObjectLike(value)) return 1;
  return objectEntries(value).reduce((total, [, child]) => total + countLeaves(child), 0);
}

function defaultConfigChangeSummary(target: ConfigChangeTarget) {
  return `${configChangeActionLabel(target.action)} ${target.path}`;
}

function configChangeActionLabel(action: ConfigChangeAction) {
  switch (action) {
    case "edit-leaf":
      return "修改叶子节点";
    case "add-leaf":
      return "新增叶子节点";
    case "delete-leaf":
      return "删除叶子节点";
    case "edit-instance":
      return "修改实例";
    case "add-instance":
      return "新增实例";
    case "delete-instance":
      return "删除实例";
  }
}

function buildConfigChangePayload(action: ConfigChangeAction, path: string, value: unknown) {
  const operation =
    action === "delete-leaf" || action === "delete-instance"
      ? "delete"
      : action === "add-leaf" || action === "add-instance"
        ? "create"
        : "replace";
  const body = operation === "delete"
    ? ""
    : `\n  <value>${escapeXmlText(formatTreeValue(value))}</value>\n`;
  return `<config-change operation="${operation}" path="${escapeXmlAttribute(path)}">${body}</config-change>`;
}

function escapeXmlText(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeXmlAttribute(value: string) {
  return escapeXmlText(value).replaceAll("\"", "&quot;");
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

// ── Changes Tab ────────────────────────────────────────────────────────────

function ChangesTab() {
  const { hasPermission } = useSession();
  const t = useT();
  const [changes, setChanges] = useState<ChangeRequestRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canApprove = hasPermission(PERM.DEVICE_CHANGE_APPROVE);
  const canExecute = hasPermission(PERM.DEVICE_CHANGE_EXECUTE);
  const canSubmit = hasPermission(PERM.DEVICE_CHANGE_SUBMIT);

  const loadChanges = useCallback(async (options: RefreshOptions = {}) => {
    if (!options.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const resp = await api.listChangeRequests();
      setChanges(resp.items);
    } catch (e) {
      if (!options.silent) setError(errorMessage(e, t));
    } finally {
      if (!options.silent) setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadChanges();
  }, [loadChanges]);

  useRealtimeRefresh(
    () => loadChanges({ silent: true }),
    changes.some((change) => isRealtimeActiveStatus(change.status))
      ? REALTIME_FAST_REFRESH_MS
      : REALTIME_NORMAL_REFRESH_MS
  );

  async function handleApprove(id: number) {
    try {
      await api.approveChangeRequest(id);
      await loadChanges();
    } catch (e) {
      setError(errorMessage(e, t));
    }
  }

  async function handleReject(id: number) {
    const note = window.prompt(t("changes.rejectionReasonPrompt"));
    if (!note) return;
    try {
      await api.rejectChangeRequest(id, note);
      await loadChanges();
    } catch (e) {
      setError(errorMessage(e, t));
    }
  }

  async function handleManualRollback(cr: ChangeRequestRead) {
    if (!cr.baseline_snapshot_id) {
      setError(t("changes.noBaselineForRollback"));
      return;
    }
    const reason = window.prompt(t("changes.rollbackProposalReasonPrompt"));
    if (!reason?.trim()) return;
    try {
      await api.submitRollback({
        device_id: cr.device_id,
        datastore: cr.datastore,
        change_summary: t("changes.rollbackProposalSummary", { id: cr.id }),
        reason,
        rollback_target_snapshot_id: cr.baseline_snapshot_id,
        rollback_of_change_id: cr.id
      });
      await loadChanges();
    } catch (e) {
      setError(errorMessage(e, t));
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t("changes.title")}</h2>
        <Button onClick={() => void loadChanges()} busy={loading} className="h-9 w-9 px-0">
          <RefreshCw className="h-4 w-4" aria-hidden />
        </Button>
      </div>

      {error ? <ErrorPanel message={error} onRetry={() => void loadChanges()} /> : null}

      {canSubmit ? (
        <InfoPanel icon={<Router />} title={t("changes.contextSubmission")}>
          <p className="text-sm text-muted">
            {t("changes.contextSubmissionHint")}
          </p>
        </InfoPanel>
      ) : null}
      {canExecute && <DirectExecuteForm onSuccess={() => void loadChanges()} />}

      {changes.length === 0 && !loading ? (
        <EmptyState icon={<ClipboardList className="h-6 w-6" />} title={t("changes.empty")} />
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
                      {t("changes.directExecuteBadge")}
                    </span>
                  )}
                  {cr.is_rollback && (
                    <span className="rounded bg-info/20 px-2 py-0.5 font-mono text-[11px] text-info flex items-center gap-1">
                      <ListRestart className="h-3 w-3" /> {t("changes.rollbackBadge")}
                    </span>
                  )}
                  <span className="font-mono text-xs text-muted">#{cr.id}</span>
                </div>
                <p className="mt-1 text-sm font-semibold">{cr.change_summary}</p>
                <p className="mt-0.5 text-xs text-muted">
                  {t("changes.deviceLine", {
                    device: cr.device_id,
                    datastore: cr.datastore,
                    submitter: cr.submitter?.display_name ?? t("changes.byUnknown")
                  })}
                </p>
                <p className="mt-0.5 text-xs text-muted">{t("changes.reasonLabel", { reason: cr.reason })}</p>
                <div className="mt-2 grid gap-2 text-xs text-muted sm:grid-cols-3">
                  <Metric label={t("changes.approver")} value={cr.approver?.display_name ?? "-"} />
                  <Metric label={t("changes.execution")} value={cr.execution_task_id ?? "-"} />
                  <Metric label={t("changes.verification")} value={cr.verification_status ?? "-"} />
                </div>
                <PreflightSummary preflight={changePreflightFromRequest(cr)} compact />
                {cr.verification_summary ? (
                  <p className="mt-2 text-xs text-muted">
                    {String(cr.verification_summary.error_message ?? "") ||
                      t("changes.postChangeSnapshot", { id: cr.verification_snapshot_id ?? "-" })}
                  </p>
                ) : null}

                {/* Rollback context card (Task 9.4) */}
                {cr.is_rollback && (
                  <div className="mt-3 rounded border border-info/30 bg-info/10 p-3 text-xs space-y-1">
                    <p className="font-semibold text-info flex items-center gap-1">
                      <ListRestart className="h-3.5 w-3.5" /> {t("changes.rollbackContext")}
                    </p>
                    {cr.rollback_of_change_id ? (
                      <p className="text-muted">
                        {t("changes.originChange")}{" "}
                        <a className="font-mono underline" href={`#change-${cr.rollback_of_change_id}`}>
                          #{cr.rollback_of_change_id}
                        </a>
                        {cr.rollback_of_change ? ` · ${cr.rollback_of_change.status}` : ""}
                      </p>
                    ) : null}
                    {cr.rollback_target_snapshot_id ? (
                      <p className="text-muted">{t("changes.targetSnapshot")} <span className="font-mono">#{cr.rollback_target_snapshot_id}</span>
                        {cr.rollback_target_snapshot ? ` · ${digestShort(cr.rollback_target_snapshot.content_digest)}` : ""}
                      </p>
                    ) : null}
                  </div>
                )}

                {/* verification_failed with pending proposal link (Task 9.3) */}
                {cr.status === "verification_failed" && !cr.is_rollback && cr.pending_rollback_proposal_id ? (
                  <div className="mt-3 rounded border border-warning/30 bg-warning/10 p-3 text-xs">
                    <p className="text-warning font-semibold flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" /> {t("changes.verificationFailedRollbackProposed")}
                    </p>
                    <p className="mt-1 text-muted">
                      {t("changes.autoRollbackProposalIs", {
                        link: `#${cr.pending_rollback_proposal_id}`,
                        status: cr.pending_rollback_proposal?.status ?? "pending_approval"
                      })}
                    </p>
                  </div>
                ) : cr.status === "verification_failed" && !cr.is_rollback && !cr.pending_rollback_proposal_id ? (
                  <div className="mt-3 rounded border border-warning/30 bg-warning/10 p-3 text-xs">
                    <p className="text-warning font-semibold flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" /> {t("changes.verificationFailed")}
                    </p>
                    {canApprove && cr.baseline_snapshot_id ? (
                      <Button
                        onClick={() => void handleManualRollback(cr)}
                        className="mt-2 h-8 px-2 text-xs bg-paper text-ink"
                      >
                        <ListRestart className="h-3.5 w-3.5" /> {t("changes.proposeRollback")}
                      </Button>
                    ) : (
                      <p className="mt-1 text-muted">
                        {t("changes.noRollbackProposalAvailable")}
                      </p>
                    )}
                  </div>
                ) : null}

                {/* Rollback verification_failed context (Task 9.5) */}
                {cr.status === "verification_failed" && cr.is_rollback && (
                  <div className="mt-3 rounded border border-error/30 bg-error/10 p-3 text-xs">
                    <p className="text-error font-semibold flex items-center gap-1">
                      <XCircle className="h-3.5 w-3.5" /> {t("changes.rollbackVerificationFailed")}
                    </p>
                    <p className="mt-1 text-muted">{t("changes.rollbackVerificationFailedHint")}</p>
                  </div>
                )}
              </div>
              {cr.status === "pending_approval" && canApprove && (
                <div className="flex gap-2">
                  <Button
                    onClick={() => void handleApprove(cr.id)}
                    className="h-8 px-2 text-xs"
                  >
                    <CheckCircle className="h-3.5 w-3.5" /> {t("changes.approve")}
                  </Button>
                  <Button
                    onClick={() => void handleReject(cr.id)}
                    className="h-8 px-2 text-xs bg-paper text-error"
                  >
                    <XCircle className="h-3.5 w-3.5" /> {t("changes.reject")}
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
  const t = useT();
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
      throw new Error(result.blockers.join(", ") || t("changes.preflightFailed"));
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
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded border border-warm bg-canvas/95 p-4">
      <h3 className="mb-3 font-semibold text-sm">
        {compact ? t("changes.requestConfigChange") : t("changes.submitChangeRequest")}
      </h3>
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
        <div className={cn("grid gap-3", compact ? "" : "sm:grid-cols-2")}>
          {initialDeviceId ? (
            <Metric label={t("common.device")} value={`#${initialDeviceId}`} />
          ) : null}
          <div>
            <FieldLabel>{t("common.datastore")}</FieldLabel>
            <DatastoreSelect value={datastore} onValueChange={setDatastore} />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <FieldLabel>{t("change.summary")}</FieldLabel>
            <input
              type="text"
              required
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <FieldLabel>{t("changes.changeRef")}</FieldLabel>
            <input
              type="text"
              value={changeRef}
              onChange={(e) => setChangeRef(e.target.value)}
              className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
            />
          </div>
        </div>
        <div>
          <FieldLabel>{t("changes.configBody")}</FieldLabel>
          <textarea
            required
            value={configBody}
            onChange={(e) => setConfigBody(e.target.value)}
            rows={4}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 font-mono text-xs"
          />
        </div>
        <div>
          <FieldLabel>{t("change.reason")}</FieldLabel>
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
          {preflight?.passed ? t("change.submit") : t("change.preview")}
        </Button>
      </form>
    </div>
  );
}

function DirectExecuteForm({ onSuccess }: { onSuccess: () => void }) {
  const t = useT();
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
    if (!reason.trim()) { setError(t("changes.directReasonRequired")); return; }
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
        if (!result.passed) throw new Error(result.blockers.join(", ") || t("changes.preflightFailed"));
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
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)} className="text-sm">
        <Send className="h-4 w-4" /> {t("changes.directExecute")}
      </Button>
    );
  }

  return (
    <div className="rounded border border-warm bg-canvas/95 p-4">
      <h3 className="mb-3 font-semibold text-sm">{t("changes.directExecuteSubtitle")}</h3>
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <FieldLabel>{t("changes.deviceId")}</FieldLabel>
            <input
              type="number"
              required
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <FieldLabel>{t("common.datastore")}</FieldLabel>
            <DatastoreSelect value={datastore} onValueChange={setDatastore} />
          </div>
        </div>
        <div>
          <FieldLabel>{t("change.summary")}</FieldLabel>
          <input
            type="text"
            required
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <FieldLabel>{t("changes.configBody")}</FieldLabel>
          <textarea
            required
            value={configBody}
            onChange={(e) => setConfigBody(e.target.value)}
            rows={4}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 font-mono text-xs"
          />
        </div>
        <div>
          <FieldLabel>{t("change.reason")}</FieldLabel>
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
            {preflight?.passed ? t("changes.execute") : t("change.preview")}
          </Button>
          <Button type="button" onClick={() => setOpen(false)} className="bg-paper">{t("common.cancel")}</Button>
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
  const t = useT();
  const [reason, setReason] = useState("");
  const [summary, setSummary] = useState(
    `${t("rollback.restoreToSnapshot", { id: snapshot.id })} (${digestShort(snapshot.content_digest)})`
  );
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
        const msgs = result.blockers.map((b) => formatRollbackBlocker(b, t));
        throw new Error(msgs.join(t("rollback.preflightBlockerSeparator")));
      }
    } catch (e) {
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) { setError(t("changes.reasonRequired")); return; }
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
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-4 rounded border border-warm bg-paper p-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold flex items-center gap-1.5">
          <ListRestart className="h-4 w-4" />
          {t("rollback.restoreToSnapshot", { id: snapshot.id })}
        </h4>
        <button onClick={onClose} className="text-muted hover:text-ink text-xs">✕ {t("rollback.cancel")}</button>
      </div>
      <div className="mb-3 grid grid-cols-2 gap-2 text-xs text-muted">
        <Metric label={t("rollback.snapshot")} value={`#${snapshot.id}`} />
        <Metric label={t("common.datastore")} value={snapshot.datastore} />
        <Metric label={t("rollback.digest")} value={digestShort(snapshot.content_digest)} />
        <Metric label={t("rollback.collected")} value={formatDate(snapshot.collected_at)} />
      </div>
      {!snapshot.rollback_eligible ? (
        <div className="rounded border border-error/20 bg-error/10 p-3 text-xs text-error">
          {t("rollback.notRestorable", {
            reason: snapshot.rollback_blocker ?? t("rollback.normalizedContentUnavailable")
          })}
        </div>
      ) : (
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <div>
            <FieldLabel>{t("change.summary")}</FieldLabel>
            <input
              type="text"
              required
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="mt-1 w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <FieldLabel>{t("change.reason")}</FieldLabel>
            <textarea
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              placeholder={t("rollback.reasonPlaceholder")}
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
                <span className="font-medium">{preflight.passed ? t("rollback.preflightPassed") : t("rollback.preflightBlocked")}</span>
              </div>
              {preflight.blockers.length > 0 ? (
                <ul className="ml-6 space-y-0.5 text-error">
                  {preflight.blockers.map((b) => <li key={b}>{formatRollbackBlocker(b, t)}</li>)}
                </ul>
              ) : null}
              {preflight.payload ? (
                <Metric label={t("rollback.payloadDigest")} value={digestShort(preflight.payload.digest)} />
              ) : null}
              {preflight.risk_summary ? (
                <Metric label={t("rollback.risk")} value={String((preflight.risk_summary as ChangeRiskSummary).risk_level ?? "-")} />
              ) : null}
            </div>
          ) : null}
          {error ? <p className="text-xs text-error">{error}</p> : null}
          <Button type="submit" busy={loading}>
            {preflight?.passed ? <><CheckCircle className="h-4 w-4" /> {t("rollback.submitRollback")}</> : <><Sparkles className="h-4 w-4" /> {t("rollback.previewPreflight")}</>}
          </Button>
        </form>
      )}
    </div>
  );
}

// ── Admin Tab ──────────────────────────────────────────────────────────────

function AdminTab() {
  const t = useT();
  const [users, setUsers] = useState<UserRead[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAdminData = useCallback(async (options: RefreshOptions = {}) => {
    if (!options.silent) {
      setLoading(true);
      setError(null);
    }
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
      if (!options.silent) setError(errorMessage(e, t));
    } finally {
      if (!options.silent) setLoading(false);
    }
  }, [t]);

  useEffect(() => { void loadAdminData(); }, [loadAdminData]);
  useRealtimeRefresh(() => loadAdminData({ silent: true }), REALTIME_SLOW_REFRESH_MS);

  return (
    <div className="mx-auto grid max-w-6xl gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t("admin.accessControl")}</h2>
          <Button onClick={() => void loadAdminData()} busy={loading} className="h-9 w-9 px-0">
            <RefreshCw className="h-4 w-4" aria-hidden />
          </Button>
        </div>
        {error ? <ErrorPanel message={error} onRetry={() => void loadAdminData()} /> : null}
        <CreateUserForm onSuccess={() => void loadAdminData()} />
        <UserListTable
          users={users}
          roles={roles}
          onToggle={(u) => void toggleUser(u)}
          onChange={() => void loadAdminData()}
        />
      </div>
      <aside className="space-y-4">
        <RolePermissionEditor
          roles={roles}
          permissions={permissions}
          onChange={() => void loadAdminData()}
        />
        <div className="rounded border border-warm bg-canvas/95 p-4">
          <h3 className="mb-3 text-sm font-semibold">{t("admin.systemConfig")}</h3>
          <div className="space-y-2 text-xs text-muted">
            <p>{t("admin.systemConfigDesc")}</p>
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
      setError(errorMessage(e, t));
    }
  }
}

function CreateUserForm({ onSuccess }: { onSuccess: () => void }) {
  const t = useT();
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
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded border border-warm bg-canvas/95 p-4">
      <h3 className="mb-3 text-sm font-semibold">{t("admin.createUser")}</h3>
      <form onSubmit={(e) => void handleSubmit(e)} className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
        <div>
          <FieldLabel>{t("admin.username")}</FieldLabel>
          <input
            required
            minLength={2}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <FieldLabel>{t("admin.displayName")}</FieldLabel>
          <input
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mt-1 w-full rounded border border-warm bg-paper px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <FieldLabel>{t("admin.password")}</FieldLabel>
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
          {t("admin.create")}
        </Button>
      </form>
      {error ? <p className="mt-2 text-xs text-error">{error}</p> : null}
    </div>
  );
}

function UserListTable({
  users,
  roles,
  onToggle,
  onChange
}: {
  users: UserRead[];
  roles: Role[];
  onToggle: (user: UserRead) => void;
  onChange: () => void;
}) {
  const t = useT();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (users.length === 0) {
    return (
      <div className="rounded border border-warm bg-canvas/95 p-4 text-xs text-muted">
        {t("admin.noUsers")}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-warm">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-warm bg-paper/70 text-left font-mono text-[11px] uppercase text-muted">
            <th className="px-3 py-2 font-medium">{t("admin.user")}</th>
            <th className="px-3 py-2 font-medium">{t("admin.roles")}</th>
            <th className="px-3 py-2 font-medium">{t("table.status")}</th>
            <th className="px-3 py-2 text-right font-medium">{t("table.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => {
            const isExpanded = expandedId === u.id;
            return (
              <Fragment key={u.id}>
                <tr className="border-b border-warm/70 last:border-0 hover:bg-paper">
                  <td className="px-3 py-3">
                    <p className="font-semibold">{u.display_name}</p>
                    <p className="mt-1 font-mono text-[11px] text-muted">{u.username}</p>
                  </td>
                  <td className="px-3 py-3 text-xs text-muted">
                    {u.roles.length === 0 ? (
                      <span className="text-muted">{t("admin.noRoles")}</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {u.roles.map((role) => (
                          <span
                            key={role.id}
                            className="rounded border border-warm bg-paper px-2 py-0.5 font-mono text-[11px] text-muted"
                          >
                            {role.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <StatusBadge status={u.is_active ? "online" : "offline"} />
                  </td>
                  <td className="px-3 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        onClick={() => setExpandedId(isExpanded ? null : u.id)}
                        className="h-8 px-2 text-xs"
                        aria-expanded={isExpanded}
                        title={t("admin.manageRoles")}
                      >
                        {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                        <span className="ml-1 hidden sm:inline">{t("admin.manageRoles")}</span>
                      </Button>
                      <Button
                        onClick={() => onToggle(u)}
                        className="h-8 px-2 text-xs"
                      >
                        {u.is_active ? t("admin.disable") : t("admin.enable")}
                      </Button>
                    </div>
                  </td>
                </tr>
                {isExpanded ? (
                  <tr className="border-b border-warm/70 bg-paper/40 last:border-0">
                    <td colSpan={4} className="px-3 py-3">
                      <UserRoleControls
                        user={u}
                        roles={roles}
                        onChange={onChange}
                      />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
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
  const t = useT();
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
      setError(errorMessage(e, t));
    }
  }

  async function removeRole(role: Role) {
    setError(null);
    try {
      await api.removeRole(user.id, role.id);
      onChange();
    } catch (e) {
      setError(errorMessage(e, t));
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {user.roles.length === 0 ? (
          <span className="text-xs text-muted">{t("admin.noRoles")}</span>
        ) : (
          user.roles.map((role) => (
            <button
              key={role.id}
              onClick={() => void removeRole(role)}
              className="rounded border border-warm bg-paper px-2 py-1 font-mono text-[11px] text-muted hover:border-error hover:text-error"
            >
              {role.name} x
            </button>
          ))
        )}
      </div>
      <div className="mt-3 flex gap-2">
        <select
          value={roleId}
          onChange={(e) => setRoleId(e.target.value)}
          className="h-8 min-w-40 rounded border border-warm bg-paper px-2 text-sm"
        >
          <option value="">{t("admin.role")}</option>
          {availableRoles.map((role) => (
            <option key={role.id} value={role.id}>{role.name}</option>
          ))}
        </select>
        <Button
          onClick={() => void assignSelectedRole()}
          disabled={!roleId}
          className="h-8 px-2 text-xs"
        >
          {t("admin.assign")}
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
  const t = useT();
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
      setError(errorMessage(e, t));
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
        <h3 className="text-sm font-semibold">{t("admin.rolesPermissions")}</h3>
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
        {t("admin.save")}
      </Button>
    </div>
  );
}

// ── Audit Tab ──────────────────────────────────────────────────────────────

function AuditTab() {
  const { hasPermission } = useSession();
  const t = useT();
  const [logs, setLogs] = useState<AuditLogRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFullAudit = hasPermission(PERM.AUDIT_READ_FULL);

  const loadLogs = useCallback(async (options: RefreshOptions = {}) => {
    if (!options.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const resp = await api.listAuditLogs({ limit: 50 });
      setLogs(resp.items);
    } catch (e) {
      if (!options.silent) setError(errorMessage(e, t));
    } finally {
      if (!options.silent) setLoading(false);
    }
  }, [t]);

  useEffect(() => { void loadLogs(); }, [loadLogs]);
  useRealtimeRefresh(() => loadLogs({ silent: true }), REALTIME_NORMAL_REFRESH_MS);

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t("audit.title")}</h2>
        <Button onClick={() => void loadLogs()} busy={loading} className="h-9 w-9 px-0">
          <RefreshCw className="h-4 w-4" aria-hidden />
        </Button>
      </div>
      {error ? <ErrorPanel message={error} onRetry={() => void loadLogs()} /> : null}
      {logs.length === 0 && !loading ? (
        <EmptyState icon={<FileClock className="h-6 w-6" />} title={t("audit.empty")} />
      ) : null}
      <div className="overflow-x-auto rounded border border-warm">
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-warm text-left font-mono text-[11px] uppercase text-muted">
              <th className="px-3 py-2 font-medium">{t("audit.time")}</th>
              <th className="px-3 py-2 font-medium">{t("audit.action")}</th>
              <th className="px-3 py-2 font-medium">{t("audit.actor")}</th>
              <th className="px-3 py-2 font-medium">{t("audit.target")}</th>
              <th className="px-3 py-2 font-medium">{t("audit.permission")}</th>
              <th className="px-3 py-2 font-medium">{t("audit.outcome")}</th>
              {hasFullAudit ? <th className="px-3 py-2 font-medium">{t("audit.context")}</th> : null}
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

function useRealtimeRefresh(
  refresh: () => void | Promise<void>,
  intervalMs: number | null,
  enabled = true
) {
  const refreshRef = useRef(refresh);

  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    if (!enabled || intervalMs === null) return;

    let cancelled = false;
    let inFlight = false;
    let timer: number | null = null;

    const run = async () => {
      if (inFlight || document.visibilityState !== "visible") return;
      inFlight = true;
      try {
        await refreshRef.current();
      } finally {
        inFlight = false;
      }
    };

    const schedule = () => {
      timer = window.setTimeout(() => {
        void run().finally(() => {
          if (!cancelled) schedule();
        });
      }, intervalMs);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") void run();
    };

    schedule();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [enabled, intervalMs]);
}

function isRealtimeActiveStatus(status: string | null | undefined) {
  return status === "queued" || status === "running" || status === "verifying";
}

function CreateDeviceForm({ onSuccess }: { onSuccess: (deviceId: number) => Promise<void> }) {
  const t = useT();
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
      setError(errorMessage(caught, t));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="mb-3 rounded border border-warm bg-paper p-3">
      <div className="grid gap-2">
        <FieldLabel>{t("createDevice.title")}</FieldLabel>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("createDevice.namePlaceholder")}
          className="w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
        />
        <div className="grid grid-cols-[1fr_76px] gap-2">
          <input
            required
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder={t("createDevice.hostPlaceholder")}
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
          placeholder={t("createDevice.usernamePlaceholder")}
          className="w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={t("createDevice.passwordPlaceholder")}
          className="w-full rounded border border-warm bg-canvas px-2 py-1.5 text-sm"
        />
        {error ? <p className="text-xs text-error">{error}</p> : null}
        <Button type="submit" busy={loading} className="w-full">
          <Plus className="h-4 w-4" /> {t("createDevice.add")}
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
  const t = useT();
  if (!preflight) return null;
  return (
    <div className="rounded border border-warm bg-paper p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <FieldLabel>{t("preflight.label")}</FieldLabel>
        <StatusBadge status={preflight.passed ? "passed" : "failed"} />
      </div>
      <div className={cn("mt-2 grid gap-2 text-xs", compact ? "" : "sm:grid-cols-2")}>
        <Metric
          label={preflight.mode === "rollback" ? t("preflight.current") : t("preflight.baseline")}
          value={preflight.baseline_snapshot?.id ?? "-"}
        />
        {preflight.mode === "rollback" ? (
          <Metric label={t("preflight.target")} value={preflight.rollback_target_snapshot?.id ?? "-"} />
        ) : null}
        <Metric label={t("preflight.payload")} value={preflight.payload ? t("preflight.payloadBytes", { count: preflight.payload.length }) : "-"} />
        <Metric label={t("preflight.risk")} value={preflight.risk_summary?.risk_level ?? "-"} />
        <Metric label={t("preflight.digest")} value={digestShort(preflight.payload?.digest)} />
      </div>
      {preflight.blockers.length > 0 ? (
        <p className="mt-2 text-xs text-error">
          {preflight.blockers.map((b) => formatRollbackBlocker(b, t)).join(", ")}
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
  device, active, canManage, showDelete = true, onSelect, onDelete
}: { device: Device; active: boolean; canManage: boolean; showDelete?: boolean; onSelect: () => void; onDelete: () => Promise<void> }) {
  const t = useT();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setDeleting(true);
    try {
      await onDelete();
    } finally {
      setDeleting(false);
      setConfirming(false);
    }
  }

  return (
    <div
      className={cn(
        "w-full rounded border p-3 text-left transition",
        active
          ? "border-warm-strong bg-paper"
          : "border-transparent bg-transparent hover:border-warm hover:bg-paper/70"
      )}
    >
      <button className="w-full text-left" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{device.name}</p>
            <p className="mt-1 truncate font-mono text-[11px] text-muted">
              {device.group ?? t("device.ungrouped")}
            </p>
          </div>
          <StatusBadge status={device.status} />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
          <Metric label={t("table.discovery")} value={summaryValue(t, device.last_discovery?.summary)} />
          <Metric label={t("rollback.snapshot")} value={digestShort(device.last_config_snapshot?.content_digest)} />
        </div>
      </button>
      {canManage && showDelete ? (
        <div className="mt-2 flex items-center justify-end gap-1 border-t border-warm/50 pt-2">
          {confirming ? (
            <>
              <span className="mr-1 text-[11px] font-medium text-red-500">{t("common.confirmDelete")}</span>
              <Button
                busy={deleting}
                onClick={(e) => void handleDelete(e)}
                className="h-6 px-1.5 text-[11px] border-red-400 text-red-500 hover:bg-red-50"
              >
                <CheckCircle className="h-3.5 w-3.5" />
              </Button>
              <Button
                onClick={(e) => { e.stopPropagation(); setConfirming(false); }}
                className="h-6 px-1.5 text-[11px]"
              >
                <XCircle className="h-3.5 w-3.5" />
              </Button>
            </>
          ) : (
            <Button
              aria-label={t("devices.delete")}
              title={t("devices.delete")}
              onClick={(e) => { e.stopPropagation(); setConfirming(true); }}
              className="h-6 w-6 px-0 text-muted hover:border-red-400 hover:text-red-500"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      ) : null}
    </div>
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
  const t = useT();
  const [rollbackTarget, setRollbackTarget] = useState<ConfigSnapshot | null>(null);

  return (
    <InfoPanel icon={<FileClock />} title={t("snapshot.title")} collapsible contentClassName="max-h-[42dvh] overflow-auto pr-1">
      {snapshots.length === 0 ? (
        <EmptyState icon={<Database className="h-6 w-6" />} title={t("snapshot.empty")} />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-warm text-left font-mono text-[11px] uppercase text-muted">
                  <th className="py-2 pr-3 font-medium">{t("common.datastore")}</th>
                  <th className="py-2 pr-3 font-medium">{t("snapshot.collected")}</th>
                  <th className="py-2 pr-3 font-medium">{t("rollback.digest")}</th>
                  <th className="py-2 font-medium">{t("snapshot.diff")}</th>
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
                        <span>{diffLabel(t, s.diff_summary)}</span>
                        <div className="flex gap-1.5">
                          {canSubmitChange && onStartChange ? (
                            <Button
                              onClick={() => onStartChange(s)}
                              className="h-8 px-2 text-xs"
                            >
                              <Send className="h-3.5 w-3.5" /> {t("snapshot.change")}
                            </Button>
                          ) : null}
                          {canApprove ? (
                            s.rollback_eligible ? (
                              <Button
                                onClick={() => setRollbackTarget(s)}
                                className="h-8 px-2 text-xs bg-paper border border-warm text-ink"
                                title={t("snapshot.restoreToThis")}
                              >
                                <ListRestart className="h-3.5 w-3.5" /> {t("snapshot.restore")}
                              </Button>
                            ) : (
                              <button
                                disabled
                                title={t("snapshot.notRestorable", { reason: s.rollback_blocker ?? t("common.unknown") })}
                                className="h-8 px-2 text-xs opacity-40 cursor-not-allowed flex items-center gap-1 rounded border border-warm"
                              >
                                <ListRestart className="h-3.5 w-3.5" /> {t("snapshot.restore")}
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
  const t = useT();
  return (
    <InfoPanel icon={<ShieldCheck />} title={t("boundary.title")} collapsible contentClassName="max-h-[30dvh] overflow-auto pr-1">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Metric label={t("boundary.fullConfig")} value={String(profile?.safety_summary.exposes_full_config ?? false)} />
          <Metric label={t("boundary.credentials")} value={String(profile?.safety_summary.exposes_credentials ?? false)} />
        </div>
        {configTaskRunning ? (
          <div className="rounded border border-info/20 bg-info/10 p-3 text-sm text-info">
            {t("boundary.collectionInProgress")}
          </div>
        ) : null}
        {lastTask ? (
          <div className="rounded border border-warm bg-paper p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <FieldLabel>{t("boundary.lastSubmitted")}</FieldLabel>
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
  const t = useT();
  return (
    <InfoPanel icon={<ListRestart />} title={t("recentTasks.title")} collapsible contentClassName="max-h-[42dvh] overflow-auto pr-1">
      {tasks.length === 0 ? (
        <EmptyState icon={<ListRestart className="h-6 w-6" />} title={t("recentTasks.empty")} />
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

function InfoPanel({ icon, title, children, collapsible = false, defaultOpen = true, className, contentClassName }: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  className?: string;
  contentClassName?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={cn("rounded border border-warm bg-surface/70 p-4", className)}>
      <div className={cn("flex items-center gap-2", open && "mb-4")}>
        <span className="text-accent [&_svg]:h-4 [&_svg]:w-4">{icon}</span>
        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</h3>
        {collapsible ? (
          <button
            type="button"
            aria-label={title}
            title={title}
            onClick={() => setOpen((value) => !value)}
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted transition hover:bg-paper hover:text-ink"
          >
            {open ? (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" aria-hidden />
            )}
          </button>
        ) : null}
      </div>
      {open ? <div className={contentClassName}>{children}</div> : null}
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
  const t = useT();
  return (
    <div className="rounded border border-error/25 bg-error/10 p-4 text-error">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p className="break-words text-sm">{message ?? t("common.requestFailed")}</p>
        </div>
        <Button onClick={onRetry} className="h-8 bg-paper text-error">{t("common.retry")}</Button>
      </div>
    </div>
  );
}

function summaryValue(t: TranslateFn, summary: Record<string, unknown> | undefined) {
  if (!summary) return "-";
  if (typeof summary.capability_count === "number") {
    return t("device.capCount", { count: summary.capability_count });
  }
  return t("device.discoverySummaryReady");
}

function onboardingSteps(t: TranslateFn, summary: Device["onboarding_summary"]) {
  if (!summary) return "-";
  return [
    `${t("onboarding.connectionLetter")} ${compactStatus(t, summary.connection.status)}`,
    `${t("onboarding.discoveryLetter")} ${compactStatus(t, summary.discovery.status)}`,
    `${t("onboarding.baselineLetter")} ${compactStatus(t, summary.baseline.status)}`
  ].join(" · ");
}

function onboardingDetail(t: TranslateFn, summary: Device["onboarding_summary"]) {
  if (!summary) return t("onboarding.profileUnavailable");
  if (summary.blockers.length > 0) return summary.blockers.join(", ");
  if (summary.next_action) return summary.next_action.replaceAll("_", " ");
  return summary.ready_for_change
    ? t("onboarding.readyForChange")
    : t("onboarding.waitingForOnboarding");
}

function compactStatus(t: TranslateFn, status: string) {
  const key = `status.${status}`;
  const translated = t(key);
  return translated === key ? status.replaceAll("_", " ") : translated;
}

function digestShort(digest: string | undefined) {
  if (!digest) return "-";
  return digest.replace("sha256:", "").slice(0, 12);
}

function diffLabel(t: TranslateFn, diff: Record<string, unknown>) {
  if (diff.previous_snapshot_id === null) return t("snapshot.firstSnapshot");
  return diff.changed ? t("snapshot.changed") : t("snapshot.unchanged");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit"
  }).format(new Date(value));
}

function errorMessage(caught: unknown, t?: TranslateFn) {
  return formatApiError(caught, t);
}
