---
doc_id: DOC-PHASE-CURRENT
title: 当前阶段
status: living
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [73, 74, 75, 76, 110, 111]
last_reviewed: 2026-08-21
---

# 当前阶段：P2 — CP-SAT Vertical Slice

## 阶段授权与证据

用户于2026-08-20明确批准P1→P2 phase transition，并授权先进行P2 Task规划。切换前已重新核验：TASK-P1-01～12全部`done`；[P1 Exit Gate audit](milestones/P1-exit-gate-audit-report.md)与[machine manifest](milestones/P1-exit-gate-evidence-manifest.json)给出overall=`READY`、blocking gaps为空；audit implementation `a5d7e4a68dc12d48e36cb692500f59446f8097b4`是规划基线`098c44059856e3203d95d046fea44894b5cf414b`的祖先。

GitHub上audit implementation的push run `32326616525` / required `validate` job `96299073525` / artifact `9391591718`均success；规划基线自身的run `32327121469` / job `96300506550` / artifact `9391753870`也精确绑定`098c44059856e3203d95d046fea44894b5cf414b`并success。规划启动时`main=origin/main`且working tree clean，因此前提一致，阶段切换成立。

P1 Milestone现为`completed`，P2 Milestone为`active`。这只授权P2范围内的Task规划与后续逐Task实现，不表示Solver、Validator、Benchmark、Export或Production能力已经形成。

## 当前目标

建立唯一受支持的P2纵向链：

```text
PlanningSnapshot
→ PlanningProblem v2
→ PlanningPolicy + SolveLimits
→ GlobalCpSatStrategy + CpSatBackend
→ PlanningSolution
→ independent ScheduleValidator
→ KPI + SolverReport + internal Export package
→ Reference Scheduler / BenchmarkRunner
```

只实现C-001～C-011与OBJ-001；Gate覆盖Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock和XS/S/M，并记录model size、build、first feasible、objective、bound、gap、memory、Validator与Snapshot→Export证据。

## 当前Task与启动边界

