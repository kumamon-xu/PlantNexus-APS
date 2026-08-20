---
doc_id: TASK-P2-02
title: Planning Machine Contracts and Status
status: in_progress
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [13, 14, 28, 29, 35, 57, 75, 96]
last_reviewed: 2026-08-20
---

# TASK-P2-02 — Planning Machine Contracts and Status

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-OBS-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-01

Start gate: TASK-P2-01=`done`且Problem v2版本/ADR/fingerprint固定；启动前固定Diff base和合同文件名。

Goal: 建立PlanningPolicy、SolveLimits、PlanningSolution、SolverReport与统一Solver status的版本化machine contracts，供Backend、Validator、Strategy、Export共同消费。

Inputs: Problem v2、OBJ-001、SolverBackend合同、PlanningRun/error状态语义、ADR-0004/0006/0008。

Diff base: 3cf4966481e4e8cb6e075a3305472e0f0a93b99c

Files allowed to change: `schemas/json/planning-policy.schema.json`、`schemas/json/solve-limits.schema.json`、`schemas/json/planning-solution.schema.json`、`schemas/json/solver-report.schema.json`、`schemas/samples/planning-policy.v1.synthetic.json`、`schemas/samples/solve-limits.v1.synthetic.json`、`schemas/samples/planning-solution.v1.synthetic.json`、`schemas/samples/solver-report.v1.synthetic.json`、`schemas/data_dictionary.yaml`、`pyproject.toml`、`backend/app/__init__.py`、`backend/app/planning/contracts.py`、`backend/app/planning/policy/__init__.py`、`backend/app/planning/policy/contracts.py`、`backend/app/planning/policy/contract_check.py`、`backend/tests/contract/test_planning_machine_contracts.py`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_import_validation.py`、`backend/tests/contract/test_rule_contracts.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`backend/tests/integration/test_ci_contract.py`、`.github/workflows/ci.yml`及`Documents to update`中的明确文档。

- Machine contracts/samples/metadata: `schemas/json/planning-policy.schema.json`、`schemas/json/solve-limits.schema.json`、`schemas/json/planning-solution.schema.json`、`schemas/json/solver-report.schema.json`、`schemas/samples/planning-policy.v1.synthetic.json`、`schemas/samples/solve-limits.v1.synthetic.json`、`schemas/samples/planning-solution.v1.synthetic.json`、`schemas/samples/solver-report.v1.synthetic.json`、`schemas/data_dictionary.yaml`、`pyproject.toml`、`backend/app/__init__.py`；
- Pure planning contracts/report: `backend/app/planning/contracts.py`、`backend/app/planning/policy/__init__.py`、`backend/app/planning/policy/contracts.py`、`backend/app/planning/policy/contract_check.py`；
- Contract/CI tests and provider handoff: `backend/tests/contract/test_planning_machine_contracts.py`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_import_validation.py`、`backend/tests/contract/test_rule_contracts.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`backend/tests/integration/test_ci_contract.py`、`.github/workflows/ci.yml`；
- every exact path listed in `Documents to update` below.

Files forbidden to change: `uv.lock`、既有PlanningProblem v1/v2 Schema/sample/builder/hash、CP-SAT backend/OR-Tools、constraint实现、Validator判定、fixtures/benchmarks、DB/API/Worker、P3状态动作及上列allow-list之外的任何路径。

Implementation steps: 固定四类合同及版本；定义OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN/MODEL_INVALID/CANCELLED/FAILED映射、objective stages、timing/model/memory/provenance字段；实现pure validation/canonicalization；Schema正反/round-trip/status测试；同步文档/追踪。

Outputs: 四份JSON Schema、solver-neutral types/prechecks、status/error mapping与fixed samples/report。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/core/glossary.md`、`docs/contracts/README.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/objective-policy.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/domain/kpi-contract.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/benchmark-regression.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、本Task卡。

Documentation impact rationale: 机器合同和状态是P2各实现Task的共同边界，必须在代码前固定版本、错误和provenance。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-PLANNING-CONTRACTS`、`IMPACT-POLICY`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009→TASK-P2-02→TEST-CONTRACT-001/TEST-ERROR-MAPPING-001→四类contract artifacts；仅合同formed，Solver/Validator/metric值仍PLANNED。

Schema changes: required；additive schema-set release，四个新document version，显式registry/unknown-field/no-default/round-trip与sample属性。

Migration: none；不创建PlanningRun/ScheduleVersion persistence。

Dependency changes: none；标准库+pydantic既有边界内实现pure合同。

ADR impact: no new ADR if strictly implementing ADR-0004/0006/0008 and existing status semantics；任何目标顺序、状态含义或time unit变化必须停止并新增superseding ADR。

Error behavior: limits耗尽无认证解=`UNKNOWN/NO_SOLUTION_WITHIN_LIMIT`，模型错误=`MODEL_INVALID`，系统异常=`FAILED`；不得把UNKNOWN写成INFEASIBLE或FEASIBLE写成OPTIMAL。

Tests: TEST-CONTRACT-001、TEST-ERROR-MAPPING-001；覆盖每种status、非法组合、objective stage/bound/gap、UTC/ticks、timing非负、version/provenance、canonical replay。

Benchmark impact: 只固定未来BenchmarkReport可引用字段，不生成benchmark数值或阈值。

Simulation scenarios: fixed synthetic samples only；无Solver执行。

Acceptance commands: `uv run pytest -q backend/tests/contract/test_planning_machine_contracts.py backend/tests/contract/test_schema_contracts.py backend/tests/contract/test_rule_contracts.py`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-02-planning-machine-contracts-and-status.md --check-diff --report build/traceability/TASK-P2-02-report.json`；`git diff --check`。

