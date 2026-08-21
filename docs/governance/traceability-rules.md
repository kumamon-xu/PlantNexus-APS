---
doc_id: DOC-GOV-004
title: 需求追踪规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [5, 6, 86, 98, 99, 111]
last_reviewed: 2026-08-21
---

# 需求追踪规则

## 标准链路

```text
REQ / NFR / ENG
→ SCHEMA / ARCH / CONSTRAINT
→ TASK
→ TEST
→ ARTIFACT
```

业务能力以 `REQ` 为根；可用性、可靠性、安全、性能和可追溯性等以 `NFR` 为根；CI、日志、Worker、版本管理等工程设施可以 `ENG` 为根，不强行映射业务需求。

## ID 规则

| 类型 | 格式示例 | 所在位置 |
|---|---|---|
| Requirement | `REQ-005` | `requirements-register.md` |
| NFR | `NFR-OBS-001` | `nfr-and-engineering-register.md` |
| Engineering | `ENG-VAL-001` | 同上 |
| Constraint | `C-001` | `planning/constraint-catalog.md` |
| Objective | `OBJ-001` | `planning/objective-policy.md` |
| Task | `TASK-P0-04` | `tasks/P0/` |
| Test | `TEST-VALIDATOR-MUTATION` | Quality/Test registry |
| ADR | `ADR-0005` | `adr/` |

治理注册表使用 `registry_version: 1.0.0`。Requirement/NFR/ENG 的 `ALLOCATED` 只表示 ID 已稳定分配，不等同实现完成；实现状态只能来自真实 TEST/ARTIFACT。引用必须使用完整 ID，范围允许写成 `REQ-001～REQ-015`，但校验器会展开并逐项核对。

稳定根集合来自：

- `requirements-register.md`；
- `nfr-and-engineering-register.md`；
- `test-strategy-and-matrix.md` 中的 Test registry；
- `prod-open-register.md`、`sim-assumption-register.md` 和 `risk-register.md` 的独立命名空间。

`PROD_OPEN` 条目使用 `OPEN-NNN`；仿真假设使用 `SIM-ASSUMPTION-NNN`。两类状态和关闭证据不可互换。

## Task Card 要求

每张任务卡必须列出 Requirement/NFR/ENG、依赖、目标、输入、允许/禁止修改文件、输出、Schema/Migration、错误行为、测试、Benchmark、Scenario、验收命令、明确排除项、开放问题、假设和回滚。P1及以后 Task还必须列出可二值判断的 `Completion conditions`。Task 进入 `in_progress` 时必须记录当时完整 40字符 HEAD SHA作为不可变 `Diff base`。

任务过程中如果必须修改允许范围以外的文件，应停止，说明原因并先更新任务卡。禁止通过无边界重构完成局部任务。

## 完整性

- 没有 TEST 的 Requirement 不能被标记为已实现。
- 没有 Validator 证据的 Solver 结果不能成为可评审计划。
- 没有 ARTIFACT/manifest 的发布不能视为可追溯发布。
- 当前尚不存在的代码、测试和产物在矩阵中标记 `PLANNED`，不能填造链接。

Schema skeleton 证据链必须同时包含 versioned machine artifact、human-readable contract、data dictionary、contract test 和 Task acceptance。它只证明合同结构可执行；Import/Snapshot/Problem builder、hash、Solver 或业务能力没有实现证据时必须继续标记 `PLANNED`。

Breaking canonical release还必须保留旧artifact的byte fingerprint、为跨document `$ref`建立显式validator registry、提供v1/v2 rejection与positive/negative/round-trip evidence，并区分Schema hash字段格式和真实builder hash结果。Pure types/precheck只能作为合同证据；没有producer、quality report evaluator、builder或persistence时，相应链路继续`PLANNED`。

Rule/state/error/capability contract 证据链还必须区分：machine rule/registry artifact、pure enum/precheck、Schema envelope、completeness/negative contract test 与真实业务 evaluator。`V1_SUPPORTED`、allowed transition metadata 或 rule-sheet PASS 不能替代 phase-specific implementation、ScheduleValidator mutation、状态持久化、权限或发布证据。