`TASK-P2-00 — P2 Phase Transition and Task Planning Governance`、`TASK-P2-01 — PlanningProblem v2 Contract Gap Closure`与`TASK-P2-02 — Planning Machine Contracts and Status`均已闭环为`done`。P2-02 implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`的GitHub push run `32342489997`、required `validate` job `96344226221`与artifact `9396828326`均精确绑定该SHA并为success；closure HEAD `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`的run `32342949743` / job `96345556588` / artifact `9396984310`也成功并作为P2-03 Diff base。

用户于2026-08-20明确授权执行`TASK-P2-03 — OR-Tools and SolverBackend Foundation`；该Task以clean、provider-verified `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`启动，并在依赖变更前接受ADR-0011。现已由implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的GitHub run `32346208046` / required job `96355386111` / artifact `9398128763`闭环为`done`。Problem/Policy/Solution/Report合同字节和语义保持只读。

P2-02把global schema set additive提升到`2.4.0`，新增四个互相离线解析的v1 document contract，并以`CONTRACT_SAMPLE`/`SOLVER_RUN`显式区分shape样例与真实运行。该发布样例的`not-installed`是P2-02历史shape证据，不随P2-03安装依赖而改写。TASK-P2-00～08现均由exact implementation provider evidence闭环为`done`；TASK-P2-09已获授权并为`in_progress`，P2-10～14未获授权。

## 当前允许

- 按已授权Task在P2范围内演进solver-neutral Problem/Policy/Limits/Solution/Report合同；
- exact pin OR-Tools并保持其只存在于CP-SAT Backend；
- 逐项实现C-001～C-011、OBJ-001、formal independent Validator、Reference Schedulers、internal Export与BenchmarkRunner；
- 使用versioned Simulation Policy/Profile/Scenario运行correctness与XS/S/M；
- 每个Task完成本地验收后，在用户本次授权边界内提交并直接push当前`main`，再核验exact required `validate`和artifact。

## 当前禁止

- TASK-P2-09已获用户明确授权并进入`in_progress`；未经另行授权不得启动P2-10～14，TASK-P2-08已关闭且不再扩展其OBJ-001/Global Strategy范围；
- 修改Task允许范围外文件、预填PASS/provider evidence或跳过独立Validator；
- 实现C-012～C-018、OBJ-002 Stability、动态Replan、ExecutionSimulator、P3 Workspace/审批/发布状态；
- 把UNKNOWN写成INFEASIBLE、FEASIBLE写成OPTIMAL，或以hint代替Execution Fact/HARD lock；
- 猜测Production权重、calendar/transport/default solve limits、性能阈值或真实system authority；
- 将synthetic correctness/XS/S/M结果外推为Production SLA、容量或readiness。

## 阶段完成条件

- Problem/Policy/Limits/Solution/Report版本化合同与solver/backend隔离成立；
- C-001～C-011与OBJ-001由CP-SAT实现且formal independent Validator全部PASS；
- Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock、Property/Mutation与Reference Scheduler证据形成；
- Snapshot→Export internal package闭环，报告/hash/版本一致；
- XS/S/M报告包含全部Gate字段且有provider artifact，不形成Production承诺；
- TASK-P2-01～13全部`done`后，最后执行TASK-P2-14 Exit Gate Audit；只有audit=`READY`且用户再次明确批准，才允许请求进入P3。

Task全部完成或audit READY都不自动切换P3；失败时保持P2并建立有界remediation Task。

## TASK-P2-03 执行结果

`ortools==9.15.6755`、`cp-sat-backend.v1`、七状态adapter、SolveLimits参数映射、namespace/serialization隔离与6-check machine report已形成；本地39 focused、319 full、Ruff/Pyright、P2-02/P0历史兼容、Compose和build均PASS。Provider artifact精确复现Linux/x86_64、6/6 foundation及50 paths/9 rows/0 issues，因此TASK-P2-03=`done`。

该foundation在TASK-P2-03关闭时没有business model builder，真实`solve()`以稳定MODEL_INVALID边界停止；empty model的OPTIMAL不表示PlanningProblem可行。该历史边界已由TASK-P2-05～07的bounded C-001～C-011 consumer取代；P2-08～14仍未授权，current phase保持P2且不进入P3。

## TASK-P2-04 启动边界

TASK-P2-04以`4c66dce3b919a53816005c4aebf4983db19a6108`为不可变Diff base，复用且不修改Problem v2、PlanningSolution、ValidationReport/Error v2与constraint-rule-sheet v1。正式Validator必须独立重算C-001～C-011，不能导入Backend/OR-Tools、复用CP-SAT constraint builder、读取expected outcome决定结果或信任solver status。P0 fixture-local evaluator与全部历史asset bytes保持只读；P2-05 core model、OBJ-001、Benchmark、DB/API/Worker和P3仍未启动。

## TASK-P2-04 执行结果

正式`ProblemScheduleValidator`现直接消费Problem v2与candidate PlanningSolution，按稳定顺序独立判定C-001～C-011，并把失败映射为`validation-report.v2`与`error.v2`。本地machine report为6/6 PASS，覆盖13个声明式mutation、11个C-ID、14个hard violations、一个positive/status-contradiction replay和6个duration/order examples；AST证据确认无Backend/OR-Tools/expected outcome决策依赖。

本地指定suite=`59 passed`、full=`343 passed`，Ruff/Pyright、历史machine compatibility、Compose、build与38-path/6-row/0-issue治理均PASS。Exact implementation provider artifact内formal report绑定同一SHA并为6/6 PASS，Task report为38 committed/0 working paths、19 checks、0 issues；因此TASK-P2-04=`done`。

## TASK-P2-05 启动边界

用户于2026-08-20明确授权执行TASK-P2-05。启动复核确认`main=origin/main=c75f7a0e96b7591ffa9220d0de942f8841283093`、working tree clean，且该SHA的GitHub run `32350571302` / required job `96368639237` / artifact `9399702868`精确成功。Problem/Solution/Policy/Limits Schema、constraint-rule-sheet v1、formal Validator、Planning contracts、Problem builder/hash、OR-Tools exact pin与`uv.lock`均作为不可变启动基线。

本Task只建模C-001/003/004/010/011，必须在build前拒绝任何需要C-002/005～009的非空事实，并用formal independent Validator复验candidate。不实现OBJ-001搜索目标、Strategy、Benchmark threshold、DB/API/Worker或P3；纯可行模型的native OPTIMAL不能升格为业务最优声明。P2-06及以后仍为`planned`且未获授权，current phase继续为P2。

## TASK-P2-05 执行结果

Core builder现使用master/optional intervals、exact-one candidate、candidate-specific duration、capacity-1 NoOverlap和horizon域；Backend把完整candidate映射为诚实FEASIBLE并强制formal Validator PASS，zero/overflow与P2-06/07非空事实在build前fail closed。模型不含objective，OBJ-001 stage仅为post-solve measurement。

本地验收：focused `64 passed`、full repository `360 passed`、Ruff/Pyright 0、`cp-sat-core-model-report.v1` 6/6、formal report 6/6、治理142 docs且Task diff 49 paths/6 rows/19 checks/0 issues、compose/build/immutable diff PASS。

Implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的GitHub run `32354050257` / required `validate` job `96379299455` / artifact `9400957897`均success；artifact digest=`sha256:c40c20dcc09e2beb38e85bbead96b83e624c8badc25c88bf78cc5a3990c7d46c`，core/formal/Task报告均绑定该SHA并分别为6/6、6/6、49 committed/0 working/6 rows/19 checks/0 issues。TASK-P2-05=`done`。Current phase保持P2；TASK-P2-06的启动来自用户新的明确授权，不是依赖完成后的自动过渡。

## TASK-P2-06 启动边界

用户于2026-08-21明确授权执行TASK-P2-06。启动复核确认`main=origin/main=c55aa294977a6cafad85741f425d46cd36e9af1a`、working tree clean，且该SHA的GitHub run `32354521904` / required `validate` job `96380738933` / artifact `9401134902`精确成功，artifact digest=`sha256:03f304162e1d862ecc320cf592a27ca1c41282cbcc9ea7c060718bcc69842fe9`。P2-05 implementation是该基线祖先；Problem/Policy/Solution Schema、constraint-rule-sheet、formal Validator、Problem builder/hash、OR-Tools pin与`uv.lock`全部冻结。

本Task只把C-002/005/006/009加入现有bounded CP-SAT模型：min使用ceil tick、max使用floor tick，calendar保持秒级half-open与tick-grid等价，release/material分别形成下界，transport只按实际选择资源的workshop独立判定。C-007/008、OBJ-001搜索、Strategy、Benchmark threshold、DB/API/Worker和P3均不在范围；native OPTIMAL仍只映射为业务FEASIBLE，UNKNOWN不得改写为INFEASIBLE。P2-07及以后保持`planned`且未获授权。

## TASK-P2-06 本地实现边界

Temporal builder现组合signed exact rounding、inclusive min/max lag、historical completion anchor、calendar fixed intervals、release/material gates及selected-option conditional transport；min与transport独立施加而非相加。Core precheck只对sub-second/overflow及仍属P2-07的RUNNING/lock fail closed；所有完整candidate继续强制formal Validator PASS。

本地验收为focused `87 passed`、full repository `367 passed`、Ruff/Pyright 0；foundation/core/formal/temporal machine reports分别6/6、6/6、6/6、7/7 PASS，temporal报告含4个C-ID、5 candidate、3 infeasible、2 precheck、4 Validator mutation与8 oracle cases。治理为142 docs且Task diff 53 paths/6 rows/19 checks/0 issues，Compose、build、`git diff --check`与禁止路径diff均PASS。

Implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`的GitHub run `32432482739` / required `validate` job `96626844156` / artifact `9429579311`均success；artifact digest=`sha256:3d1dce2dad986669d5709d7f8cf3900287773863cdda430e791e007495d5259c`，expiry=`2026-11-19T00:23:37Z`。Temporal/core/formal/Task reports均绑定该SHA并分别为7/7、6/6、6/6及53 committed/0 working/6 rows/19 checks/0 issues。TASK-P2-06=`done`；current phase仍为P2，TASK-P2-07的启动来自新的明确授权。

