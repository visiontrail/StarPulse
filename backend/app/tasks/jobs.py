from __future__ import annotations

import logging
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic

from app.auth.repositories import ChangeRequestRepository
from app.common.redaction import redact_sensitive
from app.core.config import get_settings
from app.devices.config_snapshots import (
    ConfigSnapshotService,
    RollbackPayloadDeriveError,
    RollbackPayloadDeriver,
)
from app.devices.constants import (
    DeviceAccessErrorCode,
    DeviceStatus,
    DeviceTaskStatus,
    DeviceTaskType,
)
from app.devices.credentials import CredentialService, CredentialUnavailableError
from app.devices.preflight import ChangePreflightService
from app.devices.repository import DeviceRepository
from app.netconf.client import NetconfConnectionParams
from app.netconf.services import NetconfService
from app.storage.database import SessionLocal
from app.storage.models import DeviceConfigChangeRequest, DeviceConfigSnapshot, TaskStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


class ChangePayloadUnavailableError(RuntimeError):
    pass


class RollbackPayloadMismatchError(RuntimeError):
    pass


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
                result = service.write_config(
                    params, _task_datastore(task), _task_config_body(task, session)
                )
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
                    _record_change_exec_failure(
                        session, task, result.error_message or "NETCONF write failed"
                    )
                    _mark_change_request_finished(
                        session, task, status="failed", executed_at=datetime.now(UTC)
                    )
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
                _mark_change_request_verifying(
                    session, task, executed_at=datetime.now(UTC)
                )
                verification_result = service.read_config(params, _task_datastore(task))
                if not verification_result.ok:
                    _mark_verification_failed(
                        session=session,
                        repository=repository,
                        task=task,
                        error_code=(
                            verification_result.error_code
                            or DeviceAccessErrorCode.INTERNAL_ERROR
                        ),
                        error_message=(
                            verification_result.error_message
                            or "Post-change verification failed"
                        ),
                        context=verification_result.context,
                        started_at=started_at,
                    )
                    session.commit()
                    return _task_response(task)
                snapshot_result = ConfigSnapshotService(session).save_read_result(
                    device_id=task.device_id or 0,
                    source_task_id=task.task_id,
                    datastore=_task_datastore(task),
                    result=verification_result,
                    collected_at=datetime.now(UTC),
                )
                comparison = _build_verification_comparison(
                    session=session,
                    task=task,
                    post_change_snapshot_id=snapshot_result.snapshot.id,
                    post_change_digest=snapshot_result.snapshot.content_digest,
                )

                # Task 6.2: for rollback changes, check target digest match
                rollback_digest_mismatch = False
                if task.change_request_id is not None:
                    cr = session.get(DeviceConfigChangeRequest, task.change_request_id)
                    if (
                        cr is not None
                        and cr.is_rollback
                        and cr.rollback_target_snapshot_id is not None
                    ):
                        from app.storage.models import DeviceConfigSnapshot as _DCS

                        target_snap = session.get(_DCS, cr.rollback_target_snapshot_id)
                        post_digest = snapshot_result.snapshot.content_digest
                        if target_snap is not None and target_snap.content_digest != post_digest:
                            rollback_digest_mismatch = True

                if rollback_digest_mismatch:
                    from app.devices.constants import DeviceAccessErrorCode as _EC

                    _mark_verification_failed(
                        session=session,
                        repository=repository,
                        task=task,
                        error_code=_EC.INTERNAL_ERROR,
                        error_message=(
                            "Rollback verification failed: "
                            "post-change digest does not match target snapshot"
                        ),
                        context={},
                        started_at=started_at,
                        is_rollback=True,
                    )
                    session.commit()
                    return _task_response(task)

                result_summary = {
                    "ok": True,
                    "write": "success",
                    "verification": "passed",
                    "post_change_snapshot_id": snapshot_result.snapshot.id,
                    "comparison": comparison,
                }
                _record_change_exec_success(session, task)
                _record_change_verification_success(session, task, comparison)
                _mark_change_request_verified(
                    session=session,
                    task=task,
                    verification_snapshot_id=snapshot_result.snapshot.id,
                    verification_summary=result_summary,
                    verified_at=datetime.now(UTC),
                )
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
            _record_onboarding_task_result(session, task, outcome="success")
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
            if action == "config_change":
                _record_change_exec_failure(session, task, "Device credential is unavailable")
                _mark_change_request_finished(
                    session, task, status="failed", executed_at=datetime.now(UTC)
                )
            session.commit()
            return _task_response(task)
        except ChangePayloadUnavailableError:
            session.rollback()
            task = session.query(TaskStatus).filter(TaskStatus.task_id == task_id).one()
            repository = DeviceRepository(session)
            _mark_failed(
                repository,
                task,
                error_code=DeviceAccessErrorCode.INVALID_PARAMETER,
                error_message="Config change payload is unavailable",
                context={"device_id": task.device_id, "change_request_id": task.change_request_id},
                started_at=started_at,
            )
            if action == "config_change":
                _record_change_exec_failure(
                    session, task, "Config change payload is unavailable"
                )
                _mark_change_request_finished(
                    session, task, status="failed", executed_at=datetime.now(UTC)
                )
            session.commit()
            return _task_response(task)
        except RollbackPayloadMismatchError as exc:
            session.rollback()
            task = session.query(TaskStatus).filter(TaskStatus.task_id == task_id).one()
            repository = DeviceRepository(session)
            _mark_failed(
                repository,
                task,
                error_code=DeviceAccessErrorCode.INVALID_PARAMETER,
                error_message="Rollback payload digest mismatch",
                context={"device_id": task.device_id, "change_request_id": task.change_request_id},
                started_at=started_at,
            )
            if action == "config_change":
                _record_change_exec_failure(session, task, str(exc))
                _mark_change_request_finished(
                    session, task, status="failed", executed_at=datetime.now(UTC)
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
            if action == "config_change":
                _record_change_exec_failure(session, task, "Device task failed")
                _mark_change_request_finished(
                    session, task, status="failed", executed_at=datetime.now(UTC)
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
    if task.task_type == DeviceTaskType.CONFIG_CHANGE:
        _mark_change_request_status(repository.session, task, status="running")
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
    _record_onboarding_task_result(repository.session, task, outcome="failure")
    _log_task(task, "failed", started_at, error_code=error_code)


def _safe_task_context(task: TaskStatus, started_at: float) -> dict[str, object]:
    context = {
        "device_id": task.device_id,
        "duration_ms": _duration_ms(started_at),
    }
    if task.metadata_json.get("datastore") is not None:
        context["datastore"] = task.metadata_json["datastore"]
    if task.actor_user_id is not None:
        context["actor_user_id"] = task.actor_user_id
    return context


def _task_datastore(task: TaskStatus) -> str:
    value = task.metadata_json.get("datastore")
    return str(value or "running")


def _task_config_body(task: TaskStatus, session) -> str:
    if task.change_request_id is None:
        raise ChangePayloadUnavailableError("Task is missing change request context")
    payload = ChangeRequestRepository(session).get_payload(task.change_request_id)
    if payload is None or not payload.config_body.strip():
        raise ChangePayloadUnavailableError("Config change payload is unavailable")
    _validate_rollback_payload_digest(task, session, payload.config_body)
    return payload.config_body


def _validate_rollback_payload_digest(task: TaskStatus, session, config_body: str) -> None:
    if task.change_request_id is None:
        return
    cr = session.get(DeviceConfigChangeRequest, task.change_request_id)
    if cr is None or not cr.is_rollback:
        return
    if cr.rollback_target_snapshot_id is None:
        raise RollbackPayloadMismatchError("Rollback target snapshot is missing")
    target_snapshot = session.get(DeviceConfigSnapshot, cr.rollback_target_snapshot_id)
    if target_snapshot is None or not target_snapshot.normalized_content:
        raise RollbackPayloadMismatchError("Rollback target snapshot is no longer restorable")
    try:
        derived = RollbackPayloadDeriver().build(
            target_snapshot=target_snapshot,
            datastore=cr.datastore,
        )
    except RollbackPayloadDeriveError as exc:
        raise RollbackPayloadMismatchError(
            f"Rollback target snapshot is no longer restorable: {exc.blocker}"
        ) from exc
    stored_digest = "sha256:" + sha256(config_body.encode("utf-8")).hexdigest()
    if stored_digest != derived.digest:
        raise RollbackPayloadMismatchError(
            "Stored rollback payload digest does not match target snapshot"
        )


def _record_change_exec_success(session, task: TaskStatus) -> None:
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome

    cr = (
        session.get(DeviceConfigChangeRequest, task.change_request_id)
        if task.change_request_id
        else None
    )
    metadata: dict[str, object] = {"task_id": task.task_id, "device_id": task.device_id}
    if cr is not None:
        metadata["is_rollback"] = cr.is_rollback
        if cr.is_rollback:
            metadata["rollback_of_change_id"] = cr.rollback_of_change_id
            metadata["rollback_target_snapshot_id"] = cr.rollback_target_snapshot_id
    write_audit_event(
        session=session,
        action=AuditAction.CHANGE_EXEC_SUCCESS,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=task.actor_user_id,
        target_type="change_request",
        target_id=str(task.change_request_id) if task.change_request_id else None,
        metadata=metadata,
    )


def _record_change_exec_failure(session, task: TaskStatus, error_message: str) -> None:
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome

    cr = (
        session.get(DeviceConfigChangeRequest, task.change_request_id)
        if task.change_request_id
        else None
    )
    metadata: dict[str, object] = {
        "task_id": task.task_id,
        "device_id": task.device_id,
        "error": error_message,
    }
    if cr is not None:
        metadata["is_rollback"] = cr.is_rollback
        if cr.is_rollback:
            metadata["rollback_of_change_id"] = cr.rollback_of_change_id
            metadata["rollback_target_snapshot_id"] = cr.rollback_target_snapshot_id
    write_audit_event(
        session=session,
        action=AuditAction.CHANGE_EXEC_FAILURE,
        outcome=AuditOutcome.FAILURE,
        actor_user_id=task.actor_user_id,
        target_type="change_request",
        target_id=str(task.change_request_id) if task.change_request_id else None,
        metadata=metadata,
    )


def _record_change_verification_success(
    session, task: TaskStatus, comparison: dict[str, object]
) -> None:
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome

    cr = (
        session.get(DeviceConfigChangeRequest, task.change_request_id)
        if task.change_request_id
        else None
    )
    is_rollback = cr.is_rollback if cr else False
    action = (
        AuditAction.CHANGE_ROLLBACK_VERIFIED
        if is_rollback
        else AuditAction.CHANGE_VERIFICATION_SUCCESS
    )
    metadata: dict[str, object] = {
        "task_id": task.task_id,
        "device_id": task.device_id,
        "comparison": comparison,
        "is_rollback": is_rollback,
    }
    if is_rollback and cr:
        metadata["is_rollback"] = True
        metadata["rollback_of_change_id"] = cr.rollback_of_change_id
        metadata["rollback_target_snapshot_id"] = cr.rollback_target_snapshot_id
    write_audit_event(
        session=session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=task.actor_user_id,
        target_type="change_request",
        target_id=str(task.change_request_id) if task.change_request_id else None,
        metadata=metadata,
    )


def _record_change_verification_failure(
    session, task: TaskStatus, error_code: DeviceAccessErrorCode, error_message: str
) -> None:
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome

    cr = (
        session.get(DeviceConfigChangeRequest, task.change_request_id)
        if task.change_request_id
        else None
    )
    metadata: dict[str, object] = {
        "task_id": task.task_id,
        "device_id": task.device_id,
        "error_code": error_code.value,
        "error_message": error_message,
        "is_rollback": cr.is_rollback if cr else False,
    }
    if cr is not None and cr.is_rollback:
        metadata["rollback_of_change_id"] = cr.rollback_of_change_id
        metadata["rollback_target_snapshot_id"] = cr.rollback_target_snapshot_id
    write_audit_event(
        session=session,
        action=AuditAction.CHANGE_VERIFICATION_FAILURE,
        outcome=AuditOutcome.FAILURE,
        actor_user_id=task.actor_user_id,
        target_type="change_request",
        target_id=str(task.change_request_id) if task.change_request_id else None,
        metadata=metadata,
    )


def _record_rollback_verification_failure(
    session, task: TaskStatus, error_code: DeviceAccessErrorCode, error_message: str
) -> None:
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome

    cr = (
        session.get(DeviceConfigChangeRequest, task.change_request_id)
        if task.change_request_id
        else None
    )
    write_audit_event(
        session=session,
        action=AuditAction.CHANGE_ROLLBACK_VERIFICATION_FAILED,
        outcome=AuditOutcome.FAILURE,
        actor_user_id=task.actor_user_id,
        target_type="change_request",
        target_id=str(task.change_request_id) if task.change_request_id else None,
        metadata={
            "task_id": task.task_id,
            "device_id": task.device_id,
            "error_code": error_code.value,
            "error_message": error_message,
            "is_rollback": True,
            "rollback_of_change_id": cr.rollback_of_change_id if cr else None,
            "rollback_target_snapshot_id": cr.rollback_target_snapshot_id if cr else None,
        },
    )


def _try_auto_propose_rollback(
    session,
    repository: DeviceRepository,
    task: TaskStatus,
    change_request: DeviceConfigChangeRequest,
) -> None:
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome
    from app.auth.repositories import ChangeRequestRepository
    # Task 6.3: never recurse for is_rollback=True
    if change_request.is_rollback:
        return

    # Task 6.5: skip if no baseline snapshot
    if change_request.baseline_snapshot_id is None:
        write_audit_event(
            session=session,
            action=AuditAction.CHANGE_ROLLBACK_PROPOSAL_SKIPPED,
            outcome=AuditOutcome.FAILURE,
            actor_user_id=None,
            target_type="change_request",
            target_id=str(change_request.id),
            metadata={
                "reason": "no_baseline_snapshot",
                "change_request_id": change_request.id,
                "originated_for_user_id": change_request.submitter_id,
            },
        )
        return

    target_snapshot = repository.get_snapshot_by_id(change_request.baseline_snapshot_id)
    if (
        target_snapshot is None
        or not target_snapshot.normalized_content
        or not repository.is_successful_snapshot_source(target_snapshot)
    ):
        write_audit_event(
            session=session,
            action=AuditAction.CHANGE_ROLLBACK_PROPOSAL_SKIPPED,
            outcome=AuditOutcome.FAILURE,
            actor_user_id=None,
            target_type="change_request",
            target_id=str(change_request.id),
            metadata={
                "reason": "baseline_snapshot_not_restorable",
                "change_request_id": change_request.id,
                "baseline_snapshot_id": change_request.baseline_snapshot_id,
            },
        )
        return

    try:
        derived = RollbackPayloadDeriver().build(
            target_snapshot=target_snapshot, datastore=change_request.datastore
        )
    except RollbackPayloadDeriveError as exc:
        write_audit_event(
            session=session,
            action=AuditAction.CHANGE_ROLLBACK_PROPOSAL_SKIPPED,
            outcome=AuditOutcome.FAILURE,
            actor_user_id=None,
            target_type="change_request",
            target_id=str(change_request.id),
            metadata={
                "reason": exc.blocker,
                "change_request_id": change_request.id,
                "baseline_snapshot_id": change_request.baseline_snapshot_id,
            },
        )
        return

    cr_repo = ChangeRequestRepository(session)
    if cr_repo.find_latest_rollback_proposal(change_request.id) is not None:
        return

    rollback_reason = (
        f"Automatic rollback proposal after verification failure "
        f"of change #{change_request.id}"
    )
    preflight = ChangePreflightService(session).preview(
        actor=None,
        device_id=change_request.device_id,
        datastore=change_request.datastore,
        config_body=None,
        reason=rollback_reason,
        mode="rollback",
        rollback_target_snapshot_id=target_snapshot.id,
        rollback_of_change_id=change_request.id,
    )
    rollback_cr = cr_repo.create(
        device_id=change_request.device_id,
        datastore=change_request.datastore,
        change_summary=f"Auto-proposed rollback for change #{change_request.id}",
        change_ref=None,
        reason=rollback_reason,
        status="pending_approval",
        submitter_id=change_request.submitter_id,
        is_rollback=True,
        rollback_of_change_id=change_request.id,
        rollback_target_snapshot_id=target_snapshot.id,
        **_preflight_fields(preflight),
    )
    cr_repo.create_payload(
        change_request_id=rollback_cr.id,
        config_body=derived.config_body,
        body_digest=derived.digest,
        body_length=derived.length,
        line_count=derived.line_count,
        summary_source=derived.source_label,
    )
    write_audit_event(
        session=session,
        action=AuditAction.CHANGE_ROLLBACK_PROPOSED,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=None,
        target_type="change_request",
        target_id=str(rollback_cr.id),
        metadata={
            "rollback_of_change_id": change_request.id,
            "rollback_target_snapshot_id": target_snapshot.id,
            "device_id": change_request.device_id,
            "datastore": change_request.datastore,
            "origin_status": change_request.status,
            "originated_for_user_id": change_request.submitter_id,
            "payload_digest": derived.digest,
            "preflight_status": rollback_cr.preflight_status,
        },
    )


def _record_onboarding_task_result(session, task: TaskStatus, *, outcome: str) -> None:
    if task.task_type not in {
        DeviceTaskType.CONNECTION_TEST,
        DeviceTaskType.CAPABILITY_DISCOVERY,
        DeviceTaskType.CONFIG_SNAPSHOT,
    }:
        return
    from app.auth.audit import write_audit_event
    from app.auth.constants import AuditAction, AuditOutcome

    step_by_type = {
        DeviceTaskType.CONNECTION_TEST: "connection_test",
        DeviceTaskType.CAPABILITY_DISCOVERY: "capability_discovery",
        DeviceTaskType.CONFIG_SNAPSHOT: "baseline_snapshot",
    }
    metadata = {
        "device_id": task.device_id,
        "step": step_by_type.get(task.task_type, task.task_type),
        "task_id": task.task_id,
        "status": task.status,
        "result_summary": task.result_summary or {},
        "error_code": task.error_code,
    }
    if task.metadata_json.get("datastore") is not None:
        metadata["datastore"] = task.metadata_json["datastore"]
    write_audit_event(
        session=session,
        action=(
            AuditAction.DEVICE_ONBOARDING_STEP_SUCCESS
            if outcome == "success"
            else AuditAction.DEVICE_ONBOARDING_STEP_FAILURE
        ),
        outcome=AuditOutcome.SUCCESS if outcome == "success" else AuditOutcome.FAILURE,
        actor_user_id=task.actor_user_id,
        target_type="device",
        target_id=str(task.device_id) if task.device_id is not None else None,
        metadata=metadata,
    )


def _mark_change_request_finished(
    session,
    task: TaskStatus,
    *,
    status: str,
    executed_at: datetime,
) -> None:
    if task.change_request_id is None:
        return
    change_request = session.get(DeviceConfigChangeRequest, task.change_request_id)
    if change_request is None:
        return
    change_request.status = status
    change_request.executor_id = task.actor_user_id
    change_request.executed_at = executed_at
    session.add(change_request)


def _mark_change_request_status(session, task: TaskStatus, *, status: str) -> None:
    if task.change_request_id is None:
        return
    change_request = session.get(DeviceConfigChangeRequest, task.change_request_id)
    if change_request is None:
        return
    change_request.status = status
    session.add(change_request)


def _mark_change_request_verifying(
    session, task: TaskStatus, *, executed_at: datetime
) -> None:
    if task.change_request_id is None:
        return
    change_request = session.get(DeviceConfigChangeRequest, task.change_request_id)
    if change_request is None:
        return
    change_request.status = "verifying"
    change_request.executor_id = task.actor_user_id
    change_request.executed_at = executed_at
    session.add(change_request)


def _mark_change_request_verified(
    *,
    session,
    task: TaskStatus,
    verification_snapshot_id: int,
    verification_summary: dict[str, object],
    verified_at: datetime,
) -> None:
    if task.change_request_id is None:
        return
    change_request = session.get(DeviceConfigChangeRequest, task.change_request_id)
    if change_request is None:
        return
    change_request.status = "executed"
    change_request.verification_status = "passed"
    change_request.verification_snapshot_id = verification_snapshot_id
    change_request.verification_summary = verification_summary
    change_request.verified_at = verified_at
    session.add(change_request)


def _mark_verification_failed(
    *,
    session,
    repository: DeviceRepository,
    task: TaskStatus,
    error_code: DeviceAccessErrorCode,
    error_message: str,
    context: dict[str, object],
    started_at: float,
    is_rollback: bool = False,
) -> None:
    safe_context = _safe_task_context(task, started_at) | dict(redact_sensitive(context))
    summary = {
        "ok": False,
        "write": "success",
        "verification": "failed",
        "error_code": error_code.value,
        "error_message": error_message,
    }
    repository.update_task_status(
        task,
        status=DeviceTaskStatus.FAILED,
        result_summary=summary,
        error_code=error_code,
        error_message="Post-change verification failed",
        context=safe_context,
        completed_at=datetime.now(UTC),
    )
    change_request = None
    if task.change_request_id is not None:
        change_request = session.get(DeviceConfigChangeRequest, task.change_request_id)
        if change_request is not None:
            change_request.status = "verification_failed"
            change_request.verification_status = "failed"
            change_request.verification_summary = summary
            change_request.verified_at = datetime.now(UTC)
            session.add(change_request)
            is_rollback = is_rollback or change_request.is_rollback

    _record_change_exec_success(session, task)

    if is_rollback:
        _record_rollback_verification_failure(session, task, error_code, error_message)
    else:
        _record_change_verification_failure(session, task, error_code, error_message)
        # Task 6.4: auto-propose rollback for non-rollback changes
        if change_request is not None:
            _try_auto_propose_rollback(session, repository, task, change_request)

    _log_task(task, "failed", started_at, error_code=error_code)


def _build_verification_comparison(
    *,
    session,
    task: TaskStatus,
    post_change_snapshot_id: int,
    post_change_digest: str,
) -> dict[str, object]:
    baseline_snapshot_id = None
    baseline_digest = None
    if task.change_request_id is not None:
        change_request = session.get(DeviceConfigChangeRequest, task.change_request_id)
        if change_request is not None:
            baseline_snapshot_id = change_request.baseline_snapshot_id
            if change_request.baseline_snapshot is not None:
                baseline_digest = change_request.baseline_snapshot.content_digest
    return {
        "baseline_snapshot_id": baseline_snapshot_id,
        "baseline_digest": baseline_digest,
        "post_change_snapshot_id": post_change_snapshot_id,
        "post_change_digest": post_change_digest,
        "digest_changed": (
            baseline_digest != post_change_digest if baseline_digest is not None else None
        ),
    }


def _preflight_fields(preflight) -> dict[str, object]:
    return {
        "baseline_snapshot_id": (
            preflight.baseline_snapshot.id if preflight.baseline_snapshot else None
        ),
        "preflight_status": preflight.status,
        "preflight_summary": preflight.model_dump(
            mode="json", exclude={"risk_summary", "rollback_target_snapshot"}
        ),
        "risk_summary": (
            preflight.risk_summary.model_dump(mode="json")
            if preflight.risk_summary is not None
            else None
        ),
        "preflight_generated_at": preflight.generated_at,
    }


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