Artifacts: schema/sample fingerprints、`planning-machine-contract-report.v1` status mapping report、Task traceability report。

Provider evidence: exact implementation SHA required `validate`/steps/artifact success；artifact须包含Task report和contract evidence，记录immutable provider metadata/digest/expiry。

Completion conditions: 合同完整且互相引用可离线解析；全部status语义可二值验证；Schema/version/docs/trace/provider闭环；无Solver/constraint/DB行为。

Explicitly excluded: OR-Tools、实际求解、C-ID实现、READY_FOR_REVIEW状态迁移、API/persistence、P3审批发布。

PROD_OPEN: OPEN-006/011/012不关闭；Production权重和limit/default不写入Schema默认值。

SIM_ASSUMPTIONS: Simulation policy必须显式version，不成为Production default。

Rollback: 新合同尚无consumer时删除additive release并恢复set metadata；已有consumer后只能发布兼容新版本，不重写历史合同。

## Activation evidence

2026-08-20用户明确授权执行TASK-P2-02。启动时working tree clean，`main=origin/main=3cf4966481e4e8cb6e075a3305472e0f0a93b99c`；TASK-P2-01 implementation `c64284685f37ef0d03eacade5699076146653333`为HEAD祖先，最终closure SHA对应GitHub push run `32337439199`、required `validate` job `96329607133`与artifact `9395135532`，均为success且artifact未过期。启动前固定Problem v1 Schema/sample SHA-256=`41b01bfbcdfdb0a6dc52da1121383f630ac3f08ca7db4d21c0b66dea3a96e943`/`aa31fbb20b862b7ef51a0e1ed781cddca07c00a0d2724d9ea34e6a75d08a4093`，Problem v2 Schema/sample SHA-256=`e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8`/`f655f9da0e97ede115ffe128eeabdc6e61bcb74412acfac4d7d0ccb8766d92ad`，`uv.lock` SHA-256=`7ae68d242b1f80ad05a2ae51b09552ca9e19214d33ef8380bc74ff4c87ee64dd`。

Scope review在实现前补入四份fixed synthetic sample、contract machine report/CI handoff、global schema-set metadata及受`2.4.0`断言影响的既有contract tests；同时纳入INFRA/DEPENDENCY/VERSION-METADATA/PHASE强制文档。实现中发现glossary含“current schema set”字段，故在任何该文件修改前把`docs/core/glossary.md`加入allow-list与文档清单，避免发布`2.4.0`后保留冲突的current值；首次diff governance又识别planning-run文档触发`IMPACT-STATE`，在修改其余两份state文档前把该Rule及`schedule-version.md`/`export-job.md`补入范围。该范围校正只补足审查链，尚未创建Solver、Constraint、Validator、DB/API/Worker或P2-03实现。

## Completion evidence

Implementation slice已形成四个Draft 2020-12 strict v1 document、四份explicit Simulation `CONTRACT_SAMPLE`、JSON-compatible types/Protocol、pure semantic/canonical/fingerprint/bundle checks、seven-status outcome mapping与`planning-machine-contract-report.v1`。Global schema set=`2.4.0`；Problem v2仍固定`2.3.0`，Import/Snapshot/unit/quality等旧document版本不改。新sample canonical fingerprints为Policy `sha256:32a46b97989910c7ab9b0b6f1fbfff2cdb958492d329fb4c71b06f0c7e38de7a`、Limits `sha256:76091493ee0b96a761c9df6e9881d03d9b8cca1c4b09103602661dcbf5d4a27b`、Solution `sha256:4713507110b47c8f61d16149580abe393a75bf9237f92e09ec81b5ac6ff336f5`、Report `sha256:572fd7e29f12ac64e1622424caf0914e59acf88de8c194212a3485490c59ec52`；machine report为5/5 PASS、SHA-256=`7c40627f4bf13c1a1a329980b6030592ed35dfc6f4095bab1be68fcb5a332c82`、6994 bytes。

本地验收：Task指定三文件suite=`54 passed`；完整repository suites=`311 passed`；Ruff=`All checks passed`；Pyright=`0 errors, 0 warnings`；Rule 11/7、Generator 7、Golden 0 issues、Mutation 13 cases/15 violations、P1 ingress 14 checks、Problem contract 4/4、Planning machine 5/5、Engineering 6/6均PASS；Compose config、`uv build`、full docs governance及Task diff均PASS。Final diff report记录63 paths、11 matched impact rows、19 checks、0 issues；`git diff --check`仅有Windows line-ending提示，无whitespace error。

启动冻结的Problem v1 Schema/sample、Problem v2 Schema/sample、`uv.lock` SHA-256复核仍分别为`41b01fb...e943`/`aa31fbb...4093`、`e6e4a98...b87c8`/`f655f9d...d92ad`、`7ae68d2...64dd`。Dependency/migration为none，`uv.lock`无diff；ADR review结论为no new ADR。无OR-Tools、Backend implementation、C-ID、ScheduleValidator、DB/API/Worker、Benchmark或P3行为；rollback边界保持Task卡定义。

Provider evidence当前为`PENDING_IMPLEMENTATION_PUSH`，因此Task仍为`in_progress`。下一步只允许提交并push当前implementation、核验exact required `validate`和artifact，再以evidence-only revision回填immutable provider facts；在此之前不得标记`done`或启动P2-03。
