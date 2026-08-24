---
doc_id: DOC-PLAN-003
title: V1 Constraint Catalog
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [21, 22, 25, 26, 27, 30, 31]
last_reviewed: 2026-08-21
---

# V1 Constraint Catalog

本目录是 V1 硬约束的规范索引。Solver 实现与 Validator 实现必须分别追踪这些 ID，但不得共享 CP-SAT 约束实现。

| ID | 规则 | Solver 表达 | Validator 核心检查 | P0 Test contract |
|---|---|---|---|---|
| C-001 | 必排完整性 | 每个未完成 Operation 恰有一个资源和 interval | 缺失、重复、未排均拒绝 | TEST-RULE-SHEET-001；TEST-VALIDATOR-MUTATION P0 fixture slice formed |
| C-002 | 工艺时间关系 | `succ.start >= pred.end + min_lag`；存在 max_lag 时同时约束上界 | 以 `(succ.start-pred.end)*tick_seconds` 精确检查 min/max 秒，不用 ceil 放宽 max | TEST-RULE-SHEET-001；TEST-MAX-LAG P0 negative slice formed |
| C-003 | 候选设备唯一选择 | `sum(presence[i,*]) == 1` | selected resource 属于候选且唯一 | TEST-RULE-SHEET-001；TEST-INF-NO-RESOURCE P0 wrong/multiple-selection slice formed |
| C-004 | 单机互斥 | Capacity=1 Resource 使用 NoOverlap | 同资源半开 interval 不重叠 | TEST-RULE-SHEET-001；TEST-VALIDATOR-MUTATION P0 negative slice formed |
| C-005 | 设备日历 | 不可用固定 interval 加入 NoOverlap | 非抢占任务不跨/不占不可用半开区间 | TEST-RULE-SHEET-001；TEST-CALENDAR P0 negative slice formed |
| C-006 | Release Gate | `start >= order_release_at` 且 `start >= material_ready_at` | 从 horizon/ticks 还原 candidate UTC，对两个 gate 独立检查 | TEST-RULE-SHEET-001；TEST-MATERIAL P0 negative slice formed |
| C-007 | Execution Facts | COMPLETED 不排；RUNNING 资源与未来剩余占用固定 | 历史、资源、remaining、future occupancy | TEST-RULE-SHEET-001；TEST-RUNNING P0 completed/running slice formed |
| C-008 | Lock | HARD resource/start/end 固定；SOFT 进入稳定性目标 | HARD 不移动；SOFT 不作为 hard PASS 条件 | TEST-RULE-SHEET-001；TEST-INF-LOCK P0 movement slice formed |
| C-009 | 跨车间衔接 | `succ.start >= pred.end + transport_lag` | 以 observed seconds 独立于 C-002 检查 transport lag | TEST-RULE-SHEET-001；TEST-CROSS-WORKSHOP P0 negative slice formed |
| C-010 | 工时一致性 | `end-start == selected.final_duration_ticks` | `ceil(final_duration_seconds/tick_seconds)` 可复算 | TEST-RULE-SHEET-001；TEST-VALIDATOR-MUTATION P0 negative slice formed |
| C-011 | Planning Horizon | NOT_STARTED `start>=horizon_start`、`end<=horizon_end` | 还原 UTC 后不允许截断或越界 | TEST-RULE-SHEET-001；TEST-INF-HORIZON P0 overflow slice formed |

## 共同规则

- max_lag 存在就必须实现，不能只在 Schema 存储。
- 非抢占任务不能跨 calendar unavailable interval。
- 每个候选设备使用自身 duration。
- HARD_LOCK 和 Execution Fact 不能通过 Hint 代替。
- Validator 报告至少包含 `constraint_id`、severity、entity IDs、observed、expected rule 和 message。

## Deferred/Unsupported constraints

