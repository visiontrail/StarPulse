from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.audit import write_audit_event
from app.auth.constants import AuditAction, AuditOutcome
from app.auth.repositories import ChangeRequestRepository
from app.common.time import utc_now
from app.devices.constants import SUPPORTED_CONFIG_DATASTORES
from app.devices.repository import DeviceRepository
from app.storage.models import DeviceConfigChangeRequest, User

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
        reason: str,
        ip_address: str | None = None,
    ) -> DeviceConfigChangeRequest:
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

        cr = self._repo.create(
            device_id=device_id,
            datastore=datastore,
            change_summary=change_summary,
            change_ref=change_ref,
            reason=reason,
            status="pending_approval",
            submitter_id=actor.id,
        )
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
            metadata={"approval_note": approval_note},
            ip_address=ip_address,
        )
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
        reason: str,
        ip_address: str | None = None,
    ) -> DeviceConfigChangeRequest:
        if datastore not in SUPPORTED_CONFIG_DATASTORES:
            raise ChangeRequestError(f"Unsupported datastore: {datastore}")

        device = DeviceRepository(self.session).get_with_connection(device_id)
        if device is None:
            raise ChangeRequestError("Device not found")

        cr = self._repo.create(
            device_id=device_id,
            datastore=datastore,
            change_summary=change_summary,
            change_ref=change_ref,
            reason=reason,
            status="approved",
            submitter_id=actor.id,
            approver_id=actor.id,
            direct_execute=True,
            direct_execute_reason=reason,
            executor_id=actor.id,
        )
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
            },
            ip_address=ip_address,
        )
        from app.tasks.service import TaskService

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

    def _get_pending_or_raise(self, cr_id: int) -> DeviceConfigChangeRequest:
        cr = self._repo.get_by_id(cr_id)
        if cr is None:
            raise ChangeRequestError("Change request not found")
        if cr.status != "pending_approval":
            raise ChangeRequestError(f"Change request is not pending approval (status={cr.status})")
        return cr
