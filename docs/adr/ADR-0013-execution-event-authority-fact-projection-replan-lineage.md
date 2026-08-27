---
doc_id: ADR-0013
title: ExecutionEvent 权威、事实投影与 Replan Lineage
status: accepted
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# ADR-0013 — ExecutionEvent 权威、事实投影与 Replan Lineage

Status: accepted

Date: 2026-08-27

Decision owners: PlantNexus APS repository governance；TASK-P4-01由repository owner明确授权

Requirement/NFR/ENG: REQ-004、REQ-005、REQ-007、REQ-008、REQ-009；NFR-COR-001、NFR-DET-001、NFR-TRC-001、NFR-ISO-001、NFR-SEC-001；ENG-ARCH-001、ENG-SOL-001、ENG-VAL-001、ENG-ERR-001、ENG-VER-001

Supersedes: none；落实ADR-0002、ADR-0005、ADR-0007、ADR-0009与ADR-0012的P4边界

## Context

P3已经形成不可变ScheduleVersion、APPROVED-only internal publication、copy-on-write人工command、append-only audit和Production default-deny，但没有ExecutionEvent、权威事实演进、ReplanRequest或动态求解。P4若在机器合同前不先固定权威、顺序和事务边界，会出现以下不可接受结果：

- transport收到时间被误当作业务顺序，重复、乱序或缺口事件产生不同事实；
- event、fact、Snapshot或Solver私有参数形成多套真相；
- 同一请求通过retry产生多个Snapshot、PlanningRun或ScheduleVersion；
- PUBLISHED版本被事件直接改写，或新计划被自动批准/发布；
- Simulation synthetic source被误作真实MES authority；
- 为ReplanRequest发明第二套生命周期，与既有PlanningRun状态机竞争。

真实MES/ERP event authority、source sequence、字段mapping、identity与Production binding仍受OPEN-002、OPEN-007、OPEN-010、OPEN-013和OPEN-015约束。TASK-P4-01只能确定authority-neutral、Simulation可验证且Production fail-closed的语义，不发布Schema、migration或实现。

## Decision

### 1. ExecutionEvent是唯一动态事实入口，不是Schedule mutation

P4动态输入必须先表达为版本化ExecutionEvent。Event至少具有显式data plane/environment、factory/planning scope、authority/source stream及version、source event identity、单调source position、业务发生UTC时间、entity references、event type/payload、canonical fingerprint、correlation和synthetic provenance。接收时间只属于transport/audit，不参与业务排序或内容identity。

P4支持的事件语义只限Milestone要求的operation start/completion、machine unavailable/recovery、material readiness/delay、processing duration/remaining变化、urgent demand输入，以及由已授权planning policy产生的lock create/release。具体字段、URN、版本、枚举和negative interchange由TASK-P4-02发布；未知版本、未知类型、缺失authority、跨plane、无效引用或无法完整表达的事件必须在任何事实副作用前拒绝。

Event不得直接UPDATE ScheduleVersion、PlanningProblem或Solver模型。所有消费者只能读取ledger中的已验证事件并通过同一事实投影边界形成新Snapshot。

### 2. Production authority缺失时默认拒绝

一个planning scope在一个projection epoch中只允许一个已批准的权威source stream。Production必须由外部治理明确绑定principal/system、factory scope、source version、position contract和允许event types；当前这些事实未形成，因此Production event ingress固定DENY。AI、UI、HTTP body、数据库owner、Simulation fixture或代码默认均不是authority。

Development/Test/Benchmark可以使用名称和provenance均明确的Simulation event authority，且必须`production_binding=false`、`SIMULATION` plane、synthetic source和隔离数据库。该test authority不关闭任何PROD_OPEN，也不能外推为MES contract。

### 3. Ledger、identity、ordering与重复处理

Event identity scope固定为`data plane + factory/planning scope + source stream/version + source event identity`，request fingerprint覆盖除接收时间和self identity外的全部权威语义。处理规则为：

- same identity + same fingerprint：exact replay，返回原ledger/projection logical result，不重复fact、Snapshot、ReplanRequest、audit或solve；
- same identity + different fingerprint：conflict，禁止last-write-wins；
- next source position：可进入确定性projection；
- position gap：保留可审计的接收事实但projection保持blocked，直到缺口补齐或出现经版本化治理批准的superseding source epoch；
- position不大于已投影position：late/conflicting input，禁止重写历史projection；需要纠正时必须使用显式、可追踪的更正/新epoch合同，不能DELETE或UPDATE旧event；
- received-at、线程顺序、数据库自增ID或wall clock不得决定业务顺序。

P4不支持同一事实字段的多个并行权威writer。若Production需要跨stream merge、vector clock或来源优先级，必须先提交新ADR与机器合同，不能在P4实现中隐式选择。

### 4. 接收与投影采用两个可重放事务边界

Ingress transaction只负责contract/authority/idempotency验证、append-only ledger记录和安全audit disposition；它不写业务事实。成功接收不等于事实已经生效。

Projection transaction按连续source position读取一个显式event或确定性event batch，重新验证其fingerprint和前序checkpoint，并原子提交：

```text
append-only fact revision / effective fact set
+ new immutable PlanningSnapshot
+ immutable ReplanRequest
+ projection checkpoint/result
+ append-only audit references
```

任一reference、authority、semantic、conflict或persistence错误都不得留下partial fact、Snapshot或ReplanRequest。Ledger中的原始接收记录保留为真实失败证据；纠正通过新attempt/result或新event完成，不改写旧记录。相同projection input必须返回相同fact/Snapshot/Request identity。

