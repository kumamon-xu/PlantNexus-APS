---
doc_id: TASK-P0-10
title: CI Workflow Handoff and Provider Evidence Remediation
status: in_progress
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [58, 72, 100, 110]
last_reviewed: 2026-08-19
---

# TASK-P0-10 — CI Workflow Handoff and Provider Evidence Remediation

Requirement IDs: REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-PER-001, ENG-ARCH-001, ENG-VER-001

Depends on: TASK-P0-09

Goal: 关闭 `P0-GAP-001` 与 `P0-GAP-002`：先把 CI workflow 的文档 diff gate 从硬编码 TASK-P0-08 有界交接到本 Task 的 immutable Diff base，并用 integration/governance tests 证明最终 P0 commit 可执行；再在用户明确选择并授权的 GitHub provider 上执行未弱化 workflow，保存 run/commit/artifact/required-check evidence并重新审计 P0 CI Exit Gate。

Inputs: `docs/milestones/P0-exit-gate-audit-report.md`、`docs/milestones/P0-exit-gate-evidence-manifest.json`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`、GitHub repository `kumamon-xu/PlantNexus-APS`、`origin` SSH remote、`main` branch，以及用户于 2026-08-19 对继续 TASK-P0-10 和必要 push/provider evidence 操作的明确授权。

Diff base: 5d8bb51e06add1afc2f53861cf53c7a2ba45a272

Files allowed to change: `/.github/workflows/ci.yml`、`/backend/tests/integration/test_ci_contract.py`、`/docs/milestones/P0-exit-gate-evidence-manifest.json`、下方 `Documents to update` 的全部明确 Markdown 路径，以及 GitHub repository `kumamon-xu/PlantNexus-APS` 的 `main` push-triggered Actions runs/artifacts 与该 branch 的 required-check/branch-protection evidence。JSON manifest 需要在 Files allowed 中单独列出，因为文档清单扩展只处理 Markdown；该路径已在 Task 开始前的 `Documents to update` 中声明，本次只消除机器边界表达歧义。凭证只可由进程外环境或已认证 provider session 提供，不得写入 repository。

Files forbidden to change: 除上述精确路径外的全部 repository files；`/scripts/check_docs.py`、其他 tests、Schema、Fixture、dependency/lock、Solver/P1 implementation 和 Production Secret；任何 Test assertion/required check 弱化、伪造 run URL/ID/artifact 或把 local command 写成 provider PASS。用户授权前还禁止 push、provider/branch-setting/Secret 等 external state change。

Implementation steps: 开始时记录 immutable Diff base；把 workflow 的 docs/diff step 有界切换为 TASK-P0-10，保持 full governance check、artifact upload 和其他 gates不弱化；更新 integration contract test，先在提交前及提交后证明 workflow exact command 对最终 P0-10 range PASS；对不可变 commit push 后以 GitHub REST 查询 provider run；核验全部 required jobs success、artifact upload/commit SHA 与 required check/branch-protection state；保存可引用 evidence并重新审计 P0。若需要修改 checker 或其他路径，必须先修订本卡边界。

Outputs: 可在最终 P0 commit 上 PASS 的 workflow handoff/integration evidence；provider、repository、run ID/URL、immutable commit、job conclusions、external artifact identity/digest、required-check/branch-protection evidence；superseding P0 Exit Gate audit decision。

Documentation impact: required

Documents to update: `/docs/tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md`、`/docs/current_phase.md`、`/docs/milestones/README.md`、`/docs/milestones/P0-executable-specification.md`、`/docs/milestones/P0-exit-gate-audit-report.md`、`/docs/milestones/P0-exit-gate-evidence-manifest.json`、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/architecture/configuration-environments-and-isolation.md`、`/docs/architecture/technology-stack.md`、`/docs/operations/README.md`、`/docs/quality/ci-gates-and-definition-of-done.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`。开始前必须按实际 external evidence 再复核并补齐路径。

Documentation impact rationale: workflow 当前硬编码旧 Task diff gate并在 P0-09 commit 上确定性失败，external CI evidence 也不存在；修复会改变 CI/test/infra contract、Gate/Milestone readiness 与 artifact trace。没有用户批准仍不得执行外部操作或进入 P1。

