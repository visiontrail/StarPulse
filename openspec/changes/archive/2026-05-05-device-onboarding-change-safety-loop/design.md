## Context

Star-Pulse already has a modular FastAPI backend, SQLAlchemy/Alembic storage, Celery task execution, NETCONF connection/capability/config snapshot services, JWT/RBAC, audit logs, and a Next.js operations console. The current console exposes those capabilities mostly as separate panels: device list/profile, snapshot collection, change request forms, admin, and audit views.

The next product milestone is not a new protocol or an autonomous agent. It is a safer operator workflow that connects the existing pieces into one day-to-day loop:

1. create and validate a device,
2. discover capabilities,
3. collect a baseline snapshot,
4. submit a change from the selected device context,
5. run a preflight check,
6. approve or direct-execute with risk context,
7. write the change,
8. collect and compare a post-change snapshot.

The main constraints are security and operability. Device credentials, tokens, and uncontrolled full configuration bodies must not leak through API responses, logs, task metadata, or frontend storage. NETCONF writes must stay inside the existing change-control boundary.

## Goals / Non-Goals

**Goals:**

- Provide a guided onboarding experience for device creation, connection testing, capability discovery, and initial baseline collection.
- Remove manual device ID entry from normal change workflows by making change requests contextual to device profile and snapshot views.
- Add backend preflight checks for device readiness, datastore support, payload availability, baseline freshness, and safe risk summary generation.
- Extend change execution so success means the write completed and a post-change verification snapshot was collected and compared.
- Keep all sensitive data boundaries intact while still providing enough summaries for operators and approvers.
- Add audit events that let an admin reconstruct onboarding, preflight, approval, direct execution, and verification decisions.

**Non-Goals:**

- No autonomous AI approval, remediation, or configuration generation.
- No full YANG model parser or template engine.
- No general rollback engine or multi-step maintenance-window orchestration.
- No default API exposure of raw full device configuration.
- No Kubernetes production deployment work in this change.

## Decisions

### 1. Use the existing device/task APIs as the workflow spine

The onboarding wizard should compose existing backend capabilities first: create device, submit connection test, submit capability discovery, submit config snapshot, and read the device profile. A separate persistent onboarding table is not required for v1 because progress can be derived from device status, last discovery, last snapshot, and recent tasks.

Alternative considered: create a durable `device_onboarding_sessions` table. This would make wizard progress explicit, but it adds state that can drift from the actual device/task state. The v1 workflow should stay close to operational truth.

### 2. Add computed onboarding summary to profile/API responses

The backend should expose a safe onboarding summary derived from current device state. Example fields: `connection_test_status`, `discovery_status`, `baseline_snapshot_id`, `baseline_collected_at`, `ready_for_change`, and safe blockers. This keeps the frontend simple without introducing another source of state.

Alternative considered: frontend-only derivation. That avoids backend changes, but each frontend view would need to understand task semantics and readiness rules. Backend derivation is more testable and reusable.

### 3. Server-side preflight is authoritative

The frontend can call a preflight preview endpoint, but change submission, approval, and direct execution must recompute or validate preflight server-side. The server stores the resulting safe preflight and risk summary on the change request so approvers see the same decision context that execution used.

Alternative considered: frontend-only validation. That would improve UX but would be bypassable and insufficient for audit.

### 4. Risk summary is bounded and redacted

The v1 risk summary should include safe fields such as datastore, target device, baseline snapshot ID/digest, baseline freshness, proposed payload digest/length, line-count deltas when available, whether the proposed payload is empty, and any unsupported datastore or stale baseline blockers. It must not return passwords, private keys, access tokens, refresh tokens, resolved device credentials, or uncontrolled full config.

Alternative considered: full text diff. This is useful for operators but risky because existing snapshots do not store raw full configuration by design. Full diff can be revisited later with a controlled content store, redaction model, and permission boundary.

### 5. Apply-and-verify extends the existing config-change task path

The existing config change task already writes through `NetconfService.write_config`. After a successful write, the worker should run a read-only `get-config` for the same datastore, save a post-change snapshot, compare it with the stored baseline/preflight summary, and update the change request verification fields. A write success followed by verification failure should be visible as a verification failure, not silently collapsed into success.

Alternative considered: separate verification task submitted by the frontend. That creates race conditions and weakens the execution contract. Verification should be part of the backend-controlled execution lifecycle.

### 6. Status model remains compact

Use a small set of change statuses and verification fields instead of exploding task states. Suggested change statuses: `pending_approval`, `approved`, `queued`, `running`, `verifying`, `executed`, `verification_failed`, `failed`, `rejected`. Task status can remain `queued`, `running`, `succeeded`, `failed`; task result/context carries the finer-grained phase.

Alternative considered: many task statuses. That would ripple through existing task consumers and UI. Keeping task status stable reduces blast radius.

### 7. Permissions follow existing role boundaries

Device creation/editing remains under device management permission. Connection test, capability discovery, and snapshot collection remain under collection permission. Change submission, approval, and execution continue to use existing change permissions. The frontend should expose or disable actions based on these permissions and should not issue forbidden workflow calls.

Alternative considered: add a new `device:onboard` permission. This may be useful later, but v1 can use existing permissions without changing the role matrix.

## Risks / Trade-offs

- [Risk] Operators may expect a full line-by-line diff, but v1 only provides bounded safe summaries. → Mitigation: label the summary clearly and preserve a future extension point for controlled config content/diff storage.
- [Risk] Synchronous preflight that reads live device config could be slow. → Mitigation: default preflight uses the latest baseline snapshot and flags staleness; live refresh can be explicit or handled through an async snapshot task.
- [Risk] Verification after write may fail even when the device accepted the change. → Mitigation: represent this as `verification_failed` with safe error details so operators can retry verification or investigate.
- [Risk] Derived onboarding state may miss edge cases across concurrent tasks. → Mitigation: readiness checks must query recent task state and block duplicate running operations for the same device/datastore.
- [Risk] Additional JSON fields on change requests can become schema drift. → Mitigation: define Pydantic schemas for preflight/risk/verification summaries and cover them with tests.

## Migration Plan

1. Add Alembic migration for change request preflight, baseline snapshot, verification snapshot, verification status, and safe summary fields.
2. Add derived onboarding summary fields to API schemas without breaking existing response fields.
3. Add preflight service/API and wire it into submit, approve, and direct execute paths.
4. Extend config change worker to update running/verifying/executed/verification_failed states and save post-change snapshots.
5. Update frontend API types and replace manual change forms with contextual flows while preserving existing direct URLs where useful.
6. Update README phase boundary and operator workflow docs.

Rollback should preserve existing change request records. If rollback is needed, stop workers, downgrade the migration, and restart API/worker using the previous execution behavior. Any in-flight change with new verification statuses should be completed or manually reconciled before downgrade.

## Open Questions

- What default freshness threshold should mark a baseline snapshot as stale: 15 minutes, 1 hour, or configurable per environment?
- Should direct execution require a fresh live snapshot by default, or only warn when the baseline is stale?
- Should post-change verification compare against the proposed payload digest, the previous baseline digest, or both when only bounded summaries are available?
