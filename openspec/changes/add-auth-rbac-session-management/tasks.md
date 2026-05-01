## 1. Backend Foundation

- [ ] 1.1 Add open-source JWT and password hashing dependencies to `backend/pyproject.toml`.
- [ ] 1.2 Extend backend settings with JWT secret, access token TTL, refresh token TTL, cookie, CORS, and audit retention configuration.
- [ ] 1.3 Add auth, RBAC, refresh token, device config change request, and audit log SQLAlchemy models.
- [ ] 1.4 Create Alembic migration for users, roles, permissions, role mappings, refresh tokens, change requests, audit logs, and task actor metadata.
- [ ] 1.5 Implement repositories for users, roles, permissions, refresh tokens, change requests, and audit logs.
- [ ] 1.6 Implement idempotent seed logic for permission constants and `viewer`, `operator`, `approver`, `admin` role mappings.
- [ ] 1.7 Add an initial admin bootstrap path for local development using explicit environment variables or a CLI script.

## 2. Authentication And RBAC

- [ ] 2.1 Implement password hashing and verification utilities that never expose plain passwords.
- [ ] 2.2 Implement JWT access token creation, validation, expiry handling, and claim extraction.
- [ ] 2.3 Implement refresh token generation, hashing, persistence, rotation, revocation, and expiry validation.
- [ ] 2.4 Add auth API schemas for login, token refresh, logout, current user, users, roles, and permissions.
- [ ] 2.5 Add login, refresh, logout, and current-user API routes with standard 401 responses.
- [ ] 2.6 Implement `get_current_user` and `require_permission` FastAPI dependencies.
- [ ] 2.7 Protect `/api/v1` business routes by default while keeping health, login, and refresh endpoints public.
- [ ] 2.8 Add admin-only APIs for user creation, disable/enable, role assignment, role permission management, and permission listing.
- [ ] 2.9 Map existing device, task, snapshot, system, audit, and change-control routes to explicit permission constants.

## 3. Audit Logging

- [ ] 3.1 Implement audit action constants, outcome constants, and a shared audit event writer.
- [ ] 3.2 Add metadata redaction for passwords, tokens, device credentials, private keys, and full configuration bodies.
- [ ] 3.3 Record audit events for login success, login failure, refresh failure, and logout.
- [ ] 3.4 Record audit events for user role changes, role permission changes, disabled users, and rejected admin operations.
- [ ] 3.5 Record audit events for permission-denied, validation-failed, and execution-failed operations.
- [ ] 3.6 Add paginated audit log query API with filters for time range, actor, action, target, and outcome.
- [ ] 3.7 Enforce summary/full audit read permissions according to the seeded role matrix.

## 4. Device Config Change Control

- [ ] 4.1 Add change request schemas for submit, approve, reject, direct execute, list, detail, and status responses.
- [ ] 4.2 Implement change request service for operator submission with device/datastore validation and pending approval state.
- [ ] 4.3 Implement approval and rejection service methods for approver users.
- [ ] 4.4 Implement direct execution service for approver users, requiring a reason and recording bypass metadata.
- [ ] 4.5 Add API routes for change request submit, approve, reject, direct execute, list, and detail.
- [ ] 4.6 Add Celery task support for authorized device configuration change execution.
- [ ] 4.7 Extend NETCONF service or add a bounded adapter path for authorized write operations used only by change control.
- [ ] 4.8 Update task status records to associate execution tasks with actor user and change request identifiers.
- [ ] 4.9 Record audit events for change submission, approval, rejection, direct execution, execution success, and execution failure.

## 5. Existing API Integration

- [ ] 5.1 Apply read permissions to device list, device detail, device profile, task query, and snapshot query endpoints.
- [ ] 5.2 Apply collection permissions to config snapshot, connection test, and capability discovery task submission endpoints.
- [ ] 5.3 Return 401 for missing or invalid access tokens and 403 for authenticated users lacking permissions.
- [ ] 5.4 Ensure protected failures do not create tasks or mutate business state.
- [ ] 5.5 Include safe actor user summaries in task and snapshot-related responses where required.
- [ ] 5.6 Preserve existing health check anonymous access.

## 6. Frontend Session And Permissions

- [ ] 6.1 Add frontend auth and RBAC TypeScript types for user, role, permission, session, login, and audit/change records.
- [ ] 6.2 Update frontend API client to attach access tokens, include credentials, refresh on 401, retry once, and clear session on refresh failure.
- [ ] 6.3 Add a session provider or equivalent state boundary for current user, permissions, login, refresh, and logout.
- [ ] 6.4 Build the login view and prevent protected data requests before authentication is established.
- [ ] 6.5 Add session header controls showing current user, role summary, refresh state, and logout.
- [ ] 6.6 Gate existing device, snapshot, and task actions by permission, including disabled states for forbidden operations.
- [ ] 6.7 Add operator change request submission UI with target device, datastore, change summary/reference, and reason.
- [ ] 6.8 Add approver pending approval and direct execution UI, requiring a direct execution reason.
- [ ] 6.9 Add admin user/role management UI for users, roles, permissions, and system configuration entry points.
- [ ] 6.10 Add audit log UI with summary/full read behavior based on permissions.
- [ ] 6.11 Ensure tokens, passwords, credentials, and full configuration bodies are never rendered in the UI.

## 7. Tests And Verification

- [ ] 7.1 Add backend fixtures for seeded users with viewer, operator, approver, and admin roles.
- [ ] 7.2 Add tests for password hashing, JWT validation, refresh rotation, logout revocation, and disabled user login rejection.
- [ ] 7.3 Add API tests for unauthenticated access, authenticated access, and permission-denied behavior across existing routes.
- [ ] 7.4 Add tests for admin user/role management and role-change permission refresh behavior.
- [ ] 7.5 Add tests for audit event creation, redaction, filtering, pagination, and failed operation logging.
- [ ] 7.6 Add tests for change request submission, approval, rejection, direct execution, and permission failures.
- [ ] 7.7 Add tests that config snapshot routes remain read-only and reject unauthorized collection requests.
- [ ] 7.8 Add frontend tests or build-time checks for login, session refresh, logout, and permission-gated actions.
- [ ] 7.9 Run backend tests and lint checks.
- [ ] 7.10 Run frontend lint/build checks.
- [ ] 7.11 Run OpenSpec status/validation for the change and resolve any artifact issues.

## 8. Documentation And Operations

- [ ] 8.1 Update backend README with auth settings, initial admin bootstrap, token behavior, and role matrix.
- [ ] 8.2 Update frontend README with login/session development flow and required API base URL/CORS settings.
- [ ] 8.3 Document the approver direct execution bypass behavior and required audit fields.
- [ ] 8.4 Document migration and rollback notes for enabling default API authentication.
