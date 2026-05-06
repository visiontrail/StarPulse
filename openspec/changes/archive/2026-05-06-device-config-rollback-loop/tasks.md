## 1. 实施前验证

- [x] 1.1 确认 `DeviceConfigSnapshot` 当前是否持久化了适合派生 `edit-config` 的规范化配置内容；记录结论并解决设计开放问题 Q2。
- [x] 1.2 确认自动提案回滚的操作者归因策略（系统操作者 vs. originated_for_user_id）；解决设计开放问题 Q1，如有变化更新 design.md。
- [x] 1.3 与相关方确认回滚链式语义（D5 + 开放问题 Q3），如有变化更新 design.md。

## 2. 存储与迁移

- [x] 2.1 在 `DeviceConfigChangeRequest` 上新增 `is_rollback`、`rollback_of_change_id`（FK → device_config_change_requests）和 `rollback_target_snapshot_id`（FK → device_config_snapshots）列。
- [x] 2.2 若快照当前未持久化规范化内容，新增存储列或表以持久化回滚目标快照的规范化配置内容，并记录长度上限。
- [x] 2.3 为变更申请新字段及任何新增快照内容存储创建含降级支持的 Alembic 迁移。
- [x] 2.4 更新 Repository 辅助方法：查询设备+datastore 的进行中变更申请、读取快照规范化内容用于回滚派生、按 `rollback_of_change_id` 加载变更申请。

## 3. 快照回滚资格与载荷派生

- [x] 3.1 实现快照资格评估，返回 `rollback_eligible` 及快照缺少规范化内容或不可恢复时的阻塞码。
- [x] 3.2 新增仅供变更控制服务在事务内调用的 `RollbackPayloadDeriver` 服务；生成规范化 NETCONF `edit-config` 内容，附稳定摘要、长度、行数和来源标记 `rollback_from_snapshot:<id>`。
- [x] 3.3 确保派生器在回滚创建事务内运行，通过现有 `DeviceConfigChangePayload` 表写入载荷，且绝不通过 API 响应、任务元数据、审计元数据或日志返回派生载荷的完整原始内容。
- [x] 3.4 在快照列表和详情响应中暴露 `rollback_eligible` 和阻塞码，不扩展响应面至规范化内容。

## 4. 预检服务：回滚模式

- [x] 4.1 在预检请求 Schema 中新增 `mode: forward | rollback` 参数（默认 `forward`），并在保存的预检摘要中持久化 `mode` 字段。
- [x] 4.2 实现回滚模式校验：目标快照资格、目标/设备/datastore 匹配、同设备同 datastore 无进行中（`queued | running | verifying`）变更，以及设置 `rollback_of_change_id` 时的来源变更状态。
- [x] 4.3 在回滚模式下放宽基线新鲜度规则，同时仍要求最近一次成功快照存在以判断与回滚目标的差异。
- [x] 4.4 输出阻塞码 `CHANGE_IN_FLIGHT`、`ROLLBACK_TARGET_NOT_RESTORABLE`、`ROLLBACK_NO_DIVERGENCE` 和 `ROLLBACK_ORIGIN_NOT_RECOVERABLE`，附安全可展示原因。
- [x] 4.5 收紧正向模式预检以同样强制 `CHANGE_IN_FLIGHT` 规则（对称并发控制），若当前未强制则在本次变更中补齐。
- [x] 4.6 为回滚模式预检新增后端测试：成功、进行中阻塞、目标不可恢复、无差异、来源不可恢复、直接执行缺少原因。

## 5. 变更申请服务：回滚提交

- [x] 5.1 扩展变更申请提交路径以接受可选的 `is_rollback`、`rollback_target_snapshot_id`、`rollback_of_change_id`；手动回滚提交须校验 `device:change:approve` 权限。
- [x] 5.2 将载荷派生嵌入提交事务，确保存储的载荷摘要、长度和行数由服务端生成，绝不来自客户端。
- [x] 5.3 在变更申请上持久化回滚链路字段和 `mode = rollback` 预检摘要。
- [x] 5.4 在审批和直接执行时重新运行回滚模式预检；若存储摘要或实时重派生摘要不再有效则拒绝。
- [x] 5.5 在执行任务从队列拉起时重新校验存储载荷摘要与目标快照当前规范化内容摘要一致；不一致则标记 `failed`。
- [x] 5.6 为回滚提交、审批、直接执行（含/不含原因）、摘要重校验和 viewer/operator RBAC 拒绝新增后端测试。

