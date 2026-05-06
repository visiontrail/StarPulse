## ADDED Requirements

### Requirement: 配置回滚审计
系统 MUST 记录配置回滚提案、提交、批准、直接执行、执行成功、验证成功和验证失败等回滚控制事件，并在审计中保留回滚链路上下文。

#### Scenario: 自动回滚提案审计
- **WHEN** 系统在配置变更验证失败后创建自动回滚提案
- **THEN** 系统 MUST 记录 `change.rollback_proposed` 审计事件，包含 `rollback_of_change_id`、`rollback_target_snapshot_id`、目标设备、datastore、来源变更状态和系统操作者标识

#### Scenario: 手动回滚提交审计
- **WHEN** approver 或 admin 通过快照视图或来源变更详情手动发起回滚
- **THEN** 系统 MUST 记录 `change.rollback_submitted` 审计事件，包含操作者、`rollback_target_snapshot_id`、`rollback_of_change_id`（若存在）、设备、datastore 和预检摘要

#### Scenario: 回滚执行审计
- **WHEN** 回滚变更通过审批或直接执行进入执行阶段
- **THEN** 系统 MUST 记录 `change.rollback_executed` 审计事件，包含执行任务标识、操作者、`is_rollback`、`rollback_of_change_id`、`rollback_target_snapshot_id`、预检摘要和直接执行原因（若适用）

#### Scenario: 回滚验证审计
- **WHEN** 回滚执行后完成 post-change 验证
- **THEN** 系统 MUST 记录 `change.rollback_verified` 或 `change.rollback_verification_failed` 审计事件，包含执行任务标识、目标快照标识、post-change 快照标识和受控比较摘要

#### Scenario: 回滚审计脱敏
- **WHEN** 系统写入任意回滚相关审计 metadata
- **THEN** 系统 MUST NOT 包含派生载荷正文、设备凭据、密码、token、私钥或未经控制的完整配置正文

## MODIFIED Requirements

### Requirement: 变更控制审计
系统 MUST 记录变更申请提交、预检、审批、驳回、直接执行、执行成功、执行失败、验证成功、验证失败和回滚链路相关的配置变更控制事件。

#### Scenario: 变更申请提交审计
- **WHEN** operator 成功提交设备配置变更申请
- **THEN** 系统 MUST 记录包含申请标识、设备标识、datastore、申请人、变更摘要、基线快照标识和预检摘要的审计事件

#### Scenario: 变更预检审计
- **WHEN** 系统执行配置变更预检
- **THEN** 系统 MUST 记录预检审计事件，并包含目标设备、datastore、基线快照标识、`mode`、结果、阻塞原因和安全风险摘要

#### Scenario: 变更审批审计
- **WHEN** approver 批准或驳回设备配置变更申请
- **THEN** 系统 MUST 记录包含申请标识、审批人、审批结果、审批意见摘要、预检状态、风险摘要和回滚链路字段（若存在）的审计事件

#### Scenario: 直接执行审计
- **WHEN** approver 直接执行设备配置变更
- **THEN** 系统 MUST 记录包含直接执行标记、原因、设备标识、datastore、操作者、变更摘要、基线快照标识、预检摘要和回滚链路字段（若 `is_rollback`）的审计事件

#### Scenario: 执行验证审计
- **WHEN** 配置变更执行后完成 post-change 验证
- **THEN** 系统 MUST 记录验证成功或验证失败审计事件，并包含申请标识、执行任务标识、基线快照标识、post-change 快照标识、`is_rollback`、结果和脱敏比较摘要

#### Scenario: 失败操作审计
- **WHEN** 受控操作因权限不足、参数错误、设备错误、预检失败、执行失败或验证失败而失败
- **THEN** 系统 MUST 记录失败操作审计事件，并包含标准错误码、回滚链路字段（若存在）和脱敏错误上下文
