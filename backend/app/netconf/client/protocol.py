from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NetconfConnectionParams:
    host: str
    port: int = 830
    username: str = ""
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None
    timeout: int = 30
    hostkey_verify: bool = False


class NetconfClient(Protocol):
    def get_capabilities(self, params: NetconfConnectionParams) -> list[str]:
        raise NotImplementedError

    def validate_connection(self, params: NetconfConnectionParams) -> bool:
        raise NotImplementedError

    def get_system_info(self, params: NetconfConnectionParams) -> dict[str, object]:
        raise NotImplementedError

    def get_config(self, params: NetconfConnectionParams, datastore: str) -> str:
        raise NotImplementedError

    def get_schema(
        self,
        params: NetconfConnectionParams,
        identifier: str,
        version: str | None = None,
        format: str | None = None,
    ) -> str:
        raise NotImplementedError

    def edit_config(
        self, params: NetconfConnectionParams, datastore: str, config_body: str
    ) -> None:
        raise NotImplementedError
