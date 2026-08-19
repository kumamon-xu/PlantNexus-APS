# PlantNexus APS 模块 Vibe Coding 开发技术框架与实施规格

```yaml
title: PlantNexus APS 模块 Vibe Coding 开发技术框架与实施规格
spec_version: 0.3.0
status: implementation_ready
target_release: factory_aps_v1
factory_scope: single_factory_multi_workshop
development_mode: simulation_first
primary_solver: google_or_tools_cp_sat
canonical_duration_unit: second
solver_time_unit: configurable_tick
source_of_truth: true
```

> 本文面向 Codex、Claude Code、Cursor、OpenCode 等 AI Coding Agent。
>
> 本文不是产品宣传材料，也不是算法概念设计，而是项目实施阶段的最高级技术规格。
>
> 所有代码、数据库、Schema、接口、测试、仿真环境、求解模型与发布流程不得违反本文中的 MUST / MUST NOT 规则。

---

# 0. 文档目标

本项目建设一个面向单工厂、多车间、多产线、多设备的通用 APS 模块。

系统需要形成完整闭环：

```text
业务数据
    ↓
Import / Normalization
    ↓
PlanningSnapshot
    ↓
PlanningProblem
    ↓
PlanningStrategy
    ↓
SolverBackend
    ↓
PlanningSolution
    ↓
ScheduleValidator
    ↓
ScheduleVersion
    ↓
人工审批
    ↓
MES / 文件发布
    ↓
执行事实与异常
    ↓
Replan
```

当前开发阶段没有可直接使用的真实工厂 APS 历史环境。

因此本项目采用：

> **Simulation-First APS Development**

即在真实工厂数据进入项目之前，先建立受控、可重复、可扩展的虚拟工厂、生产场景、异常事件和性能基准体系。

仿真环境不能代替真实工厂验收，但必须能够提前发现：

- 数据模型缺陷；
- 约束遗漏；
- 求解器规模问题；
- 重排不稳定问题；
- 架构无法承载未来 APS 能力的问题；
- Vibe Coding Agent 对业务规则的错误假设。

---

# 1. 规范级别

## 1.1 规范语言

- **MUST / 必须**：不可违反。
- **MUST NOT / 禁止**：任何实现不得出现。
- **SHOULD / 应当**：默认执行；偏离必须提交 ADR。
- **MAY / 可以**：可选能力。
- **DECIDED**：已经确定，不允许 Coding Agent 自行修改。
- **CONFIG**：配置项，必须有明确默认行为。
- **PROD_OPEN**：真实生产业务问题尚未确认。
- **SIM_ASSUMPTION**：仅用于仿真的显式假设。
- **DEFERRED**：明确延迟实施。
- **UNSUPPORTED**：系统能够识别，但当前版本禁止近似实现。

---

# 2. Vibe Coding Agent 执行规则

## 2.1 首次初始化仓库

Coding Agent MUST：

1. 完整读取本文件。
2. 创建 `AGENTS.md`。
3. 创建项目目录。
4. 创建 P0 文档和任务卡。
5. 创建 Schema 骨架。
6. 创建 Simulation 骨架。
7. 创建最小 Golden Fixture。
8. 登记所有 PROD_OPEN。
9. 不得实现 P1 以后能力。
10. 不得接入真实 APS 求解逻辑。

---

## 2.2 日常任务读取顺序

仓库初始化完成后，每个任务禁止机械重复读取整份大型规格。

读取顺序 MUST 为：

```text
AGENTS.md
↓
docs/current_phase.md
↓
当前 TASK
↓
TASK 引用的 Schema
↓
TASK 引用的 Constraint
↓
TASK 引用的 ADR
↓
相关代码
↓
相关测试
```

以下情况必须重新完整读取本规格：

- `spec_version` 变化；
- 当前任务涉及架构边界；
- 修改 Constraint Catalog；
- 修改 PlanningProblem；
- 修改 SolverBackend；
- 修改状态机；
- 修改发布规则；
- 修改阶段退出门。

---

# 3. 产品目标

V1 建设一个覆盖单工厂多个车间的统一 APS 模块，能够自动：

1. 从 ERP、MES、WMS、CAM 或标准文件读取数据；
2. 执行数据规范化和质量校验；
3. 生成不可变 PlanningSnapshot；
4. 将订单展开为生产批和 OperationInstance；
5. 完成跨车间设备级排程；
6. 独立验证所有硬约束；
7. 输出甘特数据、KPI、诊断和标准成果包；
8. 由计划员审批；
9. 发布到 MES 或标准接口；
10. 根据插单、缺料、设备故障和进度偏差生成新的计划草案。

---

# 4. V1 成功定义

V1 不以：

- 秒级排程；
- 全局最优；
- 无人审批；
- AI 自动决策；

作为成功标准。

V1 MUST 满足：

### Correctness

所有进入 `READY_FOR_REVIEW` 的 ScheduleVersion：

```text
hard_violation_count == 0
```

### Feasibility

代表性仿真数据集必须能够在配置的计算预算中获得业务可用方案。

### Traceability

结果必须能够追溯：

```text
Snapshot
Rule Version
PlanningProblem Version
Solver Version
Solver Parameters
Simulation Scenario（若适用）
Generator Version（若适用）
Code Commit
```

### Human Control

计划员可以：

- 查看；
- 比较；
- 锁定；
- 驳回；
- 批准；
- 发布；
- 回滚到历史版本参考状态。

### Interoperability

结果至少可以输出：

- JSON；
- CSV；
- Excel；
- MES Adapter。

---

# 5. 核心需求注册表

| ID | Requirement |
|---|---|
| REQ-001 | 自动读取版本化计划输入 |
| REQ-002 | 数据标准化、单位转换和不可变快照 |
| REQ-003 | 订单、批次和工序实例展开 |
| REQ-004 | 单 PlanningRun 跨车间排程 |
| REQ-005 | 独立硬约束验证 |
| REQ-006 | 标准成果包输出 |
| REQ-007 | ScheduleVersion、审批、锁定和发布 |
| REQ-008 | 异常重排 |
| REQ-009 | 全链路 Provenance |
| REQ-010 | AI 工时预测扩展接口 |
| REQ-011 | Synthetic Factory Generator |
| REQ-012 | Scenario Library |
| REQ-013 | Execution / Disruption Simulator |
| REQ-014 | Benchmark Harness |
| REQ-015 | Reference Scheduler Baseline |

---

# 6. 需求追踪规则

生产代码允许以三类追踪根开始：

```text
REQ
NFR
ENG
```

追踪链：

```text
REQ / NFR / ENG
       ↓
SCHEMA / ARCH / CONSTRAINT
       ↓
TASK
       ↓
TEST
       ↓
ARTIFACT
```

例如：

