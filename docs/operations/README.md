---
doc_id: DOC-OPS-INDEX
title: Operations 索引与形成边界
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: false
source_sections: [65, 66, 93, 94, 95, 101, 106]
last_reviewed: 2026-08-19
---

# Operations 索引与形成边界

P0-08 已形成工程骨架可验证的前三份 Operations baseline：

- [`security.md`](security.md)：environment-only config、Secret/log redaction、dependency/SQL/shell 边界；Import/auth/threat-model controls 仍待真实功能。
- [`observability-and-audit.md`](observability-and-audit.md)：structured log context、OpenTelemetry ID 注入、health/build metadata；PlanningRun metrics/audit persistence/retention 仍待实现。
- [`worker-reliability-and-idempotency.md`](worker-reliability-and-idempotency.md)：business-neutral heartbeat、lease、attempt、STALLED、idempotency 与 migration；distributed repository/scanner/business retry 仍待实现。

后续仍只保留计划：

- `release-and-versioning.md`：code/spec/schema/solver version 和 promotion；
- `production-readiness.md`：Historical replay、UAT、backup/restore、monitoring、runbook 和 PROD_OPEN closure。

现有三份 baseline 只引用仓库内配置、tests 与 machine report，不能被解释为 Production Runbook。Release/Production 文档必须引用真实部署配置、监控指标、backup/restore、平台 run 和责任人后才能创建并转为 `baseline/living`；P0-08 未猜测这些事实。

TASK-P0-10 只补齐 GitHub Actions 运行、job、artifact digest 与 required-check/branch-protection 的 CI 治理证据。provider 历史和 artifact retention 由 GitHub 管理，仓库只保存可核验 ID/URL/SHA/digest 与边界说明，不写入 credential。该证据可用于 P0 CI Exit Gate，但仍不是 release runbook、监控、backup/restore 或 Production readiness。

TASK-P1-01把 workflow从单一 P0-10 handoff改为 phase/task-neutral：CI event base发现唯一 current-phase Task，Task Card `Diff base`继续限定 scope，机器产物采用中性名称。既有P0 provider成功证据保持历史只读；未获push/provider授权时结果必须记为`NOT_RUN`，不能从本地测试推断。后续授权下，completion commit `2d2a4432aa42e4f38ee8ae736e2acf2df1c694b9`的GitHub run [`32237649319`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32237649319)、successful `validate` job和artifact `9359554539` / digest `sha256:bdd08f01ea23e8fe93f82c199274afc0aa5e9343ea7fa70adfb6df6a950d1216`已形成provider PASS。该变化不形成release runbook、Production监控或部署能力。

TASK-P1-03在既有Operations baseline上增加Raw Staging持久化证据：insert-only batch/row、source/version/digest/location/UTC provenance、plane-scoped idempotency、atomic rollback与destructive migration downgrade均由unit/integration tests复验。错误不回显raw/driver detail，repository不创建Worker task或业务副作用。

这仍不是Production Runbook：真实PostgreSQL并发/lock、独立数据库与roles、retention/erasure、backup/restore、access audit、容量/告警和incident response均未形成。migration downgrade只在临时开发SQLite明确删除1个synthetic sample batch/row，不能作为生产数据清理策略。

TASK-P1-03 implementation commit`25897393e31dcc0648943ec7e2e7f43dbb0e70e1`已由GitHub run [`32243895717`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32243895717)的required `validate`成功重放；artifact `9361846475` / digest `sha256:75aa68daf5bd4308a4f9143c0ae72746f540d103d6a937d472d6a7d5c3c5160b`保存机器证据。该provider PASS仍不构成Production DB、migration runbook或安全认证。

TASK-P1-04在`security.md`形成bounded CSV/XLSX file-root/type/size/shape/archive/active-content控制，并把openpyxl/defusedxml exact pins同步到既有engineering machine contract/CI assertion；OR-Tools forbidden、environment/data-plane fail-closed和既有machine report schema均未弱化。Reference files只在temporary test directory生成，Adapter不创建upload API、Worker或外部connection。

这仍不是Production Runbook或完整file-ingress security：quarantine/malware scanning、RBAC、network file share、rate limit、encryption、retention/erasure、production filesystem permission/audit和incident response均未形成；真实ERP/MES/WMS/CAM binding也仍受OPEN-002/015阻塞。

TASK-P1-04 implementation commit`9391ec021afa9e6f4f881b1538b276c84584df0e`已由GitHub run [`32247079996`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32247079996)的required `validate`成功重放；artifact `9362999088` / digest `sha256:b9ada0b25d12962f5efea51e058cd82778495f4389a240e32aa64c04143b5d4b`保存机器证据。该provider PASS仍不构成Production file-ingress、security certification或真实system binding。

TASK-P1-07不新增API、Worker、DB/migration、network、Secret或Runbook行为；仅把dev-only Hypothesis property directory加入既有repository CI test step，并以`test_ci_contract.py`防止provider遗漏核心expansion evidence。Workflow仍使用current-phase Task discovery、中性artifact名、完整既有gates和conditional Benchmark hook，无`continue-on-error`。

本地workflow contract PASS不等于GitHub provider执行；implementation commit push后必须核验required `validate`、steps与artifact，再以evidence-only commit关闭Task。即使provider PASS，也不构成Production operation、capacity、安全或on-call证据。
