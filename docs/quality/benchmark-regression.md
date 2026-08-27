---
doc_id: DOC-QUAL-005
title: Benchmark Regression 规则
status: baseline
spec_version: 0.3.0
phase: P2-P7
normative: true
source_sections: [53, 55, 56, 57, 58, 89, 102]
last_reviewed: 2026-08-26
---

# Benchmark Regression 规则

## P4 planned regression evidence

TASK-P4-10/14在保留P2 XS/S/M基线的同时记录五类continuous disruption的deterministic functional与timing证据，并分别报告Delivery/Stability/Makespan；P4-15独立复验。没有真实数据与OPEN threshold closure时，这些数字只用于regression，不构成Production capacity/SLA。本次不改runner、threshold或expected。

## TASK-P3-17 audit conclusion

P2 XS/S/M Gate regression与独立XS 8/8均PASS，P3 Gate两次语义指纹一致；Frontend bundle与各service timing只保留raw development observation。OPEN-011/012、L/XL与Production threshold/SLA仍未建立。

## TASK-P3-14 regression boundary

Vertical Gate保留P2 XS required regression与P2 Gate raw evidence，并把P3 read/render/action/export timing仅视为development observation。Semantic projection显式排除runtime timing及其派生identity，不调整P2 baseline/tolerance，也不建立L/XL、Production capacity、browser performance或SLA门槛。

Solver 升级、Constraint 修改、PlanningProblem 修改和影响模型规模的 preprocessing 修改都必须回放固定 Scenario Set。

比较维度：correctness、objective quality、runtime、memory、model size、first feasible、bound/gap 和 Validator result。

## 判定顺序

1. Validator/contract correctness；
2. feasibility/status semantics；
3. objective quality 与 Reference Scheduler；
4. runtime/memory；
5. 其他诊断指标。

Correctness 退化不能用更快运行时间抵消。显著质量或性能退化需要阻止发布或提交 ADR；“显著”的生产阈值受 OPEN-012 约束，当前使用版本化 Benchmark baseline 和明确环境作相对比较。

报告和 baseline 是版本化 artifacts，不手工覆盖历史结果。

## TASK-P0-03 review

本 Task 首次发布 `planning-problem.v1` skeleton，因此已审查 ADR-0003 与本规则。P0-03 没有 Problem builder、Solver、固定 Scenario Set 或历史 baseline，无法产生有意义的 correctness/quality/runtime/memory comparison；不得伪造零值 Benchmark。P2 首次 vertical slice 必须把该 schema version/problem hash 纳入固定 Scenario replay，并建立真实 baseline。

## TASK-P0-04 review

P0-04 将总规已有 C-001～C-018 semantics 固定为 `constraint-rule-sheet.v1`，没有修改 `planning-problem.v1`、Solver、constraint builder、目标或 Scenario baseline；状态/error/capability contract 也不改变模型规模。因此当前没有可运行的 Solver/Golden/Scenario benchmark，不生成零值或 synthetic 性能结论。

P2 首次 baseline 必须记录 rule sheet/ValidationReport version；以后任何公式、C-ID 语义或 capability 从 UNSUPPORTED 变为支持，都重新匹配本规则并执行 correctness/quality/runtime/memory replay。

## TASK-P0-05 review

P0-05 新增 versioned Profile/Scenario/Manifest 与 empty Import hash，但没有 PlanningProblem、Solver、baseline profile 或 benchmark result；rule-sheet change 只解除全局 schema set exact-value check，C-ID/formula 不变。当前无法产生有效 runtime/memory/quality comparison，不写零值报告。P2 首个 baseline 必须记录 schema set `1.2.0`、Scenario/Profile/Generator versions、dataset/problem hashes 与硬件环境。

## TASK-P0-08 review

CI workflow 保留 `PLANTNEXUS_BENCHMARK_PROFILE=pr` 的条件 hook：只有未来获准 Task 真实创建 `scripts/run_benchmark.py` 后才调用；当前明确输出 deferred 信息。P0-08 没有 OR-Tools、Solver/Problem change、BenchmarkRunner/profile/baseline 或 runtime/memory/quality 数值，不生成伪 BenchmarkReport，也不把 CI/health latency当成 Solver 性能。OPEN-012 保持 OPEN。