```text
NFR-OBS-001
→ ENG-LOG-001
→ TASK-P0-08
→ TEST-OBS-001
```

不再要求 CI、日志、监控等工程设施强行对应业务 REQ。

---

# 7. V1 范围

## 7.1 支持

- 单工厂；
- 多车间；
- 多产线；
- 多设备；
- Flexible Job Shop；
- DAG 工艺；
- 跨车间工艺；
- 候选设备；
- 不同设备不同工时；
- 单设备容量 1；
- 班次；
- 休息；
- 维护；
- 停机；
- release time；
- material_ready_at；
- 已完成任务；
- 已开工任务；
- HARD_LOCK；
- SOFT_LOCK；
- 计划版本；
- 审批；
- 发布；
- Replan。

---

## 7.2 V1 不支持

- 多工厂网络优化；
- 自动 MRP；
- 完整库存流；
- 替代料优化；
- 自动采购；
- 强化学习排程；
- 数字孪生；
- APS + CAM 套料联合优化；
- 自动发布；
- LLM 自动修改约束；
- LLM 自动修改业务权重。

---

# 8. Future Capability Registry

以下能力不允许 Coding Agent 通过“简单逻辑”偷偷近似。

| Capability | V1 |
|---|---|
| SECONDARY_CAPACITY | UNSUPPORTED |
| SEQUENCE_DEPENDENT_SETUP | UNSUPPORTED |
| BATCH_PROCESSING | UNSUPPORTED |
| SPLIT_MERGE | UNSUPPORTED |
| MATERIAL_COMPETITION | UNSUPPORTED |
| PREEMPTIVE_OPERATION | UNSUPPORTED |
| BUFFER_CAPACITY | UNSUPPORTED |
| ALTERNATIVE_MATERIAL | UNSUPPORTED |
| MULTI_FACTORY | UNSUPPORTED |

系统遇到要求这些能力的 Scenario 时 MUST 返回：

```text
UNSUPPORTED_CAPABILITY
```

禁止静默忽略。

---

# 9. 总体架构

```text
                    ┌────────────────────┐
ERP / MES / WMS ───▶│ Input Adapter      │
Excel / CSV / CAM    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ Raw Staging        │
                    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ Normalization      │
                    │ Data Validation    │
                    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ PlanningSnapshot   │
                    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ PlanningProblem    │
                    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ PlanningStrategy   │
                    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ SolverBackend      │
                    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ PlanningSolution   │
                    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ ScheduleValidator  │
                    └─────────┬──────────┘
                               ↓
                    ┌────────────────────┐
                    │ ScheduleVersion    │
                    └────────────────────┘
```

---

# 10. Simulation-First 双通道架构

仿真环境必须进入与生产数据相同的数据入口。

```text
Synthetic Factory Generator
          ↓
Scenario Package
          ↓
Standard Import Contract
          ↓
Normalization
          ↓
PlanningSnapshot
          ↓
PlanningProblem
```

禁止：

```text
Simulator
→ 直接构造 CpModel
```

禁止：

```text
Simulator
→ 绕过数据校验
```

禁止：

```text
Simulator
→ 调用特殊简化 Solver
```

这保证仿真验证的是：

> **真实产品链路，而不是测试专用链路。**

---

# 11. 推荐技术栈

## Backend

- Python 3.12
- uv
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic
- PostgreSQL
- Redis
- Celery
- Google OR-Tools CP-SAT
- Polars
- openpyxl
- structlog
- OpenTelemetry

OR-Tools MUST：

```text
固定精确版本
写入 uv.lock
写入 solver_report
```

升级必须跑完整 benchmark replay。

---

## Frontend

- React
- TypeScript
- Ant Design
- TanStack Query
- 虚拟滚动 Gantt
- Playwright

---

## Testing

- pytest
- Hypothesis
- Ruff
- Pyright 或 mypy
- Playwright
- Contract Test
- Golden Test
- Property Test
- Benchmark Regression

---

# 12. 模块边界

V1 使用 Modular Monolith。

```text
FastAPI Application
PostgreSQL
Redis
Solver Worker
React Frontend
```

Solver MUST 与 API Process 分离。

禁止在：

- API Controller；
- React Component；
- ORM Model；

中出现 CP-SAT 建模逻辑。

---

# 13. SolverBackend

领域层不得依赖 OR-Tools。

```python
class SolverBackend(Protocol):
    def solve(
        self,
        problem: PlanningProblem,
        policy: PlanningPolicy,
        limits: SolveLimits,
    ) -> PlanningSolution:
        ...
```

OR-Tools 对象只能出现在：

```text
planning/backends/cp_sat/
```

---

# 14. PlanningStrategy

V1 默认：

```text
GlobalCpSatStrategy
```

即一个 PlanningRun 对 PlanningSnapshot 中的全部 V1 OperationInstance 统一建模。

未来允许：

```text
DecomposedStrategy
RollingHorizonStrategy
HybridStrategy
```

但必须经过 ADR 和 benchmark。

---

# 15. 数据权威边界

| 数据 | Authority |
|---|---|
| Order | ERP |
| BOM | ERP |
| Purchase Promise | ERP |
| Execution | MES |
| Machine Runtime State | MES |
| Physical Inventory | WMS |
| CAM Processing Feature | CAM |
| Planning Decision | APS |

AI 不是业务权威来源。

AI 只能预测：

```text
duration
risk
confidence
```

不能改变：

```text
routing
resource compatibility
hard constraint
schedule state
```

---

# 16. 时间标准

数据库：

```text
TIMESTAMPTZ
UTC
```

显示：

```text
factory_timezone
```

持续时间：

```text
duration_seconds: integer
```

Solver：

```text
duration_ticks =
ceil(duration_seconds / tick_seconds)
```

默认：

```text
tick_seconds = 60
```

SIM 可以配置 timezone。

Production 如果 `factory_timezone` 未确认：

```text
BLOCK_PRODUCTION
```

而不是阻止开发环境启动。

---

# 17. 工厂领域模型

```text
Factory
 └ Workshop
    └ ProductionLine
       └ ResourceGroup
          └ Resource
```

Resource 包含：

```text
id
code
type
status
group
calendar
capabilities
```

---

# 18. 工艺领域模型

```text
Product
RoutingVersion
RoutingOperation
RoutingPrecedenceEdge
RoutingResourceOption
```

Routing 必须是 DAG。

禁止仅依赖：

```text
sequence_no
```

表达工艺关系。

支持：

- 串行；
- 并行；
- 汇合；
- 跨车间。

---

# 19. OperationInstance

Solver 排的对象必须是：

```text
OperationInstance
```

而不是：

```text
RoutingOperation
```

订单展开：

```text
DemandOrder
→ ProductionOrder
→ ProductionLot
→ OperationInstance
```

---

# 20. Resource Option

每个 OperationInstance 可以拥有：

