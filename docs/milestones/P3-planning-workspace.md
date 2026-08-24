---
doc_id: MILESTONE-P3
title: P3 — Planning Workspace
status: active
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [68, 69, 77, 78]
last_reviewed: 2026-08-24
---

# P3 — Planning Workspace

## Authorization and start boundary

用户于2026-08-24在核验TASK-P2-00～14全部`done`、P2 Exit Gate overall=`READY`/`blocking_gaps=[]`、audit implementation/closure拓扑与exact GitHub required `validate`/artifact后，明确批准P2→P3 transition。P2为`completed`，P3为当前`active` Milestone。

TASK-P3-00已完成Milestone激活、Task规划与文档治理，TASK-P3-01～05也已由各自exact implementation provider与evidence-only closure闭环；P3-06～15保持`planned`且未获授权。依赖满足不会自动授权后续实现。每个Task必须从当时clean、`main=origin/main`且provider-verified的完整40字符HEAD建立新的不可变Diff base。

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
| 6 | TASK-P3-06 | Gantt edit/lock command→validation→new DRAFT | P3-04/05 | `planned` |
| 7 | TASK-P3-07 | approval/rejection/audit service | P3-03/04 | `planned` |
| 8 | TASK-P3-08 | idempotent publication与supersession | P3-03/07 | `planned` |
| 9 | TASK-P3-09 | ExportJob与标准成果包 | P3-03/04/08 | `planned` |
| 10 | TASK-P3-10 | Planning Workspace HTTP API | P3-05～09 | `planned` |
| 11 | TASK-P3-11 | Frontend foundation与read-only workspace | P3-01/10 | `planned` |
| 12 | TASK-P3-12 | Gantt/Resource Load/Comparison UI | P3-05/10/11 | `planned` |
| 13 | TASK-P3-13 | Human control actions与UI E2E | P3-06～12 | `planned` |
| 14 | TASK-P3-14 | 完整P3 vertical-slice Gate evidence | P3-01～13 | `planned` |
| 15 | TASK-P3-15 | 独立P3 Exit Gate Audit | P3-14 | `planned` |

## Dependency graph

```text
P3-00 → P3-01 → P3-02 → P3-03 → P3-04 → P3-05 → P3-06
                              ├────→ P3-07 → P3-08 → P3-09
                              └──────────────────────────┘
P3-05/06/07/08/09 → P3-10 → P3-11 → P3-12 → P3-13
P3-01～13 → P3-14 → P3-15
```

P3-07可在P3-04之后与read-model支线并行准备；P3-08必须等待authorization/audit service，P3-09必须等待可发布版本语义。API必须组合全部application service后形成；UI action E2E必须等待read-only与command两条链。P3-15只审计冻结证据，不修实现。

## Exit Gate

DRAFT/REJECTED 不可发布，仅 APPROVED 可发布；PUBLISHED immutable；export idempotent。Gantt 编辑使用 UI Command→Server Validation→New Draft→Validator，不能直接更新 published schedule。

详细页面、API payload、权限矩阵在实现前形成；审批责任受 OPEN-010 约束。

Gate还必须证明：版本/比较/read model lineage一致；所有command产生新DRAFT且formal Validator复验；approval/rejection/publish/export写入append-only audit；publish/export重试same-key same-result且冲突fail closed；API与UI不能绕过application/state-machine；artifact精确绑定implementation SHA、Task、Impact Rules、checks和issues。

## P3/P4/Production boundaries

- P3只处理计划版本的人机协同、审批状态、内部发布、导出与审计；不实现ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport或Execution Simulator。
- `PUBLISHED` immutable；任何编辑/锁变更都创建新DRAFT，不能原地修改或由UI复制Solver/Validator逻辑。
- OPEN-010关闭前只允许authority-neutral capability与default-deny；不得声称已确定真实审批责任、组织角色或外部系统authority。
- Production channel、真实MES/ERP侧效应、生产密钥/部署/SLA/readiness受PROD_OPEN和P7 gate约束；P3内部Simulation publish不能外推为Production publish/approval。
- P3-15=`READY`也不自动进入P4；P3→P4需要新的用户明确批准。

