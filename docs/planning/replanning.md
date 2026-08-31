---
doc_id: DOC-PLAN-008
title: 动态重排设计合同
status: baseline
spec_version: 0.3.0
phase: P0-P5
normative: true
source_sections: [21, 28, 35, 47, 48, 49, 50, 79, 80]
last_reviewed: 2026-08-31
---

# 动态重排设计合同

## TASK-P5-21 frozen P4 regression

P5 Gate不修改动态重排，而是在自己的PHASE_GATE中独立重放P4-02～12全部公开owner两轮。报告继续要求ExecutionEvent→fact/Snapshot、ReplanRequest/attempt、freeze/HARD、OBJ-002 Stability、fresh Validator、new DRAFT、complete ChangeReport和Simulator five-disruption语义稳定；合计22 stages、10 steps、16 events、10次Validator和10份ChangeReport。

Selected P5 owner数为0，所以没有P5约束与P4重排的组合写入。Gate不推进approval/publish/export状态，不是P5 Exit，不自动启动P5-22或Production。

## TASK-P4-15 independent Exit audit

P4 Exit Audit从P4-14 closure重新执行全部owner contracts、P2/P3/P4 Gates和五类连续异常，而不复用聚合PASS。41个提交/42个provider run/67个artifact的exact拓扑、required app、expiry、digest和机器内容一致；fresh P4 Gate仍为两轮14/14、10步、16 event、10次fresh Validator、10份complete ChangeReport及唯一业务语义fingerprint，`blocking_gaps=[]`。因此P4范围的本地Exit判定为READY。

READY只说明已批准的Simulation/development动态重排切片可复验；它不授权P4→P5，不把OBJ-002或synthetic disruption外推为Production policy，也不形成真实event/approval authority、external publish、UAT、deployment、capacity或SLA。

## TASK-P4-14 aggregate validation boundary

P4 Vertical Slice Gate现以两轮fresh replay聚合P4-02～12全部公开owner报告，并连续复验Urgent Order、Machine Failure/Recovery、Material Delay、Processing Delay和Early Completion。每一步都保留前序baseline、标准ExecutionEvent、new Snapshot/Problem、ReplanRequest/attempt、fresh Validator、new DRAFT与complete ChangeReport；facts/HARD/freeze locks、before/after tardiness及四分量Stability必须跨两轮形成相同业务语义投影。

四类负向边界固定为tamper/coverage/plane fail closed、Production authority default deny、P5 unsupported及partial result不能推进state。Gate只聚合冻结owner，不修合同、公式、state pair或expected；PASS也不等于Exit READY，TASK-P4-15必须独立审计且不会自动启动。

## TASK-P4-13 reviewable workspace consumer

动态重排链现在可通过一个Simulation/development-only页面复核，但所有事实仍由server owner提供。UI严格消费event timeline、Request/attempt/result与ChangeReport read projection，显示freeze、tardiness和Stability而不重新计算；只有完整`COMPLETED → new DRAFT + ChangeReport`证据才呈现result。任何mixed lineage、fingerprint drift、unknown enum或缺失字段都整体fail closed。

Cancel/retry只表达PlanningRun attempt intent，采用server `allowed_actions`、expected state及same-key query-before-retry。页面不控制Execution Simulator、不创建ReplanRequest state、不自动approve/publish/export，也不形成P4-14 Gate、P5优化或Production event/approval/external authority。

## TASK-P4-12 transport entry and read boundary

Dynamic Replanning现有一个Simulation-only HTTP入口：标准ExecutionEvent通过append port，完整ReplanRequest通过P4-08 facade，ChangeReport通过P4-11 read authority。Transport只绑定carrier/query/action、correlation、idempotency reference、capability/scope和expected attempt state，不重建Problem、freeze、OBJ-002、Solver/Validator或new DRAFT。Cancel/retry始终指向PlanningRun attempt，不创建ReplanRequest self-transition。

## TASK-P4-10 continuous scenario consumer

