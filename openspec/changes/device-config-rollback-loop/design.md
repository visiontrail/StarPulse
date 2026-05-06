## 背景

变更控制流水线已覆盖：服务端预检（设备就绪、datastore 支持、载荷存在、权限）、审批/直接执行路径（含审计）、以及通过 NETCONF `edit-config` 写入后采集只读 post-change 快照的应用-验证工作器。然而当变更以 `verification_failed` 结束时，恢复完全依赖人工操作——运维人员必须从历史快照重新推导载荷并重新提交，这与现有安全闭环要消除的操作路径完全相同。

本设计在不引入新 NETCONF 写原语的前提下，通过回滚工作流对现有流水线进行扩展。回滚被建模为一次普通受控变更，其载荷由服务端从先前已知良好的 `DeviceConfigSnapshot` 派生，再经过相同的预检/审批/执行/验证路径处理。增量价值在于链路追踪、派生安全性和并发规则，而非新的写能力。

相关方：后端（变更服务、预检、NETCONF 工作器、快照服务、审计）、前端（变更详情视图、快照视图、角色感知动作）、运维人员（approver/admin）和下游审计人员。

## 目标 / 非目标

**目标：**
- 提供受控、可审计追踪的路径，将设备恢复到历史采集快照的状态，与正向变更享有相同的安全保证。
- 当应用-验证运行以 `verification_failed` 结束时，自动建议回滚提案（不自动执行），使恢复路径在失败界面一键可达。
- 防止回滚滥用：同设备同 datastore 不允许并发进行中的变更，目标快照必须成功采集且已持久化，不允许回滚到仅含摘要的"合成"快照。
- 保持原始配置不传给客户端——派生在服务端事务内完成，回滚申请只存储摘要、行数和受控比较字段，与现有变更记录一致。
- 复用既有审计、RBAC 和风险摘要接口，只新增可追溯性所需的回滚专属字段。

**非目标：**
- 引入新 NETCONF 原语，如 `rollback`、`confirmed-commit`、`copy-config` 或 `discard-changes`。平台仅保留 `edit-config`。
- 多设备或维护窗口级别的批量回滚编排（一次回滚 = 一个设备 + 一个 datastore = 一个变更申请）。
- 时光机 UX（如"回滚到 3 小时前"）。目标必须是明确的快照 ID。
- 在无需人工审批的情况下自动执行回滚，即使在 `verification_failed` 场景下。我们自动创建*提案*，从不创建*执行*。
- YANG 感知的差异或部分回滚。回滚恢复目标快照采集时的完整 datastore 内容。

## 决策

### D1. 回滚是一条 `DeviceConfigChangeRequest` 记录，而非独立实体

回滚以普通变更申请形式持久化，新增三列：`is_rollback: bool`、`rollback_of_change_id: int | None`（失败恢复型回滚的来源变更）和 `rollback_target_snapshot_id: int | None`。所有现有字段（载荷摘要、基线快照、预检摘要、验证快照等）保持原有语义。

**为何优于备选方案：**
- *独立 `RollbackRequest` 表*——会重复 RBAC、预检、审计和执行脚手架。运维人员还要处理两套不同工作流。已否决。
- *仅布尔标记，无来源/目标外键*——丢失从失败到恢复的审计链路。已否决。

回滚申请的载荷在提交时于服务端派生，存入现有 `DeviceConfigChangePayload` 表，`summary_source = "rollback_from_snapshot:<id>"`。下游代码（预检、工作器、审计）对其与手工载荷一视同仁——仅字节的*来源*不同。

### D2. 回滚载荷由服务端从快照派生后冻结

创建回滚申请时，新增服务辅助方法 `RollbackPayloadDeriver.build(target_snapshot_id, datastore)` 在申请事务内运行，返回可将目标快照内容恢复到同一 datastore 的规范化 NETCONF `edit-config` 内容。

