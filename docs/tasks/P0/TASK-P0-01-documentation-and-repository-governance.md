---
doc_id: TASK-P0-01
title: Documentation and Repository Governance
status: ready
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [2, 70, 71, 98, 99, 100, 110]
last_reviewed: 2026-08-19
---

# TASK-P0-01 — Documentation and Repository Governance

Requirement IDs: REQ-009

NFR / ENG IDs: NFR-TRC-001, ENG-ARCH-001, ENG-VER-001

Depends on: `docs/core/APS_IMPLEMENTATION_SPEC.md`

Goal: 建立可构建的仓库骨架、文档入口、版本元数据和 Agent 自动发现入口，使后续 P0 Task 有稳定路径和边界。

Inputs: repository layout、document-control、current Phase、推荐技术栈。

Files allowed to change: `/AGENTS.md`、`/README.md`、`.gitignore`、`pyproject.toml`、基础 lock/config、目标顶层目录的最小占位/包标识，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: 任何真实 Solver、业务 Adapter、P1 数据处理实现。

Implementation steps: 初始化 Git/基础目录；固定 Python/uv 项目元数据；完善文档导航与校验；确保根 AGENTS 只指向规范正文；登记 spec/schema/code version 占位。

Outputs: repository skeleton、可发现 Agent 规则、docs index、基础 build command。

Documentation impact: required

Documents to update: `docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/governance/document-control.md`、`docs/governance/document-inventory.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/tasks/README.md`、本 Task Card。

Documentation impact rationale: 仓库路径、依赖、读取入口和构建命令是文档导航及 Agent 行为的直接事实。

Change-impact matrix rows reviewed: dependency/lockfile；milestones/current phase；只修改文档；infrastructure/config（若形成）。

Traceability updates: REQ-009、NFR-TRC-001、ENG-ARCH-001、ENG-VER-001 到真实 repository/build artifacts 的矩阵关系。

Schema changes: 无业务 Schema。

Migration: 无。

Error behavior: 缺失总规或文档链接失败时 build/validation 明确失败。

Tests: 文档路径/链接/metadata 校验；repository import/build smoke test。

Benchmark impact: 无。

Simulation scenarios: 无。

Acceptance commands: `uv sync --locked`（lock 形成后）、文档校验命令、最小 repository build/smoke test。

Artifacts: 目录清单、依赖锁、文档校验报告。

Explicitly excluded: Schema 业务字段、Fixture、Solver、P1+ 功能。

PROD_OPEN: 不关闭任何项。

SIM_ASSUMPTIONS: 不新增定量假设。

Rollback: 删除本 Task 新增的空骨架和配置，保留总规与已批准文档；不得改写用户已有文件。
