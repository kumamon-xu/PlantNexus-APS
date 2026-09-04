# 架构、编排与 API 设计

## 1. 目标架构

    Demo Browser
        │
        ├── /api/demo/v1：业务化命令、job 状态、统一展示 DTO
        │
        └── /api/v1：复用现有 workspace / replanning 只读与控制路由
                         │
    Demo FastAPI composition root
        ├── DemoOrchestrator
        ├── 单 worker durable job runner
        ├── RoutedPlanningWorkspaceApplication
        ├── RoutedDynamicReplanningApplication
        ├── SimulationLocalAuthorizationProvider
        └── PresentationQueryService
                         │
        ├── 标准导入 → Snapshot → PlanningProblem v2
        ├── Global CP-SAT → 独立 Validator → KPI
        ├── ScheduleVersion 生命周期 / Publication
        └── ExecutionEvent → ReplanRequest → P4 Replan → ChangeReport
                         │
        ├── demo/runtime/control.db
        └── demo/runtime/runs/{run_id}/plantnexus.db

Demo API 是编排与展示适配层，不复制求解器、Validator、事件投影或版本状态机。

## 2. 目录边界

建议实现结构：

    demo/
      backend/
        plantnexus_demo/
          api/
          application/
          composition/
          data/
          jobs/
          presentation/
          persistence/
          security/
          main.py
      frontend/
        src/
          api/
          components/
          features/
          pages/
      data/
        cnc-showcase/
      benchmarks/
        profiles/
        results/
      tests/
        contract/
        integration/
        e2e/
        fixtures/
      scripts/
      runtime/
        .gitignore
      docs/

规则：

- demo 代码可以导入 backend/app 下的公开 Python 模块。
- demo 前端可以复用现有组件或类型的只读导入，但新增文件仍放在 demo/frontend。
- 不复制 schemas；按仓库根目录解析并调用现有 require/validator。
- demo/runtime 只能保存本地运行产物，必须被 Git 忽略。
- 任何写入目标都先解析绝对路径并验证仍在 demo/runtime 内。

## 3. 组合根

Demo 入口负责显式创建并注入下列对象：

1. SQLite engine 与现有 Alembic migrations。
2. Snapshot、ScheduleVersion、Publication、Audit、ExecutionEvent、ReplanRequest、Checkpoint、Lineage 和 ReplanAudit 的 SQLAlchemy repository。
3. 实际 workspace handlers，包装为 RoutedPlanningWorkspaceApplication。
4. 实际 dynamic replanning handlers，包装为 RoutedDynamicReplanningApplication。
5. SimulationLocalAuthorizationProvider。
6. DemoOrchestrator、JobRepository、ArtifactRepository 和 PresentationQueryService。
7. 现有 create_app 返回的 FastAPI 应用，再挂载 /api/demo/v1 router 和静态前端。

默认 backend/app/api/app.py 和 frontend/src/main.tsx 保持不变。Demo 通过自己的启动命令进入，不靠环境变量把产品默认入口从 fail-closed 改为可写。

## 4. 数据库与重置

### 4.1 两层存储

control.db 保存跨 run 的轻量控制状态：

- active_run_id；
- run 创建时间、scenario、seed、状态和数据库相对路径；
- job 状态、阶段、错误码与关联 run；
- command idempotency key 与结果引用。

每个 run 的 plantnexus.db 保存：

- 现有核心迁移创建的表；
- demo_artifacts：初排和展示所需的规范 JSON、document_version、artifact_id、fingerprint；
- demo_scenario_manifest：数据计数、资产 hash、生成器版本和环境证据；
- demo_command_audit：业务表单原始规范值、route_template_id 与正式事件引用。

核心 append-only 数据与演示辅助数据保持逻辑分离；辅助表不能替代正式仓储。

### 4.2 重置协议

POST resets 的 job 执行：