### 5. 事实投影是确定性、不可变和版本化的

Projector显式记录projector/version、上一个fact checkpoint、ordered event identities/fingerprints、base Snapshot、rule/source versions和canonicalization。COMPLETED、RUNNING、machine availability、material readiness和processing fact都以append-only revision表达；相互矛盾或从终态倒退的事实fail closed，不以“最新到达”覆盖。

每次有效事实变化产生新PlanningSnapshot；旧Snapshot及其引用的Problem、PlanningRun和ScheduleVersion保持可读不可变。Projector不得把事件作为Solver隐藏参数，也不得通过直接修改旧Snapshot来节省空间。

### 6. ReplanRequest是immutable envelope，不拥有独立状态机

ReplanRequest必须绑定base PUBLISHED ScheduleVersion及其content fingerprint、base/new Snapshot、ordered triggering event/fact references、reason、resolved freeze policy/reference、Planning Policy/Solve Limits references、plane/scope、correlation和request fingerprint。一个request表示一个确定性projection batch；任何coalescing/debounce window都必须是显式版本化policy，不提供隐式默认。

ReplanRequest不增加业务state或transition pair。每次计算attempt由既有PlanningRun状态机承载，request/result/audit以append-only reference关联一个或多个attempt。Retry创建或重放明确attempt；不得用ReplanRequest自环伪装幂等。TASK-P4-03只可持久化request、checkpoint、attempt/result/idempotency关系，不能新增未批准状态机。

### 7. Solve、fresh Validator与new DRAFT保持分层

Application只能在事实投影提交后，以new Snapshot构建new PlanningProblem并调用P4 lexicographic strategy。Candidate无论Solver status如何都必须经过独立fresh ScheduleValidator；UNKNOWN不是INFEASIBLE，partial/invalid candidate不得形成ScheduleVersion。

Result-application transaction必须重新读取并核对request/base current reference、base content fingerprint、new Snapshot/Problem、PlanningRun attempt、Policy/Limits、fresh ValidationReport和ChangeReport完整性，然后原子提交new `DRAFT` ScheduleVersion、ChangeReport、request result和append-only audit。Base PUBLISHED和所有历史Version绝不修改；new DRAFT不自动READY、APPROVED、PUBLISHED、export或external publish。

若base current reference已变化、事实checkpoint已被新请求取代或任何fingerprint不匹配，结果以stale/conflict失败，不把过期candidate应用为新Version。

### 8. Error、observability与安全边界

机器error namespace/version由TASK-P4-02决定，但责任层必须保持：contract/authority/order/reference错误在projection前拒绝；stale/idempotency冲突无副作用；Solver INFEASIBLE与UNKNOWN分离；Validator失败不生成Version；persistence/audit失败整体回滚。日志只记录stable references、position、fingerprint、stage、duration和correlation，不记录token、credential、raw payload全文、SQL或stack；日志不替代durable ledger/audit。

## Alternatives considered

### 直接把ExecutionEvent传给Solver

拒绝。它绕过canonical facts/Snapshot，导致Problem无法重放且不同入口产生不同约束。

### 收到事件后原地修改current PUBLISHED ScheduleVersion

拒绝。它违反ADR-0007/0012并破坏approval、publication与audit历史。

### 使用received-at或数据库自增ID排序

拒绝。网络延迟和并发会使相同source事件产生不同事实；业务顺序必须来自权威source position。

### 为ReplanRequest新增QUEUED/RUNNING/SUCCEEDED状态机

拒绝。计算生命周期已经由PlanningRun表达；第二套状态会产生冲突pair和双重authority。Request只保存immutable intent、attempt与result lineage。

### 宣称exactly-once外部delivery

拒绝。P4只形成durable idempotency和exact logical replay；外部network、outbox、connector与authority尚未形成。

## Consequences

正面结果：event到Version的每一层都有唯一authority、identity、顺序、transaction和rollback；重复/乱序/冲突可审计且不会重写历史；Simulation与未来Production共享同一入口而不共享authority；现有PlanningRun与ScheduleVersion状态机保持唯一。

代价与限制：source必须提供可验证position；gap会阻断projection；late correction需要显式新event/epoch；ledger与fact/Snapshot/request会增加append-only存储；P4-03必须实现严格unique/CAS/checkpoint/transaction；P4-08必须在应用candidate前重新核对全部lineage。

Schema：TASK-P4-02必须发布新document versions，不能修改P2/P3 bytes。Migration：TASK-P4-03实现ledger/fact/request/checkpoint/result/audit persistence，但不得用DDL默认反向定义合同。Dependency：none。State：ReplanRequest无独立状态机，既有pair不变。Test：P4-02～04/08覆盖contract、ordering、replay、rollback、stale与new DRAFT lineage；所有P4 Test ID在本Task仍为PLANNED。Production/external/capacity/SLA均未形成。

## Rollback / Revisit gate

accepted ADR不得删除或原地改写。机器consumer形成前如发现矛盾，只能提交有界superseding ADR；形成Schema/DB后必须发布新version和migration。回滚实现时停止新ingress/projector，保留ledger、facts、Snapshots、Requests、Runs、Versions与audit为只读历史；未应用candidate可丢弃，已形成DRAFT只能通过新Version/显式状态动作处理。

以下证据触发revisit：Production source无法提供单调position；同scope必须支持多个权威writer；需要event correction/supersession machine state；需要outbox/external exactly-once；现有PlanningRun无法表达attempt；或要求改变ScheduleVersion pair。任何revisit都不得把Simulation authority或received-at提升为Production事实。
