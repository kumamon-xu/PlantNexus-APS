---
doc_id: DOC-OPS-002
title: P0 Observability 与 Audit 边界
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [29, 42, 65, 93, 95]
last_reviewed: 2026-08-19
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
