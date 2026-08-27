---
doc_id: DOC-QUAL-007
title: 文档一致性自动检查合同
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 98, 99, 100, 101, 103, 104]
last_reviewed: 2026-08-27
---

# 文档一致性自动检查合同

## TASK-P4-02 governance checks

当前Task report必须从Diff base `4026597ab1015b5ea3a89d241f0d12b5b481dee3`发现唯一`in_progress` TASK-P4-02，验证逐字allow-list、依赖状态、phase policy、Document Inventory、30 roots/rows、61 Test IDs、15 OPEN、16 SIM assumptions、17 risks与实际Impact Rules。Implementation/closure artifact中的report必须与exact SHA、changed paths、checks和issues逐项一致。

## TASK-P4-01 contract/ADR validation

不可变Diff base=`b96232b2e3f5573baaf735c7fa7935f95e6c88f5`。Task diff只能出现卡片逐字列明的57个文档路径，其中新增且仅新增ADR-0013～0015三份Markdown；root `README.md`在发现其current-status仍写P4-01未授权后先扩卡纳入。Diff必须精确命中`IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`四行。`backend/**`、`schemas/**`、`frontend/**`、migration、dependency/lock、tests/fixtures/benchmarks、workflow、P0～P3历史与P5+必须零差异。

Full governance由185增至188份Markdown，保持30 roots/30 trace rows、61 Test IDs、15 OPEN、15 SIM assumptions、17 risks与71 Tasks；ADR registry新增三个accepted ID，本closure把TASK-P4-01标为`done`而P4-02～15仍`planned`。Implementation artifact `9634380233`已精确复现57 committed/0 working paths、四个Impact Rules、17/17 expected/observed documents、19/19 checks、0 issues及上述治理计数；closure提交后仍须由其自身exact provider artifact复验。

## P4 phase-plan validation

本次phase-planning batch必须由唯一TASK-P4-00 owner覆盖P4-01～15全部新增卡，验证current phase=P4、P3 completed/P4 active、依赖无环且最终Task=P4-15、成员无伪造Diff base/implementation SHA、所有引用与registry/inventory计数一致。相对`61eeacdd5efc20b2321750e1310e9e21561c9fc2`的Task diff必须只命中允许文档并为0 issues；checker代码与CI workflow本次不改。

本地结果为185 docs、30 roots/rows、61 Test IDs、15 OPEN/SIM、17 risks、71 Tasks；Task diff为83 unique paths、4 Impact Rules、19/19 checks、0 issues。首轮未注册future ADR ID引用被fail-closed检查拒绝，现改为由TASK-P4-01启动时分配stable ID并复验PASS；没有创建占位ADR或放宽检查。

Implementation artifact `9632983094`中的`traceability-report.v1`精确绑定`c94af400392418f9bb69509331fa8d1dff046184`与Diff base，复现83 committed/0 working paths、四行、17/17 expected/observed documents、19/19 checks、0 issues及全部治理计数。该证据只把TASK-P4-00标为`done`；P4-01～15 planned-member/no-SHA规则继续生效。

## TASK-P3-17 audit conclusion

审计前full governance为168 docs/30 roots/30 trace rows/49 Test IDs/15 OPEN/15 SIM/14 risks/55 Tasks，P3-17 activation diff为19 checks/0 issues。新增Exit report后inventory应为169；implementation提交前必须重新运行full/diff、`git diff --check`与禁止范围核验，provider artifact还须精确复现Task/Impact/check/issues。

## TASK-P3-16 governance contract

Diff checker固定使用`1636fe9c909b728d49f9907ed9f53030b5921914`，只允许Task卡逐字列出的Frontend source/test/E2E/evidence、additive workflow和Documents-to-update路径。完整range应命中`IMPACT-FRONTEND/INFRA/STATE/PHASE/GOVERNANCE-REGISTRY/DOCS`六行；STATE只审查三份状态机与ADR index的display-only/zero-pair-drift，不修改machine pair。`frontend/package.json`/lock、backend、Schema、migration、state实现、fixtures/benchmarks、P3历史、P4与Production必须零差异。Full governance继续为168 Markdown、30 roots/trace rows、49 Test IDs、15 OPEN、15 SIM、14 risks与55 Tasks；新增TS/Playwright/report不进入Markdown inventory。Implementation与closure各自必须以event-base动态发现TASK-P3-16、产生19/19 checks与`issues=[]`并由exact provider复验。

提交前implementation本地报告曾复验79 working/0 committed-range paths、上述六行、19/19 checks与0 issues；full治理计数为168/30/30/49/15/15/14/55。Implementation artifact `9629193057`中的exact-SHA Task report现复现79 committed/0 working paths、上述六行、19/19 checks与0 issues。Evidence-only closure本地报告为79 committed-range/38 working-tree sources、79 unique paths、同六行、19/19 checks、0 issues，且38个closure-only path全部为README/docs。Closure仍须在提交形成后从implementation event base动态发现同一Task，并取得自身exact provider。

## TASK-P3-15 amendment-governance contract

普通event唯一Task和首次all-added Pn-00 batch语义保持不变。新增修订模式要求唯一`phase-plan-amendment-owner`、完整Diff base、稳定逻辑Task ID、成员`planned/ready`且无implementation SHA；event base中active/done成员改写、deleted-only、重复存活路径、多owner与历史/future卡必须非零。22项unit regression覆盖selector与repository event-base读取；implementation artifact `9597967232`已精确复验26 committed/0 working paths、五行、19 checks与0 issues。

