---
doc_id: DOC-INDEX-001
title: PlantNexus APS 文档中心
status: baseline
spec_version: 0.3.0
phase: P5
normative: false
source_sections: [2, 6, 70]
last_reviewed: 2026-09-01
---

# PlantNexus APS 文档中心

## TASK-P5-22 local independent Exit decision

TASK-P5-22从P5-21 provider-verified closure `d0a83c58cb4a2d4afa76e8c8cff08441574e2e30`冻结PHASE_GATE。独立审计已核对P5 first-parent的11个提交/run、8 success/3 retained failure和22个未过期artifact；required `validate`均来自GitHub Actions app `15368`，下载ZIP/provider digest、exact SHA与machine语义一致。

Fresh qualification、P5/P4/P3/P2 Gate、XS/S/M、Frontend、两轮P4 browser/Simulator与治理检查均通过。Exit manifest当前为15/15、`issues=[]`、`blocking_gaps=[]`，九项DEFERRED、selected=`[]`、18张owner卡`cancelled`、C-012～C-018 unsupported及Global-only边界均未漂移。序列化排序造成的首次本地P4 object-key拒绝已由Audit入口的严格key-set校验与仅对象顺序正规化纠正；值、array与raw hash未变。

本地Exit=`READY`。首个implementation candidate `5d60dc90ddf22e75ec1783c0a7b92c016d452136` / run `33450894193`在冻结P4-13 replay因当前70-step CI contract未被隔离而fail closed；失败artifacts `9779882690`,`9779713051`已下载保留。Direct corrective只在临时worktree恢复P5-21 closure的68-step CI contract后运行未修改P4-13 evidence，不改变主工作树断言、P4 owner或Exit决定。

Corrective implementation `83c51d765045da030b8cff871191be37bb9e899a` / run `33451784906`的FULL `99683143439`与required `99685627036`已exact成功，required app=`15368`。Artifacts `9780286365`,`9780011491`的Provider/download digests一致；60 JSON、216个commit字段、15 paths、4 Rules、15/15 checks与0 issues/gaps/scope均精确。当前提交仅为两路径evidence-only closure，closure provider完成前Task仍`in_progress`、P5仍`active`；不切换P6，也不是Production/UAT、真实authority、external publish/integration、deployment或capacity/SLA证据。

## TASK-P5-21 provider-verified portfolio Gate

P5-21从P5-02 closure `d7779c014351d41909322b967c5c8eca68713e8b`冻结PHASE_GATE。公开P5-02 manifest仍精确是空selected、9项DEFERRED、18张cancelled owner和唯一直接依赖TASK-P5-02；本Gate不执行任何已取消owner。

`p5-portfolio-gate-report.v1`本地与corrective Provider均为12/12 PASS、`issues=[]`、`blocking_gaps=[]`，完整保留empty selected-owner manifest、C-012～C-018七项exact rejection、Global-only、formal Validator/mutation、XS/S/M和独立P4两轮重放。两轮P4合计22 stages、10 browser specs、10次fresh Validator和10份complete ChangeReport，Backend全量860/860 PASS。失败candidate `e0dee8544...`与`d00386f4...`的run/artifact均保留；corrective不改变P4检查或业务语义。Implementation `c8ffd042738ffe79c350262aa7195daa9a7bf083`的run `33406166742`、FULL `99534217662`、required `99538066470`和artifacts `9763658843`/`9763213551`均exact成功；ZIP/Provider digests为`sha256:ed29d5aa2891d6a442a91360391219e6c265f2a0fe6d0b5e4210bd4c5ae316ed`、`sha256:1375f3fbeb739b53dee819da977e21f875c8bdc0ca910da86f43b84cd3cd098c`，52份validation JSON全部PASS、无commit drift。Evidence-only closure exact provider前TASK仍`in_progress`；P5-22继续`planned/NOT_STARTED`，该Gate不是Exit或Production evidence。

## TASK-P5-02 portfolio amendment boundary

TASK-P5-02已获用户独立授权，并以P5-01 closure `01b8918db62cc9f5c4421d0b90d93151ddc552f1`为不可变Diff base。它不重做qualification：九项仍全部`DEFERRED`、selected=`[]`，因此TASK-P5-03～20的十八张owner卡全部进入证据化`cancelled` terminal状态，没有能力实现被启动。

[`p5-portfolio-amendment-manifest.v1`](core/p5-portfolio-amendment-manifest.md)逐项绑定P5-01 decision fingerprints、owner映射和terminal状态，并把P5-21 direct dependencies消除占位后精确解析为仅`TASK-P5-02`。Manifest为10/10 checks、0 issues/blocking issues；P5-21/P5-22继续`planned/NOT_STARTED`且不得自动启动。

Implementation `ed9ee75122341c1a71b641edc445e2a58cac70de` / run `33389105900`的classify/docs/required jobs `99478355746`,`99478399695`,`99478441483`全部exact成功，FULL按DOCS_ONLY skipped且required app=`15368`。Artifacts `9756735835`,`9756730213`的Provider/download digest一致；profile 4/4、public-doc 1/1、3 paths、77→78 documents、`issues=[]`。本tracked提交只回写implementation evidence，closure exact Provider待post-push复验。

该amendment不把DEFERRED改写为SUPPORTED，不改变Global/P4冻结边界，也不关闭OPEN-001～015、SIM-ASSUMPTION-001～020或RISK-001～017。P6+、Production/UAT、真实authority、external publish/integration、deployment、capacity/SLA继续排除。

## TASK-P5-01 qualification decision boundary

