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

TASK-P0-01 已建立可构建的顶层仓库边界，TASK-P0-02 建立治理 validator；TASK-P0-03 在既有边界内加入 Schema、纯合同类型和 contract tests，仍未创建业务数据管道或 Solver。

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
│     ├─ unit/test_check_docs.py
│     └─ contract/test_schema_contracts.py
├─ frontend/
├─ schemas/
│  ├─ json/{import-package,planning-snapshot,planning-problem,kpi,error,validation-report}.schema.json
│  ├─ samples/*.synthetic.json
│  ├─ data_dictionary.yaml
│  └─ scenario/                         # Profile/Scenario/Manifest v1 + Schema samples
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
| `backend/app/domain/`、`snapshots/contracts.py`、`planning/problem/contracts.py` | 纯标准库值语义、JSON-compatible type skeleton 和最小 contract precheck | Builder、hash、normalization、C-ID Validator 与 Solver 仍为后续 Task |
| `backend/tests/` | 治理 unit test + `TEST-CONTRACT-001` Schema contract tests | Integration/Golden/Property/Simulation/Benchmark 证据仍为后续 Task |
| `schemas/` | schema set `1.0.0` 的六份 JSON Schema、data dictionary 和明确 synthetic samples | Scenario/Profile Schema、正式 Fixture 和 builder output 尚未形成 |
| `frontend/`、`fixtures/`、`benchmarks/`、`infra/` | 目录占位 | 不表示 Frontend、Fixture、Benchmark 或基础设施已形成 |
| `scripts/check_docs.py` | 文档结构、registry/reference、Task、traceability，以及 `Diff base..HEAD` + working tree 的 diff/impact 检查 | CI 强制集成与更高 Gate 属于 TASK-P0-08/09 |
| `docker-compose.yml` | 尚未创建 | 工程与基础设施骨架由 TASK-P0-08 处理 |

TASK-P0-05 在 `simulation/profiles|scenarios|generators` 中加入纯标准库合同、七层 Protocol、seed/canonical package primitive 和 contract-check CLI；在 `schemas/scenario` 加入三份 v1 Schema 与三份 `.synthetic.json` sample。`simulation/execution|baselines|benchmarks`、`fixtures/**` 和 P1 pipeline 仍没有实现；Schema samples 不是 `SIM-MINIMAL-001`。

构建与烟雾命令以根 `README.md` 和当前 Task Card 为准。当前结构保持 Modular Monolith 边界，并未创建 API Process、Solver Worker 或 CP-SAT 实现。
