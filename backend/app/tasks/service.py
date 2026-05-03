from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.redaction import redact_sensitive
from app.devices.constants import DeviceTaskStatus, DeviceTaskType
from app.devices.repository import DeviceRepository
from app.storage.models import TaskStatus
from app.tasks.jobs import (
    run_capability_discovery,
    run_config_change,
    run_config_snapshot,
    run_connection_test,
    sample_health,
)

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def submit_sample_task(self, task_type: str, payload: dict[str, object]) -> TaskStatus:
        task_id = str(uuid4())
        task_status = TaskStatus(
            task_id=task_id,
            task_type=task_type,
            status=DeviceTaskStatus.QUEUED,
            metadata_json={"payload": redact_sensitive(payload)},
        )
        self.session.add(task_status)
        self.session.commit()
        self.session.refresh(task_status)
        sample_health.delay(task_id, payload)
        return task_status

    def submit_connection_test(
        self, device_id: int, actor_user_id: int | None = None
    ) -> TaskStatus:
        active = self._active_device_task(DeviceTaskType.CONNECTION_TEST, device_id)
        if active is not None:
            return active
        task_status = self._create_device_task(
            DeviceTaskType.CONNECTION_TEST,
            device_id,
            actor_user_id=actor_user_id,
        )
        run_connection_test.delay(task_status.task_id)
        self._log_dispatch(task_status)
        return task_status

    def submit_capability_discovery(
        self, device_id: int, actor_user_id: int | None = None
    ) -> TaskStatus:
        active = self._active_device_task(DeviceTaskType.CAPABILITY_DISCOVERY, device_id)
        if active is not None:
            return active
        task_status = self._create_device_task(
            DeviceTaskType.CAPABILITY_DISCOVERY,
            device_id,
            actor_user_id=actor_user_id,
        )
        run_capability_discovery.delay(task_status.task_id)
        self._log_dispatch(task_status)
        return task_status

    def submit_config_snapshot(
        self,
        device_id: int,
        datastore: str,
        actor_user_id: int | None = None,
    ) -> TaskStatus:
        active = self._active_device_task(
            DeviceTaskType.CONFIG_SNAPSHOT,
            device_id,
            datastore=datastore,
        )
        if active is not None:
            return active
        task_status = self._create_device_task(
            DeviceTaskType.CONFIG_SNAPSHOT,
            device_id,
            metadata={"datastore": datastore},
            actor_user_id=actor_user_id,
        )
        run_config_snapshot.delay(task_status.task_id)
        self._log_dispatch(task_status)
        return task_status

    def submit_config_change(
        self,
        device_id: int,
        change_request_id: int,
        actor_user_id: int,
        datastore: str,
    ) -> TaskStatus:
        task_status = self._create_device_task(
            DeviceTaskType.CONFIG_CHANGE,
            device_id,
            metadata={"datastore": datastore, "change_request_id": change_request_id},
            actor_user_id=actor_user_id,
            change_request_id=change_request_id,
        )
        run_config_change.delay(task_status.task_id)
        self._log_dispatch(task_status)
        return task_status

    def get_task(self, task_id: str) -> TaskStatus | None:
        return self.session.scalar(select(TaskStatus).where(TaskStatus.task_id == task_id))

    def _create_device_task(
        self,
        task_type: DeviceTaskType,
        device_id: int,
        metadata: dict[str, object] | None = None,
        actor_user_id: int | None = None,
        change_request_id: int | None = None,
    ) -> TaskStatus:
        task_id = str(uuid4())
        safe_metadata = {"device_id": device_id} | dict(redact_sensitive(metadata or {}))
        task_status = TaskStatus(
            task_id=task_id,
            task_type=task_type,
            status=DeviceTaskStatus.QUEUED,
            device_id=device_id,
            actor_user_id=actor_user_id,
            change_request_id=change_request_id,
            metadata_json=safe_metadata,
            context_json=safe_metadata,
        )
        self.session.add(task_status)
        self.session.commit()
        self.session.refresh(task_status)
        return task_status

    def _active_device_task(
        self,
        task_type: DeviceTaskType,
        device_id: int,
        datastore: str | None = None,
    ) -> TaskStatus | None:
        return DeviceRepository(self.session).find_active_device_task(
            device_id=device_id,
            task_type=task_type,
            datastore=datastore,
        )

    def _log_dispatch(self, task_status: TaskStatus) -> None:
        logger.info(
            "device task queued",
            extra={
                "action": "device_task_queued",
                "task_id": task_status.task_id,
                "device_id": task_status.device_id,
                "datastore": task_status.metadata_json.get("datastore"),
                "status": task_status.status,
                "error_code": None,
                "duration_ms": 0,
            },
        )
