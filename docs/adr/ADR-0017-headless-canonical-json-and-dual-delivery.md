---
doc_id: ADR-0017
title: Headless Canonical JSON Boundary and Dual Delivery
status: accepted
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [0, 3, 4, 9, 10, 12, 15, 63, 65, 66, 67, 68, 84, 85, 97, 105, 106, 107, 109, 112, 113]
last_reviewed: 2026-09-04
---

# ADR-0017 — Headless Canonical JSON Boundary and Dual Delivery

Status: accepted

Date: 2026-09-04

Decision owners: PlantNexus APS repository governance；真实宿主identity、authority、Production部署和发布责任仍受对应`PROD_OPEN`约束

Requirement/NFR/ENG: REQ-001、REQ-002、REQ-004、REQ-005、REQ-006、REQ-007、REQ-008、REQ-009、REQ-013、REQ-014；NFR-COR-001、NFR-DET-001、NFR-TRC-001、NFR-ISO-001、NFR-REL-001、NFR-SEC-001、NFR-OBS-001、NFR-HUM-001；ENG-ARCH-001、ENG-VER-001、ENG-ERR-001、ENG-LOG-001

Supersedes: none；细化ADR-0001的common-ingress产品边界，并继续遵守ADR-0002、ADR-0007、ADR-0009和ADR-0012

## Context

APS最终既要能够作为自有系统平台的内置排程模块运行，也要允许后续以同一后端独立开发和封装行业前端。宿主平台已经负责业务数据采集、第三方系统连接和结果展示，因此APS若继续把ERP、MES、WMS、CAM或文件格式Adapter视为产品集成边界，会重复建设连接器、扩大凭证与数据authority范围，并让同一排程核心产生多套输入语义。

当前仓库已经形成模块化单体、API/worker分进程、不可变Snapshot/Problem/Version、独立Validator和统一Application Port等基础，但尚未形成完整的canonical ingress、PlanningRun异步编排、真实host identity适配、部署封装与运维闭环。P7又因真实历史、Planner context和目标环境缺失而deferred；TASK-P7-13仅将其当前执行卡终结为`cancelled/NOT_EXECUTED`，未来仍须新建successor计划。需要在不伪造现实证据、不修改现有机器合同的前提下，先固定P8产品化方向和P7/P8关系。

## Decision

### 1. Canonical JSON是唯一外部产品输入

宿主平台只通过版本化canonical JSON向APS提交计划输入、运行命令及后续获批准的执行事实。APS不直接连接ERP、MES、WMS、CAM或其他第三方业务系统，也不把其私有payload、数据库表、SDK、凭证和字段映射纳入产品API。

既有CSV/XLSX/reference adapter、synthetic fixture和normalization路径可以继续作为开发、测试、迁移辅助或canonical JSON生产参考，但不得成为Production公共边界，也不得绕过同一canonical contract、data validation、authority、scope和lineage检查。

### 2. 宿主与APS的数据责任分离

宿主平台负责上游连接、采集、映射、脱敏、用户交互、结果展示以及将自身principal/factory scope映射到APS信任边界。宿主提交canonical JSON并保留上游source/version/authority reference；仅传输数据并不使宿主成为字段事实的隐式authority。

APS负责canonical contract验证、业务数据验证、不可变Snapshot/PlanningProblem、PlanningRun编排、Solver worker、formal Validator、ScheduleVersion/read model/export representation、结构化错误、审计和provenance。宿主不得直接写APS数据库或调用内部Solver绕过Application/API边界。

### 3. Headless API是唯一业务执行入口

APS以稳定、版本化、异步优先的HTTP API作为宿主集成和可选独立Frontend的共同入口。长时求解由独立worker消费持久化运行请求；API进程不把同步内存调用当作Production完成路径。APS拥有自己的持久化和migration边界，宿主只消费公开合同和稳定标识。

同一API既可被宿主平台调用，也可被后续独立SPA/行业Frontend调用。独立Frontend是可选交付物，不能拥有另一套业务后端、直接数据库访问或不同的状态机语义。

### 4. P7与P8从P6后并行分叉，Production再汇合

