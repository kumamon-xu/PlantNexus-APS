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

## P0 machine envelopes

[`error.schema.json`](../../schemas/json/error.schema.json) 固定七类 category、稳定 `code`、message 与可定位 details envelope；[`validation-report.schema.json`](../../schemas/json/validation-report.schema.json) 固定 PASS/FAIL、problem hash 和 violation 的 `constraint_id`、severity、entity IDs、observed、expected rule、message。PASS 必须没有 violation，FAIL 必须至少一个。

TASK-P0-03 只发布顶层 skeleton。具体产品 error code registry、状态映射和每个 C-ID 的规则/正反例仍由 TASK-P0-04 建立；Schedule Validator mutation evidence 仍由 TASK-P0-07 建立。
