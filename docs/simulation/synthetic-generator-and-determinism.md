---
doc_id: DOC-SIM-003
title: Synthetic Generator 与确定性
status: baseline
spec_version: 0.3.0
phase: P0-P1
normative: true
source_sections: [10, 41, 42, 73, 74, 104]
last_reviewed: 2026-08-20
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

## P0 deterministic fixture assembly

TASK-P0-06 的 `P0-MANUAL-FIXTURE-ASSEMBLER@1.0.0` 是 committed artifact identity，不是新增第八层随机 Generator。它把人工定义的 `SIM-MINIMAL-001@1.0.0` fixture-local records 放入同一 `import-package.v1` envelope，并复用 `canonical-json.v1` / SHA-256 得到 `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10`。seed 6001 是完整 provenance 输入；该版本没有随机采样。

[`golden_fixture.py`](../../backend/app/simulation/scenarios/golden_fixture.py) 只能重放 committed bytes/hash，不能构造 PlanningProblem、调用 Solver 或把 `sim-minimal-records.v1` 宣布为 P1 canonical fields。TEST-SCENARIO-REPLAY 因此已有 non-empty committed dataset slice；Topology/Routing/Order 等 protocol 的真实程序化 generation 和共同 Normalization pipeline 仍为 P1。

## P1 canonical generator v1

七个frozen pure layer现分别生成topology、routing、orders、calendars、material readiness、RUNNING execution facts与operation locks。每层使用`root/<layer>`命名child seed；scale selection、permutation、ratio quota和synthetic timeline均无global RNG或调用顺序状态。Profile提供count/range，Scenario提供ratio/complexity，其他合成数值由`SIM-ASSUMPTION-010`和generator version限定。

Package layer把primary/source references保留为source IDs，补齐显式UTC、quantity和duration unit，编码为ReferenceFileAdapter-v1 outer rows，经公开Normalization得到stable canonical ID/source/package bytes，再经Data Validation要求PASS/0。`synthetic-generation-manifest.v1`的generated-at不进入hash；本asset重放hash为`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`。Generator exact version mismatch、Production target、unsupported capability/Profile shape、Normalization或quality失败均显式拒绝。

Isolation test扫描所有Generator AST imports，禁止Application/Snapshot/Planning/OR-Tools/ORM。TASK-P1-10的Generator本身不生成Snapshot、Problem、Schedule或Solver，也不反向建立application common-ingress；TASK-P1-11由下游Application消费公开staging边界。Synthetic distribution始终不称为Production事实。

## TASK-P1-11 public staging handoff

`DeterministicSyntheticPackageGenerator.prepare_batch(context)`现是受支持的公开Raw Staging边界：它复用原七层版本检查与组合，返回immutable Simulation batch而不执行Normalization。原`generate()`改为先调用该方法，再执行既有Normalization/Data Validation/package manifest；因此不存在两套source-row构造逻辑，原Import bytes/hash保持不变。

Application作为下游consumer调用`prepare_batch()`并进入common pipeline；Generator本身仍无Application/Snapshot/Planning导入。TEST-SCENARIO-REPLAY现增加staging、Snapshot、Problem重放，但不改变Generator distribution/version或SIM-ASSUMPTION-010。

## TASK-P1-12 Exit Gate replay

P1-12再次运行`synthetic-generator-report.v1`得到7/7 PASS、16个非空collections、49 records和dataset hash `sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`；随后common-ingress报告以repeat=2确认Import/Snapshot/Problem完整bytes/hash不变。Generator version mismatch、Production target和四类source错误的拒绝路径仍由tests/machine报告覆盖。

审计没有修改Profile、Scenario、Generator、mapping、manifest、seed或SIM-ASSUMPTION-010。该small correctness asset不成为Benchmark baseline、真实工厂distribution或Production capacity evidence。

## P9 named benchmark composition

`simulation/benchmarks/p9_catalog.py` 在冻结 P2 blueprint 上增加有界扰动，再复用 P2 source assembler/P1 normalization 生成 canonical package；不执行 P2 correctness Solver replay，也不产生候选。命名子流取 `SHA256(catalog_version|B01|seed|label)` 前八字节大端整数，对范围宽度取模。交期标签为 `<job>/due`，增加 0～3 tick；工时标签为 `<job>/<operation>/<resource>/duration`，增加 0～2 tick。无全局 RNG，新增无关标签不移动既有子流。

catalog 与 holdout seal 必须匹配；开发和保留 seed 不交叉，未提供冻结预算访问记录拒绝保留生成。分布仅属于 P9 v1，变更须另立版本；旧 P1/P2 generator、seed、bytes、baseline 均不改。实际 Problem 由下游正式 Runtime 从 canonical 输入创建，生成器不反向调用 Solver 获取预期答案。

## P9-09 corrective qualification v2

The initial v1 qualification failed quality and remains immutable evidence. ADR-0021 adds bounded backend-local dispatch hints without changing the hard model, objective, limits or independent Validator. Catalog/holdout-seal v2 and SIM-ASSUMPTION-029 were recorded before Solver tuning: development seeds and the SHA child formula remain unchanged; independent holdout seeds are 920901/920902/920903. New development observations freeze a versioned v2 budget before holdout access; no threshold is derived from holdout. The runner defaults to v2; `--catalog-version v1` explicitly emits EXPOSED_V1_FAILURE_REGRESSION, never independent qualification. Both old regression and new qualification are required in CI. Original v1 budgets and failed reports remain available; no Production capacity/SLA inference.
