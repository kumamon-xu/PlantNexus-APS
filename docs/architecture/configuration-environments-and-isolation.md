---
doc_id: DOC-ARCH-008
title: 配置、环境与数据隔离
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [16, 38, 49, 62, 64, 95, 96]
last_reviewed: 2026-08-28
---

# 配置、环境与数据隔离

## TASK-P4-06 isolation boundary

Calculator、builder、precheck和machine fixture均为无网络、无数据库、无wall-clock/random读取的pure Simulation/development路径。Builder强制`data_plane=SIMULATION`、`synthetic=true`、`production_binding=false`且environment仅DEVELOPMENT/TEST/BENCHMARK；Production-shaped context、缺失provenance或cross-plane lineage在任何Solver/Version/persistence副作用前拒绝。CI新增证据步骤仍在FULL profile内且只上传JSON artifact。

本Task没有创建Production config、secret、route、worker、database binding或external adapter；fixture的300秒shift与KPI值只是确定性测试向量，不是Production default、容量阈值或SLA。

## CI validation profile isolation

CI Profile只由不可变event base..head的Git路径决定，不读取业务environment、Secret、数据库、data plane或用户输入。只有`README.md`、`docs/README.md`及公开技术文档目录中的Markdown-only diff可选择DOCS_ONLY；workflow、脚本、test、lock、配置、内部过程路径、混合/空/未知diff全部选择FULL。分类器和changed-doc validator仅使用Python标准库与Git，workflow权限继续为`contents: read`。

最终required context仍为`validate`：classifier成功且恰当分支成功、另一分支skipped时才PASS。DOCS_ONLY不连接Production/Simulation runtime，也不证明业务正确性、部署隔离、容量或SLA；FULL继续执行既有完整repository Gate。

Provider使用支持Node.js 24的官方Action运行分类、Python/Node setup与artifact上传；Action版本变化本身属于workflow diff并强制走FULL，不能由DOCS_ONLY自我验证。

## TASK-P4-05 isolation boundary

Freeze policy不是环境变量、UI fallback或wall-clock配置；本Task只接受`SIMULATION`且`synthetic=true`的新Snapshot与base Version，environment限定DEVELOPMENT/TEST/BENCHMARK。Production-shaped policy/base或cross-plane lineage均在投影前拒绝，900秒只能引用SIM-ASSUMPTION-017，不得进入Production配置、部署值或SLA。

## TASK-P4-04 isolation boundary

Service与四个repository实例固定为Simulation data plane；event本身还须`data_plane=SIMULATION`、`synthetic=true`、`production_binding=false`并携带完整synthetic provenance。Urgent staging同样必须为Simulation。测试数据库和SQLite原子性证据只属于development；未配置Production database/event source/credential/tenant promotion，未形成PostgreSQL并发、HA、backup或capacity结论。


## TASK-P4-03 isolation boundary

新表和repository当前只接受`data_plane=SIMULATION`且P4 carrier继续要求`production_binding=false`；所有主键、唯一约束、查询和FK均包含plane。PRODUCTION repository实例只能得到空的plane-scoped read，并对write/default/cross-plane reference fail closed；本地SQLite证明逻辑隔离与rollback，不代表独立Production database、HA或容量。

## TASK-P4-02 isolation boundary

九份P4 sample只允许Simulation/development-test语义并显式`production_binding=false`；Production-shaped mutation在Schema或pure precheck层拒绝。没有新增environment variable、database、secret、container、queue或network endpoint；Production authority/external integration/deployment仍default-deny。

## TASK-P4-01 isolation contract

ADR-0013/0015确认P4 Simulator/test authority只能在Development/Test/Benchmark的SIMULATION plane创建synthetic事件与virtual clock，必须经过与未来Production相同的versioned event/application入口，并把factory/planning scope、authority stream、run、source position和provenance纳入identity/guard。Checkpoint/restart不能跨run/plane读取或删除历史。

