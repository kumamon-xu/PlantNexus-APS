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

TASK-P0-01～08 已完成 repository/governance/contracts/Scenario/Golden/Validator 及 exact build、CI workflow、structured logging、health/config、DB/Redis/Celery、job reliability/idempotency、reversible migration skeleton 的本地 evidence。TASK-P0-09 于 2026-08-19 独立复验 Schema、Golden、Validator Rule Sheet、Scenario replay 与 Repository Build 均为 `PASS`；但 workflow 的 docs step硬编码 TASK-P0-08，在 P0-09 commit 上 exit 1，当时 provider evidence 为 `NOT_RUN`，故审计结论为 CI `FAIL`、总体 `NOT_READY` / `NO_GO`。

TASK-P0-10 已以 Diff base `5d8bb51e06add1afc2f53861cf53c7a2ba45a272` 进入 `in_progress`；GitHub baseline run `32227247262` 真实重现旧 docs step failure，workflow/test 现已交接到 TASK-P0-10，但 successful provider run 与 required `validate` check 在最终证据形成前仍不得预判。因此 P0 暂保持 `active` / `NOT_READY`；只有重新审计全部 Gate PASS 后才可声明 ready，且仍需用户明确确认才能进入 P1。
