---
doc_id: DOC-INDEX-001
title: PlantNexus APS 文档中心
status: baseline
spec_version: 0.3.0
phase: P4
normative: false
source_sections: [2, 6, 70]
last_reviewed: 2026-08-27
---

# PlantNexus APS 文档中心

## TASK-P4-02 machine-contract release

TASK-P4-02已获单独授权并以`4026597ab1015b5ea3a89d241f0d12b5b481dee3`为不可变Diff base发布additive set `2.8.0`。ExecutionEvent/ReplanRequest/ChangeReport/ExecutionSimulationManifest以及Policy/SolverReport/ScheduleVersion/Export carrier的九份Schema与九份sample均为strict、no-default、offline-reference、Simulation-only合同；implementation `539cdbbdcdd406daba25b8d6b8caaa5133691e76`的exact required provider成功后，本evidence-only closure将TASK-P4-02标为`done`。P4-03、P5与Production均未启动。

## P4 activation and planning baseline

用户于2026-08-27在P3 Exit report/manifest=`READY`、`blocking_gaps=[]`且两个精确提交provider均验证后批准P3→P4。P3现为`completed`，P4为`active`；TASK-P4-00～02状态以上方当前段落为准，P4-03～15保持`planned`，P4-15是唯一最后独立Exit Audit。当前不形成任何P4业务行为、P5能力或Production readiness/authority/external/deployment/capacity/SLA。

## P3 Exit audit status

[P3 Exit report](milestones/P3-exit-gate-audit-report.md)与[machine manifest](milestones/P3-exit-gate-evidence-manifest.json)已形成一致的`READY`/0 gaps结论，并保留39个前序P3 provider提交、4个历史失败run与阶段边界。TASK-P3-17 audit implementation与evidence-only closure均已exact provider验证，TASK-P3-17=`done`；其“P3保持active、P4未启动”是closure时的历史边界，现已由上方明确transition决定取代。Production仍未启动。

本目录是 PlantNexus APS 的唯一实质性开发文档中心。项目采用 Simulation-First、可追溯和阶段门禁驱动的开发方式；文档不是事后说明，而是代码、Schema、测试、Fixture、Benchmark 和发布活动的前置边界。

## 权威顺序

发生冲突时按以下顺序处理：

1. 用户在当前任务中的明确要求；
2. `core/APS_IMPLEMENTATION_SPEC.md` 中当前版本的 MUST、MUST NOT 和 DECIDED；
3. 已接受且未被取代的 ADR；
4. 当前阶段文件和当前任务卡；
5. 其他参考文档。

发现冲突不得自行折中，应登记问题并停止受影响的实现。

## 日常读取顺序

```text
/AGENTS.md
→ docs/agents/AGENTS.md
→ docs/current_phase.md
→ 当前 TASK
→ TASK 引用的 Schema / Contract / Constraint / ADR
→ 相关代码
→ 相关测试
```

只有规格版本变化，或任务涉及架构边界、PlanningProblem、SolverBackend、Constraint Catalog、状态机、发布规则或阶段退出门时，才需要重新完整读取总规。

## 文档分区

| 目录 | 用途 | 成熟方式 |
|---|---|---|
| `core/` | 总规、范围、原则、术语、能力边界 | 稳定、规范性 |
| `governance/` | 需求、追踪、开放问题、假设、风险 | 持续维护 |
| `architecture/` | 系统边界、模块、数据权威、环境 | ADR 驱动 |
| `domain/` | 领域对象、时间语义、状态机、错误与 KPI | Schema/业务规则驱动 |
| `contracts/` | 可执行 Schema 对应的人类语义合同 | 与 Schema 同版本 |
| `planning/` | 策略、约束、目标、求解器与独立验证 | 规范性核心 |
| `simulation/` | 虚拟工厂、场景、生成器、执行仿真和性能门 | 可重放、版本化 |
| `quality/` | 测试矩阵、Fixture、Mutation、Property、Benchmark | 持续维护 |
| `milestones/` | P0-P7 目标、范围和退出门 | 阶段级 |
| `agents/` | Coding Agent 的读取、执行和停止规则 | 稳定、简洁 |
| `tasks/` | 有界任务卡 | 随当前阶段创建 |
| `adr/` | 架构和规则决策记录 | 只追加/取代，不改历史 |
| `operations/`、`runbooks/` | 实现后形成的运维事实 | 后期形成 |

当前已生成文档的完整可点击清单见 [`governance/document-inventory.md`](governance/document-inventory.md)。

## 文档状态

- `baseline`：由规格直接建立，可用于指导当前阶段。
- `living`：已经启用，但会随实现证据持续更新。
- `draft`：尚未批准，不能单独作为实现依据。
- `planned`：只有路径和目的，等待依赖形成。
- `superseded`：已被新文档或 ADR 取代，只保留历史。

## 当前范围

