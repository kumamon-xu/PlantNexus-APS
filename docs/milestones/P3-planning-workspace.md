---
doc_id: MILESTONE-P3
title: P3 — Planning Workspace
status: completed
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [68, 69, 77, 78]
last_reviewed: 2026-08-27
---

# P3 — Planning Workspace

## P3 closure and transition

用户于2026-08-27在TASK-P3-00～17全部`done`、Exit report/manifest=`READY`且`blocking_gaps=[]`、audit implementation `201be9c6fd1b433a9d0a629a3ae7d4ffe1107476`与closure `61eeacdd5efc20b2321750e1310e9e21561c9fc2`的exact required provider/artifact均完成复验后批准P3→P4。P3现为`completed`；本段只追加transition事实，保留全部Exit报告、manifest、历史失败run、corrective链、provider evidence、OPEN/SIM assumptions、风险与P3/P4边界，不改写任何P3历史结论。

## TASK-P3-17 Exit decision

最终独立Audit已在冻结baseline `0933e10760096cdf8e812b2d41b34916e9db5750`上完成本地判定：[audit report](P3-exit-gate-audit-report.md)与[machine manifest](P3-exit-gate-evidence-manifest.json)均为overall=`READY`、`blocking_gaps=[]`。39个P3 push SHA/required checks、35个成功run、4个历史失败run、36个未过期artifact及1052文件/1010 JSON均已独立核验；621 Python、67 Vitest、三组12/12 Chromium、双语8/8、P2 11/11与P3 14/14双回放也全部通过。

Audit implementation `201be9c6fd1b433a9d0a629a3ae7d4ffe1107476`的run/job/artifact=`33033591189`/`98391337626`/`9631260796`已exact成功，下载复核44 files/38 JSON、28 SHA-bound/0 mismatch、61 committed/0 working paths、4 Impact Rules、19 checks、0 issues及P2/P3/i18n/三组Chromium一致。Evidence-only closure `61eeacdd5efc20b2321750e1310e9e21561c9fc2`的run/job/artifact=`33034464425`/`98394043379`/`9631608856`亦已exact复验成功并把TASK-P3-17标为`done`。P3在该closure时保持`active`/Exit ready awaiting explicit transition；现已由本页顶部transition记录关闭，Production仍未启动。

## TASK-P3-17 independent Exit Audit activation

用户于2026-08-27明确授权执行TASK-P3-17。启动复核确认TASK-P3-00～16全部`done`，`main=origin/main=remote main=0933e10760096cdf8e812b2d41b34916e9db5750`且working tree clean；P3-16 implementation/closure拓扑与exact required provider均成功，closure artifact `9629623182`下载内容的Task/SHA/base、双语coverage、P3 Gate、Impact Rules、checks与issues一致。该HEAD冻结为不可变Diff base；Task已完成独立Audit并由上述implementation provider支持为`done`。

本Audit独立重放全部P3 Gate并形成READY/NOT_READY；不得继承P3-14/P3-16结论代替重放，不得在Audit内修实现。在Audit执行与closure时P3继续`active`且P4未启动；现已由新的明确transition授权结束该等待状态。Production readiness/UAT/authority/deployment仍未启动。

## TASK-P3-15 amendment-governance completion and final plan

用户已批准P3末段编号调整；TASK-P3-15不再承担最终Audit，而以`06e7f794f486ac34c505237b847462c7c7c36d44`为不可变Diff base实现阶段计划修订owner。Implementation `c84e1aa1a81473f65d9f7906a6d2c67a94e7bb2f`的required run/job/artifact=`32944633958`/`98102640242`/`9597967232`精确成功；下载复核26 committed/0 working paths、5 rows、19 checks、0 issues。因此本closure把TASK-P3-15标为`done`，并由同一owner原子登记planned TASK-P3-16 bilingual localization和planned/final TASK-P3-17 Exit Audit。P3-00～14及其失败/成功provider历史保持只读，Milestone继续`active`，P4与Production未启动。

## TASK-P3-14 provider-verified Gate boundary

用户于2026-08-26单独授权TASK-P3-14；P3-01～13的done状态、提交祖先拓扑、26个exact required `validate`/未过期artifact和clean synchronized `6a3e02f00bf46f19915cb59c3c4af7daaac95be4`均已复核，该SHA冻结为Diff base。Task只允许Gate编排、双Backend/Chromium replay、四类exact rejection、semantic projection、focused tests、required CI evidence和治理同步。

