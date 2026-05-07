from __future__ import annotations

from app.devices.constants import DeviceAccessErrorCode
from app.netconf.adapters.ncclient_adapter import _reply_xml
from app.netconf.client import NetconfConnectionParams
from app.netconf.services import NetconfService
from app.netconf.services.config_digest import config_digest, normalize_config_content
from app.netconf.services.errors import NetconfAuthenticationError
from app.netconf.services.service import parse_yang_nodes


class FakeNetconfClient:
    def get_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        return [f"urn:test:{params.host}"]

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        return True

    def get_system_info(self, params: NetconfConnectionParams) -> dict[str, object]:
        return {"hostname": params.host}

    def get_config(self, params: NetconfConnectionParams, datastore: str) -> str:
        return (
            f'<config xmlns="config"><host>{params.host}</host>'
            f"<datastore>{datastore}</datastore></config>"
        )

    def get_schema(
        self,
        params: NetconfConnectionParams,
        identifier: str,
        version: str | None = None,
        format: str | None = None,
    ) -> str:
        return """
        module config {
          namespace "config";
          prefix cfg;
          container config {
            leaf host { type string; }
            leaf datastore {
              type enumeration {
                enum running;
                enum startup;
              }
            }
          }
        }
        """


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


def test_netconf_service_enriches_config_reads_with_yang_nodes() -> None:
    params = NetconfConnectionParams(host="192.0.2.23", username="netconf")
    result = NetconfService(client=FakeNetconfClient()).read_config(params, "running")

    assert result.ok is True
    models = result.summary["yang_models"]
    assert isinstance(models, list)
    nodes = models[0]["nodes"]
    assert isinstance(nodes, list)
    datastore = next(node for node in nodes if node["name"] == "datastore")
    assert datastore["type"] == "enumeration"
    assert datastore["enum_values"] == [{"name": "running"}, {"name": "startup"}]


def test_netconf_service_loads_imported_yang_models_for_grouping_nodes() -> None:
    class ImportingClient(FakeNetconfClient):
        def get_schema(
            self,
            params: NetconfConnectionParams,
            identifier: str,
            version: str | None = None,
            format: str | None = None,
        ) -> str:
            if identifier == "config":
                return """
                module config {
                  namespace "config";
                  prefix cfg;
                  import tcp-helper { prefix tcph; revision-date 2026-01-01; }
                  container config {
                    container tcp-server-parameters {
                      uses tcph:tcp-server-grouping;
                    }
                  }
                }
                """
            if identifier == "tcp-helper":
                return """
                module tcp-helper {
                  namespace "tcp-helper";
                  prefix tcph;
                  revision 2026-01-01;
                  grouping tcp-server-grouping {
                    container local-bind {
                      leaf local-address { type ip-address; }
                    }
                  }
                }
                """
            raise AssertionError(f"unexpected schema request: {identifier}")

    params = NetconfConnectionParams(host="192.0.2.23", username="netconf")
    result = NetconfService(client=ImportingClient()).read_config(params, "running")

    assert result.ok is True
    models = result.summary["yang_models"]
    assert [model["module"] for model in models] == ["config", "tcp-helper"]
    imported_nodes = models[1]["nodes"]
    assert any(node["name"] == "local-address" for node in imported_nodes)


def test_parse_yang_nodes_extracts_leaf_types_and_constraints() -> None:
    parsed = parse_yang_nodes(
        """
        module mock-router {
          namespace "urn:mock:router";
          prefix mr;
          container device-info {
            leaf vendor {
              type enumeration {
                enum MockVendor { value 1; }
                enum OtherVendor;
              }
              default MockVendor;
              mandatory true;
            }
            leaf enabled {
              type boolean;
            }
            leaf metric {
              type uint16 {
                range "1..65535";
              }
            }
          }
        }
        """
    )

    assert parsed is not None
    nodes = parsed["nodes"]
    assert isinstance(nodes, list)
    vendor = next(node for node in nodes if node["name"] == "vendor")
    assert vendor["namespace"] == "urn:mock:router"
    assert vendor["type"] == "enumeration"
    assert vendor["mandatory"] is True
    assert vendor["default"] == "MockVendor"
    assert vendor["enum_values"][0] == {"name": "MockVendor", "value": "1"}
    metric = next(node for node in nodes if node["name"] == "metric")
    assert metric["type"] == "uint16"
    assert metric["range"] == "1..65535"


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


def test_ncclient_reply_prefers_parseable_data_xml_for_get_config() -> None:
    class Reply:
        data_xml = "<data><interfaces/></data>"
        xml = "<rpc-reply><data><interfaces/></data></rpc-reply>"

        def __str__(self) -> str:
            return "<{urn:ietf:params:xml:ns:netconf:base:1.0}rpc-reply/>"

    assert _reply_xml(Reply(), prefer_data=True) == "<data><interfaces/></data>"


def test_config_digest_normalizes_equivalent_xml() -> None:
    first = "<config><interface name=\"xe0\"> up </interface></config>"
    second = """
    <config>
      <interface name="xe0">up</interface>
    </config>
    """

    assert normalize_config_content(first) == normalize_config_content(second)
    assert config_digest(first) == config_digest(second)


def test_config_digest_repairs_ncclient_clark_notation_reply() -> None:
    pseudo_xml = (
        '<{urn:ietf:params:xml:ns:netconf:base:1.0}rpc-reply message-id="1">'
        "<{urn:ietf:params:xml:ns:netconf:base:1.0}data>"
        "<{urn:ietf:params:xml:ns:yang:ietf-interfaces}interfaces>"
        "<{urn:ietf:params:xml:ns:yang:ietf-interfaces}interface>"
        "<{urn:ietf:params:xml:ns:yang:ietf-interfaces}name>eth0"
        "</{urn:ietf:params:xml:ns:yang:ietf-interfaces}name>"
        "</{urn:ietf:params:xml:ns:yang:ietf-interfaces}interface>"
        "</{urn:ietf:params:xml:ns:yang:ietf-interfaces}interfaces>"
        "</{urn:ietf:params:xml:ns:netconf:base:1.0}data>"
        "</{urn:ietf:params:xml:ns:netconf:base:1.0}rpc-reply>"
    )

    normalized = normalize_config_content(pseudo_xml)

    assert "eth0" in normalized
    assert "<{" not in normalized


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