## TASK-P1-02 review

本Task新增canonical Import/Snapshot合同但没有PlanningProblem builder、Solver、preprocessing runtime、BenchmarkRunner/profile/baseline或历史comparison。Schema/sample/entity counts只用于contract correctness，不能被解释为规模、吞吐、runtime或memory结果；不生成零值BenchmarkReport。未来TASK-P1-09/P2 consumer必须记录schema set`2.0.0`、document/builder/hash versions并按本规则回放，OPEN-012保持OPEN。

## TASK-P1-04 review

本Task新增openpyxl/defusedxml dependency和bounded file parsing，但没有PlanningProblem、Solver、constraint/preprocessing model、BenchmarkRunner/profile或baseline。2-row temporary CSV/XLSX仅用于contract/integration回归，测试耗时不设门槛且不表示吞吐、内存、factory size或Production capacity；不生成BenchmarkReport。

OR-Tools仍不存在，Solver replay Gate不触发。后续如文件解析成为可观测pipeline阶段，可记录明确环境与rows/bytes/sec诊断，但生产阈值仍由OPEN-012/P7授权。

## TASK-P1-05 review

本Task新增pure Normalization与canonical serialization，但不修改PlanningProblem、constraint、Solver、model-size preprocessing、BenchmarkRunner/profile或baseline；OR-Tools仍不存在。定向测试的小批次records/sec只可作为非门禁诊断，本Task不记录吞吐/内存/Production capacity或零值BenchmarkReport。

Mapping/unit rule version已进入Import hash，未来TASK-P1-09/P2 benchmark必须记录该version与dataset/problem hashes。Production阈值仍由OPEN-012/P7授权，本次不触发Solver replay Gate。

## TASK-P1-06 review

本Task新增标准库DAG/reference/resource/capability/time/duration evaluator，但不修改PlanningProblem、Constraint、Solver或model-size preprocessing，也没有BenchmarkRunner/profile/baseline。定向small synthetic package只用于correctness；不记录rows/sec、runtime、memory、factory scale或Production capacity，不生成零值BenchmarkReport。

未来TASK-P1-11/P2 benchmark应把data-quality-rules.v1、error registry v2与PASS report ID纳入input provenance，并在correctness失败时先停止。OR-Tools仍不存在，Solver replay Gate不触发，OPEN-012保持OPEN。

## TASK-P1-07 review

本Task新增会决定未来Problem规模的deterministic preprocessing，但当前没有PlanningProblem、Solver、BenchmarkRunner/profile/baseline或历史comparison。Hypothesis positive生成4-operation branch/merge、1～3 lots、2 workshops/resources与每operation 1～2 candidates，对应4～12 instances、4～12 edges，只用于correctness/shrinking；测试耗时不得写成runtime/memory/capacity结论，也不生成零值BenchmarkReport。

P2首次baseline必须记录`order-expansion.v1`、Import/quality/Snapshot/Problem hashes及instance/edge/candidate counts；以后改变ID/过滤/expansion cardinality必须回放固定Scenario Set。当前OR-Tools仍不存在，Solver replay无法执行，OPEN-012保持OPEN。

## TASK-P1-09 review

本Task首次形成真实PlanningProblem preprocessing与fixed Problem hash，但仍无Solver、Backend、BenchmarkRunner/profile、candidate result、runtime/memory threshold或历史Problem baseline comparison。Local Python 3.12.13 informational probe对同一1-resource/2-operation/1-edge/0-interval Snapshot执行200次完整build+verify，观察median `1.090 ms`、p95 `1.177 ms`；该单机微型sample只记录builder counts/time，不是CI gate、capacity、SLA或Production阈值，也不生成BenchmarkReport。

