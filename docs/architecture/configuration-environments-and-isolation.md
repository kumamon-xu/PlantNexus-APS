---
doc_id: DOC-ARCH-008
title: 配置、环境与数据隔离
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [16, 38, 49, 62, 64, 95, 96]
last_reviewed: 2026-09-04
---

# 配置、环境与数据隔离

## TASK-P8-03 canonical-ingress persistence isolation

P8-03应用服务只接受调用方显式注入的`TrustedCanonicalIngressContext`、server-owned build plan与repository port；Production-shaped请求还必须显式声明production binding。它不从payload、环境变量、artifact path或Extension选择字段推导Runtime/Extension-set，也不连接第三方系统、网络、queue、Solver、Worker或Frontend。宿主仍须在APS边界外完成采集与映射，只提交schema set `2.10.0`的canonical JSON。

持久化以`tenant_id + factory_id + planning_scope_id + environment + data_plane`形成有效业务scope，并把repository实例永久绑定到单一data plane；同一数据库事务内完成idempotency claim、immutable Snapshot、PlanningProblem和sanitized audit写入。相同scope、key reference与request fingerprint只返回原结果，不产生第二份对象；不同内容冲突、跨平面查询、原始幂等键泄露、校验失败或任一写入异常均fail closed并整体回滚。新增revision `0006_canonical_ingress_application`只追加P8-03表和append-only guard；降级会删除这三类P8-03入口/Problem/audit数据，既有Snapshot表保持不变，因此执行前必须按运行环境的retention和引用策略处置。

既有FULL job、required `validate`、权限、依赖与artifact通道不变。P4临时frozen replay的已有删除/恢复清单只追加P8-03的9个新模块/测试和3个包导出文件，确保P4重放仍看到其冻结checkout；CI contract逐路径要求恰好一次，preflight对遗漏继续fail closed。该隔离不跳过当前checkout中的P8-03 Backend测试，也不把新增migration隐藏于当前Alembic验证。

## TASK-P8-02 machine-contract evidence isolation

P8 contract checker是无网络、无数据库、无queue、无secret、无Runtime/Extension加载的pure offline检查；输入只来自tracked Schema、rule、synthetic sample、版本元数据及冻结的dependency projection。FULL validation在既有`full_validation` job中增加一个不可跳过的step，输出`build/validation/ci-p8-machine-contracts.json`并沿用既有`build/validation/*.json` artifact；不新增job、permission、环境变量、服务、cache、依赖或artifact通道。

该step不运行canonical ingress consumer，也不产生业务state。P4 frozen replay显式移除20个post-frozen P8 Schema/sample/test路径，并由preflight和workflow contract逐条验证恰好一次；旧replay code、expected与恢复base不变。Provider报告仅含版本、计数、指纹、稳定错误码和边界声明，不含真实payload、身份、第三方数据或Extension代码。

## TASK-P6-08 monitoring and evidence isolation

Monitor只加载tracked、content-addressed `SIM-P6-DURATION-MONITORING-001@1.0.0`并接收caller构造的单一Simulation/Test aggregate window；无environment default、credential、network、database、queue、cache、registry、filesystem telemetry store或Production namespace。Retention为当前report构造期间最多1个window且`persistence=NONE`，process结束后没有monitor-owned数据。

Privacy validator在metric计算前拒绝raw/private字段和operation/resource/source/row/user identifiers，Provider artifact只含policy/window fingerprints、counts、exact ratios、stable reasons和recommendation。任何invalid/mixed/late/tampered input均只产生sanitized `DEFAULT_DISABLE` evidence；实现不向runtime、Planning、state、model registry或外部系统发送动作。

FULL验证沿用既有P6-06 runtime reporter串接独立P6-08 aggregate report；没有workflow、job topology、permission、Secret、dependency/lock、artifact glob或P4 frozen-replay清单变化。Monitor代码有界加入既已从P4 replay移除的runtime路径，tests仅扩展既有已隔离路径，因此冻结owner与required `validate` context保持不变。

## TASK-P6-07 Planning-ingress and frozen-replay isolation

Planning adapter默认disabled，只接受caller显式提供的verified Snapshot、P6-06 in-process provider、UTC prediction time与exact FeatureRecord mapping；它不读取environment default、credential、network、database、queue、registry、cache或Production namespace，也不写任何业务state。Machine report只保留sanitized carrier/Problem fingerprints、aggregate counts与development observation，不包含raw dataset row、label或secret。

首次dependency-free preflight正确发现6个post-P4 Backend/test路径会污染P4-13 frozen replay。Workflow修订只在既有临时checkout `rm`清单精确追加这6条路径，并由`test_ci_contract.py`逐条要求恰好一次；没有新增P6-07 step，Task checker继续由Backend contract test执行。Job拓扑、permission、artifact、required `validate` context、FULL/DOCS_ONLY routing、dependency/lock、Secret及P4 owner全部不变。

