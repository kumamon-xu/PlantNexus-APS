---
doc_id: DOC-CONTRACT-005
title: PlanningSolution 与 ScheduleVersion 合同
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [29, 30, 32, 33, 67, 78]
last_reviewed: 2026-08-24
---

# PlanningSolution 与 ScheduleVersion 合同

PlanningSolution 是 SolverBackend 的候选输出，应包含 Solver 状态、operation assignments、objective/bound/gap、diagnostics 和 provenance。它不代表已经验证、批准或发布。

## Operation assignment

每个被排 Operation 至少给出 operation ID、selected resource、start/end tick 和可还原 UTC 时间、duration、lock/execution references。不得只返回展示用 Gantt 坐标。

## 从 Solution 到 Version

```text
PlanningSolution
→ independent validation
→ validation report PASS
→ DRAFT ScheduleVersion
→ READY_FOR_REVIEW
```

如果验证失败，PlanningRun 进入 VALIDATION_FAILED，不得生成可评审版本。

## ScheduleVersion

ScheduleVersion 必须引用 source PlanningRun、Snapshot、Problem、base version（若 Replan）、validation report、KPI、ChangeReport 和 audit。版本内容在 PUBLISHED 后不可变。

只有 APPROVED version 可以发布。所有编辑、拒绝后修订和 Replan 产生新 version ID。

## P0 state contract boundary

[`state-transition.v1`](../../schemas/json/state-transition.schema.json) 只验证 machine/state 名称；[`state-machines.v1`](../../schemas/rules/state-machines.v1.yaml) 与纯状态枚举共同固定允许 pair、终态、guard/evidence 文本。`DRAFT → PUBLISHED` 即使字段名称合法也必须由 transition table 拒绝为 `INVALID_STATE_TRANSITION`。

这些 artifact 不持久化状态、不执行审批/发布、不解决 OPEN-010 权限角色。P3 实现必须保留 ADR-0007 的新版本/不可变语义，并把 actor、reason、audit、idempotency 等 guard evidence 落为真实记录。

## TASK-P2-02 PlanningSolution v1 boundary

[`planning-solution.v1`](../../schemas/json/planning-solution.schema.json)固定Problem v2、Policy v1和Limits v1引用，assignment按operation ID唯一有序，保存resource、start/end tick、由horizon/tick精确还原的UTC、权威duration seconds以及lock/execution fact IDs。`duration_ticks=ceil(duration_seconds/tick_seconds)`；非candidate状态禁止assignments。

P2只允许一个OBJ-001 stage。由于weighted tardiness与bound均为非负整数，`relative_gap=(objective_value-best_bound)/max(1, objective_value)`且范围为`[0,1]`；bound不得大于minimization candidate objective。OPTIMAL还要求objective等于best bound且gap为0；FEASIBLE要求objective/bound/gap存在但不冒充最优；UNKNOWN不得携带candidate objective/gap；INFEASIBLE/MODEL_INVALID/CANCELLED/FAILED均不得携带objective/bound/gap。Stage solve time不得超过显式stage budget，所有非candidate结果必须提供sanitized diagnostics。

本合同是candidate carrier，不是独立ScheduleValidator结果。只有未来`SOLVER_RUN`且通过独立ValidationReport的candidate才能进入后续ScheduleVersion流程；本Task发布的UNKNOWN `CONTRACT_SAMPLE`没有candidate，也不创建DRAFT、READY_FOR_REVIEW或任何P3状态。

## TASK-P2-04 Validator consumption

正式Validator现直接消费`planning-solution.v1`的Problem reference与assignments，并逐项对照权威PlanningProblem v2；Policy/Limits/objective/declared solver status不参与schedule validity。Schema-valid positive vector先通过`validate_planning_solution`，随后由独立Evaluator重算C-001～C-011；status矛盾测试故意绕过machine-contract precheck，只用于证明Validator不把status当oracle，不能作为可持久化PlanningSolution。

Assignment的tick/seconds/UTC在formal边界重新核对。NOT_STARTED duration来自selected option；RUNNING future occupancy与`duration_seconds`来自Problem的`remaining_seconds`。Validation FAIL映射Error v2，不创建或迁移ScheduleVersion，也不改变四份P2-02 Schema/sample bytes、global schema set或canonical fingerprint规则。

