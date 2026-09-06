---
doc_id: DOC-OPS-002
title: P0 Observability 与 Audit 边界
status: baseline
spec_version: 0.3.0
phase: P0-P8
normative: true
source_sections: [29, 42, 65, 93, 95]
last_reviewed: 2026-09-06
---

# P0 Observability 与 Audit 边界

## TASK-P8-08 authorization decision evidence

P8-08为五项Headless operation的每次授权尝试形成strict、sanitized `headless-authorization-audit.v1`，无论ALLOW还是DENY均在调用application port或resource lookup之前持久化。固定20字段覆盖event/version、operation/capability、outcome/reason、pseudonymous actor/subject、provider/assertion/policy reference、token SHA-256、exact composite scope及fingerprint、resource type/hash、correlation、canonical UTC、plane和environment；raw token、claim、raw resource ID、display identity、payload、SQL/DSN、stack或private path不得出现。授权记录通过correlation与既有ingress/PlanningRun/Worker业务audit相连，但两者职责独立。

`0009_host_authorization_audit`在`0008`之后增加独立表、scope/correlation/occurred-at索引及SQLite/PostgreSQL append-only trigger；repository还拒绝UPDATE/DELETE并在写入、读取和exact replay时重新验证strict carrier、canonical bytes与fingerprint。Audit write/validation失败即授权500且业务调用次数为零；downgrade会显式删除P8-08授权历史，执行前必须由未来retention/backup政策保留所需证据。Structured log、trace或HTTP correlation均不能替代该durable record。

机器证据固定10项checker、5项ALLOW与15项DENY共20个持久化决定，并检查redaction、失败前置与plane/scope隔离；authorization工程Benchmark使用1000次synthetic决定且threshold=`null`，只记录开发观测，不构成SLO。真实metric/trace backend、dashboard/alert、SIEM、legal hold、retention、外部audit sink、clock-skew和Production on-call/runbook继续由P8-10与OPEN-015承接。

## TASK-P8-07 Headless HTTP evidence

5项Headless PlanningRun response均回传`X-Correlation-Id`与`Cache-Control: no-store`；create成功另回传status资源`Location`，status/cancel/retry/result回传由canonical `run_fingerprint`形成的`ETag`及`X-APS-Planning-Run-State`。请求correlation与create carrier冲突在application side effect前拒绝。客户端必须使用durable status/result对账：202仅是accepted/queued，result在非terminal时返回409，不能从连接成功、timeout或UI缓存推断Solver/Validator/发布结果。

Transport只委托P8-06 facade并复用P8-03 ingress audit、P8-04 run/attempt/command/transition/audit和P8-05 job binding/checkpoint。Exact create/retry replay返回首次logical result且不追加第二dispatch或业务audit；冲突、非法payload、scope/authority拒绝和stale state不伪造成功证据。P8-08 adapter现为每次ALLOW/DENY创建独立durable授权audit；router仍不创建身份或伪造业务audit。

`p8-headless-http-api-report.v1`记录34项operation、旧29项hash preservation、5项additive inventory、strict carrier/limit/error/layering/确定性检查；`p8-headless-openapi-diff.v1`记录基线与新增集合；`p8-headless-api-engineering-benchmark.v1`只记录固定synthetic fail-closed HTTP probe和OpenAPI构建耗时，threshold为`null`且不构成SLO。报告、响应和日志不得包含Bearer、raw idempotency key、完整canonical payload、credential、endpoint secret、SQL/DSN、stack或private path。

P8-07没有新增metric/trace exporter、dashboard、alert、SIEM、retention、rate-limit telemetry、broker lag/database pool指标、clock-skew政策或Production SLO。P8-08已形成Test边界的identity correlation和durable allow/deny audit；真实Production identity/retention/SIEM及部署期observability/backup/runbook仍由OPEN项与P8-10继续形成。

## TASK-P8-06 Runtime composition evidence

