---
doc_id: TASK-P2-11
title: KPI SolverReport and Export Closure
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [4, 34, 36, 40, 55, 67, 75, 93]
last_reviewed: 2026-08-20
---

# TASK-P2-11 — KPI SolverReport and Export Closure

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-006, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-REL-001, NFR-OBS-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-08, TASK-P2-09

Start gate: complete validated Strategy/Scenario evidence formed；P2-02 report contracts固定；明确P2内部Export与P3 approval/publish边界并记录Diff base。

Goal: 形成deterministic KPI/SolverReport并完成Snapshot→Problem→validated Solution→标准内部Export package闭环，所有文件同一run/version/hash；不实现审批、发布或外部传输。

Inputs: Snapshot/Problem hashes、PlanningSolution/ValidationReport、ImportQualityReport、solver/policy versions、OBJ-001、export-package contract。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `schemas/json/kpi.v2.schema.json`、`schemas/json/export-manifest.schema.json`、`backend/app/planning/reporting/__init__.py`、`backend/app/planning/reporting/kpi.py`、`backend/app/planning/reporting/solver_report.py`、`backend/app/exporters/__init__.py`、`backend/app/exporters/package.py`、`backend/tests/contract/test_p2_output_contracts.py`、`backend/tests/integration/test_p2_export_package.py`及`Documents to update`；新增路径先精确登记。

Files forbidden to change: ScheduleVersion/ExportJob persistence/state actions、approval/publish/API、external storage/network、P3 UI/workspace、dynamic Replan、benchmark thresholds。

Implementation steps: 定义KPI v2与manifest版本；从同一validated solution计算weighted tardiness/makespan/resource load；固化solver report；生成JSON/CSV/package hashes；验证entity counts/cross-file lineage/synthetic extras；拒绝Validator FAIL/mixed run；测试deterministic logical equivalence。

Outputs: KPI/report emitters、internal standard export package、manifest/file hash/consistency tests和machine report。

Documentation impact: required

Documents to update: `docs/contracts/export-package.md`、`docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/domain/kpi-contract.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/schedule-version.md`、`docs/planning/solver-backend-contract.md`、`docs/architecture/provenance-and-versioning.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: P2 Gate要求Snapshot→Export，必须固定报告/manifest/文件一致性并清楚隔离P3状态/publish。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-REPORTING`、`IMPACT-EXPORT`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/006/009→TASK-P2-11→TEST-OUTPUT/CONTRACT/IDEMPOTENCY→KPI/SolverReport/Validation/manifest package artifacts；P3 publish remains PLANNED。

Schema changes: required；additive KPI/manifest versions，保留kpi.v1 bytes，提供positive/negative/round-trip/cross-file validation。

Migration: none；只生成in-memory/temp-dir artifacts，不创建ExportJob/ScheduleVersion持久化。

Dependency changes: none。

ADR impact: no new ADR if package remains internal and immutable-versioned；若引入publish/state/persistence或改变ScheduleVersion语义必须停止并留P3。

Error behavior: Validator未PASS、run/hash/version混用、count/hash不一致或文件缺失均拒绝export；I/O错误稳定映射且不留下宣称成功的manifest。

Tests: TEST-OUTPUT、TEST-CONTRACT-001、TEST-IDEMPOTENCY；manifest/file hash、CSV/JSON counts、same-input logical replay、mixed-run/tamper/partial-write负例、synthetic package extras。

Benchmark impact: export/report耗时只作诊断；benchmark report由P2-12提供并作为synthetic extra，不形成Production threshold。

Simulation scenarios: 使用P2-09已验证scenario生成synthetic export；不使用真实生产数据。

Acceptance commands: `uv run pytest -q backend/tests/contract/test_p2_output_contracts.py backend/tests/integration/test_p2_export_package.py`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-11-kpi-solver-report-and-export-closure.md --check-diff --report build/traceability/TASK-P2-11-report.json`；`git diff --check`。

Artifacts: deterministic export package samples/hashes、KPI/Solver/Validation reports、Task report。

Provider evidence: exact SHA required `validate`成功；artifact须包含machine output-contract report与Task report，记录run/job/steps/artifact digest/expiry。

Completion conditions: validated solution到完整internal package可确定性复验；cross-file lineage/count/hash一致；失败不产成功manifest；schema/docs/trace/provider闭环；无P3 state/publish。

Explicitly excluded: READY_FOR_REVIEW/approval/publish、ExportJob DB/worker、external storage/API/UI、ChangeReport/dynamic Replan、P3。

PROD_OPEN: OPEN-002/006/010/015保持OPEN；输出不代表真实系统接口或业务批准。

SIM_ASSUMPTIONS: synthetic export必须携带scenario/benchmark provenance并保持synthetic标识。

Rollback: 未发布internal package可丢弃重建；合同artifact不原地改写；若partial write保留failure evidence并使用新logical job retry，禁止double publish声明。
