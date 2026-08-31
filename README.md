# PlantNexus APS

## TASK-P4-13 Replanning Workspace UI

TASK-P4-13从不可变Diff base `be2389594f3e224de3f5a73f4b8b62ffcffb5b7b`形成一个additive、Simulation/development-only的`/planning/replanning`工作台。浏览器以strict typed consumer读取P4-12的event timeline、ReplanRequest/attempt/result和ChangeReport投影，展示freeze half-open边界、before/after priority-weighted tardiness、OBJ-002 Stability及逐operation classification；query/response/resource/correlation/fingerprint任一不一致均fail closed。既有18条P3 route和12个P3 Chromium场景作为冻结子集继续复验。

`CANCEL/RETRY`只在服务端`allowed_actions`允许时挂载，并逐字绑定request fingerprint、attempt ID/number、expected PlanningRun state、hashed Idempotency-Key reference及显式确认/reason。网络或503造成unknown outcome时，浏览器仅在内存保留exact body/key，先refresh authoritative result；authority未变才允许same-body/same-key retry，变化则停止重试。Production runtime在任何read/action前default-deny；浏览器不计算event order、fact、freeze/effective lock、KPI、Stability、Validator或ChangeReport。

完整HIGH_RISK本地验收已通过：focused 19/19、Backend 821/821、Frontend 78/78、主Chromium 17/17（12个冻结P3 + 5个P4 positive/error/tamper/network recovery场景）、两轮P3 Gate各12/12、P2/P3 Gate 11/11与14/14、Ruff/Pyright、SCA/license、全部历史machine、XS Benchmark、Compose、前后端build及sdist/wheel。`p4-replanning-frontend-report.v1`为8/8、五个Impact Rules、`issues=[]`；Task治理为43 paths/5 rules/19 checks/0 issues且forbidden scope=0。首次错误工作目录Vitest、两次raw-label locator、裸`node` evidence、旧i18n loader、首轮Backend CI-step count及最初Task-diff临时文件失败均保留并在冻结allow-list内限定纠正。首个implementation candidate `18c0eb8967cfd7b11d7a9019fe72a221dfc0bd85`的run/FULL/required=`33354198989`/`99373143904`/`99373794071`又因新machine step从repository root调用frontend-relative脚本而被正确拦截；corrective只为该step设置`frontend` working directory并保持报告路径/断言语义不变。Corrective exact provider与evidence-only closure仍待本Task后续闭环。Schema/migration/dependency/lock、backend business/state pair、Solver/Validator/Simulator、external publish、P4 Gate、P5及Production identity/authority/deployment/capacity/SLA未修改或形成；TASK-P4-14不会自动启动。

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
