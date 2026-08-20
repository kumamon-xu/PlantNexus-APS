---
doc_id: MILESTONE-P1
title: P1 — Data & Snapshot
status: completed
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [73, 74]
last_reviewed: 2026-08-20
---

# P1 — Data & Snapshot

## Authorization

P0 superseding audit已给出 `READY`，用户于2026-08-19明确批准P0→P1。P1 Task与Exit Gate已全部完成；用户于2026-08-20核验前提后明确批准P1→P2，因此P1现为`completed`历史Milestone，P2为`active`。这不表示P2或Production能力已形成。

## Outcome

建立 CSV、Excel、一个正式 versioned Reference Adapter、Raw Staging、Normalization、Data Validation、Order Expansion、immutable PlanningSnapshot/hash和 solver-neutral PlanningProblem/hash，并让 Synthetic Generator从 Standard Import起进入同一正式数据链。

ReferenceFileAdapter是 P1正式、可测试的参考 Adapter，但在 OPEN-002/015关闭前不声明绑定任何真实 ERP/MES/WMS/CAM。显式 unit mapping可实现通用数学转换，但 OPEN-013未关闭前不得定义 Production默认单位。

## Ordered Task plan

| Order | Task | Outcome | Depends on | Planned state |
|---:|---|---|---|---|
| 1 | TASK-P1-01 | Phase-aware governance与可持续 CI handoff | TASK-P0-10 | `done` |
| 2 | TASK-P1-02 | Canonical records、Import v2、Snapshot v2合同 | P1-01 | `done` |
| 3 | TASK-P1-03 | Raw Staging、provenance、idempotent persistence | P1-02 | `done` |
| 4 | TASK-P1-04 | CSV、XLSX与ReferenceFileAdapter v1 | P1-02/03 | `done` |
| 5 | TASK-P1-05 | ID/time/unit Normalization与canonical Import bytes | P1-02/03/04 | `done` |
| 6 | TASK-P1-06 | DAG/reference/capability Data Validation与四类 exact rejection | P1-05 | `done` |
| 7 | TASK-P1-07 | DemandOrder→Lot→OperationInstance deterministic expansion | P1-06 | `done` |
| 8 | TASK-P1-08 | Immutable Snapshot builder/hash/repository | P1-03/06/07 | `done` |
| 9 | TASK-P1-09 | Solver-neutral Problem builder/hash，无 Solver | P1-07/08 | `done` |
| 10 | TASK-P1-10 | 七层 Synthetic Generator非空 canonical records | P1-02/05/06/07 | `done` |
| 11 | TASK-P1-11 | 双通道 common-ingress E2E、machine report与 CI evidence | P1-03～10 | `done` |
| 12 | TASK-P1-12 | P1 Exit Gate Audit | P1-01～11 | `done` |

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

## Exit Gate audit decision

TASK-P1-12已在P1-01～11全部`done`后执行独立审计。[Audit report](P1-exit-gate-audit-report.md)与[machine manifest](P1-exit-gate-evidence-manifest.json)记录271项full tests、11项focused migration/rejection、14/14 common-ingress、全部machine/Compose/build/docs gates及11组implementation provider artifacts均PASS，blocking gaps为空；因此P1 Exit Gate=`READY`。

TASK-P1-12 documentation implementation commit `a5d7e4a68dc12d48e36cb692500f59446f8097b4`已由GitHub run `32326616525` / job `96299073525` / artifact `9391591718`精确验证，Task现为`done`。用户于2026-08-20明确批准P1→P2后，本Milestone关闭为`completed`；后续P2 Task规划不改写P1审计或声称当时已存在Solver。

## Boundaries

- P1不创建 CpModel、IntervalVar、OR-Tools dependency、SolverBackend实现、PlanningSolution或P2 ScheduleValidator integration。
- Simulation不得绕过 staging/normalization/validation；Reference Adapter不得冒充真实 factory integration。
- OPEN-001～015可继续 OPEN；未关闭问题不阻止 Development/Simulation，但阻止依赖它们的 Production声明。
- P1 Exit Gate Audit是最后一项；用户后续明确批准已满足transition gate。P2范围仍必须由独立Task控制。

## Current execution boundary

Canonical-records.v1、Import v2、Snapshot v2、Error v1/v2与既有registry均保持原字节；schema set现为additive`2.2.0`。TASK-P1-03～11的Raw→Problem实现/provider链已闭环。TASK-P1-12以`8830a6dc566df8093b601a82c87c74a9cfd97b59`为Diff base完成独立Gate审计，implementation commit `a5d7e4a68dc12d48e36cb692500f59446f8097b4` / run `32326616525` / artifact `9391591718`形成自身provider closure并给出`READY`。TASK-P1-01～12全部`done`，P1现为`completed`；Solver只能按P2 Task另行授权实施。
