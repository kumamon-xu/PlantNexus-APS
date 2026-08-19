---
doc_id: TASK-P0-09
title: P0 Exit Gate Audit
status: done
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [72, 98, 99, 100, 110]
last_reviewed: 2026-08-19
---

# TASK-P0-09 — P0 Exit Gate Audit

Requirement IDs: REQ-001～REQ-015

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, NFR-HUM-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P0-01～TASK-P0-08

Goal: 独立核验 P0-01～08 的交付范围、Completion evidence 与 P0 Exit Gate，形成有日期和审计声明的报告、机器可读 evidence manifest、开放差距和是否允许请求进入 P1 的结论。P0 Gate 与本审计 Task 的完成状态分离：缺少外部证据时必须如实给出 `NOT_READY`/`NO_GO`，但完整且可复验的审计本身可以完成。

Inputs: `docs/core/APS_IMPLEMENTATION_SPEC.md` 全文、`docs/current_phase.md`、TASK-P0-01～09、`docs/milestones/P0-executable-specification.md`、Schema/version contracts、Rule/Golden/Mutation/Simulation/CI quality contracts、schemas、fixtures、tests、workflow、registries 与 Git repository state。

Diff base: 50e7cf872a0795d839b06afa025f7427b222d20d

Files allowed to change: 下方 `Documents to update` 的全部明确路径，即 `/docs/current_phase.md`（仅同步 P0-09 lifecycle 和 P0 `NOT_READY` 结论，不改变 phase、不授权 P1）、`/docs/milestones/README.md`、`/docs/milestones/P0-executable-specification.md`、`/docs/milestones/P0-exit-gate-audit-report.md`（创建）、`/docs/milestones/P0-exit-gate-evidence-manifest.json`（创建）、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/tasks/P0/TASK-P0-09-p0-exit-gate-audit.md`、`/docs/tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md`（仅创建/收敛为 `planned`，不得执行）、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`、`/docs/quality/ci-gates-and-definition-of-done.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/contracts/schema-index.md`、`/docs/contracts/schema-versioning.md`、`/docs/quality/fixtures-and-golden-tests.md`、`/docs/quality/validator-mutation-tests.md`、`/docs/simulation/synthetic-generator-and-determinism.md`，以及生成但不提交的 `/build/validation/TASK-P0-09-rule-contracts.json`、`/build/validation/TASK-P0-09-simulation-contracts.json`、`/build/validation/TASK-P0-09-golden.json`、`/build/validation/TASK-P0-09-validator-mutations.json`、`/build/validation/TASK-P0-09-engineering.json`、`/build/traceability/TASK-P0-09-report.json`、`/build/traceability/TASK-P0-08-post-P0-09-report.json`、`/dist/plantnexus_aps-0.0.0.tar.gz` 与 `/dist/plantnexus_aps-0.0.0-py3-none-any.whl`。

Files forbidden to change: 除上述精确路径外的全部文件；尤其 `/docs/core/APS_IMPLEMENTATION_SPEC.md`、`/schemas/**`、`/backend/**`、`/fixtures/**`、`/scripts/**`、`/.github/**`、`/infra/**`、`/frontend/**`、`/benchmarks/**`、`/pyproject.toml`、`/uv.lock`、`/alembic.ini`、`/docker-compose.yml`、`/.env.example`、Solver/Constraint/Test assertion、CpModel、IntervalVar、OR-Tools、任何 P1 implementation 或 P1 Task Card。若审计需要修改实现、合同、Schema、Fixture 或测试才能通过，停止并将缺口写入新的有界 P0 remediation Task，而不在本 Task 修复。

Implementation steps: 逐张复核 TASK-P0-01～08 的 scope、allowed/forbidden paths、真实 Completion evidence 与独立提交；运行 Schema/Rule Sheet/Golden/Validator Mutation/Scenario replay、全测试、lint/type、engineering、Compose config、repository build 和 governance/diff gates；核对 15 REQ、9 NFR、6 ENG、15 PROD_OPEN、9 SIM_ASSUMPTION、10 risks 与全部 Task/Test/Artifact 链；静态检查生产包与 dependency/lock 中没有 Solver import、CpModel、IntervalVar 或 OR-Tools；核对 Git remote/CI provider evidence；按总规 §72 对每个 Gate 单独给出 `PASS`、`FAIL` 或 `NOT_RUN`；抽查代表性 trace chains；发现阻塞缺口时创建精确的 P0 remediation Task；不把 local workflow/config PASS 伪装成 external CI PASS。

