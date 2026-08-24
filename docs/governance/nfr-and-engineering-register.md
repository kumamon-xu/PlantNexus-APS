---
doc_id: DOC-GOV-003
title: NFR 与工程需求注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [4, 6, 16, 23, 24, 29, 30, 42, 58, 62, 65, 66, 89, 93, 95]
last_reviewed: 2026-08-24
registry_version: 1.0.0
---

# NFR 与工程需求注册表

以下 ID 是对总规已有非功能要求的稳定化登记，不引入尚未确认的性能数值。

| ID | ID status | 要求 | 可验证标准 |
|---|---|---|---|
| NFR-COR-001 | ALLOCATED | 进入评审的计划无硬约束违反 | `hard_violation_count == 0` |
| NFR-DET-001 | ALLOCATED | Snapshot、Problem 和 Synthetic Dataset 可确定性重放 | 同输入、版本和 seed 得到同 hash |
| NFR-TRC-001 | ALLOCATED | 全链路可追溯 | 成果 manifest 包含所需版本和来源 |
| NFR-ISO-001 | ALLOCATED | Production 与 Simulation 数据隔离 | 独立数据库；生产禁用 Simulation API |
| NFR-REL-001 | ALLOCATED | 长任务故障可检测、可重试 | heartbeat、lease、attempt、STALLED、idempotency |
| NFR-SEC-001 | ALLOCATED | 导入、Secret 和外部执行安全 | 格式/大小限制，不执行宏/公式，不拼接 SQL/shell |
| NFR-OBS-001 | ALLOCATED | PlanningRun 可观测 | 记录模型规模、耗时、目标、bound、gap、内存和验证时间 |
| NFR-PER-001 | ALLOCATED | 性能通过分级 Benchmark 管理 | PR/ Nightly/ Release profiles；当前不设生产 SLA |
| NFR-HUM-001 | ALLOCATED | 发布受人工控制 | 仅 APPROVED 可发布，自动发布禁止 |
| ENG-ARCH-001 | ALLOCATED | 采用 Modular Monolith | Solver Worker 与 API Process 分离 |
| ENG-SOL-001 | ALLOCATED | 领域层 Solver-neutral | OR-Tools 类型不进入 domain/PlanningProblem |
| ENG-VAL-001 | ALLOCATED | Validator 独立实现 | 不导入/复用 CpSatBackend 约束代码 |
| ENG-ERR-001 | ALLOCATED | 错误语义可区分 | DATA_ERROR 等七类错误不统一映射 500 |
| ENG-VER-001 | ALLOCATED | Schema、Solver、Simulation 版本化 | 修改触发 lock/replay/migration/contract test |
| ENG-LOG-001 | ALLOCATED | 结构化日志可关联到运行与来源 | 日志携带稳定 run/correlation 标识且不成为唯一 provenance 载体 |

`NFR-PER-001` 只规定测量机制。生产运行时间、内存和规模阈值属于 `OPEN-012`，在 P7 以前不得填入承诺值。

`ENG-LOG-001` 补齐总规追踪示例和 Observability/Provenance 对日志关联能力的既有要求，不表示 logging 实现已经形成。与 REQ 相同，`ALLOCATED` 仅表示 ID 稳定；删除、复用或改变 ID 含义必须保留历史并提升 `registry_version`。

TASK-P0-03 review：NFR-DET-001/NFR-TRC-001 与 ENG-SOL-001/ENG-VER-001 已链接 Schema `1.0.0`、纯类型和 TEST-CONTRACT-001；canonical hash/replay、run manifest、Problem builder 和 Solver 仍为 `PLANNED`。其余 NFR/ENG 含义和全部 `ALLOCATED` 状态不变。

TASK-P0-04 review：NFR-COR-001/ENG-VAL-001 获得 C-001～C-011 rule metadata、validation-report.v2 与独立 import-boundary/completeness tests，但没有 schedule evaluator/mutation PASS；NFR-REL-001/NFR-HUM-001 只获得 ExportJob/ScheduleVersion transition contract，不是 Worker/审批/发布实现；ENG-ERR-001 获得七类/19 code 唯一映射；ENG-VER-001 获得 additive schema set `1.1.0`、v1 preservation 和 contract tests。全部根 ID 仍为 `ALLOCATED`，registry format version 不变。

