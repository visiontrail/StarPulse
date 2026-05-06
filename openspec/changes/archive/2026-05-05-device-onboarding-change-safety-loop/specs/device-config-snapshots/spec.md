## ADDED Requirements

### Requirement: 基线快照语义
系统 MUST 支持将成功采集的配置快照用于设备接入基线和配置变更执行前基线判断。

#### Scenario: 标记当前基线
- **WHEN** 某设备某 datastore 成功采集配置快照
- **THEN** 系统 MUST 能够将最新成功快照作为该设备该 datastore 的当前基线用于接入完成和变更预检

#### Scenario: 查询基线摘要
- **WHEN** 调用方查询设备画像、变更预检或变更详情
- **THEN** 系统 MUST 返回基线快照标识、datastore、content_digest、采集时间和安全差异摘要

#### Scenario: 基线不存在
- **WHEN** 设备指定 datastore 不存在成功快照
- **THEN** 系统 MUST 在设备接入摘要和变更预检中返回缺少基线的阻塞原因

### Requirement: 快照新鲜度检查
系统 MUST 支持对配置快照进行新鲜度判断，用于变更预检和直接执行安全边界。

#### Scenario: 快照仍然新鲜
- **WHEN** 最后成功快照的采集时间未超过系统配置的新鲜度阈值
- **THEN** 系统 MUST 将该快照标记为可用于预检的基线

#### Scenario: 快照已经过旧
- **WHEN** 最后成功快照的采集时间超过系统配置的新鲜度阈值
- **THEN** 系统 MUST 在预检摘要中返回 stale baseline 状态、最后采集时间和建议刷新动作

#### Scenario: 新鲜度配置
- **WHEN** 运行环境设置基线快照新鲜度阈值
- **THEN** 系统 MUST 使用该配置判断预检和直接执行是否允许继续

### Requirement: 受控快照比较摘要
系统 MUST 为变更预检和执行后验证提供不泄漏完整配置正文的快照比较摘要。

#### Scenario: 生成执行前比较摘要
- **WHEN** 系统对变更载荷和基线快照生成预检摘要
- **THEN** 系统 MUST 返回安全比较字段，例如基线 digest、载荷 digest、datastore、行数或长度摘要和是否存在可判断变化

#### Scenario: 生成执行后比较摘要
- **WHEN** 配置变更执行后成功采集 post-change 快照
- **THEN** 系统 MUST 比较基线快照和 post-change 快照，并返回 digest 是否变化、上一份快照标识和 post-change 快照标识

#### Scenario: 比较摘要脱敏
- **WHEN** 快照摘要、比较摘要或错误上下文包含敏感字段
- **THEN** 系统 MUST 对密码、token、密钥、私钥、设备凭据和未经控制的完整配置正文进行脱敏或排除
