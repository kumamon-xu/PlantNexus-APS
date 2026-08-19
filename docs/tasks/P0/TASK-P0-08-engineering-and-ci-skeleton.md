---
doc_id: TASK-P0-08
title: Engineering and CI Skeleton
status: done
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [11, 12, 58, 65, 66, 71, 93, 95, 100]
last_reviewed: 2026-08-19
---

# TASK-P0-08 — Engineering and CI Skeleton

Requirement IDs: REQ-009

NFR / ENG IDs: NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P0-01, TASK-P0-02

Goal: 建立 CI、structured logging、DB/Redis/Worker、health 和 job reliability 的可构建 P0 工程骨架，不实现业务 pipeline、业务作业或生产部署。

Inputs: `docs/architecture/technology-stack.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/quality/ci-gates-and-definition-of-done.md`、ADR-0002、ADR-0009 与总规完整复读。

Diff base: 94fc6ffed79d3c4945f6881ee566b01aced64b05

Files allowed to change: `/pyproject.toml`、`/uv.lock`、`/.env.example`、`/.github/workflows/ci.yml`、`/alembic.ini`、`/docker-compose.yml`、`/infra/Dockerfile`、`/backend/app/api/__init__.py`、`/backend/app/api/app.py`、`/backend/app/infrastructure/__init__.py`、`/backend/app/infrastructure/config.py`、`/backend/app/infrastructure/database.py`、`/backend/app/infrastructure/redis_client.py`、`/backend/app/infrastructure/health.py`、`/backend/app/infrastructure/logging.py`、`/backend/app/infrastructure/contract_check.py`、`/backend/app/jobs/__init__.py`、`/backend/app/jobs/contracts.py`、`/backend/app/jobs/idempotency.py`、`/backend/app/jobs/celery_app.py`、`/backend/migrations/env.py`、`/backend/migrations/script.py.mako`、`/backend/migrations/versions/0001_engineering_job_metadata.py`、`/backend/tests/integration/test_config_and_health.py`、`/backend/tests/integration/test_logging.py`、`/backend/tests/integration/test_job_reliability.py`、`/backend/tests/integration/test_migrations_and_infrastructure.py`、`/backend/tests/integration/test_ci_contract.py`、生成但不提交的 `/build/validation/TASK-P0-08-engineering.json` 与 `/build/traceability/TASK-P0-08-report.json`，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: `/schemas/**`、`/backend/app/__init__.py`、`/backend/app/domain/**`、`/backend/app/importers/**`、`/backend/app/normalization/**`、`/backend/app/data_validation/**`、`/backend/app/snapshots/**`、`/backend/app/planning/**`、`/backend/app/simulation/**`、`/backend/app/exporters/**`、除 `/backend/tests/integration/test_*.py` 明列文件外的 `/backend/tests/**`、`/scripts/**`、`/fixtures/**`、`/benchmarks/**`、`/frontend/**`、生产 Secret、CpModel、IntervalVar、OR-Tools、Solver/PlanningJob/Export/Publish 业务动作。若 health 以外的产品 API、业务状态机、Schema、Solver 或已有测试必须变化才能完成，则停止本 Task 并先修订边界。

Implementation steps: 锁定 Python 3.12 的 FastAPI/Pydantic Settings/SQLAlchemy/Alembic/PostgreSQL driver/Redis/Celery/structlog/OpenTelemetry/uvicorn 与测试依赖，不加入 OR-Tools；建立只从 `PLANTNEXUS_` 环境变量读取且 Production fail-closed 的配置，默认不读取 `.env`；实现递归 Secret/credential redaction、correlation/run/job context 与可选 OpenTelemetry trace/span 注入的 JSON 日志；实现 import-time 不连外部服务的 DB/Redis client 与 sanitized readiness probes；实现只包含 `/health/live`、`/health/ready` 的 FastAPI app；实现与 ExportJob 业务状态机分离的通用 JobRecord、heartbeat/lease/attempt/STALLED 纯原语及进程内 reference idempotency store，Celery app 不注册业务 task；提供只含通用工程元数据表的可回滚 Alembic migration；提供 Docker Compose/Postgres/Redis/API/Worker 开发骨架、构建 Dockerfile 与 CI lint/type/test/contract/build gates；以 integration tests 和 machine report 验证，不连接真实外部服务、不声称生产就绪。

