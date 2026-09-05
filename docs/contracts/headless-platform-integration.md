---
doc_id: DOC-CONTRACT-014
title: APS Headless 平台集成与数据权威合同
status: baseline
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [3, 4, 5, 9, 10, 12, 15, 63, 65, 66, 67, 68, 95, 97, 105, 106, 107, 109, 113, 114]
last_reviewed: 2026-09-05
---

# APS Headless 平台集成与数据权威合同

## 1. 目的与规范级别

本合同是宿主平台、APS Runtime、APS Core、Enterprise Extension、可选APS Frontend、安全和运维之间的人类可读集成基线。它执行ADR-0017和ADR-0018，并与TASK-P8-02发布的机器合同共同冻结责任、信任与失败语义。

本文件中的“必须”“禁止”“仅”是规范要求。TASK-P8-02已把其中可机器表达的入口、结果、PlanningRun与错误语义发布为strict、versioned carrier；TASK-P8-03已实现不含HTTP的durable ingress slice，TASK-P8-04已实现不含HTTP的durable PlanningRun orchestration slice，TASK-P8-05已实现内部异步Solver Worker执行与一次业务结果恢复。因而本合同与机器文件目前仍然：

- 不声明任何新HTTP path、HTTP状态码或可运行API已经可用；
- 只把现有`import-package.v2`作为`canonical-ingress-request.v1`内唯一允许的canonical payload，不把它或旧Adapter自动提升为已实现公共入口；
- 已实现canonical ingress repository、原子Snapshot/PlanningProblem落库、内部run/attempt/work item/command/transition/audit，以及strict task、lease/checkpoint、Global Solver、fresh Validator和ScheduleVersion应用；但不实现host identity provider、公开run HTTP、Production Runtime composition、Extension SDK或Plugin Registry；
- 不关闭任何PROD_OPEN，也不证明真实宿主、UAT、容量或Production readiness。

实现若不能表达本合同的必需语义，必须先修订合同或发布新版本；不得在代码、数据库、Extension或宿主中创建未登记的私有语义。

本合同与[ADR-0017](../adr/ADR-0017-headless-canonical-json-and-dual-delivery.md)、[ADR-0018](../adr/ADR-0018-extension-sdk-runtime-and-developer-kit.md)、[Import/Normalization合同](import-and-normalization.md)、[Authorization/Audit合同](authorization-and-audit.md)、[数据权威边界](../architecture/data-authority.md)和[Schema版本规则](schema-versioning.md)共同使用。若实现需要改变canonical-only、Runtime-only Extension、Core不变或双交付决定，必须先形成新ADR，不能只改本文件。

## 2. 唯一外部产品边界

APS的唯一业务输入是宿主平台经统一Headless HTTP API提交的**versioned canonical JSON**。以下输入都不是APS公共产品合同：

- ERP、MES、WMS、CAM或其他vendor原始payload；
- CSV、XLSX、数据库表、共享目录、消息主题或第三方SDK；
- 宿主私有DTO、Enterprise Extension私有route或浏览器直接调用Core；
- 宿主、Frontend或Extension直接读写APS数据库；
- 在请求中上传、安装、下载或任意选择可执行Extension代码。

历史Raw Staging、ReferenceFileAdapter和Normalization能力可继续用于开发、测试、迁移辅助或作为宿主映射参考，但`production_binding=false`。它们不得成为第二个Production入口，不得绕过公共canonical合同、Data Validation或不可变Snapshot/Problem构建链。

公共边界遵循：

```text
Upstream systems
→ Host acquisition / mapping / redaction / source reconciliation
→ versioned canonical JSON over one Headless API
→ APS authentication / scope / contract / authority / idempotency validation
→ Data Validation → immutable Snapshot / PlanningProblem
→ asynchronous PlanningRun / Solver Worker
→ fresh independent Validator
→ immutable ScheduleVersion / read model / audit / export reference
→ Host or optional APS Frontend presentation
```

长时求解必须走异步PlanningRun生命周期。HTTP接收成功只表示请求已被受控接受或排队，不表示求解成功、结果有效、已审批、已发布或已被上游系统消费。

## 3. 组件责任矩阵

