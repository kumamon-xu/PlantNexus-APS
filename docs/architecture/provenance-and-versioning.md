---
doc_id: DOC-ARCH-009
title: Provenance 与版本规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [4, 23, 24, 40, 67, 93, 101, 102, 103, 104]
last_reviewed: 2026-08-21
---

# Provenance 与版本规则

## 计划结果最小来源链

```text
Snapshot ID / Hash
Source Versions
Rule Version
PlanningProblem Version / Hash
Solver Name / Exact Version / Parameters
Simulation Scenario / Profile / Generator / Seed（若适用）
Code Commit
Schema Versions
```

这些字段应进入数据库审计记录、成果包 `manifest.json` 和相应报告，而不是只存在于日志文本。

## 版本对象

| 对象 | 修改触发 |
|---|---|
| Implementation Spec | 规范语义变化，更新 `spec_version` |
| Data Schema | `schema_version++`、migration、compatibility rule、contract test |
| PlanningProblem | Contract/serializer 变化，更新 problem version 并回放 Benchmark |
| Solver | 精确依赖版本与参数进入 report；升级执行完整 replay |
| FactoryProfile | 任意语义/生成范围变化更新 profile version |
| ScenarioSpec | 能力、复杂度、期望行为或事件变化更新 scenario version |
| Generator | 生成逻辑变化更新 generator version |
| EventSimulator | 事件语义变化更新 simulator version |

## Hash 语义

Hash 输入必须 canonicalized，不能依赖无业务意义的对象顺序、运行时地址或 `generated_at`。同输入和同规则版本应得到相同 Snapshot/Problem hash；同 Scenario/Profile/Generator/seed 应得到相同 dataset hash。

不可追溯构建不得发布。

## P0-03 executable baseline

Schema set `1.0.0` 已同步写入 `pyproject.toml`、`app.SCHEMA_VERSION` 和 `schemas/data_dictionary.yaml`。每个 JSON Schema 使用稳定 URN `$id` 和显式 `*.v1` version field；Snapshot/Problem skeleton 要求 source/rule/builder/hash 引用字段，但 P0 不生成真实 hash。

Synthetic samples 明确携带 `scenario_id` 和非生产 hash 标记；Production Snapshot/Import envelope 禁止携带 scenario reference。Code commit、真实 source versions、canonical hash 和 end-to-end manifest 仍需在对应 builder/run/export Task 中形成，不能从 Schema 文件存在推断已完成。

## P0-04 rule contract release

Schema set `1.1.0` 在 `1.0.0` 上 additive 增加 error/validation v2、state-transition.v1 和四份 v1 YAML registries；既有 v1 文件与 URN 保留。Rule sheet、capability/error/state registry 各自携带独立 version，未来修改公式、状态 pair、code mapping 或 capability status 必须升对应版本并检查 Schema/Task/Test/Benchmark 影响。

`rule-contract-report.v1` 记录 contract counts 与 schema set，但不是 run provenance、ScheduleValidator report 或发布 manifest。P2/P3 真实运行必须引用 rule/state/error contract version 及 code commit；本 Task 不生成 Snapshot/Problem hash 或业务 audit。

## P0-05 Simulation contract release

Schema set `1.2.0` additive 增加 FactoryProfile/ScenarioSpec/ScenarioManifest v1，并保留 `1.0.0/1.1.0` artifacts。Profile/Scenario contract version、asset version、Generator version、canonicalization version、schema set 和 code commit 是独立维度；任一生成语义变化不得只借其他版本掩盖。

P0 empty package 的确定性输入为 Scenario ID/version、Profile ID/version、Generator ID/version、required capabilities 和 seed；输出为 Standard Import v1 canonical bytes 与 `sha256:` hash。Manifest `generated_at` 记录运行时间但不进入 dataset hash。`simulation-contract-report.v1` 证明同输入 replay、版本变化、命名 layer seed 与 isolation precheck；它不包含生产 source versions/code commit，不是发布 manifest、Snapshot/Problem hash 或历史 Benchmark artifact。

## P0-06 formal fixture provenance

`SIM-MINIMAL-001@1.0.0` 将 Profile `1.0.0`、Assembler `1.0.0`、seed 6001、required capabilities、Import package `SIMPKG-SIM-MINIMAL-001-1.0.0`、`canonical-json.v1`、SIM-ASSUMPTION-006～009 和 hash `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10` 连接为首个正式 fixture provenance chain。manifest `generated_at` 继续不进入 hash。