```text
OperationResourceOption[]
```

包含：

```text
resource_id
setup_seconds
cycle_seconds_per_unit
final_duration_seconds
duration_source
source_version
```

不同设备速度不同必须生成不同：

```text
final_duration_seconds
```

---

# 21. 运行中任务

RUNNING Operation 必须保留：

```text
actual_start_at
resource_id
remaining_quantity
remaining_seconds
```

Solver 的未来占用从：

```text
horizon_start
```

开始表达剩余资源占用。

实际历史开始时间作为执行事实保留，不要求重新排入未来时间域。

Validator 必须确认：

- Resource 未变化；
- Remaining duration 正确；
- Future occupancy 正确。

---

# 22. Material Boundary

V1 不做完整库存平衡。

输入：

```text
material_ready_at
```

Solver 只执行：

```text
operation.start >= material_ready_at
```

未来如果上游无法提供该字段，应通过：

```text
MaterialReadinessProvider
```

扩展。

禁止 Solver 自己猜库存齐套时间。

---

# 23. PlanningSnapshot

PlanningSnapshot MUST：

- immutable；
- deterministic；
- replayable；
- hashable。

包含：

```text
snapshot_id
cutoff_at
source_versions
rule_version
snapshot_hash
entity_counts
synthetic
scenario_id
```

生产：

```text
synthetic = false
```

仿真：

```text
synthetic = true
```

---

# 24. PlanningProblem

PlanningProblem 必须：

- 可序列化；
- Solver-neutral；
- 无 OR-Tools 类型；
- deterministic。

核心结构：

```json
{
  "problem_version": "planning-problem.v1",
  "snapshot_id": "uuid",
  "tick_seconds": 60,
  "horizon_start_utc": "...",
  "horizon_end_utc": "...",
  "operation_instances": [],
  "precedence_edges": [],
  "resource_unavailable_intervals": []
}
```

同输入、同规则版本必须产生相同：

```text
problem_hash
```

---

# 25. V1 CP-SAT 决策变量

主要变量：

```text
operation_start
operation_end
resource_presence
optional_interval
tardiness
schedule_change_amount
```

对于一个 Operation：

```text
Operation i
Candidate Resource r1
Candidate Resource r2
Candidate Resource r3
```

创建：

```text
presence[i,r]
interval[i,r]
```

必须满足：

```text
ExactlyOne(presence[i,*])
```

每个候选设备使用自身 duration。

---

# 26. V1 Constraint Catalog

## C-001 必排完整性

每个未完成 OperationInstance：

```text
exactly one resource
exactly one scheduled interval
```

---

## C-002 工艺时间关系

对于 precedence：

```text
successor.start >= predecessor.end + min_lag
```

如果存在：

```text
max_lag
```

则必须同时满足：

```text
successor.start <= predecessor.end + max_lag
```

禁止 Schema 存储 max_lag 但 Solver 忽略。

---

## C-003 候选设备唯一选择

```text
sum(presence) == 1
```

---

## C-004 单机互斥

Capacity=1 Resource：

```text
NoOverlap
```

---

## C-005 设备日历

维护、班外、停机等不可用区间以固定 interval 加入资源 NoOverlap。

非抢占任务：

```text
不得跨不可用区间
```

---

## C-006 Release Gate

```text
start >= order_release_at
start >= material_ready_at
```

---

## C-007 Execution Facts

COMPLETED：

```text
不进入未来排程
```

RUNNING：

```text
resource fixed
execution history preserved
remaining occupancy fixed from horizon start
```

---

## C-008 Lock

HARD_LOCK：

```text
resource fixed
start fixed
end fixed
```

SOFT_LOCK：

通过稳定性目标表达。

---

## C-009 跨车间衔接

```text
successor.start >= predecessor.end + transport_lag
```

---

## C-010 工时一致性

```text
end - start
==
selected_resource.final_duration_ticks
```

---

## C-011 Planning Horizon

NOT_STARTED Operation：

```text
start >= horizon_start
end <= horizon_end
```

禁止静默截断任务。

---

# 27. Deferred Constraints

```text
C-012 Secondary Capacity
C-013 Sequence Dependent Setup
C-014 Material Balance
C-015 Batch Processing
C-016 Split / Merge
C-017 Buffer Capacity
C-018 Preemption
```

每个高级能力必须独立提交：

```text
ADR
Schema
Capability Contract
Solver Implementation
Validator Implementation
Positive Fixture
Negative Fixture
Benchmark
Feature Flag
```

---

# 28. Objective Policy

目标禁止通过：

```text
0.6 / 0.3 / 0.1
```

随意混权。

采用词典序分轮。

---

## OBJ-001 Delivery

优先：

```text
minimize weighted tardiness
```

---

## OBJ-002 Stability

Replan 时：

```text
minimize schedule movement
```

包括：

```text
resource change
start time deviation
operation movement
```

---

## OBJ-003 Makespan

仅在：

```text
delivery equal
stability equal
```

时作为 tie breaker。

---

# 29. 求解状态

| Solver Status | Product Meaning |
|---|---|
| OPTIMAL | 已证明达到当前模型的最优标准 |
| FEASIBLE | 当前最好可行方案 |
| INFEASIBLE | 当前快照+当前模型被证明无解 |
| UNKNOWN | 时间内没有可认证结论 |
| MODEL_INVALID | 模型或系统缺陷 |
| CANCELLED | 用户或系统取消 |
| FAILED | 系统异常 |

UNKNOWN MUST 映射：

```text
NO_SOLUTION_WITHIN_LIMIT
```

禁止解释为 INFEASIBLE。

---

# 30. 独立 ScheduleValidator

Validator：

```text
MUST NOT import CpSatBackend
MUST NOT reuse CP-SAT constraints
MUST NOT trust solver status
```

Validator 必须独立检查：

```text
C-001 ~ C-011
```

并输出：

```text
constraint_id
severity
entity_ids
observed_value
expected_rule
message
```

---

# 31. Validator Mutation Tests

系统必须人工伪造错误计划，包括：

```text
machine overlap
wrong resource
wrong duration
wrong precedence
calendar overlap
lock movement
material early start
cross workshop lag violation
missing operation
duplicate operation
```

Validator 必须全部拒绝。

---

# 32. PlanningRun 状态机

PlanningRun 只描述计算生命周期。

```text
CREATED
↓
INGESTING
↓
VALIDATING
↓
SNAPSHOTTED
↓
BUILDING
↓
SOLVING
↓
SOLVED
↓
VERIFYING
↓
COMPLETED
```

失败：

```text
DATA_REJECTED
MODEL_INVALID
INFEASIBLE
NO_SOLUTION_WITHIN_LIMIT
VALIDATION_FAILED
CANCELLED
FAILED
```

PlanningRun 不包含：

