---
doc_id: DOC-ARCH-011
title: APS Extension SDK Runtime and Developer Kit Architecture
status: active
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [4, 5, 9, 12, 30, 63, 65, 93, 95, 97, 101, 103, 106, 107, 109, 113, 114]
last_reviewed: 2026-09-10
---

# APS Extension SDK、Runtime 与 Developer Kit 架构

## TASK-P8-17 独立Exit审计

P8-17不修改Core、Runtime、SDK、Extension、Kit或业务合同，只作为独立`PHASE_GATE` consumer。它校验P8全部21个Task的DAG和20个前序终态，重核21组exact Provider输入、88份artifact与2,032个归档条目，保留10项失败/纠正历史，并检查ADR-0017/0018、canonical-only、Core无企业反向依赖、版本锁定和P7/Production边界。随后它从当前SHA重新生成P8 JUnit并fresh执行P8-19完整procedure；只有18/18平台检查、4/4 closure、`issues=[]`和`blocking_gaps=[]`同时成立才输出`READY`。

P8-20纠偏SHA已由Provider同时验证独立operations和FULL内重复演练；先前P8-17失败候选继续保留且未rerun。最终P8-17取得304项目标回归、20/20 Exit check、fresh P8-19 18/18与4/4、零gap，并由同一审计SHA的FULL required `validate` / GitHub Actions app `15368`确认，Task与P8工程里程碑已关闭。P8 Exit不改写P8-16 `NOT_READY`历史，也不把Runtime变化并入不可变Kit `1.0.0`，更不授权自动升级、真实企业业务适用性、P7现实校准或Production。

## TASK-P8-19 平台独立重资格

P8-19新增独立`PHASE_GATE` consumer，严格复用P8-16冻结profile `sha256:da5ee7830e37f86569897a80685d25e59414f05153499b3effed37b483503043`、18项check inventory、seed和原工程门槛，并校验P8-16 runner/profile原始字节及`NOT_READY` Provider身份。它同时消费P8-18 exact closure lineage和当前SHA重新生成的Runtime、Frontend、Validator、operations及七类corrective报告，再独立重放Alpha/Beta完整产品链。P8-16历史报告不会被覆盖；四个旧blocker通过`historical BLOCKED → P8-18 PASS → P8-19 fresh assertion`逐项建立后继处置记录。

当前本地候选在292项P8测试零失败/零跳过后取得18/18平台检查、4/4 blocker closure和`blocking_gaps=[]`，两条链均证明六类SPI被Runtime实际调用、Developer Kit `1.0.0`身份一致、授权publication/read/export可达且目标部署/恢复装载同一Alpha Extension集合。旧P8-16 mixed/duplicate负例仍由冻结procedure执行；P8-19只在测试fixture边界补齐P8-18后来强制的Developer Kit version+fingerprint成对配置，不修改冻结runner、profile、threshold、expected或负向错误码。

该`READY`只表示synthetic Headless+Extension工程重资格结论；TASK-P8-19已由exact SHA的non-skippable Provider闭环。它不是单独的P8 Exit、P7 reality或Production ready；后继TASK-P8-17现已完成独立审计和exact Provider确认，并只关闭P8工程里程碑。

## TASK-P8-18 产品执行纠正

P8-18在不修改Core、SDK `1.0.0`公开合同、Alpha/Beta源码、Schema、migration或依赖的前提下，把startup-resolved adapter接入真实Worker生命周期。`runtime-http-policy.v2`只增加服务端持有的Extension事实carrier；外部请求仍是既有canonical JSON，不能选择Extension、module、class、artifact或配置。Worker在求解前按resolved order调用`Plugin Registry → Planning Rule → Constraint → Replan Policy`，在Core Solver和fresh formal Validator形成候选后、创建ScheduleVersion之前调用`Objective → Validation Rule`。每次成功调用只记录lifecycle及输入/输出SHA-256，不保留payload、返回对象或异常细节。

