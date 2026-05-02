from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.schemas.auth import (
    ChangeRequestApproveRequest,
    ChangeRequestDirectExecuteRequest,
    ChangeRequestListResponse,
    ChangeRequestRead,
    ChangeRequestRejectRequest,
    ChangeRequestSubmitRequest,
)
from app.auth.constants import (
    PERM_DEVICE_CHANGE_APPROVE,
    PERM_DEVICE_CHANGE_EXECUTE,
    PERM_DEVICE_CHANGE_SUBMIT,
)
from app.auth.dependencies import CurrentUserDep, SessionDep, require_permission
from app.devices.change_requests import ChangeRequestError, ChangeRequestService

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
            reason=payload.reason,
            ip_address=request.client.host if request.client else None,
        )
    except ChangeRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ChangeRequestRead.model_validate(cr)


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
        items=[ChangeRequestRead.model_validate(cr) for cr in items],
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
    return ChangeRequestRead.model_validate(cr)


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
    return ChangeRequestRead.model_validate(cr)


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
    return ChangeRequestRead.model_validate(cr)


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
            reason=payload.reason,
            ip_address=request.client.host if request.client else None,
        )
    except ChangeRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ChangeRequestRead.model_validate(cr)
