## Why

当前后端已经具备设备、NETCONF、任务和存储的基础骨架，但还缺少一条可运行、可观测、可测试的真实业务闭环。优先打通“设备接入到能力发现”可以验证设备模型、Repository、服务层、Celery、RabbitMQ、数据库和 NETCONF 适配层是否能协同工作，并为后续配置下发和运维自动化建立稳定基础。

## What Changes

- 补齐设备接入领域模型，明确设备、连接配置、认证信息、设备状态、最后发现结果等对象边界。
- 引入安全的认证信息引用机制，密码和密钥不得明文散落在设备、任务或业务结果表中。
- 新增设备连接测试与 NETCONF 能力发现业务动作，读取 server capabilities 或基础系统信息。
- 新增 API 投递异步任务、Celery 执行任务、API 查询任务状态的完整闭环。
- 标准化连接超时、认证失败、设备不可达、NETCONF 协议错误等失败原因，形成统一错误码、错误消息和日志字段。
- 建立远端 NETCONF mock Server 集成测试策略，默认目标为 `172.16.5.38:830`，用户名 `netconf`，密码 `netconf`。
- 第一阶段不做设备配置下发、配置变更审批、复杂编排或 AI 自动运维决策。

## Capabilities

### New Capabilities

- `device-access-capability-discovery`: 覆盖设备接入模型、NETCONF 连接测试、能力发现、异步任务状态闭环、标准错误模型、结构化日志和 mock Server 测试策略。

### Modified Capabilities

- 无。

## Impact

- 影响后端 `backend/app/devices/`、`backend/app/netconf/`、`backend/app/tasks/`、`backend/app/storage/`、`backend/app/api/` 和 `backend/tests/`。
- 需要新增或调整数据库模型、Alembic 迁移、Repository、服务层、API schema 和 Celery task。
- 需要在配置中补充 NETCONF 默认超时、任务队列、mock Server 集成测试开关和日志字段约定。
- 运行依赖继续使用现有开源技术栈：FastAPI、SQLAlchemy、Alembic、Celery、RabbitMQ、PostgreSQL 或 SQLite、ncclient。
