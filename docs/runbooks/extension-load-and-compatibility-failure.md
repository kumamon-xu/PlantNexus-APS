---
doc_id: DOC-RUNBOOK-P8-EXTENSION-001
title: Extension 装载与兼容失败
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [6, 12, 65, 95, 97, 98, 99, 100, 101, 103, 113, 114]
last_reviewed: 2026-09-10
---

# Extension 装载与兼容失败

TASK-P8-18把非Production目标更新为`VERIFIED_BUILD_DEPLOY_STARTUP_ALLOW_LIST`，当前唯一允许项是精确Alpha Extension `com.example.aps.alpha@1.0.0`及其冻结artifact/config；Developer Kit固定为`1.0.0`和Provider验证fingerprint。该授权只属于`p8-operations-compose-v1`一次性`TEST/SIMULATION`演练，不能外推到其他Extension、客户环境或Production。

## 触发条件

- `APSExtensionConfigurationRejected`告警；
- 配置出现未知Extension ID/path、SDK/Runtime/Kit不兼容或API/Worker resolution不一致；
- Extension artifact/config/signature/fingerprint无法验证。

## 影响与安全边界

Extension只能在APS Runtime内部运行，宿主和浏览器不得加载。允许集合必须与target manifest逐字一致；不得为通过readiness而下载、复制、修改Core、关闭Validator、创建私有API或直写APS数据库。Production Extension trust与support window保持OPEN。

## 前置权限

当前operator只能部署target中已批准、content-addressed的Alpha集合并阻止promotion；没有批准新Extension、修改artifact/config/Kit identity或授予Production trust的权限。任何集合变更仍需要runtime owner、enterprise extension owner与security/release authority共同具名。

## 执行步骤

1. 读取target manifest，确认Registry protocol、Alpha extension/version/artifact/config、Developer Kit version/fingerprint及Runtime release identity均精确匹配。
2. 由唯一显式startup provider从read-only本地输入materialize Alpha；禁止与显式artifact tuple并存，禁止ambient entry-point扫描和网络安装。
3. 启动API/Worker并确认两者descriptor的Extension set/config、Kit和composition fingerprint逐字相同，readiness=`UP`。
4. 仅在控制器内把configured ID替换为`enterprise.unverified`，结果必须`DOWN/EXTENSION_CONFIGURATION_REJECTED`；触发`APSExtensionConfigurationRejected`后恢复精确Alpha集合。
5. 对provider失败/超时、artifact或配置digest漂移、Kit mismatch、API/Worker mismatch保持隔离，保存sanitized identity evidence；不得继续旧PlanningRun。

## 验证

observability报告必须记录Extension告警fired/resolved；deployment descriptor只暴露版本/指纹/计数，不含路径、secret或企业payload。deployment/recovery报告必须证明API、Worker、restore与rollback四处Extension identity相同，并显示精确Developer Kit `1.0.0`身份。

## 回退

停止traffic和Worker，恢复上一套完整且已验证的Runtime+SDK+Extension+config+Kit组合；不能动态卸载、混搭版本或继续同一PlanningRun。只有该组合的API/Worker readiness及descriptor一致后才可切换流量；本目标的双槽回退仍是same-artifact/same-Extension配置回退，不证明跨版本兼容。

## 升级与责任

P8-12是SDK合同owner，P8-13是Registry/runtime SPI owner，P8-14/15是模板、conformance与Kit owner。当前TASK-P8-10 operator只能阻断，不得代替这些owner或Production release authority。

## 最近演练记录

2026-09-10由TASK-P8-18执行精确Alpha装载、API/Worker identity、未验证ID拒绝、备份恢复与rollback identity检查，本地全部PASS。Alpha/Beta双链只在专项产品检查中执行；真实企业Extension、外部签名、跨版本Kit升级和Production回退仍未验证。
