---
doc_id: DOC-FRONTEND-004
title: Official zh-CN Terminology and Display Mapping
status: baseline
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [3, 5, 6, 30, 33, 34, 47, 48, 50, 58, 66, 67, 68, 69, 73, 74, 77, 78, 94, 100, 111]
last_reviewed: 2026-08-26
terminology_version: official-zh-cn-terminology.v1
---

# Official zh-CN Terminology and Display Mapping

## Authority and version

`official-zh-cn-terminology.v1`是PlantNexus APS P3展示层`en-US`/`zh-CN`的规范语义源。它定义label、说明和格式化，不改变任何英文wire contract。API路径、JSON key、Schema/URN/version、OpenAPI `operationId`、状态、命令、错误码、constraint ID、数据库字段、canonical fingerprint/idempotency input与标准JSON/CSV/XLSX bytes继续使用已发布英文机器值。

外部系统可自定义页面表现，但推荐遵循本表；其API发送/接收仍必须使用英文机器字段和值。品牌、自由文本、用户输入、ID、actor reference、business code、fingerprint、correlation ID、Schema version和代码不翻译。未知值显示`Unknown / 未知（<raw>）`并保留raw，不得猜测、静默丢弃或用英文message判断业务。

默认locale为`zh-CN`；仅可在浏览器本地保存非敏感locale preference。切换必须同时更新Ant Design locale和`document.documentElement.lang`。后端英文安全message只可作为诊断fallback；中文主文案必须由`namespace + product_error.code + workspace_control_error.reason + details.reason`确定。

下表的“原码”表示中文/英文label旁是否必须同时呈现机器值。除另有说明，未知回退均为保留raw并fail visibly。

## Pages and navigation

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `/planning/data-health` | Data health | 数据健康 | Page/menu | Frontend route inventory | 标题与菜单本地化，path不变 | no | raw route |
| `/planning/import-runs` | Import runs | 导入运行 | Page/menu | Frontend route inventory | run ID保持原样 | no | raw route |
| `/planning/runs` | Planning runs | 计划运行 | Page/menu | Frontend route inventory | machine status另按状态表 | no | raw route |
| `/planning/runs/:planning_run_id` | Planning run detail | 计划运行详情 | Page | Frontend route inventory | ID不翻译 | yes | raw route |
| `/planning/versions/:schedule_version_id` | Schedule version | 排程版本 | Page/menu | `schedule-version.v1` | ID、state raw可审计 | yes | raw route |
| `ORDERS` | Orders | 订单 | Page/menu/view | `WorkspaceView` | business ID/code不翻译 | no | raw value |
| `OPERATIONS` | Operations | 工序 | Page/menu/view | `WorkspaceView` | operation ID不翻译 | no | raw value |
| `RESOURCES` | Resources | 资源 | Page/menu/view | `WorkspaceView` | resource code不翻译 | no | raw value |
| `CALENDARS` | Calendars | 日历 | Page/menu/view | `WorkspaceView` | raw UTC保留 | no | raw value |
| `GANTT` | Gantt | 甘特图 | Page/menu/view | `WorkspaceView` | Factory/Workshop/Machine分别为工厂/车间/设备 | no | raw value |
| `RESOURCE_LOAD` | Resource load | 资源负荷 | Page/menu/view | `WorkspaceView` | seconds/count/utilization按格式表 | no | raw value |
| `VALIDATION` | Validation | 排程校验 | Page/menu | Validation contract | C-ID与code同时显示 | yes | raw value |
| `KPI` | KPI | 关键绩效指标 | Page/menu/view | KPI contract | metric key可在详情保留 | conditional | raw metric |
| `DIAGNOSTICS` | Diagnostics | 诊断 | Page/menu/view | Workspace read model | 不把UNKNOWN翻译为不可行 | conditional | raw value |
| `AUDIT` | Audit | 审计记录 | Page/menu/view | Audit projection | actor/correlation/raw UTC原样 | conditional | raw value |
| `VERSION_COMPARISON` | Version comparison | 版本对比 | Page/menu/view | comparison v1 | Version ID不翻译 | yes | raw value |

