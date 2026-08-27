# PlantNexus APS

## P4 phase activation and planning

用户已明确批准P3→P4。TASK-P3-17独立Exit Audit的report/manifest均为`READY`、`blocking_gaps=[]`；audit implementation `201be9c6fd1b433a9d0a629a3ae7d4ffe1107476`和evidence-only closure `61eeacdd5efc20b2321750e1310e9e21561c9fc2`的直接拓扑、required `validate`、GitHub Actions app `15368`及未过期artifact均已exact复验。因此P3 Milestone现为`completed`，P4 Dynamic Replanning已激活。

PlantNexus APS 是一个面向单工厂、多车间场景的高级计划与排程（APS）项目。TASK-P4-00阶段启动与完整规划治理已取得exact implementation provider并由evidence-only closure标为`done`；TASK-P4-01～15均保持`planned`，本次不会自动启动。P4规划覆盖ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator、五类连续异常、API/UI、Vertical Gate和独立Exit Audit；Production readiness/UAT/真实approval authority/external publish/deployment/capacity/SLA与P5+仍未形成。

## 开始之前

Coding Agent 必须从 [`AGENTS.md`](AGENTS.md) 进入项目规则。项目规范、当前阶段和有界 Task Card 位于 [`docs/`](docs/README.md)。

## 版本基线

| 对象 | 当前值 | 含义 |
|---|---|---|
| Implementation spec | `0.3.0` | 当前权威实施规格版本 |
| Code | `0.0.0` | P0 工程骨架占位，不代表发布版本 |
| Business schema set | `2.7.0` | 加法包含Workspace v1与P3 export v2；本Task不改Schema、migration或历史document bytes |
| Python | `3.12` | `.python-version` 与 `pyproject.toml` 固定的运行时系列 |
| OR-Tools | `9.15.6755` | TASK-P2-03 exact runtime pin；只允许在 `planning/backends/cp_sat/` 使用 |

## TASK-P3-14 Vertical Slice Gate

TASK-P3-14以`6a3e02f00bf46f19915cb59c3c4af7daaac95be4`为不可变Diff base，聚合P3-02～13已发布机器边界、两次fresh Backend replay、两次独立Chromium replay、P2 Gate regression和四类exact rejection。`p3-vertical-slice-report.v1`保留完整raw subreport；stable semantic projection只排除显式runtime/derived identity，并在先验证允许集合后归一化并发审批的合法线程交错。任一报告、语义、拒绝或provider交叉检查失败都会写入`blocking_gaps`并非零退出。

在TASK-P3-14冻结时，完整本地验收为616项Python、54项Vitest、基础Chromium与两轮Gate Chromium各12/12、全部机器合同、P2 Gate/XS、Compose/build及56 paths/8 Impact Rules/19 checks/0 issues均PASS；P3 Gate为14/14且`blocking_gaps=[]`。Corrective implementation `54a25646053979a69734a3148030830d49c04c1e`的required run/job/artifact=`32931418903`/`98064264595`/`9593460266`精确全绿并复现全部Gate/Task/browser证据，故TASK-P3-14=`done`。该时点最终TASK-P3-17 Exit Gate Audit仍为`NOT_PERFORMED`/`planned`；该历史Gate不形成P4或Production identity、approval、publish、capacity、SLA或readiness。

## TASK-P3-15 Phase Plan Amendment Governance

用户已批准调整P3末段编号。TASK-P3-15以`06e7f794f486ac34c505237b847462c7c7c36d44`为不可变Diff base，只扩展治理validator与unit regression。Implementation `c84e1aa1a81473f65d9f7906a6d2c67a94e7bb2f`的required run/job/artifact=`32944633958`/`98102640242`/`9597967232`已下载复核26/0 paths、5 rows、19 checks、0 issues；evidence-only closure `1636fe9c909b728d49f9907ed9f53030b5921914`的run/job/artifact=`32948633841`/`98114798738`/`9599442770`也已下载复核37份JSON、48/0 paths、6 rows、19 checks和0 issues。因此TASK-P3-15=`done`，其失败/成功provider历史保持只读。

