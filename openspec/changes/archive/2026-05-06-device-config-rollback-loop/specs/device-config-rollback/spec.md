## ADDED Requirements

### Requirement: 回滚目标快照资格
系统 MUST 仅允许将满足可恢复条件的成功配置快照作为回滚目标，并在回滚发起前校验目标快照与目标设备、datastore 的匹配关系。

#### Scenario: 合法回滚目标
- **WHEN** approver 或 admin 选择目标快照对某设备的某 datastore 发起回滚
- **THEN** 系统 MUST 校验该快照来自同一设备和 datastore、来源任务为成功状态、且持久化了用于受控 `edit-config` 派生的规范化内容

#### Scenario: 不可恢复目标
- **WHEN** 调用方选择仅保存了 digest 或受控摘要而未保存规范化内容的历史快照作为回滚目标
- **THEN** 系统 MUST 拒绝创建回滚申请，返回阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`，并不得创建变更申请或执行任务

#### Scenario: 设备或 datastore 不匹配
- **WHEN** 调用方选择属于其他设备或其他 datastore 的快照作为回滚目标
- **THEN** 系统 MUST 拒绝请求并返回标准参数错误，不得创建变更申请

#### Scenario: 与当前状态无差异
- **WHEN** 目标快照内容摘要与该设备 datastore 当前最新成功快照内容摘要一致
- **THEN** 系统 MUST 返回阻塞码 `ROLLBACK_NO_DIVERGENCE` 并允许调用方刷新或选择其他目标，不得创建回滚执行任务

### Requirement: 回滚载荷服务端派生
系统 MUST 在回滚申请创建时由后端从目标快照派生用于 NETCONF `edit-config` 的规范化载荷，并将派生载荷以与正向变更一致的安全摘要方式持久化。

#### Scenario: 派生与冻结
- **WHEN** 系统接受合法的回滚发起请求
- **THEN** 系统 MUST 在同一事务内从目标快照规范化内容派生 `edit-config` 载荷，记录载荷 digest、长度、行数和来源标记 `rollback_from_snapshot:<id>`，并保存到与正向变更相同的载荷存储路径

#### Scenario: 不暴露原始载荷
- **WHEN** 调用方查询回滚申请、审批队列或执行任务详情
- **THEN** 系统 MUST 仅返回派生载荷的 digest、长度、行数和受控比较摘要，不得在 API 响应、任务 metadata 或日志中返回派生载荷的完整原始内容

#### Scenario: 执行前再校验载荷一致
- **WHEN** 回滚执行任务从队列拉起准备调用 `edit-config`
- **THEN** 系统 MUST 比较存储载荷 digest 与目标快照规范化内容当前 digest，若不一致则将变更标记为失败并记录失败审计事件

### Requirement: 回滚预检模式
系统 MUST 提供回滚专用的预检模式，校验回滚目标快照、来源变更状态、设备并发约束和回滚特有的阻塞条件，复用既有预检的权限、datastore 和原因校验。

#### Scenario: 回滚模式预检通过
- **WHEN** approver 或 admin 在 `mode = rollback` 下提交目标设备、datastore、目标快照标识和原因进行预检
- **THEN** 系统 MUST 返回通过状态、目标快照摘要、当前最新快照摘要、派生载荷摘要、风险等级和受控比较摘要

#### Scenario: 同设备同 datastore 已有变更进行中
- **WHEN** 回滚预检发现同设备同 datastore 存在状态为 `queued`、`running` 或 `verifying` 的变更申请
- **THEN** 系统 MUST 返回未通过状态和阻塞码 `CHANGE_IN_FLIGHT`，并不得创建回滚申请或执行任务

#### Scenario: 来源变更状态不允许回滚
- **WHEN** 预检请求带有 `rollback_of_change_id` 但来源变更状态不在 `verification_failed` 或 `failed` 范围
- **THEN** 系统 MUST 返回阻塞码 `ROLLBACK_ORIGIN_NOT_RECOVERABLE` 并拒绝继续

#### Scenario: 基线新鲜度规则放宽
- **WHEN** 回滚预检评估当前设备状态
- **THEN** 系统 MUST 不再强制要求最新快照在常规基线新鲜度阈值内，但 MUST 要求最近一次成功快照存在以判断与目标快照的差异

### Requirement: 自动回滚提案
系统 MUST 在配置变更执行验证失败时自动创建一个待审批的回滚提案，但不得自动执行回滚。

#### Scenario: 验证失败触发自动提案
- **WHEN** 非回滚类配置变更任务以 `verification_failed` 结束
- **THEN** 系统 MUST 创建一个 `is_rollback = true`、`rollback_of_change_id = <来源变更>`、`rollback_target_snapshot_id = <来源变更基线快照>`、状态为 `pending_approval` 的回滚申请，并保存安全预检摘要

#### Scenario: 自动提案不投递执行
- **WHEN** 系统创建自动回滚提案
- **THEN** 系统 MUST NOT 投递 NETCONF 写入任务，必须由具备审批权限的用户审批或直接执行才能进入执行阶段

#### Scenario: 来源已是回滚的不递归
- **WHEN** `verification_failed` 的来源变更本身 `is_rollback = true`
- **THEN** 系统 MUST NOT 创建新的自动回滚提案，仅记录验证失败审计事件

#### Scenario: 来源缺少基线快照
- **WHEN** `verification_failed` 的来源变更未持久化基线快照标识
- **THEN** 系统 MUST 跳过自动提案创建并记录失败审计事件，不得使用其他历史快照替代

### Requirement: 回滚执行验证
系统 MUST 让回滚执行复用既有的应用-验证管道，并在验证阶段以目标快照内容摘要作为成功判定依据。

#### Scenario: 回滚执行成功
- **WHEN** 回滚任务成功调用受控 `edit-config` 并完成 post-change 快照采集
- **THEN** 系统 MUST 比较 post-change 快照内容摘要与回滚目标快照内容摘要，并仅在两者匹配时将变更状态更新为 `executed` 且验证成功

#### Scenario: 回滚验证不通过
- **WHEN** 回滚任务写入成功但 post-change 快照内容摘要与目标快照内容摘要不一致
- **THEN** 系统 MUST 将变更状态更新为 `verification_failed` 并记录验证失败审计事件，不得创建针对该回滚的自动回滚提案

#### Scenario: 回滚写入失败
- **WHEN** 回滚任务因设备拒绝、协议错误、超时或认证失败导致写入失败
- **THEN** 系统 MUST 将变更状态更新为 `failed`，返回标准错误码和脱敏错误消息，不得伪造 post-change 快照或验证成功状态

### Requirement: 回滚 RBAC
系统 MUST 仅允许具备审批权限的用户提交手动回滚或批准回滚提案，并在直接执行回滚时强制非空原因。

#### Scenario: viewer 或 operator 提交回滚
- **WHEN** viewer 或 operator 尝试发起或直接执行回滚
- **THEN** 系统 MUST 返回禁止访问响应，并记录失败操作审计事件

#### Scenario: approver 批准自动回滚提案
- **WHEN** approver 对自动创建的回滚提案点击批准
- **THEN** 系统 MUST 重新校验回滚预检并在通过后投递回滚执行任务

#### Scenario: 回滚直接执行原因
- **WHEN** approver 或 admin 选择直接执行回滚
- **THEN** 系统 MUST 拒绝空原因请求，并在直接执行审计中保存原因、目标快照标识、来源变更标识和预检摘要

### Requirement: 回滚链路追踪字段
系统 MUST 在变更申请记录和查询响应中保存并返回回滚链路字段，使回滚与原始变更可双向追踪。

#### Scenario: 持久化链路字段
- **WHEN** 系统创建回滚申请
- **THEN** 系统 MUST 持久化 `is_rollback`、`rollback_of_change_id`（可选）和 `rollback_target_snapshot_id`，并通过 Alembic 迁移管理这些字段及外键约束

#### Scenario: 查询回滚上下文
- **WHEN** 调用方查询回滚申请详情
- **THEN** 系统 MUST 返回 `is_rollback`、来源变更摘要（若存在）、目标快照摘要、目标快照与当前快照的受控比较摘要和派生载荷摘要

#### Scenario: 来源变更回链
- **WHEN** 调用方查询某个验证失败的原始变更详情
- **THEN** 系统 MUST 返回是否存在自动或手动创建的回滚提案及其标识和状态，便于跳转