Gate不得混入业务修复或改写P3-02～13、P2及失败provider历史。成功也只证明P3 vertical slice evidence；在TASK-P3-14冻结时，最终TASK-P3-17 Exit Gate Audit继续`NOT_PERFORMED`/`planned`。该历史事实保留，P4、Production identity/authority/capacity/readiness与external publish均未形成。

首个implementation `0617141e411eea146cd9fc1c512ade900710be7c`的run/job=`32930677030`/`98062166642`在repository suite失败：611 passed/5 setup errors均来自synthetic Frontend Gate夹具未绑定CI exact SHA；upload无reports且artifact count=0。失败事实保留且旧SHA不rerun。限定corrective `54a25646053979a69734a3148030830d49c04c1e`的run/job/artifact=`32931418903`/`98064264595`/`9593460266`随后完整通过，下载复验37 JSON、三组12/12 Playwright、P3 14/14/0 gaps和Task 56/0/8/19/0一致，故P3-14=`done`。P3 Milestone继续`active`，等待P3-16后再独立执行P3-17，而非自动进入Exit/P4。

当前完整local implementation Gate为PASS：616 Python、54 Vitest、基础Chromium及双Gate replay各12/12、全部machine/P2 XS/Gate/SCA/license/Compose/build与56 paths/8 rows/19 checks/0 issues均全绿；Backend双replay=18 stages/144 subordinate checks，Frontend 5/5、四类exact rejection及Python 14/14 checks通过，`blocking_gaps=[]`。这仍是provider pending状态；只有implementation exact-SHA required `validate`/artifact下载复核后，才可进入evidence-only closure。

## TASK-P3-13 completed slice

本Task把P3-06～12已形成的server command/decision/publication/export/API/read-only UI连接为isolated Simulation human-control consumer，并经用户批准additive提供EXPORTED verified package download。当前范围固定为command-only edit/lock→new DRAFT、approve/reject、internal publish、ExportJob/retry/download、audit/history及12 Chromium E2E；第18个operation不改变Schema/state/persistence。

首次closure provider暴露XLSX wall-clock non-determinism后，Task曾重新为`in_progress`；独立corrective implementation与本evidence-only closure现使其恢复`done`，closure自身仍须exact provider。P3-14必须独立聚合完整vertical slice，TASK-P3-17最后独立审计；本Task不得提前给出P3 Exit、P4或Production结论。

Local implementation Gate和首个corrective implementation `13e16e36fc0a06a079d6832f419950c830f2b96e`的run/job/artifact=`32921059019`/`98034581212`/`9589931373`曾全绿；但closure `87d47c7483185483ac8027100c1c664d18011a7c`的run `32921871460`真实失败且无artifact。独立corrective `3538d46f8b73ae434057bcbca9037436aa91f2c7`的run/job/artifact=`32923203227`/`98040743610`/`9590625358`现全绿，并复验33 JSON、12/12 Chromium与Task 91/0/11/19/0，故TASK-P3-13满足bounded DoD。其closure当时没有自动启动后续Task；P3-14现按新的用户授权执行，所有失败run继续保留。

## Authorization and start boundary

用户于2026-08-24在核验TASK-P2-00～14全部`done`、P2 Exit Gate overall=`READY`/`blocking_gaps=[]`、audit implementation/closure拓扑与exact GitHub required `validate`/artifact后，明确批准P2→P3 transition。P2为`completed`，P3为当前`active` Milestone。

TASK-P3-00已完成Milestone激活、Task规划与文档治理，TASK-P3-01～16均为`done`。TASK-P3-16冻结Diff base `1636fe9c909b728d49f9907ed9f53030b5921914`，implementation `b3ba999e83f4e8b0f96c7ce5bc72eba01432d791`及artifact `9629193057`已exact复验；closure `0933e10760096cdf8e812b2d41b34916e9db5750`的run/job/artifact=`33028998495`/`98376876640`/`9629623182`也已exact复验。TASK-P3-17现按新的用户授权以该closure为Diff base独立执行；这不授权后续阶段。

## Outcome