## ScheduleVersion and ExportJob states

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `DRAFT` | Draft | 草稿 | ScheduleVersion state | state-machines v1 | label；详情可同时显示raw | conditional | raw state + unknown |
| `READY_FOR_REVIEW` | Ready for review | 待评审 | ScheduleVersion state | state-machines v1 | 不译为“已批准” | conditional | raw state + unknown |
| `APPROVED` | Approved | 已批准 | ScheduleVersion state | state-machines v1 | 不表示Production授权 | conditional | raw state + unknown |
| `PUBLISHED` | Published internally | 已内部发布 | ScheduleVersion state | state-machines v1 | P3只可指`SIMULATION_INTERNAL` | yes | raw state + unknown |
| `SUPERSEDED` | Superseded | 已被取代 | ScheduleVersion state | state-machines v1 | 旧Version仍不可变 | conditional | raw state + unknown |
| `REJECTED` | Rejected | 已驳回 | ScheduleVersion state | state-machines v1 | 终态；修订产生新DRAFT | conditional | raw state + unknown |
| `CREATED` | Created | 已创建 | ExportJob state | state-machines v1 | 不表示开始或成功 | conditional | raw state + unknown |
| `EXPORTING` | Exporting | 导出中 | ExportJob state | state-machines v1 | 显示attempt/lease事实 | conditional | raw state + unknown |
| `EXPORTED` | Exported | 已导出 | ExportJob state | state-machines v1 | 仅manifest完整且可验证 | conditional | raw state + unknown |
| `EXPORT_FAILED` | Export failed | 导出失败 | ExportJob state | state-machines v1 | 显示attempt/correlation/retry门 | yes | raw state + unknown |
| `CANCELLED` | Cancelled | 已取消 | ExportJob state | state-machines v1 | 终态 | conditional | raw state + unknown |

## Data plane, environment and targets

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `SIMULATION` | Simulation | 仿真 | DataPlane | runtime/carrier | 页面须明显标识synthetic边界 | yes | raw value + unknown |
| `PRODUCTION` | Production | 生产 | DataPlane | runtime/carrier | P3控制面默认拒绝；不暗示已接入 | yes | raw value + unknown |
| `DEVELOPMENT` | Development | 开发 | Environment | runtime config | 环境徽标 | conditional | raw value + unknown |
| `TEST` | Test | 测试 | Environment | runtime config | 环境徽标 | conditional | raw value + unknown |
| `BENCHMARK` | Benchmark | 基准测试 | Environment | runtime config | 不表示Production SLA | conditional | raw value + unknown |
| `PRODUCTION` | Production | 生产 | Environment | runtime config | 与DataPlane分别显示 | yes | raw value + unknown |
| `WORKSPACE_INTERNAL` | Workspace internal | 工作区内部 | Command target | workspace-command v1 | 非外部发布 | yes | raw value + unknown |
| `SIMULATION_INTERNAL` | Simulation internal | 仿真内部 | Publish/export target | workspace-command v1 | 必须显示“非生产发布” | yes | raw value + unknown |

