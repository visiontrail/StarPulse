from __future__ import annotations

import socket

from app.devices.constants import DeviceAccessErrorCode
from app.netconf.client import NetconfConnectionParams
from app.netconf.services.errors import (
    NetconfAuthenticationError,
    NetconfConnectionError,
    NetconfError,
    NetconfProtocolError,
    NetconfTimeoutError,
)


class NcclientNetconfClient:
    def get_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        try:
            with self._connect(params) as session:
                return sorted(str(capability) for capability in session.server_capabilities)
        except NetconfError:
            raise
        except Exception as exc:
            raise _map_exception(exc, params) from exc

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        self.get_capabilities(params)
        return True

    def get_system_info(self, params: NetconfConnectionParams) -> dict[str, object]:
        try:
            with self._connect(params) as session:
                system_state_filter = (
                    "<system-state xmlns=\"urn:ietf:params:xml:ns:yang:ietf-system\"/>"
                )
                result = session.get(filter=("subtree", system_state_filter))
                return {"raw": _reply_xml(result)}
        except NetconfProtocolError:
            return {}
        except NetconfError:
            raise
        except Exception as exc:
            mapped = _map_exception(exc, params)
            if isinstance(mapped, NetconfProtocolError):
                return {}
            raise mapped from exc

    def get_config(self, params: NetconfConnectionParams, datastore: str) -> str:
        try:
            with self._connect(params) as session:
                result = session.get_config(source=datastore)
                return _reply_xml(result, prefer_data=True)
        except NetconfError:
            raise
        except Exception as exc:
            raise _map_exception(exc, params) from exc

    def edit_config(
        self, params: NetconfConnectionParams, datastore: str, config_body: str
    ) -> None:
        try:
            with self._connect(params) as session:
                session.edit_config(target=datastore, config=config_body)
        except NetconfError:
            raise
        except Exception as exc:
            raise _map_exception(exc, params) from exc

    def _connect(self, params: NetconfConnectionParams):
        try:
            from ncclient import manager

            return manager.connect(
                host=params.host,
                port=params.port,
                username=params.username,
                password=params.password,
                key_filename=None,
                timeout=params.timeout,
                hostkey_verify=params.hostkey_verify,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as exc:
            raise _map_exception(exc, params) from exc


def _reply_xml(reply: object, *, prefer_data: bool = False) -> str:
    attrs = ("data_xml", "xml") if prefer_data else ("xml", "data_xml")
    for attr in attrs:
        try:
            value = getattr(reply, attr, None)
        except Exception:
            value = None
        if value:
            return _xml_value_to_string(value)
    return str(reply)


def _xml_value_to_string(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _map_exception(exc: Exception, params: NetconfConnectionParams) -> Exception:
    name = exc.__class__.__name__.lower()
    module = exc.__class__.__module__.lower()
    context = {
        "host": params.host,
        "port": params.port,
        "protocol": "netconf",
        "exception_type": exc.__class__.__name__,
    }
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout) or "timeout" in name:
        return NetconfTimeoutError(
            "NETCONF operation timed out",
            code=DeviceAccessErrorCode.CONNECTION_TIMEOUT,
            context=context,
        )
    if "auth" in name or "auth" in module or "authentication" in str(exc).lower():
        return NetconfAuthenticationError(
            "NETCONF authentication failed",
            code=DeviceAccessErrorCode.AUTH_FAILED,
            context=context,
        )
    if any(marker in name for marker in ("rpc", "hello", "capabil", "protocol")):
        return NetconfProtocolError(
            "NETCONF protocol error",
            code=DeviceAccessErrorCode.NETCONF_PROTOCOL_ERROR,
            context=context,
        )
    return NetconfConnectionError(
        "NETCONF device is unreachable",
        code=DeviceAccessErrorCode.DEVICE_UNREACHABLE,
        context=context,
    )
