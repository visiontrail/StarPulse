## Context

项目当前后端已经提供 FastAPI API、SQLAlchemy/Alembic 存储、设备 Repository、NETCONF Client 抽象、Celery/RabbitMQ 任务框架和基础测试，但设备接入仍停留在基础 CRUD 与示例任务阶段。第一条真实闭环需要从“登记设备连接信息”推进到“异步连接测试与能力发现”，并把任务状态、失败原因、日志字段和测试策略统一起来。

本阶段的核心约束是：密码和密钥不能明文散落在设备表、任务表、发现结果或日志中；NETCONF 操作只做连接测试和能力读取，不做配置下发；异步任务必须通过现有 Celery/RabbitMQ 与数据库状态表形成可查询闭环。

## Goals / Non-Goals

**Goals:**

- 建立明确的设备接入领域模型，包括设备、连接配置、认证信息引用、设备状态、发现结果和任务状态。
- 提供 API 投递 NETCONF 连接测试与能力发现任务，并允许调用方查询任务执行状态。
- 由 Celery Worker 执行真实 NETCONF 连接测试和 server capabilities 读取。
- 将发现结果持久化为设备的最后发现结果，并同步更新设备状态。
- 为连接超时、认证失败、设备不可达、NETCONF 协议错误等场景提供统一错误码、错误消息和日志字段。
- 提供单元测试、API 测试、任务测试和远端 NETCONF mock Server 集成测试。

**Non-Goals:**

- 不实现 NETCONF 配置下发、配置回滚、候选配置编辑或提交操作。
- 不实现复杂凭据轮换、外部 KMS、Vault 或硬件密钥管理集成。
- 不实现 AI Agent 自动诊断、审批流或运维编排。
- 不实现多协议设备发现；本阶段只覆盖 NETCONF。

## Decisions

### 1. 设备模型拆成业务对象与安全对象

设备表只保存设备身份、分组、状态和扩展元数据；连接配置保存协议、地址、端口、用户名和认证信息引用；认证明文只允许进入受控的凭据存储边界，不进入任务 metadata、发现结果、日志或 API 读取响应。

备选方案是继续在连接配置中保存 `password_secret` 字段。该方案实现成本低，但字段语义容易演化成明文密码存储，也容易被任务 payload 和日志复制扩散。因此本阶段应引入 `credential_ref` 或等价引用，并通过服务层在发起 NETCONF 连接前解析为运行时凭据。

### 2. NETCONF 动作统一走服务层和客户端抽象

API 不直接调用 `ncclient`，任务也不直接拼接第三方库参数。设备服务负责读取设备与连接配置，凭据服务负责解析认证信息，NETCONF 服务负责执行连接测试和能力发现，底层继续由 `NcclientNetconfClient` 适配第三方库。

备选方案是在 Celery job 中直接完成所有数据库查询、凭据读取和 NETCONF 调用。该方案短期更快，但会让业务规则分散在任务函数中，后续配置下发、重试和审计会变得脆弱。

### 3. 连接测试和能力发现作为异步任务

`POST /api/v1/devices/{device_id}/connection-test` 和 `POST /api/v1/devices/{device_id}/capability-discovery` 创建任务状态记录并投递 Celery。任务状态至少包含 `queued`、`running`、`succeeded`、`failed`，调用方通过任务查询接口获取执行结果、标准错误和关联设备。

备选方案是连接测试同步执行。同步接口更简单，但设备不可达、超时和网络抖动会直接占用 API 请求生命周期，也无法充分验证 RabbitMQ、数据库和 Worker 闭环。

### 4. 最后发现结果独立建模

能力发现成功后，将 capabilities、基础系统信息、发现时间、来源任务和摘要写入最后发现结果。设备详情可返回发现摘要，但不得返回认证明文。失败时保留最后一次成功结果，同时任务中记录本次失败原因。