当前阶段为P4。P0～P3 Milestone均为`completed`；TASK-P3-00～17全部`done`且P3 Exit双提交provider已闭环。TASK-P4-00现为`done`，P4-01～15为`planned`成员；P4-01需要新的明确授权，P4-15最终独立审计也不自动进入P5或Production。详见`current_phase.md`。

P3已形成的顺序保持合同/ADR→Schema→persistence→validated DRAFT→read models→edit/lock→approval/reject→idempotent publish→ExportJob→API→Frontend/E2E→vertical Gate。批准的末段顺序为TASK-P3-15治理支持→TASK-P3-16本地化→TASK-P3-17独立Exit Audit；P3-16现已完成实现provider复验与文档closure，下一项仍须另行授权。展示术语规范见[`frontend/official-zh-cn-terminology-map.md`](frontend/official-zh-cn-terminology-map.md)，它不改变英文机器合同。

## 仓库入口与本地检查

- 项目入口、版本占位和当前可执行命令见 [`../README.md`](../README.md)；
- 根 [`../AGENTS.md`](../AGENTS.md) 只负责把 Agent 导向规范正文，不复制规则；
- 仓库治理检查运行 `uv run python scripts/check_docs.py`；
- 该检查验证 metadata、文档 ID、Markdown fence、本地链接、Task、版本化 registry、完整 ID 引用、逐根 traceability 和命名空间隔离；
- Task 进入 `in_progress` 时记录完整 `Diff base`；`--task <task-card> --check-diff` 对 `Diff base..HEAD` 与 working tree 的并集匹配 change-impact Rule ID，并可用 `--report <path>` 输出 `traceability-report.v1`。

本地检查从`current_phase.md`读取current `Pn`，保留历史terminal Task且拒绝future-phase详细卡。普通CI range只能归属一张current-phase Task；初始phase-planning batch仅允许唯一新建`TASK-Pn-00` owner加同range新建的`planned/ready`成员卡。后续阶段计划修订要求唯一已存在的`phase-plan-amendment-owner`、稳定逻辑Task ID、完整Diff base及仅`planned/ready`且无implementation SHA的成员；active/done成员改写、纯删除与重复路径均拒绝。选择owner后仍按其Diff base执行scope/impact。Provider结果必须来自真实授权运行，不能由本地PASS推断。

CI 可用 `uv run python scripts/check_docs.py --discover-task-from <event-base-sha> --check-diff --report build/traceability/ci-current-task-report.json`从一次 PR/push event range发现唯一 current-phase Task；本地 Task验收仍使用显式 `--task`。两种入口最终都使用 Task Card内的 immutable `Diff base`，不能把 event base当作 Task scope base。

## P2 历史执行证据

TASK-P2-03本地39项聚焦、319项全量和6/6 foundation均PASS；exact GitHub required `validate`与artifact也已核验，Task=`done`。工程smoke仍不是业务Solver/Validator/Benchmark证据。

TASK-P2-04本地证据为6/6 formal machine checks、13个mutation、11个C-ID、14个hard violations和6个duration/order examples；implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的exact GitHub run `32350068318` / required job `96367085099` / artifact `9399519368`复现该报告和38-path/6-row/0-issue Task report，故Task=`done`。本Task未修改Backend、合同Schema、fixture bytes、dependency、objective或Benchmark。

TASK-P2-05已形成C-001/003/004/010/011 core CP-SAT、完整candidate映射、formal Validator consumer、fixed-seed property与独立tiny oracle。Local acceptance为64 focused、360 full、Ruff/Pyright 0、core/formal各6/6、治理49 paths/6 rows/0 issues、compose/build/immutable PASS；implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的run `32354050257` / job `96379299455` / artifact `9400957897`精确复现证据，Task=`done`。

TASK-P2-06已把precedence/calendar/release/material/transport提升为C-002/005/006/009模型；TASK-P2-07再形成COMPLETED/RUNNING facts、HARD exact lock、SOFT metadata-only的C-007/008模型。Implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的exact provider evidence已闭环，Task=`done`；TASK-P2-08已在closure基线上启动，后续Task仍未授权。

TASK-P2-08把唯一OBJ-001精确建模为priority-weighted tardiness seconds，并由GlobalCpSatStrategy以显式Simulation Policy/Limits一次调用完整Backend；所有candidate必须经formal Validator PASS。70 focused、395 full及`objective-strategy-report.v1` 7/7本地PASS，implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的run `32438785162` / job `96645152864` / artifact `9431673977`精确复现并闭环为`done`；tiny timing不得作为Benchmark或SLA。

TASK-P2-09以`15c298f343a47db2a922544944ff5e02e4ca72d9`为Diff base启动。七个Scenario/Profile/assembler/policy/solver version及P0/P1 asset清单摘要已冻结；允许范围只覆盖新correctness assets、`simulation.scenarios`编排、四类测试、CI evidence和治理文档。Planning/Application/Generator、Problem/Solver/Validator语义、Schema、dependency、Benchmark与P3保持只读。