实现 Gantt、Resource Load、Order View、ScheduleVersion、Comparison、Lock、Approval、Reject、Publish、Export 和 Audit 工作区。

唯一纵向链为：validated PlanningSolution→immutable ScheduleVersion DRAFT→read model/comparison→command-only edit/lock→server validation→new DRAFT→approval/rejection/audit→idempotent publish/supersession→ExportJob/package→HTTP API/UI。P2 Problem/Solution/Validator/benchmark历史合同保持可重放和只读。

## Ordered Task plan

| Order | Task | Outcome | Depends on | State |
|---:|---|---|---|---|
| 0 | TASK-P3-00 | Phase transition、完整Task plan与治理同步 | TASK-P2-14 | `done` |
| 1 | TASK-P3-01 | Workspace页面/API/权限/状态/错误/审计/idempotency合同与ADR基线 | P3-00 | `done` |
| 2 | TASK-P3-02 | ScheduleVersion workspace/export Schema | P3-01 | `done` |
| 3 | TASK-P3-03 | ScheduleVersion、Audit与ExportJob persistence | P3-02 | `done` |
| 4 | TASK-P3-04 | validated solution→reviewable DRAFT | P3-03 | `done` |
| 5 | TASK-P3-05 | Gantt/Resource Load/Order/Comparison read models | P3-04 | `done` |
| 6 | TASK-P3-06 | Gantt edit/lock command→validation→new DRAFT | P3-04/05 | `done` |
| 7 | TASK-P3-07 | approval/rejection/audit service | P3-03/04 | `done` |
| 8 | TASK-P3-08 | idempotent publication与supersession | P3-03/07 | `done` |
| 9 | TASK-P3-09 | ExportJob与标准成果包 | P3-03/04/08 | `done` |
| 10 | TASK-P3-10 | Planning Workspace HTTP API | P3-05～09 | `done` |
| 11 | TASK-P3-11 | Frontend foundation与read-only workspace | P3-01/10 | `done` |
| 12 | TASK-P3-12 | Gantt/Resource Load/Comparison UI | P3-05/10/11 | `done` |
| 13 | TASK-P3-13 | Human control actions与UI E2E | P3-06～12 | `done` |
| 14 | TASK-P3-14 | 完整P3 vertical-slice Gate evidence | P3-01～13 | `done` |
| 15 | TASK-P3-15 | Phase plan amendment governance support | P3-14 | `done` |
| 16 | TASK-P3-16 | Frontend bilingual localization与官方中文术语 | P3-14/P3-15 | `done` |
| 17 | TASK-P3-17 | P3独立Exit Gate Audit（最终Task） | P3-16 | `done` |

## Dependency graph

```text
P3-00 → P3-01 → P3-02 → P3-03 → P3-04 → P3-05 → P3-06
                              ├────→ P3-07 → P3-08 → P3-09
                              └──────────────────────────┘
P3-05/06/07/08/09 → P3-10 → P3-11 → P3-12 → P3-13
P3-01～13 → P3-14 → P3-15 → P3-16 → P3-17
```

P3-07可在P3-04之后与read-model支线并行准备；P3-08必须等待authorization/audit service，P3-09必须等待可发布版本语义。API必须组合全部application service后形成；UI action E2E必须等待read-only与command两条链。TASK-P3-15只负责修订治理；TASK-P3-16已按独立授权完成展示层双语/zero-wire-drift；TASK-P3-17最后审计冻结证据且不得修实现。

## Exit Gate

DRAFT/REJECTED 不可发布，仅 APPROVED 可发布；PUBLISHED immutable；export idempotent。Gantt 编辑使用 UI Command→Server Validation→New Draft→Validator，不能直接更新 published schedule。

详细页面、API payload、权限矩阵在实现前形成；审批责任受 OPEN-010 约束。

Gate还必须证明：版本/比较/read model lineage一致；所有command产生新DRAFT且formal Validator复验；approval/rejection/publish/export写入append-only audit；publish/export重试same-key same-result且冲突fail closed；API与UI不能绕过application/state-machine；TASK-P3-16双语展示保留英文machine contract、unknown raw fallback、document lang/Ant locale和完整术语coverage；artifact精确绑定implementation SHA、Task、Impact Rules、checks和issues。

## P3/P4/Production boundaries

