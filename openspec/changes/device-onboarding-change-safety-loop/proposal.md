## Why

The platform now has the foundation for devices, read-only snapshots, authentication, RBAC, audit logs, and controlled NETCONF writes, but the operator experience is still split across low-level forms and manual IDs. The next step should turn those building blocks into a safe daily operations loop: onboard a device, verify it, capture a baseline, request a change from that device context, approve it with enough risk information, execute it, and verify the result.

## What Changes

- Add a guided device onboarding workflow in the operations console for creating a device, entering credentials safely, testing connectivity, discovering capabilities, and collecting the first baseline snapshot.
- Add contextual change request entry points from device profile and snapshot views so operators no longer need to manually type device IDs for normal workflows.
- Add change preflight checks that validate device readiness, datastore support, latest snapshot freshness, and availability of proposed configuration before approval or direct execution.
- Add a safe diff and risk summary for proposed configuration changes, based on the latest available snapshot summary and bounded server-side comparison output.
- Extend config change execution into an apply-and-verify loop: queue, run, write, collect a post-change snapshot, compare it to the baseline, and expose verification status.
- Improve audit coverage for onboarding steps, preflight outcomes, approval decisions with risk context, direct execution reasons, and post-change verification.
- Update documentation so the current phase boundary reflects the already implemented RBAC and approval workflow, and describes the new operator workflow.

## Capabilities

### New Capabilities

- `device-onboarding-workflow`: Guided device onboarding, connectivity validation, capability discovery, baseline snapshot collection, and safe onboarding audit behavior.
- `change-preflight-verification`: Pre-execution readiness checks, proposed-change summary/diff generation, execution verification, and post-change snapshot comparison.

### Modified Capabilities

- `operations-console-frontend`: Add guided onboarding UI, contextual change request flows, risk/diff display, execution verification states, and safer role-aware actions.
- `device-config-change-control`: Extend change requests with preflight results, risk summary, verification status, and apply-and-verify execution lifecycle.
- `device-config-snapshots`: Support baseline and post-change snapshot use cases, snapshot freshness checks, and bounded comparison summaries for verification.
- `audit-logging`: Record onboarding, preflight, approval/direct execution risk context, and post-change verification audit events.
- `device-access-capability-discovery`: Require onboarding workflows to use existing connection test and discovery task boundaries with safe task ownership and failure behavior.

## Impact

- Backend API: device onboarding helper endpoints or composed workflow endpoints, change preflight endpoint, change verification fields, and possibly task/status schema extensions.
- Backend services: device service, config snapshot service, change request service, NETCONF task execution path, audit writer, and task state transitions.
- Storage: new fields or related records for onboarding progress, change preflight summaries, baseline snapshot references, post-change snapshot references, and verification status.
- Frontend: operations console device onboarding wizard, device profile action model, change request form redesign, approval/detail views, verification status display, and audit filters.
- Documentation and tests: OpenSpec specs, backend README phase boundary, backend service/API tests, frontend type/build checks, and role-based workflow verification.
