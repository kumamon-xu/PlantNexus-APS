---
doc_id: TEMPLATE-TASK
title: Task Card Template
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [98, 99, 100, 111]
last_reviewed: 2026-08-20
---

# TASK-Px-yy — Title

Task status: 写入本 Task Card front matter 的 `status`，不在正文建立第二状态源。

Requirement IDs:

NFR / ENG IDs:

Depends on:

Start gate: P2+必填；列出依赖状态、授权、固定版本/证据和启动时clean HEAD条件

Goal:

Inputs:

Diff base: Task 进入 `in_progress` 前的完整 40 字符 HEAD commit SHA；不得使用会移动的 branch/tag

Files allowed to change:

Files forbidden to change:

Implementation steps:

Outputs:

Documentation impact: `required` | `none`

Documents to update: 使用反引号列出仓库根相对路径；禁止只写“相关 docs”

Documentation impact rationale: 说明变化影响，或声明 `none` 的可验证理由

Change-impact matrix rows reviewed: 列出 `change-impact-matrix.md` 中实际匹配的稳定 `IMPACT-*` Rule ID

Traceability updates: 明确 Requirement/NFR/ENG/Constraint/Task/Test/Artifact/Registry 关系

Schema changes:

Migration:

Dependency changes: P2+必填；写exact pin/lock影响或明确none

ADR impact: P2+必填；写required/none及触发条件，不得把planned ADR写成accepted

Error behavior:

Tests:

Benchmark impact:

Simulation scenarios:

Acceptance commands:

Artifacts:

Provider evidence: P2+必填；固定provider/repository/branch/workflow以及exact SHA/run/job/artifact/required-check要求

Completion conditions: 使用可二值判断的目标、范围、测试、文档、追踪和边界条件；P1+ Task必填

Explicitly excluded:

PROD_OPEN:

SIM_ASSUMPTIONS:

Rollback:

## Completion evidence

在任务完成时填写真实的修改文件、文档更新、影响矩阵匹配结果、追踪更新、命令/退出码、测试/Benchmark artifact 和开放问题。不得预填 PASS。

至少记录：

- 完成时间和实际 changed paths；
- Diff base、验收时 Git HEAD，以及 committed-range/working-tree source counts；
- 实际更新文档及必审但未修改文档的逐项理由；
- Requirement/NFR/ENG → Task → Test → Artifact 关系；
- `scripts/check_docs.py --task <task-card> --check-diff --report <report-path>` 的真实摘要；
- 若修改 CI，记录 `--discover-task-from <event-base-sha>` 的 Task选择结果、event base与 Task `Diff base`的区别，并证明零/多/历史/未来 Task路径硬失败；
- PROD_OPEN、SIM_ASSUMPTION、Schema/Migration、Benchmark 和回滚影响。

涉及 Schema 时还必须记录 schema set/contract version、compatibility 分类、migration 或明确 none 理由、机器 validator 版本、positive/negative/round-trip evidence，以及 sample/fixture 的 Production/Synthetic 属性。若保留历史artifact，记录固定byte fingerprint；若Schema使用跨document `$ref`，记录显式registry/resolution测试，不能依赖隐式网络获取。

涉及 Constraint rule、capability/error registry 或状态机时还必须记录：稳定 artifact/version、所有 C-ID/state/code 的完整性、允许与拒绝路径、guard/evidence、对应 Test ID、是否仅为 contract metadata、真实 evaluator/persistence/权限/业务动作是否仍为 `PLANNED`，以及是否需要 ADR/Benchmark replay。不得把 rule-sheet completeness 写成 ScheduleValidator PASS。

涉及 Validator evaluator 或 mutation 时还必须记录：正例来源/hash 保持不变、evaluator 与 Solver/backend/expected artifact 的依赖边界、mutation construction 与判断公式分离、每个 mutation 的目标及实际 C-ID、ValidationReport/Error exact/schema evidence、C-ID/required mutation coverage、deterministic replay、fixture-local 与 production/performance 边界，以及 Property/Benchmark/Solver comparison 是否仍为 `PLANNED`。