- P3只处理计划版本的人机协同、审批状态、内部发布、导出与审计；不实现ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport或Execution Simulator。
- `PUBLISHED` immutable；任何编辑/锁变更都创建新DRAFT，不能原地修改或由UI复制Solver/Validator逻辑。
- OPEN-010关闭前只允许authority-neutral capability与default-deny；不得声称已确定真实审批责任、组织角色或外部系统authority。
- Production channel、真实MES/ERP侧效应、生产密钥/部署/SLA/readiness受PROD_OPEN和P7 gate约束；P3内部Simulation publish不能外推为Production publish/approval。
- 独立P3 Exit Audit=`READY`也不自动进入P4；P3→P4需要新的用户明确批准。

## Current execution boundary

TASK-P3-05现从P3-04 closure `fc5011f78a242160097521259a1914d864d9ad17`冻结Diff base并进入`in_progress`；该closure的run/job/artifact=`32700684160`/`97351382226`/`9510431988`精确成功，启动重放再次确认synthetic READY_FOR_REVIEW Version。当前只允许只读projection/query/comparison、限定tests/machine CI与命中文档；repository write/state transition、Solver/Validator、HTTP/UI、approval/publish/export、P4/Production均禁止。P3-06不自动启动。

P3-05 read slice覆盖13个普通view与独立Version Comparison，machine为8/8、普通payload 23、exact query/comparison replay各1、4类negative、read前后row count一致、product-service Solver调用0；定向33项与全仓527项PASS。Implementation `f236fab47aa2565b87a060b2c8bde8f2e8d66229`的run/job/artifact=`32706258281`/`97367902547`/`9512423712`复现24/24 JSON及50 committed/0 working paths、7 rows、19 checks、0 issues，故本closure标为`done`。该结果不形成API/UI/write/approval/publish/P4或Production能力，P3-06仍等待用户明确授权。

用户随后明确授权TASK-P3-06；启动复核确认P3-04/05均`done`，P3-05 closure `67d38d030f8b129de7f1b2f6e5b75bd706655396`的required run/job/artifact=`32707242260`/`97370830393`/`9512779675`精确success，main与origin/main一致且工作树clean。当前仅允许该Task的四类content command→copy-on-write candidate→fresh Validator→atomic new DRAFT/audit，以及独立`SUBMIT_FOR_REVIEW`→second fresh Validator→既有DRAFT→READY同content CAS/audit链；Solver、Schema、migration、dependency、API/UI、approval/publish/export、P4和Production authority保持禁止。

TASK-P3-06形成上述5-command链与8/8 machine evidence；41 focused、546 full、Ruff/Pyright、全部既有machine、P2 Gate、XS benchmark、Compose、build与治理均PASS。Implementation `08317637c7fbb51d46880d32523545bb0b4fe1c0`的run/job/artifact=`32713635045`/`97390177509`/`9515126567`复现25/25 JSON及57 committed/0 working paths、8 rows、19 checks、0 issues，故本closure标为`done`。该结果不形成HTTP/UI、approval/rejection/publish/export、P4或Production能力。

用户于2026-08-25单独授权TASK-P3-07；启动复核确认P3-03/04及直接前序P3-06 closure均provider-verified，closure `514224b8ff2d507b613797ae697245bab14f79eb`的run/job/artifact=`32714501727`/`97392773902`/`9515436874`精确success且25/25 JSON、57 committed/0 working paths、8 rows、19 checks、0 issues。当前只允许READY_FOR_REVIEW→APPROVED/REJECTED的authority-neutral decision、atomic audit、idempotency/CAS、Simulation测试策略与Production default-deny；真实RBAC/SSO、publish/export、HTTP/UI、P3-08+、P4和Production authority/readiness均未启动。

TASK-P3-07已形成同content approve/reject、server authority与Production default-deny、success/DENIED append-only audit、exact replay/conflict/rollback/concurrency单winner；39 focused、562 full、Ruff/Pyright、8/8 decision machine、全部历史machine、P2 Gate/XS、Compose/build及50 paths/8 rows/19 checks/0 issues治理均PASS。Corrective implementation `9aed9d8c5dd86a9a9b972f8e9c5491fd6d2dbaa6`的run/job/artifact=`32794370664`/`97642478274`/`9544333991`复现26/26 JSON并通过，故本closure标为`done`；P3-08不会自动启动，OPEN-010及P3/P4/Production边界不变。

