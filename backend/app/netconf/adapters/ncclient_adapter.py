from __future__ import annotations

from app.netconf.client import NetconfConnectionParams
from app.netconf.services.errors import NetconfConnectionError


class NcclientNetconfClient:
    def get_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        try:
            from ncclient import manager

            with manager.connect(
                host=params.host,
                port=params.port,
                username=params.username,
                password=params.password,
                timeout=params.timeout,
                hostkey_verify=params.hostkey_verify,
            ) as session:
                return sorted(str(capability) for capability in session.server_capabilities)
        except Exception as exc:
            raise NetconfConnectionError("NETCONF capability query failed") from exc

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        self.get_capabilities(params)
        return True