Production在真实source binding、principal/scope、freeze policy和独立部署证据形成前于event ingress之前default-deny；不得通过environment默认、test principal或Production-shaped fixture开启。任何Secret、external endpoint、deployment、freeze/capacity/SLA值仍禁止。本Task不增加配置键、环境变量、database、service或runtime。

## TASK-P3-17 audit conclusion

Production pre-provider/application default-deny、TEST/Simulation E2E mock boundary、plane-scoped persistence、无browser credential storage及locale preference非敏感隔离均独立PASS。P3 READY不关闭OPEN、不建立Production identity、external side effect或部署环境。

## TASK-P3-16 locale preference isolation

浏览器只以versioned key `plantnexus.locale.v1`保存`zh-CN`或`en-US`展示偏好；不保存token、credential、actor、reason、payload、authority或业务数据，也不把locale加入API/header/canonical fingerprint。无值或无效值均安全回退`zh-CN`，普通Production-shaped runtime与Simulation隔离规则不变。该local preference不是server config、business timezone、identity或Production deployment配置；隔离/refresh证据已由implementation artifact `9629193057`精确复验。

## TASK-P3-14 isolated replay environment

Backend Gate每次在fresh isolated temporary database/context运行并固定version/seed/hash；Frontend Gate用`PLANTNEXUS_P3_GATE_REPLAY_INDEX=1/2`把JSON/JUnit/HTML与failure media分开到两个目录。Node/npm必须为`24.19.0`/`11.17.0`，普通runtime、Production path与secret配置不变；任何环境或语义串扰均fail closed。

## TASK-P3-13 isolated E2E runtime

`.env.e2e`只在Vite `--mode e2e`、`env.DEV=true`且显式`VITE_PLANTNEXUS_E2E_SIMULATION=true`时选择`SIMULATION`/`TEST`/synthetic runtime，并绑定`SIM-P3-HUMAN-CONTROL-001@1.0.0`。文件不含token/secret/password/key；普通build与Production-shaped默认仍为`PRODUCTION`、`synthetic=false`并隐藏controls。Mock transport只存在Playwright page interception，不创建service、database或connected environment。

Local package store只接受server配置的existing root和内容派生Job/attempt identity，拒绝symlink/path escape；没有object storage、external URL或MES target。CI browser/install/artifact仍属required validation环境，不构成Production browser matrix、hosting、secrets或isolation approval。

## 配置层

| 层 | 示例 | 是否可覆盖业务规则 |
|---|---|---|
| System Config | 服务地址、队列、日志、数据库 | 否 |
| Simulation Config | Profile、seed、故障概率 | 只在 Simulation |
| Business Policy | 优先级、锁定、目标语义 | 由业务权威确认 |
| Solver Limits | 时间、线程、内存预算 | 不能改变约束语义 |

Simulation Config 永远不能覆盖 Production Business Policy。

## 环境

- Development：允许开发工具和显式 synthetic run。
- Test：允许确定性 Fixture、Contract、Property 和 Mutation tests。
- Benchmark：允许版本化 Profile 和专用性能采集。
- Production：Simulation API 默认 disabled；仅接受生产授权来源。

## 数据隔离

Production 和 Simulation 至少独立 Database，推荐 `aps_dev`、`aps_sim`、`aps_prod`。Snapshot 必须带 `synthetic` 标识，跨环境导入和发布需显式拒绝 synthetic 数据。

## 时间与 Secret

数据库时间为 UTC `TIMESTAMPTZ`，显示使用 factory timezone。生产 timezone 未确认时阻止生产操作而非阻止开发启动。Secret 只能通过环境/Secret Manager 注入，禁止进入文档示例的真实值、仓库、日志或导出。

## P0 Simulation isolation contract

FactoryProfile/ScenarioSpec Schema 强制 `synthetic_only=true`，ScenarioManifest 强制 `synthetic=true` 且 `target_environment` 只接受 `development/test/benchmark`。pure `GenerationContext.create` 对字符串 `production` 显式返回 `SYNTHETIC_REFERENCE_IN_PRODUCTION`；Generator 输出的 Standard Import envelope 同样必须 `synthetic=true` 并携带 `scenario_id`。

