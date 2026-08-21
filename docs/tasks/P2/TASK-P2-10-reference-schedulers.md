---
doc_id: TASK-P2-10
title: Reference Schedulers
status: in_progress
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [51, 52, 53, 54, 75]
last_reviewed: 2026-08-21
---

# TASK-P2-10 — Reference Schedulers

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-015

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-VER-001

Depends on: TASK-P2-01, TASK-P2-02, TASK-P2-04

Start gate: Problem/Solution/formal Validator contracts=`done`；固定算法tie-break和Diff base；不依赖CP-SAT实现细节。启动复核还必须确认P2-09 closure HEAD的required `validate`/artifact精确成功、七个correctness Problem输入与既有Schema/Validator/lock指纹未漂移。

Goal: 实现FCFS、EDD、SPT、Priority+EDD与Greedy Earliest Available Machine reference schedulers，消费同一Problem并由同一独立Validator/KPI口径评估。

Inputs: Problem v2、PlanningSolution、formal Validator、objective/KPI definitions、P2 correctness scenarios。

Diff base: 0e4f6630412889254a7bef41f487c24dc274ca9c

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/simulation/baselines/__init__.py`、`backend/app/simulation/baselines/reference_schedulers.py`、`backend/app/simulation/baselines/contracts.py`、`backend/tests/unit/test_reference_schedulers.py`、`backend/tests/property/test_reference_scheduler_properties.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；以上为进入`in_progress`前冻结的全部实现/测试/CI路径，其他路径先修订。

Files forbidden to change: `backend/app/planning/**`、`backend/app/simulation/scenarios/p2_correctness.py`、全部P2-09 correctness assets、`schemas/**`、`pyproject.toml`、`uv.lock`、CP-SAT backend/Strategy/constraints、Validator formulas、Problem builder/hash/schema、Production fallback/API/DB/Worker、`backend/app/simulation/benchmarks/**`、`benchmarks/**`、BenchmarkRunner/XS-S-M/threshold、Export/P3+。

Implementation steps: 固定`reference-scheduler-policy.v1`与五个算法identity；FCFS按`release/demand/operation`、EDD按`due/release/demand/operation`、SPT按`minimum duration/due/operation`、Priority+EDD按`-priority/due/release/demand/operation`选择ready operation，Greedy Earliest Available Machine按`earliest end/start/duration/resource/operation`选择operation-resource；前四者统一按`earliest end/start/duration/resource`选择资源。五算法只调用同一deterministic hard-feasibility helper，在C-001～C-011边界上生成完整candidate或明确`HEURISTIC_FAILURE`；随后调用fresh formal Validator，计算相同weighted tardiness/makespan/runtime，检测partial/random output并生成`reference-scheduler-report.v1`。

Outputs: 五个baseline scheduler、deterministic/feasibility/property tests和reference report。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/planning/reference-schedulers.md`、`docs/planning/schedule-validator.md`、`docs/planning/objective-policy.md`、`docs/domain/kpi-contract.md`、`docs/simulation/benchmark-harness.md`、`docs/quality/benchmark-regression.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、本Task卡。

Documentation impact rationale: baseline算法是P2 quality sanity check，必须使用相同事实/Validator/KPI且明确非生产fallback。

Change-impact matrix rows reviewed: `IMPACT-PHASE`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/015→TASK-P2-10→TEST-REFERENCE-SCHEDULER/PROPERTY→五算法/validator/KPI report；Global CP-SAT比较留P2-12。

Schema changes: none。

Migration: none。

Dependency changes: none；baseline禁止OR-Tools import。

ADR impact: none；如用作Production fallback或简化hard constraints必须新ADR并另行授权。

Error behavior: 无法构造完整合法计划返回明确failure并保留Validator结果；不得输出partial schedule或把heuristic failure写成Problem INFEASIBLE。

Tests: TEST-REFERENCE-SCHEDULER、TEST-PROPERTY、TEST-GOLDEN-JSSP/FJSP、TEST-VALIDATOR-MUTATION；算法identity/tie-break/replay、hard constraints和无OR-Tools scan。

Benchmark impact: 形成baseline算法输出/feasibility/weighted tardiness/makespan/runtime字段；正式同场景比较和阈值在P2-12。

