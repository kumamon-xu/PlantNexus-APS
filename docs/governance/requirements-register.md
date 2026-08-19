---
doc_id: DOC-GOV-002
title: 核心需求注册表
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [3, 4, 5, 6, 107]
last_reviewed: 2026-08-19
registry_version: 1.0.0
---

# 核心需求注册表

| ID | ID status | Requirement | 首要验收证据 | 计划阶段 |
|---|---|---|---|---|
| REQ-001 | ALLOCATED | 自动读取版本化计划输入 | Import contract test、ImportRun provenance | P1 |
| REQ-002 | ALLOCATED | 数据标准化、单位转换和不可变快照 | Snapshot hash replay、unit rejection test | P1 |
| REQ-003 | ALLOCATED | 订单、批次和工序实例展开 | Expansion contract/property tests | P1 |
| REQ-004 | ALLOCATED | 单 PlanningRun 跨车间排程 | Cross-workshop golden/simulation | P2 |
| REQ-005 | ALLOCATED | 独立硬约束验证 | Validator mutation suite | P0-P2 |
| REQ-006 | ALLOCATED | 标准成果包输出 | Export package contract/idempotency test | P2-P3 |
| REQ-007 | ALLOCATED | ScheduleVersion、审批、锁定和发布 | State transition and immutability tests | P3 |
| REQ-008 | ALLOCATED | 异常重排 | Disruption replay、ChangeReport | P4 |
| REQ-009 | ALLOCATED | 全链路 Provenance | Manifest and audit evidence | P1-P4 |
| REQ-010 | ALLOCATED | AI 工时预测扩展接口 | Versioned prediction/fallback contract | P6 |
| REQ-011 | ALLOCATED | Synthetic Factory Generator | Deterministic dataset hash | P0-P1 |
| REQ-012 | ALLOCATED | Scenario Library | Versioned scenario catalog and replay | P0-P2 |
| REQ-013 | ALLOCATED | Execution / Disruption Simulator | Deterministic event stream and fact preservation | P4 |
| REQ-014 | ALLOCATED | Benchmark Harness | Versioned BenchmarkReport and profiles | P2 |
| REQ-015 | ALLOCATED | Reference Scheduler Baseline | Baseline comparison and warning behavior | P2 |

本表定义需求根 ID，不代替详细 Contract。任何生产代码应能通过 `REQ / NFR / ENG → SCHEMA / ARCH / CONSTRAINT → TASK → TEST → ARTIFACT` 链路解释其存在理由。

`ALLOCATED` 只表示 ID 已稳定分配，不表示功能已经实现。ID 不得删除或复用；需求被取代时保留原行并改为 `RETIRED`，同时链接替代 Requirement/ADR 和迁移影响。修改表结构或 ID 生命周期语义必须提升 `registry_version`。

TASK-P0-03 review：REQ-001/002/003/009 已获得 versioned Schema/type/contract-test 落点，但 Import/Normalization、Snapshot/Problem builder、hash 与 end-to-end provenance 均未实现，因此所有根 ID 状态继续为 `ALLOCATED`，没有提升为业务完成状态，也不修改 registry format version。

TASK-P0-04 review：REQ-004/005 获得 C-001～C-018 rule/capability contract、ValidationReport v2 与 completeness tests；REQ-007 获得三套 state transition registry/test；REQ-008 只获得 capability/state contract boundary。没有 Solver、candidate ScheduleValidator、审批/发布持久化、Export worker 或 Replan implementation，因此相关 Requirement 仍为 `ALLOCATED`，registry format version 不变。
