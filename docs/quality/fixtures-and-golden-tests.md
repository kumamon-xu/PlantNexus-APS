---
doc_id: DOC-QUAL-002
title: Fixture 与 Golden Test 规范
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [31, 43, 46, 71, 72, 76, 88]
last_reviewed: 2026-08-19
---

# Fixture 与 Golden Test 规范

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
