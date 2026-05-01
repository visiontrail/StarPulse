## 1. 数据模型与迁移

- [x] 1.1 扩展设备任务类型常量，新增配置快照采集任务类型和 datastore 白名单。
- [x] 1.2 新增 `DeviceConfigSnapshot` SQLAlchemy 模型，保存设备、来源任务、datastore、内容摘要、采集时间、差异摘要和安全摘要。
- [x] 1.3 编写 Alembic 迁移，创建配置快照表，并为 `device_id`、`source_task_id`、`datastore` 和 `collected_at` 建立索引。
- [x] 1.4 扩展 Repository，支持写入配置快照、查询同设备同 datastore 的上一份快照、查询最后快照和分页/限量查询快照列表。
- [x] 1.5 增加模型和 Repository 测试，验证快照字段、索引查询、最后快照和上一份快照查找行为。

## 2. NETCONF 只读采集

- [x] 2.1 扩展 `NetconfClient` 协议，新增 `get_config(params, datastore)` 只读方法。
- [x] 2.2 在 `NcclientNetconfClient` 中实现 `get-config` 调用，并复用现有连接参数、超时、host key 和错误映射。
- [x] 2.3 在 NETCONF 服务层新增配置读取方法，校验 datastore，返回标准操作结果和安全摘要输入。
- [x] 2.4 实现配置内容规范化与 digest 生成工具，确保同一配置内容生成稳定摘要。
- [x] 2.5 增加 NETCONF fake client 单元测试，覆盖配置读取成功、datastore 拒绝、标准错误映射和禁止写操作边界。

## 3. 快照服务与差异摘要

- [x] 3.1 新增配置快照服务，封装读取结果到快照模型的保存逻辑。
- [x] 3.2 实现同设备同 datastore 的差异摘要，至少包含是否变化、上一份快照标识和 digest 变化信息。
- [x] 3.3 确保任务 metadata、任务结果、API 响应和日志默认只暴露摘要、hash、采集时间和脱敏上下文。
- [x] 3.4 增加快照服务测试，覆盖首份快照、无变化快照、有变化快照和敏感信息不进入摘要。

## 4. Celery 任务闭环

- [x] 4.1 扩展任务服务，新增配置快照采集任务提交方法，保存 device_id、datastore 和安全 metadata。
- [x] 4.2 新增 Celery task 执行配置读取，启动时置为 `running`，成功时写入快照并置为 `succeeded`。
- [x] 4.3 处理配置读取失败路径，复用标准错误码、可展示错误消息和脱敏上下文，并将任务置为 `failed`。
- [x] 4.4 为配置读取任务输出结构化日志字段，包括 `action`、`task_id`、`device_id`、`datastore`、`status`、`error_code` 和 `duration_ms`。
- [x] 4.5 增加 Celery task 直接执行测试，验证成功、失败、状态流转、设备状态和结果摘要回写。

## 5. 后端 API 与 Schema

- [x] 5.1 新增配置快照相关 Pydantic schema，包括采集请求、快照摘要、差异摘要和列表响应。
- [x] 5.2 新增 `POST /api/v1/devices/{device_id}/config-snapshots`，校验设备可用性与 datastore 后投递配置读取任务。
- [x] 5.3 新增 `GET /api/v1/devices/{device_id}/config-snapshots`，返回按采集时间倒序排列的限量快照摘要。
- [x] 5.4 扩展设备详情或新增设备画像接口，返回连接状态、capabilities、system_info、最后配置快照和最近任务摘要。
- [x] 5.5 新增设备最近任务查询能力或在画像聚合中内嵌最近任务，并限制默认返回数量。
- [x] 5.6 增加 API 测试，覆盖任务投递、datastore 参数错误、快照列表、设备画像和敏感字段不泄漏。

## 6. 前端工程基础

- [x] 6.1 新建 `frontend/` Next.js + React + TypeScript 应用，并配置本地 API base URL。
- [x] 6.2 配置 Tailwind CSS 主题 token，映射 `DESIGN.md` 的暖色背景、暖黑文字、accent、oklab 边框、8px radius 和 mono 技术标签。
- [x] 6.3 引入 Radix UI/shadcn 风格基础组件和 `lucide-react` 图标，建立按钮、输入、菜单、表格、状态徽标和空态组件。
- [x] 6.4 建立类型安全 API client 和响应类型，覆盖设备、画像、任务、配置快照和采集请求。
- [x] 6.5 添加前端脚本和基础校验入口，包括 dev、build、lint 或 typecheck。

## 7. 前端 MVP 页面

- [x] 7.1 实现运维应用 shell，提供设备列表与设备详情的主从布局或等价扫描友好的布局。
- [x] 7.2 实现设备列表，展示设备名称、分组、连接状态、最后发现摘要和最后快照摘要。
- [x] 7.3 实现设备画像页，展示连接配置摘要、capabilities、system_info、最后配置快照和最近任务。
- [x] 7.4 实现只读配置采集控件，支持 datastore 选择、提交状态、重复提交防护和任务状态摘要展示。
- [x] 7.5 实现配置快照列表，展示 datastore、采集时间、内容摘要和差异摘要。
- [x] 7.6 实现加载、空状态、错误状态和重试交互，避免展示虚假设备数据。
- [x] 7.7 确保前端不提供配置编辑、提交、回滚或删除设备配置入口。

## 8. 文档与验证

- [x] 8.1 更新后端 README 或开发说明，记录配置快照采集 API、画像 API、任务查询和只读安全边界。
- [x] 8.2 更新本地运行说明，记录前端启动、API 地址配置和可选 NETCONF mock Server 集成测试。
- [x] 8.3 运行后端测试套件，确认模型、服务、API、任务和 NETCONF fake client 测试通过。
- [x] 8.4 运行前端 build/lint/typecheck，确认前端 MVP 可构建。
- [x] 8.5 执行 OpenSpec 校验或状态检查，确认 proposal、design、specs 和 tasks 均满足 schema 要求。
