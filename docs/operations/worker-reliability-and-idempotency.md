---
doc_id: DOC-OPS-003
title: P0 Worker Reliability 与 Idempotency
status: baseline
spec_version: 0.3.0
phase: P0-P8
normative: true
source_sections: [34, 65, 66, 67]
last_reviewed: 2026-09-05
---

# P0 Worker Reliability 与 Idempotency

## TASK-P8-05 asynchronous Solver Worker

P8-05注册唯一业务task `plantnexus.planning_run.solve.v1`。消息的exact字段为`message_version/planning_run_id/work_item_id/worker_id`；data plane和attempt只能由server-bound repository及immutable work item解析，`worker_id`只是受限operational lease owner reference。Runtime、Extension set、Solver、Validator、Policy、Limits和可执行实现全部由服务端启动组合绑定，消息不能选择module、class、path、plugin或配置。Celery继续使用late ACK、worker-lost reject、JSON serializer和`prefetch=1`；broker redelivery只重放同一attempt/work，业务attempt仍只能由P8-04显式retry追加。

Worker先把通用`engineering_job_records`中的确定性job绑定到immutable work item，再以owner、revision和未过期lease执行claim/heartbeat/complete CAS。默认heartbeat/lease为30/120秒且由服务端配置；Runtime/work/input fingerprint在claim前、求解后及恢复时逐字复核。真实Global CP-SAT候选必须先通过Solver bundle合同，再由独立fresh `ProblemScheduleValidator`复验并重算KPI。结果先写入`planning_run_worker_results`不可变检查点，然后只沿冻结PlanningRun pair推进；`COMPLETED` CAS之后才调用既有ScheduleVersion application，且业务task只有在该应用成功后才ACK。非candidate、Validator失败、取消、业务timeout或fingerprint drift都不得创建成功ScheduleVersion。

`0008_planning_run_solver_worker`新增append-only `planning_run_worker_jobs`和`planning_run_worker_results`，前者固定job/run/attempt/work/plane/runtime lineage，后者保存canonical result bytes、digest、outcome和exact artifact references。重复结果只有bytes完全一致才视为replay，冲突或损坏一律fail closed。崩溃发生在检查点前时，lease到期后把attempt收敛为`TIMED_OUT`，由显式retry创建新attempt；崩溃发生在检查点后且work timeout未到时，恢复器把job置为`STALLED/REQUEUE`并在同一work上完成状态或ScheduleVersion补偿，不再次求解。若已完成run但ScheduleVersion应用失败，redelivery仍只从检查点补齐同一版本；取消/timeout在检查点或发布竞争中获胜时不得补发成功结果。

本切片的可靠性证据覆盖正常、并发重复、进程崩溃前后、结果写入失败、取消/timeout race、Runtime drift、Validator mutation和ScheduleVersion应用恢复。SQLite与单进程Celery task调用只证明development correctness；真实Redis/PostgreSQL故障、网络分区、多host lease、dead-letter/backoff、优雅停机、Production容量/SLA、监控和Runbook仍由P8-06/P8-10及未来部署验证负责，不能据此宣称distributed exactly-once。

## TASK-P8-04 queue-ready orchestration boundary

P8-04为每个P8-03 CREATED run在一个数据库事务中materialize唯一run、attempt、immutable work item、initial transition、command receipt和audit。Command幂等scope包含operation、run和effective scope；raw key只保存hash reference。Same key/same fingerprint返回首次canonical result且不重复记录，different fingerprint拒绝；run update使用expected revision/state/fingerprint CAS，attempt update使用identity/number/revision CAS，并发exact materialize/transition均只有一个winner。Repository以单一数据库快照组装run/attempt/work read model，避免并发提交产生撕裂视图。

