---
doc_id: DOC-PLAN-005
title: 独立 ScheduleValidator 合同
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [30, 31, 50, 75, 86, 87]
last_reviewed: 2026-08-28
---

# 独立 ScheduleValidator 合同

## TASK-P4-07 fresh candidate validator

`replan-candidate-validation.v1`每轮从candidate、Problem、base assignments和effective-lock projection重新执行formal C-001～C-011 Validator，并独立重算active universe、running/explicit/freeze HARD tuple与metadata、completion facts、Delivery、四元Stability、Makespan及UNCHANGED/CHANGED/ADDED/REMOVED_BY_FACT分类。它不导入CP-SAT、backend或reporting calculator，不信任native solver status；任何fingerprint、universe、lock/fact、formal feasibility或objective mismatch均返回FAIL或结构化input rejection，candidate不得进入下一轮。

本Validator只提供candidate acceptance和ChangeReport算术/全集precheck；它不构造最终ChangeReport、不写new DRAFT或审批状态。

## TASK-P4-06 independent ChangeReport precheck

新增`change_report_precheck.py`直接从base/new assignments、active universe、SOFT locks、completion facts、reason inputs及before/after KPI重算完整report projection，不导入ChangeReport builder、stability calculator、CP-SAT Backend、formal ScheduleValidator、persistence、API或Simulator。它稳定返回PASS/FAIL、hard violations、四元objective vector与KPI comparison，并拒绝分类、delta、fact evidence、KPI reference、universe或identity篡改。

该precheck只证明ChangeReport completeness/consistency，不重算candidate对Problem的C-001～C-011可行性，不能替代TASK-P4-07 fresh formal Validator。既有formal Validator源码/hash/C-ID/error mapping和测试断言保持冻结。

## TASK-P4-05 independent freeze precheck

新增`freeze_window_precheck.py`从Snapshot、Problem、base Version和policy独立重算完整projection与fingerprint，不导入projector、CP-SAT Backend或formal ScheduleValidator，并以C-007/C-008及local freeze check IDs报告mutation。它不是candidate Schedule Validator，不能替代P4-07对Solver产物重算C-001～C-011；既有formal Validator源码/规则/hash保持冻结。

## TASK-P4-02 validation carrier

ScheduleVersion v2、SolverReport v2与ChangeReport v1现携带fresh ValidationReport exact reference和complete lineage，但TASK-P4-02不运行或修改Validator、C-001～C-011、mutation suite或PASS含义。P3 i18n evidence兼容修正仍冻结P3 API/Schema/registry exact paths；它不允许Frontend或P4 carrier绕过future P4-07 fresh independent validation。

## TASK-P4-01 accepted validation extension

ADR-0013/0014已固定TASK-P4-07的独立验证责任：直接从base/new Problem、facts、explicit HARD、freeze-derived effective HARD、candidate和ChangeReport重算约束与完整性；不信任Solver自报、Hint、report聚合值或application状态。必须验证operation universe恰好一次、OBJ-002整数分量/KPI、before/after lineage和new DRAFT eligibility；P4-08只能接受fresh PASS。

事实/HARD/freeze冲突、missing/duplicate operation、metric mismatch、stale base、unknown reason/reference或report fingerprint漂移都无Version副作用。SOFT lock偏离是objective/report数值而非hard constraint；UNKNOWN仍不等于INFEASIBLE。TASK-P4-14/15重放positive/negative/mutation证据。当前Validator代码、C-ID、error mapping与测试断言不变。

## TASK-P3-17 audit conclusion

formal Validator独立性、C-001～C-011 positive/negative、每个P3 command新DRAFT与submit前fresh validation、solver status不受信任、PUBLISHED immutability及Validator-fail rejection均经P2/P3 Gate独立PASS。Audit没有修改公式、C-ID或测试断言。

## TASK-P3-16 localization non-authority boundary

