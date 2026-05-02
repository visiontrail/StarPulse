## ADDED Requirements

### Requirement: 本地用户身份与凭据
系统 MUST 提供本地用户身份模型，保存用户标识、登录名、展示名、启用状态、密码哈希、创建时间和更新时间，并且不得保存明文密码。

#### Scenario: 成功创建本地用户
- **WHEN** 具备用户管理权限的调用方创建用户并提供初始密码
- **THEN** 系统 MUST 保存用户记录和密码哈希，并且不得在 API 响应、日志或审计 metadata 中返回明文密码

#### Scenario: 禁用用户无法登录
- **WHEN** 已禁用用户提交正确登录凭据
- **THEN** 系统 MUST 拒绝登录并返回标准认证失败响应

### Requirement: JWT 登录、刷新和登出
系统 MUST 支持用户使用登录凭据换取短期 JWT access token，并通过可撤销 refresh token 恢复会话、轮换令牌和登出。

#### Scenario: 登录成功
- **WHEN** 启用用户提交正确用户名和密码
- **THEN** 系统 MUST 返回包含用户信息、角色、权限和 access token 的登录结果，并设置可用于刷新会话的 refresh token

#### Scenario: 登录失败
- **WHEN** 调用方提交不存在的用户、错误密码或禁用用户凭据
- **THEN** 系统 MUST 返回认证失败响应，并且不得泄露具体是用户名不存在、密码错误还是账号禁用

#### Scenario: 刷新 Token
- **WHEN** 调用方使用有效且未撤销的 refresh token 请求刷新
- **THEN** 系统 MUST 签发新的 access token，轮换 refresh token，并撤销旧 refresh token

#### Scenario: 登出
- **WHEN** 已登录用户请求登出
- **THEN** 系统 MUST 撤销当前 refresh token，并使后续刷新请求失败

### Requirement: User Role Permission 权限模型
系统 MUST 使用 `User -> Role -> Permission` 模型表达访问控制，用户可拥有多个角色，角色可拥有多个权限点。

#### Scenario: 计算用户有效权限
- **WHEN** 用户拥有多个角色
- **THEN** 系统 MUST 将这些角色关联的权限合并为用户有效权限，并在当前用户响应中返回去重后的权限列表

#### Scenario: 角色变更后权限生效
- **WHEN** 管理员为用户新增或移除角色
- **THEN** 系统 MUST 在用户下一次登录或刷新会话后使用最新角色和权限签发 access token

### Requirement: 预置角色和默认权限
系统 MUST 预置 `viewer`、`operator`、`approver`、`admin` 角色，并为每个角色建立默认权限集合。

#### Scenario: viewer 只读访问
- **WHEN** 用户仅拥有 `viewer` 角色
- **THEN** 系统 MUST 允许其读取设备、配置快照、任务和审计摘要，并拒绝提交变更、审批、直接执行和管理操作

#### Scenario: operator 提交变更申请
- **WHEN** 用户拥有 `operator` 角色
- **THEN** 系统 MUST 允许其执行 viewer 权限、触发只读配置采集并提交设备配置变更申请

#### Scenario: approver 审批和直接执行
- **WHEN** 用户拥有 `approver` 角色
- **THEN** 系统 MUST 允许其执行 operator 权限、审批设备配置变更申请并直接执行设备配置变更

#### Scenario: admin 管理系统访问控制
- **WHEN** 用户拥有 `admin` 角色
- **THEN** 系统 MUST 允许其管理用户、角色、权限、系统配置和完整审计日志，并保留运维执行权限

### Requirement: 默认 API 鉴权和权限点授权
系统 MUST 对所有后端业务 API 默认要求认证，并按接口声明的权限点控制访问；只有健康检查、登录和刷新令牌等显式公开接口可匿名访问。

#### Scenario: 未登录访问业务 API
- **WHEN** 调用方未提供有效 access token 请求 `/api/v1` 下的业务接口
- **THEN** 系统 MUST 返回未认证响应，并且不得执行业务操作

#### Scenario: 权限不足访问业务 API
- **WHEN** 已认证用户请求其权限集合不包含的操作
- **THEN** 系统 MUST 返回禁止访问响应，并且不得执行业务操作

#### Scenario: 公开接口匿名访问
- **WHEN** 调用方请求健康检查、登录或刷新令牌接口
- **THEN** 系统 MUST 按接口语义处理请求，而不要求预先提供 access token

### Requirement: 当前用户和会话信息 API
系统 MUST 提供当前用户 API，使前端和其他调用方能够获取当前登录用户、角色、权限和会话状态。

#### Scenario: 查询当前用户
- **WHEN** 已认证用户请求当前用户接口
- **THEN** 系统 MUST 返回用户基础信息、角色列表、权限列表和会话有效状态

#### Scenario: access token 过期
- **WHEN** 调用方使用过期 access token 请求当前用户接口
- **THEN** 系统 MUST 返回未认证响应，并允许调用方通过有效 refresh token 刷新会话

### Requirement: 管理员访问控制管理
系统 MUST 仅允许具备管理权限的用户创建、禁用用户，分配角色，维护角色权限和查看权限点。

#### Scenario: 管理员分配角色
- **WHEN** admin 为用户分配或移除角色
- **THEN** 系统 MUST 保存角色关系变更，并记录角色变更审计日志

#### Scenario: 非管理员修改角色
- **WHEN** 不具备角色管理权限的用户尝试修改用户角色
- **THEN** 系统 MUST 返回禁止访问响应，并记录失败操作审计日志
