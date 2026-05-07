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
- `STAR_PULSE_NETCONF_LOOPBACK_HOST_OVERRIDE` — optional NETCONF target host rewrite for local
  Docker workflows. In `docker-compose.yml` this is set to `host.docker.internal`, so devices
  configured as `127.0.0.1`, `::1`, or `localhost` reach a MockServer running on the host instead
  of the worker container itself.
- `STAR_PULSE_BASELINE_SNAPSHOT_FRESHNESS_MINUTES`
- `NEXT_PUBLIC_API_BASE_URL` for the frontend, defaulting to `http://localhost:8000/api/v1`

### Authentication Configuration

- `STAR_PULSE_JWT_SECRET_KEY` — Required in production. Long random string. Startup fails if this is the insecure default in production environment.
- `STAR_PULSE_JWT_ALGORITHM` — JWT signing algorithm (default: `HS256`)
- `STAR_PULSE_ACCESS_TOKEN_TTL_MINUTES` — Access token lifetime in minutes (default: `15`)
- `STAR_PULSE_REFRESH_TOKEN_TTL_DAYS` — Refresh token lifetime in days (default: `7`)
- `STAR_PULSE_COOKIE_SECURE` — Set `true` in production to require HTTPS for refresh cookie (default: `false`)
- `STAR_PULSE_CORS_ALLOWED_ORIGINS` — JSON list of allowed CORS origins (default: `["http://localhost:3000"]`)
- `STAR_PULSE_AUDIT_RETENTION_DAYS` — Soft retention hint for audit logs (default: `90`)
- `STAR_PULSE_BASELINE_SNAPSHOT_FRESHNESS_MINUTES` — Maximum age for a baseline snapshot to pass change preflight checks (default: `60`)

### Initial Admin Bootstrap (Local Development)

Set the following environment variables before first startup to create an initial admin user automatically:

```bash
STAR_PULSE_BOOTSTRAP_ADMIN_USERNAME=admin
STAR_PULSE_BOOTSTRAP_ADMIN_PASSWORD=ChangeMeNow!
```

The bootstrap runs idempotently — if the username already exists, it skips creation. Clear or unset these variables after the admin user is created in production.

### Role Matrix

| Role | Permissions |
|------|-------------|
| `viewer` | `device:read`, `task:read`, `snapshot:read`, `audit:read:summary` |
| `operator` | viewer + `device:collect`, `device:change:submit` |
| `approver` | operator + `device:change:approve`, `device:change:execute` |
| `admin` | all permissions including `user:manage`, `role:manage`, `system:config`, `audit:read:full` |

Roles and permissions are seeded idempotently at startup. Existing custom role-permission relationships are preserved.

### Approver Direct Execution

Approvers can bypass the normal submit→approve flow using the direct-execute endpoint (`POST /api/v1/change-requests/direct-execute`). Direct execution:
- Requires a non-empty `reason` field (request is rejected without one)
- Runs server-side change preflight before creating the execution task
- Creates a change request record with `direct_execute: true`
- Records a `change.direct_executed` audit event with the reason, device, datastore, baseline snapshot, preflight context, and actor
- Immediately enqueues a Celery execution task

All required audit fields: `actor_user_id`, `action`, `target_type`, `target_id`, `outcome`, `permission`, `direct_execute_reason`, `device_id`, `datastore`.

### Change Safety Loop

Normal configuration changes are contextual to a known device and datastore. Before submit, approval execution, or direct execution, the backend validates:

- device connection config and credential reference
- successful connection test and capability discovery
- supported datastore
- non-empty config payload and reason
- latest successful baseline snapshot freshness (`STAR_PULSE_BASELINE_SNAPSHOT_FRESHNESS_MINUTES`)

Preflight responses and stored change records include safe summaries only: baseline snapshot IDs/digests, payload digest/length/line count, blocker codes, risk level, and bounded comparison fields. Full config bodies and credentials are not exposed in list/detail responses, audit metadata, task metadata, or logs.

After a controlled NETCONF write succeeds, the worker marks the change as `verifying`, performs a read-only `get-config` for the same datastore, saves a post-change snapshot, compares safe digests with the baseline, and records `executed` or `verification_failed`. Write failures are marked `failed` and do not run post-change verification.

### Controlled Rollback Loop

When a non-rollback configuration change ends in `verification_failed`, the worker automatically creates a `pending_approval` rollback proposal (`is_rollback=true`, `rollback_of_change_id=<origin>`, `rollback_target_snapshot_id=<origin.baseline_snapshot_id>`). The proposal is never executed automatically — an approver or admin must approve or direct-execute it.

Rollback lifecycle:
1. **Auto-proposal** (worker): on verification failure, if the baseline snapshot has `normalized_content`, the worker creates the proposal and writes a `change.rollback_proposed` audit event.
2. **Manual submission** (approver+): `POST /api/v1/change-requests/rollback` — requires `device:change:approve`.  Server derives the NETCONF payload from the target snapshot at submit time and stores only the digest.
3. **Approval/direct-execution**: same as forward changes, but re-validates rollback preflight (target snapshot still restorable, no inflight changes, origin still in failed state).
4. **Execution and verification**: reuses the same apply-verify worker path. Verification passes only if the post-change snapshot digest matches the target snapshot digest. Rollback `verification_failed` does not trigger a second proposal.

