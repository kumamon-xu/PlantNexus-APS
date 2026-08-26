---
doc_id: DOC-QUAL-002
title: Fixture 与 Golden Test 规范
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [31, 43, 46, 71, 72, 76, 88]
last_reviewed: 2026-08-26
---

# Fixture 与 Golden Test 规范

## TASK-P3-14 fixture reuse

Gate只重放已经登记的P2 correctness/XS fixtures与`SIM-P3-HUMAN-CONTROL-001@1.0.0`，使用固定version/seed/hash并在两轮间完全隔离。没有新增或修改fixture/golden/expected bytes，也没有引入定量假设；任何业务语义差异必须成为blocking gap而不是更新expected。

## SIM-MINIMAL-001

P0 首个确定性场景已固定为 [`SIM-MINIMAL-001@1.0.0`](../../fixtures/deterministic/SIM-MINIMAL-001/calculation-note.md)，包含：

- 2 workshops、2 production lines、3 capacity-1 resources；
- 1 order、3 operations，前两道 operation 各有快/慢 candidate resource；
- 同机首尾相接 interval、两条 precedence edge、一个 cross-workshop transport edge；
- heat resource 的一个 maintenance interval；
- 15 分钟 tick、4 小时 horizon 和人工给出的正确 schedule。

目录包含 versioned FactoryProfile/ScenarioSpec/Import/ScenarioManifest、人工 Golden Schedule、fixture-local expected validation/KPI 与计算说明。Import 的 canonical hash 为 `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10`；只读 [`golden_fixture.py`](../../backend/app/simulation/scenarios/golden_fixture.py) 重放 identity/hash，独立 [`test_sim_minimal_001.py`](../../backend/tests/golden/test_sim_minimal_001.py) 不信任 expected evidence 文本，直接复算 C-001～C-011、KPI 和 objective lower bound。

`golden-validation.v1` / `golden-kpi.v1` 是 fixture-local expected artifacts，不是 `validation-report.v2` / `kpi.v1` 的替代。C-007/C-008 因无 execution facts/locks 明确 `NOT_APPLICABLE`；TASK-P0-07 在独立 mutation 副本中增加这些事实，不修改正例。数据量保持足够小，使评审者可按计算说明手算。

## 目录

```text
fixtures/
├─ deterministic/
├─ infeasible/
├─ synthetic/
├─ future_capabilities/
└─ historical/
```

## Golden 断言

断言 feasibility、objective、C-001～C-011 和关键 KPI。不要对完整 operation ordering 或序列化噪声做脆弱快照比较。

TASK-P0-06 使用字段级断言和公式重算，而非比较完整 Gantt JSON。`TEST-GOLDEN-FJSP` 已形成 P0 positive correctness slice；未来 Solver/PlanningProblem integration 仍需 P2 扩展，不得从 committed hand schedule 推断 Solver 已实现。

## 非法 Fixture

P0 已创建 [`SIM-MINIMAL-001-MUTATIONS@1.0.0`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/calculation-note.md)：13 类声明式 mutation 覆盖所有 C-001～C-011，包含 exact expected ValidationReport/Error、coverage matrix 与人工 tick/秒说明。该 bundle 以 repository-relative path 和 base Import hash 引用 Golden，不复制后再覆盖其历史文件。

Fixture 和 expected artifact 必须版本化并记录来源；Synthetic 与 Historical 目录不得混用。mutation materializer 每次 deep-copy base JSON，test 验证输入对象不变；范围 gate 同时禁止 `/fixtures/deterministic/**` diff。该 negative bundle 是 P0 correctness fixture，不是生产数据、P1 canonical input 或 Solver infeasibility proof。

## TASK-P1-09 canonical Problem Golden

`test_p1_problem_replay.py`从P1 canonical Import→PASS report→Expansion→immutable Snapshot正式链重放，不读取P0 hand schedule。固定Snapshot hash `sha256:44f422…e591a`、Problem hash `sha256:6e4aff…dff72`、完整1827-byte canonical payload digest `sha256:1f00ad…08645`及1 resource/2 active operations/1 edge/0 relevant interval counts；重复构建、`verify_problem`、JSON round-trip和published `planning-problem.v1` Schema validation均PASS。

Golden断言固定身份、关键字段/count与Schema，不把完整JSON手工复制为脆弱fixture，也不形成Solver feasibility/objective/KPI结果。P0 `SIM-MINIMAL-001`及mutation bundle均未修改；Problem vector的任何合法语义变化必须通过builder/hash version规则更新并解释，不能覆盖历史hash。

## TASK-P1-10 generated ingress fixture

[`fixtures/synthetic/SIM-P1-INGRESS-001`](../../fixtures/synthetic/SIM-P1-INGRESS-001/calculation-note.md)只提交FactoryProfile、ScenarioSpec和人工可审查的生成说明；canonical Import由generator在测试/contract check中重放，不提交易漂移的完整JSON副本。固定evidence为16个非空collections、49 records、PASS/0、package ID `import-9eea9bd41216b3a2b337a83f2b6f5438a287f219251168ce8d574f4b9fb6b2c6`和hash `sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`。

该fixture不是Golden Schedule，不断言feasibility/objective/KPI，也不覆盖P0 deterministic/infeasible目录。生成语义变化必须新建generator/asset version并更新SIM assumption；P1-11 common ingress和P2 Solver Golden仍未形成。

## TASK-P2-06 derived temporal vectors

本Task不修改或新增committed fixture。Temporal unit/property/machine检查从versioned in-memory Problem v2构造precedence、historical anchor、fragmented calendar、release/material和cross-workshop cases；`SIM-MINIMAL-001`及其mutation bundle所有历史bytes保持只读。

这些derived vectors只证明边界correctness，不是TASK-P2-09 Golden Scenario或TASK-P2-12 Benchmark profile。任何未来持久化asset都必须新建版本、记录calculation note/hash/来源并更新SIM assumption，不能覆盖本Task证据。

## TASK-P2-07 fact/lock derived vectors

本Task不修改或新增committed fixture。Unit/property/machine checks从versioned in-memory Problem v2构造COMPLETED anchor、RUNNING remainder、HARD/SOFT locks、calendar/resource/horizon conflicts及self-conflict cases；`SIM-MINIMAL-001`和P0 mutation bundle历史bytes保持只读。

这些vectors形成C-007/C-008 bounded correctness evidence，但不是TASK-P2-09 Golden Scenario或TASK-P2-12 Benchmark profile。未来若持久化Running/Hard Lock asset，必须新建version、calculation note/hash/source并更新SIM assumption，不得把本Task随机或tiny值外推为Production分布。

## TASK-P2-09 committed correctness assets

[`P2-GOLDEN-JSSP`](../../fixtures/deterministic/P2-GOLDEN-JSSP/calculation-note.md)与[`P2-GOLDEN-FJSP`](../../fixtures/deterministic/P2-GOLDEN-FJSP/calculation-note.md)分别手算零迟交下界/最优解；[`P2-CORRECTNESS-MATRIX`](../../fixtures/synthetic/P2-CORRECTNESS-MATRIX/calculation-note.md)固定Cross Workshop、Calendar、Material Delay、Running与Hard Lock五例。全部asset/Profile/Scenario为`1.0.0`，seed为`20260901`～`20260907`，并由SIM-ASSUMPTION-011限定。

测试按字段断言assignment、status、objective/bound/gap、Validator与三层artifact hash，不比较无意义Gantt排序。P0/P1 assets保持逐字不变；任何新资产更正必须发布新version或superseding manifest，不能原地覆盖。