Validator的C-001～C-011、PASS/FAIL、product code、report bytes与计算公式继续是英文机器合同；TASK-P3-16已依据`official-zh-cn-terminology.v1`实现双语label/说明并保留raw C-ID、code、details与correlation。UI不根据中文文案重新判断可行性或把unknown映射为PASS/FAIL。Coverage/zero-wire-drift tests已由exact implementation provider复验；Validator、断言、fixture和expected零变化，最终由TASK-P3-17独立复验。

## TASK-P3-14 Validator Gate

两次fresh replay分别要求validated P2 solution建立reviewable DRAFT、command-derived新DRAFT再次通过正式Validator，且Approval不能覆盖失败。Gate只读取既有Validator报告并进行语义交叉检查，不导入Solver内部逻辑、不改C-001～C-011、mutation set、fixture或expected；任何失败形成blocking gap而不是在Gate内修复。

## TASK-P3-13 UI non-authority review

Browser只构造Move/Assign/Lock/Submit carrier和显示server error/result；它不导入Validator、不执行C-001～C-011、不计算可行性、目标或KPI。DRAFT command的候选与fresh ValidationReport、SUBMIT second-fresh gate仍完全由P3-06 application service负责；UI成功后只跟随authoritative Version。

Client-side时间量化和表单检查只是安全/可用性precheck，不能替代formal Validator。422 validation failure保持可见且不生成new Version；PUBLISHED无mutation入口。Validator代码、rule metadata、tests、Problem/Solver与P2 baselines在本Task零差异。

## 独立性

Validator 必须：

- 不导入 CpSatBackend；
- 不复用 CP-SAT constraint builder；
- 不信任 Solver status；
- 使用 PlanningProblem、candidate schedule 和独立规则判定；
- 检查 C-001～C-011。

可以共享稳定领域类型、时间换算和 Schema parser，但任何会让 Solver 与 Validator 产生同源逻辑缺陷的共享均禁止。

## 输出

```text
validation_passed
hard_violation_count
violations[]:
  constraint_id
  severity
  entity_ids
  observed_value
  expected_rule
  message
```

进入 READY_FOR_REVIEW 必须 `validation_passed=true` 且 `hard_violation_count=0`。

P0 当前机器输出合同为 [`validation-report.v2`](../../schemas/json/validation-report.v2.schema.json)：状态字段使用 `PASS/FAIL`，`hard_violation_count` 为非负整数，violation 只接受 C-001～C-011、`severity=HARD`、非空 entity IDs、observed value、expected rule 和 message。PASS 必须 count=0 且无 violations；FAIL 必须至少一个 hard violation。Emitter/consumer 还必须保证 count 与实际 hard violations 一致，不能依赖 JSON Schema 表达跨数组计数等式。

TASK-P0-07 同时固定 FAIL 到 [`error.v2`](../../schemas/json/error.v2.schema.json) 的映射：`VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED`，每个 detail 保留 constraint/entity/observed/expected/source；PASS 返回无 Error。该映射不是 HTTP contract。

## Mutation Set

至少人工构造并拒绝：machine overlap、wrong resource、wrong duration、wrong precedence、calendar overlap、lock movement、material early start、cross-workshop lag violation、missing operation、duplicate operation。P0 固定资产为 [`SIM-MINIMAL-001-MUTATIONS@1.0.0`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/calculation-note.md)：13 个声明式 case 还覆盖 completed/running facts 与 horizon overflow，C-001～C-011 均有负例。

## 验证顺序建议

先检查结构完整性与引用，再检查 duration/time domain，然后按 Operation/Edge/Resource/Lock/Execution 分类检查。验证结果应尽可能收集多个独立违反，而不是遇到第一条即只返回通用错误。

## 变更门

新增 Constraint 时必须同时更新 Validator 合同、正/反 Fixture、Mutation test、Property test 和 Benchmark 影响，不允许“Solver 先支持、Validator 后补”。

## P0-04 contract boundary

TASK-P0-04 形成 [`constraint-rule-sheet.v1`](../../schemas/rules/constraint-rule-sheet.v1.yaml) 和 completeness CLI。它只检查 C-001～C-018 metadata、code/category/capability/state registry 一致性，并显式扫描 validation contract package 不导入 backend/OR-Tools。它没有 `validate_schedule`、不读取 candidate schedule，也不构成 ADR-0005 的完整 Validator implementation。

