---
doc_id: DOC-CORE-004
title: 能力矩阵
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [7, 8, 27, 43, 81, 82, 107]
last_reviewed: 2026-08-19
---

# 能力矩阵

## 状态定义

- `V1_SUPPORTED`：属于 V1 合同范围，但仍需按 Milestone 实现。
- `DEFERRED`：明确推迟，不能由当前实现近似。
- `UNSUPPORTED`：系统需要识别并返回 `UNSUPPORTED_CAPABILITY`。
- `PROD_OPEN`：能力边界依赖真实业务确认。

## V1 能力

| Capability | 状态 | 主要阶段 | 说明 |
|---|---|---|---|
| SINGLE_FACTORY_MULTI_WORKSHOP | V1_SUPPORTED | P1-P3 | 单 PlanningRun 跨车间统一计划 |
| DAG_ROUTING | V1_SUPPORTED | P1-P2 | 必须校验无环，不只依赖 sequence_no |
| ALTERNATIVE_RESOURCE | V1_SUPPORTED | P2 | 候选设备 ExactlyOne，设备工时可不同 |
| MACHINE_CALENDAR | V1_SUPPORTED | P2 | 非抢占任务不得跨不可用区间 |
| RELEASE_AND_MATERIAL_GATE | V1_SUPPORTED | P1-P2 | Solver 不推断物料齐套 |
| RUNNING_OPERATION | V1_SUPPORTED | P2 | 历史事实保留，未来剩余占用固定 |
| HARD_SOFT_LOCK | V1_SUPPORTED | P2-P4 | HARD 为约束，SOFT 为稳定性目标 |
| APPROVAL_AND_PUBLICATION | V1_SUPPORTED | P3 | 仅 APPROVED 可发布，发布版本不可变 |
| DYNAMIC_REPLANNING | V1_SUPPORTED | P4 | 保留事实、锁定并输出 ChangeReport |
| SECONDARY_CAPACITY | UNSUPPORTED | P5 candidate | 不得忽略或近似 |
| SEQUENCE_DEPENDENT_SETUP | UNSUPPORTED | P5 candidate | PROFILE-C 用于验证拒绝路径 |
| BATCH_PROCESSING | UNSUPPORTED | P5 candidate | 需独立能力包 |
| SPLIT_MERGE | UNSUPPORTED | P5 candidate | lot splitting 仍为 PROD_OPEN |
| MATERIAL_COMPETITION | UNSUPPORTED | P5 candidate | V1 只接受 material_ready_at |
| PREEMPTIVE_OPERATION | UNSUPPORTED | P5 candidate | V1 为非抢占 |
| BUFFER_CAPACITY | UNSUPPORTED | P5 candidate | 不可静默忽略 |
| ALTERNATIVE_MATERIAL | UNSUPPORTED | future | 不做替代料优化 |
| MULTI_FACTORY | UNSUPPORTED | future | V1 仅单工厂 |
| AI_DURATION_PREDICTION | DEFERRED | P6 | 低置信度必须回退标准工时 |
| REALITY_CALIBRATION | DEFERRED | P7 | 需要真实匿名历史快照 |

## 新增高级能力的最小交付

每项能力必须独立提供 ADR、Schema、Capability Contract、Solver 实现、Validator 实现、正反 Fixture、Benchmark 和 Feature Flag。缺少任一部分不得宣称支持。
