---
doc_id: DOC-FRONTEND-001
title: P3 Planning Workspace 页面与只读视图合同
status: baseline
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 33, 35, 68, 77, 78, 94]
last_reviewed: 2026-08-25
---

# P3 Planning Workspace 页面与只读视图合同

本文件固定P3页面、路由、只读投影、状态可见性和server-authority边界。TASK-P3-01只形成规范；read model、HTTP、React页面和E2E分别由TASK-P3-05、10、11～13形成，当前均为`PLANNED`。

## 不变量

- 页面只显示server返回的versioned read model，不在浏览器计算约束、可行性、KPI、批准结果或发布结果。
- 每个schedule视图必须显示`data_plane`、`schedule_version_id`、`state`、父版本、Snapshot/Problem/Solution/Validation指纹和更新时间/生成时间语义。
- UI只能提交[`gantt-command-contract.md`](gantt-command-contract.md)和[`approval-publication-flow.md`](approval-publication-flow.md)定义的command；旧ScheduleVersion内容不原地修改。
- `PlanningRun.COMPLETED`只代表计算结束；它不等于ScheduleVersion已评审、批准、发布或导出。
- Production缺少真实authority mapping或target时，相关控件必须隐藏或禁用，并以server的default-deny结果为准。
- Development/Simulation页面与Production导航隔离；Scenario Lab、Benchmark Lab和Execution Simulation不属于P3 Production workspace，Execution Simulation仍属P4。

## 页面与路由

下表中的UI路由为P3固定route template；`{schedule_version_id}`和`{planning_run_id}`必须使用server identity，不能用数组位置或展示名替代。

| 页面 | UI route | 权威投影 | 最低capability | 实现Task |
|---|---|---|---|---|
| Data Health | `/planning/data-health` | Import quality、Snapshot freshness与lineage摘要 | `view` | P3-05/10/11 |
| Import Runs | `/planning/import-runs` | versioned Import run摘要 | `view` | P3-05/10/11 |
| Planning Runs | `/planning/runs` | PlanningRun列表、status与Solver/Validation摘要 | `view` | P3-05/10/11 |
| Planning Run Detail | `/planning/runs/{planning_run_id}` | Problem/Policy/Limits/Solution/Report lineage | `view` | P3-05/10/11 |
| Schedule Overview | `/planning/versions/{schedule_version_id}` | ScheduleVersion identity、state、KPI、allowed actions | `view` | P3-05/10/11 |
| Orders / Late Orders | `/planning/versions/{schedule_version_id}/orders` | order completion、due、tardiness、source | `view` | P3-05/10/11 |
| Operations | `/planning/versions/{schedule_version_id}/operations` | operation assignment、time、resource、facts/locks | `view` | P3-05/10/11 |
| Resources | `/planning/versions/{schedule_version_id}/resources` | resource/capability/assignment摘要 | `view` | P3-05/10/11 |
| Calendars | `/planning/versions/{schedule_version_id}/calendars` | UTC half-open calendar与source | `view` | P3-05/10/11 |
| Factory Gantt | `/planning/versions/{schedule_version_id}/gantt/factory` | 全厂server schedule projection | `view` | P3-05/10/12 |
| Workshop Gantt | `/planning/versions/{schedule_version_id}/gantt/workshops` | workshop分组projection | `view` | P3-05/10/12 |
| Machine Gantt | `/planning/versions/{schedule_version_id}/gantt/machines` | resource分组projection | `view` | P3-05/10/12 |
| Resource Load | `/planning/versions/{schedule_version_id}/resource-load` | server计算的load buckets与lineage | `view` | P3-05/10/12 |
| Schedule Comparison | `/planning/versions/{schedule_version_id}/compare` | 两个P3 comparison DTO；不是P4 ChangeReport | `view` | P3-05/10/12 |
| Validation Errors | `/planning/versions/{schedule_version_id}/validation` | fresh ValidationReport/Error details | `view` | P3-05/10/11 |
| Solver Diagnostics | `/planning/versions/{schedule_version_id}/diagnostics` | SolverReport与sanitized diagnostics | `view` | P3-05/10/11 |
| Locks | `/planning/versions/{schedule_version_id}/locks` | version-local HARD/SOFT lock projection | `view`; command需`lock` | P3-05/06/10/13 |
| Approval | `/planning/versions/{schedule_version_id}/approval` | decision/audit/state action view | `view`; action需`approve`或`reject` | P3-07/10/13 |
| Publication | `/planning/versions/{schedule_version_id}/publication` | internal publication/current/supersession view | `view`; action需`publish` | P3-08/10/13 |
| Export | `/planning/versions/{schedule_version_id}/exports` | ExportJob/manifest/download metadata | `view`; action需`export` | P3-09/10/13 |
| Audit | `/planning/versions/{schedule_version_id}/audit` | append-only audit projection | `audit` | P3-03/05/07～10/13 |

