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
uv build
uv run python -c "import app; assert app.CODE_VERSION == '0.0.0'; assert app.SPEC_VERSION == '0.3.0'; assert app.SCHEMA_VERSION == 'unassigned'"
```

文档检查只覆盖 P0-01 已落地的 metadata、文档 ID、Markdown fence、本地链接、Task 必需字段和文档清单完整性。REQ/NFR/ENG 引用、Git diff 与变更影响矩阵的完整自动校验属于 TASK-P0-02。

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
