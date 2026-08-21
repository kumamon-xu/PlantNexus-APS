---
doc_id: DOC-QUAL-006
title: CI Gate 与 Definition of Done
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [58, 72, 74, 76, 78, 80, 89, 100, 101]
last_reviewed: 2026-08-21
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