本closure允许同一owner稳定ID rename，并原子新增两个planned/no-SHA成员、官方术语规范、一个planned Test ID及一个风险。Full governance预期为168 Markdown、30 roots、30 trace rows、49 Test IDs、15 OPEN、15 SIM、14 risks与55 Tasks；因两份state-machine规范显式记录display-only/no-pair-impact边界，完整Diff命中`IMPACT-GOVERNANCE-VALIDATOR/STATE/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行，并须纳入ADR索引与PlanningRun必审项，仍为19 checks与0 issues。Closure必须从implementation event base动态选择TASK-P3-15，绑定原不可变Diff base，且不得出现Frontend/Backend业务、Schema、migration、dependency、workflow、P3-00～14、P4或Production变化；exact closure provider形成前只记录local closure evidence。

提交前本地full治理实际为168 docs/167 formal docs/30 roots/30 rows/49 tests/15 OPEN/15 SIM/14 risks/55 tasks/167 unique Doc IDs；显式Task report为26 committed-range + 46 working-tree sources、48 unique paths、六行、19/19 checks、0 issues。Ruff/Pyright/22项治理unit/621项full repository与禁止范围均PASS；event-base自动发现必须在closure commit形成后执行，不能从尚未提交的working tree伪造event range。

## TASK-P3-14 governance contract

Full docs仍应为165 Markdown、30 roots、30 trace rows、48 Test IDs、15 OPEN、15 SIM、13 risks与53 Tasks。Task diff必须以`6a3e02f00bf46f19915cb59c3c4af7daaac95be4`为base，只出现逐字allow-list路径并精确命中`APPLICATION/STATE/FRONTEND/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`八行；报告须为0 issues。Implementation与closure分别复验，不得把ignored Gate/provider文件计入受管路径。

提交前本地报告精确为56 working/0 committed-range paths、上述8 rows、19/19 checks和0 issues；full治理为165/30 roots/30 rows/48 tests/15 OPEN/15 SIM/13 risks/53 tasks。Corrective artifact `9593460266`中的Task report已绑定exact `54a25646053979a69734a3148030830d49c04c1e`与Diff base，复现56 committed/0 working paths、8 rows、19/19 checks和0 issues；本closure只写provider事实并须由自身exact provider复核。

## TASK-P3-13 governance contract

Diff checker必须以冻结base `3dacf83c0f0bf87a9fa673aa75d61f8ad8659386`计算committed+working union，只允许Task卡逐字路径并精确命中11行：`IMPACT-APPLICATION/API/STATE/FRONTEND/EXPORT/JOBS/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`。所有required documents必须实际进入Diff；Schema/migration/dependency/lock、domain state implementation、repository persistence、P2 bytes、Solver/Validator/KPI、fixtures/benchmarks、external/P4/Production路径必须为零。

Full docs预期保持165 Markdown、30 roots、30 trace rows、48 Test IDs、15 OPEN、53 Tasks和13 risks；新增SIM-ASSUMPTION-015使SIM count由14增至15但不改变registry format。Task report必须绑定exact SHA/base、11 rows、全部checks和0 issues；implementation/closure provider分别复验，不能自动启动P3-14。

提交前本地实测为165 docs/30 roots/30 trace rows/48 Test IDs/15 OPEN/15 SIM/13 risks/53 Tasks；Task union为91 paths、11 Impact rows、19/19 checks、0 issues。Schema/migration/dependency/lock、domain state implementation、repository、P2 bytes、Solver/Validator/KPI、fixture/benchmark与P4/external/Production禁止范围均为零差异。Artifact `9589931373`中的Task report绑定exact implementation SHA/base并复现91/0/11/19/0；closure `87d47c7483185483ac8027100c1c664d18011a7c` / run `32921871460`失败且无artifact，Task因此曾恢复`in_progress`。XLSX timestamp fix仍在同一91-path allow-list内；独立corrective artifact `9590625358`重新复验exact `3538d46f8b73ae434057bcbca9037436aa91f2c7`和91/0/11/19/0，故本closure可标Task=`done`，closure自身仍须exact provider。

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
13. CI event base为完整、存在且是HEAD祖先的SHA；普通range内历史/未来/phase错位/多个Task Card拒绝，不能硬编码旧Task或自由文本skip。多卡只允许all-added Pn-00 initial owner或唯一既存amendment owner；后者还必须执行稳定ID rename、base status、member SHA与删除/重复路径检查。

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

## TASK-P1-06 data-quality governance review

本Task沿用full repository与`Diff base..HEAD + working tree`检查，report路径为`build/traceability/TASK-P1-06-report.json`。声明的九行impact覆盖additive Schema/error registry、domain types、Data Validation import layer、global version metadata、限定tests、phase/registries和全部矩阵强制文档；Diff base固定`75d761332204ec779477ba7242c98517cce1b68b`。

治理检查只证明scope、版本、文档和追踪，不执行DAG/SCC、resource eligibility、Error排序/count/report ID或四类Gate语义；TEST-DATA-QUALITY-001与TEST-CONTRACT-001补充这些事实。完成前必须证明global `2.2.0`、Import v2 `2.0.0`、unit registry `2.1.0`的有意区别、六份历史artifact hash、`uv.lock`无变化、九行matched impact与0 issues；ignored report不提交，implementation/evidence commit分别核验provider required `validate`。

## TASK-P1-07 expansion governance review

本Task继续使用full repository与`Diff base..HEAD + working tree`检查，report路径为`build/traceability/TASK-P1-07-report.json`，不可变Diff base为`97728521e187f9f50715de4b04a09098bef62ddf`。实际路径由`IMPACT-DOMAIN/IMPORT/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`九行覆盖；启动前已先补齐初始矩阵强制文档和root README，发现CI未收集property后又在修改workflow前扩卡纳入INFRA范围及两份强制文档。Provider closure review发现端到端链路当前态仍停在P1-06，已在修改前再扩卡纳入该已登记文档；最终base-range union为46 paths。

治理检查只证明scope、dependency/version、追踪和文档一致，不执行derived ID、fact/lock/candidate copy或Hypothesis shrinking；TEST-ORDER-EXPANSION-001补充这些语义。Implementation commit `5a3dbc14c12a107abf4052cca935e3ef59009d3d`的provider artifact `9369917400`内report为45 committed paths、9 matched rows、0 issues且精确匹配SHA；provider/download digest同为`sha256:8aeb7416516f7932436bbf406d800cdbdeb8313ba9249f2709b7df71647e566e`。Closure治理继续证明46-path union、schema set=`2.2.0`、Import/Snapshot v2=`2.0.0`与0 issues；ignored report不提交，完成态提交仍按自身精确SHA核验required`validate`。

## TASK-P1-08 Snapshot governance review

本Task继续使用full repository与`Diff base..HEAD + working tree`检查，report路径为`build/traceability/TASK-P1-08-report.json`，不可变Diff base为`8b4fb4c027305d3e3aa68eec0baaf73cd0598189`。启动前先把root/docs入口、端到端链路及`IMPACT-SNAPSHOT/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行全部强制文档纳入卡片；Schema、dependency/version metadata、Import/Expansion和Planning/Solver路径保持只读。

