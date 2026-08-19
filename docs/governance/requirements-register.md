---
doc_id: DOC-GOV-002
title: 核心需求注册表
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [3, 4, 5, 6, 107]
last_reviewed: 2026-08-19
---

# 核心需求注册表

| ID | Requirement | 首要验收证据 | 计划阶段 |
|---|---|---|---|
| REQ-001 | 自动读取版本化计划输入 | Import contract test、ImportRun provenance | P1 |
| REQ-002 | 数据标准化、单位转换和不可变快照 | Snapshot hash replay、unit rejection test | P1 |
| REQ-003 | 订单、批次和工序实例展开 | Expansion contract/property tests | P1 |
| REQ-004 | 单 PlanningRun 跨车间排程 | Cross-workshop golden/simulation | P2 |
| REQ-005 | 独立硬约束验证 | Validator mutation suite | P0-P2 |
| REQ-006 | 标准成果包输出 | Export package contract/idempotency test | P2-P3 |
| REQ-007 | ScheduleVersion、审批、锁定和发布 | State transition and immutability tests | P3 |
| REQ-008 | 异常重排 | Disruption replay、ChangeReport | P4 |
| REQ-009 | 全链路 Provenance | Manifest and audit evidence | P1-P4 |
| REQ-010 | AI 工时预测扩展接口 | Versioned prediction/fallback contract | P6 |
| REQ-011 | Synthetic Factory Generator | Deterministic dataset hash | P0-P1 |
| REQ-012 | Scenario Library | Versioned scenario catalog and replay | P0-P2 |
| REQ-013 | Execution / Disruption Simulator | Deterministic event stream and fact preservation | P4 |
| REQ-014 | Benchmark Harness | Versioned BenchmarkReport and profiles | P2 |
| REQ-015 | Reference Scheduler Baseline | Baseline comparison and warning behavior | P2 |

本表定义需求根 ID，不代替详细 Contract。任何生产代码应能通过 `REQ / NFR / ENG → SCHEMA / ARCH / CONSTRAINT → TASK → TEST → ARTIFACT` 链路解释其存在理由。
