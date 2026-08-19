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
