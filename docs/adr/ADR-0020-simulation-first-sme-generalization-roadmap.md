---
doc_id: ADR-0020
title: Simulation-first SME Generalization Roadmap
status: accepted
spec_version: 0.3.0
phase: P9-P14
normative: true
source_sections: [10, 27, 44, 57, 60, 84, 97, 103, 105, 106, 115, 116]
last_reviewed: 2026-09-16
---

# ADR-0020 — Simulation-first SME Generalization Roadmap

## Context

v0.1.0 已具备基础排程与 Headless/Extension/Kit 工程底座，但内部服务、HTTP router、可安装 Runtime binding 和用户可用能力需要分别验收。面向中小企业的数量、日历、资源、物料与执行语义不能全部依赖企业定制。

项目所有者确认当前无法接入真实工厂校准，要求以大量模拟/仿真数据推进通用产品研发，预留后期真实项目接入，并按既定顺序规划 P9 以后的里程碑。

## Decision

采用[六阶段路线](../core/sme-generalization-roadmap.md)：P9 补现有能力正式链路；P10 固定制造语义/数据底座；P11 联合资源/换型与首个实际搜索扩展；P12 数量物料/装配；P13 控制与决策；P14 拆并批/联合批/固定外协与校准接入方法。

P9～P14 的研发和工程验收以版本化 synthetic 场景为依据。缺少真实数据不构成这些阶段的 blocker。正确性、覆盖、稳健性、复杂度和工程性能分别验证；固定保留场景，保留失败/超时，不将调参样本当泛化证据。具体要求见[验证策略](../simulation/generalized-product-validation-and-calibration.md)。

通用制造语义进入 Core；行业画像和参数提供可审查选择，企业扩展承担批准边界内的差异。既有 Modular Monolith、全局 CP-SAT、solver-neutral Problem、独立 Validator、canonical 唯一外部输入、受控 SDK、人工发布和不可变 Kit 继续有效。

现有 unsupported 仍 unsupported。每项新增高级能力必须另行批准详细语义和 versioned carrier，配套 Solver/Validator/正反例/Benchmark/feature control 后才能更新实现声明。本决定接受路线，不预先冻结所有未来字段或约束实现。

真实项目接入保持为宿主映射 → 版本化 canonical 校验 → 隔离回放 → Synthetic Comparison/Reality Gap → 人工审定参数/规则 → 目标环境评审。P10 留数据来源/版本接缝，后期提供离线方法/工具；具体真实 carrier、privacy、authority 和启用条件由后继任务决定。当前只用合成示例验证接缝，不能伪造 `synthetic=false`。

P7 deferred、旧 P5 Task 退役与既有 Exit 历史保持。未来 Production 仍适用既有现实校准、关键 PROD_OPEN、安全/UAT 与显式授权，不因本路线或模拟通过而自动就绪。本决定不 supersede ADR-0017/0018/0019，不开放 Connector、自动升级或自动发布。

## Alternatives

一个大里程碑无法分别判断可用性、数据底座和高级约束的收益/风险；先铺全量字段容易形成未被 Solver 消费的空合同；当前强制真实试点会阻断已明确采用仿真优先的研发条件。六阶段允许逐段验证和调整投入。

## Consequences and validation

每阶段提供可演示、可安装、可回放的纵向成果，JSON/字典随行为演进。P9 首先补当前链路，再让后续新语义有稳定承载路径。跨能力场景与独立校验增加必要验证投入；仿真分布偏差仍是已知限制，后期以真实回放校准。

本次只批准规划，文档治理检查不等于产品 Gate。详细成员任务均保持 planned，不因文档创建启动实现、测试、部署或现实校准。

