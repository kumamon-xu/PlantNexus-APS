---
doc_id: DOC-PHASE-CURRENT
title: 当前阶段
status: living
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [73, 74, 110, 111]
last_reviewed: 2026-08-20
---

# 当前阶段：P1 — Data & Snapshot

## 阶段授权与前提

用户已于 2026-08-19 明确授权项目从 P0 进入 P1，并要求先完成 P1 Task 规划。切换前重新核对：TASK-P0-01～10 全部 `done`；[`P0 Exit Gate Audit`](milestones/P0-exit-gate-audit-report.md) 与 machine manifest 的全部必需 Gate 为 `PASS`、overall=`READY`、blocking gaps为空；仓库 HEAD包含该 superseding evidence且规划开始时 working tree干净。前提一致，因此阶段切换成立。

P0 Milestone现为 `completed`。这只表示 P0 executable-specification Gate完成，不表示任何 P1业务能力、Solver或 Production readiness已形成。

## 当前目标

建立一条确定、可追溯、双通道共用的数据链：

```text
CSV / Excel / Reference Adapter / Synthetic Generator
→ Raw Staging
→ Normalization
→ Data Validation
→ Order Expansion
→ immutable PlanningSnapshot + hash
→ solver-neutral PlanningProblem + hash
```

同 Scenario/Profile/Generator version/seed必须产生相同 Import package、Snapshot hash与Problem hash；route cycle、missing resource、unit error、missing duration必须分别明确拒绝。

## 当前 Task

`TASK-P1-02 — Canonical Import Contracts`已完成：不可变Diff base为`ac1ca00d0ecf770c24e4fe4ab1683fb32728d6ce`，implementation commit为`64c40b5c21ab0be8955e55edc007e04337cac417`，对应GitHub Actions run `32241366290`/`validate=success`。Schema set现为`2.0.0`，v1 byte fingerprints保留，合同/sample/pure precheck证据闭环。

`TASK-P1-03 — Raw Staging and Import Provenance`已完成：不可变Diff base为`d122a1b16dc1b7c91227d587b99fb8a345c7c312`，implementation commit为`25897393e31dcc0648943ec7e2e7f43dbb0e70e1`，对应GitHub Actions run `32243895717`/`validate=success`。Immutable raw batch/row、durable repository、`0002` migration、幂等/事务/provenance和data-plane guard证据闭环。

`TASK-P1-04 — CSV Excel and Formal Reference Adapter`已完成：不可变Diff base为`6c259e172be4bf3cde72a56212df3a1bad427372`，implementation commit为`9391ec021afa9e6f4f881b1538b276c84584df0e`，对应GitHub Actions run `32247079996`/`validate=success`。安全CSV/XLSX读取、versioned non-production ReferenceFileAdapter v1、Raw Staging输出、exact parser dependency与文件安全拒绝证据闭环。

`TASK-P1-05 — Normalization and Unit Time Rules`已完成：不可变Diff base为`d63926f84d9d2b7bc46bbcaff5704612af120a34`，implementation commit为`d52aa62d36e8d89eba318cb5fc586311680e030f`，对应GitHub Actions run `32252308695`/required `validate` job `96065907901`=`success`，artifact `9364897397`的provider/download digest均为`sha256:5db1ccbb242b555d8a95d36ac9cc1b1373dab95d482dbde17ab7fb369cce2966`。Additive schema set`2.1.0`、unit registry、显式MappingProfile、ID/time/unit Normalization与canonical Import bytes/hash证据闭环；validation、expansion、Snapshot/Problem builder、Solver或P2均未开始。

`TASK-P1-06 — Data Quality and Routing Validation`已完成：不可变Diff base为`75d761332204ec779477ba7242c98517cce1b68b`，implementation commit为`c1ac1077fdd92e012f4050f30bab2aec4638f6ec`，对应GitHub Actions run `32257767495`/required `validate` job `96083426251`=`success`，artifact `9366988617`的provider/download digest均为`sha256:a2e38cf942e672a073f5044b936dd2b7b7450204f5d353251566ed8b7352ca98`。Schema set`2.2.0`、error registry v2/Error v3/ImportQualityReport v1、canonical structure/reference/DAG/resource/capability/time/duration/unit evaluator及四类P1 exact rejection证据已闭环。

`TASK-P1-07 — Deterministic Order Expansion`已完成：不可变Diff base为`97728521e187f9f50715de4b04a09098bef62ddf`，implementation commit为`5a3dbc14c12a107abf4052cca935e3ef59009d3d`，对应GitHub Actions run `32265257468` / required `validate` job `96108055149`=`success`；artifact `9369917400`的provider/download digest均为`sha256:8aeb7416516f7932436bbf406d800cdbdeb8313ba9249f2709b7df71647e566e`。`order-expansion.v1`、显式Lot×RoutingOperation/edge、candidate duration/source、fact/lock投影、7项unit/2项fixed-seed Hypothesis property与property-aware CI证据已闭环；本Task未修改Schema，也未创建Snapshot/Problem、ScheduleValidator、Solver或P2能力。

