---
doc_id: TASK-P2-11
title: KPI SolverReport and Export Closure
status: done
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [4, 34, 36, 40, 55, 67, 75, 93]
last_reviewed: 2026-08-21
---

# TASK-P2-11 — KPI SolverReport and Export Closure

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-006, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-REL-001, NFR-OBS-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-08, TASK-P2-09

Start gate: complete validated Strategy/Scenario evidence formed；P2-02 report contracts固定；明确P2内部Export与P3 approval/publish边界并记录Diff base。启动复核还必须确认P2-10 closure HEAD的required `validate`/artifact精确成功，P2-09 correctness输入与既有Snapshot/Problem/Solution/SolverReport/Validation/ImportQuality/KPI v1合同指纹未漂移。

Goal: 形成deterministic KPI/SolverReport并完成Snapshot→Problem→validated Solution→标准内部Export package闭环，所有文件同一run/version/hash；不实现审批、发布或外部传输。

Inputs: Snapshot/Problem hashes、PlanningSolution/ValidationReport、ImportQualityReport、solver/policy versions、OBJ-001、export-package contract。

Diff base: 41e958b771f2664b1ac50867903a30b73627878d

Files allowed to change: `.github/workflows/ci.yml`、`pyproject.toml`、`backend/app/__init__.py`、`schemas/data_dictionary.yaml`、`schemas/json/kpi.v2.schema.json`、`schemas/json/export-manifest.schema.json`、`schemas/samples/kpi.v2.synthetic.json`、`schemas/samples/export-manifest.v1.synthetic.json`、`backend/app/planning/reporting/__init__.py`、`backend/app/planning/reporting/kpi.py`、`backend/app/planning/reporting/solver_report.py`、`backend/app/exporters/__init__.py`、`backend/app/exporters/package.py`、`backend/app/exporters/contract_check.py`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_import_validation.py`、`backend/tests/contract/test_rule_contracts.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`backend/tests/contract/test_p2_output_contracts.py`、`backend/tests/integration/test_p2_export_package.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；前三个补充的历史contract test只允许把global schema set assertion提升到`2.5.0`，其document-level版本/immutable bytes断言不得改变；新增路径先修订本卡。

Files forbidden to change: `uv.lock`、既有Schema/sample bytes、`backend/app/planning/contracts.py`、Strategy/Backend/Validator/Problem/Snapshot/Import/Simulation实现与P2-09 assets、ScheduleVersion/ExportJob persistence/state actions、approval/publish/API/DB/Worker、external storage/network、P3 UI/workspace、dynamic Replan/ChangeReport计算、BenchmarkRunner/XS-S-M/threshold及P3+。

Implementation steps: 以additive global schema set `2.5.0`新增`kpi.v2`与`export-manifest.v1`并逐字保留既有artifact；固定`p2-internal-export.v1` profile和canonical JSON/RFC 4180 LF字节规则；从同一validated solution计算priority-weighted tardiness、makespan、schedule counts与按可用日历时间为分母的resource load；校验并固化同run SolverReport；生成`manifest.json`、`schedule.json`、三份CSV、KPI/Validation/Solver/ImportQuality JSON与synthetic `scenario_manifest.json`；manifest逐文件记录hash/bytes/rows及lineage/count，明确`change_report.json`=`DEFERRED_P4_DYNAMIC_REPLAN`、`benchmark_report.json`=`DEFERRED_P2_12`且`publishable=false`；拒绝Validator FAIL/mixed run/version/hash/count、tamper与缺失；通过纯内存构建和同文件系统临时目录原子rename测试deterministic logical equivalence与partial-write边界。

Outputs: KPI/report emitters、internal standard export package、manifest/file hash/consistency tests和machine report。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/contracts/export-package.md`、`docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/domain/kpi-contract.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/schedule-version.md`、`docs/planning/solver-backend-contract.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/quality/benchmark-regression.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: P2 Gate要求Snapshot→Export，必须固定报告/manifest/文件一致性并清楚隔离P3状态/publish。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-REPORTING`、`IMPACT-EXPORT`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/006/009→TASK-P2-11→TEST-OUTPUT/CONTRACT/IDEMPOTENCY→KPI/SolverReport/Validation/manifest package artifacts；P3 publish remains PLANNED。

Schema changes: required；global schema set additive提升为`2.5.0`并新增`kpi.v2`/`export-manifest.v1`，保留kpi.v1及全部既有Schema/sample bytes，提供positive/negative/round-trip/cross-file validation。PlanningSolution/SolverReport等既有document仍固定其原`schema_set_version=2.4.0`，不得随set-level release改写。

