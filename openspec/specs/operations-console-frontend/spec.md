# operations-console-frontend Specification

## Purpose
TBD - created by syncing change device-readonly-ops-loop-mvp. Update Purpose after archive.
## Requirements
### Requirement: 前端工程与设计系统
系统 MUST 提供前端 MVP 工程，使用 Next.js/React、TypeScript、Tailwind CSS、Radix UI/shadcn 风格基础组件和 `lucide-react` 图标，并按 `DESIGN.md` 定制只读运维界面设计系统。

#### Scenario: 启动前端应用
- **WHEN** 开发者安装前端依赖并执行本地启动命令
- **THEN** 系统 MUST 启动可访问的前端应用，并能够配置后端 API 地址

#### Scenario: 应用设计系统
- **WHEN** 用户访问前端页面
- **THEN** 页面 MUST 使用 `DESIGN.md` 定义的暖色背景、暖黑文字、低噪声边框、8px 半径、紧凑运维布局和克制图标按钮

#### Scenario: 使用基础组件
- **WHEN** 前端渲染按钮、输入、菜单、标签、表格、状态徽标或弹层
- **THEN** 系统 MUST 使用可复用的 TypeScript 组件，并保持 Radix UI/shadcn 风格的可访问交互

### Requirement: 设备列表与画像视图
前端 MUST 提供设备列表和设备详情画像视图，让运维人员快速查看设备状态、发现结果、配置快照和最近任务。

#### Scenario: 查看设备列表
- **WHEN** 用户打开前端应用
- **THEN** 系统 MUST 展示设备列表，并包含设备名称、分组、连接状态、最后发现摘要和最后快照摘要

#### Scenario: 查看设备画像
- **WHEN** 用户选择某个设备
- **THEN** 系统 MUST 展示设备当前画像，包括连接状态、连接配置摘要、capabilities、system_info、最后配置快照和最近任务

#### Scenario: 设备为空
- **WHEN** 后端没有返回任何设备
- **THEN** 前端 MUST 展示空状态，并且不得显示虚假的设备数据

#### Scenario: API 请求失败
- **WHEN** 前端无法加载设备列表或设备画像
- **THEN** 系统 MUST 展示可理解的错误状态，并允许用户重试

### Requirement: 只读采集操作
前端 MUST 提供只读配置采集入口，允许用户选择 datastore 并触发后端配置读取任务。

#### Scenario: 触发配置采集
- **WHEN** 用户在设备画像页选择 datastore 并点击配置采集动作
- **THEN** 前端 MUST 调用后端配置快照任务 API，并展示返回的任务状态摘要

#### Scenario: 防止重复提交
- **WHEN** 配置采集请求正在提交或同一设备存在运行中的配置采集任务
- **THEN** 前端 MUST 禁用重复提交入口或明确展示进行中状态

#### Scenario: 保持只读语义
- **WHEN** 用户使用前端 MVP
- **THEN** 前端 MUST NOT 提供配置编辑、提交、回滚、删除设备配置或等价写操作入口

### Requirement: 快照和任务展示
前端 MUST 提供配置快照和最近任务展示，使用户能够理解最近一次采集结果和任务执行闭环。

#### Scenario: 展示快照列表
- **WHEN** 用户查看设备画像或快照区域
- **THEN** 前端 MUST 展示配置快照列表摘要，包括 datastore、采集时间、内容摘要和差异摘要

#### Scenario: 展示最后快照
- **WHEN** 设备存在成功配置快照
- **THEN** 前端 MUST 高亮展示最后配置快照及其与上一份快照的变化摘要

#### Scenario: 展示最近任务
- **WHEN** 用户查看设备画像
- **THEN** 前端 MUST 展示最近任务列表，并区分 `queued`、`running`、`succeeded` 和 `failed` 状态

#### Scenario: 展示失败原因
- **WHEN** 最近任务失败
- **THEN** 前端 MUST 展示标准错误码和可展示错误消息，不得显示敏感上下文

### Requirement: 前端安全和数据边界
前端 MUST 只展示后端提供的安全摘要，不得请求、缓存或渲染认证明文和未经控制的完整配置正文。

#### Scenario: 隐藏认证材料
- **WHEN** 前端渲染设备连接配置
- **THEN** 页面 MUST 只展示主机、端口、协议、用户名和凭据引用状态，不得展示密码、密钥或私钥

#### Scenario: 限制配置内容展示
- **WHEN** 前端渲染配置快照
- **THEN** 页面 MUST 默认展示摘要、hash、采集时间和差异摘要，而不是完整配置正文

#### Scenario: 类型安全 API client
- **WHEN** 前端调用后端 API
- **THEN** 系统 MUST 使用 TypeScript 类型定义约束设备画像、任务和配置快照响应结构

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

