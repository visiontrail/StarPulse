# Star-Pulse Operations Console

Read-only operations MVP for registered NETCONF devices.

## Local Development

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

The default API base URL is `http://localhost:8000/api/v1`.

## Checks

```bash
npm run typecheck
npm run lint
npm run build
```

## Safety Boundary

The console renders backend-provided summaries only. It can trigger `get-config` snapshot collection
for an allowed datastore and display task, profile, and snapshot summaries. It does not provide
configuration edit, commit, rollback, delete, credential display, or raw full-configuration views.
