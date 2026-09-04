---
doc_id: DOC-CONTRACT-013
title: 数据字段中文名称字典
status: living
spec_version: 0.3.0
phase: P1-P7
normative: false
source_sections: [17, 18, 19, 20, 21, 22, 38, 39]
last_reviewed: 2026-09-02
---

# 数据字段中文名称字典

本字典完整覆盖当前 `canonical-records.v1` 的根集合、16 类核心业务记录以及两个共享嵌套对象，用于开发、评审和 UI 展示。英文 JSON key、类型、必填条件和取值约束以 [canonical-records.v1 Schema](../../schemas/json/canonical-records.v1.schema.json)为权威；全局文档版本、兼容性和 artifact 路径以[机器数据字典](../../schemas/data_dictionary.yaml)和 [Schema 索引](schema-index.md)为权威。

中文名称不是 wire key。API、文件、数据库交换载体、fingerprint projection、enum 和 operationId 继续使用英文机器值，不得发送中文 key 或自行翻译枚举。

## 通用规则

| 规则 | 约束 |
|---|---|
| ID | 非空、无空白和控制字符的字符串，最长 256 字符 |
| 时间 | RFC 3339 UTC，字符串以 `Z` 结尾 |
| 时长 | 整数秒；不同字段允许 `>= 0` 或要求 `>= 1` |
| 数量 | 大于 0 的 number；不能使用 boolean |
| 未知字段 | 所有 canonical record 都拒绝未知字段 |
| 业务默认值 | 禁止隐式补齐；缺失 authority 字段必须拒绝或进入数据质量错误 |
| 来源 | 每条 canonical record 都必须带 `source`，保存来源系统、版本和来源记录 ID |

## 根对象与集合

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `canonical_records_version` | 标准记录版本 | const | 是 | 固定为 `canonical-records.v1` |
| `factories` | 工厂集合 | array | 是 | Factory 记录 |
| `workshops` | 车间集合 | array | 是 | Workshop 记录 |
| `production_lines` | 产线集合 | array | 是 | ProductionLine 记录 |
| `resource_groups` | 资源组集合 | array | 是 | ResourceGroup 记录 |
| `resources` | 资源集合 | array | 是 | 主资源/设备记录 |
| `calendars` | 日历集合 | array | 是 | 资源可用性日历 |
| `products` | 产品集合 | array | 是 | Product 记录 |
| `routing_versions` | 工艺路线版本集合 | array | 是 | RoutingVersion 记录 |
| `routing_operations` | 工艺工序集合 | array | 是 | RoutingOperation 记录 |
| `routing_precedence_edges` | 工序前后关系集合 | array | 是 | 工艺 DAG 的有向边 |
| `routing_resource_options` | 工序资源选项集合 | array | 是 | 工序可选资源与标准工时 |
| `demand_orders` | 需求订单集合 | array | 是 | 客户/需求侧订单 |
| `production_orders` | 生产订单集合 | array | 是 | 可执行生产订单 |
| `production_lots` | 生产批次集合 | array | 是 | 显式拆分后的批次 |
| `execution_facts` | 执行事实集合 | array | 是 | 运行中或已完成事实 |
| `operation_locks` | 工序锁集合 | array | 是 | HARD/SOFT 计划锁 |

## 共享嵌套对象

### SourceReference — 来源引用

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `source_system` | 来源系统 | string | 是 | ERP、MES、WMS、人工文件等 authority 名称 |
| `source_version` | 来源版本 | string | 是 | 源快照、接口、文件或映射版本 |
| `source_record_id` | 来源记录 ID | string | 是 | 来源系统中的稳定记录标识 |

### UnavailableInterval — 不可用时段

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `interval_id` | 时段 ID | string | 是 | 不可用区间稳定标识 |
| `start_at_utc` | 开始时间（UTC） | datetime | 是 | 半开区间起点 |
| `end_at_utc` | 结束时间（UTC） | datetime | 是 | 半开区间终点 |
| `reason` | 不可用原因 | string | 是 | 维护、停机等来源事实；不是自由推断默认值 |

## 工厂与资源

