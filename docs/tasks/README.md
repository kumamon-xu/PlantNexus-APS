---
doc_id: DOC-TASK-INDEX
title: Task Card 索引
status: living
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [2, 6, 73, 74, 75, 76, 98, 99, 100]
last_reviewed: 2026-08-25
---

# Task Card 索引

当前Phase为P3。P0～P2 Task作为terminal历史保留；只有当前P3允许详细Task Card，P4～P7继续只保留Milestone。

## Completed history

- TASK-P0-01～10全部`done`，P0 Milestone=`completed`。
- [TASK-P1-01～12](P1/)全部`done`；[P1 audit](../milestones/P1-exit-gate-audit-report.md)=`READY`且用户已批准transition，P1 Milestone=`completed`。
- [TASK-P2-00～14](P2/)全部`done`；[P2 audit](../milestones/P2-exit-gate-audit-report.md)=`READY`、`blocking_gaps=[]`且用户已批准transition，P2 Milestone=`completed`。历史失败、修复与provider evidence不改写。

## P2 execution order

| Task | 目标 | 依赖 | 状态 |
|---|---|---|---|
| [TASK-P2-00](P2/TASK-P2-00-phase-transition-and-task-planning-governance.md) | Phase transition、Task plan与batch CI治理 | P1-12 | `done` |
| [TASK-P2-01](P2/TASK-P2-01-planning-problem-v2-contract-gap-closure.md) | PlanningProblem v2合同缺口闭环 | P2-00 | `done` |
| [TASK-P2-02](P2/TASK-P2-02-planning-machine-contracts-and-status.md) | Planning机器合同与status | P2-01 | `done` |
| [TASK-P2-03](P2/TASK-P2-03-ortools-backend-foundation.md) | OR-Tools与Backend foundation | P2-02 | `done` |
| [TASK-P2-04](P2/TASK-P2-04-formal-independent-schedule-validator.md) | 正式独立ScheduleValidator | P2-01/02 | `done` |
| [TASK-P2-05](P2/TASK-P2-05-cp-sat-core-assignment-resource-model.md) | CP-SAT core assignment/resource | P2-03/04 | `done` |
| [TASK-P2-06](P2/TASK-P2-06-cp-sat-temporal-calendar-material-model.md) | temporal/calendar/material | P2-05 | `done` |
| [TASK-P2-07](P2/TASK-P2-07-execution-facts-and-hard-lock-model.md) | execution facts/HARD lock | P2-06 | `done` |
| [TASK-P2-08](P2/TASK-P2-08-delivery-objective-and-global-strategy.md) | OBJ-001与Global Strategy | P2-02/05/06/07 | `done` |
| [TASK-P2-09](P2/TASK-P2-09-golden-scenario-property-integration.md) | Golden/scenario/property integration | P2-04～08 | `done` |
| [TASK-P2-10](P2/TASK-P2-10-reference-schedulers.md) | 五个Reference Schedulers | P2-01/02/04 | `done` |
| [TASK-P2-11](P2/TASK-P2-11-kpi-solver-report-and-export-closure.md) | KPI/report/internal Export | P2-08/09 | `done` |
| [TASK-P2-12](P2/TASK-P2-12-benchmark-runner-xs-s-m.md) | BenchmarkRunner与XS/S/M | P2-08～11 | `done` |
| [TASK-P2-13](P2/TASK-P2-13-p2-vertical-slice-gate-evidence.md) | Vertical Slice Gate evidence | P2-01～12 | `done` |
| [TASK-P2-14](P2/TASK-P2-14-p2-exit-gate-audit.md) | P2 Exit Gate Audit | P2-01～13 | `done` |

## P3 execution order