五类disruption现由versioned Simulation scenario orchestrator连续组合：每个step绑定标准ExecutionEvent delta、前一步明确Schedule/Snapshot baseline、new Snapshot/Problem、独立ReplanRequest/PlanningRun、fresh Validator、new DRAFT和complete ChangeReport。该Task只验证既有P4-04～09公共链的连续消费，不修改Delivery→Stability→Makespan公式、freeze/effective-lock规则、Replan persistence或ScheduleVersion状态机。

Test harness把刚形成DRAFT内容显式重绑定为下一步`SIMULATION_NON_PRODUCTION` baseline并声明无authority；这不是自动approval/publication，也不能用于Production。HTTP/read/export/UI仍分别归P4-11～13。

## TASK-P4-08 atomic result application

动态重排计算链现可在Simulation中应用：先原子记录Request/attempt/audit，再读取exact current PUBLISHED base和stored new Snapshot、按冻结参数重建Problem、投影effective locks、执行P4-07 solve与fresh validator、核对after KPI、构建并独立precheck complete ChangeReport；最后在另一事务重读全部关键lineage并原子提交new DRAFT/result envelope/result audit。

Same request/key已完成时直接返回durable full-artifact replay，不重复solve；different key/content、stale current、concurrent loser或任何validation/report/persistence问题fail closed。Base不原地修改，result不自动进入review/approval/publication/export。P4-09/10 Simulator/scenario、P4-11 output、P5和Production仍未形成。

## TASK-P4-07 solve and validation slice

当前纯链路扩展为`verified ReplanRequest + new Problem + effective locks + base PUBLISHED assignments → global six-round CP-SAT → fresh candidate validation per round → solver-report.v2/raw evidence`。facts/HARD/freeze在每轮保持同一约束域，base只作Hint，prior objective value逐项等式冻结；candidate必须同时通过formal schedule、facts/locks、objectives与complete change-universe复算。

链路仍在application transaction之前终止：不提交new ScheduleVersion、ChangeReport、Request result或audit，不消费连续disruption simulator。TASK-P4-08负责atomic application，P4-09/10负责Simulator/replay。

## TASK-P4-06 stability/reporting slice

Freeze/effective-lock准备之后，纯calculator现可对给定base/candidate assignments构造完整immutable ChangeReport，并由不导入builder、reporting calculator、Solver或formal Validator的precheck独立复算operation全集、分类、delta、SOFT violations、exact ratio、reasons/facts、KPI refs和identity。相同输入byte-exact replay；missing/duplicate universe、缺失completion fact、跨plane、reason/KPI/lineage或fingerprint mismatch均fail closed且无副作用。

本切片不创建PlanningRun、不调用CP-SAT或fresh C-001～C-011 Validator、不写ReplanRequest result/new DRAFT/audit，也不export或运行Simulator。P4-07仍拥有lexicographic solve/fresh Validator，P4-08拥有原子result application；因此当前ChangeReport是可验证的构建能力，不是已应用的动态重排结果。

## TASK-P4-05 freeze preparation slice

P4-04产生的event-derived new Snapshot现在可与exact Problem、base PUBLISHED Version和`SIM-P4-FREEZE-001@1.0.0`组合，生成完整可引用的effective-lock projection及独立PASS/FAIL precheck。该步骤只完成Replan solve前的事实/锁/freeze准备；不创建ReplanRequest result/PlanningRun、不调用Solver/fresh candidate Validator、不计算ChangeReport，也不提交new DRAFT。冲突、stale、cross-plane或缺失authority均保持明确blocked input而非UNKNOWN/INFEASIBLE伪装。

## TASK-P4-04 fact projection slice

