from __future__ import annotations

from app.devices.constants import DeviceAccessErrorCode


class NetconfError(RuntimeError):
    """Standard NETCONF error exposed to upper layers."""

    def __init__(
        self,
        message: str,
        *,
        code: DeviceAccessErrorCode = DeviceAccessErrorCode.INTERNAL_ERROR,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.context = context or {}


class NetconfConnectionError(NetconfError):
    """Raised when the NETCONF session cannot be established."""


class NetconfAuthenticationError(NetconfConnectionError):
    """Raised when the NETCONF endpoint rejects credentials."""


class NetconfTimeoutError(NetconfConnectionError):
    """Raised when the NETCONF operation times out."""


class NetconfProtocolError(NetconfError):
    """Raised when NETCONF protocol negotiation or RPC handling fails."""
