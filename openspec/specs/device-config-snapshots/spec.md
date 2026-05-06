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

### Requirement: 基线快照语义
系统 MUST 支持将成功采集的配置快照用于设备接入基线和配置变更执行前基线判断。

#### Scenario: 标记当前基线
- **WHEN** 某设备某 datastore 成功采集配置快照
- **THEN** 系统 MUST 能够将最新成功快照作为该设备该 datastore 的当前基线用于接入完成和变更预检

#### Scenario: 查询基线摘要
- **WHEN** 调用方查询设备画像、变更预检或变更详情
- **THEN** 系统 MUST 返回基线快照标识、datastore、content_digest、采集时间和安全差异摘要

#### Scenario: 基线不存在
- **WHEN** 设备指定 datastore 不存在成功快照
- **THEN** 系统 MUST 在设备接入摘要和变更预检中返回缺少基线的阻塞原因

### Requirement: 快照新鲜度检查
系统 MUST 支持对配置快照进行新鲜度判断，用于变更预检和直接执行安全边界。

#### Scenario: 快照仍然新鲜
- **WHEN** 最后成功快照的采集时间未超过系统配置的新鲜度阈值
- **THEN** 系统 MUST 将该快照标记为可用于预检的基线

#### Scenario: 快照已经过旧
- **WHEN** 最后成功快照的采集时间超过系统配置的新鲜度阈值
- **THEN** 系统 MUST 在预检摘要中返回 stale baseline 状态、最后采集时间和建议刷新动作

#### Scenario: 新鲜度配置
- **WHEN** 运行环境设置基线快照新鲜度阈值
- **THEN** 系统 MUST 使用该配置判断预检和直接执行是否允许继续

### Requirement: 受控快照比较摘要
系统 MUST 为变更预检和执行后验证提供不泄漏完整配置正文的快照比较摘要。

#### Scenario: 生成执行前比较摘要
- **WHEN** 系统对变更载荷和基线快照生成预检摘要
- **THEN** 系统 MUST 返回安全比较字段，例如基线 digest、载荷 digest、datastore、行数或长度摘要和是否存在可判断变化

#### Scenario: 生成执行后比较摘要
- **WHEN** 配置变更执行后成功采集 post-change 快照
- **THEN** 系统 MUST 比较基线快照和 post-change 快照，并返回 digest 是否变化、上一份快照标识和 post-change 快照标识

#### Scenario: 比较摘要脱敏
- **WHEN** 快照摘要、比较摘要或错误上下文包含敏感字段
- **THEN** 系统 MUST 对密码、token、密钥、私钥、设备凭据和未经控制的完整配置正文进行脱敏或排除

### Requirement: 快照任务用户归属
系统 MUST 在配置快照任务和任务查询结果中保留安全的发起用户归属信息。

#### Scenario: 查询快照任务归属
- **WHEN** 具备任务读取权限的用户查询配置采集任务
- **THEN** 系统 MUST 返回任务状态、设备、datastore 和发起用户摘要

#### Scenario: 隐藏敏感用户信息
- **WHEN** API 返回配置采集任务或快照摘要
- **THEN** 系统 MUST NOT 返回用户密码哈希、Token、设备凭据或未经控制的完整配置正文

### Requirement: 回滚目标资格判定
系统 MUST 为每份成功配置快照判定其是否可作为回滚目标，并在快照查询响应中暴露资格字段，使前端能够据此启用或禁用回滚入口。

#### Scenario: 持久化规范化内容
- **WHEN** 系统采集成功配置快照
- **THEN** 系统 MUST 持久化用于派生 NETCONF `edit-config` 载荷的规范化配置内容，或在持久化失败时明确标记该快照不可作为回滚目标

#### Scenario: 查询资格字段
- **WHEN** 调用方查询设备配置快照列表或单个快照详情
- **THEN** 系统 MUST 返回 `rollback_eligible` 布尔字段及不可回滚时的阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`，且不得返回完整规范化内容

#### Scenario: 历史快照向后兼容
- **WHEN** 历史快照创建于本次变更之前且未持久化规范化内容
- **THEN** 系统 MUST 将其 `rollback_eligible` 标记为 false，并附带阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`

### Requirement: 回滚载荷派生服务边界
系统 MUST 提供仅供变更控制服务在事务内调用的快照规范化内容读取与载荷派生入口，并对外保持只读语义。

#### Scenario: 仅变更控制可调用
- **WHEN** 上层模块需要从快照派生 `edit-config` 载荷
- **THEN** 系统 MUST 仅暴露给变更控制服务的内部接口，不得通过对外 API、任务 metadata、审计 metadata 或日志返回派生载荷的完整原始内容

#### Scenario: 派生不污染快照状态
- **WHEN** 系统执行回滚载荷派生
- **THEN** 系统 MUST NOT 修改、删除、覆盖或重新写入目标快照、其来源任务或其他历史快照记录

#### Scenario: 派生失败不创建变更
- **WHEN** 派生过程因规范化内容缺失、长度超限或受控错误失败
- **THEN** 系统 MUST 返回标准错误码、阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`，并不得创建变更申请或执行任务

