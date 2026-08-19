---
doc_id: MILESTONE-P1
title: P1 — Data & Snapshot
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [73, 74]
last_reviewed: 2026-08-19
---

# P1 — Data & Snapshot

## Outcome

建立 CSV、Excel、一个正式 Adapter、Raw Staging、Normalization、Data Validation、Order Expansion、PlanningSnapshot 和 hash，并让 Synthetic Generator 进入同一 Standard Import 链路。

## Gate

同 Scenario+seed 产生相同 import package、snapshot hash 和 planning problem hash；route cycle、missing resource、unit error、missing duration 明确拒绝。

## Boundary

本文件不是进入 P1 的授权，不创建 P1 Task Card。生产接口字段、单位和数据权威分别受 OPEN-002/013/015 约束。
