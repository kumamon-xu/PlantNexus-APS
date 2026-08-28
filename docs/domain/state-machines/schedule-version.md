---
doc_id: DOC-STATE-002
title: ScheduleVersion 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [30, 33, 35, 66, 69, 78]
last_reviewed: 2026-08-28
---

# ScheduleVersion 状态机

## TASK-P4-08 DRAFT-only state application

P4 application现唯一创建`source_kind=DYNAMIC_REPLAN`的new immutable DRAFT v2；PUBLISHED base/current reference保持字节级不变，new Version的decision/publication/superseded_by为空且只开放view/edit/lock/audit。Result transaction不调用任何transition，失败或并发loser不留下partial Version。

DRAFT后续仍必须走P3既有`DRAFT→READY_FOR_REVIEW→APPROVED/REJECTED→PUBLISHED→SUPERSEDED`人工控制链。本Task没有新state/pair、自动READY/approve/publish/export或Production authority。

## TASK-P4-03 persistence review

本Task只允许terminal replan result保存future `schedule-version.v2`的version/id/content fingerprint reference，不创建或更新ScheduleVersion row。既有DRAFT/READY_FOR_REVIEW/APPROVED/PUBLISHED/SUPERSEDED/REJECTED集合与全部pair零变化；PUBLISHED base保持immutable，new DRAFT application仍由P4-08独占。

## TASK-P4-02 ScheduleVersion v2 carrier review

新carrier增加dynamic-replan lineage但直接复用v1的六状态、guard evidence与allowed pairs。Synthetic sample只能是DRAFT且decision/publication为空；本Task不创建或迁移Version，不自动READY/APPROVE/PUBLISH，也不改变PUBLISHED immutable/supersession语义。实际new DRAFT transaction仍属于P4-08。

## TASK-P4-01 state decision

ADR-0013/0014确认dynamic replan不得原地修改PUBLISHED或既有Version，也不需要额外ScheduleVersion state/pair。TASK-P4-08只可在P4-03～07完成后，以fresh-validated且ChangeReport complete的结果原子创建带base/event/fact/request/run/report lineage的新DRAFT；它不自动READY、APPROVED或PUBLISHED。当前DRAFT/READY_FOR_REVIEW/APPROVED/REJECTED/PUBLISHED/SUPERSEDED集合与所有pair逐字不变。

## TASK-P3-17 audit conclusion

六状态与五个allowed pair、APPROVED-only internal publication、REJECTED/DRAFT不可发布、PUBLISHED immutable、SUPERSEDED history、CAS/idempotency/audit均经双Gate和negative replay独立PASS。状态集合与transition pair未修改，真实Production approval authority未形成。

## TASK-P3-16 display-label review

`official-zh-cn-terminology.v1`为六个ScheduleVersion state提供`zh-CN`/`en-US`展示label，但状态registry、Schema、API、repository、transition pair与audit中的machine value仍逐字使用`DRAFT/READY_FOR_REVIEW/APPROVED/REJECTED/PUBLISHED/SUPERSEDED`。TASK-P3-16已实现typed display mapping、未知raw state fallback及zero-wire-drift tests并取得exact implementation provider；没有state-machine、migration或后端测试断言变化，TASK-P3-17最终独立复验。

## TASK-P3-14 state Gate

Gate覆盖DRAFT→READY_FOR_REVIEW→APPROVED/REJECTED、APPROVED→PUBLISHED及既有supersession行为，并以四类负向证据锁定DRAFT/REJECTED不可publish、PUBLISHED不可mutation。两轮语义必须一致；本Task不增加pair、guard、actor、Schema或migration。

## TASK-P3-13 UI authority review

UI只按authoritative state/capability呈现既有commands，成功后读取server返回的新Version；DRAFT/READY_FOR_REVIEW/APPROVED/PUBLISHED控制面分别隔离，PUBLISHED永不提供edit/lock。新增download不接触ScheduleVersion repository或transition。现有6 states/9 pairs、copy-on-write、approval/publication/current语义、Schema与migration均零变化。

