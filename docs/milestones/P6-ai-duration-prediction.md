---
doc_id: MILESTONE-P6
title: P6 — AI Duration Prediction
status: planned
spec_version: 0.3.0
phase: P6
normative: true
source_sections: [15, 20, 83, 90]
last_reviewed: 2026-08-19
---

# P6 — AI Duration Prediction

P6 仅在 APS 核心稳定后进入。预测接口输出 `p50_seconds`、`p90_seconds`、`confidence`、`model_version`、`feature_schema_version` 和 `fallback_reason`。

低置信度必须回退标准 duration；回退语义受 OPEN-014 约束。AI 不改变 routing、resource compatibility、hard constraint、schedule state 或业务权重。

本阶段需要独立数据治理、模型版本、离线评估、漂移/回退监控和 provenance，不得以 AI 输出替代权威工艺数据。
