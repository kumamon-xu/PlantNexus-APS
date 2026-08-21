---
doc_id: DOC-DOM-005
title: KPI 合同
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [36, 45, 53, 55, 93]
last_reviewed: 2026-08-21
---

# KPI 合同

## Delivery

`on_time_order_ratio`、`total_tardiness_seconds`、`priority_weighted_tardiness_seconds`、`late_order_count`及逐Demand completion/due/tardiness明细。

## Planning

`makespan_seconds`、`scheduled_operation_count`、`unscheduled_operation_count`。

进入 READY_FOR_REVIEW 的计划原则上不得存在未排的 V1 未完成 Operation；若产品状态允许部分结果，必须由后续 ADR 明确，当前不得假设支持。

## Resource

`available_seconds`、`planned_busy_seconds`、`utilization`。

```text
utilization = planned_busy_seconds / available_calendar_time
```

不得以完整自然时间为分母。分母为零时的 API 表示需在 KPI Schema 中明确，不能默认为 0% 或 100%。

## Stability

`changed_operation_count`、`resource_changed_count`、`start_shift_seconds`、`schedule_stability_ratio`。

## Solver

`model_build_time`、`first_feasible_time`、`solve_time`、`objective`、`best_bound`、`relative_gap`、`variables`、`constraints`、`optional_intervals`、`memory_peak`。

所有 duration/time KPI 使用明确单位，报告必须记录 tick、时区、问题 hash、Solver 版本和计算环境。具体业务权重与迟交语义受 OPEN-006 约束。

## P0 Schema skeleton

[`kpi.schema.json`](../../schemas/json/kpi.schema.json) 固定 `kpi_version=kpi.v1`、`problem_hash`、`tick_seconds` 和 Delivery/Planning/Resource/Stability/Solver 五组字段；秒数与计数为非负数，ratio 为 `[0,1]`。`utilization` 允许 `null`，避免在 available time 为零时猜成 0% 或 100%；何时必须为 null 及完整计算校验仍由后续 KPI implementation/contract test 完成。

当前没有 KPI calculator、Solver metrics 或 Benchmark 结果，Schema PASS 不代表这些数值已产生。

## P0 Golden KPI boundary

[`SIM-MINIMAL-001 expected-kpis.json`](../../fixtures/deterministic/SIM-MINIMAL-001/expected-kpis.json) 使用 fixture-local `golden-kpi.v1`，只记录可从人工 Schedule 复算的 Delivery、Planning 和 Resource 子集；它没有 `problem_hash`、Stability 或 Solver metrics，因此故意不冒充 `kpi.v1`。Golden test 从 order/schedule/calendar 重新计算 completion/due/tardiness、`max(end_tick)*tick_seconds` makespan、busy/available/utilization，不信任 expected JSON 自证。

该 fixture 的 synthetic weight 2 与 makespan origin 定义只属于 SIM-ASSUMPTION-009/计算说明，不改变 OBJ/KPI repository-wide 语义或关闭 OPEN-006。正式 KPI calculator、Problem hash、Solver/Stability metrics 和 Benchmark report 仍为后续 Task。

## TASK-P2-02 SolverReport metric carrier

SolverReport v1现在固定model build、first feasible、solve、validation、total seconds，variables/constraints/optional intervals、memory MB以及OBJ-001 objective/bound/gap的字段与非负/status条件；PlanningSolution同时保留stage级预算、solve time和stop reason。该工作只建立NFR-OBS-001所需的carrier contract，不计算KPI，也没有真实model或performance sample。

发布样例明确`CONTRACT_SAMPLE`、UNKNOWN、零model metrics/timing和not-installed solver。它不能作为Benchmark baseline、capacity、SLA或Production值；P2-11才负责真实SolverReport/KPI计算与一致性，P2-12才形成XS/S/M证据。OPEN-006/012继续OPEN。

## TASK-P2-03 engineering timing boundary

Foundation report可记录empty/model-invalid native wall time与变量/约束计数，仅用于证明adapter可调用和JSON serialization；这些值受local平台及空模型影响，不是Planning KPI、solver quality、first-feasible、validation timing、Benchmark baseline、capacity或SLA。没有candidate，因此不计算weighted tardiness、makespan或任何OBJ/KPI；OPEN-006/012保持OPEN。

## TASK-P2-05 diagnostic and KPI boundary

Core report现记录真实model build、external solve、native wall、first feasible、Python traced peak memory及variables/constraints/optional intervals；这些只用于correctness可观测性，尚无XS/S/M profile、warm-up、分位数或回归阈值，因此不是性能KPI或SLA。

