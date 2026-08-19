---
doc_id: DOC-QUAL-003
title: Validator Mutation Test 规范
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [30, 31, 86]
last_reviewed: 2026-08-19
---

# Validator Mutation Test 规范

Mutation Test 从一个已知合法计划出发，单次或受控组合地注入错误，证明 Validator 不依赖 Solver 的自我声明。

| Mutation | 期望 Constraint |
|---|---|
| missing operation / duplicate operation | C-001 |
| wrong resource / multiple selection | C-003 |
| machine overlap | C-004 |
| calendar overlap | C-005 |
| material/release early start | C-006 |
| completed/running fact change | C-007 |
| HARD_LOCK movement | C-008 |
| wrong precedence / max lag | C-002 |
| cross-workshop lag violation | C-009 |
| wrong duration | C-010 |
| horizon overflow/truncation | C-011 |

每个断言至少验证 `validation_passed=false`、正确 `constraint_id`、相关 entity IDs、observed 和 expected。只返回通用 `VALIDATION_FAILED` 而无细节不算通过。

Mutation 生成逻辑不得复用 Validator 的判断公式，以免测试与实现同源。