| 参与方 | 必须负责 | 明确不负责或不得执行 |
|---|---|---|
| 上游ERP/MES/WMS/CAM等 | 在自身责任域内产生业务事实和可验证source/version/record identity | 不直接调用APS内部模块，不直接写APS数据库 |
| 宿主平台 | 连接第三方系统；采集、映射、必要脱敏；处理上游冲突；绑定authenticated principal上下文；提交canonical JSON；保存source与mapping lineage；处理重试、对账和最终展示 | 不把“已发送”当作authority；不提交vendor/raw/file payload；不运行Solver/Validator/Extension；不自报角色或扩大scope；不直写APS表 |
| APS API / Runtime | 验证认证上下文、effective scope、contract/version、authority reference、idempotency和lineage；编排持久化、Core、Worker、Validator、read/export与audit；受控解析Extension | 不直接连接第三方系统；不接受未知版本/字段；不从请求选择任意代码；不在HTTP线程同步执行长时Solver |
| APS Core | 提供通用planning domain、Solver-neutral model、求解和确定性语义 | 不依赖企业项目；不含vendor mapping、企业私有流程、宿主展示或Production身份配置 |
| Solver Worker | 按不可变Problem、Policy和Limits执行attempt，持久化可追踪结果或失败 | 不修改输入；不批准、不发布；不绕过取消/超时/lease或Validator |
| Validator | 对candidate执行独立fresh correctness验证并形成版本化证据 | 不复用Solver约束结果充当独立判断；不因Extension或UI声明而放行 |
| Enterprise Extension | 仅通过指定SDK实现批准的Constraint、Objective、Planning Rule、Validation Rule、Replan Policy或Registry贡献；消费已验证canonical事实；返回规定形状结果 | 不复制/修改Core；不调用Core private API；不直写数据库；不创建私有HTTP API；不联网下载代码；不创造身份、scope、字段authority、批准或发布权力 |
| Plugin Registry | 在Runtime内解析allow-listed、版本兼容、完整性可验证的Extension与配置，并记录选择/拒绝证据 | 不接受请求上传代码；不按任意class/module/path动态加载；不把注册成功等同企业批准或Production授权 |
| 可选APS Frontend | 作为同一Headless API的普通consumer显示server read model、提交canonical command intent并呈现错误/状态 | 不是运行前置；不直连数据库；不计算Solver、Validator、KPI、state、allowed action或authority；不保存可提升权限的本地事实 |
| 运维/发布责任方 | 锁定Runtime/SDK/Extension/Developer Kit组合；配置secret、resource、retention、监控、备份恢复和rollback；保留发布审计 | 不自动升级企业项目；不以“最新版”别名替代经验证版本；不从开发Gate推断Production批准 |

责任不能通过合同外口头约定隐式转移。宿主负责上游真实性与映射，不代表APS可以跳过入口验证；APS负责拒绝和保存lineage，不代表APS成为ERP/MES/WMS/CAM事实的原始owner。

## 4. 请求所有权与canonical语义

P8公共请求必须由TASK-P8-02以strict JSON Schema表达，至少承载以下语义组；本节不规定未来wire key：

| 语义组 | 责任与约束 |
|---|---|
| contract identity | 明确document type与精确版本；禁止`latest`、隐式默认或未知major fallback |
| operation intent | 只能选择公共合同登记的业务动作；不能表达数据库操作、Python入口或任意Extension代码 |
| tenant/factory/planning scope | 请求资源范围必须明确，并与服务端authenticated scope取交集 |
| source authority | 每个所需事实可回到source system/version/record及批准的authority reference |
| mapping provenance | 宿主使用的mapping/configuration/version可追踪；APS不从vendor字段名反推 |
| request correlation | 提供安全、稳定的请求关联标识；不得包含credential或PII |
| idempotency | 对所有会产生业务或持久化副作用的command提供稳定key，由APS按受控scope解析 |
| payload fingerprint | 基于合同规定的canonical bytes形成；received-at、传输重试和显示字段不得改变业务identity |
| enterprise data | 仅允许机器合同批准的namespaced、versioned canonical extension字段，并携带独立source/authority lineage |

未知顶层字段、未知namespace、缺失版本、含vendor/raw payload、混合data plane、跨scope reference、冲突authority或无法生成稳定fingerprint时必须在创建Snapshot/PlanningRun之前拒绝。宿主不得通过自由文本、metadata或Extension配置绕过strict字段集合。

传输payload必须是strict UTF-8 JSON，并按机器合同明确处理duplicate key、non-finite number、整数/时间/单位、嵌套深度、record count与byte size。未被合同显式允许的multipart、archive、base64文件、内容编码或压缩一律拒绝；具体上限和Content-Type由P8-02/P8-07版本化，不能从ReferenceFileAdapter限制或服务器默认值推断Production策略。

