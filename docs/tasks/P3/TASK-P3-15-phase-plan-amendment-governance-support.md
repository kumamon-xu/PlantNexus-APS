---
doc_id: TASK-P3-15
title: P3 Phase Plan Amendment Governance Support
status: done
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [6, 58, 73, 74, 77, 78, 98, 99, 100, 101, 103, 104, 111]
last_reviewed: 2026-08-26
---

# TASK-P3-15 — P3 Phase Plan Amendment Governance Support

Task batch role: phase-plan-amendment-owner

Requirement IDs: REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-PER-001, ENG-ARCH-001, ENG-VER-001

Depends on: TASK-P3-14

Start gate: TASK-P3-00～14全部`done`；P3-14 corrective implementation及closure exact provider成功；用户已明确批准把当前编号改作阶段计划修订治理owner，并批准TASK-P3-16本地化、TASK-P3-17独立Exit Audit的编号方案；`main=origin/main=06e7f794f486ac34c505237b847462c7c7c36d44`、remote main一致且working tree clean；该SHA冻结为immutable Diff base。

Goal: 为首次阶段计划之后的有界修订建立机器可检查的`phase-plan-amendment-owner`模式，使一个已存在、被当前event修改且拥有不可变Diff base的owner可以原子归属新增或修订的`planned/ready`成员卡，并在不削弱普通单Task和首次`phase-planning-owner`规则的前提下支持同一稳定Task ID的文件重命名；implementation exact provider通过后，以本owner原子登记TASK-P3-16、TASK-P3-17与官方中文术语规范。

Non-goals: 不执行TASK-P3-16本地化或TASK-P3-17 Audit，不修改CI workflow、业务代码、Schema、migration、dependency、Frontend、业务测试断言、P3-00～14、P4或Production材料；不声明P3 Exit、P4 transition、UAT、Production readiness/approval/publish。

Inputs: 当前phase-aware Task discovery、首次phase-planning batch规则、TASK-P3-00与P3-14 provider-verified历史、用户批准的编号方案、现有治理validator与unit tests。

Diff base: 06e7f794f486ac34c505237b847462c7c7c36d44

Files allowed to change: `scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py`、rename source `docs/tasks/P3/TASK-P3-15-p3-exit-gate-audit.md`、surviving `docs/tasks/P3/TASK-P3-15-phase-plan-amendment-governance-support.md`、`docs/tasks/P3/TASK-P3-16-frontend-bilingual-localization-and-official-terminology.md`、`docs/tasks/P3/TASK-P3-17-p3-exit-gate-audit.md`、`docs/frontend/official-zh-cn-terminology-map.md`、ignored `build/traceability/TASK-P3-15-report.json`与`Documents to update`中的全部明确路径。

Files forbidden to change: 除`backend/tests/unit/test_check_docs.py`外的`backend/**`、`schemas/**`、`frontend/**`、`backend/migrations/**`、fixtures/benchmarks、`.github/workflows/**`、`pyproject.toml`、`uv.lock`、accepted ADR bodies（仅允许必审索引`docs/adr/README.md`记录no-ADR结论）、TASK-P3-00～14历史卡/evidence、P4详细Task及所有Production部署/授权材料。

Implementation steps: 增加稳定amendment-owner role；按路径中的稳定Task ID归并rename；保留首次all-added Pn-00 owner分支；对修订批次要求唯一owner、完整Diff base、成员planned/ready且无implementation SHA；读取event base中的成员原状态并拒绝active/done历史成员改写；拒绝纯删除与重复存活路径；增加正负unit test和真实event-range入口覆盖；取得exact implementation provider；随后只以文档closure原子登记两个planned成员、重编号最终Audit、官方术语和全部治理引用。