```text
APPROVED
PUBLISHED
SUPERSEDED
```

---

# 33. ScheduleVersion 状态机

```text
DRAFT
↓
READY_FOR_REVIEW
↓
APPROVED
↓
PUBLISHED
↓
SUPERSEDED
```

允许：

```text
READY_FOR_REVIEW
→ REJECTED
```

REJECTED 可以：

```text
→ 新 ScheduleVersion
```

禁止修改 PUBLISHED Version。

---

# 34. ExportJob 状态机

```text
CREATED
↓
EXPORTING
↓
EXPORTED
```

异常：

```text
EXPORT_FAILED
CANCELLED
```

ExportJob 必须：

- 幂等；
- 可重试；
- 有 audit trail。

---

# 35. Replan

Replan 输入：

```text
base_schedule_version_id
new_snapshot_id
replan_reason
freeze_window
```

必须：

1. 保留完成事实；
2. 保留运行中事实；
3. 保留 HARD_LOCK；
4. 对 SOFT_LOCK 增加变化成本；
5. 使用旧计划 Hint；
6. 不依赖 Hint 保证稳定；
7. 生成 ChangeReport。

---

# 36. KPI Contract

必须新增：

```text
schemas/json/kpi.schema.json
docs/10-kpi-definition.md
```

核心 KPI：

### Delivery

```text
on_time_order_ratio
total_tardiness_seconds
weighted_tardiness
late_order_count
```

### Planning

```text
makespan_seconds
scheduled_operation_count
unscheduled_operation_count
```

### Resource

```text
available_seconds
planned_busy_seconds
utilization
```

利用率必须使用：

```text
planned_busy / available_calendar_time
```

而不是完整自然时间。

### Stability

```text
changed_operation_count
resource_changed_count
start_shift_seconds
schedule_stability_ratio
```

### Solver

```text
model_build_time
first_feasible_time
solve_time
objective
best_bound
relative_gap
variables
constraints
optional_intervals
memory_peak
```

---

# 37. Simulation 子系统目标

Simulation 不模拟真实物理设备。

它模拟：

```text
APS Planning Reality
```

即：

- 工厂结构；
- 订单；
- 工艺；
- 设备；
- 日历；
- 工时；
- 物料释放；
- WIP；
- 锁定；
- 执行事件；
- 异常。

---

# 38. FactoryProfile

FactoryProfile 描述一类虚拟工厂。

```yaml
profile_id: machine_shop_medium
profile_version: 1.0.0

workshops: 4

resources:
  target_count: 48

routing:
  operation_count_range: [3, 12]
  candidate_resource_range: [1, 5]

calendar:
  pattern: two_shift

orders:
  due_date_pressure: medium
```

所有 FactoryProfile：

```text
synthetic_only = true
```

禁止成为生产配置默认值。

---

# 39. ScenarioSpec

每个仿真场景必须可完全重放。

```yaml
scenario_id: SIM-FJSP-BOTTLENECK-001
scenario_version: 1.0.0

factory_profile: machine_shop_medium

seed: 12345

required_capabilities:
  - DAG_ROUTING
  - ALTERNATIVE_RESOURCE
  - MACHINE_CALENDAR

complexity:
  bottleneck_level: high
  due_date_pressure: high
  cross_workshop_ratio: 0.20

expected_behavior:
  result:
    - FEASIBLE
    - OPTIMAL
```

---

# 40. Scenario Provenance

所有 Synthetic 数据必须记录：

```text
scenario_id
scenario_version
seed
factory_profile
profile_version
generator_version
generated_at
```

这样任何失败场景都可以：

```text
100% replay
```

---

# 41. SyntheticDataGenerator

Generator 分层：

```text
TopologyGenerator
RoutingGenerator
OrderGenerator
CalendarGenerator
MaterialGenerator
ExecutionStateGenerator
LockGenerator
```

禁止一个 3000 行脚本生成所有东西。

---

# 42. Generator Determinism

同：

```text
ScenarioSpec
Generator Version
Seed
```

必须得到相同：

```text
canonical dataset
dataset_hash
```

---

# 43. 仿真工厂画像

初始 Scenario Library 至少包含五类工厂。

## PROFILE-A Flexible Job Shop

目标：

验证 V1 主模型。

特征：

- 多工序；
- 多候选设备；
- 多车间；
- 设备速度不同。

---

## PROFILE-B Bottleneck Factory

特征：

- 少量高负荷关键设备；
- 高交期压力；
- 多订单竞争。

验证：

```text
Weighted Tardiness
Solver Scaling
```

---

## PROFILE-C High-Mix Setup Factory

特征：

- 高频产品切换；
- Setup Matrix。

当前：

```text
EXPECTED = UNSUPPORTED_CAPABILITY
```

用于提前验证未来 C-013 架构兼容。

---

## PROFILE-D Assembly DAG

特征：

```text
parallel branch
merge
secondary resources
```

Secondary Capacity 当前允许返回：

```text
UNSUPPORTED_CAPABILITY
```

---

## PROFILE-E Cross-Workshop Factory

例如：

```text
Cutting
↓
Machining
↓
Heat Treatment
↓
Surface Treatment
↓
Assembly
```

重点验证：

```text
cross-workshop precedence
transport lag
calendar
```

---

# 44. Scenario Matrix

Scenario 不能只是随机大数据。

必须覆盖：

```text
Factory Size
×
Routing Complexity
×
Candidate Resources
×
Bottleneck Level
×
Due Date Pressure
×
Calendar Fragmentation
×
Material Delay
×
WIP Ratio
×
Lock Ratio
×
Cross Workshop Ratio
×
Failure Frequency
```

---

# 45. Complexity Metrics

Benchmark 必须记录：

```text
order_count
lot_count
operation_count
precedence_edge_count
resource_count
avg_candidate_resources
optional_interval_count
routing_depth
cross_workshop_edge_ratio
calendar_fragment_count
wip_ratio
lock_ratio
material_delay_ratio
bottleneck_utilization
horizon_ticks
```

禁止只使用：

```text
operation_count
```

判断 Solver 难度。

---

# 46. Scenario 分类

## Deterministic Fixture

人工可验证。

用于：

```text
correctness
```

---

## Synthetic Scenario

程序生成。

用于：

```text
scalability
robustness
coverage
```

---

## Disruption Scenario

模拟执行异常。

用于：

```text
replanning
```

---

## Historical Scenario

未来真实数据进入后建立。

用于：

```text
calibration
production validation
```

---

# 47. Execution Simulator

ExecutionSimulator 输入：

```text
Published ScheduleVersion
```

模拟生产时间推进。

输出：

```text
ExecutionEvent[]
```

---

# 48. Execution Events

V1 Simulation 支持：

