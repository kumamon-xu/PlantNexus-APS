---
doc_id: MILESTONE-P0
title: P0 — Executable Specification
status: active
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [71, 72, 90, 98, 99, 110, 111]
last_reviewed: 2026-08-19
---

# P0 — Executable Specification

## Outcome

固定“排什么”和“什么算正确”，建立可由 Schema、Fixture、Validator Rule Sheet 和 CI 检查的仓库基线。

## Deliverables

- Repository/CI/logging/database/worker/health skeleton；
- AGENTS、Current Phase、Task Template 与追踪注册表；
- Schema skeleton、Capability Matrix、Error model；
- C-001～C-011 Constraint Catalog；
- PlanningRun、ScheduleVersion、ExportJob 三套状态机；
- Simulation architecture、FactoryProfile/ScenarioSpec schemas；
- `SIM-MINIMAL-001` 和人工 Golden Schedule；
- 至少三个明确非法 Fixture；
- PROD_OPEN 与 SIM_ASSUMPTION registers。

## Explicitly excluded

真实 CP-SAT Solver、CpModel、IntervalVar、P1 数据处理实现和任何生产参数猜测。

## Exit Gate

Schema PASS、Golden Fixture PASS、Validator Rule Sheet PASS、Scenario deterministic replay PASS、Repository Build PASS、CI PASS。所有 PROD_OPEN 已登记但无需全部关闭。

当前 `P0-DOCS` 只完成文档基线，不等于本 Milestone 完成。
