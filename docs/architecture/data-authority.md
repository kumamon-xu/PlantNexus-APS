---
doc_id: DOC-ARCH-005
title: 数据权威边界
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [15, 22, 59, 61, 90]
last_reviewed: 2026-08-19
---

# 数据权威边界

| 数据 | 权威来源 | 当前注意事项 |
|---|---|---|
| Order | ERP | 字段级权威仍受 OPEN-015 约束 |
| BOM | ERP | V1 不负责自动 MRP |
| Purchase Promise | ERP | 与 material readiness 的关系待确认 |
| Execution | MES | 已完成/运行中事实不可被计划覆盖 |
| Machine Runtime State | MES | 故障/恢复成为执行事实或事件 |
| Physical Inventory | WMS | V1 不做完整库存平衡 |
| CAM Processing Feature | CAM | V1 不做联合优化 |
| Planning Decision | APS | 必须经过 Validator 和人工审批 |

## AI 边界

AI 可以输出 `duration`、`risk`、`confidence` 及版本信息。AI 不能成为 routing、resource compatibility、hard constraint、schedule state 或业务权重的权威来源。

## Material Readiness

V1 接受上游提供的 `material_ready_at`，并执行 `operation.start >= material_ready_at`。Solver 不猜库存齐套时间。若上游不能直接提供，应通过 `MaterialReadinessProvider` 扩展，并由 OPEN-007/OPEN-015 关闭其权威问题。

## 冲突处理

来源冲突不得由最后写入或 AI 推断解决。应在 Raw Staging/Normalization 阶段保留来源、版本和冲突诊断，根据字段权威规则拒绝或等待业务决策。

## P0 Schema boundary

`import-package.v1` 只建立 source version、synthetic 标记和 records envelope，记录体保持明确的 P1 扩展点；它没有批准 ERP/MES/WMS/CAM 字段映射。`planning-snapshot.v1` 与 `planning-problem.v1` 只编码总规已经决定的字段和单位。OPEN-002/007/013/015 全部保持 OPEN，sample 中的 source/scenario 值不能成为 Production authority。

## P0 rule/state authority review

`constraint-rule-sheet.v1` 只规定如何验证已经进入正式合同的事实，不成为业务数据权威。C-006 仍消费上游 `material_ready_at`，C-007 仍服从 MES execution facts，C-008 lock/approval actor 与 C-009 transport 来源分别受 OPEN-005/010/009 约束。`capability-registry.v1` 的 V1_SUPPORTED 也不是资源 capability 主数据来源。

规则 example、state guard/evidence 文本和 synthetic expected rejection 都不能关闭 PROD_OPEN、填充 Production 字段或替代 ERP/MES/WMS/CAM/人工审批权威。

## TASK-P0-08 infrastructure review

health payload 只公开 service/build metadata 与 database/redis availability code，不读取或返回 Order/BOM/Execution/Inventory/Planning Decision。`engineering_job_records`、`engineering_idempotency_records` 是通用执行元数据，不成为业务事实、Schedule 状态或发布权威；process-local idempotency reference store 也不能授权任何业务副作用。

Compose 的 database name、user、network endpoint 和 non-production placeholder 只用于 development skeleton，不回答 OPEN-002/003/015，也不成为生产字段或系统权威。P0-08 未建立任何产品 API 或外部 adapter。

## TASK-P1-02 canonical authority boundary

`canonical-records.v1`固定APS内部语义、稳定引用、单位/UTC/duration形状与record-level source provenance；`import-package.v2`要求envelope source versions与record source/version一致。它不声明任何ERP/MES/WMS/CAM列名、系统优先级、冲突解决、单位换算、timezone、lot split、duration fallback或生产日历规则。

Pure precheck只拒绝不一致的ID/reference/unit/time/duration/provenance，不能把“Schema接受”解释为字段权威或DataValidation PASS。OPEN-001/002/003/004/007/008/009/013/014/015均保持OPEN；synthetic sample值不能用于关闭任何条目。

## TASK-P1-03 staging authority boundary

Raw Staging新增的source system/version、content/row digest、row identity/location、received-at、media type与source name只构成接收和审计事实，不决定Order/Execution/Inventory/CAM/Planning字段权威，也不解决来源冲突。repository保存opaque bytes且没有canonical/Snapshot/Problem转换方法；同idempotency scope下的source/version/content差异被拒绝，不能以最后写入覆盖。

`raw_import_*`列是internal persistence schema，不是ERP/MES/WMS/CAM接口或field mapping。SQLite synthetic测试和migration sample不提供OPEN-002/015的权威来源，两个条目继续OPEN；后续Adapter/Normalization必须在本边界之后显式解释来源而不能从staging列名推断生产字段。