Rollback preflight blockers: `CHANGE_IN_FLIGHT`, `ROLLBACK_TARGET_NOT_RESTORABLE`, `ROLLBACK_NO_DIVERGENCE`, `ROLLBACK_ORIGIN_NOT_RECOVERABLE`.

Rollback requires snapshots with `normalized_content` populated (migration `0007_rollback_loop`). Snapshots created before that migration are not restorable (`rollback_eligible = false`).

### Migration and Rollback

Migration: run `star-pulse-migrate` or apply the latest Alembic revision. Revisions through `0007_rollback_loop` add rollback fields to `device_config_change_requests` and `normalized_content` to `device_config_snapshots`.

Rollback: run `alembic downgrade 0006_change_request_safety_loop`. In production, do not disable audit logging or bypass RBAC via config. Rollback must be coordinated with a backend service restart.

### Local Operations Workflow (Rollback)

To exercise the rollback loop locally:

1. Collect a baseline snapshot: `POST /api/v1/devices/{id}/config-snapshots`
2. Submit and approve a change that will fail post-change verification (e.g., mock the verifying read to return a mismatched digest)
3. After the change reaches `verification_failed`, the worker auto-creates a rollback proposal
4. Query the failed change: `GET /api/v1/change-requests/{id}` — the response includes `pending_rollback_proposal_id`
5. Approve the proposal: `POST /api/v1/change-requests/{proposal_id}/approve`
6. The rollback is enqueued; post-change snapshot digest is compared against the target snapshot digest
7. Audit trail: `change.rollback_proposed` → `change.rollback_executed` → `change.rollback_verified`

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

Run a read-only NETCONF configuration snapshot collection:

```bash
curl -X POST http://localhost:8000/api/v1/devices/1/config-snapshots \
  -H 'content-type: application/json' \
  -d '{"datastore": "running"}'
```

The supported datastore values are `running`, `candidate`, and `startup`; unsupported values return
a parameter error before any task is dispatched. The worker executes NETCONF `get-config` only. It
does not call `edit-config`, `commit`, `discard-changes`, `copy-config`, rollback, or equivalent
write operations.

These commands return a task identifier. Query task status with:

```bash
curl http://localhost:8000/api/v1/tasks/<task_id>
```

Task responses include `queued`, `running`, `succeeded`, or `failed`, the related `device_id`, safe
result summaries, standard error codes, safe messages, and redacted diagnostic context. Supported
standard error codes are `INVALID_PARAMETER`, `DEVICE_UNREACHABLE`, `CONNECTION_TIMEOUT`, `AUTH_FAILED`,
`NETCONF_PROTOCOL_ERROR`, `CREDENTIAL_UNAVAILABLE`, and `INTERNAL_ERROR`.

API and worker logs include structured fields for `action`, `task_id`, `device_id`, `datastore`,
`status`, `duration_ms`, and, when applicable, `error_code`. Passwords, private keys, passphrases,
resolved credential values, and uncontrolled full configuration bodies must not be included in task
metadata, API responses, snapshot summaries, discovery results, or logs.

## Local Operator Workflow

1. Bootstrap or create an admin user, then sign in to the operations console.
2. Create a device with NETCONF host, port, username, and credential material. The credential is stored behind a server-side reference and cleared from frontend state after submission.
3. Run connection test, capability discovery, and a baseline snapshot from the device profile.
4. Confirm the onboarding summary reports `ready_for_change: true`; otherwise follow the returned blocker codes and next action.
5. Submit a contextual change from the device profile or snapshot view. The server preflight returns baseline, payload, risk, and blocker summaries before submission.
6. Approve the pending request, or use direct execution with a non-empty reason. Both paths validate preflight server-side.
7. Watch the execution task move through queued/running/verifying, then review `executed`, `verification_failed`, or `failed` status plus the post-change snapshot and comparison summary.

## Device Profile and Snapshots

Read a device profile:

```bash
curl http://localhost:8000/api/v1/devices/1/profile
```

The profile aggregates the device connection summary, status, discovery capabilities, system info,
last configuration snapshot, recent task summaries, and a safety summary. The regular device detail
response also includes the last configuration snapshot and recent task summaries.

List configuration snapshots:

```bash
curl 'http://localhost:8000/api/v1/devices/1/config-snapshots?limit=20'
```

Snapshot responses are intentionally summary-first: `datastore`, `content_digest`, `collected_at`,
`diff_summary`, and safe summary fields. They do not expose credentials or raw full configuration
content. Recent device tasks are available at:

```bash
curl 'http://localhost:8000/api/v1/devices/1/tasks?limit=10'
```

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

Frontend validation:

```bash
cd ../frontend
npm install
npm run typecheck
npm run lint
npm run build
```

Run the frontend locally:

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

## Phase One Boundary

This phase now includes RBAC, audit logging, approval workflows, guided device onboarding, read-only baseline snapshots, server-authoritative preflight, and controlled apply-and-verify execution. It still does not implement autonomous approval/remediation, a full YANG parser, a rollback engine, multi-step maintenance windows, production Kubernetes manifests, or uncontrolled raw configuration exposure.