### Factory — 工厂

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `factory_id` | 工厂 ID | string | 是 | 标准化稳定标识 |
| `factory_code` | 工厂编码 | string | 是 | 业务编码 |
| `factory_timezone` | 工厂时区 | string | 是 | 工厂业务时区标识 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### Workshop — 车间

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `workshop_id` | 车间 ID | string | 是 | 标准化稳定标识 |
| `workshop_code` | 车间编码 | string | 是 | 业务编码 |
| `factory_id` | 所属工厂 ID | string | 是 | 引用 Factory |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### ProductionLine — 生产线

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `production_line_id` | 产线 ID | string | 是 | 标准化稳定标识 |
| `production_line_code` | 产线编码 | string | 是 | 业务编码 |
| `workshop_id` | 所属车间 ID | string | 是 | 引用 Workshop |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### ResourceGroup — 资源组

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `resource_group_id` | 资源组 ID | string | 是 | 标准化稳定标识 |
| `resource_group_code` | 资源组编码 | string | 是 | 业务编码 |
| `production_line_id` | 所属产线 ID | string | 是 | 引用 ProductionLine |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### Resource — 资源/设备

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `resource_id` | 资源 ID | string | 是 | 设备或主资源稳定标识 |
| `resource_code` | 资源编码 | string | 是 | 业务编码 |
| `resource_type` | 资源类型 | string | 是 | 类型值由权威映射提供 |
| `status` | 资源状态 | string | 是 | 状态值由权威来源提供；Schema 不猜枚举 |
| `resource_group_id` | 所属资源组 ID | string | 是 | 引用 ResourceGroup |
| `calendar_id` | 日历 ID | string | 是 | 引用 Calendar |
| `capabilities` | 能力集合 | array<string> | 是 | 至少一项、去重；用于工序资源匹配 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### Calendar — 日历

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `calendar_id` | 日历 ID | string | 是 | 稳定标识 |
| `timezone` | 日历时区 | string | 是 | 日历解释时区 |
| `unavailable_intervals` | 不可用时段集合 | array<object> | 是 | 可为空；每项见 UnavailableInterval |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

## 产品与工艺

### Product — 产品

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `product_id` | 产品 ID | string | 是 | 标准化稳定标识 |
| `product_code` | 产品编码 | string | 是 | 业务编码 |
| `quantity_unit` | 数量单位 | string | 是 | 显式单位，不允许隐式默认 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### RoutingVersion — 工艺路线版本

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `routing_version_id` | 工艺路线版本 ID | string | 是 | 稳定标识 |
| `routing_code` | 工艺路线编码 | string | 是 | 业务编码 |
| `version` | 工艺版本号 | string | 是 | 来源侧明确版本 |
| `product_id` | 产品 ID | string | 是 | 引用 Product |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### RoutingOperation — 工艺工序

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `routing_operation_id` | 工艺工序 ID | string | 是 | 工艺模板中的稳定工序标识 |
| `routing_version_id` | 工艺路线版本 ID | string | 是 | 引用 RoutingVersion |
| `operation_code` | 工序编码 | string | 是 | 业务工序编码 |
| `required_capabilities` | 所需能力集合 | array<string> | 是 | 至少一项、去重 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### RoutingPrecedenceEdge — 工序前后关系

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `routing_precedence_edge_id` | 前后关系 ID | string | 是 | DAG 边稳定标识 |
| `routing_version_id` | 工艺路线版本 ID | string | 是 | 引用 RoutingVersion |
| `predecessor_routing_operation_id` | 前置工序 ID | string | 是 | 引用 RoutingOperation |
| `successor_routing_operation_id` | 后继工序 ID | string | 是 | 引用 RoutingOperation |
| `min_lag_seconds` | 最小间隔秒数 | integer >= 0 | 是 | 前后工序的最小 lag |
| `max_lag_seconds` | 最大间隔秒数 | integer >= 0 | 否 | 存在时约束最大 lag |
| `transport_lag_seconds` | 转运时间秒数 | integer >= 0 | 是 | 明确的跨工序运输/等待时间 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### RoutingResourceOption — 工序资源选项

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `routing_resource_option_id` | 工序资源选项 ID | string | 是 | 候选资源与工时组合的稳定标识 |
| `routing_operation_id` | 工艺工序 ID | string | 是 | 引用 RoutingOperation |
| `resource_id` | 候选资源 ID | string | 是 | 引用 Resource |
| `quantity_unit` | 数量单位 | string | 是 | 与工时计算对应的显式单位 |
| `setup_seconds` | 准备时间（秒） | integer >= 0 | 是 | 固定准备时间；不是序列相关换型矩阵 |
| `cycle_seconds_per_unit` | 单件节拍（秒/单位） | integer >= 0 | 是 | 每单位加工时间 |
| `final_duration_seconds` | 最终标准工时（秒） | integer >= 1 | 是 | 该资源选项用于计划的权威时长 |
| `duration_source` | 工时来源 | string | 是 | 标准工时来源名称 |
| `duration_source_version` | 工时来源版本 | string | 是 | 来源快照/规则版本 |
| `source` | 来源引用 | object | 是 | 记录本身的来源引用 |

