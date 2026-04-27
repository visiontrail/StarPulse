from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas.health import HealthResponse
from app.storage.database import get_session

router = APIRouter(tags=["health"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/health", response_model=HealthResponse)
def health(session: SessionDep) -> HealthResponse:
    database_status = "ok"
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"
    return HealthResponse(status="ok", dependencies={"database": database_status})
