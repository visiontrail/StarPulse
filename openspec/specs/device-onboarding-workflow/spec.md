# device-onboarding-workflow Specification

## Purpose
TBD - created by syncing change device-onboarding-change-safety-loop. Update Purpose after archive.
## Requirements
### Requirement: 设备接入向导
系统 MUST 提供设备接入向导能力，引导具备权限的用户完成设备创建、连接测试、能力发现和基线快照采集，并返回可用于前端展示的安全进度摘要。

#### Scenario: 创建接入设备
- **WHEN** 具备设备管理权限的用户提交设备名称、连接地址、端口、用户名和认证材料
- **THEN** 系统 MUST 创建设备、连接配置和认证信息引用，并返回不包含认证明文的设备摘要

#### Scenario: 查询接入进度
- **WHEN** 用户查询设备画像或接入摘要
- **THEN** 系统 MUST 返回连接测试、能力发现、基线快照和阻塞原因的安全摘要，并不得返回密码、密钥、私钥或解析后的凭据值

#### Scenario: 无权限创建设备
- **WHEN** 不具备设备管理权限的用户尝试通过接入向导创建设备
- **THEN** 系统 MUST 返回禁止访问响应，并且不得保存设备、连接配置或认证材料

### Requirement: 接入验证步骤编排
系统 MUST 通过现有异步任务边界执行连接测试、能力发现和基线快照采集，且每一步都能独立失败、重试和查询状态。

#### Scenario: 连接测试成功后继续发现
- **WHEN** 接入向导中的连接测试任务成功
- **THEN** 系统 MUST 允许用户继续触发能力发现，并在设备进度摘要中标记连接测试已通过

#### Scenario: 能力发现成功后采集基线
- **WHEN** 能力发现任务成功并保存 capabilities
- **THEN** 系统 MUST 允许用户触发首份基线配置快照，并将成功快照标记为该设备当前 datastore 的可用基线

#### Scenario: 接入步骤失败
- **WHEN** 连接测试、能力发现或基线快照任务失败
- **THEN** 系统 MUST 在接入进度摘要中展示标准错误码和可展示错误消息，并允许具备权限的用户重试失败步骤

#### Scenario: 防止重复任务
- **WHEN** 同一设备已有相同接入步骤的 `queued` 或 `running` 任务
- **THEN** 系统 MUST 禁止重复投递或返回当前运行任务摘要

### Requirement: 接入完成判定
系统 MUST 明确定义设备是否已准备好进入配置变更流程。

#### Scenario: 设备准备就绪
- **WHEN** 设备存在成功连接测试、成功能力发现和至少一份指定 datastore 的成功基线快照
- **THEN** 系统 MUST 将接入摘要中的 `ready_for_change` 或等价字段标记为 true

#### Scenario: 设备未准备就绪
- **WHEN** 设备缺少连接配置、凭据、能力发现结果或基线快照
- **THEN** 系统 MUST 将 `ready_for_change` 标记为 false，并返回可展示的阻塞原因列表

#### Scenario: 不展示虚假完成状态
- **WHEN** 后端没有成功任务或快照支持某个接入步骤
- **THEN** 系统 MUST NOT 在 API 或前端展示该步骤已完成

### Requirement: 接入安全审计
系统 MUST 对设备接入关键步骤记录审计事件，且审计 metadata 必须脱敏。

#### Scenario: 记录设备创建审计
- **WHEN** 用户通过接入向导成功创建设备
- **THEN** 系统 MUST 记录设备创建审计事件，并包含操作者、设备标识、目标地址摘要和结果

#### Scenario: 记录接入任务失败审计
- **WHEN** 接入步骤因权限、参数、设备连接或凭据问题失败
- **THEN** 系统 MUST 记录失败审计事件，并包含标准错误码或阻塞原因，且不得包含认证明文
