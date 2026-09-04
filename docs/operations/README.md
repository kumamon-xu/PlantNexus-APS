---
doc_id: DOC-OPS-INDEX
title: Operations 索引与形成边界
status: baseline
spec_version: 0.3.0
phase: P0-P8
normative: false
source_sections: [65, 66, 93, 94, 95, 101, 106, 113, 114]
last_reviewed: 2026-09-04
---

# Operations 索引与形成边界

## P8 planned operations outcome

P8-09/10将来负责可复现Headless Runtime distribution、版本/SBOM/checksum、migration bundle、非Production部署、readiness、metrics/logs/traces/alerts、backup/restore、rollback和operator runbook；P8-12～15形成Extension SDK/Registry、企业模板和Developer Kit兼容发布，P8-16/17再分别形成synthetic集成Gate与独立审计。当前这些能力全部是planned，不存在Runtime/SDK/Kit release、Production package、deployment、on-call或SLA。

运行拓扑固定为APS Runtime中的API、独立Solver Worker、formal Validator、受控Extension loader、APS自有数据库及broker；可选Frontend可以缺席。API/Worker必须加载同一Extension fingerprint。宿主和Extension不共享数据库或直接投递内部queue，第三方连接器和结果展示仍由宿主负责。Plugin artifact只可在build/deploy/startup经allow-list、digest/signature、compatibility和SBOM/license校验装载，禁止请求级上传/下载/安装。本次没有修改部署配置、代码、测试、依赖或环境。

## TASK-P4-12 local API operations boundary

P4 HTTP只是Development/Test/Benchmark中的Simulation API contract与machine evidence；`no-store`、correlation、sanitized error、denial audit和Production default-deny已在本地证据中形成。这不创建Production runbook、gateway、identity provider、external event ingress、deployment/on-call、UAT或capacity/SLA。

## TASK-P4-11 internal output operations

P4新增的是bounded internal worker/reference operation：对既有v3 ExportJob claim lease，在临时目录构建并验证13-payload package，manifest last原子提交，成功后才complete；失败调用既有fail transition并清除partial directory。Verified download重新验证目录、manifest和archive，不暴露filesystem path，也不发送外部系统。

这不是Production runbook。没有queue deployment、object storage、backup/restore、credential、external delivery、on-call threshold、capacity或SLA；这些边界继续由PROD_OPEN阻止。

## TASK-P4-05 operations boundary

CI新增不可跳过的`P4 freeze window and effective lock evidence`并上传`ci-p4-freeze-window.json`；报告只含sanitized IDs/fingerprints/counts/边界，不记录secret、真实工厂事实或外部side effect。本Task无service/worker/database/API部署、告警/retention、runbook、Production authority、capacity或SLA结论，rollback仅停用后继consumer并保留immutable evidence。

## TASK-P4-04 operations boundary

本Task新增可运行的Simulation-only event/projection machine evidence，但没有形成Production Runbook、服务部署、event consumer daemon、queue/lease/retry scanner、dead-letter、outbox、external adapter、backup/restore或on-call流程。可操作的回滚边界仅为停用入口、保留ledger，并以补偿event+new Snapshot纠正；不可删除或改写历史。


## TASK-P4-03 persistence operations boundary

新增`0005`与repository/machine-check只在本地及required CI的临时SQLite执行，验证append/exact replay、CAS、transaction rollback、plane default-deny和populated downgrade/re-upgrade。没有新增常驻service、queue、worker、secret、deployment、external adapter、Runbook或on-call；PostgreSQL并发、backup/restore、capacity/SLA与Production readiness仍未形成。

## TASK-P4-02 operations boundary

CI新增纯机器合同报告生成，不新增service、worker、queue、database、secret、deployment或external adapter。Report只用于development/provider evidence；没有Runbook、on-call、capacity/SLA、Production readiness或真实authority形成。Migration manifest与Compose/lock继续冻结。

## P4 planning operations boundary

P4只规划Development/Test/Benchmark中的dynamic replanning与Execution Simulator证据。事件接入、worker、API/UI和成果包即使在后继Task形成，也不等于Production runbook、deployment、on-call、UAT、external integration或capacity/SLA；这些继续由PROD_OPEN与后续明确阶段治理。本次不创建runbook或运行配置。

