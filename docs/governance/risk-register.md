---
doc_id: DOC-GOV-008
title: 项目风险注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: false
source_sections: [0, 8, 10, 30, 42, 57, 59, 62, 89, 90, 105]
last_reviewed: 2026-08-20
registry_version: 1.0.0
---

# 项目风险注册表

| ID | Status | 风险 | 早期信号 | 当前控制 |
|---|---|---|---|---|
| RISK-001 | MONITORED | 无真实数据导致模型与业务脱节 | 大量 `PROD_OPEN` 长期无关闭证据 | Simulation-First、P7 Reality Gap、禁止生产猜测 |
| RISK-002 | MONITORED | 仿真走测试捷径，未验证真实链路 | Generator 直接构造 CpModel/Problem | 强制 Standard Import → Snapshot → Problem |
| RISK-003 | MONITORED | Solver 与 Validator 共用逻辑导致共同缺陷 | Validator 导入 backend/constraint builder | 模块隔离、Mutation Tests、独立 Rule Sheet |
| RISK-004 | MONITORED | 未支持能力被静默忽略 | Scenario 可运行但缺少对应约束 | Capability Matrix、`UNSUPPORTED_CAPABILITY` |
| RISK-005 | MONITORED | Solver 规模失控 | optional interval、日历碎片、内存快速增长 | Complexity Metrics、XS/S/M gates、分解 ADR 门 |
| RISK-006 | MONITORED | 结果状态被错误解释 | UNKNOWN 被显示成 INFEASIBLE | 状态 Contract 和错误分类测试 |
| RISK-007 | MONITORED | Synthetic 数据污染生产 | 共库、生产启用 sim API | 独立 Database、生产 404/disabled |
| RISK-008 | MONITORED | 重试导致重复发布或事件 | Worker crash 后重复副作用 | idempotency key、lease、audit trail |
| RISK-009 | MONITORED | 过早性能或最优性承诺 | 没有历史数据却设置 SLA | OPEN-012、Benchmark 环境声明、P7 Gate |
| RISK-010 | MONITORED | P5 高级能力大爆炸 | 多个高级约束同时进入一个迭代 | 每能力独立 ADR/Schema/Validator/Fixture/Benchmark |

风险状态、责任人和日期将在团队角色与仓库工作流确认后补充，当前不猜测人员归属。

状态仅允许 `MONITORED`、`MITIGATED`、`CLOSED`。状态变化必须给出可验证控制或关闭证据；未知责任人继续留空，不能为了表格完整而猜测。修改表结构或状态语义必须提升 `registry_version`。

TASK-P0-03 review：strict unknown-field/no-default policy、Production/Synthetic conditional、Solver-neutral types 和 locked contract tooling 加强 RISK-001/002/007 的早期控制，但尚无真实数据、共同 ingress implementation 或生产隔离环境证据，不能据此标记风险已缓解或关闭。RISK-001～010 全部保持 `MONITORED`。

TASK-P0-04 review：独立 rule metadata、validation package import scan 和未来 mutation boundary 加强 RISK-003；capability registry/explicit rejection 加强 RISK-004；error/status mapping test 加强 RISK-006。尚无 candidate ScheduleValidator、Solver、Scenario mutation、状态持久化或 API evidence，不能据此标记风险已缓解/关闭。RISK-001～010 全部保持 `MONITORED`，registry format version 不变。

TASK-P0-05 review：Standard Import-only Generator Protocol/empty package 加强 RISK-002；registry capability rejection 加强 RISK-004；Schema/context/Import Production guard 加强 RISK-007；manifest/version/hash 边界约束 RISK-001/009。尚无非空 pipeline、独立 DB/API/publish guard、历史数据或 Benchmark evidence，不能标记风险已缓解/关闭。RISK-001～010 全部保持 `MONITORED`，registry format version 不变。

TASK-P0-06 review：非空 committed Import 与 replay loader 加强 RISK-002，fixture-local direct C-ID calculation 与 P0-07 evaluator boundary 加强 RISK-003，manifest/assumption/version chain 加强 RISK-001/004/009。由于仍无 P1共同 ingress、通用 Validator mutation、独立 DB/API/publish guard、历史数据或 Benchmark evidence，RISK-001～010 全部保持 `MONITORED`，registry format version 不变。