TASK-P0-05 review：NFR-DET-001 获得 empty Standard Import canonical bytes/hash 与命名 layer seed replay；NFR-ISO-001 获得 synthetic Schema/context/Import target guard；NFR-TRC-001 获得 ScenarioManifest v1；ENG-VER-001 获得 additive schema set `1.2.0`、独立 Profile/Scenario/Generator versions 与 compatibility tests。非空 dataset、Snapshot/Problem hash、独立 DB/API/publish isolation 和 run/code-commit audit 均仍 `PLANNED`；全部根 ID 保持 `ALLOCATED`，registry format version不变。

TASK-P0-06 review：NFR-COR-001 获得人工可复算的 positive Golden、11 个 C-ID 完整期望与 hard violation count 0；NFR-DET-001 获得非空 Import canonical hash replay；NFR-TRC-001 获得 Profile/Scenario/Generator/seed/package/hash/assumption chain。ENG-VAL-001 只由 test-local 独立公式和 loader 无 Planning/Solver import boundary 加强，尚无 reusable evaluator/mutation rejection；ENG-VER-001 获得 fixture asset versions 而 schema set 仍为 `1.2.0`。所有根 ID 保持 `ALLOCATED`，registry format version 不变。

TASK-P0-07 review：NFR-COR-001 获得 positive count=0 与 13 mutation exact negative outcomes；ENG-VAL-001 获得不导入 planning backend/OR-Tools、不读取 expected artifact 的 fixture-local evaluator、formula-free mutation materializer 和 dependency tests；ENG-ERR-001 获得每个 failed report 到 `VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED` 的结构化 v2 details/schema evidence。P2 正式输入、规模/performance、Solver comparison、HTTP/persistence 仍 `PLANNED`；所有根 ID 保持 `ALLOCATED`，registry format version 不变。

TASK-P0-08 review：NFR-ISO-001 获得 environment/data-plane Production fail-closed 与 health-only no-Simulation-route slice；NFR-REL-001/TEST-IDEMPOTENCY 获得 generic lease/heartbeat/attempt/STALLED/replay-conflict/migration tests；NFR-SEC-001 获得 env-only Secret、recursive log/health no-leak、exact dependency/non-root container tests；NFR-OBS-001/ENG-LOG-001 获得 JSON correlation/run/job + OpenTelemetry IDs 与 TEST-OBS-001；NFR-PER-001 只获得 deferred PR hook；ENG-ARCH-001 获得 API/Worker process skeleton；ENG-VER-001 获得 exact runtime/lock/build commit metadata且 schema set 不变。真实独立 production/simulation DB、auth/import controls、distributed job repository/crash recovery、PlanningRun metrics/audit、Benchmark/production threshold/Solver Worker/production deployment 均 `PLANNED`。所有根 ID 继续 `ALLOCATED`，registry format version 不变。

TASK-P0-09 review：9 个 NFR 与 6 个 ENG root 的 P0 链路均经 90 tests、五类 machine reports、build/governance 和 no-Solver gate 重放；NFR-COR/DET/TRC 与 ENG-VAL/ERR/SOL 的 contract/correctness slice、NFR-ISO/REL/SEC/OBS 与 ENG-ARCH/VER/LOG 的 engineering slice均保持 formed。NFR-PER-001 仍只有 deferred PR hook；workflow handoff `FAIL` 且 external provider run/required check `NOT_RUN`，所以 CI Gate `FAIL`、P0 总体 `NOT_READY`。没有生产、distributed、Solver、Benchmark 或 P1/P2+ 新能力；全部根 ID继续 `ALLOCATED`，registry format version不变，planned TASK-P0-10 承接两项 CI 缺口。

TASK-P0-10 review：NFR-TRC-001/ENG-VER-001 已获得 immutable diff base、GitHub run `32228647627` / head SHA / successful job、artifact `9356432918` digest 和 protected `main` required `validate` 证据；ENG-ARCH-001 的未弱化 workflow 交接由 integration contract 保护；NFR-PER-001 的 conditional hook 保持 deferred，未产生 BenchmarkReport 或性能承诺。本 Task 不改 runtime/Secret/Production 语义，不提升任何 root ID 状态；全部 NFR/ENG 仍为 `ALLOCATED`，registry format version 不变。

