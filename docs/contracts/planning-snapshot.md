---
doc_id: DOC-CONTRACT-002
title: PlanningSnapshot 合同
status: baseline
spec_version: 0.3.0
phase: P0-P1
normative: true
source_sections: [23, 40, 62, 74, 101, 103]
last_reviewed: 2026-08-20
---

# PlanningSnapshot 合同

## TASK-P4-01 event projection boundary

ADR-0013确认ExecutionEvent不能原地修改Snapshot。Ingress先append ledger；只有连续source-position的已验证event/batch才能由versioned projector在原子事务中形成append-only fact revisions、new immutable Snapshot、ReplanRequest/checkpoint/audit。Projector identity覆盖previous checkpoint、ordered event identities/fingerprints、source/rule/projector versions；received-at和runtime timing不进入semantic hash。

Same projection input必须返回相同Snapshot ID/bytes，gap/late/conflict/cross-plane或partial failure不得产生Snapshot。旧Snapshot及其Problem/Run/Version references保持不可变。TASK-P4-02/04若现有v2字段不足必须发布新document/projection version，不能原地改写v2；本Task不修改Schema、repository或migration。

PlanningSnapshot 是某个 cutoff 的不可变计划事实集合，必须 immutable、deterministic、replayable、hashable。

## 最小元数据

```text
snapshot_id
cutoff_at
source_versions
rule_version
snapshot_hash
entity_counts
synthetic
scenario_id (synthetic only)
```

Synthetic Snapshot 还应能追溯 scenario/profile/generator/seed。Production Snapshot 必须 `synthetic=false`，且不得引用 synthetic-only source。

## 确定性

同一 canonical dataset、cutoff、规则版本和 Schema 版本必须得到相同 `snapshot_hash`。Hash 输入使用稳定排序和 canonical serialization，不包含随机 UUID、生成时间等非业务噪声。

## 不可变性

Snapshot 创建后不允许就地修改。输入事实变化、执行事件或规则版本变化必须产生新 Snapshot。删除/更正原始导入不得改写已被 PlanningRun 引用的 Snapshot。

## P0 Schema 骨架要求

[`planning-snapshot.schema.json`](../../schemas/json/planning-snapshot.schema.json) 已固定 `snapshot_version=planning-snapshot.v1`、最小元数据、严格 UTC `Z`、根对象未知字段拒绝和 synthetic/scenario 条件。Production (`synthetic=false`) 禁止携带 `scenario_id`；synthetic Snapshot 必须携带。

P0 sample 明确标记 synthetic，且 hash/builder 值标明不是生产结果。Snapshot builder、canonical serialization、hash 计算和 entity payload 仍为 P1 `PLANNED`；当前 skeleton PASS 不等于 REQ-002 实现完成。

## TASK-P1-02 v2 payload contract

[`planning-snapshot.v2`](../../schemas/json/planning-snapshot.v2.schema.json)要求schema/source/rule/normalization/expansion/canonicalization versions、Import v2 dataset hash、`import-quality-report.v1` PASS reference、严格entity counts、canonical records、expanded `operation_instances`与`operation_precedence_edges`。实例显式保留DemandOrder→ProductionOrder→ProductionLot→RoutingVersion/Operation lineage、release/material/due、required capabilities、candidate级duration/source version、execution fact和lock引用；COMPLETED可作为Snapshot事实保留。

Synthetic v2必须携带scenario/profile/generator/version/seed，Production v2禁止该provenance。Schema中的`sha256:`字段只固定格式；TASK-P1-02的contract sample digest是形状占位，不是hash builder证据。Canonical serialization、hash projection、deterministic snapshot ID、insert-only repository与immutability测试由TASK-P1-08形成并记录于下节，不能只从v2 Schema存在推断REQ-002 evidence。

## TASK-P1-06 quality-report handoff

`import-quality-report.v1`现在已有真实producer和PASS/FAIL machine contract；只有`status=PASS`且`error_count=0`的报告可满足Snapshot v2既有`import_quality_report`引用语义。报告的`report_id`由版本、package ID、status/count和有序Error v3内容派生，不能引用另一个Import或手工把FAIL改为PASS。

