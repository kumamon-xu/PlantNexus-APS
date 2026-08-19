---
doc_id: DOC-DOM-006
title: 错误与求解状态模型
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [29, 32, 34, 60, 65, 91, 92]
last_reviewed: 2026-08-19
---

# 错误与求解状态模型

## 产品错误分类

| Category | 含义 | 示例 |
|---|---|---|
| DATA_ERROR | 输入格式、引用、单位或业务数据无效 | route cycle、missing resource |
| UNSUPPORTED_CAPABILITY | 输入要求当前明确不支持的能力 | sequence-dependent setup |
| MODEL_INVALID | 问题/模型合同或建模系统缺陷 | invalid CP-SAT model |
| INFEASIBLE | 当前快照与模型被证明无可行解 | 互相冲突的 HARD_LOCK |
| NO_SOLUTION_WITHIN_LIMIT | 时间内没有可认证结论 | Solver status UNKNOWN |
| VALIDATION_FAILED | Solver 候选解未通过独立 Validator | overlap、wrong duration |
| SYSTEM_ERROR | 非业务性系统故障 | DB/worker failure |

禁止将所有失败映射为 HTTP 500。

## Solver 状态映射

| Solver Status | Product Meaning |
|---|---|
| OPTIMAL | 已证明达到当前模型的最优标准 |
| FEASIBLE | 当前最好可行方案，未证明最优 |
| INFEASIBLE | 已证明当前模型无解 |
| UNKNOWN | `NO_SOLUTION_WITHIN_LIMIT`，不是 INFEASIBLE |
| MODEL_INVALID | 模型或系统缺陷 |
| CANCELLED | 用户或系统取消 |
| FAILED | 系统异常 |

## 无解诊断顺序

```text
Precheck
→ Pure Feasibility Solve
→ Assumption Groups
→ Conflict Explanation
```

除非算法证明，Assumption conflict subset 不得称为 minimal conflict set。诊断不得通过删除硬约束或修改输入事实获得“可行”。

## P0 machine contracts

TASK-P0-03 的 [`error.v1`](../../schemas/json/error.schema.json) 与 [`validation-report.v1`](../../schemas/json/validation-report.schema.json) 原 envelope 保持不变。TASK-P0-04 新增：

- [`error.v2`](../../schemas/json/error.v2.schema.json)：只接受 [`error-code-registry.v1`](../../schemas/rules/error-code-registry.v1.yaml) 中的 19 个 code，并验证每个 code 唯一映射到上述七类；
- [`validation-report.v2`](../../schemas/json/validation-report.v2.schema.json)：增加 `hard_violation_count`，PASS 必须为 0/空 violations，FAIL 至少 1；violation 只接受 C-001～C-011、severity=`HARD` 与 entity/observed/expected/message；
- `error.v1`/`validation-report.v1` 与 v2 不互换，consumer 必须显式选择版本。

关键 code family：

| Code | Category | 边界 |
|---|---|---|
| `UNSUPPORTED_CAPABILITY` | UNSUPPORTED_CAPABILITY | 已登记但当前禁止/延迟的 capability；不得静默忽略 |
| `INVALID_CAPABILITY_DECLARATION` / `DUPLICATE_CAPABILITY` | DATA_ERROR | 未登记或重复 capability declaration |
| `INVALID_STATE_TRANSITION` | DATA_ERROR | 不在 versioned transition table 的 pair；不是第八种顶层 category |
| `SCHEDULE_VALIDATION_FAILED` | VALIDATION_FAILED | C-001～C-011 violation envelope；不得只返回 false |
| `MODEL_INVALID` / `INFEASIBLE` / `NO_SOLUTION_WITHIN_LIMIT` | 同名 category | 三种结论保持独立，UNKNOWN 只映射 limit，不映射 infeasible |

`ContractViolation` 现使用同一 code registry 并暴露确定的 category，但仍只是 P0 数据合同 precheck，不是 HTTP mapping。

TEST-ERROR-MAPPING-001 已验证 YAML、纯枚举和 error.v2 code/category 一致。TASK-P0-07 的 fixture-local evaluator 对 FAIL report 逐 violation 映射 `error.v2`：category=`VALIDATION_FAILED`、code=`SCHEDULE_VALIDATION_FAILED`，detail 保留首要 entity、完整 entity IDs、constraint ID、observed value、expected contract 和 candidate source location；PASS 不生成 Error。13 个 mutation 的 exact Error 与 ValidationReport 均经现有 JSON Schema 验证。

该映射只覆盖 `SIM-MINIMAL-001-MUTATIONS@1.0.0` 的 P0 correctness 边界。HTTP status/API payload、状态持久化、正式 PlanningProblem/candidate 错误入口以及 Solver status/diagnostics 集成仍由后续 API/P2 Task 建立。
