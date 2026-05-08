# Star-Pulse

**Satellite Router Ground Management Platform**

> 语言 / Language: **English** · [中文](README.zh.md)

Star-Pulse is an open-source, self-hostable ground management platform for satellite router fleets. It provides device onboarding, NETCONF-based configuration management, a formal change-request workflow with approval gates, apply-and-verify execution, automatic rollback proposals, and a full audit trail — all behind role-based access control.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
  - [Full-Stack (Docker Compose + local frontend)](#full-stack-recommended)
  - [Backend Only (local SQLite)](#backend-only-local-sqlite)
  - [Frontend Only](#frontend-only)
- [RBAC Roles](#rbac-roles)
- [Core Workflow](#core-workflow)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Design System](#design-system)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser / Ops Console              │
│              Next.js 14  (port 3000)                 │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / JWT
┌──────────────────────▼──────────────────────────────┐
│              FastAPI  (port 8000)                    │
│   auth · devices · change_requests · tasks · audit   │
└────────┬─────────────────────────────┬──────────────┘
         │ SQLAlchemy 2.0              │ Celery / RabbitMQ
         ▼                             ▼
┌─────────────────────┐   ┌─────────────────────────┐
│ PostgreSQL / SQLite  │   │     Celery Worker        │
│   (Alembic ORM)      │   │  NETCONF → ncclient      │
└─────────────────────┘   └─────────────────────────┘
```

The backend is a **modular monolith** — one process, cleanly separated modules, no micro-service overhead. Async device operations (connection test, capability discovery, config snapshot, change execution) run in a Celery worker; callers poll `GET /api/v1/tasks/<task_id>`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend API | FastAPI, Python 3.11+, Pydantic v2 |
| Auth | JWT access tokens + HttpOnly refresh cookie, RBAC |
| ORM / Migrations | SQLAlchemy 2.0, Alembic |
| Database | SQLite (local dev) / PostgreSQL 16 (Docker / production) |
| Task Queue | Celery 5, RabbitMQ 3.13 |
| NETCONF | ncclient |
| Linting | Ruff (backend), ESLint + tsc (frontend) |

---

## Quick Start

> Requires Docker, Docker Compose, and Node.js ≥ 18.

```bash
# Clone
git clone <repo-url> star-pulse && cd star-pulse

# Start backend services (API + worker + PostgreSQL + RabbitMQ) in Docker,
# then start the Next.js frontend locally
./start-dev.sh
```

| Service | URL |
|---------|-----|
| Operations Console | http://localhost:3000 |
| API | http://localhost:8000 |
| RabbitMQ Management | http://localhost:15672 |

Default admin credentials (Docker Compose):
- **Username:** `admin`
- **Password:** `admin123!`

---

## Development Setup

### Full-Stack (Recommended)

```bash
./start-dev.sh
```

Runs the Docker Compose stack (API, Celery worker, PostgreSQL, RabbitMQ) and the Next.js dev server concurrently. Hot-reload is active on both.

### Backend Only (Local SQLite)

```bash
cd backend
./scripts/init_dev.sh    # create .venv and install deps (Python 3.11+)
./scripts/run_api.sh     # uvicorn with --reload at port 8000
```

The default database is `backend/star_pulse.db` (SQLite). No RabbitMQ or Celery required for basic API exploration — set `STAR_PULSE_CELERY_TASK_ALWAYS_EAGER=true` to run tasks synchronously in-process.

Run database migrations:

```bash
cd backend && .venv/bin/star-pulse-migrate
```

### Frontend Only

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

---

## RBAC Roles

Four roles are seeded at startup. Roles are hierarchical — each inherits all permissions of the role below it.

| Role | Key Permissions |
|------|----------------|
| `viewer` | `device:read`, `task:read`, `snapshot:read`, `audit:read:summary` |
| `operator` | viewer + `device:collect`, `device:change:submit` |
| `approver` | operator + `device:change:approve`, `device:change:execute` |
| `admin` | all permissions + `user:manage`, `role:manage`, `system:config`, `audit:read:full` |

Initial admin is bootstrapped via `STAR_PULSE_BOOTSTRAP_ADMIN_USERNAME` / `STAR_PULSE_BOOTSTRAP_ADMIN_PASSWORD`. Unset these after first startup in production.

---

## Core Workflow

```
Device Onboarding
  └─ Create device (host, port, NETCONF credentials)
  └─ Connection test  →  Capability discovery  →  Baseline snapshot
  └─ Profile reports ready_for_change: true

Change Request (normal path)
  └─ Operator submits  →  server preflight (baseline freshness, risk, blockers)
  └─ Approver approves  →  Celery enqueues execution
  └─ Worker: edit-config  →  verifying  →  get-config  →  digest compare
  └─ executed  ──or──  verification_failed  →  auto rollback proposal

Change Request (direct-execute path)
  └─ Approver submits with non-empty reason  →  preflight  →  immediate execution

Rollback
  └─ Auto-proposed on verification_failed (worker)
  └─ OR manual: POST /api/v1/change-requests/rollback (approver+)
  └─ Same approval → execution → verification cycle
  └─ Audit trail: rollback_proposed → rollback_executed → rollback_verified
```

All device operations are **non-blocking**: the API returns a `task_id` immediately. Poll `GET /api/v1/tasks/<task_id>` for `queued | running | succeeded | failed`.

---

## Environment Variables

All backend settings use the `STAR_PULSE_` prefix (pydantic-settings, `app/core/config.py`).

### Core

| Variable | Default | Notes |
|----------|---------|-------|
| `STAR_PULSE_DATABASE_URL` | `sqlite:///star_pulse.db` | PostgreSQL in Docker |
| `STAR_PULSE_RABBITMQ_URL` | — | Required for Celery worker |
| `STAR_PULSE_JWT_SECRET_KEY` | insecure default | **Must change in production** — startup fails if default is detected |
| `STAR_PULSE_LOG_LEVEL` | `INFO` | |

### Auth & Session

| Variable | Default | Notes |
|----------|---------|-------|
| `STAR_PULSE_JWT_ALGORITHM` | `HS256` | |
| `STAR_PULSE_ACCESS_TOKEN_TTL_MINUTES` | `15` | |
| `STAR_PULSE_REFRESH_TOKEN_TTL_DAYS` | `7` | |
| `STAR_PULSE_COOKIE_SECURE` | `false` | Set `true` in production (HTTPS) |
| `STAR_PULSE_CORS_ALLOWED_ORIGINS` | `["http://localhost:3000"]` | JSON array |
| `STAR_PULSE_BOOTSTRAP_ADMIN_USERNAME` | — | Creates first admin on startup |
| `STAR_PULSE_BOOTSTRAP_ADMIN_PASSWORD` | — | Clear after initial setup in production |

### NETCONF & Operations

| Variable | Default | Notes |
|----------|---------|-------|
| `STAR_PULSE_NETCONF_LOOPBACK_HOST_OVERRIDE` | — | Set `host.docker.internal` in Docker so the worker reaches host mock servers |
| `STAR_PULSE_NETCONF_DEFAULT_TIMEOUT` | `30` | Seconds |
| `STAR_PULSE_NETCONF_HOSTKEY_VERIFY` | `true` | Set `false` for local mock servers |
| `STAR_PULSE_BASELINE_SNAPSHOT_FRESHNESS_MINUTES` | `60` | Max baseline age to pass preflight |
| `STAR_PULSE_CELERY_TASK_ALWAYS_EAGER` | `false` | `true` runs tasks synchronously (tests / no-broker dev) |
| `STAR_PULSE_AUDIT_RETENTION_DAYS` | `90` | Soft retention hint |

### Frontend

| Variable | Default |
|----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` |

---

## Testing

### Backend

```bash
cd backend
./scripts/test.sh          # pytest (unit + functional, in-memory SQLite)
./scripts/lint.sh          # ruff check

# Single file
.venv/bin/pytest tests/test_devices.py -q
# Single test
.venv/bin/pytest tests/test_devices.py::test_create_device -q
```

NETCONF integration tests require a live mock server and are opt-in:

```bash
STAR_PULSE_NETCONF_INTEGRATION_ENABLED=true ./scripts/test.sh
```

### Frontend

```bash
cd frontend
npm run typecheck    # tsc --noEmit
npm run lint         # next lint
npm run build        # production build (also catches type errors)
```

---

## Project Structure

```
star-pulse/
├── start-dev.sh              # Full-stack dev launcher
├── docker-compose.yml        # API + worker + PostgreSQL + RabbitMQ
├── DESIGN.md                 # UI design system specification
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers (devices, auth, admin, audit, changes, tasks, health)
│   │   ├── auth/             # JWT, RBAC, audit hooks, admin bootstrap, role seeding
│   │   ├── devices/          # Device CRUD, credentials, preflight, snapshot, rollback
│   │   ├── netconf/          # ncclient adapter (protocol.py, service.py)
│   │   ├── tasks/            # Celery app + jobs (connection_test, snapshot, change_execution)
│   │   ├── storage/          # SQLAlchemy models, Alembic migrations (0001–0007), repositories
│   │   ├── core/             # Settings (pydantic-settings), structured logging
│   │   └── ai/               # Placeholder extension boundary
│   ├── tests/                # pytest suite (conftest.py seeds roles, in-memory DB per test)
│   └── scripts/              # init_dev.sh, run_api.sh, test.sh, lint.sh
└── frontend/
    ├── app/
    │   └── page.tsx          # Main SPA — tabs: devices, changes, admin, audit
    ├── components/
    │   ├── auth.tsx          # LoginView, SessionHeader
    │   ├── ui.tsx            # Shared primitives (Button, StatusBadge, DatastoreSelect …)
    │   └── brand.tsx         # BrandMark
    └── lib/
        ├── api.ts            # Typed api.* methods, ApiError, silent token refresh
        ├── session.tsx       # useSession hook, SessionProvider
        ├── types.ts          # Shared TypeScript types, PERM constant map
        ├── theme.tsx         # Design token references
        └── i18n/            # Minimal useT / TranslateFn (blocker / error key i18n)
```

---

## Design System

The UI follows a **warm minimalism** documented in `DESIGN.md`.

| Token | Value |
|-------|-------|
| Background | `#f2f1ed` (warm cream) |
| Primary text | `#26251e` (warm near-black) |
| Accent | `#f54e00` (brand orange) |
| Error | `#cf2d56` (warm crimson) |
| Border | `oklab(0.263084 -0.00230259 0.0124794 / 0.1)` |
| Display font | CursorGothic (−2.16 px letter-spacing at 72 px) |
| Body font | jjannon (OpenType `"cswh"` swash alternates) |
| Code font | berkeleyMono |
