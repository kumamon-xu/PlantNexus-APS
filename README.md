# PlantNexus APS

## TASK-P5-21 — empty-selected portfolio integration Gate

TASK-P5-21已获独立授权，不可变Diff base为`d7779c014351d41909322b967c5c8eca68713e8b`。P5-02的provider-verified topology仍为selected=`[]`、9项`DEFERRED`和18张`cancelled` owner卡；本Gate因此不调用P5-03～20，而是以空组合identity证明未选能力没有进入执行图。

新增`p5-portfolio-gate-report.v1`以PHASE_GATE独立重放Global-only strategy、formal Validator、13个mutation、XS/S/M development Benchmark和两轮P4 vertical slice，并对C-012～C-018逐项要求`UNSUPPORTED_CAPABILITY`。本地报告为12/12 checks、7个exact rejection、22个P4 Backend stage、10个browser spec execution、10次fresh Validator、10份complete ChangeReport，`issues=[]`、`blocking_gaps=[]`；Backend corrective全量为860/860 PASS。首次本地调用因显式把`PLANTNEXUS_CODE_COMMIT`设为`uncommitted`而被Production default-deny配置前置拒绝；移除该错误覆盖后同一Gate完整PASS。首次全量测试还发现Gate直接import owner违反application边界，现已改由owner machine contracts执行并通过corrective全量；没有修改既有断言、P4 owner或放宽比较。

CI在既有68-step FULL路由中的P4 Gate step后追加执行P5报告器，保持P4冻结evidence和步骤计数不变；machine artifact会包含exact commit下的P5报告。首次implementation candidate `e0dee8544a27adcae7ca98fabe2665452bf38d4d`的run `33402484533`在Repository test suites按设计fail closed：新integration fixture写死`uncommitted`，与CI注入的exact SHA不一致；corrective只让fixture消费当前受控commit identity，不放宽Gate。第二个candidate `d00386f42fbd366afa94dae4cc93096c0242ce0e`的run `33403931397`已通过全量Backend和P4-13的8项功能检查，但历史P4-13 scope脚本把本Task三个新增Backend Gate文件误归为P4-13越界，required `validate`继续fail closed；新corrective仅在临时detached worktree中隔离这三个精确P5路径后运行原封不动的P4-13脚本，并继续消费本次fresh browser/API/build evidence。TASK仍`in_progress/provider pending`。即使本Gate最终PASS，也不是P5 Exit Audit，不自动启动TASK-P5-22，不形成P6+、Production/UAT、真实approval authority、external publish/integration、deployment或capacity/SLA。

## TASK-P5-02 — portfolio resolution and phase-plan amendment

用户已另行授权TASK-P5-02。该Task只消费TASK-P5-01 exact report，不重新选择portfolio：九项决定仍全部为`DEFERRED`、selected=`[]`。P5-03～20的九条合同/implementation链因此原子终结为`cancelled`；没有selected能力Task被保留或启动。P5-21的动态依赖已解析为唯一直接依赖`TASK-P5-02`，P5-21与P5-22均继续`planned/NOT_STARTED`并仍需各自授权。

机器可读的[`p5-portfolio-amendment-manifest.v1`](docs/core/p5-portfolio-amendment-manifest.md)绑定不可变Diff base `01b8918db62cc9f5c4421d0b90d93151ddc552f1`、P5-01 implementation/closure、九个decision fingerprint、十八张terminal Task和resolved DAG。Manifest为10/10 checks、`issues=[]`、`blocking_issues=[]`；tracked implementation仅包含三份公开治理Markdown。

Implementation `ed9ee75122341c1a71b641edc445e2a58cac70de`的run/classify/docs/required=`33389105900`/`99478355746`/`99478399695`/`99478441483`全部成功，FULL `99478400881`按DOCS_ONLY正确跳过，required app=`15368`。Public-doc/profile artifacts `9756735835`,`9756730213`的下载ZIP digest与Provider分别一致为`sha256:bbda3d87f66e92ca2be68a7bb47cae53a59f007ff6712a2878fed39883a15fcd`、`sha256:1a32c6a134181501271ced74d8e513a1d06322b02392e532d1d14d180062b303`；证据精确复现3 paths、4/4 profile、1/1 public-doc、77→78 documents和0 issues。本提交只作evidence-only closure，closure自身仍须post-push exact Provider。

本计划写回不改变C-012～C-018的`UNSUPPORTED_CAPABILITY`、Global唯一已形成策略或P4 ExecutionEvent/ReplanRequest/freeze/OBJ-002/ChangeReport/Execution Simulator边界。OPEN-001～015、SIM-ASSUMPTION-001～020和RISK-001～017保持原状态；P6+、Production/UAT、真实approval authority、external publish/integration、deployment及capacity/SLA均未形成。

## TASK-P5-01 — capability evidence qualification

P5-01以不可变Diff base `4ccb2ed99ffe73abeb0462efff4a5342cd7c5522`建立versioned qualification profile、raw evidence manifest和九份独立decision record。真实需求材料本次未提供；selection采用五项事实`ALL_TRUE`并交叉校验证据源的qualified/replayable状态，缺失或不满足即fail closed为`DEFERRED`，unknown version、hash tamper、source混用或声明/计算不一致则Task级失败。当前Secondary Resource、Sequence-dependent Setup、Material Competition、Batch、Split/Merge、Buffer、Preemption、Decomposition、Rolling Horizon均为`DEFERRED`，selected portfolio为空，TASK-P5-02未获授权且不会自动启动。

机器报告本地为11/11 checks、`issues=[]`、`blocking_issues=[]`；12项聚焦unit/integration测试通过，并重放冻结的P2 XS/S/M，逐项保留runtime、memory、model size和quality原始开发观察。C-012～C-018仍显式`UNSUPPORTED_CAPABILITY`，Global仍是唯一已形成策略；未修改PlanningProblem、Solver、Validator、Schema/migration、dependency/lock、state/workflow、CI或任何候选实现，也未新增数值SIM假设。P4 ExecutionEvent/ReplanRequest/freeze/OBJ-002/ChangeReport/Simulator保持冻结回归边界；P6+、Production/UAT、真实authority、external publish/integration、deployment和capacity/SLA均未形成。

首个candidate `c3761d0505690567ab6b60be1d04041dab0c0652`的FULL run `33380357486`保留为失败证据：唯一失败是P4 frozen evidence拒绝两份新增`backend/**`测试。Direct corrective `88fb9f53ab5425d72ee6659188b689a26d0e387a`只把同一12项测试迁到仓库级P5 test collection，不改P4脚本/Task或CI workflow；其run/classify/FULL/required=`33383710010`/`99461500612`/`99461537473`/`99463769376`全部成功，required `validate`由GitHub Actions app `15368`提供。

Machine/profile artifacts `9754995093`,`9754731890`均未过期，下载ZIP SHA-256与provider digest逐字一致为`sha256:766163e4b516b1645bc985575e4ab3b113d32dd20d8ef77671cc56335f17a133`、`sha256:06caf0b3a9c448e6e9e1af7c01828edbf569e9bbfc810571c40111e2396515da`。Machine artifact的54个JSON全部可解析、43个commit字段全部exact且无非空issue/gap/error；P5 report精确绑定Task、不可变Diff base、HIGH_RISK、四个Impact Rules、11/11 checks、九项DEFERRED与`selected=[]`。本提交仅作tracked evidence-only closure；其自身仍须post-push exact provider，TASK-P5-02不会自动启动。

