---
doc_id: TASK-P2-03
title: OR-Tools and SolverBackend Foundation
status: done
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [13, 14, 24, 29, 57, 75, 93, 102]
last_reviewed: 2026-08-20
---

# TASK-P2-03 — OR-Tools and SolverBackend Foundation

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-02

Start gate: TASK-P2-02=`done`且exact closure已复核；用户于2026-08-20明确授权执行本Task；solver contracts/status固定；ADR-0011须在dependency变更前accepted；启动时`main=origin/main`、working tree clean，并记录lock/contract baseline与immutable Diff base。

Goal: exact-pin OR-Tools并建立SolverBackend protocol、CP-SAT adapter边界、status/version/parameter映射和空模型诊断骨架，不实现C-001～C-011业务约束。

Inputs: Problem/Policy/Limits/Solution contracts、ADR-0002/0003/0004、SolverBackend contract、dependency/security policy。

Diff base: f73f8c90af94d3c9b05ecc10b6c999594a3b7d66

Files allowed to change: `pyproject.toml`、`uv.lock`、`.github/workflows/ci.yml`、`backend/app/infrastructure/contract_check.py`、`backend/app/planning/policy/contract_check.py`、`backend/app/planning/backends/__init__.py`、`backend/app/planning/backends/contracts.py`、`backend/app/planning/backends/cp_sat/__init__.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/app/planning/backends/cp_sat/status.py`、`backend/app/planning/backends/cp_sat/contract_check.py`、`backend/tests/unit/test_solver_backend_contract.py`、`backend/tests/contract/test_planning_machine_contracts.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`中的全部明确文档。

Files forbidden to change: `backend/app/planning/contracts.py`、`backend/app/planning/policy/contracts.py`及Problem/Policy/Solution/Report Schema/sample/语义；constraint builders、Strategy/objective、Validator evaluator、fixtures/benchmarks/export、DB/migration/API/Worker/P3；上列allow-list之外的任何路径。

Implementation steps: 接受exact solver ADR；更新direct dependency/lock/CI assertion；建立protocol与cp_sat namespace isolation；映射status/parameters/version/timing；验证domain/problem无OR-Tools import、serialization无Solver对象；构造仅工程性的empty/model-invalid smoke test。

Outputs: pinned solver dependency、backend protocol/adapter skeleton、status/version report与dependency replay evidence。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/adr/ADR-0011-ortools-9-15-cp-sat-backend-version-policy.md`、`docs/adr/README.md`、`docs/architecture/technology-stack.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/contracts/schema-versioning.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/domain/kpi-contract.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/operations/security.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、本Task卡。

Documentation impact rationale: 首次Solver依赖与Backend边界影响技术栈、版本、供应链、CI和后续所有模型/benchmark证据。

Change-impact matrix rows reviewed: `IMPACT-POLICY`、`IMPACT-BACKEND`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/009→TASK-P2-03→TEST-CONTRACT-001/TEST-SOLVER-UPGRADE→dependency lock/backend smoke artifacts；约束和feasibility保持PLANNED。

Schema changes: none；消费P2-02合同，不修改schema set。

Migration: none。

Dependency changes: required；接受`ortools==9.15.6755` exact runtime pin并由`uv.lock`锁定全部transitive版本/wheel hashes；启动`uv.lock` SHA-256=`7ae68d242b1f80ad05a2ae51b09552ca9e19214d33ef8380bc74ff4c87ee64dd`；记录Windows/local与Linux/provider平台、版本和安全审查；禁止floating range、beta或未锁定wheel。

ADR impact: required；`ADR-0011`在dependency变更前accepted，选择OR-Tools`9.15.6755`、wheel install、namespace isolation及upgrade/replay Gate；保持OR-Tools只存在于cp_sat backend。

Error behavior: import/version mismatch、MODEL_INVALID、unsupported platform或adapter异常使用稳定错误/status，sanitized detail；不把空模型smoke结果冒充业务可行性。

Tests: TEST-CONTRACT-001、TEST-SOLVER-UPGRADE；exact dependency/lock、namespace scans、status mapping、parameter capture、empty/model-invalid smoke与serialization isolation。

Benchmark impact: 触发首次版本baseline要求，但本Task无业务模型；记录NOT_APPLICABLE而非零runtime，实际baseline由P2-12。