P7继续负责真实Historical Replay、Reality Gap、Planner review和Capacity Decision；P8负责Headless runtime、canonical ingress、安全、封装、部署和工程集成。P7可以在输入未具备时保持deferred，P8可以按独立Task授权推进。

P8的synthetic端到端Gate只能证明工程链路，不关闭P7现实输入缺口。任何Production readiness、UAT、capacity或SLA结论必须同时满足P7 Exit Gate、P8 Exit Gate及总规Production Gate；任一分支未通过都必须返回`NOT_READY`。

### 5. 本ADR只冻结方向，不发布机器合同

本次不修改Schema、OpenAPI、数据库、状态机、代码、测试、依赖、部署或Demo。详细的人类可读集成合同由TASK-P8-01形成，additive machine contract由TASK-P8-02形成，所有实现和验证按P8 DAG逐Task授权。

尚未实现的高级排程能力不纳入P8基础封装的强制范围；它们必须保持显式unsupported，并在未来以独立、兼容、可验证的Task增量交付。P8不得为了等待未定义高级功能而阻塞现有稳定核心的Headless封装。

## Alternatives considered

### APS直接维护第三方系统连接器

拒绝。它扩大凭证、供应商版本、字段映射和数据authority责任，并与宿主平台已有集成能力重复。确有特殊连接器需求时，应由宿主或独立边界服务把数据转换为canonical JSON。

### 将APS作为宿主进程内Python库或共享数据库

拒绝。进程内调用或共享表会绕过版本化API、身份范围、审计、migration owner和异步运行语义，使后续独立Frontend无法复用稳定边界。

### 为宿主和独立Frontend维护两套后端

拒绝。双后端会造成状态机、验证、错误和版本行为漂移。两类客户端必须消费同一Headless API。

### 在HTTP请求中同步完成求解

拒绝。求解耗时、取消、重试、资源隔离和恢复需要持久化PlanningRun与独立worker边界；同步内存路径不能作为Production语义。

### 以P8 synthetic Gate替代P7现实校准

拒绝。工程可部署性与真实数据/Planner/容量证据是不同维度，任何一方都不能替代另一方。

## Consequences

正面结果：APS保持行业和上游系统中立；宿主与独立Frontend共享一个可审计后端；第三方凭证和mapping不进入APS；异步运行、持久化、部署与运维可按清晰边界推进；P7缺少真实输入不再阻止纯工程产品化规划。

代价与限制：宿主必须生成符合版本合同的canonical JSON并维护上游lineage；APS必须补齐canonical ingress、持久化运行编排、identity adapter、发布封装和运维证据；API兼容和Schema evolution成为长期约束。P8完成仍不等于Production ready。

`OPEN-002`被收窄为宿主canonical API、identity、scope和authority的Production闭环；直接第三方Adapter不再是APS责任，但该OPEN项不会因此自动关闭。既有REQ/NFR/ENG root数量和spec version保持不变，本ADR为0.3.0内的加法式产品化决定。

## Relationship to ADR-0018

[ADR-0018](ADR-0018-extension-sdk-runtime-and-developer-kit.md)在不改变本ADR外部边界的前提下增加服务端企业扩展机制。Enterprise Extension只由APS Runtime通过versioned SDK加载；宿主平台和可选Frontend仍只使用这里定义的同一Headless HTTP API。SDK不是新的远程API，插件不得引入vendor payload入口、共享数据库或第二套后端。两个ADR共同要求P8-16/17验证Headless与Extension组合，而不是允许企业项目fork Core。

## Rollback / Revisit gate

Accepted ADR不得删除或原地改写；语义变化必须新增superseding ADR。若P8尚无consumer，回滚可移除未实施的P8计划并把current phase恢复为P7 deferred；一旦公开API或持久化consumer形成，必须通过兼容版本、deprecation和migration回退，不能恢复共享数据库或内部旁路。

只有在宿主无法承担canonical mapping、出现经批准且边界清晰的独立连接器产品、传输协议需要超越HTTP/JSON，或法律/部署条件要求不同进程拓扑时才revisit。任何revisit仍须保持单一canonical语义、不可变lineage、formal Validator、显式authority和P7/P8双门。
