---
doc_id: DOC-ARCH-011
title: APS Extension SDK Runtime and Developer Kit Architecture
status: active
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [4, 5, 9, 12, 30, 63, 65, 93, 95, 97, 101, 103, 106, 107, 109, 113, 114]
last_reviewed: 2026-09-04
---

# APS Extension SDK、Runtime 与 Developer Kit 架构

## 目标

不同企业可在不复制、不fork、不修改`aps-core`的前提下实现业务适配，同时保留Headless API、canonical JSON、正式Validator、不可变版本、权限和审计的统一语义。当前文档冻结架构与后续P8工作，不表示SDK、loader、模板或Kit已经实现。

## 产品分层

```text
Enterprise Platform / Optional APS Frontend
                     |
          versioned Headless HTTP API
                     v
+-------------------------------------------------------------+
| APS Runtime                                                 |
| API | Application | Solver Worker | Formal Validator        |
| Persistence | Audit | Extension Loader / Plugin Registry    |
|                         |                                   |
|             selected Enterprise Extension                  |
|                         | APS Extension SDK                 |
|                         v                                   |
|                      APS Core                               |
+-------------------------------------------------------------+

APS Developer Kit = verified Runtime + SDK + template +
                    conformance tools + examples + docs
```

| 单元 | 职责 | 禁止承担 |
|---|---|---|
| APS Core | 通用domain、Problem、Solver、Validator、state与invariant | 企业分支、host/vendor适配、动态插件发现 |
| Extension SDK | 稳定SPI、manifest/value object、compatibility与Registry合同 | 外部HTTP API、Core内部实现导出、安全沙箱承诺 |
| Enterprise Extension | 一个企业的Constraint/Objective/Rule/Policy贡献和配置 | 修改Core、直写DB、私有API、浏览器执行 |
| APS Runtime | 装配Core/API/Worker/Validator，校验并加载指定Extension | 每请求上传/下载代码、隐式升级、混合插件集合运行 |
| APS Developer Kit | 发布已共同验证的开发与运行组合 | 浮动依赖、自动替换企业锁定版本、Production批准 |

## Extension SDK v1 扩展点

| 扩展点 | 允许贡献 | 必须保持的边界 |
|---|---|---|
| Constraint | 对solver-neutral planning facts的显式硬约束贡献 | 稳定ID；可解释参数；配套独立Validation Rule；不得静默忽略 |
| Objective | 批准层级内的确定性整数objective term/metric | 明确authority、方向、scale和lexicographic stage；无浮点隐式权重 |
| Planning Rule | 构建Problem或候选前后的确定性业务规则 | 不原地修改输入；输出具名、版本化；影响可行性时必须可独立验证 |
| Validation Rule | 从Problem/Solution/authority facts重新计算violation | 不导入Solver/backend constraint builder；stable violation code/path |
| Replan Policy | 事件触发、freeze/stability范围内的策略选择 | 不覆盖事实/HARD lock/state/publication；同输入同配置同决定 |
| Plugin Registry | 发现、校验、排序、解析和fingerprint贡献 | stable ID/version/capability；duplicate/conflict/unknown/mixed version fail closed |

具体Python protocol、manifest Schema、error registry和兼容规则由TASK-P8-12形成；本页不预判包名或函数签名。

## 运行时组合

1. 发布/部署阶段锁定Runtime、SDK、Extension artifact和配置digest。
2. Runtime启动时读取本地受控manifest，验证allow-list、完整性、SDK compatibility和唯一Registry resolution。
3. API与Worker分别从同一已签/已固定配置生成composition fingerprint；fingerprint不同则readiness失败或work item拒绝。
4. API只接收标准canonical request，生成不可变Snapshot/Problem/PlanningRun并记录Extension resolution。
5. Worker调用Runtime adapter和已解析Extension贡献完成求解。
6. 新鲜正式Validator使用独立Validation Rule重算；失败candidate不形成可审阅版本。
7. 标准read/export API返回结果、violation和版本fingerprint；企业特有字段必须位于批准的canonical namespace。

Extension异常、timeout、非法返回、未声明capability或版本不兼容必须映射为稳定的config/compatibility/system错误并无部分业务副作用。Extension日志、metrics和trace必须带plugin ID/version/correlation，但不得泄漏canonical业务payload或secret。

## 信任与安全

- Enterprise Extension是经企业和平台共同批准的服务端可信代码，不是租户上传脚本。
- 只允许build/deploy/startup装载；禁止请求级代码、远程floating artifact、runtime安装和未审查hot reload。
- Runtime执行allow-list、digest/signature、SBOM/license/SCA、依赖冲突和capability检查。
- Extension只能访问SDK能力，不授予数据库连接、宿主凭证、网络、文件系统或Core internal import；确需新资源时必须以Runtime port和显式最小权限另行治理。
- 当前同进程模型不能隔离恶意代码；不可信插件需要新的进程/容器隔离ADR。

## 版本和兼容矩阵

以下身份相互独立并全部进入provenance：

| 身份 | 说明 |
|---|---|
| Core version | 通用排程语义和内部实现版本 |
| Runtime version | API/Worker/Validator/composition与部署artifact版本 |
| SDK API version | 企业扩展可编译和运行的SPI版本 |
| Extension version | 企业artifact及其配置版本 |
| Developer Kit version | 一组通过共同兼容Gate的不可变交付组合 |

Compatibility manifest必须列出精确或明确范围的支持关系、禁止组合、artifact digest、schema/OpenAPI versions、Python/dependency lock和支持窗口。破坏性SDK变更提升major；additive接口仍需conformance与旧Extension回放；bugfix不得改变已声明业务语义。

## Developer Kit 交付清单

- 可复现Runtime artifact/image、checksum与SBOM；
- Extension SDK包、API参考和compatibility manifest；
- 独立Enterprise Extension项目模板，不包含Core源码副本；
- conformance CLI、unit/integration harness和determinism/import-boundary checks；
- 至少两个相互独立的示例Extension及duplicate/incompatible/invalid负例；
- 本地开发、调试、打包、发布、升级、回滚和弃用文档；
- exact lockfiles、license/SCA结果和Developer Kit release manifest。

发布新Core或Runtime不触发企业项目升级。平台发布新的Developer Kit候选并运行兼容Gate；企业项目在自己的分支和发布窗口显式选择是否迁移。旧Kit在声明的支持窗口内继续可重建和维护，支持终止或安全例外必须可审计。

## 治理与就绪边界

| 状态 | 可以声明 | 不可以声明 |
|---|---|---|
| P8-00文档完成 | 架构、ADR、DAG和治理根已确定 | SDK/Runtime loader/Kit已实现 |
| P8-12～15完成 | 对应合同、代码、模板、工具或Kit已有Task证据 | Headless全链或P8 Exit已通过 |
| P8-16 READY | Synthetic环境中API→Runtime→Extension→Solver→独立Validator可重放 | P7现实校准或Production ready |
| P8-17 READY | P8产品化与扩展工程证据完整 | 自动升级企业项目、真实UAT/SLA/authority已完成 |

Extension trust、compatibility、support window和企业责任分别纳入现有`OPEN-002/010/012/015`的P8细分问题，不新增OPEN ID。这些条目关闭前，不得把某个本地插件样例解释为企业级信任、兼容支持或长期维护承诺。高级功能和真实数据验证可在后续独立Task补充；若其语义适合SDK扩展点，可作为Enterprise Extension交付，但仍必须满足capability、Validator、Benchmark和Production Gate要求。
