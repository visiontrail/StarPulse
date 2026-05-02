# device-config-snapshots Specification

## Purpose
TBD - created by syncing change device-readonly-ops-loop-mvp. Update Purpose after archive.
## Requirements
### Requirement: NETCONF 只读配置读取
系统 MUST 提供针对已登记设备的 NETCONF `get-config` 只读配置读取能力，并通过现有 NETCONF Client 抽象执行，不得执行配置编辑、提交或回滚操作。

#### Scenario: 投递配置读取任务
- **WHEN** 调用方请求对某个设备读取配置并提交 datastore
- **THEN** 系统 MUST 创建可查询的异步任务并记录设备、任务类型和 datastore

#### Scenario: 执行 get-config
- **WHEN** Worker 执行配置读取任务
- **THEN** 系统 MUST 使用设备连接配置和认证信息发起 NETCONF `get-config` 操作，并只读取请求的 datastore

#### Scenario: 拒绝不支持的 datastore
- **WHEN** 调用方提交系统不支持的 datastore
- **THEN** 系统 MUST 返回标准参数错误，并且不得投递异步任务

#### Scenario: 禁止写操作
- **WHEN** 配置读取任务运行
- **THEN** 系统 MUST NOT 调用 `edit-config`、`commit`、`discard-changes`、`copy-config` 或等价写入设备配置的 NETCONF 操作

### Requirement: 设备配置快照持久化
系统 MUST 在配置读取成功后保存设备配置快照，至少包含设备、来源任务、datastore、配置内容摘要、采集时间、差异摘要和安全结果摘要。

#### Scenario: 保存配置快照
- **WHEN** Worker 成功读取设备配置
- **THEN** 系统 MUST 持久化配置快照，并记录 `source_task_id`、`datastore`、`content_digest`、`collected_at`、`diff_summary` 和 `summary`

#### Scenario: 生成内容摘要
- **WHEN** 系统保存配置快照
- **THEN** 系统 MUST 基于规范化后的配置内容生成稳定摘要，用于判断配置是否变化

#### Scenario: 生成差异摘要
- **WHEN** 同一设备和 datastore 存在上一份配置快照
- **THEN** 系统 MUST 生成差异摘要，标明是否变化以及参与比较的上一份快照

#### Scenario: 首份快照
- **WHEN** 同一设备和 datastore 不存在上一份配置快照
- **THEN** 系统 MUST 保存快照，并在差异摘要中标明没有可比较的上一份快照

#### Scenario: 避免敏感信息泄漏
- **WHEN** 系统写入任务 metadata、任务结果、API 响应或日志
- **THEN** 系统 MUST NOT 暴露密码、密钥、私钥、解析后的认证材料或未经控制的完整配置正文

### Requirement: 配置快照任务闭环
系统 MUST 将配置读取纳入现有异步任务闭环，使调用方可以查询排队、运行、成功和失败状态。

#### Scenario: 查询配置读取排队任务
- **WHEN** API 已创建配置读取任务但 Worker 尚未开始执行
- **THEN** 任务查询接口 MUST 返回 `queued` 状态、任务类型、关联设备、datastore 和创建时间

#### Scenario: 查询配置读取运行中任务
- **WHEN** Worker 开始执行配置读取任务
- **THEN** 任务查询接口 MUST 返回 `running` 状态和最近更新时间

#### Scenario: 查询配置读取成功任务
- **WHEN** Worker 成功保存配置快照
- **THEN** 任务查询接口 MUST 返回 `succeeded` 状态、完成时间、快照标识和安全结果摘要

#### Scenario: 查询配置读取失败任务
- **WHEN** Worker 因设备不可达、认证失败、超时、协议错误或凭据不可用导致配置读取失败
- **THEN** 任务查询接口 MUST 返回 `failed` 状态、标准错误码、可展示错误消息和脱敏上下文