Migration: none；只生成in-memory/temp-dir artifacts，不创建ExportJob/ScheduleVersion持久化。

Dependency changes: none。

ADR impact: no new ADR if package remains internal and immutable-versioned；若引入publish/state/persistence或改变ScheduleVersion语义必须停止并留P3。

Error behavior: Validator未PASS、run/hash/version混用、count/hash不一致或文件缺失均拒绝export；I/O错误稳定映射且不留下宣称成功的manifest。

Tests: TEST-OUTPUT、TEST-CONTRACT-001、TEST-IDEMPOTENCY；manifest/file hash、CSV/JSON counts、same-input logical replay、mixed-run/tamper/partial-write负例、synthetic package extras。

Benchmark impact: export/report耗时只作诊断；benchmark report由P2-12提供并作为synthetic extra，不形成Production threshold。

Simulation scenarios: 使用P2-09已验证scenario生成synthetic export；不使用真实生产数据。

Acceptance commands: `uv run pytest -q backend/tests/contract/test_p2_output_contracts.py backend/tests/integration/test_p2_export_package.py backend/tests/contract/test_schema_contracts.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run python -m app.exporters.contract_check --root . --report build/validation/TASK-P2-11-output-contracts.json`及全部既有P0/P1/P2 machine reports；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`docker compose --env-file .env.example config --quiet`；`uv build`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-11-kpi-solver-report-and-export-closure.md --check-diff --report build/traceability/TASK-P2-11-report.json`；`git diff --check`；以Diff base核验既有Schema/sample、Planning/Strategy/Backend/Validator/Problem/Snapshot/Import/Simulation/P2-09 assets、`uv.lock`、Benchmark/API/DB/Worker与P3+禁止路径无差异。

Artifacts: deterministic export package samples/hashes、KPI/Solver/Validation reports、Task report。

Provider evidence: exact SHA required `validate`成功；artifact须包含machine output-contract report与Task report，记录run/job/steps/artifact digest/expiry。

Completion conditions: validated solution到完整internal package可确定性复验；cross-file lineage/count/hash一致；失败不产成功manifest；schema/docs/trace/provider闭环；无P3 state/publish。

Explicitly excluded: READY_FOR_REVIEW/approval/publish、ExportJob DB/worker、external storage/API/UI、ChangeReport/dynamic Replan、P3。

PROD_OPEN: OPEN-002/006/010/015保持OPEN；输出不代表真实系统接口或业务批准。

SIM_ASSUMPTIONS: synthetic export必须携带scenario/benchmark provenance并保持synthetic标识。

Rollback: 未发布internal package可丢弃重建；合同artifact不原地改写；若partial write保留failure evidence并使用新logical job retry，禁止double publish声明。

## Activation evidence — 2026-08-21

用户明确授权执行TASK-P2-11。启动时`main=origin/main=41e958b771f2664b1ac50867903a30b73627878d`且working tree clean；P2-10 implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`是该closure HEAD的直接父提交。基线push run `32450216908`、required `validate` job/check `96677202782`（GitHub Actions app `15368`）均`completed/success`，branch protection精确要求`validate`/app `15368`；artifact `9435421360`（`plantnexus-ci-evidence-32450216908`，37227 bytes）未过期，digest=`sha256:f38a8deb00610bd98a43dca3f9a6c12ae936aec127787db9f24b5b84a0fe9b01`、expiry=`2026-11-19T05:20:58Z`。下载复核17/17 JSON全部PASS；Task报告为38 committed/0 working paths、6 rows、19 checks、0 issues，reference report为7/7且包含5 algorithms、7 scenarios、35 complete candidates/fresh Validator passes/deterministic replays和5 explicit failures。因此P2-08/09依赖、P2-10 closure拓扑与provider证据一致，Diff base冻结为上述HEAD。

启动前冻结P2-09 correctness asset清单摘要=`sha256:2f1ebe2362d53f193c0edb649f14e4b6673d7f3bd2e61b5f88b282a534d8cadd`；Snapshot v2=`d30ed42f…6a09`、Problem v2=`e6e4a984…87c8`、PlanningSolution v1=`4344468e…8df4`、SolverReport v1=`64feacd0…7b2a`、ValidationReport v2=`1da63e93…d353`、ImportQualityReport v1=`2d41fb0a…f434`、KPI v1=`be3dfbcd…9426`，planning contracts=`d5f7a7e4…e630`、Global Strategy=`c3c5f057…4133`、formal Validator=`e120cc65…8d9f`、P2 correctness orchestrator=`316aee9c…f3e2`、`uv.lock=8b13617f…7a82`。这些既有artifact及语义全部只读。

