---
doc_id: TASK-P0-01
title: Documentation and Repository Governance
status: done
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

Files allowed to change: `/AGENTS.md`、`/README.md`、`/.gitignore`、`/.python-version`、`/pyproject.toml`、`/uv.lock`、`/scripts/check_docs.py`、目标仓库结构内的最小 `.gitkeep` / `__init__.py` 占位与包版本标识，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: 任何真实 Solver、业务 Adapter、P1 数据处理实现。

Implementation steps: 初始化 Git/基础目录；固定 Python/uv 项目元数据；完善文档导航与校验；确保根 AGENTS 只指向规范正文；登记 spec/schema/code version 占位。

Outputs: repository skeleton、可发现 Agent 规则、docs index、基础 build command。

Documentation impact: required

Documents to update: `docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/governance/document-control.md`、`docs/governance/document-inventory.md`、`docs/governance/traceability-matrix.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/tasks/README.md`、本 Task Card。

Documentation impact rationale: 仓库路径、依赖、读取入口和构建命令是文档导航及 Agent 行为的直接事实。

Change-impact matrix rows reviewed: dependency/lockfile；milestones/current phase；只修改文档；infrastructure/config（仅顶层占位，未形成配置）；`schemas/**`、`fixtures/**`、`benchmarks/**`、`frontend/**`（均仅顶层 `.gitkeep`，未形成对应语义资产或行为）。

Traceability updates: REQ-009、NFR-TRC-001、ENG-ARCH-001、ENG-VER-001 到真实 repository/build artifacts 的矩阵关系。

Schema changes: 无业务 Schema。

Migration: 无。

Error behavior: 缺失总规或文档链接失败时 build/validation 明确失败。

Tests: 文档路径/链接/metadata 校验；repository import/build smoke test。

Benchmark impact: 无。

Simulation scenarios: 无。

Acceptance commands: `uv sync --locked`；`uv run python scripts/check_docs.py`；`uv build`；`uv run python -c "import app; assert app.CODE_VERSION == '0.0.0'; assert app.SPEC_VERSION == '0.3.0'; assert app.SCHEMA_VERSION == 'unassigned'"`。

Artifacts: 目录清单、依赖锁、文档校验报告。

Explicitly excluded: Schema 业务字段、Fixture、Solver、P1+ 功能。

PROD_OPEN: 不关闭任何项。

SIM_ASSUMPTIONS: 不新增定量假设。

Rollback: 删除本 Task 新增的空骨架和配置，保留总规与已批准文档；不得改写用户已有文件。

## Completion evidence

Completed at: `2026-08-19T09:21:50+08:00`

### Delivered artifacts

- Git baseline: 仓库已存在于 `master`（基线提交 `03a751c`），因此保留既有历史而未重复 `git init`。
- Repository skeleton: `backend/`、`frontend/`、`schemas/`、`fixtures/`、`benchmarks/`、`scripts/`、`infra/` 的顶层边界；除应用包版本占位和文档检查脚本外均为空占位。
- Build metadata: `.python-version`、`pyproject.toml`、`uv.lock`；Python 固定为 3.12 系列，项目 code version 为 `0.0.0`。
- Version placeholders: `SPEC_VERSION=0.3.0`、`SCHEMA_VERSION=unassigned`、`CODE_VERSION=0.0.0`。
- Agent/document entry: 根 `AGENTS.md` 保持薄入口，根 `README.md` 提供仓库地图与可执行命令。
- Documentation validation report: `PASS document consistency: docs=107 formal_docs=106 unique_doc_ids=106 local_links=120 tasks=9 inventory_entries=107 spec_version=0.3.0`（写入完成证据和追踪链接后复跑）。
- Build outputs（ignored artifacts）: `dist/plantnexus_aps-0.0.0.tar.gz`、`dist/plantnexus_aps-0.0.0-py3-none-any.whl`。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv sync --locked` | 0 | PASS；resolved/installed `plantnexus-aps==0.0.0` from the locked project。uv 报告跨文件系统 hardlink 回退为 copy 的非失败环境警告。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；完成证据写入后复跑，107 docs、106 份正式 metadata、106 个唯一 doc ID、120 个本地链接、9 张 P0 Task、107 条 inventory 覆盖均通过。 |
| `uv build` | 0 | PASS；成功构建 sdist 与 wheel。 |
| `uv run python -c "import app; assert app.CODE_VERSION == '0.0.0'; assert app.SPEC_VERSION == '0.3.0'; assert app.SCHEMA_VERSION == 'unassigned'"` | 0 | PASS；无 stderr/stdout，全部断言通过。 |

### Documentation impact and traceability

Documentation impact: `required`，已实际更新：根 `README.md`、根 `AGENTS.md`、`docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/governance/document-control.md`、`docs/governance/document-inventory.md`、`docs/governance/traceability-matrix.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/tasks/README.md` 和本 Task Card。

Traceability updates:

- REQ-009 / NFR-TRC-001 → `pyproject.toml`、`uv.lock`、`backend/app/__init__.py` 与本节验收证据；端到端 manifest/audit 仍为 `PLANNED`。
- ENG-ARCH-001 → Modular Monolith 顶层目录边界、可构建 `app` 包和 build/import smoke；API Process 与 Solver Worker 行为仍为 `PLANNED`。
- ENG-VER-001 → code/spec/schema 版本占位和 dependency lock；Schema/Solver/Simulation 的后续版本 Gate 仍为 `PLANNED`。

Change-impact matrix match:

- `dependency/lockfile`：已更新 technology stack；已审查 Solver contract、benchmark regression 与 ADR index。未引入 OR-Tools，因此无 Solver upgrade/ADR/replay 变更。
- `milestones/**` / `current_phase.md`：已更新 current phase、Task index、traceability matrix 和 document inventory；已审查 Milestone index 与 P0 Milestone，Phase/Gate 语义未改变，不进入 P1。
- `只修改文档`：inventory、引用入口和相关文档已同步，结构性文档检查 PASS。
- `infrastructure/**` / 配置：仅 `.gitignore`、`.python-version`、project/build metadata 与空 `infra/.gitkeep`；已审查配置/环境/隔离文档，未形成运行时基础设施、Secret 或生产配置。
- `schemas/**`、`fixtures/**`、`benchmarks/**`、`frontend/**`：仅顶层 `.gitkeep`，无 Schema、Fixture、Benchmark profile/baseline 或 Frontend 行为，故对应语义文档无需修改。

PROD_OPEN: 未关闭或新增任何项。SIM_ASSUMPTIONS: 未新增。Benchmark impact: 无。Schema/Migration: 无业务 Schema，无 Migration。
