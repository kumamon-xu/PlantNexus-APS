---
doc_id: DOC-OPS-003
title: P0 Worker Reliability 与 Idempotency
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [34, 65, 66, 67]
last_reviewed: 2026-08-25
---

# P0 Worker Reliability 与 Idempotency

## 通用 Job 原语

`JobRecord` 是 business-neutral immutable value：QUEUED 被 claim 后进入 RUNNING，attempt 加一，记录 owner/started/heartbeat/lease；只有 owner 且在 lease 到期前可 heartbeat 或 complete。heartbeat 延长 lease；到期时 `mark_stalled` 进入 STALLED并清除 owner/lease；STALLED 可由新 worker claim，attempt 再加一。成功/失败进入终态，失败必须有 stable failure code。

这些状态只诊断执行，不是 PlanningRun、ScheduleVersion 或 ExportJob 状态。Job STALLED 不推断业务 run 结果；通用 SUCCEEDED 也不证明 artifact、manifest、Validator 或 publish 成功。

## 幂等合同

`IdempotencyStore` protocol 以 `(scope, key)` 识别请求，以 lowercase SHA-256 request fingerprint 判断等价：首次注册保存 logical ID；同 fingerprint replay 返回原 record；不同 fingerprint 明确 conflict。`InMemoryIdempotencyStore` 用锁保证单进程线程原子性，只是 reference implementation，进程重启、多个 worker、DB transaction 和 side-effect exactly-once 均不受保证。

## Adapter 与 persistence skeleton

Celery 只接受/发送 JSON，启用 late ack、lost-worker reject、prefetch=1、started/event 和 UTC；没有注册业务 task。Alembic revision `0001_engineering_job_metadata` 建立 `engineering_job_records` 与 `engineering_idempotency_records`，并提供 reverse-order downgrade。migration test 在临时空 SQLite DB 验证结构 round trip；Production PostgreSQL migration/repository/locking 没有执行。

Local Compose 提供 API/Worker 分进程启动与 Redis/PostgreSQL health dependencies，但 acceptance 只运行 `docker compose config`，不启动容器、不进行故障注入。named volumes 可能包含用户数据；rollback 不得通过删除 volume 代替 migration downgrade/备份策略。

## Evidence 与后续门

[`test_job_reliability.py`](../../backend/tests/integration/test_job_reliability.py) 覆盖 owner、expiry、heartbeat、STALLED/retry、attempt、terminal transition、UTC 与并发 idempotency；[`test_migrations_and_infrastructure.py`](../../backend/tests/integration/test_migrations_and_infrastructure.py) 覆盖 migration/lazy clients/Celery/no business task。

真实 durable repository、row/advisory lock、lease scanner、retry/backoff/dead-letter、worker shutdown/cancel、PostgreSQL/Redis outage/partition、Export manifest/storage commit、double publish/event prevention 和 audit trail 全部 `PLANNED`。NFR-REL-001/TEST-IDEMPOTENCY 只形成 P0 primitive slice。

## TASK-P1-03 durable Import staging slice

Raw Staging新增首个business-specific durable idempotency repository。唯一scope为`data_plane + source_system + idempotency_key`；stored request fingerprint覆盖source/version、content digest、安全metadata、synthetic provenance和ordered row digests。完全一致的retry返回首次batch/received-at并标记`replayed=true`，fingerprint变化返回`IDEMPOTENCY_CONFLICT`，不会覆盖旧行。

batch metadata与全部opaque rows在一个SQLAlchemy transaction插入；integration trigger在第二行故障时证明batch/rows均rollback且原driver detail不泄漏。repository无update/delete，duplicate row identity由immutable contract和DB key双层拒绝；plane-scoped query不暴露另一data plane记录。

该slice没有创建ImportJob/Celery task、lease/heartbeat/scanner、distributed side-effect exactly-once或真实PostgreSQL concurrency/outage测试。P0通用`engineering_idempotency_records`保持独立，未被Raw Staging复用或改写；未来Worker编排必须调用本repository而不能把Job success等同于canonical Import成功。

