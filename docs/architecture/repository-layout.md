---
doc_id: DOC-ARCH-007
title: 目标仓库结构
status: baseline
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [12, 13, 41, 70, 71]
last_reviewed: 2026-08-27
---

# 目标仓库结构

## TASK-P3-17 audit conclusion

Exit Audit只新增P3 report/manifest并同步既有治理Markdown；业务、Schema、migration、dependency、tests、workflow与Frontend implementation相对Diff base零差异。下载和本地machine evidence继续位于ignored `build/**`，未写入正式源目录。

## TASK-P3-16 localization layout delta

本Task新增`frontend/src/i18n/`八个typed locale/registry/formatter/coverage模块、三份focused Vitest、一个双语Playwright spec及`frontend/scripts/i18n-evidence.mjs`，并有界修改既有P3页面、控件、两份E2E、style和required workflow的additive evidence step。`build/validation`与browser/provider输出保持ignored；未新增route、backend、Schema、migration、dependency/lock、P4或Production目录。Implementation exact provider已复验该79-path边界，本closure不新增业务路径。

## TASK-P3-15 governance and planning delta

Implementation只修改`scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py`与命中治理文档，增加phase-plan amendment discovery与回归。Provider通过后的closure重命名P3-15卡，新增P3-16/P3-17卡和`docs/frontend/official-zh-cn-terminology-map.md`；没有新增业务目录、Schema、migration、dependency、workflow、Frontend source、P4或Production路径。Ignored `build/traceability/TASK-P3-15-report.json`及provider下载不进入文档inventory。

## TASK-P3-14 layout delta

本Task仅新增`backend/app/application/p3_gate_report.py`、两份Backend Gate test、`frontend/playwright.p3-gate.config.ts`与`frontend/scripts/p3-gate-evidence.mjs`，并更新既有CI与命中文档。报告、Playwright输出和provider下载均位于ignored `build/`；没有新增Schema、migration、dependency、fixture、runtime service、P4或Production路径。

## TASK-P3-13 layout additions

新增Backend `application/export_downloads.py`与`jobs/export_package_store.py`，并有界扩展standard package、worker、HTTP contracts/router/check和对应tests。Frontend新增`api/commands.ts`、schedule-actions/approval/publication/export/audit feature目录、human-control unit/E2E tests与`.env.e2e`；既有Gantt/page/client/runtime/styles/evidence按allow-list扩展。Workflow只更新human-control E2E/machine step名称及既有artifact收集路径。

未新增Schema、migration、dependency、lock、domain state、repository persistence、P4/external/Production目录。`build/playwright/**`、validation/trace reports、dist/node_modules继续ignored；`.env.e2e`是无credential的版本化test configuration，须显式纳入Task提交。

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
| `frontend/` | P3-11 exact package/lock、Vite/TypeScript/ESLint、API/app/components/pages/styles与unit/component evidence scripts | 只形成read-only workspace；Gantt/load/comparison/actions/browser E2E/Production hosting未形成 |
| `benchmarks/` | P2 versioned profile/baseline | 不表示Frontend容量或Production SLA |
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

## TASK-P2-09 layout delta

新增`simulation/scenarios/p2_correctness.py`、四个聚焦测试文件、两组deterministic Golden目录和一个五例synthetic correctness matrix目录；CI与既有integration contract只增加machine evidence接线。Fixture目录只保存versioned JSON与calculation note，不新增Schema、dependency、migration、Benchmark/Reference/Export、DB/API/Worker或P3目录。

## P3 layout allocation history

P3 transition时只新增`docs/tasks/P3/`中的16张Task卡；当时没有创建backend、schema、migration、frontend或workflow路径。后续P3-01形成docs/ADR，P3-02负责Schema/contracts，P3-03负责persistence/migration，P3-04～10负责application/API/jobs/exporters；P3-11形成Frontend read-only foundation，P3-12形成read-only visualization/browser slice，P3-13形成human-control E2E，P3-14形成有界Gate evidence。当前P3卡总数为18张且P3-00～17均为`done`；P3-17为`IMPLEMENTATION_PROVIDER_VERIFIED_CLOSURE_PENDING`的final Audit，新增正式Exit报告后Markdown总数为169。

## TASK-P3-11 Frontend layout

`frontend/src/api`只拥有canonical query、checked read carrier、GET client、runtime/session boundary；`frontend/src/app`只组合router/query cache；`components/pages`只显示server projection和状态。`frontend/scripts`只生成SCA/license/build boundary evidence，`frontend/tests`使用in-memory versioned carrier且不安装browser。`dist/node_modules/coverage/*.tsbuildinfo`均ignored；仓库没有新增SSR/server、Gantt/load/comparison/control或P4目录。

Implementation artifact `9552386549`精确复验上述23个source files、13 routes、7 states和read-only/P4/Production absence；Task=`done`。该layout事实不授权P3-12/13新增目录或Production hosting。

## TASK-P3-12 visualization layout

新增`frontend/src/features/gantt/{GanttPage,GanttTimeline}.tsx`、`features/resource-load/ResourceLoadPage.tsx`、`features/version-comparison/VersionComparisonPage.tsx`、`app/useWorkspaceView.ts`、三个focused Vitest文件、`e2e/read-only-visualizations.spec.ts`与`playwright.config.ts`；既有API/app/routes/styles/tests/evidence script按Task allow-list扩展。`frontend/package.json`只增加E2E命令，`package-lock.json`与24个pins零差异；`node_modules/dist/test-results/coverage/*.tsbuildinfo`及machine/browser artifacts保持ignored。

Backend仅既有CI contract test核对required workflow接线；没有新增或修改business/API module、Schema、migration、dependency、command/action、P4或Production hosting目录。Implementation artifact `9555196470`精确复验28个Frontend source files、18 routes、7 states及上述absence flags，故该layout slice随TASK-P3-12标为`done`；P3-13、P4与Production目录仍未形成。