Immutable composition descriptor把API/Worker共同绑定到environment、data plane、schema/core/runtime/Extension-set、Policy/Limits、Solver/Validator及port implementation references；safe manifest只发布这些稳定版本/指纹和process-owned port inventory。API/Worker parity在启动检查和machine report中逐字比较，descriptor漂移必须在业务执行或Solver publication前fail closed。

Facade沿用P8-03 ingress audit和P8-04 run/attempt/command/audit；dispatch成功只返回稳定dispatch/run/work/worker references，broker失败追加既有`DISPATCH_FAILED`证据并隐藏底层异常。Worker继续由P8-05 job binding/checkpoint连接到同一descriptor。`p8-runtime-composition-report.v1`记录8项组合、安全、角色和Production拒绝检查，不保存canonical payload、credential、endpoint、absolute path、SQL或stack。

Liveness只证明进程存在；P8-06的Development readiness/probes和synthetic端到端执行不构成Production readiness、SLO或capacity结论。真实metric/trace backend、broker lag、database pool、dashboard/alert、SIEM、retention/redaction批准、clock-skew和on-call Runbook仍由P8-10及OPEN项负责。

## TASK-P8-05 Worker evidence and redaction

每次Worker执行都可由稳定的job/run/attempt/work references连接到P8-03 source、P8-04 command/transition/audit、server-owned Runtime/Extension-set和最终Solver/Validation/ScheduleVersion evidence。`planning_run_worker_jobs`保存lease执行绑定，`planning_run_worker_results`保存一次canonical checkpoint及digest；PlanningRun状态仍只通过既有transition/audit追加，job的`RUNNING/STALLED/SUCCEEDED/FAILED`只是内部执行诊断，不能替代业务状态或审计。

Worker只暴露稳定结果类别、sanitized error code、指纹、计数和耗时，不记录canonical payload、原始idempotency key、principal、credential、DSN、SQL、stack、私有path或可执行Extension selector。Runtime/input/result fingerprint mismatch、Validator拒绝、cancel、timeout与基础设施异常分别fail closed；未知异常被归一为受限code，不能把底层异常文本写入task result或machine report。

`p8-solver-worker-reliability-report.v1`记录九项correctness/recovery检查、一次真实Global CP-SAT调用、独立Validator调用次数及最终row counts；`p8-solver-worker-engineering-benchmark.v1`只记录固定synthetic profile下的单worker开发观测。两份报告明确`DEVELOPMENT_OBSERVATION_NO_SLA`且threshold为`null`。当前没有Production metric/trace backend、dashboard、alert、SIEM、retention/redaction审批、broker lag/lease SLO、跨host clock策略或容量结论；P8-10仍须建立运行期可观测与Runbook。

## TASK-P8-04 PlanningRun transition and attempt audit

每次成功materialize、run transition、attempt dispatch failure/timeout和retry均原子追加一份`audit-event.v1`及一个scoped command receipt；run transition另保存before/after run fingerprint、sequence、from/to state和audit reference。Exact command replay返回首次结果且不追加audit；same-key conflict、stale CAS、非法/terminal pair及事务失败不伪造成功记录。Restart read从canonical run/attempt/work bytes及各自SHA-256重建，并逐项复核P8-03 source、Runtime/Extension-set和artifact lineage。

Machine report记录冻结state/pair、attempt pair、migration/table、未实现边界，并声明JUnit中的materialize/read/transition微秒值只是development observation且threshold为`null`；pytest/JUnit同时负责事务、并发、scope和mutation证据。当前没有PlanningRun model/solve/validation timing、broker delivery/lease指标、trace exporter、dashboard、alert、SLO、retention/SIEM或真实host correlation；工程耗时和durable audit都不等于Production observability完成。

## TASK-P8-03 ingress observability and durable audit