APS返回由服务端拥有的稳定resource identity、当前state、immutable artifact references、allowed read/command capability projection、sanitized error和correlation evidence。返回值是公共read model，不是数据库行；宿主必须以服务端state与version为准，不得根据HTTP连接断开、UI缓存或已知旧结果自行推断成功。

### 4.1 TASK-P8-02 machine carrier

Global schema set现为additive `2.10.0`，新发布的三份JSON Schema和一份错误注册表为：

| Contract | Stable identity | 机器边界 |
|---|---|---|
| [`canonical-ingress-request.v1`](../../schemas/json/canonical-ingress-request.schema.json) | `urn:plantnexus:aps:schema:canonical-ingress-request:v1` | 只允许`CREATE_PLANNING_RUN`、exact `import-package.v2`、requested scope、source authority/mapping、Policy/Limits引用和canonical fingerprints |
| [`canonical-ingress-result.v1`](../../schemas/json/canonical-ingress-result.schema.json) | `urn:plantnexus:aps:schema:canonical-ingress-result:v1` | `ACCEPTED`绑定effective scope、idempotency、Runtime/Extension-set resolution、CREATED PlanningRun和audit；`REJECTED`固定`side_effects=NONE`且没有accepted resource |
| [`planning-run.v1`](../../schemas/json/planning-run.schema.json) | `urn:plantnexus:aps:schema:planning-run:v1` | 逐项表达既有PlanningRun state、合法最后转换、terminal、allowed actions、输入/attempt/artifact/error/audit lineage |
| [`headless-error-code-registry.v1`](../../schemas/rules/headless-error-code-registry.v1.yaml) | `HEADLESS_RUNTIME` / `headless-error-code-registry.v1` | 固定category/code/stage/retryability/action tuple；不重写product `error-code-registry.v2` |

请求fingerprint使用`canonical-json.v1`，排除`request_id`、`correlation_id`、raw `idempotency_key`与fingerprint自身，覆盖operation、精确合同版本、requested scope、authority、mapping、Policy/Limits引用、payload fingerprint及完整canonical payload。`payload_fingerprint`单独绑定嵌入的Import v2 canonical bytes；`key_reference`/`idempotency_key_reference`固定为raw key UTF-8 bytes的SHA-256，不扩散raw key。相同effective idempotency scope和key只有在request fingerprint相同时才可重放；不同fingerprint固定为`IDEMPOTENCY_CONFLICT`且零副作用。

requested scope只是客户端请求范围，不是授权证明；服务端必须把principal/policy/capability与tenant/factory/planning/data-plane/environment求交后，才可在result和PlanningRun中写入effective scope。`scope_fingerprint`是该strict effective-scope object排除自身后的`canonical-json.v1` SHA-256；五个业务字段必须与requested scope一致，不能借解析扩大请求范围。idempotency scope fingerprint还包含不进入payload的服务端principal/policy上下文，所以对外是opaque，但result与PlanningRun必须逐字相同。

所有payload record的`canonical collection + source system + source version`都必须命中唯一binding；同一collection在单个请求中不能由多个source/version或重复authority claim竞争。每个声明的source system/version必须在`source_authority.bindings`中存在，且只能有一个mapping provenance；requested factory必须存在于canonical records。未登记record、重复/歧义binding或mapping、scope和source集合不一致分别以稳定scope/authority/lineage错误拒绝。

接受结果必须与CREATED PlanningRun逐字绑定request/correlation、effective scope、ingress/payload、idempotency key/scope、Runtime resolution和transition audit；PlanningRun还必须与请求的Policy/Limits引用一致。每个run revision满足`revision = last_transition.sequence + 1`，`updated_at_utc`等于最近transition时间，最近transition及cancellation audit都必须出现在audit references中。TASK-P8-03形成初始CREATED carrier和prepared Snapshot/Problem；TASK-P8-04形成内部run读取、状态转换和attempt编排；TASK-P8-05逐字消费这些引用完成solve/validate/checkpoint/version。公开run transport仍未实现。

Runtime resolution只在result/PlanningRun的服务端字段中承载Runtime、Core、SDK、Registry protocol、Extension set/config、Developer Kit、Solver和Validator版本/指纹。请求Schema没有plugin/module/class/entry-point/artifact-path或Extension-set选择字段，任何此类添加都会因`additionalProperties=false`在副作用前拒绝。这里的`0.0.0-p8-contract-sample`仅是synthetic shape值，不表示SDK、Registry或Kit已经发布。