这些 Schema/pure precheck 证据不是发布/导出 guard 或 Production deployment 证据。

## TASK-P0-08 executable configuration boundary

`Settings` 只读取显式构造参数与 `PLANTNEXUS_*` environment；应用不会隐式读取 `.env`，`.env.example` 只供 Compose/local copy 且含非生产 placeholder。配置层包含 runtime environment、data plane、endpoint Secret、日志/trace context、health timeout 与 job heartbeat/lease；不包含 Business Policy、Solver Limits 或 synthetic Profile 数值。

Production fail-closed rules：runtime=`production` 必须同时 data plane=`production`、Database 必须是 PostgreSQL、Simulation API 必须 false、code commit 必须为 40 字符 SHA；production/runtime mismatch、lease≤heartbeat 或不受支持 URL/level 均在建立 client 前拒绝。Secret 使用 `SecretStr` 且不出现在 `safe_summary`、health 或 machine report。

本地 Compose 明确固定 development data plane，并提供 PostgreSQL/Redis 独立服务；它没有创建/验证 aps_sim 与 aps_prod、权限、backup 或 Production deployment，不能据此声称已满足生产隔离。P0-08 health-only app 没有 Simulation route，因此 Production Simulation API 是“未注册 + fail-closed config”边界；P1+ 的共同 ingress、publish/export synthetic guard 和真实独立 Database evidence 仍 `PLANNED`，RISK-007 继续 `MONITORED`。

## TASK-P0-10 GitHub CI boundary

workflow handoff 只更换当前 Task 的 diff/report 引用和 evidence artifact 名称，不改变 runtime environment、data plane、Database/Redis endpoint 或 Simulation/Production guard。GitHub Actions 仍仅有 `contents: read`；CI 中的 PostgreSQL password 是明确标记的 contract-only 非生产值，本 Task 不新增 repository Secret。

Actions run/artifact 允许通过公开 GitHub REST 读取；branch-protection 查询/设置如需认证，只能使用进程外短期 credential 或已认证 GitHub session，不得写入命令记录、文档、日志、artifact 或 repository。这是 CI 治理边界，不是 Production deployment/Secret Manager evidence。

## TASK-P1-01 phase-aware CI boundary

workflow新增 `PLANTNEXUS_CI_CHANGE_BASE`，PR取 base SHA、main push取 event `before` SHA；该值是 Git commit provenance，不是 Secret、runtime environment、data plane或业务配置。它只用于发现唯一 current-phase Task Card，真正 scope仍由 Task Card内的 immutable `Diff base`决定。

CI report/artifact改为 `ci-*.json`、`ci-current-task-report.json`与 `plantnexus-ci-evidence-<run-id>`中性命名，不改变 environment/Database/Redis/Simulation/Production guard。workflow继续 `contents: read`，没有新增 Secret、权限、deployment或 Production connectivity；本地合同 PASS不构成 provider run evidence。

## TASK-P1-03 Raw Staging isolation slice

每个SQLAlchemy staging repository实例在构造时固定为`production`或`simulation`，所有write/read predicate都携带该plane；batch contract与数据库CHECK同时要求Production无synthetic provenance、Simulation完整携带Scenario/Profile/Generator/seed。复合batch/row identity及idempotency unique scope包含data plane，因此相同业务ID不能通过另一plane repository读取或被另一plane replay覆盖。

integration test可在同一临时SQLite中同时创建两种repository以证明应用/表级guard，但这只是negative isolation evidence，不满足ADR-0009要求的独立Production/Simulation Database、roles、network policy、backup或monitoring。真实部署仍必须为不同data plane注入不同database endpoint；本Task没有修改`Settings`、Compose、Secret或Production connectivity。

## TASK-P1-04 Reference file configuration boundary

