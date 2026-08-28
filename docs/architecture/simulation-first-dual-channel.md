---
doc_id: DOC-ARCH-004
title: Simulation-First 双通道架构
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 10, 37, 40, 41, 42, 62, 74]
last_reviewed: 2026-08-28
---

# Simulation-First 双通道架构

## TASK-P4-10 continuous replay isolation

五类disruption asset与orchestrator只存在于Simulation channel，并通过P4-09 standard event port组合P4-04/P4-08 owner contracts。Raw step envelope携带`production_binding=false`，baseline advance固定为`SIMULATION_NON_PRODUCTION`且无authority claim；任何Production environment/binding、P5 capability或跨plane evidence在首个有效step前拒绝。Production channel未注册scenario route、worker、connector或default。

## TASK-P4-09 common-path implementation

Simulation channel现有一个有界Execution Simulator core：versioned synthetic inputs经pure compile产生标准`execution-event.v1`完整prefix，先复用P4-04 strict validator，再只调用与`ExecutionFactProjectionService.ingest_event`结构兼容的公共端口。Core import/call guard明确排除Infrastructure/DB、Planning/Solver/Replan、API、Application shortcut、host clock和global random；machine harness再以真实P4-04 service验证端口，而不是用私有projector替代。

当前共同路径只到event ingress。后续fact/new Snapshot→ReplanRequest→P4-08 application必须由各自公开边界驱动；Simulator不自动调用或写入这些阶段。P4-10连续五类场景、Production channel/source/authority和external adapter均没有因本Task形成。

## TASK-P4-02 Simulation carrier channel

九份新sample及SIM-ASSUMPTION-016只属于Simulation channel；Production binding/target/authority没有已批准值并被Schema/precheck拒绝。ExecutionSimulationManifest描述未来common-path replay所需版本、seed、clock、stream和checkpoint，但不启动Simulator或生产旁路；P4-09/10仍须证明真正走同一event ingress。

## TASK-P4-01 common-path decision

ADR-0015现要求TASK-P4-09/10的Execution Simulator只输出标准ExecutionEvent，使用versioned virtual clock/seed/source position，并通过P4-04同一ledger/fact入口及P4-08同一application service。禁止simulation-only projector、direct Solver/Version write或自动approval/publish。五类异常必须在同一run中连续消费前一步明确基线，而非五个clean-state happy path。

Simulator仅允许Development/Test/Benchmark + SIMULATION + synthetic + `production_binding=false`；Production不注册其route/worker/authority。TASK-P4-09现形成core runtime与SIM-ASSUMPTION-018 correctness向量，但没有Production channel、外部集成、disruption distribution或capacity/SLA证据。

## 核心设计

Production 和 Simulation 只在数据来源及环境隔离上不同，从 Standard Import Contract 开始必须使用同一产品链路。

```text
Production Sources ─┐
                    ├→ Standard Import Contract
Scenario Generator ─┘             │
                                  ▼
Normalization → Data Validation → Snapshot → Problem
→ same Strategy → same Solver → same Validator → same Export
```

## 禁止捷径

- Simulator 直接构造 CpModel；
- Generator 直接构造仅 Solver 可识别的对象；
- Simulation 绕过数据质量校验；
- Simulation 调用特殊简化 Solver；
- 为了通过场景而在生产链路添加 synthetic-only 默认规则。

## 可重放标识

Synthetic 输入和成果必须记录：

```text
scenario_id
scenario_version
seed
factory_profile
profile_version
generator_version
generated_at
dataset_hash
```

同 ScenarioSpec、FactoryProfile、Generator Version 和 seed 必须得到相同 canonical dataset 和 hash。

## 隔离

- `synthetic=true` 是 Snapshot 的显式属性；
- 至少使用独立数据库（推荐 `aps_dev`、`aps_sim`、`aps_prod`）；
- Production 默认对 `/api/v1/sim/*` 返回 404/disabled；
- Simulation Config 不能覆盖 Production Business Policy。

## P0 executable boundary

TASK-P0-05 以七层 pure Protocol 固定 Generator 责任，并提供 `build_empty_import_package` 作为最小边界证据。该 primitive 的唯一数据输出是 `import-package.v1` metadata envelope，`records={}`；它不生成 PlanningProblem、Snapshot、CpModel 或任何生产字段。`ScenarioManifest v1` 引用该 Import package 并记录 Profile/Scenario/Generator/seed、目标环境、generated-at 与 dataset hash。

