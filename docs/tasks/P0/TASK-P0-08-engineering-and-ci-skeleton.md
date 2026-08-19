---
doc_id: TASK-P0-08
title: Engineering and CI Skeleton
status: planned
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [11, 12, 58, 65, 66, 71, 93, 95, 100]
last_reviewed: 2026-08-19
---

# TASK-P0-08 — Engineering and CI Skeleton

Requirement IDs: REQ-009

NFR / ENG IDs: NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-VER-001

Depends on: TASK-P0-01, TASK-P0-02

Goal: 建立 CI、structured logging、DB/Redis/Worker、health 和 job reliability 的可构建骨架，不实现业务 pipeline。

Inputs: technology stack、module boundaries、worker/idempotency/observability contracts。

Files allowed to change: project config/lock、`infra/**`、`backend/app/infrastructure/**`、health API、job base types、CI config、工程测试，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: business importer、snapshot builder、planning solver、frontend product pages、生产 Secret。

Implementation steps: 锁定依赖；建立 config layers；结构化日志/trace context；DB/Redis connectivity；worker heartbeat/lease/attempt/STALLED skeleton；readiness/liveness；CI lint/type/test/build。

Outputs: reproducible build、health checks、job base contract、CI skeleton。

Documentation impact: required

Documents to update: `docs/architecture/technology-stack.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/operations/README.md`、`docs/operations/security.md`（创建）、`docs/operations/observability-and-audit.md`（创建）、`docs/operations/worker-reliability-and-idempotency.md`（创建）、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: 依赖、配置、Job/health 行为、日志与 CI 从计划变为真实实现后必须形成可执行运维事实。

Change-impact matrix rows reviewed: jobs/worker；infrastructure/config/security；dependency/lockfile；API health；只修改文档。

Traceability updates: REQ-009、NFR-REL/SEC/OBS/PER、ENG-ARCH/VER、health/job/CI tests 和 build artifacts。

Schema changes: 仅工程 job metadata；若需 DB migration，保持最小且可回滚。

Migration: 提供 upgrade/downgrade 和空库测试。

Error behavior: dependency unavailable、stalled worker 和 config error 可区分；Secret 不进入日志。

Tests: config、health、migration、job lease/idempotency primitives、log redaction、文档一致性 validator、CI smoke。

Benchmark impact: 仅建立 PR Benchmark hook，不运行 Solver benchmark。

Simulation scenarios: 无。

Acceptance commands: `uv run ruff check .`、type check、unit/contract/integration smoke、container config validation。

Artifacts: lockfile、CI run、migration/test results、health output。

Explicitly excluded: PlanningJob 业务执行、真实 Solver、生产部署。

PROD_OPEN: OPEN-012 保持 OPEN。

SIM_ASSUMPTIONS: 无。

Rollback: 迁移 downgrade、恢复配置；不删除用户环境数据。
