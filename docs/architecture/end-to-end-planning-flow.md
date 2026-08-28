---
doc_id: DOC-ARCH-002
title: 端到端计划链路
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 9, 10, 23, 24, 30, 32, 33, 35, 57, 67]
last_reviewed: 2026-08-28
---

# 端到端计划链路

## TASK-P4-11 read/export continuation

当前P4链路可在P4-08 durable apply之后执行两条只读/输出分支：`applied result + exact ScheduleVersion → authorized ChangeReport query → stable page`，以及`already-PUBLISHED P4 ScheduleVersion + exact ChangeReport + verified P3 compatibility package → ExportJob claim → deterministic v3 package → EXPORTED-only verified download`。两条分支都复验Solver/Validation/KPI/report lineage，均不重新求解或推进Replan/Schedule state。

Export不调用Publish；P4-08 DRAFT到PUBLISHED的authority流程仍必须由既有独立控制提供。HTTP/API、UI和browser E2E分别归P4-12/13，P5 advanced planning及Production external integration不在本链路中。

## TASK-P4-10 continuous composition edge

当前Simulation链可由一个versioned run连续执行五个step：`Scenario step → P4-09 canonical Event delta → P4-04 fact/new Snapshot owner → ReplanRequest → P4-08 application/P4-07 solve → fresh Validator → new DRAFT + complete ChangeReport → explicit non-Production next baseline`。每个箭头保存exact IDs/fingerprints，step 2～5必须消费前一步Schedule/Snapshot/Problem reference；任一缺口停止后续chain。

最后一箭头只是test harness baseline advance，明确无authority且不执行READY/APPROVE/PUBLISH/EXPORT。P4-11 read/export、P4-12 API、P4-13 UI、P4-14/15 Gate/Audit仍是独立后继。

## TASK-P4-09 event-source prefix

动态链新增一个严格前缀而不改变既有Planning路径：`PUBLISHED ScheduleVersion + exact Snapshot/Problem refs + Scenario/Profile/Generator/Simulator versions + seed + EventSchedule + VirtualClock → canonical ExecutionEvent prefix → P4-04 ingest_event`。Simulator在入口前完成完整prefix校验；每个event仍由P4-04 ledger/fact事务处理。

本Task在此停止。Fact/new Snapshot→ReplanRequest→P4-08 application、fresh Validator、new DRAFT与ChangeReport均不由Simulator直接调用；P4-10才编排连续五类场景，且仍不得自动approve/publish/export。

## TASK-P4-08 formed application edge

端到端链现扩展为`exact current PUBLISHED base + immutable ReplanRequest/attempt → stored new Snapshot → deterministic Problem rebuild → P4-05 effective locks → P4-07 global lexicographic solve → fresh independent validation → P4-06 complete ChangeReport → atomic new DRAFT ScheduleVersion v2/result envelope/result audit`。Intent与result application保持两个事务；第二个事务在写入前重新读取current/base/request/attempt/Snapshot并重建Problem，任何stale或lineage漂移均无DRAFT/result副作用。

Same request/key完成后直接从durable Solver/Validation/KPI/ChangeReport envelope返回exact logical result，不再次求解；不同key/content冲突。该链严格停在DRAFT，不触发READY/approval/publish/export/API/UI/Simulator，P4-09+、P5与Production均未进入。

## TASK-P4-07 formed solve edge

端到端纯计算链现到达`ReplanRequest/projection/base assignments/new Problem → one global C-001～C-011 model → OBJ-001 → OBJ-002.1～.4 → OBJ-003 → fresh validation → solver-report.v2`。每一箭头保留exact fingerprint/provenance，candidate只在当前轮fresh PASS后才能锁值并继续。链路在持久化前停止；new DRAFT、final ChangeReport和Request result transaction仍由TASK-P4-08形成。

## TASK-P4-05 formed freeze projection edge

当前形成的新增纯链路为`event-derived immutable Snapshot → exact PlanningProblem v2`与`base PUBLISHED ScheduleVersion + PlanningPolicy v2 → effective-lock-projection.v1 → independent freeze precheck`。该edge输出facts/HARD/freeze/SOFT的完整solver-neutral输入，不进入CP-SAT、不写Replan repository、不生成candidate/ChangeReport/new DRAFT；后续仍由P4-06/07/08分别承接稳定性、求解验证与应用事务。

## TASK-P4-04 formed flow edge

当前已形成的唯一新执行边为`validated Simulation ExecutionEvent → ledger+audit → complete ordered prefix → pure canonical fact projection → new immutable PlanningSnapshot → checkpoint+audit`。Urgent分支在projection前插入既有`Raw Staging → Normalization → Data Validation → Expansion → Snapshot candidate`，随后回到同一projector；无旁路。流程到此停止，不生成ReplanRequest/Problem/Solution/ChangeReport/ScheduleVersion，也不调用Simulator、API、UI或external adapter。


## TASK-P4-03 formed storage edge

链路中`ExecutionEvent durable ledger → projection checkpoint/ReplanRequest transaction → PlanningRun attempt/result references`的存储边已形成；这只证明append/replay/conflict/CAS/rollback/lineage。`event → business fact → new Snapshot/Problem`仍未执行，result references不生成SolverReport/Validation/ChangeReport/ScheduleVersion；因此后续箭头仍分别由P4-04～08实现并需独立授权。

## TASK-P4-02 contract-only flow

机器lineage现可表达`ExecutionEvent → fact checkpoint/new Snapshot/new Problem → ReplanRequest → SolverReport/fresh Validation → ScheduleVersion v2 + ChangeReport → internal export`，但本Task只验证document links与fingerprints，箭头均不执行。P4-03～11分别拥有transaction、projection、freeze/stability/solve/apply/export，任何步骤失败不得从sample推断partial business success。