治理检查只证明scope、依赖、文档和追踪，不执行hash projection、frozen value、repository trigger或migration；TEST-SNAPSHOT-REPLAY-001/TEST-SIM-ISOLATION及实际Alembic tests补充这些语义。Implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`的provider artifact `9386127863`内report为41 committed paths、6 matched rows、0 issues且精确匹配SHA；provider/download digest同为`sha256:69d68183bad614631df07234a3ca88508379ab89ec715f811ee7f529d6f17e0c`。Ignored report不提交；evidence-only completion commit仍须按自身精确SHA核验required `validate`。

## TASK-P1-10 generator governance review

本Task以immutable Diff base `11c6ca97882a3be5bf6eb25bab84f69d1dfe469c`运行full与`--task ... --check-diff`检查，report路径为`build/traceability/TASK-P1-10-report.json`。实际范围声明`IMPACT-IMPORT/SIM-GENERATOR/FIXTURE/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`；启动时补齐contract-check与矩阵强制文档，真实调用发现Normalization字段分类矛盾后再次先扩卡加入唯一normalizer/test路径及IMPORT强制文档。Schema、dependency、Snapshot/Problem、Solver/Benchmark和governance validator保持只读。

当前`python -m app.simulation.generators.contract_check` CLI已升级为`synthetic-generator-report.v1`，验证P1非空Import replay/PASS；历史P0 `run_contract_checks()`仍保留供既有P0测试直接调用，不能把当前CLI报告伪写成P0-05 artifact。治理报告只证明scope/docs/trace，不执行生成/Normalization/DataValidation语义；P1 generator tests和machine report补充该证据。Ignored build reports不提交，provider closure必须绑定真实implementation SHA。

TASK-P1-11的diff应精确命中`IMPACT-APPLICATION`、`IMPACT-SIM-GENERATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`七行，且Task Card必须列入每行强制文档。启动前预检已补入Generator公开staging路径、`technology-stack.md`、`milestones/README.md`与`TASK_TEMPLATE.md`；未经先扩卡不得越界修改。

P1-11验收继续原样重放P0 `engineering-skeleton-report.v1`。其`business_pipeline=NOT_IMPLEMENTED`是该P0工程报告“不执行/验证业务链”的冻结scope sentinel，不是对当前仓库能力的全局否定。P1 common-ingress的权威machine evidence是独立`p1-data-pipeline-report.v1`；不得重写历史P0 report version以伪装它验证了新pipeline。

## TASK-P1-12 audit governance

P1-12只修改卡片声明的phase/milestone/contract/architecture/quality/governance文档并新增audit report/manifest；业务代码、Schema、fixture、test、migration、workflow、dependency和P2路径均保持只读。最终diff必须仅命中`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`，且`traceability-report.v1`记录完整Diff base、actual paths、3 matched rows和0 issues。

Full检查的最终基线为125份`docs/**/*.md`、30 roots、36 Test IDs、15 OPEN、10 SIM assumptions、10 risks和22 Tasks。新增JSON evidence manifest不进入Markdown inventory；ignored machine/trace reports也不提交。Audit report的`READY`必须与manifest一致；Task自身provider run在implementation提交前不能自我包含，因此只在run `32326616525`、job `96299073525`与artifact `9391591718`真实成功后，由本evidence-only revision回填，不能预写或伪造。

## TASK-P2-00 phase-planning batch governance

用户明确批准P1→P2后，current phase切为P2，P0/P1仅允许terminal历史卡。P2+ Task除`Completion conditions`外还必须具有`Start gate`、`Dependency changes`、`ADR impact`与`Provider evidence`。TASK-P2-00的Diff base固定为`098c44059856e3203d95d046fea44894b5cf414b`；本Task只改phase/milestone/task/trace/inventory/quality docs与governance validator/tests，不修改业务代码、Schema、fixture、dependency、workflow或P3路径。

普通CI range的唯一Task规则不变。只有同一range首次新增完整阶段计划时，才可由唯一新建`TASK-Pn-00`/`phase-planning-owner`归属；所有成员必须同range新建、role=`phase-plan-member`、status=`planned/ready`且无implementation SHA。existing/active/done member、多个owner、错误owner ID或non-current card均负向失败。选择owner后仍使用owner Diff base检查全部changed paths、exact allowed scope与Impact Rules，不能以batch名义实现多个Task。

本次新增15张P2卡使inventory从125增至140；TEST-PHASE-GOVERNANCE-001与TEST-TRACEABILITY-VALIDATOR只增加batch selector正反证据。P2业务Test IDs全部保持`PLANNED`。Implementation `3298229fae89a54e0641f5907ad90c4fa81569bf`在local explicit/event-discovery clean checks及provider run `32332003608` / artifact `9393345593`中均选择TASK-P2-00并得到32 committed/0 working paths、5 rows、19 checks、0 issues；Task据此由evidence-only closure标记done。

## TASK-P2-01 contract governance

P2-01在任何业务实现前固定Diff base、验证依赖/授权/v1 hashes并扩充allowed paths/Documents/Impact Rules；新增ADR-0010使inventory从140增至141。Diff必须只落在卡片明确列出的Problem v2 Schema/sample/code/tests/workflow/version metadata与治理文档，且`uv.lock`、v1 Problem Schema/sample、Application、Backend/Strategy/Validator/Benchmark/P3路径保持无差异。

Full与Task diff检查同时识别`IMPACT-SCHEMA/PROBLEM/DOMAIN/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`，并验证global set`2.3.0`与immutable document versions/bytes并存。Implementation `c64284685f37ef0d03eacade5699076146653333`的provider artifact `9394931377`内Task report精确绑定该SHA、60 paths/10 rows/0 issues，Problem report为4/4 PASS；evidence-only closure据此只回填真实provider事实并标记Task `done`，不改变机器规则或启动P2-02。

## TASK-P2-02 contract governance

P2-02在实现前固定P2-01 verified closure、Problem v1/v2与`uv.lock`fingerprints、Diff base和exact allow-list；实现中在修改前把含current schema-set值的glossary补入范围。Diff必须命中并声明`IMPACT-SCHEMA/PLANNING-CONTRACTS/POLICY/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`，且`uv.lock`、Problem v1/v2、Backend/Constraint/Validator/DB/API/Worker/P3路径无差异。

Full与Task diff检查验证global set`2.4.0`和旧document内固定`2.0.0/2.1.0/2.2.0/2.3.0`并存、四个新Schema/sample登记完整、所有Documents/Impact rows闭合；结果为141 docs、30 roots、36 tests、37 tasks，Task diff=63 paths/11 rows/19 checks/0 issues。Ignored machine/trace reports不进入document inventory。Implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`的run `32342489997` / artifact `9396828326`精确复现上述Task结果与5/5 machine checks，故P2-02现为`done`，且没有自动激活后续Task。

## Override

不允许用自由文本 CI skip 绕过。确需例外时必须在 Task Card 记录理由，提交 ADR 或明确批准记录，并仍保留检查报告。正确性、状态语义、数据隔离和发布门不得豁免。

## TASK-P2-03 solver-foundation governance

P2-03在dependency变更前固定Diff base、启动hash、exact allow-list和accepted ADR-0011。Diff必须只命中卡内dependency/backend/compatibility tests/workflow及Documents路径；Problem/Policy/Solution/Report Schema/sample和canonical合同、C-ID/Strategy/objective/Validator/fixture/benchmark/export/DB/API/Worker/P3保持无差异。Full检查预期为142 docs、30 roots、36 Test IDs、15 OPEN、10 SIM assumptions、11 risks、37 Tasks。

