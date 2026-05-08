# Star-Pulse

**卫星路由器地面管理平台**

> 语言 / Language: [English](README.md) · **中文**

Star-Pulse 是一个开源、可自托管的卫星路由器集群地面管理平台。它提供设备接入、基于 NETCONF 的配置管理、带审批门控的变更请求工作流、应用并验证执行、自动回滚提案，以及完整的审计链——全部在基于角色的访问控制（RBAC）体系之下运行。

---

## 目录

- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [快速启动](#快速启动)
- [开发环境配置](#开发环境配置)
  - [全栈模式（推荐）](#全栈模式推荐)
  - [仅后端（本地 SQLite）](#仅后端本地-sqlite)
  - [仅前端](#仅前端)
- [RBAC 角色权限](#rbac-角色权限)
- [核心工作流](#核心工作流)
- [环境变量](#环境变量)
- [测试](#测试)
- [项目结构](#项目结构)
- [设计系统](#设计系统)

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   浏览器 / 运维控制台                  │
│              Next.js 14  (端口 3000)                 │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / JWT
┌──────────────────────▼──────────────────────────────┐
│              FastAPI  (端口 8000)                    │
│   auth · devices · change_requests · tasks · audit   │
└────────┬─────────────────────────────┬──────────────┘
         │ SQLAlchemy 2.0              │ Celery / RabbitMQ
         ▼                             ▼
┌─────────────────────┐   ┌─────────────────────────┐
│ PostgreSQL / SQLite  │   │     Celery Worker        │
│   （Alembic ORM）    │   │  NETCONF → ncclient      │
└─────────────────────┘   └─────────────────────────┘
```

后端是**模块化单体架构**——单一进程、模块清晰、无微服务开销。异步设备操作（连接测试、能力发现、配置快照、变更执行）运行在 Celery Worker 中，调用方通过轮询 `GET /api/v1/tasks/<task_id>` 获取结果。

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | Next.js 14、TypeScript、Tailwind CSS |
| 后端 API | FastAPI、Python 3.11+、Pydantic v2 |
| 认证鉴权 | JWT 访问令牌 + HttpOnly 刷新 Cookie、RBAC |
| ORM / 数据库迁移 | SQLAlchemy 2.0、Alembic |
| 数据库 | SQLite（本地开发）/ PostgreSQL 16（Docker / 生产） |
| 任务队列 | Celery 5、RabbitMQ 3.13 |
| NETCONF | ncclient |
| 代码检查 | Ruff（后端）、ESLint + tsc（前端） |

---

## 快速启动

> 需要 Docker、Docker Compose 以及 Node.js ≥ 18。

```bash
# 克隆仓库
git clone <repo-url> star-pulse && cd star-pulse

# 通过 Docker 启动后端服务（API + Worker + PostgreSQL + RabbitMQ），
# 同时在本地启动 Next.js 前端
./start-dev.sh
```

| 服务 | 地址 |
|------|------|
| 运维控制台 | http://localhost:3000 |
| API | http://localhost:8000 |
| RabbitMQ 管理界面 | http://localhost:15672 |

Docker Compose 默认管理员账号：
- **用户名：** `admin`
- **密码：** `admin123!`

---

## 开发环境配置

### 全栈模式（推荐）

```bash
./start-dev.sh
```

同时启动 Docker Compose 栈（API、Celery Worker、PostgreSQL、RabbitMQ）和 Next.js 开发服务器，两端均支持热重载。

### 仅后端（本地 SQLite）

```bash
cd backend
./scripts/init_dev.sh    # 创建 .venv 并安装依赖（Python 3.11+）
./scripts/run_api.sh     # 启动 uvicorn，--reload，端口 8000
```

默认数据库为 `backend/star_pulse.db`（SQLite）。基础 API 探索无需 RabbitMQ 或 Celery——设置 `STAR_PULSE_CELERY_TASK_ALWAYS_EAGER=true` 可在进程内同步执行任务。

执行数据库迁移：

```bash
cd backend && .venv/bin/star-pulse-migrate
```

### 仅前端

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

---

## RBAC 角色权限

启动时自动种入四个角色，角色具有继承关系——每个角色拥有其下级角色的全部权限。

| 角色 | 核心权限 |
|------|---------|
| `viewer`（只读） | `device:read`、`task:read`、`snapshot:read`、`audit:read:summary` |
| `operator`（操作员） | viewer 所有权限 + `device:collect`、`device:change:submit` |
| `approver`（审批员） | operator 所有权限 + `device:change:approve`、`device:change:execute` |
| `admin`（管理员） | 全部权限 + `user:manage`、`role:manage`、`system:config`、`audit:read:full` |

初始管理员通过 `STAR_PULSE_BOOTSTRAP_ADMIN_USERNAME` / `STAR_PULSE_BOOTSTRAP_ADMIN_PASSWORD` 引导创建，生产环境中首次启动后应清除这两个变量。

---

## 核心工作流

```
设备接入
  └─ 创建设备（主机、端口、NETCONF 凭据）
  └─ 连接测试 → 能力发现 → 基线快照
  └─ 设备概要页显示 ready_for_change: true

变更请求（标准流程）
  └─ 操作员提交 → 服务端预检（基线新鲜度、风险评估、阻塞项）
  └─ 审批员审批 → Celery 入队执行
  └─ Worker：edit-config → verifying → get-config → 摘要对比
  └─ executed（成功）或 verification_failed → 自动创建回滚提案

变更请求（直接执行流程）
  └─ 审批员填写非空原因 → 预检 → 立即执行

回滚
  └─ 验证失败时由 Worker 自动提案
  └─ 或由审批员手动提交：POST /api/v1/change-requests/rollback
  └─ 同样经历审批 → 执行 → 验证循环
  └─ 审计链：rollback_proposed → rollback_executed → rollback_verified
```

所有设备操作均为**非阻塞**：API 立即返回 `task_id`，通过轮询 `GET /api/v1/tasks/<task_id>` 获取 `queued | running | succeeded | failed` 状态。

---

## 环境变量

所有后端配置均使用 `STAR_PULSE_` 前缀（pydantic-settings，`app/core/config.py`）。

### 核心配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STAR_PULSE_DATABASE_URL` | `sqlite:///star_pulse.db` | Docker 中使用 PostgreSQL |
| `STAR_PULSE_RABBITMQ_URL` | — | Celery Worker 必填 |
| `STAR_PULSE_JWT_SECRET_KEY` | 不安全默认值 | **生产环境必须修改**——检测到默认值时启动失败 |
| `STAR_PULSE_LOG_LEVEL` | `INFO` | |

### 认证与会话

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STAR_PULSE_JWT_ALGORITHM` | `HS256` | |
| `STAR_PULSE_ACCESS_TOKEN_TTL_MINUTES` | `15` | 访问令牌有效期（分钟） |
| `STAR_PULSE_REFRESH_TOKEN_TTL_DAYS` | `7` | 刷新令牌有效期（天） |
| `STAR_PULSE_COOKIE_SECURE` | `false` | 生产环境（HTTPS）设为 `true` |
| `STAR_PULSE_CORS_ALLOWED_ORIGINS` | `["http://localhost:3000"]` | JSON 数组 |
| `STAR_PULSE_BOOTSTRAP_ADMIN_USERNAME` | — | 启动时创建初始管理员 |
| `STAR_PULSE_BOOTSTRAP_ADMIN_PASSWORD` | — | 生产初始化后清除 |

### NETCONF 与运维

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STAR_PULSE_NETCONF_LOOPBACK_HOST_OVERRIDE` | — | Docker 中设为 `host.docker.internal`，使 Worker 能访问宿主机 Mock 服务器 |
| `STAR_PULSE_NETCONF_DEFAULT_TIMEOUT` | `30` | 超时秒数 |
| `STAR_PULSE_NETCONF_HOSTKEY_VERIFY` | `true` | 本地 Mock 服务器设为 `false` |
| `STAR_PULSE_BASELINE_SNAPSHOT_FRESHNESS_MINUTES` | `60` | 基线快照通过预检的最大有效分钟数 |
| `STAR_PULSE_CELERY_TASK_ALWAYS_EAGER` | `false` | `true` 时任务同步执行（测试 / 无 Broker 开发） |
| `STAR_PULSE_AUDIT_RETENTION_DAYS` | `90` | 审计日志软保留提示天数 |

### 前端

| 变量 | 默认值 |
|------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` |

---

## 测试

### 后端

```bash
cd backend
./scripts/test.sh          # pytest（单元 + 功能测试，内存 SQLite）
./scripts/lint.sh          # ruff 静态检查

# 单个文件
.venv/bin/pytest tests/test_devices.py -q
# 单个用例
.venv/bin/pytest tests/test_devices.py::test_create_device -q
```

NETCONF 集成测试需要真实 Mock 服务器，默认不启用：

```bash
STAR_PULSE_NETCONF_INTEGRATION_ENABLED=true ./scripts/test.sh
```

### 前端

```bash
cd frontend
npm run typecheck    # tsc --noEmit
npm run lint         # next lint
npm run build        # 生产构建（同时捕获类型错误）
```

---

## 项目结构

```
star-pulse/
├── start-dev.sh              # 全栈开发启动脚本
├── docker-compose.yml        # API + Worker + PostgreSQL + RabbitMQ
├── DESIGN.md                 # UI 设计系统规范
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI 路由（devices, auth, admin, audit, changes, tasks, health）
│   │   ├── auth/             # JWT、RBAC、审计钩子、管理员引导、角色种入
│   │   ├── devices/          # 设备 CRUD、凭据、预检、快照、回滚
│   │   ├── netconf/          # ncclient 适配层（protocol.py, service.py）
│   │   ├── tasks/            # Celery 应用 + 任务（连接测试、快照、变更执行）
│   │   ├── storage/          # SQLAlchemy 模型、Alembic 迁移（0001–0007）、仓库
│   │   ├── core/             # 配置（pydantic-settings）、结构化日志
│   │   └── ai/               # 扩展边界占位模块
│   ├── tests/                # pytest 套件（conftest.py 种入角色，每测试内存 DB）
│   └── scripts/              # init_dev.sh, run_api.sh, test.sh, lint.sh
└── frontend/
    ├── app/
    │   └── page.tsx          # 主 SPA——标签页：devices, changes, admin, audit
    ├── components/
    │   ├── auth.tsx          # LoginView, SessionHeader
    │   ├── ui.tsx            # 共享原子组件（Button, StatusBadge, DatastoreSelect …）
    │   └── brand.tsx         # BrandMark
    └── lib/
        ├── api.ts            # 类型化 api.* 方法、ApiError、静默 Token 刷新
        ├── session.tsx       # useSession Hook、SessionProvider
        ├── types.ts          # 共享 TypeScript 类型、PERM 常量映射
        ├── theme.tsx         # 设计 Token 引用
        └── i18n/            # 最简 useT / TranslateFn（阻塞项 / 错误码 i18n）
```

---

## 设计系统

UI 遵循 `DESIGN.md` 中定义的 **暖色极简主义**。

| Token | 值 |
|-------|---|
| 背景色 | `#f2f1ed`（暖奶油白） |
| 主文字色 | `#26251e`（暖近黑） |
| 强调色 | `#f54e00`（品牌橙） |
| 错误色 | `#cf2d56`（暖深红） |
| 边框色 | `oklab(0.263084 -0.00230259 0.0124794 / 0.1)` |
| 标题字体 | CursorGothic（72px 时字间距 −2.16px） |
| 正文字体 | jjannon（OpenType `"cswh"` 花饰变体） |
| 代码字体 | berkeleyMono |
