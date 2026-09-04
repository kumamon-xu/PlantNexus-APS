---
doc_id: DOC-CONTRACT-012
title: API 接口开发清单
status: living
spec_version: 0.3.0
phase: P3-P8
normative: false
source_sections: [63, 65, 66, 68, 69, 77, 78, 79, 80, 95, 113, 114]
last_reviewed: 2026-09-04
---

# API 接口开发清单

本清单以当前 FastAPI OpenAPI、router、application port 和自动化测试为事实来源，用于回答“接口是否存在、实现到哪一层、还缺什么”。具体 wire 语义仍以 [Planning Workspace API 合同](planning-workspace-api.md)、[ExecutionEvent / ReplanRequest 合同](execution-events-and-replan-request.md)和[错误模型](../domain/error-model.md)为准。

P8目标边界已经确定，但尚未实现：APS未来只通过Headless API接收宿主平台提交的versioned canonical JSON；不提供ERP/MES/WMS/CAM专用连接器或raw文件产品端点。宿主和可选独立Frontend使用同一API。Extension SDK和Plugin Registry只在APS Runtime内部使用，不提供插件上传、下载、安装或企业私有业务route；企业特有数据仍须使用批准的namespaced/versioned canonical字段。下述29项仍是当前真实OpenAPI，P8计划不能被解释为现有operation。

## 状态说明

- **默认可用**：默认组合根可直接执行，不依赖业务 application adapter。
- **实现可用，合同待补**：运行时行为已经存在，但 OpenAPI 声明仍不完整；外部依赖该分支前必须补齐响应合同和合同测试。
- **路由完成，需运行时适配器**：path、operationId、输入校验、授权边界、错误映射和测试已经实现；默认组合根使用 unavailable application/authorization provider，因此业务调用会 fail closed。接入可用 repository/application/identity adapter 后才能形成可运行服务。
- **未提供公开端点**：当前 OpenAPI 没有该能力；新增前必须先形成合同、authority 和错误/幂等边界，不能从内部 Python service 推断 HTTP API 已存在。

当前 OpenAPI 共 29 个 operation：2 个健康检查、18 个 Planning Workspace operation、9 个动态重排 operation。`/docs` 与 `/redoc` 关闭，只公开 `/openapi.json`。

## 健康与合同入口

| Method | Path | Operation ID | 用途 | 响应 | 状态 |
|---|---|---|---|---:|---|
| `GET` | `/health/live` | `live_health_live_get` | 进程存活、服务与构建信息 | 200 | 默认可用 |
| `GET` | `/health/ready` | `ready_health_ready_get` | PostgreSQL/Redis readiness 汇总 | 200；未就绪为 503 | 实现可用，合同待补 |
| `GET` | `/openapi.json` | FastAPI 内建 | 当前 HTTP 合同 | 200 | 默认可用 |

## Planning Workspace

实现位置：[planning_workspace.py](../../backend/app/api/routers/planning_workspace.py)。合同/集成/安全测试分别位于 [HTTP contract test](../../backend/tests/contract/test_planning_workspace_http_api.py)、[integration test](../../backend/tests/integration/test_planning_workspace_api_integration.py)和[authorization test](../../backend/tests/security/test_planning_workspace_http_authorization.py)。

