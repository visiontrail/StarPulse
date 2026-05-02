from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.schemas.config_snapshot import (
    ConfigSnapshotCollectRequest,
    ConfigSnapshotListResponse,
    ConfigSnapshotSummaryRead,
)
from app.api.schemas.device import DeviceCreate, DeviceProfileRead, DeviceRead
from app.api.schemas.task import TaskRead
from app.auth.audit import write_audit_event
from app.auth.constants import (
    PERM_DEVICE_COLLECT,
    PERM_DEVICE_MANAGE,
    PERM_DEVICE_READ,
    PERM_SNAPSHOT_READ,
    PERM_TASK_READ,
    AuditAction,
    AuditOutcome,
)
from app.auth.dependencies import CurrentUserDep, SessionDep, require_permission
from app.devices.constants import SUPPORTED_CONFIG_DATASTORES
from app.devices.repository import DeviceRepository
from app.devices.service import (
    DeviceConnectionConfigMissingError,
    DeviceCredentialUnavailableError,
    DeviceService,
)
from app.tasks.service import TaskService

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post(
    "",
    response_model=DeviceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(PERM_DEVICE_MANAGE)],
)
def create_device(payload: DeviceCreate, session: SessionDep) -> DeviceRead:
    device = DeviceService(session).create_device(payload)
    return DeviceRead.model_validate(device)


@router.get(
    "",
    response_model=list[DeviceRead],
    dependencies=[require_permission(PERM_DEVICE_READ)],
)
def list_devices(session: SessionDep) -> list[DeviceRead]:
    devices = DeviceService(session).list_devices()
    repository = DeviceRepository(session)
    return [_device_read(device.id, session, repository=repository) for device in devices]


@router.get(
    "/{device_id}",
    response_model=DeviceRead,
    dependencies=[require_permission(PERM_DEVICE_READ)],
)
def get_device(device_id: int, session: SessionDep) -> DeviceRead:
    return _device_read(device_id, session)


@router.get(
    "/{device_id}/profile",
    response_model=DeviceProfileRead,
    dependencies=[require_permission(PERM_DEVICE_READ)],
)
def get_device_profile(device_id: int, session: SessionDep) -> DeviceProfileRead:
    device = _device_read(device_id, session)
    capabilities = device.last_discovery.capabilities if device.last_discovery else []
    system_info = device.last_discovery.system_info if device.last_discovery else {}
    return DeviceProfileRead.model_validate(
        device.model_dump()
        | {
            "capabilities": capabilities,
            "system_info": system_info,
            "safety_summary": {
                "read_only": True,
                "exposes_full_config": False,
                "exposes_credentials": False,
            },
        }
    )


@router.post(
    "/{device_id}/connection-test",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission(PERM_DEVICE_COLLECT)],
)
def submit_connection_test(device_id: int, session: SessionDep) -> TaskRead:
    _ensure_ready(device_id, session)
    task_status = TaskService(session).submit_connection_test(device_id)
    return TaskRead.model_validate(task_status)


@router.post(
    "/{device_id}/capability-discovery",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission(PERM_DEVICE_COLLECT)],
)
def submit_capability_discovery(device_id: int, session: SessionDep) -> TaskRead:
    _ensure_ready(device_id, session)
    task_status = TaskService(session).submit_capability_discovery(device_id)
    return TaskRead.model_validate(task_status)


@router.post(
    "/{device_id}/config-snapshots",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission(PERM_DEVICE_COLLECT)],
)
def submit_config_snapshot(
    device_id: int,
    payload: ConfigSnapshotCollectRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> TaskRead:
    if payload.datastore not in SUPPORTED_CONFIG_DATASTORES:
        _audit_collect_failure(
            session=session,
            actor_id=actor.id,
            device_id=device_id,
            datastore=payload.datastore,
            reason="unsupported_datastore",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported datastore",
        )
    try:
        _ensure_ready(device_id, session)
    except HTTPException as exc:
        _audit_collect_failure(
            session=session,
            actor_id=actor.id,
            device_id=device_id,
            datastore=payload.datastore,
            reason=str(exc.detail),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise
    task_status = TaskService(session).submit_config_snapshot(
        device_id, payload.datastore, actor_user_id=actor.id
    )
    return TaskRead.model_validate(task_status)


@router.get(
    "/{device_id}/config-snapshots",
    response_model=ConfigSnapshotListResponse,
    dependencies=[require_permission(PERM_SNAPSHOT_READ)],
)
def list_config_snapshots(
    device_id: int,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConfigSnapshotListResponse:
    _ensure_device_exists(device_id, session)
    snapshots = DeviceRepository(session).list_config_snapshots(
        device_id=device_id, limit=limit, offset=offset
    )
    return ConfigSnapshotListResponse(
        items=[ConfigSnapshotSummaryRead.model_validate(snapshot) for snapshot in snapshots],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{device_id}/tasks",
    response_model=list[TaskRead],
    dependencies=[require_permission(PERM_TASK_READ)],
)
def list_device_tasks(
    device_id: int,
    session: SessionDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[TaskRead]:
    _ensure_device_exists(device_id, session)
    tasks = DeviceRepository(session).list_recent_tasks(device_id=device_id, limit=limit)
    return [TaskRead.model_validate(task) for task in tasks]


def _ensure_ready(device_id: int, session: Session) -> None:
    try:
        DeviceService(session).ensure_ready_for_device_task(device_id)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        ) from None
    except DeviceConnectionConfigMissingError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device connection config is missing",
        ) from None
    except DeviceCredentialUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device credential is unavailable",
        ) from None


def _ensure_supported_datastore(datastore: str) -> None:
    if datastore not in SUPPORTED_CONFIG_DATASTORES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported datastore",
        )


def _audit_collect_failure(
    *,
    session: Session,
    actor_id: int,
    device_id: int,
    datastore: str,
    reason: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    write_audit_event(
        session=session,
        action=AuditAction.VALIDATION_FAILED,
        outcome=AuditOutcome.FAILURE,
        actor_user_id=actor_id,
        target_type="device",
        target_id=str(device_id),
        permission=PERM_DEVICE_COLLECT,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"operation": "config_snapshot_collect", "datastore": datastore, "reason": reason},
    )
    session.commit()


def _ensure_device_exists(device_id: int, session: Session) -> None:
    if DeviceService(session).get_device(device_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")


def _device_read(
    device_id: int, session: Session, *, repository: DeviceRepository | None = None
) -> DeviceRead:
    repository = repository or DeviceRepository(session)
    device = DeviceService(session).get_device(device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    last_snapshot = repository.get_last_config_snapshot(device_id=device_id)
    recent_tasks = repository.list_recent_tasks(device_id=device_id, limit=5)
    return DeviceRead.model_validate(device).model_copy(
        update={
            "last_config_snapshot": (
                ConfigSnapshotSummaryRead.model_validate(last_snapshot)
                if last_snapshot is not None
                else None
            ),
            "recent_tasks": [
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": task.status,
                    "actor_user_id": task.actor_user_id,
                    "actor": (
                        {
                            "id": task.actor.id,
                            "username": task.actor.username,
                            "display_name": task.actor.display_name,
                        }
                        if task.actor is not None
                        else None
                    ),
                    "error_code": task.error_code,
                    "error_message": task.error_message,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                }
                for task in recent_tasks
            ],
        }
    )