Operational attempt状态独立于PlanningRun状态。初始`QUEUED`不表示broker已接收；`DISPATCH_FAILED`/`TIMED_OUT`保留失败attempt并允许追加新attempt/work item，run revision不变，且失败attempt未retry前不得继续推进run。Cancel终结非terminal attempt和run；若attempt已失败/超时则保留其terminal bytes，只终结run。Terminal run永不重开。P8-04没有claim、lease、heartbeat、ack、backoff、dead-letter、Celery/Redis调用、Solver execution或distributed exactly-once；这些仍由P8-05形成并必须消费现有work item/CAS ports。

## TASK-P4-11 ChangeReport export worker

独立P4 worker复用ExportJob的durable idempotency scope、exact create replay、CAS state revision、attempt、lease reference、heartbeat、audit parent chain及fail/retry边界；它不会自动创建Publish或绕过application service。Package destination按`export_job_id/attempt`内容寻址，exact directory replay成功，different bytes冲突，manifest只在所有payload成功后最后写入。

Repository对v3完整carrier执行P4 contract/canonical SHA验证，并以显式兼容projection复用冻结P3 storage table；row/profile tamper仍会拒绝。SQLite和single-worker tests不能证明distributed exactly-once、PostgreSQL concurrency、queue HA或Production recovery SLA。

## TASK-P4-08 application reliability

Result application实现ADR-0013的两事务边界：intent可在后续失败时保留并安全重试；result transaction重新核对current/base/request/attempt/Snapshot/Problem后，把DRAFT、full result envelope和audit一次提交。Same request/key在完成后不再solve并返回exact bytes；different key/content冲突，并发只有一个完整结果，loser重试后读取winner，无partial Version/result/audit。

Audit故障注入证明result transaction全回滚；base与current保持不变。该correctness不形成queue lease、distributed lock/outbox、external exactly-once、Production HA/capacity/SLA，worker拓扑仍由后继范围决定。

## TASK-P4-04 projection reliability

接收与投影被刻意拆成两个事务：ledger+audit先durable，随后完整prefix在单一事务提交Snapshot+checkpoint+audit。Event ID/position与canonical bytes提供append exact replay，checkpoint使用position+revision CAS；响应丢失后以同一predecessor重放时，service重新投影并只有在bytes等于checkpoint Snapshot时返回exact replay。SQLite故障注入覆盖末端audit失败的零partial write。Worker lease/retry/backoff/dead-letter/outbox与distributed exactly-once仍未形成。


## TASK-P4-03 transaction primitive

P4-03形成ledger/request/attempt/result/audit的append-or-exact-replay与checkpoint compare-and-swap；same identity + same canonical bytes返回既有记录，different bytes、position collision、stale/self/backward checkpoint全部fail closed。Repository暴露caller-owned transaction入口并用失败注入证明整批rollback。尚未形成event consumer、projector worker、lease/scanner、retry/backoff/dead-letter、outbox或external exactly-once；这些不能从storage primitive推断。

## TASK-P4-01 reliability decision

ADR-0013把接收、projection和result application拆为三个可重放事务：ledger exact replay不重复projection；projection checkpoint + fact revisions + new Snapshot + Request原子；result application重核stale/current并原子写new DRAFT + ChangeReport + result + audit。Same identity/request与same fingerprint返回原logical result，different fingerprint冲突；gap/late不通过worker重试改写顺序。

ADR-0015用run identity/source position/event-prefix fingerprint实现Simulator restart；它不回滚已投影事实或删除历史。ReplanRequest无状态，attempt继续由PlanningRun承载。具体queue/lease/worker/outbox模型只有在后继Task明确扩卡后才能形成；当前P3 ExportJob worker、external exactly-once与Production HA/capacity/SLA边界不变。

## TASK-P3-17 audit conclusion

ExportJob create/claim/lease/heartbeat/failure/retry/cancel/recovery、same-key replay/conflict、manifest-last atomicity与worker/publish separation均独立PASS。没有分布式Production capacity、external target或SLA结论。

## TASK-P3-14 replay/retry Gate

两轮Gate复验command/decision/publication/export的same-key same-result、conflict fail closed、ExportJob显式retry与terminal immutability，同时确保每轮isolated state不串扰。Gate不增加worker、broker、lease策略或distributed exactly-once承诺；unknown-outcome与Production external retry仍受既有边界约束。