每次application结果提供sanitized `canonical_ingress.completed` projection：request/correlation/result IDs及fingerprints、disposition、idempotency outcome和可选PlanningRun ID，不含raw idempotency key、完整payload、SQL/DSN、stack或存储path。`CREATED`成功原子append一份`audit-event.v1`，以现有合法`EDIT_SCHEDULE + PLANNING_RUN + COMMAND`表示初始run创建，并绑定actor reference、resolved `edit` capability、auth policy、plane/environment、request/key/scope fingerprints、correlation和code commit。

Exact replay返回原ingress、CREATED PlanningRun、Runtime/Extension-set、Snapshot、Problem和创建audit reference，响应idempotency outcome变为`REPLAYED`但不追加第二份业务audit；same key/different fingerprint返回`IDEMPOTENCY_CONFLICT`且无artifact/audit。Data Validation、Snapshot/Problem或事务失败也只产生sanitized result和可选内存quality evidence，不伪造成功audit。Durable record额外保留canonical source/authority/mapping、build plan、quality与prepared artifact lineage，使后续P8-04可从单一证据边界接管状态，而不能跳过CREATED。

当前证据是synthetic、进程内projection与SQLite/PostgreSQL兼容的repository/migration合同测试；尚无Production metric/trace backend、SIEM、retention/redaction批准、alert/SLO、clock-skew策略或真实host correlation。migration downgrade会删除P8 ingress/Problem/audit证据，执行前必须按未来retention/backup政策留存引用；已有Snapshot表不随`0006`回滚删除。

## TASK-P6-08 aggregate drift/fallback monitoring

`SIM-P6-DURATION-MONITORING-001@1.0.0`只接收一个固定8-observation、run-scoped的去标识aggregate window。输入仅保留window/version/policy lineage、observation/fallback/quality/late counts及四个`HIGH/LOW/MID_HIGH/MID_LOW` bucket counts；禁止FeatureRecord、raw feature、label、operation/resource/source/row/user identifier、credential和自由文本。Validator在任何unknown field、计数不闭合、mixed model/feature version、late observation、raw/private key或content identity篡改时生成sanitized default-disable报告，不把拒绝的原值复制到证据。

`p6-duration-monitoring-check-report.v1`固定比较fallback rate不高于`1/4`、feature total variation不高于`1/4`、quality pass ratio不低于`3/4`、late count等于0且window count等于1。边界值inclusive；任一breach或无可靠telemetry产生`DEFAULT_DISABLE`建议、`DRIFT_GATE_DISABLED` runtime fallback及稳定reason，健康window只产生`NO_DISABLE_RECOMMENDATION`。Report是deterministic aggregate evidence，不执行disable、告警、retrain、promotion或rollback，也不写业务audit/state。

Retention固定为单次report构造期间最多1个aggregate window、`persistence=NONE`；实现无log/metric/trace exporter、external alert、dashboard、SIEM或Production storage。该development monitor不建立Production telemetry backend、on-call owner、retention policy、SLO、capacity或自动响应权；OPEN-010/011/014/015继续OPEN。

## TASK-P4-13 browser evidence edge

UI把correlation ID、query/projection/resource fingerprints、event positions、Request/attempt IDs、DRAFT/ChangeReport references及raw UTC保留为可复核证据；不在browser生成业务AuditEvent或覆盖server authority。Action acknowledgement与unknown-outcome恢复绑定同一action fingerprint/body/key，便于把浏览器证据连接到P4-12 transport和application audit。

Vitest、Playwright JSON/JUnit/HTML及失败时trace/video/screenshot进入CI artifact，`p4-replanning-frontend-report.v1`记录Task、exact commit、Diff base、Impact Rules、checks/issues与bounded fixture。它们只属于development correctness；尚无Production telemetry backend、SIEM、retention、alert、SLO、capacity或SLA。

## TASK-P4-12 transport observability