| Task | 目标 | 依赖 | 状态 |
|---|---|---|---|
| [TASK-P3-00](P3/TASK-P3-00-phase-transition-and-task-planning-governance.md) | Phase transition、Task plan与治理同步 | P2-14 | `done` |
| [TASK-P3-01](P3/TASK-P3-01-planning-workspace-contract-and-adr-baseline.md) | Workspace合同与ADR基线 | P3-00 | `done` |
| [TASK-P3-02](P3/TASK-P3-02-schedule-version-workspace-and-export-schemas.md) | Workspace/version/export Schema | P3-01 | `done` |
| [TASK-P3-03](P3/TASK-P3-03-schedule-version-audit-and-export-persistence.md) | Version/audit/export persistence | P3-02 | `done` |
| [TASK-P3-04](P3/TASK-P3-04-validated-solution-to-reviewable-schedule-version.md) | Validated solution→reviewable DRAFT | P3-03 | `done` |
| [TASK-P3-05](P3/TASK-P3-05-planning-workspace-read-models-and-comparison.md) | Workspace read models/comparison | P3-04 | `done` |
| [TASK-P3-06](P3/TASK-P3-06-gantt-edit-and-lock-command-pipeline.md) | Gantt edit/lock command pipeline | P3-04/05 | `done` |
| [TASK-P3-07](P3/TASK-P3-07-approval-rejection-and-audit-service.md) | Approval/rejection/audit service | P3-03/04 | `done` |
| [TASK-P3-08](P3/TASK-P3-08-idempotent-publication-and-supersession.md) | Idempotent publish/supersession | P3-03/07 | `done` |
| [TASK-P3-09](P3/TASK-P3-09-export-job-and-standard-package.md) | ExportJob/standard package | P3-03/04/08 | `done` |
| [TASK-P3-10](P3/TASK-P3-10-planning-workspace-http-api.md) | Planning Workspace HTTP API | P3-05～09 | `done` |
| [TASK-P3-11](P3/TASK-P3-11-frontend-foundation-and-read-only-workspace.md) | Frontend/read-only workspace | P3-01/10 | `in_progress` |
| [TASK-P3-12](P3/TASK-P3-12-gantt-resource-load-and-version-comparison-ui.md) | Gantt/Load/Comparison UI | P3-05/10/11 | `planned` |
| [TASK-P3-13](P3/TASK-P3-13-human-control-actions-and-ui-e2e.md) | Human control actions/UI E2E | P3-06～12 | `planned` |
| [TASK-P3-14](P3/TASK-P3-14-p3-vertical-slice-gate-evidence.md) | P3 vertical-slice Gate evidence | P3-01～13 | `planned` |
| [TASK-P3-15](P3/TASK-P3-15-p3-exit-gate-audit.md) | Independent P3 Exit Gate Audit | P3-14 | `planned` |

用户已于2026-08-24单独授权并完成P3-01/02，随后明确授权执行P3-03。P3-03只形成migration、plane-scoped repositories、既有pair的CAS/lease/transaction原语、CI/tests和治理，不执行审批、发布、导出或P3-04+；P3-15必须最后执行且只审计冻结事实。P3不得实现P4 ExecutionEvent/Replan/OBJ-002/freeze/ChangeReport/Execution Simulator，内部Simulation publish也不构成Production approval/readiness。

TASK-P3-00 implementation `1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7`的run `32681493976` / required job `97298850740` / artifact `9504310381`精确复现64 committed/0 working paths、4 rows、19 checks、0 issues及20/20 JSON PASS；closure `7f65f88b620ea1e8d2f4693911be3b52f4052d5d`的run/job/artifact=`32682015727`/`97300206924`/`9504453154`也成功。P3-01从该clean baseline启动，P3-02～15保持`planned`。