## WorkspaceView, commands and allowed actions

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `DATA_HEALTH` | Data health | 数据健康 | WorkspaceView | workspace read model | label only | no | raw view |
| `IMPORT_RUNS` | Import runs | 导入运行 | WorkspaceView | workspace read model | label only | no | raw view |
| `PLANNING_RUNS` | Planning runs | 计划运行 | WorkspaceView | workspace read model | label only | no | raw view |
| `ORDERS` | Orders | 订单 | WorkspaceView | workspace read model | label only | no | raw view |
| `OPERATIONS` | Operations | 工序 | WorkspaceView | workspace read model | label only | no | raw view |
| `RESOURCES` | Resources | 资源 | WorkspaceView | workspace read model | label only | no | raw view |
| `CALENDARS` | Calendars | 日历 | WorkspaceView | workspace read model | label only | no | raw view |
| `GANTT` | Gantt | 甘特图 | WorkspaceView | workspace read model | label only | no | raw view |
| `RESOURCE_LOAD` | Resource load | 资源负荷 | WorkspaceView | workspace read model | label only | no | raw view |
| `KPI` | KPI | 关键绩效指标 | WorkspaceView | workspace read model | label only | no | raw view |
| `DIAGNOSTICS` | Diagnostics | 诊断 | WorkspaceView | workspace read model | label only | no | raw view |
| `LOCKS` | Locks | 锁定 | WorkspaceView | backend WorkspaceView | 未暴露页面时仍必须纳入字典coverage | conditional | raw view |
| `AUDIT` | Audit | 审计记录 | WorkspaceView | workspace read model | label only | no | raw view |
| `VERSION_COMPARISON` | Version comparison | 版本对比 | WorkspaceView | comparison v1 | label only | no | raw view |
| `MOVE_OPERATION` | Move operation | 移动工序 | WorkspaceCommand | workspace-command v1 | 发送值必须仍为英文 | yes | raw command + unknown |
| `ASSIGN_RESOURCE` | Assign resource | 分配资源 | WorkspaceCommand | workspace-command v1 | 同上 | yes | raw command + unknown |
| `SET_LOCK` | Set lock | 设置锁定 | WorkspaceCommand | workspace-command v1 | HARD/SOFT raw可审计 | yes | raw command + unknown |
| `REMOVE_LOCK` | Remove lock | 移除锁定 | WorkspaceCommand | workspace-command v1 | 不使用旧称RELEASE_LOCK | yes | raw command + unknown |
| `SUBMIT_FOR_REVIEW` | Submit for review | 提交评审 | WorkspaceCommand | workspace-command v1 | 结果为READY_FOR_REVIEW | yes | raw command + unknown |
| `APPROVE` | Approve | 批准 | WorkspaceCommand | workspace-command v1 | 不表示Production authority | yes | raw command + unknown |
| `REJECT` | Reject | 驳回 | WorkspaceCommand | workspace-command v1 | reason必填 | yes | raw command + unknown |
| `PUBLISH` | Publish internally | 内部发布 | WorkspaceCommand | workspace-command v1 | 明示Simulation internal | yes | raw command + unknown |
| `REQUEST_EXPORT` | Request export | 请求导出 | WorkspaceCommand | workspace-command v1 | Publish与Export分离 | yes | raw command + unknown |
| `RETRY_EXPORT` | Retry export | 重试导出 | WorkspaceCommand | workspace-command v1 | 同一Job/contract | yes | raw command + unknown |
| `CANCEL_EXPORT` | Cancel export | 取消导出 | WorkspaceCommand | workspace-command v1 | 显式确认 | yes | raw command + unknown |
| `view` | View | 查看 | allowed action | schedule-version v1 | server-derived；UI不是authority | conditional | raw action + unknown |
| `edit` | Edit | 编辑 | allowed action | schedule-version v1 | server-derived | conditional | raw action + unknown |
| `lock` | Lock | 锁定 | allowed action | schedule-version v1 | server-derived | conditional | raw action + unknown |
| `approve` | Approve | 批准 | allowed action | schedule-version v1 | server-derived | conditional | raw action + unknown |
| `reject` | Reject | 驳回 | allowed action | schedule-version v1 | server-derived | conditional | raw action + unknown |
| `publish` | Publish | 发布 | allowed action | schedule-version v1 | P3仅内部仿真 | conditional | raw action + unknown |
| `export` | Export | 导出 | allowed action | schedule-version v1 | server-derived | conditional | raw action + unknown |
| `audit` | View audit | 查看审计 | capability | schedule-version v1 | server-derived | conditional | raw action + unknown |

