---
doc_id: DOC-PHASE-CURRENT
title: 当前阶段
status: living
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [73, 74, 75, 76, 110, 111]
last_reviewed: 2026-08-25
---

# 当前阶段：P3 — Planning Workspace

## 阶段授权与证据

用户于2026-08-24明确批准P2→P3 phase transition，并授权先执行P3 Milestone激活、Task规划与文档治理。切换前重新核验：TASK-P2-00～14全部`done`；[P2 Exit Gate audit](milestones/P2-exit-gate-audit-report.md)与[machine manifest](milestones/P2-exit-gate-evidence-manifest.json)均为overall=`READY`、`blocking_gaps=[]`；13组前序implementation/closure以及P2-14三段提交拓扑均保持祖先关系。

P2-14 audit implementation `65c556789f176ad9de55523d6420737bb60f933f`的GitHub push run `32677741558` / required `validate` job `97288829348` / artifact `9503227240`成功，artifact digest=`sha256:fbb76f0ab44d3bdcff2d31e70f9698af84e10e48ee57ae611eef8529a288240e`；evidence-only closure `80c403384d1e171258cf874d26605d0d22aff1b2`的run `32678248961` / job `97290201234` / artifact `9503372291`也成功，digest=`sha256:673412905b7420660d1e9f07755fcda6291f85f8f2bd926b4bf31a0a6bd1bd0c`。下载检查的两份artifact均含20份可解析JSON，Task/SHA/Impact Rules/checks/issues与对应提交一致且0 issue。规划启动时`main=origin/main=80c403384d1e171258cf874d26605d0d22aff1b2`、ahead/behind=`0/0`且working tree clean，因此transition前提一致。

P2 Milestone现为`completed`，P3 Milestone为`active`。`TASK-P3-00`～`TASK-P3-06`均已由exact implementation provider闭环并在evidence-only closure标为`done`；用户于2026-08-25单独授权`TASK-P3-07`，当前仅该Task为`in_progress`，P3-08～15保持`planned`且未获授权，不会自动启动。

## 当前目标

在保持P2求解与Validator闭环只读的前提下，建立唯一受支持的P3计划工作区链：

```text
validated PlanningSolution
→ immutable ScheduleVersion DRAFT
→ workspace read models / comparison
→ command-only Gantt edit and lock
→ server validation + new DRAFT
→ approval / rejection / audit
→ idempotent publish / supersession
→ ExportJob + standard export package
→ HTTP API + Planning Workspace UI
```

P3 Gate要求DRAFT/REJECTED不可发布、只有APPROVED可发布、PUBLISHED immutable、export idempotent；Gantt编辑必须走UI Command→Server Validation→New Draft→formal Validator，不得直接更新published schedule。权限先采用authority-neutral capability与default-deny边界，OPEN-010关闭前不声明真实审批责任或Production publish authority。

## 当前Task与启动边界

`TASK-P3-00`以不可变Diff base `80c403384d1e171258cf874d26605d0d22aff1b2`完成phase transition、完整Task规划和治理注册表同步；implementation `1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7`的run `32681493976` / required job `97298850740` / artifact `9504310381`成功，下载的20份JSON全部PASS，Task report为64 committed/0 working paths、4 rows、19 checks、0 issues。

`TASK-P3-01 — Planning Workspace Contract and ADR Baseline`从clean、synchronized、provider-verified HEAD `7f65f88b620ea1e8d2f4693911be3b52f4052d5d`启动并固定为不可变Diff base。Implementation `3bf99cbafdad983795a83a88646240dbb0b24509`的required run/job/artifact=`32684713630`/`97307562801`/`9505303054`成功；artifact未过期，20份JSON全部可解析并PASS，Task report精确复现43 committed/0 working paths、4 rows、19 checks和0 issues。因此本evidence-only closure把P3-01标为`done`，但不启动P3-02。

## TASK-P3-02 已完成边界

TASK-P3-02从clean、synchronized且P3-01 closure provider-verified的`a8fcec3383ea0f8d9dca4101056aff37d7eea08c`启动。启动冻结schema set`2.5.0`下21份既有Schema+13份sample的清单摘要`sha256:76bb8ae4…73723`及`uv.lock`摘要`sha256:8b13617f…87a82`；只允许additive `2.6.0`七份Workspace carrier、synthetic samples、pure precheck/machine report、CI step、tests与命中文档。