ReferenceFileAdapter不新增environment variable、`.env`、Compose service、endpoint或Business Policy。调用方必须显式传入source root与`SourceFileManifest`，manifest继续使用TASK-P1-03的data plane/synthetic conditional；`production_binding=false`不能被config覆盖。4 MiB/10000 rows等limit是versioned reference security capability，不是Factory/Simulation/Production业务参数或容量承诺。

P1-04只更新既有engineering machine contract中的exact runtime dependency集合以包含openpyxl/defusedxml，并保留OR-Tools forbidden断言；`Settings`、Production fail-closed、Database/Redis/Secret/Simulation API行为完全不变。独立Production/Simulation数据库和Production file-root/permission部署仍未形成。

## TASK-P1-07 CI property-suite boundary

本Task只把`backend/tests/property`加入phase-neutral GitHub repository suite，并由integration contract要求该路径持续存在；没有修改Settings、environment/data-plane、Secret、Compose、Database/Redis connectivity、Simulation API或Production configuration。Hypothesis为dev-only lock，runtime/container的`uv sync --no-dev`不会安装它。

CI重放生成测试只证明synthetic expansion correctness与治理交接，不建立独立Production/Simulation数据库、Production deployment、runtime capacity或外部source authority。Immutable implementation commit `5a3dbc14c12a107abf4052cca935e3ef59009d3d`的provider run `32265257468`已成功重放该边界；这不扩大其Production含义。

## TASK-P1-08 Snapshot isolation slice

每个`SqlAlchemySnapshotRepository`在构造时永久绑定`production`或`simulation`；write先核验Snapshot canonical bytes/hash/ID及synthetic marker，read predicate始终携带data plane。Synthetic Snapshot必须保留完整Scenario/Profile/Generator/version/seed，Production Snapshot不得携带该provenance；跨plane put明确`DATA_PLANE_MISMATCH`，另一plane按ID/hash读取返回不存在。

Migration在同一internal table记录data plane并以CHECK约束取值，应用与数据库trigger共同禁止update/delete。临时SQLite在同库双repository的测试只证明代码/表级negative guard；它不满足ADR-0009要求的独立Production/Simulation Database、role/network/backup/monitoring，也不修改Settings、Compose、Secret或Production endpoint。RISK-007继续`MONITORED`。

## TASK-P1-10 generator isolation slice

Generator context只接受Development/Test/Benchmark，`production`在生成任何row前明确拒绝；生成的StagedImportBatch固定Simulation plane并携带完整Scenario/Profile/Generator/seed provenance。Task没有新增environment variable、Secret、Settings、Compose service、Database endpoint、API或Production binding；unit registry由调用方显式注入，不能从环境选择`latest`。

本地同进程调用证明synthetic provenance/target negative guard与no-Planning import，不证明独立Simulation数据库、Production network/role/backup或common-ingress deployment。ADR-0009和RISK-007继续生效。

## TASK-P1-11 application/CI configuration review

Common ingress所需unit registry、data plane、cutoff、horizon、tick与Problem builder version全部由调用方显式传入，不从environment选择`latest`或猜默认。Gate CLI的`2026-11-06T12:30:00Z`到`2026-11-07T12:30:00Z`/60秒只绑定`SIM-P1-INGRESS-001@1.0.0`测试回放，不是Production policy。

CI只新增一条repository-local machine command并复用现有`PLANTNEXUS_CODE_COMMIT`；没有新Secret、service、port、database URL或environment variable。该运行不证明独立Production/Simulation deployment。

## TASK-P2-01 isolation review

Problem v2本身不增加environment、database、API route或persistence；Snapshot的`synthetic`/plane隔离继续由上游identity与调用边界负责。synthetic priority fact必须携带versioned source reference，样例使用`plantnexus-synthetic-policy@1.0.0`，不得复制为Production default。

Machine report只读取仓库Schema/sample并重放deterministic builders，写入ignored `build/validation`或CI artifact；它不连接Production数据库或外部系统。P2-01输出不能跨plane复用为正式Schedule，后继Task仍须在report/export manifest中保留synthetic与data-plane provenance。

## TASK-P2-02 policy/limits isolation review