## TASK-P2-05 core candidate mapping

完整native candidate被映射为每operation恰一条assignment，保存selected resource的原始seconds、ceiling ticks及由horizon start还原的UTC；只有formal Validator PASS时才保留assignments。INFEASIBLE/UNKNOWN/MODEL_INVALID/FAILED等非candidate状态必须输出空assignments，不能泄漏部分解。

PlanningSolution v1要求的OBJ-001 stage在本Task只承载post-solve measurement：状态为FEASIBLE、best bound为通用0、gap按已测值计算，并以`CORE_FEASIBILITY_ONLY_*_OBJECTIVE_NOT_OPTIMIZED`明确未运行目标搜索。Schema、ScheduleVersion迁移与publishability均不变；所有candidate只作为测试artifact。

## TASK-P2-06 temporal candidate mapping

Candidate继续使用既有assignment seconds/ticks/UTC字段，不新增temporal字段；C-002/005/006/009只约束这些assignment在Problem权威事实下的合法性。完整candidate仍须经formal Validator PASS后保留，任何Validator FAIL、MODEL_INVALID、INFEASIBLE或UNKNOWN均不得泄漏partial assignments。

PlanningSolution Schema、fingerprint和ScheduleVersion状态机不变。Native OPTIMAL仍映射为业务FEASIBLE，OBJ-001只做post-solve measurement；temporal正确性不能升级为objective最优、可发布ScheduleVersion或Production结果。

## TASK-P2-07 fact/lock candidate mapping

RUNNING assignment的resource来自Problem `assigned_resource_id`，`start_tick=0`，`end_tick=ceil(remaining_seconds/tick_seconds)`，`duration_seconds=remaining_seconds`；不再使用selected option的原始duration。HARD lock candidate精确匹配resource/start/end，SOFT lock可以移动；assignment仍稳定回写该operation全部HARD/SOFT `lock_ids`以保持metadata provenance。

Problem v2没有向active RUNNING operation暴露execution fact ID，因此`execution_fact_ids`保持空数组，禁止用operation ID或source record猜造；actual start/resource/remainder由candidate引用的Problem hash保存。PlanningSolution Schema/fingerprint与ScheduleVersion状态机不变，完整candidate仍须formal Validator PASS；INFEASIBLE/MODEL_INVALID/UNKNOWN/FAILED均不得泄漏partial assignments。Native OPTIMAL继续降级为业务FEASIBLE，OBJ-001仅post-solve measurement。

## TASK-P2-08 objective-aware Solution/Report

Global Strategy路径现在执行OBJ-001：native OPTIMAL只有在目标值等于certified bound且gap=0时保留OPTIMAL；有candidate但未证明最优时为FEASIBLE；无candidate且无证明时为UNKNOWN/NO_SOLUTION_WITHIN_LIMIT；hard domain证明无解才为INFEASIBLE。FEASIBLE使用保守整数lower bound计算gap，UNKNOWN可保存bound但不得保存objective/gap/assignments。Validator FAIL转FAILED并丢弃全部assignments/objective candidate。

SolverReport v1现在由真实`SOLVER_RUN`填充exact solver/parameters、stage、build/first-feasible/solve/validation/total、model metrics、memory与code commit，并与Solution逐字bundle replay。PlanningSolution/SolverReport Schema及状态合同不变；本Task不创建ScheduleVersion、approval、publish或Export。

## P3 planned consumer chain

P3-04只能把fresh formal Validator接受的PlanningSolution复制为immutable ScheduleVersion DRAFT，再由既有guard进入READY_FOR_REVIEW。P3-06的edit/lock只产生新DRAFT，P3-07/08分别执行approval/rejection与APPROVED-only publish；任何PUBLISHED内容更新均为禁止路径。上述行为须等待P3-01合同/ADR、P3-02 Schema和P3-03 persistence完成，本次没有创建ScheduleVersion。

## TASK-P3-01 ScheduleVersion contract baseline