Simulation contract 证据链必须区分：Schema contract version、Profile/Scenario asset version、Generator/canonicalization version、seed、canonical dataset/hash、manifest、Schema sample、formal Fixture、replay/isolation test 与真实 Import/Snapshot/Problem/Benchmark/Execution artifact。`records={}` 或 `.synthetic.json` 只能证明 P0 合同边界，不能替代 Scenario Library、生产隔离设施或性能结果。

Golden Fixture 证据链还必须区分：fixture-local record vocabulary、人工 Schedule、独立直接计算、expected validation/KPI 与正式 PlanningProblem/candidate/ValidationReport/KPI contracts。expected artifact 不能自证 PASS；positive Golden 不能替代 negative mutation 或 reusable ScheduleValidator。`SIM-MINIMAL-001` 的非空 Import hash证明可重放的 committed correctness dataset，不证明 P1 canonical mapping/Normalization 已实现。

Validator Mutation 证据链必须同时区分：不可变 positive base/hash、与 evaluator 分离且不含判断公式的 mutation construction、独立 evaluator、Rule Sheet metadata、exact ValidationReport/Error、Schema validation、C-ID/required-mutation coverage、deterministic replay 与 backend/Solver dependency boundary。fixture-local evaluator 可以形成 P0 correctness evidence，但没有正式 PlanningProblem/candidate、Solver comparison、Property/Benchmark 或状态集成时，必须把 P2 production/performance completion 保持为 `PLANNED`。

Engineering Skeleton 证据链必须区分：exact direct pin 与 transitive lock、environment/data-plane config、Secret redaction、lazy client 与真实 connectivity、liveness 与 readiness、generic Job primitive 与业务状态机、process-local reference idempotency 与 distributed durable repository、migration structure test 与 Production migration、workflow/config contract 与 CI provider run、conditional Benchmark hook 与真实 BenchmarkReport。local/SQLite/synthetic-probe PASS 不得写成 PostgreSQL/Redis outage、business side-effect、Production security/deployment 或 P0 Exit Gate evidence。

P0 Exit Gate 审计还必须区分“审计 Task 完成”和“Milestone Gate 通过”：审计报告/manifest 完整、命令可复验且忠实记录 `FAIL`/`NOT_RUN` 时，审计 Task 可以 `done`；但任一 §72 必需 Gate 非 `PASS` 时 P0 必须保持 `active`/`NOT_READY`，不得进入 P1。workflow 的 exact command必须能审计当前 immutable Task range，硬编码旧 Task 即使文本 contract test通过也不构成 CI PASS；local command parity、repository build 或空 remote检查不能替代 external provider run。provider、run ID/URL、immutable commit、job conclusion、external artifact 和 required-check evidence必须可核验。

TASK-P0-10 的 provider closure 必须同时记录 GitHub repository/workflow/event、run ID/URL、`head_sha`、run attempt/status/conclusion、required job 及 step conclusions、artifact ID/name/size/digest/expiry，以及 `main` 的 protected/required-check 状态。run 必须指向本 Task Diff base 之后的不可变 commit，job 必须 `success`；只有失败 run 或 artifact upload 不能关闭 CI Gate。证据文档对已完成 implementation run 的引用不能自我包含后续 evidence-only commit，因此后续 commit 仍必须执行同一 workflow，并在任务交付中记录其结果；不得用这一自引用边界跳过最终 CI。

## 自动校验

`scripts/check_docs.py` 执行以下治理检查：

1. registry 表结构、版本、ID 格式和定义唯一性；
2. 文档与测试代码中的 REQ/NFR/ENG/TEST/OPEN/SIM_ASSUMPTION/RISK 引用存在；
3. 每个已登记 REQ/NFR/ENG 在 traceability matrix 中恰有一行；
4. Task 的 Requirement/NFR/ENG、依赖、文档影响字段和创建路径有效；Task ID/目录/front matter phase一致，历史 Phase只保留 terminal Task，当前 Phase允许详细 Task，未来 Phase禁止详细卡；
5. traceability matrix 中的规范路径和实际 Artifact 链接存在，`PLANNED` 不被当成实现证据；
6. 使用 `--check-diff` 时，以 Task 的 `Diff base..HEAD` 已提交路径和当前 working tree 路径并集作为实际 Git diff；命中的 change-impact Rule ID 已在当前 Task 声明，且必审文档已列入 `Documents to update`；
7. `OPEN` 关闭记录字段完整，PROD_OPEN 与 SIM_ASSUMPTION 命名空间没有混用。