Golden Schedule/expected validation/KPI 各有 fixture-local version，并通过 Scenario/schedule ID 连接但不进入 dataset hash。任务验收的 Git Diff base/HEAD 记录代码来源；这些 artifact 仍不是 production run/export manifest、Snapshot/Problem hash 或 Benchmark baseline。任何语义改动必须发布新 asset version/hash，禁止覆盖 `1.0.0`。

## TASK-P0-08 build and logging provenance

`Settings.build_metadata()` 与 `health-report.v1` 固定公开 code/spec/schema/code-commit 四元组；Production 配置拒绝 `uncommitted` 或非 40 字符 commit。CI 将 `github.sha` 注入 code commit，local/development 可以显式使用 `uncommitted`。该字段使 API/Worker build 可关联，但不是 Snapshot/Problem/Solver/Scenario/Export manifest。

structured logs 可通过 contextvars 携带 `correlation_id`、可选 `run_id`/`job_id`，并从当前有效 OpenTelemetry span 注入 trace/span ID。日志不作为唯一 provenance 或 audit store；P0-08 没有 PlanningRun metric/audit persistence、source version、Snapshot/Problem hash、Solver version 或成果 manifest。Schema set 保持 `1.2.0`，code/spec/schema metadata 文件未改。

## TASK-P1-02 canonical provenance contract

Schema set`2.0.0`新增strict Import/Snapshot provenance。每条canonical record携带source system/version/record ID；Import v2携带source versions、normalization rule version和canonicalization version；Snapshot v2还携带rule/expansion version、Import package ID/version/dataset hash与quality report ID/version/PASS状态。Synthetic文档必须携带scenario/profile/generator各自版本和seed，Production文档禁止该引用。

这些字段只建立可追溯输入合同。Sample中的digest是符合格式的contract sentinel，不是builder计算结果；dataset hash、Snapshot canonical projection/ID/hash、code commit、persistence与发布manifest仍由后续Task形成。Import/Snapshot v1逐字保留，v1/v2不互换；Schema set、document、normalization、expansion、canonicalization、Scenario/Profile/Generator和code commit继续是独立版本维度。

## TASK-P1-03 staging provenance

`0002_raw_import_staging`持久保存source system/version、content SHA-256、row SHA-256/identity/location、source leaf name/media type/byte length、UTC received-at、data plane和完整synthetic Scenario/Profile/Generator/seed。持久化request fingerprint使用`canonical JSON + SHA-256`覆盖这些稳定字段与行顺序；candidate batch ID/received-at不参与，使相同idempotency request返回首次batch而不伪造新接收事实。source/version/content/row变化则显式conflict。

该fingerprint是Raw Staging幂等身份，不是Standard Import `dataset_hash`、Snapshot hash或Problem hash，也不替代Adapter/normalization/canonicalization/generator version。Migration revision和repository test形成internal persistence provenance；code commit/provider run只在Task完成证据中记录。当前没有成果包、run audit或Production source authority。

## TASK-P1-04 adapter provenance

Reference Adapter manifest固定`adapter_id=plantnexus.reference-file`、`adapter_version=1.0.0`、`staging_contract_version=raw-staging.v1`和`production_binding=false`。Source manifest必须显式给出adapter ID/version、relative path、batch/idempotency、source system/version、UTC received-at、data plane及conditional synthetic provenance；version mismatch在读文件前拒绝。

Adapter从实际bounded bytes计算content SHA-256，并把leaf name/media type/byte length与format-specific source location交给Raw Staging。相同CSV/XLSX业务行的row identity/raw payload可以相同，但文件digest/location不能被规范化成相同值。该版本链不是Import v2 normalization/canonicalization version、dataset hash或真实接口版本；这些仍需后续Task和OPEN closure evidence。

## TASK-P1-05 normalization provenance

Schema set additive `2.1.0`新增unit registry；Import v2 document自身仍固定`2.0.0`。Canonical `normalization_rule_version`确定性组合所有source-bound `profile_id@profile_version`与`unit-conversion-registry.v1`，source versions排序进入envelope；record source reference保留满足canonical identifier约束的显式source record ID，业务canonical ID则由namespace/authority/source value稳定哈希派生。Mapping或unit version变化必然改变bytes/hash。

Package ID从不含package ID的semantic envelope SHA-256派生，dataset hash覆盖最终`canonical-json.v1` bytes。Batch ID、idempotency key、received-at、file digest/name/media/location属于Raw Staging审计事实且不进入canonical hash，因此等价CSV/XLSX或重放批次可产生相同bytes。Simulation provenance必须完全一致并进入hash；Production禁止该字段。