[ADR-0012](../adr/ADR-0012-planning-workspace-command-state-publication.md)现已接受ScheduleVersion content append-only/copy-on-write：validated P2 Solution未来可创建新DRAFT；任何manual edit/lock都读取source Version并产生具有新ID、parent、content fingerprint、fresh ValidationReport与audit的新DRAFT，source content/state/current publication不改变。PlanningSolution仍不是ScheduleVersion，Validator PASS仍只是READY_FOR_REVIEW的必要而非充分条件。

## TASK-P3-02 ScheduleVersion machine carrier

[`schedule-version.v1`](../../schemas/json/schedule-version.schema.json)现以global set`2.6.0`固定ID/revision/state、plane/environment/synthetic provenance、parent/source kind、完整P2 PlanningRun/Snapshot/Problem/Solution/Validation/KPI/SolverReport/code lineage、assignment/lock content、canonical content fingerprint、fresh PASS evidence、decision/publication/supersession references与server-derived allowed actions。Assignment逐项复用`planning-solution.v1#/$defs/operationAssignment`的stable offline `$ref`，但两个顶层document不互换。

Schema只允许既有六个ScheduleVersion state，Production carrier只能表达未发布评审态；P3 v1 publication evidence只接受`SIMULATION_INTERNAL`。`app.domain.workspace_contracts`复验content fingerprint和Validation lineage相等，但不创建Version、不执行copy-on-write/transition/authorization/publish。P2 PlanningSolution/Validation/KPI/Export bytes完全保留；behavior owner仍为TASK-P3-03～08。

## TASK-P3-03 repository contract

ScheduleVersion persistence现要求：完整`2.6.0` carrier通过pure/top-level/plane/fingerprint precheck；identity按plane+ID唯一；creation bytes同值重放，不同值冲突；parent reference只能指向同plane已存Version；immutable projection覆盖版本、lineage、validation、content、parent、creator和created-at。合法state metadata变化必须同时满足existing pair、expected state与单调state revision，数据库trigger提供第二层content/delete保护。

Repository不会从PlanningSolution创建DRAFT、不会调用Validator，也不会判断approve/publish capability。P3-04必须复制fresh Validator PASS的validated solution并提供完整carrier；P3-06修改/lock仍必须新建Version，不能调用CAS原地改content。

既有pair不变：DRAFT→READY_FOR_REVIEW，READY_FOR_REVIEW→APPROVED/REJECTED，APPROVED→PUBLISHED，PUBLISHED→SUPERSEDED。Approve/Reject只消费READY，Publish只消费APPROVED，PUBLISHED content不可变；REJECTED/历史Version的修订只能派生新DRAFT。所有这些仍是文档合同，`schedule-version.v1` Schema、DB、application/API/UI行为由P3-02+形成。

## TASK-P3-04 validated output consumer

`ValidatedSolutionToScheduleVersionService`现在只接受完整Snapshot/Problem/PlanningSolution/SolverReport/ValidationReport/ImportQualityReport/KPI bundle与显式`PlanningRun=COMPLETED`事实。进入事务前，它调用既有`build_kpi_v2`，由该公开P2边界重新执行formal Validator、SolverReport freeze、quality与KPI计算，并要求 supplied KPI逐字等于fresh结果；任何stale、mixed、tampered或非PASS输入均不创建版本。

通过后，pure domain builder复制assignments并把Problem的`HARD_LOCK/SOFT_LOCK`稳定映射为Schedule content的`HARD/SOFT`，形成同一content identity的immutable DRAFT与READY_FOR_REVIEW candidate。Application在一个caller-owned transaction中insert DRAFT、执行既有DRAFT→READY CAS并追加`SUBMIT_FOR_REVIEW` AuditEvent；same key/same request返回原READY/audit，不执行self-transition或增行，同key/different request冲突。PlanningSolution、P2 output bytes、Schema、Validator公式与其他state pair均未修改。

该slice只形成reviewable carrier：`decision/publication/superseded_by=null`，没有approve/reject/publish/export、manual edit、HTTP/UI或P4行为。READY_FOR_REVIEW仍不是approval、publishability或Production readiness。
