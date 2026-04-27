## Context

本项目需要为星座网络中的星载路由设备建立地面侧管理平台。第一阶段重点是搭建可持续演进的基础架构，而不是完成完整业务闭环。系统将作为 NETCONF Client 连接星载路由单机，并为后续设备管理、配置下发、自动化任务、AI Native 运维辅助和前端管理界面提供稳定基础。

当前仓库尚未形成后端工程骨架，也没有既有 OpenSpec 能力规格。本次设计因此采用从零建立基础框架的方式：先构建模块化单体，清晰划分 API、核心基础设施、设备、NETCONF、存储、任务、AI 和通用能力边界；后续当设备规模、任务负载或 AI 能力增加时，再按模块边界拆分为独立服务。

关键约束如下：

- 必须使用开源、可自托管、无商业绑定的软件组件。
- 主开发语言采用 Python。
- NETCONF Client 优先采用 `ncclient`。
- 主数据库采用 PostgreSQL，本地轻量开发和单元测试允许使用 SQLite。
- 异步任务框架采用 Celery，默认 Broker 采用 RabbitMQ。
- 第一阶段只实现基础框架、示例链路和扩展入口，不实现复杂业务管理、YANG 模型解析、完整 Agent 工作流或生产级 Kubernetes 配置。

## Goals / Non-Goals

**Goals:**

- 建立 `backend/` Python 后端工程结构和统一依赖管理。
- 建立 HTTP API 服务、配置、日志、健康检查和应用启动入口。
- 建立设备管理基础模型、连接配置模型、服务层和 Repository 层边界。
- 封装 NETCONF Client 基础能力，为后续设备连接、查询和配置操作提供统一接口。
- 建立 PostgreSQL/SQLite 数据库连接、模型定义、迁移工具和初始化入口。
- 建立 Celery/RabbitMQ 异步任务基础框架，并提供示例任务验证 API 到 Worker 的链路。
- 建立 AI Native 扩展模块入口，预留 Claude Agent SDK 等后续能力集成空间。
- 建立 Dockerfile、Docker Compose 和本地脚本入口，支持开发、测试、构建和完整本地运行。
- 为后续微服务拆分、横向扩展和 Kubernetes 部署保留清晰边界。

**Non-Goals:**

- 不实现完整星载路由业务管理流程。
- 不实现复杂 NETCONF 配置下发、YANG 模型解析或业务配置模板。
- 不实现完整 Claude Agent SDK 工作流、审批策略、权限边界或自动化场景编排。
- 不实现完整前端管理界面。
- 不实现多租户、复杂 RBAC、组织管理、完整审计、回滚和变更审批系统。
- 不交付生产级 Kubernetes 全量部署清单、HPA 策略或可观测性平台。
- 不引入商业数据库、商业消息队列、商业网关或依赖商业授权的软件组件。

## Decisions

### 1. 后端采用模块化单体，保留微服务演进边界

第一阶段在 `backend/app/` 下划分 `api`、`core`、`devices`、`netconf`、`storage`、`tasks`、`ai`、`common` 等模块。API 服务和 Worker 可以共享同一代码库，但通过独立启动入口运行。

理由：

- 模块化单体能降低第一阶段交付复杂度，避免过早拆分服务带来的部署和调试成本。
- 清晰模块边界让后续拆分 API 服务、NETCONF Worker、任务服务或 AI Agent 服务时具备自然迁移路径。

备选方案：

- 一开始拆成多个微服务：扩展性更强，但会放大第一阶段的 CI、部署、通信和数据一致性复杂度。
- 只写脚本式 NETCONF 工具：启动成本低，但难以扩展为平台。

### 2. API 层优先采用 Python Web 框架承载统一 HTTP 接口

API 层提供健康检查、设备基础资源和任务触发入口。具体实现可采用 FastAPI 等开源 Python Web 框架，并通过 schema 层定义请求和响应结构。

理由：

- Python 生态便于与 NETCONF、Celery、AI Agent SDK、数据分析和自动化工具集成。
- HTTP API 是未来前端、管理终端、自动化系统和 AI Agent 统一接入点。

备选方案：

- 直接使用 CLI 工具：不利于前端和自动化系统接入。
- 采用非 Python 后端：可能削弱 NETCONF 和 AI Native 生态集成效率。

### 3. NETCONF 能力通过适配层封装 `ncclient`

`netconf/client` 负责底层连接和会话管理，`netconf/services` 对上层暴露协议操作接口，`netconf/adapters` 隔离第三方库细节。

理由：

- `ncclient` 是成熟开源 NETCONF Client 库，适合作为第一阶段底层协议能力。
- 适配层可以避免设备管理和任务模块直接依赖第三方库 API，便于后续替换、扩展 Mock、增加连接池或接入厂商差异处理。

备选方案：

- 业务层直接调用 `ncclient`：实现快，但会造成协议细节外泄。
- 自研 NETCONF Client：成本高且没有必要。

