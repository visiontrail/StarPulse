from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import monotonic

from app.common.redaction import redact_sensitive
from app.core.config import get_settings
from app.devices.config_snapshots import ConfigSnapshotService
from app.devices.constants import DeviceAccessErrorCode, DeviceStatus, DeviceTaskStatus
from app.devices.credentials import CredentialService, CredentialUnavailableError
from app.devices.repository import DeviceRepository
from app.netconf.client import NetconfConnectionParams
from app.netconf.services import NetconfService
from app.storage.database import SessionLocal
from app.storage.models import TaskStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="star_pulse.sample_health")
def sample_health(task_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return {"task_id": task_id, "status": "ok", "payload": payload or {}}


@celery_app.task(name="star_pulse.device_connection_test")
def run_connection_test(task_id: str) -> dict[str, object]:
    return _run_device_task(task_id, action="connection_test")


@celery_app.task(name="star_pulse.device_capability_discovery")
def run_capability_discovery(task_id: str) -> dict[str, object]:
    return _run_device_task(task_id, action="capability_discovery")


@celery_app.task(name="star_pulse.device_config_snapshot")
def run_config_snapshot(task_id: str) -> dict[str, object]:
    return _run_device_task(task_id, action="config_snapshot")


@celery_app.task(name="star_pulse.device_config_change")
def run_config_change(task_id: str) -> dict[str, object]:
    return _run_device_task(task_id, action="config_change")


def create_netconf_service() -> NetconfService:
    return NetconfService()


def _run_device_task(task_id: str, *, action: str) -> dict[str, object]:
    started_at = monotonic()
    with SessionLocal() as session:
        task = session.query(TaskStatus).filter(TaskStatus.task_id == task_id).one_or_none()
        if task is None:
            return {"task_id": task_id, "status": "missing"}

        repository = DeviceRepository(session)
        _mark_running(repository, task, started_at)
        session.commit()

        try:
            params = _connection_params(task, session)
            service = create_netconf_service()
            if action == "connection_test":
                result = service.test_connection(params)
            elif action == "config_snapshot":
                result = service.read_config(params, _task_datastore(task))
            elif action == "config_change":
                result = service.write_config(params, _task_datastore(task), _task_config_body(task))
            else:
                result = service.discover_capabilities(params)

            if not result.ok:
                _mark_failed(
                    repository,
                    task,
                    error_code=result.error_code or DeviceAccessErrorCode.INTERNAL_ERROR,
                    error_message=result.error_message or "NETCONF task failed",
                    context=result.context,
                    started_at=started_at,
                )
                repository.update_device_status(task.device_id or 0, DeviceStatus.OFFLINE)
                if action == "config_change":
                    _record_change_exec_failure(session, task, result.error_message or "NETCONF write failed")
                session.commit()
                return _task_response(task)

            if action == "capability_discovery":
                repository.upsert_discovery_result(
                    device_id=task.device_id or 0,
                    source_task_id=task.task_id,
                    capabilities=result.capabilities,
                    system_info=result.system_info,
                    discovered_at=datetime.now(UTC),
                    summary=result.summary,
                )
            if action == "config_snapshot":
                snapshot_result = ConfigSnapshotService(session).save_read_result(
                    device_id=task.device_id or 0,
                    source_task_id=task.task_id,
                    datastore=_task_datastore(task),
                    result=result,
                    collected_at=datetime.now(UTC),
                )
                result_summary = {
                    "ok": True,
                    "snapshot_id": snapshot_result.snapshot.id,
                    "snapshot": snapshot_result.snapshot.summary,
                }
            elif action == "config_change":
                result_summary = result.summary
                _record_change_exec_success(session, task)
            else:
                result_summary = result.summary

            repository.update_device_status(task.device_id or 0, DeviceStatus.ONLINE)
            repository.update_task_status(
                task,
                status=DeviceTaskStatus.SUCCEEDED,
                result_summary=result_summary,
                context=_safe_task_context(task, started_at),
                completed_at=datetime.now(UTC),
            )
            _log_task(task, "succeeded", started_at)
            session.commit()
            return _task_response(task)
        except CredentialUnavailableError:
            session.rollback()
            task = session.query(TaskStatus).filter(TaskStatus.task_id == task_id).one()
            repository = DeviceRepository(session)
            _mark_failed(
                repository,
                task,
                error_code=DeviceAccessErrorCode.CREDENTIAL_UNAVAILABLE,
                error_message="Device credential is unavailable",
                context={"device_id": task.device_id},
                started_at=started_at,
            )
            session.commit()
            return _task_response(task)
        except Exception as exc:
            session.rollback()
            task = session.query(TaskStatus).filter(TaskStatus.task_id == task_id).one()
            repository = DeviceRepository(session)
            _mark_failed(
                repository,
                task,
                error_code=DeviceAccessErrorCode.INTERNAL_ERROR,
                error_message="Device task failed",
                context={"device_id": task.device_id, "exception_type": exc.__class__.__name__},
                started_at=started_at,
            )
            session.commit()
            return _task_response(task)


def _connection_params(task: TaskStatus, session) -> NetconfConnectionParams:
    if task.device_id is None:
        raise CredentialUnavailableError("Task is missing device context")
    repository = DeviceRepository(session)
    connection = repository.get_connection_for_device(task.device_id)
    if connection is None:
        raise CredentialUnavailableError("Connection config is unavailable")
    credential = CredentialService(session).resolve(connection.credential_ref)
    settings = get_settings()
    return NetconfConnectionParams(
        host=connection.host,
        port=connection.port,
        username=connection.username,
        password=credential.password,
        private_key=credential.private_key,
        passphrase=credential.passphrase,
        timeout=settings.netconf_default_timeout,
        hostkey_verify=settings.netconf_hostkey_verify,
    )


def _mark_running(repository: DeviceRepository, task: TaskStatus, started_at: float) -> None:
    repository.update_task_status(
        task,
        status=DeviceTaskStatus.RUNNING,
        context=_safe_task_context(task, started_at),
    )
    if task.device_id is not None:
        repository.update_device_status(task.device_id, DeviceStatus.TESTING)
    _log_task(task, "running", started_at)


def _mark_failed(
    repository: DeviceRepository,
    task: TaskStatus,
    *,
    error_code: DeviceAccessErrorCode,
    error_message: str,
    context: dict[str, object],
    started_at: float,
) -> None:
    safe_context = _safe_task_context(task, started_at) | dict(redact_sensitive(context))
    repository.update_task_status(
        task,
        status=DeviceTaskStatus.FAILED,
        result_summary={"ok": False},
        error_code=error_code,
        error_message=error_message,
        context=safe_context,
        completed_at=datetime.now(UTC),
    )
    _log_task(task, "failed", started_at, error_code=error_code)


def _safe_task_context(task: TaskStatus, started_at: float) -> dict[str, object]:
    context = {
        "device_id": task.device_id,
        "duration_ms": _duration_ms(started_at),
    }
    if task.metadata_json.get("datastore") is not None:
        context["datastore"] = task.metadata_json["datastore"]
    return context


def _task_datastore(task: TaskStatus) -> str:
    value = task.metadata_json.get("datastore")
    return str(value or "running")


def _task_config_body(task: TaskStatus) -> str:
    return str(task.metadata_json.get("config_body", ""))


def _record_change_exec_success(session, task: TaskStatus) -> None:
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome

    write_audit_event(
        session=session,
        action=AuditAction.CHANGE_EXEC_SUCCESS,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=task.actor_user_id,
        target_type="change_request",
        target_id=str(task.change_request_id) if task.change_request_id else None,
        metadata={"task_id": task.task_id, "device_id": task.device_id},
    )


def _record_change_exec_failure(session, task: TaskStatus, error_message: str) -> None:
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome

    write_audit_event(
        session=session,
        action=AuditAction.CHANGE_EXEC_FAILURE,
        outcome=AuditOutcome.FAILURE,
        actor_user_id=task.actor_user_id,
        target_type="change_request",
        target_id=str(task.change_request_id) if task.change_request_id else None,
        metadata={"task_id": task.task_id, "device_id": task.device_id, "error": error_message},
    )


def _log_task(
    task: TaskStatus,
    status: str,
    started_at: float,
    *,
    error_code: DeviceAccessErrorCode | None = None,
) -> None:
    logger.info(
        "device task %s",
        status,
        extra={
            "action": f"device_task_{status}",
            "task_id": task.task_id,
            "device_id": task.device_id,
            "datastore": task.metadata_json.get("datastore"),
            "status": status,
            "error_code": error_code.value if error_code else None,
            "duration_ms": _duration_ms(started_at),
        },
    )


def _duration_ms(started_at: float) -> int:
    return int((monotonic() - started_at) * 1000)


def _task_response(task: TaskStatus) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status,
        "device_id": task.device_id,
        "result_summary": task.result_summary,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "context": task.context_json,
    }
