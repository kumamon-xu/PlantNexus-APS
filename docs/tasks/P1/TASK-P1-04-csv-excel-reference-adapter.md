---
doc_id: TASK-P1-04
title: CSV Excel and Formal Reference Adapter
status: done
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [3, 11, 15, 63, 73, 91, 95]
last_reviewed: 2026-08-19
---

# TASK-P1-04 — CSV, Excel, and Formal Reference Adapter

Requirement IDs: REQ-001, REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-SEC-001, NFR-REL-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-02, TASK-P1-03

Goal: 实现安全的 CSV 与 XLSX 读取，以及一个版本化 `ReferenceFileAdapter v1`，把两种文件格式转换为相同 Raw Staging contract；该 Adapter 是正式可测试的参考 Adapter，不声称已绑定任何真实 ERP/MES/WMS/CAM。

Inputs: canonical import v2、Raw Staging protocol、OPEN-002/013/015、文件导入安全规则。

Diff base: 6c259e172be4bf3cde72a56212df3a1bad427372

Files allowed to change: `backend/app/importers/adapter.py`、`backend/app/importers/csv_reader.py`、`backend/app/importers/excel_reader.py`、`backend/app/importers/reference_file_adapter.py`、`backend/app/importers/__init__.py`、`backend/app/infrastructure/contract_check.py`、`backend/tests/contract/test_input_adapters.py`、`backend/tests/integration/test_reference_file_adapter.py`、`backend/tests/integration/test_ci_contract.py`、`pyproject.toml`、`uv.lock`、生成但不提交的 `build/traceability/TASK-P1-04-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: canonical Schema、Raw Staging migration/repository、normalization/data validation/order expansion、Snapshot/Problem、Simulation Generator、API、Solver、真实客户文件、Production credentials。

Implementation steps: 定义 adapter protocol/version/capability与 source manifest；CSV 使用显式 UTF-8/dialect/header规则，XLSX 使用 exact-pinned openpyxl并只读数据；限制扩展名/大小/sheet/row/column，拒绝 XLS/XLSM、macro、公式、外部链接、重复/未知列和路径穿越；两种格式只产出相同 staged rows/source locations，字段语义留给后续 Normalization；同步既有engineering machine contract与CI dependency assertion的exact runtime pin集合，但不放宽solver-free断言。

Outputs: CSV reader、XLSX reader、ReferenceFileAdapter v1、locked dependency、正反 contract/integration evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/README.md`、`docs/contracts/schema-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/data-authority.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/domain/error-model.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/governance/prod-open-register.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/benchmark-regression.md`、`docs/planning/solver-backend-contract.md`、`docs/adr/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-04-csv-excel-reference-adapter.md`。

Documentation impact rationale: 新增外部文件边界、runtime dependency、Adapter version与拒绝行为，必须同步安全、技术栈、数据权威和测试合同。