## TASK-P5-00 — P4→P5 transition and complete P5 plan

用户已明确批准P4→P5。最小承接检查只确认P4 evidence-only closure `892c46d660a6bf3cde8ed473199f38746d041e47`仍同时是当前`main`、`origin/main`与remote `main`，ahead/behind=`0/0`、working tree clean、P4无active Task、Exit=`READY`且`blocking_gaps=[]`、无未关闭blocking项，required status check仍为GitHub Actions app `15368`提供的`validate`。没有重新运行P4 Exit Audit、下载/解析P4 artifact、重建evidence或修改P4 Task。

P4 Milestone现关闭为`completed`，P5 Milestone激活为`active`。TASK-P5-00只建立23张Task卡与治理：P5-01逐项评价Secondary Resources、Sequence-dependent Setup、Material Competition、Batch、Split/Merge、Buffer、Preemption、Decomposition和Rolling Horizon；P5-02把selected链保留、deferred链以证据化`cancelled`终结；每个selected能力再独立完成合同包和Solver/Strategy+独立Validator vertical slice；P5-21为selected portfolio Gate，P5-22为最后的独立Exit Audit。TASK-P5-01～22均未启动。

现有C-012～C-018及Decomposition/Rolling仍未形成支持能力。每条selected链必须另获授权、冻结新的40字符Diff base，并独立提交ADR、additive Schema、Capability Contract、正反Fixture、Benchmark、default-off Feature Flag和双exact provider evidence。ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport与Execution Simulator保持P4冻结边界。Multi-Factory、alternative routing扩展、tools/fixtures专用语义、Hybrid、P6+及Production/UAT/真实authority/external publish/deployment/capacity/SLA明确排除。

Implementation `a316d7a5ebf2e8c7e33da46cf1d7c08f2dfbdfa3`的run/classify/docs/required=`33373013523`/`99428152667`/`99428185042`/`99428242533`全部成功，required由GitHub Actions app `15368`提供。Profile/public-doc artifacts `9750780227`,`9750786965`均未过期，下载ZIP SHA-256与provider digest逐字一致为`sha256:2a93283ffb9cfb59fd61e68dd4ededcfbcd27b273c2bef99657c88feaa3a6848`、`sha256:bd146736ea4431ae48fd9d93ccdce43273005f9fbbc6cf61d39752b49beac3ff`。Artifact精确绑定不可变Diff base `892c46d660a6bf3cde8ed473199f38746d041e47`、implementation SHA、5个公开Markdown路径、`DOCS_ONLY`、4/4 profile checks、1/1 public-doc check与`issues=[]`。

本提交是TASK-P5-00的tracked evidence-only closure，仅回写`README.md`与`docs/README.md`中的上述implementation证据，不扩大实现范围。Closure自身仍须通过post-push exact provider复验；TASK-P5-01保持`planned`且不会自动启动。

## TASK-P4-15 independent P4 Exit Gate Audit

TASK-P4-15以P4-14 evidence-only closure `60ac4c17c6de514c036be7bac63e66da589bfb4c`为不可变Diff base，独立复核P4 first-parent拓扑、required `validate`、GitHub Actions app `15368`及全部provider artifact。审计覆盖41个提交、42个push run（37 success、4 failure、1 cancelled）和67个未过期artifact；下载后的ZIP SHA-256全部与provider digest一致，1,134份成功链JSON、981份machine report和80份browser report均无SHA/语义/issue/gap漂移。四个历史失败与一个取消run完整保留，并分别由后续direct corrective commit闭环。

fresh本地重放通过834项Backend、18 files/78项Frontend、主Chromium 17/17、P3 Gate 12/12×2、P4 Gate 5/5×2、37个machine命令、XS benchmark及P2/P3/P4 Gates。P4 Gate为14/14、两轮22 stages/176 subordinate checks、10个连续场景step、16个标准event、10次fresh Validator和10份complete ChangeReport，`blocking_gaps=[]`。基于这些独立证据，本地P4 Exit结论为`READY`；机器摘要见`docs/p4-exit-gate-audit-observations.v1.json`。该结论不切换P5，也不形成Production readiness、UAT、真实event/approval authority、external publish/deployment或capacity/SLA；implementation与后续evidence-only closure仍各自必须通过exact provider。

首个implementation candidate `aedc682a5a82e135c63ce20f1c85009282ae7f42`的run `33366070434`在P3 Gate replay 1出现一次locale选择时序失败，required按设计fail closed；两份未过期artifact及screenshot/video/trace均已下载保留，digest一致。Direct corrective implementation `3637f514947397f7ba04a6ff3061a48f1809b44e`的run/classify/FULL/required=`33367097943`/`99409899613`/`99409926891`/`99412480503`则全部成功并由GitHub Actions app `15368`提供required `validate`。Machine/profile artifacts `9748939618`,`9748651059`未过期，provider与下载ZIP digests一致为`sha256:be149288c052c84f314129bc2dbf63c9fef4608eae5de009dd51e959a93a595a`、`sha256:e853cd63c9e66d318dd44432ce2eff17d3d53ccb26481e0198fa52abf34f5946`；53份JSON无parse/status/issue/gap/SHA漂移，累计Task diff仍为8路径、`IMPACT-DOCS`、19 checks、`issues=[]`。TASK须通过本次evidence-only closure的独立exact provider后才标为`done`。

## TASK-P4-14 P4 Vertical Slice Gate

TASK-P4-14以不可变Diff base `ea05c3d9e94af91ae4525e5fbf1087a4a4198a15`形成`p4-vertical-slice-report.v1`。PHASE_GATE对P4-02～12的11个公开Backend owner边界执行两次fresh replay，完整保留22份stage运行、176个subordinate checks及raw reports；五类连续disruption合计10步、16个标准event、10次fresh Validator PASS和10份complete ChangeReport。另有两轮隔离Chromium各5/5，`p4-playwright-semantic-projection.v1`指纹一致，并严格消费冻结的TASK-P4-13 frontend report。

本地聚合结果为14/14、`blocking_gaps=[]`、P2/P3 Gate regression PASS、四类exact fail-closed rejection PASS。Runtime timing/memory与派生artifact identity只从版本化业务语义投影中排除，所有原始证据继续保留；已序列化P3 Gate的JSON object key顺序仅为复验入口正规化，不改变任何值、array顺序或raw report hash。本Gate不修改P4-01～13业务、Schema/migration/dependency/lock、fixture expected、ADR或状态机；它不是P4 Exit Audit，TASK-P4-15仍`NOT_STARTED`，P5、Production readiness/UAT/真实authority/external integration/deployment/capacity/SLA均未形成。