Change-impact matrix rows reviewed: `IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

Traceability updates: P0-GAP-002 → TASK-P0-10 → workflow handoff/integration/post-commit diff evidence；P0-GAP-001 → TASK-P0-10 → provider run/commit/job/artifact/required-check evidence；两者 → superseding P0 re-audit。REQ-009/NFR-TRC-001/NFR-PER-001/ENG-ARCH-001/ENG-VER-001 的 CI slice 只有在 local workflow exact replay与真实 provider run均 PASS 后才能形成。

Schema changes: none。

Migration: none。

Error behavior: workflow exact replay非零时保持 `P0-GAP-002 OPEN`；remote/provider/authorization 缺失、run 非 success、commit 不匹配、artifact 缺失或 required check 未配置时保持 `P0-GAP-001 OPEN`。任一 gap 未关闭则 P0 `NOT_READY`、P1 forbidden；不得隐藏失败历史或降低 gate。

Tests: integration test 必须断言 workflow 指向 TASK-P0-10、没有旧 TASK-P0-08 handoff、全部 P0 commands/artifacts仍存在；提交前后运行 TASK-P0-10 full/diff gate。provider run 必须执行 exact sync、lint、type、全部 P0 tests/machine reports、Compose config、docs/diff 与 build；本地复验不能替代 provider result。

Benchmark impact: P0 conditional hook 可保持 deferred；不得安装 Solver、创建假 Benchmark 或关闭 OPEN-012。

Simulation scenarios: 只由现有 workflow 重放 `SIM-MINIMAL-001` 和 mutation suite；不改场景或 Fixture。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；全部 P0 pytest suites；五类 machine reports；`docker compose --env-file .env.example config --quiet`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md --check-diff --report build/traceability/TASK-P0-10-report.json`；`git diff --check`；`uv build`。GitHub provider commands：`git push origin main`；`git ls-remote origin refs/heads/main`；以 PowerShell `Invoke-RestMethod` 读取 `https://api.github.com/repos/kumamon-xu/PlantNexus-APS/actions/workflows/ci.yml/runs?event=push&branch=main&per_page=20`，并按当次 immutable HEAD 选择唯一 run；读取 `/actions/runs/{run_id}`、`/actions/runs/{run_id}/jobs?per_page=100`、`/actions/runs/{run_id}/artifacts?per_page=100`；使用短期进程外 `GITHUB_TOKEN` 或已认证 GitHub session 读取 `/repos/kumamon-xu/PlantNexus-APS/branches/main/protection`，确认 `validate` 为 required check。GitHub REST headers 固定包含 `Accept: application/vnd.github+json`、`X-GitHub-Api-Version: 2022-11-28` 与非敏感 `User-Agent`；任何 token 不得回显、写入命令记录或 repository。

Artifacts: workflow handoff diff report/integration evidence；external run URL/ID、commit SHA、job conclusion、uploaded evidence artifact identity/digest、required-check/branch-protection evidence；更新后的 audit report/manifest。

Explicitly excluded: 超出 GitHub repository `kumamon-xu/PlantNexus-APS` / `main` / `P0 engineering gates` 的外部操作，超出明列路径的 checker/refactor、P1 Task/implementation、弱化 CI、真实 Solver/Benchmark、Production readiness。

PROD_OPEN: 不关闭 OPEN-001～015；CI provider 选择不是生产业务事实。

SIM_ASSUMPTIONS: 不新增或修改，SIM-ASSUMPTION-001～009 保持 `ACTIVE`。

Rollback: workflow handoff 回滚必须恢复到仍能审计当前 commit 的已验证版本，不能恢复成硬编码旧 Task 的失败状态；provider 配置回滚方式在获得授权和选定 provider 后补齐。审计/run 历史不得删除或改写；失败时保持 P0 active 和对应 gaps open。

## Completion evidence

执行中。2026-08-19 已确认 `origin` 为 `git@github-kumamon:kumamon-xu/PlantNexus-APS.git`、`main` 与 `origin/main` 均指向 Diff base `5d8bb51e06add1afc2f53861cf53c7a2ba45a272`且工作树干净；用户明确要求继续 TASK-P0-10。GitHub Actions baseline run [`32227247262`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32227247262) 在该 SHA 上真实 `failure`：`validate` job 仅 `Documentation and task diff` step 失败，其他已执行 gates 成功；artifact `p0-engineering-evidence-32227247262` / ID `9355951091` / digest `sha256:5356e4bdb7ae139bb371f340b34836fc0d74154351cd12dfb0a176682512844f` 已上传。这是 remediation 前的失败基线，不是 completion PASS。
