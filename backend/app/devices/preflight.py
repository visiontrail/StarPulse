from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy.orm import Session

from app.api.schemas.auth import (
    ChangePayloadSummary,
    ChangePreflightResponse,
    ChangeRiskSummary,
    SnapshotReferenceRead,
)
from app.auth.audit import write_audit_event
from app.auth.constants import AuditAction, AuditOutcome
from app.common.time import utc_now
from app.core.config import get_settings
from app.devices.config_snapshots import (
    RollbackPayloadDeriveError,
    RollbackPayloadDeriver,
)
from app.devices.constants import SUPPORTED_CONFIG_DATASTORES, DeviceTaskStatus, DeviceTaskType
from app.devices.credentials import CredentialService, CredentialUnavailableError
from app.devices.repository import DeviceRepository
from app.storage.models import DeviceConfigChangeRequest, User


class ChangePreflightService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DeviceRepository(session)

    def preview(
        self,
        *,
        actor: User | None,
        device_id: int,
        datastore: str,
        config_body: str | None,
        reason: str | None,
        ip_address: str | None = None,
        mode: str = "forward",
        rollback_target_snapshot_id: int | None = None,
        rollback_of_change_id: int | None = None,
    ) -> ChangePreflightResponse:
        if mode == "rollback":
            response = self._build_rollback(
                device_id=device_id,
                datastore=datastore,
                reason=reason,
                rollback_target_snapshot_id=rollback_target_snapshot_id,
                rollback_of_change_id=rollback_of_change_id,
            )
        else:
            response = self._build(
                device_id=device_id,
                datastore=datastore,
                config_body=config_body,
                reason=reason,
            )
        self._audit(actor=actor, response=response, ip_address=ip_address)
        return response

    def _build(
        self,
        *,
        device_id: int,
        datastore: str,
        config_body: str | None,
        reason: str | None,
    ) -> ChangePreflightResponse:
        generated_at = utc_now()
        blockers: list[str] = []
        recommended_action: str | None = None
        baseline_snapshot = None
        payload_summary = _payload_summary(config_body)

        device = self.repository.get_with_connection(device_id)
        if device is None:
            blockers.append("device_not_found")
        else:
            if device.connection is None:
                blockers.append("connection_config_missing")
            elif not device.connection.has_credential:
                blockers.append("credential_unavailable")
            else:
                try:
                    CredentialService(self.session).resolve(device.connection.credential_ref)
                except CredentialUnavailableError:
                    blockers.append("credential_unavailable")

            recent_tasks = self.repository.list_recent_tasks(device_id=device_id, limit=20)
            connection_task = _latest_task(recent_tasks, DeviceTaskType.CONNECTION_TEST)
            if connection_task is None or connection_task.status != DeviceTaskStatus.SUCCEEDED:
                blockers.append("connection_test_required")
            if device.last_discovery is None:
                blockers.append("capability_discovery_required")
            if datastore in SUPPORTED_CONFIG_DATASTORES:
                baseline_snapshot = self.repository.get_latest_successful_snapshot(
                    device_id=device_id, datastore=datastore
                )
                if baseline_snapshot is None:
                    blockers.append("baseline_snapshot_required")
                elif _is_stale(baseline_snapshot.collected_at, generated_at):
                    blockers.append("baseline_snapshot_stale")
                    recommended_action = "refresh_baseline_snapshot"

        if datastore not in SUPPORTED_CONFIG_DATASTORES:
            blockers.append("unsupported_datastore")
        if payload_summary is None or payload_summary.is_empty:
            blockers.append("config_body_missing")
        if reason is None or not reason.strip():
            blockers.append("reason_missing")

        # Task 4.5: enforce CHANGE_IN_FLIGHT in forward mode too
        if datastore in SUPPORTED_CONFIG_DATASTORES and not blockers:
            inflight = self.repository.find_inflight_change_requests(
                device_id=device_id, datastore=datastore
            )
            if inflight:
                blockers.append("CHANGE_IN_FLIGHT")

        baseline_ref = (
            SnapshotReferenceRead.model_validate(baseline_snapshot)
            if baseline_snapshot is not None
            else None
        )
        risk_summary = _risk_summary(
            device_id=device_id,
            datastore=datastore,
            baseline=baseline_ref,
            payload=payload_summary,
            blockers=blockers,
        )
        passed = not blockers
        if recommended_action is None and blockers:
            recommended_action = _recommended_action(blockers)
        return ChangePreflightResponse(
            status="passed" if passed else "failed",
            passed=passed,
            device_id=device_id,
            datastore=datastore,
            generated_at=generated_at,
            baseline_snapshot=baseline_ref,
            payload=payload_summary,
            blockers=blockers,
            recommended_action=recommended_action,
            risk_summary=risk_summary,
            mode="forward",
        )

    def _build_rollback(
        self,
        *,
        device_id: int,
        datastore: str,
        reason: str | None,
        rollback_target_snapshot_id: int | None,
        rollback_of_change_id: int | None,
    ) -> ChangePreflightResponse:
        generated_at = utc_now()
        blockers: list[str] = []
        recommended_action: str | None = None
        baseline_snapshot = None
        target_snapshot = None
        payload_summary = None

        device = self.repository.get_with_connection(device_id)
        if device is None:
            blockers.append("device_not_found")
        else:
            if device.connection is None:
                blockers.append("connection_config_missing")
            elif not device.connection.has_credential:
                blockers.append("credential_unavailable")
            else:
                try:
                    CredentialService(self.session).resolve(device.connection.credential_ref)
                except CredentialUnavailableError:
                    blockers.append("credential_unavailable")

            recent_tasks = self.repository.list_recent_tasks(device_id=device_id, limit=20)
            connection_task = _latest_task(recent_tasks, DeviceTaskType.CONNECTION_TEST)
            if connection_task is None or connection_task.status != DeviceTaskStatus.SUCCEEDED:
                blockers.append("connection_test_required")
            if device.last_discovery is None:
                blockers.append("capability_discovery_required")

        if datastore not in SUPPORTED_CONFIG_DATASTORES:
            blockers.append("unsupported_datastore")
        if reason is None or not reason.strip():
            blockers.append("reason_missing")

        # Validate rollback target snapshot
        if rollback_target_snapshot_id is None:
            blockers.append("rollback_target_snapshot_required")
        else:
            target_snapshot = self.repository.get_snapshot_by_id(rollback_target_snapshot_id)
            if target_snapshot is None:
                blockers.append("rollback_target_snapshot_required")
            elif target_snapshot.device_id != device_id or target_snapshot.datastore != datastore:
                blockers.append("rollback_target_mismatch")
            elif not _is_restorable_snapshot(self.repository, target_snapshot):
                blockers.append("ROLLBACK_TARGET_NOT_RESTORABLE")
            else:
                # Check divergence: compare target digest to current latest snapshot
                current_snapshot = self.repository.get_latest_successful_snapshot(
                    device_id=device_id, datastore=datastore
                )
                baseline_snapshot = current_snapshot
                if current_snapshot is None:
                    blockers.append("baseline_snapshot_required")
                elif current_snapshot.content_digest == target_snapshot.content_digest:
                    blockers.append("ROLLBACK_NO_DIVERGENCE")
                # Build payload summary from derived payload
                no_block = (
                    "ROLLBACK_TARGET_NOT_RESTORABLE" not in blockers
                    and "ROLLBACK_NO_DIVERGENCE" not in blockers
                )
                if no_block:
                    try:
                        derived = RollbackPayloadDeriver().build(
                            target_snapshot=target_snapshot, datastore=datastore
                        )
                        payload_summary = ChangePayloadSummary(
                            digest=derived.digest,
                            length=derived.length,
                            line_count=derived.line_count,
                            is_empty=False,
                        )
                    except RollbackPayloadDeriveError:
                        blockers.append("ROLLBACK_TARGET_NOT_RESTORABLE")

        # Validate source change status if provided
        if rollback_of_change_id is not None:
            origin_cr = self.session.get(DeviceConfigChangeRequest, rollback_of_change_id)
            if origin_cr is None or origin_cr.status not in ("verification_failed", "failed"):
                blockers.append("ROLLBACK_ORIGIN_NOT_RECOVERABLE")

        # Enforce CHANGE_IN_FLIGHT for rollback mode
        if not any(b in blockers for b in ("device_not_found", "unsupported_datastore")):
            inflight = self.repository.find_inflight_change_requests(
                device_id=device_id, datastore=datastore
            )
            if inflight:
                blockers.append("CHANGE_IN_FLIGHT")

        baseline_ref = (
            SnapshotReferenceRead.model_validate(baseline_snapshot)
            if baseline_snapshot is not None
            else None
        )
        target_ref = (
            SnapshotReferenceRead.model_validate(target_snapshot)
            if target_snapshot is not None
            else None
        )
        risk_summary = _rollback_risk_summary(
            device_id=device_id,
            datastore=datastore,
            current_snapshot=baseline_ref,
            target_snapshot=target_ref,
            payload=payload_summary,
            blockers=blockers,
        )
        passed = not blockers
        if not passed and recommended_action is None:
            recommended_action = _rollback_recommended_action(blockers)
        return ChangePreflightResponse(
            status="passed" if passed else "failed",
            passed=passed,
            device_id=device_id,
            datastore=datastore,
            generated_at=generated_at,
            baseline_snapshot=baseline_ref,
            payload=payload_summary,
            blockers=blockers,
            recommended_action=recommended_action,
            risk_summary=risk_summary,
            mode="rollback",
            rollback_target_snapshot=target_ref,
        )

    def _audit(
        self,
        *,
        actor: User | None,
        response: ChangePreflightResponse,
        ip_address: str | None,
    ) -> None:
        action = (
            AuditAction.CHANGE_PREFLIGHT_STALE_BASELINE
            if "baseline_snapshot_stale" in response.blockers
            else (
                AuditAction.CHANGE_PREFLIGHT_SUCCESS
                if response.passed
                else AuditAction.CHANGE_PREFLIGHT_FAILURE
            )
        )
        write_audit_event(
            session=self.session,
            action=action,
            outcome=AuditOutcome.SUCCESS if response.passed else AuditOutcome.FAILURE,
                actor_user_id=actor.id if actor is not None else None,
            target_type="device",
            target_id=str(response.device_id),
            ip_address=ip_address,
            metadata={
                "device_id": response.device_id,
                "datastore": response.datastore,
                "status": response.status,
                "mode": response.mode,
                "baseline_snapshot_id": (
                    response.baseline_snapshot.id if response.baseline_snapshot else None
                ),
                "blockers": response.blockers,
                "risk_summary": (
                    response.risk_summary.model_dump(mode="json")
                    if response.risk_summary is not None
                    else None
                ),
            },
        )


