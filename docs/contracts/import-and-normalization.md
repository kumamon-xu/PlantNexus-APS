---
doc_id: DOC-CONTRACT-001
title: Import 与 Normalization 合同
status: baseline
spec_version: 0.3.0
phase: P0-P1
normative: true
source_sections: [0, 2, 10, 15, 16, 62, 63, 73, 74, 91, 95]
last_reviewed: 2026-08-19
---

# Import 与 Normalization 合同

## 管道

```text
Versioned Source Package
→ Raw Staging
→ Parse
→ Normalize fields/units/time
→ Validate references and capabilities
→ Canonical Dataset
→ PlanningSnapshot
```

Production Adapter、CSV、Excel 和 Synthetic Generator 必须输出同一 Standard Import Contract。禁止 Synthetic 输入绕过 staging、unit conversion 或 data validation。

## 原始数据保留

Raw Staging 应保留来源系统、来源版本、导入批次、文件 hash、原始行定位和接收时间，便于诊断但不能直接进入 Solver。

## 规范化

- 时间转换为 UTC，保留来源 timezone/offset 信息；
- duration 规范为整数秒；
- 单位转换规则版本化；
- ID/reference 采用稳定 canonical ID；
- 缺失权威字段不得用仿真或 AI 默认值补齐；
- Excel 禁止执行 macro 和外部公式。

## 拒绝条件

至少包括：route cycle、missing resource、invalid candidate resource、unit error、missing duration、unsupported capability、引用孤儿、非法时间区间。

错误必须包含 code、entity/row、field、observed value、expected contract、source location 和可操作说明。接口的真实字段映射由 OPEN-002/013/015 关闭。

## P0 executable skeleton

[`import-package.schema.json`](../../schemas/json/import-package.schema.json) 只固定 `import_package_version`、`package_id`、`source_versions`、`synthetic`、conditional `scenario_id` 与 `records` envelope。`records` 内字段在 P0 明确保持 opaque，因为 Adapter/单位/字段权威仍受 OPEN-002/013/015 阻塞；这不是允许输入绕过 P1 Normalization/Data Validation。

Production envelope 禁止携带 `scenario_id`；synthetic envelope 必须携带。Import pipeline、字段映射、单位转换实现和 canonical entity validation 仍为 P1 `PLANNED`。

## P0 Simulation output boundary

TASK-P0-05 的 `build_empty_import_package` 只生成符合 `import-package.v1` 的 synthetic metadata envelope：`synthetic=true`、显式 `scenario_id`、profile/scenario/generator source versions 和 `records={}`。它用于证明 Generator 终点是 Standard Import contract 以及 canonical serialization/hash 可重放，不生成任何 Factory/Order/Routing 字段，不执行 staging、Normalization、Data Validation、Snapshot 或 PlanningProblem builder。

Scenario manifest 的 `generated_at` 不进入 Import package，因此不参与 `dataset_hash`；相同 Profile/Scenario/Generator version/seed 的 canonical Import bytes 与 hash 相同。P1 填充 canonical records 时仍必须通过权威映射和正式数据质量链路，不能把本空 envelope 当作 pipeline PASS。

## P0 deterministic fixture records

TASK-P0-06 把 `SIM-MINIMAL-001@1.0.0` 的 10 个 non-empty collection、15 个 record 放入同一 `import-package.v1` envelope，以证明 committed correctness dataset 可 canonical replay/import。collection/field vocabulary 明确标为 `sim-minimal-records.v1`，只供 Golden 手算；它没有被加入 JSON Schema/data dictionary，也不是 P1 Factory/Order/Routing canonical contract。

其 hash `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10` 只覆盖完整 Import JSON，不覆盖 manifest `generated_at`、Golden Schedule 或 expected artifacts。P1 仍必须从 versioned source package 走 staging/parse/Normalization/reference/capability validation；不得直接把本 fixture vocabulary 提升为生产 mapping 或据此关闭 OPEN-002/013/015。

