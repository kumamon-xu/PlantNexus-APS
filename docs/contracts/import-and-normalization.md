---
doc_id: DOC-CONTRACT-001
title: Import 与 Normalization 合同
status: baseline
spec_version: 0.3.0
phase: P0-P1
normative: true
source_sections: [0, 2, 10, 15, 16, 62, 63, 73, 74, 91, 95]
last_reviewed: 2026-08-19
---

# Import 与 Normalization 合同

## 管道

```text
Versioned Source Package
→ Raw Staging
→ Parse
→ Normalize fields/units/time
→ Validate references and capabilities
→ Canonical Dataset
→ PlanningSnapshot
```

Production Adapter、CSV、Excel 和 Synthetic Generator 必须输出同一 Standard Import Contract。禁止 Synthetic 输入绕过 staging、unit conversion 或 data validation。

## 原始数据保留

Raw Staging 应保留来源系统、来源版本、导入批次、文件 hash、原始行定位和接收时间，便于诊断但不能直接进入 Solver。

## 规范化

- 时间转换为 UTC，保留来源 timezone/offset 信息；
- duration 规范为整数秒；
- 单位转换规则版本化；
- ID/reference 采用稳定 canonical ID；
- 缺失权威字段不得用仿真或 AI 默认值补齐；
- Excel 禁止执行 macro 和外部公式。

## 拒绝条件

至少包括：route cycle、missing resource、invalid candidate resource、unit error、missing duration、unsupported capability、引用孤儿、非法时间区间。

错误必须包含 code、entity/row、field、observed value、expected contract、source location 和可操作说明。接口的真实字段映射由 OPEN-002/013/015 关闭。

## P0 executable skeleton

[`import-package.schema.json`](../../schemas/json/import-package.schema.json) 只固定 `import_package_version`、`package_id`、`source_versions`、`synthetic`、conditional `scenario_id` 与 `records` envelope。`records` 内字段在 P0 明确保持 opaque，因为 Adapter/单位/字段权威仍受 OPEN-002/013/015 阻塞；这不是允许输入绕过 P1 Normalization/Data Validation。

Production envelope 禁止携带 `scenario_id`；synthetic envelope 必须携带。Import pipeline、字段映射、单位转换实现和 canonical entity validation 仍为 P1 `PLANNED`。

## P0 Simulation output boundary

TASK-P0-05 的 `build_empty_import_package` 只生成符合 `import-package.v1` 的 synthetic metadata envelope：`synthetic=true`、显式 `scenario_id`、profile/scenario/generator source versions 和 `records={}`。它用于证明 Generator 终点是 Standard Import contract 以及 canonical serialization/hash 可重放，不生成任何 Factory/Order/Routing 字段，不执行 staging、Normalization、Data Validation、Snapshot 或 PlanningProblem builder。

Scenario manifest 的 `generated_at` 不进入 Import package，因此不参与 `dataset_hash`；相同 Profile/Scenario/Generator version/seed 的 canonical Import bytes 与 hash 相同。P1 填充 canonical records 时仍必须通过权威映射和正式数据质量链路，不能把本空 envelope 当作 pipeline PASS。
