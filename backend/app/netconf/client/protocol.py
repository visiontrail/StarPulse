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