## TASK-P6-06 runtime and evidence isolation

Runtime只接受content-addressed `SIM-P6-DURATION-RUNTIME-001@1.0.0`、`data_plane=SIMULATION`、`environment=TEST`、exact P6-04 artifact/manifest与P6-05 READY Gate。调用必须显式提供UTC prediction time和resource-option authority；不读取环境变量、host wall clock、credential、endpoint、database、queue、registry或Production namespace。Provider无network/external adapter、cache、全局启用或持久化side effect，unknown policy/authority default-deny。

Policy将FeatureRecord限制为16 KiB、4 features、1 source，prediction限制为32 KiB，pure fixed-model call以50 ms deadline post-check；256 measured/16 warmup、P95 20 ms与16 MiB peak只用于development machine evidence。FULL validation在既有P6 model/evaluation folded step后追加runtime reporter，并从临时P4 frozen replay移除7个post-frozen runtime/test路径；required context、job topology、permission、dependency/lock、Secret与DOCS_ONLY routing不变。Provider artifact只含sanitized runtime report，不含FeatureRecord、row、label或source-record ID。

## TASK-P6-05 evaluation and evidence isolation

Offline evaluator只接受冻结的`SIMULATION/TEST` profile、exact P6-03 dataset file、P6-04 model bundle和safe artifact；没有environment default、credential、database、network、queue、service、runtime provider或Planning side effect。Raw file SHA-256先验证，随后只对validation/test进行label语义访问；train label读取计数必须为0。Profile、threshold、timestamp与fallback precedence均来自versioned文件，不读取host clock或环境变量。

Tracked baseline和machine/Provider evidence只包含aggregate metric、slice count、exact fraction、identity、stable fallback reason和Gate decision；raw source、dataset rows、FeatureRecord或labels全部禁止。FULL main validation新增一项不可跳过的P6-05 aggregate reporter，并在临时P4 frozen replay中移除evaluation模块及三份post-frozen测试，避免新路径污染冻结owner；required `validate`、job依赖、permission、Secret、dependency/lock和部署不变。`READY_FOR_SIMULATION_RUNTIME`不改变Production隔离或启用任何runtime。

## TASK-P6-04 model artifact and CI isolation

Trainer/loader只接受`SIMULATION/TEST`、synthetic、`production_binding=false`且scope位于P6-03 manifest allow-list的输入；没有environment default、credential、database、queue、network、endpoint、service、registry或外部storage。Model/config/manifest/replay逐字声明Production与promotion未授权、planning authority=`NONE`，任何Production-shaped或cross-scope mutation在publish/estimate前拒绝。

Provider artifact只上传safe canonical model、manifest、sanitized replay/report，不上传P6-03 raw source、dataset bundle/rows或labels。FULL workflow追加一个non-skippable model checker，既有artifact glob与required `validate`不变；冻结P4-13 worktree仅显式移除本Task新增的model module与contract test后重放旧证据，不改变主树、P4 owner或隔离语义。

## TASK-P6-03 dataset and CI isolation

Dataset source/profile被逐字限制为`SIMULATION/TEST`、synthetic、local-test-only且Production binding/authorization为false；没有环境变量、credential、database、network、queue、service或外部storage。Raw source与完整row bundle只作为repository synthetic fixture，CI/provider artifact仅上传`p6-duration-dataset-report.v1`中的sanitized manifest、counts、fingerprints和rejection summary。PII flag、target-as-feature、敏感key或Production-shaped mutation在写文件前拒绝。

FULL workflow只追加一个不可跳过的dataset checker，并由既有`build/validation/*.json` glob收集report；触发器、权限、Secret、required `validate` context和部署均不变。冻结P4-13临时worktree只显式删除本Task新增的三个backend/test路径，再运行未修改P4 evidence；这不改变主树或P4 owner语义。

## TASK-P6-02 machine isolation boundary

四份`2.9.0` carrier把`data_plane=SIMULATION`、Development/Test/Benchmark environment、`synthetic=true`、`production_binding=false`、`production_authorized=false`与OPEN-010/011/014/015固定为Schema常量/完整集合；任何Production、unknown environment/version/field或跨plane引用均拒绝。Published samples和CI report只含sanitized synthetic references、fingerprints和aggregate shape values，受`SIM-ASSUMPTION-021`约束，没有raw row、PII、credential、endpoint或secret。

本Task没有新增环境变量、storage、database、queue、service、identity principal或deployment。Future Production carrier/authority不能通过配置开启，必须由新version和OPEN closure另行授权；当前唯一操作性边界仍是禁用provider并使用同resource option权威标准工时。