P1 Task 规划 review：TASK-P1-01～TASK-P1-11 已将 phase-aware governance、deterministic normalization/expansion/hash、provenance、Production/Synthetic 隔离、安全导入、模块边界、错误语义与版本兼容分别分配给 NFR-DET/TRC/ISO/COR/REL/SEC/PER 及 ENG-ARCH/SOL/ERR/VER；TASK-P1-12 仅审计证据。规划不等于实现或验收，所有 NFR/ENG 根 ID 继续 `ALLOCATED`，registry format version不变。

TASK-P1-01 review：NFR-TRC-001/ENG-VER-001 获得 current-phase policy、immutable event-base Task discovery、Task-card Diff base分层与 `traceability-report.v1.task_discovery_base`；ENG-ARCH-001 获得不再绑定P0-10的workflow/integration contract，并由completion commit `2d2a4432aa42e4f38ee8ae736e2acf2df1c694b9`的GitHub run `32237649319`、successful `validate` job和artifact `9359554539`形成provider evidence；NFR-PER-001的conditional Benchmark hook保持且没有runner/Solver结果。该证据只形成治理/CI contract，不形成P1数据链、BenchmarkReport或生产能力；所有NFR/ENG仍为`ALLOCATED`，registry format version不变。

TASK-P1-02 review：NFR-DET-001/NFR-TRC-001获得strict version/source/UTC/unit/duration/reference/provenance合同与fixed round-trip evidence；ENG-SOL-001保持domain/Snapshot types无ORM/API/OR-Tools；ENG-ERR-001获得复用既有code的pure precheck负例；ENG-VER-001获得schema set`2.0.0`、v1 fingerprint与explicit rejection compatibility。尚无canonical/hash builder、完整DataValidation、Solver或Production evidence；全部NFR/ENG仍为`ALLOCATED`，registry format version不变。