Simulation scenarios: 使用P2-09 correctness scenarios；不新建performance profile。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_reference_schedulers.py backend/tests/property/test_reference_scheduler_properties.py backend/tests/golden backend/tests/validation backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run python -m app.simulation.baselines.reference_schedulers --root . --report build/validation/TASK-P2-10-reference-schedulers.json`及全部既有P0/P1/P2 machine reports；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`docker compose --env-file .env.example config --quiet`；`uv build`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-10-reference-schedulers.md --check-diff --report build/traceability/TASK-P2-10-report.json`；`git diff --check`；以Diff base核验Schema、Planning/Validator/Scenario/fixture、dependency/lock、Benchmark/Export、API/DB/Worker与P3+禁止路径无差异。

Artifacts: `reference-scheduler-report.v1` comparison report、property/validator evidence、Task report。

Provider evidence: exact SHA required `validate`成功，artifact含五算法身份/结果/Validator与Task report，记录run/job/digest。

Completion conditions: 五算法确定且不绕过Problem/Validator/KPI；合法输出PASS、失败明确；local/provider/docs/trace闭环；不成为Production fallback。

Explicitly excluded: CP-SAT修改、benchmark profiles/thresholds、Export、API/Worker/P3。

PROD_OPEN: OPEN-006/011/012保持OPEN。

SIM_ASSUMPTIONS: 完成前在canonical register分配并登记下一可用SIM assumption ID，用于固定`reference-scheduler-policy.v1`的deterministic tie-break；priority只消费Problem中的versioned positive integer，不新增或猜测权重。二者均不得解释为Production dispatch/fallback policy。

Rollback: 删除baseline实现不影响Global Strategy；保留comparison artifacts；任何已发布benchmark必须标注baseline version不可重解释。

## Activation evidence — 2026-08-21

用户明确授权执行TASK-P2-10。启动时`main=origin/main=0e4f6630412889254a7bef41f487c24dc274ca9c`且working tree clean；P2-09 implementation `20e49c92306128b47313059fabe31534814dbe3d`为该HEAD祖先。基线push run `32443067388`、required `validate` job/check `96657446617`（GitHub Actions app `15368`）均`completed/success`，branch protection精确要求`validate`/app `15368`；artifact `9433118755`未过期，digest=`sha256:f258604cd24d9c68f66f2b9b20b23d438014d46d4e746dfe04f3231686179f10`、expiry=`2026-11-19T03:21:06Z`。下载复核16/16 JSON均PASS，Task报告为58 committed/0 working paths、7 rows、19 checks、0 issues，P2 correctness为8/8、7 scenarios/Validator/property、11 mutations及C-001～C-011正负覆盖。因此P2-01/02/04启动依赖、P2-09输入与provider证据一致，Diff base冻结为上述HEAD。

启动前冻结16个P2-09 correctness asset的repository-relative path+SHA-256清单摘要为`sha256:2f1ebe2362d53f193c0edb649f14e4b6673d7f3bd2e61b5f88b282a534d8cadd`；Problem v2/Solution/KPI/Validation Schema分别为`e6e4a984…87c8`、`4344468e…df4`、`be3dfbcd…9426`、`1da63e93…d353`，rule sheet=`83fc3663…1e2`，Problem contracts=`ff9eaf88…b3a`，planning contracts=`d5f7a7e4…e630`，formal Validator=`e120cc65…8d9f`，P2 correctness orchestrator=`316aee9c…f3e2`，`uv.lock=8b13617f…7a82`。上述文件与语义全部只读。

Scope review确认原卡未包含machine report的CI step/integration contract及Task lifecycle/Impact Rule文档；故在任何baseline实现文件产生前先冻结完整allow-list。新合同固定为`reference-scheduler-contracts.v1`、`reference-scheduler-policy.v1`与`reference-scheduler-report.v1`；算法identity固定为`reference-fcfs.v1`、`reference-edd.v1`、`reference-spt.v1`、`reference-priority-edd.v1`、`reference-greedy-earliest-available-machine.v1`，tie-break逐字使用本卡Implementation steps。本activation-only差异只命中`IMPACT-PHASE/IMPACT-DOCS`；实现完成后按完整Diff base范围重算`IMPACT-REFERENCE-SCHEDULER/TESTS/INFRA/PHASE/GOVERNANCE-REGISTRY/DOCS`。P2-11～14、BenchmarkRunner、XS/S/M、Export、Production fallback与P3均未启动。