| ID | 能力 registry key | V1 行为 |
|---|---|---|
| C-012 | SECONDARY_CAPACITY | `UNSUPPORTED_CAPABILITY` |
| C-013 | SEQUENCE_DEPENDENT_SETUP | `UNSUPPORTED_CAPABILITY` |
| C-014 | MATERIAL_COMPETITION | `UNSUPPORTED_CAPABILITY`；只支持 material_ready_at |
| C-015 | BATCH_PROCESSING | `UNSUPPORTED_CAPABILITY` |
| C-016 | SPLIT_MERGE | `UNSUPPORTED_CAPABILITY`；不猜 OPEN-008 lot policy |
| C-017 | BUFFER_CAPACITY | `UNSUPPORTED_CAPABILITY` |
| C-018 | PREEMPTIVE_OPERATION | `UNSUPPORTED_CAPABILITY`；V1 非抢占 |

## P0 验证规则表

[`constraint-rule-sheet.v1`](../../schemas/rules/constraint-rule-sheet.v1.yaml) 为 C-001～C-011 固定 input path、判定公式、positive/negative example、`VALIDATION_FAILED`/`SCHEDULE_VALIDATION_FAILED` violation shape、Test ID 与 PROD_OPEN；同时为 C-012～C-018 固定 capability key 与 explicit rejection。[`rule_sheet.py`](../../backend/app/planning/validation/rule_sheet.py) 只检查 11+7 ID、必需字段和跨 registry 一致性，不读取或评估 candidate schedule。

TASK-P0-03 的 `planning-problem.v1` 只为候选资源、min/max/transport lag、calendar unavailable interval、release/material gate、部分 RUNNING facts、horizon、duration 和 capability declaration 建立输入字段。COMPLETED execution facts、HARD/SOFT lock、cross-workshop edge identification 与 candidate assignment schema 仍需 P1/P2 合同扩展；规则表用 `contract_status` 明确这些 gap，不虚构字段已发布。OPEN-004/005/007/009/010 均未关闭。

最小 data precheck 和 rule-sheet completeness 都不是 ScheduleValidator，也不能作为任何 C-001～C-011 schedule PASS 证据。TASK-P0-07 已使用 Golden/illegal fixtures 建立 fixture-local mutation rejection；P2 才实现正式 PlanningProblem/candidate 输入下的完整独立 Validator。Constraint semantics 本次未改变，因此不触发 Solver benchmark，但 P2 首个 baseline 必须包含本 rule version。

TASK-P0-05 仅移除 rule completeness CLI 对全局 schema set `1.1.0` 的硬编码，仍要求 data dictionary 与 `app.SCHEMA_VERSION` 一致。C-001～C-018 YAML、formula、capability mapping、ValidationReport 和 evaluator 边界均未改变；CLI 在 additive `1.2.0` 下回归通过，不把 Scenario Schema 引入解释为 Constraint 或 Validator 实现。

## SIM-MINIMAL-001 positive coverage

TASK-P0-06 的 test-local direct calculations 使用 `constraint-rule-sheet.v1` ID 集但不读取 formula 决定结果：C-001/003 验证三个 assignment/candidate；C-002 验证 0 与 1800 秒 inclusive lag；C-004 验证同机 `[0,4)`/`[4,6)`；C-005/006 验证 maintenance/material exact boundary；C-009 验证 1800 >= 900 秒 transport；C-010/011 验证 duration/horizon。C-007/008 因无 execution fact/lock 明确 N/A。

该 positive Golden 形成 correctness baseline 和 TEST-GOLDEN-FJSP/CALENDAR/MATERIAL/CROSS-WORKSHOP/MAX-LAG 的 positive slice，不输出 violation 或实现 rule evaluator。TASK-P0-07 以独立 [`schedule_validator.py`](../../backend/app/planning/validation/schedule_validator.py) 和 [`SIM-MINIMAL-001-MUTATIONS@1.0.0`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/coverage-matrix.json) 形成所有 C-ID 的 negative fixture slice；duplicate case 按独立命题同时定位 C-001/C-003/C-004，其余 case 均隔离到单一 C-ID。C-001～C-011 语义、rule sheet/version、Schema 和 P2 Solver benchmark 均未改变。

