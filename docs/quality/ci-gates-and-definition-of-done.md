---
doc_id: DOC-QUAL-006
title: CI Gate 与 Definition of Done
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [58, 72, 74, 76, 78, 80, 89, 100, 101]
last_reviewed: 2026-08-20
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

## P1 planning and CI handoff

P0 Gate通过并获得用户明确 phase transition授权后，current phase已更新为 P1。TASK-P1-01把local phase policy与provider workflow收敛为同一机制：current phase只读 `docs/current_phase.md`；PR使用base SHA、main push使用event `before` SHA；`--discover-task-from`要求event range唯一归属current-phase Task，再按该卡自身 `Diff base`做scope/impact检查。

workflow继续运行 exact lock、Ruff、Pyright、全部既有 unit/contract/simulation/golden/validation/integration tests、五类machine contract、Compose、full/diff governance、conditional Benchmark hook与build；报告改为`ci-*.json`，artifact为`plantnexus-ci-evidence-<run-id>`。integration contract拒绝P0-08/P0-10 Task残留、multiple/stale Task attribution和`continue-on-error`。

repository-local workflow contract完成后，用户追加了直接push `main`与provider核验授权。completion commit `2d2a4432aa42e4f38ee8ae736e2acf2df1c694b9`对应GitHub run [`32237649319`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32237649319)为`success`，`validate` job `96021094432`及全部steps均`success`；artifact `9359554539`名为`plantnexus-ci-evidence-32237649319`，digest=`sha256:bdd08f01ea23e8fe93f82c199274afc0aa5e9343ea7fa70adfb6df6a950d1216`且未过期。该证据只把P1-01 provider execution从`NOT_RUN`更新为`PASS`；无Solver runner、BenchmarkReport、生产阈值或P1数据能力。

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
- P1及以后 Task的 `Completion conditions`逐项满足并有真实证据。
- P2及以后Task的`Start gate`、`Dependency changes`、`ADR impact`和`Provider evidence`逐项满足；planned卡不得预填implementation SHA或PASS。

## Phase Done

只有对应 Milestone 的全部 Exit Gate 有真实 Artifact 证明时才能更新 `current_phase.md`。任务全部关闭不自动等于 Phase 通过，未经确认不得进入下一阶段。

## TASK-P1-11 CI gate

Repository workflow在完整pytest与既有machine contracts之后必须运行P1 common-ingress CLI，输出`build/validation/ci-p1-data-pipeline.json`，并由中性`plantnexus-ci-evidence-${{ github.run_id }}` artifact上传。Gate必须是14/14 checks PASS，四项exact `DATA_ERROR`、Import/Snapshot/Problem replay和Reference/Synthetic parity任一失败都使job失败，不允许`continue-on-error`。

本地PASS、workflow text contract与未提交report不是provider evidence。P1-11 implementation commit `fa6c4c1159972a30ea683ad4e6eba98342d3c344`的push run `32322511227`、required `validate` job `96287321281`与artifact `9390250284`已成功并精确绑定43-path/7-row/0-issue Task report及14/14 pipeline report，因此该Task provider Gate闭环。P1-11完成后仍必须由P1-12独立审计，不自动进入P2。

## TASK-P1-12 Exit Gate result

P1-12在Diff base `8830a6dc566df8093b601a82c87c74a9cfd97b59`上独立重跑locked sync、Ruff、Pyright、271项full tests、11项migration/exit-rejection focused tests、P1 pipeline 14/14、Rule/Generator/Golden/Mutation/Engineering reports、Compose、full/diff governance和`uv build`，全部exit 0。下载并解析P1-01～11的provider artifacts后，所有实现Task报告均绑定exact head/result=`PASS`/0 issues；P1-11 closure run `32322871271`进一步证明audit起点本身已经provider验证。

因此§74 P1 Gate=`READY`、blocking gaps为空。TASK-P1-12 implementation commit `a5d7e4a68dc12d48e36cb692500f59446f8097b4`的exact GitHub run `32326616525`、required `validate` job `96299073525`和artifact `9391591718`均成功；artifact精确记录30 paths、3 impact rows、0 issues与pipeline 14/14，Task lifecycle已闭环为`done`。用户于2026-08-20明确批准后，P1关闭为completed并进入P2；该后续授权不改写P1 audit发生时的边界。

## TASK-P2-00 phase planning CI handoff

P2 phase planning一次新增TASK-P2-00～14。CI仍使用PR base或push event `before`做event attribution；新增严格batch规则只允许唯一新建`TASK-Pn-00` owner和同range新建的planned/ready成员，拒绝既有/active/done成员、多个owner、预填SHA与历史/future卡。归属后仍用P2-00的immutable Diff base检查全部scope/impact，workflow命令和中性artifact命名不变。

本次不激活Benchmark hook、不安装OR-Tools、不增加P2 machine report。P2-00 implementation `3298229fae89a54e0641f5907ad90c4fa81569bf`已通过locked sync、273 full tests、full/diff governance与exact provider run `32332003608` / required job `96314305102` / artifact `9393345593`；artifact Task report为32 paths/5 rows/19 checks/0 issues，Task由evidence-only closure标记done。P2-01～14保持planned；P2-13以后才允许接入完整P2 Gate，P2-14最后独立审计。

## TASK-P2-01 contract CI gate

Workflow在repository suites与P1 common-ingress之后运行`app.planning.problem.contract_check`，生成`build/validation/ci-planning-problem-contracts.json`。报告必须为`planning-problem-contract-report.v1`、4/4 checks PASS，且同时包含v1 byte preservation/fixed replay与v2 Schema/sample/hash/field evidence；该step不得`continue-on-error`，artifact glob必须上传报告与current Task diff report。

本地89项focused、286项full、Ruff/Pyright和4/4 machine report均PASS。Implementation `c64284685f37ef0d03eacade5699076146653333`的exact run `32336812748`、required `validate` job `96327855244`和未过期artifact `9394931377`均success；artifact内Task report精确记录该SHA、60 paths/10 rows/0 issues，Problem report精确记录同一SHA与4/4 checks，因此P2-01由evidence-only revision标记`done`。这不是P2 vertical Gate，P2-02～14仍不得启动或提前标记。

## TASK-P2-02 contract CI gate

Workflow在PlanningProblem evidence之后运行`app.planning.policy.contract_check`，生成`build/validation/ci-planning-machine-contracts.json`。报告必须为`planning-machine-contract-report.v1`、5/5 PASS并绑定`PLANTNEXUS_CODE_COMMIT`；检查同时覆盖fixed artifacts、Policy/Limits、seven-status mapping、cross-document replay与implementation boundary。Step不得`continue-on-error`，现有`build/validation/*.json`和`build/traceability/*.json`artifact glob必须同时上传该报告与current Task diff report。

本地54项指定suite、311项full、Ruff/Pyright、5/5 machine report、Compose/build与63-path/11-row/0-issue governance均PASS。Implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`的exact push run `32342489997`与required `validate` job `96344226221`为`completed/success`且22个steps无失败；未过期artifact `9396828326`内machine report精确绑定该SHA并5/5 PASS，Task report精确绑定同一SHA、63 paths/11 rows/0 issues。P2-02据此由evidence-only revision闭环为`done`；P2-03/P2-04仍需用户另行明确授权，不能自动启动。