PlanningPolicy/SolveLimits要求调用方显式提供`SIMULATION`或`PRODUCTION`及source/version，不从environment、数据库或代码推断latest/default。仓库样例只使用SIMULATION source；30秒、1 worker、seed `20260820`均是合同回放值，不是Production配置。Solution/Report必须以fingerprint保留相同Policy/Limits，防止跨plane或隐式参数漂移。

新增CLI只读仓库并写ignored machine report；workflow没有新增Secret、service、port、database、environment variable或Production route。P2-02不形成独立Production/Simulation deployment，也不允许将sample或provider CI当成Production authority。

## TASK-P2-03 solver isolation review

OR-Tools是进程内runtime dependency，但没有新增environment variable、Secret、network、service、port、database、container或Worker registration。`CpSatBackend`只消费显式Problem/Policy/Limits对象；sample的30秒/1 worker/seed不读取环境且不是Production default。CP-SAT engineering smoke仅在local/CI进程执行，报告不含model对象并保持JSON serialization边界。

Production/Simulation data-plane隔离、独立数据库与solver worker deployment仍未形成。Provider Linux runner只证明repository CI环境的locked replay，不能当成Production环境或容量认证。

## TASK-P2-04 validator isolation review

正式Validator只消费调用方显式提供的Problem v2与PlanningSolution JSON；不读取environment、数据库、API、Worker、Backend或OR-Tools，也不以candidate声明的solver status决定PASS。Simulation/Production plane及Policy/Limits provenance继续由输入合同保存，Validator只重算显式schedule facts。

CI新增的formal validator command只读仓库合同与固定hash、在进程内构造synthetic correctness vector并写ignored machine report；没有新增Secret、environment variable、service、port、container、migration或Production route。Provider replay仅证明repository correctness，不是Production deployment、容量或SLA证据。

## TASK-P2-05 core Solver isolation

Core Backend只消费调用方显式传入的Problem v2、PlanningPolicy v1与SolveLimits v1；唯一运行参数来自已验证的Limits映射，不读取额外environment、数据库、API、Worker或Production配置。含precedence/transport、calendar、非空release/material gate、RUNNING或lock事实的输入在CP-SAT model创建前以稳定`MODEL_INVALID`边界拒绝，避免把尚未实现的P2-06/07语义静默降级。

CI新增`app.planning.backends.cp_sat.core_model_check`，只构造内存tiny correctness vectors并写ignored JSON。它不新增Secret、service、port、container或deployment route；candidate均为不可发布测试artifact，P2-05证据不能外推Production容量或SLA。

## TASK-P2-06 temporal Solver isolation

Backend仍只消费显式Problem v2、PlanningPolicy v1与SolveLimits v1；precedence、calendar、release/material gate和transport均来自Problem，不读取environment、Secret、DB、API、Worker或Production配置。P2-05对这些事实的拒绝是历史边界；当前build只对sub-second/overflow、RUNNING和lock保持fail closed，后两者继续归P2-07。

`temporal_model_check`仅在进程内构造versioned synthetic vectors并写ignored JSON；没有新service、port、container、migration或deployment route。其model delta与timing只证明correctness可观察性，不构成Production容量、SLA或发布权限。

## TASK-P2-07 execution fact and lock isolation

Backend继续只消费显式Problem v2、PlanningPolicy v1与SolveLimits v1，不读取environment、Secret、DB、API、Worker或Production配置。RUNNING actual/resource/remainder和operation locks均来自Problem hash绑定的权威输入；HARD lock必须exact grid表示，SOFT lock只保留metadata reference，不读取freeze window或稳定性默认值。

`fact_lock_model_check`只构造in-memory synthetic correctness vectors并写ignored JSON；workflow未新增service、port、container、migration或deployment route。Fact/lock model delta、timing与memory只证明repository correctness，不构成Production authority、容量、SLA或发布权限。

## TASK-P2-08 explicit Simulation execution