## TASK-P1-06 quality provenance

Schema set additive `2.2.0`新增`error-code-registry.v2`、Error v3和ImportQualityReport v1；Import v2仍携带document-level `2.0.0`，unit registry v1仍为`2.1.0`。Quality report显式记录package ID、data-quality rule version、error registry version和report canonicalization version；不含generated-at、run ID或随机UUID。

每个issue以canonical entity/source/field定位并按稳定key排序；report ID对除self ID外的全部报告内容做`canonical-json.v1 + SHA-256`。因此相同package ID与相同issue集合得到byte-identical report，输入collection顺序不会改变Error顺序/ID。TASK-P1-06交由TASK-P1-08把PASS report ID与Import dataset hash一起绑定，当前实现见下节；quality report本身仍不替代Snapshot/Problem/code commit或publish provenance。

## TASK-P1-07 expansion provenance

`OrderExpansionDocument`记录`order-expansion.v1`、`canonical-json.v1`、Import document/schema/package/source/normalization/canonicalization/synthetic provenance，以及PASS report的schema/rule/error/canonicalization versions和report ID。Operation/edge identity分别对versioned lot-operation与lot-routing-edge lineage做canonical JSON SHA-256；output canonical bytes再形成`sha256:` expansion hash。该hash只标识pure expansion artifact，不冒充Import dataset、Snapshot或Problem hash。

同一Import/PASS report与expansion version重复运行、或只重排canonical collection/record顺序，必须得到byte-identical实例/edge/hash。未来语义变化发布新expansion version；v1不得原地重解释。TASK-P1-07在闭环时把Import dataset hash、quality report ID与expansion version留给TASK-P1-08绑定；下节记录当前已形成的Snapshot provenance，而code commit/run provenance仍须由实际提交与CI形成。

## TASK-P1-08 Snapshot provenance and identity

`snapshot-hash-projection.v1`固定Snapshot v2的semantic allow-list和排序规则，配合`canonical-json.v1`产生`sha256:` digest；ID使用显式`planning-snapshot-v2-<digest>` namespace。Self ID/hash、received/generated/runtime metadata不参与投影，cutoff及canonical business timestamps、facts、entity counts、source/rule/normalization/expansion/schema versions、Import dataset hash、quality report和synthetic provenance全部参与。

Builder验证P1 content-derived Import package ID并重新计算dataset hash，检查PASS report ID/package绑定及Expansion bytes/hash/全部version/provenance引用；相同输入得到byte-identical完整Snapshot，facts/cutoff/version任一变化得到新hash/ID。Repository另外保存完整canonical bytes SHA-256和非业务`created_at`，后者不反向污染Snapshot identity。

