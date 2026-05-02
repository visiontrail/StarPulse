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

### Requirement: 变更控制审计
系统 MUST 记录变更申请提交、审批、驳回、直接执行、执行成功和执行失败等配置变更控制事件。

#### Scenario: 变更申请提交审计
- **WHEN** operator 成功提交设备配置变更申请
- **THEN** 系统 MUST 记录包含申请标识、设备标识、datastore、申请人和变更摘要的审计事件

#### Scenario: 变更审批审计
- **WHEN** approver 批准或驳回设备配置变更申请
- **THEN** 系统 MUST 记录包含申请标识、审批人、审批结果和审批意见摘要的审计事件

#### Scenario: 直接执行审计
- **WHEN** approver 直接执行设备配置变更
- **THEN** 系统 MUST 记录包含直接执行标记、原因、设备标识、datastore、操作者和变更摘要的审计事件

#### Scenario: 失败操作审计
- **WHEN** 受控操作因权限不足、参数错误、设备错误或执行失败而失败
- **THEN** 系统 MUST 记录失败操作审计事件，并包含标准错误码和脱敏错误上下文

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