用户随后于2026-08-25单独授权TASK-P3-08；启动复核确认P3-03/07均`done`，P3-07 closure `a53c0f7d4a0f0bcd4e02bfeaaa0f6fc4b93157b9`的required run/job/artifact=`32794963626`/`97644228513`/`9544539992`精确success，26/26 JSON、50 committed/0 working paths、8 rows、19 checks、0 issues。该SHA成为P3-08不可变Diff base。当前仅允许authorized APPROVED→PUBLISHED、旧current PUBLISHED→SUPERSEDED、current CAS、same-key replay/conflict与atomic audit的`SIMULATION_INTERNAL` slice；ExportJob/成果包、外部MES/ERP、HTTP/UI、Schema/migration/dependency、P3-09+、P4及Production authority/readiness均禁止。

TASK-P3-08已形成pure domain/application ports service与8/8 publication machine：3 successful publications、2 supersessions、1 exact replay、1 conflict、2 authorization denials、4 no-state rejections、1 atomic rollback、1 concurrent current winner、Solver调用0、`issues=[]`。Focused 16、full repository 577、全部历史machine、P2 Gate、XS、Compose/build及51 paths/8 rows/19 checks/0 issues治理均PASS。Implementation `e90475f462b365d2e031445ad28a02ea0b89d2f5`的run/job/artifact=`32798679852`/`97655144411`/`9545782727`精确复现27/27 JSON，故本closure标为`done`；P3-09仍为`planned`且不会自动启动。

用户随后单独授权TASK-P3-09；启动复核确认P3-03/04/08均`done`，P3-08 closure `b9c0b1694448a4ec348b0b02107926f6213560c9`的run/job/artifact=`32799416669`/`97657208631`/`9546020704`精确success并成为Diff base。Schema预检发现P2-only manifest不能合法承载P3 standard profile，Agent零修改停止后获用户明确扩卡批准；当前只允许additive `2.7.0` P3 manifest/Job carrier、internal Simulation ExportJob/package/audit/retry及限定tests/CI/docs。P3-10+、external/P4/Production仍未启动。

