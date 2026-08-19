---
doc_id: DOC-GOV-004
title: 需求追踪规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [5, 6, 86, 98, 99, 111]
last_reviewed: 2026-08-19
---

# 需求追踪规则

## 标准链路

```text
REQ / NFR / ENG
→ SCHEMA / ARCH / CONSTRAINT
→ TASK
→ TEST
→ ARTIFACT
```

业务能力以 `REQ` 为根；可用性、可靠性、安全、性能和可追溯性等以 `NFR` 为根；CI、日志、Worker、版本管理等工程设施可以 `ENG` 为根，不强行映射业务需求。

## ID 规则

| 类型 | 格式示例 | 所在位置 |
|---|---|---|
| Requirement | `REQ-005` | `requirements-register.md` |
| NFR | `NFR-OBS-001` | `nfr-and-engineering-register.md` |
| Engineering | `ENG-VAL-001` | 同上 |
| Constraint | `C-001` | `planning/constraint-catalog.md` |
| Objective | `OBJ-001` | `planning/objective-policy.md` |
| Task | `TASK-P0-04` | `tasks/P0/` |
| Test | `TEST-VALIDATOR-MUTATION` | Quality/Test registry |
| ADR | `ADR-0005` | `adr/` |

## Task Card 要求

每张任务卡必须列出 Requirement/NFR/ENG、依赖、目标、输入、允许/禁止修改文件、输出、Schema/Migration、错误行为、测试、Benchmark、Scenario、验收命令、明确排除项、开放问题、假设和回滚。

任务过程中如果必须修改允许范围以外的文件，应停止，说明原因并先更新任务卡。禁止通过无边界重构完成局部任务。

## 完整性

- 没有 TEST 的 Requirement 不能被标记为已实现。
- 没有 Validator 证据的 Solver 结果不能成为可评审计划。
- 没有 ARTIFACT/manifest 的发布不能视为可追溯发布。
- 当前尚不存在的代码、测试和产物在矩阵中标记 `PLANNED`，不能填造链接。