## P3 idempotency allocation

P3-03负责version/audit/export repository的transaction与unique-key基础；P3-08负责publish same-key same-result/conflict和supersession，P3-09负责ExportJob retry/atomic package，P3-10负责HTTP idempotency envelope。Publish成功、ExportJob成功和外部传输必须分离，worker重试不得重复副作用或改写PUBLISHED内容。当前没有新增worker、lease、outbox或Production exactly-once证据。

ADR-0012现固定最低scope=`data_plane + action + resource/version + target + idempotency_key`，request fingerprint覆盖contract version、state/content precondition、payload、reason和target。same key/same fingerprint返回原logical result且不重复业务audit/state/artifact；same key/different fingerprint为conflict。Approve/Reject、Publish和Export各自独立scope，timeout后必须先查询原result，不能换key盲重试。

Publish transaction只处理APPROVED→PUBLISHED/current/必要supersession/audit；ExportJob独立执行既有pair、attempt/retry/atomic manifest-last，永不调用Publish。TASK-P3-01没有实现DB unique/CAS、lease/heartbeat、worker、storage、outbox或network exactly-once；这些仍由P3-03/08/09及未来external adapter负责。

## TASK-P3-03 durable primitives

DB unique现覆盖Audit/Publication/Export的plane+scope+key，concurrent PostgreSQL insert race在savepoint内解析为exact replay或conflict；SQLite保留外层transaction rollback。ScheduleVersion/ExportJob使用expected state+monotonic revision CAS。ExportJob claim/retry显式接收future UTC lease expiry并递增attempt，heartbeat校验owner、未过期与revision；完成/失败/cancel从`EXPORTING`时也必须持有active lease。

Publication repository可以在一个caller transaction内append immutable result并CAS current reference，exact replay不会再次移动current；它不执行APPROVED→PUBLISHED或旧current→SUPERSEDED。没有worker、automatic retry、outbox、package/storage/network side effect或distributed exactly-once，P3-08/09仍须组合业务事务与失败恢复。

## TASK-P3-07 synchronous decision idempotency

Decision scope固定`plane/action/ScheduleVersion/WORKSPACE_INTERNAL`；raw key仅生成hash reference和Audit ID。授权在replay前重新执行；same request读取原SUCCEEDED或DENIED event，different fingerprint冲突。首次成功使用ScheduleVersion expected READY+state revision CAS与Audit append同事务；audit failure回滚，concurrent APPROVE/REJECT只允许一个winner，winner重试可exact replay。该语义不依赖process-local store，也不创建retry job。

本Task没有worker、automatic retry、outbox、queue或network exactly-once。P3-08 publication与P3-09 ExportJob拥有独立scope/事务，不能复用decision key或把APPROVED自动排队为publish/export。

## TASK-P3-08 synchronous publication idempotency

Publication scope固定`plane/PUBLISH/ScheduleVersion/SIMULATION_INTERNAL`；raw key形成hash/Publication/Audit identity。授权在success replay与resource lookup前重新执行；same request从原audit重建result，不重复state/current/audit，different fingerprint冲突。首次成功将new publish、optional old supersede、result/current/audit置于一个caller transaction；audit/current failure回滚，两个并发candidate只有一个current CAS winner。

该证据不使用worker、automatic retry、outbox、queue、network或distributed exactly-once。超时调用者必须以相同key重试，不能换key盲发；P3-09 ExportJob仍拥有独立scope/attempt/side effect。

P3-09 business worker以repository CAS claim现有CREATED/FAILED，attempt单调增加且lease owner reference不可逆hash；active lease才可heartbeat/complete/fail，过期lease仅可审计恢复FAILED/CANCELLED。Package按attempt使用独立destination，payload/manifest确定性且existing exact bytes重放、差异冲突；DB completion失败时artifact不等于EXPORTED，后续显式retry生成新attempt。没有automatic retry、queue/outbox、distributed lock或external exactly-once承诺。