TASK-P5-01从`4ccb2ed99ffe73abeb0462efff4a5342cd7c5522`冻结证据范围。由于没有获得经授权的真实需求材料，九个P5候选分别以versioned Simulation/P2 XS/S/M作边界重放，但这些资产不能自行证明业务必要性；五事实`ALL_TRUE`规则因此把九项全部判为`DEFERRED`，selected=`[]`、P5-02 authorization=`false`。报告本地11/11、12项focused tests通过、`issues=[]`/`blocking_issues=[]`，未新增数值SIM假设。

该决定只形成可复现的优先级证据，不改变C-012～C-018的`UNSUPPORTED`或Global唯一策略状态，不实现候选，不修改Schema/migration/dependency/state/workflow/CI。P4动态重排能力只作为冻结回归上下文；P6+/Production/UAT/真实authority/external/deployment/capacity/SLA继续排除。

首次candidate `c3761d0505690567ab6b60be1d04041dab0c0652` / run `33380357486`因P4 frozen evidence拒绝新增backend测试而保留为失败；direct corrective `88fb9f53ab5425d72ee6659188b689a26d0e387a`不改P4或workflow，只迁移同一12项测试。Corrective run/FULL/required=`33383710010`/`99461537473`/`99463769376`全部exact成功，required app=`15368`。

Machine/profile artifacts `9754995093`,`9754731890`下载ZIP digest与provider一致为`sha256:766163e4b516b1645bc985575e4ab3b113d32dd20d8ef77671cc56335f17a133`、`sha256:06caf0b3a9c448e6e9e1af7c01828edbf569e9bbfc810571c40111e2396515da`；54 JSON全部解析、43个commit字段exact、0 issue/gap/error，P5 report为11/11、9 DEFERRED、selected empty。本tracked closure只回写上述provider evidence，closure自身等待DOCS_ONLY exact provider，P5-02仍`NOT_STARTED`。

## P5 activation and planning boundary

P4已按用户授权关闭为`completed`，P5已激活为`active`。承接检查仅确认closure `892c46d660a6bf3cde8ed473199f38746d041e47`三端一致、0/0、clean、P4 Exit=`READY`/0 gaps、无active/blocking项且required `validate`/app `15368`未漂移，不构成P4重审。

TASK-P5-00建立TASK-P5-00～22的条件计划：先证据选择和plan amendment，再为每个selected候选独立执行合同包与vertical slice，最后执行selected portfolio Gate和独立Exit Audit。所有P5业务、Schema、migration、dependency、test assertion和workflow本次均未修改；TASK-P5-01未启动。

Implementation `a316d7a5ebf2e8c7e33da46cf1d7c08f2dfbdfa3`的run/required=`33373013523`/`99428242533`已exact成功；profile/public-doc artifacts `9750780227`,`9750786965`的下载ZIP digest与provider一致，并精确复现5个公开Markdown路径、`DOCS_ONLY`、4/4+1/1 checks和`issues=[]`。本tracked evidence-only closure仅修改本文档与根`README.md`，closure exact provider待post-push复验。

P5激活不改变C-012～C-018的`UNSUPPORTED`状态，也不实现Decomposition/Rolling。P4的ExecutionEvent/ReplanRequest/freeze/OBJ-002/ChangeReport/Execution Simulator仍是冻结回归边界。P5不含multi-Factory、alternative routing扩展、tools/fixtures专用语义或Hybrid；P6+/Production/UAT/真实authority/external/deployment/capacity/SLA均未形成。

## TASK-P4-15 local independent Exit decision

P4-15从`60ac4c17c6de514c036be7bac63e66da589bfb4c`执行独立Exit审计，而非复用P4-14 Gate结论。41个P4提交、42个run、67个artifact均被重新查询和下载；0 expired、0 digest mismatch、0 JSON parse error，成功链1,134份JSON的exact SHA/Task/Diff base/Impact Rules/checks/issues及browser语义一致。0093/9a87/7e558/18c0失败候选和direct corrective chain保持可见。

fresh replay通过834 Backend、78 Frontend、17/17主Chromium、P3 12/12×2、P4 5/5×2及全部历史machine；P2/P3/P4 Gate分别11/11、14/14、14/14且均无blocking gap。审计本地结论为`READY`，公开机器观察位于[`p4-exit-gate-audit-observations.v1.json`](p4-exit-gate-audit-observations.v1.json)。P4仍是当前阶段并等待单独phase-transition授权；P5/Production、真实authority/external integration/UAT/deployment/capacity/SLA未启动或形成。

Candidate `aedc682a5a82e135c63ce20f1c85009282ae7f42`的FULL run `33366070434`因P3 locale click时序单次11/12失败而保留，required failure、两份artifact、digest与failure media均未改写；同一exact SHA本地复验12/12。Direct corrective `3637f514947397f7ba04a6ff3061a48f1809b44e`的run/classify/FULL/required=`33367097943`/`99409899613`/`99409926891`/`99412480503`成功，required app=`15368`。未过期artifacts `9748939618`,`9748651059`的provider/download digests为`sha256:be149288c052c84f314129bc2dbf63c9fef4608eae5de009dd51e959a93a595a`、`sha256:e853cd63c9e66d318dd44432ce2eff17d3d53ccb26481e0198fa52abf34f5946`，53 JSON及累计8-path/1-rule/19-check/0-issue治理证据一致；本次closure仍须通过独立DOCS_ONLY provider后Task才`done`。

## TASK-P4-14 local P4 Vertical Slice Gate

TASK-P4-14从`ea05c3d9e94af91ae4525e5fbf1087a4a4198a15`冻结全部P4-01～13 provider inputs，并新增只聚合、不修业务的`p4-vertical-slice-report.v1`。两轮Backend replay逐次调用P4-02～12的11个owner machine入口，保留22份raw subreport与176个subordinate checks；连续五类disruption合计10个step、16个标准event、10次fresh Validator及10份complete ChangeReport。两轮专用Chromium各5/5并保留JSON/JUnit/HTML与failure media策略，P2/P3 Gate也作为exact SHA回归输入。

