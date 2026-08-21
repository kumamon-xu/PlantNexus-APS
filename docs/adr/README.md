---
doc_id: DOC-ADR-INDEX
title: Architecture Decision Records
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [97]
last_reviewed: 2026-08-21
---

# Architecture Decision Records

ADR 记录 Architecture、Solver Backend、Constraint semantics、Objective hierarchy、PlanningProblem、Schedule state machine、Data authority、Decomposition、Advanced APS capability 和 Production performance threshold 的决定。

ADR 状态：`proposed`、`accepted`、`rejected`、`superseded`。Accepted ADR 不重写历史；变更通过新 ADR `supersedes` 旧记录。

ADR-0001～0009 是从 implementation spec 0.3.0 已明确决定中建立的基线记录。ADR-0010是TASK-P2-01对PlanningProblem v2合同演进的新增决定；[ADR-0011](ADR-0011-ortools-9-15-cp-sat-backend-version-policy.md)是TASK-P2-03在首次Solver dependency前接受的OR-Tools exact-version、namespace与upgrade/replay决定。Accepted状态不表示后继约束、Validator或业务可行性已经实现。

TASK-P0-03 的 Schema/type skeleton 落实 ADR-0001（共同入口 envelope）、ADR-0003（Solver-neutral Problem）、ADR-0007（immutable Snapshot）、ADR-0008（UTC/seconds/ticks）和 ADR-0009（Production/Simulation 标识隔离）的既有决定，没有改变这些决定，因此不新增 ADR。Problem builder、hash、Solver 或字段权威若偏离这些决定，必须另建 ADR，不能借 skeleton 隐式修改。

TASK-P0-04 把总规既有 C-001～C-018、ADR-0005 独立 Validator 边界和 ADR-0007 ScheduleVersion 不可变/发布状态固定为 versioned rule/state contracts。没有改变 Constraint semantics、Schedule state machine、PlanningProblem、Solver backend 或发布规则，因此不新增 ADR。`EXPORT_FAILED → EXPORTING` 只是既有“可重试”合同的显式 pair；若未来改变 pair/guard、允许 published mutation、共享 Solver validator logic 或启用高级 capability，必须新建 superseding ADR。

TASK-P0-05 落实 ADR-0001（Generator 终止于 Standard Import）与 ADR-0009（synthetic flag/Production target rejection），没有改变共同入口或环境隔离决定；empty package 不绕过 P1 pipeline。Profile/Scenario/Generator versions、canonical hash 和 manifest 属于总规既定 provenance，不修改 PlanningProblem/Constraint/Solver/状态/Data Authority，因此不新增 ADR。若未来允许 Production target、Generator 直接产 Problem 或改变隔离层级，必须新建 superseding ADR。

TASK-P0-08 落实 ADR-0002 的 health API/Celery Worker 分进程骨架与 heartbeat/lease/attempt/idempotency 原语，以及 ADR-0009 的 environment/data-plane fail-closed config；不改变 Modular Monolith、Solver 分离或 Production/Simulation 隔离决定，因此不新增 ADR。当前 Worker 无 Solver/业务 task，Compose 也不是 production deployment；若未来共享 API process 执行 Solver、允许 production Simulation route、降低 DB 隔离、改变 Job/Export state semantics 或引入分布式 topology，必须另建 ADR。OR-Tools 未安装，Solver upgrade ADR/Gate 不触发。

TASK-P1-02以schema set`2.0.0`落实ADR-0007的immutable Snapshot事实边界、ADR-0008的UTC/整数秒语义与ADR-0009的Production/Synthetic provenance隔离，并保留ADR-0003的Solver-neutral consumer边界。它没有改变这些已接受决定，也没有决定外部字段权威、hash算法、persistence或Solver，因此不新增ADR。若后续允许Production携带synthetic provenance、修改UTC/seconds、原地改写Snapshot或隐藏source mapping，必须先建立superseding ADR。

TASK-P1-04落实总规§9/§95和ADR-0001的共同文件入口边界：Reference Adapter只形成Raw Staging，不能绕过后续Normalization/DataValidation；Production/Simulation provenance继续服从ADR-0009。固定三列reference transport、read-only XLSX与安全限额不改变Architecture/Data Authority/PlanningProblem/Solver/状态/发布决定，因此不新增ADR。若未来把它声明为真实系统authority、允许macro/formula/external execution、让Adapter直接产Canonical/Snapshot或降低data-plane隔离，必须先提交相应superseding ADR与授权证据。

