---
doc_id: DOC-DOM-003
title: 时间、日历与物料边界
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [16, 20, 21, 22, 26]
last_reviewed: 2026-08-19
---

# 时间、日历与物料边界

## 时间标准

- 数据库时间：UTC `TIMESTAMPTZ`；
- 显示时间：`factory_timezone`；
- 权威持续时间：整数 `duration_seconds`；
- Solver 时间：可配置 tick；默认 `tick_seconds = 60`；
- 转换：`duration_ticks = ceil(duration_seconds / tick_seconds)`。

Production 的 factory timezone 未确认时返回 `BLOCK_PRODUCTION`，但不应阻止 Development/Simulation 启动。

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