当前本地Gate为14/14、`blocking_gaps=[]`、单一Backend与browser semantic fingerprint、四项fail-closed rejection PASS。聚合器只对已序列化P3 JSON的object key顺序正规化，raw bytes hash及所有业务值完整保存。本Task不变更Schema/migration/dependency/lock、fixture expected、ADR/state pair或前序owner实现，也不形成Exit READY；TASK-P4-15/P5/Production/external authority/capacity/SLA继续明确排除。

Implementation `296c9b495c44ac4245649f143ba9d366c25b0b13`的FULL run/job/required=`33360100486`/`99389677929`/`99391482358`及machine/profile artifacts `9746591757`,`9746389508`均为exact、成功、未过期。下载ZIP与provider digest逐字一致为`sha256:7a4645e064b00430b67eb7bf19cd7e668b3c0dc1f7d4542ee23abc7669e06ba3`、`sha256:a4028270dd0138fef240db1b1f936062e26eea971eeb7424e80718bbf4237f0a`；47份JSON全部PASS、0 issues/gaps/commit drift，17-path FULL profile的base/head与`issues=[]`一致。Evidence-only closure exact provider完成前TASK仍为`in_progress`。

## TASK-P4-13 local Replanning Workspace boundary

TASK-P4-13以`be2389594f3e224de3f5a73f4b8b62ffcffb5b7b`为不可变Diff base，只新增一个隔离的P4 route及六文件typed consumer。页面消费P4-12四类versioned projection，显示server-owned event顺序、Request/attempt/result、freeze/effective locks、tardiness/Stability和ChangeReport；英文machine values、raw UTC、ID、fingerprint和JSON证据始终可见，`zh-CN`/`en-US`只是展示层。

动作严格依赖server `allowed_actions`与expected-state CAS。Unknown outcome固定为query-before-retry且只允许复用内存中的exact body/key；Production runtime、tampered projection、unknown state/type和mixed lineage均fail closed。完整HIGH_RISK已本地通过19 focused、821 Backend、78 Frontend、17/17主Chromium、两轮P3 Gate各12/12、全部machine/XS/P2/P3 Gate/SCA/license/build/Compose及43-path/5-rule/19-check/0-issue治理，forbidden scope=0。首个candidate `18c0eb8967cfd7b11d7a9019fe72a221dfc0bd85`的run `33354198989`因P4 machine step工作目录错误而失败；corrective `9a7d79b684ce066f784179e61bcd27f05c609fc9`的run/FULL/required=`33354756522`/`99374693595`/`99376087137`已exact成功，artifacts `9744915726`,`9744760335`未过期且下载ZIP digest与provider逐字一致。Artifact精确绑定Task、SHA、不可变Diff base、五个Rules、8 checks、0 issues及双Gate；本evidence-only closure记录完成结论并等待自身post-push provider。新增`SIM-P4-REPLANNING-UI-001@1.0.0`只承载五类/六event的mock transport浏览器证据，不形成Production facts、authority、capacity或SLA。

## TASK-P4-12 local HTTP/OpenAPI boundary

TASK-P4-12以`f4a54d3bb065b5cc8b51c450ffdc435bcc77d384`为不可变Diff base，在既有FastAPI composition内additive新增8 paths/9 operations的`dynamic-replanning-http.v1`。Transport只验证已发布P4 carrier、fingerprinted query/action、header/body correlation/idempotency绑定、server-derived capability/planning-scope及稳定HTTP/error envelope，然后委托注入的P4 application facade。

`p4-replanning-api-report.v1`为8/8、五个Impact Rules、`issues=[]`；新增FULL CI step与unit/contract/integration/security证据。P3的18 operations改为精确子集回归，operation ID与路由语义不变。ReplanRequest不新增state，cancel/retry只委托PlanningRun attempt CAS；Production在provider/application lookup前default-deny。本地14 focused、821 Backend、67 Frontend、三轮12/12 Chromium、全部machine/XS/P2/P3 Gate/SCA/license/build/Compose及35/5/19/0治理均PASS。

Implementation `7cce9744783acc7cf80e0cecafb6f9e144fe085f`的run/FULL/required=`33347790649`/`99355189991`/`99356475314`已exact成功；machine/profile artifacts `9742718240`,`9742570373`未过期并已下载，ZIP SHA-256与provider digest逐字一致为`sha256:2ca6df933fee54a348b370b3fa2179dbaef0d3e48d477910f444455da27c0449`、`sha256:baad74c370a231d6933fa4d49cbd19945994d82ab39b3adb824093f9758dc229`。Artifact精确绑定Task、SHA、Diff base、35-path FULL profile、五个Rules、8 checks、0 issues与P2/P3 Gate；本evidence-only closure据此记录完成结论，但其自身仍须post-push exact provider复验，TASK-P4-13未启动。

## TASK-P4-11 local ChangeReport read/export boundary

TASK-P4-11从clean/provider-verified P4-10 closure `45b12d9a67ce5ef1680a47fecdc68705355af226`冻结不可变Diff base。新增的versioned read model只读取P4-08 durable applied-result envelope和exact `schedule-version.v2`，以report/result/schedule/Solver/Validation/KPI lineage及显式query preconditions阻止stale或mixed replay；stable filter/cursor不会触发Solver或任何state write。

Internal output consumer使用`export-job.v3`既有状态语义与独立P4 worker，生成`export-manifest.v3`、13 payload、5-sheet safe workbook及deterministic archive，随后只允许EXPORTED job的verified retrieval。P3 package/profile/bytes、Schema set `2.8.0`、migration `0005`、dependencies、Replan/Simulator owners和全部state pairs均未修改；API/UI留给P4-12/13，external/Production/P5保持`NOT_FORMED`。

