---
doc_id: TASK-P1-04
title: CSV Excel and Formal Reference Adapter
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [3, 11, 15, 63, 73, 91, 95]
last_reviewed: 2026-08-19
---

# TASK-P1-04 — CSV, Excel, and Formal Reference Adapter

Requirement IDs: REQ-001, REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-SEC-001, NFR-REL-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-02, TASK-P1-03

Goal: 实现安全的 CSV 与 XLSX 读取，以及一个版本化 `ReferenceFileAdapter v1`，把两种文件格式转换为相同 Raw Staging contract；该 Adapter 是正式可测试的参考 Adapter，不声称已绑定任何真实 ERP/MES/WMS/CAM。

Inputs: canonical import v2、Raw Staging protocol、OPEN-002/013/015、文件导入安全规则。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `backend/app/importers/adapter.py`、`backend/app/importers/csv_reader.py`、`backend/app/importers/excel_reader.py`、`backend/app/importers/reference_file_adapter.py`、`backend/app/importers/__init__.py`、`backend/tests/contract/test_input_adapters.py`、`backend/tests/integration/test_reference_file_adapter.py`、`pyproject.toml`、`uv.lock`、生成但不提交的 `build/traceability/TASK-P1-04-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: canonical Schema、Raw Staging migration/repository、normalization/data validation/order expansion、Snapshot/Problem、Simulation Generator、API、Solver、真实客户文件、Production credentials。

Implementation steps: 定义 adapter protocol/version/capability与 source manifest；CSV 使用显式 UTF-8/dialect/header规则，XLSX 使用 exact-pinned openpyxl并只读数据；限制扩展名/大小/sheet/row/column，拒绝 XLS/XLSM、macro、公式、外部链接、重复/未知列和路径穿越；两种格式只产出相同 staged rows/source locations，字段语义留给后续 Normalization。

Outputs: CSV reader、XLSX reader、ReferenceFileAdapter v1、locked dependency、正反 contract/integration evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/README.md`、`docs/architecture/data-authority.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/domain/error-model.md`、`docs/operations/security.md`、`docs/governance/prod-open-register.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/benchmark-regression.md`、`docs/planning/solver-backend-contract.md`、`docs/adr/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-04-csv-excel-reference-adapter.md`。

Documentation impact rationale: 新增外部文件边界、runtime dependency、Adapter version与拒绝行为，必须同步安全、技术栈、数据权威和测试合同。

Change-impact matrix rows reviewed: `IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/009、NFR-TRC/SEC/REL、ENG-ARCH/ERR/VER → TASK-P1-04 → TEST-IMPORT-ADAPTER-001 → CSV/XLSX/reference-adapter contract tests、lock与 staged provenance。

Schema changes: none；Adapter manifest/version使用 P1-02 已发布合同。

Migration: none。

Error behavior: 不支持格式、超限、编码/header/sheet错误、formula/macro/external-link、重复/未知字段均形成结构化 DATA_ERROR与 source location；不执行内容、不拼 shell/SQL、不静默取公式缓存值。

Tests: `TEST-IMPORT-ADAPTER-001`；CSV/XLSX semantic parity、version rejection、file hash/source location、limits、malicious/formula/macro/external-link、unknown/missing/duplicate headers、idempotent restaging。

Benchmark impact: 记录小型 synthetic 文件 parse 行数/耗时，仅作回归；不设生产吞吐承诺，dependency 变化不触发 Solver benchmark。

Simulation scenarios: 测试文件仅在临时目录生成并标记 synthetic；不提交真实数据、不修改正式 Scenario。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/importers backend/tests/contract/test_input_adapters.py backend/tests/integration/test_reference_file_adapter.py`；`uv run pyright backend/app/importers backend/tests/contract/test_input_adapters.py backend/tests/integration/test_reference_file_adapter.py`；`uv run pytest -q backend/tests/contract/test_input_adapters.py backend/tests/integration/test_reference_file_adapter.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-04-csv-excel-reference-adapter.md --check-diff --report build/traceability/TASK-P1-04-report.json`；`git diff --check`；`uv build`。

Artifacts: exact dependency lock、adapter contract results、traceability report；不提交输入 workbook/credentials。

Completion conditions: CSV/XLSX 对等输入产生相同 staged semantic rows与 provenance；全部恶意/越界路径明确拒绝；ReferenceFileAdapter version固定且明确 non-production binding；lock、tests、docs/diff governance PASS。

Explicitly excluded: 真实 ERP/MES/WMS/CAM Adapter、业务字段权威决定、Normalization/Snapshot/Problem、宏/公式执行、API、Solver。

PROD_OPEN: OPEN-002/013/015 保持 OPEN；ReferenceFileAdapter 不能关闭真实接口/单位/字段权威问题。

SIM_ASSUMPTIONS: 测试表格只表达 synthetic contract样例，不新增生产参数。

Rollback: 移除 reference adapter与 pinned dependency并保留 staged records/audit；不得把旧 workbook按另一版本静默重解释。

## Completion evidence

执行时填写 dependency/version、changed paths、正反文件矩阵、命令结果、文档与追踪证据。