`GlobalCpSatStrategy`只接受代码内固定版本的`POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`、显式传入且同为`SIMULATION`的SolveLimits，以及Problem中`plantnexus-synthetic-policy@1.0.0`来源的priority weight；不读取environment、Secret、DB、API、Worker或隐式默认值。`planning_run_id`与`code_commit`也是显式调用参数，local允许`uncommitted`，CI由`PLANTNEXUS_CODE_COMMIT`只注入machine evidence。

Workflow只新增in-memory `objective_strategy_check`与ignored JSON上传，不新增service、port、container、migration或deployment route。OPEN-006/011/012未关闭时Production Policy/weight/limit均在solve前拒绝；tiny timing/memory不是容量、SLA或Production readiness。

## TASK-P2-09 correctness isolation

七个`1.0.0`资产均由`synthetic_only=true`的ScenarioSpec、Simulation-only Profile和`StagingDataPlane.SIMULATION`固定；fixture-local assembler只产生source-shaped Raw rows，再进入公开Normalization/Data Validation链。它不读取环境变量、Secret、DB、API、Worker或Production connector，也不改变既有Production guard。CI仅新增本地文件读取与ignored JSON report，GitHub权限仍为`contents: read`。

`XS`仅表示可手算correctness，不能解释为`benchmarks/profiles.yaml`的性能级别。OPEN-006/011/012及独立Production/Simulation Database/API边界均未关闭，P2-10+不在本Task内。

## TASK-P2-10 Reference isolation

`simulation.baselines`只接受调用方显式PlanningProblem v2与algorithm ID；它不读取environment、Secret、DB、Redis、API、Worker、Planning policy default或Production connector。`reference-scheduler-policy.v1`及SIM-ASSUMPTION-012只固定Simulation tie-break，所有结果显式`non_production=true`且禁止作为Global Strategy fallback。

Workflow只新增in-process reference evidence命令并写ignored JSON；未新增service、port、container、migration、credential或deployment route。Evidence provider为Problem取得而重放既有P2-09 synthetic pipeline，但scheduler不消费其Solver result。OPEN-006/011/012、独立data-plane infrastructure与Production runtime threshold均未关闭。

## TASK-P2-11 isolation review

Internal package builder只接受`synthetic=true`且携带P2 correctness provenance的Snapshot；Production或缺失Scenario manifest会fail closed。它不读取环境变量、网络、数据库、queue或external storage。可选目录写入只面向调用方提供的本地路径，并在同一父目录临时构建后原子rename；该能力不注册Production route或publish target。

Manifest固定`publishable=false`及所有P3状态未启动，synthetic package不得进入Production publish plane。没有新增配置项、service或secret；现有environment/data-plane隔离规则保持不变。

## TASK-P2-12 benchmark environment review

Benchmark profile来自versioned YAML而非环境默认；CLI只接受`xs|s|m`并经synthetic-only Profile/Scenario与Simulation Raw Staging进入正式pipeline。报告采集OS/release/machine/processor、Python、logical CPU、OR-Tools、timer、local/GitHub provider及其SHA-256 environment signature，不采集hostname、username、secret、数据库或网络地址。

CI只通过非秘密变量选择XS并写ignored artifact，不新增service/port/container/migration/credential或Production route。跨环境baseline明确跳过相对性能判定；L/XL和Production capacity/SLA禁止。独立Production/Simulation DB仍未由本Task实现。

## TASK-P2-13 Gate environment review

Gate CLI只有`--root`、`--repeat >= 2`和`--report`三个显式参数；所有profile/policy/limits继续从版本化仓库合同读取，没有环境默认。`PLANTNEXUS_CODE_COMMIT`只接受`uncommitted`或40位小写SHA并传递到全部子报告；CI由`${{ github.sha }}`提供。报告复用Benchmark的去hostname/username/secret环境签名，不读取credential、DB、Redis、API、Worker或网络配置。

Required workflow在既有XS step后真实执行两次七类correctness、XS/S/M和output contract，并把单一Gate JSON纳入现有artifact glob。Local与provider运行都保持Simulation-only；相对baseline仍按各Benchmark报告环境规则判定，Gate不会把GitHub runner或本机值转成Production部署规格。

