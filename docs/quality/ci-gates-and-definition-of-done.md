---
doc_id: DOC-QUAL-006
title: CI Gate 与 Definition of Done
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [58, 72, 74, 76, 78, 80, 89, 100, 101]
last_reviewed: 2026-08-25
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

## TASK-P2-03 solver foundation CI gate

Workflow在P2-02 machine evidence后运行`app.planning.backends.cp_sat.contract_check`，输出`build/validation/ci-solver-backend-foundation.json`并由既有中性artifact glob上传。Step不得`continue-on-error`；报告必须为`solver-backend-foundation-report.v1`、6/6 PASS、exact OR-Tools identity/lock、零namespace violation、七状态总映射、显式参数以及empty/model-invalid serialization boundary。

本地39 focused、319 full、Ruff/Pyright、6/6 foundation、5/5 P2-02、6/6 historical Engineering、Compose/build均PASS。Implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的exact push run `32346208046`和required `validate` job `96355386111`均success；artifact `9398128763`内foundation绑定同一SHA/Linux x86_64并6/6 PASS，Task report为50 paths/9 rows/0 issues。P2-03据此闭环为`done`。该Gate不运行C-ID/OBJ-001/formal Validator/Benchmark，也不授权P2-04。

## TASK-P2-04 formal Validator CI gate

Workflow在P2-03 foundation evidence后运行`app.planning.validation.problem_validator_check`，输出`build/validation/ci-formal-schedule-validator.json`并由既有中性artifact glob上传。Step不得`continue-on-error`；报告必须为`formal-schedule-validator-report.v1`、6/6 PASS，包含fixed artifact fingerprints、formal positive/status independence、13 mutations/C-001～C-011、ValidationReport/Error schema+determinism、6 property examples和independent source boundary。

Repository suite同时执行formal unit/mutation/property与历史P0 validation，integration contract要求workflow exact CLI/report路径和机器报告counts/boundaries。该Gate不调用业务CP-SAT solve、不实现OBJ-001、不设置性能阈值，也不把synthetic correctness写成Production readiness。

Implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的exact push run `32350068318`与required `validate` job `96367085099`均`completed/success`；未过期artifact `9399519368` / digest `sha256:e67b8ca8bbb2690eca62a2df406b275876dda074dbea5855fccd9516c5d09a8f`内formal report绑定同一SHA并6/6 PASS，Task report绑定同一SHA且为38 paths/6 rows/0 issues。P2-04据此闭环为`done`；P2-05仍须另行授权。

## TASK-P2-05 required validate additions

Required `validate`在P2-03 foundation与P2-04 formal步骤之后运行`app.planning.backends.cp_sat.core_model_check --root . --report build/validation/ci-cp-sat-core-model.json`。Integration contract要求报告为`cp-sat-core-model-report.v1`、6/6 PASS、五个implemented C-ID、2 candidate/1 infeasible/2 precheck/2 Validator mutation/4 oracle cases，并明确objective未优化、future constraints deferred、candidate仅测试用途。

Artifact glob必须上传core、formal与Task diff报告且各自`code_commit`绑定exact GitHub SHA；step不得`continue-on-error`。Local PASS、provider run/job/artifact/digest及closure SHA均未核验前，TASK-P2-05不得标记`done`，也不得自动激活P2-06。

当前local Gate已通过64 focused、360 full、Ruff/Pyright、core/formal各6/6、49-path/6-row/0-issue治理、compose、build及immutable checks。下一门仅为implementation exact SHA的required `validate`与artifact；通过前Task保持`in_progress`。

Implementation provider Gate现已通过：SHA `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`、run `32354050257`、required `validate` job `96379299455`均success；artifact `9400957897`未过期且digest=`sha256:c40c20dcc09e2beb38e85bbead96b83e624c8badc25c88bf78cc5a3990c7d46c`，core/formal/Task报告绑定同一SHA并复现6/6、6/6及49 paths/6 rows/0 issues。TASK-P2-05 DoD完成；closure提交本身仍须另行核验exact provider，不自动授权P2-06。

## TASK-P2-06 required validate additions

Required `validate`在foundation/core/formal evidence后运行`app.planning.backends.cp_sat.temporal_model_check --root . --report build/validation/ci-cp-sat-temporal-model.json`。Integration contract要求`cp-sat-temporal-model-report.v1`为7/7 PASS，记录C-002/005/006/009、5 candidate、3 infeasible、2 precheck、4 Validator mutation、8 oracle cases、冻结fingerprints及objective/deferred boundary。

Step不得`continue-on-error`；artifact必须同时上传temporal/core/formal与Task diff reports，且`code_commit`绑定exact pushed SHA。Local PASS不替代required `validate`、artifact digest/expiry与内容复核；这些证据完成前TASK-P2-06保持`in_progress`，也不得自动激活P2-07。