TASK-P3-16现实现默认`zh-CN`、可切换/恢复`en-US`及[`official-zh-cn-terminology.v1`](docs/frontend/official-zh-cn-terminology-map.md)的typed display adapter；`document.lang`、Ant Design locale、Intl格式、unknown raw fallback、双语a11y/Playwright与`p3-frontend-i18n-report.v1`均已由exact implementation/closure provider复验。API路径/key/operationId/state/command/error/C-ID/fingerprint和标准载体继续使用英文机器合同，package/lock零差异。TASK-P3-17已依据后续明确授权独立执行并由exact implementation provider支持为`done`；不会自动进入P4。

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
uv run python -m app.exporters.contract_check --root . --report build/validation/TASK-P2-11-output-contracts.json
uv run python scripts/run_benchmark.py --profile xs --report build/benchmarks/TASK-P2-12-xs.json
uv run python -m app.application.p2_gate_report --root . --repeat 2 --report build/validation/TASK-P2-13-p2-gate.json
uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json
docker compose --env-file .env.example config --quiet
uv run python scripts/check_docs.py
uv build
uv run python -c "import app; assert app.CODE_VERSION == '0.0.0'; assert app.SPEC_VERSION == '0.3.0'; assert app.SCHEMA_VERSION == '2.7.0'"
```

`scripts/check_docs.py` 当前同时检查结构性 Markdown、版本化 registries、REQ/NFR/ENG/TEST 等引用、Task 依赖、逐根 traceability 和 PROD_OPEN/SIM_ASSUMPTION 隔离。Task 进入 `in_progress` 时须把当时完整 HEAD SHA 写入 `Diff base`；影响覆盖检查使用 `Diff base..HEAD` 的已提交变更与当前 working tree 的并集，因此提交前后可用同一命令复验：

```powershell
uv run python scripts/check_docs.py --task docs/tasks/P3/TASK-P3-15-phase-plan-amendment-governance-support.md --check-diff --report build/traceability/TASK-P3-15-report.json
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

P2 CP-SAT Vertical Slice与P3 Planning Workspace均已通过Exit Gate并关闭，当前阶段为P4。P2-00～14、P3-00～17与TASK-P4-00均为`done`；P3 Exit与P4 planning implementation exact provider已完整复验，P4-01～15仍为`planned`。Production capacity/SLA/identity/approval authority/external publish仍未形成，P4业务实现也尚未开始。当前边界见[`docs/current_phase.md`](docs/current_phase.md)。

TASK-P3-13保留失败implementation run `32920462781`、首次closure `87d47c7483185483ac8027100c1c664d18011a7c` / run `32921871460`的606/1失败与artifact count=0。独立XLSX deterministic corrective implementation `3538d46f8b73ae434057bcbca9037436aa91f2c7`的required run/job/artifact=`32923203227`/`98040743610`/`9590625358`已全绿并下载复验33份JSON、12/12 Chromium和Task 91/0/11/19/0；该P3-13 closure当时未自动启动P3-14，后者现依据新的用户授权独立执行。

## P2 历史执行记录

TASK-P2-05本地验收与implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的GitHub required `validate` / artifact均已闭环。TASK-P2-06 implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`及TASK-P2-07 implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的required `validate`与artifact也已闭环，二者均=`done`；TASK-P2-08/09亦已闭环，TASK-P2-10是之后另获授权启动。

TASK-P2-08形成`POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`、显式SolveLimits、priority-weighted tardiness seconds目标、single-call GlobalCpSatStrategy、诚实status/bound/gap与mandatory formal Validator gate；70 focused、395 full与7/7 local machine PASS，implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的required run `32438785162` / artifact `9431673977`精确复现证据，Task=`done`。该证据不构成XS/S/M baseline或Production policy；P2-09是之后另获授权启动。

用户于2026-08-21明确授权TASK-P2-09。Diff base固定为clean且provider-verified的`15c298f343a47db2a922544944ff5e02e4ca72d9`；本Task只新增七类versioned correctness assets、正式Ingress→Problem→Global Strategy→Validator replay、property/mutation与CI machine evidence，不修改Planning/Solver/Validator语义，不建立XS/S/M/Production baseline，也不启动P2-10或P3。

TASK-P2-09本地已形成`P2-GOLDEN-JSSP/FJSP`与五例correctness matrix、`PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`、固定object/Import/Snapshot/Problem hashes、7次Solver→Validator replay、7次row-order property及11个exact C-ID mutation；45 focused、427 full、8/8 correctness及全部历史machine/build/governance checks均PASS。Implementation `20e49c92306128b47313059fabe31534814dbe3d`的required run `32442651322` / artifact `9432982306`精确复现16/16 reports和58 committed/0 working治理证据，Task=`done`；P2-10+与P3仍未启动。

TASK-P2-06 exact run `32432482739` / required job `96626844156` / artifact `9429579311`精确复现temporal 7/7、4个implemented C-ID、5个positive candidate、3个certified infeasible、2个precheck、4个formal Validator mutation、8个tiny oracle及53 paths/6 rows/0 issues，Task已闭环。

用户于2026-08-21明确授权TASK-P2-10。启动门复核确认`main=origin/main=0e4f6630412889254a7bef41f487c24dc274ca9c`、P2-01/02/04=`done`，且该SHA的required `validate` run `32443067388` / job `96657446617` / artifact `9433118755`精确成功。当前只允许五个versioned baseline、测试、CI machine evidence与治理文档；P2-11～14、BenchmarkRunner/XS-S-M、Production fallback及P3不会自动启动。

TASK-P2-10已形成`reference-scheduler-contracts/policy/result/report.v1`及五个exact algorithm identity；七个冻结Problem×五算法得到35个完整candidate、35次fresh Validator PASS和35次deterministic replay，blocked-calendar得到5个零partial `HEURISTIC_FAILURE`。Task-specific=`13 passed`、full=`441 passed`且Ruff/Pyright为0；implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`的required run `32449742281` / artifact `9435264655`精确复现17/17 reports和38 committed/0 working治理证据，Task=`done`，不自动启动P2-11。

