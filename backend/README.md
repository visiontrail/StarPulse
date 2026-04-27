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

## Phase One Boundary

This phase establishes the platform foundation only. It does not implement full satellite-router business workflows, YANG model parsing, complex NETCONF configuration templates, production Kubernetes manifests, RBAC, approval workflows, or autonomous AI Agent behavior.
