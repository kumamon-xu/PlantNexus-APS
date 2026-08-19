---
doc_id: DOC-ARCH-006
title: 推荐技术栈与锁定规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: false
source_sections: [11, 12, 65, 95, 100, 102]
last_reviewed: 2026-08-19
---

# 推荐技术栈与锁定规则

## Backend

Python 3.12、uv、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic、PostgreSQL、Redis、Celery、Google OR-Tools CP-SAT、Polars、openpyxl、structlog、OpenTelemetry。

## Frontend

React、TypeScript、Ant Design、TanStack Query、支持虚拟滚动的 Gantt、Playwright。

## Quality

pytest、Hypothesis、Ruff、Pyright 或 mypy、Playwright、Contract/Golden/Property/Benchmark Regression tests。

## 依赖规则

- OR-Tools 必须固定精确版本并写入 `uv.lock` 和每次 `solver_report`。
- OR-Tools 升级必须提交 ADR、更新 lock、执行 Golden/Scenario replay、Benchmark comparison 和 Solver status contract tests。
- 禁止直接执行 `pip install -U ortools` 后合并。
- Secret 只能来自环境或 Secret Manager，不能进入仓库、日志或导出包。

本文件记录总规推荐栈，不代表所有库已经安装。首次依赖落地应由 Task Card 和 lockfile 提供实现证据。

## P0-01 已落地基线

| 项目 | 实际状态 |
|---|---|
| Python | `.python-version` 固定 `3.12`；项目要求 `>=3.12,<3.13` |
| 项目版本 | `plantnexus-aps==0.0.0`，仅代表 P0 骨架 |
| Build backend | `hatchling==1.27.0`，在 `pyproject.toml` 精确声明 |
| Runtime dependencies | 空；FastAPI、Pydantic、SQLAlchemy、OR-Tools 等尚未安装 |
| Lock | `uv.lock` 已形成并锁定当前空运行时依赖图与 Python 3.12 系列 |

当前可执行基线为 `uv sync --locked`、`uv build` 和包导入烟雾。OR-Tools 未进入 `pyproject.toml` 或 `uv.lock`，因此本 Task 不触发 Solver upgrade replay/ADR Gate；未来首次引入或升级仍必须遵守上方精确锁定规则。