Local Gate已通过87 focused、367 full、Ruff/Pyright 0、foundation/core/formal/temporal 6/6、6/6、6/6、7/7、53-path/6-row/19-check/0-issue治理、Compose、build与immutable checks。下一门仅为implementation exact SHA的required `validate`与artifact；通过前状态不变。

Implementation provider Gate现已通过：SHA `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`、run `32432482739`、required `validate` job/check `96626844156`（app `15368`）均success；artifact `9429579311`未过期且digest=`sha256:3d1dce2dad986669d5709d7f8cf3900287773863cdda430e791e007495d5259c`，temporal/core/formal/Task报告绑定同一SHA并复现7/7、6/6、6/6及53 paths/6 rows/19 checks/0 issues。TASK-P2-06 DoD完成；closure提交本身仍须另行核验exact provider，不自动授权P2-07。

## TASK-P2-07 required validate additions

Required `validate`新增不可跳过的`CP-SAT execution fact and hard lock model evidence`步骤，运行`app.planning.backends.cp_sat.fact_lock_model_check`并输出`build/validation/ci-cp-sat-fact-lock-model.json`。PASS要求7/7 checks、C-007/C-008、4 candidate、3 certified INFEASIBLE、4 precheck、2 independent Validator mutation、6 tiny oracle、fixed fingerprints与real telemetry全部成立；历史foundation/core/temporal/formal steps继续PASS。

Step不得`continue-on-error`；artifact必须同时上传fact-lock/temporal/core/formal与Task diff reports，且`code_commit`绑定exact pushed SHA。Local PASS不替代required `validate`、artifact digest/expiry与内容复核；完成这些证据前TASK-P2-07保持`in_progress`，也不得自动激活P2-08。

Local Gate已通过93 focused、382 full、Ruff/Pyright 0、foundation/core/formal 6/6与temporal/fact-lock 7/7、54-path/6-row/19-check/0-issue治理、Compose、build、`git diff --check`和immutable checks。下一门仅为implementation exact SHA的required `validate`与artifact；通过前状态不变。

Implementation provider Gate现已通过：SHA `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`、run `32435395744`、required `validate` job/check `96635463577`（app `15368`）均success；artifact `9430579117`未过期且digest=`sha256:a6b6ff7413b8010a8012ddd351a2a194b89b1a13cdf71c6dada5d6afa53a44ab`，fact-lock/temporal/core/formal/Task报告绑定同一SHA并复现7/7、7/7、6/6、6/6及54 paths/6 rows/19 checks/0 issues。TASK-P2-07 DoD完成；closure提交本身仍须另行核验exact provider，不自动授权P2-08。

## TASK-P2-08 required validate additions

Required `validate`在foundation/core/temporal/fact-lock/formal evidence后运行`app.planning.backends.cp_sat.objective_strategy_check --root . --report build/validation/ci-objective-strategy.json`。PASS要求7/7 checks、固定合同/model/Validator/ADR/lock fingerprints、approved Simulation Policy/Limits、exact objective shape/unit、4个brute-force optimum、4个Validator PASS、1个certified INFEASIBLE、完整status/report/provenance及Production/OBJ-002/003/Reference/Benchmark/Export边界。

Step不得`continue-on-error`；artifact必须同时上传objective-strategy及全部历史machine/Task reports且`code_commit`绑定exact pushed SHA。Local `70 focused`/`395 full`与7/7 machine PASS不替代required `validate`、artifact digest/expiry和内容复核；这些证据形成前TASK-P2-08保持`in_progress`，P2-09不自动启动。

Local Gate现已通过70 focused、395 full、Ruff/Pyright 0、objective/strategy 7/7及全部历史machine reports、142-doc治理与52-path/8-row/19-check/0-issue Task report、Compose、build、`git diff --check`和冻结路径检查。下一门仅为implementation exact SHA的required `validate`与artifact；通过前状态不变。

Implementation provider Gate现已通过：SHA `b1ec83ed96120357ecadd41d3f520181838f17c6`、run `32438785162`、required `validate` job/check `96645152864`（app `15368`）均success；artifact `9431673977`未过期且digest=`sha256:843c036ffa3e133a9bceee1ca3b3320ce42a790cc955f01e94acab135f8fab5d`，14份validation reports、objective/strategy 7/7与Task 52 committed/0 working/8 rows/19 checks/0 issues均绑定同一SHA。TASK-P2-08 DoD完成；evidence-only closure仍须由自身exact provider复核，不自动授权P2-09。

## TASK-P2-09 correctness CI Gate

