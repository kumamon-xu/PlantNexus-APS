---
doc_id: DOC-PHASE-CURRENT
title: 当前阶段
status: living
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [71, 72, 110]
last_reviewed: 2026-08-19
---

# 当前阶段：P0 — Executable Specification

## 当前目标

先固定“排什么”和“什么算正确”，把总规转换成可追踪、可审查、可由后续代码执行的规格基线。

## 已完成子阶段

```text
P0-DOCS — Documentation Baseline
```

该子阶段只生产文档与任务边界，不授权实现应用代码、Schema、Fixture、CI 或基础设施。

状态：`BASELINE_COMPLETE`（2026-08-19）。已生成 107 份仓库内 Markdown 文档及根目录 Agent 薄入口；元数据/ID、Markdown fence、相对链接、Task 必需字段和总规镜像一致性检查均通过。该状态只表示文档基线完成。

## 最新完成 Task

```text
TASK-P0-10 — CI Workflow Handoff and Provider Evidence Remediation
```

Task 状态：`done`（2026-08-19T15:52:57+08:00）。workflow exact docs diff 已从 TASK-P0-08 交接到 TASK-P0-10，integration contract 禁止旧引用；implementation commit `036bc23bc0ac4d60aab131c0d44eda5508e844d4` 的 GitHub run `32228647627`、`validate` job、artifact `9356432918` / digest 全部成功，`main` 已 protected 且 required `validate`。提交前/后本地 acceptance 与 superseding audit 全部 PASS，`P0-GAP-001/002` 已关闭。

TASK-P0-01～10 均为 `done`。[P0 superseding audit](milestones/P0-exit-gate-audit-report.md) 将全部 Exit Gate 判定为 `PASS`，P0 Gate 为 `READY`。Milestone 仍保持 `active`、当前 Phase 仍为 P0，因为用户尚未明确批准 phase transition；本 Task 不自动进入 P1。

## 当前 Task

无。TASK-P0-10 已完成；当前只等待用户对 P0 → P1 phase transition 给出另一条明确指令。未经该指令不创建/执行 P1 Task。

## 当前允许

- 建立 `docs` 文档体系；
- 维护和验证 TASK-P0-01 已形成的可构建空仓库骨架、Python/uv 元数据和结构性文档检查；
- 镜像并登记规格版本；
- 拆分范围、原则、需求、能力、架构、领域、约束和仿真规则；
- 建立 Agent 规则、Milestone、ADR、注册表和 P0 Task Card；
- 初始化 `REQ / NFR / ENG` 追踪结构；
- 建立 P0 规则表、状态/错误/capability 纯合同及机器一致性检查；
- 建立 versioned Simulation Schema、纯 Generator protocols、显式 seed/canonical hash 与 synthetic isolation 合同；
- 维护 `SIM-MINIMAL-001@1.0.0` deterministic correctness fixture、人工 Golden 与只读 replay/hash evidence；
- 在不导入 Solver/backend 的边界内维护 P0-07 fixture-local Validator Rule Sheet evaluator 与非法 mutation evidence；
- 按 TASK-P0-08 明确文件边界建立 health-only API、工程基础设施、通用 Job reliability、CI 与构建骨架；
- 维护 TASK-P0-10 已形成的 workflow handoff、GitHub Actions/artifact/required-check evidence 和 P0 `READY` audit；
- 登记 `PROD_OPEN` 与 `SIM_ASSUMPTION`，但不替业务方关闭问题。

## 当前禁止

- 创建 `CpModel`、`IntervalVar` 或真实 Solver；
- 实现 P1 及以后能力；
- 将仿真假设写成生产默认值；
- 猜工厂拓扑、班次、冻结窗口、运输时间、标准工时、库存或接口字段；
- 创建看似完整但没有实现证据的 API、Runbook、性能承诺或生产就绪声明；
- 修改总规语义以适配实现偏好。

## 当前交付

1. 文档入口和文档控制规则；
2. 核心规范、需求与追踪注册表；
3. 架构、领域、规划、仿真和测试基线；
4. P0-P7 Milestone 初版，其中 P0 为详细执行基线；
5. P0 Task Card；
6. 基础 ADR；
7. 文档一致性检查结果。

## 子阶段退出条件

- 总规已进入仓库并可追溯到 `spec_version: 0.3.0`；
- `docs/README.md` 能导航到所有已生成文档；
- 所有规范性拆分文档声明来源章节；
- P0 Task Card 的修改范围、测试和排除项明确；
- `PROD_OPEN` 与 `SIM_ASSUMPTION` 分开登记；
- 没有提前建立 P1+ Task Card；
- 没有把未知生产事实写成默认值。

完成 P0-DOCS 不等于完成 P0，也不授权进入 P1。