TEST-RULE-SHEET-001/TEST-ERROR-MAPPING-001/TEST-CAPABILITY-001/TEST-STATE-TRANSITION-001 是 P0 contract evidence；它们本身不是 TEST-VALIDATOR-MUTATION。

TASK-P0-05 的 rule-sheet 代码变更只允许 additive schema set `1.2.0`，不修改任何 rule、violation、import scan 或候选 schedule 行为；P0-04 tests 全量回归。Scenario expected behavior/manifest 不是 Validator output，empty Import package 不能作为 C-001～C-011 PASS。

## P0-06 positive Golden boundary

`SIM-MINIMAL-001@1.0.0` 提供人工 schedule 与 fixture-local `golden-validation.v1` expected checks；[`test_sim_minimal_001.py`](../../backend/tests/golden/test_sim_minimal_001.py) 从 Import/Schedule 直接复算所有 applicable C-ID，并确认 hard violation count 期望为 0。replay loader 只检查 artifact/provenance/hash，明确不评估 C-ID，且两者均不导入 Planning backend/OR-Tools。

这证明一个已知正例可独立手算；TASK-P0-07 保持原目录只读，并把该正例作为 evaluator 的 PASS 输入。它仍不是正式 PlanningProblem/candidate schema 或 Solver integration。

## P0-07 fixture-local evaluator

[`schedule_validator.py`](../../backend/app/planning/validation/schedule_validator.py) 直接消费 `sim-minimal-records.v1` 与 `golden-schedule.v1`，从 Import facts 和 candidate assignments 复算 C-001～C-011。它只共享稳定 UTC/tick/domain output types，不导入 planning backend、OR-Tools 或 constraint builder；不读取 Rule Sheet formula、mutation suite 或 expected outcome。Rule Sheet YAML 只在测试/CLI 中交叉核对 violation metadata。

[`mutation_check.py`](../../backend/app/planning/validation/mutation_check.py) 以无公式的声明式操作在内存副本上构造 mutation，验证：positive Golden PASS、13 个 negative case FAIL、15 个 hard violations 的 exact report/error、两份 v2 Schema、deterministic replay、Rule Sheet metadata、全部 C-ID 与 required mutation coverage。生成的 `validator-mutation-report.v1` 为 ignored build evidence。

这是 ADR-0005 的 P0 correctness slice，但明确不是 P2 production/performance completion：fixture-local vocabulary 尚未替换为正式 PlanningProblem/candidate contract，未做 Solver comparison、规模/耗时/内存 Benchmark、API/persistence 或 READY_FOR_REVIEW 状态集成。TEST-PROPERTY 和 P2 全链路 Validator 仍 `PLANNED`。

## TASK-P1-06 boundary review

`app.data_validation`是Import输入质量evaluator，不消费PlanningProblem或candidate assignment，也不输出`validation-report.v2`/C-ID。它检查route图本身、canonical references、resource eligibility、unit/duration/time/fact/lock输入自洽；P0 `planning/validation/schedule_validator.py`仍只消费fixture-local schedule并检查C-001～C-011，两者没有import或公式共享。

因此TEST-DATA-QUALITY-001的route/resource/unit/duration负例不能计入TEST-VALIDATOR-MUTATION或READY_FOR_REVIEW Gate。Task的source scan确认Data Validation不导入Planning/backend/OR-Tools/ScheduleValidator；P2 production Validator、Property和Benchmark仍`PLANNED`。

## TASK-P2-04 formal Problem/Solution validator

[`problem_schedule_validator.py`](../../backend/app/planning/validation/problem_schedule_validator.py) 是正式、无状态的 `PlanningProblem v2 + candidate PlanningSolution → validation-report.v2` evaluator。入口 `ProblemScheduleValidator.validate` 与 `validate_problem_schedule` 先验证权威 Problem v2 的shape/reference/hash，再独立materialize candidate assignments；candidate的Problem reference不一致、missing/duplicate/unknown operation或非法assignment字段均以稳定C-ID failure返回。权威Problem本身非法则在规则判定前以`ProblemScheduleValidationInputError`拒绝，避免把坏输入伪装成schedule infeasible。

