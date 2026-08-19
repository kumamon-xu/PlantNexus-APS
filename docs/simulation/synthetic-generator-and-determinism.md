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

## P0 protocol and primitive

[`contracts.py`](../../backend/app/simulation/generators/contracts.py) 分别定义 `TopologyGenerator`、`RoutingGenerator`、`OrderGenerator`、`CalendarGenerator`、`MaterialGenerator`、`ExecutionStateGenerator`、`LockGenerator`，以及最终 `SyntheticPackageGenerator`。所有层接收显式 `GenerationContext`，最终类型是 `GeneratedScenarioPackage`；没有协议返回 PlanningProblem、CpModel、Solver 或 persistence model。

[`SeedMaterial`](../../backend/app/simulation/generators/determinism.py) 以 root seed + Generator ID/version + namespace + label/index 通过 SHA-256 派生 63-bit seed/selection index。每层使用命名 child namespace，调用顺序和其他 layer 的采样次数不会移动其 stream；这只是确定性 primitive，不声明任何统计分布或真实工厂概率。

`canonical-json.v1` 使用 UTF-8、stable key sort、compact separators、原 Unicode并拒绝 NaN/Infinity；`dataset_hash` 是完整 Standard Import package canonical bytes 的 lowercase `sha256:`。P0 [`build_empty_import_package`](../../backend/app/simulation/generators/package_contract.py) 只输出 `records={}`，用于证明共同入口和 hash 合同，不猜 P1 canonical fields。TEST-SCENARIO-REPLAY 覆盖 same-input replay、seed/version change 和 layer order independence；Generator 真实分布/records 仍为 P1。