Workflow在完整repository tests之后执行`python -m app.simulation.scenarios.p2_correctness`并上传`ci-p2-correctness.json`。该step不得`continue-on-error`；报告必须为8/8、7 scenarios/Validator/property、11 mutations、C-001～C-011正负覆盖，并复核历史asset/frozen input hashes。Integration contract同时断言命令、report路径、counts/check names和全部scope boundaries。

Local Gate现已通过45 focused、427 full、Ruff/Pyright 0、correctness 8/8及全部历史machine reports、142-doc/58-path/7-row/19-check/0-issue治理、Compose、build、version smoke、`git diff --check`和immutable checks。Push后required `validate`、artifact digest/expiry、report `code_commit`及Task report必须绑定exact implementation SHA；完成前TASK-P2-09保持`in_progress`，不启动P2-10。

Implementation provider Gate已通过：SHA `20e49c92306128b47313059fabe31534814dbe3d`、run `32442651322`、required `validate` job/check `96656224252`（app `15368`）均success；artifact `9432982306`未过期且digest=`sha256:c736a2f029f119850f8a0c9b40b0dbbd0898383f10ddbc798f7182ff5ec90e09`。16/16 reports、correctness 8/8及Task 58 committed/0 working/7 rows/19 checks/0 issues均绑定同一SHA；TASK-P2-09 DoD完成，不自动授权P2-10。

## TASK-P2-10 Reference Scheduler CI Gate

Workflow在P2 correctness evidence后执行`python -m app.simulation.baselines.reference_schedulers --root . --report build/validation/ci-reference-schedulers.json`。该step不得`continue-on-error`；Integration contract要求`reference-scheduler-report.v1`为7/7 PASS，包含5 identities、7 Problems、35 complete candidates/independent Validator passes/deterministic replays、5 heuristic failures及完整scope boundaries。

Local code Gate为13个Task-specific tests、441个full repository tests、Ruff/Pyright零问题与reference report 7/7；全部历史machine reports、Task差异治理、Compose、build、冻结hash和`git diff --check`也均PASS。

Implementation provider Gate已通过：SHA `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`、run `32449742281`、required `validate` job/check `96675839685`（app `15368`）均success；artifact `9435264655`未过期且digest=`sha256:db250a86929c7e2c50ef0c24a2cbf74940a7b244e5d9499e42e087f4cd94c784`。17/17 reports、reference 7/7及Task 38 committed/0 working/6 rows/19 checks/0 issues均绑定同一SHA；TASK-P2-10 DoD完成，不自动授权P2-11。

## TASK-P2-11 output-contract CI Gate

Workflow在reference evidence后执行`python -m app.exporters.contract_check --root . --report build/validation/ci-p2-output-contracts.json`，不得`continue-on-error`。Integration contract要求`p2-output-contract-report.v1`为8/8 PASS并验证schema/sample、frozen inputs、deterministic package、lineage、negative cases、atomic replay/cleanup及non-publishable boundaries；报告随既有`plantnexus-ci-evidence-<run-id>`上传。

Local code Gate已通过指定49项、全仓455项、Ruff/Pyright零问题、output report 8/8及全部历史machine reports；full/diff文档治理为142 docs、58 paths、11 rows、19 checks、0 issues。Compose、build、schema metadata、immutable/forbidden-path和`git diff --check`也均PASS。

Implementation provider Gate已通过：SHA `546292831c3bd52185687a4c646c10ae10541ae2`、run `32454693799`、required `validate` job/check `96689627030`（app `15368`）均success；artifact `9436863185`未过期且digest=`sha256:77dfadb425f1c3f47d21494127785c81357351aeee6ecbdd4f00386516db054b`。18/18 reports、output 8/8及Task 58 committed/0 working paths、11 rows、19 checks、0 issues均绑定同一SHA；TASK-P2-11 DoD完成，不自动授权P2-12。

## TASK-P2-12 Benchmark CI Gate

Workflow中的deferred conditional hook已替换为不可跳过的`P2 XS BenchmarkRunner evidence`步骤：固定`PLANTNEXUS_BENCHMARK_PROFILE=xs`并写`build/benchmarks/ci-xs.json`。Artifact upload在`if: always()`下同时收集validation、traceability与benchmark JSON；integration contract禁止deferred文案、S/M进入PR步骤或遗漏baseline binding。

本地Gate已通过27项指定测试、full repository `466 passed`、Ruff/Pyright 0、XS/S/M三份8/8 BenchmarkReport、P2-11 output 8/8及全部历史machine reports。Compose、build、142-doc治理与49 paths/7 rows/19 checks/0 issues的Task diff同样PASS。CI XS是development regression，不是Production capacity/SLA或完整P2 Gate。

