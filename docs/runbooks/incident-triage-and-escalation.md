---
doc_id: DOC-RUNBOOK-P8-INCIDENT-001
title: Headless 事件分诊与升级
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [59, 60, 61, 62, 65, 66, 95, 101, 102, 103, 113, 114]
last_reviewed: 2026-09-07
---

# Headless 事件分诊与升级

TASK-P8-10把API、Worker、database、broker、Extension准入、backup/restore和golden signals汇总为统一工程分诊流程。本页只定义角色类型和停止条件；真实Production on-call姓名、联系方式、通知时限及SLA仍未批准。

## 触发条件

- 任一P8 alert firing；
- Runtime/release/composition/Extension fingerprint漂移；
- restore mismatch、backup corruption、secret疑似泄漏或sanitized evidence生成失败；
- traffic/errors/latency/saturation工程阈值需要复核。

## 影响与安全边界

先保护不可变业务状态和证据，再恢复服务。不得在报告中复制token、URL credential、canonical payload、SQL/stack或个人信息；不得删审计、改terminal state、放宽readiness或把工程阈值宣传为Production SLO。

## 前置权限

Operator能读取四份P8-10报告、health code、correlation/trace/runtime fingerprints和Compose状态。需要更高权限的数据库恢复、release promotion、安全事件或业务决策必须转给相应owner；当前没有Production incident commander权限。

## 执行步骤

1. 按correlation ID、trace ID、Runtime/Extension composition fingerprint确定影响slot和时间窗，不读取业务payload。
2. 分类为API、Worker、database、broker、Extension、backup/restore或release identity；同时检查live与ready，避免把进程存活误判为可接流量。
3. 立即停止promotion；readiness DOWN时移出工程traffic probe，Worker identity异常时停止领取任务。
4. 跳转到对应Runbook执行单一故障恢复，并记录alert fired/resolved、执行身份、artifact和sanitized结果。
5. 发现credential/payload泄漏时阻断evidence upload；发现restore mismatch时保留源库和backup；无法证明一致性时保持隔离并升级。

## 验证

事件关闭至少要求故障alert resolved、ready恢复、API/Worker composition一致、无redaction violation，并有对应machine report。恢复服务不等于关闭根因；没有owner复核不能修改风险/PROD_OPEN状态。

## 回退

诊断或修复扩大影响时立即停止操作，恢复last-known-good slot/config；数据库变更按backup Runbook处理。不能安全回退时维持隔离并选择经批准的forward fix，禁止试探Production。

## 升级与责任

工程operator负责初筛；runtime、database、broker、security、enterprise extension与host platform owner分别处理其边界。Production incident commander、业务owner、发布authority和外部通知链仍待未来具名，不由TASK-P8-10虚构。

## 最近演练记录

2026-09-07由TASK-P8-10覆盖10项alert的触发/恢复映射，其中高错误率、高延迟和饱和只做synthetic evaluator检查；其余来自真实Compose故障。未执行Production通知、HA切换或真实用户影响演练。
