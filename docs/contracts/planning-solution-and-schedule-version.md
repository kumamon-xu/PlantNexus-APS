---
doc_id: DOC-CONTRACT-005
title: PlanningSolution 与 ScheduleVersion 合同
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [29, 30, 32, 33, 67, 78]
last_reviewed: 2026-08-28
---

# PlanningSolution 与 ScheduleVersion 合同

## TASK-P4-07 SolverReport v2 execution evidence

全局重排现在输出Schema-valid `solver-report.v2`：candidate沿用`planning-solution.v1` assignment形状并携带content fingerprint，三个stage保存诚实status/value/bound/gap/budget/stop，Stability保存四元整数向量，provenance绑定exact code、Policy/Limits及冻结合同版本。OPTIMAL/FEASIBLE才可携带candidate；UNKNOWN、INFEASIBLE、MODEL_INVALID或FAILED不泄漏partial success。

该输出仍是无持久化Solver evidence，不创建ScheduleVersion、不推进PlanningRun状态，也不等于new DRAFT或最终ChangeReport；这些原子应用责任继续属于TASK-P4-08。

## TASK-P4-06 assignment comparison consumer

ChangeReport builder消费既有`planning-solution.v1` operationAssignment形状和base PUBLISHED/new DRAFT ScheduleVersion exact references；它从UTC whole-second resource/start/end tuple计算delta，同时保存完整base/new assignment、lock/fact metadata、freeze、Request/Run、Policy/Limits、Solver/Validator及KPI lineage。Report ID/fingerprint由canonical content派生，`generated_at_utc`不参与内容identity，same inputs可byte-exact replay。

本Task不创建或持久化new DRAFT，不改变PlanningSolution/ScheduleVersion Schema、content fingerprint、state pair、review/approval/publication规则，也不把report当成fresh Validator PASS。P4-08仍须在stale/current/checkpoint复核后原子提交Version、report、request result与audit。

## TASK-P4-02 P4 result carriers

`solver-report.v2`新增三阶段objective evidence与诚实native-status→product-outcome映射；UNKNOWN绝不写成INFEASIBLE，非candidate状态不得泄漏partial success。`schedule-version.v2`绑定ReplanRequest、base/new Snapshot/Problem、event/fact checkpoint、PlanningRun candidate、fresh Validation/KPI/SolverReport和complete ChangeReport lineage，但沿用P3 ScheduleVersion状态集合与allowed pairs。Synthetic sample保持DRAFT且不自动READY/APPROVED/PUBLISHED；实际求解和new DRAFT transaction仍属于P4-07/08。

## TASK-P4-01 lineage decision

ADR-0013/0014固定P4-08只能把fresh-validated replan result以copy-on-write方式原子应用为新的DRAFT ScheduleVersion，并保留base PUBLISHED ID/content fingerprint、base/new Snapshot/Problem、ordered event/facts、ReplanRequest/PlanningRun、freeze/effective locks、Policy/Limits、Solver/Validator及ChangeReport fingerprint。Result application前必须重读current/base/checkpoint；stale或任何mismatch无Version副作用。

New DRAFT与complete ChangeReport、request result和audit在同一transaction提交；PUBLISHED不改，也不自动READY/APPROVED/PUBLISHED/export。具体carrier变化只能由TASK-P4-02版本化，persistence只能由TASK-P4-03/08实现。本Task没有修改既有Solution/Version Schema、state pair或publication authority。

## TASK-P3-17 audit conclusion

validated PlanningSolution→immutable ScheduleVersion DRAFT→READY_FOR_REVIEW→APPROVED/REJECTED→PUBLISHED/SUPERSEDED链及copy-on-write command、fresh Validator、lineage/fingerprint与状态不可变性均独立PASS。没有新增state pair、原地修改PUBLISHED或P4 replan语义。

## TASK-P3-14 vertical replay

Gate两次从既有validated P2 solution重放P3 lifecycle，核对immutable lineage、fresh Validator、read/command/decision/publication/export语义及raw report。它明确拒绝DRAFT/REJECTED publish与PUBLISHED mutation，并要求两轮stable semantic projection一致；不新增ScheduleVersion字段、状态pair、Schema或迁移，也不允许Gate修正任何业务差异。

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