Task diff必须匹配`IMPACT-POLICY/BACKEND/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`九行并为0 issues；ignored foundation/pip-audit/trace reports不进入inventory。Historical P0-08 report的`solver=NOT_INSTALLED`是冻结Task边界，不得改写为current capability；P2-03独立6-check report才是当前solver foundation machine evidence。

本地full治理PASS为142 docs/30 roots/36 tests/15 OPEN/10 SIM/11 risks/37 Tasks；Task diff报告为50 actual paths、9 matched rows、19 checks、0 issues。Exact provider artifact仍需在implementation push后复核。

Implementation artifact `9398128763`内`traceability-report.v1`精确绑定`9268b88ca7ce90a8f72023241f87e2d3676fd58a`、Diff base、50 paths、9 rows、19 checks、0 issues并PASS，因此P2-03治理Gate闭环。Evidence-only closure仍须由自身exact provider run复核，不能预写其ID。

## TASK-P2-04 formal-validator governance

P2-04在实现前固定Diff base、P0/Problem/Solution/Validation/rule/lock hashes、exact allow-list及Backend/status/expected-outcome隔离。Diff只允许formal validator/CLI、validation/property/integration tests、workflow与声明Documents；Schema/fixture/dependency/Backend/Strategy/objective/Benchmark/migration/DB/API/Worker/P3必须保持无差异。

Full治理预期保持142 docs、30 roots、36 Test IDs、15 OPEN、10 SIM assumptions、11 risks和37 Tasks。Task diff必须匹配`IMPACT-VALIDATOR/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行并为0 issues；machine report必须为6/6且覆盖13 mutations、11 C-IDs、14 hard violations和6 property examples。Ignored machine/trace/provider下载不进入inventory；actual local与provider counts在验收后回填，不能预写。

格式化后本地full治理实际PASS为142 docs/30 roots/36 Test IDs/15 OPEN/10 SIM assumptions/11 risks/37 Tasks；Task diff实际为38 paths、6 matched rows、19 checks、0 issues。Implementation artifact `9399519368`内`traceability-report.v1`精确绑定`9b532e2c054b02e1692f345a252922ec7fd469e4`与Diff base，复现38 committed/0 working paths、6 rows、19 checks、0 issues并PASS；TASK-P2-04治理Gate闭环。Evidence-only closure仍须由自身exact provider run复核，不能预写其ID。

## TASK-P2-05 governance expectations

Full治理仍须保持142 docs、30 roots、36 Test IDs、15 OPEN、10 SIM assumptions、11 risks和37 Tasks。Task diff必须只匹配`IMPACT-BACKEND/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行、覆盖Task卡exact allow-list与全部required documents并为0 issues；core machine report必须6/6并保留five-C-ID、future/objective/benchmark/production boundaries。

Problem/Policy/Solution Schema、rule sheet、formal Validator、fixtures/benchmarks、dependency/lock的immutable diff必须为空。实际paths/checks与provider IDs只在命令和exact artifact通过后回填；P2-05完成只使P2-06启动依赖满足，不构成授权。

本地实际full治理PASS为142 docs/30 roots/36 Test IDs/15 OPEN/10 SIM assumptions/11 risks/37 Tasks；TASK-P2-05 diff为49 paths、6 matched rows、19 checks、0 issues。Exact provider artifact尚待implementation提交后复验，故Task仍为`in_progress`。

Implementation artifact `9400957897`内`traceability-report.v1`精确绑定`df706786e0ec1c54bf60cd43261a92ef6aa53cc7`与Diff base `c75f7a0e96b7591ffa9220d0de942f8841283093`，复现49 committed/0 working paths、6 rows、19 checks、0 issues并PASS；TASK-P2-05治理Gate据此闭环为`done`。Evidence-only closure仍须由自身exact provider run复核，不能在本提交中预写其ID。

## TASK-P2-06 governance expectations

Full治理继续要求142 docs、30 roots、36 Test IDs、15 OPEN、10 SIM assumptions、11 risks与37 Tasks。Task diff必须只匹配`IMPACT-BACKEND/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行，覆盖exact allow-list与全部required documents且0 issues；temporal machine report必须7/7并保留four-C-ID、C-007/008、objective/benchmark/production边界。

Problem/Policy/Solution Schema、rule sheet、formal Validator、Problem builder/hash、fixtures/benchmarks及dependency/lock immutable diff必须为空。实际paths/checks和provider IDs只能在相应命令与exact artifact通过后回填；TASK-P2-06完成只满足P2-07依赖，不构成启动授权。

本地实际full治理PASS为142 docs/30 roots/36 Test IDs/15 OPEN/10 SIM assumptions/11 risks/37 Tasks；TASK-P2-06 diff为53 paths、6 matched rows、19 checks、0 issues。Immutable paths、Compose与build均PASS。

Implementation artifact `9429579311`内`traceability-report.v1`精确绑定`ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`与Diff base `c55aa294977a6cafad85741f425d46cd36e9af1a`，复现53 committed/0 working paths、6 rows、19 checks、0 issues并PASS；TASK-P2-06治理Gate据此闭环为`done`。Evidence-only closure仍须由自身exact provider run复核，不能在本提交中预写其ID。

## TASK-P2-07 governance expectations

Full治理继续要求142 docs、30 roots、36 Test IDs、15 OPEN、10 SIM assumptions、11 risks与37 Tasks。Task diff必须匹配`IMPACT-BACKEND/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行，覆盖冻结allow-list与全部required documents且0 issues；fact-lock machine report必须7/7并保持Schema/rule/Validator/Builder/hash/ADR/dependency fingerprints。

Diff base固定为`33cc3282ead23a4cc1bb214190191e116b095119`；activation commit也属于完整Task range。最终local path/check/issue counts只由`TASK-P2-07-report.json`回填，provider artifact还必须对exact implementation SHA复现相同结果；不得预写run/artifact或把local PASS当Task closure。

本地实际full治理PASS为142 docs/30 roots/36 Test IDs/15 OPEN/10 SIM assumptions/11 risks/37 Tasks；TASK-P2-07完整range为54 paths、6 matched rows、19 checks、0 issues。Immutable paths、Compose、build与`git diff --check`均PASS；exact provider artifact尚待实现提交后复现。

Implementation artifact `9430579117`内`traceability-report.v1`精确绑定`5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`与Diff base `33cc3282ead23a4cc1bb214190191e116b095119`，复现54 committed/0 working paths、6 rows、19 checks、0 issues并PASS；TASK-P2-07治理Gate据此闭环为`done`。Evidence-only closure仍须由自身exact provider run复核，不能在本提交中预写其ID。

