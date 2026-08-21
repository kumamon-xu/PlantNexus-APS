---
doc_id: TASK-P2-13
title: P2 Vertical Slice Gate Evidence
status: in_progress
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [57, 58, 75, 76, 89, 101]
last_reviewed: 2026-08-21
---

# TASK-P2-13 — P2 Vertical Slice Gate Evidence

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-006, REQ-009, REQ-012, REQ-014, REQ-015

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-OBS-001, NFR-PER-001, NFR-SEC-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-01～TASK-P2-12

Start gate: PASS。P2-01～12全部`done`，各自implementation均位于当前HEAD祖先链且exact required `validate` / artifact可取；`main=origin/main=59f3b013a4be7bd11d054e8464886b3cde791602`、working tree clean。该closure HEAD的run `32461665177` / required job `96709654227` / artifact `9439159396`均success，artifact digest=`sha256:007e7a3107d06d7d629f519a87a7e8e0c54143863d422413664d857659e38cb1`且未过期；Gate config、scenario/profile versions和Diff base据此固定。

Goal: 将Snapshot→Problem→Policy/Limits→Global CP-SAT→independent Validator→KPI/SolverReport→Export与correctness/XS/S/M聚合为一个可重放P2 Gate machine report和required CI evidence，不做Exit审计结论。

Inputs: P2-01～12 completion/provider evidence、all P2 contracts/assets/profiles、P1 ingress baseline、Gate A requirements。

Diff base: 59f3b013a4be7bd11d054e8464886b3cde791602

Files allowed to change: `backend/app/application/p2_gate_report.py`、`backend/tests/integration/test_p2_vertical_slice.py`、`backend/tests/contract/test_p2_exit_rejections.py`、`backend/tests/integration/test_p1_common_ingress.py`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；report写入ignored `build/validation/TASK-P2-13-p2-gate.json`，其他路径先修订。`test_p1_common_ingress.py`只允许把原application-wide exporter禁令收窄为唯一evidence-only Gate orchestrator例外；P1 CommonIngress本身及其no-Solver/Validator/API/Infrastructure边界不得弱化。

Files forbidden to change: Solver/Validator/contract/fixture/benchmark remediation、P2-14 audit report、P3 Task/state/publish、Production config/data。

Implementation steps: 只编排公开边界；至少两次完整replay；运行七类correctness和XS/S/M；收集status/C-ID/objective/model/timing/memory/hash/export；四类unsupported/invalid/limit负例；更新CI exact report artifact；失败停止且不在本Task修复。

Outputs: `p2-vertical-slice-report.v1`、CI Gate step/artifact、fixed hashes/status/counts及blocking gap input for P2-14。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/provenance-and-versioning.md`、`docs/domain/error-model.md`、`docs/operations/README.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/simulation/performance-gates.md`、`docs/simulation/benchmark-harness.md`、`docs/contracts/export-package.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、本Task卡。

Documentation impact rationale: Gate编排和CI artifact把全部P2实现连接为单一可核验链，必须同步架构、错误、质量、性能和追踪。

Change-impact matrix rows reviewed: `IMPACT-PHASE`、`IMPACT-APPLICATION`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: 全部P2 roots→TASK-P2-01～13→P2 Test IDs/machine reports→`p2-vertical-slice-report.v1`/CI artifact；P2-14 audit和P3保持PLANNED。

Schema changes: none；Gate report必须有versioned internal contract/test，若发布JSON Schema先修订卡片。

Migration: none；只读现有artifacts并在temp/build生成输出。

Dependency changes: none；locked solver/toolchain不变。

ADR impact: none；编排不得改变既有技术决定；发现不一致作为gap交回原Task/remediation。

Error behavior: 任一required stage、Validator、scenario、benchmark、export或provider evidence非PASS则report overall FAIL/NOT_RUN并返回非零；不得用其他PASS抵消。

Tests: TEST-GOLDEN-JSSP/FJSP、所有C-specific、TEST-VALIDATOR-MUTATION/PROPERTY/OUTPUT/SCENARIO-REPLAY/REFERENCE-SCHEDULER/BENCHMARK/SOLVER-UPGRADE、CI contract及P1 application boundary regression；唯一Gate→output machine-check例外必须逐文件/逐module exact匹配。

Benchmark impact: 重放XS/S/M并引用既有baseline，不建立新Production threshold；任何回归按P2-12规则阻断。

Simulation scenarios: Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock、XS/S/M完整集合。

