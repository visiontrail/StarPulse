## ADDED Requirements

### Requirement: 配置快照 API 鉴权
系统 MUST 对设备配置快照查询和采集 API 应用认证和权限控制。

#### Scenario: 未登录查询快照
- **WHEN** 未认证调用方请求设备配置快照列表或最后快照
- **THEN** 系统 MUST 返回未认证响应

#### Scenario: viewer 查询快照
- **WHEN** viewer 请求其权限允许的设备配置快照摘要
- **THEN** 系统 MUST 返回快照摘要列表，并继续隐藏完整配置正文和敏感认证材料

#### Scenario: 无权限查询快照
- **WHEN** 已认证但缺少快照读取权限的用户请求配置快照 API
- **THEN** 系统 MUST 返回禁止访问响应

### Requirement: 配置采集权限控制
系统 MUST 仅允许具备配置采集权限的用户触发 NETCONF 只读配置采集任务。

#### Scenario: operator 触发配置采集
- **WHEN** operator 对已登记且连接配置完整的设备触发配置采集
- **THEN** 系统 MUST 创建配置采集任务，并关联发起用户用于审计和任务追踪

#### Scenario: viewer 触发配置采集
- **WHEN** viewer 尝试触发配置采集
- **THEN** 系统 MUST 返回禁止访问响应，并且不得投递配置采集任务

#### Scenario: 配置采集失败审计
- **WHEN** 配置采集请求因权限不足、参数错误或设备状态不满足而失败
- **THEN** 系统 MUST 记录失败操作审计日志，并且不得泄露设备凭据或完整配置正文

### Requirement: 快照任务用户归属
系统 MUST 在配置快照任务和任务查询结果中保留安全的发起用户归属信息。

#### Scenario: 查询快照任务归属
- **WHEN** 具备任务读取权限的用户查询配置采集任务
- **THEN** 系统 MUST 返回任务状态、设备、datastore 和发起用户摘要

#### Scenario: 隐藏敏感用户信息
- **WHEN** API 返回配置采集任务或快照摘要
- **THEN** 系统 MUST NOT 返回用户密码哈希、Token、设备凭据或未经控制的完整配置正文