## UI state and comparison change kind

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `loading` | Loading | 加载中 | UI state | Frontend state | accessible live status | no | raw state |
| `empty` | No results | 暂无数据 | UI state | Frontend state | 与missing区分 | no | raw state |
| `ready` | Ready | 已就绪 | UI state | Frontend state | 不与READY_FOR_REVIEW混用 | no | raw state |
| `stale` | Data is stale | 数据已过期 | UI state | Frontend state | 要求刷新authoritative source | conditional | raw state |
| `authorization_denied` | Access denied | 访问被拒绝 | UI state | Frontend state | 不透露所需角色 | conditional | raw reason |
| `contract_error` | Contract error | 合同错误 | UI state | Frontend state | 显示correlation/raw code | yes | raw reason |
| `server_error` | Server error | 服务端错误 | UI state | Frontend state | 安全message+correlation | yes | raw reason |
| `ADDED` | Added | 新增 | comparison change kind | comparison v1 | operation ID保留 | yes | raw kind + unknown |
| `REMOVED` | Removed | 移除 | comparison change kind | comparison v1 | operation ID保留 | yes | raw kind + unknown |
| `RESOURCE_CHANGE` | Resource changed | 资源变更 | comparison change kind | comparison v1 | old/new resource ID保留 | yes | raw kind + unknown |
| `DURATION_CHANGE` | Duration changed | 工时变更 | comparison change kind | comparison v1 | seconds与raw values保留 | yes | raw kind + unknown |
| `START_SHIFT` | Start time shifted | 开始时间偏移 | comparison change kind | comparison v1 | raw UTC保留 | yes | raw kind + unknown |
| `UNCHANGED` | Unchanged | 未变更 | comparison change kind | comparison v1 | filter语义不变 | yes | raw kind + unknown |

## Constraint labels C-001 through C-011

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `C-001` | Assignment completeness | 必排完整性 | Validation | constraint-rule-sheet v1 | 始终同时显示C-ID | yes | raw C-ID |
| `C-002` | Precedence timing | 工艺时间关系 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-003` | Candidate resource selection | 候选设备唯一选择 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-004` | Unary resource capacity | 单机互斥 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-005` | Resource calendar | 设备日历 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-006` | Release and material gate | 放行与物料就绪门 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-007` | Execution facts | 执行事实保护 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-008` | Operation lock | 工序锁定 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-009` | Cross-workshop transport | 跨车间衔接 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-010` | Duration consistency | 工时一致性 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |
| `C-011` | Planning horizon | 计划时域 | Validation | constraint-rule-sheet v1 | 同上 | yes | raw C-ID |

## Product error categories

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `DATA_ERROR` | Data error | 数据错误 | `product_error.category` | error registry v2 | code比message优先 | yes | raw category/code |
| `UNSUPPORTED_CAPABILITY` | Unsupported capability | 不支持的能力 | category | error registry v2 | 不得静默降级 | yes | raw category/code |
| `MODEL_INVALID` | Invalid model | 模型无效 | category | error registry v2 | 不等于INFEASIBLE | yes | raw category/code |
| `INFEASIBLE` | Infeasible | 已证明不可行 | category | error registry v2 | 仅证明后使用 | yes | raw category/code |
| `NO_SOLUTION_WITHIN_LIMIT` | No conclusion within limit | 限时内未得出结论 | category | error registry v2 | 不翻译为不可行 | yes | raw category/code |
| `VALIDATION_FAILED` | Validation failed | 校验失败 | category | error registry v2 | 展示C-ID/details | yes | raw category/code |
| `SYSTEM_ERROR` | System error | 系统错误 | category | error registry v2 | 安全fallback+correlation | yes | raw category/code |