## 6. 应用-验证工作器：回滚分支

- [x] 6.1 复用现有应用-验证工作器路径；不引入新 NETCONF 原语。
- [x] 6.2 在验证阶段以回滚目标快照的规范化内容摘要作为成功判定依据（标准写入成功检查之外）。
- [x] 6.3 当 `is_rollback = true` 的变更以 `verification_failed` 结束时禁止自动提案递归。
- [x] 6.4 实现非回滚变更以 `verification_failed` 结束时的自动提案创建：生成状态为 `pending_approval` 的回滚申请（含 `rollback_of_change_id`、`rollback_target_snapshot_id = origin.baseline_snapshot_id`）、运行回滚模式预检、写入 `change.rollback_proposed` 审计，但绝不投递执行任务。
- [x] 6.5 当来源变更无基线快照时跳过自动提案创建，记录含原因的失败审计事件。
- [x] 6.6 新增工作器测试：回滚写入成功+验证成功、回滚写入成功+验证摘要不匹配、回滚写入失败、正向验证失败时自动提案创建、回滚验证失败时不递归、来源无基线时不创建自动提案。

## 7. 审计事件

- [x] 7.1 输出 `change.rollback_proposed`（自动）、`change.rollback_submitted`（手动）、`change.rollback_executed`、`change.rollback_verified` 和 `change.rollback_verification_failed` 事件，包含文档规定的上下文字段，并遵守现有脱敏规则。
- [x] 7.2 扩展现有变更控制审计事件（提交、审批、直接执行、验证）以在字段存在时包含 `is_rollback`、`rollback_of_change_id` 和 `rollback_target_snapshot_id`。
- [x] 7.3 为审计写入器新增测试：脱敏校验（无载荷正文、无凭据）和每个新事件的必要字段存在性。

## 8. 前端 API 与类型

- [x] 8.1 扩展前端 TypeScript 类型以覆盖 `mode`、回滚链路字段、`rollback_eligible` 和回滚专属阻塞码。
- [x] 8.2 新增 API client 方法：回滚模式预检预览、快照驱动的回滚提交、获取与验证失败变更关联的自动提案、刷新变更详情/列表读取。
- [x] 8.3 规范 API 错误处理，确保回滚阻塞码（`CHANGE_IN_FLIGHT`、`ROLLBACK_TARGET_NOT_RESTORABLE`、`ROLLBACK_NO_DIVERGENCE`、`ROLLBACK_ORIGIN_NOT_RECOVERABLE`）以简洁的用户可读消息渲染。
- [x] 8.4 确认新回滚流程未在 localStorage 或 sessionStorage 中持久化载荷正文、原始快照内容或凭据。

## 9. 前端控制台：回滚入口

- [x] 9.1 在快照列表和详情视图新增"恢复到此快照"动作，受 `device:change:approve` 和 `rollback_eligible = true` 双重保护；不满足条件时禁用入口并展示清晰原因。
- [x] 9.2 打开回滚提交对话框，运行 `mode = rollback` 预检，展示目标快照摘要、当前快照摘要、派生载荷摘要、风险等级和受控比较，且不要求用户上传或粘贴载荷正文。
- [x] 9.3 在 `verification_failed` 变更详情中，若自动提案已存在则展示"查看待审批回滚提案"链接；否则仅为 approver/admin 展示"提案回滚"动作。
- [x] 9.4 在回滚变更详情中渲染额外的"回滚上下文"卡片，含来源变更链接、目标快照链接、比较摘要和 `is_rollback` 标记。
- [x] 9.5 为回滚执行添加运行中、验证中、已执行、验证失败、失败显示状态，与正向变更保持相同的脱敏保证。
- [x] 9.6 验证每个新回滚入口的 viewer/operator/approver/admin 权限控制。

## 10. 文档与验证

- [x] 10.1 更新后端 README 阶段边界，描述受控回滚闭环（自动提案、手动恢复、载荷派生、目标摘要验证）。
- [x] 10.2 记录本地运维工作流：触发验证失败、查看自动提案、审批或直接执行回滚、观察 post-change 验证。
- [x] 10.3 更新前端 README，说明回滚开发流程，包含快照驱动入口和验证失败提案链接。
- [x] 10.4 运行后端测试和 lint 检查。
- [x] 10.5 运行前端类型检查、lint 和构建检查。
- [x] 10.6 运行 OpenSpec 状态和 `device-config-rollback-loop` 验证。