Outputs: exact lockfile、fail-closed config、structured logging、lazy DB/Redis connectivity、health endpoints、通用 job/idempotency contract、可回滚工程 migration、Compose/Docker build config、CI workflow 与 `engineering-skeleton-report.v1`。

Documentation impact: required

Documents to update: `/README.md`、`/docs/current_phase.md`、`/docs/architecture/technology-stack.md`、`/docs/architecture/module-boundaries.md`、`/docs/architecture/configuration-environments-and-isolation.md`、`/docs/architecture/data-authority.md`、`/docs/architecture/provenance-and-versioning.md`、`/docs/architecture/repository-layout.md`、`/docs/contracts/schema-versioning.md`、`/docs/domain/state-machines/planning-run.md`、`/docs/domain/state-machines/schedule-version.md`、`/docs/domain/state-machines/export-job.md`、`/docs/domain/error-model.md`、`/docs/planning/solver-backend-contract.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/quality/benchmark-regression.md`、`/docs/quality/ci-gates-and-definition-of-done.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/operations/README.md`、`/docs/operations/security.md`（创建）、`/docs/operations/observability-and-audit.md`（创建）、`/docs/operations/worker-reliability-and-idempotency.md`（创建）、`/docs/adr/README.md`、`/docs/adr/ADR-0002-modular-monolith-and-solver-worker.md`、`/docs/adr/ADR-0009-production-simulation-data-isolation.md`、`/docs/milestones/README.md`、`/docs/milestones/P0-executable-specification.md`、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: API、Job、infrastructure、dependency/lock、version/build metadata、migration、测试、CI 与阶段状态从计划变为真实 P0 骨架；修改 ExportJob 状态文档还会触发完整状态文档审查。首次 diff check 发现 Alembic/migrations、`.env.example` 与 CI workflow 缺少 machine glob，已在稳定 `IMPACT-INFRA` 行补充有界覆盖。所有矩阵必审文档必须更新或在 Completion evidence 逐项说明不修改理由。

Change-impact matrix rows reviewed: `IMPACT-API`、`IMPACT-JOBS`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

Traceability updates: REQ-009、NFR-ISO-001/NFR-REL-001/NFR-SEC-001/NFR-OBS-001/NFR-PER-001、ENG-ARCH-001/ENG-VER-001/ENG-LOG-001 → TASK-P0-08 → TEST-OBS-001、TEST-IDEMPOTENCY 的 P0 primitive slice、config/health/migration/CI integration tests → lockfile、migration、health/engineering machine report 与 CI workflow；明确 Export/Publish/Planning 业务幂等、真实分布式 lease store、Solver Benchmark 和生产部署继续 `PLANNED`。

Schema changes: none。Schema set 保持 `1.2.0`；通用工程 DB 表不是 JSON/domain Schema，`backend/app/__init__.py` 与 `schemas/**` 保持只读。

Migration: 新增单个可逆 Alembic baseline，只建立 `engineering_job_records` 与 `engineering_idempotency_records`；以临时空 SQLite DB 验证 upgrade/downgrade，Production PostgreSQL 执行仍不在本 Task。

Error behavior: 配置错误在启动/构建依赖前 fail closed 且不回显 Secret；liveness 不依赖外部服务；readiness 将 database/redis unavailable 区分为 sanitized dependency code 和 HTTP 503；租约超时可变为 STALLED，owner/expired/invalid transition 与 idempotency conflict 可区分；不把这些工程错误伪装成业务 Error Schema。

Tests: config environment/Production guards、Secret representation；health live/ready success/503/no exception leak；log JSON/context/OpenTelemetry field/redaction；migration empty-DB upgrade/downgrade；job claim/heartbeat/lease/attempt/STALLED/complete/ownership 与 idempotency replay/conflict；lazy clients/Celery/Compose/CI/dependency boundary；所有既有 P0 suites 回归。

