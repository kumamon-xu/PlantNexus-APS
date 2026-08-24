---
doc_id: DOC-ARCH-006
title: 推荐技术栈与锁定规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: false
source_sections: [11, 12, 65, 95, 100, 102]
last_reviewed: 2026-08-24
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

## TASK-P1-03 persistence tooling review

Raw Staging复用已锁定的`sqlalchemy==2.0.43`与`alembic==1.16.5`，未修改`pyproject.toml`或`uv.lock`，也未引入ORM model、Adapter parser、openpyxl/Polars、OR-Tools或新test dependency。repository使用SQLAlchemy Core parameter binding，migration revision为`0002_raw_import_staging`。

本地integration以SQLite实际执行empty/populated upgrade/downgrade、insert/replay/rollback/isolation；该dialect只用于可复验开发证据，不等于PostgreSQL并发、权限、性能或Production migration认证。小型synthetic row计数/耗时只作回归观察，不设阈值、不运行Solver Benchmark。

## TASK-P1-04 file-reader runtime

首次精确锁定`openpyxl==3.1.5`用于read-only XLSX解析，并锁定`defusedxml==0.7.1`使openpyxl XML路径启用防御解析；`et-xmlfile==2.0.0`为lock解析出的transitive dependency。CSV继续只使用Python 3.12标准库，所有direct pins仍为exact并由`uv sync --locked`与contract test验证。

本Task没有引入Polars、OR-Tools、types stub、API/Worker或malware scanner；Schema/code版本metadata保持不变。新增dependency只服务bounded ReferenceFileAdapter，不能外推为Production supply-chain/security认证，也不触发Solver upgrade ADR或Benchmark replay。

## TASK-P1-05 normalization runtime

Normalization runtime只使用Python 3.12标准库`dataclasses/enum/json/hashlib/datetime/decimal`；YAML只由既有dev/test `PyYAML==6.0.2`加载后注入`UnitConversionRegistry.from_mapping`，production module不依赖PyYAML/jsonschema。`pyproject.toml`只把schema metadata改为`2.1.0`，未改变dependency list，故`uv.lock`保持不变并由`uv sync --locked`验证。

没有引入Polars、Pydantic model、ORM/API/Worker、OR-Tools或Benchmark runner。Canonical JSON和integer conversion不使用第三方数值库或float duration rounding；quantity小数只有在JSON文本可无损往返时才接受。

## TASK-P1-06 data-validation runtime

Data Validation runtime继续只使用Python 3.12标准库`dataclasses/hashlib/json/datetime/math/collections`及既有pure domain helpers；YAML/jsonschema仍仅由已锁定dev/test工具验证registry和Draft 2020-12跨URN `$ref`。`pyproject.toml`只把schema metadata从`2.1.0`提升到additive `2.2.0`，dependency list不变，`uv.lock`应保持原SHA-256。

没有引入graph库、Hypothesis、Pydantic model、DB/API/Worker、OR-Tools或Benchmark runner。DAG使用确定性标准库SCC遍历，report canonicalization使用JSON/SHA-256；source scan固定无Planning/Solver/ScheduleValidator依赖，因此不触发Solver upgrade ADR/replay。

## TASK-P1-07 property-test tooling

Order Expansion runtime继续只使用Python 3.12标准库`collections/dataclasses/enum/hashlib/json`与pure domain contracts；runtime direct dependency精确集合不变，仍无OR-Tools、graph库、ORM/API/Worker或Benchmark runner。`pyproject.toml`的dev group精确增加`hypothesis==6.165.10`，lock解析增加其transitive `sortedcontainers==2.4.0`；`uv sync --locked`固定完整图。

属性测试使用Hypothesis generation/shrinking、固定replay seeds `20260819/20260820`、64个positive与24个negative上限样例；无失败时不伪造minimized corpus。Hypothesis仅进入test path，不进入wheel runtime行为、Schema version或Production dependency claim。

GitHub workflow的phase-neutral repository suite现显式包含`backend/tests/property`，integration contract固定该交接；既有Python/uv/Action/Compose pins和runtime container安装方式不变。Provider evidence须来自push后的真实run，不能由本地targeted test替代。

## TASK-P1-08 Snapshot persistence runtime