Implementation `296c9b495c44ac4245649f143ba9d366c25b0b13`的run/FULL/required=`33360100486`/`99389677929`/`99391482358`已由GitHub Actions app `15368` exact成功。未过期machine/profile artifacts `9746591757`,`9746389508`已下载复验，provider与ZIP digests分别一致为`sha256:7a4645e064b00430b67eb7bf19cd7e668b3c0dc1f7d4542ee23abc7669e06ba3`、`sha256:a4028270dd0138fef240db1b1f936062e26eea971eeb7424e80718bbf4237f0a`；47份machine JSON全部PASS、0 issues/gaps/commit drift，profile为17路径FULL且`issues=[]`。TASK仍须通过本次evidence-only closure的独立exact provider后才标为`done`。

## TASK-P4-13 Replanning Workspace UI

TASK-P4-13从不可变Diff base `be2389594f3e224de3f5a73f4b8b62ffcffb5b7b`形成一个additive、Simulation/development-only的`/planning/replanning`工作台。浏览器以strict typed consumer读取P4-12的event timeline、ReplanRequest/attempt/result和ChangeReport投影，展示freeze half-open边界、before/after priority-weighted tardiness、OBJ-002 Stability及逐operation classification；query/response/resource/correlation/fingerprint任一不一致均fail closed。既有18条P3 route和12个P3 Chromium场景作为冻结子集继续复验。

`CANCEL/RETRY`只在服务端`allowed_actions`允许时挂载，并逐字绑定request fingerprint、attempt ID/number、expected PlanningRun state、hashed Idempotency-Key reference及显式确认/reason。网络或503造成unknown outcome时，浏览器仅在内存保留exact body/key，先refresh authoritative result；authority未变才允许same-body/same-key retry，变化则停止重试。Production runtime在任何read/action前default-deny；浏览器不计算event order、fact、freeze/effective lock、KPI、Stability、Validator或ChangeReport。

完整HIGH_RISK本地验收已通过：focused 19/19、Backend 821/821、Frontend 78/78、主Chromium 17/17（12个冻结P3 + 5个P4 positive/error/tamper/network recovery场景）、两轮P3 Gate各12/12、P2/P3 Gate 11/11与14/14、Ruff/Pyright、SCA/license、全部历史machine、XS Benchmark、Compose、前后端build及sdist/wheel。`p4-replanning-frontend-report.v1`为8/8、五个Impact Rules、`issues=[]`；Task治理为43 paths/5 rules/19 checks/0 issues且forbidden scope=0。首次错误工作目录Vitest、两次raw-label locator、裸`node` evidence、旧i18n loader、首轮Backend CI-step count及最初Task-diff临时文件失败均保留并在冻结allow-list内限定纠正。首个implementation candidate `18c0eb8967cfd7b11d7a9019fe72a221dfc0bd85`的run/FULL/required=`33354198989`/`99373143904`/`99373794071`又因新machine step从repository root调用frontend-relative脚本而被正确拦截；corrective `9a7d79b684ce066f784179e61bcd27f05c609fc9`只固定该step working directory，其run/FULL/required=`33354756522`/`99374693595`/`99376087137`已由GitHub Actions app `15368` exact成功。未过期machine/profile artifacts `9744915726`,`9744760335`已下载，ZIP SHA-256与provider digest逐字一致为`sha256:549da2d23cc821019bfdcfb6ba37f642b3d17663780a215021df0fff4559136e`、`sha256:4d9f2f9d0a54059deb28b871fde4b22696dfeb14e857e76fefab48c7818e44b9`；49个JSON、exact Task/SHA/Diff base、五个Rules、8/8 checks、0 issues、17/17主Chromium、两轮12/12与P2/P3 Gate均一致。本evidence-only closure据此记录完成结论，但其自身仍须post-push exact provider复验。Schema/migration/dependency/lock、backend business/state pair、Solver/Validator/Simulator、external publish、P4 Gate、P5及Production identity/authority/deployment/capacity/SLA未修改或形成；TASK-P4-14不会自动启动。

## TASK-P4-12 Dynamic Replanning HTTP API

TASK-P4-12已从不可变Diff base `f4a54d3bb065b5cc8b51c450ffdc435bcc77d384`形成Simulation/development-only `dynamic-replanning-http.v1`：8个P4 path、9个operation覆盖ExecutionEvent append/get/stream query、ReplanRequest create/get/cancel/retry/result与ChangeReport read。POST严格消费已发布`execution-event.v1`/`replan-request.v1`；GET使用fingerprinted `dynamic-replanning-query.v1`；cancel/retry使用`replan-attempt-action-http.v1`绑定hashed Idempotency-Key、request fingerprint、attempt ID/number及预期PlanningRun state。ReplanRequest仍无独立state machine。

路由在application lookup前执行server-derived capability与exact planning-scope授权，Production在provider/application lookup前审计并default-deny；raw bearer/idempotency key不进入application context。结果必须通过`dynamic-replanning-response.v1`的operation/resource/correlation反向绑定，unknown outcome固定503且要求query-before-retry。P3原18-operation作为精确冻结子集继续复验；router不导入application/domain/repository，不投影fact、计算freeze/OBJ-002、调用Solver/Validator或推进状态。

完整HIGH_RISK本地验收已通过：Task-specific `14 passed`、完整Backend `821 passed`、Frontend 67项与主E2E/P3 Gate两轮各12/12 Chromium、Ruff/Pyright、全部历史machine、XS Benchmark、P2/P3 Gate、SCA/license、Compose及前后端build；`p4-replanning-api-report.v1`为8/8、五个Impact Rules、`issues=[]`，治理为35-path/5-rule/19-check/0-issue且forbidden scope=0。Implementation `7cce9744783acc7cf80e0cecafb6f9e144fe085f`的run/FULL/required=`33347790649`/`99355189991`/`99356475314`已由GitHub Actions app `15368` exact成功；未过期machine artifact `9742718240`（digest `sha256:2ca6df933fee54a348b370b3fa2179dbaef0d3e48d477910f444455da27c0449`）和profile artifact `9742570373`（digest `sha256:baad74c370a231d6933fa4d49cbd19945994d82ab39b3adb824093f9758dc229`）已下载复验，精确绑定SHA、Diff base、35-path FULL profile、五个Rules、8/8 checks、0 issues及P2/P3 Gate。本evidence-only closure据此记录完成结论，closure自身仍须post-push exact provider；Schema/migration/dependency/lock、domain/application/Solver/Simulator语义、state pair、Frontend runtime/UI/client、external publish、P5和Production identity/authority/deployment/capacity/SLA未修改或形成，TASK-P4-13不会自动启动。

## TASK-P4-11 ChangeReport read model and internal export

TASK-P4-11现从不可变Diff base `45b12d9a67ce5ef1680a47fecdc68705355af226`形成Simulation/development-only ChangeReport read/export slice。Versioned只读服务在任何repository lookup前完成plane/capability/scope检查，再以exact Replan result、P4 ScheduleVersion、ChangeReport、SolverReport、fresh Validation与before/after KPI references绑定查询；filter、operation-id cursor和page顺序稳定，读取不调用Solver、不写状态且不改变immutable report bytes。