## TASK-P6-01 data/model isolation boundary

Duration dataset、model registry、evaluation和prediction evidence必须在Development/Test/Benchmark/Production之间使用隔离的database、credential、namespace和artifact location；synthetic数据固定`production_binding=false`，不能join、复制或promotion为Production evidence。Raw受控行留在获授权数据平面，CI/provider只允许sanitized reference、version、fingerprint、count、aggregate metric与disposition。

任一purpose、source authority、consent/获批准使用依据、retention policy、deletion procedure或具名owner closure缺失时，Production extraction/training/storage/promotion都default-deny。没有approved model/confidence/drift policy也等同禁用provider并使用标准工时；不得以environment default打开。TASK-P6-01没有增加环境变量、Secret、service、storage、route、dependency或deployment。

## TASK-P5-22 Exit audit isolation boundary

Audit只读取仓库、公开GitHub provider metadata/artifact下载副本及Development/Test/Benchmark下的fresh evidence；运行输出限定在ignored `build/**`。它不新增environment variable、Secret、service、port、database、network、container、dependency或lock，也不读取或记录Production credential。

报告固定`data_plane=SIMULATION_DEVELOPMENT_ONLY`、P6未进入、Production identity/approval authority未形成、external/deployment/capacity/SLA未建立。Local或provider READY都不改变隔离级别。

## TASK-P5-21 Gate isolation boundary

P5 portfolio Gate只在Development/Test/Benchmark与`SIMULATION`边界内编排冻结的Global/default-off、formal Validator、XS/S/M Benchmark及P4 regression入口。新增CI命令沿用既有环境与artifact目录，不新增environment variable、Secret、service、port、database、network、container、dependency或lock；C-012～C-018在进入任何owner执行前保持`UNSUPPORTED_CAPABILITY`。

Machine report明确保留P5-22 `NOT_STARTED`、P6+ `NOT_ENTERED`、Production identity/approval authority `NOT_FORMED`、external publish/integration `NONE`、deployment `NOT_PERFORMED`和capacity/SLA `NOT_ESTABLISHED`。本地或provider PASS都不改变data plane或隔离级别。

## TASK-P4-14 Gate isolation boundary

Gate在现有Development/Test/Benchmark + `SIMULATION`边界内fresh调用owner checks与Chromium mock transport，不新增environment variable、Secret、service、port、database、network、container、dependency或lock。两轮Backend与browser evidence写入`build/**`和required artifact；raw token、credential或Production connection均不读取、不记录。

报告明确保持`external_publish_or_transfer=NONE`、Production identity/authority `NOT_FORMED`、capacity/SLA `NOT_ESTABLISHED`及P5 `UNSUPPORTED`。P2/P3序列化报告只做JSON object key-order正规化以满足既有in-memory validator，所有值、list顺序和raw SHA-256保持不变；这不是跨plane转换或新的authority。

## TASK-P4-13 browser isolation boundary

P4工作台沿用既有runtime配置，只在`SIMULATION`与DEVELOPMENT/TEST/BENCHMARK中构造query/action；Production在发出read或mutation前default-deny。Bearer只由当前内存注入，请求使用`credentials: omit`，raw token与Idempotency-Key不写入local/session storage、cookie、URL、报告或UI；unknown outcome的exact action也只保留在当前hook内存，刷新页面即丢弃。

本Task没有增加env var、secret、service、port、container、network、storage、dependency或lock。E2E的mock transport和`SIM-P4-REPLANNING-UI-001@1.0.0`仅证明browser contract/isolation，不是部署拓扑、真实Production data plane、capacity或SLA。

## TASK-P4-12 HTTP isolation boundary

P4 route只在`data_plane=SIMULATION`、`simulation_api_enabled=true`且environment为DEVELOPMENT/TEST/BENCHMARK时允许委托，carrier/query/action必须与runtime逐字一致且`production_binding=false`。Production composition对有效Simulation carrier在authorization provider和application lookup前直接拒绝并审计；本Task不新增env var、secret、gateway、network、storage或deployment配置。

## TASK-P4-11 runtime/isolation boundary

ChangeReport read、P4 ExportJob、worker、local package store和machine check只接受`SIMULATION`及development/test/benchmark环境；Production-shaped context/request在lookup、transaction或I/O之前拒绝。Package target固定`SIMULATION_INTERNAL`，download不提供external transfer route。

本Task没有新增environment variable、Secret、service、port、container、dependency、lock或migration。CI只新增in-process `app.exporters.change_report_output_check`并写ignored JSON artifact；临时SQLite/local directories、correctness runtime和archive size不是Production deployment、isolation、capacity或SLA证据。

## TASK-P4-10 disruption replay isolation