完整HIGH_RISK本地证据现为18 focused、806 Backend、67 Frontend、三轮各12/12 Chromium、全部历史machine/XS/双Gate/SCA/license/build/Compose以及32-path/8-rule/19-check/0-issue治理；本Task machine为8/8、`issues=[]`，P2/P3 Gate为11/11、14/14且`blocking_gaps=[]`。首次全量Backend因旧P3 substring扫描器把`_FINGERPRINT`中的`ERP`误判为外部集成而得到800 passed/1 failed/5 errors；限定改名为`_SHA256_REFERENCE`后目标与806项全量均PASS。

Implementation `7d685d91e5011cdb4b3289ef10a9a2355c53570b`的run/FULL/required=`33156391439`/`98800085239`/`98801664096`已exact成功；machine/profile artifacts `9679951468`,`9679763686`均未过期并已下载复验，digests分别为`sha256:59088ba24779ffb2cef9d8d225c2897d50a8d4ef598cf4ecb66037354bf97d80`、`sha256:7a89878a6fecc58657633577eb8d6caebc06b97eadd9ea90fb9efed79e94d8ba`。Artifact精确绑定Task、implementation SHA、原始Diff base、八个Impact Rules、8 checks、0 issues、FULL 32-path profile及P2/P3 Gate；在该P4-11 closure历史时点TASK-P4-12保持`planned`且未启动，当前状态见本页顶部。

## TASK-P4-10 local continuous replay boundary

TASK-P4-10从clean/provider-verified P4-09 closure `8bbe0c643571e578ec637f135a2390c90de02512`冻结不可变Diff base，并在Simulation/development边界形成一个versioned五步/八事件场景资产、严格continuous replay orchestrator、raw step evidence与FULL machine step。编排只调用P4-09标准event入口和既有P4-04/P4-08 owner contracts；它不复制fact、freeze、Solver、Validator或ChangeReport公式，也不直接访问repository/API。

每步要求exact trigger event、previous Snapshot/Version baseline、new Snapshot/Problem、ReplanRequest/Run、fresh Validator PASS、new immutable DRAFT、complete ChangeReport和六项fact/lock invariants。下一步baseline使用不同ID的PUBLISHED-shaped测试载体逐字承接同一DRAFT内容，并保存`source_draft_id`、`SIMULATION_NON_PRODUCTION`与`authority_claim=NONE`；它不执行READY/APPROVE/PUBLISH/EXPORT。完整HIGH_RISK本地验收已通过14 focused、786 Backend、67 Frontend、三轮各12/12 Chromium、全部历史machine/XS/双Gate/SCA/license/build/Compose及27/5/19/0治理。P4-11不会自动启动，P5/Production边界保持未形成。

首个candidate `7e558666f89ec7ab2314ddd35320bc210d04a8f1`的run `33148120102`因既有P3 locale浏览器用例在2 workers下11/12而被required正确拦截，失败证据保留。限定corrective `f475a13baf22a0759c19967f6264d8d0b71e47d5`只串行化三轮Playwright且不改实现、断言、retry、依赖或lock；run/FULL/required=`33148902189`/`98776094074`/`98777724803`已exact成功。Machine/profile artifacts `9677080681`,`9676878307`均未过期并已下载复验，digests分别为`sha256:781240ef2b20791b4edc61509b1b95ddcffac57abfa3224ae9bd0518a1a4a46a`、`sha256:ed6bc45f16ebd928143196e4d082eb0e2d0da6950fc976b9aa6f10bd82c0d24c`；artifact精确绑定SHA、Task、原始Diff base、五个Impact Rules、8 checks、0 issues及P2/P3 Gate。本evidence-only closure记录完成结论，但其自身仍须post-push exact provider复验，TASK-P4-11保持`planned`且未启动。

## TASK-P4-09 local Execution Simulator core boundary

TASK-P4-09从clean/provider-verified P4-08 closure `e4874735166be93473ccaebaf1090980db957552`冻结不可变Diff base，并在Simulation/development边界内形成versioned virtual clock/event schedule、named-child-seed tie-break、canonical standard ExecutionEvent stream、prefix checkpoint/restart与既有ExecutionSimulationManifest consumer。完整stream在副作用前通过P4-04严格事件校验；runtime只持有`ingest_event`端口，不导入Infrastructure、Planning/Solver、API或Application捷径，machine harness以真实`ExecutionFactProjectionService`公共入口复验该端口。

完整HIGH_RISK本地验收为Task-specific 12、Backend 771、Frontend 67、三轮Chromium各12/12、历史machine/XS/双Gate/SCA/license/build/Compose与24/4/19/0治理全部PASS；machine 8/8且`issues=[]`。FULL workflow新增`P4 deterministic Execution Simulator core evidence`；Schema/migration/dependency/state machine/P4-04入口/P4-08 application保持逐字冻结。SIM-ASSUMPTION-018只登记三事件、两个10秒同刻事件、20秒末事件、1秒resolution及固定seed/origin的correctness向量；P4-10五类连续场景、P4-14 Gate、P5和Production authority/external/capacity/SLA均未形成或启动。

Implementation `6b293720d795ae7dcb2f6453dc999471d3586b94`的run/FULL/required=`33141091252`/`98751935625`/`98753074526`已exact成功；machine/profile artifacts `9674090110`,`9673955596`均未过期并已下载复验，digests分别为`sha256:521fec38cca4a625cc5dcacb6624e472b34dab1cf5fc76a5518c725cf5287e4b`、`sha256:7851c45a7abf3610030846ca27dd290ee9ef2a2949fffb02856c27dcecc4a4b4`。Artifact精确绑定implementation SHA、Task、原始Diff base、四个Impact Rules、8 checks、0 issues、FULL 24-path profile及P2/P3 Gate；本evidence-only closure记录完成结论，但其自身仍须post-push exact provider复验，TASK-P4-10保持`planned`且未启动。

