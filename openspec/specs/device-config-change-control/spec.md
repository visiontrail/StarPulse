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
系统 MUST 在变更申请查询响应中返回安全的预检、风险和验证上下文。

#### Scenario: 查询变更安全上下文
- **WHEN** 具备变更读取权限的用户查询变更申请详情或列表
- **THEN** 系统 MUST 返回预检状态、风险摘要、基线快照摘要、执行任务标识和验证状态，并不得返回未经控制的完整配置正文

#### Scenario: 隐藏变更载荷正文
- **WHEN** API 返回变更申请列表、详情、审批队列或任务摘要
- **THEN** 系统 MUST 默认隐藏完整配置载荷正文，只返回摘要、digest、长度或受控预览字段

### Requirement: 配置变更执行闭环
系统 MUST 将设备配置变更执行纳入任务和状态闭环，记录排队、运行、写入、验证、成功、失败和关联审计信息。

#### Scenario: 执行任务排队
- **WHEN** 变更申请被批准或 approver 发起直接执行
- **THEN** 系统 MUST 创建可查询的执行任务，并关联设备、变更申请、发起用户、基线快照和预检摘要

#### Scenario: 执行成功
- **WHEN** 配置变更任务成功写入设备、完成必要提交、采集 post-change 快照并通过验证
- **THEN** 系统 MUST 将任务和变更记录更新为成功状态，保存 post-change 快照标识和验证摘要，并记录直接执行或审批执行成功审计日志

#### Scenario: 执行验证失败
- **WHEN** 配置变更任务成功写入设备但 post-change 快照采集或比较失败
- **THEN** 系统 MUST 将变更记录更新为验证失败状态，返回标准错误码和脱敏错误信息，并记录验证失败审计日志

#### Scenario: 执行失败
- **WHEN** 配置变更任务因设备不可达、认证失败、协议错误、超时或设备拒绝导致失败
- **THEN** 系统 MUST 将任务和变更记录更新为失败状态，返回标准错误码和脱敏错误信息，并记录失败操作审计日志

### Requirement: 写操作服务边界
系统 MUST 将 NETCONF 写操作限制在配置变更控制服务中，配置快照服务不得执行写设备操作。

#### Scenario: 配置快照任务运行
- **WHEN** 系统执行配置快照采集任务
- **THEN** 系统 MUST 只调用只读 `get-config` 或等价读取操作，不得调用配置写入操作

#### Scenario: 配置变更任务运行
- **WHEN** 系统执行已授权的配置变更任务
- **THEN** 系统 MUST 通过配置变更控制服务调用明确的 NETCONF 写入路径，并记录目标、操作者、权限和结果

