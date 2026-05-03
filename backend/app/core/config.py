from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_SECRET"


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

    netconf_default_timeout: int = 30
    netconf_hostkey_verify: bool = False
    baseline_snapshot_freshness_minutes: int = 60

    ai_agent_sdk_provider: str = "claude-agent-sdk"
    ai_agent_sdk_enabled: bool = False

    # Auth / JWT
    jwt_secret_key: str = _INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    # Cookie / CORS
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cors_allowed_origins: list[str] = Field(default=["http://localhost:3000"])

    # Audit
    audit_retention_days: int = 90

    # Bootstrap admin (local dev only; cleared after first use)
    bootstrap_admin_username: str = ""
    bootstrap_admin_password: str = ""

    @field_validator("jwt_secret_key")
    @classmethod
    def _validate_secret(cls, v: str, info: object) -> str:
        import sys

        values = getattr(info, "data", {})
        env = values.get("environment", "development")
        if env == "production" and v == _INSECURE_DEFAULT_SECRET:
            print(  # noqa: T201
                "FATAL: STAR_PULSE_JWT_SECRET_KEY must be set to a secure value in production.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