P4 `export-job.v3`沿用P3五个state/六个pair、lease/idempotency/audit语义，只为already-PUBLISHED `schedule-version.v2`增加exact ChangeReport reference和`p4-dynamic-replan-export.v1` profile。独立worker生成manifest-bound `export-manifest.v3`：13个payload、canonical JSON/CSV、安全确定性5-sheet XLSX、manifest-last目录与deterministic ZIP；verified download逐字绑定job/attempt/ScheduleVersion/ChangeReport/audit/storage。P3 v1/v2 package bytes和profile保持冻结；任何混合lineage、tamper、partial write、非PUBLISHED source或Production/external请求均fail closed。

本Task没有新增Schema、migration、dependency/lock、state pair、自动approval/publish/export、API/UI或external storage。冻结`0004`表的profile列只作为已批准的兼容存储判别值，完整v3 carrier仍按canonical document bytes和SHA保存并在load时复验；这不形成Production authority、deployment、UAT、capacity/SLA或P5能力。TASK-P4-12不会自动启动。

完整HIGH_RISK本地验收已通过：Task-specific `18 passed`、完整Backend `806 passed`、Frontend 67项与三轮各12/12 Chromium、全部历史machine、XS Benchmark、P2/P3 Gate、SCA/license、Compose及前后端build；`p4-change-report-output-report.v1`为8/8、`issues=[]`，治理为32-path/8-rule/19-check/0-issue，P2/P3 Gate为11/11、14/14且`blocking_gaps=[]`。首次完整Backend运行得到`800 passed, 1 failed, 5 errors`，原因是旧P3原始substring边界扫描器把标识符`_FINGERPRINT`中的`ERP`误判为外部集成；限定纠正仅将内部常量改名为`_SHA256_REFERENCE`，P3目标回归与806项全量随后通过。全局npm为12.0.2，Frontend证据使用仓库冻结的npm 11.17.0执行，未修改依赖或lock。

Implementation `7d685d91e5011cdb4b3289ef10a9a2355c53570b`的run/FULL/required=`33156391439`/`98800085239`/`98801664096`已由GitHub Actions app `15368` exact成功。未过期machine artifact `9679951468`（digest `sha256:59088ba24779ffb2cef9d8d225c2897d50a8d4ef598cf4ecb66037354bf97d80`）与FULL profile artifact `9679763686`（digest `sha256:7a89878a6fecc58657633577eb8d6caebc06b97eadd9ea90fb9efed79e94d8ba`）已下载，ZIP SHA-256与provider digest逐字一致；报告精确绑定Task、SHA、Diff base、八个Impact Rules、8/8 checks、`issues=[]`、FULL 32-path profile及P2/P3 Gate。本evidence-only closure据此记录TASK-P4-11完成结论；closure自身仍须post-push exact provider复验，TASK-P4-12不会自动启动。

## TASK-P4-10 five-disruption continuous replay

TASK-P4-10已从不可变Diff base `8bbe0c643571e578ec637f135a2390c90de02512`形成versioned `SIM-P4-DISRUPTION-REPLAY-001@1.0.0`：同一fixed-seed stream按Urgent Order、Machine Failure/Recovery、Material Delay/Ready、Processing Duration/Remaining变化与Early Completion五步输出8个标准`execution-event.v1`。每步消费前一步的明确Snapshot/Version test baseline，绑定独立ReplanRequest/PlanningRun/fresh Validator/new DRAFT/ChangeReport evidence；baseline推进固定标记`SIMULATION_NON_PRODUCTION`、`authority_claim=NONE`，不构成自动批准或发布。

`p4-disruption-replay-report.v1`组合并复验P4-09 Simulator、P4-04 Event→fact/Snapshot与P4-08 Replan→Validator→DRAFT/ChangeReport既有owner machine contracts；same-seed语义投影一致（raw runtime evidence完整保留）、checkpoint partition、Schema、tamper/coverage/Production拒绝与每步六项fact/lock/report invariant均为fail closed。资产中的seed `20260828`、900秒freeze、event offsets、urgent priority/quantity、duration与tardiness/stability值都是bounded synthetic correctness值，不是Production分布、policy、capacity或SLA。

完整HIGH_RISK本地验收已通过：Task-specific `14 passed`、完整Backend `786 passed`、Frontend 67项与三轮各12/12 Chromium、全部历史machine、XS Benchmark、P2/P3 Gate、SCA/license、Compose/build，以及27-path/5-rule/19-check/0-issue治理；`p4-disruption-replay-report.v1`为8/8且`issues=[]`。首次Vitest从仓库根目录误调用，因未加载Frontend配置而失败；随后按CI冻结的`frontend`工作目录重跑67/67 PASS，未修改断言或配置。Schema、migration、dependency/lock、core Solver/Validator、API/UI、P4-11+、P5与Production readiness/authority/external integration/capacity/SLA均未修改或形成。

首个implementation candidate `7e558666f89ec7ab2314ddd35320bc210d04a8f1`的run `33148120102`因既有P3浏览器locale选择在2 workers下11/12而被required `98774673763`正确拦截；失败artifact与media保留。限定corrective `f475a13baf22a0759c19967f6264d8d0b71e47d5`只把主E2E及两轮P3 Gate固定为1 worker，保留零retry和原断言；其run/FULL/required=`33148902189`/`98776094074`/`98777724803`已由GitHub Actions app `15368` exact成功。未过期machine artifact `9677080681`（digest `sha256:781240ef2b20791b4edc61509b1b95ddcffac57abfa3224ae9bd0518a1a4a46a`）与profile artifact `9676878307`（digest `sha256:ed6bc45f16ebd928143196e4d082eb0e2d0da6950fc976b9aa6f10bd82c0d24c`）已下载，zip SHA-256与provider digest逐字一致；报告精确绑定Task、corrective SHA、原始Diff base、五个Impact Rules、8/8 checks、`issues=[]`、27个changed paths及P2/P3 Gate 11/11、14/14且`blocking_gaps=[]`。本evidence-only closure据此记录TASK-P4-10完成结论；closure自身仍须post-push exact provider复验，且不会自动启动TASK-P4-11。

## TASK-P4-09 deterministic Execution Simulator core

TASK-P4-09已从不可变Diff base `e4874735166be93473ccaebaf1090980db957552`实现Simulation-only Execution Simulator core：PUBLISHED ScheduleVersion reference、Scenario/Profile/Generator/Simulator版本与fingerprint、seed、versioned event schedule和virtual clock先形成完整run identity；同刻事件使用named-child-seed rank与event key稳定排序。全部事件在任何副作用前生成canonical `execution-event.v1` bytes并通过P4-04 strict prefix validation，随后唯一输出边界是`ExecutionFactProjectionService.ingest_event`兼容端口。Prefix checkpoint/restart会重算run/prefix fingerprint，manifest只能消费调用者显式提供的fact checkpoint reference。