SDK v1的solver-neutral输出不修改Core对象。Feasibility贡献由同artifact内独立Validation Rule在candidate admission处强制执行；Validation FAIL、Replan `REQUEST_REPLAN`、crash、timeout或非法输出都会终结当前PlanningRun且ScheduleVersion为零。`ENTERPRISE_TIE_BREAK`在本纠正链中被实际求值和验证，但P8-18不宣称它已重写Core目标层级或在多个Core等价候选之间完成Production级选择；真实企业公式与业务验收仍不在范围内。

Runtime配置现把Developer Kit version与fingerprint作为原子身份；非空Extension没有精确Kit身份时拒绝启动，API/Worker组合不一致时在Worker result之前拒绝。deployable API同时装配既有approval、publication、ScheduleVersion read和ExportJob service，继续复用server-derived authorization、state/CAS、idempotency、append-only audit及repository authority，不增加HTTP operation或第二状态机。

Kit identity和Runtime artifact identity是两个独立版本维度。P8-18 Runtime引用P8-15 Kit `1.0.0`只证明所载Extension来自该冻结开发/兼容基线；它不改变Kit archive、registry映射或其中嵌套的Runtime lineage，也不把纠正后的Runtime伪装成Kit `1.0.0`的新内容。当前CI保留六层Kit合同回归，并由P8-18产品Gate验证当前Runtime对该Extension基线的动态兼容；新的组合交付必须使用新的Developer Kit版本和独立发布Task。

部署只通过显式`module:callable` startup provider取得本地已批准artifact对象；显式对象和provider并存、provider失败/超时、非canonical集合或catalog不完整均fail closed。`p8-operations-compose-v1`当前锁定Alpha artifact/config、Developer Kit `1.0.0` fingerprint和P8-18 content-addressed Runtime，在一次性`TEST/SIMULATION`靶场证明API、Worker、恢复后实例与rollback slot保持相同Extension identity。该纠正的本地证据为P8专项287/287、四项blocker 4/4及真实Compose演练PASS；P8-16历史`NOT_READY`不被改写，只有后续独立P8-19可以作平台重资格。

## TASK-P8-16 平台集成 Gate 结论

P8-16以冻结的`headless-extension-platform-gate-profile.v1`（fingerprint `sha256:da5ee7830e37f86569897a80685d25e59414f05153499b3effed37b483503043`）从外部host client分别重放Alpha与Beta Extension。两条链均可完成canonical HTTP create、durable ingress、PlanningRun、Worker、Core Solver、fresh formal Validator和`READY_FOR_REVIEW` ScheduleVersion；idempotent replay、authorization、malformed/scope、mixed API/Worker Extension set和duplicate Extension set也均按稳定错误拒绝。目标P8 suite共283项全部通过。

但独立Gate的18项检查只有14项通过，工程结论为`NOT_READY`。四个blocking gap不能由conformance或“已成功装载”替代：

- Runtime虽然解析并fingerprint Enterprise Extension，但实际API/Worker产品链没有调用任何`Constraint`、`Objective`、`Planning Rule`、`Validation Rule`、`Replan Policy`或`Plugin Registry`贡献；Alpha/Beta invocation delta均为0。
- Runtime descriptor仍报告Developer Kit为`0.0.0-not-published`，没有把已验证Kit `1.0.0`身份与运行实例绑定。
- deployable Runtime使用不可用的Planning Workspace application和Authorization provider；Worker只产生`READY_FOR_REVIEW`候选，publication、受权read和export未形成可调用Headless输出链。
- P8-10目标部署仍以`DISABLED_UNTIL_COMPATIBILITY_VERIFIED`和default-empty Extension运行，没有部署并恢复Gate选定的Enterprise Extension集合。