TASK-P3-00 planning implementation `1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7`的run/job/artifact=`32681493976`/`97298850740`/`9504310381`已精确PASS；其closure `7f65f88b620ea1e8d2f4693911be3b52f4052d5d`的run/job/artifact=`32682015727`/`97300206924`/`9504453154`也精确PASS。TASK-P3-01 implementation `3bf99cbafdad983795a83a88646240dbb0b24509`的run/job/artifact=`32684713630`/`97307562801`/`9505303054`复现43 paths、4 rows、19 checks和0 issues。TASK-P3-02 implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a`的run/job/artifact=`32689832111`/`97321420908`/`9506913562`复现additive schema set`2.6.0`、7 Schema/7 sample、8/8 checks及65 paths/10 rows/19 checks/0 issues；closure `9621fda535f66393beab88efc13c100fc805c993`的run/job/artifact=`32690302424`/`97322642627`/`9507045338`也精确成功。TASK-P3-03已从该closure SHA激活，只允许持久化原语；P3-04～15未启动。

TASK-P3-03 implementation `e315dbf4f6c079df6d19b52f0403b00827126232`的run/job/artifact=`32694644036`/`97334382152`/`9508445635`精确复现5张plane-scoped表、四类repository、8/8 machine evidence及52 committed/0 working paths、7 rows、19 checks、0 issues，故本closure将Task标为`done`。P3-04～15仍未启动；该结果不形成业务approval/publish/export、PostgreSQL Production migration或Production能力。

TASK-P3-04已从P3-03 provider-verified closure `62604d05964413a0aa7f763afd720afa2d53a887`启动；其closure run/job/artifact=`32695127644`/`97335699708`/`9508601189`精确成功并成为启动门证据。当前只允许validated P2 lineage→DRAFT→READY_FOR_REVIEW、原子audit、幂等/冲突/隔离、限定tests/machine CI和命中文档；P3-05～15、approval/reject/publish/export、HTTP/UI、P4与Production authority均未启动。

TASK-P3-04已形成ports-only application lifecycle、fresh Validator/KPI gate、immutable DRAFT→READY_FOR_REVIEW、单事务audit、exact replay/conflict/rollback/concurrency/plane隔离；35 focused、515 full、Ruff/Pyright、8/8 machine report、全部历史machine、P2 Gate、XS benchmark、Compose/build及45 paths/8 rows/19 checks/0 issues治理均PASS。Implementation `a9be974855bb825784d639b7f6675e5a33e4273d`的run/job/artifact=`32700005280`/`97349447107`/`9510215582`精确复现23/23 JSON及上述证据，故本closure标为`done`；不自动启动P3-05或任何approval/publish能力。

TASK-P3-09已实现五state/六allowed pair、attempt/lease/heartbeat、explicit retry/cancel/expired recovery、audit-atomic CAS以及12-payload standard package。v2 manifest在P2 lineage之上绑定PUBLISHED Version、PublicationResult、Job attempt和audit；P4 ChangeReport仍`DEFERRED`。Implementation `42278239332e61e55a4e0305705534db768dc22f`的run/job/artifact=`32805450589`/`97674572006`/`9548027237`精确复现28/28 JSON、export 8/8及76 committed/0 working paths、13 rows、19 checks、0 issues，故本closure标为`done`。

用户随后单独授权TASK-P3-10；P3-05～09的closure SHA/provider artifact全部重新核验，启动时`main=origin/main=f71c4a5a11a3fac0e203e2e92198c26124755927`且clean，该SHA成为不可变Diff base。当前bounded slice形成17个versioned HTTP operation、OpenAPI、strict carrier/header/path绑定、server-derived capability/scope、Production pre-provider deny、sanitized error/correlation/denial audit和application façade；不改变P3-05～09语义、Schema/migration/dependency/repository/state pair，也不形成Frontend、external/P4/Production。Implementation `4958ce5759812331f13fab2608fbec37f1f1ff76`的run/job/artifact=`32812163430`/`97693443111`/`9550224090`精确复现29/29 JSON、API 8/8及51 committed/0 working paths、7 rows、19 checks、0 issues，故本closure标为`done`；P3-11仍为`planned`且不会自动启动。

用户随后单独授权TASK-P3-11；P3-01/10 closure provider与clean synchronized baseline复核通过，`26dd519b1f1f84e08d415cfdfce43f286fa82988`冻结为Diff base。激活前已逐字锁定Node `24.19.0`、npm `11.17.0`、24个direct pins、npm v3 lock策略、High/Critical SCA与license命令、模块级Frontend allow-list和六条Impact Rule。当前只允许read-only HTTP consumer、13条P3-11 UI route、七类页面状态、accessible virtual table、CI/machine evidence与治理；P3-12 Gantt/load/comparison、P3-13 actions/E2E、real identity、P4和Production仍未启动。

P3-11 implementation `567e8693db881ea3dfffa011de9021fef9641361`的required run/job/artifact=`32818657951`/`97712018632`/`9552386549`精确success；下载复核32/32 JSON、Frontend 9/9、SCA 0、336 package license及74 committed/0 working paths、6 rows、19 checks、0 issues，故本closure标为`done`。Milestone仍active，P3-12+保持`planned`且不自动启动；browser E2E、P4与Production仍未形成。

用户随后单独授权TASK-P3-12；P3-05/10/11 closure provider、`main=origin/main=3bca1cc10ebedc4d47227bafb2f3f66854ccb526`与clean tree复核通过，该SHA冻结为Diff base。本Task仅形成Gantt/Resource Load/KPI/Diagnostics/two-Version comparison的只读UI、virtualization、可访问替代视图与read-only Playwright evidence；dependency/lock、server business/state、P3-13 actions、P4与Production均保持冻结。

TASK-P3-12 local implementation为18条read-only route、三层Gantt、load/comparison、strict outbound binding、37项Vitest、4/4 Chromium和12/12 machine PASS；120/24 render与bundle仅为development observation，新增SIM-ASSUMPTION-014约束其不得外推Production。Implementation `a719fe5bf2c2ea2d59e1582e8f4dfd3f2674ac69`的required run/job/artifact=`32826371613`/`97735176425`/`9555196470`已精确复验33/33 JSON与55 committed/0 working paths、6 rows、19 checks、0 issues，故本closure把Task标为`done`且不自动启动P3-13。
