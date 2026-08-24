---
doc_id: DOC-OPS-002
title: P0 Observability 与 Audit 边界
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [29, 42, 65, 93, 95]
last_reviewed: 2026-08-24
---

# P0 Observability 与 Audit 边界

## Structured log contract

PlantNexus application logger 输出单行 JSON，稳定包含 `event`、`level`、UTC timestamp；调用方可绑定 `correlation_id`，并在存在时绑定 `run_id`、`job_id`。若当前 OpenTelemetry span 有效，processor 注入 32 字符 trace ID 与 16 字符 span ID；P0 不配置 exporter、collector 或 sampling policy。

所有 payload 在渲染前递归 redaction。Secret/endpoint/raw exception 不得成为 correlation 或 diagnostic 便利的代价。日志不是唯一 provenance 或 audit store；code/spec/schema/commit 由 health/build metadata显式提供，业务运行仍必须在未来持久化 manifest/audit。

## Health contract

`/health/live` 只报告 process 与 build metadata，不访问外部服务。`/health/ready` 调用 lazy database/redis probes：全部成功为 HTTP 200/UP；任一失败为 HTTP 503/DOWN，并只暴露稳定 dependency code。两者使用 `health-report.v1` Python payload contract；它还不是对外 versioned JSON Schema/product API。

## 已有与缺失 evidence

TEST-OBS-001 的 P0 slice 位于 [`test_logging.py`](../../backend/tests/integration/test_logging.py)，health/config evidence 位于 [`test_config_and_health.py`](../../backend/tests/integration/test_config_and_health.py)。machine report 固定成功/失败 health 示例与 redacted log 示例。

尚未形成 PlanningRun model size、build/first-feasible/solve/validation duration、objective/bound/gap/memory metrics，未形成 metric backend、trace exporter、dashboard、alert、SLO、audit event/table、retention/redaction review 或 clock-skew/collector failure behavior。外部 CI run、platform logs 和 production monitoring 也未运行；因此 NFR-OBS-001 只获得基础日志关联 slice，不能声称 PlanningRun observability 完成。

## P3 audit allocation

P3-02定义AuditEvent carrier，P3-03形成append-only persistence，P3-07～10为command/decision/publish/export/API记录actor capability、reason、correlation/idempotency key、source/target version与result；P3-14/15核对完整性和exact provider lineage。真实identity、retention/SIEM、dashboard/alert/SLO继续未决定，本次没有形成审计实现或Production observability。

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
