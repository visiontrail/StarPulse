from __future__ import annotations

from app.devices.constants import DeviceAccessErrorCode
from app.netconf.client import NetconfConnectionParams
from app.netconf.services import NetconfService
from app.netconf.services.errors import NetconfAuthenticationError


class FakeNetconfClient:
    def get_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        return [f"urn:test:{params.host}"]

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        return True

    def get_system_info(self, params: NetconfConnectionParams) -> dict[str, object]:
        return {"hostname": params.host}


def test_netconf_service_uses_client_abstraction() -> None:
    params = NetconfConnectionParams(host="192.0.2.20", username="netconf")
    service = NetconfService(client=FakeNetconfClient())

    assert service.validate_connection(params) is True
    assert service.list_capabilities(params) == ["urn:test:192.0.2.20"]


def test_netconf_service_discovers_capabilities_and_system_info() -> None:
    params = NetconfConnectionParams(host="192.0.2.21", username="netconf")
    service = NetconfService(client=FakeNetconfClient())

    result = service.discover_capabilities(params)

    assert result.ok is True
    assert result.capabilities == ["urn:test:192.0.2.21"]
    assert result.system_info == {"hostname": "192.0.2.21"}
    assert result.summary == {"capability_count": 1, "has_system_info": True}


def test_netconf_service_maps_standard_errors() -> None:
    class FailingClient(FakeNetconfClient):
        def validate_connection(self, params: NetconfConnectionParams) -> bool:
            raise NetconfAuthenticationError(
                "NETCONF authentication failed",
                code=DeviceAccessErrorCode.AUTH_FAILED,
                context={"password": "secret"},
            )

    params = NetconfConnectionParams(host="192.0.2.22", username="netconf")
    result = NetconfService(client=FailingClient()).test_connection(params)

    assert result.ok is False
    assert result.error_code == DeviceAccessErrorCode.AUTH_FAILED
    assert result.context == {"password": "***REDACTED***"}
