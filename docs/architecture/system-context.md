---
doc_id: DOC-ARCH-001
title: 系统上下文
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 3, 9, 15, 62, 63, 64, 67, 68]
last_reviewed: 2026-08-19
---

# 系统上下文

## 系统职责

PlantNexus APS 接收来自业务权威系统的计划输入，形成不可变快照和 Solver-neutral PlanningProblem，生成并独立验证计划草案，经计划员批准后发布至 MES 或标准成果包。异常与执行事实进入新快照并产生新 ScheduleVersion，历史版本不被覆盖。

```text
ERP / MES / WMS / CAM / Files
              │
              ▼
      PlantNexus APS
      ├─ Import & Data Health
      ├─ Snapshot & Planning Problem
      ├─ Strategy & Solver Backend
      ├─ Independent Validator
      ├─ Planning Workspace
      ├─ Version / Approval / Publish
      └─ Simulation & Benchmark (non-production)
              │
              ▼
MES Adapter / JSON / CSV / Excel / Audit Artifacts
```

## 外部参与者与系统

| Actor/System | 提供 | 接收/操作 |
|---|---|---|
| ERP | Order、BOM、Purchase Promise | 计划结果引用或回写取决于 OPEN-002 |
| MES | Execution、Machine Runtime State | 经批准的计划发布 |
| WMS | Physical Inventory 或物料就绪依据 | 当前不做完整库存平衡 |
| CAM | Processing Feature | V1 不做 APS+CAM 联合优化 |
| Planner | 业务策略、锁定、审批决策 | 查看、比较、驳回、批准、发布 |
| Developer/Benchmark operator | Scenario、limits、profiles | 仿真和 Benchmark 报告 |

## 信任边界

- AI 不是任何业务事实的权威来源。
- Solver 的候选结果在 Validator 通过前不可信。
- Simulation 资产不具备生产权威，生产环境默认不可访问 Simulation API。
- 外部输入必须先进入 Raw Staging、Normalization 和 Data Validation，不能直接进入 Solver。
