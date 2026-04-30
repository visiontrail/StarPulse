# ground-management-platform-foundation Specification

## Purpose
TBD - created by archiving change bootstrap-satellite-router-ground-management. Update Purpose after archive.
## Requirements
### Requirement: Python 后端工程骨架
系统 MUST 提供以 Python 为主要语言的后端工程骨架，并在 `backend/` 下形成清晰的模块化目录结构，至少包含 API、核心配置、设备管理、NETCONF、存储、任务、AI 扩展和通用能力模块。

#### Scenario: 创建后端基础目录
- **WHEN** 开发者查看 `backend/app/` 目录
- **THEN** 系统存在 `api`、`core`、`devices`、`netconf`、`storage`、`tasks`、`ai`、`common` 等模块目录或等价模块边界

#### Scenario: 安装 Python 依赖
- **WHEN** 开发者执行项目提供的依赖安装入口
- **THEN** 系统能够在项目级 Python 虚拟环境中安装后端运行、测试和质量检查所需依赖

### Requirement: HTTP API 服务基础
系统 MUST 提供 HTTP API 服务入口，用于承载后续前端、管理终端、自动化系统和 AI Native 模块调用。

#### Scenario: 启动 API 服务
- **WHEN** 开发者通过本地开发脚本或 Python 命令启动 API 服务
- **THEN** API 服务能够监听配置指定的地址和端口

#### Scenario: 查询健康检查
- **WHEN** 调用方请求健康检查接口
- **THEN** 系统返回服务存活状态，并包含数据库或关键依赖的基础可用性信息

### Requirement: 配置和日志基础
系统 MUST 提供统一配置管理和结构化日志基础，支持通过环境变量或配置文件切换运行环境、数据库、Broker、日志级别和服务端口。

#### Scenario: 使用环境变量覆盖配置
- **WHEN** 运行环境设置数据库连接、RabbitMQ 地址或日志级别相关环境变量
- **THEN** 系统启动时使用这些环境变量覆盖默认配置

#### Scenario: 输出服务日志
- **WHEN** API 服务或 Worker 处理请求、任务或启动流程
- **THEN** 系统输出包含时间、级别、模块和消息的日志记录

### Requirement: 设备管理基础模型
系统 MUST 提供设备管理基础模型和服务边界，用于保存星载路由设备的基础信息、连接配置、分组信息和状态扩展字段。

#### Scenario: 保存设备信息
- **WHEN** 设备管理模块接收新增设备的数据
- **THEN** 系统通过 Repository 层持久化设备基础信息和连接配置

#### Scenario: 查询设备信息
- **WHEN** API 或服务层请求设备列表或单个设备详情
- **THEN** 系统从 Repository 层读取设备基础信息并返回结构化数据

### Requirement: NETCONF Client 接入框架
系统 MUST 提供 NETCONF Client 接入框架，并通过适配层封装开源 `ncclient` 或等价开源 NETCONF Client 库。

#### Scenario: 创建 NETCONF 客户端抽象
- **WHEN** 上层服务请求连接指定设备
- **THEN** NETCONF 模块通过统一客户端接口处理连接参数，而不要求上层服务直接调用第三方库 API

#### Scenario: 执行示例 NETCONF 操作
- **WHEN** NETCONF 服务接收到基础连接验证或能力查询请求
- **THEN** 系统通过客户端适配层发起对应 NETCONF 操作，并返回成功结果或标准化错误

### Requirement: 数据库存储基础
系统 MUST 使用开源数据库作为主存储，默认支持 PostgreSQL，并允许在本地轻量开发或测试环境中使用 SQLite。

#### Scenario: 使用 PostgreSQL 运行
- **WHEN** 配置中指定 PostgreSQL 数据库连接
- **THEN** 系统通过数据库连接模块连接 PostgreSQL 并执行模型访问

#### Scenario: 使用 SQLite 测试
- **WHEN** 测试环境配置 SQLite 数据库连接
- **THEN** 系统能够使用 SQLite 执行基础 Repository 测试

### Requirement: 数据库迁移和 Repository 层
系统 MUST 提供数据库迁移基础结构、模型定义方式和 Repository 层，避免业务模块直接依赖底层数据库实现。

#### Scenario: 执行数据库迁移
- **WHEN** 开发者运行数据库迁移入口
- **THEN** 系统创建或更新设备、连接配置、系统配置和任务状态等基础表结构