## TASK-P1-06 input-quality review

Routing DAG、resource option/capability、duration/unit与calendar range检查发生在PlanningProblem和candidate schedule之前，输出ImportQualityReport/Error v3而非Constraint violation。`ROUTE_CYCLE`不等同C-002 candidate precedence violation，`MISSING_RESOURCE`不等同C-003 assignment violation，`MISSING_DURATION`/`INVALID_DURATION`不等同C-010 selected duration violation；它们阻止非法输入进入Expansion/Problem。

本Task没有修改C-001～C-018、constraint-rule-sheet.v1、P0 fixture evaluator或ValidationReport v2。新增四个P1 error code不触发Constraint/Solver benchmark；P2仍须在正式Problem/candidate上独立验证全部C-ID。

## TASK-P1-07 expansion/constraint separation

`order-expansion.v1`只把已通过input-quality Gate的Routing DAG逐lot复制为OperationInstance/edge，并复制candidate duration、release/material gate、transport/max lag、fact与lock引用。它不判断candidate schedule，不选择resource，不验证overlap/precedence/horizon，也不输出Constraint violation；因此未修改C-001～C-018、rule sheet、ValidationReport或独立ScheduleValidator。

请求SPLIT_MERGE仍按C-016 capability边界明确`UNSUPPORTED_CAPABILITY`，多个source-explicit lots不等同系统执行split/merge。P2必须在TASK-P1-09正式Problem/candidate上重新验证全部C-ID；Expansion PASS不能替代ScheduleValidator PASS。

## TASK-P1-09 Problem projection / Constraint separation

`planning-problem-builder.v1`首次把immutable Snapshot投影为正式solver-neutral Problem输入：C-001/003所需active operation与candidate、C-002/009的min/max/transport edge、C-005的horizon-intersecting calendar interval、C-006 release/material gate、C-007 RUNNING remainder、C-010 authoritative duration seconds与explicit tick、C-011 horizon config均被稳定保留。Builder只用ceiling tick检查单个operation不会被配置horizon静默截断，不选择resource、不评估全局可行性，也不产出任何Constraint PASS/violation。

COMPLETED从未来集合排除；若edge跨COMPLETED/active边界，v1无法保留historical end/lag，builder明确拒绝而不丢边。与horizon相交的HARD/SOFT lock同样因v1无字段而拒绝，故本Task没有声称C-008已具备正式Problem输入。C-001～C-018、`constraint-rule-sheet.v1`、P0 fixture evaluator和ScheduleValidator均未修改；P2仍须独立执行全部适用C-ID，Problem build成功不得写成schedule feasible或valid。

## TASK-P2-01 v2 Constraint input boundary

Problem v2补齐C-003的完整primary Resource/capacity=1事实、C-005的resource/calendar引用、C-008的active HARD/SOFT lock字段以及C-002/009跨COMPLETED→active边界所需historical completion end/source/lag。C-001/006/007/010/011既有active operation、gates、RUNNING、duration/tick/horizon语义继续保留；due/priority为OBJ-001输入。

这只把input contract标记为formed。C-008 HARD enforcement、所有C-ID的CP-SAT约束与formal independent ScheduleValidator仍未实现；SOFT_LOCK属于未授权OBJ-002而不会被P2-01执行。C-012～C-018继续unsupported，Problem verify PASS不等于candidate schedule feasible/valid。

## TASK-P2-03 no-business-model review

CP-SAT namespace仅构造零约束empty model和一个故意清空domain的invalid engineering model；没有C-001～C-011 builder、interval、NoOverlap、precedence、calendar、material、running、lock或transport表达。`OPTIMAL` smoke只描述空native model，明确不代表任何PlanningProblem可行。C-001～C-011实现与formal Validator仍保持PLANNED，C-012～C-018继续unsupported。

## TASK-P2-04 independent evaluation status

