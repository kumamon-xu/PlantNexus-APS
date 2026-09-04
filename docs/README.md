---
doc_id: DOC-INDEX-001
title: PlantNexus APS 公开文档中心
status: living
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [2, 6, 24, 90, 113, 114]
last_reviewed: 2026-09-04
---

# PlantNexus APS 公开文档中心

本目录只收录适合随公开 Git 仓库发布的核心项目文档。开发过程记录、Task Card、阶段证据、机器报告、临时草稿、截图、测试输出和下载制品不属于公开文档，应留在被忽略的本地目录或 `build/`。

项目当前已形成 P0～P6 研发能力，P7 真实数据校准暂缓，P8 Headless产品化已从机器合同推进到持久化canonical ingress应用切片。产品边界只接收宿主平台提交的versioned canonical JSON，不在APS内直接建设ERP/MES/WMS/CAM连接器；宿主和未来可选独立Frontend消费同一API。企业适配规划通过Extension SDK和独立Enterprise Extension在Runtime内实现，并由version-locked Developer Kit交付，禁止复制/修改Core或自动升级企业项目。当前已形成[Headless平台集成与数据权威合同](contracts/headless-platform-integration.md)、schema set `2.10.0`中的canonical ingress/result、PlanningRun与Headless错误注册表，以及严格消费这些合同并原子保存immutable Snapshot/PlanningProblem的内部应用服务；公开HTTP、Solver Worker、SDK、Registry和Developer Kit仍未实现，也不代表Production readiness、UAT、真实身份/审批authority、部署、容量结论或SLA已经形成。能力声明以[能力矩阵](core/capability-matrix.md)和对应合同为准。

## 核心入口

| 主题 | 首选文档 | 用途 |
|---|---|---|
| 系统范围 | [范围与成功标准](core/scope-and-success-criteria.md) | 了解目标、非目标和完成边界 |
| 系统架构 | [系统上下文](architecture/system-context.md) | 了解外部系统、边界和数据流向 |
| Headless 集成 | [Headless 平台集成与数据权威合同](contracts/headless-platform-integration.md) | 了解canonical JSON、责任矩阵、authority/scope/idempotency/lineage和失败边界 |
| 企业扩展 | [Extension SDK、Runtime 与 Developer Kit](architecture/extension-sdk-runtime-and-developer-kit.md) | 了解Core不变、服务端Extension、Plugin Registry、版本锁定和兼容发布 |
| 主流程 | [端到端计划流程](architecture/end-to-end-planning-flow.md) | 从导入到排程、校验、版本、导出和重排 |
| 领域对象 | [领域模型](domain/domain-model.md) | Factory、Routing、Order、Snapshot、Version 等对象关系 |
| API | [API 接口开发清单](contracts/api-development-checklist.md) | 当前所有 HTTP operation、状态、合同和缺口 |
| 数据字段 | [数据字段中文名称字典](contracts/data-field-dictionary.md) | canonical records 的英文 key、中文名、类型和约束 |
| 机器合同 | [Schema 索引](contracts/schema-index.md) | JSON Schema、URN、版本和兼容边界 |
| 排程规则 | [约束目录](planning/constraint-catalog.md) | C-001～C-018 约束状态和责任边界 |
| 校验 | [ScheduleValidator](planning/schedule-validator.md) | 候选排程独立验收规则 |
| 动态重排 | [重排设计](planning/replanning.md) | ExecutionEvent、freeze、stability 与 ChangeReport |
| 前端 | [Frontend 文档](frontend/README.md) | 工作台、双语、命令和浏览器边界 |
| 运维与安全 | [Operations 索引](operations/README.md) | 安全、可观测性、审计和 worker 可靠性 |

## 按角色阅读

### Backend / API 开发

1. [模块边界](architecture/module-boundaries.md)
2. [API 接口开发清单](contracts/api-development-checklist.md)
3. [Planning Workspace API 合同](contracts/planning-workspace-api.md)
4. [授权与审计](contracts/authorization-and-audit.md)
5. [错误模型](domain/error-model.md)

### 数据接入与集成

1. [Headless 平台集成与数据权威合同](contracts/headless-platform-integration.md)
2. [Headless 产品化与平台集成](architecture/headless-productization-and-platform-integration.md)
3. [Extension SDK、Runtime 与 Developer Kit](architecture/extension-sdk-runtime-and-developer-kit.md)
4. [数据 authority](architecture/data-authority.md)
5. [导入与归一化](contracts/import-and-normalization.md)
6. [数据字段中文名称字典](contracts/data-field-dictionary.md)
7. [Schema 版本规则](contracts/schema-versioning.md)
8. [Schema 索引](contracts/schema-index.md)

### 排程算法开发

1. [PlanningProblem 合同](contracts/planning-problem.md)
2. [策略与求解限制](contracts/planning-policy-and-solve-limits.md)
3. [SolverBackend 合同](planning/solver-backend-contract.md)
4. [目标函数策略](planning/objective-policy.md)
5. [独立排程校验器](planning/schedule-validator.md)

### Frontend 开发

1. [Planning Workspace](frontend/planning-workspace.md)
2. [甘特命令合同](frontend/gantt-command-contract.md)
3. [审批与发布流程](frontend/approval-publication-flow.md)
4. [官方中文术语映射](frontend/official-zh-cn-terminology-map.md)

## 公开文档分区

| 目录 | 内容 |
|---|---|
| `adr/` | 已接受的架构决策记录 |
| `architecture/` | 系统上下文、模块、技术栈、环境与数据 authority |
| `contracts/` | 人类语义合同、API 清单、字段字典与 Schema 索引 |
| `core/` | 范围、工程原则、术语和能力矩阵 |
| `domain/` | 领域模型、时间/物料边界、错误、KPI 与状态机 |
| `frontend/` | 工作台、命令、审批发布和本地化 |
| `operations/` | 安全、可观测性、审计和 worker 可靠性 |
| `planning/` | Solver、策略、目标、约束、校验和重排 |
| `simulation/` | 合成场景、生成器、执行模拟和性能 Gate |

## 权威顺序

发生冲突时按以下顺序处理：

1. `schemas/` 中的版本化 JSON Schema、规则注册表与机器数据字典；
2. accepted ADR 和 `contracts/` 中的语义合同；
3. `domain/`、`planning/`、`architecture/` 中的模块规范；
4. 本页和根 README 的导航性说明。

README 不能覆盖 Schema、合同或 ADR。中文字段名只用于阅读和展示，JSON key、enum、operationId、状态码和指纹仍使用英文机器值。

## 文档维护规则

- 新文档必须是核心、可公开、可长期维护的 Markdown；敏感信息、真实数据、凭据和内部运行证据不得进入仓库。
- API 或字段发生变化时，先更新对应 Schema/合同，再同步 API 清单或字段字典。
- 生成的 OpenAPI、测试报告、coverage、benchmark、截图、视频、HTML、临时导出和下载 artifact 写入 `build/` 或工具输出目录，不写入 `docs/`。
- 草稿应在仓库外或被忽略目录中完成；进入 `docs/` 前应移除运行编号、绝对路径、个人信息和内部链接。
- 所有本地链接必须指向公开 Git 管理的文件；不从公开索引链接内部过程文档。

## 本地检查

在仓库根目录运行：

```powershell
uv run python scripts/check_docs.py
git diff --check
```

功能或合同变更还必须运行对应模块测试；文档检查不能替代 Schema、API、Solver、Validator、Frontend 或 migration 验收。