## TASK-P4-08 local implementation boundary

TASK-P4-08已在冻结Diff base `77981f0564d91dfb57fee6e3792f4989bdb51d32`内形成Simulation-only两事务application闭环：intent事务保存immutable request/attempt/audit；求解阶段重建exact current PUBLISHED lineage下的Problem，并复用P4-05/06/07能力；result事务重新读取current/base/request/attempt/Snapshot后，原子保存new DRAFT ScheduleVersion、完整SolverReport/fresh validation/KPI/ChangeReport result envelope与审计。Exact replay、stale current、KPI mismatch、并发竞争、审计失败和no-candidate terminal链均有本地证据。完整HIGH_RISK为focused 22、Backend 759、Frontend 67、三轮Chromium各12/12、历史machine/XS/双Gate/SCA/license/build/Compose与32/6/19/0治理全部PASS；machine为8/8、`issues=[]`。

Implementation `f664517e5f17dc2453444adf9a5503ff1393530e`的run/FULL/required=`33137388411`/`98740332159`/`98741555347`已由GitHub Actions app `15368` exact成功。Machine/profile artifacts `9672684493`,`9672545763`均未过期并已下载复验；digests分别为`sha256:4d1ef3e89e32dd060e1cb946da119202f688adb9dcb7f2bd7536f2ee1c77e2f9`、`sha256:a9c4e44cdab8fab6bbdac19c7de08b2826b4286602c7fc376e2e76a89d8e3429`，精确绑定Task/base/SHA、32个changed paths、六个Impact Rules、8 checks、0 issues和P2/P3 Gate。本evidence-only closure据此把TASK-P4-08标为`done`；closure自身仍须post-push exact provider。

Schema/migration/dependency/state pair、P4-07 Solver公式、API/UI、P3 publish/export与Production边界保持冻结；P4-09现仅按上方独立授权形成core，P4-10～15仍为`planned`且不会自动启动。

## TASK-P4-07 completion boundary

TASK-P4-07已在冻结Diff base `e212ab7957d6bc5887048ee54809c8194d6e1eaf`内实现Simulation-only全局六轮词典序重排、逐轮等价锁定、base Hint、fresh独立candidate/ChangeReport算术复核和FULL CI机器证据。`solver-report.v2`保存三阶段value/bound/budget/stop/status与exact provenance；机器报告固定Task、Diff base、七个Impact Rules、8项检查和`issues=[]`。完整HIGH_RISK本地验收为focused 48、Backend 736、Frontend 67、三轮各12/12 Chromium、历史machine、XS Benchmark、双Gate、build/Compose及33/7/19/0治理全部PASS。Implementation `cd77708299edbc6c7ab9abb6aed7ff6950a7f2ec`的run/FULL job/required job=`33131611010`/`98722212668`/`98723499160`已由GitHub Actions app `15368` exact成功；machine artifact `9670605640`（digest `sha256:0623c54e61be4e0ce2e70ebf21926a78bdf956e73b1016de34d0da5fb8a22dde`）及FULL profile artifact `9670459898`（digest `sha256:90cfa27d5f9261a9bbb71de949b71bffb3183241c0b20412d7786730c4e4940c`）均未过期并已下载复验。本evidence-only closure据此把Task标为`done`；closure自身仍须post-push exact provider复验。

该P4-07 closure时new DRAFT与最终ChangeReport/Request result原子事务仍归TASK-P4-08；P4-08随后仅按新的独立授权形成上方本地application闭环，P4-09+、P5和Production边界没有变化。

## TASK-P4-06 completion boundary

TASK-P4-06已从provider-verified P4-05/P4-16 closure `d9d9f2fa2dbefe4c9942aaa8a943a93fdc7efd43`按独立授权实现纯整数OBJ-002 calculator、immutable complete ChangeReport builder、独立precheck和FULL CI机器证据。固定fixture覆盖UNCHANGED/CHANGED/ADDED/REMOVED_BY_FACT、metadata-only no-movement、1个SOFT violation、300秒resource/start movement、completion fact、solver fallback reason及before/after priority-weighted tardiness `600→300`；machine为8/8、`issues=[]`。完整HIGH_RISK本地验收同时通过Backend `724 passed`、Frontend 67项与三轮各12/12 Chromium、全部历史machine、XS benchmark、P2/P3 Gate、SCA/license、Compose/build、文档治理及26-path exact allow-list。

首个implementation `5c7d9a6a42b798f5219484f0fb19851f410c991e`/run `33125423389`因artifact缺少显式Impact Rules envelope而只作为纠正链历史保留。Corrective implementation `10abdd105c697f61ba6c88078ae0ba28fed8a4e5`的run/FULL job/required job/artifact=`33126551137`/`98706008238`/`98707464048`/`9668755204`已exact成功并下载复验；digest `sha256:64c20ceba56d5872d48d19088c4f9f889d08eb31766659c6b579d908dd4bc066`精确绑定Task、Diff base、6个Impact Rules、8/8 checks与`issues=[]`。首个closure `9a87ca13bb7623159d68fb06efec2714c065dd79`/run `33127421798`因4个仅内部工作区可见的链接而被public-doc gate和required `validate`正确拒绝；该失败证据保留。本corrective evidence-only closure移除公开文档中的内部链接并把Task标为`done`；自身仍须post-push exact provider，P4-07不会自动启动。

Schema set继续为`2.8.0`且Schema/migration/dependency/state pair/CP-SAT/formal Validator均未修改；ChangeReport尚未被Replan application、ScheduleVersion或export消费。P4-07+、P5、Production authority/external integration/deployment/capacity/SLA均保持未形成。

