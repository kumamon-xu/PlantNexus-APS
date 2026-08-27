---
doc_id: TASK-P4-05
title: Freeze Window and Effective Lock Projection
status: in_progress
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-05 — Freeze Window and Effective Lock Projection

Task batch role: phase-plan-member

Requirement IDs: REQ-005, REQ-008, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-HUM-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-01, TASK-P4-02, TASK-P4-04

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-05另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 实现versioned Simulation freeze policy与effective lock projection：COMPLETED/RUNNING/HARD不可变，freeze内按合同硬保护，SOFT保持稳定性成本输入，并以fail-closed precheck输出完整Replan Problem事实。

Non-goals: 不猜Production freeze、不计算OBJ-002、不调用Solver、不生成ChangeReport或新ScheduleVersion。

Inputs: TASK-P4-01 accepted Freeze/Stability/ChangeReport ADR、P4 event-derived Snapshot、base PUBLISHED ScheduleVersion、OPEN-005、既有C-007/C-008 contracts。

Diff base: e7b96e28913e7eb5be63ae4265c09f8281456b1c

Validation profile: HIGH_RISK

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/planning/policy/freeze_window.py`、`backend/app/planning/policy/__init__.py`、`backend/app/planning/problem/freeze_projection.py`、`backend/app/planning/problem/freeze_window_check.py`、`backend/app/planning/problem/__init__.py`、`backend/app/planning/validation/freeze_window_precheck.py`、`backend/app/planning/validation/__init__.py`、`backend/tests/unit/test_freeze_window_projection.py`、`backend/tests/property/test_freeze_window_properties.py`、`backend/tests/validation/test_freeze_window_precheck_mutations.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`逐字列出的文档；这是激活时冻结的exact allow-list。

Files forbidden to change: Schema/migration/dependency、backend objective/strategy、application Replan、Simulator/API/UI、Production defaults、P5+

Implementation steps: 固定anchor time/source/window；分类completed/running/HARD/SOFT/frozen tuples；生成solver-neutral Problem/Policy refs；拒绝冲突/缺失authority/跨plane；与formal Validator独立复验。

Outputs: `freeze-policy.v1` Simulation实例、effective lock projection与`p4-freeze-window-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/P4-dynamic-replanning.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P4/TASK-P4-05-freeze-window-and-effective-lock-projection.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/agents/task-execution-protocol.md`、`docs/agents/review-checklists.md`、`docs/contracts/README.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/kpi-contract.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/adr/README.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/operations/README.md`、`docs/quality/benchmark-regression.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/validator-mutation-tests.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`

Documentation impact rationale: freeze/effective-lock/precheck 的直接合同、测试、Simulation/OPEN 与追踪文档需要同步；Impact Rule 只强制最低语义所有者，不再加载或逐份解释未受影响的候选文档。2026-08-27 用户另行授权本轮跨阶段 agent/context/validation 治理优化；该 amendment 仅修改执行规则与状态摘要，不改变本Task的 freeze 语义、业务代码或测试断言。

Change-impact matrix rows reviewed: `IMPACT-PROBLEM`、`IMPACT-POLICY`、`IMPACT-VALIDATOR`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-005/008/009→freeze/effective locks→C-007/C-008→TEST-FREEZE-WINDOW-001、TEST-RUNNING、TEST-INF-LOCK、TEST-VALIDATOR-MUTATION、TEST-PROPERTY→report。

Contract impact: consumer-only；实现accepted freeze/effective-lock与既有C-007/C-008语义，Simulation policy必须versioned，Production value继续OPEN。

Schema changes: none unless P4-02-approved version requires generated bindings；历史Problem bytes必须冻结。

Migration: none。

Dependency changes: none。

ADR impact: none；实现TASK-P4-01 accepted Freeze/Stability/ChangeReport ADR。若freeze定义变化或HARD/SOFT语义偏离，先superseding ADR。

State-machine impact: none；projection不推进Request或Version state。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-FREEZE-WINDOW-001、TEST-RUNNING、TEST-INF-LOCK、TEST-VALIDATOR-MUTATION、TEST-PROPERTY。

Test IDs: TEST-FREEZE-WINDOW-001, TEST-RUNNING, TEST-INF-LOCK, TEST-VALIDATOR-MUTATION, TEST-PROPERTY

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 登记至少一个versioned Simulation freeze值及边界例；OPEN-005保持OPEN。

Acceptance commands: `uv sync --locked`；受影响路径Ruff/Pyright；Task-specific unit/property/mutation/CI-contract与freeze machine command；完整相关Backend pytest；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-05-freeze-window-and-effective-lock-projection.md --check-diff --report build/traceability/TASK-P4-05-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。Frontend/Playwright/SCA/license与无关历史machine不在本地重复，仍由当前统一required `validate`覆盖。

Artifacts: `p4-freeze-window-report.v1`、frozen Problem/policy hashes、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。现有workflow尚未实现轻量closure路由，因此本Task不使用新规则中的可选轻量Provider路径。

Completion conditions: 所有保护规则、边界时刻、跨horizon和拒绝路径可独立复验；Production无默认；no Solver/Version mutation；文档、追踪、OPEN、SIM一致；implementation与evidence-only closure均经当前exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: 仅形成versioned Simulation freeze值；不关闭OPEN-005，不形成真实priority/authority、external integration、deployment或capacity/SLA。

P5 boundary: freeze projection不得加入secondary/tool/batch/setup/multi-factory/alternative-route或decomposition能力。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 停止新policy版本并回退projection consumer；既有Problem/Policy evidence不可改写。

## Completion evidence

2026-08-27完成HIGH_RISK本地implementation验收。`p4-freeze-window-report.v1`为7/7且`issues=[]`，绑定本Task、不可变Diff base、versioned Simulation policy及Snapshot/Problem/projection fingerprints；Task-specific unit/property/mutation/CI contract为21项，完整Backend为`675 passed`，Ruff/Pyright零问题。Task report为56 paths、八个declared Impact Rules、19/19 checks、`issues=[]`；locked Frontend、三轮Chromium、SCA/license、双build、Compose、全仓文档、`git diff --check`及全部冻结禁止范围亦通过。

首次完整Backend replay为`674 passed / 1 failed`，原因是新增problem-package隔离测试辅助检查器自身包含被扫描的`ortools`字符串；纠正仅在既有allow-list内将辅助检查改为AST import判定，随后focused与完整Backend均PASS。两次Frontend验收编排错误（SCA漏传`--report`、Vitest未进入`frontend`工作目录）均保留为失败事实，并以CI精确参数和npm `11.17.0`纠正后全绿；它们不属于产品断言失败。

anchor补强后的一次额外全库replay为`670 passed / 5 setup errors`，五项均来自同一既有P3 publication并发Gate的跨replay语义偶发差异；本Task未修改禁止范围内的P3 application/test。随后该P3 Gate独立`5 passed`，最终全库再次`675 passed`，故保留该本地失败事实但不把它归因为P4-05产品失败。

实现SHA、Provider manifest与closure SHA尚待提交后回填，因此Task保持`in_progress`。实际语义文档已同步freeze/effective-lock/precheck、traceability、SIM-ASSUMPTION-017和OPEN-005边界；Schema/migration/dependency/ADR/state pair均无变化。回滚边界为停止新Simulation policy revision并移除projection consumer，不改写既有Problem/Policy evidence。P4-06、P5与Production均未启动。

## Activation evidence

2026-08-27用户明确授权执行TASK-P4-05。激活前确认`main=origin/main=remote main=e7b96e28913e7eb5be63ae4265c09f8281456b1c`、ahead/behind=`0/0`且working tree clean；TASK-P4-01/02/04均为`done`，其implementation/closure分别构成直接父子链`abd70942a41984a9a3956f43d39065b19e4405c3`→`4026597ab1015b5ea3a89d241f0d12b5b481dee3`、`539cdbbdcdd406daba25b8d6b8caaa5133691e76`→`7b9bfc3069de5d3738e5cc5827d27d197ed3d226`和`47f55b41e370aa9d24fd9c987cff4663672c3ee8`→`e7b96e28913e7eb5be63ae4265c09f8281456b1c`。六个required `validate`均由GitHub Actions app `15368`成功提供；artifact `9634380233`、`9634583546`、`9636892191`、`9637303205`、`9644190441`、`9644798911`均未过期，下载证据分别为38/38/39/39/41/41份可解析JSON，exact绑定Task、SHA、Diff base、Impact Rules、19/19 checks及`issues=[]`。

上述artifact digest依次为`sha256:d5078a89a3bbc8a8ffe9654c76dab04a0dd50955859f9fac1cf332a377d0cc3a`、`sha256:b25742c1b4e4c8fc19ee50e55d9c32bddd1b8de5d8588872d0bd2d1c4fe94b75`、`sha256:378fbb47f12d92773e77855eff486d51f67502f610a6578b14549cdade7f5d7b`、`sha256:66baee74223623be44a9fa78de3f38d69b5dd76ede9a0b5fd60e08a239a7b042`、`sha256:5de60ea1cb38c6f5b9d759f5c7a0179215e765e9f5c2c7e38c656ed04a6cd3a5`、`sha256:c57b22bbeee17657ea67631b08f562c48485904d42e163d065e243f856eeb81d`。Branch protection仍要求`validate`并绑定app `15368`。

启动时冻结Git object：`schemas/**=3a6a73c6df46048e2c053355959a3c684525cbe9`、`backend/migrations/**=bc11121cc424bb6014c8cc82f89af8890582207a`、CP-SAT Backend=`222a8680492a3ff266e131e67cc18f73ffaf80b8`、Strategy=`bdd20db1c8524e71e843dd61afff596d4b391f73`、application=`77c456a9c3ceb27d948fe15686aba02393afdd2a`、simulation=`2e213608aa0cb203f996497be2e9397b26b234d4`、API=`20075718f972cd13bfca12b0615f4a41eb57eb82`、Frontend=`ccbded8e149e98b5fba66bcc285d3ef20489cd48`、`pyproject.toml=241ccc5d343c4527c4e7a419ae0c282fe29e6086`、`uv.lock=a04b1285e0e1da0d2a2341a879d5e8cc718522b7`、state registry=`cd9fedc3a9c4b521646b16ec5628b00d99d249f2`、既有formal Validator=`b17717cf0235d6829b9b47e08cac37d8a966a3c2`、Problem builder/hash=`e6032a7a8a563db895eb0ec0cabbedb80719522f`/`706032dead0857fe9c018f1054b798f7b162dfb4`。本Task只实现Simulation `freeze-policy.v1`解析、独立effective-lock carrier/precheck和机器证据；不会启动TASK-P4-06或实现OBJ-002、ChangeReport、Solver、Replan application、Simulator、API/UI、Production或P5+能力。