TASK-P3-01 implementation `3bf99cbafdad983795a83a88646240dbb0b24509`的run `32684713630` / required job `97307562801` / artifact `9505303054`精确复现43 committed/0 working paths、4 rows、19 checks、0 issues及20/20 JSON PASS。TASK-P3-02 implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a`的run `32689832111` / required job `97321420908` / artifact `9506913562`精确复现21/21 JSON PASS、65 committed/0 working paths、10 rows、19 checks和0 issues；closure `9621fda535f66393beab88efc13c100fc805c993`的run/job/artifact=`32690302424`/`97322642627`/`9507045338`也精确成功。TASK-P3-03随后从该closure SHA进入`in_progress`并完成有界实现；P3-04未自动启动。

TASK-P3-03已形成`0004`、四类plane-scoped repository、既有pair CAS/lease/transaction原语及8/8 machine evidence。Implementation `e315dbf4f6c079df6d19b52f0403b00827126232`的run/job/artifact=`32694644036`/`97334382152`/`9508445635`精确复现22/22 JSON PASS及52 committed/0 working paths、7 rows、19 checks、0 issues；closure `62604d05964413a0aa7f763afd720afa2d53a887`的run/job/artifact=`32695127644`/`97335699708`/`9508601189`也精确成功。用户随后单独授权TASK-P3-04，其从该closure SHA冻结Diff base并进入`in_progress`；P3-05～15保持`planned`。

TASK-P3-04已形成fresh validated lineage→immutable DRAFT→READY_FOR_REVIEW、原子audit、exact replay/conflict/rollback/concurrency/plane隔离，service Solver调用为0。Implementation `a9be974855bb825784d639b7f6675e5a33e4273d`的run/job/artifact=`32700005280`/`97349447107`/`9510215582`精确复现35 focused、515 full、8/8 machine及45 committed/0 working paths、8 rows、19 checks、0 issues，故索引标为`done`；P3-05～15不自动启动。

用户随后单独授权TASK-P3-05；其从P3-04 provider-verified closure `fc5011f78a242160097521259a1914d864d9ad17`冻结Diff base并进入`in_progress`。当前只允许只读workspace projections、稳定query/cursor、Version Comparison、限定tests/machine CI和命中文档；P3-06～15不自动启动，HTTP/UI、write/state、approval/publish/export、P4和Production保持禁止。

TASK-P3-05已形成14种read view、stable query/cursor、Resource Load/KPI与two-Version comparison。Implementation `f236fab47aa2565b87a060b2c8bde8f2e8d66229`的run/job/artifact=`32706258281`/`97367902547`/`9512423712`精确复现24/24 JSON PASS、machine 8/8及50 committed/0 working paths、7 rows、19 checks、0 issues，故索引标为`done`；P3-06～15不自动启动，HTTP/UI/write/approval/publish/P4/Production仍未形成。

用户现已单独授权TASK-P3-06；其从P3-05 provider-verified closure `67d38d030f8b129de7f1b2f6e5b75bd706655396`冻结Diff base并进入`in_progress`。当前只允许Move/Assign/Set/Remove Lock的server content command、copy-on-write新DRAFT、每次非replay fresh Validator、显式SUBMIT second-fresh与同content READY CAS、atomic audit、限定tests/machine CI和命中文档；P3-07～15不自动启动，Solver、Schema/migration/dependency、HTTP/UI、approval/publish/export、P4与Production authority保持禁止。

TASK-P3-06本地41 focused、546 full、Ruff/Pyright、command machine 8/8、全部历史machine、P2 Gate/XS、Compose/build和57 paths/8 rows/19 checks/0 issues治理均PASS。Implementation `08317637c7fbb51d46880d32523545bb0b4fe1c0`的run/job/artifact=`32713635045`/`97390177509`/`9515126567`精确复现25/25 JSON、8/8 command及同一57 committed/0 working paths治理链，故索引标为`done`。

用户于2026-08-25单独授权TASK-P3-07；其从P3-06 provider-verified closure `514224b8ff2d507b613797ae697245bab14f79eb`冻结Diff base并进入`in_progress`。当前只允许authority-neutral approval/rejection、READY_FOR_REVIEW→APPROVED/REJECTED、atomic append-only audit、exact replay/conflict/CAS、Simulation测试策略、Production default-deny、限定tests/machine CI和命中文档；P3-08～15不自动启动，真实RBAC/SSO、publish/export、HTTP/UI、Schema/migration/dependency、P4与Production authority/readiness保持禁止。

TASK-P3-07已通过39 focused、562 full、Ruff/Pyright、8/8 decision machine、全部历史machine、P2 Gate/XS、Compose/build和50 paths/8 rows/19 checks/0 issues治理；corrective implementation `9aed9d8c5dd86a9a9b972f8e9c5491fd6d2dbaa6`的run/job/artifact=`32794370664`/`97642478274`/`9544333991`精确复现26/26 JSON及success/DENIED audit、replay/conflict/rollback/concurrency、Production default-deny，故索引标为`done`。初始失败run `32793980039`保留；P3-08～15不自动启动。

用户随后单独授权TASK-P3-08；其从provider-verified P3-07 closure `a53c0f7d4a0f0bcd4e02bfeaaa0f6fc4b93157b9`冻结Diff base并进入`in_progress`。当前只允许internal Simulation APPROVED-only publication、same-key replay/conflict、new PUBLISHED + old SUPERSEDED + current CAS + append-only audit同事务、限定tests/machine CI和命中文档；P3-09～15、ExportJob/成果包、external side effect、HTTP/UI、P4及Production authority/readiness不自动启动。

TASK-P3-08已通过16 focused、577 full、Ruff/Pyright、8/8 publication machine、全部历史machine、P2 Gate/XS、Compose/build和51 paths/8 rows/19 checks/0 issues治理；implementation `e90475f462b365d2e031445ad28a02ea0b89d2f5`的run/job/artifact=`32798679852`/`97655144411`/`9545782727`精确复现27/27 JSON及APPROVED-only、current/supersession、replay/conflict/rollback/concurrency与Production default-deny，故索引标为`done`。P3-09～15不自动启动。

用户随后单独授权TASK-P3-09；其从provider-verified P3-08 closure `b9c0b1694448a4ec348b0b02107926f6213560c9`冻结Diff base并进入`in_progress`。启动Schema审查发现P2-only `export-manifest.v1`无法合法表达P3标准XLSX与Version/publication/Job/audit lineage，Agent零修改停止后获得用户扩卡批准；该Task按批准先发布additive `2.7.0` manifest/Job新版本并保留全部v1 bytes，再实现internal Simulation ExportJob。P3-10～15、external/P4/Production不自动启动。

## Lifecycle and planning-batch rules

状态使用`planned`、`ready`、`in_progress`、`blocked`、`done`、`cancelled`。进入`in_progress`前必须确认全部依赖`done`、用户授权、允许范围与文档影响，再把即时完整40字符HEAD写入Diff base；P2 Task还必须明确Start gate、Dependency changes、ADR impact和Provider evidence。

普通CI event range仍只能变更一张current-phase Task Card。唯一例外是初始phase-planning batch：必须由新建`TASK-Pn-00`、`Task batch role: phase-planning-owner`、有效Diff base且`in_progress/done`的唯一owner归属；其他卡必须同range新建、role=`phase-plan-member`、保持`planned/ready`且不得预填implementation SHA。历史卡、既有成员、多个owner或active/done成员均硬失败。选择owner后仍按owner Diff base检查全部scope/Impact Rule。

TASK-P2-00～14已`done`。P2-03的Diff base固定为`f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`且ADR-0011先于dependency变更接受；P2-04～14的implementation及exact provider evidence均已闭环。P2 Exit Gate=`READY`；“current phase仍为P2”只描述用户transition决定前的历史边界，现已由上方P3索引取代且历史证据不改写。

P2-04限定为正式Problem/Solution独立C-001～C-011判定、stable ValidationReport/Error、mutation/property/independence machine evidence及CI handoff；不得修改Backend、合同Schema、fixture历史bytes、dependency、objective、Benchmark或P3。P2-05及以后不会由本Task自动启动。

P2-04本地实现已通过6/6 machine checks、13个mutation、11个C-ID、14个hard violations及6个duration/order examples；implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的exact required `validate`与artifact复现同一证据，故Task=`done`。用户于2026-08-20明确授权TASK-P2-05；它以clean/provider-verified `c75f7a0e96b7591ffa9220d0de942f8841283093`为Diff base启动并已闭环为`done`。P2-06随后由2026-08-21的新授权启动并闭环；P2-07再由本次明确授权启动，P2-08～14仍为`planned`且未获授权。

P2-03本地39 focused、319 full、Ruff/Pyright、6/6 foundation、5/5 P2-02 compatibility及6/6 historical Engineering均PASS；provider artifact再次证明6/6与50 paths/9 rows/0 issues，因此索引状态为`done`。

P2-05 core implementation本地已通过64 focused、360 full、Ruff/Pyright、core/formal各6/6、49 paths/6 rows/19 checks/0 issues、compose/build与immutable boundary；implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的run `32354050257` / required job `96379299455` / artifact `9400957897`精确复现同一证据，故索引状态为`done`。P2-06启动基线`c55aa294977a6cafad85741f425d46cd36e9af1a`的run `32354521904` / required job `96380738933` / artifact `9401134902`精确成功；本Task当前只执行C-002/005/006/009，P2-07～14继续`planned`。

P2-06覆盖exact precedence min/max、historical anchor、calendar fixed intervals、release/material gates与conditional transport；87 focused、367 full、Ruff/Pyright 0、temporal 7/7、治理53 paths/6 rows/19 checks/0 issues、compose/build/immutable均PASS。Implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`的run `32432482739` / job `96626844156` / artifact `9429579311`精确复现证据，故索引为`done`。TASK-P2-07的启动来自新的明确授权；其Diff base `33cc3282ead23a4cc1bb214190191e116b095119`的run `32432843343` / job `96627943272` / artifact `9429703054`精确成功。