Implementation provider Gate已通过：SHA `01e7f4bdca88fc903e7caa771f875fc1a70ff357`、run `32460861563`、required `validate` job/check `96707353990`（app `15368`）均success；artifact `9438899443`未过期且digest=`sha256:caeb61fbbbd100c301725073398410e50e4b79f979f0b72df08d32a28fc2874e`。19/19 reports、XS benchmark 8/8/0 warning及Task 49 committed/0 working paths、7 rows、19 checks、0 issues均绑定同一SHA；TASK-P2-12 DoD完成，不自动授权P2-13。

## TASK-P2-13 Vertical Slice CI Gate

Workflow在既有P2 XS Benchmark step后新增不可跳过的`P2 vertical slice Gate evidence`：执行`python -m app.application.p2_gate_report --root . --repeat 2 --report build/validation/ci-p2-vertical-slice-gate.json`。该命令内部再次完整运行七类correctness、XS/S/M、Global+五Reference、fresh Validator、KPI/SolverReport/internal Export与四类fail-closed边界；单一Gate report随既有validation/traceability/benchmark glob上传。

Local Gate现为2 replays、11/11 checks、14 correctness scenarios、22 mutations、6 benchmark profiles、108 benchmark Validator passes、8 Export executions、4 rejections、stable semantic hash unique=`1`、0 blocking gaps。FAIL report必须非零，workflow不得`continue-on-error`。这只形成TASK-P2-13 implementation candidate；exact implementation SHA required `validate`/artifact尚须push后核验，且本Task绝不产生P2 Exit READY。

Implementation provider Gate已通过：SHA `dc2e5cd41080603606090ebfc4bc6162941c5f7f`、run `32465737712`、required `validate` job/check `96721819879`（app `15368`）均success；artifact `9440650646`未过期且digest=`sha256:35e67191d1026169d9acd2a64f50e93bd8d2704df9f8ba1a2297f2dd2a00ca4d`。20/20 reports、Gate 11/11及Task 37 committed/0 working paths、6 rows、19 checks、0 issues均绑定同一SHA；TASK-P2-13 DoD完成，但P2 Exit READY仍未执行。

## TASK-P2-14 Exit Gate audit

审计先验证P2-01～13共26个exact implementation/closure runs/jobs/artifacts，再在provider-verified activation head独立执行locked sync、Ruff、Pyright、476 tests、两次P2 Gate、XS/S/M、Compose、docs与build。Gate=11/11、七场景×两轮§76 measurement完整、XS/S/M各8/8、4 rejections、0 gaps，因此report/manifest给出`READY`。

Decision writing commit `65c556789f176ad9de55523d6420737bb60f933f`的exact required run `32677741558` / job `97288829348` / artifact `9503227240`已全部success；下载复核20/20 JSON、Task 30 paths/3 rows/19 checks/0 issues及Gate 11/11均绑定同一SHA。因此TASK-P2-14在本evidence-only closure标记`done`且READY保持；P2仍保持current phase，等待用户明确P2→P3授权。

## P3 planning and CI handoff

用户已批准P2→P3；TASK-P3-00是本batch唯一owner，P3-01～15均为planned member。本规划未修改workflow；required `validate`通过current-phase discovery选择P3-00。Implementation `1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7`的run `32681493976` / job `97298850740`为success且32/32 steps成功；artifact `9504310381`未过期，digest=`sha256:306ccfc7fedef1541c36bcc4afb0727239bd3fb9a17dd4b7ea022fd7c3d4fe64`，20/20 JSON与Task 64 paths/4 rows/19 checks/0 issues一致。因此本closure把P3-00标为`done`；closure自身仍须push后核验。

未来每张P3 Task必须按卡片运行locked install、lint/type、相关unit/contract/integration/E2E/migration/build、full docs/diff治理和machine report。P3-14聚合Gate不替代P3-15独立Audit；两者READY均不构成P4 transition或Production release。

## TASK-P3-01 provider boundary

P3-01从TASK-P3-00 closure `7f65f88b620ea1e8d2f4693911be3b52f4052d5d`启动；该baseline required run/job/artifact=`32682015727`/`97300206924`/`9504453154`成功，artifact内Task/SHA、4 Impact rows、19 checks和0 issues一致。当前Task不修改workflow；current-phase discovery必须选择唯一changed card TASK-P3-01。

Implementation本地full docs、Task diff、27项指定治理/规则回归、`git diff --check`和禁止范围均通过。Exact SHA `3bf99cbafdad983795a83a88646240dbb0b24509`的run `32684713630` / required `validate` job `97307562801`（app `15368`）为success且32/32 steps成功；artifact `9505303054`未过期，digest=`sha256:06cd50a3172e234a9d2227737ecbfa648a4eb3b35cfc2d34c0e1d3bdb597b593`，20/20 JSON PASS，Task report为43 committed/0 working paths、4 rows、19 checks和0 issues。因此只允许本evidence-only closure更新状态/证据并再次通过exact required provider；不得借closure启动P3-02或写入P3行为。
## TASK-P3-02 required workspace contract gate