## TASK-P2-08 governance handoff

Task以`9c55df993b12ae0bdd3d4d38c900d601324c05d2`为immutable Diff base；activation-only提交`f6c7871`先以8 paths/`IMPACT-PHASE`+`IMPACT-DOCS`通过检查，再在首个业务文件前把卡片声明切换为实现预期的Policy/Strategy/Backend/Tests/Infra/Phase/Governance/Docs八行。最终必须以`Diff base..HEAD`+working tree并集重新计算真实paths/rows，不能沿用activation报告。

新增Python/CI/ignored JSON不增加Markdown inventory；本地最终为142 docs、30 roots、36 Test IDs、15 OPEN、10 SIM assumptions、11 risks、37 Tasks，完整range为52 paths、8 matched rows、19 checks、0 issues。Exact implementation SHA provider artifact必须包含`ci-objective-strategy.json`与`ci-current-task-report.json`；未push前不得预填run/job/artifact。

Implementation artifact `9431673977`内`traceability-report.v1`精确绑定`b1ec83ed96120357ecadd41d3f520181838f17c6`与Diff base `9c55df993b12ae0bdd3d4d38c900d601324c05d2`，复现52 committed/0 working paths、8 rows、19 checks、0 issues并PASS；TASK-P2-08治理Gate据此闭环为`done`。Closure提交仍须由自身exact provider run复核，不能在本提交预写其ID。

## TASK-P2-09 governance application

Diff base固定为`15c298f343a47db2a922544944ff5e02e4ca72d9`；范围检查必须联合activation/implementation commits与working tree，命中`IMPACT-SIM-SCENARIO/FIXTURE/TESTS/INFRA/PHASE/GOVERNANCE-REGISTRY/DOCS`。Task卡在首个asset前已展开全部路径；Schema、Planning/Application/Generator、dependency/lock、migration、Benchmark/Reference/Export与P3禁止路径应为零差异。

本Task不新增`docs/**/*.md`，文档inventory仍为142；roots=30、Test IDs=36、OPEN=15、risks=11、Tasks=37保持不变，新增SIM-ASSUMPTION-011使active Simulation assumptions=11。本地`traceability-report.v1`为58 paths/7 rows/19 checks/0 issues并PASS；provider报告须把58 committed/0 working paths绑定implementation SHA，未push前不得预填run/job/artifact。

Implementation artifact `9432982306`内`traceability-report.v1`精确绑定`20e49c92306128b47313059fabe31534814dbe3d`与Diff base `15c298f343a47db2a922544944ff5e02e4ca72d9`，复现58 committed/0 working paths、7 rows、19 checks、0 issues并PASS；TASK-P2-09治理Gate据此闭环为`done`。Closure提交仍须由自身exact provider复核。

## TASK-P2-10 governance application

Diff base固定为`0e4f6630412889254a7bef41f487c24dc274ca9c`；范围检查必须联合activation/implementation commits与working tree，命中`IMPACT-REFERENCE-SCHEDULER/TESTS/INFRA/PHASE/GOVERNANCE-REGISTRY/DOCS`。Task卡已在首个baseline文件前冻结全部实现、测试、CI和文档路径；Schema、Planning/Validator/P2-09 assets、dependency/lock、Benchmark/Export/API/DB/Worker及P3禁止路径必须为零差异。

本Task不新增`docs/**/*.md`，inventory仍为142；roots=30、Test IDs=36、OPEN=15、risks=11、Tasks=37不变，新增SIM-ASSUMPTION-012使active Simulation assumptions=12。本地`traceability-report.v1`为38 paths/6 matched rows/19 checks/0 issues并PASS；提交前source counts为8 committed-range与38 working-tree paths（union仍为38）。

Implementation artifact `9435264655`内`traceability-report.v1`精确绑定`8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`与Diff base `0e4f6630412889254a7bef41f487c24dc274ca9c`，复现38 committed/0 working paths、6 rows、19 checks、0 issues并PASS；TASK-P2-10治理Gate据此闭环为`done`。Closure提交仍须由自身exact provider复核。

## TASK-P2-11 governance application

Diff base固定为`41e958b771f2664b1ac50867903a30b73627878d`；完整activation/implementation范围必须命中`IMPACT-SCHEMA/REPORTING/EXPORT/STATE/TESTS/INFRA/DEPENDENCY/VERSION-METADATA/PHASE/GOVERNANCE-REGISTRY/DOCS`。`pyproject.toml`仅提升schema metadata，runtime/dev dependency和`uv.lock`不得变化；State行只审查并声明无transition/persistence，不能把文档更新解释为状态实现。

本Task不新增、删除或重命名`docs/**/*.md`，inventory继续为142；roots=30、Test IDs=36、OPEN=15、SIM assumptions=12、risks=11、Tasks=37，所有registry format version保持`1.0.0`。本地Task diff已覆盖58 paths、11个真实Impact rows、19项governance checks且0 issues；implementation提交后provider artifact还必须复现58 committed/0 working paths。

Implementation artifact `9436863185`内`traceability-report.v1`精确绑定`546292831c3bd52185687a4c646c10ae10541ae2`与Diff base `41e958b771f2664b1ac50867903a30b73627878d`，复现58 committed/0 working paths、11 rows、19 checks、0 issues并PASS；TASK-P2-11治理Gate据此闭环为`done`。Closure提交仍须由自身exact provider复核，不在本提交预写其ID。

## TASK-P2-12 governance application

Diff base固定为`58db14e8f18fb50866fb757d4c89e76fef1141f1`；完整范围必须命中`IMPACT-BENCHMARK/REPORTING/TESTS/INFRA/PHASE/GOVERNANCE-REGISTRY/DOCS`。Benchmark内部合同不提升schema set；Planning/Strategy/Backend/Validator/Reference/Exporter/dependency/lock和P2-09 assets必须零差异。

本Task不新增Markdown，inventory继续142；roots=30、Test IDs=36、OPEN=15、risks=11、Tasks=37，SIM assumptions=13，所有registry format version保持`1.0.0`。本地full/diff治理实际记录49 paths、七个Impact rows、19 checks和0 issues并PASS；implementation provider artifact形成前不得预写其SHA/run/artifact或关闭Task。

Implementation artifact `9438899443`内`traceability-report.v1`精确绑定`01e7f4bdca88fc903e7caa771f875fc1a70ff357`与Diff base `58db14e8f18fb50866fb757d4c89e76fef1141f1`，复现49 committed/0 working paths、7 rows、19 checks、0 issues并PASS；TASK-P2-12治理Gate据此闭环为`done`。Closure提交仍须由自身exact provider复核，不在本提交预写其ID。

## TASK-P2-13 governance application

