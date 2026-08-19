---
doc_id: DOC-ARCH-008
title: 配置、环境与数据隔离
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [16, 38, 49, 62, 64, 95, 96]
last_reviewed: 2026-08-19
---

# 配置、环境与数据隔离

## 配置层

| 层 | 示例 | 是否可覆盖业务规则 |
|---|---|---|
| System Config | 服务地址、队列、日志、数据库 | 否 |
| Simulation Config | Profile、seed、故障概率 | 只在 Simulation |
| Business Policy | 优先级、锁定、目标语义 | 由业务权威确认 |
| Solver Limits | 时间、线程、内存预算 | 不能改变约束语义 |

Simulation Config 永远不能覆盖 Production Business Policy。

## 环境

- Development：允许开发工具和显式 synthetic run。
- Test：允许确定性 Fixture、Contract、Property 和 Mutation tests。
- Benchmark：允许版本化 Profile 和专用性能采集。
- Production：Simulation API 默认 disabled；仅接受生产授权来源。

## 数据隔离

Production 和 Simulation 至少独立 Database，推荐 `aps_dev`、`aps_sim`、`aps_prod`。Snapshot 必须带 `synthetic` 标识，跨环境导入和发布需显式拒绝 synthetic 数据。

## 时间与 Secret

数据库时间为 UTC `TIMESTAMPTZ`，显示使用 factory timezone。生产 timezone 未确认时阻止生产操作而非阻止开发启动。Secret 只能通过环境/Secret Manager 注入，禁止进入文档示例的真实值、仓库、日志或导出。

## P0 Simulation isolation contract

FactoryProfile/ScenarioSpec Schema 强制 `synthetic_only=true`，ScenarioManifest 强制 `synthetic=true` 且 `target_environment` 只接受 `development/test/benchmark`。pure `GenerationContext.create` 对字符串 `production` 显式返回 `SYNTHETIC_REFERENCE_IN_PRODUCTION`；Generator 输出的 Standard Import envelope 同样必须 `synthetic=true` 并携带 `scenario_id`。

这些 Schema/pure precheck 证据不是发布/导出 guard 或 Production deployment 证据。

## TASK-P0-08 executable configuration boundary

`Settings` 只读取显式构造参数与 `PLANTNEXUS_*` environment；应用不会隐式读取 `.env`，`.env.example` 只供 Compose/local copy 且含非生产 placeholder。配置层包含 runtime environment、data plane、endpoint Secret、日志/trace context、health timeout 与 job heartbeat/lease；不包含 Business Policy、Solver Limits 或 synthetic Profile 数值。

Production fail-closed rules：runtime=`production` 必须同时 data plane=`production`、Database 必须是 PostgreSQL、Simulation API 必须 false、code commit 必须为 40 字符 SHA；production/runtime mismatch、lease≤heartbeat 或不受支持 URL/level 均在建立 client 前拒绝。Secret 使用 `SecretStr` 且不出现在 `safe_summary`、health 或 machine report。

本地 Compose 明确固定 development data plane，并提供 PostgreSQL/Redis 独立服务；它没有创建/验证 aps_sim 与 aps_prod、权限、backup 或 Production deployment，不能据此声称已满足生产隔离。P0-08 health-only app 没有 Simulation route，因此 Production Simulation API 是“未注册 + fail-closed config”边界；P1+ 的共同 ingress、publish/export synthetic guard 和真实独立 Database evidence 仍 `PLANNED`，RISK-007 继续 `MONITORED`。

## TASK-P0-10 GitHub CI boundary

workflow handoff 只更换当前 Task 的 diff/report 引用和 evidence artifact 名称，不改变 runtime environment、data plane、Database/Redis endpoint 或 Simulation/Production guard。GitHub Actions 仍仅有 `contents: read`；CI 中的 PostgreSQL password 是明确标记的 contract-only 非生产值，本 Task 不新增 repository Secret。

Actions run/artifact 允许通过公开 GitHub REST 读取；branch-protection 查询/设置如需认证，只能使用进程外短期 credential 或已认证 GitHub session，不得写入命令记录、文档、日志、artifact 或 repository。这是 CI 治理边界，不是 Production deployment/Secret Manager evidence。