## TASK-P4-05 completion boundary

TASK-P4-05已从provider-verified P4-04 closure `e7b96e28913e7eb5be63ae4265c09f8281456b1c`按独立授权实现Simulation policy、solver-neutral projection与独立precheck。HIGH_RISK本地验收、machine和mutation/Property replay均PASS；SIM-ASSUMPTION-017显式登记900秒half-open值，OPEN-005保持OPEN。Implementation `2d0ca8723b18dc08a57d12f4e26db3fae9f46a35`的required run/job/artifact=`33077329890`/`98534856259`/`9648715231`已exact成功并下载复验，本evidence-only closure据此把Task标为`done`；Schema、migration、dependency、既有Problem/formal Validator/CP-SAT、OBJ-002/ChangeReport与P4-06+均未启动或保持只读。

## TASK-P4-04 implementation completion

TASK-P4-04从closure SHA `3563bb236ce7b2c01794485110d4945a6e265105`冻结范围，现形成Simulation-only ExecutionEvent接收、连续prefix事实投影、new immutable Snapshot/checkpoint/audit及Urgent Demand标准Import复用。本地机器报告覆盖11个event type、4类拒绝、exact replay和故障注入原子回滚并为8/8 PASS；focused `12 passed`、完整Backend `654 passed`、Frontend 67 Vitest与三轮各12/12 Chromium、全部历史machine/P2/P3 Gate、SCA/license、Compose及双build均PASS。Implementation `47f55b41e370aa9d24fd9c987cff4663672c3ee8`的required run/job/artifact=`33066612047`/`98498125593`/`9644190441`已exact成功并下载复验，本evidence-only closure据此把Task标为`done`；closure自身仍须post-push exact provider复验。Schema set仍为`2.8.0`，migration head仍为`0005`，dependency/state pair不变；P4-05+、P5与Production均未启动。


## TASK-P4-03 persistence completion boundary

TASK-P4-03已在`7b9bfc3069de5d3738e5cc5827d27d197ed3d226`上独立激活。Additive migration `0005_replan_event_persistence`与plane-scoped repositories形成Simulation-only ledger/checkpoint/request/attempt/result-reference/audit storage primitive；本地machine 9/9、643 Backend、67 Vitest、三轮各12/12 Chromium、双Gate和52/6/19/0治理均PASS。Implementation `60f8e8900ecab60f0d64311912ae27f09a4d002f`的exact required provider及artifact `9639720666`已下载复验，本evidence-only closure据此把Task标为`done`；closure自身仍须post-push exact provider复验。Schema set仍为`2.8.0`且九份P4 carrier bytes、全部state pairs和dependency lock不变。P4-04 projection、P4-06 ChangeReport生成、P4-08 new DRAFT、P4-09 Simulator、P5及Production均未启动。

## TASK-P4-02 machine-contract release

TASK-P4-02已获单独授权并以`4026597ab1015b5ea3a89d241f0d12b5b481dee3`为不可变Diff base发布additive set `2.8.0`。ExecutionEvent/ReplanRequest/ChangeReport/ExecutionSimulationManifest以及Policy/SolverReport/ScheduleVersion/Export carrier的九份Schema与九份sample均为strict、no-default、offline-reference、Simulation-only合同；implementation `539cdbbdcdd406daba25b8d6b8caaa5133691e76`的exact required provider成功后，其evidence-only closure将TASK-P4-02标为`done`。P4-03随后仅按新的独立授权形成上方persistence slice；P5与Production均未启动。

## P4 activation and planning baseline

用户于2026-08-27在P3 Exit report/manifest=`READY`、`blocking_gaps=[]`且两个精确提交provider均验证后批准P3→P4。P3现为`completed`，P4为`active`；该次transition完成TASK-P4-00并将P4-01～15登记为`planned`，P4-15是唯一最后独立Exit Audit。该次transition本身不形成P4业务、P5或Production readiness/authority/external/deployment/capacity/SLA；当前Task状态见本页顶部与Task索引。

## P3 Exit audit status

内部工作区的P3 Exit report `milestones/P3-exit-gate-audit-report.md`与machine manifest `milestones/P3-exit-gate-evidence-manifest.json`已形成一致的`READY`/0 gaps结论，并保留39个前序P3 provider提交、4个历史失败run与阶段边界。TASK-P3-17 audit implementation与evidence-only closure均已exact provider验证，TASK-P3-17=`done`；其“P3保持active、P4未启动”是closure时的历史边界，现已由上方明确transition决定取代。Production仍未启动。

本目录是 PlantNexus APS 的唯一实质性开发文档中心。项目采用 Simulation-First、可追溯和阶段门禁驱动的开发方式；文档不是事后说明，而是代码、Schema、测试、Fixture、Benchmark 和发布活动的前置边界。

## 权威顺序

发生冲突时按以下顺序处理：

1. 用户在当前任务中的明确要求；
2. `core/APS_IMPLEMENTATION_SPEC.md` 中当前版本的 MUST、MUST NOT 和 DECIDED；
3. 已接受且未被取代的 ADR；
4. 当前阶段文件和当前任务卡；
5. 其他参考文档。

发现冲突不得自行折中，应登记问题并停止受影响的实现。

## 日常读取顺序

```text
/AGENTS.md
→ docs/agents/AGENTS.md
→ docs/current_phase.md
→ 当前 TASK
→ TASK 引用的 Schema / Contract / Constraint / ADR
→ 相关代码
→ 相关测试
```

只有规格版本变化，或任务涉及架构边界、PlanningProblem、SolverBackend、Constraint Catalog、状态机、发布规则或阶段退出门时，才需要重新完整读取总规。

## 文档分区

