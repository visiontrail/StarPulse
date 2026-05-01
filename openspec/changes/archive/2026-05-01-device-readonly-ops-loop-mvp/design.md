## Context

当前后端已经具备设备 CRUD、连接配置、凭据引用、NETCONF 连接测试、能力发现、最后发现结果、任务状态闭环、结构化日志和可选 mock Server 集成测试。缺口在于：能力发现之后还不能读取设备配置，设备详情仍偏基础对象视角，运维人员缺少一个从设备画像到配置快照再到最近任务的只读查询入口。

本阶段是只读运维闭环 MVP。后端继续以 FastAPI、SQLAlchemy/Alembic、Celery/RabbitMQ、`ncclient` 适配层为基础；前端新增 `frontend/` 应用，建议使用 Next.js/React、TypeScript、Tailwind CSS、Radix UI/shadcn 风格组件和 `lucide-react` 图标。视觉风格遵循 `DESIGN.md`：暖色 off-white 画布、低噪声边框、紧凑但可扫描的运维信息布局、克制的卡片和表格。

## Goals / Non-Goals

**Goals:**

- 通过 NETCONF `get-config` 读取指定 datastore 的配置，并用异步任务执行真实设备访问。
- 持久化配置快照，记录设备、来源任务、datastore、内容摘要、采集时间、差异摘要和安全结果摘要。
- 扩展设备详情为当前画像，聚合连接状态、连接配置摘要、capabilities、system_info、最后配置快照和最近任务。
- 提供运维查询 API：触发配置采集、查询设备画像、查询设备快照、查询最近任务和任务状态。
- 提供前端 MVP：设备列表、设备详情画像、只读采集动作、快照列表/摘要、任务状态反馈。
- 保持只读安全边界，避免 API 响应、任务 metadata、日志和快照摘要泄漏凭据或完整敏感配置。

**Non-Goals:**

- 不实现 NETCONF `edit-config`、commit、rollback、candidate 配置编辑或任何配置下发。
- 不实现完整配置版本库、全文搜索、复杂三方 diff 视图或配置回滚策略。
- 不实现多协议采集；MVP 继续限定 NETCONF。
- 不引入商业 SaaS、商业 UI 套件、专有云服务或外部托管依赖。
- 不实现复杂 AI 运维编排、自动诊断或审批流。

## Decisions

### 1. 配置采集作为新的设备异步任务

新增任务类型 `device.config_snapshot` 或等价常量，由 `POST /api/v1/devices/{device_id}/config-snapshots` 投递。任务创建时保存 `device_id`、`datastore` 和安全 metadata，Worker 启动后置为 `running`，成功后写入配置快照并置为 `succeeded`，失败时复用现有标准错误码和脱敏上下文。

备选方案是同步执行 `get-config`。同步接口更短，但配置读取可能受设备负载、网络延迟和 datastore 大小影响，容易拖慢 API 请求并绕开已有任务闭环。

### 2. NETCONF client 抽象增加 `get_config`

在 `NetconfClient` 协议、`NcclientNetconfClient` 和 `NetconfService` 中增加 `get_config(params, datastore)`。适配层负责调用 `ncclient` 的 `get_config`，服务层负责错误归一化、摘要生成输入规范化和结果结构化。datastore MVP 支持 `running`，允许扩展到 `candidate`、`startup`，但必须校验枚举值。

备选方案是在 Worker 中直接调用 `ncclient.manager.get_config`。该方案耦合第三方库细节，后续 fake client、集成测试和错误映射都会分散。

### 3. 快照保存摘要优先，明文配置受控

新增 `DeviceConfigSnapshot` 模型，至少包含 `device_id`、`source_task_id`、`datastore`、`content_digest`、`collected_at`、`diff_summary`、`summary` 和可选 `content_preview` 或受控 `content_ref`。MVP API 默认返回摘要和预览，不返回完整配置正文；如果实现保存正文，必须通过单独字段/接口显式控制并经过脱敏。

备选方案是只把快照写进任务 `result_summary`。该方案没有独立生命周期，无法支持设备详情聚合、快照列表和后续历史对比。

### 4. 差异摘要基于上一份同 datastore 快照生成

快照写入时查找同设备、同 datastore 的上一份快照，基于摘要或规范化文本计算简单差异摘要，例如 `changed`、`previous_snapshot_id`、`digest_changed`、`line_delta`、`collected_at_delta`。MVP 不要求精细逐行 diff UI，但必须能告诉运维人员“是否变化”和“与哪份快照比较”。

备选方案是前端拉取两份快照后自行 diff。这样会把敏感配置暴露给浏览器，也让后端审计与脱敏边界变弱。

