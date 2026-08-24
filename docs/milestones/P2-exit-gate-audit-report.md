---
doc_id: MILESTONE-P2-AUDIT-001
title: P2 Exit Gate Audit Report
status: baseline
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [75, 76, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-24
---

# P2 Exit Gate Audit Report

## Decision

| Field | Audited value |
|---|---|
| Audit Task | TASK-P2-14 |
| Task lifecycle | `done`；审计实现提交的exact required provider已成功，本revision为evidence-only closure |
| Audit date | 2026-08-24 (Asia/Hong_Kong) |
| Local execution window | 2026-08-24T08:16～08:24+08:00 |
| Diff base | `e76776d83726d13600d8ea29fd490474c8e32604` |
| Audited business baseline | `e76776d83726d13600d8ea29fd490474c8e32604`；P2-13 evidence-only closure |
| Audit execution head | `c6e57566871faefb2582e1c33218e1ba22b44785`；只含P2-14 activation docs，业务代码/Schema/test/lock均与audited baseline相同 |
| Schema / Solver | schema set `2.5.0`；PlanningProblem v2 `2.3.0`；PlanningSolution/SolverReport v1 `2.4.0`；KPI v2/ExportManifest v1 `2.5.0`；OR-Tools `9.15.6755` exact pin |
| Provider baseline | GitHub Actions / `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml` |
| P2-13 closure provider | run `32466635638` / required job `96724500691` / artifact `9440970310` / digest `sha256:4a41a54cde5fe0cb349f177769bfff6e17b5820ffbf68c4811c46169a3860890` / not expired |
| Audit activation provider | run `32675914600` / required job `97283877370` / artifact `9502674319` / digest `sha256:242d3d76e5570aa15cbba009ffd9294545940ea45f24fa945695bd6b6d6d5fef` / not expired；20/20 JSON PASS |
| Audit implementation provider | SHA `65c556789f176ad9de55523d6420737bb60f933f` / run `32677741558` / required job `97288829348` / artifact `9503227240` / digest `sha256:fbb76c4340e71a571f3051db1813e89931b17eb92f69bfd8a9cca0932987e720` / not expired；20/20 JSON PASS |
| Branch protection | `main.protected=true`；required check `validate` / GitHub Actions app ID `15368`；force-push/deletion disabled |
| Auditor | Codex execution agent |
| Attestation | 本地命令、Git拓扑、下载后的364份CI JSON与GitHub API事实分别核验；这是透明的非密码学审计声明，credential未写入仓库或artifact |
| Overall P2 Exit Gate | `READY` |
| Blocking gaps | none |
| Recommendation | 请求用户另行明确批准P2→P3；本Task不改变current phase、不创建P3 Task |

机器可读结论见
[`P2-exit-gate-evidence-manifest.json`](P2-exit-gate-evidence-manifest.json)。
`READY`只表示总规§75～76的P2 CP-SAT Synthetic Solver Gate已有可复验证据；它不表示
Production readiness、真实工厂capacity/SLA、审批发布、ScheduleVersion/ExportJob、P3 Workspace、
dynamic Replan或P4+能力已经形成。

既有`p2-vertical-slice-report.v1`内的
`exit_gate_decision=NOT_PERFORMED` / `p2_14=NOT_STARTED`是TASK-P2-13冻结的
“非Exit审计”边界，不是本次TASK-P2-14生命周期的当前值。本报告与manifest才是独立Exit判定载体；
没有修改历史Gate bytes来追写新事实。

## Gate evidence

| Gate | Result | Evidence actually observed | Boundary |
|---|---|---|---|
| P2 Task lineage and scope | `PASS` | P2-01～13均`done`；13组Diff base→implementation→closure→current ancestry成立；P2-03先行ADR与P2-05有界scope commits均保留 | 不重写历史Task、commit或失败证据 |
| P2 provider chain | `PASS` | 26个implementation/closure push runs均attempt 1、completed/success；26个required `validate` jobs success；26个artifacts可取且未过期 | 本地PASS未替代GitHub provider事实 |
| Downloaded provider contents | `PASS` | 26个artifacts共364份JSON，0 parse error、0顶层FAIL；26份Task report均绑定exact SHA/Task且PASS/0 issues | 只审计已上传证据，不把文件数量当业务正确性 |
| Published contracts and compatibility | `PASS` | full contract regression通过；schema set`2.5.0`与各document固定版本并存；历史artifacts/fingerprints保留，strict offline解析成立 | 本Task无Schema或migration变化 |
| Dependency and ADR chain | `PASS` | locked sync通过；运行时`ortools=9.15.6755`；ADR-0001～0011全部`accepted`，ADR-0010/0011及无superseding链一致；`uv.lock`相对Diff base零变化 | point-in-time供应链证据不等于持续SCA/SBOM |
| P2 scope completeness | `PASS` | PlanningProblem/Policy/Limits/Solution、Global Strategy、CP-SAT Backend、formal Validator、5 Reference、BenchmarkRunner、KPI/9-payload internal Export均由registered tests和Gate重放 | 只覆盖C-001～C-011与OBJ-001；C-012～018、OBJ-002/003仍不支持 |
| Golden JSSP/FJSP | `PASS` | 两次正式Raw→Problem→Global Solver→fresh Validator replay均OPTIMAL；manual optimum、fixed hashes与row-order replay一致 | tiny correctness不是capacity证据 |
| Cross/Calendar/Material/Running/Hard Lock | `PASS` | 五类versioned scenario各两次通过；14次场景运行均记录Problem hash、model、build/first/solve/validation/total、objective/bound/gap、memory与Validator PASS | Simulation-only，不提供真实生产语义 |
| C-001～C-011 independent validation | `PASS` | 11个positive C-ID覆盖、11个formula-free exact negative mutation、每次candidate fresh Validator；hard violation=0或精确单C-ID失败 | Validator不导入Backend/OR-Tools，不信任solver status |
| OBJ-001 and status truthfulness | `PASS` | priority-weighted tardiness、objective/bound/gap一致；OPTIMAL/FEASIBLE/UNKNOWN/INFEASIBLE及Validator-fail边界回归通过 | UNKNOWN不冒充INFEASIBLE，FEASIBLE不冒充OPTIMAL |
| Reference Schedulers | `PASS` | 五算法在七场景与XS/S/M上使用同一Problem、fresh Validator与公共KPI；complete-or-discard/explicit failure保持 | non-production baseline，不是fallback或最优性证书 |
| Standard internal output | `PASS` | 两次Gate含2次显式output和6次benchmark嵌入export；KPI/SolverReport/Validation及9 payload的hash/count/lineage/atomic replay通过 | `publishable=false`；未创建ScheduleVersion/ExportJob/approval/publish |
| XS/S/M synthetic Benchmark | `PASS` | 独立三档各8/8、0 warning；Gate两轮共6 profile executions、18 Global measured、90 Reference measured、108 Benchmark Validator PASS | 只形成development evidence；OPEN-011/012、L/XL、Production SLA未关闭 |
| §76 required measurements | `PASS` | 七correctness场景由`p2-exit-scenario-metrics-audit.v1`两轮逐次记录；XS/S/M由versioned BenchmarkReport记录model/build/first/solve/objective/bound/gap/memory/Validator | raw timing/memory保留，不用稳定投影伪装相同 |
| Deterministic replay | `PASS` | 两次Gate的correctness/XS/S/M/export业务投影combined fingerprint均为`sha256:db224819b5163abb19e9e2543e87046930f3277238fdd138f0daa39ad4290faa` | 只比较versioned timing-independent projection；raw运行差异仍保留 |
| Four exact exit rejections | `PASS` | `UNSUPPORTED_CAPABILITY`、`INVALID_PLANNING_PROBLEM`、`INVALID_SOLVE_LIMITS`、`NO_SOLUTION_WITHIN_LIMIT`均exact fail-closed | 不合并为成功、INFEASIBLE证书或Production fallback |
| Repository quality/build | `PASS` | locked sync、Ruff、Pyright、476 tests、Compose config、docs full/diff、`git diff --check`和sdist/wheel build全部通过 | 功能测试不是唯一退出条件；本行不能替代scenario/benchmark/provider Gate |
| Governance and frozen scope | `PASS` | 审计前full=143 docs/30 roots/36 tests/15 OPEN/13 SIM/11 risks/37 Tasks；业务代码、Schema、fixture、benchmark、scripts、workflow、dependency/lock、migration、P3相对Diff base零差异 | 最终文档diff仍须在implementation commit前重跑 |
| PROD_OPEN / Simulation / risk truthfulness | `PASS` | OPEN-001～015继续`OPEN`；SIM-ASSUMPTION-001～013继续`ACTIVE`；RISK-001～011继续`MONITORED` | P2 READY不关闭任何生产未知项或风险 |

## §76 per-case measurement record

下表七个correctness场景来自额外两轮独立审计重放，时间/内存为两次观测范围；
model列为`variables / constraints / optional intervals`，单位均为seconds和MiB。

| Scenario | Model | Build range | First-feasible range | Objective / bound / gap | Memory range | Validator |
|---|---:|---:|---:|---:|---:|---|
| Golden JSSP | 17 / 17 / 4 | 0.001826～0.002364 | 0.000716～0.002550 | 0 / 0 / 0 | 0.0511～0.0562 | `PASS` ×2 |
| Golden FJSP | 13 / 13 / 4 | 0.001498～0.001950 | 0.002257～0.002423 | 0 / 0 / 0 | 0.0477～0.0502 | `PASS` ×2 |
| Cross Workshop | 9 / 11 / 2 | 0.001361～0.001452 | 0.000341～0.000363 | 0 / 0 / 0 | 0.0410～0.0424 | `PASS` ×2 |
| Calendar | 6 / 7 / 1 | 0.001252～0.001277 | 0.000403～0.000405 | 0 / 0 / 0 | 0.0360～0.0416 | `PASS` ×2 |
| Material Delay | 6 / 7 / 1 | 0.001227～0.001272 | 0.000338～0.000341 | 0 / 0 / 0 | 0.0356～0.0368 | `PASS` ×2 |
| Running Operation | 10 / 14 / 3 | 0.001483～0.001519 | 0.000342～0.000362 | 0 / 0 / 0 | 0.0417～0.0427 | `PASS` ×2 |
| Hard Lock | 7 / 11 / 2 | 0.001351～0.001505 | 0.000232～0.000297 | 0 / 0 / 0 | 0.0392～0.0412 | `PASS` ×2 |

XS/S/M下表来自commit-bound两轮Gate汇总；build/first/solve/total为三次measured run的代表median，
memory为观测maximum。每个profile在每轮均执行Global+五Reference。

| Profile | Problem hash | Model | Build | First | Solve / total | Objective / bound / gap | Memory max | Validator |
|---|---|---:|---:|---:|---:|---:|---:|---|
| XS | `sha256:a70a0549f737b2872185189a010cd89169d1f473f893947869b42cbf99937b04` | 41 / 51 / 16 | 0.003441 | 0.002757 | 0.003112 / 0.010536 | 0 / 0 / 0 | 0.0738 | `PASS` |
| S | `sha256:42ee217e95dc406a9feb5bf7813a3b73c8a5c6cca028905b0cfad68ffff75bb4` | 113 / 210 / 48 | 0.008507 | 0.008532 | 0.093082 / 0.111398 | 360 / 360 / 0 | 0.1538 | `PASS` |
| M | `sha256:a49ee150d456da16eda94da8977500543e137ce78710248f0bc6abea5e0c26aa` | 217 / 429 / 96 | 0.016997 | 0.022234 | 0.305887 / 0.348231 | 0 / 0 / 0 | 0.2798 | `PASS` |

环境为Windows 11 AMD64、CPython 3.12.13、32 logical CPUs、Google OR-Tools CP-SAT
9.15.6755、`time.perf_counter`；environment signature=
`sha256:7ae89489d67298d025f752890204570db02d49154425a8f5388e66aad6303514`。
这些数值用于P2 development Gate，不是跨环境或Production性能承诺。

## Local acceptance record

| Command | Exit | Observed result |
|---|---:|---|
| `uv sync --locked` | 0 | 69 packages resolved/checked from lock |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run pyright backend/app backend/tests` | 0 | 0 errors, 0 warnings, 0 informations |
| full registered pytest directories | 0 | 476 passed in 52.66s |
| P2 Gate CLI, repeat 2 | 0 | 11/11 checks、2 replays、14 scenarios、6 profiles、108 Benchmark Validator PASS、4 rejections、0 gaps |
| independent XS/S/M CLIs | 0 | each 8/8 PASS、0 warning、fixed Problem hash matched |
| independent seven-scenario metric replay | 0 | 7 scenarios × 2；14/14完整measurement records、0 issues |
| `docker compose --env-file .env.example config --quiet` | 0 | configuration valid |
| full docs governance before final writeback | 0 | PASS；143 docs、30 roots、36 tests、15 OPEN、13 SIM、11 risks、37 Tasks |
| P2-14 diff governance before final writeback | 0 | PASS；8 paths、2 activation impact rows、19 checks、0 issues |
| full docs governance after audit writeback | 0 | PASS；143 docs、30 roots/trace rows、36 tests、15 OPEN、13 SIM、11 risks、37 Tasks |
| P2-14 final diff governance | 0 | PASS；30 paths（8 committed-range / 30 working-tree union）、3 impact rows、19 checks、0 issues |
| `git diff --check` | 0 | no whitespace errors |
| `uv build` | 0 | sdist and wheel built successfully |
| GitHub API/run/job/artifact/protection queries | 0 | exact prerequisite provider and protection facts verified |

最终文档写回后的full/diff governance已经重跑并记录；审计Task自身provider结果仍必须在
implementation/evidence-only closure中追加，当前本地结果不冒充外部required evidence。

## P2 implementation and closure provider chain

每行均已独立查询implementation与evidence-only closure；括号内为
`run / required job / artifact`，完整digest见machine manifest。

| Task | Exact implementation head (run/job/artifact) | Exact closure head (run/job/artifact) |
|---|---|---|
| P2-01 | `c64284685f37ef0d03eacade5699076146653333` (`32336812748/96327855244/9394931377`) | `3cf4966481e4e8cb6e075a3305472e0f0a93b99c` (`32337439199/96329607133/9395135532`) |
| P2-02 | `2661598ecb592942e50c9a13dd41ff5b2535ca0d` (`32342489997/96344226221/9396828326`) | `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66` (`32342949743/96345556588/9396984310`) |
| P2-03 | `9268b88ca7ce90a8f72023241f87e2d3676fd58a` (`32346208046/96355386111/9398128763`) | `4c66dce3b919a53816005c4aebf4983db19a6108` (`32346604989/96356577126/9398269688`) |
| P2-04 | `9b532e2c054b02e1692f345a252922ec7fd469e4` (`32350068318/96367085099/9399519368`) | `c75f7a0e96b7591ffa9220d0de942f8841283093` (`32350571302/96368639237/9399702868`) |
| P2-05 | `df706786e0ec1c54bf60cd43261a92ef6aa53cc7` (`32354050257/96379299455/9400957897`) | `c55aa294977a6cafad85741f425d46cd36e9af1a` (`32354521904/96380738933/9401134902`) |
| P2-06 | `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c` (`32432482739/96626844156/9429579311`) | `33cc3282ead23a4cc1bb214190191e116b095119` (`32432843343/96627943272/9429703054`) |
| P2-07 | `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70` (`32435395744/96635463577/9430579117`) | `9c55df993b12ae0bdd3d4d38c900d601324c05d2` (`32435755901/96636509174/9430697910`) |
| P2-08 | `b1ec83ed96120357ecadd41d3f520181838f17c6` (`32438785162/96645152864/9431673977`) | `15c298f343a47db2a922544944ff5e02e4ca72d9` (`32439301758/96646617379/9431840946`) |
| P2-09 | `20e49c92306128b47313059fabe31534814dbe3d` (`32442651322/96656224252/9432982306`) | `0e4f6630412889254a7bef41f487c24dc274ca9c` (`32443067388/96657446617/9433118755`) |
| P2-10 | `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c` (`32449742281/96675839685/9435264655`) | `41e958b771f2664b1ac50867903a30b73627878d` (`32450216908/96677202782/9435421360`) |
| P2-11 | `546292831c3bd52185687a4c646c10ae10541ae2` (`32454693799/96689627030/9436863185`) | `58db14e8f18fb50866fb757d4c89e76fef1141f1` (`32455399561/96691604529/9437086153`) |
| P2-12 | `01e7f4bdca88fc903e7caa771f875fc1a70ff357` (`32460861563/96707353990/9438899443`) | `59f3b013a4be7bd11d054e8464886b3cde791602` (`32461665177/96709654227/9439159396`) |
| P2-13 | `dc2e5cd41080603606090ebfc4bc6162941c5f7f` (`32465737712/96721819879/9440650646`) | `e76776d83726d13600d8ea29fd490474c8e32604` (`32466635638/96724500691/9440970310`) |

P2-03的accepted ADR-0011先于dependency change，P2-05的activation/scope-refinement commits处于
其固定Diff range内；两者不是拓扑异常。全部26个artifact在审计日均未过期，下载内容总计
3,320,998 bytes / 364 JSON；每个Task trace report均为0 issues。

## Local machine artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| `TASK-P2-14-p2-gate.json` | 307157 | `17c987715246d5d9ca28bfb61763a9b243f2a4c92acc30283dc9f92f776a3100` |
| `TASK-P2-14-xs.json` | 20834 | `2e195a25da2f012fe2a70c7fa0b92a431cdd70a12085eae5d1e1854f26d2faf9` |
| `TASK-P2-14-s.json` | 20857 | `8f63013f285d6eb1c94f5ade2a9eea4decc86699a637d1da45c0bff3a0a385fa` |
| `TASK-P2-14-m.json` | 20929 | `0c35477d5b52decc7fbe3e7db640b1a08738c8be05472c25da3156b9112596bb` |
| `TASK-P2-14-scenario-metrics.json` | 14033 | `df0f19a7dd0c3c1612a62421d1bc824b27917491a99e5ebac338a544830bc46c` |

这些报告位于ignored `build/validation`，均绑定audit execution head
`c6e57566871faefb2582e1c33218e1ba22b44785`；不伪装为已提交产品artifact。

## Audit implementation provider closure

Audit documentation implementation commit `65c556789f176ad9de55523d6420737bb60f933f`的
GitHub push run [`32677741558`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32677741558)
为attempt 1 / `completed success`；required `validate` job `97288829348`的全部主步骤成功。
Branch protection继续精确要求`validate` / GitHub Actions app ID `15368`。

Artifact `9503227240`（`plantnexus-ci-evidence-32677741558`，85829 bytes，
digest=`sha256:fbb76c4340e71a571f3051db1813e89931b17eb92f69bfd8a9cca0932987e720`，
expiry=`2026-11-22T00:47:08Z`）未过期。下载后20份JSON共495904 bytes，0 parse error、
0顶层失败；Task report精确绑定该SHA/Diff base并记录30 committed/0 working paths、
3 impact rows、19 checks、0 issues。Provider Gate同样绑定该SHA并复现11/11、2 replays、
14 correctness scenarios、6 profiles、108 Benchmark Validator passes、4 rejections、0 gaps；
两次provider业务投影一致，combined fingerprint=
`sha256:f42ddb852594941953a00c873641d4a164e175c37b9b163b4ada3ddc77e18f7f`。
因此TASK-P2-14 completion conditions全部满足并在本evidence-only revision中关闭为`done`。

## Gaps, boundaries and recommendation

`blocking_gaps=[]`。没有发现需要在本audit内修复的P2实现、Schema、test、migration、
dependency、ADR、workflow或文档治理缺口。审计实现自身exact provider已经成功并由上述事实闭环；
本evidence-only closure的exact provider将在提交后外部核验，不能由本revision自我预填。

以下事项明确不被本结论关闭：OPEN-001～015、RISK-001～011、真实source/field/topology/calendar/
material/priority authority、独立Production数据库/角色、历史生产benchmark、L/XL、Production
capacity/SLA、安全持续扫描、ScheduleVersion/ExportJob、审批发布、P3 Workspace、dynamic Replan、
Execution Simulator与Production deployment。

因此下一动作不是自动进入P3，而是：提交本evidence-only closure、外部核验其exact required provider，
随后向用户报告P2 Gate=`READY`并等待明确的P2→P3授权。
未经该授权，`docs/current_phase.md`继续为P2，P2 Milestone继续`active`（Gate ready / awaiting decision），
不得创建或执行P3 Task。