Acceptance commands: `uv run pytest -q backend/tests/integration/test_p2_vertical_slice.py backend/tests/contract/test_p2_exit_rejections.py backend/tests/integration/test_p1_common_ingress.py backend/tests/integration/test_ci_contract.py`；`uv run python -m app.application.p2_gate_report --root . --repeat 2 --report build/validation/TASK-P2-13-p2-gate.json`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-13-p2-vertical-slice-gate-evidence.md --check-diff --report build/traceability/TASK-P2-13-report.json`；`git diff --check`；`uv build`。

Artifacts: P2 Gate report、all referenced reports/hashes、CI artifact、Task report和gap list。

Provider evidence: exact implementation SHA required `validate`必须运行P2 Gate、成功上传完整machine evidence；记录run/job/all steps/artifact ID/name/size/digest/expiry/required protection；失败run保留。

Completion conditions: 公开边界完整闭环、repeat hashes一致、七类correctness+XS/S/M+Export全部PASS、CI/provider exact evidence闭环、无remediation混入；否则Task可诚实FAIL但不得给Exit READY。

Explicitly excluded: 修复任何失败、P2 Exit decision、P3 Task/Workspace/approval/publish、dynamic Replan、Production readiness。

PROD_OPEN: 全部保持真实状态；Gate不关闭Production问题。

SIM_ASSUMPTIONS: 报告完整引用scenario/profile/policy assumptions，禁止Production外推。

Rollback: CI Gate可回退到previous workflow但失败evidence保留；若Gate暴露缺口，回到有界remediation Task并重新完整运行，不在报告中抹除。

用户明确授权执行TASK-P2-13。启动时`main=origin/main=59f3b013a4be7bd11d054e8464886b3cde791602`且working tree clean；P2-01～12全部`done`，十二个implementation及各自exact provider evidence均位于该HEAD可追溯祖先链。基线closure push run `32461665177`、required `validate` job/check `96709654227`（GitHub Actions app `15368`）均`completed/success`；artifact `9439159396`未过期，digest=`sha256:007e7a3107d06d7d629f519a87a7e8e0c54143863d422413664d857659e38cb1`。故依赖、提交拓扑与退出前证据一致，Diff base冻结为上述HEAD。

启动范围审查补入Task lifecycle所需current phase/Milestone/index与provenance文档，并声明`IMPACT-PHASE`。Activation-only差异只允许命中`IMPACT-PHASE/IMPACT-DOCS`；在首个实现路径修改前，本卡将把Impact Rule恢复为实际Gate实现所需的`IMPACT-APPLICATION/INFRA/TESTS/GOVERNANCE-REGISTRY/DOCS`集合。既有Solver/Validator/合同/fixture/benchmark、P2-14与P3保持冻结。

Activation implementation `00ba68d59b883599bf1182d055faf53684ba8d64`的push run `32463228988`（attempt 1）/ required `validate` job/check `96714316051`（GitHub Actions app `15368`）全部success；branch protection精确要求`validate`/app `15368`。Artifact `9439713239`（`plantnexus-ci-evidence-32463228988`，45099 bytes）未过期，digest=`sha256:19179316733e2d94c6ca0c8deb7604beb6f7afe22322ea9383a9194280ab62dc`、expiry=`2026-11-19T08:26:59Z`；下载复核`ci-current-task-report.json`绑定该SHA与固定Diff base，为8 committed/0 working paths、2 rows、19 checks、0 issues。现在进入实现差异，完整Impact Rule恢复为六行声明。

首轮全仓回归为`475 passed, 1 failed`：新增指定`application/p2_gate_report.py`公开导入`app.exporters.contract_check`，触发P1时期对全部`application/*.py`统一禁止Exporter的AST断言。由于本Task必须在该指定application入口聚合Export，禁止以dynamic import规避；故在修改该测试前先扩展allow-list，并只允许`p2_gate_report.py → app.exporters.contract_check`一个exact evidence-only例外。其他application文件及API/Infrastructure/Backend/Strategy/Validator/OR-Tools/SQLAlchemy禁令保持原样。

本地实现形成strict internal `p2-vertical-slice-report.v1`与`p2-gate-semantic-projection.v1`。每次完整replay按`correctness → benchmark XS/S/M → output`执行，并嵌入全部sub-report、真实timing/memory/hash/export证据；稳定投影只排除运行时噪声及由其派生的identity，不修改原始证据。两次业务投影的combined fingerprint相同，四类`UNSUPPORTED_CAPABILITY`、`INVALID_PLANNING_PROBLEM`、`INVALID_SOLVE_LIMITS`、`NO_SOLUTION_WITHIN_LIMIT`均以exact category/code/stage fail-closed。

指定聚焦命令为`30 passed in 37.68s`，完整仓库回归为`476 passed in 50.60s`；Gate CLI exit 0并得到11/11 PASS、14次correctness scenario executions、6次benchmark profile executions、108次benchmark Validator passes、4次exit rejection、2次explicit output contract与0 blocking gap。边界固定为P2/Simulation-only、Exit Audit=`NOT_PERFORMED`、P2-14/P3=`NOT_STARTED`、Production readiness=`NOT_CLAIMED`。其余lint/type/build/machine/governance检查和exact implementation provider evidence仍待下述验收完成，故Task保持`in_progress`。

其余本地验收也已完成：Ruff=`All checks passed`，Pyright=`0 errors`；Rule/Generator/Golden/Mutation、P1 Gate、Problem/Machine/Backend/Formal Validator、Core/Temporal/Fact-Lock/Objective、Correctness/Reference/Output/Engineering全部machine reports为PASS；独立XS/S/M各8/8且0 warning；Compose config、`uv build`与`git diff --check`退出0。Full docs治理为142 docs/30 roots/36 Tests/15 OPEN/13 SIM/11 risks/37 Tasks；Task diff为37 paths（8 committed-range、37 working-tree union）、6 Impact rows、19 checks、0 issues并PASS。Schema/migration/dependency/lock/ADR以及冻结的Planning/Strategy/Backend/Validator/Reference/Scenario/Benchmark/Exporter实现均零差异。Exact implementation SHA的required `validate` / artifact仍待push后核验，故Task继续`in_progress`。
