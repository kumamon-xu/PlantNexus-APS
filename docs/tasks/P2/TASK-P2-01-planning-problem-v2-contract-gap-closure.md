---
doc_id: TASK-P2-01
title: PlanningProblem v2 Contract Gap Closure
status: in_progress
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [13, 14, 24, 25, 26, 28, 75, 89]
last_reviewed: 2026-08-20
---

# TASK-P2-01 — PlanningProblem v2 Contract Gap Closure

Task batch role: phase-plan-member

Requirement IDs: REQ-002, REQ-003, REQ-004, REQ-009, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-00

Start gate: TASK-P2-00=`done`、用户另行明确授权启动P2实现、启动时working tree clean；先把当时HEAD写入Diff base并复核PlanningProblem v1固定hash与P1 replay。

Goal: 发布solver-neutral PlanningProblem新版本并升级builder/hash，显式表达due/priority、active HARD/SOFT lock、COMPLETED→active历史完成锚点/lag和P2所需完整资源事实，消除C-008与OBJ-001输入缺口。

Inputs: immutable Snapshot v2、planning-problem.v1及fixed hashes、C-001～C-011、OBJ-001、ADR-0003/0007/0008/0009、OPEN-004/005/006/007/009/010。

Diff base: 617dd0fb8d6543dc2c9be6ac1e868f751763603d

Activation evidence（2026-08-20）：用户已明确授权执行TASK-P2-01；依赖TASK-P2-00=`done`。启动时working tree clean，`main=origin/main=617dd0fb8d6543dc2c9be6ac1e868f751763603d`；该SHA的GitHub Actions run `32332234513`、required `validate` job `96314960661`均`success`，artifact `9393422424`未过期且digest=`sha256:9532338d9d830da33c955b789d18fdcb3cffb7efde6e71abaa3e94d822c7ad73`。PlanningProblem v1 Schema/sample SHA-256分别为`41b01bfbcdfdb0a6dc52da1121383f630ac3f08ca7db4d21c0b66dea3a96e943`、`aa31fbb20b862b7ef51a0e1ed781cddca07c00a0d2724d9ea34e6a75d08a4093`，P1 fixed Problem hash=`sha256:6e4afffebf464de5c156094c894dccb5fe3efc712449f8583bcd91e1694dff72`且canonical-bytes SHA-256=`1f00ad7a856395328e9eb2c70afe8fe5878d69c3d8618ae7ef45bca34ef08645`。启动前已完整复核总规、Problem/Snapshot/Schema/Authority/Provenance/Constraint/Objective合同、ADR-0003/0007/0008/0009、质量与治理文档及相关代码测试；以下scope expansion在任何P2业务实现前完成。

Files allowed to change: `schemas/json/planning-problem.v2.schema.json`、`schemas/samples/planning-problem.v2.synthetic.json`、`schemas/data_dictionary.yaml`、`backend/app/__init__.py`、`pyproject.toml`、`backend/app/planning/problem/__init__.py`、`backend/app/planning/problem/contracts.py`、`backend/app/planning/problem/builder.py`、`backend/app/planning/problem/hashing.py`、`backend/app/planning/problem/contract_check.py`、`backend/app/domain/validation.py`、`.github/workflows/ci.yml`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_rule_contracts.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`backend/tests/contract/test_import_validation.py`、`backend/tests/unit/test_planning_problem_builder.py`、`backend/tests/property/test_planning_problem_properties.py`、`backend/tests/golden/test_p1_problem_replay.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`中的明确文档。

Files forbidden to change: `backend/app/planning/backends/**`、`backend/app/planning/strategies/**`、`backend/app/application/**`、fixture历史bytes、`schemas/json/planning-problem.schema.json`、`schemas/samples/planning-problem.synthetic.json`及其他P1 schema/sample bytes、`uv.lock`、OR-Tools或任何dependency pin、Validator evaluator、Export/Benchmark/P3代码。

Implementation steps: 建立v2 ADR与兼容分类；定义字段/引用/时间语义；实现v2 build/canonical hash/verify；保留v1 reader/hash向量；为due/priority、locks、historical edge/resource facts增加正反/重排/property证据；更新registry/docs。

Outputs: PlanningProblem v2 Schema/sample/types/builder/hash、v1兼容证据、固定v2 replay向量与machine contract report。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/contracts/README.md`、`docs/contracts/planning-problem.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/error-model.md`、`docs/core/glossary.md`、`docs/architecture/data-authority.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/planning/solver-backend-contract.md`、`docs/operations/README.md`、`docs/quality/property-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、`docs/adr/ADR-0010-planning-problem-v2-contract-evolution.md`、本Task卡。