TASK-P1-05落实ADR-0001共同入口、ADR-0008 UTC/整数秒/tick边界和ADR-0009 Production/Simulation隔离，并按既有canonical-json/SHA-256决定生成Import bytes/hash。Additive schema set`2.1.0`只新增unit registry，Import v2/canonical-records.v1合同不改；没有改变Architecture、Data Authority、Snapshot/Problem、Solver或发布决定，因此不新增ADR。若未来允许隐式unit/timezone/default、浮点duration rounding、隐藏mapping version或绕过Data Validation，必须先提交superseding ADR与授权证据。

TASK-P1-06落实ADR-0001共同入口中的Data Validation门、ADR-0008 UTC/整数秒边界与ADR-0009统一Production/Simulation canonical evaluator；additive schema set`2.2.0`只新增Error/quality-report合同，未改变Import/Snapshot/PlanningProblem、C-ID、ScheduleValidator独立性、Solver或发布决定，因此不新增ADR。若未来允许Simulation跳过quality Gate、让evaluator修复/默认输入、共享Solver/ScheduleValidator逻辑或改变report hash/版本兼容，必须先提交superseding ADR与对应回放证据。

TASK-P1-07落实ADR-0001的共同入口顺序、ADR-0003的Solver-neutral派生边界、ADR-0007的Snapshot前事实准备、ADR-0008的显式整数秒copy和ADR-0009的Production/Synthetic provenance隔离。`order-expansion.v1`只把DataValidation PASS后的显式Lot/Routing展开为既有Snapshot v2 shape，不改变Schema、PlanningProblem、Constraint、Solver、状态机、发布规则或Data Authority，因此不新增ADR。若未来自动split/merge、重算candidate duration、丢弃COMPLETED事实或改变versioned ID lineage，必须先建立相应ADR/Schema/回放证据。

TASK-P1-09落实ADR-0003的solver-neutral deterministic Problem、ADR-0007的immutable Snapshot consumer和ADR-0008的UTC/权威秒/显式tick决定。`planning-problem.v1` Schema与C-ID不变，builder/hash只在既有可表达slice内工作；active lock、multi-factory和completed-active historical lag不能表达时明确停止，不修改Backend/Strategy/Validator或引入OR-Tools，因此不新增ADR。若未来扩展Problem字段、改变builder/hash语义、隐藏unsupported事实或让Backend绕过canonical Problem，必须先提交相应superseding/new ADR与replay/benchmark证据。

TASK-P2-00只批准阶段与Task治理，不作技术决定。TASK-P2-01已接受[ADR-0010](ADR-0010-planning-problem-v2-contract-evolution.md)：新增非互换Problem v2，明确active locks、sourced due/priority、capacity=1 Resources、completed-active historical anchor及v1默认兼容/hash策略，同时保持ADR-0003 solver-neutral边界。它不决定Solver/Validator行为或Production authority。P2-03在首次安装OR-Tools前仍必须建立exact-version/upgrade-replay ADR；后续Task严格实施ADR-0004/0005/0006/0008。

TASK-P2-02严格实施ADR-0003的solver-neutral Protocol、ADR-0006的Delivery-first阶段边界、ADR-0008的UTC/seconds/ticks和既有PlanningRun/error语义；只固定Policy/Limits/Solution/Report v1与status mapping，没有改变目标顺序、状态含义、time unit或Backend/Validator职责，因此不新增ADR。OBJ-002/003继续deferred，OR-Tools仍未安装。若后继实现改变七种status映射、混合目标、默认limits、fingerprint语义或让Solver contract绕过independent Validator，必须停止并建立superseding/new ADR。

TASK-P2-03在任何dependency变更前接受ADR-0011：选择官方稳定`ortools==9.15.6755` binary wheel/exact lock，把OR-Tools对象限定于`planning/backends/cp_sat`，固定SolveLimits参数来源、native/adapter status映射、engineering smoke非业务可行性及后续upgrade Gate。该决定落实ADR-0003/0004，不修改P2-02合同字节，也不授权C-ID、OBJ-001 execution、Validator、Benchmark baseline或Production SLA。

TASK-P2-04严格实施ADR-0005的独立ScheduleValidator与ADR-0008的UTC/整数秒/tick语义：Validator直接从Problem/Solution事实重算C-001～C-011，禁止Backend/OR-Tools/constraint builder共享和solver status信任。实现未改变Schema、C-ID语义、dependency、objective或状态机，因此不新增ADR；若后继工作共享Solver约束逻辑、改变RUNNING/lock/duration语义或允许status绕过Validator，必须先提交superseding/new ADR。