1. 获取全局 reset lock。
2. 确认没有 RUNNING 或 CANCELLING job。
3. 在 demo/runtime/runs 下创建新的 run 目录和数据库。
4. 运行现有迁移，再运行 demo 自有迁移。
5. 写入 scenario manifest，并执行生成器与标准导入。
6. 重新打开并读取关键计数、指纹，做启动后自检。
7. 在 control.db 事务中切换 active_run_id。
8. 保留最近 3 个非活动 run；更老 run 通过显式、路径验证后的清理 job 删除。

失败时不切换 active run，当前演示仍可使用。不能通过 DELETE 清空当前核心表来模拟重置。

## 5. Simulation 授权

Demo 只监听 127.0.0.1，默认不允许局域网访问。启动时生成或读取本地非生产 token，前端从同源 bootstrap 获得短期会话；token 不写入日志和 Git。

授权 provider 固定返回：

- actor_ref：actor:cnc-demo-presenter；
- data_plane：SIMULATION；
- environment：DEVELOPMENT 或 TEST；
- production_binding：false；
- policy/version：demo-local-simulation-auth.v1；
- 仅演示所需的 factory、planning scope 与 capability。

所有现有 API 仍经过正式 capability/scope 检查。Demo router 也逐命令检查能力，不能因为监听本机而跳过授权。响应和 job 错误只返回稳定错误码与消毒后的消息。

这是一套本地演示身份，不是生产认证方案。

TASK-DEMO-08 实施证据（2026-09-04）：启动入口只接受小写字母、数字和连字符组成的具名 runtime id，并解析为 `demo/runtime` 的直接子目录；任意数据库路径、绝对路径、`..`、分隔符和超长名称均被拒绝。后端/Vite 只监听 loopback。错误 token、缺 capability、错误 scope、非 loopback 会话和 Production binding 全部返回消毒后的拒绝，不产生业务写入；session token 未进入 HTTP 正文、服务日志、control.db、仓库或浏览器证据。

## 6. Job 模型与进度

采用数据库持久化、进程内执行器、最大并发 1 的 job runner。API 请求只负责校验、幂等登记并返回 202；后台线程执行 CPU/IO 工作，不阻塞事件循环。

重启恢复规则：

- QUEUED 以原 job identity 重新入队；
- 遗留 RUNNING 或 CANCELLING 在进程启动时标记为 INTERRUPTED；
- INTERRUPTED 只允许从记录的安全边界以同一 job/idempotency identity 显式重试，并增加 attempt；
- 已经提交的 append-only 写操作依赖原幂等键重放，不能生成新 identity；
- 用户可以查看错误并点击重试，不显示假成功。

TASK-DEMO-08 已用重启 replay 证明遗留执行任务先持久化为 `INTERRUPTED / PROCESS_INTERRUPTED`，随后以同一 job identity 成功完成 attempt 2；不会自动生成新命令或把中断伪装为成功。并发 reset 恰有一个 `ACCEPTED` 和一个 `ACTIVE_JOB_CONFLICT`，数据库只登记一个 durable job；在 active-run 切换前注入的 reset 失败保留旧 active run。

通用 job 状态：

- QUEUED；
- RUNNING；
- SUCCEEDED；
- FAILED；
- INTERRUPTED；
- CANCELLING；
- CANCELLED。

初始排产真实阶段：

1. GENERATING；
2. STAGING；
3. NORMALIZING；
4. VALIDATING_DATA；
5. SNAPSHOTTING；
6. BUILDING_PROBLEM；
7. SOLVING；
8. VERIFYING_SOLUTION；
9. PERSISTING_VERSION；
10. COMPLETE。

加急重排真实阶段：

1. PREPARING_IMPORT；
2. IMPORTING_URGENT_DEMAND；
3. APPENDING_EVENT；
4. PROJECTING_FACTS；
5. CREATING_REQUEST；
6. SOLVING；
7. VERIFYING_SOLUTION；
8. COMMITTING_RESULT；
9. BUILDING_PRESENTATION；
10. COMPLETE。

