# device-config-change-control Specification

## Purpose
TBD - created by archiving change add-auth-rbac-session-management. Update Purpose after archive.
## Requirements
### Requirement: 设备配置变更申请
系统 MUST 允许具备权限的用户提交设备配置变更申请，并保存目标设备、datastore、变更内容引用或摘要、申请原因、申请人和状态。

#### Scenario: operator 提交变更申请
- **WHEN** operator 对存在且可连接的设备提交配置变更申请
- **THEN** 系统 MUST 创建状态为 `pending_approval` 的变更申请，并记录申请提交审计日志

#### Scenario: viewer 提交变更申请
- **WHEN** viewer 尝试提交设备配置变更申请
- **THEN** 系统 MUST 返回禁止访问响应，并且不得创建变更申请

#### Scenario: 变更申请参数无效
- **WHEN** 调用方提交不存在设备、不支持 datastore 或缺少变更原因的申请
- **THEN** 系统 MUST 返回标准参数或资源错误，并记录失败操作审计日志

### Requirement: 设备配置变更审批
系统 MUST 允许具备审批权限的用户审批或驳回待审批的设备配置变更申请。

#### Scenario: approver 批准变更申请
- **WHEN** approver 批准状态为 `pending_approval` 的变更申请
- **THEN** 系统 MUST 记录审批人、审批意见和审批时间，并将申请推进到可执行状态或投递执行任务

#### Scenario: approver 驳回变更申请
- **WHEN** approver 驳回状态为 `pending_approval` 的变更申请
- **THEN** 系统 MUST 将申请状态更新为 `rejected`，保存驳回原因，并记录审批审计日志

#### Scenario: operator 审批变更申请
- **WHEN** operator 尝试审批或驳回变更申请
- **THEN** 系统 MUST 返回禁止访问响应，并且不得改变申请状态

### Requirement: approver 直接执行设备配置变更
系统 MUST 允许 approver 绕过普通提交-审批流程直接执行设备配置变更，用于高级运维、测试和紧急处理场景。

#### Scenario: approver 直接执行
- **WHEN** approver 提供目标设备、datastore、变更内容引用或摘要和直接执行原因
- **THEN** 系统 MUST 创建带有直接执行标记的变更记录，投递或执行配置变更，并记录绕过审批审计日志

#### Scenario: 直接执行缺少原因
- **WHEN** approver 请求直接执行但未提供原因
- **THEN** 系统 MUST 拒绝请求，并且不得执行设备配置变更

#### Scenario: 非 approver 直接执行
- **WHEN** viewer 或 operator 尝试直接执行设备配置变更
- **THEN** 系统 MUST 返回禁止访问响应，并记录失败操作审计日志

### Requirement: 配置变更预检约束
系统 MUST 将设备配置变更预检纳入提交、审批和直接执行路径，确保执行前存在有效的安全决策上下文。

#### Scenario: 提交时执行预检
- **WHEN** operator 提交设备配置变更申请
- **THEN** 系统 MUST 校验设备准备状态、datastore、变更载荷、基线快照和原因，并在变更申请中保存安全预检摘要

#### Scenario: 审批时预检失效
- **WHEN** approver 批准变更申请但预检已过期、基线过旧或设备状态不再满足要求
- **THEN** 系统 MUST 拒绝投递执行任务，并要求刷新预检或重新提交变更

#### Scenario: 直接执行时执行预检
- **WHEN** approver 发起直接执行
- **THEN** 系统 MUST 在创建执行任务前执行预检，并将预检摘要、风险摘要和直接执行原因写入变更记录和审计日志

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

### Requirement: 同设备同 datastore 并发约束
系统 MUST 在变更申请提交、审批执行和直接执行路径中阻止同一设备同一 datastore 出现多个并行进行中的变更，避免与回滚或其他变更产生竞态。

#### Scenario: 已有进行中变更时阻止新提交
- **WHEN** 调用方提交配置变更申请且同设备同 datastore 已存在状态为 `queued`、`running` 或 `verifying` 的变更
- **THEN** 系统 MUST 返回未通过状态和阻塞码 `CHANGE_IN_FLIGHT`，并不得创建变更申请或执行任务

#### Scenario: 已有进行中回滚时阻止新提交
- **WHEN** 调用方提交配置变更申请且同设备同 datastore 已存在 `is_rollback = true` 且状态为 `queued`、`running` 或 `verifying` 的回滚申请
- **THEN** 系统 MUST 返回阻塞码 `CHANGE_IN_FLIGHT`，并不得创建新的变更申请

### Requirement: 写操作服务边界
系统 MUST 将 NETCONF 写操作限制在配置变更控制服务中，配置快照服务不得执行写设备操作。

#### Scenario: 配置快照任务运行
- **WHEN** 系统执行配置快照采集任务
- **THEN** 系统 MUST 只调用只读 `get-config` 或等价读取操作，不得调用配置写入操作

#### Scenario: 配置变更任务运行
- **WHEN** 系统执行已授权的配置变更任务
- **THEN** 系统 MUST 通过配置变更控制服务调用明确的 NETCONF 写入路径，并记录目标、操作者、权限和结果