## Product error codes

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `INVALID_TIME` | Invalid time | 时间值无效 | product error | error registry v2 | 显示安全field/detail | yes | raw code + unknown |
| `DUPLICATE_ID` | Duplicate ID | 标识重复 | product error | error registry v2 | ID原样 | yes | raw code + unknown |
| `MISSING_SCENARIO_ID` | Missing scenario ID | 缺少场景标识 | product error | error registry v2 | ID原样 | yes | raw code + unknown |
| `SYNTHETIC_REFERENCE_IN_PRODUCTION` | Synthetic reference in Production | 生产数据中包含仿真引用 | product error | error registry v2 | 明示隔离边界 | yes | raw code + unknown |
| `INVALID_ENTITY_COUNT` | Invalid entity count | 实体数量无效 | product error | error registry v2 | raw数值保留 | yes | raw code + unknown |
| `INVALID_DURATION` | Invalid duration | 工时无效 | product error | error registry v2 | seconds/raw保留 | yes | raw code + unknown |
| `INVALID_TIME_RANGE` | Invalid time range | 时间范围无效 | product error | error registry v2 | raw UTC保留 | yes | raw code + unknown |
| `MISSING_RUNNING_FACT` | Missing running fact | 缺少运行事实 | product error | error registry v2 | operation ID保留 | yes | raw code + unknown |
| `INVALID_REFERENCE` | Invalid reference | 引用无效 | product error | error registry v2 | reference原样 | yes | raw code + unknown |
| `INVALID_LAG_RANGE` | Invalid lag range | 时间间隔范围无效 | product error | error registry v2 | raw bounds保留 | yes | raw code + unknown |
| `INVALID_CAPABILITY_DECLARATION` | Invalid capability declaration | 能力声明无效 | product error | error registry v2 | capability raw保留 | yes | raw code + unknown |
| `DUPLICATE_CAPABILITY` | Duplicate capability | 能力声明重复 | product error | error registry v2 | capability raw保留 | yes | raw code + unknown |
| `INVALID_STATE_TRANSITION` | Invalid state transition | 状态转换无效 | product error | error registry v2 | from/to raw保留 | yes | raw code + unknown |
| `ROUTE_CYCLE` | Routing cycle | 工艺路线存在环 | product error | error registry v2 | route ID保留 | yes | raw code + unknown |
| `MISSING_RESOURCE` | Missing eligible resource | 缺少可用资源 | product error | error registry v2 | resource/capability raw保留 | yes | raw code + unknown |
| `UNIT_CONVERSION_ERROR` | Unit conversion error | 单位换算错误 | product error | error registry v2 | unit raw保留 | yes | raw code + unknown |
| `MISSING_DURATION` | Missing duration | 缺少工时 | product error | error registry v2 | source raw保留 | yes | raw code + unknown |
| `UNSUPPORTED_CAPABILITY` | Unsupported capability | 不支持的能力 | product error | error registry v2 | capability raw保留 | yes | raw code + unknown |
| `MODEL_INVALID` | Invalid model | 模型无效 | product error | error registry v2 | 不等于不可行 | yes | raw code + unknown |
| `INFEASIBLE` | Infeasible | 已证明不可行 | product error | error registry v2 | 仅认证证据后显示 | yes | raw code + unknown |
| `NO_SOLUTION_WITHIN_LIMIT` | No conclusion within limit | 限时内未得出结论 | product error | error registry v2 | 不等于不可行 | yes | raw code + unknown |
| `SCHEDULE_VALIDATION_FAILED` | Schedule validation failed | 排程校验失败 | product error | error registry v2 | C-ID必须同时显示 | yes | raw code + unknown |
| `SYSTEM_ERROR` | System error | 系统错误 | product error | error registry v2 | correlation ID必须保留 | yes | raw code + unknown |

## Workspace control reasons and authorization detail reasons