### Requirement: 配置快照查询 API
系统 MUST 提供面向运维查询的配置快照 API，用于查看设备快照列表、最后快照和单个快照摘要。

#### Scenario: 查询设备配置快照列表
- **WHEN** 调用方查询某个设备的配置快照列表
- **THEN** 系统 MUST 返回按采集时间倒序排列的快照摘要，并包含 datastore、内容摘要、采集时间和差异摘要

#### Scenario: 查询最后配置快照
- **WHEN** 调用方查询设备当前画像或快照摘要
- **THEN** 系统 MUST 返回该设备最近一次成功采集的配置快照摘要

#### Scenario: 设备不存在
- **WHEN** 调用方查询不存在设备的配置快照
- **THEN** 系统 MUST 返回标准资源不存在错误

#### Scenario: 限制快照列表规模
- **WHEN** 调用方查询设备配置快照列表
- **THEN** 系统 MUST 支持限制返回数量，并避免默认返回无限历史数据

### Requirement: 配置读取可观测性和测试
系统 MUST 为配置读取任务提供结构化日志、脱敏校验和分层测试覆盖。

#### Scenario: 输出配置读取日志
- **WHEN** 系统投递、开始、完成或失败一个配置读取任务
- **THEN** 日志 MUST 包含 `action`、`task_id`、`device_id`、`datastore`、`status`、`error_code` 和 `duration_ms` 字段

#### Scenario: 使用 fake client 测试
- **WHEN** 测试 NETCONF 配置读取服务
- **THEN** 测试套件 MUST 能够使用 fake client 验证成功、失败、摘要和差异摘要行为

#### Scenario: 使用 mock Server 集成测试
- **WHEN** 开发者启用 NETCONF 集成测试
- **THEN** 测试套件 MUST 能够对远端 NETCONF mock Server 执行只读 `get-config` 验证，并在未启用或不可达时跳过

### Requirement: 配置快照 API 鉴权
系统 MUST 对设备配置快照查询和采集 API 应用认证和权限控制。

#### Scenario: 未登录查询快照
- **WHEN** 未认证调用方请求设备配置快照列表或最后快照
- **THEN** 系统 MUST 返回未认证响应

#### Scenario: viewer 查询快照
- **WHEN** viewer 请求其权限允许的设备配置快照摘要
- **THEN** 系统 MUST 返回快照摘要列表，并继续隐藏完整配置正文和敏感认证材料

#### Scenario: 无权限查询快照
- **WHEN** 已认证但缺少快照读取权限的用户请求配置快照 API
- **THEN** 系统 MUST 返回禁止访问响应

### Requirement: 配置采集权限控制
系统 MUST 仅允许具备配置采集权限的用户触发 NETCONF 只读配置采集任务。

#### Scenario: operator 触发配置采集
- **WHEN** operator 对已登记且连接配置完整的设备触发配置采集
- **THEN** 系统 MUST 创建配置采集任务，并关联发起用户用于审计和任务追踪

#### Scenario: viewer 触发配置采集
- **WHEN** viewer 尝试触发配置采集
- **THEN** 系统 MUST 返回禁止访问响应，并且不得投递配置采集任务

#### Scenario: 配置采集失败审计
- **WHEN** 配置采集请求因权限不足、参数错误或设备状态不满足而失败
- **THEN** 系统 MUST 记录失败操作审计日志，并且不得泄露设备凭据或完整配置正文

### Requirement: 快照任务用户归属
系统 MUST 在配置快照任务和任务查询结果中保留安全的发起用户归属信息。

#### Scenario: 查询快照任务归属
- **WHEN** 具备任务读取权限的用户查询配置采集任务
- **THEN** 系统 MUST 返回任务状态、设备、datastore 和发起用户摘要

#### Scenario: 隐藏敏感用户信息
- **WHEN** API 返回配置采集任务或快照摘要
- **THEN** 系统 MUST NOT 返回用户密码哈希、Token、设备凭据或未经控制的完整配置正文

