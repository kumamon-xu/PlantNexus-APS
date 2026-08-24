---
doc_id: DOC-MILESTONE-INDEX
title: Milestone 索引
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84]
last_reviewed: 2026-08-24
---

# Milestone 索引

项目沿用总规 P0～P7，不建立 M0～M7 平行编号。

| Phase | 名称 | 主要结果 |
|---|---|---|
| P0 | Executable Specification | 固定排什么、什么算正确 |
| P1 | Data & Snapshot | 正式/仿真输入走同一确定性数据链 |
| P2 | CP-SAT Vertical Slice | C-001～C-011 + OBJ-001 闭环 |
| P3 | Planning Workspace | 版本、比较、审批、发布和导出 |
| P4 | Dynamic Replanning | 执行异常、事实保护、稳定性与 ChangeReport |
| P5 | Advanced Capabilities | 仅按证据逐项增加高级能力 |
| P6 | AI Duration Prediction | 核心稳定后的版本化预测接口 |
| P7 | Reality Calibration | 历史重放、现实差距与生产边界 |

Milestone 定义 outcome 和 exit gate，不等同 Sprint。只有当前 Phase 创建详细 Task Card；更新 `current_phase.md` 需要 Gate 的真实证据和用户确认。

P0 当前状态：TASK-P0-01～10 全部完成；[superseding audit](P0-exit-gate-audit-report.md) 的 Schema、Golden、Validator Rule Sheet、Scenario replay、Repository Build、CI 和 PROD_OPEN registration全部 `PASS`，P0 Gate=`READY`。用户于 2026-08-19 明确批准 phase transition后，P0转为 `completed`，历史失败/修复/provider evidence继续保留。

P1当前状态：[`P1 — Data & Snapshot`](P1-data-and-snapshot.md)为`completed`，TASK-P1-01～12全部`done`。[P1 audit](P1-exit-gate-audit-report.md)的271项回归、14/14 pipeline、全部machine/build/docs/provider证据均PASS；TASK-P1-12 implementation `a5d7e4a68dc12d48e36cb692500f59446f8097b4` / run `32326616525` / artifact `9391591718`已闭环，Gate=`READY`且无blocking gap。用户于2026-08-20明确批准transition。

P2当前状态：[`P2 — CP-SAT Vertical Slice`](P2-cp-sat-vertical-slice.md)为`completed`。TASK-P2-00～14均已闭环为`done`；P2 Exit Gate=`READY`且0 gaps。用户于2026-08-24在复核exact provider evidence、提交拓扑与clean synchronized baseline后明确批准P2→P3。

P3当前状态：[`P3 — Planning Workspace`](P3-planning-workspace.md)为`active`。TASK-P3-00～05均已由exact implementation provider闭环并在evidence-only closure标为`done`；用户已单独授权TASK-P3-06并从`67d38d030f8b129de7f1b2f6e5b75bd706655396`冻结Diff base进入`in_progress`，P3-07～15保持`planned`且未获授权。P3-15必须最后独立执行Exit Gate Audit；command/Validator PASS不表示approval/publish，也不自动进入P4或Production。

TASK-P3-04 implementation `a9be974855bb825784d639b7f6675e5a33e4273d`的run/job/artifact=`32700005280`/`97349447107`/`9510215582`精确复现35 focused、515 full、8/8 lifecycle、23/23 JSON PASS与45 committed/0 working paths、8 rows、19 checks、0 issues，故本closure标为`done`。该证据只形成reviewable ScheduleVersion，不形成approval、publish、P4或Production readiness。

## P2 execution history

TASK-P2-03 implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的run `32346208046`、required job `96355386111`和artifact `9398128763`均success；P2 phase保持active，后续Task不自动启动。

TASK-P2-04 implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的run `32350068318`、required job `96367085099`与artifact `9399519368`均success；artifact formal report为6/6且Task report为38 paths/6 rows/0 issues，故Task=`done`。P2-05的启动来自用户新的明确授权，不是依赖完成后的自动过渡。

