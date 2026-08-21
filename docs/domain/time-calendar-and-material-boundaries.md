---
doc_id: DOC-DOM-003
title: 时间、日历与物料边界
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [16, 20, 21, 22, 26]
last_reviewed: 2026-08-21
---

# 时间、日历与物料边界

## 时间标准

- 数据库时间：UTC `TIMESTAMPTZ`；
- 显示时间：`factory_timezone`；
- 权威持续时间：整数 `duration_seconds`；
- Solver 时间：可配置 tick；默认 `tick_seconds = 60`；
- 转换：`duration_ticks = ceil(duration_seconds / tick_seconds)`。

Production 的 factory timezone 未确认时返回 `BLOCK_PRODUCTION`，但不应阻止 Development/Simulation 启动。

P0 machine contracts 要求所有计划 instant 使用 RFC 3339 UTC 且以 `Z` 结尾；非 UTC offset 不会在合同层静默转换。`domain/types.py` 对 naive/non-UTC datetime、负 duration、非整数 duration 和非正 tick 明确抛出 `ContractValueError`，并用整数运算实现 ceiling tick。

## Planning Horizon

NOT_STARTED Operation 必须满足：

```text
start >= horizon_start
end <= horizon_end
```

不能静默截断超出 horizon 的任务。Horizon 必须足以表达 RUNNING 的剩余占用和所有固定不可用 interval。

## Resource Calendar

班外、休息、维护和停机等不可用区间以固定 interval 参与 Capacity=1 Resource 的 NoOverlap。V1 非抢占任务不能跨越不可用区间。真实日历的边界、重叠和跨日语义属于 OPEN-004。

## Material Boundary

V1 不做库存竞争、替代料或完整物料平衡。唯一 Solver gate 为：

```text
operation.start >= material_ready_at
```

`material_ready_at` 必须来自上游权威或未来 `MaterialReadinessProvider`。缺失必填值应产生数据错误，不能由 Solver、AI 或 Simulation 默认值补猜。

在 `planning-problem.v1` 中字段名为 `material_ready_at_utc` 并为必填 UTC instant；P0 sample 使用显式 synthetic 时间，仅用于 Schema validation，不构成 OPEN-001/004/007 的生产决定。

## TASK-P1-02 canonical time/unit boundary

Canonical/Import v2与Snapshot v2所有计划instant均使用RFC 3339 UTC `Z`字段，duration/lag/remaining time均为integer seconds；quantity必须同时携带非空unit。Resource calendar只承载显式unavailable intervals及其source，pure precheck要求`end > start`；它不定义班次合并、跨日或重叠处理规则。

ProductionOrder必须显式携带`release_at_utc`与`material_ready_at_utc`，Snapshot OperationInstance只能逐值复制，不得猜测。Factory timezone、calendar processing、material authority和unit conversion继续受OPEN-001/004/007/013约束；contract sample值只验证shape，不是生产默认值。

## TASK-P1-05 executable time/unit rules

Normalization只接受second precision RFC3339及`Z`或显式numeric offset；naive、date-only、fractional-second和非法offset均为`INVALID_TIMEZONE/DATA_ERROR`。Numeric offset消除DST歧义后转UTC `Z`；原offset仍保留在Raw Staging bytes而不进入canonical instant。Calendar nested interval也执行相同转换并按stable interval ID排序，range/overlap业务判断留给Data Validation。

Duration只接受integer source value与同row显式unit。Registry v1精确支持`s/min/h`，以integer numerator/denominator运算并拒绝non-integral second、negative/zero规则冲突和int64 overflow。它不是OPEN-013的Production unit policy closure；任何额外unit、alias或默认值都必须发布新版本并有权威证据。

## TASK-P1-06 canonical time/calendar/unit validation

Data Validation复核所有canonical instant为UTC `Z`、calendar/lock/execution interval严格递增，并拒绝同一Calendar内显式unavailable intervals重叠；它不猜测OPEN-004的班次合并、跨日或生产日历语义。Routing lag必须为非负整数秒且`max >= min`；execution status-specific事实、positive remaining/completed quantity与remaining duration必须完整。

Product→DemandOrder→ProductionOrder→ProductionLot→ExecutionFact以及Product→RoutingResourceOption的quantity unit必须逐级相等；missing/blank/mismatch输出`UNIT_CONVERSION_ERROR`，但不在Data Validation中转换。Required duration缺失输出`MISSING_DURATION`，非法duration保持`INVALID_DURATION`。OPEN-001/004/007/013/014继续OPEN，test-local时刻与unit不成为生产默认值。

## TASK-P1-07 copied time/material boundaries

Expansion不转换或推导时间：每个实例逐字复制Demand due、ProductionOrder release/material-ready UTC以及Routing edge的min/max/transport seconds；candidate duration也只复制P1-06已验证的显式整数秒与source version。RUNNING/COMPLETED的actual/remaining事实留在canonical record并由`execution_fact_id`回链，不把实际开始时间重新排入未来域。

缺duration/source不得以setup+cycle×quantity、平均值或AI fallback补齐；material-ready不得从lot/order状态猜测。OPEN-001/004/007/009/013/014继续OPEN，属性测试中的UTC、300秒transport和duration只属于synthetic test values。

## TASK-P1-09 Problem time/horizon projection

Builder要求horizon start精确等于immutable Snapshot cutoff，start/end为second-precision UTC且end严格更晚，tick为显式正整数。每个duration/remaining仍以权威秒进入Problem；`ceil(seconds/tick_seconds)`只检查RUNNING remainder和至少一个NOT_STARTED candidate可在release/material gate后完整落入horizon，不把秒值替换为tick，也不静默截断。全局precedence/calendar可行性留给P2 Solver/independent Validator，build成功不表示feasible。

Calendar按Resource引用投影所有与当前horizon相交的显式unavailable interval，保留原始start/end，不生成班次、不合并、不clip；完全历史或horizon外interval对当前future domain无效而不进入Problem。与horizon相交的lock因Problem v1无字段而拒绝。OPEN-004/007/009/014继续OPEN；本Task不把synthetic cutoff、tick=60或24小时horizon变成Production默认值。

## TASK-P2-06 exact Solver projection

设tick为正整数秒。任意signed秒偏移`x`的下界使用`ceil(x/tick)`，上界使用`floor(x/tick)`；precedence min与cross-workshop transport分别形成下界，因此有效约束为`start-successor - end-predecessor >= max(ceil(min/tick), ceil(transport/tick))`，不得相加。Max lag独立使用`<= floor(max/tick)`，historical predecessor使用其权威完成时刻作绝对anchor。

原始calendar unavailable half-open interval`[a,b)`投影为`[floor(a/tick), ceil(b/tick))`，裁到horizon后合并overlap/touching blocks并作为对应resource固定interval加入`NoOverlap`。这对tick-grid assignment与原始秒级相交判定等价；release/material各自使用ceiling下界。所有instant必须是canonical whole-second UTC，sub-second输入fail closed而非静默取整。OPEN-004/009/010/011/012继续OPEN；synthetic值不成为Production默认。