2026-08-20用户明确批准P1→P2后，校验器继续从`docs/current_phase.md` front matter读取current phase并支持任意`TASK-Pn-NN～NN`依赖范围。P0/P1 `done`历史卡继续参与依赖/引用审计；P1+必须包含`Completion conditions`，P2+还必须包含`Start gate`、`Dependency changes`、`ADR impact`与`Provider evidence`；P3+仍只能保留Milestone。

TASK-P1-01建立的CI changed-task discovery仍要求`--discover-task-from <event-base-sha>`为完整、存在且为HEAD祖先的commit。普通range在`docs/tasks/**`中只能出现一个current-phase Task Card；历史/未来/phase错位/多个卡直接失败。若range没有Task Card，仅当仓库恰有一个current-phase `in_progress` Task时回退。选择完成后仍使用卡片`Diff base..HEAD`+working tree执行scope/impact，不把event base混成Task baseline。

TASK-P2-00只为“首次创建完整阶段计划”增加严格batch例外：range中所有Task卡必须为本次新增；唯一owner必须是`TASK-Pn-00`、role=`phase-planning-owner`、status=`in_progress/done`并有完整Diff base；每个其余成员必须role=`phase-plan-member`、status=`planned/ready`且不得预填implementation SHA。既有成员、多个/错误owner、active/done成员、历史/future卡均硬失败。Batch选择owner后，全部range仍受owner精确allowed scope、Impact Rule和文档检查约束；该规则不允许批量实现或修改既有Task。

结构化报告 schema 为 `traceability-report.v1`，至少包含 Task、可选 `task_discovery_base`、Git HEAD、Diff base、committed-range/working-tree source counts、changed paths、matched impact rows、expected/observed documents、missing trace refs、registry counts 和失败明细。失败返回非零退出码，不允许自由文本 skip。

TASK-P1-02将REQ-001/002/003/009、NFR-DET/TRC与ENG-SOL/ERR/VER链接到canonical-records.v1、Import v2、Snapshot v2、data dictionary、pure types/prechecks及TEST-CONTRACT-001。当前artifact state只标记contract formed；Adapter/staging/Normalization/DataValidation/Expansion/Snapshot/Problem builder/hash与P1 Gate继续`PLANNED`。

Raw Staging evidence链必须区分：opaque immutable batch/row contract、source/version/content与row digest/location/UTC provenance、data-plane/synthetic conditional、idempotency scope/fingerprint、exact replay/conflict、atomic transaction rollback、internal migration empty/populated round trip、raw-not-canonical dependency scan，以及真实Adapter/Normalization/DataValidation/independent Production database仍`PLANNED`。SQLite测试不得写成PostgreSQL concurrency、Production security或common-ingress PASS。

TASK-P1-03将REQ-001/009、NFR-TRC/REL/ISO/SEC与ENG-ARCH/ERR/VER链接到Raw Staging contracts/repository、`0002_raw_import_staging`、TEST-IMPORT-STAGING-001和TEST-IDEMPOTENCY durable Import slice。它不改变Schema set、产品error registry或外部field authority；后续链路继续`PLANNED`。

Reference file evidence链必须区分：adapter ID/version/capability与真实系统binding；fixed transport header与业务field mapping；format-neutral raw payload/row identity与format-specific file digest/media/location；CSV UTF-8/dialect和XLSX read-only/archive/active-content controls；prepared batch与durable repository replay；temporary synthetic files与真实客户数据。单文件首错DATA_ERROR、2-row parity或lock PASS不能替代Normalization/DataValidation、malware/auth review、Production interface authority或common-ingress Gate。

TASK-P1-04将REQ-001/009、NFR-TRC/SEC/REL与ENG-ARCH/ERR/VER链接到`ReferenceFileAdapter@1.0.0`、exact dependency lock、TEST-IMPORT-ADAPTER-001 contract/integration evidence及TASK-P1-03 repository。OPEN-002/013/015、Schema set和产品error registry均不改变；canonical producer与后续pipeline继续`PLANNED`。