这些值属于`WORKSPACE_CONTROL` namespace或安全`details.reason`，不得误当成product error code。相同字符串在不同namespace中必须按namespace选择字典。

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `AUTHORIZATION_DENIED` | Authorization denied | 授权被拒绝 | workspace reason | HTTP error mapping | 不透露角色 | yes | raw reason + unknown |
| `UNAUTHORIZED` | Unauthorized | 未获授权 | workspace reason | HTTP error mapping | 区分认证缺失 | yes | raw reason + unknown |
| `PRODUCTION_AUTHORITY_UNAVAILABLE` | Production authority unavailable | 生产授权不可用 | workspace reason | HTTP error mapping | 明示default-deny | yes | raw reason + unknown |
| `SOURCE_NOT_FOUND` | Source not found | 未找到来源 | workspace reason | HTTP error mapping | resource ref原样 | yes | raw reason + unknown |
| `SOURCE_MISSING` | Source missing | 缺少来源 | workspace reason | HTTP error mapping | 同上 | yes | raw reason + unknown |
| `PUBLICATION_NOT_FOUND` | Publication not found | 未找到发布记录 | workspace reason | HTTP error mapping | ID原样 | yes | raw reason + unknown |
| `PREVIOUS_CURRENT_NOT_FOUND` | Previous current version not found | 未找到先前当前版本 | workspace reason | HTTP error mapping | Version ID原样 | yes | raw reason + unknown |
| `NOT_FOUND` | Not found | 未找到 | workspace reason | HTTP error mapping | resource ref原样 | yes | raw reason + unknown |
| `STALE_SOURCE` | Source is stale | 来源已过期 | workspace reason | HTTP error mapping | 刷新后显式重试 | yes | raw reason + unknown |
| `STALE_VERSION` | Version is stale | 版本已过期 | workspace reason | HTTP error mapping | actual/expected保留 | yes | raw reason + unknown |
| `STALE_CURSOR` | Cursor is stale | 游标已过期 | workspace reason | HTTP error mapping | 不猜测下一页 | yes | raw reason + unknown |
| `STATE_CONFLICT` | State conflict | 状态冲突 | workspace reason | HTTP error mapping | state raw保留 | yes | raw reason + unknown |
| `INVALID_STATE_TRANSITION` | Invalid state transition | 状态转换无效 | workspace reason | HTTP error mapping | namespace区分 | yes | raw reason + unknown |
| `CURRENT_REFERENCE_CONFLICT` | Current reference conflict | 当前版本引用冲突 | workspace reason | HTTP error mapping | Version raw保留 | yes | raw reason + unknown |
| `LEASE_CONFLICT` | Lease conflict | 租约冲突 | workspace reason | HTTP error mapping | attempt/Job raw保留 | yes | raw reason + unknown |
| `LOCK_CONFLICT` | Lock conflict | 锁定冲突 | workspace reason | HTTP error mapping | lock/operation ID保留 | yes | raw reason + unknown |
| `IMMUTABLE_EXECUTION_FACT` | Immutable execution fact | 执行事实不可变 | workspace reason | HTTP error mapping | fact ID保留 | yes | raw reason + unknown |
| `NO_OP` | No effective change | 没有有效变更 | workspace reason | HTTP error mapping | 不显示成功 | yes | raw reason + unknown |
| `IDEMPOTENCY_CONFLICT` | Idempotency conflict | 幂等请求冲突 | workspace reason | workspace carrier | 原请求引用保留 | yes | raw reason + unknown |
| `INVALID_REQUEST` | Invalid request | 请求无效 | workspace reason | HTTP error mapping | field/detail安全显示 | yes | raw reason + unknown |
| `INVALID_COMMAND` | Invalid command | 命令无效 | workspace reason | HTTP error mapping | command raw保留 | yes | raw reason + unknown |
| `INVALID_QUERY` | Invalid query | 查询无效 | workspace reason | HTTP error mapping | query field保留 | yes | raw reason + unknown |
| `INVALID_INPUT` | Invalid input | 输入无效 | workspace reason | HTTP error mapping | field保留 | yes | raw reason + unknown |
| `INVALID_REFERENCE` | Invalid reference | 引用无效 | workspace reason | HTTP error mapping | namespace区分 | yes | raw reason + unknown |
| `INVALID_TIME` | Invalid time | 时间值无效 | workspace reason | HTTP error mapping | raw UTC保留 | yes | raw reason + unknown |
| `DATA_PLANE_MISMATCH` | Data-plane mismatch | 数据平面不匹配 | workspace reason | HTTP error mapping | plane raw保留 | yes | raw reason + unknown |
| `MIXED_LINEAGE` | Mixed lineage | 血缘混用 | workspace reason | HTTP error mapping | IDs/fingerprints保留 | yes | raw reason + unknown |
| `KPI_MISMATCH` | KPI mismatch | KPI不一致 | workspace reason | HTTP error mapping | metric/raw values保留 | yes | raw reason + unknown |
| `PLANNING_RUN_NOT_COMPLETED` | Planning run is not complete | 计划运行尚未完成 | workspace reason | HTTP error mapping | state raw保留 | yes | raw reason + unknown |
| `VALIDATION_FAILED` | Validation failed | 校验失败 | workspace reason | HTTP error mapping | product code/C-ID保留 | yes | raw reason + unknown |
| `PERSISTENCE_FAILED` | Persistence failed | 持久化失败 | workspace reason | HTTP error mapping | 不泄漏SQL | yes | raw reason + unknown |
| `EXPORT_FAILED` | Export failed | 导出失败 | workspace reason | workspace carrier | Job/attempt/correlation保留 | yes | raw reason + unknown |
| `SERVICE_UNAVAILABLE` | Service unavailable | 服务暂不可用 | workspace reason | HTTP error mapping | retryability按server事实 | yes | raw reason + unknown |
| `SYSTEM_ERROR` | System error | 系统错误 | workspace reason | HTTP error mapping | correlation保留 | yes | raw reason + unknown |
| `AUTHENTICATION_REQUIRED` | Authentication required | 需要身份认证 | `details.reason` | authorization provider | 不回显credential | yes | raw detail + unknown |
| `INVALID_AUTHENTICATION` | Invalid authentication | 身份认证无效 | `details.reason` | authorization provider | 不回显credential | yes | raw detail + unknown |
| `CAPABILITY_DENIED` | Capability denied | 能力权限被拒绝 | `details.reason` | authorization provider | 不透露角色 | yes | raw detail + unknown |
| `RESOURCE_SCOPE_DENIED` | Resource scope denied | 资源范围权限被拒绝 | `details.reason` | authorization provider | resource ref安全显示 | yes | raw detail + unknown |
| `AUTHORIZATION_PROVIDER_UNAVAILABLE` | Authorization provider unavailable | 授权服务不可用 | `details.reason` | authorization provider | fail closed | yes | raw detail + unknown |
| `INVALID_PROVIDER_CONTEXT` | Invalid provider context | 授权上下文无效 | `details.reason` | authorization provider | fail closed | yes | raw detail + unknown |
| `SIMULATION_API_DISABLED` | Simulation API disabled | 仿真API未启用 | `details.reason` | authorization provider | 不提供绕过 | yes | raw detail + unknown |