Simulation scenarios: none。

Acceptance commands: `uv lock --check`；`uv sync --locked`；`uv run pytest -q backend/tests/unit/test_solver_backend_contract.py backend/tests/contract/test_planning_machine_contracts.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python -m app.planning.backends.cp_sat.contract_check --root . --report build/validation/TASK-P2-03-solver-backend-foundation.json`；`uv run python -m app.planning.policy.contract_check --root . --report build/validation/TASK-P2-02-planning-machine-contracts.json`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-03-ortools-backend-foundation.md --check-diff --report build/traceability/TASK-P2-03-report.json`；`docker compose --env-file .env.example config --quiet`；`uv build`；`git diff --check`。

Artifacts: accepted ADR、dependency/lock fingerprints、`solver-backend-foundation-report.v1`、Task `traceability-report.v1`。

Provider evidence: provider=`GitHub Actions`、repository=`kumamon-xu/PlantNexus-APS`、branch=`main`、workflow=`PlantNexus repository gates`；用`gh run view <run-id> --repo kumamon-xu/PlantNexus-APS`与GitHub REST查询exact SHA。Required `validate`必须在clean Linux runner完成locked install、tests/build并上传Task/backend artifacts；记录immutable SHA、run/attempt/event/job/steps、artifact ID/name/size/digest/expiry、solver version及branch required-check=`validate`。

Completion conditions: exact dependency和ADR闭环；Backend边界/状态/版本可测；上层无OR-Tools泄漏；local/provider PASS；没有业务constraint/strategy结果。

Explicitly excluded: C-001～C-011、OBJ-001、candidate schedule、benchmark baseline、Solver Worker/DB/API、P3。

PROD_OPEN: OPEN-011/012保持OPEN；本Task不承诺solver limit、capacity或SLA。

SIM_ASSUMPTIONS: none。

Rollback: 回退dependency/lock和backend namespace；保留ADR为rejected/superseded历史，不重写；若后继已消费则先回退consumer并重跑全部replay。

## Activation evidence

2026-08-20用户明确授权执行TASK-P2-03。启动复核时working tree clean，`main=origin/main=f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`；P2-02 implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`为HEAD祖先，closure run `32342949743`、required `validate` job `96345556588`和artifact `9396984310`均为`completed/success`且artifact未过期，required context仍为`validate`。

启动冻结SHA-256：`pyproject.toml=8b43a21525089655fbc0505f8ded44ab0e512092dc84f4837dcff23700be0d53`、`uv.lock=7ae68d242b1f80ad05a2ae51b09552ca9e19214d33ef8380bc74ff4c87ee64dd`、`app.planning.contracts=d5f7a7e49e4f83e1da011da113f93a80c7f6bc7b1dc3814df374c5dfaefae630`、`policy.contracts=eff050db6a337866631a7e27d0dd00f29c4d48dce913e819a17687feec01d89c`；四份P2-02 Schema分别为`62624424...1bda`、`8caff522...1d95`、`4344468e...df4`、`64feacd0...b2a`，本Task禁止修改这些合同字节。

官方PyPI与Google release资料确认`9.15.6755`是启动日最新稳定版，并提供CPython 3.12 Windows x86-64、manylinux x86-64/aarch64和macOS wheels；`v10.0 Beta`不进入本Task。官方GitHub repository-level security advisories查询为空；release已知Python wrapper问题包括`status_name()`调用异常，因此foundation使用显式enum/name映射而不依赖该API。上述审查不等于持续漏洞监控或Production安全认证。

Scope review在任何dependency/Backend修改前补入新ADR、machine report CLI、P2-02/P0 historical report兼容更新、contract test、workflow，以及POLICY/INFRA/PHASE等Impact Rule要求的强制文档。Problem/Policy/Solution/Report合同语义、Schema/sample、C-ID、Strategy/objective、Validator、fixture/benchmark/export、DB/API/Worker/P3全部保持禁止。

## Local implementation evidence

ADR-0011以独立先行commit `ba7efc1`接受后才修改dependency。`pyproject.toml`现exact pin `ortools==9.15.6755`；`uv.lock` SHA-256=`8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`，固定CPython 3.12 Windows/Linux/macOS wheels及transitive versions。Local runtime为CPython 3.12.13 / Windows AMD64 / OR-Tools 9.15.6755。