Outputs: `P0-exit-gate-audit-report.md`、`p0-exit-gate-evidence-manifest.v1` JSON、gate-by-gate evidence、go/no-go recommendation，以及必要时仅创建不执行的 P0 remediation Task Card。

Documentation impact: required

Documents to update: `/docs/current_phase.md`、`/docs/milestones/README.md`、`/docs/milestones/P0-executable-specification.md`、`/docs/milestones/P0-exit-gate-audit-report.md`、`/docs/milestones/P0-exit-gate-evidence-manifest.json`、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/tasks/P0/TASK-P0-09-p0-exit-gate-audit.md`、`/docs/tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md`、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`、`/docs/quality/ci-gates-and-definition-of-done.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/contracts/schema-index.md`、`/docs/contracts/schema-versioning.md`、`/docs/quality/fixtures-and-golden-tests.md`、`/docs/quality/validator-mutation-tests.md`、`/docs/simulation/synthetic-generator-and-determinism.md`。

Documentation impact rationale: Exit Gate 审计将 P0-01～08 的分散证据汇总为可复验 Gate 结论，并把缺失的 external CI provider run 与 P1 禁入边界显式写入 Milestone、Phase、CI/quality、registry 和 Task 追踪。`docs/current_phase.md` 只同步当前 P0 Task 和 `NOT_READY`，不进行原卡禁止的 P1 phase transition；任何进入 P1 的修改仍须用户另行批准。

Change-impact matrix rows reviewed: `IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

Traceability updates: REQ-001～REQ-015、全部 9 NFR/6 ENG → TASK-P0-01～09 → 27 registered Test IDs/90-test P0 suite + five machine contract reports + build/governance/workflow replay evidence → P0 audit report/manifest；分别记录 formed P0 slice 与 P1/P2+ `PLANNED` 边界。OPEN-001～015 必须仍完整登记，SIM-ASSUMPTION-001～009 必须保持 Simulation-only；`P0-GAP-001` external provider evidence 与 `P0-GAP-002` stale workflow handoff均追踪到 planned TASK-P0-10，不创建 P1 Task。

Schema changes: none。只审计 schema set `1.2.0`、保留的 `1.0.0/1.1.0` artifacts、Draft 2020-12 contract tests 与 compatibility 文档，不修改任何 Schema/version/sample。

Migration: none。只复核 TASK-P0-08 的 engineering SQLite empty-DB upgrade/downgrade evidence；不执行 Production migration。

Error behavior: 任一 §72 必需 Gate 无真实证据时该 Gate 必须为 `FAIL` 或 `NOT_RUN`，总体必须为 `NOT_READY` 且 recommendation 为 `NO_GO`；workflow exact command非零必须记录为 `FAIL`，不能因 provider 未运行而掩盖。不得用文档声明、local workflow inspection 或修改断言替代缺失证据。审计 Task 只有在遗漏事实、审计断言失败、manifest/report 不一致或范围违规时才验收失败。

Tests: 回归 unit/contract/simulation/golden/validation/integration 全部 P0 suites；运行五类 machine contract report；运行 governance full/diff checks；验证 audit JSON 可解析且 Gate 汇总与报告一致。

Benchmark impact: P0 不安装 Solver、不运行或声称真实 Solver Benchmark；仅审计 conditional PR hook 和 NFR-PER-001/OPEN-012 的 deferred/open 边界。缺少 P0 不要求的 Solver benchmark 不构成 Gate 缺口。

Simulation scenarios: 重放 `SIM-MINIMAL-001@1.0.0` 及 canonical hash，运行 13 类 illegal mutation/15 violation evidence；不生成新场景、不改 Fixture，不把 SIM_ASSUMPTION 作为 PROD_OPEN closure。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration`；`uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-09-rule-contracts.json`；`uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P0-09-simulation-contracts.json`；`uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P0-09-golden.json`；`uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-09-validator-mutations.json`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-09-engineering.json`；`docker compose --env-file .env.example config --quiet`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-09-p0-exit-gate-audit.md --check-diff --report build/traceability/TASK-P0-09-report.json`；`uv run python -c "import json, subprocess; report='build/traceability/TASK-P0-08-post-P0-09-report.json'; r=subprocess.run(['uv','run','python','scripts/check_docs.py','--task','docs/tasks/P0/TASK-P0-08-engineering-and-ci-skeleton.md','--check-diff','--report',report]); d=json.load(open(report, encoding='utf-8')); bad={i['path'] for i in d['issues'] if i['check_id']=='TASK-SCOPE'}; expected={'docs/milestones/P0-exit-gate-audit-report.md','docs/milestones/P0-exit-gate-evidence-manifest.json','docs/tasks/P0/TASK-P0-09-p0-exit-gate-audit.md','docs/tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md'}; assert r.returncode==1 and expected <= bad; print('PASS observed stale TASK-P0-08 workflow diff failure')"`；PowerShell static gate `$matches = rg -n 'CpModel|IntervalVar|from ortools|import ortools|name = "ortools"' backend/app pyproject.toml uv.lock; if ($LASTEXITCODE -eq 0) { $matches; exit 1 }; if ($LASTEXITCODE -eq 1) { 'PASS no Solver symbols/imports/dependency'; exit 0 }; exit $LASTEXITCODE`；`git remote -v`（只收集 external CI availability，不把空输出写成 CI PASS）；`uv run python -c "import json; from pathlib import Path; p=Path('docs/milestones/P0-exit-gate-evidence-manifest.json'); d=json.loads(p.read_text(encoding='utf-8')); assert d['manifest_version']=='p0-exit-gate-evidence-manifest.v1'; assert d['overall_status']=='NOT_READY'; assert d['recommendation']=='NO_GO'; assert any(g['gate_id']=='ci-workflow-replay' and g['status']=='FAIL' for g in d['gates']); assert any(g['gate_id']=='ci-provider' and g['status']=='NOT_RUN' for g in d['gates']); print('PASS audit manifest')"`；`git diff --check`；`uv build`。

