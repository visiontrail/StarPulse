from __future__ import annotations

from enum import StrEnum


class DeviceStatus(StrEnum):
    PLANNED = "planned"
    READY = "ready"
    TESTING = "testing"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class DeviceTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DeviceTaskType(StrEnum):
    CONNECTION_TEST = "device.connection_test"
    CAPABILITY_DISCOVERY = "device.capability_discovery"
    CONFIG_SNAPSHOT = "device.config_snapshot"


class DeviceConfigDatastore(StrEnum):
    RUNNING = "running"
    CANDIDATE = "candidate"
    STARTUP = "startup"


SUPPORTED_CONFIG_DATASTORES = tuple(datastore.value for datastore in DeviceConfigDatastore)


class DeviceAccessErrorCode(StrEnum):
    INVALID_PARAMETER = "INVALID_PARAMETER"
    DEVICE_UNREACHABLE = "DEVICE_UNREACHABLE"
    CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
    AUTH_FAILED = "AUTH_FAILED"
    NETCONF_PROTOCOL_ERROR = "NETCONF_PROTOCOL_ERROR"
    CREDENTIAL_UNAVAILABLE = "CREDENTIAL_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