## 订单与批次

### DemandOrder — 需求订单

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `demand_order_id` | 需求订单 ID | string | 是 | 需求侧稳定标识 |
| `product_id` | 产品 ID | string | 是 | 引用 Product |
| `quantity` | 需求数量 | number > 0 | 是 | 显式数量 |
| `quantity_unit` | 数量单位 | string | 是 | 与 Product/订单一致的权威单位 |
| `due_at_utc` | 交期（UTC） | datetime | 是 | 需求交付时间 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### ProductionOrder — 生产订单

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `production_order_id` | 生产订单 ID | string | 是 | 可执行订单稳定标识 |
| `demand_order_id` | 需求订单 ID | string | 是 | 引用 DemandOrder |
| `routing_version_id` | 工艺路线版本 ID | string | 是 | 指定不可变工艺版本 |
| `quantity` | 生产数量 | number > 0 | 是 | 显式数量 |
| `quantity_unit` | 数量单位 | string | 是 | 不允许隐式换算 |
| `release_at_utc` | 最早释放时间（UTC） | datetime | 是 | 订单可开始进入计划的时间门 |
| `material_ready_at_utc` | 物料齐套时间（UTC） | datetime | 是 | 物料可用时间门 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### ProductionLot — 生产批次

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `production_lot_id` | 生产批次 ID | string | 是 | 显式批次稳定标识 |
| `production_order_id` | 生产订单 ID | string | 是 | 引用 ProductionOrder |
| `quantity` | 批次数量 | number > 0 | 是 | 不能由排程器私自拆批 |
| `quantity_unit` | 数量单位 | string | 是 | 与生产订单保持可核对 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

## 执行事实与锁

### ExecutionFact — 执行事实

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `execution_fact_id` | 执行事实 ID | string | 是 | 稳定事实标识 |
| `production_lot_id` | 生产批次 ID | string | 是 | 引用 ProductionLot |
| `routing_operation_id` | 工艺工序 ID | string | 是 | 引用 RoutingOperation |
| `status` | 执行状态 | enum | 是 | `RUNNING` 或 `COMPLETED` |
| `observed_at_utc` | 事实观察时间（UTC） | datetime | 是 | authority 观察时间 |
| `resource_id` | 实际资源 ID | string | 条件必填 | RUNNING/COMPLETED 均要求 |
| `actual_start_at_utc` | 实际开始时间（UTC） | datetime | 条件必填 | RUNNING/COMPLETED 均要求 |
| `actual_end_at_utc` | 实际结束时间（UTC） | datetime | COMPLETED | RUNNING 时禁止 |
| `completed_quantity` | 已完成数量 | number > 0 | COMPLETED | RUNNING 时禁止 |
| `remaining_quantity` | 剩余数量 | number > 0 | RUNNING | COMPLETED 时禁止 |
| `quantity_unit` | 数量单位 | string | 是 | 完成/剩余数量单位 |
| `remaining_seconds` | 剩余加工时间（秒） | integer >= 1 | RUNNING | COMPLETED 时禁止 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

### OperationLock — 工序锁

