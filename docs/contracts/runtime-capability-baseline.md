---
doc_id: DOC-CONTRACT-016
title: P9 Runtime 能力、准入与验收基线
status: baseline
spec_version: 0.3.0
phase: P9
normative: false
source_sections: [6, 30, 44, 57, 65, 97, 100, 103, 105, 106, 115, 116]
last_reviewed: 2026-09-16
---

# P9 Runtime 能力、准入与验收基线

## P9-05 当前实现增量

相对 P9-01 冻结矩阵，本卡新增 getWorkspaceDataHealth/listWorkspaceImportRuns/listWorkspacePlanningRuns/getPlanningRun/queryScheduleVersionWorkspace/compareScheduleVersions/listScheduleVersionAuditEvents 读 binding，并在显式共享 store 配置下新增 retryExportJob/cancelExportJob/downloadExportPackage 和 export execution。Workspace 的 15 个内部 operation 分派已接通；HTTP operation 数与内部 enum 不混用。下方冻结矩阵不改写历史。

证据范围为安装当前 wheel 的真实 HTTP/SQL/Worker/文件回放，正式源自 durable ingress 和 exact Worker checkpoint；任意人工结果或 v2 不宣称兼容。缺 store 维持 Job-only，缺仿真 manifest 不可生成新包。动态事件/重排、P9-06+、Production 仍未启动，完整证据归属 TASK-P9-05 completion manifest。

本页冻结 P9-01 的静态事实与后续验收分配；不发布新 API、Schema、状态、约束、版本迁移或性能结论。业务规范仍由 [Headless 合同](headless-platform-integration.md)、[Workspace 合同](planning-workspace-api.md)、[事件与重排合同](execution-events-and-replan-request.md)、[版本规则](schema-versioning.md)拥有。P9 目标是补齐正式 Runtime 链路，不能把 router、内部服务或测试注入当成可安装产品覆盖。

## 身份、范围与证据等级

P9-04 当前进展（独立于下方 P9-01 冻结矩阵）：新增 executeScheduleVersionCommand、validateScheduleVersion、rejectScheduleVersion 正式委托；Workspace 共八项，连同 Headless 五项为十三项业务绑定、十九项业务未绑定，健康两项另计。人工/submit 仅 v1，v2 明确 422 MIXED_LINEAGE；完整 read envelope、export execution/download 和 dynamic replanning 仍待后续卡。证据是当前 wheel 安装后 HTTP→DB 重放，不改写 v0.1.0/Kit 旧 bytes 或 P9-01 的静态事实。

核对基线为公开 v0.1.0 的 Runtime 0.1.0、Schema set 2.10.0、SDK 1.0.0；公开 Kit 1.0.1 嵌入选定 Runtime，既有离线包保持 Kit 1.0.0。它们分别版本化，不能合并成“最新版本”。本次读取已发布 Runtime 归档内 wheel，组合根、API 入口、Workspace adapter 与 Worker 源文件和开工源码文本一致；这是字节/源码核对，未重新安装或执行制品。具体不可变身份与摘要在本卡机器报告保存。

状态口径：`BOUND` 是显式配置身份/scope/Runtime 后有正式委托；`UNBOUND` 是无正式委托，授权先通过也只能到 unavailable；`BOUND_JOB_ONLY` 不证明导出执行/文件下载；`BOUND_RAW_DOCUMENT` 不证明完整 workspace read envelope/allowed_actions。默认配置缺少身份/provider 时仍拒绝；所有支持声明限 TEST/SIMULATION。健康两项加业务十项有绑定，业务二十二项未绑定；34 项不是 34 项可用业务能力。`/openapi.json` 是内建合同入口，不计入这 34 项。

Router：H=[app.py](../../backend/app/api/app.py)，R=[headless_planning_runs.py](../../backend/app/api/routers/headless_planning_runs.py)，W=[planning_workspace.py](../../backend/app/api/routers/planning_workspace.py)，D=[dynamic_replanning.py](../../backend/app/api/routers/dynamic_replanning.py)。

正式装配由 [compose_runtime](../../backend/app/runtime_composition.py) 和 [create_runtime_app](../../backend/app/api/app.py)拥有；[RuntimePlanningWorkspaceApplication](../../backend/app/application/runtime_planning_workspace.py) 的五项白名单是 W 的实际边界。D 仅有 [port/路由 helper/unavailable](../../backend/app/api/replanning_contracts.py)，入口未注入 dynamic application。

