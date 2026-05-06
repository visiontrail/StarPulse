# change-preflight-verification Specification

## Purpose
TBD - created by syncing change device-onboarding-change-safety-loop. Update Purpose after archive.
## Requirements
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

### Requirement: 安全风险摘要
系统 MUST 为预检和审批提供边界受控的风险摘要，帮助操作者理解变更影响，同时避免泄漏完整配置正文或敏感材料。

#### Scenario: 生成风险摘要
- **WHEN** 系统执行配置变更预检
- **THEN** 风险摘要 MUST 至少包含设备标识、datastore、基线快照标识、基线内容摘要、变更载荷摘要、载荷长度或行数、阻塞原因和风险等级或等价分类

#### Scenario: 生成受控比较摘要
- **WHEN** 系统具备可比较的基线摘要和变更载荷摘要
- **THEN** 系统 MUST 返回受控比较摘要，例如 digest 是否变化、行数变化、目标 datastore 和比较基线，不得返回未经控制的完整配置正文

#### Scenario: 风险摘要脱敏
- **WHEN** 变更载荷、设备连接配置或错误上下文包含密码、token、密钥、私钥或设备凭据
- **THEN** 风险摘要、任务 metadata、API 响应和日志 MUST 对这些字段进行脱敏或排除

### Requirement: 预检结果持久化
系统 MUST 将用于审批和执行决策的安全预检结果保存到变更申请记录或等价受控记录中。

#### Scenario: 提交变更保存预检
- **WHEN** operator 成功提交配置变更申请
- **THEN** 系统 MUST 保存提交时的预检状态、基线快照标识、风险摘要和生成时间

#### Scenario: 审批时校验预检
- **WHEN** approver 批准变更申请
- **THEN** 系统 MUST 校验保存的预检仍然有效，若基线过旧或设备状态不满足要求则拒绝执行并要求刷新预检

#### Scenario: 直接执行校验预检
- **WHEN** approver 发起直接执行
- **THEN** 系统 MUST 在创建执行记录前运行或校验预检，并在直接执行审计中保存安全预检摘要和直接执行原因

### Requirement: 执行后验证
系统 MUST 在配置写入成功后执行只读验证，采集 post-change 快照并与执行前基线或预检摘要比较。

#### Scenario: 写入后验证成功
- **WHEN** 配置变更任务成功调用受控 NETCONF 写入路径
- **THEN** 系统 MUST 对同一设备和 datastore 采集 post-change 快照，保存快照标识，并将变更记录更新为执行成功和验证成功状态

#### Scenario: 写入成功但验证失败
- **WHEN** 配置写入成功但 post-change 快照采集或比较失败
- **THEN** 系统 MUST 将变更记录标记为验证失败或等价状态，保留执行任务标识，并返回标准错误码和脱敏错误消息

#### Scenario: 写入失败不执行验证
- **WHEN** 配置写入因设备不可达、认证失败、协议错误、超时或设备拒绝而失败
- **THEN** 系统 MUST 将变更记录和任务标记为失败，并且不得伪造 post-change 快照或验证成功状态

#### Scenario: 查询验证摘要
- **WHEN** 用户查询变更申请详情或执行任务结果
- **THEN** 系统 MUST 返回执行状态、验证状态、基线快照摘要、post-change 快照摘要和安全比较摘要