Required `validate`新增non-continue步骤：

```text
uv run python -m app.domain.workspace_contract_check \
  --root . \
  --report build/validation/ci-p3-workspace-contracts.json
```

报告必须为`p3-workspace-contract-report.v1`、Task=`TASK-P3-02`、schema set=`2.6.0`、8/8 checks、7 Schema/7 sample、34 frozen P2 artifacts、24 shape negative、6 fingerprint negative并绑定`PLANTNEXUS_CODE_COMMIT` exact SHA。现有`build/validation/*.json` artifact glob会上传它；缺失/FAIL不能continue。Gate PASS只证明机器carrier与历史冻结，不证明P3 persistence/state/API/UI、P4或Production。

Implementation provider Gate已通过：SHA `aff27d3d6b63fb9f216c9a2687408a6c676fa96a`、run `32689832111`、required `validate` job/check `97321420908`（app `15368`）均success；artifact `9506913562`未过期，digest=`sha256:fdc527be47df10febdd50395134b0a97799e15c2607fa0202c99d6679798ef0b`。21/21 JSON PASS，workspace 8/8与Task 65 committed/0 working paths、10 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-02 DoD完成，不自动授权P3-03。

## TASK-P3-03 required persistence evidence

Required `validate`新增non-skippable `P3 workspace persistence evidence`：`uv run python -m app.infrastructure.workspace_persistence_check --root . --report build/validation/ci-p3-persistence.json`。报告必须为`p3-persistence-report.v1`、Task=`TASK-P3-03`、migration=`0004_schedule_versions_audit_export_jobs`、status PASS、8/8 checks、5 tables、4 repositories、4 DB mutation与2 plane mismatch拒绝，并与Task report绑定同一`PLANTNEXUS_CODE_COMMIT` exact SHA。

本地PASS只允许Task保持`in_progress`。只有implementation push的required run/job成功、artifact同时复现persistence/Task report的SHA、7 Impact rows、全部checks和`issues=[]`后，才可进行evidence-only closure；closure自身也须exact provider。任一migration/replay/CAS/lease/rollback/artifact失败阻止P3-04，不得删历史row或改写migration恢复绿色。

Implementation provider Gate已通过：SHA `e315dbf4f6c079df6d19b52f0403b00827126232`、run `32694644036`、required `validate` job/check `97334382152`（app `15368`）均success；artifact `9508445635`未过期，digest=`sha256:4a0d30ae020c998e2b2a399a3c8c93848b14b66daecaa3c75b95fa7f11feb588`。22/22 JSON顶层PASS，persistence 8/8与Task 52 committed/0 working paths、7 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-03 DoD完成，不自动授权P3-04。

## TASK-P3-04 required lifecycle evidence

Required `validate`新增non-skippable `P3 reviewable ScheduleVersion lifecycle evidence`：

```bash
uv run python -m app.application.schedule_version_lifecycle_check \
  --root . \
  --report build/validation/ci-p3-schedule-version-lifecycle.json
```

报告必须为`p3-schedule-version-lifecycle-report.v1`、Task=`TASK-P3-04`、schema set=`2.6.0`、lifecycle=`schedule-version-lifecycle.v1`、8/8 checks、1 reviewable Version、1 atomic audit、1 exact replay、5无副作用拒绝、service Solver调用0、`issues=[]`，并与Task report绑定同一`PLANTNEXUS_CODE_COMMIT` exact SHA。Workflow不改变required job名称、permissions、Secret、service/deployment并复用既有artifact glob。

本地PASS只允许Task保持`in_progress`。Implementation push后必须核验required run/job、下载artifact并逐项核对SHA/Task/8 checks/八Impact rows/full checks/issues；成功后才可做evidence-only closure，closure自身也须exact provider。READY_FOR_REVIEW evidence不构成approval/publish/Production readiness，任一Validator/transaction/audit/provider失败阻止P3-05自动启动。

本地实现Gate现已实际通过：35 focused、515 full、Ruff、Pyright、8/8 lifecycle、全部既有machine contracts、P2 Gate、XS benchmark、Compose、build、full/diff docs治理及forbidden boundary均无失败；Task report为45 paths/8 rows/19 checks/0 issues。该结果不替代push后的exact provider Gate，Task仍为`in_progress`。

Implementation provider Gate已通过：SHA `a9be974855bb825784d639b7f6675e5a33e4273d`、run `32700005280`、required `validate` job/check `97349447107`（app `15368`）均success；artifact `9510215582`未过期，digest=`sha256:828311f8b2f512aa6ddcbf113d80aba2e475e99f192867cad1d14dda53842d54`。23/23 JSON顶层PASS，lifecycle 8/8与Task 45 committed/0 working paths、8 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-04 DoD完成，不自动授权P3-05。

