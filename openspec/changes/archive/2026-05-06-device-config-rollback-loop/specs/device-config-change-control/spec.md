## ADDED Requirements

### Requirement: 同设备同 datastore 并发约束
系统 MUST 在变更申请提交、审批执行和直接执行路径中阻止同一设备同一 datastore 出现多个并行进行中的变更，避免与回滚或其他变更产生竞态。

#### Scenario: 已有进行中变更时阻止新提交
- **WHEN** 调用方提交配置变更申请且同设备同 datastore 已存在状态为 `queued`、`running` 或 `verifying` 的变更
- **THEN** 系统 MUST 返回未通过状态和阻塞码 `CHANGE_IN_FLIGHT`，并不得创建变更申请或执行任务

#### Scenario: 已有进行中回滚时阻止新提交
- **WHEN** 调用方提交配置变更申请且同设备同 datastore 已存在 `is_rollback = true` 且状态为 `queued`、`running` 或 `verifying` 的回滚申请
- **THEN** 系统 MUST 返回阻塞码 `CHANGE_IN_FLIGHT`，并不得创建新的变更申请

## MODIFIED Requirements

### Requirement: 变更详情安全上下文
系统 MUST 在变更申请查询响应中返回安全的预检、风险、验证和回滚链路上下文。

#### Scenario: 查询变更安全上下文
- **WHEN** 具备变更读取权限的用户查询变更申请详情或列表
- **THEN** 系统 MUST 返回预检状态、风险摘要、基线快照摘要、执行任务标识、验证状态、`is_rollback`、`rollback_of_change_id` 和 `rollback_target_snapshot_id`，并不得返回未经控制的完整配置正文

#### Scenario: 隐藏变更载荷正文
- **WHEN** API 返回变更申请列表、详情、审批队列或任务摘要
- **THEN** 系统 MUST 默认隐藏完整配置载荷正文，只返回摘要、digest、长度或受控预览字段，且对回滚派生载荷采用同样的隐藏规则

#### Scenario: 回滚链路双向跳转
- **WHEN** 调用方查询某变更申请详情
- **THEN** 系统 MUST 在响应中包含可用于双向跳转的 `is_rollback`、来源变更摘要（若存在）、目标快照摘要（若存在）和已存在的回滚提案摘要（若该变更曾验证失败并已生成提案）

### Requirement: 配置变更执行闭环
系统 MUST 将设备配置变更执行纳入任务和状态闭环，记录排队、运行、写入、验证、成功、失败、关联审计信息，并对验证失败的非回滚变更触发自动回滚提案。

#### Scenario: 执行任务排队
- **WHEN** 变更申请被批准或 approver 发起直接执行
- **THEN** 系统 MUST 创建可查询的执行任务，并关联设备、变更申请、发起用户、基线快照、预检摘要和回滚链路字段（若存在）

#### Scenario: 执行成功
- **WHEN** 配置变更任务成功写入设备、完成必要提交、采集 post-change 快照并通过验证
- **THEN** 系统 MUST 将任务和变更记录更新为成功状态，保存 post-change 快照标识和验证摘要，并记录直接执行或审批执行成功审计日志

#### Scenario: 执行验证失败触发自动回滚提案
- **WHEN** 非回滚配置变更任务成功写入设备但 post-change 快照采集或比较失败
- **THEN** 系统 MUST 将变更记录更新为 `verification_failed`，记录验证失败审计日志，并自动创建一个状态为 `pending_approval` 的回滚提案；系统 MUST NOT 自动执行该回滚提案

#### Scenario: 回滚变更验证失败不递归
- **WHEN** `is_rollback = true` 的变更任务成功写入设备但 post-change 验证失败
- **THEN** 系统 MUST 将变更记录更新为 `verification_failed` 并记录回滚验证失败审计日志，且不得创建新的自动回滚提案

#### Scenario: 执行失败
- **WHEN** 配置变更任务因设备不可达、认证失败、协议错误、超时或设备拒绝导致失败
- **THEN** 系统 MUST 将任务和变更记录更新为失败状态，返回标准错误码和脱敏错误信息，并记录失败操作审计日志，且不得创建自动回滚提案