Normalization evidence链必须区分：global schema set版本与immutable Import document字段；mapping profile版本与source system/version；unit registry合同与Production unit policy；Raw transport provenance与canonical hash projection；field normalization与跨实体Data Validation。Same-input bytes/hash、unit/time/ID正反测试不能替代DAG/reference/capability quality report、Snapshot/Problem replay或common-ingress Gate。

TASK-P1-05将REQ-002/003/009、NFR-DET/TRC与ENG-ERR/VER链接到`app.normalization`、`unit-conversion-registry.v1`、TEST-NORMALIZATION-001及扩展TEST-CONTRACT-001。`2.1.0`是additive set version，Import v2 document仍固定`2.0.0`且既有Schema hash保留；OPEN-001/002/013/015、产品error registry和后续Data Validation边界均不改变。

Data Validation evidence链必须区分：Import v2 document/package identity、data-quality rule/error registry/error/report/canonicalization各版本；structure/reference/DAG/resource/capability/time/duration/unit evaluator；PASS零Error与FAIL count等式；rich source/action detail；stable multi-error ordering/report ID；以及仍未形成的Expansion/Snapshot/Problem/common-ingress/ScheduleValidator/Solver/Production authority。固定negative builder不得复用expected report或C-ID公式，也不得把input quality错误写成candidate schedule violation。

TASK-P1-06将REQ-001/002/003/009、NFR-COR/DET/TRC与ENG-ERR/VER链接到`app.data_validation`、error registry v2/Error v3/ImportQualityReport v1、TEST-DATA-QUALITY-001/TEST-INF-NO-RESOURCE/TEST-CAPABILITY-001及扩展TEST-CONTRACT-001。`2.2.0`为additive set release，Import v2=`2.0.0`、unit registry v1=`2.1.0`和历史Error artifacts保持不变；OPEN项、Constraint/ScheduleValidator/Solver边界均未改变。

Order Expansion evidence链必须区分：source-explicit ProductionLot与系统自动split/merge；Routing definition与derived OperationInstance/edge；candidate duration/source逐字copy与任何重新计算/fallback；RUNNING/COMPLETED fact引用与未来Problem过滤；Import/PASS report/expansion versions与Snapshot hash；固定样例、Hypothesis generation/shrinking、P2 PlanningProblem Property和Benchmark。Output可通过Snapshot v2 pure precheck不等于Snapshot builder/hash/persistence已形成。

TASK-P1-07将REQ-003/009、NFR-DET/TRC与ENG-SOL/ERR/VER链接到`domain.production`、`normalization.order_expansion`、TEST-ORDER-EXPANSION-001和TEST-RUNNING P1 slice。`order-expansion.v1`使用versioned lot-operation/lot-edge SHA-256 identity；schema set仍`2.2.0`，Import/Snapshot v2仍`2.0.0`，product error registry/C-ID不变。SPLIT_MERGE、Snapshot/Problem/common-ingress/P2 Solver均继续明确排除。

PlanningSnapshot evidence链必须区分：Import dataset hash、Expansion hash、Snapshot semantic hash和full canonical-bytes digest；self ID/hash与received/generated/runtime metadata；canonical business timestamps与非业务storage `created_at`；application/table plane guard与独立Production/Simulation Database；exact replay与identity/content conflict；reversible migration与destructive downgrade。任一层不得用另一层digest或本地SQLite替代。

TASK-P1-08将REQ-002/003/009、NFR-DET/TRC/ISO/REL与ENG-SOL/ERR/VER链接到`app.snapshots`、Infrastructure repository、`0003_planning_snapshots`、TEST-SNAPSHOT-REPLAY-001及TEST-SIM-ISOLATION Snapshot slice。Schema set仍`2.2.0`、Snapshot document仍`2.0.0`且Schema字节未改；PlanningProblem/common ingress/PlanningRun manifest/independent Production DB/Solver仍明确排除。

