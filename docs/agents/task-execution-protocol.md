---
doc_id: DOC-AGENT-003
title: Task 执行协议
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 98, 99, 100, 111]
last_reviewed: 2026-08-19
---

# Task 执行协议

## Before

1. 确认 Task 属于 `current_phase`；
2. 校验 Requirement/NFR/ENG、依赖和输入存在；
3. 校验 allowed/forbidden files；
4. 读取相关 Contract/Constraint/ADR；
5. 明确错误行为、测试、Benchmark 和 excluded scope。
6. 根据 `governance/change-impact-matrix.md` 完成文档影响分析；
7. 确认 `Documents to update` 均包含在允许修改范围内。

## During

- 先更新 Schema/contract，再实现 consumer；
- 以最小有界变更完成目标；
- 发现新的业务未知登记 PROD_OPEN；
- 使用仿真假设时登记 SIM_ASSUMPTION；
- 需要架构/语义改变时停止并提交 ADR；
- 不通过修改测试期望掩盖实现缺陷。
- 实际变更偏离原文档影响分析时，先更新 Task Card，再继续实施。

## After

1. 运行 Acceptance Commands；
2. 记录修改文件和结果；
3. 更新追踪矩阵；
4. 更新版本、manifest 和 changelog（如适用）；
5. 报告未关闭问题、Benchmark 影响和回滚；
6. 核对 `Documents to update` 已全部处理；
7. 运行文档一致性检查；
8. 检查没有超出明确排除项。

如果没有文档变化，完成证据必须包含 `Documentation impact: none`、理由和 change-impact matrix 审查结论。空白、`N/A` 或“无需更新”但无理由均不合格。

Task Done 不等于 Milestone Done。