## TASK-P3-05 required read-model evidence

Required `validate`增加唯一step：`uv run python -m app.application.workspace_read_model_check --root . --report build/validation/ci-p3-workspace-read-models.json`。报告必须为`p3-workspace-read-model-report.v1`、Task=`TASK-P3-05`、schema set=`2.6.0`、read model=`workspace-read-model.v1`、8/8 checks、14 views、两个versioned synthetic inputs、query/comparison各1次exact replay、4类negative、product-service Solver调用0、durable read前后不变且`issues=[]`。

本地PASS只允许Task保持`in_progress`。Implementation push后必须核验exact SHA required run/job/app、下载artifact并核对read-model/Task report的Task/SHA、7 Impact rows、all checks/issues；成功后才可evidence-only closure，closure自身也须exact provider。该Gate不形成HTTP/UI、approval/publish/export、P4或Production readiness，也不自动启动TASK-P3-06。

本地implementation Gate已通过：33 focused、527 full、locked sync、Ruff、Pyright、Compose、build、8/8 read-model machine、full/diff docs、`git diff --check`和禁止路径均PASS；提交前Task report为50 working paths、7 rows、19 checks、0 issues。

Implementation provider Gate已通过：SHA `f236fab47aa2565b87a060b2c8bde8f2e8d66229`、run `32706258281`、required `validate` job/check `97367902547`（app `15368`）均success；artifact `9512423712`未过期，digest=`sha256:46f783ea4871d845aab57cf84bc3952b4686d52e4fb8a327087e6d75e77b4219`。24/24 JSON顶层PASS，read-model 8/8与Task 50 committed/0 working paths、7 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-05 DoD完成，不自动授权P3-06。

## TASK-P3-06 required command evidence

Required `validate`新增唯一step：`uv run python -m app.application.schedule_command_check --root . --report build/validation/ci-p3-schedule-commands.json`。报告必须为`p3-schedule-command-report.v1`、Task=`TASK-P3-06`、schema set=`2.6.0`、pipeline=`schedule-command-pipeline.v1`、8/8 checks、5 command types（4 content + 1 submit）、5 fresh Validator passes、2 exact replay/1 conflict、2 historical source states、Solver调用0、`issues=[]`，并明确failed candidate discarded、source content update absent、manual DRAFT READY=`EXPLICIT_CAS_SAME_CONTENT`以及P4/Production readiness absent。

本地PASS只允许Task保持`in_progress`。Implementation push后必须核验exact SHA required run/job/app、下载artifact并核对command/Task report的Task/SHA、8 Impact rows、all checks/issues；成功后才可evidence-only closure，closure自身也须exact provider。该Gate不形成HTTP/UI、approval/publish/export、P4或Production readiness，也不自动启动TASK-P3-07。

本地implementation Gate已通过：41 focused、546 full、8/8 command machine、全部历史machine、P2 Gate 11/11、XS benchmark、locked sync、Ruff、Pyright、Compose、build、full/diff docs、`git diff --check`与禁止路径均PASS；提交前Task report为57 working paths、8 rows、19 checks、0 issues。

Implementation provider Gate已通过：SHA `08317637c7fbb51d46880d32523545bb0b4fe1c0`、run `32713635045`、required `validate` job/check `97390177509`（app `15368`）均success；artifact `9515126567`未过期，digest=`sha256:33e501d81fad861a0dba4f1f2760fb98ce0b22cf02c6ad04265174a6cb409e4e`。25/25 JSON顶层PASS，command 8/8与Task 57 committed/0 working paths、8 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-06 DoD完成，不自动授权P3-07。

## TASK-P3-07 required approval decision evidence

Required `validate`新增唯一step：`uv run python -m app.application.approval_decision_check --root . --report build/validation/ci-p3-approval-decisions.json`。报告必须为`p3-approval-decision-report.v1`、Task=`TASK-P3-07`、service=`approval-decision-service.v1`、8/8 checks、2 decision types、3 successful decisions、2 exact replay、1 conflict、3 authorization denial/audit、4 rejected requests without business state、1 atomic rollback、Solver调用0、`issues=[]`，并明确existing READY→APPROVED/REJECTED only、source content update absent、Production default-deny/OPEN-010、real RBAC/SSO/publish/export/API/UI/P4/Production readiness absent。

本地PASS只允许Task保持`in_progress`。Implementation push后必须核验exact SHA required run/job/app、下载artifact并核对decision/Task report的Task/SHA/Diff base、8 Impact rows、全部checks/issues；成功后才可evidence-only closure，closure自身也须exact provider。该Gate不形成HTTP/UI、publish/export、P4或Production approval/readiness，也不自动启动TASK-P3-08。