Benchmark impact: 仅在 PR CI 保留明确的未来 Benchmark hook；P0-08 不安装 OR-Tools、不运行 Solver Benchmark、不新增阈值或 baseline，OPEN-012 保持 OPEN。

Simulation scenarios: 无；不创建或修改 Simulation/Profile/Scenario/Fixture，Production 配置保持 `simulation_api_enabled=false` 且 data plane fail closed。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration`；`uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-08-rule-contracts.json`；`uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P0-08-simulation-contracts.json`；`uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P0-08-golden.json`；`uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-08-validator-mutations.json`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json`；`docker compose --env-file .env.example config --quiet`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-08-engineering-and-ci-skeleton.md --check-diff --report build/traceability/TASK-P0-08-report.json`；`git diff --exit-code 94fc6ffed79d3c4945f6881ee566b01aced64b05 -- schemas backend/app/__init__.py backend/app/domain backend/app/importers backend/app/normalization backend/app/data_validation backend/app/snapshots backend/app/planning backend/app/simulation backend/app/exporters scripts fixtures benchmarks frontend backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation`；`git diff --check`；`uv build`。

Artifacts: exact `uv.lock`、Alembic revision、health payloads、`engineering-skeleton-report.v1`、CI workflow；CI provider run URL/ID 不存在于本地验收，必须明确记录为外部 `NOT_RUN`，不得填造 PASS。

Explicitly excluded: PlanningJob/Import/Export/Publish 业务执行、真实 distributed durable idempotency/lease repository、产品 API、Solver、Solver Benchmark、生产部署与 P0 Exit Gate 审计。

PROD_OPEN: OPEN-012 保持 OPEN；OPEN-001～015 均不关闭，不从本地 Compose/config 推断生产值。

SIM_ASSUMPTIONS: 无新增或修改；现有 SIM-ASSUMPTION-001～009 保持 `ACTIVE`。

Rollback: 在没有下游消费者时可 downgrade 工程 metadata migration、停止/移除本地 Compose skeleton 并恢复依赖/配置；不得删除或覆盖用户环境数据库/Redis 数据，已经被环境执行的 migration 必须先显式 downgrade。

## Completion evidence

Completed at: `2026-08-19T14:05:53+08:00`

### Delivered artifacts

- Runtime/config：[`pyproject.toml`](../../../pyproject.toml) 与 `uv.lock` 精确锁定 10 个 direct runtime pins 和 dev `httpx`，未安装 OR-Tools；[`config.py`](../../../backend/app/infrastructure/config.py) 只读取 `PLANTNEXUS_*` environment/显式参数、不隐式读 `.env`，对 Production runtime/data plane、Simulation API、PostgreSQL、40-char commit、URL/log level 和 lease>heartbeat fail closed，错误/summary 不回显 Secret。
- Logging/health/connectivity：[`logging.py`](../../../backend/app/infrastructure/logging.py) 输出 JSON、合并 correlation/run/job context、按配置注入有效 OpenTelemetry trace/span ID，并递归屏蔽 Secret key、URL userinfo 与 free-text credential；[`database.py`](../../../backend/app/infrastructure/database.py) / [`redis_client.py`](../../../backend/app/infrastructure/redis_client.py) 构造时不连接；[`app.py`](../../../backend/app/api/app.py) 只注册 live/ready，依赖失败返回 sanitized 503/code，不提供产品 API/OpenAPI UI。
- Worker/migration：[`contracts.py`](../../../backend/app/jobs/contracts.py) 固定 immutable QUEUED/RUNNING/STALLED/SUCCEEDED/FAILED、owner、heartbeat、lease、attempt 与 UTC/SHA-256 invariants；[`idempotency.py`](../../../backend/app/jobs/idempotency.py) 固定 scope/key/fingerprint replay-conflict 原语且明确 process-local；Celery JSON-only/late-ack/prefetch 配置不注册业务 task。Alembic revision [`0001_engineering_job_metadata`](../../../backend/migrations/versions/0001_engineering_job_metadata.py) 只建立两张通用 metadata 表，临时空 SQLite upgrade/downgrade PASS。
- Container/CI：[`Dockerfile`](../../../infra/Dockerfile) 固定 Python 3.12.13/uv 0.11.32 且 non-root；[`docker-compose.yml`](../../../docker-compose.yml) 建立 development PostgreSQL/Redis/API/Worker skeleton；[`ci.yml`](../../../.github/workflows/ci.yml) 编排 exact sync、lint/type、全部 P0 suites/machine reports、Compose config、docs/diff、conditional PR Benchmark hook、build 与 evidence upload。
- Tests/report：5 个 [`backend/tests/integration`](../../../backend/tests/integration) files 共 26 tests，覆盖 config/health/log/job/idempotency/migration/lazy clients/Celery/dependency/Compose/Dockerfile/CI；`engineering-skeleton-report.v1` 六项 PASS，明确 `business_pipeline/distributed_persistence=NOT_IMPLEMENTED`、`solver=NOT_INSTALLED`、`production_deployment=NOT_CLAIMED`。
- 边界：没有修改 Schema、Domain、Import/Normalization/Snapshot、Planning/Validator/Backend、Simulation、Exporter、既有 tests/fixtures/benchmarks/frontend/scripts；没有产品 API、业务 task、真实 PostgreSQL/Redis connectivity/outage、distributed repository/scanner、Solver、production migration/deployment 或 P0 Exit Gate claim。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv sync --locked` | 0 | PASS；resolved/checked 58 packages，lock 无漂移。 |
| `uv run ruff check .` | 0 | PASS；`All checks passed!`。 |
| `uv run pyright backend/app backend/tests` | 0 | PASS；0 errors、0 warnings、0 informations。 |
| `uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration` | 0 | PASS；90 passed（既有 64 + P0-08 integration 26）。 |
| `uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-08-rule-contracts.json` | 0 | PASS；11 active、7 deferred、20 capabilities、19 error codes、3 machines/27 states/42 transitions。 |
| `uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P0-08-simulation-contracts.json` | 0 | PASS；8 checks，hash `sha256:cd0fb164704530e83197ec5cc806acc86dc8430f15e503c5840f898397fa9456`。 |
| `uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P0-08-golden.json` | 0 | PASS；原 hash `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10`，0 issues。 |
| `uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-08-validator-mutations.json` | 0 | PASS；13 cases、11 constraints、13 classes、15 violations。 |
| `uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json` | 0 | PASS；6/6 checks，health UP/DOWN、redaction、attempt=2/STALLED/idempotent replay 与 solver/business/deployment boundaries 均入 report。 |
| `docker compose --env-file .env.example config --quiet` | 0 | PASS；Compose interpolation/config 有效；未启动/拉取容器。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；110 docs、30 roots/trace rows、27 Test IDs、15 OPEN、9 SIM assumptions、10 risks、9 Tasks。 |
| `uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-08-engineering-and-ci-skeleton.md --check-diff --report build/traceability/TASK-P0-08-report.json` | 0 | PASS；67 paths、10 impact rows、28 expected/28 observed required docs、0 missing refs/issues。 |
| `git diff --exit-code 94fc6ffed79d3c4945f6881ee566b01aced64b05 -- schemas backend/app/__init__.py backend/app/domain backend/app/importers backend/app/normalization backend/app/data_validation backend/app/snapshots backend/app/planning backend/app/simulation backend/app/exporters scripts fixtures benchmarks frontend backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation` | 0 | PASS；所有 forbidden code/data/existing-test paths 保持不变。 |
| `git diff --check` | 0 | PASS；无 whitespace error，仅 Windows working-copy LF→CRLF 提示。 |
| `uv build` | 0 | PASS；生成 `plantnexus_aps-0.0.0.tar.gz` 与 `plantnexus_aps-0.0.0-py3-none-any.whl`。 |