### 4. 存储层采用 PostgreSQL 主存储，SQLite 用于轻量开发和测试

数据库模块提供连接配置、会话管理、模型定义、迁移脚本和 Repository 基类。生产和集成环境默认 PostgreSQL；本地轻量开发或单元测试可以通过配置切换到 SQLite。

理由：

- PostgreSQL 开源、成熟、可自托管，适合作为系统主存储。
- SQLite 能降低单元测试和轻量开发门槛。
- Repository 层能隔离业务模块与具体数据库实现。

备选方案：

- 只使用 SQLite：不适合后续并发、部署和扩展。
- 使用商业数据库或云托管专有数据库：不符合开源和私有化部署约束。

### 5. 异步任务采用 Celery + RabbitMQ

API 服务接收请求后，将耗时任务或后台任务投递到 Celery 队列；Celery Worker 从 RabbitMQ 消费并执行。第一阶段只提供示例任务或健康检查任务，验证链路可用。

理由：

- Celery 是 Python 生态成熟的开源任务框架。
- RabbitMQ 是开源、通用、可自托管的消息 Broker。
- API 与 Worker 分离有利于后续横向扩展、任务隔离和 Kubernetes 分别部署。

备选方案：

- API 进程内执行后台任务：简单但不利于扩展和稳定性。
- 采用商业队列或云厂商专有队列：不符合开源约束。
- 第一阶段仅预留抽象不落地：无法验证关键任务链路。

### 6. AI Native 只建立扩展入口

`ai/agents`、`ai/tools`、`ai/services` 只定义模块边界和占位接口，不实现复杂 Agent 行为、权限策略或审批流程。

理由：

- 先保留 Claude Agent SDK 等集成空间，避免后续 AI 能力硬接入业务层。
- 第一阶段可以避免在权限、安全和自动化执行策略尚未明确时过早实现高风险行为。

备选方案：

- 第一阶段直接实现 Agent 工作流：需求和安全边界尚不清晰，风险较高。
- 完全不建立 AI 模块：后续接入时容易破坏既有模块边界。

### 7. 部署采用 Docker Compose 起步，并预留 Kubernetes 方向

第一阶段提供 Dockerfile 和 Docker Compose，支持 API、PostgreSQL、RabbitMQ 和 Celery Worker 一键本地运行。服务进程尽量无状态，状态保存在外部数据库和 Broker 中。

理由：

- Docker Compose 适合本地开发和集成验证。
- 无状态 API 和独立 Worker 进程便于后续迁移到 Kubernetes Deployment 并独立扩容。

备选方案：

- 只支持本机进程启动：依赖环境不稳定。
- 第一阶段交付完整 Kubernetes：超出当前目标，容易引入未验证复杂度。

## Risks / Trade-offs

- [模块化单体后续拆分成本] → 通过模块目录、服务接口和 Repository 层边界降低耦合，避免跨模块直接访问内部实现。
- [第一阶段数据库模型过度设计] → 只建立设备、连接配置、系统配置、任务状态等基础模型和扩展字段，不展开完整业务表。
- [NETCONF 设备差异导致适配复杂] → 第一阶段只定义统一 Client 和 Adapter 边界，具体厂商差异和 YANG 模型处理后续独立变更实现。
- [Celery/RabbitMQ 增加本地环境复杂度] → 提供 Docker Compose 和脚本入口，保证开发者可以一键启动完整依赖。
- [AI Native 入口被误用为完整 Agent 能力] → 第一阶段仅保留模块边界、占位接口和文档说明，不实现自动执行、审批或权限策略。
- [开源依赖许可证风险] → 依赖选择时优先使用主流宽松或清晰开源许可证组件，并在后续实现阶段记录核心依赖。

## Migration Plan

1. 创建 `backend/` 工程骨架和 Python 项目配置。
2. 引入 API 服务启动入口、配置、日志和健康检查。
3. 建立存储层、迁移工具和基础模型。
4. 建立设备、NETCONF、任务和 AI 模块边界。
5. 接入 Celery/RabbitMQ 示例任务链路。
6. 增加 Dockerfile、Docker Compose 和本地脚本入口。
7. 增加基础测试、格式化和静态检查入口。
8. 在本地运行 API、数据库、Broker 和 Worker，验证健康检查、迁移和示例任务链路。

回滚策略：本次为新增基础架构变更，不迁移既有业务数据。若实现阶段出现问题，可移除新增 `backend/` 目录、容器编排文件和相关 OpenSpec 变更，不影响现有功能。

## Open Questions

- 第一阶段 API 框架是否最终固定为 FastAPI，还是允许实现阶段根据仓库约束调整为同等开源 Python Web 框架？
- 设备基础模型中的字段是否需要提前包含轨道、星座、地面站或链路拓扑标识？
- 任务状态是否第一阶段只保存在数据库，还是同时暴露 Celery 后端状态读取接口？
- AI Native 模块是否需要在第一阶段定义最小工具注册接口，还是仅保留目录和服务占位？
