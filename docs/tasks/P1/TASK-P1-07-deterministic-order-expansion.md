---
doc_id: TASK-P1-07
title: Deterministic Order Expansion
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [18, 19, 20, 21, 22, 73, 74]
last_reviewed: 2026-08-19
---

# TASK-P1-07 — Deterministic Order Expansion

Requirement IDs: REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-06

Goal: 将已验证的 DemandOrder/ProductionOrder/显式 ProductionLot 与 RoutingVersion 确定性展开为 OperationInstance、候选资源选项和 precedence edges，并保留全部 source lineage；不得自行猜 lot splitting 或 duration fallback。

Inputs: valid canonical Import v2、domain/operation contracts、OPEN-008/014、P1 DataValidation PASS report。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `backend/app/domain/production.py`、`backend/app/normalization/order_expansion.py`、`backend/app/normalization/__init__.py`、`backend/tests/unit/test_order_expansion.py`、`backend/tests/property/test_order_expansion_properties.py`、`pyproject.toml`、`uv.lock`、生成但不提交的 `build/traceability/TASK-P1-07-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: Schema/error registry、Adapter/Staging、unit/time Normalizer、DataValidation rules、Snapshot/Problem builder、Simulation、API、Solver、自动 lot split/merge或 duration预测。

Implementation steps: 只接受 source明确提供的 ProductionLot/quantity与 RoutingVersion；按稳定 ID algorithm实例化 operation和 edge；复制 candidate级 final duration/source version、release/material gates、COMPLETED/RUNNING facts与locks；COMPLETED保留在 Snapshot事实但不进入未来 Problem；同输入/版本输出稳定排序；property tests覆盖 DAG分支/汇合、跨车间和多候选。

Outputs: pure order-expansion service、versioned expansion provenance、unit/property evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/domain/domain-model.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/planning/constraint-catalog.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-07-deterministic-order-expansion.md`。

Documentation impact rationale: Order/Lot/OperationInstance lineage与执行事实进入正式 P1行为，影响 Domain、Import、Problem输入和 Property测试口径。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-003/009、NFR-DET/TRC、ENG-SOL/ERR/VER → TASK-P1-07 → TEST-ORDER-EXPANSION-001/TEST-RUNNING → OperationInstance/edge artifacts和 property regressions。

Schema changes: none；消费 TASK-P1-02 canonical contract，若发现字段不足必须停止并先升版，禁止在代码内藏字段。

Migration: none。

Error behavior: missing explicit lot、routing version mismatch、missing option duration/source、duplicate derived ID、invalid execution fact或请求 SPLIT_MERGE明确拒绝；不得自动修复。

Tests: `TEST-ORDER-EXPANSION-001`、`TEST-RUNNING`；serial/parallel/merge/cross-workshop、candidate duration、source lineage、completed/running、explicit lots、stable IDs/order、property generation/shrinking与 missing/fallback负例。

Benchmark impact: property样例记录 entity counts但不声称性能；无 Solver benchmark。

Simulation scenarios: 使用合法 synthetic canonical inputs；随机失败保存 seed/minimized example/version/hash，不修改正式 P0 fixture。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/domain/production.py backend/app/normalization backend/tests/unit/test_order_expansion.py backend/tests/property/test_order_expansion_properties.py`；`uv run pyright backend/app/domain/production.py backend/app/normalization backend/tests/unit/test_order_expansion.py backend/tests/property/test_order_expansion_properties.py`；`uv run pytest -q backend/tests/unit/test_order_expansion.py backend/tests/property/test_order_expansion_properties.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-07-deterministic-order-expansion.md --check-diff --report build/traceability/TASK-P1-07-report.json`；`git diff --check`；`uv build`。

Artifacts: expansion test/property corpus、seed/minimized failures（如有）、traceability report。

Completion conditions: 同 valid canonical input + expansion version产生相同 instances/edges；显式 lot与 lineage完整；missing duration/lot/unsupported split负例通过；无默认/AI/Solver；docs/trace/governance PASS。

Explicitly excluded: 自动 lot sizing/splitting、BOM/MRP、duration fallback/prediction、Snapshot persistence、Problem/Solver、schedule validation。

PROD_OPEN: OPEN-007/008/014/015 保持 OPEN；Production必须显式提供本 Task所需事实。

SIM_ASSUMPTIONS: property/generated values显式 synthetic并记录 seed，不成为业务默认值。

Rollback: expansion version不可重解释历史 output；回退 consumer时保留来源与旧版本，发现错误发布新版本并回放 Snapshot。

## Completion evidence

执行时填写 expansion version、property seeds/cases、changed paths、命令结果、开放问题和文档影响。
