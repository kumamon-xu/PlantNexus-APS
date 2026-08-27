---
doc_id: ADR-0015
title: Deterministic Execution Simulator Common-Path
status: accepted
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [47, 48, 49, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# ADR-0015 — Deterministic Execution Simulator Common-Path

Status: accepted

Date: 2026-08-27

Decision owners: PlantNexus APS repository governance；TASK-P4-01由repository owner明确授权

Requirement/NFR/ENG: REQ-008、REQ-009、REQ-012、REQ-013、REQ-014；NFR-COR-001、NFR-DET-001、NFR-TRC-001、NFR-ISO-001、NFR-SEC-001、NFR-OBS-001；ENG-ARCH-001、ENG-SOL-001、ENG-VAL-001、ENG-LOG-001、ENG-VER-001

Supersedes: none；落实ADR-0001、ADR-0002、ADR-0009、ADR-0013与ADR-0014

## Context

P0/P1已经决定Synthetic与Reference source共享标准导入入口，P2/P3形成deterministic Solver/Validator/Version/Workspace证据，但尚无Execution Simulator。P4 Dynamic Gate要求连续模拟Urgent Order、Machine Failure、Material Delay、Processing Delay和Early Completion，并检查Facts Preserved、Locks Preserved、Validator PASS和ChangeReport Complete。

若Simulator直接写fact、调用Solver私有方法或构造ScheduleVersion，会形成只在测试中通过的第二套业务路径；若使用wall clock/global RNG或未版本化概率，同一场景无法重放；若可在Production启用，则synthetic事件可能污染真实计划。真实工厂分布、事件频率、持续时间、capacity和SLA均未形成，本ADR不能补猜数值。

## Decision

### 1. Simulator只生成标准ExecutionEvent

Execution Simulator的唯一业务输出是ADR-0013定义的版本化ExecutionEvent stream。它不得直接创建/修改execution fact、PlanningSnapshot、PlanningProblem、ReplanRequest、PlanningRun、ScheduleVersion、ChangeReport、audit或publication。事件必须通过与未来Production adapter相同的application ingress port，依次经过ledger、authority/idempotency/order、fact projection、new Snapshot、ReplanRequest、Solver、fresh Validator和new DRAFT/ChangeReport路径。

共同路径要求以module/import/call-boundary test证明，不接受“字段相同但调用另一实现”的替代。Simulator可以拥有test-only orchestration和evidence collector，但不能复制projector、constraint、objective、Validator或ChangeReport公式。

### 2. 输入、clock、seed和identity全部版本化

一次Simulation run必须显式绑定：

```text
base PUBLISHED ScheduleVersion + base Snapshot/Problem fingerprints
Scenario/Profile/Generator/Simulator versions
explicit seed and named child-seed derivation
virtual-clock origin and deterministic event schedule
Simulation authority/source stream/version
data plane/environment/factory scope
policy/limits/freeze references
code/schema versions
```

Virtual clock是唯一事件时间来源；host wall clock只可记录run observation，不能进入event payload、ordering、identity或semantic hash。RNG必须从显式seed按稳定layer name派生，禁止module-global RNG和依赖调用顺序的隐式消费。

Event ID/fingerprint由run identity、simulator version、source stream、monotonic position、event type、virtual occurred-at、entity refs和payload的canonical bytes派生。相同全部输入必须得到byte-identical ordered event stream和相同下游semantic identities；任一版本/seed/scenario/policy变化必须产生不同run/event identity。

### 3. Replay、checkpoint与restart不增加业务状态机

Simulator checkpoint只是`run identity + last emitted source position + event stream prefix fingerprint`的可验证operational artifact，不是新业务state machine。Restart重新计算并核对prefix后从下一position继续；不匹配即拒绝。Same run/event replay由ADR-0013 exact replay规则吸收，不重复下游side effect。

取消或失败只停止继续发射事件并保存raw evidence；它不回滚已经合法投影的事实，也不删除Request/Run/DRAFT/Report。若场景需要从零重放，必须在fresh isolated Simulation run/database scope执行，而不是清除历史记录。

### 4. 五类异常采用连续而非独立快照测试

TASK-P4-10必须在同一versioned run中按显式position连续注入并消费前一步结果：

1. Urgent Order：增加可追踪的新需求事实；
2. Machine Failure：发出不可用事实，并在场景显式要求时发出独立recovery事件；
3. Material Delay：改变权威material-ready事实；
4. Processing Delay：改变RUNNING remaining/processing事实，不回写历史duration；
5. Early Completion：形成COMPLETED事实并保护actual resource/time。

每一步都必须从上一轮new Snapshot/current approved test baseline的明确引用继续，生成独立ReplanRequest/PlanningRun/new DRAFT/ChangeReport evidence；不得把五个case各自在干净进程中通过后宣称“continuous”。如何让DRAFT进入下一测试基线必须是显式Simulation harness policy，不得冒充真实approval或自动publish。

具体事件时间、duration、概率、资源、订单量和序列由P4-10的versioned Scenario/SIM_ASSUMPTION决定；TASK-P4-01不新增数值。

### 5. Gate保留raw与semantic双层证据

每次run至少保存并相互绑定：Scenario/Profile/Simulator/seed、virtual clock、ordered raw events及stream hash、ledger dispositions、fact/checkpoint/New Snapshot hashes、ReplanRequests、PlanningRuns/SolverReports、fresh ValidationReports、new DRAFTs、ChangeReports和per-step correlation/audit references。

P4 Gate必须重新执行而不是只读取stale报告，并验证：

- same-input replay的raw stream与semantic chain一致；
- facts、explicit HARD和freeze-derived locks保持；
- 每个candidate由fresh Validator PASS；
- 每个ChangeReport operation universe、KPI/OBJ-002算术和lineage完整；
- duplicate、conflict、gap、cross-plane、unknown version、stale base和partial failure均fail closed；
- raw timing/memory观察不进入semantic identity。

### 6. 隔离、安全与Production边界

Simulator只允许Development/Test/Benchmark + `SIMULATION` plane + synthetic provenance + `production_binding=false`，并使用与Production不同的database/credentials/namespace。普通Production app不得注册Simulator route/worker或读取Simulation authority；任何Production-shaped request在event产生前拒绝。

Scenario不得包含真实customer payload、credential、external endpoint或Production identity。Evidence/log按stable reference和fingerprint记录并redact。GitHub/local runner、test principal、synthetic event source与成功Gate都不是Production MES authority、deployment、capacity、SLA或UAT证据。

## Alternatives considered

### Simulator直接调用fact projector或Solver

拒绝。它绕过event contract/ledger/idempotency，使测试无法证明真实入口。

### 为每类异常编写独立fixture并在clean state运行

拒绝。它不能证明连续事实演进、stale base、历史锁与多次Replan lineage。

### 使用real-time sleep和默认随机数

拒绝。wall clock、scheduler jitter和global RNG破坏deterministic replay并拖慢Gate。

### 在Production部署Simulator但隐藏UI

拒绝。隐藏UI不是隔离；Production必须没有synthetic source/route/authority binding。

### 复用Simulation成功自动批准/发布每轮结果

拒绝。P4不得形成真实approval authority；test harness只能显式选择下一步基线并标记non-Production。

## Consequences

正面结果：Simulator证明的是同一入口和完整P4链，而非测试捷径；相同版本/seed可重放；连续异常暴露stale、ordering、fact/lock和ChangeReport问题；Production默认没有synthetic入口。

代价与限制：Gate需保存大量raw/derived artifact；连续场景比独立case复杂；restart必须核对prefix；没有Production分布时性能只作development regression；test harness基线推进不能解释为approval/publish。

Schema：TASK-P4-02发布Simulator run/checkpoint/event carrier或明确其internal machine contract；旧Scenario/Profile和P2/P3 Schema不改。Migration：none in TASK-P4-01；P4-03只实现共同event/replan持久化，Simulator不得建旁路表。Dependency：none；P4-09如需新依赖必须先扩卡并完成lock/SCA/license。State：无新business state machine。Tests：P4-09/10/14/15形成determinism/common-path/continuous replay；本Task全部保持PLANNED。Production/external/capacity/SLA均未形成。

## Rollback / Revisit gate

accepted ADR不得删除或原地改写。Simulator consumer形成前用superseding ADR修正；形成event/scenario/checkpoint版本后必须新增版本并保留旧stream可重放。回滚实现时禁用Simulator composition和新run创建，保留已有Simulation ledger、Snapshots、Requests、Runs、DRAFTs、Reports与evidence；不得删除它们来制造clean replay。

以下证据触发revisit：共同ingress无法表达某个必需事件；continuous scenario需要已批准的自动基线推进语义；checkpoint不足以恢复；需要distributed simulator或external event broker；或Production digital-twin需求获得独立授权。任何revisit都必须保留同入口、明确authority和Simulation/Production隔离。
