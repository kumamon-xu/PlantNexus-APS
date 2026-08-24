---
doc_id: DOC-ARCH-002
title: 端到端计划链路
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 9, 10, 23, 24, 30, 32, 33, 35, 57, 67]
last_reviewed: 2026-08-24
---

# 端到端计划链路

```text
Versioned Input Package
→ Raw Staging
→ Normalization
→ Data Validation
→ immutable PlanningSnapshot
→ deterministic PlanningProblem
→ PlanningStrategy
→ SolverBackend
→ PlanningSolution
→ independent ScheduleValidator
→ DRAFT ScheduleVersion
→ READY_FOR_REVIEW
→ Human APPROVED
→ PUBLISHED
→ MES / Export Package
→ Execution Facts & Disruptions
→ new Snapshot / ReplanRequest
→ new ScheduleVersion
```

## 关键门

| 门 | 输入 | 通过条件 | 失败语义 |
|---|---|---|---|
| Import | 外部/仿真输入包 | 合同、单位和引用完整 | DATA_ERROR / DATA_REJECTED |
| Snapshot | 规范化数据 | immutable、hashable、provenance 完整 | MODEL_INVALID 或系统错误 |
| Problem | Snapshot + rules | deterministic、serializable、solver-neutral | MODEL_INVALID |
| Solve | Problem + Policy + Limits | 合法 Solver 状态与候选解 | INFEASIBLE / NO_SOLUTION_WITHIN_LIMIT / FAILED |
| Verify | PlanningSolution | C-001～C-011 全部独立验证 | VALIDATION_FAILED |
| Review | 已验证 ScheduleVersion | 人工批准 | REJECTED 或保留评审状态 |
| Publish | APPROVED version | 幂等、审计、不可变 | Publish/Export 明确失败状态 |

## Replan

Replan 不修改旧 ScheduleVersion。它使用旧版本、执行事实、新 Snapshot、冻结窗口和原因生成新版本，并输出 ChangeReport。旧计划 Hint 只帮助搜索，不能替代 HARD_LOCK 或稳定性目标。

## P1 implementation status

TASK-P1-03/04已形成Raw Staging与ReferenceFileAdapter；TASK-P1-05形成`RawImportRow → explicit MappingProfile/unit registry → canonical Import v2 bytes/hash`；TASK-P1-06形成canonical structure/reference/DAG/resource/capability/time/duration Data Validation与deterministic ImportQualityReport。Import门只有报告PASS/0 errors才通过，四类Gate问题使用exact DATA_ERROR，unsupported capability保持独立category。

TASK-P1-07只在matching PASS report之后，以`order-expansion.v1`把source-explicit DemandOrder/ProductionOrder/Lot/Routing确定性展开为OperationInstance与逐lot precedence edge，并保留candidate duration/source、fact/lock和versioned lineage；该Task本身止于纯Order Expansion输出，不创建Snapshot、Problem或Solver。任何consumer不得从Adapter/Raw/Normalization或FAIL report绕过Data Validation进入Expansion，也不得把Expansion hash当作Snapshot/Problem hash；P0/P2 ScheduleValidator仍只验证candidate schedule，与本输入Gate不同。

TASK-P1-08现把该链路推进到immutable PlanningSnapshot v2：builder验证content-derived Import、matching PASS report与self-consistent Expansion，形成stable bytes/hash/ID和strict entity counts；plane-scoped repository以insert/exact replay/read及DB mutation trigger保留不可变事实。Snapshot Gate的stale package、FAIL、provenance mismatch、invalid cutoff、content conflict和Production/Synthetic混用均明确拒绝。

当前端到端实现边界止于已持久化Snapshot；PlanningProblem、PlanningStrategy、Solver、candidate ScheduleValidator、ScheduleVersion与发布仍未创建。P1-09只能从本Snapshot合同继续构建solver-neutral Problem，不能绕回上游或把Expansion/dataset hash冒充Snapshot hash。

## TASK-P1-11 executable common ingress

当前已形成一条单一application调用链：`StagedImportBatch → normalize_import → validate_import_package(PASS) → expand_orders → build_planning_snapshot → build_planning_problem`。Synthetic Generator和ReferenceFileAdapter只在Raw Staging前不同，之后使用同一`CommonIngressPipeline.run()`。固定Scenario两次重放与reference parity均得到Import `24a74b…`、Snapshot `090e0e…`、Problem `71c0b7…`。

数据质量FAIL和Normalization首错均在所属stage终止，不会调用后续builder。链路到PlanningProblem终止；Solve、Verify、ScheduleVersion、Publish、Export、Execution/Replan仍是后续Phase边界。

## TASK-P2-01 handoff

P2的第一段现在固定为`verified PlanningSnapshot v2 + explicit versioned priority facts → build_planning_problem_v2 → immutable planning-problem.v2`。v2 output包含DeliveryDemand、complete primary Resource facts、active OperationInstances、HistoricalCompletionAnchors、precedence edges、active locks、calendar intervals与required platform capabilities；机器report同时重放v1默认路径。

