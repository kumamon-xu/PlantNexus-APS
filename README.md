# PlantNexus APS

PlantNexus APS 是一个面向单工厂、多车间场景的高级计划与排程（APS）项目。项目当前处于 P0（Executable Specification），本仓库只建立可构建的工程与治理骨架；真实 Solver、业务 Adapter、生产参数和 P1+ 能力尚未实现。

## 开始之前

Coding Agent 必须从 [`AGENTS.md`](AGENTS.md) 进入项目规则。项目规范、当前阶段和有界 Task Card 位于 [`docs/`](docs/README.md)。

## 版本基线

| 对象 | 当前值 | 含义 |
|---|---|---|
| Implementation spec | `0.3.0` | 当前权威实施规格版本 |
| Code | `0.0.0` | P0 工程骨架占位，不代表发布版本 |
| Business schema | `unassigned` | 将由后续获准的 Schema Task 建立 |
| Python | `3.12` | `.python-version` 与 `pyproject.toml` 固定的运行时系列 |

## 本地验收

需要 [uv](https://docs.astral.sh/uv/)。在仓库根目录运行：

```powershell
uv sync --locked
uv run python scripts/check_docs.py
uv run python -m unittest discover -s backend/tests/unit -p "test_check_docs.py"
uv build
uv run python -c "import app; assert app.CODE_VERSION == '0.0.0'; assert app.SPEC_VERSION == '0.3.0'; assert app.SCHEMA_VERSION == 'unassigned'"
```

`scripts/check_docs.py` 当前同时检查结构性 Markdown、版本化 registries、REQ/NFR/ENG/TEST 等引用、Task 依赖、逐根 traceability 和 PROD_OPEN/SIM_ASSUMPTION 隔离。对当前 Task 的实际 Git diff 运行影响覆盖检查：

```powershell
uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-02-requirements-and-traceability.md --check-diff --report build/traceability/TASK-P0-02-report.json
```

报告使用 `traceability-report.v1`，生成到已忽略的 `build/`；Task Card Completion evidence 保存持久结果摘要。CI 强制集成仍属于 TASK-P0-08。

## 仓库结构

```text
backend/      Python 应用包、迁移与测试的预留边界
frontend/     前端工作区预留边界
schemas/      可执行 Schema 预留边界
fixtures/     确定性、非法、仿真与历史 Fixture 预留边界
benchmarks/   Benchmark profile 与 baseline 预留边界
docs/         唯一实质性开发文档中心
scripts/      仓库级校验与自动化脚本
infra/        基础设施配置预留边界
```

目录存在只表示路径已预留，不表示对应能力已经实现。当前授权范围见 [`docs/current_phase.md`](docs/current_phase.md)。