完整HIGH_RISK本地验收已通过：Task-specific `12 passed`、完整Backend `771 passed`、Frontend 67项与三轮各12/12 Chromium、全部历史machine、XS Benchmark、P2/P3 Gate、SCA/license、Compose/build，以及24-path/4-rule/19-check/0-issue治理；`p4-execution-simulator-report.v1`为8/8且`issues=[]`。FULL CI新增不可跳过的Simulator machine step；Schema、migration、dependency/lock、P4-04入口、Solver/Replan、ScheduleVersion state、API/UI及P0～P3历史bytes均未修改。三事件/两个同刻offset/固定seed与origin只是SIM-ASSUMPTION-018 correctness vector；五类连续disruption仍归TASK-P4-10且未启动，P5 advanced capability会被显式拒绝，Production source/authority/external integration/deployment/capacity/SLA仍未形成。

Implementation `6b293720d795ae7dcb2f6453dc999471d3586b94`的run/FULL/required=`33141091252`/`98751935625`/`98753074526`已由GitHub Actions app `15368` exact成功。未过期machine artifact `9674090110`（digest `sha256:521fec38cca4a625cc5dcacb6624e472b34dab1cf5fc76a5518c725cf5287e4b`）与profile artifact `9673955596`（digest `sha256:7851c45a7abf3610030846ca27dd290ee9ef2a2949fffb02856c27dcecc4a4b4`）已下载，zip SHA-256与provider digest逐字一致；报告精确绑定Task、SHA、Diff base、四个Impact Rules、8/8 checks、`issues=[]`、24个changed paths及P2/P3 Gate 11/11、14/14且`blocking_gaps=[]`。本evidence-only closure据此记录TASK-P4-09完成结论；closure自身仍须post-push exact provider复验，且不会自动启动TASK-P4-10。

## TASK-P4-08 replan application / new DRAFT

TASK-P4-08现已在不可变Diff base `77981f0564d91dfb57fee6e3792f4989bdb51d32`上形成Simulation-only application闭环：先以独立事务持久化immutable ReplanRequest、attempt与审计，再从exact current PUBLISHED及其PlanningSnapshot重建Problem，复用P4-05 effective locks、P4-07 lexicographic Solver、fresh独立Validator和P4-06 ChangeReport precheck，最后在第二个原子事务中同时写入new DRAFT ScheduleVersion、完整result envelope与审计。Exact idempotency replay不重复调用Solver或产生新DRAFT；stale current、KPI不一致、竞争失败、审计失败和无candidate terminal结果均fail closed且不留下partial result。

完整HIGH_RISK本地验收已通过：focused `22 passed`、完整Backend `759 passed`、Frontend 67项与三轮各12/12 Chromium、全部历史machine、XS Benchmark、P2/P3 Gate、SCA/license、Compose/build及32-path/6-rule/19-check/0-issue治理；`p4-replan-application-report.v1`为8/8且`issues=[]`。Implementation `f664517e5f17dc2453444adf9a5503ff1393530e`的run/FULL/required=`33137388411`/`98740332159`/`98741555347`已由GitHub Actions app `15368` exact成功；未过期machine artifact `9672684493`（digest `sha256:4d1ef3e89e32dd060e1cb946da119202f688adb9dcb7f2bd7536f2ee1c77e2f9`）与profile artifact `9672545763`（digest `sha256:a9c4e44cdab8fab6bbdac19c7de08b2826b4286602c7fc376e2e76a89d8e3429`）已下载复验，精确绑定Task、SHA、Diff base、六个Impact Rules、8/8 checks、`issues=[]`及P2/P3 Gate。本evidence-only closure据此把TASK-P4-08标为`done`；closure自身仍须post-push exact provider复验。

Schema/migration/dependency/lock、P4-07 Solver公式、Simulator/scenario、API/UI、P3 approval/publication/export及状态集合均未修改；P4-09不会自动启动，P5与Production readiness/UAT/真实authority/external publish/deployment/capacity/SLA仍未形成。

## TASK-P4-07 lexicographic replan solver

TASK-P4-07现已在不可变Diff base `e212ab7957d6bc5887048ee54809c8194d6e1eaf`上形成Simulation-only全局重排路径：同一完整C-001～C-011 CP-SAT模型按`Delivery/OBJ-001 → Stability/OBJ-002`四个整数分量→`Makespan/OBJ-003`执行六轮有界求解，每轮接受值以等式锁定后才进入下一轮。base schedule只作为Hint；Execution facts、显式HARD与freeze-derived HARD仍是约束。每轮candidate均由不导入CP-SAT/backend/reporting calculator的fresh独立Validator重算formal feasibility、事实/锁、objective与ChangeReport operation universe；结果以Schema-valid `solver-report.v2`及`p4-replan-solver-report.v1`机器证据输出。

完整HIGH_RISK本地验收已通过：P4-07 focused 48项、完整Backend `736 passed`、Frontend 67项与三轮各12/12 Chromium、全部历史machine、XS Benchmark、P2/P3 Gate、SCA/license、build/Compose，以及33-path/7-Impact-Rule/19-check/0-issue治理。首次全量回归暴露旧OR-Tools合法文件集合断言并以显式scope expansion纠正；首次Frontend evidence暴露本机npm 12.0.2偏差，随后用冻结npm 11.17.0完整重跑PASS。Implementation `cd77708299edbc6c7ab9abb6aed7ff6950a7f2ec`的run/FULL job/required job=`33131611010`/`98722212668`/`98723499160`已由GitHub Actions app `15368` exact成功；未过期machine artifact `9670605640`（digest `sha256:0623c54e61be4e0ce2e70ebf21926a78bdf956e73b1016de34d0da5fb8a22dde`）及FULL profile artifact `9670459898`（digest `sha256:90cfa27d5f9261a9bbb71de949b71bffb3183241c0b20412d7786730c4e4940c`）已下载复验，精确绑定Task、SHA、Diff base、七个Impact Rules、8/8 machine checks、`issues=[]`及P2/P3 Gate。本evidence-only closure据此把TASK-P4-07标为`done`；closure自身仍须post-push exact provider复验。

该P4-07实现本身不创建或持久化new DRAFT/ChangeReport/Request result，不改Schema、migration、dependency/lock、状态集合、Simulator、API/UI或export；P4-08随后仅按新的独立授权形成上方application闭环，P4-09+、P5 decomposition/rolling/hybrid及Production readiness/authority/external integration/capacity/SLA均未启动或未形成。

## TASK-P4-06 OBJ-002 Stability / ChangeReport completion

TASK-P4-06已按独立授权在不可变Diff base `d9d9f2fa2dbefe4c9942aaa8a943a93fdc7efd43`上实现Simulation-only纯整数`obj-002-stability.v1`、immutable `change-report.v1` builder、独立`change-report-precheck.v1`与`p4-stability-change-report.v1`机器证据。完整operation universe恰好一次分类为UNCHANGED/CHANGED/ADDED/REMOVED_BY_FACT；movement只由resource/start/end tuple决定，SOFT lock、changed existing、resource change、absolute start shift组成四元整数向量，before/after KPI、facts、reasons、freeze与完整lineage均可独立复算。HIGH_RISK本地验收已完整通过：Task-specific 21项、focused `64 passed`、完整Backend `724 passed`、Frontend 67项及三轮各12/12 Chromium、全部历史machine、XS benchmark、P2/P3 Gate、SCA/license、Compose/build、文档治理和26-path exact allow-list均PASS。