## TASK-P3-13 UI retry and download boundary

UI同步in-flight gate防止double click；已知4xx不自动retry，network/5xx只保留exact command并在authority refresh后same-key replay。ExportJob `EXPORT_FAILED`只通过用户显式`RETRY_EXPORT`且绑定expected attempt；browser不claim/heartbeat/complete/fail。Download只读EXPORTED terminal attempt，绝不把目录存在解释为Job success。

Worker与download共用root-confined destination函数；manifest-last原子写入和full verifier保证partial/tampered目录不会下载。仍无automatic retry、queue/outbox/distributed lock/exactly-once或external transfer承诺，failure只能由新command/attempt纠正而不能改写旧audit/package。

## 通用 Job 原语

`JobRecord` 是 business-neutral immutable value：QUEUED 被 claim 后进入 RUNNING，attempt 加一，记录 owner/started/heartbeat/lease；只有 owner 且在 lease 到期前可 heartbeat 或 complete。heartbeat 延长 lease；到期时 `mark_stalled` 进入 STALLED并清除 owner/lease；STALLED 可由新 worker claim，attempt 再加一。成功/失败进入终态，失败必须有 stable failure code。

这些状态只诊断执行，不是 PlanningRun、ScheduleVersion 或 ExportJob 状态。Job STALLED 不推断业务 run 结果；通用 SUCCEEDED 也不证明 artifact、manifest、Validator 或 publish 成功。

## 幂等合同

`IdempotencyStore` protocol 以 `(scope, key)` 识别请求，以 lowercase SHA-256 request fingerprint 判断等价：首次注册保存 logical ID；同 fingerprint replay 返回原 record；不同 fingerprint 明确 conflict。`InMemoryIdempotencyStore` 用锁保证单进程线程原子性，只是 reference implementation，进程重启、多个 worker、DB transaction 和 side-effect exactly-once 均不受保证。

## Adapter 与 persistence skeleton

P0基线中的Celery只接受/发送JSON，启用late ack、lost-worker reject、prefetch=1、started/event和UTC，当时没有注册业务task。P8-05现新增上节唯一PlanningRun业务task，但未改变其他队列业务。Alembic revision `0001_engineering_job_metadata`建立通用`engineering_job_records`与`engineering_idempotency_records`；P8-05由additive `0008`复用前者并增加专用binding/checkpoint。migration测试在临时SQLite验证round trip与populated downgrade/re-upgrade；Production PostgreSQL repository/locking和真实broker执行尚未验证。

Local Compose 提供 API/Worker 分进程启动与 Redis/PostgreSQL health dependencies，但 acceptance 只运行 `docker compose config`，不启动容器、不进行故障注入。named volumes 可能包含用户数据；rollback 不得通过删除 volume 代替 migration downgrade/备份策略。

## Evidence 与后续门

[`test_job_reliability.py`](../../backend/tests/integration/test_job_reliability.py) 覆盖 owner、expiry、heartbeat、STALLED/retry、attempt、terminal transition、UTC 与并发 idempotency；[`test_migrations_and_infrastructure.py`](../../backend/tests/integration/test_migrations_and_infrastructure.py) 覆盖 migration/lazy clients/Celery/no business task。

P8-05已形成PlanningRun专用durable repository、lease recovery、same-work checkpoint replay及cancel/timeout保护；[`test_p8_solver_worker.py`](../../backend/tests/integration/test_p8_solver_worker.py)、[`test_p8_solver_worker_recovery.py`](../../backend/tests/integration/test_p8_solver_worker_recovery.py)和[`solver-worker-engineering-profile.v1.json`](../../benchmarks/p8/solver-worker-engineering-profile.v1.json)是当前直接证据。通用row/advisory lock、持续scanner service、broker backoff/dead-letter、优雅shutdown、真实PostgreSQL/Redis outage/partition、distributed exactly-once与Production SLA仍为开放边界。

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