Snapshot builder/hash只使用Python 3.12标准库`dataclasses/enum/json/hashlib/copy`与既有pure domain/DataValidation/Expansion contracts；repository/migration复用已锁定`sqlalchemy==2.0.43`和`alembic==1.16.5`，property tests复用P1-07已锁定的`hypothesis==6.165.10`。`pyproject.toml`、`uv.lock`、schema/code metadata和runtime/dev dependency集合均不修改。

`0003_planning_snapshots`在SQLite与PostgreSQL dialect分别建立insert-only mutation trigger；当前自动化只在临时SQLite实际执行empty/populated upgrade/downgrade、repository replay/conflict/isolation和trigger负例，不能声明PostgreSQL并发、权限、性能或Production migration认证。仍无OR-Tools、Planning backend、Benchmark runner或新供应链工具，因此不触发Solver upgrade ADR/replay。

GitHub run `32310098594`对implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`完成exact lock sync、lint/type/test/build和machine evidence上传；该结果确认无dependency/lock漂移，不新增供应链或Production runtime声明。

## TASK-P1-11 stack review

Application pipeline和Gate CLI只使用Python 3.12标准库及已锁定的PyYAML/Reference Adapter依赖，不修改`pyproject.toml`或`uv.lock`。Workflow仍使用已锁定Python/uv/Actions版本，只增加P1 report命令和artifact glob中的JSON。仓库仍无OR-Tools、Solver backend、新数据库驱动或Production部署组件。

## TASK-P2-01 stack review

本Task只使用既有Python 3.12标准库、`jsonschema==4.25.1`开发验证能力与既有pytest/Hypothesis工具；runtime/dev dependency pins和`uv.lock`均不变，OR-Tools仍不存在。`app.planning.problem`保持TypedDict/dataclass/canonical JSON/SHA-256且无ORM/API/Infrastructure/Solver类型。

CI在既有full suites之后新增`python -m app.planning.problem.contract_check`，产出`ci-planning-problem-contracts.json`并由中性artifact glob上传。它不是新service/worker、数据库migration或Production endpoint；P2-03的Solver dependency ADR/Gate仍未触发。

## TASK-P2-02 stack review

Global schema metadata提升到`2.4.0`，实现仍只使用Python 3.12标准库、既有`jsonschema==4.25.1`开发验证和pytest。runtime/dev dependency列表没有增删，`uv.lock`保持启动SHA-256 `7ae68d242b1f80ad05a2ae51b09552ca9e19214d33ef8380bc74ff4c87ee64dd`；OR-Tools/CpModel/IntervalVar仍不存在。

Workflow新增`app.planning.policy.contract_check`机器步骤并由既有artifact glob上传JSON，没有新service、container、migration、API或Worker。P2-03首次Solver dependency仍必须单独exact pin、ADR、lock/replay与upgrade Gate；不能把本Task的Protocol当成Backend implementation。

## TASK-P2-03 OR-Tools lock

ADR-0011先于dependency变更接受。Runtime现exact pin `ortools==9.15.6755`，`uv.lock` SHA-256为`8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`；锁内固定`absl-py==2.5.0`、`immutabledict==4.3.1`、`numpy==2.5.2`、`pandas==3.0.5`、`protobuf==6.33.6`和既有`typing-extensions==4.16.0`，并保存CPython 3.12 Windows amd64、manylinux x86-64/aarch64及macOS x86-64/arm64 wheel hashes。Local replay为CPython 3.12.13/Windows AMD64；Linux provider仍必须由exact pushed SHA的locked install和artifact证明。

OR-Tools import只允许出现在`backend/app/planning/backends/cp_sat/`。本Task没有引入service、container、migration、DB/API/Worker、Strategy、业务constraint/objective、Validator或Benchmark runner。Point-in-time `pip-audit==2.10.1`检查显示新增OR-Tools依赖子树无记录；既有`pytest==8.4.1`与`starlette==0.47.3`存在上游advisory，登记为RISK-011且不在本Task越界升级。该结果不是持续供应链监控或Production安全认证。

GitHub implementation run `32346208046`在Linux/x86_64、CPython 3.12.13以exact lock安装OR-Tools`9.15.6755`并通过全部Gate；artifact `9398128763`保存该平台identity和wheel/lock证据。该provider replay关闭P2-03，不改变后续Golden/Benchmark升级门。

## TASK-P2-04 validator stack review

正式Validator只使用Python 3.12标准库和既有solver-neutral Planning合同；测试复用pytest、Hypothesis与既有`jsonschema==4.25.1`验证能力。`pyproject.toml`、`uv.lock`、Schema metadata和所有dependency pins均不变，Validator namespace没有OR-Tools import。

Workflow只增加`app.planning.validation.problem_validator_check`机器步骤并由既有artifact glob上传JSON；没有新service、container、database、migration、API、Worker或Benchmark runtime。P2-03的OR-Tools仍只存在于CP-SAT Backend namespace，P2-04不把Validator变成Solver组件。

## TASK-P2-05 technology use

Core model使用既有exact pin `ortools==9.15.6755`的`cp_model` API构造IntVar、BoolVar、optional interval、`AddExactlyOne`与`AddNoOverlap`；没有修改`pyproject.toml`或`uv.lock`，也没有新Schema、migration、service或runtime dependency。Native对象继续只存在于`planning/backends/cp_sat`，对外仍返回JSON-compatible PlanningSolution与machine report。

测试复用既有pytest/Hypothesis，并以单worker、显式seed和SolveLimits时间上限保证可重放边界。CI增加core machine CLI但不启用Benchmark runner或Production Solver入口。

## TASK-P2-06 technology use

Temporal model复用exact-pinned `ortools==9.15.6755`的linear constraints、fixed/optional intervals、`AddNoOverlap`与`OnlyEnforceIf`；signed integer rounding由Python整数运算完成，不使用浮点或隐式timezone转换。`pyproject.toml`、`uv.lock`及所有transitive pins不变。

没有新增Schema、migration、service、container、database、API、Worker或runtime dependency。OR-Tools import仍被限制在`planning/backends/cp_sat`，CI只新增temporal machine evidence步骤，不启用Strategy、objective或Benchmark runner。

## TASK-P2-07 technology use

Fact/lock模型复用exact-pinned `ortools==9.15.6755`的linear equality、optional interval、`AddExactlyOne`与`AddNoOverlap`；没有修改`pyproject.toml`、`uv.lock`或transitive pins。新增OR-Tools import只位于既有`planning/backends/cp_sat/fact_lock_constraints.py`，namespace scan同步覆盖该路径。

没有新增Schema、migration、service、container、database、API、Worker或runtime dependency。CI只增加fact/lock machine evidence步骤并沿用既有artifact glob；不启用OBJ-001搜索、Strategy、dynamic Replan或Benchmark runner。

## TASK-P2-08 objective technology

OBJ-001复用exact-pinned `ortools==9.15.6755`，使用IntVar、`AddMaxEquality`、整数线性和与`Minimize`表达Demand completion和priority-weighted tardiness seconds；先检查每项及总和可落入CP-SAT int64。`pyproject.toml`、`uv.lock`、wheel hashes、Backend identity/version与所有Schema均不变，namespace scan新增且只允许`objectives.py`的OR-Tools import。

CI新增`app.planning.backends.cp_sat.objective_strategy_check`并沿用`build/validation/*.json`/中性artifact；没有新Action、service、container、migration、database、API、Worker或BenchmarkRunner。Timing/memory/model metrics只作tiny correctness可观测性，不形成Production hardware/SLA结论。

## TASK-P2-09 stack review

Correctness orchestration只使用现有Python 3.12、JSON/YAML、jsonschema/Hypothesis/pytest和exact-pinned OR-Tools `9.15.6755`；`pyproject.toml`与`uv.lock`字节保持不变。CI新增`python -m app.simulation.scenarios.p2_correctness`步骤并复用既有artifact upload，不增加Action、service、container、Secret、migration或runtime dependency。

## TASK-P2-10 reference technology review

Reference实现只使用Python 3.12标准库、既有solver-neutral Planning typed contracts与formal Validator；baseline namespace不直接导入native Solver package或`planning.backends`。Unit/property tests复用既有pytest/Hypothesis，CI复用既有Python/uv/Actions与`build/validation/*.json` artifact glob。

`pyproject.toml`、`uv.lock`、Schema/code metadata、exact Solver pin及全部transitive dependency字节不变；没有新Action、service、container、database、migration、API、Worker或Benchmark dependency。因此不触发dependency ADR/upgrade Gate，single-run runtime也不形成hardware或SLA结论。

## TASK-P2-11 technology review

Reporting/export实现继续使用Python 3.12标准库的`dataclasses`、`hashlib`、`json`、`csv`、`tempfile`与`os.replace`；runtime/development dependency和`uv.lock`均无变化。JSON Schema Draft 2020-12验证沿用既有`jsonschema` dev tool，Ruff/Pyright/Pytest/CI技术选择不变。

Global schema metadata additive提升为`2.5.0`。CI新增`app.exporters.contract_check`机器步骤并上传同一evidence artifact；没有新service、container、database、queue、network或external storage provider，也没有技术栈ADR触发。

## TASK-P2-12 technology review

Benchmark实现使用Python 3.12标准库`dataclasses/statistics/platform/tracemalloc/perf_counter/hashlib/json`与已有dev pin `PyYAML==6.0.2`读取profile；Solver仍为exact `ortools==9.15.6755`且仅CP-SAT namespace直接导入。`pyproject.toml`、`uv.lock`、runtime/dev dependency、schema/code metadata均零变化，因此无dependency ADR或migration。

CI把既有deferred shell hook替换为直接Python CLI XS调用，并把`build/benchmarks/*.json`加入同一artifact；没有新Action、service/container/database/queue/network/provider。Baseline环境值只用于可比性，不是部署规格。

## TASK-P2-13 technology review

Gate实现只使用Python 3.12标准库`argparse/datetime/hashlib/json/pathlib/perf_counter`与已有public application/planning/simulation/export boundaries；没有新增runtime/dev dependency、Action、service、container、database、queue或network provider。`pyproject.toml`、`uv.lock`、Schema set`2.5.0`、OR-Tools exact pin和所有migration保持字节不变，因此Dependency/Schema/Migration/ADR impact均为none。

`p2-vertical-slice-report.v1`是严格internal Python-validated machine contract，未发布外部JSON Schema；若未来持久化、API或第三方consumer使用，必须另立Task发布Schema/compatibility/retention。当前workflow仅新增不可跳过的CLI step并复用`actions/upload-artifact@v4`既有路径。

Implementation provider对exact lock、Lint、Type、full tests、Gate、build与artifact全部success；artifact digest=`sha256:35e67191d1026169d9acd2a64f50e93bd8d2704df9f8ba1a2297f2dd2a00ca4d`。本Task无dependency/Schema/migration/ADR变化的结论据此闭环。

## P3 dependency allocation

本次transition不修改Python依赖、`uv.lock`、Frontend依赖或CI。TASK-P3-01须先在ADR/技术栈中确认React/TypeScript/build/test方案；只有TASK-P3-11可在独立授权后引入exact frontend pins/lock并执行point-in-time SCA/license审查。P3-12/13不得无审查增加Gantt/E2E库，Production部署栈继续未形成。

## TASK-P3-01 frontend stack decision

ADR-0012已接受React + TypeScript + Ant Design + TanStack Query；build/dev选择Vite；package manager选择npm并要求`package-lock.json` + `npm ci`；unit/component选择Vitest + Testing Library；browser E2E选择Playwright。该组合遵循总规推荐栈并与P3-11现有acceptance command一致。

TASK-P3-01没有创建`frontend/**`、`package.json`/lock、Node pin、dependency、bundle、test或workflow；因此这些组件仍是selected-not-installed。P3-11启动前必须逐字固定Node/npm和全部direct pins、lock策略、SCA/license命令并由exact provider执行；P3-12/13新增Gantt/E2E库必须另行dependency review。SSR、microfrontend、client-side Solver与Production hosting不在当前决定内。
## TASK-P3-02 technology and dependency review

P3 Schema/precheck复用Python 3.12标准库、既有`jsonschema==4.25.1`与`referencing`链；没有新增runtime/dev dependency。`pyproject.toml`只把global schema metadata提升到`2.6.0`，`uv.lock`保持启动摘要`sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`。CI增加单一required machine step并复用既有artifact upload glob。

本Task不安装Frontend技术栈、不增加DB/queue/export库、不修改Solver/Validator，也不形成Production topology。

## TASK-P3-03 persistence technology review

实现只复用locked Python 3.12、SQLAlchemy `2.0.43`与Alembic `1.16.5`；`pyproject.toml`和`uv.lock`零变化。`0004_schedule_versions_audit_export_jobs`使用SQLAlchemy/Alembic portable table/index/FK/check定义，并为SQLite/PostgreSQL分别提供immutability trigger；repository使用SQLAlchemy Core、nested savepoint仅处理PostgreSQL concurrent unique race，SQLite保持caller rollback语义。

临时SQLite证明合同、migration和negative path，不证明PostgreSQL并发吞吐、locking plan、capacity、backup或Production deployment。未引入outbox、queue、storage SDK、API/UI或P4依赖。
