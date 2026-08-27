---
doc_id: DOC-ADR-INDEX
title: Architecture Decision Records
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [97]
last_reviewed: 2026-08-27
---

# Architecture Decision Records

## TASK-P4-02 conformance review

本Task不新增或修改ADR。Additive `2.8.0` carrier逐项实现ADR-0013的event authority/order/Replan lineage、ADR-0014的half-open freeze/四元OBJ-002/complete ChangeReport，以及ADR-0015的Simulation manifest/common-path boundary；35/7负例用于拒绝语义漂移。若后继需要改变这些决定，必须先提交superseding ADR，不能修改既有Schema含义。

## TASK-P4-01 ADR decisions

TASK-P4-01启动时registry precheck确认`ADR-0013`～`ADR-0015`未占用，并已在任何P4 Schema、migration、dependency或业务代码前接受三份独立决定：

- [ADR-0013](ADR-0013-execution-event-authority-fact-projection-replan-lineage.md)：唯一versioned ExecutionEvent入口、Production authority default-deny、source-position ordering、append-only ledger、确定性fact→new Snapshot投影、ReplanRequest无独立状态机及new DRAFT lineage；
- [ADR-0014](ADR-0014-freeze-window-stability-change-report.md)：Snapshot cutoff锚定的half-open freeze、fact/HARD/effective-lock优先级、Delivery→OBJ-002→Makespan、整数Stability向量与完整可复算ChangeReport；
- [ADR-0015](ADR-0015-deterministic-execution-simulator-common-path.md)：Simulator只生成标准ExecutionEvent、virtual clock/seed/version确定性、同一入口、连续五类异常和Production隔离。

三份ADR均为`accepted`，不改写ADR-0001～0012。它们只冻结人类语义，TASK-P4-02仍须独立发布机器Schema/compatibility，P4-03+仍须逐Task授权；当前没有P4行为、Production event authority、external integration、capacity或SLA形成。

## TASK-P3-15 / TASK-P3-16 ADR impact review

阶段计划修订治理、`official-zh-cn-terminology.v1`与TASK-P3-16 Frontend双语展示继续遵循ADR-0002/0005/0007/0009/0012；typed display dictionaries、local non-sensitive locale preference和英文machine contract zero drift已按既有决定实现并由exact implementation provider复验，没有改变模块、authority、state、persistence、Schema、dependency或Production决策，因此ADR impact为`none`，accepted ADR正文保持逐字只读。若未来需要server locale negotiation、新dependency、localized wire value、client authority或新state pair，必须停止并先走独立ADR/治理审查。

## TASK-P3-14 ADR review

Gate编排继续严格遵循accepted ADR-0002/0005/0007/0009/0012：模块边界、独立Validator、immutable ScheduleVersion、Simulation隔离与server-authority command/state/publication均不变。三份状态文档只记录既有pair的Gate复验，未增加或修改state pair、authority、Schema、persistence、dependency或P4/Production决策，因此无需新ADR；任何Gate发现的业务偏差必须登记remediation而不能在Gate内改写ADR或实现。

## TASK-P3-13 ADR review

实现继续遵循accepted ADR-0012：server authority、copy-on-write new Version、existing state pairs、Production default-deny、approved-only internal publish、Publish/Export分离、append-only audit和React/TypeScript Frontend。Additive binary download只暴露verified existing artifact，不改变架构决策、Schema或persistence，因此本Task无需新ADR。

若引入Production identity/role、external/MES/object storage、client authority、streaming contract、新state pair、P4 Replan或新增dependency，必须先获明确授权并新建或修订ADR；不得从本Task的Simulation E2E/ZIP transport推导批准。

ADR 记录 Architecture、Solver Backend、Constraint semantics、Objective hierarchy、PlanningProblem、Schedule state machine、Data authority、Decomposition、Advanced APS capability 和 Production performance threshold 的决定。

ADR 状态：`proposed`、`accepted`、`rejected`、`superseded`。Accepted ADR 不重写历史；变更通过新 ADR `supersedes` 旧记录。

ADR-0001～0009 是从 implementation spec 0.3.0 已明确决定中建立的基线记录。ADR-0010是TASK-P2-01对PlanningProblem v2合同演进的新增决定；[ADR-0011](ADR-0011-ortools-9-15-cp-sat-backend-version-policy.md)是TASK-P2-03在首次Solver dependency前接受的OR-Tools exact-version、namespace与upgrade/replay决定；[ADR-0012](ADR-0012-planning-workspace-command-state-publication.md)是TASK-P3-01在任何P3 Schema/代码前接受的Workspace command/state/publication决定；ADR-0013～0015是TASK-P4-01在任何P4 Schema/代码前接受的dynamic replanning基线。Accepted状态不表示后继Schema、持久化、行为或Production authority已经实现。

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

## TASK-P3-01 ADR decision

TASK-P3-01以当时下一个未使用编号接受ADR-0012，决定command-only/copy-on-write edit/lock→new DRAFT、ScheduleVersion content immutability、authority-neutral/default-deny authorization、APPROVED-only idempotent internal publish、Publish/Export分离、append-only audit、domain→repository→application→API/jobs→frontend依赖方向，以及React/TypeScript/Ant Design/TanStack Query + npm/Vite/Vitest/Testing Library/Playwright组合。该决定不修改既有state pair、Schema、migration、dependency/lock或业务实现，也不关闭OPEN-002/010/015。

若实际需要新state/pair、identity provider、outbox、external storage/MES、SSR/microfrontend、mutable Version或P4语义，必须另建new/superseding ADR；不得修改ADR-0002/0005/0007/0009/0012历史事实。
## TASK-P3-02 ADR conformance

