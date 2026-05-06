# device-access-capability-discovery Specification

## Purpose
TBD - created by archiving change device-access-capability-discovery. Update Purpose after archive.
## Requirements
### Requirement: 设备接入领域模型
系统 MUST 为设备接入建立明确领域对象，至少包含设备、连接配置、认证信息引用、设备状态、最后发现结果、最后配置快照和关联任务状态，并能向查询方返回可直接用于运维查看的当前画像。

#### Scenario: 创建设备接入信息
- **WHEN** 调用方提交设备名称、地址、NETCONF 端口、用户名和认证信息
- **THEN** 系统 MUST 创建设备、连接配置和认证信息引用，并将设备置为可用于连接测试的初始状态

#### Scenario: 查询设备详情
- **WHEN** 调用方查询单个设备详情
- **THEN** 系统 MUST 返回设备基础信息、连接配置摘要、设备状态、最后发现结果摘要、最后配置快照摘要和最近任务摘要

#### Scenario: 查询设备当前画像
- **WHEN** 调用方查询单个设备的当前画像
- **THEN** 系统 MUST 返回连接状态、capabilities、system_info、最后配置快照、最近任务和可展示的安全摘要

#### Scenario: 设备不存在
- **WHEN** 调用方对不存在的设备提交连接测试或能力发现
- **THEN** 系统 MUST 返回标准资源不存在错误，并且不得投递异步任务

### Requirement: 认证信息安全边界
系统 MUST 防止密码、密钥或私钥明文散落在设备表、任务表、发现结果、API 读取响应和日志中。

#### Scenario: 保存认证信息
- **WHEN** 调用方在创建设备或更新连接配置时提交密码
- **THEN** 系统 MUST 只在受控凭据存储边界保存认证材料，并在业务表中保存认证信息引用

#### Scenario: 返回设备连接配置
- **WHEN** 调用方查询设备列表或设备详情
- **THEN** 系统 MUST 返回主机、端口、协议、用户名和认证信息引用状态，不得返回密码或密钥明文

#### Scenario: 写入任务和日志
- **WHEN** 系统创建任务、更新任务 metadata 或输出 API 与 Worker 日志
- **THEN** 系统 MUST 对密码、密钥、私钥和解析后的凭据值进行脱敏或排除

### Requirement: NETCONF 连接测试
系统 MUST 提供针对已登记设备的 NETCONF 连接测试业务动作，并通过异步任务执行真实连接验证。

#### Scenario: 投递连接测试任务
- **WHEN** 调用方请求对某个设备执行连接测试
- **THEN** 系统 MUST 创建任务状态记录、投递 Celery 任务，并返回可查询的任务标识

#### Scenario: 连接测试成功
- **WHEN** Worker 使用设备连接配置和认证信息成功建立 NETCONF session
- **THEN** 系统 MUST 将任务状态更新为成功，并将设备状态更新为在线或等价可连接状态

#### Scenario: 连接测试失败
- **WHEN** Worker 因设备不可达、连接超时、认证失败或 NETCONF 协议错误导致连接测试失败
- **THEN** 系统 MUST 将任务状态更新为失败，并记录标准错误码、可展示错误消息和脱敏排障上下文

### Requirement: NETCONF 能力发现
系统 MUST 提供针对已登记设备的 NETCONF 能力发现业务动作，读取 server capabilities，并在设备支持时记录基础系统信息。

#### Scenario: 投递能力发现任务
- **WHEN** 调用方请求对某个设备执行能力发现
- **THEN** 系统 MUST 创建任务状态记录、投递 Celery 任务，并返回可查询的任务标识

#### Scenario: 能力发现成功
- **WHEN** Worker 成功读取 NETCONF server capabilities
- **THEN** 系统 MUST 持久化最后发现结果，包含设备标识、任务标识、capabilities、发现时间和结果摘要

#### Scenario: 记录基础系统信息
- **WHEN** NETCONF mock Server 或真实设备返回基础系统信息
- **THEN** 系统 MUST 将基础系统信息作为最后发现结果的一部分进行结构化保存

#### Scenario: 能力发现失败
- **WHEN** Worker 在能力发现过程中遇到连接、认证、超时或协议错误
- **THEN** 系统 MUST 保留上一次成功发现结果，并在当前任务中记录失败状态和标准错误

### Requirement: 异步任务状态闭环
系统 MUST 通过 API、数据库和 Celery Worker 形成可查询的异步任务闭环。

#### Scenario: 查询排队任务
- **WHEN** API 已创建任务但 Worker 尚未开始执行
- **THEN** 任务查询接口 MUST 返回 `queued` 状态、任务类型、关联设备和创建时间

#### Scenario: 查询运行中任务
- **WHEN** Worker 开始执行连接测试或能力发现
- **THEN** 任务查询接口 MUST 返回 `running` 状态和最近更新时间

#### Scenario: 查询成功任务
- **WHEN** Worker 成功完成连接测试或能力发现
- **THEN** 任务查询接口 MUST 返回 `succeeded` 状态、完成时间和安全的结果摘要

