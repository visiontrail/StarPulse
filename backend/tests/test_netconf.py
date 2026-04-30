from __future__ import annotations

from app.devices.constants import DeviceAccessErrorCode
from app.netconf.client import NetconfConnectionParams
from app.netconf.services import NetconfService
from app.netconf.services.config_digest import config_digest, normalize_config_content
from app.netconf.services.errors import NetconfAuthenticationError


class FakeNetconfClient:
    def get_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        return [f"urn:test:{params.host}"]

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        return True

    def get_system_info(self, params: NetconfConnectionParams) -> dict[str, object]:
        return {"hostname": params.host}

    def get_config(self, params: NetconfConnectionParams, datastore: str) -> str:
        return f"<config><host>{params.host}</host><datastore>{datastore}</datastore></config>"


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


def test_netconf_service_reads_config_and_returns_stable_summary() -> None:
    params = NetconfConnectionParams(host="192.0.2.23", username="netconf")
    result = NetconfService(client=FakeNetconfClient()).read_config(params, "running")

    assert result.ok is True
    assert result.datastore == "running"
    assert result.config_content is not None
    assert result.content_digest == config_digest(result.config_content)
    assert result.summary["content_digest"] == result.content_digest
    assert "config_content" not in result.summary


def test_netconf_service_rejects_unsupported_datastore_without_client_call() -> None:
    class TrackingClient(FakeNetconfClient):
        called = False

        def get_config(self, params: NetconfConnectionParams, datastore: str) -> str:
            self.called = True
            return super().get_config(params, datastore)

    client = TrackingClient()
    params = NetconfConnectionParams(host="192.0.2.24", username="netconf")
    result = NetconfService(client=client).read_config(params, "intended")

    assert result.ok is False
    assert result.error_code == DeviceAccessErrorCode.INVALID_PARAMETER
    assert client.called is False


def test_netconf_service_config_read_maps_standard_errors_and_redacts_context() -> None:
    class FailingClient(FakeNetconfClient):
        def get_config(self, params: NetconfConnectionParams, datastore: str) -> str:
            raise NetconfAuthenticationError(
                "NETCONF authentication failed",
                code=DeviceAccessErrorCode.AUTH_FAILED,
                context={"private_key": "key-secret", "host": params.host},
            )

    params = NetconfConnectionParams(host="192.0.2.25", username="netconf")
    result = NetconfService(client=FailingClient()).read_config(params, "running")

    assert result.ok is False
    assert result.error_code == DeviceAccessErrorCode.AUTH_FAILED
    assert result.context["private_key"] == "***REDACTED***"


def test_config_digest_normalizes_equivalent_xml() -> None:
    first = "<config><interface name=\"xe0\"> up </interface></config>"
    second = """
    <config>
      <interface name="xe0">up</interface>
    </config>
    """

    assert normalize_config_content(first) == normalize_config_content(second)
    assert config_digest(first) == config_digest(second)


def test_netconf_service_does_not_use_write_operations() -> None:
    class ReadOnlyBoundaryClient(FakeNetconfClient):
        def edit_config(self, *args, **kwargs):
            raise AssertionError("write operation must not be called")

        def commit(self, *args, **kwargs):
            raise AssertionError("write operation must not be called")

        def discard_changes(self, *args, **kwargs):
            raise AssertionError("write operation must not be called")

        def copy_config(self, *args, **kwargs):
            raise AssertionError("write operation must not be called")

    params = NetconfConnectionParams(host="192.0.2.26", username="netconf")
    result = NetconfService(client=ReadOnlyBoundaryClient()).read_config(params, "running")

    assert result.ok is True
