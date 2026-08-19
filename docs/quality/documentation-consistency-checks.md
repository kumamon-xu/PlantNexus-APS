---
doc_id: DOC-QUAL-007
title: 文档一致性自动检查合同
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 98, 99, 100, 101, 103, 104]
last_reviewed: 2026-08-19
---

# 文档一致性自动检查合同

本文件定义由 TASK-P0-02 建立的文档/追踪校验器合同。实现入口为
[`scripts/check_docs.py`](../../scripts/check_docs.py)，负向和回归测试入口为
[`TEST-TRACEABILITY-VALIDATOR`](../../backend/tests/unit/test_check_docs.py)。该检查器只使用 Python
标准库；P0-02 提供本地/Task acceptance 能力，P0-08 已编排 PR/push 自动执行，Release/P0 Exit Gate 仍由 P0-09 审计。

## 命令接口

仓库全量一致性检查：

```text
uv run python scripts/check_docs.py
```

当前 Task 从不可变基线至 HEAD、再联合 working tree 的影响矩阵检查，并生成机器可读报告：

```text
uv run python scripts/check_docs.py --task <task-card> --check-diff --report <report-path>
```

CI 从不可变 PR/push event base发现当前 Task并执行同一检查：

```text
uv run python scripts/check_docs.py --discover-task-from <40-char-event-base> --check-diff --report build/traceability/ci-current-task-report.json
```

event base只用于Task attribution；实际scope仍来自选中Task Card的`Diff base`。`--task`与`--discover-task-from`互斥，后者必须与`--check-diff`同用。

校验器单元测试：

```text
uv run python -m unittest discover -s backend/tests/unit -p "test_check_docs.py"
```

## 输入

- `--task` 指定的当前 Task Card及其中在进入 `in_progress` 时记录的完整 `Diff base`；
- `git diff --name-only Diff-base..HEAD` 的已提交路径；
- `git status --porcelain` 相对 `HEAD` 的 tracked/untracked working tree 路径；
- `change-impact-matrix.md`；
- 文档元数据、治理注册表、追踪矩阵和测试 ID 表；
- 当前 Phase 和 Milestone。
- 可选CI event base，以及该range内唯一current-phase Task Card；无changed card时只允许唯一`in_progress` current Task回退。

## 必须检查

1. Task Card 包含非空 `Documentation impact`、`Documents to update`、`Traceability updates`；
2. `required` 时文档路径明确存在或由本 Task 创建，并包含在 Files allowed to change；
3. `none` 时有非空理由和已审查的 impact-matrix 行；
4. `Diff base` 是存在且为当前 HEAD 祖先的完整 40 字符 commit SHA；已提交范围与 working tree 并集命中的 `IMPACT-*` 行已在 Task 声明，规则要求的文档已列入 Documents to update；
5. 实际 changed paths 全部位于 Task 允许范围；`.gitkeep` 由矩阵显式忽略；
6. 文档 metadata、唯一 doc ID、source sections、相对链接和 Markdown fence 有效；
7. `registry_version: 1.0.0` 存在，注册表 ID 唯一，Requirement/NFR/ENG/C/OBJ/TASK/TEST/ADR/OPEN/SIM/RISK 引用可解析；
8. 追踪矩阵对所有 Requirement/NFR/ENG 根 ID 一一覆盖，且只链接真实存在的代码、测试和 artifact；
9. 当前 Task 的 dependency、ID/目录/front matter Phase、状态和当前阶段约束一致；P1+ Task还必须包含 `Completion conditions`；
10. `PROD_OPEN-*` 关闭时包含权威来源、证据、决定日期、影响面和迁移/回放结论；
11. `PROD_OPEN-*` 与 `SIM_ASSUMPTION-*` 没有混用，模拟假设不能关闭生产开放项；
12. 历史 Phase只保留 `done`/`cancelled` Task，当前 Phase允许详细 Task Card，未来 Phase只能保留 Milestone。
13. CI event base为完整、存在且是HEAD祖先的SHA；range内历史/未来/phase错位/多个Task Card拒绝，不能硬编码旧Task或自由文本skip。

