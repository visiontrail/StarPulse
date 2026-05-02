from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, audit, auth, change_requests, devices, health, tasks
from app.auth.seed import seed_permissions_and_roles
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.storage.database import SessionLocal, init_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_database()
    with SessionLocal() as session:
        seed_permissions_and_roles(session)
        _bootstrap_admin(session)
    yield


def _bootstrap_admin(session: object) -> None:
    settings = get_settings()
    if settings.bootstrap_admin_username and settings.bootstrap_admin_password:
        from app.auth.bootstrap import bootstrap_admin

        bootstrap_admin(
            session,  # type: ignore[arg-type]
            username=settings.bootstrap_admin_username,
            password=settings.bootstrap_admin_password,
        )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(change_requests.router, prefix="/api/v1")

    return app