因此P8-16只证明既有Headless基链、Extension装载/conformance和负例边界可复算，不能声明“Runtime已执行企业扩展”或“Headless输出闭环”。产品修复归TASK-P8-18；TASK-P8-19在P8-18后以独立wrapper复用同一冻结profile和check inventory形成新的重资格证据，且不改写P8-16历史结论。P8-16本身保持审计边界，不修改被审计的Core、Runtime、SDK、Extension、Schema、API、migration或Frontend实现。

## 目标

不同企业可在不复制、不fork、不修改`aps-core`的前提下实现业务适配，同时保留Headless API、canonical JSON、正式Validator、不可变版本、权限和审计的统一语义。TASK-P8-12已形成SDK `1.0.0`合同，TASK-P8-13形成Runtime loader与Registry，TASK-P8-14形成独立项目模板、conformance工具和两个synthetic示例；TASK-P8-15现将其与exact Runtime release组装为Developer Kit `1.0.0`工程候选。真实企业规则、外部签名和Production批准仍未形成。

## TASK-P8-12 formed SDK boundary

公开命名空间为`aps_extension_sdk`，只依赖标准库并暴露六类Protocol、frozen value、strict manifest/compatibility/error parser和code-free resolution。SDK package不得导入`app`或Core；Core/API/Runtime也未在本Task新增对SDK的反向依赖。机器carrier保存在SDK自身目录，不进入global业务Schema Set和既有Runtime `0.1.0`分发。

SDK v1不暴露privileged service；所有输入先由Runtime裁剪并深度冻结。Objective唯一插槽为全部Core目标之后的`ENTERPRISE_TIE_BREAK`；Replan返回必须逐字保留fact/HARD lock/freeze/state/publication authority绑定；feasibility贡献与Validation Rule必须在同artifact双向配对且entrypoint/execution domain分离。具体合同以[`extension-sdk-and-developer-kit.md`](../contracts/extension-sdk-and-developer-kit.md)和package carrier为准。

## TASK-P8-13 Runtime Extension execution boundary

`app.extensions`是唯一Runtime侧Extension consumer：`contracts`定义受控artifact、稳定错误与预算，`loader`在任何数据库或业务副作用前读取单一strict本地catalog并验证canonical fingerprint、HMAC-SHA256标签、artifact SHA-256、manifest/config identity、SDK/Runtime兼容与capability allow-list，`registry`按SDK resolution逐项绑定并调用六类Protocol。API和Worker的唯一composition root接收相同的服务端artifact provider并把同一Extension-set/config fingerprint写入immutable Runtime descriptor；非空配置不一致会阻止Worker启动，而不是在任务消息或HTTP请求中选择代码。

装载只接受部署bootstrap显式传入、已materialize的实现对象；artifact bytes与对象的构建映射属于可信发布/部署bootstrap责任，P8-13不进行全局entry-point扫描、动态import、pip/git/URL下载、自动安装或hot reload。HMAC key只来自`SecretStr`启动配置且不进入descriptor、日志或报告；HMAC是当前本地工程allow-list标签，不冒充PKI签名、远端attestation或Production信任结论。

单catalog/manifest/config/artifact分别受1 MiB、256 KiB、256 KiB、16 MiB上限约束，最多16个artifact/256项贡献；单次SPI和startup预算均进入catalog fingerprint。调用在有界daemon thread中执行，timeout后丢弃整个返回并把该贡献标记为unhealthy；这只能提供fail-closed调用边界，不能中止或隔离恶意Python代码，因此信任模型仍为`trusted_in_process=true`、`sandboxed=false`。

当前adapter证明六类SPI可被裁剪、冻结、校验和观测，并证明Validation Rule entrypoint/domain与Solver侧贡献分离；它没有把synthetic Constraint/Objective/Planning Rule解释为Core Solver的真实企业公式，也没有替代fresh formal Validator。企业实现和独立双实现conformance由P8-14形成；P8-16曾确认这些贡献尚未接入实际API/Worker产品链，P8-18完成产品整合，P8-19再以独立fresh replay复验调用、拒绝和输出边界。

