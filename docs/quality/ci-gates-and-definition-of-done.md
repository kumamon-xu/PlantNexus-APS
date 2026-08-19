---
doc_id: DOC-QUAL-006
title: CI Gate 与 Definition of Done
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [58, 72, 74, 76, 78, 80, 89, 100, 101]
last_reviewed: 2026-08-19
---

# CI Gate 与 Definition of Done

## 常规验收命令目标

Backend：Ruff、type check、unit/contract/integration tests。Frontend：test 和 production build。P2 后增加 golden/simulation；涉及 Solver 的任务增加 PR Benchmark。

具体命令以仓库脚本和 lockfile 落地为准；在这些文件不存在前不宣称已运行。

文档/traceability 本地检查由 `scripts/check_docs.py` 实现，合同见 `documentation-consistency-checks.md`。Task 进入 `in_progress` 时记录完整 `Diff base`；acceptance 至少运行全仓检查、带 `--check-diff` 的当前 Task 基线范围检查和 `TEST-TRACEABILITY-VALIDATOR`，并确认提交前后均可复验。P0-08 已将它接入 PR/push workflow；P0 Release Gate 仍由 TASK-P0-09 审计。

P0-07 增加可本地复验的 fixture Validator gate：

```text
uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-07-validator-mutations.json
```

该 gate 必须同时得到 positive PASS、13 negative FAIL、C-001～C-011/required mutation 无缺口、exact v2 report/error、deterministic replay 和无 backend/OR-Tools 依赖；P0-08 workflow 已连同 rule/simulation/Golden contracts 一起执行。

## TASK-P0-08 executable workflow

`.github/workflows/ci.yml` 在 pull request 和 main push 上以 Python 3.12、`uv==0.11.32` 执行：

1. `uv sync --locked`；
2. `ruff check .` 与 Pyright；
3. unit/contract/simulation/golden/validation/integration 全部 P0 tests；
4. Rule Sheet、Simulation、Golden、Validator Mutation、Engineering 五类 machine reports；
5. `docker compose --env-file .env.example config --quiet`；
6. repository docs + TASK-P0-08 immutable diff-base check；
7. conditional PR Benchmark hook（当前无 runner/Solver，明确 deferred）；
8. `uv build` 与 machine evidence artifact upload。

workflow 使用 read-only repository permission、并发取消与 20 分钟 job timeout。Action tags、Compose image tags和本地 config validation 尚不等于 supply-chain hardened/digest-pinned Production pipeline；provider run/branch-protection 结果也不能由本地验收填造。TASK-P0-09 仍需用真实 evidence 审计 P0 CI Exit Gate。

## TASK-P0-09 audited result

2026-08-19 的 [P0 Exit Gate audit](../milestones/P0-exit-gate-audit-report.md) 重新执行 exact sync、lint、type、90 tests、五类 machine reports、Compose config、build 与 P0-09 governance gate；这些非 CI 层均 `PASS`。但 workflow 的 Documentation and task diff step仍硬编码 TASK-P0-08，在包含 audit paths 的 P0-09 commit上 raw exit 1；`git remote -v` 也为空，provider run URL/ID、external uploaded artifact 和 required branch-check evidence均为 `NOT_RUN`。因此 CI Gate为 `FAIL`，P0 总体为 `NOT_READY` / `NO_GO`。

TASK-P0-10 必须先关闭 `P0-GAP-002`：将 workflow diff gate有界交接到其 immutable Diff base并通过 integration/post-commit replay；再关闭 `P0-GAP-001`：对不可变 commit形成可核验 external run/artifact/required-check evidence。两项均完成并重新审计前 CI Gate不能关闭。TASK-P0-09 完成只表示审计真实完整，不表示 Phase Done。

## TASK-P0-10 workflow handoff

TASK-P0-10 将 workflow 中的五类 machine report、documentation diff report 和 uploaded artifact 名称交接到 TASK-P0-10，其中 exact governance command 为：

```text
uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md --check-diff --report build/traceability/TASK-P0-10-report.json
```

integration contract 显式断言新 command/artifact 存在且 workflow 不再含 `TASK-P0-08`；full docs gate、sync/lint/type/tests、Compose、Benchmark hook、build 和 `if: always()` artifact upload 保持。remediation 前 GitHub run `32227247262` 在 Diff base 上真实重现旧 docs step failure，并上传 artifact `9355951091`；这只是 failure baseline。TASK-P0-10 只能在新 immutable commit 的 GitHub job `success`、artifact digest 可读、`main` 的 `validate` required check 可核验且本地提交前/后命令全部 PASS 后标记 done。

上述完成条件现已形成：implementation commit `036bc23bc0ac4d60aab131c0d44eda5508e844d4` 的 GitHub run [`32228647627`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32228647627) 为 `success`，`validate` job 和全部 steps 均成功；artifact `9356432918` 的 provider digest 为 `sha256:d5cb630772f06732251f785a6ee6aff36856c2a2f619c4178f43b01ac3f0214b`；`main.protected=true` 且 required context/check 均为 `validate`。提交前与 clean post-commit diff governance均 PASS，因此 `P0-GAP-001/002` 已关闭，[P0 re-audit](../milestones/P0-exit-gate-audit-report.md) 将 CI Gate 判定为 `PASS`。

## Task Done

任务完成至少满足：

- Task Card 的目标、允许范围和明确排除项均遵守；
- Requirement/NFR/ENG 追踪已更新；
- Schema/Contract/ADR 影响已处理；
- Task Card 已填写文档影响、明确文档路径和追踪更新；
- change-impact matrix 要求的文档均已更新，或存在经审查的 `Documentation impact: none` 理由；
- 成功、错误、边界和回滚行为有测试证据；
- 没有新增未登记 PROD_OPEN/SIM_ASSUMPTION；
- 文档与实现一致；
- 文档一致性检查通过；
- 验收命令实际通过并记录结果。

## Phase Done

只有对应 Milestone 的全部 Exit Gate 有真实 Artifact 证明时才能更新 `current_phase.md`。任务全部关闭不自动等于 Phase 通过，未经确认不得进入下一阶段。
