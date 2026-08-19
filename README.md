# PlantNexus APS

PlantNexus APS 是一个面向单工厂、多车间场景的高级计划与排程（APS）项目。P0 Exit Gate 已通过，用户已明确授权进入 P1（Data & Snapshot）；TASK-P1-02正在发布canonical Import/Snapshot合同，尚未实现数据pipeline。真实 Solver、生产Adapter/参数和P2+能力仍未实现。

## 开始之前

Coding Agent 必须从 [`AGENTS.md`](AGENTS.md) 进入项目规则。项目规范、当前阶段和有界 Task Card 位于 [`docs/`](docs/README.md)。

## 版本基线

| 对象 | 当前值 | 含义 |
|---|---|---|
| Implementation spec | `0.3.0` | 当前权威实施规格版本 |
| Code | `0.0.0` | P0 工程骨架占位，不代表发布版本 |
| Business schema set | `2.0.0` | 保留全部 P0 artifacts，并发布 P1 canonical-records.v1、Import v2 与 Snapshot v2 |
| Python | `3.12` | `.python-version` 与 `pyproject.toml` 固定的运行时系列 |

## 本地验收

需要 [uv](https://docs.astral.sh/uv/)。在仓库根目录运行：

```powershell
uv sync --locked
uv run ruff check .
uv run pyright backend/app backend/tests
uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration
uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json
docker compose --env-file .env.example config --quiet
uv run python scripts/check_docs.py
uv build
uv run python -c "import app; assert app.CODE_VERSION == '0.0.0'; assert app.SPEC_VERSION == '0.3.0'; assert app.SCHEMA_VERSION == '2.0.0'"
```

`scripts/check_docs.py` 当前同时检查结构性 Markdown、版本化 registries、REQ/NFR/ENG/TEST 等引用、Task 依赖、逐根 traceability 和 PROD_OPEN/SIM_ASSUMPTION 隔离。Task 进入 `in_progress` 时须把当时完整 HEAD SHA 写入 `Diff base`；影响覆盖检查使用 `Diff base..HEAD` 的已提交变更与当前 working tree 的并集，因此提交前后可用同一命令复验：

```powershell
uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-02-canonical-import-contracts.md --check-diff --report build/traceability/TASK-P1-02-report.json
```

报告使用 `traceability-report.v1`，包含 `diff_base` 与 committed/working-tree source counts，生成到已忽略的 `build/`；Task Card Completion evidence 保存持久结果摘要。[`ci.yml`](.github/workflows/ci.yml) 已编排 exact lock、lint、type、全部 P0 tests、machine contracts、Compose config、文档 diff 和 package build。仓库内只证明 workflow/config 可执行；CI provider run URL/ID 必须来自真实外部运行，不能由本地结果替代。

CI 不再硬编码某个 P0/P1 Task。PR 使用 base SHA、main push 使用 event `before` SHA，通过 `--discover-task-from <40-char-sha>` 找到唯一当前 Phase Task Card，再按该卡自身的 `Diff base`执行完整 scope/impact检查；零个、多个、历史/未来或 phase/path不一致的 Task Card都硬失败。workflow机器报告使用 `ci-*.json`与 `plantnexus-ci-evidence-<run-id>`中性名称；本地实现通过不等于 provider PASS。

## 仓库结构

```text
backend/      Python 应用包、工程 migration 与 P0 测试
frontend/     前端工作区预留边界
schemas/      可执行 Schema 预留边界
fixtures/     确定性、非法、仿真与历史 Fixture 预留边界
benchmarks/   Benchmark profile 与 baseline 预留边界
docs/         唯一实质性开发文档中心
scripts/      仓库级校验与自动化脚本
infra/        P0 开发容器构建配置
```

P0-08只形成health-only API、环境配置、日志、lazy DB/Redis connectivity、通用Job reliability/idempotency、Alembic/Compose/CI骨架；它不形成业务pipeline、产品API、真实分布式作业存储、Solver或生产部署。P1的12张有界Task Card已建立，TASK-P1-01=`done`、TASK-P1-02=`in_progress`；P1-02只发布严格机器合同、样例与pure precheck，Adapter/Normalization/DataValidation/Expansion/Snapshot builder仍由后续Task实现。当前授权范围见[`docs/current_phase.md`](docs/current_phase.md)。