## TASK-P8-14 Enterprise Extension开发边界

`templates/enterprise-extension`是一个不含Core源码、只声明`aps-extension-sdk==1.0.0`运行依赖的独立Python项目模板。`enterprise-extension-project.v1`把项目ID、distribution/package、企业owner、无凭据HTTPS repository、license表达式、source commit、SDK `1.0.0`、Runtime `0.1.0`、未发布Kit占位及项目内manifest/config/schema/lock/fixture路径组成封闭合同。scaffold只写入指定本地目录，不初始化Git或创建远程仓库。

`aps_extension_tooling`先静态拒绝Core/internal/第三方import、I/O和非确定性引用、符号链接、源码副本及浮动lock，再两次生成固定时间戳的pure-Python SDK/Extension wheel和项目归档。默认在临时clean venv中以`--no-index --no-deps`安装本地wheel并运行项目自带测试，然后把显式materialize的对象交给P8-13 Runtime；它不扫描ambient entry point、不下载代码，也不改变Runtime loader语义。

Alpha和Beta示例是两个独立项目：Alpha只提供resource-tag Constraint及不同模块中的Validation Rule；Beta提供Planning Rule、Core目标后的integer tie-break Objective、保持五类受保护绑定的Replan Policy和Plugin Registry。conformance对每个SPI执行两次、验证独立Validation正反输入和Registry一致性，并验证两个项目可组成确定性Extension set。示例事实、标签和数值只属synthetic工程证据。

使用方式、项目布局、拒绝条件、调试、交付和升级见[Enterprise Extension开发指南](enterprise-extension-development-guide.md)。P8-14源项目继续使用`0.0.0-not-published`占位且不得被自动改写；P8-15只在临时组装输入中显式relock副本，从而保留历史重放与no-auto-upgrade证据。

## TASK-P8-15 Developer Kit发布边界

Developer Kit `1.0.0`将Runtime `0.1.0`的exact archive digest/release fingerprint/code commit、SDK `1.0.0`、Tooling `1.0.0`、Template `1.0.0`、两个synthetic Extension、五份开发/运维文档和供应链metadata组合成单一确定性ZIP。包内compatibility matrix和Kit lock同时绑定Application/Core、Headless API、Schema、database、Registry、Python与tool dependency hashes；逐文件checksum、Core source hash inventory、嵌套Runtime SBOM、Kit SBOM和license report使组合可离线核对。

工程registry按`version -> archive SHA-256 -> path`追加且不可覆盖。同一输入双构建必须逐字一致；同一版本的不同bytes、缺失artifact、lock/checksum/SBOM/license/signing状态漂移或unsupported组合均在安装/Runtime装载前fail closed。包内CLI可用随包SDK wheel和Core source inventory执行scaffold/check/check-set，不依赖APS源码checkout；Extension仍只在已安装Runtime内执行。

支持矩阵目前只有`Kit 1.0.0 + Runtime 0.1.0 + SDK 1.0.0 + Tooling 1.0.0 + Template 1.0.0`。P8-14只作为`SYNTHETIC_UNPUBLISHED_REPLAY_ONLY`前代，不构成历史支持承诺。从它迁移需要企业owner显式relock和重新验证；新Core/Runtime只产生新Kit候选，不推送或改写企业仓库。当前release owner只负责repository/CI工程channel，签名状态为`UNSIGNED_ENGINEERING_CANDIDATE`；public/Production仍因没有外部PKI authority而default-deny。

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

具体Python protocol、manifest Schema、error registry和兼容规则已由TASK-P8-12形成；Runtime调用、装载、确定性Registry与readiness语义已由P8-13形成；独立项目、打包和conformance开发入口已由P8-14形成。

## 运行时组合