| Field | 中文名称 | Type | 必填 | 说明 |
|---|---|---|---|---|
| `lock_id` | 锁 ID | string | 是 | 稳定标识 |
| `production_lot_id` | 生产批次 ID | string | 是 | 引用 ProductionLot |
| `routing_operation_id` | 工艺工序 ID | string | 是 | 引用 RoutingOperation |
| `lock_type` | 锁类型 | enum | 是 | `HARD_LOCK` 或 `SOFT_LOCK` |
| `resource_id` | 锁定资源 ID | string | 是 | 引用 Resource |
| `start_at_utc` | 锁定开始时间（UTC） | datetime | 是 | 半开区间起点 |
| `end_at_utc` | 锁定结束时间（UTC） | datetime | 是 | 半开区间终点 |
| `source` | 来源引用 | object | 是 | 见 SourceReference |

## 常用跨文档字段

以下中文名用于阅读多个 Planning/API artifact；字段是否存在、是否必填及其精确类型必须回到对应 Schema。

| Field | 中文名称 | 常见文档 |
|---|---|---|
| `snapshot_id` | 计划快照 ID | PlanningSnapshot、PlanningProblem lineage |
| `snapshot_hash` | 计划快照哈希 | PlanningSnapshot |
| `problem_id` / `problem_hash` | 计划问题 ID / 哈希 | PlanningProblem、Solution、Report |
| `planning_run_id` | 计划运行 ID | PlanningRun、KPI、ScheduleVersion |
| `schedule_version_id` | 计划版本 ID | ScheduleVersion、Workspace、Export |
| `state` | 状态 | PlanningRun、ScheduleVersion、ExportJob；枚举按各自状态机解释 |
| `content_fingerprint` | 内容指纹 | ScheduleVersion 与 CAS 前置条件 |
| `validation_report_id` | 校验报告 ID | ScheduleVersion/KPI lineage |
| `solver_report_id` | 求解报告 ID | Solution/KPI/ScheduleVersion lineage |
| `event_id` | 执行事件 ID | ExecutionEvent |
| `request_id` | 重排请求 ID | ReplanRequest |
| `change_report_id` | 变更报告 ID | ChangeReport、replan result、export |
| `export_job_id` | 导出任务 ID | ExportJob |
| `correlation_id` | 关联追踪 ID | API、audit、event、command |
| `idempotency_key` | 幂等键 | command intent；持久化/audit 只保留安全引用 |
| `data_plane` | 数据平面 | `SIMULATION` 或 `PRODUCTION`；不允许隐式默认 |
| `environment` | 运行环境 | DEVELOPMENT/TEST/BENCHMARK/PRODUCTION 等合同值 |
| `production_binding` | 生产绑定标志 | Simulation artifact 必须为 `false` |

## P8 Headless machine carrier fields

以下字段由TASK-P8-02的set `2.10.0`新增。中文名称只用于阅读；英文key、required/nullable、enum与条件约束仍以对应Schema为唯一机器权威。

### CanonicalIngressRequest v1 — 标准入口请求

| Field | 中文名称 | 关键约束 |
|---|---|---|
| `canonical_ingress_request_version` | 标准入口请求版本 | 固定`canonical-ingress-request.v1` |
| `ingress_policy_version` | 入口策略版本 | 固定`canonical-ingress-policy.v1`，不代表HTTP实现 |
| `operation` | 操作意图 | 仅`CREATE_PLANNING_RUN` |
| `request_id` | 请求标识 | 仅关联，不进入业务request fingerprint |
| `correlation_id` | 关联追踪标识 | 仅追踪，不是authority |
| `idempotency_key` | 幂等键 | 16～128安全字符；result/run只扩散raw UTF-8 bytes的SHA-256 reference |
| `request_fingerprint` | 请求业务指纹 | 排除request/correlation/raw key/self，覆盖全部业务与authority内容 |
| `requested_scope` | 请求范围 | tenant/factory/planning/data-plane/environment；必须由服务端再求effective scope |
| `source_authority` | 来源权威与映射证明 | 每个record的collection/source/version须命中唯一binding；每个source/version只有一个mapping provenance，歧义或重复claim拒绝 |
| `planning_inputs` | 计划策略输入 | exact PlanningPolicy v1/v2及SolveLimits v1 artifact reference |
| `payload_fingerprint` | 标准载荷指纹 | `canonical-json.v1`下完整Import v2 payload指纹 |
| `payload` | 标准载荷 | 只能是strict `import-package.v2`，不能是vendor/raw/file envelope |