| 目录 | 用途 | 成熟方式 |
|---|---|---|
| `core/` | 总规、范围、原则、术语、能力边界 | 稳定、规范性 |
| `governance/` | 需求、追踪、开放问题、假设、风险 | 持续维护 |
| `architecture/` | 系统边界、模块、数据权威、环境 | ADR 驱动 |
| `domain/` | 领域对象、时间语义、状态机、错误与 KPI | Schema/业务规则驱动 |
| `contracts/` | 可执行 Schema 对应的人类语义合同 | 与 Schema 同版本 |
| `planning/` | 策略、约束、目标、求解器与独立验证 | 规范性核心 |
| `simulation/` | 虚拟工厂、场景、生成器、执行仿真和性能门 | 可重放、版本化 |
| `quality/` | 测试矩阵、Fixture、Mutation、Property、Benchmark | 持续维护 |
| `milestones/` | P0-P7 目标、范围和退出门 | 阶段级 |
| `agents/` | Coding Agent 的读取、执行和停止规则 | 稳定、简洁 |
| `tasks/` | 有界任务卡 | 随当前阶段创建 |
| `adr/` | 架构和规则决策记录 | 只追加/取代，不改历史 |
| `operations/`、`runbooks/` | 实现后形成的运维事实 | 后期形成 |

当前已生成文档的完整清单记录在内部工作区的`governance/document-inventory.md`。

## 文档状态

- `baseline`：由规格直接建立，可用于指导当前阶段。
- `living`：已经启用，但会随实现证据持续更新。
- `draft`：尚未批准，不能单独作为实现依据。
- `planned`：只有路径和目的，等待依赖形成。
- `superseded`：已被新文档或 ADR 取代，只保留历史。

## 当前范围

当前阶段为P4。P0～P3 Milestone均为`completed`；TASK-P3-00～17全部`done`且P3 Exit双提交provider已闭环。TASK-P4-00～08与P4-16现为`done`，P4-09～15为`planned`成员且未自动启动；P4-15最终独立审计也不自动进入P5或Production。详见`current_phase.md`。

P3已形成的顺序保持合同/ADR→Schema→persistence→validated DRAFT→read models→edit/lock→approval/reject→idempotent publish→ExportJob→API→Frontend/E2E→vertical Gate。批准的末段顺序为TASK-P3-15治理支持→TASK-P3-16本地化→TASK-P3-17独立Exit Audit；P3-16现已完成实现provider复验与文档closure，下一项仍须另行授权。展示术语规范见[`frontend/official-zh-cn-terminology-map.md`](frontend/official-zh-cn-terminology-map.md)，它不改变英文机器合同。

## 仓库入口与本地检查

- 项目入口、版本占位和当前可执行命令见 [`../README.md`](../README.md)；
- 根 [`../AGENTS.md`](../AGENTS.md) 只负责把 Agent 导向规范正文，不复制规则；
- 仓库治理检查运行 `uv run python scripts/check_docs.py`；
- 该检查验证 metadata、文档 ID、Markdown fence、本地链接、Task、版本化 registry、完整 ID 引用、逐根 traceability 和命名空间隔离；
- Task 进入 `in_progress` 时记录完整 `Diff base`；`--task <task-card> --check-diff` 对 `Diff base..HEAD` 与 working tree 的并集匹配 change-impact Rule ID，并可用 `--report <path>` 输出 `traceability-report.v1`。

本地检查从`current_phase.md`读取current `Pn`，保留历史terminal Task且拒绝future-phase详细卡。普通CI range只能归属一张current-phase Task；初始phase-planning batch仅允许唯一新建`TASK-Pn-00` owner加同range新建的`planned/ready`成员卡。后续阶段计划修订要求唯一已存在的`phase-plan-amendment-owner`、稳定逻辑Task ID、完整Diff base及仅`planned/ready`且无implementation SHA的成员；active/done成员改写、纯删除与重复路径均拒绝。选择owner后仍按其Diff base执行scope/impact。Provider结果必须来自真实授权运行，不能由本地PASS推断。

CI 可用 `uv run python scripts/check_docs.py --discover-task-from <event-base-sha> --check-diff --report build/traceability/ci-current-task-report.json`从一次 PR/push event range发现唯一 current-phase Task；本地 Task验收仍使用显式 `--task`。两种入口最终都使用 Task Card内的 immutable `Diff base`，不能把 event base当作 Task scope base。

## P2 历史执行证据

TASK-P2-03本地39项聚焦、319项全量和6/6 foundation均PASS；exact GitHub required `validate`与artifact也已核验，Task=`done`。工程smoke仍不是业务Solver/Validator/Benchmark证据。

TASK-P2-04本地证据为6/6 formal machine checks、13个mutation、11个C-ID、14个hard violations和6个duration/order examples；implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的exact GitHub run `32350068318` / required job `96367085099` / artifact `9399519368`复现该报告和38-path/6-row/0-issue Task report，故Task=`done`。本Task未修改Backend、合同Schema、fixture bytes、dependency、objective或Benchmark。

TASK-P2-05已形成C-001/003/004/010/011 core CP-SAT、完整candidate映射、formal Validator consumer、fixed-seed property与独立tiny oracle。Local acceptance为64 focused、360 full、Ruff/Pyright 0、core/formal各6/6、治理49 paths/6 rows/0 issues、compose/build/immutable PASS；implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的run `32354050257` / job `96379299455` / artifact `9400957897`精确复现证据，Task=`done`。

TASK-P2-06已把precedence/calendar/release/material/transport提升为C-002/005/006/009模型；TASK-P2-07再形成COMPLETED/RUNNING facts、HARD exact lock、SOFT metadata-only的C-007/008模型。Implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的exact provider evidence已闭环，Task=`done`；TASK-P2-08已在closure基线上启动，后续Task仍未授权。

