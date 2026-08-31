---
doc_id: DOC-OPS-002
title: P0 Observability 与 Audit 边界
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [29, 42, 65, 93, 95]
last_reviewed: 2026-08-31
---

# P0 Observability 与 Audit 边界

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

尚未形成 PlanningRun model size、build/first-feasible/solve/validation duration、objective/bound/gap/memory metrics，未形成 metric backend、trace exporter、dashboard、alert、SLO、audit event/table、retention/redaction review 或 clock-skew/collector failure behavior。外部 CI run、platform logs 和 production monitoring 也未运行；因此 NFR-OBS-001 只获得基础日志关联 slice，不能声称 PlanningRun observability 完成。

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
