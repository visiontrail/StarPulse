from __future__ import annotations

from app.netconf.adapters import NcclientNetconfClient
from app.netconf.client import NetconfClient, NetconfConnectionParams


class NetconfService:
    def __init__(self, client: NetconfClient | None = None) -> None:
        self.client = client or NcclientNetconfClient()

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        return self.client.validate_connection(params)

    def list_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        return self.client.get_capabilities(params)

