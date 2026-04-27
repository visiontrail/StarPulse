from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STAR_PULSE_", env_file=".env", extra="ignore")

    app_name: str = "Star-Pulse Ground Management"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    reload: bool = False
    log_level: str = "INFO"

    database_url: str = Field(default="sqlite:///./star_pulse.db")
    postgres_database_url: str = (
        "postgresql+psycopg://star_pulse:star_pulse@postgres:5432/star_pulse"
    )
    sqlite_database_url: str = "sqlite:///./star_pulse.db"

    rabbitmq_url: str = "amqp://star_pulse:star_pulse@rabbitmq:5672//"
    celery_result_backend: str | None = None
    celery_task_always_eager: bool = False

    ai_agent_sdk_provider: str = "claude-agent-sdk"
    ai_agent_sdk_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