Schema层固定strict JSON object、已登记URN、UTC `Z`、有限JSON number与拒绝unknown字段；raw UTF-8解析还必须拒绝duplicate key和non-finite number。HTTP `Content-Type`、编码、byte/depth/record部署上限和状态码仍由TASK-P8-07在不放宽本合同的前提下版本化；在该配置形成前不得猜Production默认。

### 4.2 TASK-P8-03 durable application slice

`CanonicalIngressApplicationService`只接收`bytes`并通过服务端固定Schema目录严格解析`canonical-ingress-request.v1`；实现不依赖运行时`jsonschema`包，也不接受请求指定Schema、module、class、entry point、plugin、Extension set或artifact path。客户端requested scope先与`TrustedCanonicalIngressContext`中的principal reference、auth policy、`edit` capability、tenant/factory/planning scope、plane/environment求交；authority reference与mapping fingerprint也必须与服务端allow-list精确一致。Production carrier只有在服务端显式`production_binding=true`时机械可用，该能力不等于真实identity/authority或Production readiness。

新请求按唯一顺序执行strict contract→scope/authority→scoped idempotency lookup→pinned Runtime/build-plan resolution→既有Data Validation→Order Expansion→immutable Snapshot v2→PlanningProblem v2。Build plan由Runtime内部提供exact Policy/Limits引用、cutoff、horizon、tick、builder version和有来源的priority facts；请求只能引用Policy/Limits，不能注入这些执行参数。Data Validation FAIL、Snapshot lineage错误、Problem build错误与Runtime/persistence错误分别产生注册表中的稳定sanitized rejection，且`side_effects=NONE`。

`0006_canonical_ingress_application`新增append-only ingress、PlanningProblem和ingress audit表；它们与既有`planning_snapshots`在单一SQLAlchemy transaction中提交。事务先占用`idempotency_scope_fingerprint + key_reference`，任一步失败整批回滚；same scope/key/fingerprint返回原ingress、PlanningRun、Snapshot、Problem与audit reference，响应明确为`REPLAYED`且不新增记录；different fingerprint返回`IDEMPOTENCY_CONFLICT`。持久化记录保留canonical payload/source/authority/mapping、Runtime/Extension-set reference、build plan、quality report和prepared artifact lineage，但只保存raw idempotency key的SHA-256 reference。

初始PlanningRun仍严格处于`CREATED/revision=1/sequence=0`，其公开`artifacts`全部为`null`；P8-03内部准备的Snapshot/Problem只记录在durable ingress record中，不能冒充后续`SNAPSHOTTED/BUILDING/SOLVING`状态。创建audit复用现有`audit-event.v1`的`EDIT_SCHEDULE + PLANNING_RUN + COMMAND`合法carrier并原子append；这是初始创建证据，不扩展P3 Schema或状态机。migration downgrade会删除三张P8-03新表及其记录，但保留既有append-only Snapshot表；因此downgrade具有明确P8 ingress/Problem/audit数据损失，执行前必须保留已被下游引用的不可变证据，重新upgrade后只能按原canonical请求重建，不能手工修表。

专项unit/contract/integration/property/security/concurrency/migration测试登记为`TEST-P8-CANONICAL-INGRESS-001`。它证明synthetic请求的确定性、精确重放、冲突、跨scope/plane隔离、append-only与失败回滚；不证明公开HTTP、真实host authorization、retention/backup、PostgreSQL并发容量、Solver运行、Extension装载或企业Production数据已形成。

### 4.3 TASK-P8-04 durable PlanningRun orchestration slice

`PlanningRunOrchestrationService`从P8-03已验证的immutable ingress record materialize唯一PlanningRun资源，并在同一事务写入`planning_runs`、`planning_run_attempts`、`planning_run_work_items`、`planning_run_transitions`、`planning_run_command_records`和`planning_run_audit_records`。初始公开carrier保持`CREATED/revision=1/sequence=0/attempt=null`；内部attempt为`QUEUED`，work item逐字冻结effective scope、Policy/Limits、prepared artifact、Runtime resolution及Extension-set fingerprints。Repository按data plane绑定并在读取时复核canonical bytes、SHA-256、row projection和P8-03 source lineage。

Run update只接受`state-machines.v1`中16 states/31 pairs，并要求expected revision/state/run fingerprint的CAS；已发布artifact reference和audit history只能单调追加，terminal state没有出边。Cancel终结run并同步终结非terminal operational attempt；若最新attempt已是`DISPATCH_FAILED/TIMED_OUT`，则保留该terminal证据而只终结run。Dispatch failure或timeout本身不伪造成`FAILED`、`INFEASIBLE`或`COMPLETED`，且该run必须先retry或显式终结，不能继续沿非terminal pair推进。Retry只允许最新`DISPATCH_FAILED/TIMED_OUT` attempt，保留run state/revision并追加attempt number和immutable work item。Same scoped key/fingerprint即使run后来已终结也返回首次command result；different fingerprint、stale run/attempt、非法pair及terminal action稳定拒绝。