## TASK-P3-17 audit conclusion

P3的append-only audit、correlation/redaction、idempotency/CAS、ExportJob lease/recovery和internal package evidence均独立PASS；这些是开发/Simulation运行边界，不形成Production runbook、SLA、on-call、backup/restore或deployment readiness。

## TASK-P3-16 bilingual operations boundary

TASK-P3-16仅以key `plantnexus.locale.v1`保存`zh-CN`/`en-US`非敏感展示选择，不保存token、actor、reason、payload或authority，也未增加server config、Accept-Language、monitoring、runbook或deployment。Required workflow只additive运行双语machine evidence并沿用同一`validate`/artifact边界；implementation exact SHA的8/8检查与完整required Gate已由artifact `9629193057`复验。TASK-P3-17最后独立审计；没有service、queue、dashboard、secret、external target或Production operations变化。

## TASK-P3-14 Gate operations

本地操作入口为两轮`playwright.p3-gate.config.ts`、Node `p3-gate-evidence.mjs`及Python `app.application.p3_gate_report --repeat 2`。成功要求Backend 18 stage executions/144 subordinate checks、Frontend 24 spec executions、4 exact rejections、14 aggregate checks和0 blocking gaps；失败报告与Playwright failure media必须保留并非零退出。该入口是CI evidence，不是Production Runbook、deployment、on-call或SLO。

## TASK-P3-13 validation operations

Required workflow在locked frontend install/SCA/license/lint/type后于`frontend` working directory用shell-neutral `npm exec -- vitest --exclude=e2e/** --run`执行Vitest，再安装Chromium并执行12条human-control+visualization E2E，随后build和12/12 frontend machine evidence；`if: always()`继续上传JSON/HTML/JUnit及failure trace/video/screenshot。Backend先执行第18个API operation machine check和full regression。Implementation/closure各自都必须push main、等待唯一required `validate`、下载exact run artifact并核对SHA/Task/base/Impact/checks/issues。run `32920462781`因历史unquoted glob在Linux展开而失败，属于必须保留的negative evidence，不能用本地Windows PASS替代。

首个corrective implementation run/job/artifact=`32921059019`/`98034581212`/`9589931373`已全步骤success并下载复核。Success browser run只上传JSON/JUnit/HTML；trace/video/screenshot按配置仅在browser failure时产生，因此本次absence不是缺口。其后的首次closure失败仍按下段保留。

首次closure run/job=`32921871460`/`98036888624`在Repository suite失败并且upload因无报告文件失败，artifact count=0。该run不可作为closure evidence；Task曾重新打开以修复XLSX core wall-clock timestamp，且没有仅rerun旧closure。独立corrective `3538d46f8b73ae434057bcbca9037436aa91f2c7` / run/job/artifact=`32923203227`/`98040743610`/`9590625358`已完整重跑并下载复验，故本closure标Task=`done`；closure仍须按同一流程核对exact SHA，P3-14不自动启动。

这不是Production Runbook：没有部署、值班、SLO、真实identity、external storage、backup/restore或support browser matrix。P3-14 Gate、P3-16与P3-17双提交provider均已完成；P4现在只激活规划，仍不形成上述Production能力。

P0-08 已形成工程骨架可验证的前三份 Operations baseline：

- [`security.md`](security.md)：environment-only config、Secret/log redaction、dependency/SQL/shell 边界；Import/auth/threat-model controls 仍待真实功能。
- [`observability-and-audit.md`](observability-and-audit.md)：structured log context、OpenTelemetry ID 注入、health/build metadata；PlanningRun metrics/audit persistence/retention 仍待实现。
- [`worker-reliability-and-idempotency.md`](worker-reliability-and-idempotency.md)：business-neutral heartbeat、lease、attempt、STALLED、idempotency 与 migration；distributed repository/scanner/business retry 仍待实现。

后续仍只保留计划：

- `release-and-versioning.md`：code/spec/schema/solver version 和 promotion；
- `production-readiness.md`：Historical replay、UAT、backup/restore、monitoring、runbook 和 PROD_OPEN closure。

