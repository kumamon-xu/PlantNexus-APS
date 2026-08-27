---
doc_id: DOC-PHASE-CURRENT
title: 当前阶段
status: living
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [73, 74, 75, 76, 110, 111]
last_reviewed: 2026-08-27
---

# 当前阶段：P4 — Dynamic Replanning

## 最近完成 Task

- Owner：[TASK-P4-05 — Freeze Window and Effective Lock Projection](tasks/P4/TASK-P4-05-freeze-window-and-effective-lock-projection.md)
- Status：`done`
- Validation profile：`HIGH_RISK`
- Immutable Diff base：`e7b96e28913e7eb5be63ae4265c09f8281456b1c`
- Authorization：用户已于 2026-08-27 单独授权 TASK-P4-05

目标是形成 versioned Simulation freeze policy、solver-neutral effective-lock projection 与独立 fail-closed precheck。COMPLETED、RUNNING、显式 HARD、freeze-derived HARD 和 SOFT 的优先级与半开 freeze window 必须可确定重放。

HIGH_RISK本地验收已全部通过。Implementation `2d0ca8723b18dc08a57d12f4e26db3fae9f46a35`的required `validate` run/job=`33077329890`/`98534856259`由GitHub Actions app `15368`成功提供；artifact `9648715231`未过期，下载复核确认exact SHA、Task、Diff base、八条Impact Rules、19/19 checks、`issues=[]`与freeze machine 7/7一致。本evidence-only closure据此把Task标为`done`；closure自身仍须post-push exact provider复验。

## 直接依赖

| Dependency | State | Reused evidence |
| --- | --- | --- |
| TASK-P4-01 | done | accepted Freeze/Stability/ChangeReport ADR baseline |
| TASK-P4-02 | done | versioned P4 machine contracts |
| TASK-P4-04 | done | event-derived Snapshot/fact projection |

启动门已经核验以上直接依赖的 compact manifest、状态与 Provider 结论。普通 Task 不递归下载或重放其全部祖先历史；身份不匹配、manifest 过期或 Phase Gate 时才展开原始 artifact。

## 当前边界

允许：

- Simulation-only freeze policy；
- base PUBLISHED ScheduleVersion 与新 Snapshot/Problem 的 effective-lock projection；
- 独立 precheck、对应 unit/property/mutation/CI contract；
- 当前 Task 卡逐字允许的 package export、workflow evidence 和治理文档。

禁止：

- 修改 PlanningProblem v2 Schema、migration、dependency/lock 或 state pair；
- 修改既有 formal Validator、CP-SAT Backend、strategy 或 objective；
- 实现 OBJ-002、ChangeReport、新 ScheduleVersion 或 Replan application；
- 实现 Simulator、API、UI、P5 能力或 Production default/authority。

Production freeze 仍由 OPEN-005 阻塞；Simulation 值不得外推为 Production policy。

## P4 Task 状态

| Task | Outcome | Status |
| --- | --- | --- |
| P4-00 | Phase transition and plan | done |
| P4-01 | Contract and ADR baseline | done |
| P4-02 | P4 machine contracts | done |
| P4-03 | Event/replan persistence | done |
| P4-04 | Event fact projection | done |
| P4-05 | Freeze window and effective locks | done |
| P4-06 | OBJ-002 and ChangeReport | planned |
| P4-07 | Lexicographic replan solver/validator | planned |
| P4-08 | Replan application and DRAFT lineage | planned |
| P4-09 | Execution Simulator core | planned |
| P4-10 | Disruption library and replay | planned |
| P4-11 | ChangeReport read/export | planned |
| P4-12 | Dynamic Replanning API | planned |
| P4-13 | Replanning UI/E2E | planned |
| P4-14 | Vertical Slice Gate | planned |
| P4-15 | Independent Exit Gate Audit | planned |

完整依赖、Outcome 与 Gate 见 [P4 Milestone](milestones/P4-dynamic-replanning.md) 和 [Task Index](tasks/README.md)。

## 下一步

1. 对本evidence-only closure的exact SHA完成required `validate`与artifact复验；
2. 确认main/origin/main/remote main一致且working tree clean后停止；
3. TASK-P4-06保持`planned`，只有用户另行明确授权且启动门重新通过时才可执行。

TASK-P4-14 的 PASS 不替代 TASK-P4-15 fresh independent audit；P4 Exit READY 也不自动进入 P5 或 Production。

## 证据与历史位置

- P4 当前语义与 Gate：[P4 Milestone](milestones/P4-dynamic-replanning.md)
- P4 Task 卡与顺序：[Task Index](tasks/README.md)
- P3 终态审计：[P3 Exit Report](milestones/P3-exit-gate-audit-report.md)
- P3 机器清单：[P3 Exit Manifest](milestones/P3-exit-gate-evidence-manifest.json)

本文件只保存当前快照，不保存逐 Task run/job/artifact/digest、测试计数或过往阶段日志。历史由已完成 Task 卡、Milestone Exit report、machine manifest 与 Git 保留。
