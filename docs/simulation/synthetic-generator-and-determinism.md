---
doc_id: DOC-SIM-003
title: Synthetic Generator 与确定性
status: baseline
spec_version: 0.3.0
phase: P0-P1
normative: true
source_sections: [10, 41, 42, 73, 74, 104]
last_reviewed: 2026-08-19
---

# Synthetic Generator 与确定性

Generator 按责任分层：

```text
TopologyGenerator
RoutingGenerator
OrderGenerator
CalendarGenerator
MaterialGenerator
ExecutionStateGenerator
LockGenerator
```

禁止将全部逻辑堆入一个大型脚本，也禁止直接生成 CpModel、IntervalVar 或特殊 PlanningProblem。

## 输出

Generator 输出符合 Standard Import Contract 的版本化 package，包括 canonical data、manifest 和 hash。此 package 随后走正式 Import/Normalization/Data Validation。

## 确定性合同

```text
ScenarioSpec
+ FactoryProfile Version
+ Generator Version
+ Seed
→ same canonical dataset
→ same dataset_hash
```

实现应控制所有随机源、稳定排序、时区、浮点/单位转换和序列化。失败场景必须能用 manifest 100% replay。

## 版本

生成逻辑、分布、默认策略或字段语义变化均更新 Generator Version。只修改性能但不改变数据内容时仍需记录代码提交，并用 regression test 证明 hash 未变化。