现有三份 baseline 只引用仓库内配置、tests 与 machine report，不能被解释为 Production Runbook。Release/Production 文档必须引用真实部署配置、监控指标、backup/restore、平台 run 和责任人后才能创建并转为 `baseline/living`；P0-08 未猜测这些事实。

TASK-P0-10 只补齐 GitHub Actions 运行、job、artifact digest 与 required-check/branch-protection 的 CI 治理证据。provider 历史和 artifact retention 由 GitHub 管理，仓库只保存可核验 ID/URL/SHA/digest 与边界说明，不写入 credential。该证据可用于 P0 CI Exit Gate，但仍不是 release runbook、监控、backup/restore 或 Production readiness。

TASK-P1-01把 workflow从单一 P0-10 handoff改为 phase/task-neutral：CI event base发现唯一 current-phase Task，Task Card `Diff base`继续限定 scope，机器产物采用中性名称。既有P0 provider成功证据保持历史只读；未获push/provider授权时结果必须记为`NOT_RUN`，不能从本地测试推断。后续授权下，completion commit `2d2a4432aa42e4f38ee8ae736e2acf2df1c694b9`的GitHub run [`32237649319`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32237649319)、successful `validate` job和artifact `9359554539` / digest `sha256:bdd08f01ea23e8fe93f82c199274afc0aa5e9343ea7fa70adfb6df6a950d1216`已形成provider PASS。该变化不形成release runbook、Production监控或部署能力。

TASK-P1-03在既有Operations baseline上增加Raw Staging持久化证据：insert-only batch/row、source/version/digest/location/UTC provenance、plane-scoped idempotency、atomic rollback与destructive migration downgrade均由unit/integration tests复验。错误不回显raw/driver detail，repository不创建Worker task或业务副作用。

这仍不是Production Runbook：真实PostgreSQL并发/lock、独立数据库与roles、retention/erasure、backup/restore、access audit、容量/告警和incident response均未形成。migration downgrade只在临时开发SQLite明确删除1个synthetic sample batch/row，不能作为生产数据清理策略。

TASK-P1-03 implementation commit`25897393e31dcc0648943ec7e2e7f43dbb0e70e1`已由GitHub run [`32243895717`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32243895717)的required `validate`成功重放；artifact `9361846475` / digest `sha256:75aa68daf5bd4308a4f9143c0ae72746f540d103d6a937d472d6a7d5c3c5160b`保存机器证据。该provider PASS仍不构成Production DB、migration runbook或安全认证。

TASK-P1-04在`security.md`形成bounded CSV/XLSX file-root/type/size/shape/archive/active-content控制，并把openpyxl/defusedxml exact pins同步到既有engineering machine contract/CI assertion；OR-Tools forbidden、environment/data-plane fail-closed和既有machine report schema均未弱化。Reference files只在temporary test directory生成，Adapter不创建upload API、Worker或外部connection。

这仍不是Production Runbook或完整file-ingress security：quarantine/malware scanning、RBAC、network file share、rate limit、encryption、retention/erasure、production filesystem permission/audit和incident response均未形成；真实ERP/MES/WMS/CAM binding也仍受OPEN-002/015阻塞。

TASK-P1-04 implementation commit`9391ec021afa9e6f4f881b1538b276c84584df0e`已由GitHub run [`32247079996`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32247079996)的required `validate`成功重放；artifact `9362999088` / digest `sha256:b9ada0b25d12962f5efea51e058cd82778495f4389a240e32aa64c04143b5d4b`保存机器证据。该provider PASS仍不构成Production file-ingress、security certification或真实system binding。

TASK-P1-07不新增API、Worker、DB/migration、network、Secret或Runbook行为；仅把dev-only Hypothesis property directory加入既有repository CI test step，并以`test_ci_contract.py`防止provider遗漏核心expansion evidence。Workflow仍使用current-phase Task discovery、中性artifact名、完整既有gates和conditional Benchmark hook，无`continue-on-error`。

本地workflow contract PASS不等于GitHub provider执行；implementation commit push后必须核验required `validate`、steps与artifact，再以evidence-only commit关闭Task。即使provider PASS，也不构成Production operation、capacity、安全或on-call证据。

