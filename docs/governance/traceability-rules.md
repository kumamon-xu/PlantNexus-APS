---
doc_id: DOC-GOV-004
title: 需求追踪规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [5, 6, 86, 98, 99, 111]
last_reviewed: 2026-08-19
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

2026-08-19 phase transition后，校验器从 `docs/current_phase.md` front matter读取 current phase，不再硬编码 P0，并支持任意 `TASK-Pn-NN～NN` 依赖范围。P0 `done`历史卡继续参与依赖/引用审计；P1卡必须包含 `Completion conditions`；P2+仍只能保留 Milestone。

TASK-P1-01增加 CI changed-task discovery：`--discover-task-from <event-base-sha>`要求完整、存在且为 HEAD祖先的 commit，在该 range的 `docs/tasks/**`中只能出现一个 current-phase Task Card；历史/未来/phase错位/多个卡直接失败。若 range没有 Task Card，仅当仓库恰有一个 current-phase `in_progress` Task时回退。选择完成后仍使用卡片 `Diff base..HEAD` + working tree执行 scope/impact，不把 CI event base混成 Task baseline。

结构化报告 schema 为 `traceability-report.v1`，至少包含 Task、可选 `task_discovery_base`、Git HEAD、Diff base、committed-range/working-tree source counts、changed paths、matched impact rows、expected/observed documents、missing trace refs、registry counts 和失败明细。失败返回非零退出码，不允许自由文本 skip。

TASK-P1-02将REQ-001/002/003/009、NFR-DET/TRC与ENG-SOL/ERR/VER链接到canonical-records.v1、Import v2、Snapshot v2、data dictionary、pure types/prechecks及TEST-CONTRACT-001。当前artifact state只标记contract formed；Adapter/staging/Normalization/DataValidation/Expansion/Snapshot/Problem builder/hash与P1 Gate继续`PLANNED`。

Raw Staging evidence链必须区分：opaque immutable batch/row contract、source/version/content与row digest/location/UTC provenance、data-plane/synthetic conditional、idempotency scope/fingerprint、exact replay/conflict、atomic transaction rollback、internal migration empty/populated round trip、raw-not-canonical dependency scan，以及真实Adapter/Normalization/DataValidation/independent Production database仍`PLANNED`。SQLite测试不得写成PostgreSQL concurrency、Production security或common-ingress PASS。

TASK-P1-03将REQ-001/009、NFR-TRC/REL/ISO/SEC与ENG-ARCH/ERR/VER链接到Raw Staging contracts/repository、`0002_raw_import_staging`、TEST-IMPORT-STAGING-001和TEST-IDEMPOTENCY durable Import slice。它不改变Schema set、产品error registry或外部field authority；后续链路继续`PLANNED`。

Reference file evidence链必须区分：adapter ID/version/capability与真实系统binding；fixed transport header与业务field mapping；format-neutral raw payload/row identity与format-specific file digest/media/location；CSV UTF-8/dialect和XLSX read-only/archive/active-content controls；prepared batch与durable repository replay；temporary synthetic files与真实客户数据。单文件首错DATA_ERROR、2-row parity或lock PASS不能替代Normalization/DataValidation、malware/auth review、Production interface authority或common-ingress Gate。

TASK-P1-04将REQ-001/009、NFR-TRC/SEC/REL与ENG-ARCH/ERR/VER链接到`ReferenceFileAdapter@1.0.0`、exact dependency lock、TEST-IMPORT-ADAPTER-001 contract/integration evidence及TASK-P1-03 repository。OPEN-002/013/015、Schema set和产品error registry均不改变；canonical producer与后续pipeline继续`PLANNED`。

Normalization evidence链必须区分：global schema set版本与immutable Import document字段；mapping profile版本与source system/version；unit registry合同与Production unit policy；Raw transport provenance与canonical hash projection；field normalization与跨实体Data Validation。Same-input bytes/hash、unit/time/ID正反测试不能替代DAG/reference/capability quality report、Snapshot/Problem replay或common-ingress Gate。

TASK-P1-05将REQ-002/003/009、NFR-DET/TRC与ENG-ERR/VER链接到`app.normalization`、`unit-conversion-registry.v1`、TEST-NORMALIZATION-001及扩展TEST-CONTRACT-001。`2.1.0`是additive set version，Import v2 document仍固定`2.0.0`且既有Schema hash保留；OPEN-001/002/013/015、产品error registry和后续Data Validation边界均不改变。