Documentation impact rationale: Problem字段、版本和hash projection变化会影响所有P2 consumer、兼容性、C-008/OBJ-001及回放证据。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-PROBLEM`、`IMPACT-DOMAIN`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/004/009/012→TASK-P2-01→TEST-CONTRACT-001/TEST-PROBLEM-REPLAY-001/TEST-PROPERTY→v1 preservation + v2 replay artifacts；C-008/OBJ-001只标记input contract formed，不宣称Solver/Validator formed。

Schema changes: required；新增版本化Problem document并提升schema set，保留v1原字节/URN/hash，记录additive/breaking consumer分类、显式registry与positive/negative/round-trip证据。

Migration: none expected；PlanningProblem当前无持久化表；若发现持久化影响立即停止并拆分migration Task，不在本卡顺带修改。

Dependency changes: none；仍禁止OR-Tools及新runtime dependency。

ADR impact: required；新ADR记录v2字段权威、v1兼容和hash/version策略，保持ADR-0003 solver-neutral边界；任何边界改变需superseding ADR和用户决策。

Error behavior: 缺due/priority来源、非法lock、缺历史anchor、版本/hash/reference不一致在Solver前以稳定DATA/contract错误拒绝，不映射为INFEASIBLE。

Tests: TEST-CONTRACT-001、TEST-PROBLEM-REPLAY-001、TEST-PROPERTY；覆盖v1 fingerprint、v2 schema/round-trip、same-input bytes/hash、field/version mutation、locks、completed-active lag、unsupported capability及no-OR-Tools scan。

Benchmark impact: Problem/model输入变化触发未来固定Scenario benchmark；本Task只记录counts/hash并更新replay baseline，不运行Solver或伪造性能值。

Simulation scenarios: 扩展现有P1 correctness input或最小专用synthetic cases验证字段投影；不改变Production authority或正式XS/S/M baseline。

Acceptance commands: `uv run pytest -q backend/tests/contract/test_schema_contracts.py backend/tests/contract/test_rule_contracts.py backend/tests/contract/test_unit_conversion_registry.py backend/tests/contract/test_import_validation.py backend/tests/unit/test_planning_problem_builder.py backend/tests/property/test_planning_problem_properties.py backend/tests/golden/test_p1_problem_replay.py backend/tests/integration/test_ci_contract.py`；`uv run python -m app.planning.problem.contract_check --root . --report build/validation/TASK-P2-01-planning-problem-contracts.json`；`uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-01-planning-problem-v2-contract-gap-closure.md --check-diff --report build/traceability/TASK-P2-01-report.json`；`git diff --exit-code 617dd0fb8d6543dc2c9be6ac1e868f751763603d -- uv.lock schemas/json/planning-problem.schema.json schemas/samples/planning-problem.synthetic.json`；`git diff --check`。

Artifacts: schema fingerprints、v1/v2 replay vectors、Problem contract report、Task traceability report。

Provider evidence: exact implementation SHA的GitHub push run必须required `validate`成功并上传含Task report/contract evidence的未过期artifact；记录run/job/steps/artifact digest与branch protection。

Completion conditions: v2全部必需事实可表达且verify/build/hash确定；v1历史bytes/hash保持；非法输入明确拒绝；ADR/Schema/文档/追踪闭环；local/provider gates PASS；没有Backend/Solver/Validator执行。

Explicitly excluded: CP-SAT、PlanningPolicy/Solution实现、Solver status、ScheduleValidator、Reference Scheduler、BenchmarkRunner、DB migration、P3 Workspace。

PROD_OPEN: OPEN-004/005/006/007/009/010保持OPEN；字段允许显式输入但不猜Production default/authority。

SIM_ASSUMPTIONS: 可用既有versioned synthetic facts验证，但不得改变或冒充Production语义。

Rollback: 保留v1默认consumer和固定hash；v2未被后继消费前可回退新增artifact；一旦被消费只能通过新版本/ADR迁移，禁止覆盖v2历史bytes。

## Local implementation evidence（provider pending）

已形成ADR-0010、global schema set`2.3.0`、`planning-problem.v2` Schema/sample、version-specific types/builder/hash/verify与CI machine report。v2 fixed Problem hash=`sha256:9927418a446dd046ddd1d835643da03fbf5cdcf8ca246ba22c3700563a17e9e8`，canonical bytes SHA-256=`2dbe06907952d6aba303977d67a7f5d7a6ef89c4be5ac5a6ac8d74e3f95d720a`/3366 bytes；v2 Schema/sample file SHA-256分别为`e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8`、`f655f9da0e97ede115ffe128eeabdc6e61bcb74412acfac4d7d0ccb8766d92ad`。

v1 Schema/sample bytes、default `build_planning_problem`及fixed Problem/canonical digests均保持启动门记录值。八文件focused suite=`89 passed`，full repository suite=`286 passed`，v2 property文件5项PASS，Ruff/Pyright=`0 issues`，`planning-problem-contract-report.v1`=`4/4 PASS`。Full docs governance=`141 docs/30 roots/36 tests/15 OPEN/10 SIM/10 risks/37 tasks` PASS；Task diff governance=`60 paths/10 impact rows/0 issues` PASS；locked sync、immutable v1/`uv.lock` diff和`git diff --check`均exit 0。

没有DB migration、dependency/`uv.lock`变化、OR-Tools、Backend/Strategy、Application切换、ScheduleValidator、candidate schedule、Solver、Benchmark或P3实现。以上为working-tree本地证据；implementation SHA、required `validate` job和artifact尚未产生，因此Task保持`in_progress`，不得预填provider PASS或启动P2-02。