## TASK-P2-07 启动边界

用户于2026-08-21明确授权执行TASK-P2-07。启动复核确认`main=origin/main=33cc3282ead23a4cc1bb214190191e116b095119`、working tree clean，且该SHA的GitHub run `32432843343` / required `validate` job/check `96627943272`（app `15368`）/ artifact `9429703054`精确成功，artifact digest=`sha256:de371e743b27881ea7901e1252a2c3465256d797e54736e95cf225e05eef065c`、expiry=`2026-11-19T00:29:15Z`。P2-06 implementation是该基线祖先；Problem/Policy/Solution Schema、constraint-rule-sheet、formal Validator、Problem builder/hash、OR-Tools pin与`uv.lock`全部冻结。

本Task只把C-007/008加入现有bounded CP-SAT模型：COMPLETED继续不生成未来assignment且historical anchor仍可参与lag；RUNNING固定已分配资源，并从horizon start按`ceil(remaining_seconds/tick_seconds)`占用未来区间；HARD lock精确固定resource/start/end；SOFT lock只保留metadata/reference，不作为硬约束或hint。事实/lock自相矛盾必须在model build前稳定拒绝，真实constraint冲突才返回certified INFEASIBLE。OBJ-001搜索、Strategy、动态Replan、Benchmark threshold、DB/API/Worker和P3均不在范围；native OPTIMAL仍只映射为业务FEASIBLE，UNKNOWN不得改写为INFEASIBLE。P2-08及以后保持`planned`且未获授权。