TASK-P2-07已完成本地实现验收：93 focused、382 full、Ruff/Pyright 0、fact-lock 7/7，治理54 paths/6 rows/19 checks/0 issues，Compose/build/immutable均PASS。Exact implementation provider evidence形成前索引继续为`in_progress`；P2-08～14不因本地PASS自动启动。

TASK-P2-07 implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的run `32435395744` / required job `96635463577` / artifact `9430579117`精确复现fact-lock 7/7及54 committed/0 working/6 rows/19 checks/0 issues，故索引状态为`done`。TASK-P2-08的启动基线run `32435755901` / job `96636509174` / artifact `9430697910`精确成功；本Task仅执行OBJ-001/Global Strategy，P2-09～14不会自动启动。

TASK-P2-08本地实现已通过70 focused、395 full、Ruff/Pyright 0、objective/strategy 7/7及全部历史machine checks，治理为142 docs、52 paths/8 rows/19 checks/0 issues，Compose/build/immutable均PASS；implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的run `32438785162` / required job `96645152864` / artifact `9431673977`精确复现7/7及52 committed/0 working/8 rows/19 checks/0 issues，故索引=`done`。P2-09～14保持`planned`且未授权。

用户于2026-08-21授权TASK-P2-09。启动门确认P2-04～08均`done`、closure HEAD/required check/artifact一致，且P0/P1 asset逐文件摘要、Scenario/Profile/assembler/policy/solver版本均已固定；当前只允许correctness assets、Scenario orchestration、四类测试、CI evidence及治理文档，P2-10～14不会自动启动。

