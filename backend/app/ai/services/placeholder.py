from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class AiCapabilitySummary:
    provider: str
    enabled: bool
    phase: str
    supported_actions: tuple[str, ...]


class AiCapabilityService:
    def summary(self) -> AiCapabilitySummary:
        settings = get_settings()
        return AiCapabilitySummary(
            provider=settings.ai_agent_sdk_provider,
            enabled=settings.ai_agent_sdk_enabled,
            phase="foundation-placeholder",
            supported_actions=(),
        )

