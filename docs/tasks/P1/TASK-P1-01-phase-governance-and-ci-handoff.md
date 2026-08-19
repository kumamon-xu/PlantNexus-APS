---
doc_id: TASK-P1-01
title: P1 Phase Governance and CI Handoff
status: done
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [6, 58, 73, 74, 98, 99, 100, 101]
last_reviewed: 2026-08-19
---

# TASK-P1-01 — P1 Phase Governance and CI Handoff

Requirement IDs: REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-PER-001, ENG-ARCH-001, ENG-VER-001

Depends on: TASK-P0-10；用户于 2026-08-19 明确授权进入 P1

Goal: 将文档治理和 CI 从 P0-10 的一次性 handoff 收敛为可识别当前 Phase 与当前变更 Task 的 P1 基线，使后续 P1 Task 能在不改业务代码的情况下得到 full/diff governance 与 provider evidence。

Inputs: `docs/current_phase.md`、`docs/tasks/README.md`、`docs/quality/documentation-consistency-checks.md`、`.github/workflows/ci.yml`、P0 successful provider evidence。

Diff base: 430506349ccdc135072e12fc98f7df1744a63e2c

Files allowed to change: `scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`、生成但不提交的 `build/traceability/TASK-P1-01-report.json`、`build/traceability/ci-current-task-report.json`、`build/validation/ci-rule-contracts.json`、`build/validation/ci-simulation-contracts.json`、`build/validation/ci-golden.json`、`build/validation/ci-validator-mutations.json`、`build/validation/ci-engineering.json` 与 `build/validation/TASK-P1-01-ci-contract.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: `backend/app/domain/**`、`backend/app/importers/**`、`backend/app/normalization/**`、`backend/app/data_validation/**`、`backend/app/snapshots/**`、`backend/app/planning/**`、`backend/app/simulation/**`、`schemas/**`、`fixtures/**`、`pyproject.toml`、`uv.lock`、任何 P1 数据实现、Solver 或 Production 配置。

Implementation steps: 固定 phase-aware Task policy（历史 Phase 只保留 terminal Task、未来 Phase 禁止详细卡）；让 Task range/changed-task discovery 不再硬编码 P0；CI 保留 full governance、全部 P0 回归、构建和 artifact upload，并对本次 P1 Task 执行 immutable diff check；integration/unit tests 覆盖 current/historical/future phase、短范围依赖和 stale P0 handoff 拒绝；任何 provider push/branch 变更须另有执行时授权。

Outputs: current-phase-aware governance validator、不会遗留 P0-10 task range 的 P1 CI contract、机器报告与更新后的治理说明。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/governance/document-control.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/operations/README.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md`。

Documentation impact rationale: 治理 validator、Task phase policy 与 CI provider gate 的行为和使用命令都会改变，必须同步 Agent、质量、追踪和阶段文档。

Change-impact matrix rows reviewed: `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-009/NFR-TRC-001/NFR-PER-001/ENG-ARCH-001/ENG-VER-001 → TASK-P1-01 → TEST-TRACEABILITY-VALIDATOR/TEST-PHASE-GOVERNANCE-001 → phase-aware report、workflow contract 与 provider artifact；不把治理 PASS 写成 P1 数据能力证据。

Schema changes: none。

Migration: none。

Error behavior: current phase 无效、未来 Phase Task、历史非 terminal Task、Task phase/path/ID 不一致、stale P0 command 或遗漏 diff gate均必须返回非零；不得自由文本 skip。

Tests: `TEST-TRACEABILITY-VALIDATOR`、`TEST-PHASE-GOVERNANCE-001`；覆盖 P0 terminal history + P1 current cards、P2 future rejection、跨 Phase 依赖、changed-task CI 和 artifact handoff。

Benchmark impact: 仅保留既有 conditional hook；无 Solver、无 BenchmarkReport、无性能承诺。

Simulation scenarios: 只重放既有 P0 Simulation/Golden/Mutation gates，不修改 Scenario 或 Fixture。

Acceptance commands: `uv sync --locked`；`uv run ruff check scripts/check_docs.py backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run pyright scripts/check_docs.py backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md --check-diff --report build/traceability/TASK-P1-01-report.json`；`git diff --check`；`uv build`。

Artifacts: `traceability-report.v1`、CI contract test result、workflow evidence artifact；provider run ID/URL 仅在实际执行并授权后记录。

Completion conditions: phase-aware unit/integration negative paths全部通过；CI 不再引用 P0-10 immutable range且不削弱既有 gates；本 Task 提交前后 diff governance均 PASS；真实 provider 结果如未获授权必须记为 `NOT_RUN` 而非 PASS；没有业务代码变更。

Explicitly excluded: P1 Schema/Adapter/Staging/Normalization/Snapshot/Problem/Generator 实现、CI gate 弱化、P2、OR-Tools、Production deployment。

PROD_OPEN: OPEN-001～015 均不关闭；CI/provider 信息不是生产业务权威。

SIM_ASSUMPTIONS: SIM-ASSUMPTION-001～009 不新增、不修改、不用于生产结论。

Rollback: 恢复到最后一个能识别当前 Phase 且通过 full/diff governance 的版本；不得恢复 stale P0 task handoff，provider 历史不得删除。

## Completion evidence

2026-08-19 已按用户指令启动；启动时 HEAD/`origin/main` 均为 `430506349ccdc135072e12fc98f7df1744a63e2c`，working tree clean，因此该 commit固定为不可变 Diff base。

提交前实现证据：

- phase policy、changed-task selector、immutable event-range discovery、CLI互斥入口、`task_discovery_base`报告字段与hidden-directory路径保真已落地；workflow使用PR base/main-push `before`、中性report/artifact命名，并保留原全部 gates；
- targeted Ruff=`PASS`，targeted Pyright=`0 errors`，`test_check_docs.py` + `test_ci_contract.py`=`20 passed`；全仓Ruff=`PASS`、全仓Pyright=`0 errors`、完整 unit/contract/simulation/golden/validation/integration=`97 passed`；
- rule contracts=`PASS active=11 deferred=7 capabilities=20 error_codes=19 machines=3 states=27 transitions=42`，Simulation contracts、Golden replay、13-case Validator mutation、Engineering contract与Compose config均`PASS`；`uv sync --locked`和`uv build`均成功；
- full governance=`PASS docs=124 roots=30 trace_rows=30 tests=36 open=15 sim=9 risks=10 tasks=22`；显式Task diff governance=`PASS diff_paths=31 impact_rows=6`，命中`IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`，报告位于忽略目录`build/traceability/TASK-P1-01-report.json`；动态event-base入口也选择`TASK-P1-01`并PASS；
- 实际31个tracked changed paths恰为4个实现/测试文件和`Documents to update`列出的27个文档；未修改业务代码、Schema、Fixture、Migration、dependency、Solver、Production配置或P2内容；REQ/NFR/ENG仍为`ALLOCATED`，OPEN-001～015仍为`OPEN`，SIM-ASSUMPTION-001～009保持`ACTIVE`；
- 未获得单独的push/branch/provider执行授权，因此新的provider run/job/artifact/required-check=`NOT_RUN`；既有P0 provider证据只作历史输入，不冒充本Task结果。Benchmark hook保持conditional，runner/BenchmarkReport=`NOT_RUN`。

implementation commit=`8d8ceced4496bfc7be4651f67eb376993e49ec67`。该commit后working tree clean；full governance=`PASS`，显式与动态diff governance均=`PASS diff_paths=31 impact_rows=6`，targeted tests=`20 passed`。动态报告明确记录`task_discovery_base=430506349ccdc135072e12fc98f7df1744a63e2c`、`git_head=8d8ceced4496bfc7be4651f67eb376993e49ec67`、Task `diff_base=430506349ccdc135072e12fc98f7df1744a63e2c`、`committed_range=31`、`working_tree=0`，证明CI event attribution与Task scope基线没有混用。

上述实现、负向路径、文档/追踪、提交前后治理和明确排除项均满足，故TASK-P1-01标记`done`。本次completion-only文档提交不能自引用其最终SHA；最终clean-tree治理结果在交付中记录。回滚点为Diff base；生成的`build/`与`dist/`产物均不提交，provider仍为`NOT_RUN`。