## 逐 operation 覆盖矩阵

每行独立列出 owner、repository、binding 和证据组；owner 表示内部语义归属，含 port 的行明确尚无正式业务 adapter。后续责任是验收分配，均未在本卡执行。所有行都须通过下节公共正反验收；不能凭同组其他行 PASS 补齐本行。

| Operation ID | Method / path | Router | 内部 owner | Repository / source | Runtime binding | 证据组 | 后续验收 owner |
|---|---|---|---|---|---|---|---|
| `getChangeReport` | `GET /api/v1/change-reports/{report_id}` | D | change_report_queries / read projection | ReplanLineage / ChangeReport | UNBOUND | Q | P9-07 |
| `listExecutionEvents` | `GET /api/v1/execution-events` | D | DynamicReplanningApplicationPort / stream read | ExecutionEvent | UNBOUND | D | P9-06 |
| `appendExecutionEvent` | `POST /api/v1/execution-events` | D | ExecutionFactProjectionService.ingest_event | ExecutionEvent + ReplanAudit | UNBOUND | E | P9-06 |
| `getExecutionEvent` | `GET /api/v1/execution-events/{event_id}` | D | DynamicReplanningApplicationPort / ledger read | ExecutionEvent | UNBOUND | D | P9-06 |
| `getExportJob` | `GET /api/v1/export-jobs/{export_job_id}` | W | RuntimePlanningWorkspaceApplication._get_export | ExportJob | BOUND_JOB_ONLY | O | P9-05 |
| `cancelExportJob` | `POST /api/v1/export-jobs/{export_job_id}/cancel` | W | ExportJobService.cancel | ExportJob + Audit | UNBOUND | X | P9-05 |
| `downloadExportPackage` | `GET /api/v1/export-jobs/{export_job_id}/download` | W | ExportPackageDownloadService | ExportJob + verified package store | UNBOUND | X | P9-05 |
| `retryExportJob` | `POST /api/v1/export-jobs/{export_job_id}/retry` | W | ExportJobService.claim（EXPORT_FAILED 重试；HTTP adapter 待补） | ExportJob + Audit | UNBOUND | X | P9-05 |
| `createHeadlessPlanningRun` | `POST /api/v1/planning-runs` | R | APSRuntimeApplicationFacade.submit_canonical | Ingress + PlanningRun | BOUND | R | P9-03/10 |
| `getPlanningRun` | `GET /api/v1/planning-runs/{planning_run_id}` | W | WorkspaceQueryService / PlanningRun projection | WorkspaceSourceDocuments | UNBOUND | W | P9-05 |
| `cancelHeadlessPlanningRun` | `POST /api/v1/planning-runs/{planning_run_id}/cancel` | R | APSRuntimeApplicationFacade.cancel_planning_run | PlanningRun CAS | BOUND | R | P9-10 |
| `getHeadlessPlanningRunResult` | `GET /api/v1/planning-runs/{planning_run_id}/result` | R | APSRuntimeApplicationFacade.read_planning_run（terminal guard） | PlanningRun/result | BOUND | R | P9-10 |
| `retryHeadlessPlanningRun` | `POST /api/v1/planning-runs/{planning_run_id}/retry` | R | APSRuntimeApplicationFacade.retry_planning_run | PlanningRun + dispatch | BOUND | R | P9-10 |
| `getHeadlessPlanningRunStatus` | `GET /api/v1/planning-runs/{planning_run_id}/status` | R | APSRuntimeApplicationFacade.read_planning_run | PlanningRun | BOUND | R | P9-10 |
| `createReplanRequest` | `POST /api/v1/replan-requests` | D | ReplanApplicationService / future async adapter | ReplanRequest + Lineage + Snapshot | UNBOUND_SYNC_OWNER | Q | P9-07 |
| `getReplanRequest` | `GET /api/v1/replan-requests/{request_id}` | D | DynamicReplanningApplicationPort / request read | ReplanRequest + Lineage | UNBOUND | D | P9-07 |
| `cancelReplanRequest` | `POST /api/v1/replan-requests/{request_id}/cancel` | D | DynamicReplanningApplicationPort / attempt action | Lineage / future durable async attempt | UNBOUND | D | P9-07 |
| `getReplanResult` | `GET /api/v1/replan-requests/{request_id}/result` | D | DynamicReplanningApplicationPort / result read | ReplanLineage | UNBOUND | D | P9-07 |
| `retryReplanRequest` | `POST /api/v1/replan-requests/{request_id}/retry` | D | DynamicReplanningApplicationPort / attempt action | Lineage / future durable async attempt | UNBOUND | D | P9-07 |
| `compareScheduleVersions` | `POST /api/v1/schedule-version-comparisons` | W | ScheduleComparisonService | ScheduleVersion + source projections | UNBOUND | W | P9-05 |
| `getScheduleVersion` | `GET /api/v1/schedule-versions/{schedule_version_id}` | W | RuntimePlanningWorkspaceApplication._get_schedule | ScheduleVersion | BOUND_RAW_DOCUMENT | O | P9-05 |
| `approveScheduleVersion` | `POST /api/v1/schedule-versions/{schedule_version_id}/approve` | W | ApprovalDecisionService | ScheduleVersion + Audit | BOUND | O | P9-04 |
| `listScheduleVersionAuditEvents` | `GET /api/v1/schedule-versions/{schedule_version_id}/audit-events` | W | WorkspaceQueryService / AUDIT view | Audit | UNBOUND | W | P9-05 |
| `executeScheduleVersionCommand` | `POST /api/v1/schedule-versions/{schedule_version_id}/commands` | W | ScheduleCommandService | ScheduleVersion + Audit | UNBOUND | M | P9-03/04 |
| `createScheduleVersionExport` | `POST /api/v1/schedule-versions/{schedule_version_id}/exports` | W | ExportJobService.create | ExportJob + Publication + Audit | BOUND_JOB_ONLY | O | P9-05 |
| `publishScheduleVersion` | `POST /api/v1/schedule-versions/{schedule_version_id}/publish` | W | PublicationService | ScheduleVersion + Publication + Audit | BOUND | O | P9-04 |
| `rejectScheduleVersion` | `POST /api/v1/schedule-versions/{schedule_version_id}/reject` | W | ApprovalDecisionService | ScheduleVersion + Audit | UNBOUND | W | P9-04 |
| `validateScheduleVersion` | `POST /api/v1/schedule-versions/{schedule_version_id}/validate` | W | ScheduleCommandService / SUBMIT_FOR_REVIEW | ScheduleVersion + Audit | UNBOUND | M | P9-03/04 |
| `queryScheduleVersionWorkspace` | `GET /api/v1/schedule-versions/{schedule_version_id}/workspace/{view}` | W | WorkspaceQueryService | ScheduleVersion + source projections | UNBOUND | W | P9-05 |
| `getWorkspaceDataHealth` | `GET /api/v1/workspace/data-health` | W | WorkspaceQueryService | WorkspaceSourceDocuments | UNBOUND | W | P9-05 |
| `listWorkspaceImportRuns` | `GET /api/v1/workspace/import-runs` | W | WorkspaceQueryService | WorkspaceSourceDocuments | UNBOUND | W | P9-05 |
| `listWorkspacePlanningRuns` | `GET /api/v1/workspace/planning-runs` | W | WorkspaceQueryService | WorkspaceSourceDocuments | UNBOUND | W | P9-05 |
| `live_health_live_get` | `GET /health/live` | H | liveness_report | none | BOUND | H | P9-10 |
| `ready_health_ready_get` | `GET /health/ready` | H | readiness_report | DB/Redis/Registry probes | BOUND_RESPONSE_GAP | H | P9-10 |