Migration `0007_planning_run_orchestration`是`0006`之后的additive head；work item、transition、command和audit为append-only，run/attempt只允许受控CAS更新，downgrade明确删除P8-04六表但保留P8-03 ingress/Snapshot/Problem，以批准的原canonical source重新materialize。事务故障、8-way exact race、restart read、scope/plane/Production binding、raw-key redaction、全部31 pair及downgrade/re-upgrade由`TEST-P8-PLANNING-RUN-001`覆盖。

本slice不调用broker、Celery、Redis、Solver、Validator或HTTP router，也不建立lease/heartbeat/delivery claim。`queue-ready`只表示数据库事务中存在可供P8-05消费的不可变work item；它不是已投递、已启动、已完成、可发布或Production-ready声明。

### 4.4 TASK-P8-05 asynchronous Solver Worker slice

唯一业务task只接受`message_version/planning_run_id/work_item_id/worker_id`四个字段；data plane和attempt从server-bound repository及immutable work item解析，并由启动时绑定的Runtime executor提供Repository、Global Solver、fresh Validator及ScheduleVersion application。Worker在claim前后复核P8-03/P8-04 immutable input和Runtime fingerprints，以通用job lease/heartbeat和P8专用append-only binding/checkpoint保存exact execution/result lineage。客户端、宿主或消息不能选择Extension、module、class、path、Policy、Limits、Solver或Validator。

候选必须通过既有Solver bundle合同与fresh independent Validator；结果checkpoint先于PlanningRun terminal CAS，`COMPLETED`之后才允许创建同一candidate的`READY_FOR_REVIEW` ScheduleVersion，ACK又晚于版本应用。Duplicate、检查点后崩溃及version application failure只恢复同一work/result而不再次solve；检查点前崩溃/lease expiry收敛为attempt timeout并要求P8-04显式retry。Cancel、business timeout、fingerprint mismatch、Validator failure与非candidate均不得发布成功版本。该slice不形成公开HTTP、Production broker/database拓扑、Extension加载或distributed exactly-once。

## 5. Identity、scope与授权

认证principal、capability、tenant/factory/planning scope、environment、data plane和Production binding只能由服务端可信组合解析。请求body、query、header中的业务值、UI按钮、Extension结果、数据库owner和测试actor均不能自证授权。

有效授权至少是以下信息的交集：

```text
authenticated principal reference
+ auth policy version
+ server-resolved capability
+ tenant / factory / planning scope
+ resource identity and current state
+ environment / data plane / target
→ ALLOW or DENY
```

强制规则：

- 缺失、未知、过期或冲突的认证/范围信息一律DENY，不能回退到全局factory或“admin”角色；
- 所有读取、提交、取消、重试、审批、发布、导出和audit读取均须独立scope检查；
- 跨tenant、factory、planning scope或data plane引用必须拒绝；
- 未授权响应不得泄漏目标资源是否存在，错误文本和时序不得成为枚举旁路；
- Extension只能接收Runtime已裁剪的scope context，不能扩大scope或替代authorization provider；
- Production principal→capability/resource/target映射在OPEN-002/010关闭前保持default-deny。

具体认证机制、token/assertion格式、challenge、状态码和宿主identity适配由P8-02/P8-07/P8-08在本语义下形成，不能由本合同反向推断已存在。

## 6. 数据authority与冲突处理

### 6.1 三类权威不得混淆

| Authority layer | Owner | 证明什么 | 不证明什么 |
|---|---|---|---|
| transport/source evidence | 宿主与原始系统 | 哪个source/version/record经哪个mapping进入请求 | 内容真实、冲突已获业务批准 |
| canonical acceptance | APS入口与Data Validation | 文档、引用、scope、authority carrier及业务事实在已批准规则下完整自洽 | ERP/MES事实天然真实、Production已批准 |
| planning/state decision | APS Core/Application/Validator及人工command | 哪个不可变输入产生哪个attempt、candidate、Validation和ScheduleVersion state | 外部系统已执行、企业审批或发布目标已接受 |

“宿主提交”“Schema通过”“数据库已写入”“Extension已返回”“Solver找到解”“Frontend已显示”都不是新的业务authority。