用户于2026-08-21明确授权TASK-P2-11。启动门复核确认`main=origin/main=41e958b771f2664b1ac50867903a30b73627878d`，该SHA的required `validate` run `32450216908` / job `96677202782` / artifact `9435421360`精确成功。当前只允许additive KPI/manifest、deterministic reporting/internal package、测试/CI与治理文档；ScheduleVersion/ExportJob、approval/publish/external transfer、ChangeReport、BenchmarkRunner、P2-12+及P3不会自动启动。

TASK-P2-11新增`kpi.v2`、`export-manifest.v1`和`p2-internal-export.v1`：所有JSON采用`canonical-json.v1`，CSV采用UTF-8/RFC 4180 LF，manifest固定9个payload的hash/bytes/rows与同一run lineage。包只承载validated PlanningSolution，显式声明`publishable=false`及P3/P4 deferred边界；原子目录写入支持exact replay并在失败时不留下成功manifest。指定验收49项、全仓455项和output machine 8/8均PASS；implementation `546292831c3bd52185687a4c646c10ae10541ae2`的required run `32454693799` / artifact `9436863185`精确复现18/18 reports与58-path治理证据，故Task=`done`。P2-12仍为`planned`且未获启动授权。

用户于2026-08-21明确授权TASK-P2-12。启动门复核确认`main=origin/main=58db14e8f18fb50866fb757d4c89e76fef1141f1`，其required `validate` run `32455399561` / job `96691604529` / artifact `9437086153`精确成功并复现P2-11 closure证据。当前只允许versioned XS/S/M profile/baseline、BenchmarkRunner、共享但不改变输出的schedule KPI pure calculation、CLI/CI/test与治理文档；L/XL、Production threshold、P2-13/14及P3不会自动启动。

TASK-P2-12已形成`benchmark-profile-set/report/baseline.v1`、`benchmark-runner.v1`和SIM-ASSUMPTION-013。XS/S/M分别固定8/24/48 operations，同一正式Raw→Problem链上运行Global与五个Reference，各完成1次warm-up和3次measured replay；三份报告均8/8 PASS、formal Validator与共享KPI一致，baseline comparison无warning。Implementation `01e7f4bdca88fc903e7caa771f875fc1a70ff357`的required run `32460861563` / artifact `9438899443`精确复现19/19 reports、XS 8/8及49 committed/0 working治理证据，故Task=`done`；P2-13/14与P3未启动。

用户于2026-08-21明确授权TASK-P2-13。启动门复核确认`main=origin/main=59f3b013a4be7bd11d054e8464886b3cde791602`且working tree clean，P2-01～12 implementation与exact provider evidence均位于可追溯祖先链；closure run `32461665177` / required job `96709654227` / artifact `9439159396`精确success。当前只允许聚合公开边界形成可重放`p2-vertical-slice-report.v1`、四类负例、测试/CI evidence及治理文档；不修复既有实现、不作P2 Exit结论，也不启动P2-14或P3。

TASK-P2-13本地Gate现以两次完整replay聚合七场景correctness、XS/S/M Global+五Reference Benchmark、formal Validator/KPI/SolverReport与九payload internal Export；聚焦`30 passed`、全仓`476 passed`，Gate为11/11 PASS、14次correctness场景、6次profile、108次Benchmark Validator、4类exit rejection且0 blocking gap。报告保留全部原始运行字段，同时用versioned semantic projection验证业务一致性；`Exit Gate Audit=NOT_PERFORMED`，exact implementation provider闭环前Task保持`in_progress`。

Implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的GitHub required run [`32465737712`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32465737712) / job `96721819879` / artifact `9440650646`精确success；20份artifact JSON全部PASS，Gate 11/11与37 committed/0 working paths、6 rows、19 checks、0 issues均绑定同一SHA。因此TASK-P2-13=`done`；这只满足P2-14依赖，不构成Exit READY或P3授权。
