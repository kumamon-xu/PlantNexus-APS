---
doc_id: DOC-ARCH-002
title: 端到端计划链路
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 9, 10, 23, 24, 30, 32, 33, 35, 57, 67]
last_reviewed: 2026-08-19
---

# 端到端计划链路

```text
Versioned Input Package
→ Raw Staging
→ Normalization
→ Data Validation
→ immutable PlanningSnapshot
→ deterministic PlanningProblem
→ PlanningStrategy
→ SolverBackend
→ PlanningSolution
→ independent ScheduleValidator
→ DRAFT ScheduleVersion
→ READY_FOR_REVIEW
→ Human APPROVED
→ PUBLISHED
→ MES / Export Package
→ Execution Facts & Disruptions
→ new Snapshot / ReplanRequest
→ new ScheduleVersion
```

## 关键门

| 门 | 输入 | 通过条件 | 失败语义 |
|---|---|---|---|
| Import | 外部/仿真输入包 | 合同、单位和引用完整 | DATA_ERROR / DATA_REJECTED |
| Snapshot | 规范化数据 | immutable、hashable、provenance 完整 | MODEL_INVALID 或系统错误 |
| Problem | Snapshot + rules | deterministic、serializable、solver-neutral | MODEL_INVALID |
| Solve | Problem + Policy + Limits | 合法 Solver 状态与候选解 | INFEASIBLE / NO_SOLUTION_WITHIN_LIMIT / FAILED |
| Verify | PlanningSolution | C-001～C-011 全部独立验证 | VALIDATION_FAILED |
| Review | 已验证 ScheduleVersion | 人工批准 | REJECTED 或保留评审状态 |
| Publish | APPROVED version | 幂等、审计、不可变 | Publish/Export 明确失败状态 |

## Replan

Replan 不修改旧 ScheduleVersion。它使用旧版本、执行事实、新 Snapshot、冻结窗口和原因生成新版本，并输出 ChangeReport。旧计划 Hint 只帮助搜索，不能替代 HARD_LOCK 或稳定性目标。

## P1 implementation status

TASK-P1-03/04已形成Raw Staging与ReferenceFileAdapter；TASK-P1-05形成`RawImportRow → explicit MappingProfile/unit registry → canonical Import v2 bytes/hash`；TASK-P1-06形成canonical structure/reference/DAG/resource/capability/time/duration Data Validation与deterministic ImportQualityReport。Import门只有报告PASS/0 errors才通过，四类Gate问题使用exact DATA_ERROR，unsupported capability保持独立category。

TASK-P1-07现只在matching PASS report之后，以`order-expansion.v1`把source-explicit DemandOrder/ProductionOrder/Lot/Routing确定性展开为OperationInstance与逐lot precedence edge，并保留candidate duration/source、fact/lock和versioned lineage。当前链路因此止于纯Order Expansion输出；尚未创建immutable Snapshot、PlanningProblem或Solver。任何consumer不得从Adapter/Raw/Normalization或FAIL report绕过Data Validation进入Expansion，也不得把Expansion hash当作Snapshot/Problem hash；P0/P2 ScheduleValidator仍只验证candidate schedule，与本输入Gate不同。