本Task无需新ADR：七份v1 carrier逐项实现accepted ADR-0012的append-only/copy-on-write shape、query/command分离、既有state/pair、capability/default-deny边界、approve/publish/export分离、idempotency/audit同一致性要求和P3/P4/Production边界。它没有执行这些行为或改变transaction topology；发现语义缺口时仍必须先提交superseding ADR，不能私改Schema。ADR-0007/0009的immutability/provenance与ADR-0012均保持accepted。

## TASK-P3-03 ADR conformance

`0004`与repositories直接实现ADR-0002/0007/0009/0012已经接受的modular repository、immutable version、provenance、append-only/idempotency/CAS边界；没有引入outbox、event bus、external storage、new state/pair或不同transaction topology，因此不需新ADR。Storage-only state/reference revision和显式lease expiry不改变carrier/state语义，也没有DB业务默认。

若P3-04+需要公开lease expiry、新outbox/exactly-once、mutable PUBLISHED content、cross-plane current、external target或新pair，必须先停止并新建/supersede ADR与Schema；现有ADR历史事实不改写。

## TASK-P3-04 ADR conformance

本Task直接落实ADR-0005的independent Validator、ADR-0007的immutable version/provenance与ADR-0012的command-only/application transaction/append-only audit：validated output复制成DRAFT，既有pair推进READY，content/lineage不变，same-key replay/conflict稳定。没有新state/pair、mutable Version、outbox、external target、authorization provider或topology，因此不需新ADR。

若后续需要跳过DRAFT、允许READY覆盖Validator FAIL、把COMPLETED视为approval、修改audit历史、跨plane identity、outbox/exactly-once或外部side effect，必须停止并新建/supersede ADR；不得改写现有accepted历史。

## TASK-P3-06 ADR conformance

本Task直接落实ADR-0005的independent Validator、ADR-0007的immutable version/provenance与ADR-0012的server command/copy-on-write new DRAFT/idempotency/atomic audit：四类content command只insert派生DRAFT，显式`SUBMIT_FOR_REVIEW`在第二次fresh PASS后以既有pair把同一manual DRAFT推进`READY_FOR_REVIEW`，content/identity不变；PUBLISHED/current不变，failed candidate丢弃。没有新state/pair、Schema、mutable content、Solver/Replan、outbox、external target、authorization provider或topology，因此不需新ADR。

若未来允许原地edit/PUBLISHED update、command触发Solver/P4、failed Version持久化、跨事务attempt/outbox或Production identity/target，必须停止并新建/supersede ADR；不得改写上述accepted历史。

## TASK-P3-07 ADR review

本Task直接落实ADR-0007的immutable Version/provenance、ADR-0009的同事务state+audit边界与ADR-0012的authority-neutral capability、Production default-deny、READY-only approve/reject和append-only audit。实现只组合既有Schema、state pair和repository CAS/append ports；没有新增state/pair、Schema/migration/dependency、real role mapping、external side effect或topology，因此不需新ADR。

若未来允许Production actor fallback、client/UI自报authority、decision绕过READY/fingerprint、跨事务成功audit、修改/删除历史decision，或把approve自动扩张为publish/export，必须停止并新建或supersede ADR；OPEN-010未关闭前不得用test policy替代该决定。

## TASK-P3-08 ADR review

本Task直接落实ADR-0007的immutable Version/provenance、ADR-0009的state/result/current/audit同事务边界及ADR-0012的APPROVED-only internal Publish、Publish/Export分离、idempotent replay、current/supersession与Production default-deny。实现只组合既有Schema、state pair与repository ports；没有新增state/pair、Schema/migration/dependency、outbox/external target或topology，因此不需新ADR。

若未来允许mutable PUBLISHED/SUPERSEDED content、rollback/delete publication history、cross-plane current、automatic Export/external delivery、跨事务成功或Production target fallback，必须停止并新建/supersede ADR与authority；不得改写accepted历史。

TASK-P3-09落实ADR-0002/0007/0009与accepted ADR-0012：internal-only、deterministic canonical artifacts、显式state/idempotency/audit和Version authority。Additive v2 carrier是已批准的兼容性修复，不改变storage topology、external adapter或state machine，故不新建ADR。若引入cloud/object storage、Celery topology/outbox、external MES/ERP、automatic retry policy、P4 ChangeReport或Production target，必须先停止并创建/取代ADR。

## TASK-P3-10 ADR review

本Task落实ADR-0002/0009与accepted ADR-0012的thin API、Version authority、server authorization/default-deny、strict command/idempotency/audit边界，不改Schema、state machine、identity model、storage/network topology或dependency，故不新建ADR。若引入API gateway、OIDC/SSO/RBAC provider、session model、async/outbox、external endpoint、P4 route或Production deployment，必须先停止并创建/取代ADR。

## TASK-P3-11 ADR review

实现直接落实accepted ADR-0012选择的React/TypeScript/Ant Design/TanStack Query/npm/Vite/Vitest/Playwright stack与server-authority/read-only边界；具体版本属于Task-local exact dependency Gate，不改变架构选择。Frontend不引入SSR/microfrontend、Schema interpreter、client Solver/Validator、identity topology、command/state transition、external target或Production hosting，因此不需新ADR。

Implementation artifact `9552386549`已复验该实现边界；`typescript-eslint=8.68.0`兼容组仍是Task-local fixed gate，不构成新架构选择。ADR-0012保持`accepted`，P3-12/13或Production拓扑变化仍须按Impact Rule重新审查。

若P3-12/13拟改变stack、安装新的Gantt/E2E/runtime dependency、引入browser authority/session persistence、SSR/microfrontend或Production deployment topology，必须先执行独立dependency/ADR review；不得把本Task的Playwright pin解释为browser E2E已形成。
