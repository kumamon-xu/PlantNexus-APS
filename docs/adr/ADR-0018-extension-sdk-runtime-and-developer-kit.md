---
doc_id: ADR-0018
title: Extension SDK Runtime Loading and Versioned Developer Kit
status: accepted
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [4, 5, 9, 12, 30, 63, 65, 93, 95, 97, 101, 103, 106, 107, 109, 113, 114]
last_reviewed: 2026-09-04
---

# ADR-0018 — Extension SDK Runtime Loading and Versioned Developer Kit

## Context

ADR-0017确定APS以Headless HTTP API接收versioned canonical JSON，并允许宿主平台或可选独立Frontend消费同一API。不同企业仍需要在约束、目标、计划规则、校验规则和重排策略上进行适配。如果企业项目复制或修改`aps-core`，Core升级、缺陷修复、Validator独立性、版本追踪和多项目维护都会失去统一边界。

同时，单独发布一个SDK版本不足以证明企业扩展可以安全运行。企业项目需要一组经过共同兼容性验证、可以长期锁定和重放的Runtime、SDK、模板、工具、示例和文档；Core或Runtime的新版本也不能隐式改变已交付企业项目的运行结果。

## Decision

### 1. 四个产品单元

- **APS Core**：保存通用领域模型、PlanningProblem、Solver策略、正式Validator、状态机和不可变性等核心语义；不导入企业扩展实现。
- **APS Extension SDK**：提供稳定、版本化的企业扩展接口和manifest模型，首批扩展点为`Constraint`、`Objective`、`Planning Rule`、`Validation Rule`、`Replan Policy`和`Plugin Registry`。
- **APS Runtime**：唯一运行载体，装配APS Core、Headless API、Solver Worker、Validator、持久化与受控Extension loader。企业Extension只在Runtime服务端执行。
- **APS Developer Kit**：经过兼容性验证的不可变交付组合，包含指定Runtime、Extension SDK、Enterprise Extension项目模板、conformance测试工具、正反示例和版本化文档。

每个企业项目创建独立的**Enterprise Extension**仓库或artifact，通过明确版本的SDK开发并锁定Runtime/SDK/Developer Kit版本。企业项目不得复制、vendor或修改APS Core来实现业务差异。

### 2. 依赖方向与外部边界

规范依赖方向为：

```text
Enterprise Extension -> APS Extension SDK <- APS Runtime adapters -> APS Core
                                              |
                                              +-> API / Solver Worker / Validator

Enterprise platform / optional Frontend -> Headless HTTP API -> APS Runtime
```

Extension SDK不是远程API，Enterprise Extension不得被宿主平台或浏览器加载。宿主继续只提交canonical JSON并读取标准结果；Extension不得创建vendor payload入口、企业私有数据库旁路或第二套业务API。若扩展需要额外数据，只能使用经批准、命名空间化、版本化且可校验的canonical字段。

### 3. 扩展语义约束

- Registry以稳定plugin ID、extension point、artifact version、SDK compatibility range和deterministic order解析贡献；duplicate、unknown、冲突或mixed-version配置必须fail closed。
- Extension只能消费SDK暴露的immutable views/value objects和显式services，不得访问Core内部模块、直接写APS数据库或原地修改Snapshot、Problem、ScheduleVersion及历史audit。
- 新Constraint或Planning Rule若影响候选可行性，必须同时提供语义独立的Validation Rule；Validator不得调用Solver侧约束builder或把Solver status当作正确性证明。
- Objective贡献必须保持确定性、整数化和批准的lexicographic层级；不得隐式改变既有目标优先级或权重authority。
- Replan Policy必须服从Execution Fact、HARD lock、freeze window、state machine和publication authority，不能移动已冻结事实或绕过人工控制。
- Core invariant、状态迁移、authorization、publication、audit和外部API兼容属于封闭边界，不能被插件覆盖。

### 4. 装载和信任模型

Extension由管理员在build、deploy或startup阶段安装和选择，Runtime在接受流量前完成allow-list、完整性、manifest、版本和capability校验。禁止按请求上传代码、远程拉取未固定包、运行时`pip install`或任意hot load。

Python同进程Extension按可信代码管理，并不构成安全沙箱。若未来需要运行不可信第三方代码，必须先通过新ADR设计独立进程/容器、资源限额和通信协议；不得把当前SDK描述为隔离机制。

API进程与Solver Worker必须加载同一套已解析Extension集合。每次PlanningRun的fingerprint至少绑定Core、Runtime、SDK、Enterprise Extension artifact/config、Registry resolution、Solver、Validator和rule versions；不一致时不得领取或发布结果。

### 5. Developer Kit与升级策略

每个Developer Kit版本绑定：

- Runtime artifact及digest；
- Extension SDK API/version；
- Enterprise Extension模板；
- conformance CLI/test harness；
- 正向与拒绝示例；
- compatibility manifest/matrix、lockfiles、SBOM、license和迁移文档。

Core、Runtime、SDK、Enterprise Extension和Developer Kit分别版本化，禁止把它们压缩为一个模糊的“APS版本”。已发布Kit不可原地覆盖。Core或Runtime升级不要求企业项目自动升级；新Kit只有在合同、Registry、双Extension样例、Solver/Validator独立性、旧Kit重放和升级负例通过后才能发布。企业项目按自己的维护窗口显式选择升级，并可继续使用仍在支持窗口内的已验证组合。安全修复、支持终止和弃用必须通过明确策略发布，不能静默替换已锁定版本。

## Consequences

- Core保持单一、可升级且不含企业分支；企业差异成为可识别、可测试、可撤销的artifact。
- Runtime组合和Developer Kit发布会增加兼容矩阵、供应链、运维和支持成本，但这些成本变为显式可审计对象。
- 不是所有Core语义都可扩展；未经SDK暴露的能力继续由标准Task/ADR演进。
- 同进程插件故障可能影响Runtime，因此装载、资源预算、timeout、日志脱敏和故障归属必须进入P8 Gate。

## Rejected alternatives

1. **为每个企业fork APS Core**：会造成语义漂移、重复升级和Validator不可审计，拒绝。
2. **把Extension作为宿主侧代码或浏览器插件运行**：会破坏Headless单一authority和服务端审计，拒绝。
3. **只发布SDK、不发布验证过的组合**：无法回答Runtime兼容性和可重放性，拒绝。
4. **Runtime自动升级所有企业项目**：会把平台发布变成未经授权的业务语义迁移，拒绝。
5. **允许运行时任意下载/上传插件**：扩大供应链与执行面且无法形成稳定fingerprint，拒绝。

## Follow-up

TASK-P8-12～15依次形成SDK合同、Runtime SPI/Registry、Enterprise Extension模板与conformance工具、Developer Kit组装和兼容发布；TASK-P8-16执行Headless+Extension集成Gate，TASK-P8-17进行独立Exit审计。Extension trust、compatibility、support window和企业责任作为`OPEN-002/010/012/015`的P8细分问题继续OPEN，不新增OPEN ID。
