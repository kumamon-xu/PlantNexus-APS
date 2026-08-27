---
doc_id: MILESTONE-P4
title: P4 — Dynamic Replanning
status: active
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80]
last_reviewed: 2026-08-27
---

# P4 — Dynamic Replanning

## TASK-P4-04 active projection slice

TASK-P4-04已从P4-03 provider-verified closure `3563bb236ce7b2c01794485110d4945a6e265105`按独立用户授权启动。范围限于Simulation-only ExecutionEvent ingestion、连续ledger事实投影、新immutable Snapshot/checkpoint/audit和Urgent Demand标准Import/Validation共同入口；P4-05 freeze、P4-06 OBJ-002/ChangeReport、P4-07 Solver/Validator、P4-08 new DRAFT application及P4-09+ Simulator/API/UI均未启动。

当前4 unit + 2 property + 4 migration-backed integration为10项，连同application boundary和CI contract合计focused `12 passed`；完整Backend `654 passed`、Frontend 67 Vitest与三轮各12/12 Chromium、全部历史machine/P2/P3 Gate、SCA/license、Compose及双build均PASS。Machine 8/8为local PASS，全部11个event type、exact replay、ordering/terminal/reference/plane rejection、standard urgent与atomic rollback已有证据，但implementation provider仍pending，故Task保持`in_progress`。

## TASK-P4-03 completed persistence slice

TASK-P4-03已在provider-verified closure `7b9bfc3069de5d3738e5cc5827d27d197ed3d226`上按独立用户授权启动。它只实现additive `0005_replan_event_persistence`、Simulation plane-scoped ExecutionEvent ledger、projection checkpoint operational CAS、immutable ReplanRequest、request→PlanningRun attempt→terminal result references和append-only transaction audit；不新增ReplanRequest状态、不投影事实、不生成ChangeReport或new DRAFT。Implementation `60f8e8900ecab60f0d64311912ae27f09a4d002f` / artifact `9639720666` exact成功后，本closure把Task标为`done`；P4-04在该历史closure时保持`planned`，当前状态见上方active slice。

## TASK-P4-02 completed machine-contract slice

TASK-P4-02已从provider-verified P4-01 closure `4026597ab1015b5ea3a89d241f0d12b5b481dee3`独立启动。它只发布additive set `2.8.0`的九份P4 Simulation carrier、对应sample、纯语义precheck和non-skippable CI machine report；58份历史Schema/sample、migration `0004`、dependency lock和既有state pairs保持不变。Implementation `539cdbbdcdd406daba25b8d6b8caaa5133691e76` exact provider成功后，该closure将Task标为`done`；在该历史时点P4-03～15仍为`planned`，当前状态以上方P4-03 active slice为准。

## Activation

用户于2026-08-27在P3 Exit双提交provider与clean synchronized closure baseline精确通过后批准P3→P4。TASK-P4-00 phase-planning、TASK-P4-01 contract/ADR、TASK-P4-02 machine contract与TASK-P4-03 persistence均已按独立治理链登记为`done`。P4-04现按独立授权为`in_progress`，P4-05～15继续`planned`且不会自动启动，P4-15是最后一项独立Exit Gate Audit。

TASK-P4-01已形成accepted ADR-0013～0015：事件authority/append-only投影/Replan lineage，半开freeze/四元OBJ-002/完整ChangeReport，以及Simulator只经标准ExecutionEvent共同路径。当前只形成合同基线，机器carrier、Schema、migration、persistence、业务实现和行为测试均未形成。

## Outcome

实现 ExecutionEvent、ReplanRequest、Freeze Window、HARD/SOFT LOCK、OBJ-002、ChangeReport 和 Execution Simulator。

## Gate

连续模拟 Urgent Order、Machine Failure、Material Delay、Processing Delay、Early Completion；证明 facts/locks preserved、Validator PASS、ChangeReport complete，并比较重排前后 tardiness/stability。

生产 freeze window 由 OPEN-005 关闭；Simulation 值必须显式登记。

## Task allocation

| Task | Owner outcome | Depends on |
|---|---|---|
| TASK-P4-00 | Phase transition与完整规划治理 | P3-17 |
| TASK-P4-01 | Dynamic Replanning合同与accepted ADR-0013～0015（done） | P4-00 |
| TASK-P4-02 | ExecutionEvent/Replan/ChangeReport等机器合同（done） | P4-01 |
| TASK-P4-03 | Event/Replan持久化与状态事务（done） | P4-02 |
| TASK-P4-04 | ExecutionEvent→事实→新Snapshot（in progress） | P4-02/03 |
| TASK-P4-05 | Freeze Window与effective locks | P4-01/02/04 |
| TASK-P4-06 | OBJ-002 Stability与ChangeReport | P4-01/02 |
| TASK-P4-07 | Delivery→Stability→Makespan Solver/Validator | P4-04/05/06 |
| TASK-P4-08 | ReplanRequest应用与new DRAFT lineage | P4-03～07 |
| TASK-P4-09 | Deterministic Execution Simulator core | P4-02/04 |
| TASK-P4-10 | 五类连续disruption场景 | P4-05/08/09 |
| TASK-P4-11 | ChangeReport read/export integration | P4-06/08 |
| TASK-P4-12 | Dynamic Replanning HTTP API | P4-02/03/04/08/11 |
| TASK-P4-13 | Replanning Workspace UI/browser E2E | P4-09～12 |
| TASK-P4-14 | P4 Vertical Slice Gate | P4-01～13 |
| TASK-P4-15 | Independent P4 Exit Gate Audit | P4-14 |

P4 Gate必须连续而非单点地模拟Urgent Order、Machine Failure/Recovery、Material Delay、Processing Delay和Early Completion；每一步保存raw event/replan/change evidence并证明completed/running/HARD/freeze facts、independent Validator和ChangeReport completeness。TASK-P4-14的PASS不替代P4-15 fresh independent audit。

## P4/P5/Production boundary

P4不得引入secondary resource、batching、sequence setup、tool/fixture capacity、多Factory、替代工艺、rolling/decomposed/hybrid strategy等P5 advanced capabilities。真实Production freeze、priority/KPI authority、identity/approval角色、external adapter/target、deployment/UAT、容量和SLA继续由OPEN项阻塞；Simulation policy/scenario/actor/API/UI证据不得外推Production。
