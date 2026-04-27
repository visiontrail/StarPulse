from __future__ import annotations

from app.netconf.client import NetconfConnectionParams
from app.netconf.services import NetconfService


class FakeNetconfClient:
    def get_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        return [f"urn:test:{params.host}"]

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        return True


def test_netconf_service_uses_client_abstraction() -> None:
    params = NetconfConnectionParams(host="192.0.2.20", username="netconf")
    service = NetconfService(client=FakeNetconfClient())

    assert service.validate_connection(params) is True
    assert service.list_capabilities(params) == ["urn:test:192.0.2.20"]