```text
DRAFT
→ READY_FOR_REVIEW
→ APPROVED
→ PUBLISHED
→ SUPERSEDED

READY_FOR_REVIEW
→ REJECTED
→（通过新 Planning/Editing command 产生新 DRAFT Version）
```

## 转移门

| 转移 | 必须满足 |
|---|---|
| DRAFT → READY_FOR_REVIEW | 独立 Validator PASS，硬违反数为 0，provenance 完整 |
| READY_FOR_REVIEW → APPROVED | 有权限的人工作出审批并记录 audit |
| READY_FOR_REVIEW → REJECTED | 记录 actor、reason；原版本保留 |
| APPROVED → PUBLISHED | 发布操作幂等、目标明确、没有 synthetic/production 混用 |
| PUBLISHED → SUPERSEDED | 新版本已成为当前生产参考；旧版本仍不可变 |

## 不变量

- DRAFT 和 REJECTED 不可发布；仅 APPROVED 可发布。
- PUBLISHED Version 不可修改或删除。
- Reject、Gantt 编辑、Replan 都产生新版本，不复用旧 ID。
- 发布重试不能 double publish。
- “Rollback”只表示选择历史版本作为新计划的参考输入；不得直接把历史 PUBLISHED 行改回当前。

## P0 versioned transition table

允许 pair 仅为：

| From | To | Guard/evidence boundary |
|---|---|---|
| DRAFT | READY_FOR_REVIEW | independent validation PASS、hard count 0、provenance 完整 |
| READY_FOR_REVIEW | APPROVED | authorized human actor/decision/audit；角色仍受 OPEN-010 约束 |
| READY_FOR_REVIEW | REJECTED | actor/reason/audit；修订必须产生新 DRAFT version |
| APPROVED | PUBLISHED | idempotent、target 明确、Production/Synthetic 安全 |
| PUBLISHED | SUPERSEDED | 新版本成为当前生产参考，旧版本仍不可变 |

`SUPERSEDED` 与 `REJECTED` 为终态；REJECTED 没有回到 DRAFT 的同实体转移。任何 `DRAFT → PUBLISHED`、PUBLISHED 修改或 REJECTED 复用均返回 `INVALID_STATE_TRANSITION`。

[`state-transition.v1`](../../../schemas/json/state-transition.schema.json) 只验证 machine/state 名称，[`state-machines.v1`](../../../schemas/rules/state-machines.v1.yaml) 和纯状态合同授权 pair。TEST-STATE-TRANSITION-001 不替代 P3 权限、audit、immutability、publish/idempotency tests。

## TASK-P0-08 generic idempotency review

process-local `InMemoryIdempotencyStore` 只固定“同 scope/key + 同 request hash 返回原 logical ID；不同 hash 冲突”的工程原语，不注册 Publish/Export task，也不授权 `APPROVED → PUBLISHED`。ScheduleVersion pair、guard、权限、不可变与发布副作用全部未实现且未改变；business publish idempotency 继续 `PLANNED`。

## TASK-P2-02 review

PlanningSolution v1仍只是未验证candidate carrier；`CONTRACT_SAMPLE`的UNKNOWN没有candidate。P2-02不创建DRAFT ScheduleVersion、不执行`DRAFT → READY_FOR_REVIEW`，也不修改`state-machines.v1`的pair/guard。后继P2-04必须先产出independent validation PASS，P3权限/审批/发布仍未授权。

## TASK-P2-11 validated-solution boundary

Internal package中的`schedule.json`虽然必须绑定fresh exact PASS ValidationReport，却仍是`planning-solution.v1`，不是DRAFT ScheduleVersion。Manifest明确`schedule_version=NOT_CREATED`、approval/publication=`NOT_STARTED`和`publishable=false`；因此不执行`DRAFT → READY_FOR_REVIEW`，也不创建actor、decision、audit或current-version记录。