## CI 分层

| 层 | 行为 |
|---|---|
| Local/Task acceptance | 对当前 Task 的 `Diff base..HEAD` + working tree 运行；提交前后均须可复验，失败不得标记 Done |
| Pull Request | P0-08 接入后成为必需检查；阻止缺失文档影响、断链、版本漏更和越阶段任务 |
| Release | P0-09 接入后在 PR 检查上增加 Artifact/manifest、Milestone Gate 和 production readiness 一致性 |

## 输出

`--report` 写出 `traceability-report.v1` JSON，包含总体状态、Task、可选`task_discovery_base`、Git HEAD、`diff_base`、
`diff_source_counts`、changed paths、matched matrix rows、expected docs、observed docs、检查统计、
带 check ID/severity/message/hint 的 issues。
任一 error 均返回非零退出码；通过时终端输出 `PASS repository governance` 及关键计数。

## 已知边界

校验器验证治理结构、引用、范围和影响同步，不判断业务规则是否正确，也不替代 Schema
兼容性、Solver 正确性、迁移回放或 benchmark 结果。上述语义验证由对应 Task 和后续 CI/Release
Gate 负责；P0-02 不据此声称任何业务能力已实现。

机器治理检查不解析 JSON Schema 语义或 YAML data dictionary。TASK-P0-03 由 `TEST-CONTRACT-001` 使用锁定的 `jsonschema` Draft 2020-12 validator、PyYAML、Ruff 与 Pyright 补充这层证据；后续 Schema Task 必须同时运行治理检查和对应 contract tests。

TASK-P0-04 增加独立的规则合同入口：

```text
uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-04-rule-contracts.json
```

该命令校验 C-001～C-018 rule sheet、20 capability、七类/19 code、三套 state/42 transitions、三份新增 JSON Schema、schema set version 和 validation package 的 Solver import boundary。报告为 `rule-contract-report.v1`，只证明 metadata/registry/schema 一致，不判断 candidate schedule、业务 guard、持久化或 Solver 正确性。

TASK-P0-05 增加 Simulation 合同入口：

```text
uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P0-05-simulation-contracts.json
```

该命令生成 `simulation-contract-report.v1`，验证 empty Standard Import package 的 same-input bytes/hash、generated-at hash exclusion、Generator version change、named layer seed、Production target 和 unsupported capability rejection。Schema/sample 语义由 pytest/jsonschema 补充。报告不验证非空 Factory/Order/Routing records、Import pipeline、Snapshot/Problem、DB/API isolation、Solver 或 Benchmark。

TASK-P0-06 增加 deterministic Golden fixture replay 入口：

```text
uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P0-06-sim-minimal-001.json
```

该命令生成 `golden-fixture-replay-report.v1`，严格加载 8 个 versioned artifacts，执行既有 Profile/Scenario/Manifest pure precheck、跨文件 identity/source/version/seed/capability/package join、non-empty Import canonical bytes/hash replay，并确认 C-ID expected set 完整。它的 `scope=artifact-integrity-and-replay-only`，不读取 rule formula、不输出 ValidationReport、不替代 [`test_sim_minimal_001.py`](../../backend/tests/golden/test_sim_minimal_001.py) 的独立 C-ID/KPI 计算或 TASK-P0-07 mutation evaluator。

TASK-P0-07 增加 fixture-local Validator mutation 入口：

```text
uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-07-validator-mutations.json
```

该命令生成 `validator-mutation-report.v1`，检查 positive Golden、13 个声明式 negative mutations、exact `validation-report.v2`/`error.v2`、Draft 2020-12 Schema、deterministic replay、Rule Sheet violation metadata、C-001～C-011 与 13 required mutation classes 无缺口。其 scope 明确为 P0 fixture-local evaluator，不判断 PlanningProblem/Solver、性能、API/persistence 或 Phase Gate。当前 Task 仍须同时运行 rule-contract CLI、validation pytest 和 `check_docs.py --task ... --check-diff`；任一报告不能替代其他层。

TASK-P0-08 增加 engineering contract 入口：

```text
uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json
```

