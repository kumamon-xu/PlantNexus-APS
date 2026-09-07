---
doc_id: DOC-RUNBOOK-P8-EXTENSION-001
title: Extension 装载与兼容失败
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [6, 12, 65, 95, 97, 98, 99, 100, 101, 103, 113, 114]
last_reviewed: 2026-09-07
---

# Extension 装载与兼容失败

TASK-P8-10只建立未来Extension故障的运维门：P8-09 Runtime声明loading=`DISABLED_UNTIL_COMPATIBILITY_VERIFIED`、allowed set为空。任何非空Extension配置在启动/traffic promotion前readiness DOWN并告警。真正SDK/Registry/Enterprise Extension由P8-12～15实现，本Runbook当前不能授权加载插件。

## 触发条件

- `APSExtensionConfigurationRejected`告警；
- 配置出现未知Extension ID/path、SDK/Runtime/Kit不兼容或API/Worker resolution不一致；
- Extension artifact/config/signature/fingerprint无法验证。

## 影响与安全边界

Extension只能在APS Runtime内部运行，宿主和浏览器不得加载。当前允许集合严格为空；不得为通过readiness而下载、复制、修改Core、关闭Validator、创建私有API或直写APS数据库。Production Extension trust与support window保持OPEN。

## 前置权限

当前operator只有读取target manifest和阻止promotion的权限，没有安装Extension、修改Registry或批准企业artifact的权限。未来需要runtime owner、enterprise extension owner与security/release authority共同具名。

## 执行步骤

1. 读取target manifest，确认Registry protocol=`plugin-registry.v1`、loading禁用且allowed IDs为空。
2. 用空Extension集合执行准入，结果必须`UP/promotion_allowed=true`。
3. 注入`enterprise.unverified`配置，仅在部署控制器内评估；结果必须`DOWN/EXTENSION_CONFIGURATION_REJECTED`，不得把artifact传入容器或执行代码。
4. 触发告警并恢复为空集合，重新核对Runtime composition中的Extension-set fingerprint。
5. API和Worker descriptor不同、配置未知或artifact不可验证时保持隔离，保存sanitized identity evidence。

## 验证

`p8-10-observability.json`必须记录Extension告警fired/resolved；deployment descriptor只暴露版本/指纹/计数，不含路径、secret或企业payload。P8-09 Runtime仍显示SDK/Developer Kit未发布。

## 回退

移除未批准配置并切回last-known-good empty set；不能动态卸载后继续同一PlanningRun。未来有Extension时必须停止traffic/Worker、恢复上一套完整Runtime+SDK+Extension+config+Kit组合，再按兼容测试重放。

## 升级与责任

P8-12是SDK合同owner，P8-13是Registry/runtime SPI owner，P8-14/15是模板、conformance与Kit owner。当前TASK-P8-10 operator只能阻断，不得代替这些owner或Production release authority。

## 最近演练记录

2026-09-07由TASK-P8-10执行empty-set正例和未验证Extension负例；负例没有加载或运行任何插件。真实双Extension、旧Kit重放和升级回退仍待P8-12～15。