P4-04把已持久化ExecutionEvent连续prefix解释为effective canonical facts并生成new immutable Snapshot/checkpoint；它只完成Replan链的事实准备阶段。Same input可byte-exact replay，gap/late/conflict/stale/terminal regression/cross-plane均fail closed，错误事实只能由后续补偿event和新Snapshot纠正，禁止改写ledger或历史Snapshot。Freeze resolution、OBJ-002、ReplanRequest、lexicographic solve、fresh Validator、ChangeReport和new DRAFT仍未执行。


## TASK-P4-03 persistence slice

P4-03只把P4-02 carrier落入plane-scoped durable primitives：ExecutionEvent按authority/source stream/version/event ID、position与canonical fingerprint append/exact replay；projection checkpoint只通过strict CAS前进；ReplanRequest必须先引用已持久化checkpoint及同一有序ledger事件；attempt/result继续引用PlanningRun既有状态，ReplanRequest自身无状态机；audit为versioned append-only record。Caller可在单一事务中组合这些原语并在失败时完整rollback。

本切片不解释event payload、不写fact revision或Snapshot、不计算freeze/OBJ-002/ChangeReport、不调用Solver/Validator/Simulator，也不创建new DRAFT。P4-04才拥有事实投影；P4-08才拥有结果应用。SQLite migration/repository测试仅为Simulation/development证据，不形成Production数据库、external exactly-once或capacity/SLA。

## TASK-P4-02 machine-contract slice

ExecutionEvent v1、ReplanRequest v1、Policy v2、SolverReport v2、ChangeReport v1与ScheduleVersion v2现可离线组成exact lineage bundle。Freeze resolution固定半开区间，Request无状态，ChangeReport覆盖完整operation universe，new Version仍只能是后继Task创建的DRAFT。本Task不持久化、投影、求解、验证或应用，因此动态重排行为仍未形成。

## TASK-P4-01 contract activation

用户已单独授权TASK-P4-01；ADR-0013～0015及一致的人类合同现已形成。P4-02仍须先发布机器合同，P4-03～08再依次拥有persistence、event facts、freeze/locks、OBJ-002/ChangeReport、Solver/Validator与new DRAFT application，P4-09/10形成deterministic Simulator与五类连续异常，P4-11～13形成read/export、API与UI，P4-14/15分别Gate/Audit。除合同/ADR外所有P4行为仍为`PLANNED_NOT_FORMED`，P4-02不会自动启动。

## TASK-P3-17 phase boundary

P3 Exit READY只覆盖Planning Workspace；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport和Execution Simulator仍属于P4且未实现。详细Task现已由TASK-P4-00规划，但每张仍需新的明确授权。任何P3编辑仍是显式command→new DRAFT，不是dynamic replan。

## TASK-P3-16 localization / P4 boundary

双语展示只本地化现有P3 workspace术语，没有新增ExecutionEvent、ReplanRequest、freeze window、OBJ-002、ChangeReport、Execution Simulator或任何P4 route/action。中文“移动/重新分配/锁定”仍只是P3 copy-on-write command label，不是dynamic replan。TASK-P3-16 implementation已取得exact provider；TASK-P3-17最终审计没有自动进入P4，当前P4仅因后续明确授权进入规划状态。

## TASK-P3-14 boundary Gate

P3 Gate只重放P3 copy-on-write manual command与publication链，并证明PUBLISHED不能原地mutation；它不消费ExecutionEvent、不生成ReplanRequest/ChangeReport、不实现freeze/OBJ-002或ExecutionSimulator。最终TASK-P3-17已完成本地独立审计并等待provider闭环，P4只有另行phase transition授权后才能启动。

## TASK-P3-13 P3/P4 boundary review

Gantt drag/move/assign/lock是对单一immutable ScheduleVersion的人工command proposal，经既有P3-06 fresh Validator产生new DRAFT；它不读取ExecutionEvent、不生成ReplanRequest、不计算freeze window/OBJ-002/Stability/ChangeReport，也不调用Solver。UI的“refresh authority”仅重读Version/Job，不是replan trigger。