该命令生成 `engineering-skeleton-report.v1`，检查 exact runtime pins/无 OR-Tools、environment isolation/Production fail closed、live/ready sanitized payload、recursive log redaction、job lease/STALLED/retry 与 idempotency replay/conflict，以及 migration/Compose/Dockerfile/CI artifact layout。它使用 synthetic probes 与 process-local store，不连接真实 PostgreSQL/Redis、不执行 migration、不验证 distributed crash recovery、业务 pipeline、production deployment 或 Solver。对应语义由 integration tests、Alembic empty-DB round trip、Compose config 和独立 acceptance commands 补充。

`.github/workflows/ci.yml` 现执行所有既有 machine checks、本文件两种 docs 命令与 artifact upload。仓库 validator 仍只验证 workflow 文本/路径和 Task diff；外部 provider 是否实际运行、分支保护是否 required 及 run URL/ID 必须由平台证据证明，不能写成 local PASS。

TASK-P0-09 将上述边界实际应用于 Exit Gate：P0-09 full/diff validator 与 repository build均 PASS，但 workflow 仍硬编码 TASK-P0-08 diff range，其 exact command在新 audit commit上 exit 1；空 `git remote -v` 还证明 external provider evidence不可得。因此 CI Gate必须为 `FAIL`，不能只写 `NOT_RUN` 或用其他 local PASS 抵消。planned TASK-P0-10 必须先有界交接 workflow/test，再在用户授权后形成 provider evidence；不得修改本 validator 或 Task 文本来放宽 scope。

TASK-P0-10 不修改 `scripts/check_docs.py` 或 `TEST-TRACEABILITY-VALIDATOR`，只把 workflow exact command 交接为当前 Task Card/`TASK-P0-10-report.json`，并在既有 integration test 内断言完整 command、artifact 名称与旧 `TASK-P0-08` 引用不存在。Diff base `5d8bb51e06add1afc2f53861cf53c7a2ba45a272` 定义 committed range，working tree 仍与该 range 取并集；full repository check 没有删除。

provider 层必须额外校验 Actions run `head_sha`、workflow/job conclusion、artifact ID/name/digest 及 `main` branch required check。这些平台事实不由本地 validator 猜测；remediation 前 run `32227247262` 的失败只是反例，不能充当 PASS。

实际 provider closure 为 run `32228647627` / `head_sha=036bc23bc0ac4d60aab131c0d44eda5508e844d4` / `validate=success` / artifact `9356432918` + digest `sha256:d5cb630772f06732251f785a6ee6aff36856c2a2f619c4178f43b01ac3f0214b`；公开 branch state 显示 `main.protected=true`、required `validate` / app ID `15368`。clean implementation commit 的 TASK-P0-10 report 再次得到 25 committed paths、0 working-tree paths、5 impact rows、19 checks PASS、0 issues。这些平台/提交事实与本地 validator 的职责分层保持不变。

## P1 phase-aware planning baseline

2026-08-19 获得明确 phase transition授权后，validator改为从 `docs/current_phase.md` front matter读取 `Pn`，允许 prior-phase terminal Task与 current-phase detailed Task共存，拒绝 prior-phase non-terminal和future-phase detailed cards，并支持任意 phase内的 Task range依赖。P1及以后卡新增必填 `Completion conditions`；历史 P0卡无需追补。

该调整只使 P1 Task规划可由既有治理命令验证，不实现 canonical Import、Adapter、Snapshot、Problem或任何业务能力。TASK-P1-01仍需把 provider workflow从 P0-10-specific handoff收敛为可持续 P1 CI；本 planning baseline不把 local governance PASS写成 provider PASS。

## TASK-P1-01 changed-task CI handoff

TASK-P1-01新增pure phase-policy/changed-path selector、immutable Git event-range discovery和CLI互斥入口；unit tests覆盖prior terminal/current/future/misaligned、stale historical/multiple/no-card fallback与非完整SHA。workflow integration test固定PR/push event-base来源、中性report/artifact命名、full+diff governance、P0 gate保留和无P0 Task残留。

