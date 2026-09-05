---
doc_id: DOC-STATE-001
title: PlanningRun 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P8
normative: true
source_sections: [29, 32, 65]
last_reviewed: 2026-09-05
---

# PlanningRun 状态机

## TASK-P8-05 Worker state consumer

Worker领取P8-04 `QUEUED` attempt时只把operational attempt改为`ACTIVE`，不会制造PlanningRun self-transition。成功候选按冻结pair依次消费`CREATED → INGESTING → VALIDATING → SNAPSHOTTED → BUILDING → SOLVING → SOLVED → VERIFYING → COMPLETED`；每步继续使用expected revision/state/fingerprint CAS并追加原有transition/audit。Solver无候选和Validator拒绝分别收敛到既有terminal语义，状态集合、31个allowed pairs、terminal guards与Schema bytes均未改变。

通用job的`QUEUED/RUNNING/STALLED/SUCCEEDED/FAILED`和lease attempt只诊断消息执行，不是PlanningRun或operational attempt的新状态。无结果检查点的expired lease把当前业务attempt标记`TIMED_OUT`，run保持最后合法状态，只有P8-04显式retry可追加新attempt/work；同work已有有效检查点且业务timeout未到时，job可`STALLED → RUNNING`恢复并继续terminal CAS/版本应用，但不得再次求解或增加业务attempt。业务timeout已到、取消已生效、Runtime/input drift或checkpoint损坏均fail closed。

Terminal PlanningRun永不重开。Cancel与Worker竞争时，以repository合法CAS顺序为准：取消获胜后Worker不能提交后续成功转换或ScheduleVersion；检查点先提交也不赋予绕过取消/timeout的发布权。`COMPLETED`之后的ScheduleVersion补偿只完成一次业务结果，不增加PlanningRun transition。

## TASK-P8-04 durable state implementation

P8-04首次把本页冻结状态机作为durable application consumer实现：`planning_runs`保存current canonical carrier，`planning_run_transitions`按run/sequence append-only保存每个pair，写入要求expected revision/state/run fingerprint CAS，且`revision = sequence + 1`。实现与Schema/registry逐项复验16 states、8 terminal和31 pairs，拒绝unknown、自转换、terminal出边、stale revision/fingerprint及已发布artifact reference变化；`planning-run.schema.json`与`state-machines.v1.yaml` bytes未修改。

Operational attempt使用独立内部诊断状态`QUEUED/ACTIVE/DISPATCH_FAILED/TIMED_OUT/CANCEL_REQUESTED/CANCELLED/SUCCEEDED/FAILED`。它不是新增PlanningRun state：dispatch failure/timeout保持run原state/revision，且terminal attempt只能先retry或显式终结run，不能继续推进非terminal pair；retry只追加新attempt/work item。Cancel终止尚未terminal的attempt，已失败/超时attempt保持原bytes；业务run仍只按本页合法pair推进。Queue-ready不表示Worker已执行，P8-05必须在不增加PlanningRun self-transition的前提下消费该边界。

## TASK-P4-08 terminal result application review

Application只接受既有PlanningRun terminal semantics：`COMPLETED`可原子绑定Solver/Validation/new DRAFT/ChangeReport，其他terminal只绑定SolverReport且不得泄漏partial success。Request/attempt/result是append-only lineage，不新增ReplanRequest状态机或PlanningRun transition/self-transition；same command replay返回原terminal envelope。

状态集合、allowed pairs、guards和`UNKNOWN → NO_SOLUTION_WITHIN_LIMIT`语义逐字不变。New DRAFT是ScheduleVersion创建，不是PlanningRun状态扩展。

## TASK-P4-07 state mapping review

Replan strategy只生成`solver-report.v2.planning_run_outcome`证据并使用既有status mapping：OPTIMAL/FEASIBLE→SOLVED，INFEASIBLE→INFEASIBLE，UNKNOWN→NO_SOLUTION_WITHIN_LIMIT，MODEL_INVALID/FAILED分别保持原义。它不持久化PlanningRun、不产生transition/self-transition，也不创建ScheduleVersion；P4-08仍须在事务内验证terminal result references。状态集合、allowed pairs和guards未修改。

## TASK-P4-03 persistence review

P4-03只追加`request_id/request_fingerprint → planning_run_id/attempt_number → terminal result references`，result必须引用本机既有terminal state；`COMPLETED`才允许完整Solver/Validation/new ScheduleVersion/ChangeReport success references，其他terminal state不得暴露new Version或ChangeReport成功引用。状态集合、allowed pairs、guard与evidence逐字不变，ReplanRequest仍无状态机，exact replay不产生self-transition。

## TASK-P4-02 carrier review

SolverReport v2和ScheduleVersion v2只引用既有PlanningRun identity/outcome；ReplanRequest与ExecutionSimulationManifest不获得业务状态。`state-machines.v1`中PlanningRun states/pairs与terminal semantics逐字冻结，本Task没有run repository、transition或worker行为。

## TASK-P4-01 state decision

ADR-0013已决定ReplanRequest是immutable intent/result envelope，不拥有独立状态机。每个solve attempt继续由本PlanningRun状态机承载，request、attempt、result和audit以append-only reference连接；exact replay不伪造成self-transition。P4-03才可实现持久化，P4-08才可把fresh-validated结果应用为new DRAFT。PlanningRun state set、allowed pair、guard、audit与terminal semantics逐字不变；任何新pair仍须new ADR/contract/Schema/Task扩卡。

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
