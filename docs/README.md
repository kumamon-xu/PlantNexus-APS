---
doc_id: DOC-INDEX-001
title: PlantNexus APS 文档中心
status: baseline
spec_version: 0.3.0
phase: P2
normative: false
source_sections: [2, 6, 70]
last_reviewed: 2026-08-20
---

# PlantNexus APS 文档中心

本目录是 PlantNexus APS 的唯一实质性开发文档中心。项目采用 Simulation-First、可追溯和阶段门禁驱动的开发方式；文档不是事后说明，而是代码、Schema、测试、Fixture、Benchmark 和发布活动的前置边界。

## 权威顺序

发生冲突时按以下顺序处理：

1. 用户在当前任务中的明确要求；
2. `core/APS_IMPLEMENTATION_SPEC.md` 中当前版本的 MUST、MUST NOT 和 DECIDED；
3. 已接受且未被取代的 ADR；
4. 当前阶段文件和当前任务卡；
5. 其他参考文档。

发现冲突不得自行折中，应登记问题并停止受影响的实现。

## 日常读取顺序

```text
/AGENTS.md
→ docs/agents/AGENTS.md
→ docs/current_phase.md
→ 当前 TASK
→ TASK 引用的 Schema / Contract / Constraint / ADR
→ 相关代码
→ 相关测试
```

只有规格版本变化，或任务涉及架构边界、PlanningProblem、SolverBackend、Constraint Catalog、状态机、发布规则或阶段退出门时，才需要重新完整读取总规。

## 文档分区

| 目录 | 用途 | 成熟方式 |
|---|---|---|
| `core/` | 总规、范围、原则、术语、能力边界 | 稳定、规范性 |
| `governance/` | 需求、追踪、开放问题、假设、风险 | 持续维护 |
| `architecture/` | 系统边界、模块、数据权威、环境 | ADR 驱动 |
| `domain/` | 领域对象、时间语义、状态机、错误与 KPI | Schema/业务规则驱动 |
| `contracts/` | 可执行 Schema 对应的人类语义合同 | 与 Schema 同版本 |
| `planning/` | 策略、约束、目标、求解器与独立验证 | 规范性核心 |
| `simulation/` | 虚拟工厂、场景、生成器、执行仿真和性能门 | 可重放、版本化 |
| `quality/` | 测试矩阵、Fixture、Mutation、Property、Benchmark | 持续维护 |
| `milestones/` | P0-P7 目标、范围和退出门 | 阶段级 |
| `agents/` | Coding Agent 的读取、执行和停止规则 | 稳定、简洁 |
| `tasks/` | 有界任务卡 | 随当前阶段创建 |
| `adr/` | 架构和规则决策记录 | 只追加/取代，不改历史 |
| `operations/`、`runbooks/` | 实现后形成的运维事实 | 后期形成 |

当前已生成文档的完整可点击清单见 [`governance/document-inventory.md`](governance/document-inventory.md)。

## 文档状态

- `baseline`：由规格直接建立，可用于指导当前阶段。
- `living`：已经启用，但会随实现证据持续更新。
- `draft`：尚未批准，不能单独作为实现依据。
- `planned`：只有路径和目的，等待依赖形成。
- `superseded`：已被新文档或 ADR 取代，只保留历史。

## 当前范围

当前阶段为P2。P1 Milestone为`completed`，P2为`active`；TASK-P2-00～04均已闭环为`done`，TASK-P2-05已经用户明确授权并以`c75f7a0e96b7591ffa9220d0de942f8841283093`为Diff base处于`in_progress`。正式Problem/Solution Validator独立重算C-001～C-011，且local/exact-provider mutation/property/schema/error/independence证据完整；P2-05只实施C-001/003/004/010/011 core model，OBJ-001搜索、C-002/005～009、Benchmark、P2-06～14和P3均未启动，详见`current_phase.md`。

## 仓库入口与本地检查

- 项目入口、版本占位和当前可执行命令见 [`../README.md`](../README.md)；
- 根 [`../AGENTS.md`](../AGENTS.md) 只负责把 Agent 导向规范正文，不复制规则；
- 仓库治理检查运行 `uv run python scripts/check_docs.py`；
- 该检查验证 metadata、文档 ID、Markdown fence、本地链接、Task、版本化 registry、完整 ID 引用、逐根 traceability 和命名空间隔离；
- Task 进入 `in_progress` 时记录完整 `Diff base`；`--task <task-card> --check-diff` 对 `Diff base..HEAD` 与 working tree 的并集匹配 change-impact Rule ID，并可用 `--report <path>` 输出 `traceability-report.v1`。

本地检查从`current_phase.md`读取current `Pn`，保留历史terminal Task且拒绝future-phase详细卡。普通CI range只能归属一张current-phase Task；初始phase-planning batch仅允许唯一新建`TASK-Pn-00` owner加同range新建的`planned/ready`成员卡，之后仍按owner Diff base执行scope/impact。Provider结果必须来自真实授权运行，不能由本地PASS推断。

CI 可用 `uv run python scripts/check_docs.py --discover-task-from <event-base-sha> --check-diff --report build/traceability/ci-current-task-report.json`从一次 PR/push event range发现唯一 current-phase Task；本地 Task验收仍使用显式 `--task`。两种入口最终都使用 Task Card内的 immutable `Diff base`，不能把 event base当作 Task scope base。

TASK-P2-03本地39项聚焦、319项全量和6/6 foundation均PASS；exact GitHub required `validate`与artifact也已核验，Task=`done`。工程smoke仍不是业务Solver/Validator/Benchmark证据。

TASK-P2-04本地证据为6/6 formal machine checks、13个mutation、11个C-ID、14个hard violations和6个duration/order examples；implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的exact GitHub run `32350068318` / required job `96367085099` / artifact `9399519368`复现该报告和38-path/6-row/0-issue Task report，故Task=`done`。本Task未修改Backend、合同Schema、fixture bytes、dependency、objective或Benchmark。

TASK-P2-05已形成C-001/003/004/010/011 core CP-SAT、完整candidate映射、future-fact fail-closed、formal Validator consumer、fixed-seed property与独立tiny oracle。Local acceptance为64 focused、360 full、Ruff/Pyright 0、core/formal各6/6、治理49 paths/6 rows/0 issues、compose/build/immutable PASS；等待exact implementation provider evidence，Task暂为`in_progress`，P2-06未获授权。