#### Scenario: 业务模块访问数据
- **WHEN** 设备、任务或配置服务需要读取或写入数据
- **THEN** 服务通过 Repository 接口访问数据，而不是直接在业务逻辑中拼接数据库操作

### Requirement: Celery 异步任务框架
系统 MUST 引入 Celery 作为异步任务框架，并使用 RabbitMQ 作为默认开源 Broker。

#### Scenario: 启动 Worker
- **WHEN** 开发者通过脚本或容器命令启动 Celery Worker
- **THEN** Worker 连接 RabbitMQ 并等待消费任务

#### Scenario: 投递示例任务
- **WHEN** API 服务触发示例后台任务
- **THEN** 系统将任务投递到 Celery 队列，并由 Worker 消费执行

### Requirement: 任务状态基础
系统 MUST 为后续设备查询、配置操作、自动化任务和异步执行建立任务状态基础结构。

#### Scenario: 创建任务状态记录
- **WHEN** API 服务提交后台任务
- **THEN** 系统创建包含任务标识、类型、状态、创建时间和扩展元数据的任务状态记录

#### Scenario: 查询任务状态
- **WHEN** 调用方根据任务标识查询任务
- **THEN** 系统返回任务当前状态和基础元数据

### Requirement: AI Native 扩展入口
系统 MUST 建立 AI Native 扩展模块入口，预留 Claude Agent SDK 或等价 AI Agent 能力的集成空间，但第一阶段 MUST NOT 实现复杂 Agent 行为。

#### Scenario: 查看 AI 模块边界
- **WHEN** 开发者查看 `backend/app/ai/` 模块
- **THEN** 系统存在 agents、tools、services 或等价扩展边界

#### Scenario: 第一阶段不执行复杂 Agent 行为
- **WHEN** 系统运行第一阶段基础服务
- **THEN** AI 模块不执行自动化配置下发、审批决策或复杂运维编排

### Requirement: 容器化本地运行环境
系统 MUST 支持通过 Docker 容器化运行，并在本地 Docker Compose 中编排 API 服务、PostgreSQL、RabbitMQ 和 Celery Worker。

#### Scenario: 启动完整本地环境
- **WHEN** 开发者执行本地完整环境启动入口
- **THEN** Docker Compose 启动 API 服务、PostgreSQL、RabbitMQ 和 Celery Worker

#### Scenario: 构建 API 镜像
- **WHEN** 开发者执行镜像构建入口
- **THEN** 系统能够构建包含后端服务依赖和启动入口的 Docker 镜像

### Requirement: 本地开发测试和发布入口
系统 MUST 提供统一脚本入口，支持初始化开发环境、创建虚拟环境、安装依赖、启动服务、启动依赖服务、执行测试、格式化、静态检查、构建镜像和本地发布流程。

#### Scenario: 初始化开发环境
- **WHEN** 开发者执行本地初始化脚本
- **THEN** 系统创建或复用项目级虚拟环境并准备后端开发依赖

#### Scenario: 执行质量检查
- **WHEN** 开发者执行测试、格式化或静态检查脚本
- **THEN** 系统运行对应工具并返回成功或失败结果

### Requirement: 动态扩展架构基础
系统 MUST 以无状态 API、外部数据库、外部 Broker 和独立 Worker 进程为基础，为后续微服务拆分、横向扩展和 Kubernetes 部署预留结构。

#### Scenario: API 与 Worker 独立运行
- **WHEN** 本地环境启动 API 服务和 Celery Worker
- **THEN** 两者作为独立进程或容器运行，并通过 RabbitMQ 传递任务

#### Scenario: 状态不保存在 API 进程内
- **WHEN** API 服务处理设备、任务或系统配置数据
- **THEN** 系统将持久状态保存到外部数据库或 Broker，而不是仅保存在 API 进程内存中

### Requirement: 开源软件约束
系统 MUST 完全基于开源、可自托管、无商业绑定的软件组件构建第一阶段基础架构。

#### Scenario: 选择基础依赖
- **WHEN** 实现阶段选择数据库、Broker、Web 框架、NETCONF Client、迁移工具或测试工具
- **THEN** 所选组件为开源软件，并支持本地部署、私有化部署和容器化运行

#### Scenario: 避免商业绑定
- **WHEN** 系统提供默认运行配置
- **THEN** 默认配置不依赖商业数据库、商业消息队列、商业网关或云厂商专有托管服务

