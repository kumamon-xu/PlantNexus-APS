---
doc_id: DOC-OPS-INDEX
title: Operations 索引与形成边界
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: false
source_sections: [65, 66, 93, 94, 95, 101, 106]
last_reviewed: 2026-08-21
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

TASK-P1-08新增internal PlanningSnapshot persistence：hash主键、ID唯一、full-bytes digest、plane scope、atomic insert/exact replay/read，以及repository与database-trigger双层update/delete拒绝。Migration测试明确验证空库升级、含一个synthetic Snapshot的destructive downgrade至`0002`、re-upgrade后记录为空；历史Snapshot不能用代码rollback原地改写。

这仍不是Production Runbook：独立aps_sim/aps_prod数据库与roles、PostgreSQL trigger/concurrency实跑、retention/legal erasure、backup/restore、access audit、capacity/alert和incident response均未形成。`created_at`只属于storage audit metadata且不进入Snapshot hash。Implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`已由GitHub run [`32310098594`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32310098594)的required `validate`成功重放；artifact `9386127863` / digest `sha256:69d68183bad614631df07234a3ca88508379ab89ec715f811ee7f529d6f17e0c`保存机器证据，但不构成上述Production能力。

## TASK-P1-11 operator-facing evidence

本地/CI可运行`python -m app.application.p1_gate_report --root . --scenario fixtures/synthetic/SIM-P1-INGRESS-001 --repeat 2 --report <path>`生成`p1-data-pipeline-report.v1`。返回码0只表示双入口parity、两次hash replay、quality PASS、四类exact rejection与Problem终止边界均通过；返回码非0必须保留report/CI failure并阻断Task闭环。

Report本身不写业务数据库，temporary CSV随进程回收，`build/validation/*.json`保持ignored并由CI artifact托管。这不是Production Runbook、SLA、capacity、backup或incident evidence。

## TASK-P2-01 operator-facing contract evidence

本地/CI可运行`python -m app.planning.problem.contract_check --root . --report <path>`生成`planning-problem-contract-report.v1`。PASS同时验证v1 Schema/sample bytes、v1 fixed replay、v2 Schema/sample replay、两类lock和historical/delivery/resource字段计数；CI固定输出`build/validation/ci-planning-problem-contracts.json`并上传中性evidence artifact。非零返回码必须保留FAIL report并阻断Task closure。

该命令只读repository输入并写machine evidence，不写数据库、调用Solver或建立service endpoint。`code_commit=uncommitted`的本地报告不构成provider证据；只有exact GitHub SHA/run/job/artifact可关闭Task。本段不是Production操作手册、priority/lock policy、SLA或on-call能力。

## TASK-P2-02 operator-facing contract evidence

本地/CI运行`python -m app.planning.policy.contract_check --root . --report <path>`生成`planning-machine-contract-report.v1`。PASS必须包含fixed Schema/sample bytes、Policy/Limits无默认值、七种status唯一映射、四文档fingerprint/replay与no-Solver/no-Validator scope共5项检查；CI路径为`build/validation/ci-planning-machine-contracts.json`。非零返回码保留FAIL report并阻断closure。

命令不连接数据库或外部系统、不加载Solver、不生成candidate，也不执行Benchmark/Validator。local `uncommitted`只用于验收；Task关闭必须查询exact pushed SHA的required `validate`步骤和未过期artifact。该命令不是Production runbook、SLA、capacity或incident evidence。

## TASK-P2-03 operator-facing foundation evidence

本地/CI运行`python -m app.planning.backends.cp_sat.contract_check --root . --report <path>`生成`solver-backend-foundation-report.v1`。PASS要求exact dependency/lock、平台identity、namespace/Protocol、七状态、参数及两类engineering smoke共6项全部通过；CI固定路径为`build/validation/ci-solver-backend-foundation.json`。非零返回码必须保留FAIL report并阻断closure。

命令只调用空/故意invalid的native CP-SAT model，不读取业务数据、不连接DB/API/Worker、不生成candidate、不运行Validator/Benchmark，也不声明Production readiness。升级OR-Tools时必须按ADR-0011重新执行lock/platform/status/Golden/Scenario/Benchmark Gate；本段不是solver生产Runbook、SLA或incident流程。

## TASK-P2-04 operator-facing validator evidence

本地/CI运行`python -m app.planning.validation.problem_validator_check --root . --report <path>`生成`formal-schedule-validator-report.v1`。PASS要求6项检查全部成功，并显示13个声明式mutation覆盖C-001～C-011、14个hard violations、6个duration/order examples、status contradiction identical replay及Backend/OR-Tools/expected-outcome隔离；CI固定路径为`build/validation/ci-formal-schedule-validator.json`。

非零返回码必须保留FAIL report并阻断closure。该命令只验证synthetic correctness与合同/hash边界，不连接Production系统、不执行CP-SAT business model、objective或Benchmark；local `uncommitted`报告不替代exact GitHub SHA的required `validate`与artifact，也不是Production runbook、capacity或SLA证据。

## TASK-P2-05 core model evidence command

本地/CI运行`python -m app.planning.backends.cp_sat.core_model_check --root . --report <path>`生成`cp-sat-core-model-report.v1`。PASS要求6项检查全部成功：冻结合同/rule/Validator/lock hash、five-C-ID model shape、tiny JSSP/FJSP candidate、unary infeasible与zero/overflow precheck、formal Validator正反例、独立穷举oracle与真实telemetry；CI固定路径为`build/validation/ci-cp-sat-core-model.json`。

非零返回必须保留sanitized FAIL report并阻断Task closure。该命令不读取Production数据、不发布ScheduleVersion、不运行OBJ-001搜索、Strategy或Benchmark；含P2-06/07事实的Problem应视为当前core slice不支持并稳定拒绝，而不是改写输入或忽略事实。

## TASK-P2-06 temporal model evidence command

本地/CI运行`python -m app.planning.backends.cp_sat.temporal_model_check --root . --report <path>`生成`cp-sat-temporal-model-report.v1`。PASS要求7项检查全部成功，并显示4个temporal C-ID、5 candidate、3 infeasible、2 precheck、4 independent Validator mutation、8 tiny oracle cases、冻结合同/Builder/Validator/lock fingerprints和真实model delta；CI固定路径为`build/validation/ci-cp-sat-temporal-model.json`。

非零返回必须保留sanitized FAIL report并阻断closure。该命令仅使用in-memory synthetic data，不读取Production系统、不发布ScheduleVersion、不运行C-007/008、OBJ-001、Strategy或Benchmark；local `uncommitted`结果不替代exact GitHub provider evidence。
