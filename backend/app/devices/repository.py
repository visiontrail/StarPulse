from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.devices.constants import DeviceTaskStatus
from app.storage.models import (
    Device,
    DeviceConfigSnapshot,
    DeviceConnectionConfig,
    DeviceDiscoveryResult,
    TaskStatus,
)
from app.storage.repositories import Repository


class DeviceRepository(Repository[Device]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Device)

    def list(self) -> list[Device]:
        return list(
            self.session.scalars(
                select(Device).options(
                    selectinload(Device.connection),
                    selectinload(Device.last_discovery),
                    selectinload(Device.config_snapshots),
                )
                .execution_options(populate_existing=True)
            ).all()
        )

    def get_with_connection(self, device_id: int) -> Device | None:
        return self.session.scalar(
            select(Device)
            .where(Device.id == device_id)
            .options(
                selectinload(Device.connection),
                selectinload(Device.last_discovery),
                selectinload(Device.config_snapshots),
            )
            .execution_options(populate_existing=True)
        )

    def get_connection_for_device(self, device_id: int) -> DeviceConnectionConfig | None:
        return self.session.scalar(
            select(DeviceConnectionConfig).where(DeviceConnectionConfig.device_id == device_id)
        )

    def update_device_status(self, device_id: int, status: str) -> Device | None:
        device = self.session.get(Device, device_id)
        if device is None:
            return None
        device.status = status
        self.session.flush()
        return device

    def upsert_discovery_result(
        self,
        *,
        device_id: int,
        source_task_id: str,
        capabilities: list[str],
        system_info: dict[str, object],
        discovered_at: datetime,
        summary: dict[str, object],
    ) -> DeviceDiscoveryResult:
        result = self.session.scalar(
            select(DeviceDiscoveryResult).where(DeviceDiscoveryResult.device_id == device_id)
        )
        if result is None:
            result = DeviceDiscoveryResult(
                device_id=device_id,
                source_task_id=source_task_id,
                capabilities=capabilities,
                system_info=system_info,
                discovered_at=discovered_at,
                summary=summary,
            )
            self.session.add(result)
        else:
            result.source_task_id = source_task_id
            result.capabilities = capabilities
            result.system_info = system_info
            result.discovered_at = discovered_at
            result.summary = summary
        self.session.flush()
        return result

    def create_config_snapshot(
        self,
        *,
        device_id: int,
        source_task_id: str,
        datastore: str,
        content_digest: str,
        collected_at: datetime,
        diff_summary: dict[str, object],
        summary: dict[str, object],
    ) -> DeviceConfigSnapshot:
        snapshot = DeviceConfigSnapshot(
            device_id=device_id,
            source_task_id=source_task_id,
            datastore=datastore,
            content_digest=content_digest,
            collected_at=collected_at,
            diff_summary=diff_summary,
            summary=summary,
        )
        self.session.add(snapshot)
        self.session.flush()
        self.session.refresh(snapshot)
        return snapshot

    def get_previous_config_snapshot(
        self,
        *,
        device_id: int,
        datastore: str,
        before_snapshot_id: int | None = None,
    ) -> DeviceConfigSnapshot | None:
        query = (
            select(DeviceConfigSnapshot)
            .where(
                DeviceConfigSnapshot.device_id == device_id,
                DeviceConfigSnapshot.datastore == datastore,
            )
            .order_by(desc(DeviceConfigSnapshot.collected_at), desc(DeviceConfigSnapshot.id))
        )
        if before_snapshot_id is not None:
            current = self.session.get(DeviceConfigSnapshot, before_snapshot_id)
            if current is None:
                return None
            query = query.where(
                (DeviceConfigSnapshot.collected_at < current.collected_at)
                | (
                    (DeviceConfigSnapshot.collected_at == current.collected_at)
                    & (DeviceConfigSnapshot.id < current.id)
                )
            )
        return self.session.scalar(query.limit(1))

    def get_last_config_snapshot(
        self, *, device_id: int, datastore: str | None = None
    ) -> DeviceConfigSnapshot | None:
        query = select(DeviceConfigSnapshot).where(DeviceConfigSnapshot.device_id == device_id)
        if datastore is not None:
            query = query.where(DeviceConfigSnapshot.datastore == datastore)
        return self.session.scalar(
            query.order_by(
                desc(DeviceConfigSnapshot.collected_at), desc(DeviceConfigSnapshot.id)
            ).limit(1)
        )

    def get_latest_successful_snapshot(
        self, *, device_id: int, datastore: str
    ) -> DeviceConfigSnapshot | None:
        return self.get_last_config_snapshot(device_id=device_id, datastore=datastore)

    def list_config_snapshots(
        self, *, device_id: int, limit: int = 20, offset: int = 0
    ) -> list[DeviceConfigSnapshot]:
        safe_limit = min(max(limit, 1), 100)
        safe_offset = max(offset, 0)
        return list(
            self.session.scalars(
                select(DeviceConfigSnapshot)
                .where(DeviceConfigSnapshot.device_id == device_id)
                .order_by(desc(DeviceConfigSnapshot.collected_at), desc(DeviceConfigSnapshot.id))
                .limit(safe_limit)
                .offset(safe_offset)
            ).all()
        )

    def list_recent_tasks(self, *, device_id: int, limit: int = 10) -> list[TaskStatus]:
        safe_limit = min(max(limit, 1), 50)
        return list(
            self.session.scalars(
                select(TaskStatus)
                .where(TaskStatus.device_id == device_id)
                .order_by(desc(TaskStatus.created_at), desc(TaskStatus.id))
                .limit(safe_limit)
            ).all()
        )

    def find_active_device_task(
        self,
        *,
        device_id: int,
        task_type: str,
        datastore: str | None = None,
    ) -> TaskStatus | None:
        active_statuses = (str(DeviceTaskStatus.QUEUED), str(DeviceTaskStatus.RUNNING))
        tasks = list(
            self.session.scalars(
                select(TaskStatus)
                .where(
                    TaskStatus.device_id == device_id,
                    TaskStatus.task_type == task_type,
                    TaskStatus.status.in_(active_statuses),
                )
                .order_by(desc(TaskStatus.created_at), desc(TaskStatus.id))
            )
        )
        if datastore is None:
            return tasks[0] if tasks else None
        for task in tasks:
            if task.metadata_json.get("datastore") == datastore:
                return task
        return None

    def update_task_status(
        self,
        task: TaskStatus,
        *,
        status: str,
        result_summary: dict[str, object] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        context: dict[str, object] | None = None,
        completed_at: datetime | None = None,
    ) -> TaskStatus:
        task.status = status
        task.result_summary = result_summary
        task.error_code = error_code
        task.error_message = error_message
        task.context_json = context or {}
        task.completed_at = completed_at
        self.session.flush()
        return task
