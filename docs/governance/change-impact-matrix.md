---
doc_id: DOC-GOV-010
title: 变更影响与必审文档矩阵
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 97, 98, 99, 100, 101, 102, 103, 104, 111]
last_reviewed: 2026-08-27
registry_version: 1.0.0
---

# 变更影响与必审文档矩阵

## 目的

本矩阵只回答两个机器可检查的问题：

1. changed path 命中了哪个稳定 Rule ID；
2. 为保证最低语义一致性，至少要复核哪一份核心文档。

它不是 Task 历史、验收日志或候选文档全集。每个 Task 的实际判定、例外、命令与证据保存在 Task 卡、机器报告和 Git 历史中，不回填到本文件。

## 精简原则

- 稳定 Rule ID 和 path glob 是长期接口，不因单个 Task 改名。
- Required documentation 是无条件最小集合，不是所有可能相关文档。
- Task 仍须根据行为变化补充直接语义所有者；仅因路径相邻，不要求更新整组文档。
- 同一 changed path 可以命中多条规则；当前 Task 必须声明全部实际命中的 Rule ID。
- 纯 `.gitkeep` 不参与影响匹配。
- 大型登记表按 Rule ID 或路径检索，不要求完整加载本文之外的历史材料。

## Machine-checkable rules

| Rule ID | Changed path globs | Required documentation |
| --- | --- | --- |
| IMPACT-SCHEMA | `schemas/**` | `docs/contracts/schema-index.md` |
| IMPACT-DOMAIN | `backend/app/domain/**` | `docs/domain/domain-model.md` |
| IMPACT-APPLICATION | `backend/app/application/**` | `docs/architecture/end-to-end-planning-flow.md` |
| IMPACT-IMPORT | `backend/app/importers/**`、`backend/app/normalization/**`、`backend/app/data_validation/**` | `docs/contracts/import-and-normalization.md` |
| IMPACT-SNAPSHOT | `backend/app/snapshots/**` | `docs/contracts/planning-snapshot.md` |
| IMPACT-PROBLEM | `backend/app/planning/problem/**` | `docs/contracts/planning-problem.md` |
| IMPACT-PLANNING-CONTRACTS | `backend/app/planning/contracts.py`、`backend/app/planning/contracts/**` | `docs/contracts/planning-problem.md` |
| IMPACT-POLICY | `backend/app/planning/policy/**` | `docs/contracts/planning-policy-and-solve-limits.md` |
| IMPACT-STRATEGY | `backend/app/planning/strategies/**` | `docs/planning/planning-strategies.md` |
| IMPACT-REPORTING | `backend/app/planning/reporting/**` | `docs/domain/kpi-contract.md` |
| IMPACT-BACKEND | `backend/app/planning/backends/**` | `docs/planning/solver-backend-contract.md` |
| IMPACT-VALIDATOR | `backend/app/planning/validation/**` | `docs/planning/schedule-validator.md` |
| IMPACT-DIAGNOSTICS | `backend/app/planning/diagnostics/**` | `docs/planning/infeasibility-diagnostics.md` |
| IMPACT-STATE | `backend/app/domain/state_machines/**`、`docs/domain/state-machines/**` | `docs/governance/traceability-matrix.md` |
| IMPACT-SIM-PROFILE | `backend/app/simulation/profiles/**`、`schemas/scenario/factory-profile*` | `docs/simulation/factory-profile.md` |
| IMPACT-SIM-SCENARIO | `backend/app/simulation/scenarios/**`、`schemas/scenario/scenario*` | `docs/simulation/scenario-spec-and-provenance.md` |
| IMPACT-SIM-GENERATOR | `backend/app/simulation/generators/**` | `docs/simulation/synthetic-generator-and-determinism.md` |
| IMPACT-SIM-EXECUTION | `backend/app/simulation/execution/**` | `docs/simulation/execution-simulator-and-disruptions.md` |
| IMPACT-BENCHMARK | `backend/app/simulation/benchmarks/**`、`benchmarks/**`、`scripts/run_benchmark.py` | `docs/simulation/benchmark-harness.md` |
| IMPACT-REFERENCE-SCHEDULER | `backend/app/simulation/baselines/**` | `docs/planning/reference-schedulers.md` |
| IMPACT-FIXTURE | `fixtures/**` | `docs/quality/fixtures-and-golden-tests.md` |
| IMPACT-API | `backend/app/api/**` | `docs/domain/error-model.md` |
| IMPACT-FRONTEND | `frontend/**` | `docs/frontend/README.md` |
| IMPACT-EXPORT | `backend/app/exporters/**` | `docs/contracts/export-package.md` |
| IMPACT-JOBS | `backend/app/jobs/**` | `docs/domain/state-machines/export-job.md` |
| IMPACT-INFRA | `infra/**`、`backend/app/infrastructure/**`、`backend/migrations/**`、`alembic.ini`、`.env.example`、`.github/workflows/**`、`docker-compose.yml` | `docs/architecture/configuration-environments-and-isolation.md` |
| IMPACT-DEPENDENCY | `pyproject.toml`、`uv.lock` | `docs/architecture/technology-stack.md` |
| IMPACT-VERSION-METADATA | `backend/app/__init__.py`、`pyproject.toml` | `docs/contracts/schema-versioning.md` |
| IMPACT-PHASE | `docs/milestones/**`、`docs/current_phase.md` | `docs/tasks/README.md` |
| IMPACT-GOVERNANCE-REGISTRY | `docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md` | `docs/governance/change-impact-matrix.md` |
| IMPACT-GOVERNANCE-VALIDATOR | `scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py` | `docs/quality/documentation-consistency-checks.md` |
| IMPACT-TESTS | `backend/tests/**` | `docs/quality/test-strategy-and-matrix.md` |
| IMPACT-DOCS | `docs/**`、`README.md`、`AGENTS.md` | `docs/README.md` |