```text
OPERATION_STARTED
OPERATION_COMPLETED
OPERATION_DELAYED
MACHINE_DOWN
MACHINE_RECOVERED
MATERIAL_DELAYED
URGENT_ORDER_CREATED
LOCK_CREATED
LOCK_RELEASED
```

---

# 49. Disruption Model

仿真允许配置：

```yaml
machine_failure:
  enabled: true

processing_delay:
  enabled: true

urgent_order:
  enabled: true

material_delay:
  enabled: true
```

所有概率参数都是：

```text
SIM_ASSUMPTION
```

不允许进入生产规则。

---

# 50. Dynamic Replanning Validation

Execution Simulator 必须验证：

### Fact Preservation

```text
completed operation unchanged
running resource unchanged
```

### Freeze Protection

```text
hard lock unchanged
```

### Stability

记录：

```text
changed operation count
machine changes
time deviation
```

### Delivery

比较：

```text
before replan tardiness
after replan tardiness
```

---

# 51. Reference Scheduler

开发阶段不能只拿 CP-SAT 和自己比较。

必须实现简单 Baseline Scheduler。

这些 Scheduler：

```text
NOT PRODUCTION SOLVER
```

---

# 52. Baseline Algorithms

至少：

```text
FCFS
EDD
SPT
Priority + EDD
Greedy Earliest Available Machine
```

用途：

```text
Benchmark
Regression
Sanity Check
```

---

# 53. Solver Benchmark

每个 Scenario 同时可运行：

```text
Reference Scheduler
GlobalCpSatStrategy
```

比较：

```text
feasibility
weighted tardiness
makespan
runtime
```

如果 CP-SAT 结果明显劣于简单 heuristic：

```text
BENCHMARK_WARNING
```

必须进入诊断。

---

# 54. Benchmark Harness

接口：

```python
BenchmarkRunner.run(
    scenario,
    solver,
    limits
)
```

输出：

```text
benchmark_report.json
```

---

# 55. BenchmarkReport

```json
{
  "scenario_id": "...",
  "problem_hash": "...",
  "solver": "...",
  "status": "FEASIBLE",
  "model_build_seconds": 0,
  "first_solution_seconds": 0,
  "solve_seconds": 0,
  "objective": 0,
  "best_bound": 0,
  "gap": 0,
  "memory_peak_mb": 0,
  "validation_passed": true
}
```

---

# 56. Benchmark Complexity Profiles

使用：

```text
XS
S
M
L
XL
```

Profile 本身在：

```text
benchmarks/profiles.yaml
```

定义。

不允许把某个固定工序数量视为真实生产容量标准。

每个 Profile 定义：

```text
operation target
resource target
candidate density
calendar density
routing complexity
```

---

# 57. 性能 Gate

## Gate A — P2 Synthetic Solver Gate

必须验证：

```text
Snapshot
→ Problem
→ Solver
→ Validator
→ Export
```

完整闭环。

至少运行：

```text
XS
S
M
```

同时记录：

```text
build time
first feasible
runtime
gap
memory
```

---

## Gate B — P4 Dynamic Replanning Gate

通过 ExecutionSimulator 连续注入异常。

必须确认：

```text
Execution Fact 不被修改
HARD_LOCK 不被修改
新 ScheduleVersion Validator = PASS
```

---

## Gate C — P7 Reality Calibration Gate

真实历史数据进入后：

```text
Historical Snapshot
↓
Replay
↓
Synthetic Comparison
↓
FactoryProfile Calibration
↓
Production Capacity Boundary
```

P7 不允许成为第一次性能测试。

---

# 58. Performance Regression

CI 不要求大型 Benchmark 每次运行。

分三级：

```text
PR:
XS

Nightly:
XS + S + M

Release:
XS + S + M + L + selected stress scenarios
```

XL 可以人工或专用环境执行。

---

# 59. PROD_OPEN 与 SIM_ASSUMPTION

真实业务问题使用：

```text
PROD_OPEN
```

例如：

```text
OPEN-003 Factory Topology
```

仿真开发可以同时存在：

```text
SIM_ASSUMPTION-003
```

例如：

```text
4 workshops
48 machines
```

两者必须严格区分。

---

# 60. PROD_OPEN 规则

如果：

```text
PROD_OPEN unresolved
```

允许：

```text
development
simulation
benchmark
```

禁止：

```text
production release
```

这解决没有真实工厂环境时无法继续开发的问题。

---

# 61. 关键 PROD_OPEN

至少维护：

```text
OPEN-001 factory timezone
OPEN-002 ERP/MES/WMS/CAM interfaces
OPEN-003 real factory topology
OPEN-004 calendar processing semantics
OPEN-005 freeze window
OPEN-006 priority/tardiness business meaning
OPEN-007 material_ready_at authority
OPEN-008 lot splitting policy
OPEN-009 cross-workshop transport rule
OPEN-010 approval responsibility
OPEN-011 historical benchmark data
OPEN-012 production runtime threshold
OPEN-013 unit conversion
OPEN-014 duration fallback
OPEN-015 field authority
```

---

# 62. 数据隔离

Synthetic 数据绝对禁止混入生产数据。

推荐：

```text
aps_dev
aps_sim
aps_prod
```

至少使用独立 Database。

Simulation API 在 Production：

```text
disabled = true
```

---

# 63. API

## Import

```text
POST /api/v1/import-runs
GET  /api/v1/import-runs/{id}
POST /api/v1/planning-snapshots
```

## Planning

```text
POST /api/v1/planning-runs
GET  /api/v1/planning-runs/{id}
POST /api/v1/planning-runs/{id}/cancel
```

## Schedule

```text
GET  /api/v1/schedule-versions/{id}
POST /api/v1/schedule-versions/{id}/validate
POST /api/v1/schedule-versions/{id}/approve
POST /api/v1/schedule-versions/{id}/reject
POST /api/v1/schedule-versions/{id}/publish
```

## Replan

```text
POST /api/v1/replan-requests
POST /api/v1/execution-events
```

---

# 64. Simulation API

只允许：

```text
Development
Test
Benchmark Environment
```

接口：

```text
POST /api/v1/sim/scenarios/generate
POST /api/v1/sim/scenarios/{id}/run
POST /api/v1/sim/benchmarks
POST /api/v1/sim/execution-runs
GET  /api/v1/sim/benchmarks/{id}
```

Production 默认：

```text
404 / disabled
```

---

# 65. Worker Reliability

所有长任务必须异步。

任务：

```text
ImportJob
SnapshotJob
PlanningJob
ExportJob
BenchmarkJob
SimulationJob
```

必须具备：

```text
idempotency_key
heartbeat
lease
attempt
status
started_at
heartbeat_at
finished_at
```

Worker 崩溃后：

```text
STALLED
```

而不是永久 RUNNING。

---

# 66. 幂等性

至少：

```text
Import
Planning request
Export
Publish
Execution Event
```

