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

`TASK-P2-00 — P2 Phase Transition and Task Planning Governance`已完成：implementation commit=`3298229fae89a54e0641f5907ad90c4fa81569bf`，GitHub run `32332003608` / required job `96314305102` / artifact `9393345593`均success，artifact内Task report为32 paths/5 Impact Rules/19 checks/0 issues。用户随后明确授权执行`TASK-P2-01 — PlanningProblem v2 Contract Gap Closure`；其Diff base固定为`617dd0fb8d6543dc2c9be6ac1e868f751763603d`，状态为`in_progress`，TASK-P2-02～14仍为`planned`且不得启动。

P2-01已以ADR-0010和additive schema set`2.3.0`建立opt-in `planning-problem.v2`：显式表达sourced due/priority、capacity=1完整Resource事实、active HARD/SOFT locks及COMPLETED→active历史完成锚点/lag；v1 Schema/sample/default API/fixed hashes保持不变。本地合同、replay与property证据已形成，Task仍须等待implementation commit的exact provider `validate`和artifact后才能关闭。

## 当前允许

- 按已授权Task在P2范围内演进solver-neutral Problem/Policy/Limits/Solution/Report合同；
- exact pin OR-Tools并保持其只存在于CP-SAT Backend；
- 逐项实现C-001～C-011、OBJ-001、formal independent Validator、Reference Schedulers、internal Export与BenchmarkRunner；
- 使用versioned Simulation Policy/Profile/Scenario运行correctness与XS/S/M；
- 每个Task完成本地验收后，在用户本次授权边界内提交并直接push当前`main`，再核验exact required `validate`和artifact。

## 当前禁止

- 未经另行指令启动TASK-P2-02或任何后续P2实现；
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
