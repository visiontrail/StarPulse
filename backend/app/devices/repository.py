from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.storage.models import Device, DeviceConnectionConfig, DeviceDiscoveryResult, TaskStatus
from app.storage.repositories import Repository


class DeviceRepository(Repository[Device]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Device)

    def list(self) -> list[Device]:
        return list(
            self.session.scalars(
                select(Device).options(
                    selectinload(Device.connection), selectinload(Device.last_discovery)
                )
            ).all()
        )

    def get_with_connection(self, device_id: int) -> Device | None:
        return self.session.scalar(
            select(Device)
            .where(Device.id == device_id)
            .options(selectinload(Device.connection), selectinload(Device.last_discovery))
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