TASK-P0-07 review：独立 evaluator、formula-free mutation materializer、expected-artifact separation、backend/OR-Tools import scan 和 13 类负例显著加强 RISK-003 的早期控制；wrong-resource/explicit detail 同时加强 RISK-004。证据仍局限 fixture-local vocabulary，尚无 P1 common ingress、P2 Solver comparison/scale/property/benchmark、生产隔离或真实数据，因此不能标记风险已缓解或关闭。RISK-001～010 全部保持 `MONITORED`，registry format version 不变。

TASK-P0-08 review：Production config/no-Simulation-route/Compose separation boundary 加强 RISK-007，lease/STALLED/atomic replay-conflict primitive 加强 RISK-008，deferred Benchmark hook/OPEN-012 边界加强 RISK-009；但尚无独立 production/simulation DB evidence、durable distributed repository、Export/Publish side effect、crash/outage test、真实 Benchmark 或生产平台，因此不能标记 mitigated/closed。RISK-001～010 全部保持 `MONITORED`，registry format version 不变。

TASK-P0-09 review：本地 Schema/Golden/Validator/Replay/Build evidence 与 no-Solver boundary 均复验通过，未发现需要改变现有十项风险状态的新实现事实；workflow handoff failure 与 provider evidence缺失分别登记为 `P0-GAP-002/001` 并追踪到 planned TASK-P0-10，而不是伪装成已缓解控制。RISK-001～010 全部保持 `MONITORED`，registry format version 不变。

TASK-P0-10 review：未弱化 workflow handoff、immutable successful run/artifact 追踪与 protected `main` required `validate` 已关闭 CI evidence gap 并加强工程回归可见性，但不改变 RISK-001～010 的业务、Solver、生产隔离、幂等性或性能事实。这些 P0 CI 证据不足以将任何风险标记 `MITIGATED/CLOSED`。RISK-001～010 全部保持 `MONITORED`，registry format version 不变。

P1 Task 规划 review：共同 ingress、明确 capability/data-quality rejection、独立 canonical builder、Production/Synthetic source guard 和 replay/hash evidence 已分配给 TASK-P1-02～TASK-P1-11，可在执行后分别加强 RISK-001/002/004/007/009 的控制；当前仅为计划，没有 implementation 或 Gate evidence，RISK-001～010 全部保持 `MONITORED`，registry format version不变。