Change-impact matrix rows reviewed: `IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/009、NFR-TRC/SEC/REL、ENG-ARCH/ERR/VER → TASK-P1-04 → TEST-IMPORT-ADAPTER-001 → CSV/XLSX/reference-adapter contract tests、lock与 staged provenance。

Schema changes: none；Adapter manifest/version使用 P1-02 已发布合同。

Migration: none。

Error behavior: 不支持格式、超限、编码/header/sheet错误、formula/macro/external-link、重复/未知字段均形成结构化 DATA_ERROR与 source location；不执行内容、不拼 shell/SQL、不静默取公式缓存值。

Tests: `TEST-IMPORT-ADAPTER-001`；CSV/XLSX semantic parity、version rejection、file hash/source location、limits、malicious/formula/macro/external-link、unknown/missing/duplicate headers、idempotent restaging。

Benchmark impact: 记录小型 synthetic 文件 parse 行数/耗时，仅作回归；不设生产吞吐承诺，dependency 变化不触发 Solver benchmark。

Simulation scenarios: 测试文件仅在临时目录生成并标记 synthetic；不提交真实数据、不修改正式 Scenario。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/importers backend/app/infrastructure/contract_check.py backend/tests/contract/test_input_adapters.py backend/tests/integration/test_reference_file_adapter.py backend/tests/integration/test_ci_contract.py`；`uv run pyright backend/app/importers backend/app/infrastructure/contract_check.py backend/tests/contract/test_input_adapters.py backend/tests/integration/test_reference_file_adapter.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/contract/test_input_adapters.py backend/tests/integration/test_reference_file_adapter.py backend/tests/integration/test_ci_contract.py backend/tests/integration/test_migrations_and_infrastructure.py`；`uv run pytest -q`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-04-csv-excel-reference-adapter.md --check-diff --report build/traceability/TASK-P1-04-report.json`；`git diff --check`；`uv build`。

Artifacts: exact dependency lock、adapter contract results、traceability report；不提交输入 workbook/credentials。

Completion conditions: CSV/XLSX 对等输入产生相同 staged semantic rows与 provenance；全部恶意/越界路径明确拒绝；ReferenceFileAdapter version固定且明确 non-production binding；lock、tests、docs/diff governance PASS。

Explicitly excluded: 真实 ERP/MES/WMS/CAM Adapter、业务字段权威决定、Normalization/Snapshot/Problem、宏/公式执行、API、Solver。

PROD_OPEN: OPEN-002/013/015 保持 OPEN；ReferenceFileAdapter 不能关闭真实接口/单位/字段权威问题。

SIM_ASSUMPTIONS: 测试表格只表达 synthetic contract样例，不新增生产参数。

Rollback: 移除 reference adapter与 pinned dependency并保留 staged records/audit；不得把旧 workbook按另一版本静默重解释。

## Completion evidence

2026-08-19按用户指令启动。启动时HEAD与`origin/main`均为`6c259e172be4bf3cde72a56212df3a1bad427372`、working tree clean、TASK-P1-02/03均为`done`且P1-03最终provider replay成功，因此该SHA固定为不可变Diff base。已完整读取Agent规则、current phase/Task、Import v2/Raw Staging合同、OPEN-002/013/015、安全/ADR、总规、相邻Normalization Task及相关代码/测试；不进入TASK-P1-05/P2。

Scope治理真实经历三次fail-closed修正：启动前影响矩阵发现5份phase/governance必审文档遗漏，先补卡再激活；首次actual diff检查发现`pyproject.toml`同时命中`IMPACT-VERSION-METADATA`，先加入`schema-versioning.md`；首次全仓回归随后以2个真实失败暴露P0 engineering exact dependency集合过期，因修复需要原卡外`infrastructure/contract_check.py`与`test_ci_contract.py`，再次先扩卡并加入`IMPACT-INFRA`、configuration/Operations文档。最终没有删除、skip或放宽exact dependency/solver-free断言。

Implementation candidate共42个changed paths（committed range=0、working tree=42）：31份声明文档全部实际更新；其余为5份Importer文件、1份既有engineering machine contract、2份新Adapter tests、1份既有CI dependency test及`pyproject.toml/uv.lock`。`plantnexus.reference-file@1.0.0`/`raw-staging.v1`明确`production_binding=false`，三列contract固定为`record_type,source_record_id,payload_json`和XLSX sheet=`records`。CSV/XLSX等价输入产生相同stable row identity/raw payload和caller source/version/data-plane/synthetic provenance；实际file SHA-256、leaf name/media/length和format-specific location忠实保留差异，不伪造“相同文件 provenance”。`payload_json`保持opaque，不解析mapping/unit/time。

安全矩阵固定4 MiB file、10000 rows、3 columns、262144 cell characters、1 sheet、512 ZIP members和32 MiB expansion limits；拒绝absolute/`..`/resolved escape、missing/non-file、`.xls/.xlsm/unknown`、UTF-8 BOM/invalid encoding/malformed CSV、unknown/missing/duplicate/reordered header、duplicate record/control text、non-text cell、formula-like content、VBA、external member/relationship、DTD/entity、unsafe/duplicate/encrypted/over-limit archive。所有错误为sanitized module-local`DATA_ERROR`，不包含raw cell/payload/absolute path/parser exception，不执行macro/formula、SQL或shell。

Dependency/lock证据：exact direct pins新增`openpyxl==3.1.5`与`defusedxml==0.7.1`，lock新增transitive`et-xmlfile==2.0.0`，总解析图61 packages；contract test确认openpyxl实际版本且`DEFUSEDXML=true`。OR-Tools仍不在`pyproject.toml`/lock，engineering machine report与CI assertion的exact集合已同步且solver-free断言保持。

本地最终Acceptance真实结果：`uv sync --locked` exit 0（61 packages）；Task范围Ruff exit 0；Pyright 0 errors/0 warnings；Adapter自身contract/integration 31 passed，卡片focused四文件suite 42 passed in 1.58s；full repository 152 passed in 2.79s；full/diff docs exit 0（124 docs、30 roots、36 Test IDs、15 OPEN、9 SIM、10 risks、22 Tasks；42 paths/8 impact rows/0 issues）；`git diff --check` exit 0，仅有Windows LF→CRLF提示；`uv build`成功生成`plantnexus_aps-0.0.0` sdist/wheel。额外全仓Ruff/Pyright同样PASS。`build/traceability/TASK-P1-04-report.json`是ignored machine artifact，不提交。

实际更新文档为Task声明的31份：current phase；3份contracts；5份architecture；error model；Operations index/security；9份governance registries/rules/inventory；3份quality；Solver contract；ADR index；2份Milestone；Task index/template/card。没有新增Markdown路径，inventory仍124。追踪已更新为REQ-001/009、NFR-TRC/SEC/REL、ENG-ARCH/ERR/VER→TASK-P1-04→TEST-IMPORT-ADAPTER-001→adapter/readers/lock/contract+integration tests；实际impact rows为`IMPACT-DOCS/GOVERNANCE-REGISTRY/IMPORT/INFRA/DEPENDENCY/VERSION-METADATA/PHASE/TESTS`。

Schema set保持`2.0.0`，无Schema/migration/ADR/正式Scenario/Fixture；全部OPEN仍OPEN，尤其OPEN-002/013/015未关闭；SIM-ASSUMPTION-001～009不变。31项Adapter tests的2-row files全部在pytest temporary directory生成，不提交workbook/真实客户数据/credential，不构成Benchmark/Production throughput/security certification。malware/quarantine/auth/RBAC/encryption/retention、真实system binding、Normalization/DataValidation/canonical Import、Snapshot/Problem/API/Worker/Solver/P2继续`PLANNED`。

本地实现已满足可在提交前验证的Completion conditions。Rollback为移除Reference Adapter与exact dependencies并同步exact machine contract；无DB migration，既有Raw Staging audit不得被无审计删除，旧文件不得按其他adapter version静默重解释。

Implementation commit=`9391ec021afa9e6f4f881b1538b276c84584df0e`（42 paths、1883 insertions/28 deletions）。提交后full/diff governance再次PASS：committed range=42、working tree=0、8 impact rows、0 issues，working tree clean。直接push`main`时GitHub提示required `validate`尚待运行并发生rule bypass，该提示未计为PASS。

真实provider closure：GitHub repository=`kumamon-xu/PlantNexus-APS`、branch=`main`、workflow=`PlantNexus repository gates`；run [`32247079996`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32247079996)，event=`push`、attempt=1、head SHA=`9391ec021afa9e6f4f881b1538b276c84584df0e`、status=`completed`、conclusion=`success`。Job `validate` ID=`96049843226`为success，checkout/setup/sync/lint/type/tests/五类contracts/Compose/docs+Task diff/Benchmark deferred hook/build/upload及post steps全部success。Artifact ID=`9362999088`、name=`plantnexus-ci-evidence-32247079996`、size=6288 bytes、digest=`sha256:b9ada0b25d12962f5efea51e058cd82778495f4389a240e32aa64c04143b5d4b`、expired=false、expires=`2026-11-17T11:20:19Z`。公开branch state为`main.protected=true`、head与implementation SHA一致、required check=`validate`/app ID=`15368`。

全部Completion conditions满足，Task标记`done`。本evidence-only状态提交无法由上述implementation run自我包含；推送后必须再运行同一workflow并在交付中报告最终run。该闭环不自动启动TASK-P1-05、不进入P2。