C-001～C-011现在均有正式PlanningProblem v2/PlanningSolution evaluator的positive、exact mutation和property证据；rule IDs、formula、severity、expected/message与`constraint-rule-sheet.v1`保持不变。C-002包含inclusive min/max lag并支持historical predecessor end，C-009使用selected/historical resource的workshop独立判断transport，C-004/C-005使用half-open interval，C-008只hard-enforce HARD_LOCK。

RUNNING仍由C-007固定resource、horizon-start和remaining occupancy；为避免把已执行历史重新排程，C-010对RUNNING复算`ceil(remaining_seconds/tick_seconds)`，NOT_STARTED复算selected option `final_duration_seconds`。这是C-007权威执行事实对C-010一般工时的既有特化，不改变rule-sheet或Problem/Solution Schema。Formal PASS不表示CP-SAT已经建模任何C-ID；P2-05～07的Backend constraints与P2-09 Solver/Validator integration继续`PLANNED`，C-012～C-018继续unsupported。

## TASK-P2-05 implemented core constraint slice

CP-SAT现实现C-001完整且唯一assignment、C-003合法candidate resource、C-004同resource half-open unary NoOverlap、C-010 selected candidate seconds到ceiling tick duration、C-011完整horizon containment。Tight JSSP证明back-to-back区间合法，FJSP证明不同resource option使用各自duration；independent formal Validator对正例及C-001/C-010 mutation复验。

C-002与C-005～009仍未进入Solver。任何非空precedence/transport、calendar、late release/material、RUNNING或lock事实必须在model build前拒绝，不能被当作vacuous或忽略；C-012～018继续unsupported。Rule sheet、公式与severity均未修改。

## TASK-P2-06 implemented temporal constraint slice

CP-SAT现新增C-002 precedence inclusive min/max lag、C-005 resource calendar half-open exclusion、C-006 release/material-ready lower bounds与C-009 selected-resource cross-workshop transport。Min与transport分别向上取tick且独立施加，max向下取tick；calendar用grid-equivalent fixed intervals，historical completed predecessor由absolute end anchor约束active successor。

这些约束与既有C-001/003/004/010/011共同形成当前bounded model，并由formal Validator独立复验。C-007 RUNNING与C-008 HARD lock仍fail closed并由P2-07承接；C-012～018继续unsupported，OBJ-001仍未进入搜索。Rule sheet、C-ID公式、severity和Problem/Solution Schema均未修改。

## TASK-P2-07 execution fact and lock model

CP-SAT现实现C-007/C-008：COMPLETED不产生future assignment但historical anchor继续参与lag；RUNNING固定assigned resource、`start_tick=0`与`end_tick=ceil(remaining_seconds/tick_seconds)`；HARD lock exact固定resource/start/end。SOFT lock只保留metadata reference，不属于hard validation pass condition，也不形成hint/objective。

Fact/lock self-conflict或grid不可表示性在model build前MODEL_INVALID；grid-aligned lock与calendar、capacity-1 resource或C-011 horizon冲突由solver认证INFEASIBLE。当前bounded model至此覆盖C-001～C-011并继续由formal Validator独立复验；OBJ-001搜索仍未实现，C-012～018继续unsupported。Rule sheet、C-ID公式、severity、Problem/Solution Schema与Validator源码均未修改。

## TASK-P2-08 hard-domain review

OBJ-001只在P2-05～07已形成的完整C-001～C-011可行域上增加目标，不修改任何C-ID公式、severity、rule sheet、core/temporal/fact-lock builder或formal Validator。每个优化candidate仍由Validator独立重算全部C-ID；Validator FAIL不能通过更优objective抵消。C-012～C-018继续explicit unsupported，OBJ-002/003不是硬约束或本Task目标。

## TASK-P2-14 Exit audit

独立审计以两次七场景replay、11个positive C-ID、11个formula-free exact negative mutation和476项全仓回归确认C-001～C-011完整硬域为PASS。Rule sheet、Backend builders与formal Validator均零差异；`UNSUPPORTED_CAPABILITY`继续覆盖C-012～018。Audit READY不改变任何C-ID公式、severity、Production authority或后续能力状态。
