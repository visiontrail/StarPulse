from __future__ import annotations


class NetconfError(RuntimeError):
    """Standard NETCONF error exposed to upper layers."""


class NetconfConnectionError(NetconfError):
    """Raised when the NETCONF session cannot be established."""