Synthetic Generator evidence链必须区分：FactoryProfile/ScenarioSpec/Generator/mapping/manifest各自version；root/named child seed与调用顺序；source-shaped Raw row、Normalization结果与quality report；canonical Import bytes/hash与non-hash generated-at/transport metadata；asset correctness规模与Benchmark/Production distribution；P1 generator slice与P1-11 common ingress。局部manifest不得重解释已发布ScenarioManifest Schema，PASS不得替代Production authority或Solver evidence。

TASK-P1-10将REQ-001/003/009/011/012、NFR-DET/TRC/ISO与ENG-ARCH/ERR/VER链接到七层generator、`SIM-P1-INGRESS-001@1.0.0`、TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION、Normalization cycle-duration regression及`synthetic-generator-report.v1`。Schema set/Import/Profile/Scenario发布合同不变；common ingress、Snapshot/Problem orchestration、Solver/Benchmark/Production继续明确排除。

Common-ingress evidence链必须同时记录：two source forms到Raw Staging的差异；staging后唯一函数链与quality PASS先后顺序；Import/Snapshot/Problem的complete bytes/hash/ID replay；四类exact rejection的stage/category/code和无下游调用；data-plane/no-shortcut边界；report的commit/version/config/count与provider artifact。Reference temporary synthetic input不得写成Production connector，Problem终止不得写成Solver/Validator/feasibility。

TASK-P1-11将REQ-001/002/003/009/011/012、NFR-COR/DET/TRC/ISO/REL/SEC与ENG-ARCH/SOL/ERR/VER链接到`app.application`、Generator公开staging、TEST-P1-COMMON-INGRESS/SCENARIO/SNAPSHOT/PROBLEM/DATA-QUALITY/SIM-ISOLATION及`p1-data-pipeline-report.v1`。Schema/registry/migration/dependency未变，P1-12 audit、Solver/P2、Production authority/deployment仍明确排除。

P1 Exit Gate evidence链必须区分：P1-01～11 implementation commit/provider artifact、P1-11 closure head、P1-12本地audit execution head、P1-12 documentation implementation commit及其后续evidence-only closure。Audit report可基于已验证P1 baseline和本地独立命令作出§74 decision，但不得自我包含尚未push的run；Task lifecycle只有在自身exact provider run/artifact回填后才为`done`。

TASK-P1-12将全部P1 roots→TASK-P1-01～12→36个registered Test IDs/七类machine reports→11组implementation provider artifacts→P1 audit report/manifest闭环。`READY`只关闭P1 Data & Snapshot Gate，不改变root `ALLOCATED`状态、15项PROD_OPEN、10项SIM_ASSUMPTION、10项风险或P2/Production `PLANNED`边界；current phase必须等待用户明确授权。

用户于2026-08-20批准transition后，TASK-P2-00把P1 Milestone关闭为completed、P2激活，并分配TASK-P2-01～14。Implementation `3298229fae89a54e0641f5907ad90c4fa81569bf` / run `32332003608` / artifact `9393345593`证明32 paths/5 rows/19 checks/0 issues，phase-planning batch归属闭环。计划链为合同缺口→机器合同→Backend/Validator→C-001～C-011→OBJ-001→correctness/reference/export/benchmark→vertical Gate→Exit Audit。所有P2业务Test/Artifact仍为`PLANNED`，root ID继续`ALLOCATED`，C-012～C-018、OBJ-002、P3/P4与Production边界不变。

TASK-P2-01 evidence链必须同时区分：v1 immutable Schema/sample fingerprint与v1 fixed builder replay；global schema set`2.3.0`与Import/Snapshot/unit/quality document内固定旧版本；v2 Schema sample与真实builder replay；Snapshot due/source与独立priority/source authority；active operation与historical anchor；expired/active/cross-horizon HARD/SOFT locks；Problem hash与canonical-bytes digest；local report与exact provider artifact。任一项不得用另一项替代。

本Task把REQ-002/003/004/009/012及NFR-COR/DET/TRC、ENG-SOL/ERR/VER链接到ADR-0010、Problem v2 Schema/types/builder/hash/verify、TEST-CONTRACT-001/TEST-PROBLEM-REPLAY-001/TEST-PROPERTY和`planning-problem-contract-report.v1`。只把C-008/OBJ-001输入合同从PLANNED更新为formed；Backend/Solver/formal Validator/Benchmark和P2-02～14仍为PLANNED。Provider closure前Task保持`in_progress`，root生命周期与registry版本不变。

