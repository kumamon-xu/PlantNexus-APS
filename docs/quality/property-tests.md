---
doc_id: DOC-QUAL-004
title: Property Test 规范
status: baseline
spec_version: 0.3.0
phase: P1-P4
normative: true
source_sections: [45, 86, 87]
last_reviewed: 2026-08-19
---

# Property Test 规范

Property Test 随机生成合法 V1 PlanningProblem 或合法 canonical input，检验跨大量组合保持的不变量。

## 核心性质

- 任何被接受的 Schedule 必须 `validator_passed=true`；
- 每个未完成 Operation 恰排一次；
- 同 resource interval 不重叠且尊重 calendar；
- precedence、material/release、lock、duration 和 horizon 均成立；
- 同 canonical input 和版本产生相同 hash；
- unsupported capability 被明确拒绝；
- 序列化 round-trip 不改变语义。

## 非性质

不要求相同 schedule ordering、相同 Solver search path 或相同 runtime，因为多个同质量解可能正确。

随机失败必须保存最小化 example、seed、Schema/Generator/Problem version 和 Problem hash，确保可回归。

TASK-P0-03 已对两个明确 synthetic sample 执行 JSON serialization round-trip，并验证 UTC/duration/reference 的确定性 helper；这只是 `TEST-CONTRACT-001` 的固定样例证据，不是随机 Property Test、Snapshot/Problem hash replay 或 TEST-PROPERTY 完成。完整性质测试仍为 P1/P2 `PLANNED`。

TASK-P0-06 对固定 `SIM-MINIMAL-001@1.0.0` 复算 canonical non-empty Import round-trip/hash、C-ID 与 KPI；这属于 Golden/Scenario replay，不包含随机生成、shrinking 或多组合不变量，因此不能标记 TEST-PROPERTY 已形成。未来 Property Test 可使用该 fixture 的稳定 ID/hash 作为最小回归种子，但不得改写历史版本。

TASK-P0-07 的 13 个声明式 mutation 验证 deterministic replay、base immutability、C-001～C-011 完整负例 coverage 与固定关键算术；它们仍是枚举的 Mutation Test，不是随机 Property Test。`SIM-MINIMAL-001-MUTATIONS@1.0.0` 可作为未来 generator/shrinker 的固定 regression corpus，但 TEST-PROPERTY 和合法 PlanningProblem 跨组合生成仍为 P2 `PLANNED`。

TASK-P1-02对两份固定synthetic v2 sample执行serialization round-trip，并对canonical reference/unit/time/duration/provenance与Snapshot count/copy不变量做明确mutation负例。这只形成TEST-CONTRACT-001的deterministic contract evidence；没有Hypothesis/random generator、shrinking、seed corpus或Snapshot/Problem hash性质，因此TASK-P1-07/08的P1 property tests与P2 TEST-PROPERTY仍为`PLANNED`。

TASK-P1-05以固定构造覆盖三项deterministic properties：row/input order与volatile batch metadata不改变canonical bytes/hash；mapping profile version改变必然改变bytes/hash；namespaced source identity稳定派生ID且不同namespace/authority不碰撞。另以枚举负例覆盖unit integer arithmetic、DST offsets和schema field-set invariant。这些是TEST-NORMALIZATION-001/TEST-CONTRACT-001的固定property-style evidence，不含随机生成、shrinking或seed corpus；P1-07/08与P2 TEST-PROPERTY继续`PLANNED`。