TASK-P1-08新增internal PlanningSnapshot persistence：hash主键、ID唯一、full-bytes digest、plane scope、atomic insert/exact replay/read，以及repository与database-trigger双层update/delete拒绝。Migration测试明确验证空库升级、含一个synthetic Snapshot的destructive downgrade至`0002`、re-upgrade后记录为空；历史Snapshot不能用代码rollback原地改写。

这仍不是Production Runbook：独立aps_sim/aps_prod数据库与roles、PostgreSQL trigger/concurrency实跑、retention/legal erasure、backup/restore、access audit、capacity/alert和incident response均未形成。`created_at`只属于storage audit metadata且不进入Snapshot hash。Implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`已由GitHub run [`32310098594`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32310098594)的required `validate`成功重放；artifact `9386127863` / digest `sha256:69d68183bad614631df07234a3ca88508379ab89ec715f811ee7f529d6f17e0c`保存机器证据，但不构成上述Production能力。

## TASK-P1-11 operator-facing evidence

本地/CI可运行`python -m app.application.p1_gate_report --root . --scenario fixtures/synthetic/SIM-P1-INGRESS-001 --repeat 2 --report <path>`生成`p1-data-pipeline-report.v1`。返回码0只表示双入口parity、两次hash replay、quality PASS、四类exact rejection与Problem终止边界均通过；返回码非0必须保留report/CI failure并阻断Task闭环。

Report本身不写业务数据库，temporary CSV随进程回收，`build/validation/*.json`保持ignored并由CI artifact托管。这不是Production Runbook、SLA、capacity、backup或incident evidence。

## TASK-P2-01 operator-facing contract evidence

本地/CI可运行`python -m app.planning.problem.contract_check --root . --report <path>`生成`planning-problem-contract-report.v1`。PASS同时验证v1 Schema/sample bytes、v1 fixed replay、v2 Schema/sample replay、两类lock和historical/delivery/resource字段计数；CI固定输出`build/validation/ci-planning-problem-contracts.json`并上传中性evidence artifact。非零返回码必须保留FAIL report并阻断Task closure。

该命令只读repository输入并写machine evidence，不写数据库、调用Solver或建立service endpoint。`code_commit=uncommitted`的本地报告不构成provider证据；只有exact GitHub SHA/run/job/artifact可关闭Task。本段不是Production操作手册、priority/lock policy、SLA或on-call能力。

## TASK-P2-02 operator-facing contract evidence

本地/CI运行`python -m app.planning.policy.contract_check --root . --report <path>`生成`planning-machine-contract-report.v1`。PASS必须包含fixed Schema/sample bytes、Policy/Limits无默认值、七种status唯一映射、四文档fingerprint/replay与no-Solver/no-Validator scope共5项检查；CI路径为`build/validation/ci-planning-machine-contracts.json`。非零返回码保留FAIL report并阻断closure。

命令不连接数据库或外部系统、不加载Solver、不生成candidate，也不执行Benchmark/Validator。local `uncommitted`只用于验收；Task关闭必须查询exact pushed SHA的required `validate`步骤和未过期artifact。该命令不是Production runbook、SLA、capacity或incident evidence。

## TASK-P2-03 operator-facing foundation evidence

本地/CI运行`python -m app.planning.backends.cp_sat.contract_check --root . --report <path>`生成`solver-backend-foundation-report.v1`。PASS要求exact dependency/lock、平台identity、namespace/Protocol、七状态、参数及两类engineering smoke共6项全部通过；CI固定路径为`build/validation/ci-solver-backend-foundation.json`。非零返回码必须保留FAIL report并阻断closure。

命令只调用空/故意invalid的native CP-SAT model，不读取业务数据、不连接DB/API/Worker、不生成candidate、不运行Validator/Benchmark，也不声明Production readiness。升级OR-Tools时必须按ADR-0011重新执行lock/platform/status/Golden/Scenario/Benchmark Gate；本段不是solver生产Runbook、SLA或incident流程。

## TASK-P2-04 operator-facing validator evidence

本地/CI运行`python -m app.planning.validation.problem_validator_check --root . --report <path>`生成`formal-schedule-validator-report.v1`。PASS要求6项检查全部成功，并显示13个声明式mutation覆盖C-001～C-011、14个hard violations、6个duration/order examples、status contradiction identical replay及Backend/OR-Tools/expected-outcome隔离；CI固定路径为`build/validation/ci-formal-schedule-validator.json`。

非零返回码必须保留FAIL report并阻断closure。该命令只验证synthetic correctness与合同/hash边界，不连接Production系统、不执行CP-SAT business model、objective或Benchmark；local `uncommitted`报告不替代exact GitHub SHA的required `validate`与artifact，也不是Production runbook、capacity或SLA证据。

## TASK-P2-05 core model evidence command

本地/CI运行`python -m app.planning.backends.cp_sat.core_model_check --root . --report <path>`生成`cp-sat-core-model-report.v1`。PASS要求6项检查全部成功：冻结合同/rule/Validator/lock hash、five-C-ID model shape、tiny JSSP/FJSP candidate、unary infeasible与zero/overflow precheck、formal Validator正反例、独立穷举oracle与真实telemetry；CI固定路径为`build/validation/ci-cp-sat-core-model.json`。

非零返回必须保留sanitized FAIL report并阻断Task closure。该命令不读取Production数据、不发布ScheduleVersion、不运行OBJ-001搜索、Strategy或Benchmark；含P2-06/07事实的Problem应视为当前core slice不支持并稳定拒绝，而不是改写输入或忽略事实。

## TASK-P2-06 temporal model evidence command

本地/CI运行`python -m app.planning.backends.cp_sat.temporal_model_check --root . --report <path>`生成`cp-sat-temporal-model-report.v1`。PASS要求7项检查全部成功，并显示4个temporal C-ID、5 candidate、3 infeasible、2 precheck、4 independent Validator mutation、8 tiny oracle cases、冻结合同/Builder/Validator/lock fingerprints和真实model delta；CI固定路径为`build/validation/ci-cp-sat-temporal-model.json`。

非零返回必须保留sanitized FAIL report并阻断closure。该命令仅使用in-memory synthetic data，不读取Production系统、不发布ScheduleVersion、不运行C-007/008、OBJ-001、Strategy或Benchmark；local `uncommitted`结果不替代exact GitHub provider evidence。

## TASK-P2-07 fact/lock model evidence command

本地/CI运行`python -m app.planning.backends.cp_sat.fact_lock_model_check --root . --report <path>`生成`cp-sat-fact-lock-model-report.v1`。PASS要求7项检查全部成功，并显示2个fact/lock C-ID、4 candidate、3 certified INFEASIBLE、4 precheck、2 independent Validator mutation、6 tiny oracle、冻结合同/Builder/Validator/rule/ADR/lock fingerprints与real model delta/telemetry；CI固定路径为`build/validation/ci-cp-sat-fact-lock-model.json`。

非零返回必须保留sanitized FAIL report并阻断closure。该命令仅使用in-memory synthetic data，不读取Production系统、不发布ScheduleVersion、不运行OBJ-001/002、Strategy、dynamic Replan或Benchmark；local `uncommitted`结果不替代exact GitHub provider evidence。

## TASK-P2-08 objective/strategy evidence command

本地/CI运行`python -m app.planning.backends.cp_sat.objective_strategy_check --root . --report <path>`生成`objective-strategy-report.v1`；CI固定路径为`build/validation/ci-objective-strategy.json`。PASS必须为7/7，并包含冻结fingerprints、approved Simulation Policy/Limits、exact OBJ-001 model、4个tiny exhaustive optimum/Validator PASS、hard INFEASIBLE、七状态/report/provenance与Production deferred边界。

非零返回保留sanitized FAIL report并阻断closure。命令只使用in-memory synthetic vectors，不读取Production source、不设置默认limits、不运行Reference/XS/S/M Benchmark、不创建ScheduleVersion/Export/approval/publish。Provider核验时必须确认report `code_commit`等于exact pushed SHA，local `uncommitted`不算external evidence。

## TASK-P2-09 correctness evidence command

运行`uv run python -m app.simulation.scenarios.p2_correctness --root . --report <path>`生成`p2-correctness-report.v1`；CI固定为`build/validation/ci-p2-correctness.json`。PASS必须为8/8 checks、7 scenarios/Validator passes/property replays、11 exact mutations及C-001～C-011正负全覆盖，并验证P0/P1 immutable assets和冻结输入fingerprints。

命令只读versioned synthetic fixtures并写ignored report；不连接DB/Redis/API/Worker，不运行Reference/Benchmark/Export或Production。Provider closure必须复核report `code_commit`、hash/status/counts和同一artifact中的current Task report。

## TASK-P2-10 Reference Scheduler evidence command

运行`uv run python -m app.simulation.baselines.reference_schedulers --root . --report <path>`生成`reference-scheduler-report.v1`；CI固定为`build/validation/ci-reference-schedulers.json`。PASS必须为7/7 checks、5个versioned identity、7个冻结Problem、35个完整candidate/fresh Validator/deterministic replay及5个explicit heuristic failure，并保持零partial、零infeasibility certificate claim。

命令只读synthetic correctness assets并写ignored report，不连接DB/Redis/API/Worker、不创建PlanningRun/ScheduleVersion/Export、不建立XS/S/M或Production fallback。Provider验收必须确认report `code_commit`等于exact pushed SHA、required `validate`成功，并与同一artifact的Task report一起下载复核；local `uncommitted` PASS不是外部证据或Production runbook。

## TASK-P2-11 output-contract evidence command

运行`uv run python -m app.exporters.contract_check --root . --report <path>`生成`p2-output-contract-report.v1`；CI固定为`build/validation/ci-p2-output-contracts.json`。PASS必须为8/8 checks，覆盖两份新Schema/sample、冻结input hashes、同一validated correctness run的确定性package、cross-file lineage/count/hash、mixed/tamper/missing负例、exact replay以及partial-write cleanup/state boundary。

命令只在进程内构建synthetic bytes并可使用临时目录；不创建业务ExportJob/ScheduleVersion、不连接外部storage/network/DB/queue，也不publish。Provider验收必须下载同一artifact，确认report `code_commit`、8/8 checks和current Task report均绑定exact implementation SHA；local `uncommitted` report不是发布或Production runbook。

## TASK-P2-12 benchmark commands

运行`uv run python scripts/run_benchmark.py --profile <xs|s|m> --report build/benchmarks/<name>.json`。CLI必须读取versioned profile与对应immutable baseline；成功报告为`benchmark-report.v1`/8 checks，失败写`benchmark-failure-report.v1`并返回非零。PR CI固定只执行XS；S/M是local/nightly-ready命令，仓库尚未创建Nightly scheduler，L/XL不接受。

命令只使用synthetic data并在进程内运行正式pipeline/Solver/Validator/Reference/KPI/Export；不连接DB/Redis/API/Worker、不写业务ScheduleVersion/ExportJob、不publish，也不会覆盖baseline。Provider closure必须确认exact SHA report、required `validate`、benchmark artifact和Task diff同一提交；结果不得作为Production capacity/SLA runbook。

## TASK-P2-13 vertical Gate command

运行`uv run python -m app.application.p2_gate_report --root . --repeat 2 --report build/validation/TASK-P2-13-p2-gate.json`。成功必须为`p2-vertical-slice-report.v1`、2 full replays、11/11 checks、7 scenarios×2、C-001～C-011正负覆盖、XS/S/M×2、108 benchmark Validator passes、四类rejection、stable projection unique=`1`和0 blocking gaps；Exit decision必须仍为`NOT_PERFORMED`。

任一stage失败时CLI仍写包含stage/error/blocking gap的FAIL report并返回非零；不得在本Task内修改Solver/Validator/fixture/baseline来“让Gate变绿”。命令不连接业务服务、不创建状态或可发布artifact。CI使用同一命令与`--repeat 2`输出`build/validation/ci-p2-vertical-slice-gate.json`，exact provider SHA/required job/artifact必须在实现提交后另行核验。

该provider验收已完成：implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`、run `32465737712`、required job `96721819879`和artifact `9440650646`全部success；artifact 20/20 JSON PASS。命令仍是evidence-only，不是Production runbook或P2 Exit audit。

## P3 operations planning

P3-01先定义security/audit/idempotency责任，P3-03/07～10再形成repository、audit、publish/export/API的development行为，P3-14验证Gate，P3-17最终独立验证failure/retry/evidence；P3-15只形成计划修订治理，P3-16只实现展示层本地化且implementation provider已复验。没有新增Runbook、service、queue、dashboard、Production secret/target或deployment；P3 internal Simulation workflow不得写成Production operation readiness。
## TASK-P3-02 operational boundary

新增`python -m app.domain.workspace_contract_check --root . --report <ignored-json>`只做离线Schema/sample/fingerprint/frozen-byte验证。CI step non-skippable且artifact保存report，但没有service、health endpoint、DB、queue、worker、storage、external publish、rollback procedure或Production runbook形成。失败时返回非零并保存sanitized FAIL report；不得通过放宽Schema或删除负例恢复绿色。

## TASK-P3-03 operational boundary

新增`python -m app.infrastructure.workspace_persistence_check --root . --report <ignored-json>`在临时SQLite执行`0001→0004`、四repository正负路径、database trigger、caller rollback、populated `0004→0003→0004`并输出8/8 machine checks。CI step无`continue-on-error`并复用既有artifact glob；FAIL报告只含error type与sanitized固定message。

非生产回滚仅允许在确认备份/可丢弃synthetic rows后downgrade到`0003`，这会删除全部P3表和历史；不得对真实ScheduleVersion/audit历史原地回退。没有新增service、health、queue、worker、dashboard、runbook、Production Secret/target或deployment，PostgreSQL backup/restore演练仍未形成。

## TASK-P3-04 lifecycle evidence command

`uv run python -m app.application.schedule_version_lifecycle_check --root . --report <ignored-json>`复用一个冻结P2 correctness input，在三个临时SQLite数据库验证fresh lineage/KPI、DRAFT→READY、atomic audit、exact replay、五类无副作用拒绝、audit-conflict rollback、concurrent exact request、plane/PlanningRun/Solver边界并输出8/8 `p3-schedule-version-lifecycle-report.v1`。CI命令写`build/validation/ci-p3-schedule-version-lifecycle.json`且不可continue-on-error。

这是development machine evidence，不是业务Runbook：没有常驻service、health、queue、external storage、Production credential/target或deployment。业务回滚不得删除已形成的ScheduleVersion/audit；代码回退只能停止新调用并保留append-only历史，测试临时数据库随测试清理。

## TASK-P3-05 read-model evidence command

`uv run python -m app.application.workspace_read_model_check --root . --report <ignored-json>`在临时SQLite创建两个versioned synthetic READY_FOR_REVIEW输入，读取13个普通view与1个comparison view，验证23个payload reference、load/KPI、lineage、stable page replay、empty/missing/stale/plane/tamper/cursor负例、exact comparison及read-only row count，输出8/8 `p3-workspace-read-model-report.v1`。CI固定写`build/validation/ci-p3-workspace-read-models.json`且不可continue-on-error。

报告中的elapsed/source/projected bytes仅为XS synthetic observation，没有alert/SLO/Production threshold；代码回滚不删除或改变任何ScheduleVersion/Audit历史。

## TASK-P3-06 command evidence command

`uv run python -m app.application.schedule_command_check --root . --report <ignored-json>`在三个临时SQLite数据库重放versioned P2 JSSP/FJSP inputs，验证Move、Assign、Set/Remove Lock、显式SUBMIT_FOR_REVIEW、每次非replay fresh Validator、新DRAFT/audit、同ID/content READY、exact replay/conflict、REJECTED/PUBLISHED source immutability、stale/auth/validation负例、insert/CAS transaction rollback及Solver/P4边界，输出8/8 `p3-schedule-command-report.v1`。CI固定写`build/validation/ci-p3-schedule-commands.json`且不可continue-on-error。

报告中的command microseconds/schedule size只为development observation，`SLA=NOT_DEFINED`。没有常驻endpoint、queue、credential、external target或Production Runbook。代码回退不得删除已提交Version/audit；错误计划只能通过新command修订，不能UPDATE历史。

## TASK-P3-07 operator command

`uv run python -m app.application.approval_decision_check --root . --report <ignored-json>`在临时SQLite上复用P3-04 reviewable sources，验证APPROVE/REJECT同content CAS+audit、exact replay/conflict、REJECTED terminal、capability/resource/authentication与Production default-deny audit、stale/empty/credential-like reason无副作用、audit rollback及并发单winner，输出8/8 `p3-approval-decision-report.v1`。CI固定写`build/validation/ci-p3-approval-decisions.json`且不可continue-on-error。

报告只证明Simulation/Test application behavior，不配置真实principal/role、endpoint、publisher/exporter、external target或Production Runbook。回滚代码不得删除已提交decision/audit；错误decision只能通过受治理的新Version/纠正event处理，不能UPDATE历史。

## TASK-P3-08 operator command

`uv run python -m app.application.publication_check --root . --report <ignored-json>`在临时SQLite重放APPROVED-only first publish、historical replay/conflict/double publish、current/supersession、DRAFT/READY/REJECTED拒绝、Simulation/Production denial、audit rollback及并发current单winner，输出8/8 `p3-publication-report.v1`。CI固定写`build/validation/ci-p3-publication.json`且不可continue-on-error。

报告只证明internal Simulation state/idempotency行为，不配置endpoint、worker、publisher/exporter、MES/ERP、storage或Production Runbook。已提交PUBLISHED/SUPERSEDED/Audit/PublicationResult/current历史不得由代码回滚删除；修订只能走新的受治理Version/publication。

P3-09新增可调用的internal worker composition与local atomic storage boundary，但不注册Celery task、不配置service/queue/external storage或Production Runbook。运维只可通过显式claim/heartbeat/fail/retry/cancel恢复；不得手改EXPORTED、删除terminal Job/audit/artifact或以目录存在替代manifest/DB成功。

## TASK-P3-10 operational boundary

API process现提供health与17个P3 route的composition seam，但默认application/principal provider为unavailable，因而不构成可运营Production service。本Task没有连接真实identity、MES/ERP/storage、queue、database或SIEM，也没有新增deployment/rollback/runbook。运维故障只能通过sanitized correlation和现有audit/log边界定位，不得用test provider开通Production。

## TASK-P3-11 operator commands and boundary

本地与required CI依次使用`npm --prefix frontend ci`、`audit:sca`、`licenses:check`、`lint`、`typecheck`、`test -- --run`、`build`和`evidence`。SCA显式查询official npm advisory endpoint，High/Critical阻断；license未知/deny list阻断；machine report记录24 pins、13 routes、7 states、bundle bytes与P3/P4/Production absence。Playwright browser不安装。

Run `32818657951` / required job `97712018632`已逐步成功执行该链；artifact `9552386549`复验Frontend/SCA/license/Task reports均PASS。该命令链只属于development CI，不是Production deploy、hosting、rollback或support runbook。

生成的`node_modules/dist/coverage/*.tsbuildinfo`与JSON report均不提交。Frontend bundle不是deployment，默认session无token且Backend application仍可fail closed；没有Production hosting、CDN、runtime secret、runbook、SLO或rollback authority形成。

## TASK-P3-12 browser evidence operations

在P3-11 locked chain后执行`npm --prefix frontend exec -- playwright install --with-deps chromium`、`npm --prefix frontend run test:e2e`、build与visualization evidence。Playwright配置单worker、read-only Vite、JSON report，并对失败保留trace/video/screenshot；required workflow的machine artifact step使用`if: always()`收集`build/playwright/**`，不能因前置失败跳过诊断证据。

Local首轮2/4因strict locator歧义失败，失败介质保留后收紧role断言并4/4通过；不得删除row、skip spec或以截图替代behavior。Implementation run/job/artifact=`32826371613`/`97735176425`/`9555196470`已在required Linux runner精确复验4 expected/0 unexpected/0 flaky、Frontend 12/12与artifact always-upload，故TASK-P3-12=`done`。该命令链不连接Production API/identity、不会执行command/action或写ScheduleVersion，也不形成deployment、support runbook、browser matrix、SLO或rollback authority。
