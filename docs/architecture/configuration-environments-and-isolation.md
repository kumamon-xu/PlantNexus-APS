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

这些是 contract/precheck 证据，不是独立 Database、权限、Simulation API 404、发布/导出 guard 或 Production deployment 证据；相关 infrastructure/API 行为仍为 TASK-P0-08/P1+ `PLANNED`，RISK-007 继续 `MONITORED`。