阶段具有 started_at、finished_at、elapsed_seconds 和可选 evidence_ref。SOLVING 只展示经过时间和求解上限，不展示百分比。取消只在现有求解/重排取消边界支持时提供；不能把前端按钮等同于任意时刻强杀。

## 7. 初始排产编排

### 7.1 输入

- 当前 active run；
- scenario manifest；
- 固定 priority facts；
- problem builder version；
- 300 秒 tick；
- 固定 horizon；
- versioned solve limits；
- code commit 与环境证据；
- idempotency key。

### 7.2 标准链路

1. CNC 生成器产生 StagedImportBatch。
2. DemoIngressPipeline 复用正式 mapping、normalization、Data Validation、Expansion 与 Snapshot 公开边界，并显式调用 v2 Problem builder；根 CommonIngressPipeline 默认生成 v1 Problem，因此不作为最终 v2 facade。
3. 规范记录提交到 Snapshot repository。
4. build_planning_problem_v2 注入 priority facts、时钟、horizon 和 tick。
5. GlobalCpSatStrategy 运行预检、CP-SAT 和独立 Validator。
6. 只有存在 candidate 且 Validator PASS 时计算 KPI。
7. ValidatedSolutionToScheduleVersionService.create_reviewable 原子写入 DRAFT→READY_FOR_REVIEW 与审计。
8. demo_artifacts 保存 Snapshot、Problem、Solution、SolverReport、Validation、ImportQuality 和 KPI 的精确副本与指纹。
9. PresentationQueryService 构建缓存；缓存可丢弃重建，规范 artifact 不可变。

任何数据校验或 Validator 失败都阻止版本创建。

### 7.3 仿真基线激活

POST baseline-activations 必须携带当前 READY_FOR_REVIEW 的 version id、content fingerprint 和显式 confirmation。服务端按现有状态机：

1. 重新读取并比较期望版本与 revision；
2. 执行批准；
3. 执行发布到 SIMULATION_INTERNAL；
4. 校验 Publication current reference；
5. 写入 demo command audit。

该命令不重新求解。重复同一 idempotency key 返回原结果；不同输入复用同一 key 返回冲突。

## 8. 加急重排编排

1. 接收业务化 UrgentOrderCommand，并验证 expected_base_version_id 仍是当前 PUBLISHED。
2. 规范化表单、锁定 active run、计算 command fingerprint。
3. 展开路线模板，调用标准导入链验证加急候选。
4. 提交新增 demand/order/lot/operation/routing 记录。
5. 构造并验证精确 execution-event.v1，再追加 URGENT_DEMAND_RECEIVED。
6. 通过现有事件 authority、stream 和 checkpoint 投影新事实。
7. 创建包含当前 PUBLISHED 基线、新 Snapshot 和事件范围的严格 ReplanRequest。
8. 使用 Simulation 900 秒冻结策略与单 worker solve limits 调用 ReplanApplicationService。
9. 使用真实 candidate 构建 after KPI，并由服务再次核对。
10. 只有 Validator、KPI 和 ChangeReport 交叉验证通过，才原子提交 schedule-version.v2 DRAFT 及 lineage。
11. 生成 presentation DTO，把 UI 自动导航到新 DRAFT 比较页。

重排目标严格沿用现有六轮顺序，不在 Demo 中重新加权：OBJ-001 交付目标 → OBJ-002.1 软锁违反数 → OBJ-002.2 发生变化的既有工序数 → OBJ-002.3 设备变更数 → OBJ-002.4 绝对开始时间偏移总秒数 → OBJ-003 makespan。后续轮次必须固定前序轮次已取得的目标值。