## TASK-P3-05 immutable read consumer

Read service只从repository取得权威ScheduleVersion，并用request中的`state/content_fingerprint` precondition拒绝stale读取；随后把Version lineage逐项与Snapshot、Problem、PlanningSolution、ValidationReport、KPI、SolverReport及code commit重绑。Orders/Gantt/Resource Load等投影只消费已验证assignments，Locks只消费Version content，任何不一致均拒绝而不修补source或写回Version。

Version Comparison产生`schedule-version-comparison.v1`只读DTO：operation delta、六项KPI delta、summary和canonical fingerprint均可重放；它不创建parent/new DRAFT、不执行transition、不写decision/publication，也不包含ChangeReport、Replan或OBJ-002。

## TASK-P3-06 manual command derivation

人工命令不创建或冒充新的Solver run。新ScheduleVersion保留source的PlanningRun/Snapshot/Problem/PlanningSolution/KPI/SolverReport provenance，替换为对copy-on-write assignments执行fresh formal Validator所得的ValidationReport reference，并以`source_kind=MANUAL_EDIT|LOCK_CHANGE`和parent Version明确表达派生边界。Schedule content是新Version的权威计划内容；origin PlanningSolution仍是求解来源而不是人工修改后的等同document。

应用不会CAS更新content command的source，也不改变current publication；每个成功Move/Assign/Set/Remove Lock insert一个revision递增、identity独立的DRAFT并append command audit。该DRAFT只有经独立`SUBMIT_FOR_REVIEW`、第二次fresh Validator且report fingerprint与lineage一致，才以CAS复用既有`DRAFT→READY_FOR_REVIEW` pair；ID/content/fingerprint保持不变并原子追加submit audit。失败candidate完全不持久化。P3-06没有approve/reject/publish/export。P3-05基于原始PlanningSolution/KPI的严格read bundle不会被静默伪造成已重算manual KPI；后续API/UI若需要manual Version的完整KPI projection，必须消费明确的Version content/derived read contract，不得把旧KPI当新KPI。

## TASK-P3-07 immutable decision boundary

Approval/Reject不创建新PlanningSolution、ValidationReport、KPI或ScheduleVersion identity，也不重跑Solver/Validator。服务只在READY carrier及其existing validation/lineage通过冻结carrier precheck后，保持revision/content/content fingerprint/parent/source kind/validation/created facts逐字不变，新增Schema已允许的decision evidence并改变state/allowed actions：APPROVED为`view,publish`，REJECTED为`view,edit,lock`。REJECTED修订仍只能由后续copy-on-write command派生新DRAFT，不能回滚原行。

Decision AuditEvent复制既有完整lineage并绑定READY source与同ID/content terminal reference；授权拒绝event没有resource lineage/reference，避免通过not-found泄漏。该slice不实现APPROVED→PUBLISHED、current/supersession、ExportJob、HTTP/UI、P4或Production side effect。

## TASK-P3-08 immutable publication boundary

Publication不创建新PlanningSolution、ValidationReport、KPI或ScheduleVersion identity，也不调用Solver/Validator。新current candidate只把同一APPROVED carrier改为PUBLISHED并增加冻结publication evidence/`view,export` actions；如已有current，则旧PUBLISHED只改为SUPERSEDED、写入指向新PUBLISHED reference的`superseded_by`并收窄为`view`。两者的revision、content/content fingerprint、decision、parent/source kind、validation、lineage和created facts逐字不变。

新publish、旧supersede、PublicationResult、current reference CAS与success AuditEvent必须同事务，任一失败全部回滚。历史exact replay从append-only audit重建原logical result，即使新Version后来也被supersede也不修改历史。DRAFT/READY/REJECTED、double publish、stale current一律拒绝；ExportJob、文件包、HTTP/UI、external/Production side effect未形成。

P3-09只接受当前state=`PUBLISHED`且content fingerprint同时匹配ExportRequest、PublicationResult与ExportJob的Version。Standard package再次校验P2 PlanningSolution assignments和lineage fingerprint；Job重试/失败/取消绝不修改ScheduleVersion content、publication或current reference。SUPERSEDED不是新export source。
