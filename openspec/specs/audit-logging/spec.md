# audit-logging Specification

## Purpose
TBD - created by archiving change add-auth-rbac-session-management. Update Purpose after archive.
## Requirements
### Requirement: 审计事件模型
系统 MUST 记录关键安全和运维操作的审计事件，至少包含操作者、动作、目标、结果、权限点、请求上下文、脱敏 metadata 和发生时间。

#### Scenario: 写入成功审计事件
- **WHEN** 系统完成需要审计的成功操作
- **THEN** 系统 MUST 写入包含 `actor_user_id`、`action`、`target_type`、`target_id`、`outcome`、`permission` 和 `created_at` 的审计事件

#### Scenario: 审计 metadata 脱敏
- **WHEN** 系统写入审计 metadata
- **THEN** metadata MUST NOT 包含密码、access token、refresh token、私钥、设备凭据或未经控制的完整配置正文

### Requirement: 登录和登出审计
系统 MUST 记录登录成功、登录失败、Token 刷新失败和登出事件。

#### Scenario: 登录成功审计
- **WHEN** 用户成功登录
- **THEN** 系统 MUST 记录登录成功审计事件，并包含用户、来源地址和 user agent 摘要

#### Scenario: 登录失败审计
- **WHEN** 登录请求因错误凭据、禁用用户或无效输入失败
- **THEN** 系统 MUST 记录登录失败审计事件，并且不得在事件中保存明文密码

#### Scenario: 登出审计
- **WHEN** 已登录用户成功登出
- **THEN** 系统 MUST 记录登出审计事件，并关联用户和会话标识摘要

### Requirement: 角色和权限变更审计
系统 MUST 记录用户角色分配、角色权限变更、用户禁用和用户启用等访问控制管理操作。

#### Scenario: 角色分配审计
- **WHEN** admin 为用户新增或移除角色
- **THEN** 系统 MUST 记录角色变更审计事件，并包含目标用户、变更前后角色摘要和操作者

#### Scenario: 权限管理失败审计
- **WHEN** 非管理员尝试执行用户、角色或权限管理操作
- **THEN** 系统 MUST 记录失败操作审计事件，并包含被拒绝的权限点

### Requirement: 设备接入审计
系统 MUST 记录设备接入向导中的关键操作和失败结果，以便追踪设备从创建到可变更状态的过程。

#### Scenario: 接入步骤成功审计
- **WHEN** 用户成功创建设备、完成连接测试、完成能力发现或采集基线快照
- **THEN** 系统 MUST 记录成功审计事件，并包含操作者、设备标识、步骤名称、任务标识和结果摘要

#### Scenario: 接入步骤失败审计
- **WHEN** 接入步骤因权限不足、参数错误、凭据不可用、连接失败或协议错误失败
- **THEN** 系统 MUST 记录失败审计事件，并包含步骤名称、标准错误码或阻塞原因，且不得包含认证明文

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

### Requirement: 审计日志查询
系统 MUST 提供受权限控制的审计日志查询能力，支持分页、时间范围、操作者、动作、目标和结果过滤。

#### Scenario: 查询审计日志
- **WHEN** 具备审计读取权限的用户查询审计日志
- **THEN** 系统 MUST 返回分页审计事件列表，并按发生时间倒序排列

#### Scenario: 无权限查询审计日志
- **WHEN** 不具备审计读取权限的用户查询审计日志
- **THEN** 系统 MUST 返回禁止访问响应

#### Scenario: 限制审计日志规模
- **WHEN** 调用方查询审计日志但未提供分页参数
- **THEN** 系统 MUST 使用安全默认分页限制，避免返回无限历史数据

