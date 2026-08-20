---
doc_id: TASK-P2-00
title: P2 Phase Transition and Task Planning Governance
status: done
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [73, 74, 75, 76, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-20
---

# TASK-P2-00 — P2 Phase Transition and Task Planning Governance

Task batch role: phase-planning-owner

Requirement IDs: REQ-004, REQ-005, REQ-006, REQ-009, REQ-012, REQ-014, REQ-015

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-12

Start gate: 用户明确批准 P1→P2；P1 audit overall=`READY`且blocking gaps为空；TASK-P1-01～12全部`done`；audit implementation `a5d7e4a68dc12d48e36cb692500f59446f8097b4`与当前基线`098c44059856e3203d95d046fea44894b5cf414b`的祖先、required `validate`及artifact证据一致；`main=origin/main`且working tree在Task启动前干净。

Goal: 仅完成P1关闭、P2激活、完整P2 Task拆分和可持续多卡规划CI归属治理；不实现任何P2业务能力。

Inputs: P1 Exit Gate report/manifest/provider证据、P2 Milestone、总规§75～76、架构/合同/Planning/质量/治理基线及用户本次授权。

Diff base: 098c44059856e3203d95d046fea44894b5cf414b

Files allowed to change: `scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py`、`docs/current_phase.md`、`docs/README.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P2/TASK-P2-00-phase-transition-and-task-planning-governance.md`、`docs/tasks/P2/TASK-P2-01-planning-problem-v2-contract-gap-closure.md`、`docs/tasks/P2/TASK-P2-02-planning-machine-contracts-and-status.md`、`docs/tasks/P2/TASK-P2-03-ortools-backend-foundation.md`、`docs/tasks/P2/TASK-P2-04-formal-independent-schedule-validator.md`、`docs/tasks/P2/TASK-P2-05-cp-sat-core-assignment-resource-model.md`、`docs/tasks/P2/TASK-P2-06-cp-sat-temporal-calendar-material-model.md`、`docs/tasks/P2/TASK-P2-07-execution-facts-and-hard-lock-model.md`、`docs/tasks/P2/TASK-P2-08-delivery-objective-and-global-strategy.md`、`docs/tasks/P2/TASK-P2-09-golden-scenario-property-integration.md`、`docs/tasks/P2/TASK-P2-10-reference-schedulers.md`、`docs/tasks/P2/TASK-P2-11-kpi-solver-report-and-export-closure.md`、`docs/tasks/P2/TASK-P2-12-benchmark-runner-xs-s-m.md`、`docs/tasks/P2/TASK-P2-13-p2-vertical-slice-gate-evidence.md`、`docs/tasks/P2/TASK-P2-14-p2-exit-gate-audit.md`，以及`Documents to update`列出的文档与ignored `build/traceability/TASK-P2-00-report.json`。

Files forbidden to change: `backend/app/**`、`schemas/**`、`fixtures/**`、`benchmarks/**`、`pyproject.toml`、`uv.lock`、migrations、`.github/workflows/**`、P1 audit历史报告/manifest、任何P2 Solver/Validator/Export/Benchmark实现、P3+详细Task。

Implementation steps: 复核P1状态/拓扑/provider artifact；将P1 Milestone置为completed并激活P2；按合同缺口和Gate依赖创建P2-01～14；引入严格的phase-planning batch owner/member发现规则及负向测试；同步Task/Milestone/Phase/trace/inventory/quality治理；运行本地验收；提交并push当前main；核验exact required check/artifact；以evidence-only closure关闭本Task。

Outputs: active P2治理基线、15张P2 Task卡、依赖图、更新后的追踪/清单、可审计的多卡规划CI归属证据。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/architecture/repository-layout.md`、`docs/governance/document-control.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/tasks/README.md`、`docs/adr/README.md`，以及Files allowed to change中逐字列出的15张P2 Task卡。

Documentation impact rationale: Phase、Milestone、Task分配、CI Task归属和root→Task计划关系同时变化；强制文档逐项审查，只有事实变化的文档才修改，未修改项在completion evidence解释。

Change-impact matrix rows reviewed: `IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-TESTS`、`IMPACT-DOCS`

Traceability updates: P1 audit/授权→TASK-P2-00；REQ/NFR/ENG与C-001～C-011、OBJ-001→TASK-P2-01～14→既有planned Test IDs→预期machine/provider artifacts；所有root保持`ALLOCATED`且P2 artifact保持`PLANNED`。

Schema changes: none；不修改schema set、document schema或sample。

Migration: none；不修改或执行数据迁移。

Dependency changes: none；`pyproject.toml`与`uv.lock`保持无OR-Tools，首次依赖变更只允许在TASK-P2-03。

ADR impact: none for this governance-only transition；只登记TASK-P2-01/03各自的ADR启动门，不创建或接受技术决定。

Error behavior: P1状态、证据或HEAD任一不一致立即停止且不切Phase；batch归属出现多个owner、历史卡、非新增成员、成员已active/done或预填SHA时CI硬失败。

Tests: TEST-PHASE-GOVERNANCE-001与TEST-TRACEABILITY-VALIDATOR增加合法batch及existing/active-member负例；不增加业务Test ID。

Benchmark impact: none；不运行Solver Benchmark，不建立性能baseline，不关闭OPEN-012。

Simulation scenarios: none；只复核P1已形成Scenario证据，不生成或求解新Scenario。

Acceptance commands: `uv sync --locked`；`uv run ruff check scripts/check_docs.py backend/tests/unit/test_check_docs.py`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-00-phase-transition-and-task-planning-governance.md --check-diff --report build/traceability/TASK-P2-00-report.json`；`git diff --check`。

Artifacts: `traceability-report.v1`、targeted/full test outputs、P1 topology/provider verification record、GitHub exact run/job/artifact/required-check evidence。

Provider evidence: provider/repository/branch/workflow固定为GitHub/`kumamon-xu/PlantNexus-APS`/`main`/`.github/workflows/ci.yml`；记录immutable head SHA、push run ID/URL/attempt、required `validate` job/steps、artifact ID/name/size/digest/expiry及branch protection；失败或取消必须保留并阻断closure。

Completion conditions: P1证据一致；P1=`completed`、P2=`active`；P2-01～14均为依赖/范围/Schema/迁移/依赖/ADR/测试/本地/CI/docs/rollback可执行的`planned`卡且P2-14最后；batch发现负向路径不放宽；full/diff治理与回归PASS；implementation commit及evidence-only closure均有exact provider成功证据；无业务代码/P3变化。

Explicitly excluded: P2-01或任何后续Task实现、OR-Tools安装、Schema/fixture/benchmark创建、Solver运行、P3 Task/审批/发布/动态重排/Production声明。

PROD_OPEN: OPEN-001～015全部保持既有真实状态；尤其OPEN-004/005/006/007/009/010/011/012不由Task规划关闭。

SIM_ASSUMPTIONS: SIM-ASSUMPTION-001～010保持既有状态；P2未来权重/profile只能引用版本化Simulation policy，不能外推Production。

Rollback: 在push前回退本Task全部文档/治理变更并保持P1 active；push后若事实错误使用有界更正或superseding governance commit，绝不重写P1 audit历史或以reset/force-push删除失败run。

## Completion evidence

### Preconditions and transition decision

- Task启动基线：`main=origin/main=098c44059856e3203d95d046fea44894b5cf414b`，working tree clean；`git fetch origin main`后仍一致。
- TASK-P1-01～12 front matter全部`done`。`8830a6dc566df8093b601a82c87c74a9cfd97b59`→P1 audit implementation `a5d7e4a68dc12d48e36cb692500f59446f8097b4`→当前基线的祖先检查均exit 0。
- P1 audit report/manifest均为overall=`READY`、blocking gaps为空。Audit implementation的GitHub run `32326616525` / required job `96299073525` / artifact `9391591718`及当前基线run `32327121469` / job `96300506550` / artifact `9391753870`均为push attempt 1、completed/success且未过期；branch protection required context=`validate`，force push/deletion disabled。
- 下载的当前基线artifact中`traceability-report.v1`=`PASS`、TASK-P1-12、30 paths/3 rows/0 issues，P1 pipeline=`PASS`且14/14 checks；因此用户声明、audit、topology、HEAD和provider evidence一致，P1→P2切换获准。

### Actual scope and governance

- Pre-commit actual range：Diff base/Git HEAD均为`098c44059856e3203d95d046fea44894b5cf414b`，`committed_range=0`、`working_tree=32`、32 paths；matched=`IMPACT-DOCS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-PHASE`、`IMPACT-TESTS`，0 issues。
- 实际修改17个既有文件：governance validator/unit test、Phase/P1/P2/Milestone/Task索引、Task template、trace rules/matrix/inventory/change-impact、CI/docs consistency/test strategy、docs/ADR入口；新增15张`docs/tasks/P2`卡。没有业务代码、Schema、fixture、dependency/lock、migration、workflow、benchmark或P3路径。
- 强制审查但未修改：根`README.md`、`docs/agents/AGENTS.md`、`reading-order-and-context-policy.md`、`architecture/repository-layout.md`、`governance/document-control.md`的入口/读取/路径规则无需改变；requirements/NFR/PROD_OPEN/SIM_ASSUMPTION/risk registry的ID、状态和表结构无需改变。Change-impact matrix增加`IMPACT-PLANNING-CONTRACTS`、`IMPACT-REPORTING`、`IMPACT-REFERENCE-SCHEDULER`并把`run_benchmark.py`纳入benchmark rule，防止P2未来路径无归属。
- P1 Milestone front matter改为`completed`，P2改为`active`；current phase/Task index改为P2。TASK-P2-01～14均为`planned`且无implementation SHA，P2-14为最后一项。
- 多卡CI规则只有一个新建`TASK-Pn-00` owner；成员必须同range新增、planned/ready且无SHA。新增unit tests实际覆盖合法owner和existing/active-member拒绝，普通单卡及历史/future/multiple拒绝保持回归。
- 使用当前machine-readable rules对14张P2 member卡的计划allowed paths、declared Impact IDs和Documents to update进行dry run，14/14 PASS；每张卡在启动前仍须把任何glob展开为exact paths并用真实diff复验。

### Local acceptance

| Command / gate | Exit | Actual result |
|---|---:|---|
| `uv sync --locked` | 0 | 63 packages resolved/checked；dependency与lock未变 |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run pyright backend/app backend/tests` | 0 | 0 errors/warnings/informations |
| targeted governance/CI tests | 0 | 22 passed |
| full registered pytest directories | 0 | 273 passed |
| `uv run python scripts/check_docs.py` | 0 | 140 docs、30 roots、36 tests、15 OPEN、10 assumptions、10 risks、37 Tasks |
| P2-00 `--check-diff` report | 0 | 32 paths、5 impact rows、19 checks PASS、0 issues |
| `git diff --check` | 0 | no whitespace errors；仅工作区LF→CRLF提示 |
| `uv build` | 0 | sdist与wheel成功 |

### Schema, dependency, ADR, evidence, and rollback boundaries

- Schema/migration/dependency=`none`；schema set保持`2.2.0`，`pyproject.toml`/`uv.lock`仍无OR-Tools。ADR技术决定=`none`；P2-01/03只登记未来启动门。
- Test registry仍为36项/`registry_version=1.0.0`；只有TEST-PHASE-GOVERNANCE-001与TEST-TRACEABILITY-VALIDATOR增加当前代码证据，全部P2业务Test/Artifact仍`PLANNED`。
- OPEN-001～015、SIM-ASSUMPTION-001～010与RISK-001～010状态未变；没有Production/性能/容量结论。
- Implementation commit=`3298229fae89a54e0641f5907ad90c4fa81569bf`。GitHub push run [`32332003608`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32332003608)为attempt 1/completed/success；required `validate` job `96314305102`的20个steps全部success。Artifact `9393345593`=`plantnexus-ci-evidence-32332003608`，size=9103 bytes，digest=`sha256:847f2299969bc47fc1cc49024fc1f3a51a6bca06db41fc63eccb909aa7dd5e7c`且`expired=false`；required context=`validate`/app ID `15368`，exact commit check-run=`completed/success`。
- 下载artifact内`traceability/ci-current-task-report.json`精确绑定TASK-P2-00、head=`3298229fae89a54e0641f5907ad90c4fa81569bf`、discovery base/Diff base=`098c44059856e3203d95d046fea44894b5cf414b`，记录32 committed/0 working paths、5 impact rows、19/19 checks PASS、0 issues。其余六份既有P1/P0 machine reports均随job成功上传；Benchmark hook明确deferred，未运行Solver。
- Evidence-only closure提交前再次运行targeted tests=22 passed、full docs=140/30/36/15/10/10/37且0 issues；explicit Task report在implementation HEAD上记录32 committed + 12 working source paths的并集仍为32 unique paths、5 rows、19/19 checks PASS、0 issues，`git diff --check` exit 0。
- Task在本evidence-only closure标记`done`；closure自身的exact required run/artifact将在提交/推送后作为最终外部交付证据核验，不可能由本commit自我包含。若closure provider失败，保留失败run并追加有界修复，不改写P1 audit或force-push历史。
