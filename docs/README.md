---
doc_id: DOC-INDEX-001
title: PlantNexus APS 公开文档中心
status: living
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [2, 6, 24, 90, 113, 114]
last_reviewed: 2026-09-11
---

# PlantNexus APS 公开文档中心

企业Runtime镜像的固定输入、构建与离线tar身份见[部署说明](operations/deployment.md#企业-runtime-oci-镜像)；[安全说明](operations/security.md#企业镜像扫描与未关闭风险)保留未关闭OS漏洞，使用范围为内部TEST/SIMULATION。配置、Compose与最终离线包继续按后续交付任务实现。

本目录只收录适合随公开 Git 仓库发布的核心项目文档。开发过程记录、Task Card、阶段证据、机器报告、临时草稿、截图、测试输出和下载制品不属于公开文档，应留在被忽略的本地目录或 `build/`。

项目当前已形成P0～P6研发能力，P7真实数据校准暂缓；P8 Headless产品化工程里程碑已完成。当前具备durable canonical ingress、PlanningRun、Solver Worker、单一Runtime组合、五项公开HTTP operation、Test identity/authorization/audit、Runtime工程分发与非Production运维演练。产品边界只接收宿主平台提交的versioned canonical JSON，不在APS内直接建设ERP/MES/WMS/CAM连接器；宿主与可选独立Frontend消费同一API。P8还形成`0.1.0`静态Frontend工程分发、Extension SDK `1.0.0`、服务端Registry/loader、独立项目模板、确定性conformance工具、两份synthetic Enterprise Extension及不可变Developer Kit `1.0.0`。企业项目锁定已验证的Runtime、SDK和Kit组合独立维护，Core/Runtime升级不触发自动升级。

2026-09-11治理决定已将历史P5中未实现、未执行的TASK-P5-03～20全部最终退役；这些Task不得恢复或继续实现。本轮定制的Secondary Resource、Sequence-dependent Setup、Material Competition、Batch、Split/Merge、Buffer、Preemption、Decomposition与Rolling Horizon方案据此作废，C-012～C-018继续显式`UNSUPPORTED_CAPABILITY`，Global仍是唯一已形成策略。未来如重新审定高级功能，必须基于届时需求建立全新versioned计划与全新Task ID，不能继承或复活原P5卡。

P8-17独立`PHASE_GATE`已核验21个P8 Task、21组前序Provider输入（20个前序Task）、88份artifact/2,032个条目及10项保留失败/纠正历史，并在精确提交上fresh重放P8-19。304项P8目标回归、20/20 Exit check、18/18平台检查和4/4 closure均为PASS，零issue/zero gap；该提交的FULL与required Provider已成功，P8-17=`done`、P8=`completed`。失败候选及其artifact仍保留且不rerun。冻结Developer Kit `1.0.0`继续保留`UNSIGNED_ENGINEERING_CANDIDATE`元数据；最终外层成果是`UNSIGNED_INTERNAL_ENGINEERING_DELIVERY`，只代表synthetic工程产品化，不等于外部签名、Production部署、真实客户Extension、P7现实校准、容量/SLA或UAT。能力声明以[能力矩阵](core/capability-matrix.md)和对应合同为准。

## 核心入口

| 主题 | 首选文档 | 用途 |
|---|---|---|
| 系统范围 | [范围与成功标准](core/scope-and-success-criteria.md) | 了解目标、非目标和完成边界 |
| 系统架构 | [系统上下文](architecture/system-context.md) | 了解外部系统、边界和数据流向 |
| Headless 集成 | [Headless 平台集成与数据权威合同](contracts/headless-platform-integration.md) | 了解canonical JSON、责任矩阵、authority/scope/idempotency/lineage和失败边界 |
| 企业扩展 | [Extension SDK、Runtime 与 Developer Kit](architecture/extension-sdk-runtime-and-developer-kit.md) | 了解Core不变、服务端Extension、Plugin Registry、版本锁定和兼容发布 |
| 扩展开发 | [Enterprise Extension 开发指南](architecture/enterprise-extension-development-guide.md) | 创建独立项目，执行SDK-only构建、clean测试、conformance与升级回放 |
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
| 发布与安装 | [Runtime 发布、版本与回退合同](operations/release-and-versioning.md) | 版本矩阵、确定性distribution、SBOM、preflight、升级与回退 |
| Developer Kit | [Developer Kit 发布、升级与回滚](operations/developer-kit-release-upgrade-and-rollback.md) | Kit `1.0.0`内容身份、兼容矩阵、显式升级、支持和签名边界 |

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
4. [Enterprise Extension 开发指南](architecture/enterprise-extension-development-guide.md)
5. [数据 authority](architecture/data-authority.md)
6. [导入与归一化](contracts/import-and-normalization.md)
7. [数据字段中文名称字典](contracts/data-field-dictionary.md)
8. [Schema 版本规则](contracts/schema-versioning.md)
9. [Schema 索引](contracts/schema-index.md)

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
- 规范性、确定生成的版本化OpenAPI快照可以随其API owner提交；运行期测试报告、coverage、benchmark、截图、视频、HTML、临时导出和下载artifact仍写入`build/`或工具输出目录，不写入`docs/`。
- 阶段Exit所需的公开观察文件只能包含脱敏身份、计数和指纹；原始下载包、内部Task Card、过程报告、运行日志与交付组装临时目录必须保持在忽略范围内。
- 草稿应在仓库外或被忽略目录中完成；进入 `docs/` 前应移除运行编号、绝对路径、个人信息和内部链接。
- 所有本地链接必须指向公开 Git 管理的文件；不从公开索引链接内部过程文档。

## 本地检查

在仓库根目录运行：

```powershell
uv run python scripts/check_docs.py
git diff --check
```

功能或合同变更还必须运行对应模块测试；文档检查不能替代 Schema、API、Solver、Validator、Frontend 或 migration 验收。

CI执行、显式阶段审计与机器取证见[CI execution and evidence](architecture/ci-execution-and-evidence.md)。