涉及 Simulation Profile/Scenario/Generator 时还必须记录：contract/asset/generator/mapping/manifest/canonicalization各自版本、seed与命名随机源控制、source-shaped Raw输入→公开Normalization/DataValidation边界、canonical dataset/hash定义、`generated_at`等non-hash provenance、Production target/unsupported/version拒绝、TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION证据，以及sample/Fixture/Benchmark/Execution/common-ingress哪些仍为`PLANNED`。局部consumer manifest不得重新解释已发布Schema；不得把empty package、Schema sample或small generated asset写成正式Scenario/性能/Production证据。

涉及 engineering infrastructure/API health/Worker/CI 时还必须记录：direct dependency/lock 与明确未安装组件；environment/data-plane/Secret fail-closed boundary；liveness/readiness 的外部依赖与 no-leak 行为；Job heartbeat/lease/attempt/STALLED、idempotency scope/fingerprint、持久化/transaction/side-effect 边界；migration upgrade/downgrade 与测试数据库；structured log/trace context/redaction 和 audit/metrics 缺口；Compose/container/CI 实际执行层级。仓库内 workflow/config/local PASS 不得伪装成 CI provider run、branch protection、Production deployment、distributed crash recovery 或 production security evidence。

涉及Raw Staging时还必须记录：batch/row immutable fields、source/version/content与row digest/location/received-at、Production/Simulation conditional、idempotency scope/fingerprint与exact replay/conflict、batch+rows transaction rollback、empty/populated migration upgrade/downgrade及明确数据损失、raw-not-canonical/Snapshot/Problem/Solver边界。临时SQLite不得伪装成PostgreSQL concurrency、独立Production数据库或Production security；Adapter/Normalization/DataValidation未形成时继续标记`PLANNED`。

涉及外部文件Adapter时还必须记录：adapter ID/version/capabilities/production binding、固定encoding/dialect/header/sheet合同、root/path/type/file-row-column-cell/archive limits、macro/formula/external-link/XML拒绝、exact parser/security dependency lock、format-neutral semantic rows与format-specific digest/media/location的区别、temporary/real data边界、sanitized error、Raw Staging replay，以及Normalization/DataValidation/malware/auth/Production interface仍未形成的范围。

涉及 external CI provider 时还必须在开始前固定 provider/repository/branch/workflow 和官方 query 命令，并在完成证据中记录 immutable head SHA、run ID/URL/attempt/event/status/conclusion、required jobs/steps、artifact ID/name/size/digest/expiry 与 required-check/branch-protection 状态。credential 必须由进程外环境或已认证 session 提供，不得记入 Task、日志或 artifact；失败 run 必须保留为反例，不得伪写 PASS。

仓库内 CI workflow应使用 current-phase Task discovery与中性 artifact命名，不得每个 Task手工改写旧 Task路径。没有外部执行授权时 provider结果必须写 `NOT_RUN`，本地 workflow contract、YAML parse或 diff governance不能替代 provider事实。

P1及以后 Task必须单列 `Completion conditions`，把“实现目标、负向路径、文档/追踪、提交前后治理和明确排除项均满足”写成可核验条件；不能只写“测试通过”或重复 Goal。

P2及以后Task还必须单列`Start gate`、`Dependency changes`、`ADR impact`和`Provider evidence`。初始phase planning若一次新增多卡，唯一`TASK-Pn-00`写`Task batch role: phase-planning-owner`且拥有有效Diff base；其余新卡写`Task batch role: phase-plan-member`、保持`planned/ready`且不得预填implementation SHA。该例外只用于同一range新建完整阶段计划，不允许批量修改既有Task或同时启动多个Task。

若Task做set-level additive schema release但保留既有document版本，`Schema changes`和completion evidence必须分别记录global set version、各document内固定version、preserved artifact hash和consumer compatibility；不得用全局版本搜索替换改写immutable旧合同。Versioned mapping/rule还必须说明历史rows如何显式选择版本及禁止`latest`重解释。