该handoff终止于verified Problem。Application common ingress尚未切换默认v2，PlanningPolicy/SolveLimits/Solution、Backend/Strategy、ScheduleValidator、KPI/Export/Benchmark均未调用；这些只能从P2-02起按依赖链逐Task接入。

## TASK-P2-13 vertical-slice Gate orchestration

`app.application.p2_gate_report`现只通过P2-09/P2-12/P2-11公开machine boundaries聚合`Snapshot → PlanningProblem v2 → PlanningPolicy/SolveLimits → GlobalCpSatStrategy → independent Validator → KPI/SolverReport → p2-internal-export.v1`。每个完整replay依次运行七类correctness、XS/S/M Global+五Reference与独立output contract；本地`repeat=2`形成14个correctness scenario executions、6个benchmark profile executions、108个benchmark Validator passes、8个显式/嵌入Export executions及四类fail-closed边界，11/11 checks PASS。

该入口是无状态、in-process、Simulation-only验收编排，不创建PlanningRun/ScheduleVersion/ExportJob，不连接API/DB/Worker/queue，也不批准或发布。`p2-vertical-slice-report.v1`保留每次完整子报告、timing/memory/hash/export evidence，并只对排除generated/timing的versioned业务语义投影要求跨replay一致；P2-14才可独立审计Exit。

Implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的required run `32465737712` / artifact `9440650646`已精确复现该完整链与两次replay，Gate 11/11且0 blocking gap。该provider证据仍明确Exit=`NOT_PERFORMED`，只满足P2-14启动依赖。

## P3 planned continuation

P2 Exit已provider-verified并关闭；P3在其后追加`validated solution → immutable DRAFT → read/compare → command validation → new DRAFT → approve/reject → idempotent publish → ExportJob/package → API/UI`。P3-01先固定合同/ADR，P3-02～13分层实现，P3-14/15分别负责vertical Gate与独立Audit。该链不回写P2 artifacts，也不包含P4 Execution/Replan或Production external side effect。

## TASK-P3-01 flow contract

P3先行合同现把链固定为`P2 validated immutable inputs → ScheduleVersion copy-on-write → versioned read/query → server command/precondition → fresh Validator → new DRAFT → capability/state decision → internal idempotent publication/current/supersession → independent ExportJob/package → API/UI consumer`。每个箭头都必须保留plane、fingerprint、correlation、idempotency和append-only audit lineage；UI/router/worker没有旁路。

TASK-P3-01仅形成文档和ADR-0012；Schema/persistence/application/API/UI节点仍未落地。链在ExportJob/internal artifact处终止，不进入P4 Execution/Replan，也不连接Production external target。

## TASK-P3-04 formed application segment

当前已形成的新增段为：`completed PlanningRun fact + frozen P2 bundle → build_kpi_v2(fresh formal Validator) → pure ScheduleVersion documents → one DB transaction(insert DRAFT → CAS READY_FOR_REVIEW → append SUBMIT_FOR_REVIEW audit)`。任何input/lineage/KPI错误在transaction前停止；任一repository/audit错误使整个本次transaction回滚。

该段不回写PlanningRun、不调用Solver、不经过API/Frontend/Worker，也不越过READY_FOR_REVIEW。Read model/comparison仍由P3-05，edit/lock新DRAFT由P3-06，approval/rejection由P3-07，publish/export由P3-08/09；P4 Execution/Replan与Production external target仍不在流中。

## TASK-P3-05 formed read segment

当前新增只读段为：`workspace-query REQUEST + exact Version precondition + seven immutable source documents + plane-scoped schedule/audit repository → lineage binding → pure view projection → stable filter/sort/cursor page → workspace-query RESULT`；comparison再显式读取第二个Version/reference并输出fingerprinted P3 comparison DTO。查询前后ScheduleVersion/Audit row count不变，product service Solver调用为0。

该段没有HTTP/UI、command、new DRAFT、state transition、Validator重算、approval/publish/export或P4。P3-10只能包装该application boundary，P3-06+ write flow不得复用read DTO作为写权威。

## TASK-P3-06 formed command segment

当前新增写段为：`workspace-command + server capability/plane/precondition/idempotency guard + immutable source Version/Problem → copy-on-write assignment/lock candidate → new independent ProblemScheduleValidator → PASS/0 → one transaction(insert new DRAFT + append command AuditEvent) → stable logical result`。MOVE/ASSIGN与SET/REMOVE Lock均走同一pipeline；manual DRAFT可再以显式`SUBMIT_FOR_REVIEW → second fresh Validator PASS → one transaction(CAS existing DRAFT→READY_FOR_REVIEW + append audit)`进入既有评审态，ID/content/fingerprint不变。Same key/same fingerprint从durable audit/new Version重放，conflict/Validator/audit失败不留下成功副作用。

四类content command不回写source、PlanningRun、Problem或Snapshot；submit只改变其目标manual DRAFT的state/allowed actions，不改变content/lineage/identity。该段不调用Solver/KPI optimizer，不隐式submit或自动approval，也没有HTTP/UI、approval/rejection、publication/export或P4。Failed candidate在内存丢弃；历史REJECTED/PUBLISHED只可作为parent参考派生DRAFT。
