from __future__ import annotations

import uvicorn

from app.api.router import create_app
from app.core.config import get_settings
from app.core.logging import configure_logging

app = create_app()


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    run()

