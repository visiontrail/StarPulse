from __future__ import annotations

import os

import pytest

from app.netconf.client import NetconfConnectionParams
from app.netconf.services import NetconfService


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@pytest.mark.integration
def test_real_netconf_server_capabilities() -> None:
    host = os.getenv("STAR_PULSE_NETCONF_TEST_HOST")
    username = os.getenv("STAR_PULSE_NETCONF_TEST_USERNAME")
    password = os.getenv("STAR_PULSE_NETCONF_TEST_PASSWORD")
    if not host or not username:
        pytest.skip("set STAR_PULSE_NETCONF_TEST_HOST and STAR_PULSE_NETCONF_TEST_USERNAME")

    params = NetconfConnectionParams(
        host=host,
        port=int(os.getenv("STAR_PULSE_NETCONF_TEST_PORT", "830")),
        username=username,
        password=password,
        timeout=int(os.getenv("STAR_PULSE_NETCONF_TEST_TIMEOUT", "15")),
        hostkey_verify=_bool_env("STAR_PULSE_NETCONF_TEST_HOSTKEY_VERIFY"),
    )

    capabilities = NetconfService().list_capabilities(params)

    assert "urn:ietf:params:netconf:base:1.0" in capabilities
    assert capabilities