### 5. 设备画像由后端聚合

新增或扩展设备详情 schema，返回 `profile` 或等价结构：设备基础信息、连接状态、连接配置摘要、last_discovery 的 capabilities/system_info、last_config_snapshot、recent_tasks。聚合逻辑放在设备服务/Repository 层，避免前端为了一个详情页串联多个接口并自行合并状态。

备选方案是前端分别调用设备详情、任务列表、快照列表再组装。该方案实现灵活，但会产生更多请求和不一致的 loading/error 状态，不适合作为 MVP 主路径。

### 6. 运维查询 API 使用资源化路径

后端保留现有 `/api/v1/devices` 与 `/api/v1/tasks/{task_id}`，新增：

- `POST /api/v1/devices/{device_id}/config-snapshots`：投递只读配置采集任务，可接收 `datastore`。
- `GET /api/v1/devices/{device_id}/profile` 或增强 `GET /api/v1/devices/{device_id}`：读取当前画像。
- `GET /api/v1/devices/{device_id}/config-snapshots`：查询设备快照列表。
- `GET /api/v1/devices/{device_id}/tasks?limit=...` 或在画像中内嵌最近任务：查询最近任务摘要。

是否单独新增 `/profile` 由实现阶段结合兼容性决定；无论选择哪条路径，设备详情契约必须满足规格中的画像字段。

### 7. 前端 MVP 采用独立 `frontend/` Next.js 应用

新建 `frontend/`，使用 App Router、TypeScript、Tailwind CSS、Radix UI/shadcn 风格基础组件和 `lucide-react`。页面优先服务运维扫描与操作：左侧或顶部设备导航，主区域展示设备画像、状态、capabilities、system_info、最后快照、最近任务和只读采集按钮。Tailwind 主题映射 `DESIGN.md` 的暖色 palette、8px radius、oklab 边框、紧凑表格、mono 技术标签和克制图标按钮。

备选方案是先用静态 HTML 或后端模板。静态实现更快，但不利于后续任务轮询、状态组件和设计系统沉淀。

### 8. 测试和验证分层推进

后端增加模型/Repository、NETCONF fake client、服务层、Celery task 和 API 测试；前端至少提供 TypeScript 构建、lint 或等价静态校验，并对 API client、关键页面空态/加载/错误态做轻量测试。可选集成测试继续使用远端 NETCONF mock Server，并允许未启用时跳过。

## Risks / Trade-offs

- [Risk] `get-config` 可能返回敏感配置内容 -> Mitigation: 默认只在 API 和任务结果中返回摘要、hash、差异摘要和安全预览；日志与 metadata 继续走脱敏。
- [Risk] 真实设备 datastore 支持差异较大 -> Mitigation: MVP 校验 datastore 枚举并优先支持 `running`，失败映射到稳定错误码和可展示消息。
- [Risk] 配置正文较大会拖慢数据库和 API -> Mitigation: MVP 保存摘要优先；如需正文，使用 `Text` 字段加返回限制或后续演进为对象存储/content_ref。
- [Risk] 画像聚合接口可能变胖 -> Mitigation: 限制最近任务数量和快照摘要字段，列表页仍使用轻量 schema。
- [Risk] 新增前端会扩大工具链和 CI 成本 -> Mitigation: 前端独立目录与脚本，先落地 build/lint/typecheck 的最小验证。

## Migration Plan

1. 新增数据库迁移，创建配置快照表并为设备、任务、datastore、采集时间建立必要索引。
2. 扩展常量、schema、Repository、服务层和 NETCONF 抽象，增加 `get-config` 与快照摘要逻辑。
3. 新增 Celery task 和任务投递 API，保证成功/失败路径回写任务与设备状态。
4. 扩展设备详情或新增画像 API，聚合 discovery、快照和最近任务。
5. 新建前端工程、设计系统 token、基础组件、API client 和 MVP 页面。
6. 更新 README 或开发说明，记录后端 API、前端启动方式和只读安全边界。
7. 回滚时撤回新增路由、任务类型、Worker 逻辑和前端目录；数据库可通过 Alembic downgrade 删除快照表，不影响已有设备接入与能力发现能力。

## Open Questions

- MVP 是否保存完整配置正文，还是只保存摘要、差异摘要和有限预览。
- 设备详情画像是增强现有 `GET /api/v1/devices/{device_id}`，还是新增 `GET /api/v1/devices/{device_id}/profile` 以保持基础详情兼容。
- 前端任务状态是否使用短轮询，还是先以手动刷新为 MVP。