Required run `32465737712`已在GitHub Linux runner精确执行该Gate并上传artifact `9440650646`；Gate及全部sub-report绑定同一SHA，未泄漏secret或建立Production配置。跨环境执行结果仍仅属development evidence。

## P3 environment planning

P3 development/Simulation只能使用显式data plane和test actor；Production channel保持default-deny并不得配置真实publish target或Simulation API。P3-03 persistence、P3-08 publish、P3-09 ExportJob、P3-10 API与P3-11 frontend分别必须证明环境/secret/target隔离；本次不修改配置、infra、数据库或deployment。

TASK-P3-01合同固定授权上下文必须同时包含environment、data plane、resource scope和target。Simulation test policy只能在Development/Test/Benchmark环境、`SIMULATION` plane、synthetic resource及`SIMULATION_INTERNAL` target生效，并明确`production_binding=false`；Production缺少真实mapping/target时所有write/decision/publish/export默认拒绝，Production导航不得暴露Simulation labs。

本Task没有新增env var、Secret、service、database、storage、network、frontend build或deployment配置。identity provider、external target、retention/SIEM和Production publish channel继续未形成。
## TASK-P3-02 contract isolation review

新carrier必须逐文档显式`data_plane`与`environment`：SIMULATION只允许Development/Test/Benchmark，synthetic=true时必须携带完整Scenario/Profile/Generator/seed provenance；PRODUCTION必须Production environment且synthetic=false。PublicationResult/ExportJob v1只接受SIMULATION + `SIMULATION_INTERNAL`，不提供external/Production target或默认值。

CI新增的workspace contract CLI只读repository并写ignored JSON，不新增env var、Secret、service、port、DB/Redis连接或deployment权限。它不能把test actor/sample/provider升级为Production authority。

## TASK-P3-03 storage isolation

每个repository实例固定一个uppercase carrier `WorkspaceDataPlane`，所有PK/unique/read/CAS均包含plane；ScheduleVersion/Audit支持显式Simulation或Production carrier，PublicationResult/ExportJob v1在constructor与DB check层都只允许Simulation/internal target。Cross-plane read返回空，cross-plane write稳定拒绝；任何credential、DSN或SQL都不会进入carrier/error/report。

Migration包含PostgreSQL DDL和SQLite test兼容trigger，但本Task只在临时SQLite执行empty/populated round-trip；未修改env、Compose、Secret、service、network或deployment。独立Production/Simulation数据库、role/network isolation、backup/restore和Production migration Runbook仍未形成。

## TASK-P3-04 lifecycle isolation

Service实例固定一个`WorkspaceDataPlane`；context environment必须与plane兼容，synthetic P2 output只允许`SIMULATION` + Development/Test/Benchmark。Machine/integration tests验证同一engine上的Production repository看不到Simulation Version，synthetic→Production在持久化前拒绝；所有key只以SHA-256 reference扩散。

Workflow只新增离线/临时SQLite lifecycle machine命令并复用既有`PLANTNEXUS_CODE_COMMIT`与artifact glob；没有新env、Secret、权限、port、service、network、storage或deployment。SQLite concurrency/replay不证明独立Production DB、PostgreSQL capacity、backup或role isolation。

## TASK-P3-05 query isolation

每个query/comparison service实例固定单一data plane；request、base/compared Version及environment必须一致，repository本身仍plane-scoped。Machine负例验证Production carrier不能读取Simulation repository、mixed source fingerprint和stale cursor均拒绝；read前后两个Version/两个AuditEvent保持原row count。没有新configuration key、network、cache、database、credential或Production route。

## TASK-P3-06 command isolation

Command service实例固定`SIMULATION`或`PRODUCTION` repository plane；command/source/problem provenance、environment与synthetic标记必须一致。当前仅Simulation test policy可执行，Production在source lookup和idempotent replay前固定拒绝。Machine/tests只用临时SQLite验证transaction、replay/rollback与plane guard，不新增env key、Secret、port、service、database、network或deployment，也不能外推PostgreSQL concurrency/Production isolation。