TASK-P1-01 review：phase/task-neutral CI减少stale handoff与错误归属风险，但没有真实provider run、业务pipeline、生产隔离、Solver、Benchmark或side-effect证据，不能将任何风险标记`MITIGATED/CLOSED`。RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-02 review：strict canonical source/version/no-default与Production/Synthetic conditional加强RISK-001/002/007的早期控制，version/fingerprint/rejection tests加强错误consumer可见性；但尚无真实source、共同ingress、独立生产数据面、builder/hash或Benchmark。任何风险均无充分mitigation/closure evidence，RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-03 review：opaque Raw Staging与raw-not-canonical scan加强RISK-002，repository/DB plane guard加强RISK-007，durable replay/conflict和atomic rollback加强RISK-008；source provenance/no-default边界也继续约束RISK-001。证据仍限临时SQLite与synthetic rows，尚无真实Adapter、共同ingress、独立Production数据库、PostgreSQL并发/故障、Snapshot/Problem或Benchmark，因此不足以标记任何风险`MITIGATED/CLOSED`。RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-04 review：versioned Reference Adapter进入同一Raw Staging加强RISK-002，`production_binding=false`/source manifest/no-mapping边界继续约束RISK-001，explicit data plane与synthetic provenance加强RISK-007，exact restaging/conflict加强RISK-008。证据仍限temporary synthetic files/SQLite；没有真实interface/data、common ingress到Problem、独立Production DB、malware/auth或Benchmark，因此不足以标记任何风险`MITIGATED/CLOSED`。RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-05 review：explicit mapping/no-default与OPEN保持约束RISK-001，Adapter→Raw→Normalization单向链及no-later-layer import加强RISK-002，data-plane/provenance冲突拒绝加强RISK-007，deterministic bytes/hash加强replay可见性。证据仍是test-local profiles/rows且尚无Data Validation、common ingress、独立Production DB、真实authority或Benchmark，因此不足以标记任何风险`MITIGATED/CLOSED`。RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-06 review：明确DAG/resource/capability rejection加强RISK-004，单一canonical evaluator与no-Planning/Solver scan加强RISK-002/003，rich deterministic report加强RISK-001可见性；但尚无Synthetic common ingress、Snapshot/Problem、独立Production DB、真实authority、Solver或Benchmark。该早期控制不足以把任何风险标记`MITIGATED/CLOSED`；RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-07 review：PASS-gated expansion、versioned lineage/replay和禁止自动lot/duration规则加强RISK-001/002/004，Production/Synthetic provenance copy加强RISK-007，generated branch/merge/cross-workshop properties提升早期correctness可见性。但尚无common ingress、immutable Snapshot/Problem、独立Production DB、Solver/Validator comparison或Benchmark，因此不足以标记任何风险`MITIGATED/CLOSED`；RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-08 review：PASS/Expansion-gated immutable Snapshot、semantic hash与insert-only trigger加强RISK-001/002，plane-scoped repository和synthetic provenance guard加强RISK-007，atomic exact replay/content conflict加强RISK-008，property mutation提升早期determinism可见性。证据仍限schema sample与临时SQLite，尚无common ingress、independent Production DB/roles、PostgreSQL concurrency、Problem/Solver或Benchmark；不足以把任何风险标记`MITIGATED/CLOSED`。RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-09 review：只经immutable Snapshot进入Problem及no-upstream shortcut scan加强RISK-002，active lock/multi-factory/completed-active边界明确拒绝加强RISK-004，stable builder/hash replay加强RISK-001可见性，错误不映射INFEASIBLE加强RISK-006。证据仍限small synthetic canonical vector；尚无common ingress、独立Production DB、真实数据、Backend/Solver/independent Validator或Benchmark baseline，micro timing也不是capacity/SLA。RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-10 review：七层Generator必须经过Raw/Normalization/Data Validation且AST禁止Snapshot/Problem/Solver shortcut，加强RISK-002；unsupported/version/Profile shape明确拒绝加强RISK-004；manifest/hash和assumption登记提高RISK-001可见性；Production target与synthetic provenance guard加强RISK-007。证据仍是49-record synthetic correctness asset，无真实数据/common ingress/独立Production DB/Solver/Benchmark/校准，不足以标记任何风险`MITIGATED/CLOSED`。RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-11 review：单一staging→Problem application链与no-shortcut scan加强RISK-002，exact stage rejection加强RISK-004/006，三层hash/parity/report提高RISK-001可见性，expected-plane guard加强RISK-007，CI machine artifact加强RISK-008的回放可见性。证据仍限49-record synthetic/reference temporary input和同进程pure chain，无真实Production binding/独立DB、Solver/Validator、Benchmark或校准，RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P1-12 review：独立audit及provider artifacts确认P1-02～11控制未被回归，P1 Gate=`READY`且无实现blocking gap；这加强RISK-001/002/004/006/007/008的可见控制，但没有真实数据、独立Production DB/roles、Solver/Validator、Benchmark、历史校准、发布side effect或生产阈值证据。故不足以将任何风险改为`MITIGATED/CLOSED`；RISK-001～010全部保持`MONITORED`，registry format version不变。

TASK-P2-01 review：versioned complete Problem facts和Backend旁路禁止加强RISK-002，priority/lock/history稳定拒绝加强RISK-004/006，v1/v2 replay/machine artifact提高RISK-001/008可见性，synthetic priority provenance加强RISK-007。证据仍是单一small synthetic contract vector，无Solver/formal Validator/Benchmark/真实authority/Production provider运行，不能把任何风险标记`MITIGATED/CLOSED`；RISK-001～010继续`MONITORED`，registry format version保持`1.0.0`。