## TASK-P4-01 accepted end-to-end extension

ADR-0013～0015已固定受控反馈链：versioned authoritative ExecutionEvent→append-only ledger→deterministic fact revision/new Snapshot/ReplanRequest→freeze/effective locks→Delivery/Stability/Makespan Solver→fresh independent Validator→atomic new DRAFT ScheduleVersion+complete ChangeReport。接收、projection和result application是三个明确可重放事务边界；base PUBLISHED与历史artifact不改。

TASK-P4-03～08分别拥有持久化/投影/freeze/stability/solve/apply，P4-09/10只能通过同一event/application入口重放Simulation，P4-12/13只提供transport/UI。ReplanRequest无独立state，Simulator无业务state；当前没有实现或启用任何节点，P4-02仍是下一独立启动门。

## TASK-P3-17 audit conclusion

完整P3链`validated PlanningSolution→immutable DRAFT→read/comparison→command/new DRAFT→approval/rejection→internal publish/supersession→ExportJob/package→HTTP/UI`已由两次Backend Gate及独立machine/tests复验PASS。链路终止于内部Simulation工作区；ExecutionEvent/Replan/P4与Production side effect未进入。

## TASK-P3-14 aggregated flow Gate

P3-14现已获单独授权，并在一个fail-closed report中两次重放`validated P2 solution → immutable DRAFT → read/compare → command/new DRAFT → approve/reject → publish → ExportJob/package → API/UI`。18个Backend stage execution、两轮12-spec Chromium和P2 Gate regression的raw证据均保留，stable semantic projection必须唯一；最终TASK-P3-17 Exit Audit仍未执行。

## TASK-P3-13 human-control edge

当前bounded链为`authoritative read → state/capability-sensitive UI → canonical workspace-command.v1 → authorized HTTP/application → existing validation/state service → authoritative Version/Job refresh`。Browser不直连repository、不生成domain state、不调用Solver/Validator；PUBLISHED成果包下载为`authorize → EXPORTED Job → verified package directory → deterministic ZIP`只读支路。任何error/unknown outcome都回到authority refresh，不靠client rollback伪造事实。

该edge完成P3 human-control consumer；其P3-14 vertical Gate、TASK-P3-16本地化与TASK-P3-17 Exit Audit均为`done`，P3-17 audit implementation与closure provider均已exact验证。本地化只可在API/UI边缘把英文machine value映射为`zh-CN/en-US` label并保留raw，不得进入domain/application链。ExecutionEvent→Replan、OBJ-002/freeze/ChangeReport现属于已激活但尚未实现的P4计划；真实identity、external publish/download、deployment与Production readiness均不在链内。

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

P2 Exit已provider-verified并关闭；P3在其后追加`validated solution → immutable DRAFT → read/compare → command validation → new DRAFT → approve/reject → idempotent publish → ExportJob/package → API/UI`。P3-01先固定合同/ADR，P3-02～13分层实现，P3-14负责vertical Gate，P3-15负责计划修订治理，P3-16计划增加display-only双语，P3-17最终独立Audit。该链不回写P2 artifacts，不允许localized label污染machine value，也不包含P4 Execution/Replan或Production external side effect。

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

## TASK-P3-07 decision segment

当前新增控制段为：`workspace-command APPROVE|REJECT + server authenticated/capability/resource/test-policy context → authorization before source/result lookup → exact READY/content precondition → one transaction(CAS same ScheduleVersion state+decision + append DECISION audit) → stable logical result`。Exact replay读取原event；different fingerprint冲突；并发两种decision只有一个CAS winner；audit失败回滚state。高风险DENY只写无resource reference的sanitized event。

该段不修改content或上游PlanningRun/Snapshot/Problem/Solution/Validation/KPI/SolverReport，不调用Solver/Validator，不创建新Version、PublicationResult或ExportJob。APPROVED只到P3-08 publish前置，REJECTED只允许后续copy-on-write revision；HTTP/UI、真实RBAC/SSO、P4和Production side effect均未形成。

## TASK-P3-08 internal publication segment

当前新增控制段为：`PUBLISH command + server publish context → authorization before audit/source/current lookup → exact APPROVED/content/current preconditions → one transaction(new APPROVED→PUBLISHED CAS + optional old PUBLISHED→SUPERSEDED CAS + PUBLICATION audit + PublicationResult + current CAS) → stable logical result`。Same request从历史audit重建result；different request/double publish/stale current冲突；并发只有一个current winner；任一持久化失败回滚全部state。

该段不改Schedule content或上游PlanningRun/Snapshot/Problem/Solution/Validation/KPI/SolverReport，不调用Solver/Validator，也不创建ExportJob/文件包/HTTP/UI/external side effect。Target严格是`SIMULATION_INTERNAL`，Production pre-lookup default-deny；P3-09、P4与Production未形成。

P3-09在publication之后增加独立支路：authorized request→durable CREATED+audit→worker claim/lease→冻结P2 payload与PUBLISHED/publication lineage校验→deterministic JSON/CSV/XLSX→manifest-last atomic materialization→EXPORTED+audit。任何package/I/O/transaction失败进入FAILED并显式retry；全程不反向调用Publish、不改PlanningRun/ScheduleVersion，也无external transfer。

## TASK-P3-10 HTTP composition edge

HTTP入口现固定为`request → strict carrier/path/header binding → server authorization → PlanningWorkspaceApplicationPort → sanitized response`。Router不跨过application直达domain/repository/Solver/Validator；Production在principal provider或application lookup前拒绝。该edge不改变Import→Planning→Version→Decision→Publication→Export的authority链，不引入Frontend、external adapter或P4 replan/execution支路。