所有P4 response固定回传`X-Correlation-Id`和`Cache-Control: no-store`，并要求application envelope的correlation与route逐字一致。Authentication/capability/scope/Production denial使用既有sanitized `AuthorizationAuditRecord`，记录capability、`PLANNING_SCOPE`、outcome/reason/plane/environment，不记raw token/key。成功ExecutionEvent/Replan/ChangeReport audit内容仍由对应application/persistence owner原子产生，router不伪造业务audit。

## TASK-P4-08 result-application audit edge

Durable correlation现连接`Request → attempt/PlanningRun → SolverReport → fresh Validation/KPI/ChangeReport → new DRAFT → result`。Intent transaction保存Request与attempt两类audit，result transaction保存result audit；same command replay复用既有三条业务audit，不重复写入。Terminal no-candidate也保存exact SolverReport envelope，便于区分UNKNOWN/INFEASIBLE/FAILED。

`p4-replan-application-report.v1`输出Task、exact code commit、Diff base、8个Impact Rules、checks/issues和transaction manifest；runtime/memory/SQLite observation只属Development。未配置Production log/trace backend、SIEM、retention、alert或SLO。

## TASK-P4-04 audit evidence

每个成功ingress原子写`EXECUTION_EVENT_APPENDED`，每个成功projection原子写`PROJECTION_CHECKPOINT_COMMITTED`；audit含aggregate/correlation/idempotency/fingerprint/occurred time且exact replay不重复。失败注入证明Snapshot/checkpoint/audit整批回滚而已成功ingress ledger保留。当前没有Production telemetry pipeline、metric threshold、SIEM、retention policy或external trace export。


## TASK-P4-03 durable evidence slice

ExecutionEvent ledger、request/attempt/result关联和internal audit record现在保存stable identity、canonical fingerprint、plane/factory、correlation与artifact reference；exact replay返回原logical record，不追加重复审计。Machine report记录table/index/FK/unique、DB rejection、Production rejection与rollback计数，但不把wall clock或SQLite runtime解释为业务identity或SLA。原始payload全文、credential、SQL和stack仍不得进入audit/log。

## TASK-P4-01 observability chain

ADR-0013～0015固定stable correlation/identity链：authority/source position/event fingerprint→ledger disposition→projector/checkpoint/fact/new Snapshot→ReplanRequest/PlanningRun/Solver/fresh Validator→new DRAFT/ChangeReport→Simulator run/seed/virtual clock/stream hash。Ingress、projection和result application分别保留原子成功/失败audit；exact replay引用原logical result，不改写历史event。

Received-at、host wall clock、runtime/memory与线程顺序保留为raw development observation但不进入semantic identity。TASK-P4-14/15必须同时检查raw、semantic、失败和corrective chain；不得记录secret或以log替代durable ledger/audit。当前metric/log/trace配置及Production monitoring/retention/SLO不变。

## TASK-P3-17 audit conclusion

ScheduleVersion decision/publication/export的success与denial audit、correlation、redaction、lineage、raw runtime observation及provider artifacts已独立重放；0 issue/0 gap。Production retention、alerting和SLA仍未形成。

## TASK-P3-14 evidence observability

Gate报告保留每个subreport的raw checks/issues/counts、四类rejection详情、两轮semantic fingerprint、P2/Frontend引用与前序closure map；CI artifact再绑定exact SHA/Task/Impact Rules。它不增加Production telemetry、dashboard、alert、retention或SIEM，也不把runtime microseconds解释为SLA。

## TASK-P3-13 control evidence

每个command/download都保留correlation；成功UI显示server-confirmed operation，unknown outcome显示correlation并要求authority refresh。Audit/history页面只读已有append-only events；download响应额外携带package、manifest、archive和completion-audit identifiers，使保存的bytes可回指EXPORTED Job，不暴露storage path。

Playwright JSON/JUnit/HTML和failure trace/video/screenshot、Frontend 12-check report、API 18-operation report与Task trace report构成本Task CI artifact。它们没有形成metrics backend、log retention、SIEM、alert、Production audit owner或SLO。

## Structured log contract

