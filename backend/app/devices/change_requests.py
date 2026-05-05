from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.audit import write_audit_event
from app.auth.constants import AuditAction, AuditOutcome
from app.auth.repositories import ChangeRequestRepository
from app.common.time import utc_now
from app.core.config import get_settings
from app.devices.constants import SUPPORTED_CONFIG_DATASTORES
from app.devices.preflight import ChangePreflightService
from app.devices.repository import DeviceRepository
from app.storage.models import DeviceConfigChangeRequest, User
from app.tasks.service import TaskService

logger = logging.getLogger(__name__)


class ChangeRequestError(RuntimeError):
    pass


class ChangeRequestService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._repo = ChangeRequestRepository(session)

    def submit(
        self,
        *,
        actor: User,
        device_id: int,
        datastore: str,
        change_summary: str,
        change_ref: str | None,
        config_body: str | None,
        reason: str,
        ip_address: str | None = None,
    ) -> DeviceConfigChangeRequest:
        config_body = self._require_config_body(
            actor=actor,
            device_id=device_id,
            config_body=config_body,
            ip_address=ip_address,
        )
        if datastore not in SUPPORTED_CONFIG_DATASTORES:
            write_audit_event(
                session=self.session,
                action=AuditAction.VALIDATION_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_user_id=actor.id,
                target_type="device",
                target_id=str(device_id),
                metadata={"reason": "unsupported_datastore", "datastore": datastore},
                ip_address=ip_address,
            )
            self.session.commit()
            raise ChangeRequestError(f"Unsupported datastore: {datastore}")

        device = DeviceRepository(self.session).get_with_connection(device_id)
        if device is None:
            write_audit_event(
                session=self.session,
                action=AuditAction.VALIDATION_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_user_id=actor.id,
                target_type="device",
                target_id=str(device_id),
                metadata={"reason": "device_not_found"},
                ip_address=ip_address,
            )
            self.session.commit()
            raise ChangeRequestError("Device not found")

        preflight = self._run_passing_preflight(
            actor=actor,
            device_id=device_id,
            datastore=datastore,
            config_body=config_body,
            reason=reason,
            ip_address=ip_address,
        )
        cr = self._repo.create(
            device_id=device_id,
            datastore=datastore,
            change_summary=change_summary,
            change_ref=change_ref,
            reason=reason,
            status="pending_approval",
            submitter_id=actor.id,
            **_preflight_fields(preflight),
        )
        self._repo.create_payload(change_request_id=cr.id, config_body=config_body)
        write_audit_event(
            session=self.session,
            action=AuditAction.CHANGE_SUBMITTED,
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            target_type="change_request",
            target_id=str(cr.id),
            metadata={
                "device_id": device_id,
                "datastore": datastore,
                "change_summary": change_summary[:200],
                "config_body_length": len(config_body),
                "baseline_snapshot_id": cr.baseline_snapshot_id,
                "preflight_status": cr.preflight_status,
                "risk_summary": cr.risk_summary,
            },
            ip_address=ip_address,
        )
        self.session.commit()
        self.session.refresh(cr)
        return cr

    def approve(
        self,
        *,
        actor: User,
        cr_id: int,
        approval_note: str | None,
        ip_address: str | None = None,
    ) -> DeviceConfigChangeRequest:
        cr = self._get_pending_or_raise(cr_id)
        self._ensure_preflight_valid(cr, actor=actor, ip_address=ip_address)
        cr.status = "approved"
        cr.approver_id = actor.id
        cr.approval_note = approval_note
        cr.approved_at = utc_now()
        write_audit_event(
            session=self.session,
            action=AuditAction.CHANGE_APPROVED,
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            target_type="change_request",
            target_id=str(cr.id),
            metadata={
                "approval_note": approval_note,
                "preflight_status": cr.preflight_status,
                "risk_summary": cr.risk_summary,
            },
            ip_address=ip_address,
        )
        task_status = TaskService(self.session).submit_config_change(
            device_id=cr.device_id,
            change_request_id=cr.id,
            actor_user_id=actor.id,
            datastore=cr.datastore,
        )
        cr.status = "queued"
        cr.executor_id = actor.id
        cr.execution_task_id = task_status.task_id
        self._repo.save(cr)
        self.session.commit()
        self.session.refresh(cr)
        return cr

    def reject(
        self,
        *,
        actor: User,
        cr_id: int,
        rejection_note: str,
        ip_address: str | None = None,
    ) -> DeviceConfigChangeRequest:
        cr = self._get_pending_or_raise(cr_id)
        cr.status = "rejected"
        cr.approver_id = actor.id
        cr.approval_note = rejection_note
        cr.approved_at = utc_now()
        write_audit_event(
            session=self.session,
            action=AuditAction.CHANGE_REJECTED,
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            target_type="change_request",
            target_id=str(cr.id),
            metadata={"rejection_note": rejection_note[:200]},
            ip_address=ip_address,
        )
        self._repo.save(cr)
        self.session.commit()
        self.session.refresh(cr)
        return cr

    def direct_execute(
        self,
        *,
        actor: User,
        device_id: int,
        datastore: str,
        change_summary: str,
        change_ref: str | None,
        config_body: str | None,
        reason: str,
        ip_address: str | None = None,
    ) -> DeviceConfigChangeRequest:
        config_body = self._require_config_body(
            actor=actor,
            device_id=device_id,
            config_body=config_body,
            ip_address=ip_address,
        )
        if datastore not in SUPPORTED_CONFIG_DATASTORES:
            write_audit_event(
                session=self.session,
                action=AuditAction.VALIDATION_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_user_id=actor.id,
                target_type="device",
                target_id=str(device_id),
                metadata={"reason": "unsupported_datastore", "datastore": datastore},
                ip_address=ip_address,
            )
            self.session.commit()
            raise ChangeRequestError(f"Unsupported datastore: {datastore}")

        device = DeviceRepository(self.session).get_with_connection(device_id)
        if device is None:
            write_audit_event(
                session=self.session,
                action=AuditAction.VALIDATION_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_user_id=actor.id,
                target_type="device",
                target_id=str(device_id),
                metadata={"reason": "device_not_found"},
                ip_address=ip_address,
            )
            self.session.commit()
            raise ChangeRequestError("Device not found")

        preflight = self._run_passing_preflight(
            actor=actor,
            device_id=device_id,
            datastore=datastore,
            config_body=config_body,
            reason=reason,
            ip_address=ip_address,
        )
        cr = self._repo.create(
            device_id=device_id,
            datastore=datastore,
            change_summary=change_summary,
            change_ref=change_ref,
            reason=reason,
            status="queued",
            submitter_id=actor.id,
            approver_id=actor.id,
            approved_at=utc_now(),
            direct_execute=True,
            direct_execute_reason=reason,
            executor_id=actor.id,
            **_preflight_fields(preflight),
        )
        self._repo.create_payload(change_request_id=cr.id, config_body=config_body)
        write_audit_event(
            session=self.session,
            action=AuditAction.CHANGE_DIRECT_EXECUTED,
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            target_type="change_request",
            target_id=str(cr.id),
            metadata={
                "device_id": device_id,
                "datastore": datastore,
                "change_summary": change_summary[:200],
                "direct_execute_reason": reason[:200],
                "direct_execute": True,
                "config_body_length": len(config_body),
                "baseline_snapshot_id": cr.baseline_snapshot_id,
                "preflight_status": cr.preflight_status,
                "risk_summary": cr.risk_summary,
            },
            ip_address=ip_address,
        )
        task_status = TaskService(self.session).submit_config_change(
            device_id=device_id,
            change_request_id=cr.id,
            actor_user_id=actor.id,
            datastore=datastore,
        )
        cr.execution_task_id = task_status.task_id
        self._repo.save(cr)
        self.session.commit()
        self.session.refresh(cr)
        return cr

    def list_requests(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[DeviceConfigChangeRequest]:
        return self._repo.list_all(status=status, limit=limit, offset=offset)

    def get_request(self, cr_id: int) -> DeviceConfigChangeRequest | None:
        return self._repo.get_by_id(cr_id)

    def _run_passing_preflight(
        self,
        *,
        actor: User,
        device_id: int,
        datastore: str,
        config_body: str,
        reason: str,
        ip_address: str | None,
    ):
        preflight = ChangePreflightService(self.session).preview(
            actor=actor,
            device_id=device_id,
            datastore=datastore,
            config_body=config_body,
            reason=reason,
            ip_address=ip_address,
        )
        if not preflight.passed:
            self.session.commit()
            raise ChangeRequestError(
                "Change preflight failed: " + ", ".join(preflight.blockers)
            )
        return preflight

    def _ensure_preflight_valid(
        self,
        cr: DeviceConfigChangeRequest,
        *,
        actor: User,
        ip_address: str | None,
    ) -> None:
        if cr.preflight_status != "passed" or cr.baseline_snapshot_id is None:
            raise ChangeRequestError("Change request does not have a valid preflight")

        baseline = DeviceRepository(self.session).get_latest_successful_snapshot(
            device_id=cr.device_id, datastore=cr.datastore
        )
        if baseline is None or baseline.id != cr.baseline_snapshot_id:
            raise ChangeRequestError("Change request preflight baseline must be refreshed")

        age_seconds = (utc_now() - _aware_datetime(baseline.collected_at)).total_seconds()
        freshness_seconds = get_settings().baseline_snapshot_freshness_minutes * 60
        if age_seconds > freshness_seconds:
            write_audit_event(
                session=self.session,
                action=AuditAction.CHANGE_PREFLIGHT_STALE_BASELINE,
                outcome=AuditOutcome.FAILURE,
                actor_user_id=actor.id,
                target_type="change_request",
                target_id=str(cr.id),
                metadata={
                    "device_id": cr.device_id,
                    "datastore": cr.datastore,
                    "baseline_snapshot_id": cr.baseline_snapshot_id,
                    "preflight_status": cr.preflight_status,
                },
                ip_address=ip_address,
            )
            self.session.commit()
            raise ChangeRequestError("Change request preflight baseline is stale")

    def _get_pending_or_raise(self, cr_id: int) -> DeviceConfigChangeRequest:
        cr = self._repo.get_by_id(cr_id)
        if cr is None:
            raise ChangeRequestError("Change request not found")
        if cr.status != "pending_approval":
            raise ChangeRequestError(f"Change request is not pending approval (status={cr.status})")
        return cr

    def _require_config_body(
        self,
        *,
        actor: User,
        device_id: int,
        config_body: str | None,
        ip_address: str | None,
    ) -> str:
        if config_body is None or not config_body.strip():
            write_audit_event(
                session=self.session,
                action=AuditAction.VALIDATION_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_user_id=actor.id,
                target_type="device",
                target_id=str(device_id),
                metadata={"reason": "config_body_missing"},
                ip_address=ip_address,
            )
            self.session.commit()
            raise ChangeRequestError("Config body is required for executable config changes")
        return config_body


def _preflight_fields(preflight) -> dict[str, object]:
    return {
        "baseline_snapshot_id": (
            preflight.baseline_snapshot.id if preflight.baseline_snapshot else None
        ),
        "preflight_status": preflight.status,
        "preflight_summary": preflight.model_dump(mode="json", exclude={"risk_summary"}),
        "risk_summary": (
            preflight.risk_summary.model_dump(mode="json")
            if preflight.risk_summary is not None
            else None
        ),
        "preflight_generated_at": preflight.generated_at,
    }


def _aware_datetime(value):
    from datetime import UTC

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