def _payload_summary(config_body: str | None) -> ChangePayloadSummary | None:
    if config_body is None:
        return None
    stripped = config_body.strip()
    digest = "sha256:" + sha256(stripped.encode("utf-8")).hexdigest()
    return ChangePayloadSummary(
        digest=digest,
        length=len(stripped),
        line_count=len(stripped.splitlines()) if stripped else 0,
        is_empty=not bool(stripped),
    )


def _risk_summary(
    *,
    device_id: int,
    datastore: str,
    baseline: SnapshotReferenceRead | None,
    payload: ChangePayloadSummary | None,
    blockers: list[str],
) -> ChangeRiskSummary:
    comparison = {
        "datastore": datastore,
        "baseline_digest": baseline.content_digest if baseline else None,
        "payload_digest": payload.digest if payload else None,
        "digest_changes": (
            baseline.content_digest != payload.digest if baseline is not None and payload else None
        ),
    }
    return ChangeRiskSummary(
        device_id=device_id,
        datastore=datastore,
        risk_level="blocked" if blockers else "low",
        baseline_snapshot_id=baseline.id if baseline else None,
        baseline_digest=baseline.content_digest if baseline else None,
        payload=payload,
        blockers=blockers,
        comparison=comparison,
    )


def _rollback_risk_summary(
    *,
    device_id: int,
    datastore: str,
    current_snapshot: SnapshotReferenceRead | None,
    target_snapshot: SnapshotReferenceRead | None,
    payload: ChangePayloadSummary | None,
    blockers: list[str],
) -> ChangeRiskSummary:
    comparison = {
        "datastore": datastore,
        "current_digest": current_snapshot.content_digest if current_snapshot else None,
        "target_digest": target_snapshot.content_digest if target_snapshot else None,
        "payload_digest": payload.digest if payload else None,
        "digest_changed": (
            current_snapshot.content_digest != target_snapshot.content_digest
            if current_snapshot is not None and target_snapshot is not None
            else None
        ),
    }
    return ChangeRiskSummary(
        device_id=device_id,
        datastore=datastore,
        risk_level="blocked" if blockers else "medium",
        baseline_snapshot_id=current_snapshot.id if current_snapshot else None,
        baseline_digest=current_snapshot.content_digest if current_snapshot else None,
        payload=payload,
        blockers=blockers,
        comparison=comparison,
    )


