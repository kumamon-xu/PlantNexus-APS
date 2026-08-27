---
doc_id: ADR-0014
title: Freeze Window、OBJ-002 Stability 与 ChangeReport
status: accepted
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 36, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101]
last_reviewed: 2026-08-27
---

# ADR-0014 — Freeze Window、OBJ-002 Stability 与 ChangeReport

Status: accepted

Date: 2026-08-27

Decision owners: PlantNexus APS repository governance；TASK-P4-01由repository owner明确授权

Requirement/NFR/ENG: REQ-004、REQ-005、REQ-006、REQ-007、REQ-008、REQ-009；NFR-COR-001、NFR-DET-001、NFR-TRC-001、NFR-HUM-001；ENG-SOL-001、ENG-VAL-001、ENG-ERR-001、ENG-VER-001

Supersedes: none；落实ADR-0005、ADR-0006、ADR-0007与ADR-0013

## Context

P2只实现Delivery/OBJ-001，SOFT lock仍是metadata；P3 comparison只是两个immutable Version的read delta，不是Replan objective或ChangeReport。P4需要同时保护执行事实、HARD lock和freeze window，在Delivery不退化的候选中最小化计划扰动，并向计划员解释新旧计划变化。

如果不冻结精确语义，后继实现可能用浮点权重混合Delivery/Stability、把freeze当Hint、把新urgent operation算作“变化惩罚”而阻止接单、静默放松冲突lock，或生成不完整/不可复算的ChangeReport。Production freeze值与业务批准来源仍由OPEN-005阻塞；本ADR不猜默认时长、approval authority或SLA。

## Decision

### 1. Freeze必须来自显式版本化policy

每个ReplanRequest必须引用一个明确的freeze policy/version，并保存resolved freeze interval。确定性anchor为new PlanningSnapshot的`cutoff_at_utc`；若policy以正整数秒表达，则：

```text
freeze_start_utc = new_snapshot.cutoff_at_utc
freeze_end_utc   = freeze_start_utc + freeze_duration_seconds
```

区间采用half-open `[freeze_start_utc, freeze_end_utc)`。Policy、duration、resolved endpoints、source/authority和canonical fingerprint都进入Request/Problem/ChangeReport lineage。不得读取wall clock、environment默认、UI fallback或仓库中的Simulation样例填充Production值。Production缺少approved freeze policy时Replan在solve前拒绝；Simulation数值只能由P4-05/10在独立Task登记versioned SIM_ASSUMPTION。

### 2. Effective lock投影规则固定

以base PUBLISHED ScheduleVersion为比较基线。对仍为NOT_STARTED且base start位于freeze interval内的operation，确定性投影exact `(resource_id, start_utc, end_utc)` effective HARD lock；start恰等于`freeze_end_utc`不属于冻结区。base start早于cutoff但没有对应RUNNING/COMPLETED权威事实属于stale/inconsistent input，必须拒绝而不是猜测状态。

约束优先级和冲突处理固定为：

1. COMPLETED/RUNNING等权威执行事实；
2. 显式HARD_LOCK；
3. freeze-derived effective HARD lock；
4. SOFT_LOCK与非冻结旧计划稳定性成本；
5. Solver hint，仅影响搜索，不影响可行域、objective value或正确性。

前三层之间出现resource/time/duration冲突时在solve前fail closed。权威事实不能被lock覆盖，HARD/freeze也不能为urgent order、可行性或性能静默放松；结果可以明确INFEASIBLE或blocked，但不能产出违反事实/lock的candidate。

### 3. OBJ-002是Delivery之后的整数词典序向量

全局目标顺序保持ADR-0006：

```text
hard feasibility
→ OBJ-001 Delivery
→ OBJ-002 Stability
→ OBJ-003 Makespan
```

只有在OBJ-001达到同一已证明value/bound条件后才优化OBJ-002；只有Delivery和完整Stability向量都相等时才以Makespan tie-break。不得把三层折算为单个浮点/大M权重。

OBJ-002内部按以下非负整数向量再次词典序最小化：

```text
1. soft_lock_violation_count
2. changed_existing_operation_count
3. resource_changed_count
4. total_absolute_start_shift_seconds
```

`soft_lock_violation_count`只统计new Snapshot cutoff时仍active的显式SOFT lock，其目标tuple发生偏离即计1。`changed_existing_operation_count`针对base与candidate都存在且在new Snapshot仍active的operation；resource、start或end任一不同即计1。`resource_changed_count`是其中resource不同的数量；`total_absolute_start_shift_seconds`为共同operation start UTC差值绝对值之和。所有时间从权威UTC/seconds计算，不以tick差、float或展示时区代替。

新urgent operation在base中没有assignment，因此不产生movement penalty，只在ChangeReport标记ADDED；因COMPLETED权威事实退出future Problem的operation也不由Solver“奖励”或“惩罚”，只按fact reference报告。该规则防止OBJ-002阻止必要新需求或把已完成事实当作可选删除。

旧计划可以作为CP-SAT Hint，但相同Problem/Policy/Limits/base必须由上述objective和deterministic tie-break决定可审计结果；Hint命中与否不得改变score定义、Validator结果或ChangeReport算术。

### 4. Stability KPI采用可复算比较集合

