## Why

当前系统已具备设备、配置快照和运维控制台基础能力，但缺少统一登录、认证、权限控制和审计闭环。随着后续引入变更申请、审批、直接执行等高风险运维动作，系统需要先建立可追溯、默认安全的身份与访问控制基线。

## What Changes

- 引入用户登录、JWT 访问令牌、刷新令牌、登出和前端会话管理能力。
- 建立 `User -> Role -> Permission` 权限模型，后端 API 默认要求认证，并按权限点控制访问。
- 建立设备配置变更申请、审批和直接执行的权限边界，使高风险写操作必须经过 RBAC 校验。
- 预置 `viewer`、`operator`、`approver`、`admin` 角色及其默认权限边界：
  - `viewer` 只读访问设备、快照、任务和审计摘要。
  - `operator` 可在只读能力基础上提交设备配置变更申请。
  - `approver` 可审批变更申请，并可绕过普通提交-审批流程直接执行设备配置变更。
  - `admin` 可管理用户、角色、权限和系统配置。
- 引入关键审计日志，覆盖登录、登出、角色变更、变更申请提交、审批、直接执行和失败操作。
- 调整现有后端 API 和前端控制台，使其从匿名只读访问变为受认证和权限控制的访问。

## Capabilities

### New Capabilities

- `auth-rbac-session-management`: 覆盖用户身份、JWT 登录、刷新令牌、登出、RBAC 权限模型、默认 API 鉴权、前端会话管理和权限点检查。
- `device-config-change-control`: 覆盖设备配置变更申请提交、审批、驳回、执行、approver 直接执行和相关状态流转。
- `audit-logging`: 覆盖关键安全与运维操作的审计事件记录、查询边界、脱敏和失败操作追踪。

### Modified Capabilities

- `ground-management-platform-foundation`: 后端基础 API、Repository、迁移和配置需要增加身份认证、授权中间件、用户/角色/权限/审计存储基础。
- `operations-console-frontend`: 前端从匿名只读控制台调整为登录后访问，并根据用户权限展示会话状态、导航入口和受控操作。
- `device-config-snapshots`: 设备、快照和任务相关 API 需要默认鉴权，并对配置采集、任务查询和快照读取应用权限点控制。

## Impact

- 后端 API：新增认证、刷新令牌、登出、当前用户、用户/角色/权限管理、配置变更申请/审批/直接执行、审计日志查询等接口，并为既有 API 接入统一认证和权限依赖。
- 数据模型与迁移：新增 users、roles、permissions、user_roles、role_permissions、refresh_tokens、device_config_change_requests、audit_logs 等持久化结构。
- 前端控制台：新增登录页、会话恢复、Token 刷新、登出、权限感知的导航和操作状态。
- 安全与配置：新增 JWT 密钥、访问令牌有效期、刷新令牌有效期、密码哈希、审计日志保留等配置项。
- 测试：新增认证/RBAC 单元测试、API 权限矩阵测试、前端会话测试和审计日志验证。
