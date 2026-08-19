# SIM-MINIMAL-001@1.0.0 手工计算说明

本目录是 P0 correctness fixture，不是生产工厂参数、P1 canonical record contract、正式
`validation-report.v2`、正式 `kpi.v1` 或 Solver 输出。`import-package.json.records` 中的键只属于
`sim-minimal-records.v1`；P1 必须按权威字段映射另行建立 Standard Import canonical records。

## Provenance

| Artifact | Version / identity |
|---|---|
| FactoryProfile | `PROFILE-SIM-MINIMAL-FJSP@1.0.0` / `factory-profile.v1` |
| ScenarioSpec | `SIM-MINIMAL-001@1.0.0` / `scenario-spec.v1` |
| Assembler identity | `P0-MANUAL-FIXTURE-ASSEMBLER@1.0.0` / seed `6001` |
| Import package | `SIMPKG-SIM-MINIMAL-001-1.0.0` / `import-package.v1` |
| Canonicalization | `canonical-json.v1` / `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10` |
| Golden schedule | `SCHEDULE-SIM-MINIMAL-001-GOLDEN-1.0.0` / `golden-schedule.v1` |
| Expected evidence | `golden-validation.v1` and `golden-kpi.v1` (fixture-local) |

`generated_at` belongs only to the manifest and is excluded from the dataset hash. Replaying the committed
Import JSON with sorted keys, UTF-8, no whitespace and finite JSON numbers must reproduce the manifest hash.

## Registered quantitative assumptions

| ID | Values fixed only for this fixture version |
|---|---|
| `SIM-ASSUMPTION-006` | 2 workshops, 2 production lines, 3 capacity-1 resources, 1 order, 3 operations |
| `SIM-ASSUMPTION-007` | horizon `08:00Z`–`12:00Z`, tick 900 s, heat-resource maintenance `09:00Z`–`10:00Z` |
| `SIM-ASSUMPTION-008` | selected durations 3600/1800/3600 s; alternatives 5400/2700 s; edge windows `[0,1800]` s; cross-workshop transport 900 s |
| `SIM-ASSUMPTION-009` | release gates `08:00Z`; OP-CUT-002 material gate `09:00Z`; due `11:30Z`; tardiness weight 2 |

这些数值不定义通用 XS、真实产能、标准工时、班次、运输时间、交期规则或 Objective 权重。

## Timeline and schedule

`horizon_start=08:00Z`，所以 1 tick = 15 分钟：

| Operation | Selected resource | Tick interval | UTC interval | Duration |
|---|---|---:|---|---:|
| OP-CUT-001 | RES-CUT-FAST | `[0,4)` | 08:00–09:00 | 3600 s |
| OP-CUT-002 | RES-CUT-FAST | `[4,6)` | 09:00–09:30 | 1800 s |
| OP-HEAT-001 | RES-HEAT-001 | `[8,12)` | 10:00–11:00 | 3600 s |

RES-HEAT-001 maintenance 是 `[4,8)`；第三道 operation 恰在 maintenance 结束边界开始。
同机前两道 operation 为 `[0,4)` 与 `[4,6)`，半开区间只接触边界、不重叠。

## Constraint calculations

- C-001：三个 `NOT_STARTED` operation 在 assignments 中各出现一次。
- C-002：两条 observed lag 分别为 `(4-4)*900=0` 和 `(8-6)*900=1800` 秒，均在声明的闭区间 `[0,1800]`。
- C-003：三个 assignment 均只选择一个已列出的 candidate resource。
- C-004：RES-CUT-FAST 的 `[0,4)`、`[4,6)` 不重叠；其他资源至多一个 assignment。
- C-005：RES-HEAT-001 的 `[8,12)` 与 unavailable `[4,8)` 不相交。
- C-006：三个 start 均不早于 release/material；OP-CUT-002 在 material-ready tick 4 恰好开始。
- C-007：无 COMPLETED/RUNNING execution fact，故对本 fixture 明确 `NOT_APPLICABLE`。
- C-008：locks 为空，故对本 fixture 明确 `NOT_APPLICABLE`。
- C-009：跨车间 observed transport `(8-6)*900=1800 >= 900` 秒，独立于 C-002 检查。
- C-010：选中设备的期望 ticks 为 `ceil(3600/900)=4`、`ceil(1800/900)=2`、`ceil(3600/900)=4`，与 interval 长度一致。
- C-011：horizon 为 `[0,16)`，所有 `NOT_STARTED` assignment 均完整落在其中。

`expected-validation.json` 只是上述人工期望的结构化记录；P0-06 Golden test 从 Import 和 Schedule
重新计算这些结论，不读取 evidence 文本决定 PASS。通用 evaluator、negative mutation 和正式 v2
ValidationReport 属于 TASK-P0-07，不能由本文件声称完成。

## KPI and objective calculations

- Order completion = tick 12 = 11:00Z；due = tick 14 = 11:30Z，因此 tardiness = 0、weighted tardiness = 0、on-time ratio = 1。
- 本 fixture 明确把 makespan 定义为 `max(end_tick) * tick_seconds`（相对 horizon origin），所以 `12*900=10800` 秒。
- RES-CUT-FAST busy = `(4+2)*900=5400` 秒，available = 14400 秒，utilization = 0.375。
- RES-CUT-SLOW busy = 0，available = 14400 秒，utilization = 0。
- RES-HEAT-001 available = `14400-3600=10800` 秒，busy = 3600 秒，utilization = 1/3。

手工 lower bound：前两道工序最快在 tick 6 完成；transport 使 heat earliest tick 7，但 `[4,8)`
maintenance 令一个 4-tick 非抢占 heat operation 最早只能在 tick 8 开始、tick 12 完成。Golden 达到
该界且 weighted tardiness 已达到非负下界 0，因此在本 fixture 的明确 Delivery→makespan 比较口径下为最优。
