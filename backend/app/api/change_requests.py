from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.schemas.auth import (
    ChangePreflightRequest,
    ChangePreflightResponse,
    ChangeRequestApproveRequest,
    ChangeRequestDirectExecuteRequest,
    ChangeRequestListResponse,
    ChangeRequestRead,
    ChangeRequestReferenceRead,
    ChangeRequestRejectRequest,
    ChangeRequestSubmitRequest,
    RollbackDirectExecuteRequest,
    RollbackSubmitRequest,
)
from app.auth.audit import write_audit_event
from app.auth.constants import (
    PERM_DEVICE_CHANGE_APPROVE,
    PERM_DEVICE_CHANGE_EXECUTE,
    PERM_DEVICE_CHANGE_SUBMIT,
    AuditAction,
    AuditOutcome,
)
from app.auth.dependencies import CurrentUserDep, SessionDep, require_permission
from app.auth.repositories import ChangeRequestRepository
from app.devices.change_requests import ChangeRequestError, ChangeRequestService
from app.devices.preflight import ChangePreflightService

router = APIRouter(prefix="/change-requests", tags=["change-requests"])


@router.post(
    "",
    response_model=ChangeRequestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_SUBMIT)],
)
def submit_change_request(
    payload: ChangeRequestSubmitRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ChangeRequestRead:
    try:
        cr = ChangeRequestService(session).submit(
            actor=actor,
            device_id=payload.device_id,
            datastore=payload.datastore,
            change_summary=payload.change_summary,
            change_ref=payload.change_ref,
            config_body=payload.config_body,
            reason=payload.reason,
            ip_address=request.client.host if request.client else None,
        )
    except ChangeRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _change_request_read(cr, session)


@router.post(
    "/preflight",
    response_model=ChangePreflightResponse,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_SUBMIT)],
)
def preview_change_preflight(
    payload: ChangePreflightRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ChangePreflightResponse:
    if payload.mode == "rollback" and not _has_permission(actor, PERM_DEVICE_CHANGE_APPROVE):
        write_audit_event(
            session=session,
            action=AuditAction.PERMISSION_DENIED,
            outcome=AuditOutcome.DENIED,
            actor_user_id=actor.id,
            permission=PERM_DEVICE_CHANGE_APPROVE,
            target_type="endpoint",
            target_id=request.url.path,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"mode": payload.mode, "operation": "rollback_preflight"},
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    preflight = ChangePreflightService(session).preview(
        actor=actor,
        device_id=payload.device_id,
        datastore=payload.datastore,
        config_body=payload.config_body,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
        mode=payload.mode,
        rollback_target_snapshot_id=payload.rollback_target_snapshot_id,
        rollback_of_change_id=payload.rollback_of_change_id,
    )
    session.commit()
    return preflight


@router.get(
    "",
    response_model=ChangeRequestListResponse,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_SUBMIT)],
)
def list_change_requests(
    session: SessionDep,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ChangeRequestListResponse:
    items = ChangeRequestService(session).list_requests(
        status=status_filter, limit=limit, offset=offset
    )
    return ChangeRequestListResponse(
        items=[_change_request_read(cr, session) for cr in items],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{cr_id}",
    response_model=ChangeRequestRead,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_SUBMIT)],
)
def get_change_request(cr_id: int, session: SessionDep) -> ChangeRequestRead:
    cr = ChangeRequestService(session).get_request(cr_id)
    if cr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _change_request_read(cr, session)


@router.post(
    "/{cr_id}/approve",
    response_model=ChangeRequestRead,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_APPROVE)],
)
def approve_change_request(
    cr_id: int,
    payload: ChangeRequestApproveRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ChangeRequestRead:
    try:
        cr = ChangeRequestService(session).approve(
            actor=actor,
            cr_id=cr_id,
            approval_note=payload.approval_note,
            ip_address=request.client.host if request.client else None,
        )
    except ChangeRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _change_request_read(cr, session)


@router.post(
    "/{cr_id}/reject",
    response_model=ChangeRequestRead,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_APPROVE)],
)
def reject_change_request(
    cr_id: int,
    payload: ChangeRequestRejectRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ChangeRequestRead:
    try:
        cr = ChangeRequestService(session).reject(
            actor=actor,
            cr_id=cr_id,
            rejection_note=payload.rejection_note,
            ip_address=request.client.host if request.client else None,
        )
    except ChangeRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _change_request_read(cr, session)


@router.post(
    "/direct-execute",
    response_model=ChangeRequestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_EXECUTE)],
)
def direct_execute(
    payload: ChangeRequestDirectExecuteRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ChangeRequestRead:
    try:
        cr = ChangeRequestService(session).direct_execute(
            actor=actor,
            device_id=payload.device_id,
            datastore=payload.datastore,
            change_summary=payload.change_summary,
            change_ref=payload.change_ref,
            config_body=payload.config_body,
            reason=payload.reason,
            ip_address=request.client.host if request.client else None,
        )
    except ChangeRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _change_request_read(cr, session)


@router.post(
    "/rollback",
    response_model=ChangeRequestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_APPROVE)],
)
def submit_rollback(
    payload: RollbackSubmitRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ChangeRequestRead:
    try:
        cr = ChangeRequestService(session).submit_rollback(
            actor=actor,
            device_id=payload.device_id,
            datastore=payload.datastore,
            change_summary=payload.change_summary,
            reason=payload.reason,
            rollback_target_snapshot_id=payload.rollback_target_snapshot_id,
            rollback_of_change_id=payload.rollback_of_change_id,
            ip_address=request.client.host if request.client else None,
        )
    except ChangeRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _change_request_read(cr, session)


@router.post(
    "/rollback-execute",
    response_model=ChangeRequestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(PERM_DEVICE_CHANGE_EXECUTE)],
)
def rollback_direct_execute(
    payload: RollbackDirectExecuteRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> ChangeRequestRead:
    try:
        cr = ChangeRequestService(session).rollback_direct_execute(
            actor=actor,
            device_id=payload.device_id,
            datastore=payload.datastore,
            change_summary=payload.change_summary,
            reason=payload.reason,
            rollback_target_snapshot_id=payload.rollback_target_snapshot_id,
            rollback_of_change_id=payload.rollback_of_change_id,
            ip_address=request.client.host if request.client else None,
        )
    except ChangeRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _change_request_read(cr, session)


def _change_request_read(cr, session: Session) -> ChangeRequestRead:
    repo = ChangeRequestRepository(session)
    updates: dict[str, object] = {}
    if cr.rollback_of_change_id is not None:
        origin = repo.get_by_id(cr.rollback_of_change_id)
        if origin is not None:
            updates["rollback_of_change"] = ChangeRequestReferenceRead.model_validate(origin)
    if cr.status == "verification_failed" and not cr.is_rollback:
        proposal = repo.find_latest_rollback_proposal(cr.id)
        if proposal is not None:
            updates["pending_rollback_proposal"] = ChangeRequestReferenceRead.model_validate(
                proposal
            )
            if proposal.status == "pending_approval":
                updates["pending_rollback_proposal_id"] = proposal.id
    return ChangeRequestRead.model_validate(cr).model_copy(update=updates)


def _has_permission(actor, permission: str) -> bool:
    return any(perm.name == permission for role in actor.roles for perm in role.permissions)
