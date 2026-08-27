---
doc_id: DOC-STATE-001
title: PlanningRun 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [29, 32, 65]
last_reviewed: 2026-08-27
---

# PlanningRun 状态机

## TASK-P3-17 audit conclusion

P3 application链只消费已完成且validated的P2 PlanningRun lineage，未新增或修改PlanningRun state/pair，也未在workspace service中调用Solver。P2 regression与P3 Gate均PASS；P4 execution/replan state未形成。

## TASK-P3-16 display-boundary review

PlanningRun页面名称和既有state已按`official-zh-cn-terminology.v1`显示`zh-CN`/`en-US` label，但PlanningRun enum、carrier、repository、worker、allowed pairs与Solver lifecycle继续使用英文machine value；未知state显示raw值并fail visibly。Locale切换不触发run、retry、transition或重新计算。Typed coverage/zero-wire-drift evidence已由exact implementation provider复验；PlanningRun实现、Schema和state pair零变化，TASK-P3-17最终独立审计。

## TASK-P3-14 zero-transition Gate

Gate从已完成且已验证的P2 output开始两次fresh replay，并核对P3 lifecycle未反向修改PlanningRun、重试Solver或增加pair。完整raw lifecycle evidence被保留；任何PlanningRun状态副作用都会成为blocking gap。状态机版本不变。

## TASK-P3-13 no-transition review

Human-control browser只调用已有ScheduleVersion/ExportJob application commands；新增download是EXPORTED artifact的只读binary retrieval。PlanningRun enum、16 states、31 allowed pairs、terminal semantics及carrier bytes均未修改，router/browser不导入PlanningRun transition、Solver或Validator。

PlanningRun 只描述计算生命周期，不承载批准、发布或版本替代语义。

```text
CREATED
→ INGESTING
→ VALIDATING
→ SNAPSHOTTED
→ BUILDING
→ SOLVING
→ SOLVED
→ VERIFYING
→ COMPLETED
```

## 终止/失败状态

`DATA_REJECTED`、`MODEL_INVALID`、`INFEASIBLE`、`NO_SOLUTION_WITHIN_LIMIT`、`VALIDATION_FAILED`、`CANCELLED`、`FAILED`。

| 终止状态 | 允许来源示例 | 必需证据 |
|---|---|---|
| DATA_REJECTED | INGESTING/VALIDATING | import quality report |
| MODEL_INVALID | BUILDING/SOLVING | model diagnostics、版本信息 |
| INFEASIBLE | SOLVING | 已认证 Solver 状态与诊断 |
| NO_SOLUTION_WITHIN_LIMIT | SOLVING | limits、UNKNOWN 状态、耗时 |
| VALIDATION_FAILED | VERIFYING | independent validation report |
| CANCELLED | 非终止运行状态 | cancel actor/reason/audit |
| FAILED | 任意系统执行状态 | structured error、attempt、trace |

## 不变量

- `APPROVED`、`PUBLISHED`、`SUPERSEDED` 不得出现在 PlanningRun。
- 状态转移持久化必须幂等并有时间戳/audit。
- Worker 失联应通过任务可靠性机制标记 `STALLED`；`STALLED` 是 Job 运行诊断，不得假装 PlanningRun 已完成。
- `COMPLETED` 只说明计算与验证完成，不说明计划已批准或发布。

## P0 versioned transition table

[`state-machines.v1`](../../../schemas/rules/state-machines.v1.yaml) 固定以下允许目标；表外 pair 统一拒绝为 `INVALID_STATE_TRANSITION`。同一幂等事件重放由持久化层识别，不通过 self-transition 表示。

| From | Allowed to |
|---|---|
| CREATED | INGESTING、CANCELLED、FAILED |
| INGESTING | VALIDATING、DATA_REJECTED、CANCELLED、FAILED |
| VALIDATING | SNAPSHOTTED、DATA_REJECTED、CANCELLED、FAILED |
| SNAPSHOTTED | BUILDING、CANCELLED、FAILED |
| BUILDING | SOLVING、MODEL_INVALID、CANCELLED、FAILED |
| SOLVING | SOLVED、MODEL_INVALID、INFEASIBLE、NO_SOLUTION_WITHIN_LIMIT、CANCELLED、FAILED |
| SOLVED | VERIFYING、CANCELLED、FAILED |
| VERIFYING | COMPLETED、VALIDATION_FAILED、CANCELLED、FAILED |

`COMPLETED`、`DATA_REJECTED`、`MODEL_INVALID`、`INFEASIBLE`、`NO_SOLUTION_WITHIN_LIMIT`、`VALIDATION_FAILED`、`CANCELLED`、`FAILED` 均为终态且无 outgoing pair。`SOLVING → SOLVED` 只接受 OPTIMAL/FEASIBLE candidate；UNKNOWN 只能进入 NO_SOLUTION_WITHIN_LIMIT。`VERIFYING → COMPLETED` 的 guard 是独立 `validation-report.v2` PASS 且 hard count 为 0。

`state-transition.v1` JSON Schema 验证 machine/state 名称；纯 transition table 与 TEST-STATE-TRANSITION-001 才授权 pair。本 Task 不持久化 PlanningRun，也不实现 Worker cancellation 或 Solver status ingestion。

## TASK-P0-08 generic worker review

`jobs/contracts.py` 的 `QUEUED/RUNNING/STALLED/SUCCEEDED/FAILED` 是通用执行诊断，不是 PlanningRun 状态扩展。lease 到期只把 Job 标成 STALLED；不得把 PlanningRun 推到 COMPLETED、FAILED、INFEASIBLE 或其他业务状态。P0-08 没有 PlanningRun persistence/task、Solver status 或 cancellation，因此 `state-machines.v1`、27 states/42 transitions 与 TEST-STATE-TRANSITION-001 均保持不变。