`0003_planning_snapshots`与repository形成artifact persistence provenance；implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`已由GitHub run `32310098594`及其SHA精确匹配的machine artifact闭环。该CI provenance只证明本Task代码/测试/治理重放；本Slice尚无PlanningProblem/code-commit PlanningRun manifest、Solver version、PlanningRun audit或Export manifest，这些不能从Snapshot hash或CI run推断。

## TASK-P1-09 PlanningProblem provenance and identity

`planning-problem-builder.v1`固定Snapshot v2→Problem v1的active-future投影，`planning-problem-hash-projection.v1`固定self/noise exclusion和stable collection ordering，`canonical-json.v1`形成最终bytes。Hash projection覆盖Problem version、content-derived Snapshot ID、builder version、tick/horizon、resources、active operations/candidates/RUNNING facts、edges、relevant calendar intervals与platform capability declarations；Snapshot ID本身已绑定Snapshot hash/rule/facts/upstream versions，故不在Problem schema重复复制整条provenance。

P1 canonical vector以Snapshot `sha256:44f422f81490159c4b0343a52aadd7991191684fa3b25394a0dd8b8a1b7e591a`产生Problem `sha256:6e4afffebf464de5c156094c894dccb5fe3efc712449f8583bcd91e1694dff72`，完整canonical bytes digest为`sha256:1f00ad7a856395328e9eb2c70afe8fe5878d69c3d8618ae7ef45bca34ef08645`。Self hash、generated-at、run ID和runtime nonce不进入projection；tick/horizon/builder或任一合法Snapshot事实变化会改变Problem identity。

该Problem hash不是PlanningRun manifest：code commit、Solver exact version/parameters、candidate solution、Validator、Benchmark、approval/export provenance仍未形成。Builder version/hash语义不得原地重解释；任何字段或投影语义变化必须发布新Problem/builder/hash版本并执行ADR/replay/benchmark review。

Implementation commit `e8c59547857d2eeace1c9f8b453a5a294cca5ef7`已由GitHub Actions push run `32315513504`、successful required `validate` job `96266776018`及digest匹配的machine artifact `9387907707`闭环；artifact Task report绑定immutable Diff base、该implementation SHA、30 committed paths、5 impact rows与0 issues。该provider provenance只证明TASK-P1-09 builder/hash代码、测试与治理重放，不扩张为PlanningRun/Solver/Production provenance。

## TASK-P1-10 generator provenance and identity

`synthetic-generation-manifest.v1`记录Scenario/Profile/Generator ID+version、seed、target、capabilities、generated-at、canonicalization、normalization rule、unit registry、Import v2/package ID、quality report引用和dataset hash。发布的`scenario-manifest.v1`仍只引用Import v1，本Task没有用局部consumer重新解释其Schema；P1 manifest因此是generator-local versioned contract。

Hash只覆盖Normalization产生的完整canonical Import v2 bytes。Raw received-at/content/source location和manifest generated-at不进入hash；synthetic provenance、mapping/unit/source versions与全部canonical业务值进入。`SIM-P1-INGRESS-001@1.0.0` replay hash为`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`，package ID为`import-9eea9bd41216b3a2b337a83f2b6f5438a287f219251168ce8d574f4b9fb6b2c6`；更改生成语义必须发布新generator/asset version，不得覆盖该identity。Implementation commit `5ac08183dd03049ad02c77e6cba80c4621847e0f`已由GitHub run `32319530217`/artifact `9389283489`精确重放，provider digest=`sha256:2b04b7bd134810c7d37d6130a2ba84911b6f672fb8a95ef83c761496370b73cf`。

## TASK-P1-11 pipeline provenance

`p1-data-pipeline-report.v1`同时记录repository commit/dirty state、Scenario/Profile/Generator/seed、Raw/Adapter/mapping/unit/quality/expansion/Snapshot/Problem各版本、planning cutoff/horizon/tick、entity counts、Import/quality/expansion/Snapshot/Problem的ID、canonical-byte digest与内容hash。当前固定vectors为Import `sha256:24a74b…`、Snapshot `sha256:090e0e…`、Problem `sha256:71c0b7…`。

Report的`generated_at`和working-tree/provider状态是run provenance，不进入业务artifact hash。本地运行只记录当前HEAD+未提交diff；provider evidence必须来自push后的exact GitHub run/artifact。Implementation commit `fa6c4c1159972a30ea683ad4e6eba98342d3c344`的run `32322511227`/artifact `9390250284`和closure commit `8830a6dc566df8093b601a82c87c74a9cfd97b59`的run `32322871271`/artifact `9390358424`均为`validate=success`，两份pipeline报告均14/14、相同三层hash且0 issues。

## TASK-P1-12 audit provenance

P1 Exit Gate audit把Diff base `8830a6dc566df8093b601a82c87c74a9cfd97b59`、P1-01～11 exact implementation commits/runs/artifacts、P1-12本地命令和machine report SHA-256、branch protection/required-check事实汇总到versioned audit report与`p1-exit-gate-evidence-manifest.v1`。审计execution head与随后提交的audit documentation commit分开记录，避免报告自我包含不存在的provider run；implementation commit `a5d7e4a68dc12d48e36cb692500f59446f8097b4`的run `32326616525`/artifact `9391591718`成功后，本evidence-only revision才回填其30 paths/3 impact rows/0 issues和pipeline 14/14事实。

该audit manifest不是PlanningRun、Solver或Export manifest，也不改变任何业务artifact hash。P1 Gate=`READY`仍要求current phase保持P1直至用户明确批准，不把CI provenance解释成Production authority或P2授权。

## TASK-P2-01 Problem v2 provenance chain

v2 identity链为`Snapshot ID/hash → problem_version=planning-problem.v2 → schema_set=2.3.0 → builder=planning-problem-builder.v2 → canonicalization=canonical-json.v1 → hash_projection=planning-problem-hash-projection.v2 → problem_hash`。projection覆盖DeliveryDemand due/priority各自source、Resource拓扑/calendar/capabilities/capacity、Operation/options、historical fact source/times、lock source/interval/type、edge/lag及tick/horizon/config；self hash和runtime noise排除。

固定report同时记录v1 immutable Schema/sample fingerprints及v1/v2 replay hash/bytes digest。Provider artifact必须绑定exact implementation commit和`PLANTNEXUS_CODE_COMMIT`；本地`uncommitted`report不替代GitHub evidence。Problem v2被后继consumer使用后不得用`latest`重解释，必须显式保存全部version IDs。

## TASK-P2-02 planning-machine provenance chain

新增链为`Problem v2 hash/reference → PlanningPolicy v1 canonical fingerprint → SolveLimits v1 canonical fingerprint → PlanningSolution v1 canonical fingerprint → SolverReport v1`。Policy/Limits分别保存ID/revision/source/data plane，Solution保存Problem builder/hash projection/tick/horizon与Policy/Limits exact refs，Report再保存Solution fingerprint、backend/solver exact versions/parameters、code commit、spec/schema/canonicalization/constraint/objective/state/error versions及metrics。

Global schema set为`2.4.0`，但Problem v2 document仍固定`2.3.0`，Import/Snapshot/quality/unit的历史版本也不改。所有fingerprint使用sorted finite JSON的`canonical-json.v1`；完整document参与且没有self fingerprint字段。四份published samples固定shape/canonical replay，但只有future `SOLVER_RUN` report和exact provider artifact能证明运行；当前`CONTRACT_SAMPLE`/`uncommitted`不能替代Solver、Validator、Benchmark或Production provenance。

## TASK-P2-03 solver foundation provenance

Backend identity固定为`cp-sat` / `cp-sat-backend.v1` / `Google OR-Tools CP-SAT` / `9.15.6755`，并与direct pin、lock SHA-256和平台信息一起写入`solver-backend-foundation-report.v1`。四个SolveLimits/Backend参数逐项记录name/source/value；native status使用显式0～4映射，CANCELLED/FAILED只来自adapter控制或错误路径，未知native code fail closed。

本地report的`code_commit=uncommitted`只证明工作树验收；push后CI必须以`PLANTNEXUS_CODE_COMMIT`绑定exact implementation SHA。Empty model的OPTIMAL与intentional invalid model的MODEL_INVALID均标记`business_feasibility=NOT_EVALUATED`、`candidate_produced=false`，不进入PlanningSolution/SolverReport业务provenance，也不形成Benchmark baseline。

Implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的GitHub run `32346208046` / required job `96355386111` / artifact `9398128763`已形成provider provenance。下载的foundation report绑定同一commit、Linux/x86_64、exact solver/lock且6/6 PASS；Task report绑定同一commit与Diff base、50 paths/9 rows/0 issues。该链只证明Backend foundation，不生成业务PlanningRun provenance。

## TASK-P2-04 formal validation provenance

正式链为`Problem v2 identity/hash + PlanningSolution fingerprint/assignments → independent C-001～C-011 evaluation → validation-report.v2 → optional error.v2 mapping`。稳定report保存Problem/Solution引用、constraint-rule-sheet版本、每个violation的C-ID/entity/observed/expected；candidate solver status不参与判定，输入Problem的合同/hash失败与schedule violation保持不同错误边界。

`formal-schedule-validator-report.v1`记录固定Schema/rule/fixture/lock hashes、positive与status contradiction replay、13个mutation的exact C-ID、6个duration/order examples、报告/schema determinism和source isolation。Local `code_commit=uncommitted`只证明工作树；implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的run `32350068318` / required job `96367085099` / artifact `9399519368`已绑定exact SHA，formal/Task report文件SHA-256分别为`1126e8ca…d669b`与`15c20fa5…b78a`。本链不生成Solver/Benchmark/Production provenance。

## TASK-P2-05 core solve provenance

Core solve链固定为`Problem hash + Policy fingerprint + Limits fingerprint + cp-sat-backend.v1/OR-Tools 9.15.6755 + parameters → native outcome → complete assignments → independent validation`。PlanningSolution ID由规范化输入fingerprint、assignments和诚实的业务`FEASIBLE`状态确定；纯可行模型的native OPTIMAL被降级为业务FEASIBLE，不能形成OBJ-001 optimality provenance。

`cp-sat-core-model-report.v1`记录五个implemented C-ID、模型变量/约束/optional interval计数、build/solve/first-feasible/solver-wall/Python-memory诊断、Validator状态、tiny oracle与冻结合同hash。Objective stage仅记录candidate的post-solve weighted tardiness、通用0 lower bound及`OBJECTIVE_NOT_OPTIMIZED` stop reason；local `uncommitted`仍须由exact GitHub SHA artifact替代后才能关闭Task。

Implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的run `32354050257` / job `96379299455` / artifact `9400957897`已完成exact绑定；artifact digest=`sha256:c40c20dcc09e2beb38e85bbead96b83e624c8badc25c88bf78cc5a3990c7d46c`。Core/formal/Task report文件SHA-256分别为`9986bd6a…1e44f`、`6f0f67c7…a3a28`、`16cc6147…32a36`，全部记录同一implementation SHA；TASK-P2-05 provenance据此闭环。

## TASK-P2-06 temporal solve provenance

当前链扩展为`Problem hash + Policy/Limits fingerprints + exact solver identity + temporal constraint metrics → complete candidate → independent formal validation`。Temporal report冻结Problem/Solution/Policy/Limits Schema、rule sheet、formal Validator、Planning contracts、Problem builder/hash与`uv.lock`指纹，并记录C-002/005/006/009 candidate、infeasible/precheck、Validator mutation、tiny oracle和真实model delta。

Local report的`code_commit=uncommitted`只用于工作树验收；Task关闭前必须由exact pushed implementation SHA的required `validate`与artifact替代。该链不改变Schema/Problem identity，也不产生OBJ-001 optimality、Benchmark baseline、ScheduleVersion或Production provenance。

Implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`的run `32432482739` / job `96626844156` / artifact `9429579311`完成exact绑定；artifact digest=`sha256:3d1dce2dad986669d5709d7f8cf3900287773863cdda430e791e007495d5259c`。Temporal/core/formal/Task report文件SHA-256分别为`014cbfe2…d1611`、`d338300d…d523`、`af575341…ebb5`、`06ebb6c7…9661`，全部记录同一implementation SHA；TASK-P2-06 provenance据此闭环。