TASK-P2-02 evidence链必须区分：global schema set`2.4.0`与Problem v2=`2.3.0`及更早document固定版本；Schema/sample原始bytes digest与canonical document fingerprint；Policy/Limits明确Simulation source/value与Production authority；`CONTRACT_SAMPLE`与`SOLVER_RUN`；七种status mapping与真实Solver结论；PlanningSolution candidate与independent ValidationReport；local `uncommitted` report与exact provider artifact。任一项不得互相替代。

本Task把REQ-004/005/009、NFR-COR/DET/TRC/OBS与ENG-SOL/ERR/VER链接到四份Schema/sample、pure contracts、TEST-CONTRACT-001/TEST-ERROR-MAPPING-001、CI integration contract及`planning-machine-contract-report.v1`。只把机器shape/status/provenance carrier从PLANNED更新为formed；Backend/C-ID/OBJ-001计算/formal Validator/KPI/Benchmark/P3仍为PLANNED。Exact implementation provider已按run `32342489997` / required job `96344226221` / artifact `9396828326`闭环，Task现为`done`；root生命周期与registry版本不变，后续Task不自动激活。

## TASK-P2-03 trace slice

REQ-004/009、NFR-COR/TRC/SEC/OBS/PER与ENG-ARCH/SOL/ERR/VER链接到ADR-0011、exact dependency/lock、`planning/backends`代码、TEST-CONTRACT-001/TEST-SOLVER-UPGRADE、CI integration及`solver-backend-foundation-report.v1`。只有dependency/namespace/status/parameter/engineering-smoke从PLANNED变为formed；C-ID、OBJ-001 execution、candidate/formal Validator、Golden/Scenario/Benchmark/Export/P3继续PLANNED。Exact implementation run `32346208046` / artifact `9398128763`已闭环，Task=`done`；root生命周期与registry版本不变。

## TASK-P2-04 trace slice

REQ-004/005/009、NFR-COR/DET/TRC与ENG-VAL/ERR/VER链接到ADR-0005/0008、`problem_schedule_validator.py`、TEST-VALIDATOR-MUTATION及C-specific/Hypothesis tests、CI integration和`formal-schedule-validator-report.v1`。Problem/Solution→independent C-ID evaluation→ValidationReport/Error链已在本地formed；CP-SAT business candidate、OBJ-001、consumer integration、Golden/Scenario/Reference/Benchmark/Export/P3继续PLANNED。

证据链必须区分authoritative Problem input rejection与candidate schedule violation、candidate solver status与独立validation result、P0 immutable fixture evaluator与formal Problem/Solution Validator、local `uncommitted` report与exact provider artifact。Expected mutation outcome只用于test assertion，不得进入Validator决策。Implementation run `32350068318` / artifact `9399519368`已精确绑定同一SHA并闭环，TASK-P2-04=`done`；root生命周期与registry版本不变，P2-05不自动激活。

## TASK-P2-05 trace formation rule

形成链为`REQ-004/005/009 → TASK-P2-05 → C-001/003/004/010/011 → core builder/mapper + formal Validator → TEST-GOLDEN-JSSP/FJSP、TEST-INF-NO-RESOURCE/HORIZON、TEST-PROPERTY、TEST-VALIDATOR-MUTATION → cp-sat-core-model-report.v1 + Task report + exact provider artifact`。只有这五个C-ID的bounded Solver slice可从PLANNED提升为formed；其他C-ID、OBJ-001 execution、Strategy、Reference/Benchmark/Export/P3继续PLANNED。

必须区分native OPTIMAL与无objective的业务FEASIBLE、post-solve metric与objective optimization、formal Validator PASS与Production publishability、tiny oracle与Benchmark。Provider artifact未绑定exact implementation/closure SHA前只能记录local evidence；完成P2-05也只满足P2-06依赖，不自动授权其启动。

Implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的required run `32354050257`与artifact `9400957897`已精确绑定并复现core/formal/Task链，因此TASK-P2-05从formed转为`done`。C-002/005～009、OBJ-001 execution、Strategy、Benchmark/Export/P3仍为PLANNED；P2-06没有自动激活。

## TASK-P2-06 trace formation rule

形成链为`REQ-004/005/009/012 → TASK-P2-06 → C-002/005/006/009 → temporal builder + independent formal Validator → TEST-MAX-LAG/CALENDAR/MATERIAL/CROSS-WORKSHOP/PROPERTY/VALIDATOR-MUTATION → cp-sat-temporal-model-report.v1 + Task report + exact provider artifact`。只把这四个temporal C-ID的bounded Solver slice提升为formed；C-007/008、OBJ-001 execution、Strategy、Reference/Benchmark/Export/P3继续PLANNED。

证据必须区分seconds权威值与tick projection、min/transport独立下界与错误相加、grid-equivalent calendar与输入改写、MODEL_INVALID与certified INFEASIBLE、local `uncommitted`与exact provider SHA。Formal Validator公式、Problem builder/hash和rule sheet保持独立且冻结；provider artifact未绑定implementation SHA前Task保持`in_progress`，完成也不自动授权P2-07。

Implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`的required run `32432482739`与artifact `9429579311`已精确绑定并复现temporal/core/formal/Task链，因此TASK-P2-06=`done`。C-007/008、OBJ-001 execution、Strategy、Benchmark/Export/P3仍为PLANNED；P2-07没有自动激活。

## TASK-P2-07 traceability rule application

形成链为`REQ-004/005/009/012 → TASK-P2-07 → C-007/008 → fact_lock_constraints + independent formal Validator → TEST-RUNNING/INF-LOCK/PROPERTY/VALIDATOR-MUTATION → cp-sat-fact-lock-model-report.v1 + Task report + exact provider artifact`。COMPLETED anchor、RUNNING tuple、HARD exact、SOFT metadata、precheck与certified INFEASIBLE必须分别可追踪，不能用单一“lock PASS”合并。

证据必须区分Problem hash保存的RUNNING历史与Problem未暴露的execution fact ID、HARD constraint与SOFT metadata、self-conflict MODEL_INVALID与合法constraint INFEASIBLE、local `uncommitted`与exact provider SHA。Formal Validator、Problem builder/hash、rule sheet、ADR-0007与dependency保持独立且冻结；implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的artifact `9430579117`已绑定exact SHA并关闭Task，完成也不自动授权P2-08。

## TASK-P2-08 traceability rule application

形成链为`REQ-004/005/009 → TASK-P2-08 → OBJ-001 → versioned Simulation Delivery Policy + GlobalCpSatStrategy + objective builder + formal Validator → TEST-GOLDEN-JSSP/FJSP、TEST-PROPERTY、TEST-SOLVER-UPGRADE、TEST-ERROR-MAPPING-001 → objective-strategy-report.v1 + Task report + exact provider artifact`。只有完整C-001～C-011域上的priority-weighted tardiness seconds与Global Strategy可从PLANNED提升为local formed；OBJ-002/003、P2-09 Golden/scenario integration、Reference/Export/Benchmark/Gate/P3继续PLANNED。

证据必须区分hard feasibility与objective optimality、native best bound与candidate objective、OPTIMAL/FEASIBLE/UNKNOWN/INFEASIBLE、solver candidate与formal Validator接受、explicit Simulation value与Production authority、tiny correctness timing与XS/S/M baseline、local `uncommitted` report与exact provider SHA。Validator FAIL必须丢弃candidate；UNKNOWN不得冒充INFEASIBLE，FEASIBLE不得冒充OPTIMAL。Provider artifact未绑定implementation SHA前TASK-P2-08保持`in_progress`，完成也不自动授权P2-09。

Implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的required run `32438785162`与artifact `9431673977`已精确绑定并复现objective/strategy 7/7及52 committed/0 working paths、8 rows、19 checks、0 issues，因此TASK-P2-08=`done`。OBJ-002/003、P2-09 Golden/scenario、Reference/Export/Benchmark/Gate/P3继续PLANNED；P2-09没有自动激活。

## TASK-P2-09 traceability rule application

形成链为`REQ-004/005/009/012 + NFR-COR/DET/TRC/ISO + ENG-ARCH/SOL/VAL/VER → TASK-P2-09 → seven versioned Scenario/Profile/blueprint/manifest assets → public Raw/Import/Snapshot/Problem → Global Strategy → formal Validator → TEST-GOLDEN-JSSP/FJSP、CALENDAR/MATERIAL/RUNNING/CROSS-WORKSHOP/INF-LOCK、TEST-PROPERTY/VALIDATOR-MUTATION/SCENARIO-REPLAY → p2-correctness-report.v1 + Task report + exact provider artifact`。

只有七类correctness、7个property replay和C-001～C-011 formula-free negative integration可提升为local formed。证据必须固定version/seed/hash，区分fixture-local manifest与发布Schema、local `uncommitted`与provider SHA、correctness `XS`与性能profile；不得更新expected掩盖回归。P2-10 Reference、P2-11 Export、P2-12 XS/S/M Benchmark、P2 Gate/P3仍PLANNED，provider完成前TASK-P2-09保持`in_progress`。

Implementation `20e49c92306128b47313059fabe31534814dbe3d`的required run `32442651322`与artifact `9432982306`已精确绑定并复现correctness 8/8、16 reports及58 committed/0 working paths、7 rows、19 checks、0 issues，因此TASK-P2-09=`done`。Reference/Export/XS-S-M Benchmark/Gate/P3继续PLANNED；P2-10没有自动激活。

## TASK-P2-10 traceability rule application

形成链为`REQ-004/005/009/015 + NFR-COR/DET/TRC/PER + ENG-ARCH/SOL/VAL/ERR/VER → TASK-P2-10 → reference-scheduler-contracts/policy + five algorithm IDs → PlanningProblem v2 → complete candidate → fresh formal Validator → weighted tardiness/makespan/runtime → TEST-REFERENCE-SCHEDULER/PROPERTY → reference-scheduler-report.v1 + Task report + exact provider artifact`。

只有五个deterministic non-production baseline、35个七场景完整candidate、fresh Validator与explicit failure可提升为formed。证据必须区分heuristic failure与INFEASIBLE certificate、complete/discard与partial schedule、single-run runtime与XS/S/M baseline、Reference measurement与OBJ optimality、local `uncommitted`与provider SHA。Planning/Validator公式、Schema、P2-09 assets、dependency与Benchmark路径保持冻结；Global comparison/warning、Export、P2 Gate和P3继续PLANNED。

Implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`的required run `32449742281`与artifact `9435264655`已精确绑定并复现reference 7/7、17 reports及38 committed/0 working paths、6 rows、19 checks、0 issues，因此TASK-P2-10=`done`。Global comparison/Benchmark/Export/Gate/P3继续PLANNED；P2-11没有自动激活。

## TASK-P2-11 traceability rule application

形成链为`REQ-004/005/006/009 + NFR-COR/DET/TRC/REL/OBS + ENG-ARCH/SOL/VAL/ERR/VER → TASK-P2-11 → kpi.v2/export-manifest.v1 + reporting/exporters → validated P2-09 replay → TEST-OUTPUT/CONTRACT-001/IDEMPOTENCY → p2-output-contract-report.v1 + Task report + exact provider artifact`。

只有validated synthetic KPI、真实SolverReport freeze和不可发布9-payload internal package可提升为local formed。证据必须区分set version与document version、KPI/package ID与exact-byte fingerprint、PlanningSolution与ScheduleVersion、directory replay与ExportJob idempotency、formal PASS与approval、single-run telemetry与Benchmark。ChangeReport=P4、BenchmarkReport=P2-12，二者不得伪造；P3 state/persistence/publish继续PLANNED。

Implementation provider artifact绑定exact SHA前TASK-P2-11保持`in_progress`。Provider必须复现output report 8/8、全部历史reports和Task diff，并确认`uv.lock`、Planning/Strategy/Backend/Validator/Scenario/Benchmark/API/DB/Worker/P3禁止边界无差异；完成也不自动授权P2-12。
