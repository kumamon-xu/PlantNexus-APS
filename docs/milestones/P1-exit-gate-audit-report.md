---
doc_id: MILESTONE-P1-AUDIT-001
title: P1 Exit Gate Audit Report
status: baseline
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [74, 75, 98, 99, 100, 110, 111]
last_reviewed: 2026-08-20
---

# P1 Exit Gate Audit Report

## Decision

| Field | Audited value |
|---|---|
| Audit Task | TASK-P1-12 |
| Task lifecycle at decision | `in_progress`；只有本报告提交后的 exact GitHub provider run成功并回填时才改为`done` |
| Audit date | 2026-08-20 (Asia/Hong_Kong) |
| Audit execution time | 2026-08-20T10:42:46～10:58:36+08:00 |
| Diff base | `8830a6dc566df8093b601a82c87c74a9cfd97b59` |
| Audited repository head | `8830a6dc566df8093b601a82c87c74a9cfd97b59`；审计文档尚未提交，业务代码/Schema/test均未改 |
| Schema set | `2.2.0`；Import/Snapshot v2 document仍为`2.0.0`，unit registry v1为`2.1.0` |
| Provider baseline | GitHub Actions / `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml` |
| Latest audited successful run | [`32322871271`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32322871271), exact head `8830a6dc566df8093b601a82c87c74a9cfd97b59`, attempt 1, push, `success` |
| Required job | [`validate`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32322871271/job/96288301743), 20/20 steps successful or intentionally skipped |
| Uploaded evidence | `plantnexus-ci-evidence-32322871271`, artifact ID `9390358424`, size 9154 bytes, digest `sha256:740b5f0a5e8d4fb0d7df2585422b3be7a74079a4ba531db8b8fb45edfe89ea24`, not expired |
| Branch protection | `main.protected=true`；required check `validate` / GitHub Actions app ID `15368`；force-push/deletion disabled |
| Auditor | Codex execution agent |
| Attestation | 本地命令、Git提交拓扑、下载后的CI JSON和GitHub API事实分别核验；这是透明的非密码学审计声明，credential未写入仓库或artifact |
| Overall P1 Exit Gate | `READY` |
| Blocking gaps | none |
| Recommendation | 请求用户另行批准 P1→P2；本审计不更新 current phase、不创建P2 Task、不执行Solver |

机器可读结论见
[`P1-exit-gate-evidence-manifest.json`](P1-exit-gate-evidence-manifest.json)。
`READY`只表示总规§74的P1 Data & Snapshot Gate已有可复验证据；它不表示
Production readiness、真实ERP/MES/WMS/CAM binding、独立生产数据库、Solver、
ScheduleValidator P2 integration、Benchmark或发布能力已经形成。

## Gate evidence