## TASK-P2-07 fact/lock solve provenance

当前链扩展为`Problem hash（RUNNING actual/resource/remainder + anchors + locks）+ Policy/Limits fingerprints + exact solver identity + fact/lock metrics → complete assignments/lock references → independent C-007/C-008 validation`。COMPLETED anchor不产生future assignment；RUNNING历史字段和SOFT metadata由Problem identity保存，Solver不得猜造Problem未暴露的RUNNING execution fact ID。

`cp-sat-fact-lock-model-report.v1`冻结Problem/Solution Schema、rule sheet、formal Validator、Problem builder/hash、ADR-0007与`uv.lock`指纹，并记录4 candidate、3 certified INFEASIBLE、4 precheck、2 Validator mutation、6 tiny oracle及real model delta/telemetry。Local `code_commit=uncommitted`只用于工作树验收；Task关闭前必须由exact pushed implementation SHA的required `validate`与artifact替代。该链不产生OBJ-001 optimality、dynamic Replan、Benchmark baseline、ScheduleVersion或Production provenance。

本地工作树报告已7/7 PASS并与93 focused、382 full及54-path/6-row/19-check/0-issue治理相互印证；它仍不是可发布provenance。实现提交后必须以`PLANTNEXUS_CODE_COMMIT=<exact SHA>`重生成并由GitHub artifact验证，随后才允许写入closure evidence。

