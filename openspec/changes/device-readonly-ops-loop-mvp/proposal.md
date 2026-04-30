## Why

设备接入后目前只能完成连接测试与能力发现，缺少对设备当前配置、运行画像和最近任务的统一只读查询闭环。MVP 需要让运维人员在不下发配置的前提下，完成“读取设备状态 -> 保存配置快照 -> 查看设备画像与任务历史 -> 前端呈现”的最小闭环。

## What Changes

- 增加 NETCONF `get-config` 与基础状态读取能力，支持按 datastore 读取设备配置并复用现有认证、错误归一化、日志脱敏和异步任务机制。
- 新增设备配置快照持久化，保存来源任务、datastore、配置内容摘要、采集时间和差异摘要；MVP 不保存可直接泄漏敏感信息的明文配置内容。
- 扩展设备详情为“当前画像”，返回连接状态、capabilities、system_info、最后配置快照和最近任务摘要。
- 新增面向运维查询闭环的 API，包括触发只读采集、查询设备画像、查询快照列表/详情摘要和查询最近任务。
- 新增前端 MVP，使用 Next.js/React、TypeScript、Tailwind CSS、Radix UI/shadcn 风格基础组件和 `lucide-react` 图标，并按 `DESIGN.md` 的暖色、低噪声、专业运维界面风格定制设计系统。

## Capabilities

### New Capabilities
- `device-config-snapshots`: 覆盖 NETCONF `get-config` 只读采集、配置快照持久化、摘要与差异摘要生成、快照查询和相关任务闭环。
- `operations-console-frontend`: 覆盖只读运维查询 MVP 的前端应用、设备列表/详情、配置快照、最近任务和设计系统约束。

### Modified Capabilities
- `device-access-capability-discovery`: 扩展设备详情读取契约，使其返回完整当前画像，包括连接状态、capabilities、system_info、最后配置快照和最近任务摘要。

## Impact

- 影响后端 `backend/app/netconf/`、`backend/app/devices/`、`backend/app/tasks/`、`backend/app/storage/`、`backend/app/api/` 和 `backend/tests/`。
- 需要新增数据库模型与 Alembic 迁移，用于保存配置快照、摘要字段、datastore、采集时间、来源任务和差异摘要。
- 需要新增或扩展任务类型、Repository、服务层、API schema、Celery job 和 NETCONF client 抽象。
- 需要新增前端工程目录、依赖配置、Tailwind 主题、基础组件、API client、页面与前端测试或构建校验。
