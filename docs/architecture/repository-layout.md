---
doc_id: DOC-ARCH-007
title: 目标仓库结构
status: baseline
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [12, 13, 41, 70, 71]
last_reviewed: 2026-08-19
---

# 目标仓库结构

TASK-P0-01 已建立可构建的顶层仓库边界；TASK-P0-02 在该边界内扩展 `scripts/check_docs.py` 并新增唯一的治理 unit test。以下树继续定义 P0 的目标责任结构，不因治理脚本而提前创建业务模块实现。

```text
/
├─ AGENTS.md
├─ README.md
├─ .python-version
├─ pyproject.toml
├─ uv.lock
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ application/
│  │  ├─ domain/
│  │  ├─ infrastructure/
│  │  ├─ importers/
│  │  ├─ normalization/
│  │  ├─ data_validation/
│  │  ├─ snapshots/
│  │  ├─ planning/
│  │  │  ├─ problem/
│  │  │  ├─ policy/
│  │  │  ├─ preprocessing/
│  │  │  ├─ strategies/
│  │  │  ├─ backends/cp_sat/
│  │  │  ├─ validation/
│  │  │  ├─ diagnostics/
│  │  │  └─ kpi/
│  │  ├─ simulation/
│  │  │  ├─ profiles/
│  │  │  ├─ scenarios/
│  │  │  ├─ generators/
│  │  │  ├─ execution/
│  │  │  ├─ baselines/
│  │  │  └─ benchmarks/
│  │  ├─ exporters/
│  │  └─ jobs/
│  ├─ migrations/
│  └─ tests/
│     └─ unit/test_check_docs.py
├─ frontend/
├─ schemas/{json,scenario}/
├─ fixtures/{deterministic,infeasible,synthetic,future_capabilities,historical}/
├─ benchmarks/{profiles.yaml,baselines/}
├─ docs/
├─ scripts/
│  └─ check_docs.py
└─ infra/
```

机器可执行的 Schema、Fixture 和 Benchmark 数据不放入 `docs`；文档只解释其语义并链接实际文件。

## 当前实现状态

| 路径 | P0-01 状态 | 后续边界 |
|---|---|---|
| `backend/app/` | 可安装的空应用包；只登记 code/spec/schema 占位版本 | Domain、API、Planning、Simulation 行为由各自 Task 实现 |
| `backend/tests/` | 已有治理 validator unit test；其他测试类型仍为占位 | 业务/Contract/Golden 等测试由交付对应行为的 Task 增加 |
| `frontend/`、`schemas/`、`fixtures/`、`benchmarks/`、`infra/` | 目录占位 | 不表示 Frontend、Schema、Fixture、Benchmark 或基础设施已形成 |
| `scripts/check_docs.py` | 文档结构、registry/reference、Task、traceability 和 diff/impact 检查 | CI 强制集成与更高 Gate 属于 TASK-P0-08/09 |
| `docker-compose.yml` | 尚未创建 | 工程与基础设施骨架由 TASK-P0-08 处理 |

构建与烟雾命令以根 `README.md` 和当前 Task Card 为准。当前结构保持 Modular Monolith 边界，并未创建 API Process、Solver Worker 或 CP-SAT 实现。
