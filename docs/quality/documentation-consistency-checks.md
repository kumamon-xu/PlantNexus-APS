---
doc_id: DOC-QUAL-007
title: 文档一致性自动检查合同
status: baseline
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [6, 98, 99, 100, 101, 103, 104]
last_reviewed: 2026-08-19
---

# 文档一致性自动检查合同

本文件定义 TASK-P0-02 应实现的文档/追踪校验器。当前仅有合同，尚无脚本或 CI PASS 证据。

## 输入

- 当前 Task Card；
- base/head 或 staged Git diff；
- `change-impact-matrix.md`；
- 文档元数据、注册表、Schema/Fixture/Benchmark manifests；
- 当前 Phase 和 Milestone。

## 必须检查

1. Task Card 包含非空 `Documentation impact`、`Documents to update`、`Traceability updates`；
2. `required` 时文档路径明确存在或由本 Task 创建，并包含在 allowed files；
3. `none` 时有非空理由和已审查的 impact-matrix 行；
4. 实际 diff 命中的矩阵行均已处理，不能只相信 Task 的预先声明；
5. 文档 metadata、doc ID、source sections、相对链接和 Markdown fence 有效；
6. Requirement/NFR/ENG/C/OBJ/TASK/TEST/ADR 引用存在且不重复；
7. Schema/Problem/Solver/Profile/Scenario/Generator 变化伴随相应版本和测试影响；
8. PROD_OPEN 与 SIM_ASSUMPTION 没有混用；
9. 只有当前 Phase 存在详细 Task Card；
10. 追踪矩阵只链接真实存在的代码、测试和 artifact。

## CI 分层

| 层 | 行为 |
|---|---|
| Local/Task acceptance | 对当前 Task 与 working diff 运行，失败不得标记 Done |
| Pull Request | 必需检查；阻止缺失文档影响、断链、版本漏更和越阶段任务 |
| Release | 在 PR 检查上增加 Artifact/manifest、Milestone Gate 和 production readiness 一致性 |

## 输出

结构化报告至少包含 check ID、severity、Task、changed paths、matched matrix rows、expected docs、observed docs、missing trace refs 和修复建议。

## Override

不允许用自由文本 CI skip 绕过。确需例外时必须在 Task Card 记录理由，提交 ADR 或明确批准记录，并仍保留检查报告。正确性、状态语义、数据隔离和发布门不得豁免。