`TASK-P1-08 — Immutable PlanningSnapshot and Hash`已完成：不可变Diff base=`8b4fb4c027305d3e3aa68eec0baaf73cd0598189`，implementation commit=`72670d18a29c9a10cb70f7a263c981a2b660e0ee`；GitHub Actions push run [`32310098594`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32310098594) / required `validate` job `96251145353`及全部步骤=`success`。Artifact `9386127863`的provider/download digest同为`sha256:69d68183bad614631df07234a3ca88508379ab89ec715f811ee7f529d6f17e0c`，其中Task report精确记录该SHA、41 committed paths、6 impact rows、0 issues。本地Task suite=`25 passed`、full repository=`238 passed`，PlanningSnapshot v2 canonical projection、deterministic ID/hash、insert-only repository与`0003` migration证据闭环。

`TASK-P1-09 — PlanningProblem Builder and Hash`已完成：不可变Diff base=`100e2573a76462ad2a0751e9e4aae7990c9048dd`，implementation commit=`e8c59547857d2eeace1c9f8b453a5a294cca5ef7`；GitHub Actions push run [`32315513504`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32315513504) / required `validate` job `96266776018`及全部步骤=`success`。Artifact `9387907707`的provider/download digest同为`sha256:1ede296252bb04e9015240e13222eaf4ee783bc6e7582012cac0a441fd624568`，Task report精确记录该SHA、30 committed paths、5 impact rows、0 issues。本地Task suite=`34 passed`、full repository=`253 passed`；solver-neutral builder/hash、fixed replay vector和unsupported-boundary证据闭环。建议下一项执行`TASK-P1-10 — Synthetic Generator Canonical Records`，但尚未启动。

用户于2026-08-19进一步授权：后续每个P1 Task完成本地验收并提交后，可直接push当前`main`并核验对应GitHub CI。该授权只覆盖当前Task完成后的push/provider核验，不自动启动下一Task、不改变Task允许范围，也不授权进入P2。

后续顺序以 [`P1 Milestone`](milestones/P1-data-and-snapshot.md) 与 [`Task Card 索引`](tasks/README.md) 为准；只有依赖为 `done` 后才可启动下一 Task。

## 当前允许

- 仅按 P1 Task Card建立 canonical Import、Raw Staging、CSV/XLSX Reference Adapter、Normalization、Data Validation、Order Expansion、Snapshot/Problem builder与 hash；
- 让 Synthetic Generator输出非空 Standard Import并从 staging后走相同产品链；
- 创建 P1所需 versioned Schema/error/report/fixture/test/migration和机器证据；
- 使用明确 synthetic Profile/Scenario/seed继续开发，即使 PROD_OPEN未关闭；
- 更新 P1 CI、追踪、文档和 Exit Gate audit，但必须保留 P0回归和失败证据。

## 当前禁止

- 在未开始对应 Task前修改其业务代码，或修改 Task允许范围外文件；
- 创建 `CpModel`、`IntervalVar`、OR-Tools依赖、真实 Solver/Strategy/Solution、ScheduleValidator P2集成或任何 P2 Task Card；
- 绕过 Raw Staging、Normalization或Data Validation，让 Simulation直接构造 Snapshot/Problem/Solver；
- 猜 ERP/MES/WMS/CAM字段、生产单位、timezone、lot split、duration fallback、transport、calendar或其他 PROD_OPEN答案；
- 将 ReferenceFileAdapter、synthetic fixture或测试数据库声明为真实生产 Adapter/数据/容量；
- 创建产品 API、审批/发布、Replan、Benchmark Solver或 Production deployment，除非后续 Milestone另行授权。

## P1 Task 规划状态

P1共规划12个Task：phase governance/CI、canonical contracts、Raw Staging、CSV/Excel/reference adapter、Normalization、Data Validation、Order Expansion、Snapshot、Problem hash、Synthetic Generator、common-ingress Gate evidence，最后为P1 Exit Gate Audit。TASK-P1-01～09=`done`，TASK-P1-10～12=`planned`；建议下一项执行TASK-P1-10但尚未启动，P1 Milestone继续`active`，不得进入P2。

## 阶段完成条件

- CSV、Excel和一个正式 versioned Reference Adapter均通过合同/安全测试；
- Raw Staging、Normalization、Data Validation和Order Expansion具有可复验实现证据；
- PlanningSnapshot immutable且 hash可重放；
- Synthetic Generator与Reference Adapter从 staging后使用同一产品链；
- same scenario+seed的 import bytes/hash、snapshot hash、problem bytes/hash一致；
- route cycle、missing resource、unit error、missing duration exact rejection全部通过；
- 全部 P1 Task完成，P1 Exit Gate Audit给出真实 `READY` 且用户再次明确批准后，才允许请求进入 P2。

Task全部 `done` 不自动等于 Phase Done；P1 Exit Gate Audit失败时保持 P1并创建有界 remediation Task。