def _latest_task(tasks, task_type: DeviceTaskType):
    for task in tasks:
        if task.task_type == task_type:
            return task
    return None


def _is_stale(collected_at: datetime, now: datetime) -> bool:
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=UTC)
    return now - collected_at > timedelta(
        minutes=get_settings().baseline_snapshot_freshness_minutes
    )


def _is_restorable_snapshot(repository: DeviceRepository, snapshot) -> bool:
    return bool(snapshot.normalized_content) and repository.is_successful_snapshot_source(snapshot)


def _recommended_action(blockers: list[str]) -> str | None:
    if "device_not_found" in blockers:
        return None
    if "unsupported_datastore" in blockers:
        return "choose_supported_datastore"
    if "config_body_missing" in blockers:
        return "provide_config_body"
    if "reason_missing" in blockers:
        return "provide_reason"
    if "connection_config_missing" in blockers or "credential_unavailable" in blockers:
        return "update_connection"
    if "connection_test_required" in blockers:
        return "run_connection_test"
    if "capability_discovery_required" in blockers:
        return "run_capability_discovery"
    if "baseline_snapshot_required" in blockers:
        return "collect_baseline_snapshot"
    if "CHANGE_IN_FLIGHT" in blockers:
        return "wait_for_inflight_change"
    return None


def _rollback_recommended_action(blockers: list[str]) -> str | None:
    if "CHANGE_IN_FLIGHT" in blockers:
        return "wait_for_inflight_change"
    if "ROLLBACK_TARGET_NOT_RESTORABLE" in blockers:
        return "choose_restorable_snapshot"
    if "ROLLBACK_NO_DIVERGENCE" in blockers:
        return "choose_different_snapshot"
    if "ROLLBACK_ORIGIN_NOT_RECOVERABLE" in blockers:
        return "verify_origin_change_status"
    if "rollback_target_mismatch" in blockers:
        return "choose_correct_snapshot"
    return None
