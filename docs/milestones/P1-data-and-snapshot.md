---
doc_id: MILESTONE-P1
title: P1 — Data & Snapshot
status: active
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [73, 74]
last_reviewed: 2026-08-20
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
| 12 | TASK-P1-12 | P1 Exit Gate Audit | P1-01～11 | `in_progress` |

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

TASK-P1-12在其documentation implementation commit与exact GitHub provider artifact回填前仍为`in_progress`。即使该Task闭环为`done`，Milestone仍保持`active`并等待用户明确批准P1→P2；审计没有创建P2 Task或Solver。

## Boundaries

- P1不创建 CpModel、IntervalVar、OR-Tools dependency、SolverBackend实现、PlanningSolution或P2 ScheduleValidator integration。
- Simulation不得绕过 staging/normalization/validation；Reference Adapter不得冒充真实 factory integration。
- OPEN-001～015可继续 OPEN；未关闭问题不阻止 Development/Simulation，但阻止依赖它们的 Production声明。
- P1 Exit Gate Audit是最后一项。即使 audit `READY`，仍需用户另行批准才可更新到 P2；本 Milestone不自动创建 P2 Task。

## Current execution boundary

Canonical-records.v1、Import v2、Snapshot v2、Error v1/v2与既有registry均保持原字节；schema set现以additive`2.2.0`加入error registry v2/Error v3/ImportQualityReport v1，Import v2和unit registry document version分别保持`2.0.0/2.1.0`。TASK-P1-03/04/05已分别形成Raw Staging、non-production ReferenceFileAdapter与Normalization证据；TASK-P1-06的Data Validation由implementation commit `c1ac1077fdd92e012f4050f30bab2aec4638f6ec` / run `32257767495`闭环。TASK-P1-07的`order-expansion.v1`与fixed-seed generated evidence已由implementation commit `5a3dbc14c12a107abf4052cca935e3ef59009d3d` / run `32265257468`闭环。TASK-P1-08的Snapshot builder/hash/insert-only repository已由implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee` / run `32310098594`闭环。TASK-P1-09的Problem builder/hash由implementation commit `e8c59547857d2eeace1c9f8b453a5a294cca5ef7` / run `32315513504`闭环。TASK-P1-10的七层generator与49-record replay由implementation commit `5ac08183dd03049ad02c77e6cba80c4621847e0f` / run `32319530217`闭环。P1-11以Diff base `ea56c3867651c0f03306e66936fd649526049319`实现双入口唯一common-ingress chain，implementation commit `fa6c4c1159972a30ea683ad4e6eba98342d3c344` / run `32322511227` / artifact `9390250284`与closure run `32322871271`形成精确provider evidence。TASK-P1-12以`8830a6dc566df8093b601a82c87c74a9cfd97b59`为Diff base完成本地独立Gate审计并给出`READY`，现等待自身provider closure；Solver仍须按后续阶段另行授权实施。