必须支持幂等。

禁止：

```text
Worker retry
→ double publish
```

---

# 67. Standard Export Package

成功 PlanningRun：

```text
export_package/
├─ manifest.json
├─ schedule.json
├─ schedule_operations.csv
├─ order_summary.csv
├─ resource_load.csv
├─ kpi.json
├─ validation_report.json
├─ solver_report.json
├─ change_report.json
└─ import_quality_report.json
```

Synthetic Run 额外：

```text
scenario_manifest.json
benchmark_report.json
```

---

# 68. Frontend Workspace

V1 页面：

```text
Data Health
Import Runs
Orders
Operations
Resources
Calendars
Planning Runs
Factory Gantt
Workshop Gantt
Machine Gantt
Late Orders
Resource Load
Schedule Comparison
Validation Errors
Solver Diagnostics
Locks
Approval
Publication
Export
```

开发环境增加：

```text
Scenario Lab
Benchmark Lab
Execution Simulation
```

---

# 69. Gantt 编辑

拖拽操作不能直接修改数据库计划。

必须：

```text
UI Command
↓
Server Validation
↓
New Draft Version
↓
Validator
```

禁止：

```text
UPDATE published_schedule
```

---

# 70. Repository Structure

```text
/
├─ AGENTS.md
├─ README.md
├─ APS_IMPLEMENTATION_SPEC.md
├─ pyproject.toml
├─ uv.lock
├─ docker-compose.yml
│
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ application/
│  │  ├─ domain/
│  │  ├─ infrastructure/
│  │  ├─ importers/
│  │  ├─ normalization/
│  │  ├─ data_validation/
│  │  ├─ snapshots/
│  │  │
│  │  ├─ planning/
│  │  │  ├─ problem/
│  │  │  ├─ policy/
│  │  │  ├─ preprocessing/
│  │  │  ├─ strategies/
│  │  │  ├─ backends/
│  │  │  │  └─ cp_sat/
│  │  │  ├─ validation/
│  │  │  ├─ diagnostics/
│  │  │  └─ kpi/
│  │  │
│  │  ├─ simulation/
│  │  │  ├─ profiles/
│  │  │  ├─ scenarios/
│  │  │  ├─ generators/
│  │  │  ├─ execution/
│  │  │  ├─ baselines/
│  │  │  └─ benchmarks/
│  │  │
│  │  ├─ exporters/
│  │  └─ jobs/
│  │
│  ├─ migrations/
│  └─ tests/
│     ├─ unit/
│     ├─ contract/
│     ├─ integration/
│     ├─ golden/
│     ├─ property/
│     ├─ simulation/
│     └─ benchmark/
│
├─ frontend/
│
├─ schemas/
│  ├─ json/
│  ├─ scenario/
│  └─ data_dictionary.yaml
│
├─ fixtures/
│  ├─ deterministic/
│  ├─ infeasible/
│  ├─ synthetic/
│  ├─ future_capabilities/
│  └─ historical/
│
├─ benchmarks/
│  ├─ profiles.yaml
│  └─ baselines/
│
├─ docs/
│  ├─ current_phase.md
│  ├─ 00-scope.md
│  ├─ 01-glossary.md
│  ├─ 02-domain-model.md
│  ├─ 03-data-contracts.md
│  ├─ 04-planning-run.md
│  ├─ 05-constraint-catalog.md
│  ├─ 06-objectives.md
│  ├─ 07-solver-contract.md
│  ├─ 08-validator.md
│  ├─ 09-simulation.md
│  ├─ 10-kpi-definition.md
│  ├─ 11-api.md
│  ├─ 12-test-matrix.md
│  ├─ 13-benchmark.md
│  ├─ 14-roadmap.md
│  ├─ adr/
│  ├─ phases/
│  ├─ tasks/
│  ├─ runbooks/
│  └─ open_questions/
│
├─ scripts/
└─ infra/
```

---

# 71. P0 — Executable Specification

目标：

> 先固定“排什么”和“什么算正确”。

交付：

```text
Repository Skeleton
AGENTS.md
Schema Skeleton
Constraint Catalog
State Machines
Simulation Architecture
ScenarioSpec Schema
FactoryProfile Schema
Golden Fixture
Infeasible Fixtures
Current Phase File
Task Template
CI Skeleton
```

必须创建：

```text
SIM-MINIMAL-001
```

至少：

```text
2 workshops
3 resources
multiple candidate resources
cross-workshop dependency
maintenance interval
```

同时人工给出正确 schedule。

P0 禁止：

```text
real solver implementation
```

---

# 72. P0 Exit Gate

必须满足：

```text
Schema PASS
Golden Fixture PASS
Validator Rule Sheet PASS
Scenario deterministic replay PASS
Repository Build PASS
CI PASS
```

所有 PROD_OPEN 必须登记。

不要求关闭全部 PROD_OPEN。

---

# 73. P1 — Data & Snapshot

实现：

```text
CSV
Excel
one formal adapter
Raw Staging
Normalization
Data Validation
Order Expansion
PlanningSnapshot
Snapshot Hash
```

同时实现：

```text
Synthetic Generator
→ Standard Import
```

保证仿真数据也走正式数据链。

---

# 74. P1 Exit Gate

要求：

```text
same scenario + seed
→ same import package
→ same snapshot hash
→ same planning problem hash
```

并保证：

```text
route cycle rejected
missing resource rejected
unit error rejected
missing duration rejected
```

---

# 75. P2 — CP-SAT Vertical Slice

只实现：

```text
C-001 ~ C-011
OBJ-001
```

实现：

```text
PlanningProblem
PlanningPolicy
SolveLimits
PlanningSolution
GlobalCpSatStrategy
CpSatBackend
ScheduleValidator
Reference Scheduler
BenchmarkRunner
```

---

# 76. P2 Synthetic Solver Gate

必须执行：

```text
Golden JSSP
Golden FJSP
Cross Workshop
Calendar
Material Delay
Running Operation
Hard Lock
XS
S
M
```

每次记录：

```text
model size
build time
first feasible
objective
bound
gap
memory
validator result
```

P2 不允许以：

```text
“功能测试通过”
```

作为唯一退出条件。

---

# 77. P3 — Planning Workspace

实现：

```text
Gantt
Resource Load
Order View
ScheduleVersion
Comparison
Lock
Approval
Reject
Publish
Export
Audit
```

---

# 78. P3 Exit Gate

必须证明：

```text
DRAFT cannot publish
REJECTED cannot publish
only APPROVED can publish
published version immutable
export idempotent
```

---

# 79. P4 — Dynamic Replanning

实现：

```text
ExecutionEvent
ReplanRequest
Freeze Window
HARD_LOCK
SOFT_LOCK
OBJ-002
ChangeReport
Execution Simulator
```

---