TASK-P2-09本地实现已形成七个`1.0.0` correctness Scenario、SIM-ASSUMPTION-011、正式Raw→Problem→Strategy→Validator replay、row-order/fresh Validator property、C-001～C-011 exact mutations及`p2-correctness-report.v1` 8/8 PASS。45 focused、427 full、Ruff/Pyright、全部历史machine、58 paths/7 rows/19 checks/0 issues、Compose/build/immutable均PASS；implementation `20e49c92306128b47313059fabe31534814dbe3d`的run `32442651322` / required job `96656224252` / artifact `9432982306`精确复现并闭环，故索引=`done`。P2-10～14保持`planned`且未授权。

用户于2026-08-21授权TASK-P2-10。启动门确认P2-01/02/04及P2-09均`done`，closure HEAD `0e4f6630412889254a7bef41f487c24dc274ca9c`的required `validate` run `32443067388` / job `96657446617` / artifact `9433118755`一致；当前只允许五个reference algorithms、测试/CI evidence和治理文档，P2-11～14不会自动启动。

TASK-P2-10实现已形成五个`reference-*.v1` algorithms、SIM-ASSUMPTION-012、complete-or-discard/fresh Validator与`reference-scheduler-report.v1` 7/7。13 task-specific、441 full、Ruff/Pyright均PASS；implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`的run `32449742281` / required job `96675839685` / artifact `9435264655`精确复现17/17 reports及38 committed/0 working/6 rows/19 checks/0 issues，故索引=`done`。P2-11～14保持`planned`且未授权。

用户于2026-08-21授权TASK-P2-11。启动门确认P2-08/09均`done`，closure HEAD `41e958b771f2664b1ac50867903a30b73627878d`的required `validate` run `32450216908` / job `96677202782` / artifact `9435421360`一致；当前只允许KPI v2/manifest、deterministic reporting/internal package、测试/CI evidence和治理文档，P2-12～14不会自动启动。

TASK-P2-11已形成additive schema set`2.5.0`、validated-solution KPI/SolverReport、9-payload不可发布internal package及8/8 machine evidence；same-input bytes、cross-file lineage、tamper/missing/mixed-run、exact replay和partial-write cleanup均有测试。Implementation `546292831c3bd52185687a4c646c10ae10541ae2`的run `32454693799` / required job `96689627030` / artifact `9436863185`精确复现18/18 reports及58 committed/0 working paths、11 rows、19 checks、0 issues，故索引=`done`。P2-12～14保持`planned`且未获授权。

用户于2026-08-21授权TASK-P2-12。启动门确认P2-08～11均`done`，closure HEAD `58db14e8f18fb50866fb757d4c89e76fef1141f1`的required `validate` run `32455399561` / job `96691604529` / artifact `9437086153`一致；当前只允许XS/S/M BenchmarkRunner/profile/baseline、共享schedule KPI pure calculation、测试/CI evidence和治理文档，P2-13/14不会自动启动。

TASK-P2-12已形成严格XS/S/M profile/baseline、同Problem的Global/五Reference比较、formal Validator/共享KPI、warm-up/repetition/percentile、environment capture、CLI和CI XS artifact路径；27项指定、466项全仓测试及三份8/8报告均PASS。Implementation `01e7f4bdca88fc903e7caa771f875fc1a70ff357`的run `32460861563` / required job `96707353990` / artifact `9438899443`精确复现19/19 reports及49 committed/0 working paths、7 rows、19 checks、0 issues，故索引=`done`；P2-13/14不自动启动。

用户于2026-08-21授权TASK-P2-13。启动门确认P2-01～12均`done`，closure HEAD `59f3b013a4be7bd11d054e8464886b3cde791602`的required `validate` run `32461665177` / job `96709654227` / artifact `9439159396`一致；当前只允许公开边界Gate report、correctness/XS/S/M replay、四类拒绝、测试/CI evidence和治理文档，P2-14与P3不会自动启动。

TASK-P2-13本地已形成两次完整Gate replay、11/11 checks、14次correctness场景、6次benchmark profile、108次Benchmark Validator PASS、4类exact rejection与0 blocking gap；30项聚焦和476项全仓测试PASS。Exact implementation provider闭环前索引继续为`in_progress`；P2-14保持`planned`且未授权，P3未进入。

Implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的required run `32465737712` / job `96721819879` / artifact `9440650646`精确复现20/20 reports、Gate 11/11及37 committed/0 working paths、6 rows、19 checks、0 issues，故索引=`done`。P2-14保持`planned`且未授权，P3未进入。

用户于2026-08-24授权TASK-P2-14。启动门确认P2-01～13全部`done`，13组Diff base/implementation/closure ancestry、26个exact required runs/jobs/artifacts及下载后的364份JSON均一致；clean Diff base=`e76776d83726d13600d8ea29fd490474c8e32604`，其run/job/artifact=`32466635638`/`96724500691`/`9440970310`。当前只允许独立Exit审计、report/manifest和治理证据；不得修P2实现、创建P3 Task或改变current phase。

TASK-P2-14本地审计已形成overall=`READY`、blocking gaps为空：476 tests、两次Gate 11/11、七场景×两轮完整§76 measurements、XS/S/M各8/8、108次Benchmark Validator与四类fail-closed拒绝全部PASS。Audit implementation `65c556789f176ad9de55523d6420737bb60f933f`的run `32677741558` / required job `97288829348` / artifact `9503227240`精确复现20/20 JSON、30 committed/0 working paths、3 rows、19 checks、0 issues及Gate 11/11，故索引=`done`；P3未进入。

TASK-P3-09已通过16 focused、594 full、Ruff/Pyright、8/8 export machine、全部历史machine、P2 Gate/XS、Compose/build和76 paths/13 rows/19 checks/0 issues治理；implementation `42278239332e61e55a4e0305705534db768dc22f`的run/job/artifact=`32805450589`/`97674572006`/`9548027237`精确复现28/28 JSON及v1 preservation、standard package、job lifecycle/recovery/audit与Production default-deny，故索引标为`done`。

用户随后单独授权TASK-P3-10；P3-05～09 closure/provider、`main=origin/main`与clean tree复核通过，Diff base固定为`f71c4a5a11a3fac0e203e2e92198c26124755927`。该Task仅实现17个P3 HTTP operation、OpenAPI、strict carrier/idempotency/correlation、server-derived auth/scope、sanitized error与machine/test/docs；implementation `4958ce5759812331f13fab2608fbec37f1f1ff76`的run/job/artifact=`32812163430`/`97693443111`/`9550224090`精确复现603 tests、29/29 JSON、8/8 machine及51 committed/0 working paths、7 rows、19 checks、0 issues，故索引标为`done`。P3-11～15不自动启动。

用户随后单独授权TASK-P3-11；启动门复核P3-01/10 closure provider、`main=origin/main=26dd519b1f1f84e08d415cfdfce43f286fa82988`与clean tree一致，并把该SHA冻结为Diff base。激活前已冻结Node/npm、24个exact direct pins、npm v3 lock、SCA/license命令、13条read-only route及模块级allow-list；Task现为`in_progress`。P3-12～15、Gantt/load/comparison、actions/E2E、P4和Production不自动启动。

P3-11本地implementation已形成13 routes/seven states/read-only authority UI、25 tests、npm SCA/license/build与9/9 machine evidence；Python全仓604项、CI contract 28项及全部历史门禁也已通过。Required provider尚未形成，所以索引保持`in_progress`，不得预填implementation SHA/run/artifact或启动P3-12。