### Owner 与 repository 定位

- R：[Runtime facade](../../backend/app/application/runtime_facade.py) → [canonical ingress repository](../../backend/app/infrastructure/canonical_ingress_repository.py)、[PlanningRun repository](../../backend/app/infrastructure/planning_run_repository.py)，Worker 使用独立 lease/checkpoint repository。
- W read：[WorkspaceQueryService](../../backend/app/application/workspace_queries.py)、[ScheduleComparisonService](../../backend/app/application/schedule_comparison.py)消费显式 WorkspaceSourceDocuments；现有服务不等于已有完整 durable source assembler。版本/审计由 [schedule repository](../../backend/app/infrastructure/schedule_version_repository.py)、[audit repository](../../backend/app/infrastructure/audit_repository.py)拥有。
- W control：[ScheduleCommandService](../../backend/app/application/schedule_commands.py)、[ApprovalDecisionService](../../backend/app/application/approval.py)、[PublicationService](../../backend/app/application/publication.py)；导出使用 [ExportJobService](../../backend/app/application/export_jobs.py)、[download service](../../backend/app/application/export_downloads.py)、[export repository](../../backend/app/infrastructure/export_job_repository.py)。Runtime 当前创建 Job，不装配完整 export worker/store/download 链。
- D：[ExecutionFactProjectionService](../../backend/app/application/execution_fact_projection.py) → [event repository](../../backend/app/infrastructure/execution_event_repository.py)和 [checkpoint/request/lineage/audit repositories](../../backend/app/infrastructure/replan_repository.py)；[ReplanApplicationService](../../backend/app/application/replan_application.py)内部同步调用 strategy.solve，不能原样挂到 HTTP。取消/重试需 P9-07 形成正式 durable attempt adapter，不能从 port 推定已存在。