本地implementation Gate已通过：39 focused、562 full、8/8 decision machine、全部历史machine、P2 Gate 11/11、XS benchmark、locked sync、Ruff、Pyright、Compose、build、full/diff docs、`git diff --check`与禁止范围均PASS；提交前Task report为50 working paths、8 rows、19 checks、0 issues。Provider字段在真实push前不得预填。

初始implementation `3f85959e91e74966f6482426b9db296a45d715ef`的run `32793980039` / required job `97641324105`为failure：Linux上SQLite LargeBinary不支持该report使用的`BLOB LIKE`统计，故1项CI contract看到success/denial均为0而失败（其余556项PASS），artifact未生成；required suite还未列出新增security目录。纠正要求canonical JSON计数、同一required suite显式执行security tests，并保留本失败记录；纠正SHA的required validate/artifact成功前不得closure。

Corrective implementation provider Gate已通过：SHA `9aed9d8c5dd86a9a9b972f8e9c5491fd6d2dbaa6`、run `32794370664`、required `validate` job/check `97642478274`（app `15368`）均success；artifact `9544333991`未过期，97281 bytes，digest=`sha256:b96ca2fe44c7dff726f67bb3b23c11017d07de71bd196c6f6cd6b93dfdb2310f`、expiry=`2026-11-23T00:37:21Z`。下载复核26/26 JSON顶层PASS，decision 8/8与Task 50 committed/0 working paths、8 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-07 bounded DoD完成，本closure不自动授权P3-08且自身仍须exact provider。

## TASK-P3-08 required publication evidence

Required `validate`新增唯一step：`uv run python -m app.application.publication_check --root . --report build/validation/ci-p3-publication.json`。报告必须为`p3-publication-report.v1`、Task=`TASK-P3-08`、service=`publication-service.v1`、8/8 checks、3 successful publications、2 supersessions、1 replay、1 conflict、2 denial、4无业务state拒绝、1 rollback、1 concurrent current winner、Solver调用0、`issues=[]`，并明确APPROVED-only、PUBLISHED immutable、Simulation target、Publish/Export分离、Production default-deny及external/API/UI/P4 absent。

提交前本地Gate为focused 16、full 577、publication 8/8、全部历史machine、P2 Gate、XS benchmark、locked sync、Ruff/Pyright、Compose/build及full/diff治理全部PASS；Task report为51 working paths、8 rows、19 checks、0 issues。

Implementation provider Gate已通过：SHA `e90475f462b365d2e031445ad28a02ea0b89d2f5`、run `32798679852`、required `validate` job/check `97655144411`（app `15368`）均success；artifact `9545782727`未过期，98713 bytes，digest=`sha256:f836569f5793334129a643147bdb5609f2992374e1a26c64955bbb42deb64044`、expiry=`2026-11-23T01:44:03Z`。下载复核27/27 JSON顶层PASS，publication 8/8与Task 51 committed/0 working paths、8 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-08 bounded DoD完成，本closure不自动授权P3-09且自身仍须exact provider。该Gate不形成ExportJob/package、external publish、HTTP/UI、P4或Production readiness。

## TASK-P3-09 required ExportJob evidence

Required `validate`新增non-skippable `P3 ExportJob and standard package evidence`：`uv run python -m app.application.export_job_check --root . --report build/validation/ci-p3-export-jobs.json`。报告必须为`p3-export-job-report.v1`、Task=`TASK-P3-09`、schema set=`2.7.0`、8/8 checks、2 Schema/2 sample、16 focused、12 payload、4 XLSX sheet、五state/六pair、0 provider side effect并`issues=[]`。同一artifact glob必须上传该报告与Task diff exact SHA。Local PASS不替代implementation/closure exact provider；P3-10不自动启动，external/P4/Production不得声明。

提交前本地Gate已通过：16 focused、594 full、Ruff/Pyright、locked sync、27份machine reports、P2 Gate 11/11、XS benchmark 8/8、Compose、build、full/diff治理、`git diff --check`与冻结/禁止范围均PASS；Task report为76 working paths、13 rows、19 checks、0 issues。Provider字段在真实push前不得预填。

Implementation provider Gate已通过：SHA `42278239332e61e55a4e0305705534db768dc22f`、run `32805450589`、required `validate` job/check `97674572006`（app `15368`）均success且全部steps通过；artifact `9548027237`未过期，100011 bytes，digest=`sha256:77cda829c35ad0b7018fa15ea5176c257b6ed0b60c89f9dba244da80bba7fe26`、expiry=`2026-11-23T03:30:45Z`。下载复核28/28 JSON顶层PASS，export 8/8与Task 76 committed/0 working paths、13 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-09 bounded DoD完成，本closure不自动授权P3-10且自身仍须exact provider。该Gate不形成external transfer、HTTP/UI、P4或Production readiness。