TASK-P1-06本身不创建Snapshot，也不计算Snapshot schema内的Import dataset hash；它交给TASK-P1-08同时核验报告与目标Import/package hash的绑定并构建immutable payload。Quality PASS单独存在仍不能替代Expansion、Snapshot entity counts/hash或repository evidence；下节记录当前实现。

## TASK-P1-08 immutable builder and hash contract

`snapshot-hash-projection.v1`对白名单中的Snapshot v2业务字段做`canonical-json.v1`编码：包含cutoff、全部canonical records、expanded instances/edges、entity counts、source/rule/normalization/expansion/schema/canonicalization versions、Import dataset hash、quality report引用及conditional synthetic provenance；排除self `snapshot_id/snapshot_hash`和不属于Snapshot合同的received/generated/runtime噪声。Canonical record collections、capabilities、calendar intervals、instance candidates/locks和edges按稳定ID/值排序，业务时间字段不会被当作噪声删除。

`snapshot_hash=sha256(canonical projection)`，`snapshot_id=planning-snapshot-v2-<digest>`，因此同facts/cutoff/versions产生相同完整Snapshot bytes/hash/ID，任一投影内事实或版本变化产生新identity。Builder只接受内容派生的Import package ID、匹配该Import的zero-error PASS report和bytes/hash/provenance自洽的`order-expansion.v1`；FAIL、stale package、跨Import/plane expansion、非法cutoff或hash tamper均以module-local稳定错误拒绝。

`ImmutablePlanningSnapshot`仅保存frozen canonical bytes与identity，`document`每次返回新copy；SQLAlchemy repository按data plane只提供insert/exact replay/read，应用update/delete明确拒绝。`0003_planning_snapshots`以hash主键、ID唯一、canonical bytes digest和SQLite/PostgreSQL mutation trigger固定insert-only语义；downgrade会删除全部Snapshot，必须只在已确认的开发/测试回滚中执行。Schema v1/v2均未修改，PlanningProblem、PlanningRun、ScheduleVersion、API和Solver仍未形成。

上述合同由implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`及GitHub run `32310098594`的required `validate`/machine artifact重放成功；该provider PASS不扩大Schema、Production或后续Planning能力边界。

## TASK-P1-09 read-only Problem consumer

PlanningProblem builder只接收`ImmutablePlanningSnapshot`并先执行完整identity/bytes/plane验证；它不读取Snapshot repository、Import、Expansion、quality report producer或Raw Staging，也不会改写Snapshot document。Problem hash只保存Snapshot的content-derived ID而不复制整份source chain；该ID已经由TASK-P1-08绑定Snapshot hash、rule、facts和upstream versions。

因此同一Snapshot与同一Problem config可byte-identical replay，Snapshot内任一合法facts/version变化必须先形成新的Snapshot ID，再传播为新的Problem hash。P1-09不改变Snapshot v2 Schema/hash projection/repository，也不允许Problem consumer绕过immutable Snapshot入口。

## TASK-P1-11 common-ingress replay

Common ingress在matching PASS report和`order-expansion.v1`之后仍只调用既有`build_planning_snapshot`；没有修改Snapshot v2 Schema、hash projection、repository或persistence。`SIM-P1-INGRESS-001@1.0.0`以cutoff `2026-11-06T12:30:00Z`得到固定Snapshot hash `sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409`；Synthetic与Reference transport及两次Synthetic replay的完整bytes/hash/ID均相同。

该cutoff/horizon只是versioned Scenario Gate配置，使fixture内既有lock在Problem horizon前结束；不是Production时钟、冻结窗或运行默认。Machine report不持久化Snapshot，既有insert-only repository证据仍由TASK-P1-08提供。

## TASK-P1-12 Exit Gate audit

P1-12的repeat=2和Reference parity再次得到完整Snapshot bytes digest `sha256:dec4302f3606ef450b5f6fd70373ddfd018100fc8fe8f67f8c60779f8ccaab55`、Snapshot hash `sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409`与content-derived ID完全一致。271项回归和focused migration suite同时复验frozen copy、fact/cutoff/version sensitivity、plane guard、insert/exact replay/content conflict及`0003` upgrade/downgrade。

审计没有修改Snapshot v1/v2 Schema、hash projection、repository或migration。P1 Gate=`READY`不等于独立Production数据库、PlanningRun、ScheduleVersion、Solver或发布能力形成。