| Gate | Result | Evidence actually observed | Boundary |
|---|---|---|---|
| P1 Task lineage and scope | `PASS` | TASK-P1-01～11均为`done`；11组Diff base/implementation commit均存在、base先于implementation且implementation是当前HEAD祖先；下载的11份`traceability-report.v1`均绑定exact SHA、0 issues | audit不重写历史Task或失败证据 |
| Canonical contracts | `PASS` | schema set`2.2.0`；full contract suite在271项回归中通过；Import/Snapshot历史版本与显式版本边界保持 | Schema存在不等于Production authority |
| CSV/XLSX/reference ingress | `PASS` | TEST-IMPORT-ADAPTER-001回归通过；`ReferenceFileAdapter@1.0.0`安全CSV/XLSX读取并输出Raw Staging；P1 pipeline用temporary reference CSV形成parity | `production_binding=false`，不是客户接口或真实数据 |
| Raw Staging and provenance | `PASS` | TEST-IMPORT-STAGING-001、idempotency/transaction与`0002` upgrade/downgrade回归通过；source/version/content/row/location/plane provenance可重放 | 临时SQLite不冒充Production PostgreSQL隔离/并发 |
| Normalization and quality | `PASS` | explicit mapping/unit/time/ID producer与Data Validation回归通过；pipeline先得到PASS/0 quality再允许Expansion | 不提供默认单位、timezone、field authority或fallback |
| Order Expansion | `PASS` | `order-expansion.v1` fixed/generated tests通过；2 lots产生6 operation instances/4 edges，candidate duration/source与fact/lock lineage保留 | 不自动split/merge，不改变OPEN-008/014 |
| Immutable PlanningSnapshot | `PASS` | builder/hash/property/repository/migration tests通过；pipeline Snapshot bytes digest=`sha256:dec4302f3606ef450b5f6fd70373ddfd018100fc8fe8f67f8c60779f8ccaab55`，hash=`sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409` | common-ingress报告不代替TASK-P1-08 insert-only persistence evidence |
| Solver-neutral PlanningProblem | `PASS` | builder/hash/property tests通过；pipeline full bytes digest=`sha256:c3ff3f0cc810007da4dc251642896b0d8b6fab1f98d4d5bced743752904e9233`，problem hash=`sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da` | terminal artifact为Problem；没有candidate Schedule或feasibility结论 |
| Synthetic Generator | `PASS` | `synthetic-generator-report.v1` 7/7；16个非空collections、49 records；same input bytes/hash、seed change、version rejection与generated-at exclusion通过 | 单一correctness asset不是Benchmark/Production distribution |
| §74 common-ingress deterministic replay | `PASS` | P1-12 `p1-data-pipeline-report.v1` 14/14、issues=0；两次Synthetic与Reference输入的完整Import/Snapshot/Problem bytes/hash相同；Import hash=`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4` | 两入口都表达同一synthetic semantics；不声称真实Production connector |
| Four exact input rejections | `PASS` | route cycle→`data_validation/DATA_ERROR/ROUTE_CYCLE`；missing resource→`data_validation/DATA_ERROR/MISSING_RESOURCE`；unit error→`normalization/DATA_ERROR/UNIT_CONVERSION_ERROR`；missing duration→`normalization/DATA_ERROR/MISSING_DURATION`；11项聚焦tests通过 | 输入错误未映射成SYSTEM_ERROR/INFEASIBLE，失败后无下游artifact |
| P0 correctness regression | `PASS` | rule sheet: 11 active/7 deferred constraints、20 capabilities、19 errors、3 machines/27 states/42 transitions；Golden hash重放；13 mutation classes/11 C-ID/15 violations全部通过 | mutation evaluator仍为fixture-local P0证据，不冒充P2 production Validator |
| Isolation and phase boundary | `PASS` | Production target/data-plane guards与AST no-shortcut tests在271项回归中通过；代码/dependency扫描无OR-Tools import/dependency、CpModel或IntervalVar；无`docs/tasks/P2`且current phase仍P1 | 独立aps_prod/aps_sim数据库、network/role隔离仍未形成 |
| Migration, Compose and build | `PASS` | migration/rejection聚焦11项通过；`docker compose ... config --quiet` exit 0；`uv build`成功产生sdist+wheel | 本地build/Compose不是Production deployment |
| Documentation and traceability | `PASS` | full governance最终要求125份Markdown、30 roots、36 Test IDs、15 OPEN、10 assumptions、10 risks、22 Tasks全部一致；P1-12 diff gate匹配3行impact、0 issues | ignored build reports不进入文档清单 |
| External CI provider | `PASS` | P1-01～11的11个实现run及P1-11 closure run均exact SHA、push/attempt 1、`validate=success`、artifact未过期；下载内容的Task/head/result/path/row/issue facts与API一致 | P1-12自身提交后的run属于Task关闭证据，将在evidence-only revision回填 |
| PROD_OPEN / Simulation truthfulness | `PASS` | OPEN-001～015均保持`OPEN`；SIM-ASSUMPTION-001～010均保持`ACTIVE`且只绑定versioned synthetic assets；RISK-001～010均保持`MONITORED` | P1 READY不关闭任何生产未知项或风险 |

## Local acceptance record

