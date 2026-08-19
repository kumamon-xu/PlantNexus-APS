---
doc_id: TASK-P0-06
title: SIM-MINIMAL-001 and Golden Schedule
status: planned
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [43, 46, 71, 72, 88]
last_reviewed: 2026-08-19
---

# TASK-P0-06 — SIM-MINIMAL-001 and Golden Schedule

Requirement IDs: REQ-004, REQ-005, REQ-011, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001

Depends on: TASK-P0-05

Goal: 创建可人工验证、可重复生成/导入的 `SIM-MINIMAL-001` 和正确 Golden Schedule。

Inputs: Scenario/FactoryProfile schemas、C-001～C-011 rule sheet、Standard Import skeleton。

Files allowed to change: `fixtures/deterministic/SIM-MINIMAL-001/**`、最小 fixture loader/generator、golden tests，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: CpModel、随机/启发式 Solver、生产数据、Constraint 语义。

Implementation steps: 设计 2 workshops/3 resources；加入 alternative resources、cross-workshop edge、maintenance；手算 schedule；生成 canonical package/hash；独立复核每条适用 Constraint。

Outputs: ScenarioSpec、FactoryProfile reference、import package、manual schedule、calculation note、expected validation/KPI。

Documentation impact: required

Documents to update: `docs/quality/fixtures-and-golden-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: 首个 Golden Fixture 会形成稳定 Scenario/Test/Artifact 引用和具体 SIM_ASSUMPTION。

Change-impact matrix rows reviewed: fixtures/Golden；simulation/scenarios；simulation/profiles（只审查引用）；tests/fixtures；只修改文档。

Traceability updates: REQ-004/005/011/012、NFR-COR/DET/TRC、SIM-MINIMAL-001、相关 C-ID、Golden Test IDs 和 expected artifacts。

Schema changes: 只在发现真实合同缺口时先返回 TASK-P0-03/05 修订。

Migration: 无。

Error behavior: Fixture 不符合 Schema 或人工结果不可复算时任务失败，不调整规则迎合 Fixture。

Tests: deterministic replay、Schema pass、manual rule-sheet pass、hash stability。

Benchmark impact: 只作为 correctness fixture，不作性能结论。

Simulation scenarios: SIM-MINIMAL-001。

Acceptance commands: fixture/schema validation、replay hash test、golden rule-sheet test。

Artifacts: complete deterministic fixture package 和人工验证说明。

Explicitly excluded: 真实求解逻辑、生产参数、规模 Benchmark。

PROD_OPEN: 不关闭；所有 topology/time 数值是 synthetic。

SIM_ASSUMPTIONS: 为场景每项定量假设登记并引用 ID。

Rollback: 删除该 fixture version；如果已经作为 baseline 发布，则新建修订版，不覆盖历史。
