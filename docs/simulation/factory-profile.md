---
doc_id: DOC-SIM-001
title: FactoryProfile 合同
status: baseline
spec_version: 0.3.0
phase: P0-P1
normative: true
source_sections: [38, 43, 44, 45, 56, 104]
last_reviewed: 2026-08-19
---

# FactoryProfile 合同

FactoryProfile 描述一类虚拟工厂的结构和分布边界，不描述单次订单或异常事件。

```yaml
profile_id: machine_shop_medium
profile_version: 1.0.0
synthetic_only: true
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

示例值只展示 Schema 形状，不是批准的生产参数，也不是当前场景库的默认值。

## 必须表达

- profile ID/version 与 `synthetic_only=true`；
- topology/resource/capability 分布；
- routing depth、candidate density；
- calendar fragmentation 模式；
- order/due pressure 范围；
- 适用和预期拒绝的 capability。

Profile 任意语义变化必须更新 version，否则 Historical Benchmark 无法重放。Profile 不能成为 Production Config 的默认值。
