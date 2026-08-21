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
| `frontend/`、`benchmarks/` | 目录占位 | 不表示 Frontend 或 Benchmark 已形成 |
| `api/`、`infrastructure/`、`jobs/`、`backend/migrations/`、`infra/Dockerfile`、`docker-compose.yml` | P0-08 health/config/log/connectivity/job/migration/container skeleton | 产品 API、业务 repository/task、Solver 与 production deployment 仍为后续 Task |
| `scripts/check_docs.py` | 文档结构、registry/reference、Task、traceability，以及 `Diff base..HEAD` + working tree 的 diff/impact 检查 | CI 强制集成与更高 Gate 属于 TASK-P0-08/09 |
| `.github/workflows/ci.yml` | P0-08 PR/push gate 编排 | 本地只验证 workflow contract；provider run/branch protection 需外部证据 |

TASK-P0-05 在 `simulation/profiles|scenarios|generators` 中加入纯标准库合同、七层 Protocol、seed/canonical package primitive 和 contract-check CLI；在 `schemas/scenario` 加入三份 v1 Schema 与三份 `.synthetic.json` sample。`simulation/execution|baselines|benchmarks`、`fixtures/**` 和 P1 pipeline 仍没有实现；Schema samples 不是 `SIM-MINIMAL-001`。

构建与烟雾命令以根 `README.md` 和当前 Task Card 为准。当前结构保持 Modular Monolith：health API 与通用 Celery Worker 可由同一 image 分进程启动，但没有产品 API、业务 Worker task、Solver Worker 或 CP-SAT 实现。

## P1 planning baseline

用户于 2026-08-19授权进入 P1后，`docs/tasks/P1/` 新增 TASK-P1-01～12；当前没有 P1业务代码。治理 validator从 `docs/current_phase.md`读取 phase并允许 P0 terminal history + P1 current cards，未来 P2+详细卡仍被拒绝。P1预期在既有 `importers/`、`normalization/`、`data_validation/`、`snapshots/`、`planning/problem/`、`simulation/generators/` 和 `application/`边界内逐 Task落地，不在本 planning baseline创建这些实现。

TASK-P1-01只修改 repository-governance边界：`scripts/check_docs.py`增加 phase policy与CI event-range Task discovery，`.github/workflows/ci.yml`使用中性 report/artifact并保留 P0全部 test/machine/build gates；`backend/tests/unit/test_check_docs.py`和`backend/tests/integration/test_ci_contract.py`覆盖负向路径。没有新增目录、业务模块、Schema、Fixture、Migration、dependency、Solver或 P2代码。

TASK-P1-02在既有`schemas/json`/`schemas/samples`边界新增canonical-records.v1、Import v2、Snapshot v2与synthetic contract samples，并在`backend/app/domain/canonical_records.py`新增pure JSON-compatible types/prechecks。没有创建`importers`、staging、normalization、data-validation、expansion、Snapshot/Problem builder、migration、API或Solver实现；后续模块只能消费已发布v2合同，发现缺口必须先走Schema升版。

## TASK-P2-08 layout delta

新增`backend/app/planning/strategies/{__init__,global_cp_sat}.py`、`planning/policy/delivery.py`、`planning/backends/cp_sat/{objectives,objective_strategy_check}.py`及对应unit/property/integration tests；既有Backend/mapper/foundation check与CI workflow仅做有界接线。没有新增Schema、fixture、benchmark profile、migration、DB/API/Worker、exporter或P3/P4目录；OR-Tools仍只存在于`planning/backends/cp_sat/`。