TASK-P2-05本地实现和治理验收均PASS：64 focused、360 full、core/formal各6/6、Task diff 49 paths/6 rows/0 issues及compose/build/immutable。Implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的run `32354050257` / job `96379299455` / artifact `9400957897`也精确PASS，故Task=`done`。TASK-P2-06的启动来自用户新的明确授权；其启动基线run `32354521904` / job `96380738933` / artifact `9401134902`精确绑定Diff base并成功，不会自动启动P2-07。

TASK-P2-06已形成C-002/005/006/009 bounded temporal model与7/7 machine evidence；implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`的run `32432482739` / required job `96626844156` / artifact `9429579311`精确成功，故Task=`done`。用户随后明确授权TASK-P2-07；其clean/provider-verified启动基线为`33cc3282ead23a4cc1bb214190191e116b095119`。P2保持`active`，P2-08不会自动启动，P2-14仍必须最后执行。

TASK-P2-07已形成C-007/008 fact/lock model与7/7 machine evidence；implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的run `32435395744` / required job `96635463577` / artifact `9430579117`精确成功，故Task=`done`。

用户于2026-08-21明确授权TASK-P2-08；clean Diff base `9c55df993b12ae0bdd3d4d38c900d601324c05d2`的run `32435755901`、required job `96636509174`与artifact `9430697910`精确success。TASK-P2-08现只执行versioned Simulation OBJ-001、Global Strategy与honest status/report；P2-09～14未授权，P2-14仍必须最后执行。

TASK-P2-08本地已形成explicit Simulation policy/limits、exact OBJ-001、single-call Global Strategy、honest seven-status/objective/bound/gap/report与mandatory Validator gate；70 focused、395 full和7/7 machine checks均PASS。Implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的run `32438785162` / required job `96645152864` / artifact `9431673977`精确复现全部证据，故Task=`done`；Milestone保持`active`且不启动P2-09。

用户于2026-08-21明确授权TASK-P2-09；clean/provider-verified Diff base为`15c298f343a47db2a922544944ff5e02e4ca72d9`。本Task只启动七类correctness Scenario/Golden/property/mutation integration及machine evidence，不启动Benchmark、P2-10～14或P3；P2 Milestone继续`active`。

TASK-P2-09本地已使7/7 versioned scenarios通过正式Raw→Problem→Global Strategy→formal Validator链，并形成7次property replay、11个exact C-ID mutation与8/8 machine checks；45 focused、427 full、Ruff/Pyright、全部历史reports、58-path治理、Compose/build均PASS。Implementation `20e49c92306128b47313059fabe31534814dbe3d`的run `32442651322` / required job `96656224252` / artifact `9432982306`精确复现全部证据，故Task=`done`；P2-10～14及P3不会自动启动。

用户于2026-08-21明确授权TASK-P2-10；Diff base `0e4f6630412889254a7bef41f487c24dc274ca9c`的run `32443067388`、required job `96657446617`与artifact `9433118755`精确success。当前只启动五个versioned non-production baseline、deterministic tie-break、fresh Validator/KPI与machine evidence；P2-11～14及P3不自动启动，P2-14仍必须最后执行。

TASK-P2-10已通过13个Task-specific、441个full tests、Ruff/Pyright与reference machine 7/7，形成35 complete/fresh Validator/deterministic candidates和5 explicit failures。Implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`的run `32449742281` / required job `96675839685` / artifact `9435264655`精确复现全部证据，故Task=`done`；P2 Milestone继续`active`，P2-11～14不自动启动。

用户于2026-08-21明确授权TASK-P2-11；Diff base `41e958b771f2664b1ac50867903a30b73627878d`的run `32450216908`、required job `96677202782`与artifact `9435421360`精确success。当前只启动additive KPI/manifest合同、validated-solution KPI/SolverReport和不可发布internal package；ChangeReport/BenchmarkRunner、P3 state/persistence/approval/publish及P2-12～14不自动启动。