## Business, KPI, validation, audit, publication and export terms

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `ScheduleVersion` | Schedule version | 排程版本 | Domain/UI | schedule-version v1 | class/Schema名不翻译，展示名本地化 | conditional | raw identifier |
| `PlanningRun` | Planning run | 计划运行 | Domain/UI | PlanningRun state | state raw可审计 | conditional | raw identifier |
| `ExportJob` | Export job | 导出任务 | Domain/UI | export-job v1 | Job ID/attempt原样 | conditional | raw identifier |
| `weighted_tardiness` | Weighted tardiness | 加权延期 | KPI | KPI contract | metric key可在raw detail显示 | conditional | raw metric |
| `makespan_seconds` | Makespan | 总工期 | KPI | KPI contract | 中文值后显示单位；raw seconds可审计 | conditional | raw metric |
| `late_order_count` | Late orders | 延期订单数 | KPI | KPI contract | 整数，不补猜 | conditional | raw metric |
| `scheduled_operation_count` | Scheduled operations | 已排工序数 | KPI | workspace read model | 整数 | conditional | raw metric |
| `utilization` | Utilization | 利用率 | KPI/load | workspace read model | 0..1按百分比显示并保留raw | conditional | raw metric |
| `PASS` | Pass | 通过 | Validation | validation-report v2 | 不改machine status | yes | raw status + unknown |
| `FAIL` | Fail | 失败 | Validation | validation-report v2 | 显示C-ID/code | yes | raw status + unknown |
| `HARD` | Hard violation | 硬约束违反 | Validation | rule sheet | C-ID/raw severity保留 | yes | raw severity + unknown |
| `SOFT` | Soft observation | 软约束观察 | Validation | rule/lock semantics | 不翻译成硬失败 | yes | raw severity + unknown |
| `AuditEvent` | Audit event | 审计事件 | Audit | authorization/audit contract | actor/reason/correlation/raw UTC保留 | conditional | raw type |
| `PublicationResult` | Publication result | 发布结果 | Publication | publication carrier | P3须显示internal Simulation | conditional | raw type |
| `artifact_manifest` | Artifact manifest | 成果清单 | Export | export manifest v2 | file/hash/bytes原样 | conditional | raw field |
| `idempotent replay` | Idempotent replay | 幂等重放 | Command/result | idempotency contract | replay flag/raw key ref可审计 | conditional | raw value |