## TASK-P3-10 required HTTP API evidence

Required `validate`新增non-skippable `P3 planning workspace HTTP API evidence`：`uv run python -m app.api.planning_workspace_check --root . --report build/validation/ci-p3-planning-workspace-api.json`。报告必须为`p3-planning-workspace-api-report.v1`、Task=`TASK-P3-10`、8/8 checks、17 paths/operation IDs/successful delegations、8 mapped error reasons、Production provider/application调用0、router business transition/Solver/Validator调用0，明确Schema/migration/dependency/state零变化、P4/Production未实现且`issues=[]`。同一artifact必须包含API与Task report并绑定exact SHA/Diff base/7 Impact rows。

本地Gate已通过：41 focused、最终603 full、API machine 8/8、required当前29份JSON evidence、P2 Gate 11/11、XS benchmark 8/8、locked sync、Ruff/Pyright、Compose/build与full/diff docs均PASS。首轮full曾因未修改的P3-09 deterministic XLSX用例瞬时失败（601/1），定向5次与后续完整重跑均PASS；provider若再现则停止closure。Local PASS不可替代exact implementation required run/job/app与下载artifact复核；provider成功后才可evidence-only closure，closure自身也须exact provider。该Gate不形成Frontend、真实identity、external adapter、P4或Production readiness，不自动启动TASK-P3-11。

Implementation provider Gate已通过：SHA `4958ce5759812331f13fab2608fbec37f1f1ff76`、run `32812163430`、required `validate` job/check `97693443111`（app `15368`）均success且全部steps通过；artifact `9550224090`未过期，101191 bytes，digest=`sha256:d8577d6429167d8782622722d4d64fb993e2db07cbca43a4f279bfd0ba3b9ecf`、expiry=`2026-11-23T05:16:01Z`。下载复核29/29 JSON顶层PASS，API 8/8与Task 51 committed/0 working paths、7 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-10 bounded DoD完成，本closure不自动授权P3-11且自身仍须exact provider。该Gate不形成Frontend、真实identity、external adapter、P4或Production readiness。

## TASK-P3-11 required Frontend evidence

Required `validate`须使用Node `24.19.0`和npm `11.17.0`执行locked `npm ci`，随后顺序执行point-in-time SCA、license、lint、typecheck、Vitest component、build和`p3-frontend-report.v1` machine evidence；任何step均不得`continue-on-error`。同一artifact glob必须包含Frontend/SCA/license/Task JSON并绑定exact implementation SHA和Diff base `26dd519b1f1f84e08d415cfdfce43f286fa82988`。

Dependency Gate逐字拒绝direct range、lock drift、High/Critical advisory、unknown/deny-listed license与peer conflict。用户批准的typescript-eslint边界只允许固定组`typescript-eslint=8.68.0`、`eslint=10.9.1`、`typescript=6.0.3`，且TypeScript须满足`>=4.8.4 <6.1.0`；不得用“latest”浮动解析。Playwright browser/E2E、P3-12/13、P4与Production不属于本Gate。

提交前Local PASS只允许Task保持`in_progress`；implementation push后必须核验exact SHA required run/job/app并下载artifact复核Task/SHA/Diff base、六个Impact rows、route/state/dependency/boundary checks和`issues=[]`。该门已由下述provider evidence满足；本evidence-only closure自身仍须exact provider。

当前本地Frontend Gate为npm ci、SCA、license、lint、typecheck、25/25 tests、build和9/9 machine PASS；SCA 0 advisory、license 336 package/0 issue、bundle 944682 JS/1365 CSS bytes。CI contract 28项、Python全仓604项、全部历史machine/P2 Gate/XS、Compose及build均PASS，并要求official registry lock、exact compatibility peers、无Playwright browser install及全部non-skippable commands。任何本地结果都不替代provider。

Implementation provider Gate已通过：SHA `567e8693db881ea3dfffa011de9021fef9641361`、run `32818657951`、required `validate` job/check `97712018632`（app `15368`）均success且全部steps通过；artifact `9552386549`未过期，103338 bytes，digest=`sha256:8d558b57453db04cb32ad55d8a42ff738b215100071f2564d46d185a78631aea`、expiry=`2026-11-23T06:49:23Z`。下载复核32/32 JSON顶层PASS，Frontend 9/9、SCA 0、license 336/0与Task 74 committed/0 working paths、6 rows、19 checks、0 issues均绑定同一SHA；TASK-P3-11 bounded DoD完成。该Gate不形成P3-12/13 browser/control、真实identity、P4或Production readiness，也不自动授权P3-12。
