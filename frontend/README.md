# Star-Pulse Operations Console

Ground management operations console with authentication, RBAC, change control, and audit log views.

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
