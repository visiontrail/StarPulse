# Star-Pulse Backend

Star-Pulse backend is a Python modular monolith for the first phase of the satellite router ground management platform. It provides API, configuration, storage, device management, NETCONF, asynchronous tasks, and AI extension boundaries while staying open source and self-hostable.

## Service Parts

- HTTP API: FastAPI application in `app/api`
- Storage: SQLAlchemy models, repositories, and Alembic migrations in `app/storage`
- Devices: device schemas, repository, and service in `app/devices`
- NETCONF: `ncclient` adapter boundary in `app/netconf`
- Tasks: Celery application and sample task in `app/tasks`
- AI Native: placeholder extension modules in `app/ai`

## Local Development

All helper scripts live in `backend/scripts/` and use a project virtual environment at `backend/.venv/`.
The scripts prefer Python 3.14, 3.13, 3.12, or 3.11 when available; set `PYTHON_BIN` to override the interpreter.

```bash
cd backend
./scripts/init_dev.sh
./scripts/run_api.sh
```

The bare local default database is SQLite at `backend/star_pulse.db`. Docker Compose overrides this to PostgreSQL and RabbitMQ.

Important environment variables:

- `STAR_PULSE_DATABASE_URL`
- `STAR_PULSE_RABBITMQ_URL`
- `STAR_PULSE_API_HOST`
- `STAR_PULSE_API_PORT`
- `STAR_PULSE_LOG_LEVEL`
- `STAR_PULSE_CELERY_TASK_ALWAYS_EAGER`
- `STAR_PULSE_NETCONF_DEFAULT_TIMEOUT`
- `STAR_PULSE_NETCONF_HOSTKEY_VERIFY`

## Device Access Workflow

Device onboarding stores connection details separately from runtime credentials. API callers may submit
a password when creating a device, but read responses only expose the connection summary and credential
reference state.

```bash
curl -X POST http://localhost:8000/api/v1/devices \
  -H 'content-type: application/json' \
  -d '{
    "name": "sat-router-001",
    "connection": {
      "host": "192.0.2.10",
      "port": 830,
      "username": "netconf",
      "password": "netconf"
    }
  }'
```

Run a NETCONF connection test:

```bash
curl -X POST http://localhost:8000/api/v1/devices/1/connection-test
```

Run NETCONF capability discovery:

```bash
curl -X POST http://localhost:8000/api/v1/devices/1/capability-discovery
```

Both commands return a task identifier. Query task status with:

```bash
curl http://localhost:8000/api/v1/tasks/<task_id>
```

Task responses include `queued`, `running`, `succeeded`, or `failed`, the related `device_id`, safe
result summaries, standard error codes, safe messages, and redacted diagnostic context. Supported
standard error codes are `DEVICE_UNREACHABLE`, `CONNECTION_TIMEOUT`, `AUTH_FAILED`,
`NETCONF_PROTOCOL_ERROR`, `CREDENTIAL_UNAVAILABLE`, and `INTERNAL_ERROR`.

API and worker logs include structured fields for `action`, `task_id`, `device_id`, `status`,
`duration_ms`, and, when applicable, `error_code`. Passwords, private keys, passphrases, and resolved
credential values must not be included in task metadata, API responses, discovery results, or logs.

## NETCONF Mock Server Integration Tests

Remote NETCONF integration tests are opt-in so normal local and CI runs are stable. Enable them with:

```bash
STAR_PULSE_NETCONF_INTEGRATION_ENABLED=true ./scripts/test.sh
```

Defaults target the shared mock server:

- `STAR_PULSE_NETCONF_TEST_HOST=172.16.5.38`
- `STAR_PULSE_NETCONF_TEST_PORT=830`
- `STAR_PULSE_NETCONF_TEST_USERNAME=netconf`
- `STAR_PULSE_NETCONF_TEST_PASSWORD=netconf`
- `STAR_PULSE_NETCONF_TEST_TIMEOUT=15`
- `STAR_PULSE_NETCONF_TEST_HOSTKEY_VERIFY=false`

If the integration flag is disabled, the test is skipped. If the flag is enabled but the remote mock
server is unavailable, the integration test skips after reporting the safe NETCONF error message.

## Docker Compose

```bash
cd backend
./scripts/start_all.sh
```

This starts the API service, PostgreSQL, RabbitMQ, and a Celery worker through the repository-level `docker-compose.yml`.

## Quality

```bash
cd backend
./scripts/test.sh
./scripts/lint.sh
```

## Phase One Boundary

This phase establishes the platform foundation only. It does not implement full satellite-router business workflows, YANG model parsing, complex NETCONF configuration templates, production Kubernetes manifests, RBAC, approval workflows, or autonomous AI Agent behavior.