P2首次Solver baseline必须携带Snapshot/Problem hash、builder/hash projection、tick/horizon、instance/edge/candidate/interval counts、Solver exact version/parameters及环境。当前OR-Tools仍不存在，不能执行Solver correctness/quality/runtime/memory replay；OPEN-012继续OPEN，未建立或覆盖任何baseline。

## TASK-P2-01 review

本Task改变未来model input cardinality：v2固定sample包含1 delivery demand、1 capacity=1 Resource、1 active operation、1 historical anchor、1 precedence edge、2 active locks和0 calendar intervals；Problem hash/bytes digest已固定。它没有model variables/constraints、Solver、Reference Scheduler、BenchmarkRunner或runtime/memory/quality baseline，测试耗时不得解释为性能证据。

P2-12首次XS/S/M benchmark必须记录`planning-problem.v2`、builder/hash projection、Snapshot/Problem hashes及上述全部fact counts；任何后续Problem字段或projection变化触发fixed Scenario correctness与benchmark replay。OPEN-012继续OPEN，conditional CI hook仍deferred。

## TASK-P2-02 review

SolverReport v1固定未来Benchmark可引用的objective/bound/gap、model build/first feasible/solve/validation/total timing、variables/constraints/optional intervals、memory、exact solver parameters/version和完整input fingerprints。字段合同不包含阈值、baseline comparison或性能判定。

发布样例的零metrics/timing与not-installed solver只证明JSON/status条件，绝非一次benchmark。没有运行Solver/Reference Scheduler、没有新增profile或`run_benchmark.py`、conditional hook继续deferred，OPEN-012保持OPEN。P2-12必须用真实`SOLVER_RUN`、同一Problem/Validator/KPI和XS/S/M环境另行形成provider evidence。

## TASK-P2-03 foundation replay classification

首次solver exact pin触发ADR、lock、platform、status与API replay，但由于没有业务model/candidate/Validator，Benchmark结论为`NOT_APPLICABLE_FOUNDATION_ONLY`，不得记录零runtime baseline或quality comparison。Empty/model-invalid wall time只用于adapter diagnostics。Golden/Scenario/Reference Scheduler/XS/S/M、memory/quality regression和conditional benchmark hook仍由后续Task形成；OPEN-012保持OPEN。

## TASK-P2-05 core telemetry classification

Core report为tiny JSSP/FJSP记录variables、constraints、optional intervals、build/solve/native wall/first-feasible与Python traced peak memory；这些是correctness diagnostics，不是warm-up后的统计样本，不含XS/S/M、Reference Scheduler、quality delta或阈值。因此不得写入Benchmark baseline或触发regression判定。

CI中的conditional benchmark hook保持deferred。P2-12仍负责正式runner、profiles、runtime/memory/quality口径与回归门；OPEN-012保持OPEN。

## TASK-P2-06 temporal telemetry classification

Temporal report记录precedence、min/max、calendar input/fixed blocks、gate、conditional transport等constraint/model delta，以及tiny solve的build/solve/native wall/Python memory。数据仅说明约束确已进入模型并可观测，不经过warm-up、重复统计或Reference comparison。

因此不建立XS/S/M baseline、threshold、quality delta或conditional regression Gate。P2-12职责与OPEN-012保持不变。

## TASK-P2-07 fact/lock model delta only

Fact/lock report记录RUNNING/HARD/SOFT counts、fixed operation intervals、resource/start/end equality counts与相对无事实模型的6条constraint delta，并保存tiny solve build/solve/first-feasible/native wall/Python memory。6-case oracle只核对grid/horizon/calendar half-open feasibility。

这些值没有warm-up、重复统计、Reference comparison、stability objective或profile，不建立XS/S/M baseline、threshold、quality delta或conditional regression Gate。P2-12职责与OPEN-012保持不变。

## TASK-P2-08 objective correctness, not baseline

新machine report对4个tiny vectors同时运行Global Strategy与独立穷举oracle，要求objective=value=bound、gap=0并由formal Validator PASS；另有一个complete hard-domain certified INFEASIBLE。报告也保存单次build/first-feasible/solve/validation/model/memory值。

