from __future__ import annotations

import os

import pytest

from app.netconf.client import NetconfConnectionParams
from app.netconf.services import NetconfService
from app.netconf.services.errors import NetconfError


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@pytest.mark.integration
def test_real_netconf_server_capabilities() -> None:
    if not _bool_env("STAR_PULSE_NETCONF_INTEGRATION_ENABLED"):
        pytest.skip("set STAR_PULSE_NETCONF_INTEGRATION_ENABLED=true to run remote NETCONF tests")

    host = os.getenv("STAR_PULSE_NETCONF_TEST_HOST", "172.16.5.38")
    username = os.getenv("STAR_PULSE_NETCONF_TEST_USERNAME", "netconf")
    password = os.getenv("STAR_PULSE_NETCONF_TEST_PASSWORD", "netconf")

    params = NetconfConnectionParams(
        host=host,
        port=int(os.getenv("STAR_PULSE_NETCONF_TEST_PORT", "830")),
        username=username,
        password=password,
        timeout=int(os.getenv("STAR_PULSE_NETCONF_TEST_TIMEOUT", "15")),
        hostkey_verify=_bool_env("STAR_PULSE_NETCONF_TEST_HOSTKEY_VERIFY"),
    )

    try:
        capabilities = NetconfService().list_capabilities(params)
    except NetconfError as exc:
        pytest.skip(f"remote NETCONF mock server unavailable: {exc.safe_message}")

    assert "urn:ietf:params:netconf:base:1.0" in capabilities
    assert capabilities