| Command | Exit | Observed result |
|---|---:|---|
| `uv sync --locked` | 0 | 63 packages resolved/checked from lock |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run pyright backend/app backend/tests` | 0 | 0 errors, 0 warnings, 0 informations |
| full registered pytest directories | 0 | 271 passed in 7.86s |
| migrations + four exit rejections pytest | 0 | 11 passed in 2.00s |
| P1 gate CLI, repeat 2 | 0 | 14/14 checks PASS, 0 issues |
| Rule Sheet CLI | 0 | PASS, counts 11/7/20/19/3/27/42 |
| Synthetic Generator CLI | 0 | 7/7 PASS, 16 collections/49 records |
| Golden Fixture CLI | 0 | PASS, 8 artifacts/15 records/11 expectations |
| Validator Mutation CLI | 0 | PASS, 13 cases/11 constraints/13 classes/15 violations |
| Engineering CLI | 0 | 6/6 PASS；P0 frozen scope sentinel未被误解为当前pipeline缺失 |
| `docker compose --env-file .env.example config --quiet` | 0 | configuration valid |
| full docs governance | 0 | PASS；最终值见上方documentation Gate |
| P1-12 diff docs governance | 0 | PASS；最终report记录actual paths/3 impact rows/0 issues |
| `git diff --check` | 0 | no whitespace errors |
| `uv build` | 0 | sdist and wheel built successfully |
| GitHub API/run/artifact/branch queries | 0 | exact provider and protection facts verified |

## P1 implementation provider chain

| Task | Exact implementation head | Run / job / artifact | Provider digest | Trace report |
|---|---|---|---|---|
| P1-01 | `2d2a4432aa42e4f38ee8ae736e2acf2df1c694b9` | `32237649319` / `96021094432` / `9359554539` | `sha256:bdd08f01ea23e8fe93f82c199274afc0aa5e9343ea7fa70adfb6df6a950d1216` | 31 paths / 6 rows / 0 issues |
| P1-02 | `64c40b5c21ab0be8955e55edc007e04337cac417` | `32241366290` / `96032439734` / `9360906246` | `sha256:90484bc64d02458f2fced9d8e7691fa8251149884e6d9f272407b7e50fa83fc3` | 50 / 8 / 0 |
| P1-03 | `25897393e31dcc0648943ec7e2e7f43dbb0e70e1` | `32243895717` / `96040166509` / `9361846475` | `sha256:75aa68daf5bd4308a4f9143c0ae72746f540d103d6a937d472d6a7d5c3c5160b` | 36 / 6 / 0 |
| P1-04 | `9391ec021afa9e6f4f881b1538b276c84584df0e` | `32247079996` / `96049843226` / `9362999088` | `sha256:b9ada0b25d12962f5efea51e058cd82778495f4389a240e32aa64c04143b5d4b` | 42 / 8 / 0 |
| P1-05 | `d52aa62d36e8d89eba318cb5fc586311680e030f` | `32252308695` / `96065907901` / `9364897397` | `sha256:5db1ccbb242b555d8a95d36ac9cc1b1373dab95d482dbde17ab7fb369cce2966` | 49 / 8 / 0 |
| P1-06 | `c1ac1077fdd92e012f4050f30bab2aec4638f6ec` | `32257767495` / `96083426251` / `9366988617` | `sha256:a2e38cf942e672a073f5044b936dd2b7b7450204f5d353251566ed8b7352ca98` | 63 / 9 / 0 |
| P1-07 | `5a3dbc14c12a107abf4052cca935e3ef59009d3d` | `32265257468` / `96108055149` / `9369917400` | `sha256:8aeb7416516f7932436bbf406d800cdbdeb8313ba9249f2709b7df71647e566e` | 45 / 9 / 0 |
| P1-08 | `72670d18a29c9a10cb70f7a263c981a2b660e0ee` | `32310098594` / `96251145353` / `9386127863` | `sha256:69d68183bad614631df07234a3ca88508379ab89ec715f811ee7f529d6f17e0c` | 41 / 6 / 0 |
| P1-09 | `e8c59547857d2eeace1c9f8b453a5a294cca5ef7` | `32315513504` / `96266776018` / `9387907707` | `sha256:1ede296252bb04e9015240e13222eaf4ee783bc6e7582012cac0a441fd624568` | 30 / 5 / 0 |
| P1-10 | `5ac08183dd03049ad02c77e6cba80c4621847e0f` | `32319530217` / `96278754755` / `9389283489` | `sha256:2b04b7bd134810c7d37d6130a2ba84911b6f672fb8a95ef83c761496370b73cf` | 52 / 7 / 0 |
| P1-11 | `fa6c4c1159972a30ea683ad4e6eba98342d3c344` | `32322511227` / `96287321281` / `9390250284` | `sha256:77e0389e2902021c419e8ec2fcf99d88c02c19d96a69304791693b822498bd6e` | 43 / 7 / 0 |

P1-11的evidence-only closure `8830a6dc566df8093b601a82c87c74a9cfd97b59`
由run `32322871271`再次得到14/14 pipeline、43 paths/7 rows/0 issues和
artifact `9390358424`，因此P1-12审计开始时的远端基线不是未验证提交。

## Local machine artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| `TASK-P1-12-p1-pipeline.json` | 9348 | `0b57578eca2e624becfa64cb6206677f2b9c1d03ea49249457660a70fea67f67` |
| `TASK-P1-12-rule-contracts.json` | 552 | `f7d8fb1f963a26cbcf6b2b368567ea5ecc1dda6c6f35f93d5d5a32c5427e7b72` |
| `TASK-P1-12-simulation-contracts.json` | 1867 | `53498e176e14dadae0c8cd2734c3eb4312311129e00470979a2f85230f312d0d` |
| `TASK-P1-12-golden.json` | 1085 | `ab69e90ba23e77c0b648283a903097f24422cfa24b35f8b05b844dd82d550534` |
| `TASK-P1-12-validator-mutations.json` | 5236 | `dbcfb4225f76cc1a8efc1ed2d2b4ed6f42070c1539ab930a47c02e0b114c4a2f` |
| `TASK-P1-12-engineering.json` | 3805 | `7e06e5abc8b5677a531601d5f8236962492d55b4e370cd9754c3f983a924a31f` |

这些报告位于ignored `build/validation`，不会伪装成已提交产品artifact；同一CLI由
GitHub workflow在P1-11基线上重放。P1-12提交后的CI artifact将构成审计Task自己的
provider closure。

## Gaps, boundaries and recommendation

`blocking_gaps=[]`。没有发现需要在audit内修复的P1实现、Schema、test、migration、
workflow或文档治理缺口。

以下事项明确不被本结论关闭：OPEN-001～015、RISK-001～010、真实source binding、
独立Production/Simulation数据库与角色、malware/auth review、PlanningRun/Export
manifest、Solver/Strategy/Solution、P2 ScheduleValidator integration、Benchmark/OPEN-012
阈值、审批发布、Replan和Production deployment。

因此建议的唯一下一动作是：在TASK-P1-12自身provider closure完成后，向用户报告
P1 Gate=`READY`并等待明确的P1→P2授权。未经该授权，`docs/current_phase.md`继续为P1，
P1 Milestone继续`active`（Gate ready / awaiting decision），不得创建或执行P2 Task。