Diff base固定为`59f3b013a4be7bd11d054e8464886b3cde791602`；完整activation/implementation范围必须命中`IMPACT-APPLICATION/TESTS/INFRA/PHASE/GOVERNANCE-REGISTRY/DOCS`。新增Gate实现、三份测试文件（含既有application boundary精确例外）、workflow及全部治理文档都必须显式列入Task allow-list；Schema/migration/dependency/lock/ADR、Planning/Strategy/Backend/Validator/Reference/Scenario/Benchmark/Exporter实现及P2-14/P3必须零差异。

本Task不新增Markdown，inventory继续142；roots=30、Test IDs=36、OPEN=15、SIM assumptions=13、risks=11、Tasks=37，所有registry format version保持`1.0.0`。本地full/diff治理及最终path/count/check/issue须在完整验收后记录；implementation provider artifact形成前不得预写其SHA/run/artifact或关闭Task。

本地full治理实际为142 docs、30 roots/trace rows、36 Test IDs、15 OPEN、13 SIM assumptions、11 risks、37 Tasks并PASS；Task diff实际为37 paths（8 committed-range、37 working-tree union）、六个Impact rows、19 checks、0 issues并PASS。`git diff --check`退出0，仅报告Windows工作区预期的LF→CRLF提示；exact implementation provider形成前TASK-P2-13继续`in_progress`。

Implementation artifact `9440650646`内`traceability-report.v1`精确绑定`dc2e5cd41080603606090ebfc4bc6162941c5f7f`与Diff base `59f3b013a4be7bd11d054e8464886b3cde791602`，复现37 committed/0 working paths、6 rows、19 checks、0 issues并PASS；TASK-P2-13治理Gate据此闭环为`done`。本evidence-only closure仍须由自身exact provider复核，不在提交前预写其ID。

## TASK-P2-14 audit governance application

Diff base固定为`e76776d83726d13600d8ea29fd490474c8e32604`；完整范围只允许audit report/JSON manifest、phase/milestone/task/contract/planning/quality/governance文档及ignored `TASK-P2-14-*` reports，必须命中`IMPACT-PHASE/GOVERNANCE-REGISTRY/DOCS`三行。业务代码、Schema、fixture、benchmark、scripts、workflow、dependency/lock、migration与P3必须零差异。

Activation provider `32675914600` / artifact `9502674319`已对8 paths/2 rows/0 issues闭环。写回前full治理为143 docs、30 roots、36 tests、15 OPEN、13 SIM assumptions、11 risks与37 Tasks；activation-range diff为8 paths/2 rows/19 checks/0 issues。Audit decision写回后再次生成最终`TASK-P2-14-report.json`：full治理保持143/30/36/15/13/11/37，Task diff为30 paths、3 rows、19 checks、0 issues并PASS。Implementation provider run `32677741558` / artifact `9503227240`精确复现30 committed/0 working paths及相同治理结果，因此Task治理闭环为`done`；本evidence-only closure仍须在push后外部复核。

## TASK-P3-00 governance application

P3首次规划batch以`80c403384d1e171258cf874d26605d0d22aff1b2`为不可变Diff base。唯一owner必须是`TASK-P3-00`、role=`phase-planning-owner`且`in_progress`；P3-01～15必须同range新建、role=`phase-plan-member`、`planned`且无implementation SHA。P0～P2卡保持terminal，P4+不得创建详细卡。

本batch新增16份Markdown，inventory预期从143增至159；Task总数从37增至53，Test IDs从36增至48，风险从11增至13，roots=30、OPEN=15、SIM assumptions=13不变。完整治理和current Task diff必须实际核对这些计数、4条Impact Rule、changed paths、19项或当时完整checks与issues；provider artifact形成前不得预填PASS或关闭owner。

实际full governance与implementation provider均确认159/30/48/15/13/13/53计数；artifact `9504310381`中的`traceability-report.v1`精确绑定implementation SHA，记录64 committed/0 working paths、4 rows、19/19 checks与0 issues。因此P3-00治理Gate闭环；本evidence-only closure自身仍须push后复核。

## TASK-P3-01 governance application

不可变Diff base为`7f65f88b620ea1e8d2f4693911be3b52f4052d5d`。本Task新增三份Frontend规范、两份contract和ADR-0012，因此`docs/**/*.md`预期由159增至165；Task数53、roots 30、Test IDs 48、OPEN 15、SIM assumptions 13、risks 13和所有registry format version保持。Inventory必须逐项登记6个新path/Doc ID/status/title，且Frontend index从planned转为baseline。

完整range只允许Task卡逐字列出的docs路径，命中`IMPACT-STATE/PHASE/GOVERNANCE-REGISTRY/DOCS`。`backend/**`、`schemas/**`、`frontend/**`、migrations、`.github/workflows/**`、`pyproject.toml`和`uv.lock`相对Diff base零变化；P2 historical docs/artifacts未改写。Full治理实际为165/30/48/15/13/13/53；implementation artifact `9505303054`中的`traceability-report.v1`精确绑定`3bf99cbafdad983795a83a88646240dbb0b24509`与Diff base，记录43 committed/0 working paths、4 rows、19/19 checks与0 issues。因此TASK-P3-01治理Gate闭环；本evidence-only closure自身仍须push后复核。
## TASK-P3-02 documentation and diff governance

本Task exact Diff base=`a8fcec3383ea0f8d9dca4101056aff37d7eea08c`。Diff治理必须识别10行Impact Rule：SCHEMA、DOMAIN、STATE、INFRA、DEPENDENCY、VERSION-METADATA、TESTS、PHASE、GOVERNANCE-REGISTRY、DOCS；逐字允许七Schema/七sample、data dictionary、两个domain模块、六个测试文件、metadata/workflow与本卡列出的文档。`uv.lock`、34份P2 Schema/sample、三份规则表、migration/application/API/jobs/exporters/frontend与later-phase roots必须零差异。

Full docs、Task diff report、`git diff --check`与forbidden-root checks须在implementation和evidence-only closure各自运行；Task report必须绑定exact SHA/Impact rows/checks/issues。Provider artifact内workspace machine report和Task report任一Task/SHA/count/issue不一致即保持`in_progress`并阻止TASK-P3-03。

Implementation artifact `9506913562`中的`traceability-report.v1`精确绑定`aff27d3d6b63fb9f216c9a2687408a6c676fa96a`与Diff base，复现165/30/48/15/13/13/53治理计数、65 committed/0 working paths、10 rows、19/19 checks和0 issues。因此TASK-P3-02治理Gate闭环；本evidence-only closure自身仍须push后复核，P3-03保持`planned`。

## TASK-P3-03 diff governance

