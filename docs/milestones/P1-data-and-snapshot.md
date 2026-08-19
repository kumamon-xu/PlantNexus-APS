---
doc_id: MILESTONE-P1
title: P1 — Data & Snapshot
status: active
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [73, 74]
last_reviewed: 2026-08-19
---

# P1 — Data & Snapshot

## Authorization

P0 superseding audit已给出 `READY`，用户于 2026-08-19 明确批准 P0→P1 phase transition。P1现为当前 active Milestone；该授权允许创建并依序执行 P1 Task，不授权 P2或 Production release。

## Outcome

建立 CSV、Excel、一个正式 versioned Reference Adapter、Raw Staging、Normalization、Data Validation、Order Expansion、immutable PlanningSnapshot/hash和 solver-neutral PlanningProblem/hash，并让 Synthetic Generator从 Standard Import起进入同一正式数据链。

ReferenceFileAdapter是 P1正式、可测试的参考 Adapter，但在 OPEN-002/015关闭前不声明绑定任何真实 ERP/MES/WMS/CAM。显式 unit mapping可实现通用数学转换，但 OPEN-013未关闭前不得定义 Production默认单位。

## Ordered Task plan

| Order | Task | Outcome | Depends on | Planned state |
|---:|---|---|---|---|
| 1 | TASK-P1-01 | Phase-aware governance与可持续 CI handoff | TASK-P0-10 | `in_progress` |
| 2 | TASK-P1-02 | Canonical records、Import v2、Snapshot v2合同 | P1-01 | `planned` |
| 3 | TASK-P1-03 | Raw Staging、provenance、idempotent persistence | P1-02 | `planned` |
| 4 | TASK-P1-04 | CSV、XLSX与ReferenceFileAdapter v1 | P1-02/03 | `planned` |
| 5 | TASK-P1-05 | ID/time/unit Normalization与canonical Import bytes | P1-02/03/04 | `planned` |
| 6 | TASK-P1-06 | DAG/reference/capability Data Validation与四类 exact rejection | P1-05 | `planned` |
| 7 | TASK-P1-07 | DemandOrder→Lot→OperationInstance deterministic expansion | P1-06 | `planned` |
| 8 | TASK-P1-08 | Immutable Snapshot builder/hash/repository | P1-03/06/07 | `planned` |
| 9 | TASK-P1-09 | Solver-neutral Problem builder/hash，无 Solver | P1-07/08 | `planned` |
| 10 | TASK-P1-10 | 七层 Synthetic Generator非空 canonical records | P1-02/05/06/07 | `planned` |
| 11 | TASK-P1-11 | 双通道 common-ingress E2E、machine report与 CI evidence | P1-03～10 | `planned` |
| 12 | TASK-P1-12 | P1 Exit Gate Audit | P1-01～11 | `planned` |

任务依赖是开始门，不是建议顺序。任何 Task若需要扩大文件范围、改变合同/ADR或关闭 PROD_OPEN，必须先停止并修订 Task Card。

## Deliverables

- versioned canonical import/data dictionary及兼容规则；
- immutable Raw Staging batch/row provenance与reversible migrations；
- safe CSV/XLSX readers和ReferenceFileAdapter v1；
- explicit mapping/unit/time normalization与canonical bytes；
- deterministic ImportQualityReport及route/resource/unit/duration拒绝；
- deterministic Order/Lot/OperationInstance expansion；
- PlanningSnapshot v2 builder、hash和insert-only persistence；
- PlanningProblem v1 builder/hash，保持 solver-neutral且不安装 OR-Tools；
- seven-layer Synthetic Generator和versioned P1 regression Scenario；
- `p1-data-pipeline-report.v1`、P1 CI artifact与 Exit Gate audit/manifest。

## Exit Gate

必须证明：

```text
same ScenarioSpec + FactoryProfile + Generator Version + seed
→ byte-identical Standard Import package + dataset hash
→ identical PlanningSnapshot bytes + snapshot hash
→ identical PlanningProblem bytes + problem hash
```

并分别证明：

```text
route cycle       → ROUTE_CYCLE / DATA_ERROR
missing resource  → MISSING_RESOURCE / DATA_ERROR
unit error        → UNIT_CONVERSION_ERROR / DATA_ERROR
missing duration  → MISSING_DURATION / DATA_ERROR
```

Gate证据还必须覆盖 CSV/XLSX/Reference Adapter、Raw Staging provenance、Normalization、Order Expansion、Snapshot immutability、Production/Synthetic isolation、repository build和文档治理。没有真实证据的项为 `NOT_RUN`/`FAIL`，不能用其他 PASS抵消。

## Boundaries

- P1不创建 CpModel、IntervalVar、OR-Tools dependency、SolverBackend实现、PlanningSolution或P2 ScheduleValidator integration。
- Simulation不得绕过 staging/normalization/validation；Reference Adapter不得冒充真实 factory integration。
- OPEN-001～015可继续 OPEN；未关闭问题不阻止 Development/Simulation，但阻止依赖它们的 Production声明。
- P1 Exit Gate Audit是最后一项。即使 audit `READY`，仍需用户另行批准才可更新到 P2；本 Milestone不自动创建 P2 Task。