Provider provenance现已形成：implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的run `32435395744` / job `96635463577` / artifact `9430579117`全部success，artifact digest=`sha256:a6b6ff7413b8010a8012ddd351a2a194b89b1a13cdf71c6dada5d6afa53a44ab`。Fact-lock与历史machine reports及Task report全部绑定该SHA；这只证明bounded C-001～C-011 correctness，不产生OBJ-001 optimality、dynamic Replan、Benchmark、ScheduleVersion或Production provenance。

## TASK-P2-08 objective/run provenance

每次Global Strategy运行同时绑定Problem hash、approved Policy/Limits canonical fingerprints、PlanningSolution fingerprint、`planning_run_id`、exact backend/solver/version/parameters、OBJ-001 value/bound/gap、build/first-feasible/solve/validation/total、model size、memory与显式`code_commit`。SolverReport与Solution的problem/policy/limits/status/objective/diagnostics必须逐字一致并通过bundle replay；local `uncommitted`不能冒充provider SHA。

`objective-strategy-report.v1`冻结Problem/Solution/Report/Policy/Limits Schema、Planning contracts、core model、Problem hashing、formal Validator、rule sheet、ADR-0004/0006与`uv.lock` fingerprints，并记录4个tiny optimum/Validator及完整报告。它是correctness provenance，不创建ScheduleVersion/Export/approval/publish或Production authority；implementation exact provider evidence仍须在push后核验。