TASK-P1-03 review：NFR-TRC/REL获得source/version/digest/location/received-at持久化、durable exact replay/conflict与transaction rollback；NFR-ISO获得repository/DB plane guard和synthetic provenance conditional；NFR-SEC获得leaf source name、opaque bytes、parameterized SQL和sanitized no-leak error slice；ENG-ARCH保持Importer pure contract与Infrastructure adapter分层；ENG-ERR分配module-local staging code而不改19项产品registry；ENG-VER获得`0002_raw_import_staging`及empty/populated migration replay。独立Production数据库、真实PostgreSQL并发/安全、Adapter/pipeline/Worker仍PLANNED；全部root继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-04 review：NFR-TRC获得versioned source/adapter manifest、actual file/row digest和location；NFR-SEC获得root-contained path、type/size/row/column/sheet/archive limits及encoding/formula/macro/external-link/XML拒绝；NFR-REL获得Reference batch通过durable repository的exact replay/conflict slice。ENG-ARCH获得reader→adapter→Raw Staging单向边界，ENG-ERR获得sanitized module-local DATA_ERROR，ENG-VER获得Reference Adapter`1.0.0`及exact openpyxl/defusedxml lock。真实Production binding、malware/auth/independent DB、Normalization/pipeline/Worker仍PLANNED；全部root继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-05 review：NFR-DET获得row/input order及volatile staging metadata不影响Import bytes/hash、mapping version mutation改变hash；NFR-TRC获得source/profile/unit/canonicalization version与stable record source；ENG-ERR获得sanitized NormalizationError及unit/missing-duration/time/duplicate exact rejection；ENG-VER获得additive schema set`2.1.0`、unit registry v1与两份既有Schema fingerprint preservation。Snapshot/Problem replay、multi-error quality report、Production authority和完整common ingress仍PLANNED；全部root继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-06 review：NFR-COR获得canonical input四类exact拒绝与multi-error negative evidence；NFR-DET获得同issue/重排输入的report bytes/ID replay；NFR-TRC获得Error v3 entity/field/observed/expected/source/action链。ENG-ERR获得additive registry v2/Error v3/ImportQualityReport v1与count/status/identity invariant，ENG-VER获得schema set`2.2.0`、历史artifact fingerprints和显式consumer版本；无ScheduleValidator/Solver/HTTP/persistence/Production声明。全部root继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-07 review：NFR-DET获得固定version/input与collection重排下相同instance/edge bytes/hash，NFR-TRC获得Import/quality/source/synthetic与lot-operation/edge lineage；ENG-SOL保持pure JSON-compatible output且无Planning/OR-Tools，ENG-ERR获得module-local exact missing/fact/lock/version与SPLIT_MERGE拒绝而产品registry不变，ENG-VER获得`order-expansion.v1`和exact dev-only Hypothesis lock。Snapshot/Problem/common-ingress/P2 Property/Solver/Production仍PLANNED；全部root继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-08 review：NFR-DET/TRC获得Snapshot complete bytes/hash/ID replay、fact/cutoff/version mutation与full provenance；NFR-ISO获得synthetic conditional和plane-scoped repository负例；NFR-REL获得atomic insert/exact replay、identity conflict和DB mutation trigger。ENG-SOL保持Snapshot无Planning/OR-Tools，ENG-ERR使用module-local stable rejection，ENG-VER获得`snapshot-hash-projection.v1`与`0003_planning_snapshots` reversible migration。独立Production/Simulation DB、PostgreSQL concurrency/roles、Problem/common ingress、Solver/Benchmark仍PLANNED；全部root继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-09 review：NFR-DET获得same Snapshot/config/version的Problem complete bytes/hash replay及order/self/noise、fact/tick/horizon/version sensitivity；NFR-TRC获得Snapshot ID、builder/hash projection、Problem hash和fixed Golden bytes链。ENG-SOL获得pure solver-neutral Problem且source scan无OR-Tools/ORM/API/Infrastructure，ENG-ERR获得module-local DATA_ERROR/UNSUPPORTED_CAPABILITY/MODEL_INVALID且不产INFEASIBLE，ENG-VER获得`planning-problem-builder.v1`与`planning-problem-hash-projection.v1`。无Backend/Solver/Validator/Benchmark/common ingress/Production阈值；全部root继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-10 review：NFR-DET获得same Profile/Scenario/generator/seed的49-record Import bytes/hash replay、named-seed/call-order及seed/profile/version sensitivity；NFR-TRC获得source/mapping/unit/quality/manifest/package/hash链；NFR-ISO获得Production target拒绝和synthetic staging provenance slice。ENG-ARCH以公开Normalization/DataValidation及AST no-later-layer scan保持单向边界，ENG-ERR获得sanitized generator-local rejection，ENG-VER获得generator/mapping/manifest/asset version和`cycle_seconds_per_unit`既有duration compatibility regression。无common ingress、独立Production DB、Solver/Benchmark/Production evidence；全部root继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-11 review：NFR-COR获得四类input Gate exact DATA_ERROR；NFR-DET/TRC获得Reference/Synthetic与两次Scenario replay的Import/Snapshot/Problem bytes/hash、全版本和machine report；NFR-ISO获得application expected-plane guard；NFR-REL/SEC复验既有staging idempotency/transaction和Reference bounded reader。ENG-ARCH以公开单向边界/AST scan形成application orchestration，ENG-SOL保持Problem终止且无OR-Tools，ENG-ERR保留stage exact code，ENG-VER记录全链版本而不改Schema/dependency。独立Production DB/API、Solver/Validator/Benchmark仍未形成；全部根ID保持`ALLOCATED`，registry format version不变。

TASK-P1-12 review：NFR-COR/DET/TRC的P1数据链、NFR-ISO/REL/SEC既有guards，以及ENG-ARCH/SOL/ERR/VER边界由full tests、machine reports、exact provider artifacts和docs治理独立复核为PASS。代码/dependency扫描无OR-Tools/CpModel/IntervalVar，current phase仍P1。NFR-PER仍只有conditional hook，独立Production DB/API、Solver/Validator/Benchmark/threshold与Production deployment仍未形成；所有NFR/ENG根ID继续`ALLOCATED`，registry format version不变。

