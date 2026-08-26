---
doc_id: TASK-P3-15
title: P3 Phase Plan Amendment Governance Support
status: in_progress
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

Start gate: TASK-P3-00～14全部`done`；P3-14 corrective implementation及closure exact provider成功；用户已明确批准把当前编号改作阶段计划修订治理owner、把本地化与独立Exit Audit顺延；`main=origin/main=06e7f794f486ac34c505237b847462c7c7c36d44`、remote main一致且working tree clean；该SHA冻结为immutable Diff base。

Goal: 为首次阶段计划之后的有界修订建立机器可检查的`phase-plan-amendment-owner`模式，使一个已存在、被当前event修改且拥有不可变Diff base的owner可以原子归属新增或修订的`planned/ready`成员卡，并在不削弱普通单Task和首次`phase-planning-owner`规则的前提下支持同一稳定Task ID的文件重命名。

Non-goals: 不创建后续本地化或Exit Audit卡、不执行任何本地化/业务实现、不修改CI workflow、Schema、migration、dependency、业务测试断言、P4或Production材料。

Inputs: 当前phase-aware Task discovery、首次phase-planning batch规则、TASK-P3-00与P3-14 provider-verified历史、用户批准的编号方案、现有治理validator与unit tests。

Diff base: 06e7f794f486ac34c505237b847462c7c7c36d44

Files allowed to change: `scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py`、ignored `build/traceability/TASK-P3-15-report.json`与`Documents to update`中的全部明确路径。

Files forbidden to change: 除`backend/tests/unit/test_check_docs.py`外的`backend/**`、`schemas/**`、`frontend/**`、`backend/migrations/**`、fixtures/benchmarks、`.github/workflows/**`、`pyproject.toml`、`uv.lock`、ADRs、TASK-P3-00～14历史卡/evidence、P4详细Task及所有Production部署/授权材料。

Implementation steps: 增加稳定amendment-owner role；按路径中的稳定Task ID归并rename；保留首次all-added Pn-00 owner分支；对修订批次要求唯一owner、完整Diff base、成员planned/ready且无implementation SHA；读取event base中的成员原状态并拒绝active/done历史成员改写；拒绝纯删除与重复存活路径；增加正负unit test和真实event-range入口覆盖；同步治理合同并取得exact provider evidence。

Outputs: backward-compatible phase plan amendment discovery、21项以上治理unit regression、更新后的Task/phase/quality/governance合同与exact provider artifact。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/architecture/repository-layout.md`、`docs/governance/document-control.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P3/TASK-P3-15-p3-exit-gate-audit.md`。

Documentation impact rationale: Task discovery语义属于仓库治理合同；新增修订owner必须同步Agent入口、阶段/Task索引、质量门、追踪规则和全部Impact Rule强制注册表，同时保持首次规划与历史provider事实不变。

Change-impact matrix rows reviewed: `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-009/NFR-TRC-001/NFR-PER-001/ENG-ARCH-001/ENG-VER-001→TASK-P3-15→TEST-TRACEABILITY-VALIDATOR/TEST-PHASE-GOVERNANCE-001→Task report/exact provider artifact；不新增root或Test ID，不把治理PASS写成业务/Exit证据。

Schema changes: none；schema set与全部published bytes保持冻结。

Migration: none；禁止新DDL或repository语义变化。

Dependency changes: none；`pyproject.toml`与locks零差异。

ADR impact: none；只扩展既有治理机制，不改变业务架构或状态合同。

State-machine impact: none；状态、command、error与wire contract全部冻结。

Error behavior: 无owner/多owner、all-added非Pn-00 owner、owner无完整SHA、成员active/done或预填SHA、纯删除、重复存活path、历史/future phase或不唯一归属均抛`TaskDiscoveryError`并使治理非零；不得回退猜测Task。

Tests: TEST-TRACEABILITY-VALIDATOR与TEST-PHASE-GOVERNANCE-001；覆盖首次规划不回归、amendment rename/new members成功、base中active/done成员降级改写拒绝、deleted-only拒绝及repository event-base读取。

Benchmark impact: none；不执行或改变Benchmark，不形成容量/SLA。

Simulation scenarios: none；不新增/修改/retire任何assumption。

Acceptance commands: `uv run ruff check scripts/check_docs.py backend/tests/unit/test_check_docs.py`；`uv run pyright scripts/check_docs.py backend/tests/unit/test_check_docs.py`；`uv run pytest -q backend/tests/unit/test_check_docs.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P3/TASK-P3-15-p3-exit-gate-audit.md --check-diff --report build/traceability/TASK-P3-15-report.json`；从event base动态发现同一Task并复验；`git diff --check`；禁止范围相对Diff base零差异。

Artifacts: `traceability-report.v1`、targeted test/type/lint结果与GitHub required `validate` exact artifact；无业务machine report。

Provider evidence: implementation exact push run/job/artifact成功并下载确认SHA、Task、Diff base、五个Impact Rules、19 checks与issues=[]后，才允许同一owner发起后续计划修订closure；closure自身也须exact provider复验。失败run必须保留，Task保持`in_progress`。

Completion conditions: 新旧selector正负路径与repository event-base test全部PASS；普通单Task与首次Pn-00 batch无回归；完整文档/diff治理、scope/Impact与禁止范围PASS；implementation exact provider artifact形成；后续修订批次可由本owner合法归属但不会自动实现成员Task或形成Exit/P4/Production结论。

Failure handling: 任一本地或provider门失败即停止后续编号/规划修订，保持本Task`in_progress`，保留失败证据并只在本卡范围内修正；不得绕过validator、改workflow、force-push或批量启动成员。

Explicitly excluded: 本地化实现与对应Task卡创建、P3 Exit Audit执行、P4创建/transition/implementation、Production readiness/UAT/approval/publish/deployment、CI workflow变更、PROD_OPEN closure。

PROD_OPEN: OPEN-001～015全部保持`OPEN`；治理能力不是业务Authority或closure evidence。

SIM_ASSUMPTIONS: SIM-ASSUMPTION-001～015全部保持`ACTIVE`；无新增定量值或生命周期变化。

Rollback: 回退到Diff base恢复旧selector与原planned卡；不得删除P3-14或失败provider历史。若implementation provider未通过，不得使用amendment-owner修订阶段计划。

## Activation evidence

2026-08-26启动前已复核`main`、`origin/main`和remote main均为`06e7f794f486ac34c505237b847462c7c7c36d44`且working tree clean；该SHA为不可变Diff base。P3-00～14均保持`done`，P3 Gate corrective/closure provider证据与失败历史不改写。本Task只建立后续文档计划修订所需治理能力，exact implementation provider形成前保持`in_progress`。

## Local implementation evidence

当前实现已覆盖唯一既存amendment owner、同ID rename、新planned/ready成员、base active/done成员保护、new-owner拒绝、deleted-only与重复路径边界，同时保留普通单Task和首次Pn-00 planning batch。Targeted Ruff=`PASS`、Pyright=`0 errors`、治理unit=`22 passed`；完整repository suites为既有603项加security 18项，共621项PASS。Full governance=`PASS docs=165 roots=30 trace_rows=30 tests=48 open=15 sim=15 risks=13 tasks=53`；显式与event-base动态diff均选择TASK-P3-15并为26 paths/5 Impact Rules/19 checks/0 issues。`git diff --check`与业务/Schema/Frontend/migration/workflow/dependency/P3-00～14禁止范围为PASS/零差异。Implementation exact provider尚未形成，因此Task继续`in_progress`且后续计划修订未执行。
