from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import devices, health, tasks
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.storage.database import init_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")

    return app
