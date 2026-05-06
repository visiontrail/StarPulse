## ADDED Requirements

### Requirement: 回滚目标资格判定
系统 MUST 为每份成功配置快照判定其是否可作为回滚目标，并在快照查询响应中暴露资格字段，使前端能够据此启用或禁用回滚入口。

#### Scenario: 持久化规范化内容
- **WHEN** 系统采集成功配置快照
- **THEN** 系统 MUST 持久化用于派生 NETCONF `edit-config` 载荷的规范化配置内容，或在持久化失败时明确标记该快照不可作为回滚目标

#### Scenario: 查询资格字段
- **WHEN** 调用方查询设备配置快照列表或单个快照详情
- **THEN** 系统 MUST 返回 `rollback_eligible` 布尔字段及不可回滚时的阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`，且不得返回完整规范化内容

#### Scenario: 历史快照向后兼容
- **WHEN** 历史快照创建于本次变更之前且未持久化规范化内容
- **THEN** 系统 MUST 将其 `rollback_eligible` 标记为 false，并附带阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`

### Requirement: 回滚载荷派生服务边界
系统 MUST 提供仅供变更控制服务在事务内调用的快照规范化内容读取与载荷派生入口，并对外保持只读语义。

#### Scenario: 仅变更控制可调用
- **WHEN** 上层模块需要从快照派生 `edit-config` 载荷
- **THEN** 系统 MUST 仅暴露给变更控制服务的内部接口，不得通过对外 API、任务 metadata、审计 metadata 或日志返回派生载荷的完整原始内容

#### Scenario: 派生不污染快照状态
- **WHEN** 系统执行回滚载荷派生
- **THEN** 系统 MUST NOT 修改、删除、覆盖或重新写入目标快照、其来源任务或其他历史快照记录

#### Scenario: 派生失败不创建变更
- **WHEN** 派生过程因规范化内容缺失、长度超限或受控错误失败
- **THEN** 系统 MUST 返回标准错误码、阻塞码 `ROLLBACK_TARGET_NOT_RESTORABLE`，并不得创建变更申请或执行任务
