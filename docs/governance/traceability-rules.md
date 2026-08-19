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

治理注册表使用 `registry_version: 1.0.0`。Requirement/NFR/ENG 的 `ALLOCATED` 只表示 ID 已稳定分配，不等同实现完成；实现状态只能来自真实 TEST/ARTIFACT。引用必须使用完整 ID，范围允许写成 `REQ-001～REQ-015`，但校验器会展开并逐项核对。

稳定根集合来自：

- `requirements-register.md`；
- `nfr-and-engineering-register.md`；
- `test-strategy-and-matrix.md` 中的 Test registry；
- `prod-open-register.md`、`sim-assumption-register.md` 和 `risk-register.md` 的独立命名空间。

`PROD_OPEN` 条目使用 `OPEN-NNN`；仿真假设使用 `SIM-ASSUMPTION-NNN`。两类状态和关闭证据不可互换。

## Task Card 要求

每张任务卡必须列出 Requirement/NFR/ENG、依赖、目标、输入、允许/禁止修改文件、输出、Schema/Migration、错误行为、测试、Benchmark、Scenario、验收命令、明确排除项、开放问题、假设和回滚。

任务过程中如果必须修改允许范围以外的文件，应停止，说明原因并先更新任务卡。禁止通过无边界重构完成局部任务。

## 完整性

- 没有 TEST 的 Requirement 不能被标记为已实现。
- 没有 Validator 证据的 Solver 结果不能成为可评审计划。
- 没有 ARTIFACT/manifest 的发布不能视为可追溯发布。
- 当前尚不存在的代码、测试和产物在矩阵中标记 `PLANNED`，不能填造链接。

## 自动校验

`scripts/check_docs.py` 执行以下治理检查：

1. registry 表结构、版本、ID 格式和定义唯一性；
2. 文档与测试代码中的 REQ/NFR/ENG/TEST/OPEN/SIM_ASSUMPTION/RISK 引用存在；
3. 每个已登记 REQ/NFR/ENG 在 traceability matrix 中恰有一行；
4. Task 的 Requirement/NFR/ENG、依赖、文档影响字段和创建路径有效；
5. traceability matrix 中的规范路径和实际 Artifact 链接存在，`PLANNED` 不被当成实现证据；
6. 使用 `--check-diff` 时，实际 Git diff 命中的 change-impact Rule ID 已在当前 Task 声明，且必审文档已列入 `Documents to update`；
7. `OPEN` 关闭记录字段完整，PROD_OPEN 与 SIM_ASSUMPTION 命名空间没有混用。

结构化报告 schema 为 `traceability-report.v1`，至少包含 Task、Git HEAD、changed paths、matched impact rows、expected/observed documents、missing trace refs、registry counts 和失败明细。失败返回非零退出码，不允许自由文本 skip。