不可变Diff base=`9621fda535f66393beab88efc13c100fc805c993`。完整union只能命中`IMPACT-DOMAIN/STATE/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`七行；Task卡逐字冻结migration、四repository、shared/machine modules、两个state modules、四个test/CI文件和全部required docs。Schema/sample/rules、Planning/Solver/Validator、application/API/jobs/exporters/frontend、dependency/lock、fixture/benchmark与P4路径必须零差异。

Full docs、Task diff、`git diff --check`、forbidden-root与machine report必须在implementation和closure各运行一次。Provider artifact必须精确绑定Task/SHA/Diff base、7 rows、full check set和0 issues；在provider形成前P3-03保持`in_progress`且P3-04不得启动。

Implementation artifact `9508445635`中的`traceability-report.v1`精确绑定`e315dbf4f6c079df6d19b52f0403b00827126232`与Diff base，复现165/30/48/15/13/13/53治理计数、52 committed/0 working paths、7 rows、19/19 checks和0 issues。因此TASK-P3-03治理Gate闭环；本evidence-only closure自身仍须push后复核，P3-04保持`planned`。

## TASK-P3-04 diff governance

不可变Diff base=`62604d05964413a0aa7f763afd720afa2d53a887`。完整union只能命中`IMPACT-DOMAIN/APPLICATION/STATE/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`八行；Task卡逐字冻结两个domain/application模块与`__init__`、machine CLI、限定contract/integration/CI tests、单一workflow command和全部required docs。Schema/sample/rules、migration/repository primitive、Planning/Solver/Validator公式、P2 fixture/baseline/export bytes、dependency/lock、API/jobs/exporters/frontend与P4路径必须零差异。

Full docs、Task diff、`git diff --check`、forbidden-root、machine report与全部local validation须在implementation和closure各运行。当前full治理实际为165 docs、30 roots/trace rows、48 Test IDs、15 OPEN、13 SIM assumptions、13 risks、53 Tasks；implementation artifact `9510215582`中的`traceability-report.v1`精确绑定`a9be974855bb825784d639b7f6675e5a33e4273d`与Diff base，复现45 committed/0 working paths、8 rows、19/19 checks和0 issues。因此TASK-P3-04治理Gate闭环；本evidence-only closure自身仍须push后复核，P3-05保持`planned`。

## TASK-P3-05 diff governance

不可变Diff base=`fc5011f78a242160097521259a1914d864d9ad17`。完整union只能命中`IMPACT-DOMAIN/APPLICATION/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`七行；allow-list逐字冻结pure domain、两个read service、machine CLI、四类测试、既有CI contract、单一workflow step及所有required docs。Schema/sample/rules、migration/dependency/lock、repository write语义、Planning/Solver/Validator/Exporter、API/Frontend、state pair和P4路径必须零差异。

Implementation/closure均须通过full docs、Task diff、`git diff --check`、forbidden path、8/8 report、定向与full repository检查；provider artifact必须精确绑定Task/SHA/Diff base、7 rows、全部checks与0 issues。Provider形成前保持`in_progress`，且TASK-P3-06不得自动启动。

Implementation artifact `9512423712`中的`traceability-report.v1`精确绑定`f236fab47aa2565b87a060b2c8bde8f2e8d66229`与Diff base，复现165/30/48/15/13/13/53治理计数、50 committed/0 working paths、7 rows、19/19 checks和0 issues。因此TASK-P3-05治理Gate闭环；本evidence-only closure自身仍须push后复核，P3-06保持`planned`。

## TASK-P3-06 diff governance

不可变Diff base=`67d38d030f8b129de7f1b2f6e5b75bd706655396`。完整union只能命中`IMPACT-DOMAIN/APPLICATION/STATE/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`八行；allow-list逐字冻结pure command domain、application service/machine CLI、五类tests、既有CI contract、单一workflow step及所有required docs。Schema/sample/rules、migration/dependency/lock、PlanningProblem/Snapshot/Validator/Backend/Strategy/Reporting、API/Frontend、publication/export和P4路径必须零差异。

Implementation/closure均须通过full docs、Task diff、`git diff --check`、forbidden path、8/8 report、focused/full repository、Ruff/Pyright/locked sync、Compose/build及全部历史machine checks；provider artifact必须精确绑定Task/SHA/Diff base、8 rows、全部checks与0 issues。Provider形成前Task保持`in_progress`，TASK-P3-07不得自动启动。

当前本地full docs计数为165/30 roots/30 trace rows/48 tests/15 OPEN/13 SIM/13 risks/53 tasks；提交前Task diff为57 working paths、8 rows、19 checks、0 issues。Implementation artifact `9515126567`中的`traceability-report.v1`精确绑定`08317637c7fbb51d46880d32523545bb0b4fe1c0`与Diff base，复现57 committed/0 working paths、8 rows、19/19 checks和0 issues。因此TASK-P3-06治理Gate闭环；本evidence-only closure自身仍须push后复核，P3-07保持`planned`。

## TASK-P3-07 diff governance

不可变Diff base=`514224b8ff2d507b613797ae697245bab14f79eb`。完整union只能命中`IMPACT-DOMAIN/APPLICATION/STATE/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`八行；allow-list逐字冻结pure authorization domain、approval application/machine CLI、unit/contract/integration/security与CI contract tests、单一workflow step及所有required docs。Schema/sample/rules、migration/dependency/lock、infrastructure repository semantics、PlanningProblem/Snapshot/Solver/Validator/Backend/Strategy/Reporting、API/Frontend、publication/export和P4路径必须零差异。

Implementation/closure均须通过full docs、Task diff、`git diff --check`、forbidden path、8/8 report、focused/full repository、Ruff/Pyright/locked sync、Compose/build及全部历史machine checks；provider artifact必须精确绑定Task/SHA/Diff base、8 rows、全部checks与0 issues。Corrective artifact `9544333991`中的Task report已绑定`9aed9d8c5dd86a9a9b972f8e9c5491fd6d2dbaa6`与不可变Diff base，复现165 docs/30 roots/30 trace rows/48 tests/15 OPEN/13 SIM/13 risks/53 tasks、50 committed/0 working paths、8 rows、19 checks、0 issues。本closure只写provider事实并不得启动TASK-P3-08；closure自身仍须exact provider。

## TASK-P3-08 diff governance

不可变Diff base=`a53c0f7d4a0f0bcd4e02bfeaaa0f6fc4b93157b9`。完整union只能命中`IMPACT-DOMAIN/APPLICATION/STATE/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`八行；allow-list逐字冻结publication domain/application/machine CLI、unit/contract/integration/security与CI contract tests、单一workflow step及required docs。Schema/sample/rules、migration/dependency/lock、infrastructure repository semantics、Planning/Solver/Validator、API/Frontend、Exporter/ExportJob和P4路径必须零差异。

