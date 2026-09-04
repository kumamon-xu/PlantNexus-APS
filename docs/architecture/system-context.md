---
doc_id: DOC-ARCH-001
title: 系统上下文
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 3, 9, 15, 62, 63, 64, 67, 68, 113]
last_reviewed: 2026-09-04
---

# 系统上下文

## P8 Headless target and current status

P8固定APS的外部产品边界为宿主平台提交的versioned canonical JSON。ERP、MES、WMS、CAM、文件和人工录入均先由宿主平台采集、映射与治理；APS不持有其连接器、SDK、数据库或凭证。宿主平台和后续可选独立Frontend都只消费同一Headless HTTP API。

该边界目前是accepted架构和planned Milestone，不是已实现能力。当前仍只有29项既有HTTP operation，默认业务application/authorization adapter unavailable；P8-01～13必须逐项实施并验证。

## TASK-P3-17 audit conclusion

P3 Exit只验证内部Planning Workspace和Simulation publish/export边界；外部ERP/MES、Production identity/authority、真实工厂source与deployment均继续位于系统边界之外。TASK-P3-17本地READY不改变context ownership。

## 系统职责

PlantNexus APS 接收宿主平台提供的canonical计划输入及经授权执行事实，形成不可变快照和Solver-neutral PlanningProblem，生成并独立验证计划草案，经计划员批准后以API read model或标准成果包交还宿主。异常与执行事实进入新快照并产生新ScheduleVersion，历史版本不被覆盖。

```text
ERP / MES / WMS / CAM / Files / Human Input
              │
              ▼
 Host Platform: acquire / map / authorize / display
              │ versioned canonical JSON
              ▼
      PlantNexus APS Headless API
      ├─ Contract & Data Validation
      ├─ Snapshot & Planning Problem
      ├─ Durable PlanningRun & Solver Worker
      ├─ Independent Validator
      ├─ Version / Approval / Read / Export
      └─ Simulation & Benchmark (non-production)
              │
              ├──────────────► Host Platform UI
              └──────────────► Optional APS Frontend
```

## 外部参与者与系统

| Actor/System | 提供 | 接收/操作 |
|---|---|---|
| Host Platform | 已映射canonical JSON、verified principal/scope、上游authority/version reference | API状态、计划/read model、导出与审计引用；负责最终展示 |
| ERP/MES/WMS/CAM | 向宿主提供各自业务事实 | 不直接调用APS；其回写/展示由宿主负责 |
| Planner | 通过宿主或可选Frontend提供策略、锁定、审批意图 | 查看、比较、驳回、批准、发布 |
| Optional APS Frontend | 无独立业务authority | 与宿主使用相同公开API；可以完全不部署 |
| Developer/Benchmark operator | Scenario、limits、profiles | 仿真和 Benchmark 报告 |

## 信任边界

- AI 不是任何业务事实的权威来源。
- Solver 的候选结果在 Validator 通过前不可信。
- Simulation 资产不具备生产权威，生产环境默认不可访问 Simulation API。
- 外部产品输入必须通过canonical JSON contract、Data Validation和不可变输入链，不能直接进入数据库或Solver。
- Reference file/Normalization仅是内部研发或迁移辅助，不是Production公共接口。
- 宿主传输的principal、scope和source reference仍须由APS验证，不能因来自宿主便自动成为authority。