# 80. P4 Dynamic Gate

Scenario 必须连续模拟：

```text
Urgent Order
Machine Failure
Material Delay
Processing Delay
Early Completion
```

检查：

```text
Facts Preserved
Locks Preserved
Validator PASS
ChangeReport Complete
```

---

# 81. P5 — Advanced Capabilities

只有真实需求或 Simulation / Benchmark 证明必要时增加。

候选：

```text
Secondary Resources
Setup Matrix
Batch
Split/Merge
Material Competition
Preemption
Buffer
Decomposition
Rolling Horizon
```

一项一项实施。

禁止：

```text
P5 big bang
```

---

# 82. DecomposedStrategy Gate

只有出现以下证据之一才能开发：

```text
Synthetic large benchmark shows unacceptable scaling
Historical benchmark shows unacceptable scaling
Model memory exceeds deployment budget
Advanced constraints cause model explosion
```

必须提交：

```text
ADR
comparison benchmark
merge validator
quality impact report
```

---

# 83. P6 — AI Duration Prediction

只有 APS 核心稳定后进入。

接口：

```text
DurationPrediction
```

输出：

```text
p50_seconds
p90_seconds
confidence
model_version
feature_schema_version
fallback_reason
```

低置信度：

```text
fallback standard duration
```

---

# 84. P7 — Reality Calibration

P7 不是第一次测试性能。

P7 输入：

```text
real anonymized historical snapshots
```

执行：

```text
Historical Replay
Synthetic Comparison
FactoryProfile Calibration
Solver Benchmark
Planner Baseline Comparison
Production Capacity Decision
```

---

# 85. Reality Gap Report

必须新增：

```text
reality_gap_report.json
```

比较：

```text
synthetic routing depth
real routing depth

synthetic candidate density
real candidate density

synthetic calendar fragmentation
real calendar fragmentation

synthetic bottleneck
real bottleneck

synthetic solver runtime
real solver runtime
```

用来持续改进 Simulation。

---

# 86. Test Matrix

必须至少存在：

```text
TEST-CONTRACT-001
TEST-GOLDEN-JSSP
TEST-GOLDEN-FJSP
TEST-INF-NO-RESOURCE
TEST-INF-LOCK
TEST-INF-HORIZON
TEST-CALENDAR
TEST-MATERIAL
TEST-RUNNING
TEST-CROSS-WORKSHOP
TEST-MAX-LAG
TEST-VALIDATOR-MUTATION
TEST-REPLAN
TEST-OUTPUT
TEST-IDEMPOTENCY
TEST-SCENARIO-REPLAY
TEST-SIM-ISOLATION
TEST-REFERENCE-SCHEDULER
TEST-BENCHMARK
TEST-PROPERTY
TEST-SOLVER-UPGRADE
```

---

# 87. Property Tests

随机生成合法 V1 Problem。

任何被接受的 Schedule 必须满足：

```text
validator_passed == true
```

Property Test 不要求：

```text
same schedule ordering
```

因为多个同质量解都可能正确。

---

# 88. Golden Tests

Golden Fixture 很小。

必须可以：

```text
manual verify
or
brute force verify
```

Golden Test 关注：

```text
feasibility
objective
constraint correctness
```

禁止只比较完整 Gantt JSON。

---

# 89. Benchmark Regression

Solver 升级、Constraint 修改、PlanningProblem 修改必须对固定 Scenario Set 回放。

比较：

```text
correctness
objective quality
runtime
memory
```

如果显著退化：

```text
release blocked
or
ADR required
```

---

# 90. AI Coding 防幻觉规则

Coding Agent MUST NOT：

- 猜生产数据；
- 猜工厂班次；
- 猜冻结区；
- 猜运输时间；
- 猜标准工时；
- 猜库存；
- 猜资源能力；
- 猜目标权重；
- 删除硬约束解决 INFEASIBLE；
- 把 FEASIBLE 描述为最优；
- 把 UNKNOWN 描述为无解；
- 把 Hint 当约束；
- 把 Simulator 假设当真实业务；
- 把随机 schedule 当求解结果；
- 把 unsupported capability 静默忽略；
- 通过修改测试断言让测试通过；
- 在 UI 中复制 Solver Logic；
- 在 Validator 中复制 CP-SAT Constraint Builder。

---

# 91. Error Philosophy

系统必须区分：

```text
DATA_ERROR
UNSUPPORTED_CAPABILITY
MODEL_INVALID
INFEASIBLE
NO_SOLUTION_WITHIN_LIMIT
VALIDATION_FAILED
SYSTEM_ERROR
```

禁止全部返回：

```text
500 Internal Server Error
```

---

# 92. 无解诊断

按顺序：

```text
Precheck
↓
Pure Feasibility Solve
↓
Assumption Groups
↓
Conflict Explanation
```

Assumption 返回：

```text
conflict subset
```

除非算法证明，否则禁止称：

```text
minimal conflict set
```

---

# 93. Observability

每次 PlanningRun 记录：

```text
snapshot size
problem size
variable count
constraint count
optional interval count
model build time
first feasible
solve time
objective
bound
gap
memory
validator time
```

Simulation additionally：

```text
scenario
seed
generator version
```

---

# 94. Audit

必须审计：

```text
Import
Manual Override
Lock
Approve
Reject
Publish
Rollback Reference
Replan
```

---

# 95. Security

文件导入：

- 限制格式；
- 限制大小；
- 禁止执行 Excel Macro；
- 禁止直接执行外部公式；
- 禁止拼接 SQL；
- 禁止拼接 shell command。

Secret：

```text
environment / secret manager
```

禁止写入：

```text
repository
logs
exports
```

---

# 96. Configuration Layers

配置分：

```text
System Config
Simulation Config
Business Policy
Solver Limits
```

Simulation Config 永远不能覆盖 Production Business Policy。

---

# 97. ADR 必须覆盖

以下修改必须 ADR：

```text
Architecture
Solver Backend
Constraint Semantics
Objective Hierarchy
PlanningProblem Contract
Schedule State Machine
Data Authority
Decomposition
Advanced APS Capability
Production Performance Threshold
```

---

# 98. Task Card

每个 Vibe Coding Task 必须使用：

```markdown
### TASK-Px-yy

Requirement IDs:
NFR / ENG IDs:

Depends on:

Goal:

Inputs:

Files allowed to change:

Files forbidden to change:

Implementation steps:

Outputs:

Schema changes:

Migration:

Error behavior:

Tests:

Benchmark impact:

Simulation scenarios:

Acceptance commands:

Artifacts:

Explicitly excluded:

PROD_OPEN:

SIM_ASSUMPTIONS:

Rollback:
```

---

# 99. Task Scope Rule

Coding Agent 只允许修改：

```text
Files allowed to change
```

如果发现必须修改其他文件：