未知ID、跨plane引用或无法验证lineage时，页面必须显示明确错误且不得拼接来自其他Version的数据。

## 状态可见性与动作

所有状态均可在拥有`view`时只读查看。下面的“派生新DRAFT”不改变source Version的content或state；具体command必须经server guard、幂等检查和fresh formal Validator。

| ScheduleVersion state | 编辑/lock | approve/reject | publish | export | UI说明 |
|---|---|---|---|---|---|
| `DRAFT` | 可请求派生新DRAFT | 禁止 | 禁止 | 禁止 | 可显示validation与草稿lineage |
| `READY_FOR_REVIEW` | 可请求派生新DRAFT；原Version保持 | 仅相应capability可执行 | 禁止 | 禁止 | decision前必须刷新state/fingerprint |
| `APPROVED` | 不原地编辑；修订只能派生新DRAFT | 禁止重复decision | 仅`publish`且明确internal target | 禁止 | approved不等于published |
| `REJECTED` | 修订只能派生新DRAFT | 禁止 | 禁止 | 禁止 | REJECTED Version保持终态/内容不可变 |
| `PUBLISHED` | 不原地编辑；历史参考可派生新DRAFT | 禁止 | 禁止重复side effect | 仅`export`且显式target | `PUBLISHED`内容不可变 |
| `SUPERSEDED` | 历史参考可派生新DRAFT | 禁止 | 禁止 | 只允许读取历史artifact | 只读历史，不复活原Version |

`allowed_actions`只能由server依据state、capability、environment/data plane和target计算。客户端不得仅根据上表自行授权；server拒绝结果覆盖UI缓存。

## 查询、筛选与比较

- 列表必须采用稳定sort key和cursor；同一cursor/query/version fingerprint的重放结果顺序一致。
- 时间全部以UTC ISO-8601和整数秒传输；显示时可以本地化，但必须保留原UTC值且不得补猜OPEN-001中的业务时区。
- Gantt、订单、资源负载和KPI必须绑定同一`schedule_version_id`与`content_fingerprint`。
- comparison必须显式提交`base_schedule_version_id`和`compare_schedule_version_id`，输出changed/unchanged assignment与KPI差异；不得生成freeze、stability cost或ChangeReport。
- 空集合、资源不存在、无ValidationReport和query失败必须是不同可见状态。

## 页面状态与可访问性

每个页面至少具备`loading`、`empty`、`ready`、`stale`、`authorization_denied`、`contract_error`和`server_error`状态。错误不得显示成功toast、伪造零值或泄漏credential/raw exception。

Gantt必须提供键盘可操作的等价表格视图、可读operation/resource/time标签和焦点恢复；颜色不能是状态的唯一载体。确认对话框必须展示source Version、预期结果、reason和不可逆边界。

## 规模测试维度

P3-05/11/12只记录versioned synthetic数据下的orders、operations、resources、calendar fragments、Gantt rows、time span、comparison rows、payload bytes、render/query latency、bundle bytes和virtualized rendered rows。TASK-P3-01不设置Production阈值，不把P2 XS/S/M baseline外推为UI容量或SLA。

