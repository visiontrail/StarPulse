from __future__ import annotations

from dataclasses import dataclass, field

from app.common.redaction import redact_sensitive
from app.devices.constants import DeviceAccessErrorCode
from app.netconf.adapters import NcclientNetconfClient
from app.netconf.client import NetconfClient, NetconfConnectionParams
from app.netconf.services.errors import NetconfError


@dataclass(frozen=True)
class NetconfOperationResult:
    ok: bool
    summary: dict[str, object] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    system_info: dict[str, object] = field(default_factory=dict)
    error_code: DeviceAccessErrorCode | None = None
    error_message: str | None = None
    context: dict[str, object] = field(default_factory=dict)


class NetconfService:
    def __init__(self, client: NetconfClient | None = None) -> None:
        self.client = client or NcclientNetconfClient()

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        return self.client.validate_connection(params)

    def list_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        return self.client.get_capabilities(params)

    def test_connection(self, params: NetconfConnectionParams) -> NetconfOperationResult:
        try:
            self.client.validate_connection(params)
        except NetconfError as exc:
            return _error_result(exc)
        return NetconfOperationResult(ok=True, summary={"connected": True})

    def discover_capabilities(self, params: NetconfConnectionParams) -> NetconfOperationResult:
        try:
            capabilities = self.client.get_capabilities(params)
            system_info = self.client.get_system_info(params)
        except NetconfError as exc:
            return _error_result(exc)
        summary = {
            "capability_count": len(capabilities),
            "has_system_info": bool(system_info),
        }
        return NetconfOperationResult(
            ok=True,
            summary=summary,
            capabilities=capabilities,
            system_info=system_info,
        )


def _error_result(exc: NetconfError) -> NetconfOperationResult:
    return NetconfOperationResult(
        ok=False,
        error_code=exc.code,
        error_message=exc.safe_message,
        context=redact_sensitive(exc.context),
    )