Candidate weighted tardiness按交付需求最大completion在solve后测量，用于满足既有Solution stage合同；CP-SAT没有`Minimize/Maximize`，该值不能视为OBJ-001 execution、质量最优性或Benchmark基线。OPEN-006/012及Production KPI口径保持未关闭。

## TASK-P2-06 temporal telemetry boundary

Temporal report新增constraint、calendar fixed interval、gate、conditional transport等model delta及build/solve/memory观测值，只用于证明C-002/005/006/009已实际进入模型。它没有warm-up、profile、percentile、threshold或Reference comparison，不是KPI baseline、capacity或SLA。

Weighted tardiness仍仅为post-solve合同值，CP-SAT模型不含objective。OPEN-006/012及全部Production KPI口径保持不变。

## TASK-P2-07 KPI boundary

Fact/lock report新增RUNNING/HARD/SOFT数量、fixed operation interval、resource/start/end equality、constraint delta及build/solve/first-feasible/memory telemetry，只证明C-007/C-008实际进入模型。它没有warm-up、profile、percentile、Reference comparison、stability cost或threshold，不是KPI/Benchmark baseline、capacity或SLA。

Weighted tardiness仍只在candidate后测量，CP-SAT模型不含objective；SOFT lock movement不计入OBJ-002。OPEN-005/006/012及全部Production KPI口径保持不变。

## TASK-P2-08 Solver metric evidence

Global Strategy的真实SolverReport现记录OBJ-001 weighted tardiness seconds、certified best bound/relative gap、model build、first feasible、solve、independent validation、total、variables/constraints/optional intervals与Python traced peak MB，并绑定tick/Problem/Policy/Limits/Solver/commit。Objective由neutral assignments独立复算并必须等于native objective carrier。

这些字段只证明tiny correctness/observability；没有KPI calculator、makespan/Resource/Stability计算、warm-up、percentile、hardware profile、Reference comparison或XS/S/M baseline。OPEN-006/012继续OPEN，不形成Production KPI、capacity或SLA。

## TASK-P2-10 Reference metric slice

`reference-scheduler-report.v1`对每个Validator-PASS完整candidate记录`weighted_tardiness_seconds`、`makespan_seconds`、`runtime_seconds`、scheduled/unscheduled counts和Problem hash。Weighted tardiness逐Demand取active operation最大completion tick，保留非grid due的exact秒偏移并乘Problem显式priority；makespan从horizon origin取最大end tick，成功结果unscheduled恒为0。失败结果不暴露partial candidate，quality/makespan为null且scheduled为0。

这些字段是同Problem/Validator口径的Reference correctness measurement，不是完整`kpi.v1` calculator、SolverReport、Benchmark统计、hardware-normalized baseline、capacity或SLA。Runtime只是一轮本地/CI evidence timing；P2-11仍负责正式KPI/SolverReport一致性，P2-12负责XS/S/M比较，OPEN-006/012保持OPEN。

## TASK-P2-11 KPI v2

[`kpi.v2.schema.json`](../../schemas/json/kpi.v2.schema.json)与`app.planning.reporting.build_kpi_v2`形成validated synthetic run的immutable calculator。输入必须是同一Snapshot v2、Problem v2、`SOLVER_RUN` PlanningSolution/SolverReport、fresh exact PASS ValidationReport v2与PASS ImportQualityReport v1；任一hash/version/report/run漂移均拒绝。

Delivery逐Demand以其active operations的最大end tick为completion，按Problem的horizon origin/tick换算UTC与秒级tardiness，priority-weighted总和必须等于OBJ-001 stage carrier。Planning makespan为最大end tick乘tick seconds，scheduled count必须覆盖全部Problem operation，unscheduled为零。Resource available seconds按horizon减去合并后的不可用calendar half-open区间，busy seconds来自assignment interval；分母为零时utilization严格为`null`，否则按12位小数稳定舍入。

当前没有base ScheduleVersion，Stability必须为`NOT_APPLICABLE_NO_BASE_SCHEDULE`且四个变化指标均为`null`；不得伪造ChangeReport或把zero当稳定性。Solver部分复制已校验的objective/bound/gap、timing/model/memory carrier，不把tiny single-run值解释为Benchmark或SLA。KPI ID与fingerprint绑定canonical内容，输入对象不被修改。OPEN-005/006/012仍OPEN，P2-12负责XS/S/M。