PlantNexus application logger 输出单行 JSON，稳定包含 `event`、`level`、UTC timestamp；调用方可绑定 `correlation_id`，并在存在时绑定 `run_id`、`job_id`。若当前 OpenTelemetry span 有效，processor 注入 32 字符 trace ID 与 16 字符 span ID；P0 不配置 exporter、collector 或 sampling policy。

所有 payload 在渲染前递归 redaction。Secret/endpoint/raw exception 不得成为 correlation 或 diagnostic 便利的代价。日志不是唯一 provenance 或 audit store；code/spec/schema/commit 由 health/build metadata显式提供，业务运行仍必须在未来持久化 manifest/audit。

## Health contract

`/health/live` 只报告 process 与 build metadata，不访问外部服务。`/health/ready` 调用 lazy database/redis probes：全部成功为 HTTP 200/UP；任一失败为 HTTP 503/DOWN，并只暴露稳定 dependency code。两者使用 `health-report.v1` Python payload contract；它还不是对外 versioned JSON Schema/product API。

## 已有与缺失 evidence

TEST-OBS-001 的 P0 slice 位于 [`test_logging.py`](../../backend/tests/integration/test_logging.py)，health/config evidence 位于 [`test_config_and_health.py`](../../backend/tests/integration/test_config_and_health.py)。machine report 固定成功/失败 health 示例与 redacted log 示例。

P8-05工程报告已形成单一synthetic执行的worker/solve/validation/total duration、结果计数和安全lineage观测，但没有形成Production model-size/memory基线，也没有metric backend、trace exporter、dashboard、alert、SLO、retention/redaction review或clock-skew/collector failure behavior。外部platform logs和Production monitoring仍未运行；因此NFR-OBS-001不能被解释为完整PlanningRun observability已经形成。

## P3 audit allocation

P3-02定义AuditEvent carrier，P3-03形成append-only persistence，P3-07～10为command/decision/publish/export/API记录actor capability、reason、correlation/idempotency key、source/target version与result；P3-14核对Gate，P3-17最终核对完整性和exact provider lineage。P3-16只计划本地化展示且必须保留raw audit值，P3-15只形成治理。真实identity、retention/SIEM、dashboard/alert/SLO继续未决定，本次没有新增审计实现或Production observability。

TASK-P3-01已固定`audit-event.v1`的人类语义：event identity/version/UTC、stable actor reference与resolved capability、environment/plane/action/aggregate/target、sanitized reason、request fingerprint/idempotency reference、完整P2/P3 lineage、before/after或source/new Version、result/error/replay和correlation/code/schema/policy versions。成功state/idempotency/audit必须同一一致性边界；audit append-only，纠正只能追加引用旧event。

该carrier机器Schema与durable store仍未形成。Structured log/trace不替代audit，read access日志与business audit分开；retention、SIEM、legal hold、backup/restore、dashboard/alert/SLO和external collector继续未决定。

## TASK-P3-03 append-only audit storage

`audit_events`现在按plane+event ID保存完整canonical carrier/SHA，按aggregate/time和correlation建索引，并以可选scope/key unique实现exact replay/conflict。Parent event必须在同plane存在；database trigger禁止任何update/delete，纠正只能由后续application追加新event。Caller-owned transaction入口允许P3-07～10把成功state/idempotency/audit放在同一transaction，但本Task不自行写业务audit。

Machine evidence只证明synthetic append/replay/conflict/list/trigger/rollback。Audit retention、legal hold、SIEM、PII policy、dashboard/alert/SLO、backup/restore与Production identity仍未形成。

## TASK-P3-04 business audit slice

成功submit-for-review现在把DRAFT→READY与单一`SUBMIT_FOR_REVIEW` event原子提交；event绑定actor/auth-policy/capability、reason、correlation、key/request fingerprint、完整lineage、before/after/source/new version、result和code commit。Exact replay不会追加第二条event，same-key conflict使本次schedule transaction回滚；machine check另记录transaction观测微秒但明确`SLA=NOT_DEFINED`。