## 阶段边界

- P3形成read/command/approval/internal publication/export工作流；真实身份、角色责任、MES/ERP/storage target和Production批准保持OPEN-002/010/015。
- ExecutionEvent、ReplanRequest、freeze window、OBJ-002、ChangeReport和Execution Simulator属于P4。
- Production deployment、UAT、publish authority、capacity和SLA证据均未形成。

## TASK-P3-05 read-model handoff

Backend现提供页面矩阵所需的14种只读投影，且每页完整payload均由carrier fingerprint引用。Frontend必须保留server排序与cursor、显示`found=false`和`found=true/items=[]`的不同状态、在Version precondition过期时重新获取权威Version；不得在浏览器重算Resource Load/KPI、推断UNKNOWN为INFEASIBLE或将comparison渲染成P4 ChangeReport。P3-05交接时尚无组件/API call；P3-11现只消费获授权的read-only subset。

## TASK-P3-06 command handoff

Backend application现可把Move/Assign/Set/Remove Lock intent转换为fresh-validated、audited新DRAFT，并以独立`SUBMIT_FOR_REVIEW`在第二次fresh PASS后把该DRAFT的同一identity/content推进READY。未来UI必须把content command响应中的new Version identity作为下一次读取/命令基准，并把submit与approve/reject明确分离；不能继续把optimistic preview、source Version或READY状态当作已批准结果。Stale、authorization、Validator与idempotency失败均不得显示成功。当前仍没有Frontend组件、drag interaction或browser evidence，P3-13才可接入human-control UI。

## TASK-P3-10 HTTP handoff

Backend现以17个`/api/v1` operation暴露已有read/validate/edit/decision/publication/export application边界，并提供stable OpenAPI、correlation、strict carrier与sanitized error envelope。这只是Backend transport handoff：本Task没有创建Frontend组件、browser client、session/identity integration或用户可见成功状态。P3-11～13的consumer必须保留URL-encoded strict query、exact Version precondition、Idempotency-Key/body一致和401/403/404/409/422/500/503区分，不得将test principal或Simulation flag外推为Production authority。

## TASK-P3-11 read-only activation

P3-11已在Diff base `26dd519b1f1f84e08d415cfdfce43f286fa82988`上激活，只允许实现Data Health、Import Runs、Planning Runs/Run Detail、Version、Orders、Operations、Resources、Calendars、Validation、KPI、Diagnostics和Audit的read-only route。每个consumer必须显式呈现`loading/empty/ready/stale/authorization_denied/contract_error/server_error`，区分`found=false`与`found=true/items=[]`，保留server cursor、raw UTC、Version/content/source fingerprints与lineage，并让server error/state authority覆盖客户端缓存。

本Task不创建Gantt、Resource Load、Version Comparison或control route，也不在browser计算Solver/Validator/KPI/Resource Load。默认session provider没有token且fail closed；不得存储或记录token，Production navigation不得暴露Simulation-only入口。该read-only行为已由下述provider复验，但不构成Production identity或readiness。

## TASK-P3-11 implementation and provider closure

现有13条route与页面矩阵逐字一致。Workspace-level read构造URL-encoded canonical JSON `query`；schedule-scoped read先取得`schedule-version.v1`，再把exact identity/state/content fingerprint作为precondition。Consumer检查query fingerprint、carrier reference与完整payload item的identity/type/fingerprint一致；payload fingerprint本身保持server authority而不从解析后可能丢失number lexical form的JavaScript object重新定义canonical bytes。

UI分别显示missing、found-empty、ready、stale、authorization、contract和server failure，保留raw UTC、Version/content/source/collection fingerprints、完整lineage和correlation；cursor只按server opaque value前后导航。Implementation `567e8693db881ea3dfffa011de9021fef9641361` / artifact `9552386549`复验25 tests、axe结构检查、type/lint/build、Frontend 9/9及74-path治理，Task=`done`。Playwright browser、Gantt/load/comparison、control、identity、P4和Production仍未形成。