### 6.2 字段级规则

宿主必须按未来批准的字段authority matrix提交来源、版本、record和必要cutoff/revision。APS必须验证所声明authority适用于当前tenant/factory/scope、字段、数据平面和时间边界。下列情况必须fail closed：

- 同一事实存在多个来源且没有批准的优先级/仲裁记录；
- authority reference缺失、未知、跨scope、版本不兼容或已被撤销；
- source revision/cutoff与请求中的事实不一致；
- 数据缺失，只能靠last-write-wins、UI缓存、AI、Extension或通用默认补猜；
- Extension字段未登记namespace/version/source，或试图覆盖Core canonical字段。

Planning Snapshot只冻结通过验证的事实。发现事实错误必须由权威上游和宿主产生新canonical输入、新Snapshot及后继Version；禁止就地修补历史Snapshot、Problem、ScheduleVersion或audit。

## 7. Idempotency、重试与并发

所有有副作用的公共command必须使用按以下语义隔离的idempotency scope：

```text
principal/tenant + factory/planning scope + operation + idempotency key
```

请求fingerprint必须覆盖会改变业务结果或authority的全部canonical内容与精确合同版本；认证credential、received-at、网络连接信息和显示语言不进入业务fingerprint。

- same scope + same key + same fingerprint：返回首次已持久化的logical result或同一resource/attempt reference，不重复创建Snapshot、PlanningRun、ScheduleVersion、发布、导出或业务audit；
- same scope + same key + different fingerprint：明确冲突且零副作用；
- different scope：不得命中或泄漏其他scope的replay记录；
- 连接超时或未知结果：宿主必须先以same key重试或读取权威状态，不能换key并假定首次失败；
- 并发command：以服务端current state、expected version/fingerprint和CAS决定唯一winner，loser收到稳定冲突，不做last-write-wins。

idempotency retention、key最小/最大长度和可重试窗口由后续machine/operations合同显式版本化。未配置这些策略时Production不得猜测永久保存或任意过期。

## 8. 端到端lineage与审计

成功的计划链至少必须可从输出反向追踪到：

```text
ScheduleVersion / read model / export reference
← Validation report + PlanningSolution/SolverReport
← PlanningRun attempt + Policy + SolveLimits
← immutable PlanningProblem + Snapshot
← accepted canonical payload fingerprint + contract version
← host source records + source versions + authority references
← host mapping/config version
```

使用Enterprise Extension时还必须加入Runtime、Core、Extension SDK、Plugin Registry、Extension artifact/config、Developer Kit及适用policy版本与完整性fingerprint。Extension输出必须回链输入事实和所用extension point；不能只记录插件名称或“custom”。

审计至少区分request accepted/rejected、authorization decision、idempotent replay/conflict、artifact creation、attempt state、cancel/retry、validation、human decision、publication/export及Extension resolution/failure。业务state、idempotency result和成功audit必须处于同一可解释一致性边界；structured log/trace不能替代durable audit。

日志、错误、audit和CI artifact禁止包含raw bearer/token/cookie、secret、数据库DSN、SQL、stack、绝对存储路径、完整canonical payload、未经批准的PII或Extension私有配置。使用stable reference、hash、计数和sanitized diagnostic；payload retention、legal hold、SIEM与删除责任仍须由OPEN/运维合同关闭。

## 9. 版本与兼容性

公共API carrier、APS Core、Runtime、Extension SDK、Registry protocol、Enterprise Extension和Developer Kit分别版本化，不存在跨组件的隐式“latest”。

机器合同必须遵守：

- 请求显式选择精确document version；未知版本或未知major拒绝；
- additive兼容与breaking release按`schema-versioning.md`登记，禁止consumer自行容错未知字段；
- Runtime只能装载兼容矩阵明确允许、完整性可验证且配置获批的Extension；
- Enterprise Extension只依赖公开SDK，不依赖Core内部包、数据库结构或偶然的Runtime实现；
- Core/Runtime升级不自动升级任何企业项目；已有项目可继续使用已验证的Runtime/SDK/Developer Kit组合；
- 新组合只能作为新的Developer Kit候选，经兼容、安全、许可、rollback与支持窗口验证后独立发布；
- API版本兼容与SDK/Kit兼容是不同结论，任一通过都不能替代另一项。

版本不匹配必须在产生业务副作用前拒绝。禁止静默降级Extension、跳过Validation Rule、替换Objective/Policy或用默认配置继续运行。

