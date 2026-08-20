---
doc_id: DOC-SIM-001
title: FactoryProfile 合同
status: baseline
spec_version: 0.3.0
phase: P0-P1
normative: true
source_sections: [38, 43, 44, 45, 56, 104]
last_reviewed: 2026-08-20
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

## v1 machine contract

[`factory-profile.v1`](../../schemas/scenario/factory-profile.schema.json) 区分 `profile_contract_version` 与 `profile_version`，根对象强制 `synthetic_only=true`、拒绝未知字段且无 default。v1 固定 topology/workshop/line count ranges、resource target/capability pool、operation/candidate/routing-depth/cross-workshop ranges、calendar pattern/fragmentation、order count/due pressure，以及 `supported_capabilities`/`expected_rejections`。

Schema 只能限制 range 端点类型与上下界域；pure [`validate_factory_profile_contract`](../../backend/app/simulation/profiles/contracts.py) 额外检查 `minimum <= maximum`、stable ID/SemVer、capacity=1 与 capability registry status。`SCHEMA-PROFILE-P0-05` 只是 synthetic Schema sample，其 `1`/`0` 值不批准通用工厂、不关闭 OPEN-003/004，也不属于 Scenario Library。

## SIM-MINIMAL-001 profile asset

[`PROFILE-SIM-MINIMAL-FJSP@1.0.0`](../../fixtures/deterministic/SIM-MINIMAL-001/factory-profile.json) 是首个正式、但仅供 correctness 的 Profile asset：range 精确绑定到 2 workshops、2 lines、3 resources、3 operations、candidate count 1～2、routing depth 3、cross-workshop ratio 0.5 和一个 maintenance fragment。它引用 SIM-ASSUMPTION-006～009 并声明 `synthetic_only=true`。

这些单值 range 只保证 `SIM-MINIMAL-001@1.0.0` 的手算规模，不定义初始 Scenario Library 五类 Profile 的通用参数、XS benchmark baseline 或生产容量；Profile 语义变化必须发布新 asset version，不能覆盖本 `1.0.0`。

## SIM-P1-INGRESS-001 profile asset

[`PROFILE-SIM-P1-INGRESS-001@1.0.0`](../../fixtures/synthetic/SIM-P1-INGRESS-001/factory-profile.json)固定2 workshops/lines、4 capacity-1 resources、2 orders、3-operation chain、2 candidates、1 calendar fragment和0.5 cross-workshop range，并声明七项已支持capability。Generator先冻结全部消费字段，再以命名seed从range选择；mutable JSON在运行中不能改变layer结果。

duration/quantity/timeline值不是Profile v1字段，故由`PLANTNEXUS-P1-CANONICAL-IMPORT-GENERATOR@1.0.0`的版本化算法和`SIM-ASSUMPTION-010`明确限定，而不伪造Profile schema default。该小型asset不是通用XS/Benchmark或Production Profile；任何range或算法变化都必须提升相应asset/generator version。