现有 [disruption_replay_check.py](../../backend/app/simulation/scenarios/disruption_replay_check.py#L400)已经展示了用真实重排 candidate 捕获 after KPI 的测试型适配方式。Demo 需要在 demo/backend 中实现有独立单元与集成测试的等价 adapter，不能提交占位 KPI，也不能修改正式 ReplanApplicationInput 契约。

TASK-DEMO-03 实施注记（2026-09-02）：上述第 1～10 步和 `POST /urgent-orders` 已落地。根 `project_effective_locks` 会把 Snapshot 中基线前历史 completed 事实带入 projection，但版本比较 universe 只包含基线 active assignments；Demo 保留 Snapshot 历史 tuple 原字节，并在单 worker 的单次正式服务调用范围内把 effective-lock completed comparison view 收窄为 base→new 实际移除集合。该兼容层不修改正式 projector 或 Validator。当前一个 deterministic run 只允许提交一个不同加急事件；同命令可精确重放，连续多次不同插单需在后续设计中明确 DRAFT/基线链式语义。

TASK-DEMO-07 实施注记（2026-09-04）：第 11 步现已闭合。`GET /bootstrap` 从批准资产提供四个路线模板和三类优先级，并在 durable 重排成功后恢复精确的 before/after/ChangeReport 引用；中文前端只提交业务字段，自动绑定 active run 与 current `PUBLISHED`，持久化原命令及幂等键，并复用 job polling。成功后严格解析 `DemoComparisonView v1` 并自动进入 v2 `DRAFT` 比较；刷新只重读同一引用，不重放写命令。比较筛选与 120 条分页均由服务端执行，浏览器不推导 ChangeReport 分类、KPI 或稳定性，也不批准、发布或替换 current Publication。

## 9. 版本统一展示模型

### 9.1 问题

现有 P3 workspace 契约固定解析 schedule-version.v1 与 solver-report.v1；P4 重排结果是 schedule-version.v2 与对应重排报告。直接把 v2 ID 传给原工作台会产生契约错误，而不是自动升级。

### 9.2 解决方案

Demo 在服务端生成非权威、不可发布的 DemoScheduleView v1：

- version：ID、schema version、state、parent、created_at；
- solver：status、limit、objective、best bound、wall time；
- validation：PASS/FAIL、validator version、fingerprint；
- orders：订单级交期、计划完工、延期秒数、priority；
- assignments：operation、resource、workshop、start、end、state、lock/freeze；
- resources：日历、维护和计划负荷；
- kpis：从规范 KPI 投影，不在浏览器重算；
- provenance：Snapshot、Problem、Schedule、KPI、Validation 指纹；
- publishable：固定 false。

DemoComparisonView v1 包含：

- before 与 after 的版本引用；
- ChangeReport 引用和验证状态；
- 每道工序的 before/after assignment；
- change_class：UNCHANGED、CHANGED、ADDED、REMOVED_BY_FACT；
- resource_changed、start_shift_seconds、end_shift_seconds；
- 交付 KPI 前后值和差值；
- 稳定性向量与受影响订单；
- 只显示变更的默认过滤结果。

变更分类由 ChangeReport 决定；浏览器不得按浮点或显示时区自行推导。若 ScheduleVersion、KPI、Validator 或 ChangeReport 指纹不一致，presentation 构建失败并阻止自动跳转。

### 9.3 TASK-DEMO-04 实现约束

三个 Demo-local response contract 已冻结为 `cnc-demo-factory-view.v1`、`cnc-demo-schedule-view.v1` 和 `cnc-demo-comparison-view.v1`。所有对象均采用 strict、frozen、`extra=forbid` 模型，OpenAPI 根 schema 为 `additionalProperties=false`；它们只是已提交事实的只读投影，不是新的排产、验证或发布 authority。

- Factory 从 approved asset pack 和规范 Snapshot 投影工厂、3 个车间、产线、设备组、设备、班次不可用区间与维护事件。
- Schedule v1/v2 共用一个 DTO；订单交期指标只读规范 KPI，资源负荷按 `planned_busy_seconds / available_seconds` 计算并携带 Problem evidence，浏览器不重算 KPI。
- Comparison 先通过正式 `ChangeReportQueryService` 校验 lineage，再把报告中的 `UNCHANGED`、`CHANGED`、`ADDED`、`REMOVED_BY_FACT` 原样投影；分类和 operation universe 不在 Demo 层推测。
- 每个 artifact 都校验 document version、artifact ID、语义 fingerprint 与跨 artifact lineage；缺项或冲突整体 fail closed，不返回“部分可信”页面。
- authoritative 时间比较统一使用 UTC；`Asia/Shanghai` local time 与 UTC 成对输出。同一工序在 v1/v2 的相同时间与设备保持字节级一致的展示语义。
- assignments/operations 最大页长为 500；过滤后按稳定复合键排序再分页。时间窗口采用半开区间，任务 `[start,end)` 与查询 `[start_at,end_at)` 相交才返回。
- `view_fingerprint` 覆盖规范化查询和完整响应语义，但不包含每次请求变化的 correlation ID；HTTP ETag 因而可稳定重验。

## 10. Demo API

统一前缀：/api/demo/v1。所有写请求必须带 Idempotency-Key；所有响应通过 `X-Correlation-Id` 和 `X-Demo-Active-Run` headers 关联请求与活动 run。命令/state 响应可同时在正文携带这两个字段；immutable presentation DTO 不混入易变请求元数据。

| 方法与路径 | 用途 | 成功结果 |
|---|---|---|
| GET /bootstrap | 首页一次性获取场景、活动 run、当前版本和活动 job | 200 DemoBootstrap |
| GET /state | 轻量轮询当前故事状态 | 200 DemoState |
| POST /resets | 新建并切换固定种子 run | 202 JobAccepted |
| POST /initial-plans | 运行初始排产 | 202 JobAccepted |
| POST /baseline-activations | 显式批准并发布仿真基线 | 200 BaselineActivation |
| POST /urgent-orders | 导入加急订单并重排 | 202 JobAccepted |
| GET /jobs/{job_id} | 读取 job 阶段、计时、终态和结果引用 | 200 DemoJob |
| POST /jobs/{job_id}/retries | 对可恢复失败做同输入重试 | 202 JobAccepted |
| GET /factory | 工厂、车间、设备、日历与维护 | 200 DemoFactoryView |
| GET /versions/{version_id} | 统一 v1/v2 排程展示 | 200 DemoScheduleView |
| GET /comparisons/{request_id} | 新旧版本、ChangeReport 和稳定性展示 | 200 DemoComparisonView |

### 10.1 初始排产命令

请求只需要 expected_run_id。seed、horizon、limits 和策略由活动 scenario manifest 取得，避免浏览器篡改。

### 10.2 基线激活命令

请求字段：

- expected_run_id；
- schedule_version_id；
- content_fingerprint；
- expected_state_revision；
- confirmation 固定为 ACTIVATE_SIMULATION_BASELINE。

### 10.3 加急订单命令

请求字段：

- expected_run_id；
- expected_base_version_id；
- route_template_id；
- quantity；
- due_at_local；
- priority_class；
- note。

factory、scope、authority、stream、position、request fingerprint 和 attempt identity 全部由服务端当前状态派生，不让演示人员手输。

### 10.4 D16 浏览器与服务恢复约束

- 浏览器接受 durable job 后立即保存 job id/kind；刷新优先恢复服务端 active job，否则按本地 pending identity 查询同一 job，不创建新写命令。
- reset、initial plan、activation 和 urgent mutation 均有同步 in-flight 防重入；真实浏览器双击只观察到一次对应 POST。
- 对话框以共享 focus trap 管理初始焦点、Tab/Shift+Tab、Escape 和触发控件焦点恢复；表单错误通过 `aria-invalid` 与 `aria-describedby` 关联并聚焦首个无效字段。
- 当前 tablist 的每个 `aria-controls` 都指向常驻 DOM 的对应 tabpanel；非活动 panel 使用 `hidden`，避免悬空 ARIA 引用。
- D16 没有开放通用 manual retry/cancel API，也没有改变 `PUBLISHED`/`DRAFT` 生命周期；中断恢复由已有相同命令身份的显式重试路径完成。

### 10.5 展示读取查询

- `/versions/{version_id}`：`resource_id`、`workshop_id`、`demand_order_id`、`state` 可重复或逗号分隔；`start_at_utc`、`end_at_utc`、`sort`、`offset`、`limit` 为标量。排序支持 `START_ASC`、`RESOURCE_START_ASC`、`ORDER_START_ASC`。
- `/comparisons/{request_id}`：支持 `classification`、resource/workshop/order、UTC window、offset/limit；排序支持 `OPERATION_ASC`、`SHIFT_DESC`、`START_ASC`。未指定分类时只返回 `ADDED + CHANGED`。
- 集合查询在服务端规范化为排序后的唯一值；空值、重复值、未知参数、重复标量、逆序窗口、越界分页和未知枚举统一返回 `INVALID_PRESENTATION_QUERY`。
- 成功读取返回基于 `view_fingerprint` 的强 ETag；匹配 `If-None-Match` 时返回 304 和相同关联 headers。cache policy 为 private revalidation。
- 版本和 request 不存在返回 `PRESENTATION_NOT_FOUND`；artifact/lineage 不一致返回稳定的 presentation 错误且不泄漏内部路径、token 或原始异常。

### 10.6 错误语义

稳定错误至少包括：

- DEMO_NOT_INITIALIZED；
- ACTIVE_JOB_CONFLICT；
- STALE_RUN；
- STALE_BASE_VERSION；
- INVALID_URGENT_ORDER；
- IMPORT_VALIDATION_FAILED；
- SOLVER_NO_CANDIDATE；
- SOLVER_INFEASIBLE；
- SOLUTION_VALIDATION_FAILED；
- CHANGE_REPORT_INVALID；
- BASELINE_STATE_CONFLICT；
- PRESENTATION_NOT_FOUND；
- PRESENTATION_LINEAGE_MISMATCH；
- INVALID_PRESENTATION_QUERY；
- PERSISTENCE_FAILED。

UNKNOWN 且没有 candidate 映射为 SOLVER_NO_CANDIDATE，不得映射为 INFEASIBLE。

## 11. 状态机

### 11.1 故事状态

    EMPTY
      → INITIALIZED
      → INITIAL_PLAN_RUNNING
      → READY_FOR_REVIEW
      → BASELINE_PUBLISHED
      → REPLAN_RUNNING
      → DRAFT_COMPARISON_READY

失败不推进故事状态。用户修正或重试后从最后一个已提交状态继续。

### 11.2 并发规则

- 一个 active run 同时最多一个 mutating job。
- presentation 查询可与 job 并发，但只读取已提交 artifact。
- reset 与任何其他 job 互斥。
- urgent command 使用 expected base version 做 CAS。
- 基线发布期间不接受 urgent command。
- 新 DRAFT 不替换 current PUBLISHED；再次插单默认仍基于 current PUBLISHED，除非后续明确设计 DRAFT 审批流程。

## 12. 可观测性

每个 job 记录：

- correlation_id、idempotency fingerprint、run_id；
- scenario、seed、代码 commit；
- Python、OR-Tools、OS、CPU 摘要；
- 每阶段耗时；
- problem 规模、模型变量/约束摘要与最大内存；
- solver status、objective、best bound、gap；
- Validator 与 ChangeReport 指纹；
- 所有版本、Snapshot、事件和请求引用。

日志禁止记录 token、完整 note 或未消毒异常。页面提供“复制诊断摘要”，但只包含允许公开的合成数据标识和错误码。

## 13. 启动与打包

最终目标是仓库根目录的一条跨平台友好命令启动 Demo，但实际脚本位于 demo/scripts。启动检查顺序：

1. Python 与 Node 依赖；
2. runtime 目录权限；
3. 迁移版本；
4. schema 路径与必要资产 hash；
5. 本地端口；
6. 后端 health；
7. 前端静态资源。

默认打开本地浏览器到 /demo。不得自动暴露公网端口、自动下载未锁定依赖或修改根项目配置。
