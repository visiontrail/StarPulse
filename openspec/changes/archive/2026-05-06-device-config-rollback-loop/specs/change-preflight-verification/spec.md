## ADDED Requirements

### Requirement: 预检模式参数
系统 MUST 在预检接口和持久化字段中支持 `mode` 参数，区分正向变更预检和回滚预检，并基于模式应用不同的校验规则。

#### Scenario: 默认正向模式
- **WHEN** 调用方未在预检请求中提供 `mode`
- **THEN** 系统 MUST 按 `mode = forward` 处理，并保留既有正向预检校验逻辑

#### Scenario: 显式回滚模式
- **WHEN** 调用方在预检请求中提供 `mode = rollback`
- **THEN** 系统 MUST 在校验中加入回滚目标快照、并发约束和来源变更状态规则，并在预检结果中包含 `mode` 字段

#### Scenario: 持久化预检模式
- **WHEN** 系统在变更申请记录中保存安全预检摘要
- **THEN** 系统 MUST 同时保存 `mode` 字段以支持审批时再次以同模式校验

## MODIFIED Requirements

### Requirement: 配置变更预检
系统 MUST 在配置变更提交、审批执行和直接执行前提供后端权威预检，并按模式校验设备、datastore、变更载荷、基线快照、回滚目标快照、并发约束和权限边界。

#### Scenario: 预检成功（正向模式）
- **WHEN** 具备配置变更提交权限的用户在 `mode = forward` 下对已接入完成的设备提交 datastore、变更摘要、变更载荷和原因进行预检
- **THEN** 系统 MUST 返回通过状态、目标设备摘要、datastore、基线快照摘要、载荷摘要和安全风险摘要

#### Scenario: 预检成功（回滚模式）
- **WHEN** 具备审批权限的用户在 `mode = rollback` 下对已接入完成的设备提交 datastore、目标快照标识、可选的来源变更标识和原因进行预检
- **THEN** 系统 MUST 返回通过状态、目标快照摘要、当前最新快照摘要、派生载荷摘要、风险等级和受控比较摘要

#### Scenario: 设备未准备好
- **WHEN** 预检目标设备缺少连接配置、可用凭据、能力发现结果或基线快照
- **THEN** 系统 MUST 返回未通过状态和可展示阻塞原因，并且不得创建变更申请或执行任务

#### Scenario: 基线快照过旧
- **WHEN** `mode = forward` 下预检使用的最后基线快照超过系统配置的新鲜度阈值
- **THEN** 系统 MUST 将预检标记为未通过或需要刷新基线，并返回最后快照时间和建议刷新动作

#### Scenario: 回滚模式放宽基线新鲜度
- **WHEN** `mode = rollback` 下预检评估当前设备状态
- **THEN** 系统 MUST 不再强制基线新鲜度阈值，但 MUST 要求最近一次成功快照存在以判断与目标快照的差异，否则返回阻塞码 `CHANGE_IN_FLIGHT` 之外的合适阻塞原因

#### Scenario: 回滚目标不可恢复
- **WHEN** `mode = rollback` 下目标快照未持久化规范化内容
- **THEN** 系统 MUST 返回未通过状态和阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`

#### Scenario: 同设备同 datastore 已有进行中变更
- **WHEN** 预检发现同设备同 datastore 存在状态为 `queued`、`running` 或 `verifying` 的变更
- **THEN** 系统 MUST 返回阻塞码 `CHANGE_IN_FLIGHT`，无论 `mode` 为正向还是回滚

#### Scenario: 来源变更状态不允许回滚
- **WHEN** `mode = rollback` 且预检请求带有 `rollback_of_change_id` 但来源变更状态不在 `verification_failed` 或 `failed` 范围
- **THEN** 系统 MUST 返回阻塞码 `ROLLBACK_ORIGIN_NOT_RECOVERABLE`

#### Scenario: 与当前状态无差异
- **WHEN** `mode = rollback` 且目标快照内容摘要与当前最新快照内容摘要一致
- **THEN** 系统 MUST 返回阻塞码 `ROLLBACK_NO_DIVERGENCE`

#### Scenario: 载荷无效
- **WHEN** 变更载荷为空、datastore 不受支持或缺少变更原因
- **THEN** 系统 MUST 返回标准参数错误或未通过预检结果，并记录失败审计事件
