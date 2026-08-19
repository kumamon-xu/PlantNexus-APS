---
doc_id: DOC-INDEX-001
title: PlantNexus APS 文档中心
status: baseline
spec_version: 0.3.0
phase: P1
normative: false
source_sections: [2, 6, 70]
last_reviewed: 2026-08-19
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

当前阶段为P1。P0 Gate已通过且用户已明确授权phase transition；TASK-P1-02的canonical records、Import v2与PlanningSnapshot v2合同已完成，TASK-P1-03仍为`planned`，尚未开始Adapter/staging/normalization/builder。禁止真实CP-SAT/P2、生产参数猜测或绕过正式入口。详见`current_phase.md`。

## 仓库入口与本地检查

- 项目入口、版本占位和当前可执行命令见 [`../README.md`](../README.md)；
- 根 [`../AGENTS.md`](../AGENTS.md) 只负责把 Agent 导向规范正文，不复制规则；
- 仓库治理检查运行 `uv run python scripts/check_docs.py`；
- 该检查验证 metadata、文档 ID、Markdown fence、本地链接、Task、版本化 registry、完整 ID 引用、逐根 traceability 和命名空间隔离；
- Task 进入 `in_progress` 时记录完整 `Diff base`；`--task <task-card> --check-diff` 对 `Diff base..HEAD` 与 working tree 的并集匹配 change-impact Rule ID，并可用 `--report <path>` 输出 `traceability-report.v1`。

本地检查已经形成，并从 `current_phase.md` 读取 current `Pn`，保留历史 terminal Task且拒绝 future-phase详细卡。TASK-P1-01已形成repository-local CI handoff；provider结果仍须来自真实授权运行，不能因本地命令PASS而宣称P1 Gate或生产就绪。

CI 可用 `uv run python scripts/check_docs.py --discover-task-from <event-base-sha> --check-diff --report build/traceability/ci-current-task-report.json`从一次 PR/push event range发现唯一 current-phase Task；本地 Task验收仍使用显式 `--task`。两种入口最终都使用 Task Card内的 immutable `Diff base`，不能把 event base当作 Task scope base。