## TASK-P2-02 status outcome contract

Pure mapping把OPTIMAL/FEASIBLE送往`SOLVED`，INFEASIBLE送往`INFEASIBLE`，UNKNOWN送往`NO_SOLUTION_WITHIN_LIMIT`，MODEL_INVALID送往`MODEL_INVALID`，CANCELLED送往`CANCELLED`，FAILED送往`FAILED`。该映射与`state-machines.v1`现有状态一致，没有增加state或transition；候选存在性与product error同时机器校验。

本Task不执行`SOLVING → ...` transition、不持久化PlanningRun，也不实现cancel actor/reason或failure audit。`CONTRACT_SAMPLE`中的UNKNOWN只是映射样例，不能证明真实limits耗尽；后继Worker/Backend仍须把真实status和evidence写入持久化transition guard。

## TASK-P2-11 reporting review

KPI v2与internal manifest只引用既有`planning_run_id`，并要求该ID与真实SolverReport完全一致；它们不创建、claim、完成或重试PlanningRun。`generated_at_utc`取同一SolverReport的finished time，只是immutable provenance，不是状态转移时间写入。PlanningRun state registry、repository、worker lease/heartbeat和failure audit均未修改。

## P3 planning allocation

P3只消费已经完成且candidate通过formal Validator的PlanningRun/Solution；创建ScheduleVersion不得改变PlanningRun状态或重试Solver。P3-04负责消费边界，P3-14 Gate与P3-17 Audit验证lineage和无反向状态副作用；P3-15仅治理计划修订，P3-16仅处理display label。本次不增加PlanningRun pair、repository或worker行为。

## TASK-P3-01 contract review

Workspace合同确认PlanningRun只承担计算生命周期：`COMPLETED`不能授权approve/publish/export，也不等于ScheduleVersion存在。P3 query可只读展示PlanningRun/Solution/Validation lineage；任何manual command只针对ScheduleVersion并产生新DRAFT，不反向改变PlanningRun或重跑Solver。本Task未修改`state-machines.v1`、pure state contract、repository或worker，P3行为仍为`PLANNED`。
## TASK-P3-02 separation review

新增P3 Schema没有修改PlanningRun的16个state、31个allowed pair或terminal集合。`schedule-version.v1.lineage.planning_run_id`只引用已完成的validated P2 run；Workspace command、approval、publication与ExportJob不得重新解释Solver status或推进PlanningRun。Solver `UNKNOWN`继续终止为`NO_SOLUTION_WITHIN_LIMIT`且不能创建Version。

## TASK-P3-03 persistence separation

`0004`没有新增PlanningRun table、state或pair。ScheduleVersion repository只保存已由上游提供的lineage引用，不查询、推进或补写PlanningRun；Publication/Export storage也不能把`COMPLETED`解释为approve/publish/export授权。P3-04+的application仍必须在自己的启动门消费fresh validated solution；本Task的8/8 machine report只证明持久化边界。

## TASK-P3-04 completed-run consumption

Lifecycle context现在必须逐次显式提供`planning_run_state=COMPLETED`；`VERIFYING`及其他值在任何持久化前以`PLANNING_RUN_NOT_COMPLETED`拒绝。P2 PlanningSolution/SolverReport中的`planning_run_outcome.state=SOLVED`继续是求解输出语义，不能被服务改写或冒充持久化PlanningRun COMPLETED事实。

服务没有PlanningRun repository/import/write，也不调用Solver或重试计算；machine evidence记录`planning_run_mutations=0`与`lifecycle_service_solver_invocations=0`。COMPLETED只开放validated output消费门，不授予approve/reject/publish/export，PlanningRun state/pair/terminal bytes保持不变。

## TASK-P3-06 zero-transition review

Command service只读取ScheduleVersion中已绑定的PlanningRun/Problem lineage并对content或review-submit candidate执行Validator；它没有PlanningRun repository或transition port，product-service Solver调用为0。Move/Assign/Lock/SUBMIT不会重开、重试或推进PlanningRun，既有16 states、31 pairs和terminal bytes均无变化。

## TASK-P3-07 zero-transition review

ApprovalDecisionService只读取ScheduleVersion已冻结的PlanningRun lineage并执行ScheduleVersion CAS；没有PlanningRun repository、Solver、Validator或job port。APPROVE/REJECT不会重开、推进或重新解释COMPLETED，也不会把PlanningRun terminal结果当成人工授权；PlanningRun 16 states、31 pairs、terminal集合与machine bytes均保持不变。

## TASK-P3-08 zero-transition review

PublicationService只复制ScheduleVersion已冻结的PlanningRun/Snapshot/Problem/Solution/Validation/KPI/SolverReport lineage进入publication audit；没有PlanningRun repository、Solver、Validator或worker port。APPROVED→PUBLISHED与PUBLISHED→SUPERSEDED均属于ScheduleVersion，不能重开、推进或重解释PlanningRun；其16 states、31 pairs、terminal集合与machine bytes保持不变。

Export worker只消费冻结P2 package和PUBLISHED ScheduleVersion lineage，不读取或推进PlanningRun，不调用Solver/Validator，也不新增PlanningRun pair。Package内PlanningRun ID与P2 payload hash必须原样保留；Export retry只增加Job attempt。

## TASK-P3-10 zero-transition HTTP review

PlanningRun GET与Workspace read route只委托application port；validate/edit/decision/publication/export route也不持有PlanningRun repository、transition或Solver/Validator实现。Router business transition与Solver/Validator invocation在machine evidence中均为0，现16 states、31 pairs、terminal与machine bytes零变化。