实现形成`cp-sat` / `cp-sat-backend.v1` identity、canonical Protocol neutral re-export、native five-status + CANCELLED/FAILED adapter、unknown/version fail-closed、四项显式参数、empty/model-invalid engineering smoke与AST namespace scan。真实`solve()`对已验证合同返回稳定`MODEL_BUILDER_NOT_IMPLEMENTED`/MODEL_INVALID且无candidate，未实现任何C-ID、OBJ-001、Strategy、Validator、fixture/benchmark/export、DB/API/Worker或P3路径。

本地结果：`uv lock --check`与`uv sync --locked` PASS；focused=`39 passed`；full=`319 passed`；Ruff/Pyright=0；foundation=`6/6 PASS`，report SHA-256=`f9444d8602d66dd7d280ac3400675db3179f7beab38826f524247ca79c07315d`/7545 bytes；P2-02 compatibility=`5/5 PASS`；historical Engineering=`6/6 PASS`；Compose、`uv build`与`git diff --check` PASS。

Point-in-time `pip-audit==2.10.1 --skip-editable`报告SHA-256=`45dfe31d6873211b1851c25ad3bd4247884ec45ba02db0db773fed04853494f2`/17722 bytes：新增OR-Tools依赖子树0 findings；Diff base已存在pytest 1个与starlette 6个唯一advisory，登记RISK-011且本Task不越界升级。该审查不是持续监控或Production认证。

文档治理full PASS为142 docs/30 roots/36 tests/15 OPEN/10 SIM/11 risks/37 Tasks；Task diff PASS为50 actual paths、9 matched Impact rows、19 checks、0 issues。Ignored report不提交；provider必须在clean Linux runner重建同类machine/task evidence。

## Completion evidence

提交拓扑为Diff base `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66` →先行accepted ADR commit `ba7efc1aef67c8d1aa651d28cda9449e2ba1d6d7` → implementation commit `9268b88ca7ce90a8f72023241f87e2d3676fd58a`；ADR先于dependency/lock变更且两者已直接推送`main`。Implementation diff与本地验收事实保持上述50 paths/9 rows/0 issues、39 focused/319 full、6/6 foundation及无业务model/candidate边界。

GitHub push run [`32346208046`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32346208046)为`event=push`、`attempt=1`、`head_sha=9268b88ca7ce90a8f72023241f87e2d3676fd58a`、`completed/success`。Required `validate` job [`96355386111`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32346208046/job/96355386111)在clean Linux runner完成23个steps，locked sync、lint、type、repository suites、全部machine contracts、新CP-SAT foundation、Compose、docs/Task diff、build和artifact upload均success。Branch protection required context精确为`validate`、GitHub Actions app ID `15368`；唯一非阻塞annotation为GitHub runner将部分Node 20 actions强制运行于Node 24，纳入RISK-011持续监测而不改变本次成功结论。

Artifact `9398128763`=`plantnexus-ci-evidence-32346208046`，size=`14747` bytes，digest=`sha256:d706f0bda6e8612531b107d5b0c28d3575913d81bd4a9b9e013bed6202f1f087`，`expired=false`，expires=`2026-11-18T07:54:35Z`。下载后`validation/ci-solver-backend-foundation.json` SHA-256=`09542b81c6eaac50857ad97c00ec02640e5af2acd8e77fc8973dfaee9142ae2e`：精确绑定implementation SHA、Linux/x86_64、OR-Tools`9.15.6755`、lock SHA `8b13617f…87a82`、6/6 PASS和全部NOT_EVALUATED/NOT_IMPLEMENTED边界；`traceability/ci-current-task-report.json` SHA-256=`f434bf72427bc5170e8b9c1b201dde66f2be763fc032beb9fb2f14eaa211518b`：绑定同一head、Diff base、TASK-P2-03、50 paths、9 impact rows、19 checks、0 issues和`result=PASS`。

因此全部Completion conditions满足并标记`done`。P2继续`active`；TASK-P2-04～14保持`planned`且未获启动授权，C-001～C-011、OBJ-001、candidate/formal Validator、Benchmark/DB/API/Worker/P3仍未实现。Evidence-only closure自身的exact provider结果只能在本提交推送后核验；若失败则保留失败run并追加有界修复，不重写历史或force-push。