ChangeReport和KPI必须同时输出：

```text
comparable_existing_operation_count
unchanged_existing_operation_count
changed_operation_count
resource_changed_count
start_shift_seconds
schedule_stability_ratio numerator/denominator
soft_lock_violation_count
```

ratio的exact语义为`unchanged_existing / comparable_existing`；分母为0时为`null/NOT_APPLICABLE_NO_COMPARABLE_OPERATION`，不得猜0或1。机器Schema的decimal编码/rounding由TASK-P4-02决定，但必须保留exact numerator/denominator。既有KPI v1/v2 bytes和无base时`NOT_APPLICABLE_NO_BASE_SCHEDULE`历史语义不改写。

### 5. ChangeReport是immutable、完整、可独立复算的结果证据

每份ChangeReport绑定base/new ScheduleVersion、base/new Snapshot和Problem hashes、ReplanRequest、trigger events/facts、freeze policy/effective locks、Planning Policy/Solve Limits、SolverReport、fresh ValidationReport、code/schema/projector/objective/report versions及canonical fingerprint。

Operation universe必须完整分类且恰好一次：

- `UNCHANGED`：共同active operation的resource/start/end相同；
- `CHANGED`：共同active operation至少一项assignment不同，并提供before/after与稳定性分量；
- `ADDED`：只在new Problem出现；
- `REMOVED_BY_FACT`：因有明确COMPLETED/authoritative fact而不再进入future Problem。

任何无fact依据的missing operation、重复分类、unknown entity、计数/总和不一致或before/after fingerprint漂移都使报告不完整并阻断new DRAFT应用。报告至少包含before/after Delivery tardiness、完整OBJ-002向量、Makespan、facts/explicit HARD/effective freeze lock preservation、SOFT lock deviation、Validator PASS和每项变化的reason/evidence references。

Reason只陈述可证明的直接证据，例如trigger event/fact、new demand、freeze/HARD preservation或solver stability trade-off；不能把相关性编造成业务因果。无法证明具体因果时必须使用显式`UNATTRIBUTED_SOLVER_CHANGE`类并保留objective/constraint evidence，不能省略或写自由文本猜测。具体enum由TASK-P4-02版本化。

### 6. Transaction、状态与rollback

ChangeReport在candidate通过fresh Validator后生成并独立复算。TASK-P4-08必须在同一result-application transaction中提交new DRAFT、ChangeReport、request result和audit；任一完整性/fingerprint/transaction错误都不得留下可见DRAFT。Report不是ScheduleVersion comparison的别名，也不推进READY/APPROVED/PUBLISHED状态。

失败或回滚绝不修改base PUBLISHED、facts、locks、旧Report或历史KPI。新的event/fact/policy需要新的Snapshot、Request、Run、DRAFT和ChangeReport；纠正通过superseding artifact完成。

## Alternatives considered

### Freeze只作为Solver Hint

拒绝。Hint不保证约束，无法满足Facts/Locks Preserved Gate。

### 用单一浮点加权总分混合Delivery、Stability和Makespan

拒绝。权重尺度会让低优先级目标覆盖Delivery，且float/Big-M难以跨环境重放。

### 将ADDED urgent operation计为changed operation

拒绝。它没有base assignment可比较，会产生阻止必要新需求的错误成本。

### 只输出聚合变化计数

拒绝。聚合值无法证明operation全集、事实/lock保持和lineage，也无法独立复算或审计原因。

### 冲突时自动缩短freeze或把HARD降为SOFT

拒绝。该行为篡改policy/authority；应明确失败并要求新policy/lock/event。

## Consequences

正面结果：freeze与HARD拥有真正约束语义；Stability在Delivery之后以整数向量可复算；urgent work不会被虚假movement成本压制；ChangeReport可证明全集、指标、facts/locks和lineage。

代价与限制：多阶段词典序求解增加solve次数和报告复杂度；report需要保存per-operation before/after；冲突会fail closed而非自动“修复”；Production freeze、priority/tardiness与SLA仍需外部authority。

Schema：TASK-P4-02为freeze policy/reference、objective stages和ChangeReport发布新版本，不改写KPI/Comparison旧文档。Migration：TASK-P4-03只持久化versioned refs/result；具体Report repository由后继卡实现。Dependency：none。State：existing pairs不变。Validator：P4-07必须独立检查facts/HARD/freeze、operation completeness与report算术，不信任Solver自报。Tests在本Task仍为PLANNED。Benchmark只保留P2 XS/S/M并新增development observation，不形成Production capacity/SLA。

## Rollback / Revisit gate

accepted ADR不得原地改写。consumer形成前以superseding ADR修正；形成Schema/solver/report后必须新version、migration/compatibility和Golden/Scenario replay。回滚P4 implementation时停用new Replan入口，保留base Version、Request/Run/Report/audit；未发布DRAFT可按既有状态治理处理，不能删除历史事实或Report。

以下证据触发revisit：业务批准不同freeze anchor/边界；SOFT lock需要分级而非count；Stability内部排序不符合授权policy；operation split/merge导致一对一比较不足；P5引入batch/alternative route/secondary resource；或Production KPI/rounding被正式批准。未出现这些证据前不得用代码默认替代本决定。
