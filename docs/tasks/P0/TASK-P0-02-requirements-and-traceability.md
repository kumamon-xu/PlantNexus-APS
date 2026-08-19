---
doc_id: TASK-P0-02
title: Requirements and Traceability
status: done
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [5, 6, 59, 60, 61, 98, 99]
last_reviewed: 2026-08-19
---

# TASK-P0-02 — Requirements and Traceability

Requirement IDs: REQ-001～REQ-015

NFR / ENG IDs: NFR-TRC-001, ENG-VER-001

Depends on: TASK-P0-01

Goal: 固定 REQ/NFR/ENG 根 ID、追踪规则、开放问题/假设/风险注册表，并提供可自动检测孤立 ID 和伪造路径的机制。

Inputs: `docs/governance/*`、Milestone、Task Template。

Files allowed to change: `/scripts/check_docs.py`、`/backend/tests/unit/test_check_docs.py`、生成但不提交的 `/build/traceability/TASK-P0-02-report.json`，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: Backend/Frontend 业务实现、Schema 语义、Solver。

Implementation steps: 审核 ID 唯一性；建立 registry parser/validator；验证 Task 引用存在；初始化矩阵到真实路径；定义关闭 PROD_OPEN 的证据格式。

Outputs: 可验证 registries、traceability report、无重复 ID。

Documentation impact: required

Documents to update: `/README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/architecture/repository-layout.md`、`docs/governance/document-control.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/README.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、本 Task Card。

Documentation impact rationale: 本 Task 的交付本身就是注册表、追踪规则与自动一致性合同。

Change-impact matrix rows reviewed: `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-DOCS`。

Traceability updates: REQ-001～015、全部已登记 NFR/ENG、TASK-P0-02、TEST-TRACEABILITY-VALIDATOR、`scripts/check_docs.py`、unit tests 与 validation report 的关系。

Schema changes: 治理 Markdown registry format 建立 `registry_version: 1.0.0`；无业务 Schema。

Migration: 无。

Error behavior: duplicate/missing ID、不存在路径或非法状态导致 validation fail。

Tests: TEST-TRACEABILITY-VALIDATOR；覆盖 registry parse、duplicate ID、broken reference、缺失文档影响字段、diff/impact matrix 不匹配、PROD_OPEN/SIM_ASSUMPTION 混用负例。

Benchmark impact: 无。

Simulation scenarios: 无。

Acceptance commands: `uv run python -m unittest discover -s backend/tests/unit -p "test_check_docs.py"`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-02-requirements-and-traceability.md --check-diff --report build/traceability/TASK-P0-02-report.json`。

Artifacts: `build/traceability/TASK-P0-02-report.json`（生成且由 `.gitignore` 排除）及本 Task Card 内的持久化结果摘要。

Explicitly excluded: 将 PLANNED TEST/ARTIFACT 伪装为已实现；关闭生产问题。

PROD_OPEN: OPEN-001～015 保持 OPEN，除非有外部权威证据。

SIM_ASSUMPTIONS: 只登记明确场景假设。

Rollback: 恢复到上一个 registry version，保留已经分配的 ID 不复用。

## Completion evidence

Completed at: `2026-08-19T09:48:58+08:00`

### Delivered artifacts

- Governance registries: `registry_version: 1.0.0`；15 个 REQ、9 个 NFR、6 个 ENG 根 ID，15 个 `PROD_OPEN-*`、5 个 `SIM_ASSUMPTION-*` 和 10 个 `RISK-*` 均可机器解析且无重复。
- Traceability baseline: 30 个 REQ/NFR/ENG 根 ID 在追踪矩阵中恰好各一行；`REGISTERED` 与 `PLANNED` 语义分离，未把计划能力标成已实现。
- Validator: `scripts/check_docs.py` 提供全仓库治理检查、Task/diff 范围检查、`IMPACT-*` 规则匹配及 `traceability-report.v1` JSON 报告。
- Tests: `backend/tests/unit/test_check_docs.py` 的 7 个用例覆盖 registry parse、重复 ID、断裂引用、缺失 Task 文档影响字段、diff/impact 不匹配、生产开放项与模拟假设混用，以及 ID range 展开。
- Validation report: `build/traceability/TASK-P0-02-report.json`（由 `.gitignore` 排除）记录基线提交 `cf781531d135824ec4bf2ad4b0b9a652545af0b5`、25 个 changed paths、5 个 matched impact rows、21 个 expected/observed documents、0 个 missing trace refs 和 0 个 issues。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv run python -m unittest discover -s backend/tests/unit -p "test_check_docs.py"` | 0 | PASS；运行 7 个测试，全部通过。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；107 docs、30 root IDs、30 trace rows、23 test IDs、15 open IDs、5 simulation assumptions、10 risks、9 Tasks 均通过。 |
| `uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-02-requirements-and-traceability.md --check-diff --report build/traceability/TASK-P0-02-report.json` | 0 | PASS；25 个 changed paths 命中 5 个 impact rows；报告写入指定 ignored path，issues 为空。 |

以上命令在完成状态、证据和追踪链接写入后再次执行，结果保持 PASS。

### Documentation impact and traceability

Documentation impact: `required`。`Documents to update` 中列出的 23 个文档路径全部实际更新；生成报告确认影响矩阵要求的 21 个 supporting documents 全部出现在 observed documents 中。

Traceability updates:

- REQ-001～REQ-015 → 根注册表、规范落点及逐根追踪行；这里只证明 ID/引用/路径闭环，不声称对应业务实现完成。
- NFR-TRC-001 → `scripts/check_docs.py`、`TEST-TRACEABILITY-VALIDATOR`、本节 PASS 结果和 `traceability-report.v1` 报告。
- ENG-VER-001 → 六份治理注册表的 `registry_version: 1.0.0`、版本校验规则与本节 PASS 结果。
- TASK-P0-02 → validator、unit tests、同步文档和 ignored validation report；P0-03 保持 `planned`，未自动启动。

Change-impact matrix match:

- `IMPACT-GOVERNANCE-VALIDATOR`：同步 validator 合同、CI Gate、Agent 规则、仓库布局、README 和测试策略，并以单元测试及 acceptance 验证。
- `IMPACT-GOVERNANCE-REGISTRY`：同步根注册表、开放项/假设/风险注册表、追踪规则、追踪矩阵、文档控制和 inventory。
- `IMPACT-TESTS`：登记并实现 `TEST-TRACEABILITY-VALIDATOR`，测试策略指向真实测试文件。
- `IMPACT-PHASE`：同步 current phase、Milestone index、Task index、inventory 和追踪矩阵；只记录 P0-02 完成，不改变 P0 Exit Gate 或后续 Task 状态。
- `IMPACT-DOCS`：所有实际 Markdown 改动均通过 metadata、doc ID、link、fence 与 inventory 检查。

PROD_OPEN: OPEN-001～015 全部保持 `OPEN`，未以模拟假设代替外部权威证据。SIM_ASSUMPTIONS: 未新增；仅规范现有 ID 和状态格式。Benchmark impact: 无。Schema/Migration: 只建立治理 Markdown registry format `1.0.0`，无业务 Schema 或 Migration。
