# SIM-P1-INGRESS-001@1.0.0 生成说明

本目录是 P1 Standard Import ingress correctness/replay asset，不是生产参数、容量基线、
Benchmark 或 Solver 运行证据。Profile、ScenarioSpec、generator identity 与 seed 共同定义一次
可重放的合成输入；生成结果必须先成为 ReferenceFileAdapter-v1 形状的 Raw Staging rows，再经
公开 normalization 与 data-validation 边界得到 `import-package.v2`。

## Provenance

| Artifact | Version / identity |
|---|---|
| FactoryProfile | `PROFILE-SIM-P1-INGRESS-001@1.0.0` / `factory-profile.v1` |
| ScenarioSpec | `SIM-P1-INGRESS-001@1.0.0` / `scenario-spec.v1` |
| Generator | `PLANTNEXUS-P1-CANONICAL-IMPORT-GENERATOR@1.0.0` / seed `20260820` |
| Mapping | `P1-SYNTHETIC-SOURCE-MAPPING@1.0.0` |
| Unit registry | `unit-conversion-registry.v1` |
| Canonicalization | `canonical-json.v1` |
| Import package | `import-9eea9bd41216b3a2b337a83f2b6f5438a287f219251168ce8d574f4b9fb6b2c6` / `import-package.v2` |
| Canonical dataset | 16 non-empty collections / 49 records / `sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4` |
| Quality report | `import-quality-600341c55f6f8511bd25387fcf2a9f3ff62d2c72901f8bb454df32636b4cafbe` / PASS / 0 errors |

`generated_at`只属于 generator-local `synthetic-generation-manifest.v1`，不进入 canonical
Import bytes/hash。发布的 `scenario-manifest.v1`仍只引用 Import v1，因此本 Task 不修改或重新解释
该已发布 Schema。

## Registered quantitative assumptions

| ID | Values fixed only for this asset/generator version |
|---|---|
| `SIM-ASSUMPTION-010` | Profile固定 2 workshops、2 lines、4 capacity-1 resources、2 orders、每 routing 3 operations、每 operation 2 candidates、每 resource 1 calendar fragment；Scenario比例均为 0.5。Generator v1从命名 seed 选择 10–50 piece order quantity、0–600 s setup、300–900 s cycle、0/600 s transport；material delay 为 90 min；calendar fragment 为 30 min且按 3 h间隔；medium due window 为 12 h；running observation/lock offsets分别由 material-ready 后 30/15 min与 2 h/60 min构成。合成 timeline origin由 seed在 2026 UTC年度内选择。 |

这些数值不定义通用 XS、生产产能、标准工时、真实班次、交期规则、WIP/lock分布或生产默认值。
更改任一算法边界必须提升 generator/asset version并登记新的 assumption，而不能覆盖本版本。

## Expected generated shape

- 16 个 `canonical-records.v1` collection key 全部存在。
- topology、routing、order、calendar collection 非空；0.5 quota使 material delay、RUNNING fact、
  operation lock 各覆盖 2 个 orders/lots 中的 1 个。
- Routing是 route-local chain DAG，每道 operation有 2 个显式 resource options与版本化 duration
  provenance；所有 duration在源记录中携带值和单位。
- Import quality report为`PASS`且`error_count=0`。
- 该 asset不构造 Snapshot、Problem、Schedule、Solver或 Production对象。
