# PlantNexus APS

PlantNexus APS 是一个面向单工厂、多车间场景的高级计划与排程（APS）项目。P1 Data & Snapshot 已通过 Exit Gate并关闭，当前阶段为P2（CP-SAT Vertical Slice）。TASK-P2-01～10已由local/exact provider闭环；五个非生产Reference Schedulers及同Problem/Validator/KPI证据现已形成。Benchmark、Production能力、P2-11～14和P3仍未形成或未获启动授权。

## 开始之前

Coding Agent 必须从 [`AGENTS.md`](AGENTS.md) 进入项目规则。项目规范、当前阶段和有界 Task Card 位于 [`docs/`](docs/README.md)。

## 版本基线

| 对象 | 当前值 | 含义 |
|---|---|---|
| Implementation spec | `0.3.0` | 当前权威实施规格版本 |
| Code | `0.0.0` | P0 工程骨架占位，不代表发布版本 |
| Business schema set | `2.4.0` | 加法包含 PlanningProblem v2 与 Policy/Limits/Solution/Report v1；历史 document 版本和字节保持不变 |
| Python | `3.12` | `.python-version` 与 `pyproject.toml` 固定的运行时系列 |
| OR-Tools | `9.15.6755` | TASK-P2-03 exact runtime pin；只允许在 `planning/backends/cp_sat/` 使用 |

## 本地验收

需要 [uv](https://docs.astral.sh/uv/)。在仓库根目录运行：

```powershell
uv sync --locked
uv run ruff check .
uv run pyright backend/app backend/tests
uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property
uv run python -m app.planning.validation.problem_validator_check --root . --report build/validation/TASK-P2-04-formal-schedule-validator.json
uv run python -m app.simulation.scenarios.p2_correctness --root . --report build/validation/TASK-P2-09-correctness.json
uv run python -m app.simulation.baselines.reference_schedulers --root . --report build/validation/TASK-P2-10-reference-schedulers.json
uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json
docker compose --env-file .env.example config --quiet
uv run python scripts/check_docs.py
uv build
uv run python -c "import app; assert app.CODE_VERSION == '0.0.0'; assert app.SPEC_VERSION == '0.3.0'; assert app.SCHEMA_VERSION == '2.4.0'"
```

`scripts/check_docs.py` 当前同时检查结构性 Markdown、版本化 registries、REQ/NFR/ENG/TEST 等引用、Task 依赖、逐根 traceability 和 PROD_OPEN/SIM_ASSUMPTION 隔离。Task 进入 `in_progress` 时须把当时完整 HEAD SHA 写入 `Diff base`；影响覆盖检查使用 `Diff base..HEAD` 的已提交变更与当前 working tree 的并集，因此提交前后可用同一命令复验：

```powershell
uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-10-reference-schedulers.md --check-diff --report build/traceability/TASK-P2-10-report.json
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

P1 Data & Snapshot已通过Exit Gate并关闭，当前阶段为P2。TASK-P2-01～10均已由local与exact provider evidence闭环；TASK-P2-10以`0e4f6630412889254a7bef41f487c24dc274ca9c`为Diff base形成五个deterministic non-production baseline并复用相同Problem/formal Validator/KPI。Benchmark、DB/API/Worker、P2-11～14和P3仍未实现或未获授权。当前边界见[`docs/current_phase.md`](docs/current_phase.md)。

TASK-P2-05本地验收与implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的GitHub required `validate` / artifact均已闭环。TASK-P2-06 implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`及TASK-P2-07 implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的required `validate`与artifact也已闭环，二者均=`done`；TASK-P2-08/09亦已闭环，TASK-P2-10是之后另获授权启动。

TASK-P2-08形成`POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`、显式SolveLimits、priority-weighted tardiness seconds目标、single-call GlobalCpSatStrategy、诚实status/bound/gap与mandatory formal Validator gate；70 focused、395 full与7/7 local machine PASS，implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的required run `32438785162` / artifact `9431673977`精确复现证据，Task=`done`。该证据不构成XS/S/M baseline或Production policy；P2-09是之后另获授权启动。

用户于2026-08-21明确授权TASK-P2-09。Diff base固定为clean且provider-verified的`15c298f343a47db2a922544944ff5e02e4ca72d9`；本Task只新增七类versioned correctness assets、正式Ingress→Problem→Global Strategy→Validator replay、property/mutation与CI machine evidence，不修改Planning/Solver/Validator语义，不建立XS/S/M/Production baseline，也不启动P2-10或P3。

TASK-P2-09本地已形成`P2-GOLDEN-JSSP/FJSP`与五例correctness matrix、`PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`、固定object/Import/Snapshot/Problem hashes、7次Solver→Validator replay、7次row-order property及11个exact C-ID mutation；45 focused、427 full、8/8 correctness及全部历史machine/build/governance checks均PASS。Implementation `20e49c92306128b47313059fabe31534814dbe3d`的required run `32442651322` / artifact `9432982306`精确复现16/16 reports和58 committed/0 working治理证据，Task=`done`；P2-10+与P3仍未启动。

TASK-P2-06 exact run `32432482739` / required job `96626844156` / artifact `9429579311`精确复现temporal 7/7、4个implemented C-ID、5个positive candidate、3个certified infeasible、2个precheck、4个formal Validator mutation、8个tiny oracle及53 paths/6 rows/0 issues，Task已闭环。

用户于2026-08-21明确授权TASK-P2-10。启动门复核确认`main=origin/main=0e4f6630412889254a7bef41f487c24dc274ca9c`、P2-01/02/04=`done`，且该SHA的required `validate` run `32443067388` / job `96657446617` / artifact `9433118755`精确成功。当前只允许五个versioned baseline、测试、CI machine evidence与治理文档；P2-11～14、BenchmarkRunner/XS-S-M、Production fallback及P3不会自动启动。

TASK-P2-10已形成`reference-scheduler-contracts/policy/result/report.v1`及五个exact algorithm identity；七个冻结Problem×五算法得到35个完整candidate、35次fresh Validator PASS和35次deterministic replay，blocked-calendar得到5个零partial `HEURISTIC_FAILURE`。Task-specific=`13 passed`、full=`441 passed`且Ruff/Pyright为0；implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`的required run `32449742281` / artifact `9435264655`精确复现17/17 reports和38 committed/0 working治理证据，Task=`done`，不自动启动P2-11。
