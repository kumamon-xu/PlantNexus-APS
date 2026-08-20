---
doc_id: DOC-PHASE-CURRENT
title: 当前阶段
status: living
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [73, 74, 75, 76, 110, 111]
last_reviewed: 2026-08-20
---

# 当前阶段：P2 — CP-SAT Vertical Slice

## 阶段授权与证据

用户于2026-08-20明确批准P1→P2 phase transition，并授权先进行P2 Task规划。切换前已重新核验：TASK-P1-01～12全部`done`；[P1 Exit Gate audit](milestones/P1-exit-gate-audit-report.md)与[machine manifest](milestones/P1-exit-gate-evidence-manifest.json)给出overall=`READY`、blocking gaps为空；audit implementation `a5d7e4a68dc12d48e36cb692500f59446f8097b4`是规划基线`098c44059856e3203d95d046fea44894b5cf414b`的祖先。

GitHub上audit implementation的push run `32326616525` / required `validate` job `96299073525` / artifact `9391591718`均success；规划基线自身的run `32327121469` / job `96300506550` / artifact `9391753870`也精确绑定`098c44059856e3203d95d046fea44894b5cf414b`并success。规划启动时`main=origin/main`且working tree clean，因此前提一致，阶段切换成立。

P1 Milestone现为`completed`，P2 Milestone为`active`。这只授权P2范围内的Task规划与后续逐Task实现，不表示Solver、Validator、Benchmark、Export或Production能力已经形成。

## 当前目标

建立唯一受支持的P2纵向链：

```text
PlanningSnapshot
→ PlanningProblem v2
→ PlanningPolicy + SolveLimits
→ GlobalCpSatStrategy + CpSatBackend
→ PlanningSolution
→ independent ScheduleValidator
→ KPI + SolverReport + internal Export package
→ Reference Scheduler / BenchmarkRunner
```

只实现C-001～C-011与OBJ-001；Gate覆盖Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock和XS/S/M，并记录model size、build、first feasible、objective、bound、gap、memory、Validator与Snapshot→Export证据。

## 当前Task与启动边界

`TASK-P2-00 — P2 Phase Transition and Task Planning Governance`、`TASK-P2-01 — PlanningProblem v2 Contract Gap Closure`与`TASK-P2-02 — Planning Machine Contracts and Status`均已闭环为`done`。P2-02 implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`的GitHub push run `32342489997`、required `validate` job `96344226221`与artifact `9396828326`均精确绑定该SHA并为success；closure HEAD `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`的run `32342949743` / job `96345556588` / artifact `9396984310`也成功并作为P2-03 Diff base。

用户已于2026-08-20明确授权执行`TASK-P2-03 — OR-Tools and SolverBackend Foundation`；该Task以clean、provider-verified `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`进入`in_progress`，并在依赖变更前接受ADR-0011。范围只允许exact-pin OR-Tools、`planning/backends/cp_sat` adapter/status/parameter/version engineering foundation、机器报告、测试与治理兼容；Problem/Policy/Solution/Report合同字节和语义继续只读。

P2-02把global schema set additive提升到`2.4.0`，新增四个互相离线解析的v1 document contract，并以`CONTRACT_SAMPLE`/`SOLVER_RUN`显式区分shape样例与真实运行。该发布样例的`not-installed`是P2-02历史shape证据，不随P2-03安装依赖而改写。P2-03的empty/model-invalid smoke只证明binary/API/status/parameter边界，必须标记business feasibility未评估；不实现C-001～C-011、OBJ-001、candidate、Validator或Benchmark baseline。P2-04及P2-05～14仍为`planned`且未获启动授权。

## 当前允许

- 按已授权Task在P2范围内演进solver-neutral Problem/Policy/Limits/Solution/Report合同；
- exact pin OR-Tools并保持其只存在于CP-SAT Backend；
- 逐项实现C-001～C-011、OBJ-001、formal independent Validator、Reference Schedulers、internal Export与BenchmarkRunner；
- 使用versioned Simulation Policy/Profile/Scenario运行correctness与XS/S/M；
- 每个Task完成本地验收后，在用户本次授权边界内提交并直接push当前`main`，再核验exact required `validate`和artifact。

## 当前禁止

- 未经用户另行明确授权启动TASK-P2-04或任何P2-05～14实现；
- 修改Task允许范围外文件、预填PASS/provider evidence或跳过独立Validator；
- 实现C-012～C-018、OBJ-002 Stability、动态Replan、ExecutionSimulator、P3 Workspace/审批/发布状态；
- 把UNKNOWN写成INFEASIBLE、FEASIBLE写成OPTIMAL，或以hint代替Execution Fact/HARD lock；
- 猜测Production权重、calendar/transport/default solve limits、性能阈值或真实system authority；
- 将synthetic correctness/XS/S/M结果外推为Production SLA、容量或readiness。

## 阶段完成条件

- Problem/Policy/Limits/Solution/Report版本化合同与solver/backend隔离成立；
- C-001～C-011与OBJ-001由CP-SAT实现且formal independent Validator全部PASS；
- Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock、Property/Mutation与Reference Scheduler证据形成；
- Snapshot→Export internal package闭环，报告/hash/版本一致；
- XS/S/M报告包含全部Gate字段且有provider artifact，不形成Production承诺；
- TASK-P2-01～13全部`done`后，最后执行TASK-P2-14 Exit Gate Audit；只有audit=`READY`且用户再次明确批准，才允许请求进入P3。

Task全部完成或audit READY都不自动切换P3；失败时保持P2并建立有界remediation Task。