判定顺序为candidate/reference materialization、C-001 completeness、C-002 lag、C-003 resource、C-004 capacity-1 overlap、C-005 calendar、C-006 release/material、C-007 completed/running、C-008 HARD lock、C-009 cross-workshop transport、C-010 duration和C-011 horizon/UTC projection；violations最终按C-ID/entity/observed canonical JSON排序。RUNNING的未来assignment从horizon start占用`ceil(remaining_seconds/tick_seconds)`，因此C-007与C-010对RUNNING均使用权威remainder；NOT_STARTED继续使用selected resource option的`final_duration_seconds`。SOFT lock不作为hard validation pass condition。

正式Evaluator源文件不读取`solver_status`，也不导入`app.planning.backends`、OR-Tools、P0 evaluator/mutation runner或expected outcome。机器向量把声明状态改成FAILED并删除run outcome/objective metadata后仍得到完全相同报告，证明PASS/FAIL只来自Problem/Solution assignment事实。该行为不批准Solver结果；后继consumer仍必须在正式生命周期中先获得candidate再调用Validator。

[`problem_validator_check.py`](../../backend/app/planning/validation/problem_validator_check.py) 生成`formal-schedule-validator-report.v1`：1个formal positive、13个formula-free declarative mutations、C-001～C-011全覆盖、14个hard violations、6个duration/order property examples、ValidationReport/Error v2 Schema重放及AST independence scan。P0 positive/mutation目录、Problem/Solution/Validation Schema、rule sheet、历史fixture evaluator/runner与`uv.lock`均由固定SHA-256证明只读。本Task不运行CP-SAT业务model、OBJ-001、Benchmark、API/persistence或READY_FOR_REVIEW transition。

Implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的GitHub run `32350068318` / required job `96367085099` / artifact `9399519368`已精确复现6/6 formal report及38-path/6-row/0-issue治理报告，TASK-P2-04据此`done`。后继P2-05+ Solver candidate仍必须经过本Validator；Task关闭不等于已有business candidate或Production validation。

## TASK-P2-05 consumer integration

`CpSatBackend.solve_with_evidence()`现把每个core candidate送入既有`validate_problem_schedule()`；PASS时保留完整assignments，FAIL时丢弃assignments并映射稳定FAILED diagnostic。Validator源码、Schema、rule sheet、公式和import boundary均保持字节不变，Backend只消费它的solver-neutral报告。

Core machine evidence同时验证JSSP/FJSP positive、missing assignment→C-001与wrong selected duration→C-010；原13类formal mutation仍是C-001～011完整独立覆盖。该接线只形成P2-05 bounded consumer，不表示P2-06/07事实已由Solver建模，也不是P2-09 vertical-slice integration或Production publish gate。

## TASK-P2-06 temporal consumer integration

Backend生成的precedence、calendar、release/material与transport candidates继续交给同一formal Validator；Evaluator从Problem/Solution seconds/ticks/UTC独立重算C-002/005/006/009，不导入`temporal_constraints.py`或OR-Tools。Temporal machine evidence分别构造四类positive candidate，并对min/max lag、calendar、gate与cross-workshop transport做独立mutation复验。

Formal Validator源码、公式、Schema、rule sheet和13-case corpus保持字节不变。该交叉证据不覆盖C-007/008，也不是P2-09完整Scenario integration、objective correctness或Production publish gate。

## TASK-P2-07 Solver/Validator cross-check

Backend生成的RUNNING/HARD/SOFT candidates继续交给同一formal Validator；Evaluator从Problem/Solution独立重算COMPLETED exclusion、RUNNING resource/start/remainder occupancy及HARD resource/start/end，不导入`fact_lock_constraints.py`或OR-Tools。Machine evidence分别把合法candidate移动RUNNING与HARD tuple，稳定命中C-007和C-008；SOFT movement保持PASS。