TASK-P2-08把唯一OBJ-001精确建模为priority-weighted tardiness seconds，并由GlobalCpSatStrategy以显式Simulation Policy/Limits一次调用完整Backend；所有candidate必须经formal Validator PASS。70 focused、395 full及`objective-strategy-report.v1` 7/7本地PASS，implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的run `32438785162` / job `96645152864` / artifact `9431673977`精确复现并闭环为`done`；tiny timing不得作为Benchmark或SLA。

TASK-P2-09以`15c298f343a47db2a922544944ff5e02e4ca72d9`为Diff base启动。七个Scenario/Profile/assembler/policy/solver version及P0/P1 asset清单摘要已冻结；允许范围只覆盖新correctness assets、`simulation.scenarios`编排、四类测试、CI evidence和治理文档。Planning/Application/Generator、Problem/Solver/Validator语义、Schema、dependency、Benchmark与P3保持只读。

本地correctness实现使2个Golden和5个matrix case全部OPTIMAL且formal Validator PASS，固定7组Import/Snapshot/Problem hash；Hypothesis row-order/fresh Validator property与11个formula-free exact C-ID mutation均PASS。45 focused、427 full、8/8 machine、Ruff/Pyright、全部历史reports、Compose/build及58-path治理均PASS；implementation exact required run/artifact已复现同一证据并闭环为`done`。

用户于2026-08-21明确授权TASK-P2-10；clean/provider-verified Diff base为`0e4f6630412889254a7bef41f487c24dc274ca9c`，其run `32443067388` / required job `96657446617` / artifact `9433118755`均success。当前只启动五算法identity/tie-break、完整candidate或明确heuristic failure、fresh formal Validator和CI report；既有Schema/Planning/Validator/correctness assets/dependency与Benchmark/Production/P2-11+保持冻结。

TASK-P2-10实现为5个versioned deterministic algorithms、35/35 complete candidate/fresh Validator/deterministic replay及5个zero-partial explicit failures；`reference-scheduler-report.v1`为7/7 PASS。13个Task-specific与441个full tests、Ruff/Pyright均PASS；implementation exact required run/artifact已精确复现17/17 reports并闭环为`done`。Global comparison/XS-S-M/threshold、Export、Production fallback和P2-11+仍未启动。

用户于2026-08-21明确授权TASK-P2-11；clean/provider-verified Diff base为`41e958b771f2664b1ac50867903a30b73627878d`，其run `32450216908` / required job `96677202782` / artifact `9435421360`均success。当前只启动additive KPI/manifest合同、validated solution reporting和不可发布internal package；ChangeReport/BenchmarkRunner、P3 state/persistence/approval/publish及P2-12～14保持冻结。

TASK-P2-11链路为`Snapshot/Problem → validated PlanningSolution + ValidationReport + SolverReport + ImportQualityReport → KPI v2 → p2-internal-export.v1`。Machine report执行8项确定性、Schema/sample、血缘、tamper/mixed-run、原子写入/清理和状态边界检查；它不创建ScheduleVersion或ExportJob，也不产生可发布artifact。Global schema set现为additive `2.5.0`，既有document版本与bytes不改。Implementation `546292831c3bd52185687a4c646c10ae10541ae2`的required run `32454693799` / artifact `9436863185`已精确复现output 8/8、18/18 reports与58 committed/0 working paths，Task=`done`；P2-12不自动启动。

用户于2026-08-21明确授权TASK-P2-12；clean/provider-verified Diff base为`58db14e8f18fb50866fb757d4c89e76fef1141f1`，其run `32455399561` / required job `96691604529` / artifact `9437086153`均success。当前只启动versioned XS/S/M benchmark profile/baseline、同Problem/Validator/KPI的Global与五Reference比较、环境/规模/时间/质量/内存报告和CI XS artifact；L/XL、Production capacity/SLA、P2-13/14与P3保持冻结。

TASK-P2-12已形成严格Profile/Report/Baseline v1、确定性source-shaped generator、warm-up/repetition/median/p95、环境签名、Global/五Reference comparison、`BENCHMARK_WARNING`和immutable baseline规则。XS/S/M报告绑定三个固定Problem hash并均为8/8 PASS；implementation `01e7f4bdca88fc903e7caa771f875fc1a70ff357`的run `32460861563` / required job `96707353990` / artifact `9438899443`已复现19/19 PASS与49-path治理，Task=`done`。该证据只属development/simulation，OPEN-011/012保持OPEN，P2-13/14与P3未启动。

用户于2026-08-21明确授权TASK-P2-13；clean/provider-verified Diff base为`59f3b013a4be7bd11d054e8464886b3cde791602`，其run `32461665177` / required job `96709654227` / artifact `9439159396`均success。当前只编排已发布的P2公开边界，重放correctness与XS/S/M并聚合Validator/KPI/SolverReport/Export、四类拒绝和CI artifact；不得混入remediation、Exit READY、P2-14或P3。

TASK-P2-13本地已形成`p2-vertical-slice-report.v1`与`p2-gate-semantic-projection.v1`：两次完整replay均PASS，七场景、XS/S/M、Global+五Reference、formal Validator、KPI/SolverReport、internal Export和四类拒绝全部闭环。聚焦30项与全仓476项测试PASS，11项Gate checks全部PASS且无blocking gap；exact implementation provider形成前Task仍为`in_progress`，P2-14/P3保持未启动。

Implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的required run `32465737712` / job `96721819879` / artifact `9440650646`已精确复现20/20 JSON、Gate 11/11与37-path治理证据，故TASK-P2-13=`done`。P2仍为`active`，P2-14仍是未授权的唯一最后Exit Audit，P3未进入。