这些case未使用Reference Scheduler或versioned XS/S/M profile，未做warm-up、重复、分位数、hardware normalization、threshold或升级比较，因此只构成OBJ-001 correctness regression，不构成Benchmark baseline。P2-12与TEST-BENCHMARK仍PLANNED，OPEN-012不变。

## TASK-P2-10 Reference correctness, not comparison baseline

`reference-scheduler-report.v1`对五个versioned algorithms在七个tiny P2-09 Problem上记录35个Validator-PASS candidate及weighted tardiness/makespan/single-run runtime；另以5个blocked-calendar case证明`HEURISTIC_FAILURE`不泄漏partial schedule或不可行证书。该证据使Reference算法本身可回归，但没有Global Strategy comparison row。

没有修改`simulation/benchmarks/**`、`benchmarks/**`或`run_benchmark.py`，也没有warm-up、repeat、percentile、hardware normalization、XS/S/M profile、threshold或`BENCHMARK_WARNING`判定。因此TEST-BENCHMARK与REQ-014继续PLANNED，P2-12职责及OPEN-011/012保持不变；P2-10 runtime不得被追认为性能baseline。

## TASK-P2-11 output telemetry, not BenchmarkReport

KPI v2和冻结SolverReport保存同一validated run的objective/bound/gap、model build/first feasible/solve/validation/total、model size与memory；internal manifest固定这些payload的bytes和lineage。这只使单run输出可复验，不增加warm-up、repeat、percentile、hardware profile、Global/Reference comparison或threshold。

Manifest明确`benchmark_report.json=DEFERRED_P2_12`且文件不存在，禁止以空报告或单次timing冒充Benchmark。`simulation/benchmarks/**`、`benchmarks/**`及TEST-BENCHMARK均未修改，REQ-014、OPEN-011/012和P2-12职责保持不变。

## TASK-P2-12 versioned regression baseline

首次正式baseline为`p2-xs/s/m.v1.json`，分别绑定Problem hash `a70a0549…7b04`、`42ee217e…5bb4`、`a49ee150…26aa`、完整complexity projection、环境签名、Global objective/bound与runtime/memory观测、五Reference quality和development ceilings。文件只允许首次创建；更新profile/generator/Problem/KPI或观测基线必须新建版本，禁止CLI原地覆盖。

判定严格遵循correctness→status/feasibility→quality→runtime/memory→diagnostics。Problem/complexity漂移hard fail；所有Global/Reference candidate必须fresh Validator PASS且共享KPI一致；CP-SAT质量劣于Reference产生`BENCHMARK_WARNING`。跨环境不做相对性能回归，只应用非生产宽松ceiling；同一环境才比较2.5倍factor。当前XS/S/M本地报告均8/8 PASS、无warning，但这不关闭历史生产数据OPEN-011或生产阈值OPEN-012。

## TASK-P2-14 Exit audit replay

审计在Windows 11 AMD64/CPython 3.12.13/OR-Tools 9.15.6755环境独立生成XS/S/M三份`benchmark-report.v1`，Problem hashes与v1 baselines逐项一致，三份均8/8且0 warning；两次完整Gate又执行6个profile、18次Global measured、90次Reference measured和108次fresh Validator PASS。Baseline文件、Profile/Generator/KPI/runner与dependency均零差异；结果只支持P2 development READY，不更新baseline、不关闭OPEN-011/012，也不建立L/XL或Production threshold。
## TASK-P3-02 benchmark impact

本Task只在machine report记录七份Schema/七份sample的exact byte size与SHA、34份P2 frozen artifact count以及negative count；不新增timing、throughput、Gantt scale、DB/API/worker或Production threshold。P2 XS/S/M baseline与所有KPI/solver timings逐字保留，OPEN-011/012不受影响。

P3-09 machine report记录2 Schema/2 sample、12 payload、4 XLSX sheet、五state/六pair与focused count；单个synthetic package bytes/rows/sheets只用于development correctness，不新增latency/memory/throughput threshold。P2 XS/S/M baseline不改，OPEN-012继续OPEN，禁止外推Production package scale或worker SLA。