## TASK-P2-07 本地实现边界

Fact/lock builder现已组合进bounded CP-SAT model并由formal Validator独立复验。Mapper稳定输出Problem中可追溯的全部lock references；Problem v2没有暴露active RUNNING execution fact ID，因此不得猜造，`execution_fact_ids`保持空集合，而actual/resource/remaining仍由Problem hash与model evidence保存。

本地验收为focused `93 passed`、full repository `382 passed`、Ruff/Pyright 0；foundation/core/formal machine reports各6/6、temporal/fact-lock各7/7 PASS。治理为142 docs且Task diff 54 paths/6 rows/19 checks/0 issues，Compose、build、`git diff --check`与禁止路径diff均PASS。Exact implementation SHA的required `validate`及artifact复核仍是关闭门，完成前TASK-P2-07保持`in_progress`且P2-08不启动。

## TASK-P2-07 执行结果

Implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的GitHub run `32435395744` / required `validate` job/check `96635463577`（app `15368`）均success；artifact `9430579117`未过期，digest=`sha256:a6b6ff7413b8010a8012ddd351a2a194b89b1a13cdf71c6dada5d6afa53a44ab`、expiry=`2026-11-19T01:11:01Z`。Foundation/core/formal/temporal/fact-lock及Task reports全部绑定该SHA，分别为6/6、6/6、6/6、7/7、7/7及54 committed/0 working/6 rows/19 checks/0 issues。TASK-P2-07=`done`；current phase仍为P2，P2-08保持`planned`且未获启动授权。

## TASK-P2-08 启动边界

用户于2026-08-21明确授权执行TASK-P2-08。启动复核确认`main=origin/main=9c55df993b12ae0bdd3d4d38c900d601324c05d2`、working tree clean，且该SHA的GitHub run `32435755901` / required `validate` job/check `96636509174`（app `15368`）/ artifact `9430697910`精确成功；artifact digest=`sha256:6fd173b5cdb6cdae4d5f86bbdee773b8ca7679db34d90d52c4db05d5ca18d8c4`、expiry=`2026-11-19T01:17:08Z`。P2-07 implementation是该基线祖先；Problem/Policy/Solution/Report Schema、formal Validator、Problem builder/hash、C-ID formulas、OR-Tools pin与`uv.lock`全部冻结。

本Task只在完整C-001～C-011硬可行域内实现单一OBJ-001 weighted tardiness、唯一`GlobalCpSatStrategy`、显式Simulation Policy/SolveLimits、honest OPTIMAL/FEASIBLE/UNKNOWN及完整SolverReport/machine evidence。OBJ-002/003、Production policy/default、Reference Scheduler、BenchmarkRunner、Export、DB/API/Worker、P3/P4均禁止；OPEN-006/011/012保持OPEN。P2-09～14继续`planned`且未获授权。

## TASK-P2-08 本地实现边界

`POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`现以source `plantnexus-synthetic-policy@1.0.0`和显式SolveLimits保护Simulation-only入口；GlobalCpSatStrategy对完整Problem只调用一次Backend，OBJ-001严格计算`sum(priority_weight × max(0, demand_completion_seconds - due_offset_seconds))`，支持非tick-grid due offset且先执行int64域检查。Candidate仅在native OPTIMAL/FEASIBLE且formal independent Validator PASS后保留；UNKNOWN不冒充INFEASIBLE、FEASIBLE不冒充OPTIMAL，validator失败映射FAILED并丢弃assignment/objective。

本地focused=`70 passed`、full repository=`395 passed`，Ruff/Pyright均0问题；`objective-strategy-report.v1`为7/7 PASS，覆盖4个tiny brute-force optimum、4次independent Validator PASS、1个certified infeasible、7种status及Production rejection。全部历史machine reports、142-doc治理、52 paths/8 rows/19 checks/0 issues、Compose、build、`git diff --check`与冻结边界均PASS。Exact implementation provider仍需在push后闭环，因此TASK-P2-08保持`in_progress`；P2-09～14仍未授权，P2不进入P3。

## TASK-P2-08 执行结果

Implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的GitHub run `32438785162` / required `validate` job/check `96645152864`（app `15368`）全部success；artifact `9431673977`未过期，digest=`sha256:843c036ffa3e133a9bceee1ca3b3320ce42a790cc955f01e94acab135f8fab5d`、expiry=`2026-11-19T02:08:20Z`。下载复核确认14份validation report全部PASS，objective/strategy为7/7，Task report为52 committed/0 working paths、8 rows、19 checks、0 issues且均绑定同一SHA。因此TASK-P2-08=`done`；current phase保持P2，P2-09～14未获授权且不会自动启动，P3仍禁止。

## TASK-P2-09 启动边界

用户于2026-08-21明确授权执行TASK-P2-09。启动复核确认`main=origin/main=15c298f343a47db2a922544944ff5e02e4ca72d9`、working tree clean，P2-08 implementation位于祖先链；该SHA的run `32439301758` / required `validate` job `96646617379`（app `15368`）/ artifact `9431840946`均精确success，artifact digest=`sha256:b7de66a574d81ce959bbaf290b3b0d80e67fdb72460e8d4a1cf2989d219f6974`、expiry=`2026-11-19T02:16:54Z`。Diff base据此冻结；P0/P1三组既有fixture逐文件清单摘要固定为`sha256:cab42c498ad74607d8e7bb172b6daf3f320626eb0e08b2d155e1b31cb8b45df4`。

本Task只新增Golden JSSP/FJSP及Cross Workshop、Calendar、Material Delay、Running、Hard Lock七类`1.0.0` correctness assets，使用`PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`逐例走Raw Staging→Normalization/Import v2→Data Validation→Expansion→Snapshot v2→Problem v2→approved OBJ-001 Global Strategy→formal Validator，并形成formula-free C-001～C-011 mutations、deterministic/property replay和CI machine report。Scenario/Profile published Schema、Planning/Application/Generator、Problem/Solver/Validator/C-ID/Objective、dependency/lock、Benchmark/Reference/Export、DB/API/Worker和P3+均冻结；P2-10～14未启动。

## TASK-P2-09 本地实现边界

七个versioned case均已从source-shaped Raw rows进入正式pipeline并取得OPTIMAL/OBJ-001=0/formal Validator PASS；每例manifest固定Profile/Scenario/blueprint/expected对象hash及Import/Snapshot/Problem hash。两份Golden有手算零目标下界，五例分别覆盖Cross Workshop、Calendar、Material、Running与Hard Lock，合计覆盖C-001～C-011 positive set。

Row-order replay保持全部business artifacts/assignments/report不变；fresh independent Validator property覆盖7例，11个formula-free Solver-candidate mutation各自只命中同名C-ID。Focused=`45 passed`、full=`427 passed`，Ruff/Pyright=0；correctness 8/8及全部历史machine reports、142-doc治理、58 paths/7 rows/19 checks/0 issues、Compose/build/`git diff --check`与冻结边界均PASS。Exact implementation provider尚待push后闭环，故Task保持`in_progress`；P2-10～14/P3未启动。