CI discovery失败返回`PHASE-TASK`/非零，不生成skip PASS。成功报告同时记录`task_discovery_base`与Task `diff_base`，使event attribution和Task scope可分别审计。provider没有实际执行证据时仍为`NOT_RUN`。

## TASK-P1-02 schema governance review

本Task沿用full repository与`Diff base..HEAD + working tree`双检查，并由`IMPACT-SCHEMA/DOMAIN/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`驱动明确文档清单。机器治理仍不解释JSON Schema；TEST-CONTRACT-001补充Draft 2020-12跨URN registry、v1固定fingerprint、positive/negative/round-trip及data dictionary coverage。

Schema set major release必须在Task Completion evidence记录compatibility、migration none理由、retained artifacts、pure/runtime边界与所有必审文档review；生成的`build/traceability/TASK-P1-02-report.json`继续忽略不提交。治理PASS只证明scope/trace/document一致，不证明Adapter、pipeline、Snapshot hash或P1 Exit Gate。

## TASK-P1-03 persistence governance review

本Task沿用full repository与`Diff base..HEAD + working tree`检查，report路径为`build/traceability/TASK-P1-03-report.json`。实际计划路径由`IMPACT-IMPORT/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`覆盖；Task声明的22份文档必须逐项实际更新，migration/internal table不能伪装成Business Schema或外部Contract。

治理检查只验证scope、dependency、changed paths、文档/追踪和impact rows，不执行SQL transaction或判断idempotency correctness。`TEST-IMPORT-STAGING-001`与实际Alembic empty/populated round trip补充该语义；最终提交前后report必须记录完整Diff base、committed/working-tree source counts和0 issues。生成report继续位于ignored `build/`且不提交。

## TASK-P1-04 adapter governance review

本Task沿用full repository与`Diff base..HEAD + working tree`检查，report路径为`build/traceability/TASK-P1-04-report.json`。最终路径由`IMPACT-IMPORT/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`覆盖；启动前补齐5份治理文档，首次diff补齐version metadata审查，全仓回归再驱动有界engineering exact-pin baseline更新；Diff base始终固定为`6c259e172be4bf3cde72a56212df3a1bad427372`。

治理检查不读取CSV/XLSX、不判断macro/formula/archive guard或semantic parity；TEST-IMPORT-ADAPTER-001与exact locked dependency补充该语义。最终提交前后report必须记录完整changed paths/source counts/matched rows/0 issues，ignored `build/` report不提交；provider CI仍须针对immutable implementation/evidence commit另行核验。

## TASK-P1-05 normalization governance review

本Task沿用full repository与`Diff base..HEAD + working tree`检查，report路径为`build/traceability/TASK-P1-05-report.json`。声明的八行impact覆盖新增rule/schema metadata、Normalization code、既有global version assertions、phase/registries和文档；启动前scope expansion已纳入全部矩阵强制路径。检查器只证明路径/引用/版本治理，不解析unit factor、canonical bytes或error semantics，后者由TEST-NORMALIZATION-001/TEST-CONTRACT-001补充。

完成前必须同时证明global schema set`2.1.0`与Import v2 document`2.0.0`的有意区别、两份immutable Schema hash、`uv.lock`无变化、八行matched impact和0 issues。Ignored `build/` report不提交；implementation与evidence commit均须各自核验provider required `validate`。

TASK-P1-05 implementation commit `d52aa62d36e8d89eba318cb5fc586311680e030f`已由GitHub Actions run `32252308695`的required `validate` job `96065907901`证明成功；artifact `9364897397`内`ci-current-task-report.json`精确记录49 changed paths、8 matched impact rows、0 issues且result=`PASS`。Provider/download ZIP digest均为`sha256:5db1ccbb242b555d8a95d36ac9cc1b1373dab95d482dbde17ab7fb369cce2966`。完成态证据提交仍按其自身精确SHA核验，不以本段自我声明替代provider结果。

## Override

不允许用自由文本 CI skip 绕过。确需例外时必须在 Task Card 记录理由，提交 ADR 或明确批准记录，并仍保留检查报告。正确性、状态语义、数据隔离和发布门不得豁免。
