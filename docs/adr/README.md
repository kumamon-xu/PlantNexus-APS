---
doc_id: DOC-ADR-INDEX
title: Architecture Decision Records
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [97]
last_reviewed: 2026-08-19
---

# Architecture Decision Records

ADR 记录 Architecture、Solver Backend、Constraint semantics、Objective hierarchy、PlanningProblem、Schedule state machine、Data authority、Decomposition、Advanced APS capability 和 Production performance threshold 的决定。

ADR 状态：`proposed`、`accepted`、`rejected`、`superseded`。Accepted ADR 不重写历史；变更通过新 ADR `supersedes` 旧记录。

ADR-0001～0009 是从 implementation spec 0.3.0 已明确决定中建立的基线记录。它们不表示对应代码已经实现。

TASK-P0-03 的 Schema/type skeleton 落实 ADR-0001（共同入口 envelope）、ADR-0003（Solver-neutral Problem）、ADR-0007（immutable Snapshot）、ADR-0008（UTC/seconds/ticks）和 ADR-0009（Production/Simulation 标识隔离）的既有决定，没有改变这些决定，因此不新增 ADR。Problem builder、hash、Solver 或字段权威若偏离这些决定，必须另建 ADR，不能借 skeleton 隐式修改。

TASK-P0-04 把总规既有 C-001～C-018、ADR-0005 独立 Validator 边界和 ADR-0007 ScheduleVersion 不可变/发布状态固定为 versioned rule/state contracts。没有改变 Constraint semantics、Schedule state machine、PlanningProblem、Solver backend 或发布规则，因此不新增 ADR。`EXPORT_FAILED → EXPORTING` 只是既有“可重试”合同的显式 pair；若未来改变 pair/guard、允许 published mutation、共享 Solver validator logic 或启用高级 capability，必须新建 superseding ADR。

TASK-P0-05 落实 ADR-0001（Generator 终止于 Standard Import）与 ADR-0009（synthetic flag/Production target rejection），没有改变共同入口或环境隔离决定；empty package 不绕过 P1 pipeline。Profile/Scenario/Generator versions、canonical hash 和 manifest 属于总规既定 provenance，不修改 PlanningProblem/Constraint/Solver/状态/Data Authority，因此不新增 ADR。若未来允许 Production target、Generator 直接产 Problem 或改变隔离层级，必须新建 superseding ADR。

TASK-P0-08 落实 ADR-0002 的 health API/Celery Worker 分进程骨架与 heartbeat/lease/attempt/idempotency 原语，以及 ADR-0009 的 environment/data-plane fail-closed config；不改变 Modular Monolith、Solver 分离或 Production/Simulation 隔离决定，因此不新增 ADR。当前 Worker 无 Solver/业务 task，Compose 也不是 production deployment；若未来共享 API process 执行 Solver、允许 production Simulation route、降低 DB 隔离、改变 Job/Export state semantics 或引入分布式 topology，必须另建 ADR。OR-Tools 未安装，Solver upgrade ADR/Gate 不触发。

TASK-P1-02以schema set`2.0.0`落实ADR-0007的immutable Snapshot事实边界、ADR-0008的UTC/整数秒语义与ADR-0009的Production/Synthetic provenance隔离，并保留ADR-0003的Solver-neutral consumer边界。它没有改变这些已接受决定，也没有决定外部字段权威、hash算法、persistence或Solver，因此不新增ADR。若后续允许Production携带synthetic provenance、修改UTC/seconds、原地改写Snapshot或隐藏source mapping，必须先建立superseding ADR。

TASK-P1-04落实总规§9/§95和ADR-0001的共同文件入口边界：Reference Adapter只形成Raw Staging，不能绕过后续Normalization/DataValidation；Production/Simulation provenance继续服从ADR-0009。固定三列reference transport、read-only XLSX与安全限额不改变Architecture/Data Authority/PlanningProblem/Solver/状态/发布决定，因此不新增ADR。若未来把它声明为真实系统authority、允许macro/formula/external execution、让Adapter直接产Canonical/Snapshot或降低data-plane隔离，必须先提交相应superseding ADR与授权证据。