CI provider run/URL、required branch protection 与 uploaded external Artifact 状态：`NOT_RUN`；本 Task 只创建并本地验证 workflow，未填造远端 PASS。Docker image build、container startup、real PostgreSQL/Redis probe 与 Production deployment 同样 `NOT_RUN`，不属于本卡 Acceptance Commands。

### Documentation impact and traceability

Documentation impact: `required`。实际 diff 为 67 paths：8 个根/构建/依赖/容器/CI文件，17 个 API/infrastructure/jobs/migration files，5 个 integration test files，37 份 `docs/**`。全部 Task-declared documents 实际更新；machine required review documents 为 28/28，无“必审但未修改”项。首次 diff check 暴露 `alembic.ini`、`backend/migrations/**`、`.env.example`、`.github/workflows/**` 缺少 machine rule，随后以不改变 required docs 的方式扩展稳定 `IMPACT-INFRA` glob 并复验通过。

真实矩阵命中 `IMPACT-API`、`IMPACT-JOBS`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Operations 从 1 个 planned index 变为 1 个 baseline index + security/observability/worker 三份 baseline，总文档数 107→110；状态机 machine artifacts 未改。

Traceability updates:

- REQ-009 → build code/spec/schema/commit metadata + health/log correlation → TASK-P0-08 → config/health/log tests + `engineering-skeleton-report.v1`；真实 source/Snapshot/Problem/Solver/Export manifest/audit 继续 `PLANNED`。
- NFR-ISO-001/SEC-001 → environment/data-plane Production guards、health-only API、Secret/no-leak/dependency/container tests；独立 sim/prod Database、auth/import/publish/production controls 继续 `PLANNED`。
- NFR-REL-001 → generic job/migration；TEST-IDEMPOTENCY → atomic process-local replay/conflict + lease/STALLED/attempt tests；durable distributed repository、scanner 和业务 side-effect exactly-once 继续 `PLANNED`。
- NFR-OBS-001/ENG-LOG-001 → JSON correlation/run/job/OpenTelemetry/redaction → TEST-OBS-001；PlanningRun metrics、exporter、audit store/retention 继续 `PLANNED`。
- NFR-PER-001 只连接 conditional PR hook，未形成 BenchmarkReport/threshold；ENG-ARCH-001 只形成 health API/Worker process skeleton，无 Solver/business task；ENG-VER-001 获得 exact pins/lock/build commit，Schema set 仍为 `1.2.0`。

