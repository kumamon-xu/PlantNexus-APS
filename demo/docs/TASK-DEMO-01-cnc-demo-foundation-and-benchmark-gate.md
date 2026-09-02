---
doc_id: TASK-DEMO-01
title: CNC Simulation Demo Foundation and Benchmark Gate
status: done
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-02
---

# TASK-DEMO-01 — CNC Simulation Demo Foundation and Benchmark Gate

Task family: demo-exclusive

Depends on: none

Start gate: 用户明确要求依据 demo/docs 设计与任务清单开始实施，并进一步确认本任务不属于 P7 任务链。当前根仓库 HEAD 为 fd9ce328a180a8b1f0baa1a0fe870a8d39e0d200；根工作区中其他任务拥有的未提交文件全部保持只读，本任务只写 demo。

Goal: 完成 CNC Demo 的 D00～D04 基础切片：可执行契约断点、Demo-local 后端/测试骨架、固定 132 单/610 工序行业资产、确定性标准导入生成器，以及 610/700 工序 B1/B2 单次早期求解结论。完整 D01 前端/runtime 和 D04 B4/warmup+5 不在本 Task closure 内。

Non-goals: 不实现完整生产 UI、动态重排发布、外部认证、真实数据、P7 Reality Calibration 或 Production capacity；不修改 backend、frontend、schemas、fixtures、benchmarks 和根项目文档。

Inputs: demo/docs 下的设计文档；根仓库现有 Import、Snapshot、PlanningProblem、Solver、Validator、ExecutionEvent 和 Benchmark 合同及实现，全部只读消费。

Diff base: fd9ce328a180a8b1f0baa1a0fe870a8d39e0d200

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 先实现契约 probes；建立 demo Python package/test/asset 骨架；编写版本化 CNC 资产与严格 loader；分层生成标准 StagedImportBatch；复用现有公开 Normalization、Data Validation、Expansion、Snapshot 边界并由 demo adapter 显式构建 PlanningProblem v2（根 CommonIngressPipeline 默认只产出 v1 Problem，不能直接复用）；运行 Global CP-SAT 和独立 Validator；实现 smoke/showcase/upper benchmark runner；保留 raw reports 和诚实状态结论。

Outputs: demo 内的代码、资产、测试、context manifest、machine report、benchmark raw/baseline candidate 和实施状态文档。

Documentation impact: required

Documents to update: demo/docs/README.md、demo/docs/TASKS.md、demo/docs/TASK-DEMO-01-cnc-demo-foundation-and-benchmark-gate.md、demo/docs/IMPLEMENTATION-STATUS.md。

Schema changes: none；不修改正式 JSON Schema。Demo 自有资产使用 demo-local versioned strict schema/typed loader。

Migration: none；本里程碑不建立运行数据库。

Dependency changes: none；复用根项目锁定环境，不修改根 pyproject、uv.lock、frontend package 或 lockfile。

ADR impact: none；严格消费已接受的 Simulation/common-ingress/Problem/Validator/时间/重排 ADR。若 probe 证明必须改正式契约则停止而不扩围。

State-machine impact: none；本里程碑不写批准、发布或动态重排状态。

Error behavior: 资产、引用、计数、时间、候选能力、标准导入、Problem、Solver candidate 或 Validator 任一失败均 fail closed；不得自动换 seed、降低规模、称 UNKNOWN 为不可行或称 FEASIBLE 为最优。

Tests: demo asset loader positive/negative；generator exact counts/determinism/reference/calendar/capability；standard ingress integration；v1/v2/event contract probes；smoke/showcase/upper benchmark；demo-only forbidden scope check。

Test IDs: DEMO-CONTRACT-001～004, DEMO-DATA-001～010, DEMO-INTEGRATION-001～003, DEMO-BENCH-001～003

Benchmark impact: 新增 demo-local CNC-SMOKE、CNC-SHOWCASE 和 CNC-UPPER；不覆盖现有 P2 baseline，不建立 Production SLA。

Simulation scenarios: CNC-DEMO-SHOWCASE / generator PLANTNEXUS-DEMO-CNC-IMPORT-GENERATOR@1.0.0 / seed 20260902 / SIMULATION。

Acceptance commands: demo 自有 context manifest；uv run pytest demo/tests；demo benchmark CLI；受影响 Ruff/Pyright；git diff --check -- demo；demo-only forbidden-scope check。

Artifacts: demo/build/validation/task-context-manifest.json、demo/build/validation/task-machine-report.json、demo/benchmarks/results/*.json。

Provider evidence: 本次为 demo-exclusive 本地工作区交付，不提交或 push，不属于 P7、Provider 或 Production 证据。

Completion conditions: D00 probes 全部通过；132/610/24/1311 和 580 active 精确可复算；同输入 batch/Snapshot/Problem 指纹一致；标准导入与独立 Validator 通过；SHOWCASE/UPPER 有真实 B1/B2 raw benchmark 结论；demo 外文件 hash 不变；文档只陈述实测 synthetic 结果。

Failure handling: 保留失败报告和真实 solver 状态；只在 demo 内修正资产或 adapter。需要正式代码/Schema/依赖变化时停止并请求新范围；不得弱化 Validator 或隐藏失败。

Explicitly excluded: P7 全部任务与状态、D05～D18 完整 runtime/API/UI、Production、真实历史数据、外部 authority、deployment、SLA。

Simulation assumptions: 使用 demo/docs/02-cnc-data-design.md 已声明的 CNC 演示数值；只作为 demo-local versioned assets。

Completion evidence:

- `demo/build/validation/contract-probes.json`：5/5 `PASS`。
- `uv run pytest demo/tests -q`：18 passed；Ruff 与 Pyright 均为 0 issue。
- Showcase：132 单 / 610 总工序 / 580 active / 24 设备 / 1,311 source options；20 秒预算内 `OPTIMAL`，solve 2.427 秒，Solver total 2.924 秒，Validator `PASS`。
- Upper：150 单 / 700 总工序 / 665 active / 30 设备；30 秒预算内 `OPTIMAL`，solve 6.304 秒，Solver total 6.947 秒，Validator `PASS`。
- `demo/build/validation/protected-root-baseline.json` 保留的 10 个非 Demo 文件 SHA-256 全部未变化；无新增 demo 外路径。
- 结果仅是单次 synthetic initial-solve evidence；D04 B4 加急重排、warmup + 5 measured、RSS、ChangeReport 分布和 immutable baseline 仍由后续 Task 完成。

Rollback: 删除本 Task 新增的 demo 实现、测试、资产和生成报告，恢复进入实现前的 demo/docs 设计文件；不触碰根项目既有工作区差异。
