## ADDED Requirements

### Requirement: 身份认证与授权基础配置
系统 MUST 在统一配置管理中提供认证、授权和会话相关配置，并支持通过环境变量覆盖。

#### Scenario: 使用环境变量配置 JWT
- **WHEN** 运行环境设置 JWT 密钥、access token 有效期或 refresh token 有效期
- **THEN** 系统启动时 MUST 使用这些环境变量覆盖默认认证配置

#### Scenario: 生产环境缺少安全密钥
- **WHEN** 系统以生产环境启动且 JWT 密钥仍为不安全默认值
- **THEN** 系统 MUST 拒绝启动或输出明确的启动失败错误

### Requirement: 认证授权数据库迁移
系统 MUST 通过数据库迁移和 Repository 层管理用户、角色、权限、refresh token、设备配置变更申请和审计日志等持久化数据。

#### Scenario: 执行认证授权迁移
- **WHEN** 开发者运行数据库迁移入口
- **THEN** 系统 MUST 创建或更新用户、角色、权限、角色关系、refresh token、配置变更申请和审计日志表结构

#### Scenario: 通过 Repository 访问认证数据
- **WHEN** 认证、授权、审计或变更控制服务需要读取或写入持久化数据
- **THEN** 服务 MUST 通过 Repository 或等价数据访问边界访问数据库，而不是在 API 层拼接数据库操作

### Requirement: 预置权限和角色种子数据
系统 MUST 提供幂等初始化逻辑，确保预置权限点和 `viewer`、`operator`、`approver`、`admin` 角色存在。

#### Scenario: 首次初始化权限数据
- **WHEN** 系统在空数据库中执行权限初始化
- **THEN** 系统 MUST 创建预置权限点、角色和默认角色权限关系

#### Scenario: 重复初始化权限数据
- **WHEN** 系统在已有权限数据的数据库中再次执行初始化
- **THEN** 系统 MUST 补齐缺失的系统权限和角色，并且不得删除已有用户或自定义角色关系

### Requirement: API 默认安全边界
系统 MUST 为业务 API 建立默认认证边界，并保持健康检查等基础可观测接口可匿名访问。

#### Scenario: 业务路由默认认证
- **WHEN** 新增业务路由挂载到 `/api/v1`
- **THEN** 路由 MUST 默认要求有效认证，除非被显式加入公开 allowlist

#### Scenario: 健康检查保持公开
- **WHEN** 调用方请求健康检查接口
- **THEN** 系统 MUST 返回服务存活状态，而不要求 access token

### Requirement: 结构化安全日志
系统 MUST 在结构化日志中记录认证、授权和审计相关关键上下文，并避免敏感信息泄漏。

#### Scenario: 输出授权失败日志
- **WHEN** 已认证用户因权限不足访问业务 API
- **THEN** 系统 MUST 输出包含用户标识、权限点、路径和结果的结构化日志，并且不得包含 token 或密码