## TASK-P3-07 decision isolation

Decision service实例同样固定单一repository plane。Simulation只允许Development/Test/Benchmark、synthetic provenance、名称显式含test/simulation且`production_binding=false`的server policy；resource scope必须精确包含Version。Production command只能形成`WORKSPACE_INTERNAL` sanitized DENIED audit，且在任何source或success replay lookup前拒绝；Simulation/Production audit和Schedule tables按既有plane key隔离。

本Task没有新增env var、Secret、credential、port、service、database、network或deployment。临时SQLite并发/CAS只证明bounded development behavior，不替代PostgreSQL、identity boundary、Production backup/restore或capacity验证。

## TASK-P3-08 publication isolation

Publication service实例固定单一plane；成功只允许Development/Test/Benchmark中的`SIMULATION`、synthetic provenance、explicit test/simulation policy、`production_binding=false`和`SIMULATION_INTERNAL`。Schedule/Audit/PublicationResult/current rows均由既有plane key隔离；mixed plane、unknown target或Production success carrier无法进入业务查询/事务。Production只形成`WORKSPACE_INTERNAL` sanitized denial audit。

没有新增env var、Secret、database、storage、network、publisher、service或deployment。临时SQLite transaction/concurrency是development evidence，不证明PostgreSQL distributed CAS、Production backup/channel或external exactly-once。

P3-09只使用显式`SIMULATION`与DEVELOPMENT/TEST/BENCHMARK、target=`SIMULATION_INTERNAL`；Production/auth binding在lookup前拒绝。Storage root由composition注入且必须为已存在目录，carrier/audit/manifest不保存absolute path。没有新增Secret/env var/network/storage service；临时filesystem/SQLite evidence不定义Production topology、retention或capacity。

## TASK-P3-10 API isolation

Planning Workspace route只在显式`PLANTNEXUS_SIMULATION_API_ENABLED=true`且data plane=`SIMULATION`时可使用test provider；Production无论Bearer或声明capability如何都在provider lookup/application调用前拒绝。本Task未新增env var、Secret、network、DB、container或deployment config，只消费已有typed setting。Simulation TestClient与test principal不得用于Production。

## TASK-P3-11 Frontend isolation

Production bundle只接受same-origin默认`/api/v1`或显式base URL，并把plane/environment固定为`PRODUCTION/PRODUCTION`、`synthetic=false`；请求不能从页面、query string或local storage切换plane。任何Simulation/Development env尝试在runtime loader中fail closed，synthetic carrier只存在于unit/component test fixture且没有navigation/seed入口。

Implementation `567e8693db881ea3dfffa011de9021fef9641361` / artifact `9552386549`已复验runtime isolation、default no-token/no storage与Production non-synthetic boundary；真实identity、gateway、hosting和Production deployment仍未形成。

Session provider默认无token，client使用`credentials=omit`、`cache=no-store`且不读写local/session storage或cookie。真实OIDC/session、CORS/CSRF、gateway base URL和Production deployment仍由OPEN-010/015及后续授权决定。

## TASK-P3-12 browser isolation

Gantt/load/comparison沿用P3-11 Production-only runtime与default no-token session，不新增env var、Secret、base URL switch、Simulation navigation、service、database、container或deployment。Playwright只在ephemeral Vite/Chromium进程中拦截same-origin request；`VERSIONED_SYNTHETIC_UI_120@1.0.0`使用Production-shaped mock carrier是为了验证Frontend runtime contract，不表示真实Production数据、authority或connected environment。

Comparison POST仍使用`credentials=omit`/`cache=no-store`、Bearer只来自内存provider且没有Idempotency-Key；authorization denied保持显式页面状态。Artifact `9555196470`精确复验4/4 browser与no-command/no-Production flags。Browser install、screenshots/traces/video和bundle均为development CI artifact，不进入Production image或data plane；OPEN-010/015、真实identity/gateway/hosting与Production isolation证据未形成。