Library loader只接受DEVELOPMENT/TEST/BENCHMARK、`synthetic=true`、`production_binding=false`以及exact boundary `SIMULATION_NON_PRODUCTION/UNSUPPORTED/NOT_ESTABLISHED`。Production environment、缺失五类coverage、未知字段/版本、乱序offset或tampered invariant在继续编排前fail closed。Orchestrator无Infrastructure/API/OR-Tools/SQLAlchemy、wall clock、global random、network或secret依赖；FULL CI只上传JSON evidence。

Seed、900秒freeze、offset、priority、duration、tardiness与stability均来自versioned asset/SIM registry，不读取环境默认且不形成Production policy/capacity/SLA。

## TASK-P4-09 Execution Simulator isolation

Execution Simulator config只接受`SIMULATION`、`synthetic=true`、`production_binding=false`与`DEVELOPMENT/TEST/BENCHMARK`。Environment为`PRODUCTION`、stale input fingerprint、unsupported/deferred capability或未知version时，在compile/ingress前fail closed。Core不读取环境变量、host clock、credential、network、database或Worker配置；code commit只能是`uncommitted`或exact 40字符lowercase SHA。

FULL CI以`PLANTNEXUS_CODE_COMMIT=${{ github.sha }}`生成machine report并上传，报告不注册Simulator route/worker/Production authority。P4-10 quantitative disruption config、真实event source与Production enablement仍需独立治理，不得通过环境变量隐式开启。

## TASK-P4-08 isolation boundary

Application composition在首次repository/idempotency lookup前强制Simulation plane、synthetic request、非Production binding和Development/Test/Benchmark environment；Production-shaped context、cross-plane repository或`SIMULATION_INTERNAL`以外current target均default-deny。真实SQLite迁移头测试只证明隔离correctness/rollback，不形成Production PostgreSQL topology、HA或capacity evidence。

Service无HTTP/UI/secret/network/external publish路径；solver limits、seed、900秒freeze和fixture KPI仍引用既有versioned Simulation assumptions，不成为Production default。P4-09 Execution Simulator、P5与Production deployment/SLA保持未形成。

## TASK-P4-07 isolation boundary

Strategy只接受Simulation plane、synthetic PUBLISHED base、approved versioned Policy/Limits及同一ReplanRequest/projection/Problem lineage；任何Production-shaped、cross-plane或stale输入在建模前拒绝。求解器无网络、数据库、secret、external adapter或state副作用，CI只上传JSON evidence。fixture limits、seed、worker和运行时间都是bounded Development配置，不是Production default或SLA。

## TASK-P4-06 isolation boundary

Calculator、builder、precheck和machine fixture均为无网络、无数据库、无wall-clock/random读取的pure Simulation/development路径。Builder强制`data_plane=SIMULATION`、`synthetic=true`、`production_binding=false`且environment仅DEVELOPMENT/TEST/BENCHMARK；Production-shaped context、缺失provenance或cross-plane lineage在任何Solver/Version/persistence副作用前拒绝。CI新增证据步骤仍在FULL profile内且只上传JSON artifact。

本Task没有创建Production config、secret、route、worker、database binding或external adapter；fixture的300秒shift与KPI值只是确定性测试向量，不是Production default、容量阈值或SLA。

## CI validation profile isolation

CI Profile只由不可变event base..head的Git路径决定，不读取业务environment、Secret、数据库、data plane或用户输入。只有`README.md`、`docs/README.md`及公开技术文档目录中的Markdown-only diff可选择DOCS_ONLY；workflow、脚本、test、lock、配置、内部过程路径、混合/空/未知diff全部选择FULL。分类器和changed-doc validator仅使用Python标准库与Git，workflow权限继续为`contents: read`；公共README新增run/job/artifact长ID、digest或implementation/closure SHA会被拒绝，避免把内部Provider证据复制到公开入口。

最终required context仍为`validate`。FULL先由不安装依赖的`full_preflight`核验exact runtime、UTF-8/locale、working directory、单worker Playwright、fail-closed routing和P4 frozen replay隔离；成功后`full_backend`与machine/frontend/browser/build/Gate主链在独立runner并行，两个分支都必须成功。DOCS_ONLY要求全部FULL jobs skipped且只验证公开文档。任一未知、失败或意外skip都使`validate`失败。

Provider使用支持Node.js 24的官方Action运行分类、Python/Node setup与artifact上传；uv/npm缓存仅缓存immutable lock对应依赖，不共享working tree或业务状态。`provider_evidence.py`只通过已有`gh`认证读取exact SHA run/check/artifact，输出和ZIP限定在ignored `build/**`，不把credential写入参数、报告或仓库。Action版本变化本身属于workflow diff并强制走FULL，不能由DOCS_ONLY自我验证。

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