1. 发布/部署阶段锁定Runtime、SDK、Extension artifact和配置digest。
2. Runtime启动时读取本地受控manifest，验证allow-list、完整性、SDK compatibility和唯一Registry resolution。
3. API与Worker分别从同一已签/已固定配置生成composition fingerprint；fingerprint不同则readiness失败或work item拒绝。
4. API只接收标准canonical request，生成不可变Snapshot/Problem/PlanningRun并记录Extension resolution。
5. Worker进程持有同一resolved adapter；P8-18已把六类SPI接入真实产品lifecycle，P8-19要求动态调用计数和输入/输出fingerprint同时存在，不能用descriptor parity替代执行证据。
6. 既有fresh formal Validator保持独立；Extension Validation Rule在候选进入可审阅状态前由Runtime实际调用，并与formal Validator共同fail closed，P8-19同时重放Validation与Replan拒绝。
7. 标准publication/read/export API返回结果、violation和完整版本fingerprint；P8-19复验证授权输出和exact replay。企业特有字段仍必须位于批准的canonical namespace。

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

P8-12 compatibility carrier固定SDK `1.0.0`、manifest v1、Registry v1、六类point、Core目标/Replan/Validator封闭策略和SemVer/deprecation规则。P8-15 compatibility manifest现列出精确Runtime/Core/SDK/Tooling/Template、artifact digest、Schema/API、Python/dependency lock和支持窗口。破坏性SDK变更提升major；additive接口仍需conformance与旧Extension回放；bugfix不得改变已声明业务语义。

## Developer Kit 交付清单

- 可复现Runtime artifact、checksum与嵌套SBOM；
- Extension SDK包、API参考和compatibility manifest；
- 独立Enterprise Extension项目模板，不包含Core源码副本；
- conformance CLI、unit/integration harness和determinism/import-boundary checks；
- 至少两个相互独立的示例Extension及duplicate/incompatible/invalid负例；
- 本地开发、调试、打包、发布、升级、回滚和弃用文档；
- exact lockfiles、license/SCA结果、Core source inventory和Developer Kit release manifest。

P8-15已把上述清单组装为`1.0.0`工程候选并在clean环境验证包内CLI。发布新Core或Runtime不触发企业项目升级；平台只能发布新的Developer Kit候选并运行兼容Gate，企业项目在自己的变更和发布窗口显式选择是否迁移。旧Kit在声明的支持窗口内继续可重建和维护，支持终止或安全例外必须可审计。

## 治理与就绪边界

| 状态 | 可以声明 | 不可以声明 |
|---|---|---|
| P8-00文档完成 | 架构、ADR、DAG和治理根已确定 | SDK/Runtime loader/Kit已实现 |
| P8-12～15完成 | 对应合同、代码、模板、工具或Kit已有Task证据 | Headless全链或P8 Exit已通过 |
| P8-16 `NOT_READY` | Headless基链与Extension装载/conformance可重放，且四项集成缺口已由机器证据定位 | Runtime已执行Extension、Kit已绑定、输出/部署已闭环 |
| P8-18 corrective完成 | 四项产品缺口已有有界实现与专项证据 | 自动继承P8-16 READY或启动Exit |
| P8-19 READY | 同一平台Gate已在corrective新SHA独立复验 | P7现实校准或Production ready |
| P8-17 READY | P8产品化与扩展synthetic工程证据完整，可形成内部交付选择 | 自动升级企业项目、真实UAT/SLA/authority或Production已完成 |

Extension trust、compatibility、support window和企业责任分别纳入现有`OPEN-002/010/012/015`的P8细分问题，不新增OPEN ID。这些条目关闭前，不得把某个本地插件样例解释为企业级信任、兼容支持或长期维护承诺。高级功能和真实数据验证可在后续独立Task补充；若其语义适合SDK扩展点，可作为Enterprise Extension交付，但仍必须满足capability、Validator、Benchmark和Production Gate要求。