TASK-P2-05按ADR-0003/0004/0005/0008/0011实现bounded core：OR-Tools仍exact-pinned且限定于CP-SAT namespace，five-C-ID模型与formal Validator保持独立，UTC/tick/duration沿既有合同，纯可行native OPTIMAL不升格为业务最优。没有Schema、rule语义、dependency、Strategy或objective policy变化，因此不新增ADR；若后续允许静默忽略future facts、共享Validator/solver constraint实现、改变capacity/tick语义或在P2-08前引入目标搜索，必须先提交新ADR。

TASK-P2-06严格落实ADR-0003/0004/0005/0008/0011：权威整数秒到tick分别使用exact ceil/floor，calendar保持half-open grid equivalence，transport按selected/historical workshop独立条件化，Solver与formal Validator继续隔离。Problem/Solution Schema、rule公式、Builder/hash、dependency与objective policy均未改变，因此不新增ADR；若未来改为浮点/隐式rounding、把min与transport相加、改变calendar/lag语义或共享Validator builder，必须停止并提交superseding/new ADR。

TASK-P2-07严格落实ADR-0003/0004/0005/0007/0008/0011：immutable Problem identity保存execution/lock facts，RUNNING/HARD tuple不可移动，SOFT不硬化，Solver与formal Validator继续隔离。Problem/Solution Schema、rule公式、Builder/hash、dependency、objective policy与ScheduleVersion状态均未改变，因此不新增ADR；若未来猜造execution fact ID、移动RUNNING/HARD、把SOFT当constraint/hint、引入freeze/stability/dynamic Replan语义或共享Validator builder，必须停止并提交superseding/new ADR。

TASK-P2-08严格落实ADR-0004/0006并保持ADR-0003/0005/0008/0011：GlobalCpSatStrategy只构建一次完整模型，唯一接受目标为OBJ-001 priority-weighted tardiness，candidate必须经独立Validator，OR-Tools exact pin/namespace与UTC/seconds/ticks不变。显式Simulation Policy/Limits不构成Production authority，OBJ-002/003继续deferred；Schema、Problem、Validator、C-ID公式、dependency与目标层级均未改变，因此不新增ADR。若未来混合目标、改变lexicographic顺序、引入decomposition/fallback、猜测Production权重/default或允许status绕过Validator，必须先提交superseding/new ADR。

TASK-P2-09严格落实ADR-0003/0004/0005/0006/0008/0011：versioned Scenario只经公开Import→Snapshot→Problem进入单Global model，Solver candidate由独立Validator复验，OBJ-001/UTC/tick/solver pin不变。Fixture-local blueprint/catalog/manifest是evidence contract，不改变发布Schema、Planning/Validator/constraint/objective语义或dependency，因此不新增ADR。若未来直接构造Problem/CpModel、改变expected来隐藏回归、混入Benchmark/Production default或修改目标/约束，必须先停止并提交对应ADR/versioned contract change。

TASK-P2-11继续落实ADR-0003/0005/0007/0008：reporting/export只消费solver-neutral immutable documents，SolverReport与formal Validator绑定，canonical UTC/seconds/ticks不改，validated PlanningSolution不冒充ScheduleVersion。Additive KPI/manifest合同和本地原子目录materialization未引入状态持久化、外部storage、approval或publish，也未改变module topology/dependency，因此不新增ADR。若未来创建ExportJob/ScheduleVersion、允许publish/external transfer、改变package identity/canonicalization或把ChangeReport提前到P2，必须停止并由P3/P4 Task及新/取代ADR治理。

TASK-P2-12继续落实ADR-0002/0003/0004/0005/0006/0008/0011：Benchmark位于预留Simulation模块，只经solver-neutral Problem/Global Strategy/formal Validator/public KPI/Exporter；OR-Tools exact pin、单Global模型、OBJ-001、UTC/tick与Validator隔离均不变。三个internal v1 evidence合同、existing PyYAML dev工具和CI XS activation不改变架构、Schema、dependency或Production policy，因此不新增ADR。若未来引入decomposition/fallback、Production threshold/default、L/XL release gate、外部Benchmark service、持久化报告合同或共享Solver/Validator实现，必须停止并提交new/superseding ADR。