Outputs: backward-compatible phase plan amendment discovery、22项治理unit regression、completed TASK-P3-15 owner、planned TASK-P3-16/TASK-P3-17、`official-zh-cn-terminology.v1`、更新后的Task/phase/quality/governance合同与两次exact provider artifact。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/adr/README.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/provenance-and-versioning.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/domain/error-model.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/approval-publication-flow.md`、`docs/frontend/official-zh-cn-terminology-map.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/operations/README.md`、`docs/operations/observability-and-audit.md`、`docs/governance/document-control.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、本Task卡与两个新增成员卡。

Documentation impact rationale: Task discovery语义属于仓库治理合同；新增修订owner必须同步Agent入口、阶段/Task索引、质量门、追踪规则和全部Impact Rule强制注册表。规划closure还必须一致登记本地化展示语义、英文机器合同边界、Test ID、风险、Milestone顺序和最终Audit编号，同时保持首次规划与历史provider事实不变。

Change-impact matrix rows reviewed: `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-009/NFR-TRC-001/NFR-PER-001/ENG-ARCH-001/ENG-VER-001→TASK-P3-15→TEST-TRACEABILITY-VALIDATOR/TEST-PHASE-GOVERNANCE-001→Task report/exact provider artifact；规划层新增REQ-005/006/007/009及相关NFR/ENG→planned TASK-P3-16→TEST-FRONTEND-I18N-001→future artifact，TASK-P3-17最后独立审计；新增RISK-014但不新增root row，不把治理PASS写成本地化/Exit证据。

Schema changes: none；schema set与全部published bytes保持冻结。

Migration: none；禁止新DDL或repository语义变化。

Dependency changes: none；`pyproject.toml`与locks零差异。

ADR impact: none；只扩展既有治理机制，不改变业务架构或状态合同。

State-machine impact: none；状态、command、error与wire contract全部冻结。

Error behavior: 无owner/多owner、all-added非Pn-00 owner、owner无完整SHA、成员active/done或预填SHA、纯删除、重复存活path、历史/future phase或不唯一归属均抛`TaskDiscoveryError`并使治理非零；不得回退猜测Task。

Tests: TEST-TRACEABILITY-VALIDATOR与TEST-PHASE-GOVERNANCE-001已覆盖首次规划不回归、amendment rename/new members成功、base中active/done成员降级改写拒绝、new-owner/deleted-only拒绝及repository event-base读取；TEST-FRONTEND-I18N-001本轮只登记为`PLANNED`，不创建Frontend断言。

Benchmark impact: none；不执行或改变Benchmark，不形成容量/SLA。

Simulation scenarios: none；不新增/修改/retire任何assumption。

Acceptance commands: `uv run ruff check scripts/check_docs.py backend/tests/unit/test_check_docs.py`；`uv run pyright scripts/check_docs.py backend/tests/unit/test_check_docs.py`；`uv run pytest -q backend/tests/unit/test_check_docs.py`；完整repository suites；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P3/TASK-P3-15-phase-plan-amendment-governance-support.md --check-diff --report build/traceability/TASK-P3-15-report.json`；从implementation event base动态发现amendment batch并复验；`git diff --check`；业务/Schema/Frontend/migration/workflow/dependency/P3-00～14禁止范围相对Diff base零差异；全仓活动引用确认最终Audit为TASK-P3-17。

Artifacts: `traceability-report.v1`、targeted test/type/lint结果与GitHub required `validate` exact artifact；无业务machine report。

Provider evidence: implementation `c84e1aa1a81473f65d9f7906a6d2c67a94e7bb2f`的push run/job=`32944633958`/`98102640242`与required `validate`/GitHub Actions app `15368`成功；artifact `9597967232` / `plantnexus-ci-evidence-32944633958`未过期，798863 bytes，digest=`sha256:db5d7c67b33f81378fb2c2345aa4a3b6044cdacd899cc6320563607fed2b2e55`、expiry=`2026-11-24T07:49:19Z`。下载复核Task=`TASK-P3-15`、head=`c84e1aa1a81473f65d9f7906a6d2c67a94e7bb2f`、base=`06e7f794f486ac34c505237b847462c7c7c36d44`、26 committed/0 working paths、五个Impact Rules、19/19 checks、`issues=[]`。本evidence-only closure自身仍须exact provider复验；失败run必须保留。