七份strict Schema/URN、七份sample、canonical fingerprints、24个Schema negative、6个fingerprint negative和8/8 machine checks已经形成；P2 bytes、state pair、global error registry、dependency/lock保持不变。Implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a`的run/job/artifact=`32689832111`/`97321420908`/`9506913562`精确复现21/21 JSON PASS、65 committed/0 working paths、10 rows、19 checks和0 issues，故本closure把Task标为`done`；P3-03不启动。

## TASK-P3-03 已完成边界

TASK-P3-03从clean、synchronized且P3-02 closure provider-verified的`9621fda535f66393beab88efc13c100fc805c993`启动并冻结为不可变Diff base。P3-02 closure run/job/artifact=`32690302424`/`97322642627`/`9507045338`精确成功；启动门定向migration/Snapshot回归12 passed。当前只允许`0004`可逆migration、plane-scoped ScheduleVersion/Audit/Publication/ExportJob repositories、既有pair的CAS/lease/transaction原语、限定tests/machine evidence与命中文档；业务审批、发布、导出、API/UI/Celery task和P3-04+仍禁止。

本地实现已形成5张表、四类repository与`p3-persistence-report.v1` 8/8 checks；36项focused与503项全仓测试、Ruff、Pyright、全部既有machine contracts、P2 Gate、XS benchmark、Compose、build及治理均PASS。Implementation `e315dbf4f6c079df6d19b52f0403b00827126232`的run/job/artifact=`32694644036`/`97334382152`/`9508445635`精确复现22/22 JSON PASS、52 committed/0 working paths、7 rows、19 checks和0 issues，故本closure把Task标为`done`；P3-04不启动。

## TASK-P3-04 已完成边界

TASK-P3-04从clean、synchronized且P3-03 closure provider-verified的`62604d05964413a0aa7f763afd720afa2d53a887`启动并冻结为不可变Diff base。P3-03 closure run/job/artifact=`32695127644`/`97335699708`/`9508601189`精确成功，下载artifact为22/22 JSON PASS、52 committed/0 working paths、7 rows、19 checks、0 issues；启动复核还确认固定P2 Snapshot→Problem→Solution→SolverReport→fresh ValidationReport→KPI lineage可重放。

本Task只形成validated P2 output→immutable DRAFT→`READY_FOR_REVIEW`的原子application/domain生命周期、同事务audit、幂等/冲突/隔离行为、限定tests与machine evidence。PlanningRun必须由调用者显式证明`COMPLETED`且不会被本服务修改；服务不调用Solver、不改Validator公式，不形成approve/reject/publish/export、HTTP/UI、P4或Production authority。workflow只新增machine evidence命令，required `validate`名称、权限、Secret、service/deployment保持不变。

## TASK-P3-04 本地实现边界

当前实现已形成fresh Validation/KPI/lineage前置Gate、deterministic immutable DRAFT、同事务CAS `DRAFT→READY_FOR_REVIEW`与append-only audit，以及same-request replay、conflict/rollback/concurrency/plane isolation。核心application只依赖repository ports与transaction factory；SQLAlchemy adapter仅由composition root装配，生命周期service不调用Solver，也不写PlanningRun。

本地35项定向与515项全仓测试、Ruff、Pyright、8/8 lifecycle report、全部既有machine contracts、P2 Gate、XS benchmark、Compose、build与治理均PASS；Task diff为45 paths、8 rows、19 checks、0 issues。Implementation `a9be974855bb825784d639b7f6675e5a33e4273d`的run/job/artifact=`32700005280`/`97349447107`/`9510215582`精确复现23/23 JSON PASS、lifecycle 8/8及45 committed/0 working paths、8 rows、19 checks、0 issues，故本closure把TASK-P3-04标为`done`。READY_FOR_REVIEW不等于approval/publish；该closure发生时P3-05～15、P4和Production均未启动。

## TASK-P3-05 启动边界

用户于2026-08-24单独授权TASK-P3-05。该Task从clean、synchronized且P3-04 closure provider-verified的`fc5011f78a242160097521259a1914d864d9ad17`启动并冻结为不可变Diff base；closure run/job/artifact=`32700684160`/`97351382226`/`9510431988`，required `validate`来自GitHub Actions app `15368`且success，artifact未过期、23/23 JSON PASS、lifecycle 8/8、Task 45 committed/0 working paths、8 rows、19 checks、0 issues。启动时本地重新确认一个synthetic ScheduleVersion为`READY_FOR_REVIEW`且exact replay成立。

本地实现覆盖14种read view、strict carrier+complete payload fingerprint、stable filter/sort/cursor、found-empty/missing/stale/plane/tamper、Resource Load/KPI及two-Version comparison；8/8 machine、33项定向及527项全仓测试PASS，locked sync/Ruff/Pyright/Compose/build/full+diff治理/禁止范围均通过，read前后durable rows不变且product-service Solver调用0。

Implementation `f236fab47aa2565b87a060b2c8bde8f2e8d66229`的run/job/artifact=`32706258281`/`97367902547`/`9512423712`精确success；下载的24/24 JSON全部PASS，read-model报告为8/8且Task报告为50 committed/0 working paths、7 rows、19 checks、0 issues。因此本closure把TASK-P3-05标为`done`，P3 Milestone保持`active`。其closure `67d38d030f8b129de7f1b2f6e5b75bd706655396`的run/job/artifact=`32707242260`/`97370830393`/`9512779675`也精确success；用户随后明确授权TASK-P3-06，当前仅该Task为`in_progress`。

TASK-P3-06完成的有界slice仅包含Move/Assign/Set/Remove Lock content command、server semantic validation、copy-on-write新DRAFT、每次非replay fresh formal Validator、显式`SUBMIT_FOR_REVIEW` second-fresh与既有DRAFT→READY同content CAS、atomic append-only audit、限定tests/machine CI和命中文档。它不调用Solver、不改Problem/Snapshot、不原地修改content command source，也不形成HTTP/UI/approval/reject/publish/export或P4 ChangeReport/Replan；P3-07～15和Production authority均未启动。

本地实现形成5种command（4 content + 1 submit）、fresh Validator、insert/CAS两类原子audit、exact replay/conflict、历史Version与失败无副作用边界；focused=`41 passed`、full repository=`546 passed`、Ruff/Pyright/locked sync均PASS。Command machine为8/8、5 fresh passes、2 exact replay、1 conflict、6个无副作用拒绝、Solver调用0、`issues=[]`；全部历史machine、P2 Gate 11/11、XS benchmark、Compose、build及治理也PASS。

Implementation `08317637c7fbb51d46880d32523545bb0b4fe1c0`的run/job/artifact=`32713635045`/`97390177509`/`9515126567`精确success；下载的25/25 JSON全部PASS，command报告为8/8且Task报告为57 committed/0 working paths、8 rows、19 checks、0 issues。因此本closure把TASK-P3-06标为`done`，P3 Milestone保持`active`。

## TASK-P3-07 启动边界

用户于2026-08-25单独授权TASK-P3-07。启动复核确认TASK-P3-03/04均`done`，且直接前序治理closure `514224b8ff2d507b613797ae697245bab14f79eb`的required run/job/artifact=`32714501727`/`97392773902`/`9515436874`精确success；下载artifact为25/25 JSON PASS、57 committed/0 working paths、8 Impact rows、19 checks、0 issues。启动时`main=origin/main=514224b8ff2d507b613797ae697245bab14f79eb`、ahead/behind=`0/0`且working tree clean，故该完整SHA已冻结为不可变Diff base。

当前只允许authority-neutral capability、sanitized actor/reason、READY_FOR_REVIEW→APPROVED/REJECTED、exact replay/conflict/CAS、同事务append-only audit、Simulation测试策略、Production default-deny、限定tests/machine CI和命中文档。不得定义真实RBAC/SSO或Production审批责任，不得实现publish/export、HTTP/UI、Schema/migration/dependency、Solver/Validator改动、P4或Production readiness；OPEN-010保持`OPEN`。

## TASK-P3-07 本地实现边界

当前实现形成strict APPROVE/REJECT carrier、server-derived authority context、sanitized actor/reason、authorization-before-source/replay lookup、Production pre-lookup default-deny、READY_FOR_REVIEW同content CAS、atomic append-only success/DENIED audit、exact replay/conflict及并发单winner。聚焦39项与全仓562项测试、Ruff/Pyright/locked sync、8/8 decision machine、全部既有machine、P2 Gate 11/11、XS benchmark、Compose、build及治理均PASS；Task报告为50 working paths、8 rows、19 checks、0 issues。

这些仍是本地证据：exact implementation required `validate`/artifact及evidence-only closure未形成前TASK-P3-07保持`in_progress`。OPEN-010继续`OPEN`；真实RBAC/SSO、HTTP/UI、publish/export、P3-08+、P4与Production authority/readiness均未形成。

初始implementation `3f85959e91e74966f6482426b9db296a45d715ef`的run/job=`32793980039`/`97641324105`在Linux tests因machine report使用SQLite `BLOB LIKE`产生跨平台0-count而失败（`1 failed, 556 passed`），且未生成artifact；该失败事实保留。修正仅把统计改为canonical JSON解析，并将新增security目录纳入required suite；本地exact suite重新为562 PASS、8/8 report的success/denial counts为3/3。修正provider成功前仍不允许closure或P3-08。

## 当前允许

- 读取并复核P3-01～06合同、Schema、persistence/lifecycle/read/command provider evidence和P2 frozen artifact；
- 只执行TASK-P3-07卡中固定allow-list内的approval/rejection/audit service、限定tests/machine CI与命中文档；
- 后续P3-08～15只有在逐Task明确授权后，才可按各卡允许范围和新的不可变Diff base实施。

## 当前禁止

- 在没有新Task授权时修改业务代码、migration、Schema、dependency/lock、P2 fixture/benchmark bytes、`frontend/**`、API/Worker或deployment；
- 执行P3-08～15，或让其中任何Task自动进入`ready/in_progress`；
- 直接更新PUBLISHED、绕过server/formal Validator、允许DRAFT/REJECTED发布或产生非幂等export/publish；
- 实现P4的ExecutionEvent、ReplanRequest、OBJ-002 Stability、freeze window、ChangeReport或Execution Simulator；
- 创建P4详细Task、进入P4，或声明Production readiness、approval authority、external publish/deployment已形成；
- 改写P2历史audit、失败记录、provider evidence、Simulation假设或阶段边界。

## TASK-P3-01 闭环合同边界

页面/路由/read model见[`frontend/planning-workspace.md`](frontend/planning-workspace.md)，编辑/lock见[`frontend/gantt-command-contract.md`](frontend/gantt-command-contract.md)，人工批准/发布/导出见[`frontend/approval-publication-flow.md`](frontend/approval-publication-flow.md)；HTTP payload/error和capability/audit分别由[`contracts/planning-workspace-api.md`](contracts/planning-workspace-api.md)与[`contracts/authorization-and-audit.md`](contracts/authorization-and-audit.md)固定。ADR-0012接受copy-on-write new DRAFT、server authority、既有state pair、Production default-deny、approved-only internal publish、Publish/Export分离、append-only audit及React/TypeScript/npm/Vite/Vitest/Playwright组合。

这些是contract-only事实：schema set继续`2.5.0`，`state-machines.v1`不变，所有P3机器carrier、persistence、application/API/UI/E2E行为仍为`PLANNED`；OPEN-002/010/015保持OPEN，P4/Production边界不变。

## 阶段完成条件

- ScheduleVersion、Comparison、Gantt/Resource Load/Order View、Lock、Approval/Reject/Publish、ExportJob、Audit、HTTP API与UI按P3卡片闭环；
- DRAFT/REJECTED publish拒绝、APPROVED-only publish、PUBLISHED immutability、new-DRAFT edit和idempotent export均有contract/integration/E2E证据；
- P3-14形成完整vertical-slice Gate evidence；最后独立执行P3-15 Exit Gate Audit；
- P3-15 report/manifest必须给出真实overall和`blocking_gaps`，并由exact GitHub required `validate`和artifact复验；
- 即使P3-15=`READY`，也必须等待用户再次明确批准才允许P3→P4 transition。

失败时保持P3；实现缺口只能进入有界P3 remediation Task，P3-15本身不得修实现。P3 Task完成、Gate READY或内部Simulation publish都不构成Production readiness/approval/publish声明。

## P2 阶段历史

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

Row-order replay保持全部business artifacts/assignments/report不变；fresh independent Validator property覆盖7例，11个formula-free Solver-candidate mutation各自只命中同名C-ID。Focused=`45 passed`、full=`427 passed`，Ruff/Pyright=0；correctness 8/8及全部历史machine reports、142-doc治理、58 paths/7 rows/19 checks/0 issues、Compose/build/`git diff --check`与冻结边界均PASS。

## TASK-P2-09 执行结果

Implementation `20e49c92306128b47313059fabe31534814dbe3d`的GitHub push run `32442651322`（attempt 1）/ required `validate` job/check `96656224252`（GitHub Actions app `15368`）全部success；branch protection仍精确要求`validate`/app `15368`。Artifact `9432982306`（33761 bytes）未过期，digest=`sha256:c736a2f029f119850f8a0c9b40b0dbbd0898383f10ddbc798f7182ff5ec90e09`、expiry=`2026-11-19T03:14:03Z`。

下载复核16份JSON全部PASS；`ci-p2-correctness.json`绑定implementation SHA并为8/8、7 scenarios/Validator/property、11 mutations及C-001～C-011正负覆盖；`ci-current-task-report.json`绑定同一SHA/Diff base并为58 committed/0 working paths、7 rows、19 checks、0 issues。因此TASK-P2-09=`done`，current phase仍为P2；P2-10～14未获授权，P3仍禁止。

## TASK-P2-10 启动边界

用户于2026-08-21明确授权执行TASK-P2-10。启动复核确认`main=origin/main=0e4f6630412889254a7bef41f487c24dc274ca9c`且working tree clean，P2-09 implementation位于祖先链；该SHA的run `32443067388` / required `validate` job `96657446617`（app `15368`）/ artifact `9433118755`均精确success，artifact digest=`sha256:f258604cd24d9c68f66f2b9b20b23d438014d46d4e746dfe04f3231686179f10`、expiry=`2026-11-19T03:21:06Z`。下载复核16/16 JSON均PASS，Task报告为58 committed/0 working paths、7 rows、19 checks、0 issues；Diff base据此冻结。

本Task只实现FCFS、EDD、SPT、Priority+EDD和Greedy Earliest Available Machine五个versioned deterministic non-production baseline；输入复用七个P2-09 Problem，输出必须是完整candidate或明确`HEURISTIC_FAILURE`，并由fresh formal Validator与相同weighted tardiness/makespan/runtime口径复验。Planning/Solver/Validator语义、Schema、P2-09 assets、dependency/lock、BenchmarkRunner/XS-S-M/threshold、Production fallback、P2-11～14及P3全部冻结；current phase保持P2。

## TASK-P2-10 本地实现边界

`reference-scheduler-contracts.v1`、`reference-scheduler-policy.v1`与五个`reference-*.v1` identity已形成；共享deterministic hard-feasibility helper覆盖C-001～C-011候选构造，成功必须complete且fresh Validator PASS，失败只返回`HEURISTIC_FAILURE`并丢弃partial state。七Problem×五算法形成35个candidate/Validator/replay，5个blocked-calendar failure不声明INFEASIBLE；report同口径记录weighted tardiness、makespan和runtime且显式non-production/no-optimality。

Task-specific=`13 passed`、full repository=`441 passed`，Ruff/Pyright均0问题，reference machine report=`7/7 PASS`。Schema、Planning/Validator、P2-09 assets、dependency/lock、Benchmark/Export/API/DB/Worker禁止路径保持零差异。

## TASK-P2-10 执行结果

Implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`的GitHub push run `32449742281`（attempt 1）/ required `validate` job/check `96675839685`（GitHub Actions app `15368`）全部success；branch protection仍精确要求`validate`/app `15368`。Artifact `9435264655`（37194 bytes）未过期，digest=`sha256:db250a86929c7e2c50ef0c24a2cbf74940a7b244e5d9499e42e087f4cd94c784`、expiry=`2026-11-19T05:13:14Z`。

下载复核17份JSON全部PASS；`ci-reference-schedulers.json`绑定implementation SHA并为7/7、5 algorithms、7 scenarios、35 complete candidates/Validator passes/deterministic replays及5 heuristic failures；`ci-current-task-report.json`绑定同一SHA/Diff base并为38 committed/0 working paths、6 rows、19 checks、0 issues。因此TASK-P2-10=`done`，current phase仍为P2；P2-11～14未获授权，P3仍禁止。

## TASK-P2-11 启动边界

用户于2026-08-21明确授权执行TASK-P2-11。启动复核确认`main=origin/main=41e958b771f2664b1ac50867903a30b73627878d`且working tree clean，P2-10 implementation为直接父提交；该SHA的run `32450216908` / required `validate` job `96677202782`（app `15368`）/ artifact `9435421360`均精确success，artifact digest=`sha256:f38a8deb00610bd98a43dca3f9a6c12ae936aec127787db9f24b5b84a0fe9b01`、expiry=`2026-11-19T05:20:58Z`。下载复核17/17 JSON均PASS，Task报告为38 committed/0 working paths、6 rows、19 checks、0 issues；Diff base据此冻结。

本Task只形成additive schema set `2.5.0`的KPI v2/export-manifest v1、同一validated solution的deterministic KPI与SolverReport冻结，以及`p2-internal-export.v1`纯内存/原子目录包。既有Planning/Solver/Validator/Scenario语义与artifact bytes、`uv.lock`、ChangeReport/dynamic Replan、BenchmarkRunner/XS-S-M/threshold、ScheduleVersion/ExportJob状态与持久化、approval/publish/API/DB/Worker/external transfer及P3均冻结；current phase保持P2，P2-12～14不会自动启动。

## TASK-P2-11 本地实现边界

当前本地实现已从P2-09首个validated synthetic replay生成immutable KPI与10文件目录（`manifest.json`加9个payload）。KPI独立复算逐订单交付、OBJ-001、makespan、完整排程计数与calendar-denominator resource utilization；无base ScheduleVersion时Stability固定为`NOT_APPLICABLE_NO_BASE_SCHEDULE`。SolverReport保持真实`SOLVER_RUN`字节，不用样例或重写timing代替。

Package verifier重新校验全部canonical JSON、manifest/package/KPI identity、每文件hash/size/CSV row count、同一planning run和Problem/Snapshot/Solution/Validation/Solver/Quality lineage、fresh SolverReport binding以及synthetic provenance。目录写入使用同父目录临时目录、manifest last和原子rename；exact replay幂等，冲突和partial I/O均稳定拒绝且不留下成功目录。指定验收49项、全仓455项、Ruff/Pyright及machine report 8/8均PASS；全部历史machine reports、Compose、build、schema metadata、immutable/forbidden-path与`git diff --check`也均PASS。

## TASK-P2-11 执行结果

Implementation `546292831c3bd52185687a4c646c10ae10541ae2`的GitHub push run `32454693799`（attempt 1）/ required `validate` job/check `96689627030`（GitHub Actions app `15368`）全部success；branch protection仍精确要求`validate`/app `15368`。Artifact `9436863185`（41084 bytes）未过期，digest=`sha256:77dfadb425f1c3f47d21494127785c81357351aeee6ecbdd4f00386516db054b`、expiry=`2026-11-19T06:30:51Z`。

下载复核18份JSON全部PASS；`ci-p2-output-contracts.json`绑定implementation SHA并为8/8、9 package payloads、2 deterministic replays及3 rejection cases；`ci-current-task-report.json`绑定同一SHA/Diff base并为58 committed/0 working paths、11 rows、19 checks、0 issues。因此TASK-P2-11=`done`，current phase仍为P2；P2-12～14未获授权，P3仍禁止。

## TASK-P2-12 启动边界

用户于2026-08-21明确授权执行TASK-P2-12。启动复核确认`main=origin/main=58db14e8f18fb50866fb757d4c89e76fef1141f1`且working tree clean，P2-11 implementation位于祖先链；该SHA的run `32455399561` / required `validate` job/check `96691604529`（app `15368`）/ artifact `9437086153`均精确success，artifact digest=`sha256:1da721655426224cf9dae4f3ee9cc16c4fbe1433e4c601ace3aef61f32f91156`、expiry=`2026-11-19T06:41:15Z`。下载复核18/18 JSON全部PASS，P2-11 output为8/8，Task报告为58 committed/0 working paths、11 rows、19 checks、0 issues；Diff base据此冻结。

本Task只形成strict internal Benchmark Profile/Report/Baseline v1、versioned deterministic XS/S/M输入、相同Problem/formal Validator/schedule KPI上的Global与五Reference比较、环境/规模/时间/质量/内存采集、local CLI与PR XS artifact。Global schema set保持`2.5.0`；Reporting只允许抽取不改变KPI v2/Export字节的公共pure calculation。P2-09 assets、P2-10算法、P2-11 exporter、Planning/Strategy/Backend/Validator语义、dependency/lock、L/XL、Production capacity/SLA、P2-13/14与P3全部冻结；current phase保持P2。

## TASK-P2-12 本地实现边界

`benchmark-profile-set.v1`固定XS/S/M为8/24/48 operations、3/6/8 resources、1/2/4 calendar fragments、60秒tick、显式seed与1 warm-up + 3 measured runs；三个immutable v1 baseline绑定Problem hashes `a70a0549…7b04`、`42ee217e…5bb4`、`a49ee150…26aa`。Runner对每个profile经正式source-shaped Raw→Import→Quality→Expansion→Snapshot→Problem链生成一次verified replay，再在同一Problem运行Global和五Reference；所有candidate均fresh formal PASS，并用`calculate_schedule_kpi_metrics`公共pure函数交叉KPI v2/P2-10 metric carrier。

本地27项指定测试与full repository `466 passed`，Ruff/Pyright为0问题，XS/S/M三份`benchmark-report.v1`各8/8 checks且无warning，P2-11 output 8/8及全部历史machine reports保持PASS。142-doc full治理与Task diff为49 paths/7 rows/19 checks/0 issues，Compose、build、`git diff --check`和冻结禁止路径均PASS；CI已把deferred hook改为required XS并上传benchmark JSON。以上只形成development/simulation baseline，不关闭OPEN-011/012或完整Gate A。

## TASK-P2-12 执行结果

Implementation `01e7f4bdca88fc903e7caa771f875fc1a70ff357`的GitHub push run `32460861563` / required `validate` job/check `96707353990`（app `15368`）全部success；artifact `9438899443`（45692 bytes）未过期，digest=`sha256:caeb61fbbbd100c301725073398410e50e4b79f979f0b72df08d32a28fc2874e`、expiry=`2026-11-19T07:56:26Z`。Branch protection仍精确要求`validate`/app `15368`。

下载复核19/19 JSON全部PASS；`benchmarks/ci-xs.json`绑定implementation SHA并为8/8、0 warning及固定XS Problem hash，`ci-current-task-report.json`绑定同一SHA/Diff base并为49 committed/0 working paths、7 rows、19 checks、0 issues。因此TASK-P2-12=`done`，current phase仍为P2；P2-13/14未获授权，P3仍禁止，L/XL与Production capacity/SLA保持未形成。

## TASK-P2-13 启动边界

用户于2026-08-21明确授权执行TASK-P2-13。启动复核确认`main=origin/main=59f3b013a4be7bd11d054e8464886b3cde791602`且working tree clean，P2-01～12均`done`，十二个implementation均位于当前HEAD祖先链且各自exact required `validate` / artifact可取；closure HEAD的run `32461665177` / required `validate` job/check `96709654227`（app `15368`）/ artifact `9439159396`均success，artifact digest=`sha256:007e7a3107d06d7d629f519a87a7e8e0c54143863d422413664d857659e38cb1`且未过期。Diff base据此冻结。

本Task只编排Snapshot→Problem→Policy/Limits→Global CP-SAT→independent Validator→KPI/SolverReport→internal Export公开边界，至少两次完整replay七类correctness与XS/S/M，形成versioned Gate report、四类unsupported/invalid/limit拒绝、CI exact artifact及blocking gap列表。既有Solver/Validator/合同/fixture/benchmark只读；任何失败诚实返回FAIL且不在本Task修复。P2-14 Exit Gate Audit、P3及Production readiness全部禁止，current phase保持P2。

## TASK-P2-13 本地实现边界

`p2-vertical-slice-report.v1`现执行两次完整`correctness → XS → S → M → output`顺序链；每次保存全部sub-report、timing/memory/hash/export证据，并由`p2-gate-semantic-projection.v1`仅排除运行时噪声及其派生identity后比较业务语义。聚焦测试`30 passed`、全仓`476 passed`；Gate为11/11 PASS、14次correctness场景、6次benchmark profile、108次benchmark Validator PASS、4类exact rejection与0 blocking gap。

本地PASS不等于required provider或Exit结论。当前`Exit Gate Audit=NOT_PERFORMED`、P2-14/P3=`NOT_STARTED`、Production readiness=`NOT_CLAIMED`；implementation exact required `validate` / artifact闭环前TASK-P2-13保持`in_progress`，P2 Milestone保持`active`。

## TASK-P2-13 执行结果

Implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的GitHub push run [`32465737712`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32465737712)（attempt 1）/ required `validate` job/check `96721819879`（GitHub Actions app `15368`）全部success；branch protection仍精确要求`validate`/app `15368`。Artifact `9440650646`（`plantnexus-ci-evidence-32465737712`，86029 bytes）未过期，digest=`sha256:35e67191d1026169d9acd2a64f50e93bd8d2704df9f8ba1a2297f2dd2a00ca4d`、expiry=`2026-11-19T08:59:32Z`。

下载复核20/20 JSON全部PASS；Gate及每个correctness/XS/S/M/export sub-report均绑定implementation SHA，Gate为11/11、两次replay、14 scenarios、108 Benchmark Validator passes、4 rejections、0 gaps且Exit=`NOT_PERFORMED`。Task报告绑定同一SHA/Diff base并为37 committed/0 working paths、6 rows、19 checks、0 issues。因此TASK-P2-13=`done`，current phase/P2 Milestone仍为P2/`active`；P2-14保持`planned`且未授权，P3禁止。

## TASK-P2-14 启动边界

用户于2026-08-24明确授权执行TASK-P2-14。启动复核确认`main=origin/main=e76776d83726d13600d8ea29fd490474c8e32604`且working tree clean，P2-01～13全部`done`。13组Diff base→implementation→closure→当前HEAD祖先检查全部PASS；26个implementation/closure run与required `validate` job均success，26个artifact全部可取且未过期。下载后的364份JSON无解析/顶层失败，26份Task trace report均绑定exact SHA并为PASS/0 issues；closure HEAD的run/job/artifact=`32466635638`/`96724500691`/`9440970310`，digest=`sha256:4a41a54cde5fe0cb349f177769bfff6e17b5820ffbf68c4811c46169a3860890`。Diff base据此冻结。

本Task只独立重跑并审计P2合同、C-001～C-011、OBJ-001、correctness、Reference、Export、XS/S/M、Gate、文档治理与provider证据，形成诚实`READY/NOT_READY`和blocking gaps。不得在audit内修业务代码、Schema、test、baseline或workflow；不得关闭Production开放项、创建P3 Task或自动切换current phase。P2 Milestone在用户另行批准P2→P3前继续为`active`。

## TASK-P2-14 本地审计结论

独立验收已在audit execution head `c6e57566871faefb2582e1c33218e1ba22b44785`完成：locked sync、Ruff、Pyright、476项全仓测试、Compose、build与写回前full/diff治理均PASS；两次P2 Gate为11/11、14次correctness场景、6次XS/S/M profile、108次Benchmark Validator、4类exact rejection且0 blocking gap。为完整满足总规§76，另对七个correctness场景执行两轮逐场景measurement capture，14/14均保存model/build/first-feasible/objective/bound/gap/memory与Validator PASS。三份独立XS/S/M报告均8/8且0 warning。

[P2 Exit audit report](milestones/P2-exit-gate-audit-report.md)与[machine manifest](milestones/P2-exit-gate-evidence-manifest.json)据此给出overall=`READY`、`blocking_gaps=[]`。Audit implementation `65c556789f176ad9de55523d6420737bb60f933f`的exact push run `32677741558`、required `validate` job `97288829348`和artifact `9503227240`均success；artifact内20/20 JSON、30 paths/3 rows/19 checks/0 issues及Gate 11/11全部绑定该SHA，因此TASK-P2-14=`done`。Current phase仍为P2、Milestone仍为`active`（Gate ready / awaiting user decision），P3保持`NOT_STARTED`，必须等待用户另行明确批准P2→P3。
