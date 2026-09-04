---
doc_id: DOC-ARCH-001
title: 系统上下文
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 3, 4, 5, 9, 12, 15, 30, 62, 63, 64, 65, 67, 68, 95, 101, 113, 114]
last_reviewed: 2026-09-04
---

# 系统上下文

## P8 Headless target and current status

P8固定APS的外部产品边界为宿主平台提交的versioned canonical JSON。ERP、MES、WMS、CAM、文件和人工录入均先由宿主平台采集、映射与治理；APS不持有其连接器、数据库或凭证。宿主平台和后续可选独立Frontend都只消费同一Headless HTTP API。企业业务适配由独立Enterprise Extension通过Extension SDK实现并只在APS Runtime内运行；它不是外部系统连接器，也不改变客户端边界。

该边界目前已有accepted架构、人类治理合同和schema set `2.10.0`的canonical ingress/result、PlanningRun机器合同，但还不是可调用的Headless能力。当前仍只有29项既有HTTP operation，默认业务application/authorization adapter unavailable；P8 durable ingress、持久化、Worker、Runtime组合、Extension SDK、Registry和Developer Kit也尚未形成，P8-03～17必须逐项实施并验证。

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
      PlantNexus APS Runtime / Headless API
      ├─ Contract & Data Validation
      ├─ Snapshot & Planning Problem
      ├─ Extension SDK / Registry → Enterprise Extension
      ├─ Durable PlanningRun & Solver Worker
      ├─ Independent Validation Rule / Validator
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
| Enterprise Extension team | 通过指定SDK提交versioned extension artifact/config、独立Validator规则与兼容证据 | Developer Kit、conformance工具和Runtime装载结果；不得获得Core/DB/私有API权限 |
| Developer/Benchmark operator | Scenario、limits、profiles | 仿真和 Benchmark 报告 |

## 信任边界

- AI 不是任何业务事实的权威来源。
- Solver 的候选结果在 Validator 通过前不可信。
- Simulation 资产不具备生产权威，生产环境默认不可访问 Simulation API。
- 外部产品输入必须通过canonical JSON contract、Data Validation和不可变输入链，不能直接进入数据库或Solver。
- Reference file/Normalization仅是内部研发或迁移辅助，不是Production公共接口。
- 宿主传输的principal、scope和source reference仍须由APS验证，不能因来自宿主便自动成为authority。
- Extension是管理员批准并在build/deploy/startup装载的服务端可信代码，不是请求级上传脚本；它只能使用SDK，不能导入Core internal、直写数据库或复用Solver builder充当Validator。
- Runtime、SDK、Extension和Developer Kit版本必须进入run provenance；版本混用或自动企业升级必须fail closed。
