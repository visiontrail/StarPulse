## ADDED Requirements

### Requirement: 快照视图回滚入口
前端 MUST 在快照列表和快照详情视图为具备审批权限的用户展示回滚入口，并在快照不可作为回滚目标时禁用入口并展示原因。

#### Scenario: approver 看到回滚入口
- **WHEN** approver 或 admin 在快照视图查看 `rollback_eligible = true` 的成功快照
- **THEN** 前端 MUST 展示「恢复到此快照」动作，并在点击后打开预填充回滚模式的提交对话框

#### Scenario: 不可恢复快照禁用入口
- **WHEN** 快照 `rollback_eligible = false` 或带有阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`
- **THEN** 前端 MUST 禁用或隐藏回滚入口，并展示可理解的不可回滚原因

#### Scenario: viewer 或 operator 隐藏回滚入口
- **WHEN** viewer 或 operator 查看快照视图
- **THEN** 前端 MUST NOT 展示回滚动作入口

### Requirement: 回滚提交与预检展示
前端 MUST 在回滚提交、审批和直接执行前展示后端返回的回滚预检状态、目标快照摘要、当前快照摘要、派生载荷摘要和阻塞原因。

#### Scenario: 回滚预检通过
- **WHEN** 后端返回 `mode = rollback` 的预检通过
- **THEN** 前端 MUST 展示目标快照摘要、当前最新快照摘要、派生载荷摘要、风险等级和受控比较摘要，并启用提交或直接执行按钮

#### Scenario: 回滚预检阻塞
- **WHEN** 后端返回回滚预检阻塞，例如 `CHANGE_IN_FLIGHT`、`ROLLBACK_TARGET_NOT_RESTORABLE`、`ROLLBACK_NO_DIVERGENCE` 或 `ROLLBACK_ORIGIN_NOT_RECOVERABLE`
- **THEN** 前端 MUST 禁止提交、审批或直接执行，并展示对应阻塞原因和建议刷新或更换目标的动作

#### Scenario: 直接执行回滚要求原因
- **WHEN** approver 选择直接执行回滚
- **THEN** 前端 MUST 强制要求填写非空原因，并在提交前刷新或展示后端预检结果

### Requirement: 自动回滚提案展示
前端 MUST 在原始变更详情和待审批队列中展示自动创建的回滚提案，并提供跳转链路。

#### Scenario: 验证失败展示提案链接
- **WHEN** 用户查看状态为 `verification_failed` 且已生成自动回滚提案的非回滚变更详情
- **THEN** 前端 MUST 展示「查看待审批回滚提案」入口和提案标识

#### Scenario: 回滚提案展示来源
- **WHEN** approver 查看自动创建的回滚提案
- **THEN** 前端 MUST 展示来源变更摘要、目标快照摘要、自动提案标记和受控比较摘要

#### Scenario: 已存在提案不重复创建
- **WHEN** 验证失败的变更已经存在 `pending_approval` 状态的回滚提案
- **THEN** 前端 MUST 隐藏「手动创建回滚提案」入口，仅展示跳转到现有提案的链接

### Requirement: 回滚执行验证状态展示
前端 MUST 展示回滚变更从排队、运行、验证到成功或失败的状态闭环，并区分回滚验证失败与正向变更验证失败。

#### Scenario: 展示回滚验证中
- **WHEN** 回滚执行任务进入验证阶段
- **THEN** 前端 MUST 展示验证中状态、目标快照摘要和当前进展，并允许用户刷新

#### Scenario: 展示回滚验证成功
- **WHEN** 后端返回回滚验证成功
- **THEN** 前端 MUST 展示 post-change 快照与目标快照的受控比较摘要、执行任务标识和回滚链路字段

#### Scenario: 展示回滚验证失败
- **WHEN** 后端返回回滚验证失败
- **THEN** 前端 MUST 展示标准错误码、可展示错误消息、不创建嵌套自动提案的明确说明，且不得展示派生载荷正文或敏感材料

## MODIFIED Requirements

### Requirement: 上下文配置变更入口
前端 MUST 从设备画像、快照上下文和回滚链路发起配置变更申请，避免正常流程中手工输入设备 ID。

#### Scenario: 从设备画像发起变更
- **WHEN** operator 在设备画像页点击提交配置变更
- **THEN** 前端 MUST 自动带入所选设备、datastore 和最近基线快照摘要，并展示变更摘要、变更载荷和原因输入

#### Scenario: 从快照发起变更
- **WHEN** operator 从某个配置快照区域发起正向变更
- **THEN** 前端 MUST 将该快照作为候选基线展示，并在提交前调用后端预检

#### Scenario: 从快照发起回滚
- **WHEN** approver 或 admin 从某个 `rollback_eligible = true` 的历史快照点击「恢复到此快照」
- **THEN** 前端 MUST 以 `mode = rollback` 调用后端预检，预填充目标快照标识，且不要求用户输入或上传载荷正文

#### Scenario: 设备未准备好时禁用变更
- **WHEN** 设备接入摘要标记为未准备好进入变更流程
- **THEN** 前端 MUST 禁用或隐藏提交变更和回滚入口，并展示缺失的连接测试、能力发现或基线快照阻塞原因