## 10. Enterprise Extension数据与执行边界

Extension只在APS Runtime内部执行。宿主提交的是canonical业务数据与公共operation intent，不是代码或module/class/path。实际Extension artifact和配置由部署/Registry根据tenant/factory、Runtime/SDK兼容矩阵与allow-list解析；请求不得覆盖artifact digest、签名、入口点或权限。

企业特有数据只有同时满足以下条件才可进入Runtime：

1. 已由P8-02+机器合同登记namespace、版本、严格形状和大小边界；
2. 每个事实具备source/version/record、authority reference、scope和mapping lineage；
3. 不覆盖Core canonical字段，不携带vendor原始payload、credential或可执行内容；
4. 在Extension缺失、禁用、版本不兼容或校验失败时有显式拒绝或批准的fail-safe语义，禁止静默忽略；
5. Extension结果由独立Validator与Runtime边界重新检查，不能凭插件自报PASS进入ScheduleVersion。

Constraint、Objective、Planning Rule、Validation Rule和Replan Policy必须使用不同extension point和输出合同。Solver约束实现不得复用为唯一Validator；企业Validation Rule也不能降低Core hard constraints。Plugin Registry负责解析与证据，不成为字段、审批或发布authority。

## 11. 结果、双交付与对账

宿主平台和可选APS Frontend必须消费同一Headless API、相同resource identity、state、read model、错误与审计语义。不得为Frontend建立第二套Backend、私有状态机、共享数据库或浏览器侧计算分支。

APS输出至少按语义区分：请求接收、Data Validation结果、PlanningRun/attempt状态、Solver结果、fresh Validation结果、immutable ScheduleVersion、审批/发布状态、read model和export artifact reference。宿主展示可以本地化label和布局，但不能改写ID、枚举、时间、数量、错误code、correlation、lineage或allowed action。

宿主对账必须以稳定request/resource/version/attempt reference查询服务端权威状态。导出文件只是由服务端manifest、hash和完成audit共同验证的交付表示，不等于ScheduleVersion已发布或上游系统已执行。未来外部publish/回写仍通过宿主负责的独立流程，不得让APS直接连接第三方系统来绕过本边界。

## 12. 失败语义与default-deny矩阵

TASK-P8-02已由`headless-error.v1`与`headless-error-code-registry.v1`提供稳定namespace/category/code、stage、安全pointer/entity reference、expected contract、correlation、retryability和action；P8-07再映射HTTP。错误tuple必须精确命中注册表，不能把module-local或product错误强塞进不相符category。

| 失败条件 | 必须发生的阶段/结果 | 禁止行为 |
|---|---|---|
| 缺失或非法认证 | resource/application lookup前DENY并按policy记录sanitized evidence | 泄漏资源存在、fallback匿名/全局principal |
| capability或scope不匹配 | 副作用与跨scope lookup前DENY | 信任body、UI或Extension声明 |
| 非JSON、超限、未知合同/版本/字段 | canonical解析/合同Gate拒绝，零业务artifact | 宽松忽略、猜版本、进入Raw/vendor解析 |
| authority或lineage缺失/冲突 | Data Validation/Snapshot前拒绝 | last-write-wins、AI/Extension/default补猜 |
| same key/different fingerprint | idempotency conflict，零副作用 | 覆盖首次结果或创建第二attempt |
| business data invalid/unsupported | 返回完整稳定diagnostic，不创建可求解Problem | 首错后隐藏其余可确定问题、自动修复事实 |
| Extension未知/不兼容/完整性失败 | Runtime/Registry在调用Core前拒绝 | 动态下载、fallback任意版本、跳过企业规则 |
| Extension执行失败/超限 | attempt明确失败或按已批准policy fail-safe；保存sanitized evidence | 吞错、返回部分成功、泄漏stack/config |
| HTTP已接受后Worker失败/取消/超时 | 更新同一PlanningRun attempt的权威terminal状态 | 把202/连接成功当Schedule成功 |
| candidate未通过fresh Validator | 不创建可审批/发布结果，保留失败证据 | 使用Solver自检或Extension PASS替代Validator |
| persistence/audit原子边界失败 | 业务state不得提交或必须进入明确可恢复状态 | state成功但idempotency/audit丢失 |
| 输出读取越权或引用不一致 | DENY或完整性失败，不返回payload | 从对象存储/数据库路径绕过API |

错误响应必须可操作但最小披露。客户端不得依据不同错误文本判断未授权resource是否存在；服务端不得把credential、raw payload、SQL、stack或绝对路径作为diagnostic。