`canonical-json.v1` 的 hash 输入是完整 canonical Import package bytes，不含 manifest `generated_at`。相同 Profile/Scenario/Generator version/seed 得到相同 package/hash；generator version 或 seed 变化会进入 source provenance 并改变 hash。Development/Test/Benchmark 可创建 context，`production` 在 context 建立阶段以 `SYNTHETIC_REFERENCE_IN_PRODUCTION` 拒绝。

TASK-P1-03～05已形成双方共用的Raw Staging、Reference transport和Normalization primitive：Simulation batch必须携带一致Scenario/Profile/Generator/seed，Production batch禁止这些字段；两者随后使用同一MappingProfile/unit/time/ID/canonical serializer。TASK-P1-06新增单一`app.data_validation` evaluator，既不读取data plane也不提供synthetic-only规则；Production/Simulation canonical Import必须得到相同结构/reference/DAG/resource/capability/time/unit/duration判定。

TASK-P1-06完成时仍没有Synthetic Generator→staging orchestration、Order Expansion、Snapshot/Problem或common-ingress Gate；该历史边界解释为什么固定schema sample的quality PASS不能单独视为双通道闭环。后续TASK-P1-10/11已按下节形成对应实现，但Simulation仍不得伪造PASS report或绕过Data Validation。

## TASK-P1-10 executable synthetic channel

七层Generator现从frozen FactoryProfile/ScenarioSpec context与命名child seed生成source-shaped topology/routing/orders/calendars/material/execution/locks records，再进入Simulation StagedImportBatch、公开Normalization和Data Validation，形成非空Import v2及PASS/0 quality evidence。Canonical package hash覆盖Import完整bytes，不覆盖generator-local manifest的`generated_at`；同Profile/Scenario/generator/seed得到相同bytes/hash。

本Slice只形成synthetic channel到canonical Import gate；没有把Production source接入同一application use case，也没有构建Snapshot/Problem/Solver。TASK-P1-11 common-ingress evidence、独立Production/Simulation数据库和Production connector仍未形成，不能因source形状相同而宣布双通道Exit Gate完成。

## TASK-P1-11 shared application channel

Generator公开`prepare_batch()`和ReferenceFileAdapter现分别产生Simulation `StagedImportBatch`，然后同时进入唯一`CommonIngressPipeline`直到PlanningProblem。Reference侧使用temporary CSV表达同一synthetic source semantics，因此证明的是adapter/generator双入口共用产品链路，不是真实Production connector。

Application在Normalization前比对explicit expected plane，交叉输入以`DATA_PLANE_MISMATCH`拒绝。独立aps_sim/aps_prod数据库、network/role、Production API与发布隔离仍未形成；ADR-0009与RISK-007仍然有效。

## TASK-P1-12 Exit Gate audit

独立审计以`SIM-P1-INGRESS-001@1.0.0`/generator`1.0.0`/seed`20260820`执行两次Synthetic replay并用同义Reference CSV进入同一application链，Import/Snapshot/Problem完整bytes/hash parity与14/14 checks均PASS。Import、Snapshot和Problem hashes分别为`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`、`sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409`、`sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da`。

该PASS使总规§74的共同数据链Gate=`READY`，但Reference文件仍为synthetic temporary input、`production_binding=false`；独立Production/Simulation数据库与角色、真实connector、Solver/Validator/Export链仍未形成。P1-12没有进入P2。

## TASK-P2-09 Simulation correctness channel

新Scenario assembler从versioned blueprint产生source-shaped Raw rows，并复用P1 mapping/Normalization/Data Validation/Expansion/Snapshot/Problem公开边界；随后才调用P2 Global Strategy和formal Validator。它不允许直接Problem/CpModel构造，也不改写P1 Generator或Reference channel，因此新证据验证真实模块边界而不是测试捷径。

七例全部属于Simulation correctness；它们不会绑定Production source、修改Production policy、生成Reference Scheduler/Benchmark/Export或进入P3。真实双通道Production authority仍由后续OPEN closure和Task治理。
