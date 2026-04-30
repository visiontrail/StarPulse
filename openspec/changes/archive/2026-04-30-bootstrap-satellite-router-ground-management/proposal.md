## Why

星座网络中的星载路由设备需要由地面管理系统（Star-Pulse星脉）进行集中、标准化和可扩展的管理。当前阶段需要先建立可维护的后端工程、NETCONF Client 接入、数据库持久化、异步任务、AI Native 扩展入口和容器化运行基础，避免后续功能以脚本堆叠方式增长。

## What Changes

- 建立以 Python 为主的后端工程骨架，采用模块化单体并预留微服务演进空间。
- 引入 HTTP API 服务层、配置管理、日志、健康检查和统一服务启动入口。
- 建立设备管理、连接管理、NETCONF Client 封装、数据存储、任务执行、AI Native 扩展等基础模块边界。
- 选择并接入开源 NETCONF Client 生态，采用 `ncclient` 作为底层协议能力。
- 选择 PostgreSQL 作为主数据库，允许本地开发或测试使用 SQLite。
- 建立数据库连接配置、迁移、模型定义和 Repository 层基础结构。
- 引入 Celery 作为异步任务框架，RabbitMQ 作为默认开源 Broker，并提供示例任务链路。
- 支持 Docker 容器化运行，并提供本地 Docker Compose 编排 API 服务、PostgreSQL、RabbitMQ 和 Celery Worker。
- 建立统一脚本入口，支持开发环境初始化、依赖安装、启动、测试、格式化、静态检查、镜像构建和本地完整环境运行。
- 预留 Claude Agent SDK 等 AI Native 能力的模块入口，但不实现复杂 Agent 行为。
- 明确第一阶段完全基于开源、可自托管、无商业绑定的软件组件。

## Capabilities

### New Capabilities

- `ground-management-platform-foundation`: 星载路由地面管理系统第一阶段基础架构能力，覆盖后端工程骨架、NETCONF Client 接入框架、设备管理基础模型、数据库存储基础、Celery/RabbitMQ 异步任务基础、AI Native 扩展入口、健康检查、日志、配置和容器化运行。

### Modified Capabilities

无。

## Impact

- 新增 `backend/` 后端工程目录及 Python 项目配置。
- 新增 API、core、devices、netconf、storage、tasks、ai、common 等模块边界。
- 新增数据库迁移和 Repository 层基础结构。
- 新增 Celery Worker 入口、RabbitMQ Broker 配置和示例任务。
- 新增 Dockerfile、Docker Compose、本地开发脚本和基础测试。
- 引入开源依赖，包括但不限于 Python Web 框架、`ncclient`、数据库 ORM/迁移工具、PostgreSQL 驱动、Celery、RabbitMQ 客户端和测试/质量工具。
- 不引入商业数据库、商业消息队列、商业网关或依赖商业授权的软件组件。