Formal Validator源码、公式、Schema、rule sheet和13-case corpus保持字节不变。该证据形成C-007/C-008 Solver/Validator交叉，但不是P2-09完整Golden/Scenario integration、OBJ-001 correctness或Production publish gate。

## TASK-P2-10 Reference candidate validation

五个Reference Scheduler不复制或修改Validator公式。共享heuristic只生成solver-neutral`problem + assignments`候选；成功路径每次实例化fresh `ProblemScheduleValidator`并要求C-001～C-011全PASS，Validator FAIL时立即丢弃candidate并返回`VALIDATION_FAILED`。机器报告又对35个成功candidate进行第二次fresh validation，得到35/35 PASS、零hard violation。

`HEURISTIC_FAILURE`表示确定性构造过程没有找到完整hard-feasible placement，不是formal `INFEASIBLE`证书；失败路径不提交partial assignment给Validator，也不伪造PASS report。PlanningProblem本身非法继续在规则计算前拒绝。Validator源码、ValidationReport Schema、rule sheet、P2-09 assets与Solver backend均保持冻结；该交叉证据只形成TEST-REFERENCE-SCHEDULER，不形成Production publish gate或P2-12策略比较。

## TASK-P2-14 Exit audit

审计确认七correctness场景两轮、XS/S/M两轮Global+五Reference以及所有output candidate均由fresh formal Validator接受，Gate累计108次Benchmark Validator PASS；11个exact C-ID mutation仍逐一FAIL且无共同公式导入。Validator源码、Schema/rule与Backend均零差异。P2 READY只表示Simulation/development candidate可进入本阶段评审，不构成approval、publish或Production acceptance。

## P3 consumer allocation

P3-04创建reviewable DRAFT前、P3-06 edit/lock产生新DRAFT后以及P3-14 Gate/P3-17 Audit时都必须通过fresh formal Validator；TASK-P3-16只消费报告并本地化展示。FAIL必须丢弃candidate/new version，不得保留“待人工接受”的非法计划。Approval不能覆盖Validator FAIL，UI/API不得复制或降级规则。P3不修改C-001～C-011公式或Validator独立性，任何缺口需有界P3 remediation而非Audit内修复。

## TASK-P3-04 fresh validation consumer

`create_reviewable`在任何DB调用前通过`build_kpi_v2`重新调用现有`validate_problem_schedule(problem, solution)`，要求fresh report逐字等于supplied ValidationReport，并再次冻结SolverReport/quality/KPI；随后pure builder只接受`PASS + hard_violation_count=0 + violations=[]`。失败、stale、tamper、mixed或KPI drift均不产生DRAFT/audit。

本Task没有修改Validator、C-001～C-011、mutation assets、expected outcomes或Backend模型，也没有在domain/application复制约束公式。成功machine case复用P2 frozen correctness input；`lifecycle_service_solver_invocations=0`，测试fixture replay不能写成业务Solver rerun或新correctness baseline。

## TASK-P3-06 fresh command consumer

每个非replay content command先构造完整candidate assignments，再通过factory新建独立`ProblemScheduleValidator`执行正式Problem→candidate验证；只有精确`validation-report.v2`、matching problem hash、PASS、hard=0、violations=[]才构建/提交new DRAFT。`SUBMIT_FOR_REVIEW`对DRAFT content再次创建独立Validator，除PASS/0外还要求fresh report fingerprint逐字等于DRAFT validation lineage，才可CAS READY。Validator input不信任client status/objective，且domain command模块不导入Validator/Backend公式。Exact replay只核验已持久化fresh ValidationReport reference和immutable content，不重复制造历史event。

Validation mutation suite先取得一个server-accepted Move candidate，再把resource改为非候选并要求C-003 FAIL，证明application不能以semantic precheck替代formal gate。Validator FAIL candidate直接丢弃且row count不变。C-001～C-011、rule metadata、Solver、fixtures和P2 baseline均未修改。