Schema changes: none；`schemas/**`、`app.SCHEMA_VERSION=1.2.0`、data/rule/state/error/simulation artifacts 均未改。Migration: additive/reversible engineering metadata revision；SQLite empty-DB round trip PASS，Production PostgreSQL execution `NOT_RUN`。Benchmark: hook only，无 runner/Solver/profile/baseline/数值，OPEN-012 保持 OPEN。ADR-0002/0009 仅补实现证据，Decision 未改变、无新 ADR。

PROD_OPEN: OPEN-001～015 全部保持 `OPEN`，没有 authority/closure record；Compose name/password placeholder、heartbeat/lease 与 health timeout 不是生产值。SIM_ASSUMPTIONS: 未新增/修改，SIM-ASSUMPTION-001～009 全部保持 `ACTIVE`。Risks: RISK-007/008/009 早期控制增强但 production/distributed/Benchmark evidence 不足，RISK-001～010 全部保持 `MONITORED`。

Diff base 与验收时 Git HEAD 均为 `94fc6ffed79d3c4945f6881ee566b01aced64b05`；报告 source counts 为 committed range 0、working tree 67。本 Task 未提交用户工作树。Rollback：未被环境消费时可移除 P0-08 files/dependencies/docs；已经执行 migration 的环境必须先显式 downgrade，named volumes/用户 DB/Redis 数据不得删除；后续 consumer 形成后必须用新 migration/config contract 迁移而非覆盖。TASK-P0-09 保持 `planned`，本 Task 未自动进入下一任务。
