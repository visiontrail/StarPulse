## 1. Data Model And Configuration

- [ ] 1.1 Add baseline freshness configuration to backend settings and document its environment variable.
- [ ] 1.2 Extend change request models with baseline snapshot, preflight summary, risk summary, verification status, verification snapshot, verification summary, and executed/verified timing fields.
- [ ] 1.3 Create an Alembic migration for new change request verification and preflight fields with downgrade support.
- [ ] 1.4 Add or update Pydantic schemas for onboarding summary, change preflight request/response, risk summary, verification summary, and extended change request reads.
- [ ] 1.5 Add repository helpers for reading latest successful snapshot by device/datastore, storing preflight summaries, and updating verification fields.

## 2. Device Onboarding Backend

- [ ] 2.1 Implement derived onboarding summary generation from device profile, connection config, last discovery, latest baseline snapshots, and recent tasks.
- [ ] 2.2 Include onboarding summary in device profile or an equivalent read endpoint without exposing credentials or full config.
- [ ] 2.3 Ensure device create, connection test, capability discovery, and baseline snapshot paths write safe actor/task/audit context.
- [ ] 2.4 Prevent duplicate onboarding step submissions when an equivalent queued or running task already exists.
- [ ] 2.5 Add backend tests for onboarding summary readiness, blockers, duplicate task prevention, and sensitive field exclusion.

## 3. Change Preflight Backend

- [ ] 3.1 Implement a change preflight service that validates permissions, device readiness, datastore support, payload presence, reason presence, and baseline freshness.
- [ ] 3.2 Generate bounded risk summaries with baseline snapshot identifiers, digests, payload digest/length/line counts, blocker list, and no raw full config.
- [ ] 3.3 Add a preflight preview API endpoint for the frontend and ensure it does not create change requests or execution tasks.
- [ ] 3.4 Recompute or validate preflight during normal change submission and persist the resulting safe summary on the change request.
- [ ] 3.5 Enforce valid preflight during approval and direct execution, rejecting stale or failed preflight states.
- [ ] 3.6 Add audit events for preflight success, preflight failure, stale baseline rejection, and direct execution with preflight context.
- [ ] 3.7 Add backend tests for successful preflight, missing baseline, stale baseline, invalid datastore, empty payload, redaction, and permission failures.

## 4. Apply And Verify Execution

- [ ] 4.1 Extend config change task execution to mark change records as running and verifying at the appropriate phases.
- [ ] 4.2 After successful NETCONF write, collect a post-change read-only snapshot for the same device and datastore.
- [ ] 4.3 Save post-change snapshot identifiers and safe comparison summaries on the change request.
- [ ] 4.4 Distinguish write failure from verification failure in task result summaries, change status, and audit events.
- [ ] 4.5 Ensure config snapshot service remains read-only and NETCONF writes remain reachable only through change-control execution.
- [ ] 4.6 Add worker/service tests for write success with verification success, write success with verification failure, write failure without verification, and sensitive context redaction.

## 5. Frontend API And Types

- [ ] 5.1 Extend frontend TypeScript types for onboarding summary, preflight response, risk summary, verification summary, and extended change request status.
- [ ] 5.2 Add API client methods for device creation, connection test, capability discovery, preflight preview, contextual submit, and refreshed change detail/list reads.
- [ ] 5.3 Normalize API error handling so preflight blockers and verification failures render as concise user-facing messages.
- [ ] 5.4 Confirm access tokens, refresh tokens, device credentials, and raw config bodies are not persisted in localStorage or sessionStorage.

## 6. Frontend Onboarding Workflow

- [ ] 6.1 Build the device onboarding wizard entry point from the device list and empty state for users with device management permission.
- [ ] 6.2 Implement device connection and credential input states with safe clearing after submission.
- [ ] 6.3 Add connection test, capability discovery, and baseline snapshot steps with status, retry, duplicate-running-state handling, and refresh controls.
- [ ] 6.4 Update device profile to show onboarding readiness, blockers, latest baseline snapshot, and next recommended action.
- [ ] 6.5 Verify viewer/operator/approver/admin permission gates for onboarding actions.

## 7. Frontend Change Safety Workflow

- [ ] 7.1 Replace normal manual Device ID change submission with contextual actions from device profile and snapshot views.
- [ ] 7.2 Add preflight preview before submit, approve, and direct execute, including baseline, risk, blocker, and bounded comparison display.
- [ ] 7.3 Update change request cards/detail views to show submitter, approver, baseline snapshot, preflight result, risk summary, execution task, and verification state.
- [ ] 7.4 Require non-empty direct execution reason and show the preflight/risk context before direct execution submission.
- [ ] 7.5 Add running, verifying, executed, verification_failed, failed, and rejected display states with safe error messages.

## 8. Documentation And Verification

- [ ] 8.1 Update backend README phase boundary to reflect existing RBAC, approval workflows, and the new onboarding/change safety loop.
- [ ] 8.2 Document the local operator workflow: bootstrap admin, create device, test connection, discover capabilities, collect baseline, submit change, approve/direct execute, and verify.
- [ ] 8.3 Update frontend README with onboarding and preflight development flow.
- [ ] 8.4 Run backend tests and lint checks.
- [ ] 8.5 Run frontend typecheck, lint, and build checks.
- [ ] 8.6 Run OpenSpec status and validation for `device-onboarding-change-safety-loop`.