该边界保留“Validator PASS是进入评审的必要但非充分条件”：只有P3创建immutable ScheduleVersion并满足provenance/权限/状态guard后才能进入评审。状态pair、terminal semantics与`state-machines.v1`均未修改。

## P3 implementation allocation

P3-01补齐guard/actor/reason/audit/idempotency合同但不改v1 pair；P3-03形成immutable persistence，P3-04实现DRAFT→READY_FOR_REVIEW，P3-07实现READY_FOR_REVIEW→APPROVED/REJECTED，P3-08实现APPROVED→PUBLISHED与PUBLISHED→SUPERSEDED。DRAFT/REJECTED不可publish、PUBLISHED/REJECTED内容不可变，edit/lock只产生新DRAFT。P3-10/13只能调用这些application guards，P3-14负责Gate，P3-16只本地化label，P3-17负责最终Audit。

## TASK-P3-01 guard baseline

[ADR-0012](../../adr/ADR-0012-planning-workspace-command-state-publication.md)已接受以下guard，但没有实现transition：所有Version content append-only；manual edit/lock永远copy-on-write生成新DRAFT且source state/content不变；READY_FOR_REVIEW的approve/reject分别要求`approve`/`reject` capability、non-empty reason、expected fingerprint和atomic audit；publish只允许APPROVED、明确internal Simulation target和`publish` capability；Export不是ScheduleVersion transition。

same idempotency scope/key + same request只重放原logical result，不建立self-transition；不同request冲突。新current publication时，APPROVED→PUBLISHED与旧current PUBLISHED→SUPERSEDED必须在同一一致性边界完成。Production authority/target未知时default-deny。state enum、pair、terminal集合和`state-machines.v1` bytes均不变；persistence/application/API/UI证据继续`PLANNED`。
## TASK-P3-02 carrier alignment

`schedule-version.v1`只允许`DRAFT/READY_FOR_REVIEW/APPROVED/PUBLISHED/SUPERSEDED/REJECTED`，并通过conditional约束decision/publication/superseded reference的合法形状。Machine report逐项比对既有五个allowed pair，未新增self-transition或state。Production carrier不能表达PUBLISHED/SUPERSEDED；P3 publication evidence只接受`SIMULATION_INTERNAL`。

这些是serialization与precheck，不证明任何pair已由repository/application执行。Copy-on-write、CAS、transition、APPROVED-only publish和current supersession分别等待TASK-P3-03/04/06～08。

## TASK-P3-03 persistence primitive

`schedule_versions`按`data_plane + schedule_version_id`隔离保存creation bytes、当前carrier、content/immutable fingerprint与单调`state_revision`。数据库trigger禁止identity、revision、lineage、validation、content、parent、creator和creation bytes更新并禁止delete；repository只允许通过expected state + expected revision的CAS执行既有五个pair。PUBLISHED→SUPERSEDED只更新state metadata，PUBLISHED/SUPERSEDED的content仍逐字节不可变；self-transition和stale CAS均拒绝。

该primitive不决定capability、decision、APPROVED-only publish、supersession事务或fresh Validator，也不会创建DRAFT；这些仍属于P3-04/06～08 application。Schema、`state-machines.v1`及pair bytes保持不变，SQLite只提供测试证据，不等于Production concurrency。

## TASK-P3-04 formed transition

P3-04 application现以fresh P2 validation/KPI为事务前置门，insert immutable DRAFT后仅调用P3-03 CAS执行既有`DRAFT→READY_FOR_REVIEW`，随后在同一transaction追加`SUBMIT_FOR_REVIEW` audit。DRAFT和READY保持相同ID/revision/content/lineage/validation/creator/timestamps，仅state与state-derived `allowed_actions`变化；storage `state_revision`从0增至1。