Implementation/closure均须通过full docs、Task diff、`git diff --check`、forbidden path、8/8 publication report、focused/full repository、Ruff/Pyright/locked sync、Compose/build及全部历史machine checks；provider artifact必须绑定Task/SHA/Diff base、8 rows、checks与0 issues。Implementation artifact `9545782727`中的Task report已绑定`e90475f462b365d2e031445ad28a02ea0b89d2f5`与不可变Diff base，复现165 docs/30 roots/30 trace rows/48 tests/15 OPEN/13 SIM/13 risks/53 tasks、51 committed/0 working paths、8 rows、19 checks、0 issues。本closure只写provider事实并不得启动TASK-P3-09；closure自身仍须exact provider。

提交前实际Task diff为51 working paths、上述8 rows、19/19 checks、0 issues；full docs为165 docs/30 roots/30 trace rows/48 Test IDs/15 OPEN/13 SIM assumptions/13 risks/53 Tasks，禁止路径零差异。

TASK-P3-09治理验证13个Impact rows、Diff base `b9c0b1694448a4ec348b0b02107926f6213560c9`、新增2 Schema/2 sample及全部精确allow-list；四份v1 hash、`uv.lock`、migration、publication service、P2 package、API/frontend/P4/external路径保持冻结。Full docs/Task diff、16 focused/594 full、Ruff/Pyright/locked sync、27份machine reports、P2 Gate、XS benchmark、Compose/build与`git diff --check`均PASS；implementation artifact `9548027237`中的Task report绑定exact SHA/Diff base并复现165 docs/30 roots/30 trace rows/48 tests/15 OPEN/13 SIM/13 risks/53 tasks、76 committed/0 working paths、13 rows、19 checks、0 issues。本closure只写provider事实并不得启动TASK-P3-10；closure自身仍须exact provider。

## TASK-P3-10 diff governance

不可变Diff base=`f71c4a5a11a3fac0e203e2e92198c26124755927`。完整union只允许命中`IMPACT-API/STATE/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`七行；精确allow-list仅包含API composition/contracts/auth/router/machine check、三类API tests、既有health/CI contract、单一workflow step与Task卡逐字列出的文档。Schema/sample/rules、migration、dependency/lock、domain/application/repository/exporter/job、Frontend/P4/external路径保持冻结。

本地API report为8/8、`issues=[]`，focused为41 PASS、最终full为603 PASS，required当前29份JSON evidence、Compose/build与full docs均PASS。Implementation artifact `9550224090`中的Task report绑定exact SHA/Diff base并复现165 docs/30 roots/30 trace rows/48 tests/15 OPEN/13 SIM/13 risks/53 tasks、51 committed/0 working paths、7 rows、19 checks、0 issues；29/29 JSON与API 8/8均PASS。本closure只写provider事实并不得启动TASK-P3-11；closure自身仍须exact provider，P4与Production均不在本Diff内。

## TASK-P3-11 diff governance

不可变Diff base=`26dd519b1f1f84e08d415cfdfce43f286fa82988`。完整union只允许命中`IMPACT-FRONTEND/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行；精确allow-list只包含Task卡列出的Frontend foundation/read-only模块、单一required workflow、read-only CI contract及逐字治理文档。Schema/sample/rules、migration、Python dependency/lock、Backend business/API semantics、P3-12+、P4与Production路径必须冻结。

Full docs与Task diff检查必须逐字验证Node/npm/24个direct pins/lockfile v3、SCA/license命令、13个route、七类状态和禁止模块。typescript-eslint的用户批准被编码为exact gate：`8.68.0`配`eslint 10.9.1`和`typescript 6.0.3`，TypeScript peer为`>=4.8.4 <6.1.0`；range、drift、peer conflict或未审查升级均为issue。Activation提交只证明计划边界，不能预填implementation/provider PASS。

提交前working Task diff为74 paths、六行、19/19 checks、0 issue；full governance为165 docs/30 roots/30 trace rows/48 Test IDs/15 OPEN/13 SIM assumptions/13 risks/53 Tasks。Frontend machine报告为9/9、24 direct pins、13 routes、7 states、23 source files和0 boundary issue，SCA/license均顶层PASS；Frontend 25 tests、CI contract 28项、Python全仓604项、全部历史machine/P2 Gate/XS、Compose及build均已重跑通过。

Implementation artifact `9552386549`中的Task report绑定`567e8693db881ea3dfffa011de9021fef9641361`与不可变Diff base，复现165 docs/30 roots/30 trace rows/48 tests/15 OPEN/13 SIM/13 risks/53 tasks、74 committed/0 working paths、6 rows、19 checks、0 issues；32/32 JSON和Frontend/SCA/license均PASS。本closure只写provider事实并不得启动TASK-P3-12；closure自身仍须exact provider，P4与Production均不在本Diff内。

## TASK-P3-12 diff governance

不可变Diff base=`3bca1cc10ebedc4d47227bafb2f3f66854ccb526`。完整union只允许命中`IMPACT-FRONTEND/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行；精确allow-list仅包含Task卡列出的visualization API/client/routes/features/styles/tests、read-only Playwright/config、单一required workflow、单个CI contract test与逐字治理文档。Schema/sample/rules、migration/database、Python dependency/lock、Frontend lock/pins、Backend business/API semantics、state machine、P2 bytes、actions、P4与Production路径必须冻结。

Full docs与Task diff必须复验165 docs/30 roots/30 trace rows/48 Test IDs/15 OPEN/14 SIM assumptions/13 risks/53 Tasks，SIM-ASSUMPTION-014仅绑定versioned 120-row UI fixture。Frontend machine必须为12/12、18 routes、4/4 browser、120/24 render、24 pins/lock无漂移和0 issues；Task report必须绑定exact SHA/base、六行、全部checks和0 issues。Impact review还逐项确认state/replanning/Validator/Task Template/ADR无语义变化并保持零diff。

Local full governance为165 docs/30 roots/30 trace rows/48 Test IDs/15 OPEN/14 SIM/13 risks/53 Tasks，Task diff为55 working paths、6 Impact rows、19 checks、0 issues；604 Python tests、37 Frontend tests、4/4 Chromium、32/32 validation JSON、XS/P2 Gate、Ruff/Pyright/locked sync、SCA/license、Compose与build均PASS。Implementation artifact `9555196470`中的Task report精确绑定`a719fe5bf2c2ea2d59e1582e8f4dfd3f2674ac69`与不可变Diff base，复现55 committed/0 working paths、6 rows、19 checks、0 issues；33/33 JSON、Frontend与Playwright均PASS，故TASK-P3-12可由本closure标为`done`。Closure自身仍须exact provider，且不得自动启动P3-13、P4或Production。