## 路径到行为的补充审查

机器最小集合之外，按实际语义选择直接所有者：

| 行为变化 | 应追加审查 |
| --- | --- |
| Schema 兼容性、默认值或版本策略 | schema-versioning、对应 contract、migration/replay 文档 |
| 状态或转换规则 | 被修改的那一份 state-machine 文档、ADR、traceability |
| Solver 约束、目标或搜索策略 | constraint catalog、objective policy、backend contract、benchmark |
| Validator 判定或错误分类 | validator、error model、mutation/property test 文档 |
| 数据来源、lineage 或指纹 | data authority、provenance/versioning |
| CI required check、权限、artifact 或运行时 | CI gates；部署行为变化时再追加 operations/security |
| 依赖能力或许可证风险 | technology stack；确有新增风险时追加 risk register/ADR |
| API 或 UI 可观察合同 | 对应 API/workspace contract、state/error model、test strategy |
| Phase 状态或 Task 拓扑 | 当前 milestone、tasks index、current phase；不改历史阶段正文 |

“应追加审查”不表示一律修改。Task 的 Documentation impact rationale 应简短写明“更新”或“不变及原因”，无需逐项复制整个候选列表。

## Task 使用合同

Task 卡必须：

1. 在 Change-impact matrix rows reviewed 中声明实际命中的稳定 Rule ID；
2. 在 Documents to update 中包含全部机器最小文档；
3. 仅追加本次行为的直接语义所有者；
4. 对明显相关但不变的高风险合同给出一句理由；
5. 若 path 未命中任何规则，先新增有界规则，再继续实现。

校验器以不可变 Diff base 计算 committed range 与 working tree union。声明了但未实际命中的 Rule ID、遗漏的 Rule ID、遗漏的最低文档和越界路径都必须 fail closed。

## Documentation impact: none

只有同时满足以下条件时允许：

- 变更不改变用户可见、机器可见或运维可见合同；
- 不改变 Schema、状态、错误、权限、安全、依赖、版本、性能门槛或阶段事实；
- 没有新增/删除/重命名正式 Markdown；
- 机器影响规则仍被声明，且最低必审文档已完成复核；
- rationale 指向已复核的语义所有者，并说明为何无需修改。

none 表示“复核后无需改正文”，不是“跳过文档检查”。

## 维护边界

- 新增顶层实现目录且现有 glob 无法覆盖时，才新增 Rule ID。
- 改变表结构或解析格式时提升 registry_version，并同步校验器与测试。
- 仅收窄/扩展 required documentation 或 glob 时，保持稳定 ID，并在当前 Task 报告记录真实匹配结果。
- 禁止在本文件追加每个 Task 的 run ID、artifact digest、测试计数或完成历史。