本地correctness实现使2个Golden和5个matrix case全部OPTIMAL且formal Validator PASS，固定7组Import/Snapshot/Problem hash；Hypothesis row-order/fresh Validator property与11个formula-free exact C-ID mutation均PASS。45 focused、427 full、8/8 machine、Ruff/Pyright、全部历史reports、Compose/build及58-path治理均PASS；implementation exact required run/artifact已复现同一证据并闭环为`done`。

用户于2026-08-21明确授权TASK-P2-10；clean/provider-verified Diff base为`0e4f6630412889254a7bef41f487c24dc274ca9c`，其run `32443067388` / required job `96657446617` / artifact `9433118755`均success。当前只启动五算法identity/tie-break、完整candidate或明确heuristic failure、fresh formal Validator和CI report；既有Schema/Planning/Validator/correctness assets/dependency与Benchmark/Production/P2-11+保持冻结。

TASK-P2-10实现为5个versioned deterministic algorithms、35/35 complete candidate/fresh Validator/deterministic replay及5个zero-partial explicit failures；`reference-scheduler-report.v1`为7/7 PASS。13个Task-specific与441个full tests、Ruff/Pyright均PASS；implementation exact required run/artifact已精确复现17/17 reports并闭环为`done`。Global comparison/XS-S-M/threshold、Export、Production fallback和P2-11+仍未启动。

用户于2026-08-21明确授权TASK-P2-11；clean/provider-verified Diff base为`41e958b771f2664b1ac50867903a30b73627878d`，其run `32450216908` / required job `96677202782` / artifact `9435421360`均success。当前只启动additive KPI/manifest合同、validated solution reporting和不可发布internal package；ChangeReport/BenchmarkRunner、P3 state/persistence/approval/publish及P2-12～14保持冻结。

TASK-P2-11链路为`Snapshot/Problem → validated PlanningSolution + ValidationReport + SolverReport + ImportQualityReport → KPI v2 → p2-internal-export.v1`。Machine report执行8项确定性、Schema/sample、血缘、tamper/mixed-run、原子写入/清理和状态边界检查；它不创建ScheduleVersion或ExportJob，也不产生可发布artifact。Global schema set现为additive `2.5.0`，既有document版本与bytes不改。Implementation `546292831c3bd52185687a4c646c10ae10541ae2`的required run `32454693799` / artifact `9436863185`已精确复现output 8/8、18/18 reports与58 committed/0 working paths，Task=`done`；P2-12不自动启动。

用户于2026-08-21明确授权TASK-P2-12；clean/provider-verified Diff base为`58db14e8f18fb50866fb757d4c89e76fef1141f1`，其run `32455399561` / required job `96691604529` / artifact `9437086153`均success。当前只启动versioned XS/S/M benchmark profile/baseline、同Problem/Validator/KPI的Global与五Reference比较、环境/规模/时间/质量/内存报告和CI XS artifact；L/XL、Production capacity/SLA、P2-13/14与P3保持冻结。

TASK-P2-12已形成严格Profile/Report/Baseline v1、确定性source-shaped generator、warm-up/repetition/median/p95、环境签名、Global/五Reference comparison、`BENCHMARK_WARNING`和immutable baseline规则。XS/S/M报告绑定三个固定Problem hash并均为8/8 PASS；implementation `01e7f4bdca88fc903e7caa771f875fc1a70ff357`的run `32460861563` / required job `96707353990` / artifact `9438899443`已复现19/19 PASS与49-path治理，Task=`done`。该证据只属development/simulation，OPEN-011/012保持OPEN，P2-13/14与P3未启动。

用户于2026-08-21明确授权TASK-P2-13；clean/provider-verified Diff base为`59f3b013a4be7bd11d054e8464886b3cde791602`，其run `32461665177` / required job `96709654227` / artifact `9439159396`均success。当前只编排已发布的P2公开边界，重放correctness与XS/S/M并聚合Validator/KPI/SolverReport/Export、四类拒绝和CI artifact；不得混入remediation、Exit READY、P2-14或P3。

TASK-P2-13本地已形成`p2-vertical-slice-report.v1`与`p2-gate-semantic-projection.v1`：两次完整replay均PASS，七场景、XS/S/M、Global+五Reference、formal Validator、KPI/SolverReport、internal Export和四类拒绝全部闭环。聚焦30项与全仓476项测试PASS，11项Gate checks全部PASS且无blocking gap；exact implementation provider形成前Task仍为`in_progress`，P2-14/P3保持未启动。

Implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的required run `32465737712` / job `96721819879` / artifact `9440650646`已精确复现20/20 JSON、Gate 11/11与37-path治理证据，故TASK-P2-13=`done`。P2仍为`active`，P2-14仍是未授权的唯一最后Exit Audit，P3未进入。
