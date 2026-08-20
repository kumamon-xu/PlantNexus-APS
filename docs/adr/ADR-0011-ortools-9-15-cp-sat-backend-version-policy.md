---
doc_id: ADR-0011
title: OR-Tools 9.15 CP-SAT Backend 与版本策略
status: accepted
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [14, 24, 29, 57, 75, 93, 102]
last_reviewed: 2026-08-20
---

# ADR-0011 — OR-Tools 9.15 CP-SAT Backend 与版本策略

Status: accepted

Date: 2026-08-20

Decision owners: PlantNexus APS maintainers under TASK-P2-03 authorization

Requirement/NFR/ENG: REQ-004、REQ-009、NFR-COR-001、NFR-TRC-001、NFR-OBS-001、NFR-PER-001、ENG-ARCH-001、ENG-SOL-001、ENG-ERR-001、ENG-VER-001

Supersedes: none；落实ADR-0003/0004并保持ADR-0002/0008

## Context

P2-02已固定solver-neutral Problem/Policy/Limits/Solution/Report与七种产品status，但尚无Backend实现或Solver dependency。ADR-0004要求P2主Backend使用固定精确版本的Google OR-Tools CP-SAT；首次引入还必须在依赖变更前明确版本、安装介质、namespace、参数/status映射、升级重放与回滚边界。

截至2026-08-20，官方[PyPI发布页](https://pypi.org/project/ortools/)将`9.15.6755`列为最新稳定版，并提供CPython 3.12的Windows x86-64、manylinux x86-64/aarch64与macOS wheels；官方[OR-Tools v9.15 release](https://github.com/google/or-tools/releases/tag/v9.15)记录CP-SAT与Python层改进。`v10.0 Beta`不是稳定发布。审查时官方repository-level security advisories为空；v9.15已知wrapper问题包含`status_name()`调用异常，因此不能把该便利API作为合同边界。

## Decision

1. Runtime direct dependency固定为`ortools==9.15.6755`，由`uv.lock`锁定完整transitive graph与所有受支持platform wheel hashes；只使用官方PyPI binary wheel，不在本Task源码编译、启用第三方商业solver或使用floating range。
2. OR-Tools/CpModel/CpSolver对象和import只允许存在于`backend/app/planning/backends/cp_sat/`。Domain、PlanningProblem、Policy、public `SolverBackend` protocol、Validator、API、DB与Worker保持solver-neutral；任何跨边界输出必须是JSON-compatible primitive/document。
3. Backend identity固定为`cp-sat` / `cp-sat-backend.v1` / `Google OR-Tools CP-SAT` / `9.15.6755`。每个未来真实SolverReport必须记录上述identity、code commit与实际参数。
4. SolveLimits只显式映射为`max_time_in_seconds`、`num_search_workers`和`random_seed`；Backend固定参数（当前`log_search_progress=false`）标记为`BACKEND`来源。不得隐藏业务默认或让参数改变C-ID/OBJ语义。
5. 五个CP-SAT native status显式映射到OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN/MODEL_INVALID；CANCELLED来自adapter控制路径，FAILED来自version/import/native-status/adapter异常。UNKNOWN继续映射`NO_SOLUTION_WITHIN_LIMIT`，不能改写为INFEASIBLE。实现不得调用已知有兼容问题的`status_name()`便利API。
6. TASK-P2-03只允许empty与intentionally-invalid engineering smoke；empty模型的OPTIMAL只证明binary/API可执行，必须标记`business_feasibility=NOT_EVALUATED`，不得产出candidate或冒充C-001～C-011/OBJ-001结果。正式model construction从TASK-P2-05开始，独立Validator由TASK-P2-04负责。
7. 首次foundation的机器证据必须保存exact direct pin、installed/locked version、lock fingerprint、platform/Python、namespace scan、status/parameter mapping、empty/model-invalid smoke和serialization isolation。由于尚无业务模型，Benchmark结论为`NOT_APPLICABLE_FOUNDATION_ONLY`，不是零运行时baseline。
8. 后续任何OR-Tools/Backend版本升级必须提交新的superseding ADR，更新exact pin/lock，并重跑status/parameter/namespace合同、全部已形成Golden/Scenario/Property/Mutation、同Problem/Policy/Limits replay与Benchmark comparison。正确性退化、status漂移或未批准的显著性能退化阻止升级。

## Alternatives considered

- `ortools==9.14.6206`：上一稳定版可用，但没有证据表明应在首次baseline主动选择旧版；拒绝。
- `v10.0 Beta`或Git commit/nightly：尚非稳定发布且升级面更大；拒绝。
- `ortools>=9.15`、`~=9.15`或运行时动态安装：不能形成可重放依赖与SolverReport identity；拒绝。
- 源码编译或启用SCIP/Gurobi/XPress等第三方solver：本Task不需要，扩大平台和许可/供应链面；拒绝。
- 在Problem/Domain中直接构造CpModel：违反ADR-0003并破坏可序列化重放；拒绝。

## Consequences

本决定首次增加大型native runtime wheel及其transitive依赖，local/container/provider安装体积与供应链面上升；因此exact lock、Linux provider replay、安全审查和artifact是完成门。Windows local与GitHub Linux runner都必须实际import/solve smoke，单一平台成功不能替代另一平台事实。

Protocol和合同字节不因安装Solver而变化。P2-02的`CONTRACT_SAMPLE`仍保留`not-installed`作为历史shape样例值，不会被改写为真实Solver run。P0/P2历史machine report必须改为区分“该历史Task未实现Solver”与“当前仓库已有P2-03 foundation”，不得继续把全仓无OR-Tools当成永久事实。

Repository-level advisory空列表和一次性dependency audit只说明2026-08-20审查时未发现已知公告，不构成持续监控、SBOM/signing、Production threat assessment、capacity或SLA证据。OPEN-011/012继续OPEN。

## Rollback / Revisit gate

P2-05等consumer形成前，可回退`pyproject.toml`/`uv.lock`与整个`planning/backends/cp_sat` namespace，并保留本ADR为历史、另建superseding/rejected decision；不得重写本记录。Consumer形成后必须先回退consumer，再删除Backend dependency，并重跑合同、Scenario与治理检查。

出现官方安全公告、Python/platform wheel缺失、native crash、status/parameter语义变化、correctness regression或Benchmark显著退化时立即停止升级/发布并建立superseding ADR。P2-12形成正式baseline后，任何版本改变都必须以相同Problem/Policy/Limits和固定Scenario Set比较，不能只凭release note接受。
