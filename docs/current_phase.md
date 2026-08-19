---
doc_id: DOC-PHASE-CURRENT
title: 当前阶段
status: living
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [73, 74, 110, 111]
last_reviewed: 2026-08-19
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

`TASK-P1-02 — Canonical Import Contracts`已按用户指令进入`in_progress`，不可变Diff base为`ac1ca00d0ecf770c24e4fe4ab1683fb32728d6ce`。当前只发布canonical records、Import v2、PlanningSnapshot v2、schema set与pure contract evidence；不实现Adapter、staging、normalization、validation、expansion、builder、Solver或P2。

本Task的工作版本已将schema set提升为`2.0.0`并保留v1 byte fingerprints；新增合同、sample和pure precheck在完成全量本地验收、提交及GitHub provider CI前仍只视为`in_progress`证据，不据此启动TASK-P1-03。

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

P1共规划12个Task：phase governance/CI、canonical contracts、Raw Staging、CSV/Excel/reference adapter、Normalization、Data Validation、Order Expansion、Snapshot、Problem hash、Synthetic Generator、common-ingress Gate evidence，最后为P1 Exit Gate Audit。TASK-P1-01=`done`，TASK-P1-02=`in_progress`，TASK-P1-03～12仍为`planned`；P1 Milestone继续`active`，不得进入P2。

## 阶段完成条件

- CSV、Excel和一个正式 versioned Reference Adapter均通过合同/安全测试；
- Raw Staging、Normalization、Data Validation和Order Expansion具有可复验实现证据；
- PlanningSnapshot immutable且 hash可重放；
- Synthetic Generator与Reference Adapter从 staging后使用同一产品链；
- same scenario+seed的 import bytes/hash、snapshot hash、problem bytes/hash一致；
- route cycle、missing resource、unit error、missing duration exact rejection全部通过；
- 全部 P1 Task完成，P1 Exit Gate Audit给出真实 `READY` 且用户再次明确批准后，才允许请求进入 P2。

Task全部 `done` 不自动等于 Phase Done；P1 Exit Gate Audit失败时保持 P1并创建有界 remediation Task。
