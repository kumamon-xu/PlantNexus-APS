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

P0 必须建立最小确定性场景，至少包含：

- 2 workshops；
- 3 resources；
- multiple candidate resources；
- cross-workshop dependency；
- maintenance interval；
- 人工给出的正确 schedule。

数据量必须足够小，使评审者能手算或用独立 brute force 验证。

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

## 非法 Fixture

P0 至少创建三类明确非法输入/计划；建议覆盖 no resource、conflicting lock/horizon、route cycle/calendar/precedence。每个 Fixture 包含 expected error/category/Constraint ID，不以“测试失败”作为唯一说明。

Fixture 和 expected artifact 必须版本化并记录来源；Synthetic 与 Historical 目录不得混用。