首个implementation `5c7d9a6a42b798f5219484f0fb19851f410c991e`的required run成功但artifact缺少显式Impact Rules envelope，故作为纠正链历史保留。Corrective implementation `10abdd105c697f61ba6c88078ae0ba28fed8a4e5`的run/FULL job/required job/artifact=`33126551137`/`98706008238`/`98707464048`/`9668755204`已由GitHub Actions app `15368` exact成功并下载复验；artifact digest为`sha256:64c20ceba56d5872d48d19088c4f9f889d08eb31766659c6b579d908dd4bc066`，精确包含Task、不可变Diff base、6个Impact Rules、8/8 checks与`issues=[]`。首个closure `9a87ca13bb7623159d68fb06efec2714c065dd79`/run `33127421798`因4个仅内部工作区可见的链接而被public-doc gate与required `validate`正确拒绝；该失败证据保留。本corrective evidence-only closure移除公开文档中的内部链接并据此把TASK-P4-06标为`done`；自身仍须post-push exact provider复验。

本Task没有修改Schema、migration、dependency/lock、CP-SAT objective/strategy、formal C-001～C-011 Validator、业务状态、application/API/UI/Simulator或P3历史。OBJ-002当前仅是reporting/completeness能力，不代表P4-07词典序Solver已形成；P4-07+、P5与Production readiness/UAT/真实authority/external publish/deployment/capacity/SLA均未启动或未形成。

## TASK-P4-05 Freeze Window completion

TASK-P4-05已按用户独立授权在不可变Diff base `e7b96e28913e7eb5be63ae4265c09f8281456b1c`上实现versioned `SIM-P4-FREEZE-001@1.0.0`、solver-neutral `effective-lock-projection.v1`、独立fail-closed precheck和`p4-freeze-window-report.v1`。HIGH_RISK本地验收覆盖900秒half-open boundary、COMPLETED/RUNNING、显式/derived HARD、SOFT、ADDED、stale/conflict/grid/plane与exact replay；implementation `2d0ca8723b18dc08a57d12f4e26db3fae9f46a35`的required run/job/artifact=`33077329890`/`98534856259`/`9648715231`已由GitHub Actions app `15368` exact成功并下载复验，故本evidence-only closure把Task标为`done`。Schema/migration/dependency/state pair、既有Problem builder/hash/formal Validator/CP-SAT保持冻结，OBJ-002、ChangeReport、Replan application、ScheduleVersion、Simulator、API/UI、Production、P5+与TASK-P4-06均未启动；closure自身仍须post-push exact provider复验。

## TASK-P4-04 ExecutionEvent fact projection completion

TASK-P4-04已按用户独立授权在不可变Diff base `3563bb236ce7b2c01794485110d4945a6e265105`上执行。当前实现只在Simulation plane形成两段原子边界：ingress事务append exact ExecutionEvent ledger+audit，projection事务把连续source-position prefix解释为canonical execution/material/resource/duration/lock facts并提交new immutable PlanningSnapshot+checkpoint+audit；Urgent Demand只能携带完整Raw Staging+MappingProfile并重走Normalization→Data Validation→Order Expansion→Snapshot。全部11种已批准event均有确定性/replay/negative证据，Schema/migration/dependency/state pair不变。

当前Task-specific 10项、application boundary与CI contract合计focused `12 passed`，完整Backend `654 passed`，Frontend 67 Vitest、主E2E及两轮Gate Chromium各12/12，全部历史machine、P2/P3双Gate、SCA/license、Compose和双build均PASS；`p4-execution-fact-projection-report.v1`为8/8且`issues=[]`。Implementation `47f55b41e370aa9d24fd9c987cff4663672c3ee8`的required run/job/artifact=`33066612047`/`98498125593`/`9644190441`已由GitHub Actions app `15368` exact成功并下载复验，故本evidence-only closure把TASK-P4-04标为`done`；closure自身仍须post-push exact provider复验。ReplanRequest、freeze window、OBJ-002、Solver/Validator、ChangeReport、ScheduleVersion、Simulator、API/UI、P5与Production/external authority/capacity/SLA均未形成；TASK-P4-05保持`planned`且不会自动启动。


## TASK-P4-03 Replan persistence completion

TASK-P4-03已获独立授权并在不可变Diff base `7b9bfc3069de5d3738e5cc5827d27d197ed3d226`上执行。实现增加additive `0005_replan_event_persistence`、7张Simulation-only关系表、5个plane-scoped repository边界和`p4-replan-persistence-report.v1`；本地machine evidence为9/9 PASS，完整Backend为643项、Frontend为67 Vitest及三轮各12/12 Chromium，P2/P3双Gate与52-path/6-rule/19-check/0-issue治理均通过。Implementation `60f8e8900ecab60f0d64311912ae27f09a4d002f`的required run/job/artifact=`33055784278`/`98462103078`/`9639720666`已由GitHub Actions app `15368` exact成功并下载复验，因此本evidence-only closure把Task标为`done`；closure自身仍须post-push exact provider复验。该持久化层只保存ExecutionEvent ledger、projection checkpoint CAS、immutable ReplanRequest、request→PlanningRun attempt→terminal result references与append-only audit，不解释事件、不投影事实、不生成ChangeReport/new DRAFT，也不调用Solver/Simulator或形成Production能力。P4-04在该closure时保持`planned`；当前已按新的独立授权完成，状态见本页顶部。

## P4 phase activation and TASK-P4-02

用户已明确批准P3→P4。TASK-P3-17独立Exit Audit的report/manifest均为`READY`、`blocking_gaps=[]`；audit implementation `201be9c6fd1b433a9d0a629a3ae7d4ffe1107476`和evidence-only closure `61eeacdd5efc20b2321750e1310e9e21561c9fc2`的直接拓扑、required `validate`、GitHub Actions app `15368`及未过期artifact均已exact复验。因此P3 Milestone现为`completed`，P4 Dynamic Replanning已激活。

PlantNexus APS 是一个面向单工厂、多车间场景的高级计划与排程（APS）项目。TASK-P4-00～11与TASK-P4-16均已形成provider-verified implementation/evidence-only closure；TASK-P4-12 implementation provider已exact通过，本evidence-only closure记录其完成结论并等待自身post-push复验。TASK-P4-13～15保持`planned`且未启动；Frontend replanning UI与Production readiness/UAT/真实authority/external publish/deployment/capacity/SLA仍未形成。

## 开始之前

Coding Agent 必须从 [`AGENTS.md`](AGENTS.md) 进入项目规则。项目规范、当前阶段和有界 Task Card 位于 [`docs/`](docs/README.md)。

## 版本基线

| 对象 | 当前值 | 含义 |
|---|---|---|
| Implementation spec | `0.3.0` | 当前权威实施规格版本 |
| Code | `0.0.0` | P0 工程骨架占位，不代表发布版本 |
| Business schema set | `2.8.0` | 九份P4 Simulation机器carrier逐字冻结；数据库migration head现增加consumer-only `0005_replan_event_persistence`，不改变Business Schema bytes |
| Python | `3.12` | `.python-version` 与 `pyproject.toml` 固定的运行时系列 |
| OR-Tools | `9.15.6755` | TASK-P2-03 exact runtime pin；只允许在 `planning/backends/cp_sat/` 使用 |

