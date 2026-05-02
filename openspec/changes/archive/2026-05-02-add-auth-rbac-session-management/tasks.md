## 1. Backend Foundation

- [x] 1.1 Add open-source JWT and password hashing dependencies to `backend/pyproject.toml`.
- [x] 1.2 Extend backend settings with JWT secret, access token TTL, refresh token TTL, cookie, CORS, and audit retention configuration.
- [x] 1.3 Add auth, RBAC, refresh token, device config change request, and audit log SQLAlchemy models.
- [x] 1.4 Create Alembic migration for users, roles, permissions, role mappings, refresh tokens, change requests, audit logs, and task actor metadata.
- [x] 1.5 Implement repositories for users, roles, permissions, refresh tokens, change requests, and audit logs.
- [x] 1.6 Implement idempotent seed logic for permission constants and `viewer`, `operator`, `approver`, `admin` role mappings.
- [x] 1.7 Add an initial admin bootstrap path for local development using explicit environment variables or a CLI script.

## 2. Authentication And RBAC

- [x] 2.1 Implement password hashing and verification utilities that never expose plain passwords.
- [x] 2.2 Implement JWT access token creation, validation, expiry handling, and claim extraction.
- [x] 2.3 Implement refresh token generation, hashing, persistence, rotation, revocation, and expiry validation.
- [x] 2.4 Add auth API schemas for login, token refresh, logout, current user, users, roles, and permissions.
- [x] 2.5 Add login, refresh, logout, and current-user API routes with standard 401 responses.
- [x] 2.6 Implement `get_current_user` and `require_permission` FastAPI dependencies.
- [x] 2.7 Protect `/api/v1` business routes by default while keeping health, login, and refresh endpoints public.
- [x] 2.8 Add admin-only APIs for user creation, disable/enable, role assignment, role permission management, and permission listing.
- [x] 2.9 Map existing device, task, snapshot, system, audit, and change-control routes to explicit permission constants.

## 3. Audit Logging

- [x] 3.1 Implement audit action constants, outcome constants, and a shared audit event writer.
- [x] 3.2 Add metadata redaction for passwords, tokens, device credentials, private keys, and full configuration bodies.
- [x] 3.3 Record audit events for login success, login failure, refresh failure, and logout.
- [x] 3.4 Record audit events for user role changes, role permission changes, disabled users, and rejected admin operations.
- [x] 3.5 Record audit events for permission-denied, validation-failed, and execution-failed operations.
- [x] 3.6 Add paginated audit log query API with filters for time range, actor, action, target, and outcome.
- [x] 3.7 Enforce summary/full audit read permissions according to the seeded role matrix.

## 4. Device Config Change Control

- [x] 4.1 Add change request schemas for submit, approve, reject, direct execute, list, detail, and status responses.
- [x] 4.2 Implement change request service for operator submission with device/datastore validation and pending approval state.
- [x] 4.3 Implement approval and rejection service methods for approver users.
- [x] 4.4 Implement direct execution service for approver users, requiring a reason and recording bypass metadata.
- [x] 4.5 Add API routes for change request submit, approve, reject, direct execute, list, and detail.
- [x] 4.6 Add Celery task support for authorized device configuration change execution.
- [x] 4.7 Extend NETCONF service or add a bounded adapter path for authorized write operations used only by change control.
- [x] 4.8 Update task status records to associate execution tasks with actor user and change request identifiers.
- [x] 4.9 Record audit events for change submission, approval, rejection, direct execution, execution success, and execution failure.

## 5. Existing API Integration

- [x] 5.1 Apply read permissions to device list, device detail, device profile, task query, and snapshot query endpoints.
- [x] 5.2 Apply collection permissions to config snapshot, connection test, and capability discovery task submission endpoints.
- [x] 5.3 Return 401 for missing or invalid access tokens and 403 for authenticated users lacking permissions.
- [x] 5.4 Ensure protected failures do not create tasks or mutate business state.
- [x] 5.5 Include safe actor user summaries in task and snapshot-related responses where required.
- [x] 5.6 Preserve existing health check anonymous access.

## 6. Frontend Session And Permissions

- [x] 6.1 Add frontend auth and RBAC TypeScript types for user, role, permission, session, login, and audit/change records.
- [x] 6.2 Update frontend API client to attach access tokens, include credentials, refresh on 401, retry once, and clear session on refresh failure.
- [x] 6.3 Add a session provider or equivalent state boundary for current user, permissions, login, refresh, and logout.
- [x] 6.4 Build the login view and prevent protected data requests before authentication is established.
- [x] 6.5 Add session header controls showing current user, role summary, refresh state, and logout.
- [x] 6.6 Gate existing device, snapshot, and task actions by permission, including disabled states for forbidden operations.
- [x] 6.7 Add operator change request submission UI with target device, datastore, change summary/reference, and reason.
- [x] 6.8 Add approver pending approval and direct execution UI, requiring a direct execution reason.
- [x] 6.9 Add admin user/role management UI for users, roles, permissions, and system configuration entry points.
- [x] 6.10 Add audit log UI with summary/full read behavior based on permissions.
- [x] 6.11 Ensure tokens, passwords, credentials, and full configuration bodies are never rendered in the UI.

## 7. Tests And Verification

- [x] 7.1 Add backend fixtures for seeded users with viewer, operator, approver, and admin roles.
- [x] 7.2 Add tests for password hashing, JWT validation, refresh rotation, logout revocation, and disabled user login rejection.
- [x] 7.3 Add API tests for unauthenticated access, authenticated access, and permission-denied behavior across existing routes.
- [x] 7.4 Add tests for admin user/role management and role-change permission refresh behavior.
- [x] 7.5 Add tests for audit event creation, redaction, filtering, pagination, and failed operation logging.
- [x] 7.6 Add tests for change request submission, approval, rejection, direct execution, and permission failures.
- [x] 7.7 Add tests that config snapshot routes remain read-only and reject unauthorized collection requests.
- [x] 7.8 Add frontend tests or build-time checks for login, session refresh, logout, and permission-gated actions.
- [x] 7.9 Run backend tests and lint checks.
- [x] 7.10 Run frontend lint/build checks.
- [x] 7.11 Run OpenSpec status/validation for the change and resolve any artifact issues.

## 8. Documentation And Operations

- [x] 8.1 Update backend README with auth settings, initial admin bootstrap, token behavior, and role matrix.
- [x] 8.2 Update frontend README with login/session development flow and required API base URL/CORS settings.
- [x] 8.3 Document the approver direct execution bypass behavior and required audit fields.
- [x] 8.4 Document migration and rollback notes for enabling default API authentication.