Artifacts: committed audit report、`p0-exit-gate-evidence-manifest.v1`、planned TASK-P0-10；ignored five machine reports、P0-09 traceability report、stale-workflow failure report 与 build outputs。报告记录 audit date/auditor/attestation 和 content hashes；workflow replay failure必须为 `FAIL`，没有 CI provider run URL/ID 时必须明确 `NOT_RUN`。

Explicitly excluded: 自动进入 P1、创建 P1 Task、关闭未解决 PROD_OPEN、修改现有实现/Schema/Fixture/Test、真实 Solver/Benchmark、Production readiness/deployment 声明，以及执行 TASK-P0-10。

PROD_OPEN: 审计 OPEN-001～015 是否全部登记；不要求关闭，也不得补猜 authority/value。缺少 closure 不阻塞 P0 Exit Gate，登记缺口才阻塞。

SIM_ASSUMPTIONS: 审计 SIM-ASSUMPTION-001～009 的 asset/version links 和 Production 隔离；不新增通用数值、不改变 `ACTIVE` 状态。

Rollback: 报告和 manifest 是审计记录，不通过覆盖历史“修成 PASS”；事实错误用后续更正记录。若 Gate `NOT_READY`，保留 P0 active，创建有界 remediation Task，待新证据形成后重新审计；不得删除失败/`NOT_RUN` evidence 或自动进入 P1。

## Completion evidence

Completed at: `2026-08-19T14:39:20+08:00`

### Audit decision and delivered artifacts