## TASK-P3-14 Vertical Slice Gate

TASK-P3-14以`6a3e02f00bf46f19915cb59c3c4af7daaac95be4`为不可变Diff base，聚合P3-02～13已发布机器边界、两次fresh Backend replay、两次独立Chromium replay、P2 Gate regression和四类exact rejection。`p3-vertical-slice-report.v1`保留完整raw subreport；stable semantic projection只排除显式runtime/derived identity，并在先验证允许集合后归一化并发审批的合法线程交错。任一报告、语义、拒绝或provider交叉检查失败都会写入`blocking_gaps`并非零退出。

在TASK-P3-14冻结时，完整本地验收为616项Python、54项Vitest、基础Chromium与两轮Gate Chromium各12/12、全部机器合同、P2 Gate/XS、Compose/build及56 paths/8 Impact Rules/19 checks/0 issues均PASS；P3 Gate为14/14且`blocking_gaps=[]`。Corrective implementation `54a25646053979a69734a3148030830d49c04c1e`的required run/job/artifact=`32931418903`/`98064264595`/`9593460266`精确全绿并复现全部Gate/Task/browser证据，故TASK-P3-14=`done`。该时点最终TASK-P3-17 Exit Gate Audit仍为`NOT_PERFORMED`/`planned`；该历史Gate不形成P4或Production identity、approval、publish、capacity、SLA或readiness。

## TASK-P3-15 Phase Plan Amendment Governance

用户已批准调整P3末段编号。TASK-P3-15以`06e7f794f486ac34c505237b847462c7c7c36d44`为不可变Diff base，只扩展治理validator与unit regression。Implementation `c84e1aa1a81473f65d9f7906a6d2c67a94e7bb2f`的required run/job/artifact=`32944633958`/`98102640242`/`9597967232`已下载复核26/0 paths、5 rows、19 checks、0 issues；evidence-only closure `1636fe9c909b728d49f9907ed9f53030b5921914`的run/job/artifact=`32948633841`/`98114798738`/`9599442770`也已下载复核37份JSON、48/0 paths、6 rows、19 checks和0 issues。因此TASK-P3-15=`done`，其失败/成功provider历史保持只读。

TASK-P3-16现实现默认`zh-CN`、可切换/恢复`en-US`及[`official-zh-cn-terminology.v1`](docs/frontend/official-zh-cn-terminology-map.md)的typed display adapter；`document.lang`、Ant Design locale、Intl格式、unknown raw fallback、双语a11y/Playwright与`p3-frontend-i18n-report.v1`均已由exact implementation/closure provider复验。API路径/key/operationId/state/command/error/C-ID/fingerprint和标准载体继续使用英文机器合同，package/lock零差异。TASK-P3-17已依据后续明确授权独立执行并由exact implementation provider支持为`done`；不会自动进入P4。

## 本地验收