## Current execution boundary

TASK-P3-05现从P3-04 closure `fc5011f78a242160097521259a1914d864d9ad17`冻结Diff base并进入`in_progress`；该closure的run/job/artifact=`32700684160`/`97351382226`/`9510431988`精确成功，启动重放再次确认synthetic READY_FOR_REVIEW Version。当前只允许只读projection/query/comparison、限定tests/machine CI与命中文档；repository write/state transition、Solver/Validator、HTTP/UI、approval/publish/export、P4/Production均禁止。P3-06不自动启动。

P3-05 read slice覆盖13个普通view与独立Version Comparison，machine为8/8、普通payload 23、exact query/comparison replay各1、4类negative、read前后row count一致、product-service Solver调用0；定向33项与全仓527项PASS。Implementation `f236fab47aa2565b87a060b2c8bde8f2e8d66229`的run/job/artifact=`32706258281`/`97367902547`/`9512423712`复现24/24 JSON及50 committed/0 working paths、7 rows、19 checks、0 issues，故本closure标为`done`。该结果不形成API/UI/write/approval/publish/P4或Production能力，P3-06仍等待用户明确授权。

TASK-P3-00 planning implementation `1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7`的run/job/artifact=`32681493976`/`97298850740`/`9504310381`已精确PASS；其closure `7f65f88b620ea1e8d2f4693911be3b52f4052d5d`的run/job/artifact=`32682015727`/`97300206924`/`9504453154`也精确PASS。TASK-P3-01 implementation `3bf99cbafdad983795a83a88646240dbb0b24509`的run/job/artifact=`32684713630`/`97307562801`/`9505303054`复现43 paths、4 rows、19 checks和0 issues。TASK-P3-02 implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a`的run/job/artifact=`32689832111`/`97321420908`/`9506913562`复现additive schema set`2.6.0`、7 Schema/7 sample、8/8 checks及65 paths/10 rows/19 checks/0 issues；closure `9621fda535f66393beab88efc13c100fc805c993`的run/job/artifact=`32690302424`/`97322642627`/`9507045338`也精确成功。TASK-P3-03已从该closure SHA激活，只允许持久化原语；P3-04～15未启动。

TASK-P3-03 implementation `e315dbf4f6c079df6d19b52f0403b00827126232`的run/job/artifact=`32694644036`/`97334382152`/`9508445635`精确复现5张plane-scoped表、四类repository、8/8 machine evidence及52 committed/0 working paths、7 rows、19 checks、0 issues，故本closure将Task标为`done`。P3-04～15仍未启动；该结果不形成业务approval/publish/export、PostgreSQL Production migration或Production能力。

TASK-P3-04已从P3-03 provider-verified closure `62604d05964413a0aa7f763afd720afa2d53a887`启动；其closure run/job/artifact=`32695127644`/`97335699708`/`9508601189`精确成功并成为启动门证据。当前只允许validated P2 lineage→DRAFT→READY_FOR_REVIEW、原子audit、幂等/冲突/隔离、限定tests/machine CI和命中文档；P3-05～15、approval/reject/publish/export、HTTP/UI、P4与Production authority均未启动。

TASK-P3-04已形成ports-only application lifecycle、fresh Validator/KPI gate、immutable DRAFT→READY_FOR_REVIEW、单事务audit、exact replay/conflict/rollback/concurrency/plane隔离；35 focused、515 full、Ruff/Pyright、8/8 machine report、全部历史machine、P2 Gate、XS benchmark、Compose/build及45 paths/8 rows/19 checks/0 issues治理均PASS。Implementation `a9be974855bb825784d639b7f6675e5a33e4273d`的run/job/artifact=`32700005280`/`97349447107`/`9510215582`精确复现23/23 JSON及上述证据，故本closure标为`done`；不自动启动P3-05或任何approval/publish能力。