TASK-P2-11已形成`kpi.v2`、`export-manifest.v1`与`p2-internal-export.v1`，包括9个payload的canonical bytes/hash/count/lineage、8项machine checks以及idempotent/atomic failure边界。该包明确`publishable=false`、ScheduleVersion/ExportJob=`NOT_CREATED`、ChangeReport延后P4、BenchmarkReport延后P2-12。Implementation `546292831c3bd52185687a4c646c10ae10541ae2`的run `32454693799` / required job `96689627030` / artifact `9436863185`精确success并复现18/18 reports与58-path治理证据，故Task=`done`；P2 Milestone继续`active`，P2-12不自动启动。

用户于2026-08-21明确授权TASK-P2-12；Diff base `58db14e8f18fb50866fb757d4c89e76fef1141f1`的run `32455399561`、required job `96691604529`与artifact `9437086153`精确success。当前只启动versioned XS/S/M BenchmarkRunner、同Problem/Validator/KPI比较、环境/规模/性能/质量报告及CI XS artifact；L/XL、Production threshold、P2-13/14及P3不自动启动。

TASK-P2-12现已对XS/S/M固定Problem完成Global+五Reference、fresh Validator、共享KPI、1+3 repetition、环境/规模/时间/质量/内存采集与immutable baseline比较；三份报告均8/8 PASS且无warning。Implementation `01e7f4bdca88fc903e7caa771f875fc1a70ff357`的run `32460861563` / required job `96707353990` / artifact `9438899443`精确复现19/19 reports与49-path治理，故Task=`done`。Milestone继续`active`；P2-13/14与P3不自动启动。

用户于2026-08-21明确授权TASK-P2-13；Diff base `59f3b013a4be7bd11d054e8464886b3cde791602`的run `32461665177`、required job `96709654227`与artifact `9439159396`精确success。当前只启动公开边界Gate编排、至少两次correctness/XS/S/M replay、四类拒绝、CI machine evidence与治理同步；P2-14 Audit和P3不自动启动。

TASK-P2-13本地Gate已完成两次完整replay并为11/11 PASS；30项聚焦、476项全仓测试通过，累计14次correctness场景、6次XS/S/M profile、108次Benchmark Validator与4类exit rejection，blocking gap为空。Exact implementation provider尚未闭环，Task保持`in_progress`；P2 Milestone仍为`active`，P2-14仍是唯一最后Exit Gate Audit且未启动。

Implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的required run `32465737712` / job `96721819879` / artifact `9440650646`精确复现20/20 JSON与37-path治理证据，故TASK-P2-13=`done`。P2 Milestone仍`active`，P2-14继续`planned`且未授权，P3不自动启动。

用户于2026-08-24明确授权TASK-P2-14。启动时`main=origin/main=e76776d83726d13600d8ea29fd490474c8e32604`且clean；P2-01～13的13组提交拓扑、26个implementation/closure required runs与artifacts均独立复核PASS，当前closure run/job/artifact为`32466635638` / `96724500691` / `9440970310`。本Task只形成P2 Exit Gate report/manifest与治理证据，不进入P3；Milestone在用户另行批准transition前继续`active`。

TASK-P2-14本地独立审计结论为`READY`：476 tests、两次11/11 Gate、七correctness场景×两轮完整§76 measurement、XS/S/M各8/8、108次Benchmark Validator、四类exact rejection及0 blocking gap均PASS；report/manifest一致。Audit implementation `65c556789f176ad9de55523d6420737bb60f933f`的run `32677741558` / required job `97288829348` / artifact `9503227240`精确复现20/20 JSON、30 paths/3 rows/19 checks/0 issues及Gate 11/11，故Task=`done`。

Evidence-only closure `80c403384d1e171258cf874d26605d0d22aff1b2`的run `32678248961` / required job `97290201234` / artifact `9503372291`精确success；下载的implementation/closure artifacts均为20份可解析JSON且SHA、Task、Impact Rules、19 checks、0 issues一致。该SHA是P3-00不可变规划Diff base；transition保留P2所有历史记录，不把P2 internal Export提升为P3/Production publish。
