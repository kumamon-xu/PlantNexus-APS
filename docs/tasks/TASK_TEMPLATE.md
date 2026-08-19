---
doc_id: TEMPLATE-TASK
title: Task Card Template
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [98, 99, 100, 111]
last_reviewed: 2026-08-19
---

# TASK-Px-yy — Title

Task status: 写入本 Task Card front matter 的 `status`，不在正文建立第二状态源。

Requirement IDs:

NFR / ENG IDs:

Depends on:

Goal:

Inputs:

Diff base: Task 进入 `in_progress` 前的完整 40 字符 HEAD commit SHA；不得使用会移动的 branch/tag

Files allowed to change:

Files forbidden to change:

Implementation steps:

Outputs:

Documentation impact: `required` | `none`

Documents to update: 使用反引号列出仓库根相对路径；禁止只写“相关 docs”

Documentation impact rationale: 说明变化影响，或声明 `none` 的可验证理由

Change-impact matrix rows reviewed: 列出 `change-impact-matrix.md` 中实际匹配的稳定 `IMPACT-*` Rule ID

Traceability updates: 明确 Requirement/NFR/ENG/Constraint/Task/Test/Artifact/Registry 关系

Schema changes:

Migration:

Error behavior:

Tests:

Benchmark impact:

Simulation scenarios:

Acceptance commands:

Artifacts:

Explicitly excluded:

PROD_OPEN:

SIM_ASSUMPTIONS:

Rollback:

## Completion evidence

在任务完成时填写真实的修改文件、文档更新、影响矩阵匹配结果、追踪更新、命令/退出码、测试/Benchmark artifact 和开放问题。不得预填 PASS。

至少记录：

- 完成时间和实际 changed paths；
- Diff base、验收时 Git HEAD，以及 committed-range/working-tree source counts；
- 实际更新文档及必审但未修改文档的逐项理由；
- Requirement/NFR/ENG → Task → Test → Artifact 关系；
- `scripts/check_docs.py --task <task-card> --check-diff --report <report-path>` 的真实摘要；
- PROD_OPEN、SIM_ASSUMPTION、Schema/Migration、Benchmark 和回滚影响。

涉及 Schema 时还必须记录 schema set/contract version、compatibility 分类、migration 或明确 none 理由、机器 validator 版本、positive/negative/round-trip evidence，以及 sample/fixture 的 Production/Synthetic 属性。

涉及 Constraint rule、capability/error registry 或状态机时还必须记录：稳定 artifact/version、所有 C-ID/state/code 的完整性、允许与拒绝路径、guard/evidence、对应 Test ID、是否仅为 contract metadata、真实 evaluator/persistence/权限/业务动作是否仍为 `PLANNED`，以及是否需要 ADR/Benchmark replay。不得把 rule-sheet completeness 写成 ScheduleValidator PASS。

涉及 Validator evaluator 或 mutation 时还必须记录：正例来源/hash 保持不变、evaluator 与 Solver/backend/expected artifact 的依赖边界、mutation construction 与判断公式分离、每个 mutation 的目标及实际 C-ID、ValidationReport/Error exact/schema evidence、C-ID/required mutation coverage、deterministic replay、fixture-local 与 production/performance 边界，以及 Property/Benchmark/Solver comparison 是否仍为 `PLANNED`。

涉及 Simulation Profile/Scenario/Generator 时还必须记录：contract/asset/generator/canonicalization 各自版本、seed 与随机源控制、canonical dataset/hash 定义、`generated_at` 等非 hash provenance、Standard Import 共同入口、Production target rejection、TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION 证据，以及 sample/Fixture/Benchmark/Execution 行为哪些仍为 `PLANNED`。不得把 empty package 或 Schema sample 写成正式 Scenario/性能证据。

涉及 engineering infrastructure/API health/Worker/CI 时还必须记录：direct dependency/lock 与明确未安装组件；environment/data-plane/Secret fail-closed boundary；liveness/readiness 的外部依赖与 no-leak 行为；Job heartbeat/lease/attempt/STALLED、idempotency scope/fingerprint、持久化/transaction/side-effect 边界；migration upgrade/downgrade 与测试数据库；structured log/trace context/redaction 和 audit/metrics 缺口；Compose/container/CI 实际执行层级。仓库内 workflow/config/local PASS 不得伪装成 CI provider run、branch protection、Production deployment、distributed crash recovery 或 production security evidence。

涉及 external CI provider 时还必须在开始前固定 provider/repository/branch/workflow 和官方 query 命令，并在完成证据中记录 immutable head SHA、run ID/URL/attempt/event/status/conclusion、required jobs/steps、artifact ID/name/size/digest/expiry 与 required-check/branch-protection 状态。credential 必须由进程外环境或已认证 session 提供，不得记入 Task、日志或 artifact；失败 run 必须保留为反例，不得伪写 PASS。