TASK-P2-01 review：NFR-COR获得非法priority/lock/history/reference在solve前拒绝的input slice；NFR-DET/TRC获得v1 preservation、v2 complete bytes/hash、order/noise和新增事实mutation/source/version链。ENG-SOL确认Problem v2仍无OR-Tools/ORM/API/Infrastructure，ENG-ERR新增module-local稳定DATA/MODEL错误而不改产品registry，ENG-VER形成schema set`2.3.0`、ADR-0010及v1/v2显式consumer兼容。没有candidate correctness、formal Validator、Solver/Benchmark/Production evidence；所有NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-02 review：NFR-COR获得status/candidate/objective/tick/time/limit非法组合的pure rejection slice，但没有candidate C-ID正确性；NFR-DET/TRC获得四文档canonical fingerprint、fixed bytes/sample replay及Problem→Policy/Limits→Solution→Report来源链；NFR-OBS获得timing/model/memory/objective/parameter carrier字段但无真实数值。ENG-SOL形成无实现的Protocol与JSON-compatible contracts且无OR-Tools/ORM/API；ENG-ERR形成七种status唯一PlanningRun/product mapping；ENG-VER形成additive schema set`2.4.0`与四个显式v1 consumer合同。formal Validator、Backend/Solver、Benchmark/Production evidence仍未形成；所有NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-03 review：NFR-COR只获得native status/fail-closed adapter slice而无业务candidate correctness；NFR-TRC/OBS获得exact identity、platform、lock、parameters、status、model metrics和smoke timing machine evidence；NFR-PER只形成可重放solver版本前提而没有baseline；NFR-SEC完成point-in-time新增依赖审查并登记既有advisory债务RISK-011。ENG-ARCH/SOL形成唯一CP-SAT namespace、neutral Protocol与JSON边界，ENG-ERR形成unknown/version/adapter稳定错误，ENG-VER固定`9.15.6755`与`cp-sat-backend.v1`。C-ID/OBJ-001、formal Validator、Benchmark/Production仍未形成；所有NFR/ENG根ID保持`ALLOCATED`，registry format version不变。