## 13. 开放项与Production关闭条件

| PROD_OPEN | 本合同形成的边界 | 仍需独立形成的closure evidence |
|---|---|---|
| OPEN-002 | APS只接收host canonical JSON；identity/scope/source责任与对账必须显式 | 真实host consumer、认证机制、factory scope、source/version责任、错误/重试/对账、UAT及具名authority |
| OPEN-010 | principal/capability/approval/publish必须server-derived、default-deny；Extension不能获得人类批准权 | 具名角色与责任、审批/发布矩阵、identity mapping、审计/retention和目标企业批准 |
| OPEN-011 | P8合同不接收或认可真实历史数据；synthetic仍非现实证据 | 获授权历史scope、代表性、保留/删除、匿名化、P7 successor校准与签署 |
| OPEN-012 | 异步Worker、Extension、Kit需要资源/超时/隔离/支持边界，本合同不设数值 | 目标环境capacity/SLA、worker与Extension limits、恢复阈值、支持/安全修复窗口和演练证据 |
| OPEN-014 | duration/AI fallback不能由宿主或Extension补猜 | 标准工时authority、versioned confidence/drift/fallback政策、reason及disable/rollback owner |
| OPEN-015 | canonical与Extension字段必须有字段级source/priority/revision/cutoff | 逐字段mapping、冲突优先级、revision/cutoff、Extension配置authority、用途依据与签署证据 |

上述六项及OPEN-001～015全部继续`OPEN`。ADR、本合同、Schema、synthetic test、Provider PASS、Extension兼容或Developer Kit发布均不是closure record。缺少适用closure时Production integration、身份、数据、Extension装载、容量和发布保持default-deny。

## 14. 后继Task消费边界

| 后继工作 | 必须消费本合同 | 不得越界 |
|---|---|---|
| TASK-P8-02 | 已把canonical request/result、PlanningRun、error/version/idempotency/lineage语义形成strict machine carriers和正负例 | 不实现API、DB、worker或Extension SDK |
| TASK-P8-03～05 | 建立durable ingress、PlanningRun与Worker，保存不可变lineage并执行fresh Validator | 不新增私有input或同步长时求解 |
| TASK-P8-06～08 | 组合Runtime、统一HTTP API和host identity/scope adapter | 不直连第三方、信任client role或共享数据库 |
| TASK-P8-09～11 | 发布、运维和可选Frontend消费同一API | 不宣称P7/Production readiness，不复制业务authority到Frontend |
| TASK-P8-12～15 | 形成SDK、Registry、Enterprise Extension模板和Developer Kit兼容链 | 不修改Core、自动升级企业项目或让请求选择任意代码 |
| TASK-P8-16～17 | 聚合synthetic工程Gate与独立Exit Audit | 不关闭P7现实校准、PROD_OPEN、UAT、capacity或上线授权 |

## 15. 合同验收清单

本合同只有在以下语义同时保持时才可作为P8-02输入：

- 唯一外部业务输入是versioned canonical JSON；
- 第三方采集、映射、脱敏、冲突仲裁和展示归宿主；
- API/Runtime负责认证、scope、contract、authority、idempotency、lineage和Data Validation；
- Core不反向依赖企业项目，Extension仅在Runtime内经SDK/Registry运行；
- Host、Frontend和Extension均不能直写数据库或创建第二业务入口；
- identity/capability/scope只由服务端可信组合解析；
- same-key replay、different-fingerprint conflict、CAS并发和unknown-outcome行为明确；
- Snapshot/Problem/ScheduleVersion不可变且端到端lineage包含Extension/Kit版本；
- 未知版本、字段、authority、scope、lineage、Extension或Production配置全部fail closed；
- 错误和日志结构化、可关联、最小披露且不包含raw payload/credential/stack；
- 宿主与可选Frontend使用同一API/read model；
- Developer Kit版本锁定，Core/Runtime升级不自动升级企业项目；
- OPEN-002/010/011/012/014/015只被细化，没有关闭；
- 不存在由本合同宣称已实现的Schema、API、测试、UAT或Production能力。

`TEST-P8-HEADLESS-GOVERNANCE-001`只验证上述文档治理、一致性与forbidden scope；它不是产品行为测试。`TEST-P8-CANONICAL-CONTRACT-001`验证三份Schema、五份正例、十份negative vector、offline refs、fingerprint/lineage、state/error registry对齐、97份不可变历史artifact与dependency/lock preservation。它仍不是API、数据库、Worker、Extension SDK或Production行为证据。