涉及canonical Data Validation/quality report时还必须记录：输入document/rule/error/report/canonicalization各自版本、旧Error/registry fingerprint、PASS零Error与FAIL count等式、四类P1 exact code/category、rich source/action evidence、multi-error stable ordering、report ID projection、malformed input不崩溃、capability/resource/DAG边界，以及与Normalization、Expansion、Snapshot/Problem、ScheduleValidator/Solver的依赖隔离。固定sample不得写成Production authority或common-ingress evidence。

涉及Order/Lot/OperationInstance expansion时还必须记录：expansion/canonicalization version、Import与matching PASS report引用、source-explicit lot policy、derived operation/edge ID lineage与排序、candidate duration/source逐项copy、RUNNING/COMPLETED/lock投影、SPLIT_MERGE和missing/fallback拒绝、Hypothesis seed/example/shrinking结果，以及Snapshot/Problem/Constraint/Solver仍未形成的边界。通过Snapshot pure precheck不得写成Snapshot builder/hash/persistence PASS。

涉及PlanningSnapshot builder/hash/persistence时还必须记录：Snapshot/schema/canonicalization/hash-projection版本、semantic allow-list与self/noise exclusion、Import dataset/package identity、matching PASS与Expansion自洽检查、全部collection/inner排序、deterministic full bytes/hash/ID vector、fact/cutoff/version mutation、frozen copy边界、Production/Synthetic provenance/plane guard、insert/exact replay/content conflict、repository及database update/delete拒绝、empty/populated migration upgrade/downgrade与数据损失，以及Problem/common-ingress/independent Production DB/Solver仍未形成。Storage `created_at`不得污染business hash，临时SQLite不得冒充PostgreSQL Production evidence。

涉及common-ingress/application orchestration时还必须记录：每个source到Raw Staging的公开边界、staging后唯一顺序函数链、quality FAIL/Normalization错误的exact stage/category/code与no-downstream-call、Reference/Synthetic transport差异和业务artifact parity、Import/Snapshot/Problem完整bytes/hash重放、data-plane/no-shortcut边界、machine report版本/commit/config/counts与CI artifact。必须明确终止于PlanningProblem，不得把temporary reference data写成Production binding，也不得把Problem replay写成Solver、Validator、feasibility或P2 evidence。

涉及Phase Exit Gate audit时还必须记录：全部前置Task Diff base/implementation/provider ancestry、审计execution head、所有mandatory local命令和machine artifact digest、外部run/job/artifact/required-check、每项Gate的PASS/FAIL/NOT_RUN、blocking gaps、PROD_OPEN/SIM_ASSUMPTION/RISK边界和下一Phase授权状态。Audit decision可以基于已provider验证的前置baseline与本地独立命令形成，但报告不得自我包含尚未push的自身run；Task只有在audit documentation implementation commit及其后续evidence-only closure都得到exact provider核验后才为`done`。`READY`不自动改变current phase或创建下一Phase Task。

涉及PlanningProblem新版本时还必须记录：旧Schema/sample/default API/fixed replay fingerprints、global schema set与各旧document固定version、consumer compatibility/migration/rollback、builder/canonicalization/hash-projection版本、hash语义allow-list与runtime/self exclusion、due/priority/resource/fact/lock/edge authority和cutoff/horizon语义、positive/negative/reordering/mutation/property vectors、Backend旁路禁止及Solver/Validator未形成边界。新增priority/default或Production authority必须引用对应OPEN决定；Schema sample不得替代builder replay或provider artifact。

涉及PlanningPolicy/SolveLimits/PlanningSolution/SolverReport机器合同时还必须记录：各document/schema-set/canonicalization/constraint/objective/state/error版本，Policy/Limits ID/revision/source/data plane和no-default边界，Problem/Policy/Limits/Solution exact fingerprint链，七种Solver status到PlanningRun/product error/candidate的总映射，assignment seconds/ticks/UTC还原，objective/bound/gap条件，timing/model/memory/parameter/code-commit provenance，`CONTRACT_SAMPLE`与真实`SOLVER_RUN`隔离，以及Backend/C-ID/Validator/DB/API/Worker仍未形成。Simulation sample中的weight/limit/seed/zero metrics不得写成Production default、Solver execution或Benchmark evidence。