## TASK-P1-02 canonical contract release

Schema set `2.0.0` 新增 [`canonical-records.v1`](../../schemas/json/canonical-records.v1.schema.json) 与 [`import-package.v2`](../../schemas/json/import-package.v2.schema.json)。Canonical records固定16个collection、稳定ID/reference、显式quantity unit、UTC instant、integer-second duration与每条记录的`source_system/source_version/source_record_id`；Import v2还要求schema/source/normalization/canonicalization version。未知字段、缺失unit/duration/source/version、非法UTC和Production携带synthetic provenance均拒绝，不补默认值。

这是set-level major release：`import-package.v1`保持逐字不变，v1/v2不可互换，consumer必须显式选择。v2字段是authority-neutral APS语义，不声明ERP/MES/WMS/CAM列映射，不关闭OPEN-002/013/015；`backend/app/domain/canonical_records.py`只做ID、reference、unit、time、duration和provenance的pure semantic precheck，不实现Raw Staging、Normalization、Data Validation或Adapter。Synthetic sample只用于Schema/round-trip测试，不是正式Scenario、生产事实或common-ingress PASS。

## TASK-P1-03 Raw Staging contract

Raw Staging现以immutable `StagedImportBatch`/`RawImportRow`保存batch ID、data plane、source system/version、content SHA-256、leaf source name、media type、byte length、UTC received-at、row identity/location、opaque bytes与逐行SHA-256。Simulation批次必须完整携带Scenario/Profile/Generator各自版本和seed；Production批次禁止这些synthetic字段。该层不读取CSV/XLSX、不解析JSON、不映射字段、不转换单位/时间，也不调用canonical precheck。

持久化幂等scope为`data_plane + source_system + idempotency_key`。request fingerprint覆盖source/version、content digest、安全metadata、synthetic provenance与按序row digest/location，但排除candidate batch ID和received-at；exact replay返回首次持久化的batch，任何fingerprint差异明确返回`IDEMPOTENCY_CONFLICT`。batch与全部rows在同一SQLAlchemy transaction写入，repository只有`stage/get`，没有update/delete/Snapshot/Problem转换入口。

`0002_raw_import_staging`是internal persistence migration，不改变Standard Import v2或外部字段权威。当前reference evidence使用SQLite验证空库、含1个synthetic batch的destructive downgrade/re-upgrade、transaction rollback与data-plane query guard；真实Adapter、文件安全解析、Normalization/DataValidation和独立Production/Simulation数据库部署仍由后续Task/平台证据形成。

## TASK-P1-04 ReferenceFileAdapter v1

`plantnexus.reference-file@1.0.0`定义严格三列transport contract：`record_type,source_record_id,payload_json`；CSV只接受无BOM的strict UTF-8、固定comma/double-quote dialect，XLSX只接受单一`records` sheet和text cells。Adapter不解析`payload_json`字段语义，而是把三列按sorted compact JSON编码为opaque `RawImportRow.raw_payload`；`record_type + source_record_id`的canonical projection产生稳定row identity。Normalization仍由TASK-P1-05负责。

两种格式的等价输入必须产生相同row identity与raw payload bytes，并保留相同caller source/version/data-plane/synthetic provenance；transport provenance必须忠实不同，包括原文件SHA-256、leaf name、media type、byte length和CSV/XLSX source location。不能为了“对等”伪造相同文件hash或位置。

Reference reader固定4 MiB文件、10000 data rows、3 columns、单sheet、512 archive members和32 MiB uncompressed archive上限；拒绝路径穿越、`.xls/.xlsm`、UTF-8 BOM/非法编码、unknown/missing/duplicate/reordered header、非text XLSX cell、formula-like值、VBA、external link/relationship、DTD/entity及重复/加密/越界archive。该版本是可测试参考入口，`production_binding=false`；不声明ERP/MES/WMS/CAM字段mapping，不关闭OPEN-002/013/015，也不构成malware scanning、authentication或Production security认证。