规则：
- 目标快照必须是成功持久化的 `DeviceConfigSnapshot`（通过 `source_task_id` 对应任务的状态过滤），必须属于同一设备，且必须匹配所请求的 datastore。
- 派生器使用快照存储的规范化内容。若快照仅存储摘要+受控汇总（当前模型存有 `content_digest` 和内容 blob——在 tasks.md 中实施前需验证），则该变更以存储回滚目标快照的规范化内容为前置条件。
- 派生载荷哈希后的存储方式与正向变更载荷完全相同。前端永远看不到原始内容，只能看到摘要、长度、行数和与基线的受控比较结果。
- 当目标快照的规范化内容从未以受控形式持久化时，派生器必须拒绝，并返回阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`。

**为何优于备选方案：**
- *客户端提供回滚载荷*——重新引入了本变更要消除的手工构造攻击面。已否决。
- *每次预检时都重新派生*——浪费计算资源，且预览与执行之间存在漂移风险。我们在提交时派生一次、冻结，执行时仅重新校验摘要。

### D3. 回滚预检有独立模式，附加额外规则

现有预检服务新增 `mode: "forward" | "rollback"` 参数。回滚模式额外校验：
- `rollback_target_snapshot_id` 必须存在，指向同设备同 datastore 的成功快照，并通过 D2 的可恢复性检查。
- 同设备同 datastore 不得存在其他进行中（`queued | running | verifying`）的变更申请。新增阻塞码：`CHANGE_IN_FLIGHT`。
- 若设置了 `rollback_of_change_id`，来源变更必须处于 `verification_failed` 或 `failed` 状态。新增阻塞码：`ROLLBACK_ORIGIN_NOT_RECOVERABLE`。
- 回滚模式**放宽**基线新鲜度规则：当前设备状态即为隐含基线。我们仍要求最近一次成功快照存在以确认目标与当前状态存在差异（否则无需回滚），但不要求其在 `STAR_PULSE_BASELINE_SNAPSHOT_FRESHNESS_MINUTES` 阈值内。当目标快照内容摘要等于当前快照摘要时新增阻塞码：`ROLLBACK_NO_DIVERGENCE`。

预检其余部分（权限、datastore 支持、载荷非空、直接执行时原因非空）保持不变。

### D4. 验证失败时自动生成提案，绝不自动执行

当应用-验证工作器将变更申请写入 `verification_failed` 时，同时创建一条兄弟 `DeviceConfigChangeRequest`：`is_rollback=true`、`rollback_of_change_id=<来源>`、`rollback_target_snapshot_id=<来源.baseline_snapshot_id>`，状态为 `pending_approval`，`actor_user_id` 设为系统操作者标识（或在工作器上下文可用时使用来源操作者——见开放问题）。工作器运行回滚模式预检，存储安全摘要，并写入 `change.rollback_proposed` 审计事件。

工作器不投递执行任务。必须由具备审批权限的用户（approver/admin）批准或直接执行，与其他变更完全一致。前端在原始失败变更详情和待审批队列中均展示自动创建的提案。

**为何优于备选方案：**
- *自动执行回滚*——风险过高；若失败原因是短暂的网络抖动，自动回滚会放大抖动影响。已否决。
- *仅展示"创建回滚"按钮而不自动创建*——在最糟糕的时刻（刚发生变更失败）增加运维摩擦。自动创建一条提案是合理的平衡点。

### D5. 回滚执行复用现有应用-验证工作器路径，不做修改

Celery 任务已完成：标记 `running`、调用 `edit-config`、标记 `verifying`、执行 `get-config`、计算比较摘要、标记 `executed` 或 `verification_failed`。回滚时唯一的行为差异：
- 验证阶段以回滚目标快照的内容摘要作为**成功判定依据**（在标准写入成功检查之外）。
- 回滚变更的 `verification_failed` 不触发新的自动回滚提案。通过检查来源变更的 `is_rollback` 字段显式禁止递归。新增审计事件：`change.rollback_verification_failed`。

### D6. 审计事件仅做增量扩展

五个新事件名：`change.rollback_proposed`、`change.rollback_submitted`（approver/admin 手动提交）、`change.rollback_executed`、`change.rollback_verified`、`change.rollback_verification_failed`。所有事件包含 `rollback_of_change_id`、`rollback_target_snapshot_id`、标准变更控制字段，并遵守现有脱敏规则。现有正向变更审计事件不变。

### D7. RBAC：回滚仅限 approver/admin

提交回滚（手动或通过自动提案的批准动作）需要 `device:change:approve`（现有 approver 权限）。operator 不能提交回滚申请，因为回滚按定义总是越过审批门槛（它是对已审批失败变更的补救）。回滚直接执行使用现有 `device:change:execute`，并要求填写非空原因。

**为何优于备选方案：**
- *允许 operator 像正向变更一样提案回滚*——容易在 operator 发起和工作器自动提案之间产生竞态和争议。v1 已否决，可根据运营反馈重新评估。

### D8. 前端接入面增量扩展，复用现有组件

- 快照详情/列表（approver+）：新增"恢复到此快照"动作，打开已预填回滚模式的标准变更提交对话框。
- 变更详情（任何有查看权限的角色）：当 `is_rollback` 为真时，渲染额外的"回滚上下文"卡片，含来源变更链接、目标快照链接和回滚比较结果。
- 失败变更详情：若自动提案存在，展示"查看待审批回滚提案"链接；若不存在（如本特性上线前的历史失败），为 approver/admin 展示"提案回滚"动作。
- 本次变更不在范围内对 `app/page.tsx` 做结构性重构；我们以与现有变更视图同级的方式新增视图，接受文件体积代价。专项拆分变更是处理该技术债的正确时机。

## 风险 / 权衡

- **风险：未持久化规范化内容的快照无法作为回滚目标。** → 应对：显式 `ROLLBACK_TARGET_NOT_RESTORABLE` 阻塞码，前端置灰入口并展示原因。在 README 中说明并给出清晰提示，而非静默失败。
- **风险：回滚派生载荷被设备拒绝（如快照中采集了只读节点，无法通过 `edit-config` 写入）。** → 应对：现有应用路径已通过标记 `failed` 处理 `edit-config` 失败；回滚继承此行为。新增工作器测试模拟该场景。
- **风险：回滚进行中时并发提交正向变更。** → 应对：`CHANGE_IN_FLIGHT` 阻塞码对称适用——回滚模式拒绝其他进行中变更，正向模式也已拒绝 verifying/running 的变更。确认正向模式预检已强制此规则；如未强制，在本次变更中一并收紧。
- **风险：暂时性验证失败自动解决后，自动提案产生噪音。** → 应对：自动提案是*待审批*申请，非执行。Approver 可像其他申请一样驳回，驳回代价极低，审计轨迹仍保留失败记录。
- **风险：自动提案中的来源操作者归因问题。** → 应对：见开放问题 Q1；默认使用文档化的系统操作者，以 `originated_for_user_id` 元数据存储原始变更的操作者（若实现更简单）。
- **权衡：回滚仅支持全量快照，不支持部分回滚。** → v1 可接受。部分/YANG 感知回滚属于未来变更，等 YANG 模型体系就位后再推进。
- **权衡：回滚提交 RBAC 仅限 approver。** → 部分团队可能希望 operator 也能提案回滚。v1 接受此限制，根据运营反馈再作调整。

## 迁移计划

- 一次 Alembic 迁移，在 `device_config_change_requests` 上新增 `is_rollback`、`rollback_of_change_id`、`rollback_target_snapshot_id` 三列（`nullable=True`，新 ID 列加外键）。降级时删除这些列和外键。
- 无需回填：已有变更申请的 `is_rollback` 默认为 False，新列为 NULL，这是正确的历史状态。
- 部署顺序：后端迁移 → 后端服务 → 前端。新接口纯属新增；旧版前端无需感知回滚上下文即可正常工作。
- 特性本身的回滚策略：还原后端服务以忽略新字段，并执行 `alembic downgrade` 到前一版本。新审计事件是纯增量的，即使禁用特性也无需回滚 schema。

## 开放问题

- **Q1.** 自动提案的回滚申请应归因于专用的 `system:rollback-proposer` 操作者，还是带"系统代表 <用户> 提案"注释的原始变更操作者？倾向于专用系统操作者 + `originated_for_user_id` 元数据，因为人工操作者并未授权该提案——但这影响审计报表，需在锁定 tasks.md 前确认。
- **Q2.** 当前 `DeviceConfigSnapshot` 记录是否持久化了可直接传给 `edit-config` 的规范化内容（字节），还是仅有摘要+受控汇总？任务中包含显式验证步骤；若内容未持久化，需增加一个早期任务，仅对满足条件的快照新增规范化内容存储。
- **Q3.** `rollback_of_change_id` 是否允许链式（回滚的回滚）？当前设计允许（无特殊限制，仅来源状态检查），但对回滚的回滚显式禁用自动提案（D5）。在锁定任务前确认是否符合运维预期。
