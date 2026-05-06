# Star-Pulse Operations Console

Ground management operations console with authentication, RBAC, device onboarding, contextual change control, preflight risk review, execution verification, and audit log views.

## Local Development

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

The default API base URL is `http://localhost:8000/api/v1`.

### Required API Settings

The backend must have CORS configured to allow the frontend origin:

```bash
STAR_PULSE_CORS_ALLOWED_ORIGINS='["http://localhost:3000"]'
```

### Login and Session Flow

1. The app loads and attempts session recovery via `POST /api/v1/auth/refresh` (uses HttpOnly refresh cookie).
2. If recovery fails, the login view is shown; no protected data is requested until authenticated.
3. After login, the access token is stored in-memory only. The refresh token is stored in an HttpOnly cookie.
4. On access token expiry (HTTP 401), the client automatically calls refresh once and retries. If refresh fails, the session is cleared and the login view is shown.
5. Logout calls `POST /api/v1/auth/logout`, clears the cookie, and returns to the login view.

### Onboarding and Preflight Flow

1. Users with `device:manage` can add a device from the device list.
2. Users with `device:collect` can run connection test, capability discovery, and baseline snapshot steps from the selected device profile.
3. The profile shows onboarding readiness, blocker codes, latest baseline snapshot, and the next action returned by the backend.
4. Normal change submission is contextual from a device profile or snapshot row; the console no longer offers a free-standing manual Device ID submit form.
5. Submit and direct-execute forms first call backend preflight and show baseline, payload, risk, and blockers before sending the final request.
6. Change cards show submitter, approver, preflight/risk context, execution task, verification state, and safe post-change summary fields.

### Rollback Development Flow

Snapshot-driven rollback entry points:
- In the Devices tab, each snapshot row shows a **Restore** button for approvers and admins (`device:change:approve`).
- Snapshots with `rollback_eligible = false` show the button disabled with a tooltip explaining why (e.g., `ROLLBACK_TARGET_NOT_RESTORABLE`).
- Clicking **Restore** opens the `RollbackSubmitForm` inline, which previews the rollback preflight before allowing submission.

Verification-failed proposal link:
- Change cards in the Changes tab that have `status = "verification_failed"` show a warning banner.
- If `pending_rollback_proposal_id` is set, the banner indicates the proposal ID for easy navigation.
- If no proposal exists (e.g., baseline snapshot not restorable), the banner explains no rollback is available.

Rollback change cards:
- Rollback changes display an `is_rollback` badge alongside the status badge.
- A "Rollback Context" card shows the origin change ID and target snapshot ID/digest.
- Rollback `verification_failed` cards display a distinct message explaining no further auto-proposal will be created.

Type additions: `ChangeRequestRead` now includes `is_rollback`, `rollback_of_change_id`, `rollback_target_snapshot_id`, `rollback_target_snapshot`, and `pending_rollback_proposal_id`. `ConfigSnapshot` now includes `rollback_eligible` and `rollback_blocker`. `ChangePreflightResponse` now includes `mode` and `rollback_target_snapshot`.

### CORS Configuration

When the frontend and backend run on different origins (common in development), ensure:
- `STAR_PULSE_CORS_ALLOWED_ORIGINS` includes the frontend origin
- `STAR_PULSE_COOKIE_SECURE=false` in local dev (set `true` in production with HTTPS)
- The fetch client uses `credentials: "include"` (already configured in `lib/api.ts`)

## Checks

```bash
npm run typecheck
npm run lint
npm run build
```

## Safety Boundary

- Access tokens, refresh tokens, passwords, and device credentials are never rendered in the UI.
- Configuration change summaries are shown by reference/summary, never as uncontrolled full config bodies.
- Sensitive fields are not cached in localStorage or sessionStorage.
- Permission-gated actions are hidden or disabled when the current user lacks the required permission.
- Preflight and verification UI uses backend summaries and blocker/error codes instead of rendering raw config bodies.