Exact replay读取原creation bytes和当前READY carrier并返回原audit，不新增state self-pair；同key不同request、stale/mixed/failed validation、audit冲突和synthetic→Production plane均fail closed。READY仍只能等待P3-07的授权审批/驳回行为；本Task没有实现READY→APPROVED/REJECTED、APPROVED→PUBLISHED、PUBLISHED→SUPERSEDED或REJECTED revision。

## TASK-P3-06 copy-on-write creation

Move/Assign/Set/Remove Lock不是state transition：source在DRAFT、READY_FOR_REVIEW、REJECTED、APPROVED、PUBLISHED或SUPERSEDED下都不发生self-pair或content update；成功只insert具有new ID、parent source reference、revision+1、fresh validation及DRAFT state的新carrier。`MANUAL_EDIT`用于Move/Assign，`LOCK_CHANGE`用于Set/Remove Lock。Same key/same request只重放原DRAFT logical reference，不新增Version/audit；不同request冲突。

P3-03允许pair与`state-machines.v1` bytes没有变化，新DRAFT不自动执行DRAFT→READY_FOR_REVIEW。独立`SUBMIT_FOR_REVIEW`只接受本Task生成的manual/lock DRAFT，第二次fresh PASS且fingerprint一致后以CAS执行既有pair；只允许state与allowed actions改变，ID/content/content fingerprint/lineage/decision保持不变，audit失败则transition回滚。Failed candidate不保存为ScheduleVersion。TASK-P3-07/08仍分别拥有decision与publication state transition；PUBLISHED source仅可历史参考派生DRAFT，绝无原地更新。

## TASK-P3-07 executable decision transitions

本Task只执行既有`READY_FOR_REVIEW→APPROVED`与`READY_FOR_REVIEW→REJECTED`两对。Guard同时要求server-resolved exact capability/resource scope、Simulation test policy、Production default-deny、non-empty sanitized reason、expected READY/content fingerprint、decision/publication/superseded为空及state revision CAS。Candidate仅改变`state/decision/allowed_actions`；immutable projection、ID、revision、content/fingerprint、lineage/validation和created facts不变。成功CAS与一条append-only DECISION audit同事务，audit失败回滚；并发Approve/Reject最多一个winner。

Same key/same request从原audit返回READY→terminal logical reference，不新增self-pair或改写event；different request冲突。APPROVED的carrier actions为`view,publish`但P3-08尚未实现publish；REJECTED为terminal且只能由copy-on-write command派生新DRAFT。未新增state、pair或`state-machines.v1` bytes，PUBLISHED/SUPERSEDED仍未实现。

## TASK-P3-08 executable publication transitions

本Task只执行既有`APPROVED→PUBLISHED`与必要时旧current的`PUBLISHED→SUPERSEDED`。Guard要求server-resolved publish capability/resource scope、Simulation test policy、Production default-deny、exact state/content/current reference及state revision CAS。新candidate仅改变state/publication/allowed actions，旧candidate仅改变state/superseded_by/allowed actions；两者immutable content/decision/lineage/validation/creation facts保持不变。

两个CAS、PublicationResult、current reference CAS与PUBLICATION audit在同一事务，任一步失败回滚。Same request重放原APPROVED→PUBLISHED及optional supersession logical references，不执行self-pair或移动current；different request、DRAFT/READY/REJECTED、double publish与并发loser拒绝。没有新增state/pair或修改`state-machines.v1` bytes；PUBLISHED/SUPERSEDED内容仍不可变。

ExportJob只引用PUBLISHED Version reference；create/attempt/retry/fail/cancel/complete均不进入ScheduleVersion repository transaction。Export成功不是Publish，Export失败不会回滚或重开PUBLISHED；P3-09没有新增ScheduleVersion state/pair。

## TASK-P3-10 transport-only review

17个HTTP operation仅把path/query/header/body绑定到已有application operation，不在router中执行copy-on-write、DRAFT→READY、decision、publication/current或supersession。稳定state/stale失败只映射为409，不产生self-transition或新pair；ScheduleVersion state、pair、carrier bytes、migration和Schema零变化。