Scope review确认原卡遗漏schema set metadata/sample注册、machine report的CI step/integration contract以及Task lifecycle/Impact Rule强制文档，故在任何实现文件产生前冻结上述完整allow-list。新合同固定为`kpi.v2`、`export-manifest.v1`与`p2-internal-export.v1`；P2内部包以validated PlanningSolution承载`schedule.json`，不是ScheduleVersion，不创建ExportJob，不可审批/发布。由于ChangeReport属于P4 dynamic Replan、benchmark report属于P2-12，二者只在manifest中以deferred状态显式登记，不伪造内容；因此该profile完整但不冒充P3可发布标准包。本activation-only差异只命中`IMPACT-PHASE/IMPACT-DOCS`；实现完成后按完整Diff base范围重算`IMPACT-SCHEMA/REPORTING/EXPORT/STATE/TESTS/INFRA/DEPENDENCY/VERSION-METADATA/PHASE/GOVERNANCE-REGISTRY/DOCS`。P2-12～14与P3均未启动。

## Local implementation evidence — 2026-08-21

已形成`kpi.v2`、`export-manifest.v1`、immutable SolverReport freeze与`p2-internal-export.v1`。KPI从同一validated replay独立计算逐Demand交付/OBJ-001、makespan、完整assignment counts、calendar-denominator resource utilization及明确no-base stability；SolverReport只接受真实`SOLVER_RUN`、formal PASS和Global Strategy identity，保持原timing/metrics字节。Package固定manifest加9个payload，全部JSON canonical、CSV为UTF-8 RFC4180 LF，逐文件保存role/media/hash/bytes/rows并交叉验证run/Problem/Snapshot/Solution/Validation/Solver/Quality/KPI/Scenario血缘与content identities。

纯内存package在返回前完整复验；目录writer在同父目录临时构建、manifest last、原子rename，exact byte replay幂等，conflict/I/O/partial write稳定失败且清理临时目录。Manifest固定`publishable=false`、ScheduleVersion/ExportJob=`NOT_CREATED`、approval/publication=`NOT_STARTED`，并将ChangeReport延后P4、BenchmarkReport延后P2-12。新增task-specific 13项、指定验收49项、全仓455项、Ruff/Pyright、全部历史machine和output report 8/8均PASS；治理为142 docs、58 paths、11 rows、19 checks、0 issues。Compose/build/schema metadata/immutable/forbidden-path与`git diff --check`均PASS，`uv.lock`保持精确摘要`8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`。

首次全量回归为`452 passed / 3 failed`，仅暴露`test_import_validation.py`、`test_rule_contracts.py`与`test_unit_conversion_registry.py`仍精确断言旧global set`2.4.0`。按本卡范围协议，在修改这三处前先将其加入allow-list；修复只同步set-level metadata到`2.5.0`，不弱化Import/Unit/Rule document版本或任何历史fingerprint断言。

## Provider evidence and completion — 2026-08-21

Implementation `546292831c3bd52185687a4c646c10ae10541ae2`已直接push到`main`。GitHub push run [`32454693799`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32454693799)（attempt 1）为`completed/success`；required [`validate` job/check `96689627030`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32454693799/job/96689627030)由GitHub Actions app `15368`执行并success。Branch protection仍精确要求`validate`/app `15368`。

Artifact `9436863185`（`plantnexus-ci-evidence-32454693799`，41084 bytes）未过期，digest=`sha256:77dfadb425f1c3f47d21494127785c81357351aeee6ecbdd4f00386516db054b`、expiry=`2026-11-19T06:30:51Z`。下载复核确认18/18 JSON reports全部PASS且各report的`code_commit`精确绑定implementation SHA；`ci-p2-output-contracts.json`为8/8 checks，并记录4 assignments、2 demands、2 deterministic replays、9 package payloads、3 rejection cases和2 resources；`ci-current-task-report.json`绑定同一SHA和Diff base，记录58 committed/0 working paths、11 Impact Rules、19 checks、0 issues。

因此Goal、测试、Schema/版本/指纹、文档/追踪、provider和回滚边界全部满足，TASK-P2-11=`done`。BenchmarkRunner/XS-S-M/threshold、ChangeReport/dynamic Replan、ScheduleVersion/ExportJob persistence、approval/publish/external transfer、P2 Exit Audit与P3/P4仍明确排除；P2保持`active`，本次关闭不授权或启动TASK-P2-12。