需要 [uv](https://docs.astral.sh/uv/)。在仓库根目录运行：

```powershell
uv sync --locked
uv run ruff check .
uv run pyright backend/app backend/tests
uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property
uv run python -m app.planning.validation.problem_validator_check --root . --report build/validation/TASK-P2-04-formal-schedule-validator.json
uv run python -m app.simulation.scenarios.p2_correctness --root . --report build/validation/TASK-P2-09-correctness.json
uv run python -m app.simulation.baselines.reference_schedulers --root . --report build/validation/TASK-P2-10-reference-schedulers.json
uv run python -m app.exporters.contract_check --root . --report build/validation/TASK-P2-11-output-contracts.json
uv run python -m app.domain.execution_contract_check --root . --report build/validation/ci-p4-machine-contracts.json
uv run python -m app.infrastructure.replan_persistence_check --root . --report build/validation/TASK-P4-03-replan-persistence.json
uv run python scripts/run_benchmark.py --profile xs --report build/benchmarks/TASK-P2-12-xs.json
uv run python -m app.application.p2_gate_report --root . --repeat 2 --report build/validation/TASK-P2-13-p2-gate.json
uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json
docker compose --env-file .env.example config --quiet
uv run python scripts/check_docs.py
uv build
uv run python -c "import app; assert app.CODE_VERSION == '0.0.0'; assert app.SPEC_VERSION == '0.3.0'; assert app.SCHEMA_VERSION == '2.8.0'"
```

`scripts/check_docs.py` 当前同时检查结构性 Markdown、版本化 registries、REQ/NFR/ENG/TEST 等引用、Task 依赖、逐根 traceability 和 PROD_OPEN/SIM_ASSUMPTION 隔离。Task 进入 `in_progress` 时须把当时完整 HEAD SHA 写入 `Diff base`；影响覆盖检查使用 `Diff base..HEAD` 的已提交变更与当前 working tree 的并集，因此提交前后可用同一命令复验：

```powershell
uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-03-replan-event-persistence-and-state-transactions.md --check-diff --report build/traceability/TASK-P4-03-report.json
```

报告使用 `traceability-report.v1`，包含 `diff_base` 与 committed/working-tree source counts，生成到已忽略的 `build/`；Task Card Completion evidence 保存持久结果摘要。[`ci.yml`](.github/workflows/ci.yml) 已编排 exact lock、lint、type、全部 P0 tests、machine contracts、Compose config、文档 diff 和 package build。仓库内只证明 workflow/config 可执行；CI provider run URL/ID 必须来自真实外部运行，不能由本地结果替代。

CI 不再硬编码某个 P0/P1 Task。PR 使用 base SHA、main push 使用 event `before` SHA，通过 `--discover-task-from <40-char-sha>` 找到唯一当前 Phase Task Card，再按该卡自身的 `Diff base`执行完整 scope/impact检查；零个、多个、历史/未来或 phase/path不一致的 Task Card都硬失败。workflow机器报告使用 `ci-*.json`与 `plantnexus-ci-evidence-<run-id>`中性名称；本地实现通过不等于 provider PASS。

## 仓库结构

```text
backend/      Python 应用包、工程 migration 与 P0 测试
frontend/     前端工作区预留边界
schemas/      可执行 Schema 预留边界
fixtures/     确定性、非法、仿真与历史 Fixture 预留边界
benchmarks/   Benchmark profile 与 baseline 预留边界
docs/         唯一实质性开发文档中心
scripts/      仓库级校验与自动化脚本
infra/        P0 开发容器构建配置
```

P2 CP-SAT Vertical Slice与P3 Planning Workspace均已通过Exit Gate并关闭，当前阶段为P4。P2-00～14、P3-00～17、TASK-P4-00～08与P4-16均为`done`；P4-09～15仍为`planned`且没有自动启动的下一Task。Production capacity/SLA/identity/approval authority/external publish仍未形成。内部工作区的当前边界记录为`docs/current_phase.md`。

TASK-P3-13保留失败implementation run `32920462781`、首次closure `87d47c7483185483ac8027100c1c664d18011a7c` / run `32921871460`的606/1失败与artifact count=0。独立XLSX deterministic corrective implementation `3538d46f8b73ae434057bcbca9037436aa91f2c7`的required run/job/artifact=`32923203227`/`98040743610`/`9590625358`已全绿并下载复验33份JSON、12/12 Chromium和Task 91/0/11/19/0；该P3-13 closure当时未自动启动P3-14，后者现依据新的用户授权独立执行。

## P2 历史执行记录

TASK-P2-05本地验收与implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的GitHub required `validate` / artifact均已闭环。TASK-P2-06 implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`及TASK-P2-07 implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的required `validate`与artifact也已闭环，二者均=`done`；TASK-P2-08/09亦已闭环，TASK-P2-10是之后另获授权启动。

TASK-P2-08形成`POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`、显式SolveLimits、priority-weighted tardiness seconds目标、single-call GlobalCpSatStrategy、诚实status/bound/gap与mandatory formal Validator gate；70 focused、395 full与7/7 local machine PASS，implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的required run `32438785162` / artifact `9431673977`精确复现证据，Task=`done`。该证据不构成XS/S/M baseline或Production policy；P2-09是之后另获授权启动。

用户于2026-08-21明确授权TASK-P2-09。Diff base固定为clean且provider-verified的`15c298f343a47db2a922544944ff5e02e4ca72d9`；本Task只新增七类versioned correctness assets、正式Ingress→Problem→Global Strategy→Validator replay、property/mutation与CI machine evidence，不修改Planning/Solver/Validator语义，不建立XS/S/M/Production baseline，也不启动P2-10或P3。

TASK-P2-09本地已形成`P2-GOLDEN-JSSP/FJSP`与五例correctness matrix、`PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`、固定object/Import/Snapshot/Problem hashes、7次Solver→Validator replay、7次row-order property及11个exact C-ID mutation；45 focused、427 full、8/8 correctness及全部历史machine/build/governance checks均PASS。Implementation `20e49c92306128b47313059fabe31534814dbe3d`的required run `32442651322` / artifact `9432982306`精确复现16/16 reports和58 committed/0 working治理证据，Task=`done`；P2-10+与P3仍未启动。

TASK-P2-06 exact run `32432482739` / required job `96626844156` / artifact `9429579311`精确复现temporal 7/7、4个implemented C-ID、5个positive candidate、3个certified infeasible、2个precheck、4个formal Validator mutation、8个tiny oracle及53 paths/6 rows/0 issues，Task已闭环。

用户于2026-08-21明确授权TASK-P2-10。启动门复核确认`main=origin/main=0e4f6630412889254a7bef41f487c24dc274ca9c`、P2-01/02/04=`done`，且该SHA的required `validate` run `32443067388` / job `96657446617` / artifact `9433118755`精确成功。当前只允许五个versioned baseline、测试、CI machine evidence与治理文档；P2-11～14、BenchmarkRunner/XS-S-M、Production fallback及P3不会自动启动。

TASK-P2-10已形成`reference-scheduler-contracts/policy/result/report.v1`及五个exact algorithm identity；七个冻结Problem×五算法得到35个完整candidate、35次fresh Validator PASS和35次deterministic replay，blocked-calendar得到5个零partial `HEURISTIC_FAILURE`。Task-specific=`13 passed`、full=`441 passed`且Ruff/Pyright为0；implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`的required run `32449742281` / artifact `9435264655`精确复现17/17 reports和38 committed/0 working治理证据，Task=`done`，不自动启动P2-11。

用户于2026-08-21明确授权TASK-P2-11。启动门复核确认`main=origin/main=41e958b771f2664b1ac50867903a30b73627878d`，该SHA的required `validate` run `32450216908` / job `96677202782` / artifact `9435421360`精确成功。当前只允许additive KPI/manifest、deterministic reporting/internal package、测试/CI与治理文档；ScheduleVersion/ExportJob、approval/publish/external transfer、ChangeReport、BenchmarkRunner、P2-12+及P3不会自动启动。

TASK-P2-11新增`kpi.v2`、`export-manifest.v1`和`p2-internal-export.v1`：所有JSON采用`canonical-json.v1`，CSV采用UTF-8/RFC 4180 LF，manifest固定9个payload的hash/bytes/rows与同一run lineage。包只承载validated PlanningSolution，显式声明`publishable=false`及P3/P4 deferred边界；原子目录写入支持exact replay并在失败时不留下成功manifest。指定验收49项、全仓455项和output machine 8/8均PASS；implementation `546292831c3bd52185687a4c646c10ae10541ae2`的required run `32454693799` / artifact `9436863185`精确复现18/18 reports与58-path治理证据，故Task=`done`。P2-12仍为`planned`且未获启动授权。

用户于2026-08-21明确授权TASK-P2-12。启动门复核确认`main=origin/main=58db14e8f18fb50866fb757d4c89e76fef1141f1`，其required `validate` run `32455399561` / job `96691604529` / artifact `9437086153`精确成功并复现P2-11 closure证据。当前只允许versioned XS/S/M profile/baseline、BenchmarkRunner、共享但不改变输出的schedule KPI pure calculation、CLI/CI/test与治理文档；L/XL、Production threshold、P2-13/14及P3不会自动启动。

TASK-P2-12已形成`benchmark-profile-set/report/baseline.v1`、`benchmark-runner.v1`和SIM-ASSUMPTION-013。XS/S/M分别固定8/24/48 operations，同一正式Raw→Problem链上运行Global与五个Reference，各完成1次warm-up和3次measured replay；三份报告均8/8 PASS、formal Validator与共享KPI一致，baseline comparison无warning。Implementation `01e7f4bdca88fc903e7caa771f875fc1a70ff357`的required run `32460861563` / artifact `9438899443`精确复现19/19 reports、XS 8/8及49 committed/0 working治理证据，故Task=`done`；P2-13/14与P3未启动。

用户于2026-08-21明确授权TASK-P2-13。启动门复核确认`main=origin/main=59f3b013a4be7bd11d054e8464886b3cde791602`且working tree clean，P2-01～12 implementation与exact provider evidence均位于可追溯祖先链；closure run `32461665177` / required job `96709654227` / artifact `9439159396`精确success。当前只允许聚合公开边界形成可重放`p2-vertical-slice-report.v1`、四类负例、测试/CI evidence及治理文档；不修复既有实现、不作P2 Exit结论，也不启动P2-14或P3。

TASK-P2-13本地Gate现以两次完整replay聚合七场景correctness、XS/S/M Global+五Reference Benchmark、formal Validator/KPI/SolverReport与九payload internal Export；聚焦`30 passed`、全仓`476 passed`，Gate为11/11 PASS、14次correctness场景、6次profile、108次Benchmark Validator、4类exit rejection且0 blocking gap。报告保留全部原始运行字段，同时用versioned semantic projection验证业务一致性；`Exit Gate Audit=NOT_PERFORMED`，exact implementation provider闭环前Task保持`in_progress`。

Implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的GitHub required run [`32465737712`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32465737712) / job `96721819879` / artifact `9440650646`精确success；20份artifact JSON全部PASS，Gate 11/11与37 committed/0 working paths、6 rows、19 checks、0 issues均绑定同一SHA。因此TASK-P2-13=`done`；这只满足P2-14依赖，不构成Exit READY或P3授权。