备选方案是把结果塞进 `Device.metadata`。该方案迁移少，但会把状态、审计和业务结果混在一个 JSON 字段中，不利于查询、展示和后续归档。

### 5. 错误模型使用稳定错误码

服务层对底层异常进行归一化，暴露稳定错误码，例如 `DEVICE_UNREACHABLE`、`AUTH_FAILED`、`CONNECTION_TIMEOUT`、`NETCONF_PROTOCOL_ERROR`、`CREDENTIAL_UNAVAILABLE`、`INTERNAL_ERROR`。任务失败时同时记录错误码、可展示消息和可排障上下文。

备选方案是直接把底层异常字符串写入任务结果。该方案信息多但不可控，可能泄漏主机、用户名、路径甚至凭据片段，也不利于前端和运维工具做稳定展示。

### 6. 可观测性以结构化字段为主

API 和 Worker 日志统一携带 `action`、`task_id`、`device_id`、`host`、`port`、`status`、`error_code`、`duration_ms` 等字段。日志不得输出密码、密钥、私钥、完整凭据引用解析结果或 NETCONF payload 中的敏感内容。

备选方案是只保留当前普通日志。该方案无法支撑后续批量设备接入和任务排障。

### 7. 测试分层验证

单元测试覆盖 Repository、服务层、错误映射和 NETCONF client fake；API 测试覆盖任务投递与查询；任务测试覆盖 Celery job 的直接执行；集成测试通过环境变量连接远端 NETCONF mock Server，默认目标为 `172.16.5.38:830`、用户名 `netconf`、密码 `netconf`，并允许在不可达时跳过。

备选方案是只使用 fake client。fake client 快速稳定，但无法验证 ncclient 与真实 NETCONF session 的行为差异。

## Risks / Trade-offs

- [Risk] 凭据存储第一阶段如果做得过重会拖慢闭环落地 → Mitigation: 先定义凭据服务边界和 `credential_ref`，本地开发可使用受控的应用级加密或测试凭据提供器，后续再替换为外部密钥管理。
- [Risk] 远端 mock Server 不稳定会导致 CI 抖动 → Mitigation: 集成测试默认通过环境变量启用，本地和 CI 未配置时跳过；单元测试覆盖主要分支。
- [Risk] NETCONF 设备差异导致基础系统信息读取不一致 → Mitigation: capabilities 作为必取结果，基础系统信息作为设备支持时记录的结构化补充。
- [Risk] Celery task 与数据库状态更新不一致 → Mitigation: 任务启动时先置为 `running`，成功或失败时以单次事务写入最终状态和结果；API 查询以数据库为准。
- [Risk] 错误归一化会隐藏底层细节 → Mitigation: 对外保留稳定错误码和安全消息，日志中记录脱敏后的异常类型、动作、设备和耗时。

## Migration Plan

1. 新增或调整数据库模型与迁移：设备连接配置的凭据引用、设备发现结果、任务错误与结果字段。
2. 补充 Repository 与服务层：设备查询、凭据解析、发现结果写入、任务状态更新。
3. 扩展 NETCONF 服务：连接测试、能力发现、错误归一化和 ncclient 异常映射。
4. 新增 API：设备连接测试任务投递、能力发现任务投递、任务状态查询增强。
5. 新增 Celery task：按任务类型执行连接测试或能力发现，并回写数据库状态。
6. 增加测试：单元测试、API 测试、任务测试和可选的远端 mock Server 集成测试。
7. 回滚时撤回新增 API 路由、任务类型和迁移；保留已有基础设备 CRUD 与示例任务能力。

## Open Questions

- 第一阶段凭据存储是否采用应用级加密字段、独立凭据表，还是只实现可替换的凭据服务接口并使用本地测试提供器。
- 最后发现结果是否需要保留历史版本；当前设计只要求保存最后一次成功发现结果。
- 基础系统信息的 NETCONF RPC 范围是否限定为标准 capabilities，还是需要约定特定 mock Server 的 system-state 响应。
