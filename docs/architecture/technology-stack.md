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

本文件记录总规推荐栈；已安装范围以下方锁定表为准，未列入的推荐库不能声称已落地。首次依赖落地必须由 Task Card 和 lockfile 提供实现证据。

## P0-01 已落地基线

| 项目 | 实际状态 |
|---|---|
| Python | `.python-version` 固定 `3.12`；项目要求 `>=3.12,<3.13` |
| 项目版本 | `plantnexus-aps==0.0.0`，仅代表 P0 骨架 |
| Build backend | `hatchling==1.27.0`，在 `pyproject.toml` 精确声明 |
| Runtime dependencies | 空；FastAPI、Pydantic、SQLAlchemy、OR-Tools 等尚未安装 |
| Lock | `uv.lock` 已形成并锁定当前空运行时依赖图与 Python 3.12 系列 |

当前可执行基线为 `uv sync --locked`、`uv build` 和包导入烟雾。OR-Tools 未进入 `pyproject.toml` 或 `uv.lock`，因此本 Task 不触发 Solver upgrade replay/ADR Gate；未来首次引入或升级仍必须遵守上方精确锁定规则。

## P0-03 quality toolchain

Runtime dependencies 继续为空；纯领域合同只使用标准库。`dependency-groups.dev` 精确锁定 `jsonschema==4.25.1`、`PyYAML==6.0.2`、`pytest==8.4.1`、`ruff==0.12.10`、`pyright==1.1.411` 及其 transitive dependencies，用于 Draft 2020-12 Schema、data dictionary、test/lint/type acceptance。TASK-P0-03 发布时 schema set version 为 `1.0.0`。

本次未引入 Pydantic、FastAPI、SQLAlchemy 或 OR-Tools；因此没有 Solver upgrade、runtime behavior 或生产依赖声明。质量工具升级仍需更新 lock 并重跑对应 acceptance。

## P0-04 contract tooling review

依赖版本与 runtime dependency 空集保持不变；`pyproject.toml` 只把 schema set metadata 更新到 `1.1.0`。规则 CLI 在 dev/test acceptance 中使用既有 PyYAML/jsonschema，打包后的纯 enum/precheck/state transition 仍只依赖标准库。`uv.lock` 经 `uv sync --locked` 验证无依赖漂移。

未引入 OR-Tools、Pydantic、API/DB/Worker 库或 Solver code，因此不触发 Solver upgrade replay；新增合同测试仍由既有 Ruff/Pyright/pytest pins 执行。

## P0-05 Simulation contract tooling review

Runtime dependencies 与 lock 图保持不变；Simulation Profile/Scenario/Generator package 只使用 Python 3.12 标准库，Schema/测试继续使用既有 jsonschema/PyYAML/pytest/Ruff/Pyright pins。`pyproject.toml` 仅把 schema set metadata 从 `1.1.0` 更新为 additive `1.2.0`，`uv.lock` 不应因该 metadata 变化产生依赖漂移。

未引入随机/数值库、Pydantic、FastAPI、DB、Worker 或 OR-Tools；canonical primitive 使用 `json`/`hashlib`，命名 seed 使用 SHA-256 派生而非全局 RNG。没有 Solver/Benchmark，因此不触发 upgrade replay，也不产生性能承诺。

## TASK-P0-08 engineering runtime

P0 工程骨架首次落地以下精确 direct pins；transitive graph 以 `uv.lock` 为唯一可复验来源：

| Area | Exact direct dependency |
|---|---|
| API/config | `fastapi==0.116.1`、`pydantic-settings==2.10.1`、`uvicorn==0.35.0` |
| Database/migration | `sqlalchemy==2.0.43`、`alembic==1.16.5`、`psycopg[binary]==3.2.9` |
| Queue/cache | `redis==6.4.0`、`celery==5.5.3` |
| Logging/trace context | `structlog==25.4.0`、`opentelemetry-api==1.36.0` |
| Integration test client | dev-only `httpx==0.28.1` |
| Container build tool | `uv==0.11.32` in `infra/Dockerfile` and CI setup |

`pyproject.toml` 中全部 direct runtime/dev dependencies 使用 exact pin，`uv sync --locked` 禁止解析漂移。PostgreSQL/Redis Compose images 使用 patch-level tag；尚未形成 digest-pinned production deployment。OR-Tools、Polars、openpyxl、Hypothesis、Frontend/Playwright 均未安装；没有 Solver dependency/upgrade/Benchmark evidence，ADR Solver gate 不触发。

## TASK-P0-10 CI toolchain review

本 Task 不修改 `pyproject.toml`、`uv.lock`、Python/uv pin、Action major tag、Compose image 或 runtime dependency；五类 machine report 只从 TASK-P0-08 文件名交接为 TASK-P0-10，报告 schema 与生成器不变。provider evidence 通过 GitHub Actions 和 GitHub REST 获取，不向项目依赖图引入 GitHub CLI/SDK。

Actions provider PASS 只证明锁定的 P0 repository gates 在 GitHub-hosted runner 上执行；它不将 tag 提升为 digest pin，也不构成 Production supply-chain hardening、deployment 或 Solver/Benchmark evidence。

## TASK-P1-01 CI toolchain review

本 Task不修改 `pyproject.toml`、`uv.lock`、Python/uv pin、Action major tag、Compose image或 runtime/dev dependency。changed-task discovery只使用 Python标准库、Git和既有 workflow context；unit/integration tests继续使用现有 pytest/PyYAML/Ruff/Pyright pins。

五类 P0 machine CLI、Compose、build和conditional Benchmark hook保持执行，只把输出改为中性 `ci-*.json`。OR-Tools、Benchmark runner和新供应链工具仍未安装；provider未在本地执行时保持 `NOT_RUN`。

## TASK-P1-02 contract tooling review

Runtime/dev dependency pins与`uv.lock`图保持不变。新合同继续使用JSON Schema Draft 2020-12、既有`jsonschema==4.25.1`及其`referencing` registry解析跨URN `$ref`；pure types/prechecks只使用Python 3.12标准库和既有domain helpers。`pyproject.toml`仅把schema set metadata从`1.2.0`提升为breaking `2.0.0`，没有dependency resolution变化。

未引入openpyxl/Polars/Pydantic model、DB/Worker、OR-Tools、Hypothesis或Benchmark runner；没有Solver upgrade、migration或性能结论。未来Adapter/Property/Solver首次引入依赖时仍须由各自Task更新lock并执行对应Gate。