### 证据组与缺口

| 组 | 可检查的现有证据入口 | 能证明的层次 / P9 仍需 |
|---|---|---|
| H | API 组合根、提交版 OpenAPI | 进程/探针代码；ready 实际有 503，快照仅声明 200，P9-10 补响应合同与制品负例 |
| R | [Runtime integration](../../backend/tests/integration/test_p8_runtime_composition.py)、[Headless integration](../../backend/tests/integration/test_p8_headless_http_api_integration.py) | 已有正式首排链；P9-03 准入回归、P9-10 新精确制品组合验证 |
| O | [Runtime adapter](../../backend/app/application/runtime_planning_workspace.py)、[公开部署边界](../operations/deployment.md#显式-test-工作区授权与离线验收) | 历史制品链覆盖读版本/审批/发布/导出 Job；不覆盖完整读模型/导出字节 |
| W | [Workspace HTTP contract](../../backend/tests/contract/test_planning_workspace_http_api.py)、[read unit](../../backend/tests/unit/test_workspace_read_models.py) | 路由/内部 owner；缺正式组装与逐 operation 制品正反例 |
| M | [command transaction](../../backend/tests/integration/test_schedule_command_transactions.py)、[独立 mutation](../../backend/tests/validation/test_schedule_command_validator_mutation.py) | 内部 fresh Core 校验；缺 Runtime、Extension 和 v2 consumer |
| X | ExportJob/download owner、Workspace HTTP contract | 内部导出 lifecycle/verified binary port；缺正式 executor/store/download 与恢复证据 |
| E | [projection integration](../../backend/tests/integration/test_p4_execution_fact_projection.py) | ledger/projection 内部事务；缺 Runtime binding |
| D | [dynamic HTTP contract](../../backend/tests/contract/test_dynamic_replanning_http_api.py) | transport/注入 port；不证明生产式异步编排或已装配 |
| Q | [replan integration](../../backend/tests/integration/test_p4_replan_application.py)、[change read](../../backend/app/application/change_report_queries.py) | 内部重排/ChangeReport；缺正式异步 Worker、统一 Extension 准入和 v2 下游 |

这些测试文件本次仅作静态证据定位，未执行；P9-01 的文档 PASS 不代替它们的业务结果。新制品证据由 P9-10 绑定 Runtime/SDK/Extension/Kit、安装环境及每行正反路径，P9-11 做纵向 Gate，P9-12 独立判定。

公共逐行验收：有授权的合法输入得到声明的状态/carrier/lineage；缺身份、错 capability/scope、未知版本、篡改 fingerprint 在业务副作用前拒绝；有 command 的行再验证 same-key replay、different-content conflict、stale state/revision/CAS 和故障回滚；读行验证空/缺失/越权/陈旧和 cursor；健康行验证依赖 unavailable。错误按现有 namespace 映射，不能把 `SERVICE_UNAVAILABLE` 与排程 `UNSUPPORTED_CAPABILITY` 混用。

P9 承诺补齐表中既有 surface 并验收；新约束 C-012～C-018、搜索扩展贡献、真实 IdP/Production、外部系统回写与新私有 route 均排除。任何 operation 最终未覆盖须保留 gap 并显式修订阶段承诺，不能在 Exit 自动跳过。

## 三来源候选准入基线

这是对现有独立校验、不变 lineage、人工控制规则的汇总；“统一”实现归 P9-03。本卡不改变状态机，不把重排 DRAFT 自动提升 READY。

共同顺序：服务端身份/scope与精确版本 → scoped idempotency / source state-content-revision → 不可变 source/Snapshot/Problem/Policy/Limits 和 Runtime/Registry/config 绑定 → 构造候选 → fresh Core Validator → 所有适用 Extension Validation Rule → 验证报告/候选/输入引用一致 → 事务或现有 checkpoint+CAS 边界持久化 → 显式人工审批发布。每个新候选和新的提交评审动作都要 fresh；exact command replay重放已持久化相同逻辑结果，不产生新候选。Worker recovery 沿既有规则复验 checkpoint，不能用 replay 绕过 identity/完整性检查。

| 来源 | source 与输入 lineage | 当前实际准入 / 产出 | P9 验收责任 |
|---|---|---|---|
| 首次排程 | canonical acceptance → Snapshot v2 / Problem v2 → PlanningRun work/attempt；精确 Policy/Limits/Runtime/Extension set | Worker 检查输入/lease、调用 Global Solver、fresh ProblemScheduleValidator；验证 checkpoint 时调用 Extension after_candidate；COMPLETED 后 application 原子保存 DRAFT→READY 与 audit | P9-03 保持现有 checkpoint/terminal/recovery 边界，统一准入且不重复 solve；P9-10 制品验证 |
| move/assign/set/remove lock | exact source Version + Problem；derived manual candidate、source/new Version 与 ValidationReport 引用 | ScheduleCommandService 注入 validator_factory，fresh Core 后 copy-on-write DRAFT；未装配 Runtime Extension | P9-03/04：same violation 三来源均拒绝；manual/lock 不改变旧 content；支持的 v1/v2 路径显式选择 |
| submit/validate | exact manual DRAFT state/revision/content + 所属 Problem | 再次 fresh Core 后 CAS DRAFT→READY；命令 replay 复用原 audit/引用 | P9-03/04：不得借旧报告、缺失 Registry、错 scope 或绕过 Extension 入评审 |
| 事件重排 | PUBLISHED base/current + 有序 event prefix/checkpoint + 新 Snapshot/Problem + freeze/effective locks + Policy v2/Limits | ReplanApplicationService 同步 solve，fresh validate_replan_candidate，事务保存新 ScheduleVersion v2 DRAFT / 完整 ChangeReport / result / audit；未接 Runtime Extension | P9-03/06/07：HTTP 只接受/查询，Worker 求解；保留 base、完成/运行事实、HARD/freeze；无自动 approve/publish |

必须保留的拒绝：缺失/异常 Validator、Core 非 PASS/硬违反、适用扩展缺失/异常/timeout/拒绝、错 Problem/source/Registry/config/version、越权/跨 plane、取消/过期 lease/CAS loser。失败可保留注册的 attempt/audit/error 证据，但不能留下成功候选、部分发布/导出或被接受的非法计划。FEASIBLE 不称最优，UNKNOWN 仍为 NO_SOLUTION_WITHIN_LIMIT，不能改成 INFEASIBLE。

现有 [Extension executor](../../backend/app/extensions/product_execution.py) 调用 constraints/planning rules/replan policy/objectives/validation callbacks；这不等于其贡献被编译进 CP-SAT 搜索，后者属于 P11。P9-03 不能靠增加回调次数宣称搜索能力。

## JSON 与版本消费差异

| 检查项 | 当前事实与风险 | 冻结处理 / 后续 owner |
|---|---|---|
| canonical 字节 | Python canonical serializer 为 UTF-8、sort_keys、compact separators、ensure_ascii=False、allow_nan=False；各 artifact projection 的排除字段不同 | P9-02 对每种 projection 建跨语言向量；保持旧 canonical-json.v1 字节/hash；不称 RFC 8785/JCS |
| 数值 | Python json.dumps 与浏览器 JSON.stringify 并非相同数值词法；1.0/1、负零、指数阈值和超出 JS safe integer 是风险 | P9-02 实测明确向量，禁止以 JSON.parse 后重序列化改写后端指纹；任何 hash 语义改变先新版本/兼容决定 |
| Unicode/键 | [Frontend canonical](../../frontend/src/api/canonical.ts)显式 code-point 排序，字符串仍走 JSON.stringify；不能假定 Unicode normalization | P9-02 覆盖非 BMP、转义、组合/分解字符、控制字符与无效 UTF-8；按既有合同拒绝/保留，不擅加 normalization |
| strict ingress | Headless bytes parser 拒绝重复键、NaN/Infinity、unknown field/version、压缩/文件输入；其他 consumer 的等价覆盖不能由此推定 | P9-02/08 对请求与响应分别核对；区分 null/缺失，不补默认、不四舍五入 |
| 时间与数量 | canonical records 要求 UTC Z、整数秒与字段级范围；quantity 为正 number，尚不是 P10 精确数量 carrier | P9-02 保留边界/时区/精度与错误；P10 再决定数量新语义，不把 JS number 当任意精度 |
| Schema set / document | 当前 set 2.10.0，不代表所有 document 内的历史 set const 都变成 2.10.0 | 精确选 URN/version，旧 bytes 保留；本卡 migration=none |
| PlanningRun reads | getPlanningRun 是旧 workspace 摘要，/status、/result 是 planning-run.v1；非 terminal result=409 | P9-05/08 明确各 consumer，禁止用新 read 偷换旧 operation |
| ScheduleVersion v1/v2 | 首排/人工 P3 路径 v1；重排产生 v2；schedule_commands source 检查只接受 v1，Frontend api/contracts.ts 也只接受 v1 | P9-02 兼容决策；P9-04/05/08 显式 v2 支持及错误，不删除 v2 lineage 或伪装 v1 |
| read envelope | Runtime getScheduleVersion 返回 repository document；完整 allowed_actions、workspace 投影/分页/比较另属 read service | P9-05 补 durable source assembly 与 read envelope；P9-08 消费相同协议，不能前端推算 state/KPI |
| export v1/v2/v3 | v1 保留；P3 Job/Manifest v2，P4 ChangeReport 对应 Job/Manifest v3，不能互换；现 Runtime 只创建/读取 Job | P9-05/08 显式 v2/v3 路径、下载校验、retry/cancel 与重启恢复；旧版本不能补假字段升级 |
| Runtime/SDK/Kit | Runtime 0.1.0、SDK 1.0.0、公开 Kit 1.0.1 与离线 Kit 1.0.0 是不同组合 | P9-10 新制品精确组合、旧 Kit 重放/回退；不覆盖旧包，不自动升级企业项目 |

代码事实入口：[Snapshot canonical](../../backend/app/snapshots/canonical.py)、[Workspace canonical](../../backend/app/domain/workspace_contracts.py)、[manual version guard](../../backend/app/domain/schedule_commands.py)、[replan v2 producer](../../backend/app/domain/replan_application.py)、[Frontend consumer](../../frontend/src/api/contracts.ts)。所有差异在 owner 完成前都是 gap；本卡没有把建议转换为新 wire 合同。

## P9 仿真覆盖与验收冻结

以下是设计冻结的覆盖单元，每单元均需合法正例、独立非法/边界例、至少一个关联组合及正式制品 HTTP→DB/queue→Worker 路径。现有内部回归可作输入，不能替代安装制品；P9-09 负责形成资产/报告，P9-11/12 负责 Gate/独立重放。

| 单元 | 必需语义和拒绝路径 | 组合 | owner |
|---|---|---|---|
| B01 | 基本 FJSP/DAG、候选设备差异工时、跨车间 transport；非法资源/重叠/precedence | 日历碎片 + 跨车间 + tight due | P9-03/09 |
| B02 | 运行中/已完成事实与 HARD/SOFT lock；独立篡改事实、锁/冻结冲突 | 事实 + 锁 + 日历边界 | P9-03/04/07 |
| B03 | move/assign/set/remove/submit、approve/reject/publish；旧 content/state/revision、并发 loser | manual + Extension + stale version | P9-03/04 |
| B04 | orders/operations/resources/calendars/Gantt/load/KPI/diagnostics/locks/audit、分页/compare | v1/v2 + cursor + scope | P9-05/08 |
| B05 | 导出创建/读取/执行/下载/retry/cancel；坏 hash/partial write/未完成下载 | publication + v2/v3 + restart | P9-05/08 |
| B06 | 连续五类异常：Urgent Order、Machine Failure、Material Delay、Processing Delay、Early Completion；另覆盖恢复与锁变化，逐项覆盖合同11种事件 | 连续五类 + 运行/完成 + 锁 | P9-06/07/09 |
| B07 | event exact replay/conflict、gap/late/out-of-order、cross authority/scope；非法 prefix 不推进 checkpoint | 重启 + prefix + projection CAS | P9-06/07 |
| B08 | Worker 中断/取消/timeout、checkpoint 前后、重复投递、retry | recovery + Registry mismatch + same work | P9-03/07/10 |
| B09 | Core/Extension 同类拒绝、缺失/异常/超时、篡改 Problem/Registry/config | 首排 + manual + replan | P9-03/09/10 |
| B10 | strict JSON、跨语言 hash、版本错配、same key different body、越权 | host + Frontend + immutable old bytes | P9-02/08/10 |

正确性硬门：接受候选 Core/适用 Extension 全部通过且硬违反为零；缺项为 NOT_RUN/gap，不能计 PASS。人工可核验小例使用独立 oracle，mutation 不调用 Solver 的约束构建代码；故意不可行与预算 UNKNOWN 分开计数，不隐藏失败分母。

### 画像、seed 与保留集

复用 [P2 profiles](../../benchmarks/profiles.yaml) 原版本，只作已有开发基线，不称 SME 真实分布：XS=4×2 工序/3资源/1车间/1日历片，S=8×3/6/2/2，M=12×4/8/2/4；各工序2候选，tick=60秒，horizon=180/480/900 ticks。原 seed 20261201/20261202/20261203、原文件及 baseline bytes 不变。

P9 新 catalog 以 B01～B10 × 适用 XS/S/M 的显式映射覆盖，而非盲目全乘积。冻结的 seed 预留为：开发 910101/910102/910103；保留 910901/910902/910903，分别对应 XS/S/M。场景 child seed 必须由 catalog version、单元、主 seed 和命名子流确定，禁止依调用顺序/全局随机状态。P9-09 使用前登记新 SIM 假设，生成器/画像/场景精确版本和全部参数须在首次生成前写入不可变 catalog；本卡不生成资产，也不宣称预留 seed 已被运行或验证。

保留集由独立 Exit 消费，开发调参只读取开发集；P9-09 在调参前封存 holdout catalog/hash，登记访问和首次结果。失败保留原结果与缩减例；不得换 seed 或移动阈值获得通过，若需修订，保留旧集并新版本重审。L/压力层未定义，不计入 P9 规模承诺。

### 测量方案与待冻结项

旧 P2 单求解预算 XS/S/M=3/5/4秒、warmup=1/measured=3 仅用于原 profiles 可比重放，不能充当整个 Runtime 端到端 SLA。P9-09 开始性能验收前，必须用开发样本测量并冻结新 profile：CPU/核心数/内存/OS、Python/OR-Tools/Runtime/SDK/Kit/Extension 精确版本、DB/broker、并行度、每阶段及端到端 wall-time/内存预算、相对退化门、重复目的和次数。未测新链预算明确 `PENDING_MEASUREMENT`，缺冻结值阻断 P9-09 性能验收及 P9-11/12 Gate，不阻断本卡文档基线。

报告分别列 build/first-feasible/solve/validation/export/端到端耗时、模型规模/峰值内存、objective/bound/gap、每状态计数与分母、失败/超时/重试。3次测量保留全部原值和 min/median/max，不能拿单次最好值或小样本 P95 声称稳定 SLA。开发测量结束后冻结退化门再开保留集；同输入重复用于确定性，重启重复用于恢复，二者分别说明目的。

### 二值验收归属

P9-02 关闭 JSON/版本决策，P9-03 关闭三来源统一准入，P9-04/05 关闭 W 的控制/read/export，P9-06/07 关闭事件和异步 D，P9-08 关闭宿主/Frontend 同协议消费，P9-09 交付冻结场景与预算证据，P9-10 交付每 operation 的可安装组合证据，P9-11 纵向 Gate，P9-12 独立 Exit。每项须提供输入/version/hash、正负结果、错误与无非法副作用证据、Runtime/SDK/Extension/Kit identity 和未覆盖项；缺任一适用项不能算完成。