### CanonicalIngressResult v1 — 标准入口结果

| Field | 中文名称 | 关键约束 |
|---|---|---|
| `disposition` | 处理结果 | `ACCEPTED`或`REJECTED` |
| `side_effects` | 副作用结论 | accepted=`PLANNING_RUN_CREATED_OR_REPLAYED`；rejected=`NONE` |
| `idempotency` | 幂等结果 | CREATED/REPLAYED/CONFLICT/NOT_RECORDED；key reference可由raw key复核，server-context scope fingerprint对外opaque并与run逐字绑定 |
| `effective_scope` | 服务端有效范围 | accepted必填object；拒绝时可为null以避免泄漏；指纹为排除自身后的完整strict object SHA-256，业务字段不得扩大requested scope |
| `accepted` | 接受结果 | ingress/payload、Runtime resolution、CREATED PlanningRun和audit引用；拒绝时null |
| `rejection` | 拒绝错误 | strict `headless-error.v1`；接受时null |
| `runtime_resolution` | 运行组合解析 | 仅服务端写入Runtime/Core/SDK/Registry/Extension-set/Kit/Solver/Validator identity与fingerprint |
| `result_fingerprint` | 结果指纹 | 除自身外的完整result canonical projection |

### PlanningRun v1 — 计划运行生命周期

| Field | 中文名称 | 关键约束 |
|---|---|---|
| `planning_run_id` / `revision` | 计划运行标识 / 修订号 | revision从1开始且等于`last_transition.sequence + 1`；carrier是权威revision read model，不是DB row |
| `state` / `terminal` | 当前状态 / 是否终态 | 精确复用`state-machines.v1`；两者必须一致 |
| `allowed_actions` | 允许动作投影 | 非终态固定`READ,CANCEL`，终态固定`READ`；仍不替代authorization |
| `effective_scope` | 有效范围 | 与入口接受结果相同的server-owned scope/fingerprint |
| `ingress` | 入口lineage | 与request/result逐字绑定request、payload、ingress、idempotency key/scope指纹 |
| `runtime_resolution` | 运行组合解析 | API进程、Worker和attempt必须绑定同一resolution fingerprint |
| `inputs` | 不可变计划输入 | 与入口请求逐字一致的PlanningPolicy与SolveLimits引用 |
| `attempt` | 求解尝试证据 | BUILDING以后按状态需要；绑定同一Runtime resolution |
| `artifacts` | 阶段产物 | Quality→Snapshot→Problem→Solution/SolverReport→Validation→ScheduleVersion的nullable前缀 |
| `last_transition` | 最近状态转换 | from/to必须存在于既有31个PlanningRun pair；CREATED使用sequence 0/from null；时间必须等于`updated_at_utc` |
| `cancellation` / `error` | 取消 / 失败证据 | 仅相应终态允许；error tuple命中P8错误注册表 |
| `audit_references` | 审计引用集合 | 至少包含最近transition audit；存在cancellation时也必须包含其audit |
| `run_fingerprint` | 运行修订指纹 | 除自身外的完整revision canonical projection |

### HeadlessError v1 — Headless错误

`namespace`固定为`HEADLESS_RUNTIME`，`registry_version`固定为`headless-error-code-registry.v1`。`category`、`code`、`stage`、`retryability`与`action`是注册表中的不可拆分tuple；`message`、`pointer`、`entity_reference`与`expected_contract`只能保存sanitized诊断，不能包含credential、payload全文、SQL、stack或绝对artifact path。HTTP状态码不在本字段合同中，由TASK-P8-07另行映射。

## 维护方式

字段变化必须遵循以下顺序：

1. 修改或新增版本化 JSON Schema，并明确兼容分类；
2. 同步 `schemas/data_dictionary.yaml` 的 document registry；
3. 更新 producer、consumer、样例和正负合同测试；
4. 同步本字典的中文名称与解释；
5. 若字段进入 API，再同步 [API 接口开发清单](api-development-checklist.md)。

禁止只改中文文档而悄悄改变 wire 语义，也禁止为了中文展示修改英文 key、enum、状态或 fingerprint projection。
