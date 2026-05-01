## ADDED Requirements

### Requirement: 前端登录和会话恢复
前端 MUST 提供登录界面、会话恢复、Token 刷新和登出能力，使用户必须登录后才能访问运维控制台业务视图。

#### Scenario: 未登录访问控制台
- **WHEN** 用户未登录并打开前端应用
- **THEN** 前端 MUST 展示登录界面，并且不得请求受保护的业务数据

#### Scenario: 登录成功进入控制台
- **WHEN** 用户提交正确登录凭据
- **THEN** 前端 MUST 保存当前会话状态，获取当前用户角色和权限，并展示运维控制台

#### Scenario: 页面刷新恢复会话
- **WHEN** 用户刷新页面且 refresh token 仍有效
- **THEN** 前端 MUST 通过刷新接口恢复 access token、当前用户和权限状态

#### Scenario: 登出清理会话
- **WHEN** 用户点击登出
- **THEN** 前端 MUST 调用登出接口，清理本地会话状态，并返回登录界面

### Requirement: 权限感知导航和操作
前端 MUST 根据当前用户权限展示或禁用导航入口、按钮和高风险操作，并在权限不足时避免发起无效请求。

#### Scenario: viewer 查看只读数据
- **WHEN** viewer 登录控制台
- **THEN** 前端 MUST 允许其查看设备、快照、任务和允许的审计摘要，并隐藏或禁用配置采集、变更申请、审批、直接执行和管理入口

#### Scenario: operator 提交变更申请
- **WHEN** operator 登录控制台并查看设备详情
- **THEN** 前端 MUST 展示提交配置变更申请入口，并隐藏或禁用审批、直接执行和用户管理入口

#### Scenario: approver 审批和直接执行
- **WHEN** approver 登录控制台
- **THEN** 前端 MUST 展示待审批变更入口和直接执行入口，并要求直接执行填写原因

#### Scenario: admin 管理用户和角色
- **WHEN** admin 登录控制台
- **THEN** 前端 MUST 展示用户、角色、权限、系统配置和完整审计管理入口

### Requirement: API Client 会话处理
前端 API client MUST 为受保护请求附带 access token，并在 access token 过期时尝试刷新会话。

#### Scenario: 受保护请求成功
- **WHEN** 前端调用受保护业务 API 且 access token 有效
- **THEN** API client MUST 附带认证信息并返回业务响应

#### Scenario: access token 过期后刷新成功
- **WHEN** 业务 API 返回未认证且 refresh token 仍有效
- **THEN** API client MUST 调用刷新接口，使用新 access token 重试原请求

#### Scenario: 刷新失败
- **WHEN** access token 过期且 refresh token 无效、过期或被撤销
- **THEN** 前端 MUST 清理会话状态并返回登录界面

### Requirement: 前端安全显示边界
前端 MUST 避免展示或持久化敏感认证材料，并继续遵守设备凭据和配置正文的安全展示边界。

#### Scenario: 不展示 Token
- **WHEN** 前端渲染当前用户、会话或错误状态
- **THEN** 页面 MUST NOT 展示 access token、refresh token、密码或设备凭据

#### Scenario: 不缓存完整配置正文
- **WHEN** 用户提交或查看配置变更申请
- **THEN** 前端 MUST 默认展示配置摘要、目标、原因和状态，而不是未经控制的完整配置正文