CLI FAIL只输出稳定reason/error type/fixed message，不输出SQL、DSN、credential或stack。该证据不形成read-audit API、retention/legal hold/SIEM、metrics backend、dashboard/alert/SLO、Production identity或backup/restore。

## TASK-P3-05 query evidence

Read-model machine report记录Task/exact code commit、14 views/counts、payload/comparison fingerprints、query/comparison replay、source/projected bytes、observed microseconds、negative reasons、durable counts before/after及product-service Solver invocation=0。Audit read view只呈现既有event reference，不产生“读取日志”业务event或修改历史。FAIL artifact继续只暴露稳定reason/type/fixed message；没有新增metric backend、retention、alert或Production SLA。

## TASK-P3-06 command evidence

每条成功command audit绑定actor/policy/capability、sanitized reason、source/new Version、request/key reference、fresh validation lineage、correlation、parent event、result和code commit；content event与new DRAFT原子提交，submit event与同content READY CAS原子提交。Machine report记录5 command types（4 content + 1 submit）、5 fresh Validator passes、2 exact replay/1 conflict、historical states、无副作用拒绝、insert/CAS rollback、schedule size及observed microseconds；明确Solver调用0、SLA未定义、Production readiness未声明。

失败CLI只输出stable reason/type/fixed message，既不泄露SQL/DSN/credential/stack，也不把未提交candidate写成成功audit。仍无metric backend、dashboard/alert、retention/SIEM、backup/restore或Production identity。

## TASK-P3-07 decision audit evidence

成功APPROVE/REJECT event固定`intent_type=DECISION`、actor/policy/evaluated capability、sanitized reason、request/hash key reference、完整lineage、READY/terminal同ID/content reference、correlation/code commit与SUCCEEDED result，并与state CAS同事务。授权DENIED event保留同一identity/result但source/new/lineage/before/after均为空；exact replay不改写event内`replayed=false`历史事实。Machine report记录2 decision types、3 success、2 replay、1 conflict、3 denial audit、4无业务state拒绝、1 rollback与并发单winner。

这些字段可供未来audit projection，但没有metrics backend、dashboard/alert、retention/SIEM、legal hold、backup/restore或Production identity。Observed microseconds只为development事实，不建立SLA。

## TASK-P3-08 publication audit evidence

成功PUBLISH event固定`PUBLICATION` intent、actor/policy/publish capability、sanitized reason、request/hash key、完整lineage、APPROVED/PUBLISHED reference、correlation/code与SUCCEEDED result，并与new/old CAS、PublicationResult/current同事务。DENIED无source/new/lineage/before/after；exact replay不改写event。Machine记录3 success、2 supersession、1 replay、1 conflict、2 denial、4无业务state拒绝、1 rollback及1 concurrent winner。

这些仍是临时SQLite与machine artifact；没有metrics backend、dashboard/alert、retention/SIEM、external delivery telemetry或Production SLO。

ExportJob append-only audit覆盖create、attempt/retry、failed/recovered、cancel与complete的before/after/outcome/request/key reference/actor/policy/correlation/code；heartbeat只更新同lease operational metadata。Manifest记录package/file/lineage事实，machine report记录counts/boundaries/issues。尚无metrics backend、lease-expiry alert、orphan artifact scanner、retention/SIEM或Production SLO；OPEN-012继续OPEN。

## TASK-P3-10 transport observability

每个API response回传`X-Correlation-Id`且`Cache-Control: no-store`；client correlation与carrier冲突在委托前以422拒绝。高风险authorization denial通过可注入sink记录operation、actor/resource/policy/reason/correlation/UTC，不写Bearer/raw key。`p3-planning-workspace-api-report.v1`记录17 route/delegation、error/auth/boundary计数与OpenAPI fingerprint；这不形成metrics backend、retention、SIEM、alert或Production SLO。