- [P0 Exit Gate audit report](../../milestones/P0-exit-gate-audit-report.md) 与 [`p0-exit-gate-evidence-manifest.v1`](../../milestones/P0-exit-gate-evidence-manifest.json) 已形成；Schema、Golden、Validator Rule Sheet、Scenario deterministic replay、Repository Build 和 PROD_OPEN registration 为 `PASS`。CI Gate为 `FAIL`：workflow 的旧 TASK-P0-08 diff step在 P0-09 commit上 exit 1，external provider evidence同时 `NOT_RUN`；总体 `NOT_READY`，recommendation `NO_GO`。
- TASK-P0-01～08 的 Completion evidence 和连续 commit ranges 全部复读；P0-01 是 immutable Diff-base 规则建立前的 bootstrap card，保留 initial Git baseline/evidence；P0-02～08 的完整 Diff base 与后续独立提交连续相接。未发现靠修改 assertion/constraint/fixture/workflow 形成 PASS 的情况。
- [TASK-P0-10](TASK-P0-10-ci-provider-evidence-remediation.md) 仅创建/收敛为 `planned`，承接 `P0-GAP-002` workflow handoff 与 `P0-GAP-001` provider evidence；workflow/test没有修改或执行，provider/remote/owner 未确认且未猜测，也未执行 push、CI、branch protection 或任何外部操作。
- 审计范围内没有修改 code、Schema、Fixture、Test、workflow、dependency/lock、infrastructure 或总规；没有 CpModel、IntervalVar、OR-Tools、Solver/P1 implementation 或 P1 Task。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv sync --locked` | 0 | PASS；resolved/checked 58 packages，lock 无漂移。 |
| `uv run ruff check .` | 0 | PASS；`All checks passed!`。 |
| `uv run pyright backend/app backend/tests` | 0 | PASS；0 errors、0 warnings、0 informations。 |
| `uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration` | 0 | PASS；90 passed in 1.43s。 |
| `uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-09-rule-contracts.json` | 0 | PASS；11 active、7 deferred、20 capabilities、19 error codes、3 machines/27 states/42 transitions。 |
| `uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P0-09-simulation-contracts.json` | 0 | PASS；8 checks，hash `sha256:cd0fb164704530e83197ec5cc806acc86dc8430f15e503c5840f898397fa9456`。 |
| `uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P0-09-golden.json` | 0 | PASS；8 artifacts、15 records、3 assignments、11 expectations、0 issues，hash `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10`。 |
| `uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-09-validator-mutations.json` | 0 | PASS；positive 0 violation；13 cases、11 constraints、13 classes、15 negative violations。 |
| `uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-09-engineering.json` | 0 | PASS；6 checks；`solver=NOT_INSTALLED`，business/distributed/production boundaries 未声称。 |
| `docker compose --env-file .env.example config --quiet` | 0 | PASS；只验证 interpolation/config，未启动或拉取容器。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；112 docs、30 roots/trace rows、27 tests、15 open、9 sim、10 risks、10 tasks。 |
| `uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-09-p0-exit-gate-audit.md --check-diff --report build/traceability/TASK-P0-09-report.json` | 0 | PASS；20 paths、3 impact rows、13 expected/12 modified required docs、0 missing refs/issues。 |
| workflow raw docs step `check_docs.py --task TASK-P0-08 --check-diff` on the P0-09 commit | 1 | Expected audited failure；4 个 audit/task paths 超出旧 P0-08 allowed boundary，CI Gate `FAIL`。 |
| Task-card stale-workflow audit assertion | 0 | PASS；子进程 raw exit 1 且四个 expected `TASK-SCOPE` paths 全部存在；known failure 已进入 report/manifest。 |
| Task-card PowerShell static no-Solver gate | 0 | PASS；production package/dependency/lock 中没有 `CpModel`、`IntervalVar`、OR-Tools import 或 lock entry。 |
| `git remote -v` | 0 | 空输出；真实结论为 external CI provider/run/artifact/required check `NOT_RUN`，不是 PASS。 |
| Task-card audit manifest parse command | 0 | PASS；version v1、overall `NOT_READY`、recommendation `NO_GO`、CI `NOT_RUN` 断言成立。 |
| `git diff --check` | 0 | PASS；无 whitespace error，仅 Windows working-copy LF→CRLF 提示。 |
| `uv build` | 0 | PASS；生成 `plantnexus_aps-0.0.0.tar.gz` 与 `plantnexus_aps-0.0.0-py3-none-any.whl`。 |

本 Task 的 Acceptance 是“审计完整、命令真实、Gate 分类正确并保持边界”。Task-card 命令均 exit 0；其中 stale-workflow assertion 明确要求其被审计子进程 exit 1并核对 failure paths，因此没有把 raw failure伪装成 PASS。audit acceptance `PASS`，而 P0 Milestone 因 CI Gate `FAIL` 仍 `NOT_READY`；二者没有混用。

### Evidence integrity and scope

| Local artifact | SHA-256 |
|---|---|
| `TASK-P0-09-rule-contracts.json` | `a22d986ac8e5e90cb6432278becedd4f27714e9df991ec839f5dda095f942c42` |
| `TASK-P0-09-simulation-contracts.json` | `09f169b703552ef24107b5375f7ad6aa053361c79a85b462c95f3ec29ca75167` |
| `TASK-P0-09-golden.json` | `90c3ad27920ab42a3997928da64a86aedbc120bbe56a1365e5d5d6714dc13cb9` |
| `TASK-P0-09-validator-mutations.json` | `11376303ff2633aaea8d2e5602d8afd2bd0efbb87362f074a1ea1e84c4dfa762` |
| `TASK-P0-09-engineering.json` | `19b5be12a7cca38816d752376d7ef7591ceceede21d5cd92cc2aa5dcda8495a2` |

Diff base 为 `50e7cf872a0795d839b06afa025f7427b222d20d`。首次提交前验收 HEAD 同 Diff base，source counts 为 committed 0 / working tree 20；首次审计提交后 workflow replay发现 gap并进行 corrected acceptance，source counts 为 committed 20 / working tree 18，union仍为相同 20 个路径；该中间提交随后被事实更正 amend，不作为稳定 Evidence SHA。实际 changed paths：`docs/current_phase.md`；10 份 `docs/governance/**`；audit report/JSON、P0 milestone/index；3 份 quality docs；P0-09/P0-10/task index，共 20 个精确允许路径。真实命中 `IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`；post-amend committed-range revalidation记录在最终 handoff。

实际修改的 machine-required documents 为 12/13；`docs/tasks/TASK_TEMPLATE.md` 经审查未修改，因为 audit/task completion distinction 已写入 traceability rules，模板字段/状态/完成证据结构没有变化。额外列入并审查但未修改：`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`（schema set/compatibility 均未变）；`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/validator-mutation-tests.md`（fixture/version/hash/expected outcomes 未变）；`docs/simulation/synthetic-generator-and-determinism.md`（Generator/canonicalization/seed contract 未变）。其余列出的 Documents to update均已实际修改。

### Traceability and boundaries

- 15 REQ + 9 NFR + 6 ENG 共 30 root 恰有 30 trace rows，27 Test IDs 均保持既有 formed/`PLANNED` 边界；audit report 记录 REQ-005 correctness、REQ-011/012 replay、REQ-009 engineering/CI 三条代表性链路。根 ID全部继续 `ALLOCATED`，未从 audit 推断业务完成。
- OPEN-001～015 共 15 项全部登记并保持 `OPEN`，无 authority/closure record；这使 registration Gate PASS，但不产生生产默认值。SIM-ASSUMPTION-001～009 共九项保持 `ACTIVE` 且未用于关闭 production-open；RISK-001～010 保持 `MONITORED`。
- Schema changes: none；schema set `1.2.0`、保留的 v1/v2 artifacts 和 Draft 2020-12 contracts只读。Migration: none；仅复核 P0-08 的 SQLite empty-DB round trip，Production migration `NOT_RUN`。
- Benchmark: P0 conditional hook only；没有 runner/Solver/profile result/threshold，OPEN-012 保持 OPEN。Simulation: 只重放现有 empty/non-empty/illegal artifacts，不修改 Scenario/Profile/Fixture。
- Workflow/test 修复未在 P0-09 执行；external CI、branch protection、uploaded artifact、container startup、real PostgreSQL/Redis、Production deployment也未执行或声称。TASK-P0-10 必须先关闭 `P0-GAP-002` workflow handoff，再在用户授权后关闭 `P0-GAP-001` provider evidence，并重新审计。

Rollback：audit report/manifest 保留 workflow `FAIL` 与 provider `NOT_RUN` 历史事实；若发现事实错误，以更正/superseding audit 处理，不删除失败记录。P0 保持 `active`，当前 Phase不变；TASK-P0-10 保持 `planned`，本 Task未自动进入下一任务或 P1。