| Method | Path | Operation ID | 用途 | 成功响应 | 状态 |
|---|---|---|---|---:|---|
| `GET` | `/api/v1/planning-runs/{planning_run_id}` | `getPlanningRun` | 查询计划运行摘要 | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/schedule-versions/{schedule_version_id}` | `getScheduleVersion` | 查询计划版本与允许动作 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/schedule-versions/{schedule_version_id}/validate` | `validateScheduleVersion` | 提交独立校验/评审 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/schedule-versions/{schedule_version_id}/approve` | `approveScheduleVersion` | 审批 READY_FOR_REVIEW 版本 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/schedule-versions/{schedule_version_id}/reject` | `rejectScheduleVersion` | 驳回 READY_FOR_REVIEW 版本 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/schedule-versions/{schedule_version_id}/publish` | `publishScheduleVersion` | 发布已审批版本到内部目标 | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/workspace/data-health` | `getWorkspaceDataHealth` | 查询数据质量与新鲜度投影 | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/workspace/import-runs` | `listWorkspaceImportRuns` | 分页查询导入运行 | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/workspace/planning-runs` | `listWorkspacePlanningRuns` | 分页查询计划运行 | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/schedule-versions/{schedule_version_id}/workspace/{view}` | `queryScheduleVersionWorkspace` | 查询订单、工序、资源、日历、甘特、负荷、KPI、诊断、锁和审计视图 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/schedule-version-comparisons` | `compareScheduleVersions` | 比较两个不可变计划版本 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/schedule-versions/{schedule_version_id}/commands` | `executeScheduleVersionCommand` | 移动、改派、设置/删除锁，copy-on-write 生成新 DRAFT | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/schedule-versions/{schedule_version_id}/audit-events` | `listScheduleVersionAuditEvents` | 查询计划版本审计事件 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/schedule-versions/{schedule_version_id}/exports` | `createScheduleVersionExport` | 创建内部导出任务 | 202 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/export-jobs/{export_job_id}` | `getExportJob` | 查询导出任务状态 | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/export-jobs/{export_job_id}/download` | `downloadExportPackage` | 下载已验证的内部 ZIP 包 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/export-jobs/{export_job_id}/retry` | `retryExportJob` | 重试失败导出任务 | 202 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/export-jobs/{export_job_id}/cancel` | `cancelExportJob` | 取消允许取消的导出任务 | 200 | 路由完成，需运行时适配器 |

## 动态重排

实现位置：[dynamic_replanning.py](../../backend/app/api/routers/dynamic_replanning.py)。合同/集成/安全测试分别位于 [HTTP contract test](../../backend/tests/contract/test_dynamic_replanning_http_api.py)、[integration test](../../backend/tests/integration/test_dynamic_replanning_api_integration.py)和[authorization test](../../backend/tests/security/test_dynamic_replanning_http_authorization.py)。

| Method | Path | Operation ID | 用途 | 成功响应 | 状态 |
|---|---|---|---|---:|---|
| `POST` | `/api/v1/execution-events` | `appendExecutionEvent` | 追加版本化 ExecutionEvent | 202 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/execution-events` | `listExecutionEvents` | 按 authority/stream/position 查询事件流 | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/execution-events/{event_id}` | `getExecutionEvent` | 查询单个执行事件 | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/replan-requests` | `createReplanRequest` | 创建不可变 ReplanRequest 与求解 attempt | 202 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/replan-requests/{request_id}` | `getReplanRequest` | 查询请求与当前 attempt | 200 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/replan-requests/{request_id}/cancel` | `cancelReplanRequest` | 以 expected attempt state 请求取消 | 202 | 路由完成，需运行时适配器 |
| `POST` | `/api/v1/replan-requests/{request_id}/retry` | `retryReplanRequest` | 以新 attempt 重试请求 | 202 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/replan-requests/{request_id}/result` | `getReplanResult` | 查询 terminal result、新 DRAFT 和 ChangeReport 引用 | 200 | 路由完成，需运行时适配器 |
| `GET` | `/api/v1/change-reports/{report_id}` | `getChangeReport` | 查询版本化 ChangeReport read model | 200 | 路由完成，需运行时适配器 |

## 通用请求与错误约定

- `/api/v1/**` 的 capability、actor、scope 必须由服务端授权 provider 解析；客户端 body 不能自报角色。
- command/event/replan action 使用 `Idempotency-Key` header，长度 16～128；same key + different fingerprint 返回冲突且不产生副作用。
- workspace 和 replanning GET 使用名为 `query` 的 URL 编码 canonical JSON，长度 2～16384，并绑定版本、排序、筛选、cursor 和 fingerprint。
- Planning Workspace command body 使用 `workspace-command.v1`；动态事件和请求分别使用 `execution-event.v1`、`replan-request.v1`。
- 业务错误统一提供 sanitized envelope；公开错误状态为 401、403、404、409、422、500、503。SQL、stack、credential、绝对文件路径和 raw token 不得进入响应。
- Production-shaped 请求在真实 authority、数据来源和运行时适配器形成前 default-deny。Simulation 只允许显式隔离的测试/开发上下文。

## 尚未提供或待补齐的公开 API/合同

| 能力 | 当前状态 | 补齐前置 |
|---|---|---|
| 提交versioned canonical JSON | P8-01/02人类与机器合同已形成，当前未提供公开端点 | P8-03的Data Validation、幂等事务和不可变artifact owner，之后由P8-07暴露HTTP |
| 上传/提交原始ERP/MES/WMS/CAM、Excel/CSV数据 | 不属于APS公共产品API | 由宿主平台采集/映射为canonical JSON；reference adapter仅内部/研发使用 |
| 通过 HTTP 创建 PlanningSnapshot / PlanningProblem | P8规划，当前未提供公开端点 | Canonical ingress成功后由APS原子创建，不开放直接数据库写入 |
| 通过 HTTP 创建并启动新的 PlanningRun | P8-02 lifecycle机器合同已形成，当前未提供公开端点 | P8-04/05的持久化、Policy/Limits、排队/取消/超时和Worker行为，之后由P8-07暴露HTTP |
| 工厂、资源、工艺、订单主数据 CRUD | 不作为Snapshot旁路 | 宿主维护上游主数据并提交新canonical版本；APS不直接修改既有Snapshot |
| 用户、角色、SSO/RBAC 管理 | 用户生命周期不属于APS；当前只有provider port | P8-08接入宿主identity并由APS强制role/capability/factory scope |
| 生产MES/ERP事件连接器与外部发布 | 连接器不属于APS；当前无Production发布 | 宿主负责上游/下游连接，APS只提供canonical input与read/export API；authority仍需closure |
| readiness 失败响应的 OpenAPI 声明 | 运行时会返回 503，但当前 OpenAPI 只声明 200 | 显式声明 503 response/schema，并增加 OpenAPI 合同断言 |
| Swagger/ReDoc UI 与提交版 OpenAPI 快照 | UI 关闭、快照未提交 | 决定公开范围、敏感信息审查和版本漂移 Gate |

上述缺口不是隐藏能力。若要新增接口，应先更新语义合同与机器 Schema，再实现 application port、router、授权、错误、正负测试和 OpenAPI 清单。

## 清单维护检查

接口变更至少同步以下位置：

1. router 与 application port；
2. 对应合同和 JSON Schema；
3. OpenAPI contract/integration/security tests；
4. 本清单及必要的 Frontend client；
5. 文档链接与版本兼容说明。