#### Scenario: 查询失败任务
- **WHEN** Worker 执行失败
- **THEN** 任务查询接口 MUST 返回 `failed` 状态、标准错误码、可展示错误消息和脱敏上下文

### Requirement: 标准错误模型
系统 MUST 将设备接入和 NETCONF 能力发现失败归一化为稳定错误码。

#### Scenario: 设备不可达
- **WHEN** Worker 无法连接设备地址或端口
- **THEN** 系统 MUST 记录 `DEVICE_UNREACHABLE` 错误码

#### Scenario: 连接超时
- **WHEN** NETCONF 连接或能力读取超过配置的超时时间
- **THEN** 系统 MUST 记录 `CONNECTION_TIMEOUT` 错误码

#### Scenario: 认证失败
- **WHEN** 设备拒绝用户名、密码、密钥或认证方式
- **THEN** 系统 MUST 记录 `AUTH_FAILED` 错误码

#### Scenario: NETCONF 协议错误
- **WHEN** NETCONF session 建立后发生 RPC、hello、capability 或协议解析错误
- **THEN** 系统 MUST 记录 `NETCONF_PROTOCOL_ERROR` 错误码

#### Scenario: 凭据不可用
- **WHEN** Worker 无法通过认证信息引用解析连接所需凭据
- **THEN** 系统 MUST 记录 `CREDENTIAL_UNAVAILABLE` 错误码

### Requirement: 结构化日志与可观测性
系统 MUST 为 API 投递、Worker 执行和 NETCONF 调用输出结构化日志字段。

#### Scenario: 输出任务执行日志
- **WHEN** 系统投递、开始、完成或失败一个连接测试或能力发现任务
- **THEN** 日志 MUST 包含 `action`、`task_id`、`device_id`、`status` 和 `duration_ms` 字段

#### Scenario: 输出设备连接日志
- **WHEN** Worker 执行 NETCONF 连接测试或能力发现
- **THEN** 日志 MUST 包含脱敏后的 `host`、`port`、`protocol` 和 `error_code` 字段

#### Scenario: 避免敏感信息泄漏
- **WHEN** 系统输出 API、服务层、Worker 或 NETCONF 适配层日志
- **THEN** 日志 MUST 不包含密码、密钥、私钥或解析后的认证材料

### Requirement: 接入工作流复用设备任务边界
系统 MUST 让设备接入向导复用现有连接测试、能力发现和任务状态边界，而不是绕过任务服务直接执行设备访问。

#### Scenario: 接入向导投递连接测试
- **WHEN** 用户在接入向导中请求连接测试
- **THEN** 系统 MUST 通过现有连接测试任务创建、投递和查询机制执行测试，并返回任务标识和安全状态摘要

#### Scenario: 接入向导投递能力发现
- **WHEN** 用户在接入向导中请求能力发现
- **THEN** 系统 MUST 通过现有能力发现任务创建、投递和查询机制执行发现，并在成功后更新最后发现结果

#### Scenario: 接入任务归属
- **WHEN** 接入向导投递连接测试或能力发现任务
- **THEN** 系统 MUST 在任务状态或审计上下文中保留安全的发起用户归属信息

### Requirement: 设备画像接入摘要
系统 MUST 在设备详情或画像响应中提供用于前端接入向导和变更入口的安全接入摘要。

#### Scenario: 返回接入摘要
- **WHEN** 调用方查询设备当前画像
- **THEN** 系统 MUST 返回连接测试状态、能力发现状态、最后基线快照摘要、是否准备好进入变更流程和阻塞原因

#### Scenario: 接入摘要隐藏敏感信息
- **WHEN** API 返回接入摘要
- **THEN** 系统 MUST NOT 返回密码、密钥、私钥、解析后的凭据、access token、refresh token 或未经控制的完整配置正文

#### Scenario: 接入摘要反映最近任务
- **WHEN** 设备存在运行中或失败的连接测试、能力发现或基线快照任务
- **THEN** 系统 MUST 在接入摘要中反映最近任务状态、标准错误码和可展示错误消息

### Requirement: NETCONF mock Server 测试策略
系统 MUST 支持通过远端 NETCONF mock Server 验证连接测试与能力发现闭环。

#### Scenario: 使用默认 mock Server 参数
- **WHEN** 开发者启用 NETCONF 集成测试但未覆盖测试目标
- **THEN** 测试配置 MUST 使用主机 `172.16.5.38`、端口 `830`、用户名 `netconf` 和密码 `netconf`

#### Scenario: 读取 mock Server capabilities
- **WHEN** 集成测试连接到远端 NETCONF mock Server
- **THEN** 系统 MUST 成功读取 server capabilities，并验证返回结果包含 NETCONF 基础能力

#### Scenario: mock Server 不可用
- **WHEN** 集成测试未启用或远端 mock Server 不可达
- **THEN** 测试套件 MUST 能够跳过远端集成测试，并保留 fake client 单元测试覆盖