P3-14已完成有界Gate，P3-15已完成修订治理，P3-16已完成双语实现双提交provider复验；P3-17独立Audit implementation与closure均已exact provider验证，Exit=`READY`。P4 dynamic replanning现仅激活并完成Task规划，尚无业务实现；PUBLISHED immutable且rollback只能以新Version/command表达，不能修改执行事实或历史发布。

## 输入

ReplanRequest 引用 base ScheduleVersion、新 PlanningSnapshot、reason 和 freeze window。执行事实必须先进入权威事实层和新 Snapshot，不能作为 Solver 的临时隐藏参数。

ADR-0013要求同时绑定base content fingerprint/base Snapshot、ordered event/fact references、freeze policy/resolved interval、Policy/Limits、plane/scope/correlation/request fingerprint。ReplanRequest无独立state；每次attempt使用PlanningRun。Ledger接收与fact/Snapshot/Request projection为两个可重放事务，result application再以独立事务原子写new DRAFT、ChangeReport、result和audit。

## 约束与目标

1. COMPLETED 保持不变；
2. RUNNING resource 与历史事实保持不变，未来剩余占用固定；
3. HARD_LOCK 保持不变；
4. SOFT_LOCK/旧计划变化通过 OBJ-002 计价；
5. 旧计划可作为 Hint，但 Hint 不保证稳定；
6. Delivery 优先于 Stability，Makespan 最后；
7. 结果必须经过同一独立 Validator。

## ChangeReport

至少比较：changed operation count、resource changes、start shifts、lock/fact preservation、before/after tardiness 和不可避免变化原因。报告引用 base/new version 和两个 Snapshot/Problem hash。

Operation universe必须恰好一次分类为UNCHANGED、CHANGED、ADDED或有明确COMPLETED证据的REMOVED_BY_FACT。指标、before/after、facts/HARD/freeze/SOFT、fresh Validator、events/request/policy/solver/code lineage必须可独立复算；missing/duplicate/mismatch阻断new DRAFT。无法证明具体因果时使用显式unattributed reason，不得用自由文本补猜。

## Dynamic Gate

Execution Simulator 连续注入 Urgent Order、Machine Failure、Material Delay、Processing Delay、Early Completion，检查 Facts Preserved、Locks Preserved、Validator PASS 和 ChangeReport Complete。

freeze window 的生产语义由 OPEN-005 决定；仿真值必须标记 SIM_ASSUMPTION。

## TASK-P2-07 static fact/lock boundary

本Task只在单次immutable Problem求解中保护COMPLETED/RUNNING facts与HARD lock；SOFT lock只保留metadata reference。它不接收ExecutionEvent，不生成ReplanRequest/ChangeReport，不执行freeze window或稳定性目标，也不改变ScheduleVersion。

因此C-007/C-008 correctness不能声明动态Replan已形成。P4事件幂等、事实演进、lock policy与change comparison仍须独立Task/Scenario/ADR证据；OPEN-005及现有SIM assumptions保持不变。

## P3/P4 boundary

P3 version comparison只比较两个immutable ScheduleVersion的既有assignment/KPI/lineage；Gantt edit/lock是人工新DRAFT命令，不是ExecutionEvent驱动的Replan。ExecutionEvent、ReplanRequest、freeze、OBJ-002 stability、ChangeReport和Execution Simulator全部继续属于P4，P3 Task/Schema/API/UI不得预埋可执行P4语义。

## TASK-P3-06 enforced P3/P4 boundary

形成的Move/Assign/Lock及manual review-submit service仅消费一个immutable Problem和source Version，不读ExecutionEvent、不构建Problem/Snapshot、不调用Solver，也不计算freeze window、OBJ-002或ChangeReport。SOFT lock仍是metadata，HARD lock只保护Version tuple；READY只表示通过fresh review gate，不是执行态或Replan结果。Machine report固定`solver_replan_obj002=NOT_IMPLEMENTED`和`p4_capabilities=NOT_IMPLEMENTED`；这些边界不得因“人工重排”名称而解释为动态Replan。
