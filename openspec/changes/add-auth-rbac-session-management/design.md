## Context

Star Pulse 当前后端是 FastAPI + SQLAlchemy/Alembic + Celery 的模块化服务，已有 `/api/v1/devices`、`/api/v1/tasks` 和健康检查接口；前端是 Next.js/React 单页运维控制台，当前默认匿名访问设备、快照和任务数据。现有能力已经触达设备连接、NETCONF 只读采集和任务闭环，后续引入配置变更申请、审批和直接执行前，需要先把身份、权限、审计和前端会话作为平台级基础能力落地。

## Goals / Non-Goals

**Goals:**

- 为后端提供本地用户身份、密码哈希、JWT access token、refresh token 轮换和登出撤销。
- 用 `User -> Role -> Permission` 模型统一表达预置角色、权限点和 API 授权。
- 将 `/api/v1` 下除显式公开接口外的 API 统一纳入认证，并在具体路由上声明权限点。
- 支持设备配置变更申请、审批、approver 直接执行，并对高风险动作记录审计日志。
- 为前端提供登录、会话恢复、自动刷新、登出和权限感知的操作状态。

**Non-Goals:**

- 不引入 SSO、LDAP、OAuth 外部身份提供方或多因素认证。
- 不实现复杂策略语言、资源级 ABAC 或跨租户隔离。
- 不扩大 AI 模块自动决策范围；审批和直接执行仍由具备权限的人类用户触发。
- 不在本次变更中实现完整配置回滚、批量变更编排或长期工单系统。

## Decisions

1. **本地身份存储与密码哈希**

   后端新增 `app/auth/` 模块，使用 SQLAlchemy 模型保存用户、角色、权限和 refresh token；密码仅保存强哈希值，登录时通过密码哈希库校验。这样与当前自托管、开源、无商业绑定的项目约束一致。备选方案是接入外部 IdP，但会增加部署依赖，不适合作为当前阶段的基础能力。

2. **短期 access token + 持久化 refresh token 轮换**

   access token 使用 JWT，包含 `sub`、`roles`、`permissions`、`iat`、`exp` 和 token id；refresh token 使用高熵随机值，只保存哈希和过期/撤销状态。刷新时轮换 refresh token，登出时撤销当前 refresh token。备选的完全无状态 refresh JWT 难以做登出撤销和泄漏止损，因此不采用。

3. **默认鉴权与显式公开 allowlist**

   在 API 路由层建立默认认证依赖：`/api/v1` 下的业务接口默认要求有效用户；健康检查、登录、刷新令牌等接口作为显式公开 allowlist。具体路由继续声明 `require_permission("<permission>")`，避免只验证登录而遗漏 RBAC。这样可以让新增 API 默认安全，减少逐个路由漏加认证的风险。

4. **权限点以常量和种子数据双轨维护**

   代码中维护权限常量，数据库通过迁移或幂等 seed 保证预置权限和角色存在。预置角色映射为：`viewer` 拥有设备/快照/任务只读和审计摘要读取；`operator` 继承 viewer 并可提交变更申请、触发只读采集；`approver` 继承 operator 并可审批和直接执行设备配置变更；`admin` 拥有用户、角色、权限、系统配置和完整审计管理权限，同时保留运维执行权限。

5. **配置变更控制独立于只读快照能力**

   新增 `app/devices/change_requests.py` 或等价服务边界管理配置变更申请、审批和执行。只读快照服务继续只执行 `get-config`；配置写入只允许在变更控制服务中通过明确权限和审计后触发。普通 operator 提交申请后进入待审批；approver 审批后触发执行；approver 也可以带原因直接执行并产生 bypass 审计事件。

6. **审计日志与业务操作同事务优先**

   登录/登出、角色变更、变更申请、审批、直接执行和失败操作都写入 `audit_logs`。对业务状态变更，审计事件与业务记录尽量在同一数据库事务中提交；对认证失败等没有业务事务的事件，使用独立写入。审计 metadata 必须经过脱敏，不能记录密码、token、私钥或完整设备配置正文。

7. **前端以 HttpOnly refresh cookie 恢复会话**

   登录接口返回 access token，并通过 HttpOnly、SameSite cookie 设置 refresh token；前端将 access token 保存在内存状态中，请求 401 时调用刷新接口恢复。页面刷新后前端通过 refresh 接口恢复当前用户和权限。备选 localStorage refresh token 更容易被脚本读取，不作为默认方案。

## Risks / Trade-offs

- [Risk] 默认鉴权可能导致现有前端和测试在未登录时全部失败 -> Mitigation: 先补认证测试夹具和前端登录流程，再逐步给既有 API 加权限断言。
- [Risk] refresh cookie 跨端口开发环境需要正确 CORS 和 credentials 配置 -> Mitigation: 增加开发环境允许源配置，并在前端 API client 统一设置 `credentials: "include"`。
- [Risk] 角色种子数据和人工修改可能漂移 -> Mitigation: 权限 seed 必须幂等，只补齐系统权限，不删除已有自定义关系；测试覆盖预置角色权限矩阵。
- [Risk] approver 直接执行绕过审批会放大误操作风险 -> Mitigation: 强制记录原因、目标、配置摘要、操作者和结果，并在前端以独立入口呈现直接执行语义。
- [Risk] 审计写入失败可能阻断关键运维动作 -> Mitigation: 对高风险写操作审计失败时阻断业务提交；对登录失败等安全事件至少输出结构化日志并返回标准错误。

## Migration Plan

1. 新增依赖、配置项、认证模块、数据库模型和 Alembic 迁移。
2. 添加幂等 seed，创建预置权限、角色和本地开发管理员账号初始化入口。
3. 增加认证/授权依赖和 auth API，再把既有 `/api/v1` 业务路由接入默认鉴权和权限点。
4. 实现配置变更申请、审批、直接执行服务和 API，并接入任务/NETCONF 执行边界。
5. 实现审计日志写入、查询 API 和脱敏策略。
6. 更新前端登录、会话、权限感知 UI 和 API client。
7. 补齐后端权限矩阵测试、审计测试、前端会话测试后运行质量检查。

Rollback 策略：保留迁移可回退脚本；若认证接入导致发布阻断，可回滚到未启用默认鉴权的上一版本。生产环境不得通过配置关闭审计或绕过高风险写操作权限。

## Open Questions

- 初始管理员账号使用一次性环境变量创建，还是提供命令行初始化脚本？
- access token 和 refresh token 的默认有效期是否采用 15 分钟/7 天，还是按部署环境区分？
- 设备配置变更正文是否在首版持久化完整内容，还是仅保存外部引用和摘要以降低敏感信息暴露面？