```text
STOP
→ update task card
→ report reason
```

禁止无边界重构。

---

# 100. 每次任务后的最低验收

Backend：

```bash
uv run ruff check .
uv run pyright
uv run pytest backend/tests/unit
uv run pytest backend/tests/contract
uv run pytest backend/tests/integration
```

Frontend：

```bash
npm test
npm run build
```

P2 后增加：

```bash
uv run pytest backend/tests/golden
uv run pytest backend/tests/simulation
```

涉及 Solver 修改：

```bash
uv run python scripts/run_benchmark.py --profile pr
```

---

# 101. Git / Version Rule

每个发布构建记录：

```text
code_commit
spec_version
schema_version
solver_version
```

不可追溯构建不得发布。

---

# 102. Solver Upgrade Rule

OR-Tools 升级必须：

```text
ADR
Dependency Lock Update
Golden Replay
Scenario Replay
Benchmark Comparison
Solver Status Contract Test
```

禁止：

```text
pip install -U ortools
```

后直接合并。

---

# 103. 数据 Schema Versioning

Schema 修改必须：

```text
schema_version++
```

并提供：

```text
migration
compatibility rule
contract test
```

---

# 104. Simulation Versioning

以下任意修改都必须更新版本：

```text
FactoryProfile
ScenarioSpec
Generator
EventSimulator
```

否则 historical benchmark 无法复现。

---

# 105. 不允许过早承诺的指标

没有真实历史数据前禁止：

```text
5分钟一定排完
秒级排程
99%最优
全局最优
支持任意规模工厂
```

Synthetic Benchmark 只能说明：

> 当前测试场景与当前硬件环境下的行为。

---

# 106. Production Readiness

生产上线至少需要：

```text
Historical Snapshot
Historical Replay
Planner Review
Reality Gap Report
Performance Boundary
PROD_OPEN closure
Security Review
Backup Restore Test
Monitoring
Runbook
UAT
```

---

# 107. V1 最终能力边界

V1 的真正交付不是：

```text
一个 OR-Tools 脚本
```

而是：

```text
标准数据模型
+
不可变快照
+
PlanningProblem
+
SolverBackend
+
GlobalCpSatStrategy
+
ScheduleValidator
+
Planning Workspace
+
Version / Approval / Publish
+
Simulation Environment
+
Scenario Library
+
Benchmark Harness
+
Execution Simulator
+
Replanning
+
Traceability
```

---

# 108. 项目核心原则

本项目必须长期坚持以下顺序：

```text
Correctness
    ↓
Explainability
    ↓
Reproducibility
    ↓
Feasibility
    ↓
Performance
    ↓
Optimization Quality
    ↓
Advanced Capability
    ↓
AI
```

禁止反过来：

```text
AI
↓
复杂算法
↓
漂亮 Gantt
↓
最后才验证排程是否可生产
```

---

# 109. 核心技术路线总结

```text
               ┌───────────────────┐
               │ Business Sources  │
               └─────────┬─────────┘
                         │
                         ▼
               ┌───────────────────┐
               │ Canonical Data    │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ PlanningSnapshot  │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ PlanningProblem   │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ PlanningStrategy  │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ SolverBackend     │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ PlanningSolution  │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ Independent       │
               │ Validator         │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ ScheduleVersion   │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ Human Approval    │
               └─────────┬─────────┘
                         ▼
               ┌───────────────────┐
               │ Production        │
               └───────────────────┘


Simulation Side:

FactoryProfile
      ↓
ScenarioSpec
      ↓
Synthetic Generator
      ↓
Standard Import Contract
      ↓
同一 PlanningSnapshot
      ↓
同一 PlanningProblem
      ↓
同一 Solver
      ↓
同一 Validator
      ↓
Benchmark

Published Schedule
      ↓
Execution Simulator
      ↓
ExecutionEvent
      ↓
Replan
      ↓
New ScheduleVersion
```

---

# 110. 第一轮 Vibe Coding 启动指令

```text
完整阅读 APS_IMPLEMENTATION_SPEC.md。

当前只允许实施 P0。

禁止实现真实 CP-SAT 排程逻辑。
禁止提前进入 P1。

首先：

1. 创建 AGENTS.md。
2. 创建 docs/current_phase.md，并标记 P0。
3. 创建完整仓库目录。
4. 创建 REQ / NFR / ENG 追踪机制。
5. 创建 Constraint Catalog。
6. 创建三个独立状态机：
   - PlanningRun
   - ScheduleVersion
   - ExportJob
7. 创建 ScenarioSpec Schema。
8. 创建 FactoryProfile Schema。
9. 创建 Capability Matrix。
10. 创建 Simulation 模块骨架。
11. 创建 SIM-MINIMAL-001。
12. 创建人工可验证 Golden Schedule。
13. 创建至少三个明确非法 Fixture。
14. 创建 PROD_OPEN Registry。
15. 创建 SIM_ASSUMPTION Registry。
16. 创建统一错误码。
17. 创建 CI、日志、数据库、Worker 和健康检查骨架。

不得：

- 创建 CpModel；
- 创建 IntervalVar；
- 编写真正 Solver；
- 提前实现 P1；
- 猜任何真实工厂参数。

完成后运行 P0 全部测试并输出：

- 修改文件；
- Schema；
- Fixture；
- 测试结果；
- PROD_OPEN；
- SIM_ASSUMPTION；
- 下一阶段进入条件。

未经确认不得进入 P1。
```

---

# 111. 最终工程判断标准

对于任何新增功能，Coding Agent 必须依次回答：

```text
1. 它对应什么 Requirement？

2. 输入数据从哪里来？

3. Production 与 Simulation 如何区分？

4. PlanningProblem 如何表达？

5. SolverBackend 如何实现？

6. Validator 如何独立验证？

7. 有什么 Positive Fixture？

8. 有什么 Negative Fixture？

9. 有什么 Scenario？

10. 性能可能如何变化？

11. 是否产生新的 PROD_OPEN？

12. 是否需要 ADR？
```

任何无法回答以上问题的功能：

```text
不得进入生产代码。
```

---

# 112. 项目最终目标

本项目最终不是为了证明：

> “CP-SAT 很强。”

而是建立一个：

> **可以持续吸收真实制造业务约束、能够独立证明排程正确性、能够通过仿真提前暴露风险、能够用真实数据持续校准、并且能够在未来替换或扩展求解器的通用 APS 技术底座。**

在没有真实生产数据的阶段：

```text
Simulation
不是 Demo
不是 Mock
不是随机构造测试数据
```

而是：

> **APS 研发阶段的第一套可控生产环境。**

真实工厂数据进入之后：

```text
Simulation
↓
Calibration
↓
Historical Replay
↓
Production Benchmark
```

从而让项目从“理论可运行”逐步演进到“真实可生产”。