Completion conditions: selector正负路径与repository event-base test全部PASS；普通单Task与首次Pn-00 batch无回归；implementation exact provider artifact已下载核验；本owner改名并为`done`；TASK-P3-16/TASK-P3-17为planned/no-SHA成员且依赖链明确；术语规范、TEST-FRONTEND-I18N-001、RISK-014、Milestone/索引/注册表完整；full/diff治理、scope/Impact与禁止范围PASS；closure exact provider复验后才完成全部证据链，成员不会自动执行。

Failure handling: 任一本地或provider门失败即停止编号/规划修订或后续Task授权，保持P3 active并保留失败证据；只在本卡范围内修正，不得绕过validator、改workflow、force-push、伪造状态或批量启动成员。

Explicitly excluded: TASK-P3-16本地化实现、TASK-P3-17 Exit Audit执行、P4创建/transition/implementation、Production readiness/UAT/approval/publish/deployment、CI workflow变更、PROD_OPEN closure。

PROD_OPEN: OPEN-001～015全部保持`OPEN`；治理能力不是业务Authority或closure evidence。

SIM_ASSUMPTIONS: SIM-ASSUMPTION-001～015全部保持`ACTIVE`；无新增定量值或生命周期变化。

Rollback: 回退到Diff base恢复旧selector与当时的planned Audit卡；不得删除P3-14、失败provider或implementation provider历史。closure若失败，TASK-P3-16/17保持未授权，不得实施。

## Activation evidence

2026-08-26启动前已复核`main`、`origin/main`和remote main均为`06e7f794f486ac34c505237b847462c7c7c36d44`且working tree clean；该SHA为不可变Diff base。P3-00～14均保持`done`，P3 Gate corrective/closure provider证据与失败历史不改写。本Task先建立后续文档计划修订所需治理能力；exact implementation provider形成后才允许本次原子closure。

## Local implementation evidence

当前实现已覆盖唯一既存amendment owner、同ID rename、新planned/ready成员、base active/done成员保护、new-owner拒绝、deleted-only与重复路径边界，同时保留普通单Task和首次Pn-00 planning batch。Targeted Ruff=`PASS`、Pyright=`0 errors`、治理unit=`22 passed`；完整repository suites为既有603项加security 18项，共621项PASS。Implementation full governance=`PASS docs=165 roots=30 trace_rows=30 tests=48 open=15 sim=15 risks=13 tasks=53`；显式与event-base动态diff均选择TASK-P3-15并为26 paths/5 Impact Rules/19 checks/0 issues。`git diff --check`与业务/Schema/Frontend/migration/workflow/dependency/P3-00～14禁止范围为PASS/零差异。

Implementation exact provider已按本卡Provider evidence下载核验，因此本closure使用同一owner原子登记TASK-P3-16/TASK-P3-17与`official-zh-cn-terminology.v1`。closure只修改治理/规划/规范文档：P3仍`active`，P3-16与P3-17均为`planned`且无Diff base/implementation SHA，P3-17为最终独立Audit；没有Frontend/Backend/Schema/migration/dependency/test assertion/workflow/P4/Production实现。closure提交与provider字段在push后以exact artifact复验，不以本地PASS替代。

Closure本地验收为Ruff=`PASS`、Pyright=`0 errors`、治理unit=`22 passed`、完整repository=`621 passed`；full governance=`PASS docs=168 formal_docs=167 roots=30 trace_rows=30 tests=49 open=15 sim=15 risks=14 tasks=55 unique_doc_ids=167`。显式Task报告记录26 committed-range/46 working-tree sources，去重后48 paths、六个Impact Rules、19/19 checks、`issues=[]`；closure-only 46 paths均为`README.md`/`docs/**`，完整48-path范围除治理脚本/unit test外也只为文档，P3-00～14历史卡零差异。`git diff --check`与event-base discovery在形成closure commit后复验；local PASS不预填closure provider。