TASK-P2-04 review：NFR-COR获得正式Problem/Solution的C-001～C-011独立正反判定、malformed/reference fail-closed及RUNNING/lock/time语义；NFR-DET/TRC获得稳定violation ordering、identical status-contradiction replay、fixed hashes、versioned machine report与exact provider replay。ENG-VAL形成不导入Backend/OR-Tools且不信任status的formal Validator，ENG-ERR形成`validation-report.v2`→`error.v2`稳定映射，ENG-VER记录`formal-schedule-validator-report.v1`且不改Schema set。无业务Solver candidate、OBJ-001、Benchmark或Production证据；所有NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-05 review：NFR-COR获得five-C-ID Solver/independent Validator正反交叉与tiny exhaustive oracle；NFR-TRC/OBS获得fingerprints、native/product status、参数、model counts、build/solve/first-feasible/wall/memory及Validator状态；NFR-DET由单worker、显式seed、canonical assignment/solution ID和fixed-seed properties约束。ENG-SOL形成bounded core builder/mapper，ENG-VAL形成mandatory consumer gate，ENG-ERR形成zero/overflow/future-fact MODEL_INVALID与Validator FAIL边界，ENG-VER保持`cp-sat-backend.v1`/OR-Tools 9.15.6755。无objective optimality、Benchmark或Production证据；所有根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-06 review：NFR-COR获得signed rounding、lag/calendar/gate/transport正反例、formal mutation与tiny oracle；NFR-DET/TRC获得固定seed、冻结fingerprints、canonical candidate和versioned machine report。ENG-SOL形成独立temporal builder并组合进bounded model，ENG-VAL保持solver-neutral独立复算，ENG-ERR形成sub-second/overflow/RUNNING/lock MODEL_INVALID、certified INFEASIBLE和UNKNOWN不升级边界，ENG-VER保持Problem/Solution/rule/Backend/dependency版本不变。无objective optimality、Benchmark或Production证据；所有NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-07 review：NFR-COR获得COMPLETED/RUNNING/HARD/SOFT正反例、formal mutation及tiny oracle；NFR-DET/TRC获得固定seed、canonical lock references、冻结Schema/rule/Validator/Builder/hash/ADR/lock fingerprints和versioned report。ENG-SOL形成独立fact/lock builder并组合进bounded model，ENG-VAL保持solver-neutral独立复算，ENG-ERR区分grid/self-conflict MODEL_INVALID与calendar/resource/horizon certified INFEASIBLE并保持UNKNOWN不升级，ENG-VER保持Problem/Solution/rule/Backend/dependency版本不变。无objective optimality、dynamic Replan、Benchmark或Production证据；所有NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-08 local review：NFR-COR获得OBJ-001精确整数目标、非tick-grid due-date与tiny exhaustive optimum；NFR-DET/TRC获得显式Simulation Policy/Limits、固定seed、冻结Schema/Problem/Validator/rule/ADR/lock fingerprint及完整report lineage；NFR-OBS获得objective/bound/gap、诚实七状态、build/first-feasible/solve/validation/total、model size与memory字段。ENG-ARCH/SOL形成只调用一次Backend的GlobalCpSatStrategy和独立objective builder，ENG-VAL保持candidate强制formal PASS，ENG-ERR保持MODEL_INVALID/INFEASIBLE/UNKNOWN/FAILED与validator-fail fail-closed，ENG-VER保持合同、OR-Tools exact pin和lock不变。NFR-PER仅获得tiny correctness timing，未形成XS/S/M baseline或threshold；exact provider、P2-09+ Gate与Production仍待后续。所有NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-08 provider closure：implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的required run `32438785162` / artifact `9431673977`复现objective/strategy 7/7、全部历史reports及52 committed/0 working治理链，故Task=`done`。这不形成XS/S/M baseline/threshold、P2-09+ Gate或Production证据；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-09 local review：NFR-COR由7个Solver candidate formal PASS、C-001～C-011正覆盖及11个exact negative mutation加强；NFR-DET/TRC由固定version/seed/object与Import/Snapshot/Problem hashes、row-order replay和resolved manifests加强；NFR-ISO只获得synthetic-only/Simulation-plane correctness slice。ENG-ARCH保持public pipeline/no direct Problem或CpModel，ENG-SOL取得七个真实pipeline candidate，ENG-VAL独立fresh validation/mutation，ENG-VER取得`1.0.0` assets与`p2-correctness-report.v1`而Schema/dependency不变。无XS/S/M baseline、Reference/Export/Production；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-09 provider closure：required run/artifact在Linux精确复现16/16 reports、correctness 8/8及58 committed/0 working治理，确认NFR-COR/DET/TRC/ISO与ENG-ARCH/SOL/VAL/VER的bounded correctness控制。该证据不形成独立Production DB/API、Reference/Export、XS/S/M baseline/threshold或P2 Gate；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-10 local review：NFR-COR由35个完整candidate/fresh Validator PASS及5个no-partial failure加强；NFR-DET/TRC由五个versioned identity、exact total-order tie-break、Problem/candidate fingerprint与35次replay加强；NFR-PER只获得明确单位的single-run runtime carrier而没有性能baseline。ENG-ARCH保持baseline→solver-neutral Problem/Validator单向边界，ENG-SOL仅形成非生产heuristic，ENG-VAL保持fresh独立判定，ENG-ERR区分invalid/heuristic/validation failure且不伪造INFEASIBLE，ENG-VER形成contracts/policy/result/report v1。Global comparison、XS/S/M、Production fallback仍PLANNED；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-10 provider closure：required run `32449742281` / artifact `9435264655`精确复现17/17 reports、reference 7/7及38 committed/0 working治理链，确认上述bounded correctness/determinism/trace controls。该证据不形成XS/S/M baseline/threshold、Production fallback或P2 Gate；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-11 local review：NFR-COR要求完整candidate/fresh exact PASS且KPI OBJ-001独立复算；NFR-DET/TRC由canonical JSON/LF CSV、content IDs、same-input bytes和全链fingerprint加强；NFR-REL获得internal exact replay/conflict、manifest-last原子提交与partial cleanup；NFR-OBS获得KPI delivery/planning/resource/stability/solver和冻结report carrier。ENG-ARCH保持reporting→exporter单向边界，ENG-SOL保持native-free output，ENG-VAL保持formal acceptance，ENG-ERR形成稳定output/I/O拒绝，ENG-VER发布additive set`2.5.0`并保留历史bytes。无dependency/ADR/状态持久化/Benchmark/Production；所有NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-11 provider closure：required run `32454693799` / artifact `9436863185`精确复现18/18 reports、output 8/8及58 committed/0 working治理链，确认上述bounded correctness/determinism/trace/reliability/observability controls。该证据不形成XS/S/M baseline/threshold、ScheduleVersion/ExportJob persistence、approval/publish、Production或P2 Gate；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-12 local review：NFR-COR由XS/S/M全Global/Reference fresh Validator与KPI cross-check加强；NFR-DET/TRC由versioned generator/profile/baseline、seed、Problem hash、1+3 stable assignment replay和environment/code fingerprints加强；NFR-OBS/PER获得真实model/build/first/solve/validation/total/objective/bound/gap/memory raw/median/p95及CI XS。ENG-ARCH保持Simulation→public Planning/Reporting/Exporter单向边界，ENG-SOL/VAL保持native隔离与formal gate，ENG-ERR形成hard correctness/contract/baseline drift失败和warning分离，ENG-VER形成三个internal v1合同且schema/dependency不变。OPEN-011/012、Production SLA与完整P2 Gate仍未形成；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-12 provider closure：required run `32460861563` / artifact `9438899443`精确复现19/19 reports、XS Benchmark 8/8及49 committed/0 working治理链，确认上述bounded correctness/determinism/trace/isolation/observability/performance controls。该证据不形成S/M provider schedule、L/XL、Production capacity/SLA或完整P2 Gate；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-13 local review：NFR-COR/DET/TRC/ISO/REL/OBS/PER由两次完整Gate replay、每次七场景/三profile/正式输出合同、fresh Validator和四类fail-closed退出拒绝加强；NFR-SEC确认无新增依赖、secret或Production authority。ENG-ARCH保持application Gate只调用公开Planning/Simulation/Reporting/Exporter边界，唯一直接Exporter合同检查例外被精确限定；ENG-SOL/VAL保持native隔离、独立复验与candidate fail-discard，ENG-ERR形成四类稳定退出结果，ENG-VER形成`p2-vertical-slice-report.v1`与`p2-gate-semantic-projection.v1`而不改Schema set/dependency/ADR。原始运行字段与稳定业务投影并存，不能以投影掩盖timing/memory/hash差异。Exact provider、P2-14独立audit、L/XL与Production capacity/SLA仍未形成；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-13 provider closure：required run `32465737712` / artifact `9440650646`精确复现20/20 reports、Gate 11/11及37 committed/0 working治理链，确认上述correctness/determinism/trace/isolation/reliability/security/observability/performance与engineering边界。该证据不形成P2-14 audit、L/XL、Production capacity/SLA或deployment；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-14 local audit review：NFR-COR/DET/TRC/ISO/REL/SEC/OBS/PER与ENG-ARCH/SOL/VAL/ERR/VER由完整provider lineage、476 tests、两次Gate、七场景逐次§76 metrics、XS/S/M、fresh Validator、Reference/KPI/Export和四类fail-closed拒绝独立审计为PASS。业务/Schema/lock/ADR零差异，raw运行证据未被semantic projection覆盖；overall=`READY`且0 gaps。Decision-writing时Audit Task provider尚未形成；L/XL、Production authority/capacity/SLA/security deployment仍未形成，全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-14 provider closure：required run `32677741558` / artifact `9503227240`精确复现20/20 reports、Gate 11/11、两轮provider业务投影一致及30 paths/3 rows/0 issues，故Task=`done`、Exit=`READY`。该证据不形成L/XL、Production authority/capacity/SLA/security deployment；全部NFR/ENG根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

## P3 planning allocation

P3-01～15把NFR-COR/DET/TRC/ISO/REL/SEC/OBS/PER/HUM与ENG-ARCH/VAL/ERR/VER/LOG分配到合同、immutable persistence、command/state guards、approval/publish/export、API/UI、Gate及独立Audit；ENG-SOL只作为P2 frozen boundary，不在P3扩展Solver。NFR-HUM的唯一允许目标是APPROVED-only、authorized-human capability与default-deny，OPEN-010关闭前不得写成真实角色授权。

本次只有规划与治理证据，不形成状态行为、可靠性、权限、UI、Production安全/性能或deployment证据。全部NFR/ENG根ID保持`ALLOCATED`，P4动态重排和Production readiness继续显式排除，`registry_version=1.0.0`格式不变。
