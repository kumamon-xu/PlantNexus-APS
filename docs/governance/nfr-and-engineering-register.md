---
doc_id: DOC-GOV-003
title: NFR 与工程需求注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [4, 6, 16, 23, 24, 29, 30, 42, 58, 62, 65, 66, 89, 93, 95]
last_reviewed: 2026-08-20
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