## Time, units, missing and raw data

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `*_at_utc` | UTC time | UTC时间 | Time | all P3 carriers | 可用locale格式显示，但“查看原始数据”保留精确raw UTC；不得补业务时区 | yes | raw UTC |
| `seconds` | seconds | 秒 | Duration | contracts/KPI/load | 使用Intl number；raw integer seconds保留 | conditional | raw value + unit |
| `count` | count | 数量 | KPI/table | contracts | 使用Intl integer，不对missing补0 | conditional | raw value |
| `utilization` | utilization | 利用率 | Resource Load | read model | ratio按百分比显示，raw ratio保留 | conditional | raw value |
| `null` | Not provided | 未提供 | Nullable value | Schema | 与empty/zero区分 | yes | raw null |
| `missing` | Missing | 缺失 | Contract/reference | API/error | 显式错误或empty state，不补猜 | yes | raw field/ref |
| `empty` | No results | 暂无数据 | Found-empty result | workspace query | `found=true, items=[]`；不得显示“未找到” | conditional | raw found/count |
| `not found` | Not found | 未找到 | Missing resource | API/error | 与found-empty区分 | conditional | raw reason |
| `raw JSON` | View raw data | 查看原始数据 | Audit/detail | API response | 只在独立可展开区域；不得作为中文主业务展示 | yes | raw JSON |

## Phase boundary terminology

| English machine value | Official en-US display | Official zh-CN display | Context | Source contract / state | Display rule | Raw code | Unknown fallback |
|---|---|---|---|---|---|---|---|
| `P3` | Planning Workspace | 计划工作区 | Current phase | Milestone governance | 当前仅P3；不表示Production | yes | raw phase |
| `P4` | Execution Feedback and Replanning | 执行反馈与重排 | Future phase | technical master spec | 未经transition只能显示“未启动” | yes | raw phase |
| `Production` | Production | 生产环境 | Deployment/authority | PROD_OPEN governance | 不等于PUBLISHED/internal Simulation | yes | raw boundary |
| `READY` | Ready for phase decision | 已具备阶段决策条件 | Exit audit | Gate governance | 只表示audit结论；不自动transition | yes | raw decision |
| `NOT_READY` | Not ready | 尚未具备阶段决策条件 | Exit audit | Gate governance | 显示blocking gaps | yes | raw decision |
| `Production readiness` | Production readiness | 生产就绪 | Production gate | future governance | P3禁止声明已形成 | yes | raw boundary |

## Change and test governance

- 术语变更必须提升`terminology_version`或以兼容additive规则发布新版本，保留历史版本和来源合同；不得用`latest`重解释旧artifact。
- TASK-P3-16实施时，英文和中文dictionary key集合必须逐字相等；所有注册state/view/command/action/change kind/C-ID/product category/code/workspace reason/detail reason必须由机器coverage检查。
- TEST-FRONTEND-I18N-001必须覆盖两个locale、默认与preference、document lang/Ant locale、unknown raw fallback、raw UTC/ID/code/fingerprint/JSON、error namespace/correlation与API canonical fingerprint/state/command zero drift。
- 任何新机器值先由其权威Contract/Schema/状态机版本发布；展示字典不得抢先创造机器语义。未登记值进入UI时必须fail visibly并保留raw。
- 本文只形成规范基线，不表示TASK-P3-16实现、P3 Exit、P4 transition、UAT、Production approval/publish或Production readiness已经形成。
