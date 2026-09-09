---
doc_id: DOC-CONTRACT-015
title: APS Extension SDK 与 Developer Kit 合同
status: baseline
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [4, 5, 9, 12, 30, 57, 63, 65, 93, 95, 97, 101, 103, 107, 113, 114]
last_reviewed: 2026-09-09
---

# APS Extension SDK 与 Developer Kit 合同

## 1. 当前形成范围

TASK-P8-12发布APS Extension SDK `1.0.0`的合同层：独立Python命名空间`aps_extension_sdk`、六类SPI Protocol、递归不可变输入/输出值、`extension-manifest.v1`、`extension-compatibility.v1`、`extension-error-code-registry.v1`、正反样例、严格checker和分层测试。企业项目必须针对指定SDK版本创建独立Enterprise Extension，不得复制、vendor或修改`app`/APS Core源码。

TASK-P8-13已形成Runtime loader、确定性Registry、六类受控调用adapter、API/Worker composition fingerprint和readiness/metrics边界。TASK-P8-14在其上形成独立Enterprise Extension项目合同、模板、确定性打包/clean-install/conformance工具、两个互不共享源码的synthetic示例及负例；它不形成动态发现、真实企业Solver/Validator规则、已发布Developer Kit、外部Extension API或Production信任结论。P8-15仍单独负责Developer Kit组合与兼容发布。

机器carrier位于`backend/aps_extension_sdk/contracts/`，属于SDK自身的additive contract set，不进入既有业务`schemas/**`集合，也不提升global Schema Set `2.10.0`、Runtime `0.1.0`或Core/Application `0.0.0`。P8-12关闭SHA上的既有Schema、OpenAPI、migration、Core、Runtime seam、`pyproject.toml`与`uv.lock`历史bytes仍由固定树证据验证；P8-13只把`aps_extension_sdk`加入同一Runtime wheel的内部package集合，未新增依赖且`uv.lock`不变。

## 2. 独立版本维度

| 维度 | 当前值/状态 | 兼容含义 |
|---|---|---|
| SDK API | `1.0.0` | 企业源码只导入本公开面；必须精确锁定 |
| Extension manifest | `extension-manifest.v1` | document-level exact；unknown version拒绝 |
| Compatibility carrier | `extension-compatibility.v1` | 固定当前SDK兼容与弃用规则 |
| Registry protocol | `plugin-registry.v1` | P8-13 Runtime实现必须逐字复核SDK权威resolution |
| Enterprise Extension artifact/config | 企业独立SemVer/合同 | 不由Core或Runtime版本替代 |
| Runtime | `0.1.0`既有工程候选 | P8-13增加受控装载能力但不发布新Runtime/Kit版本 |
| Enterprise project | `enterprise-extension-project.v1` | 精确绑定owner/repository/license/source/SDK/Runtime/Kit及项目内carrier |
| Developer Kit | `0.0.0-not-published` | P8-15前只表示未发布占位，不存在`latest` |

不存在可代表上述全部维度的单一“APS版本”。Runtime/Core升级不自动升级企业项目；旧项目可继续使用仍受支持的精确组合。

## 3. 公开依赖与导入边界

允许的依赖方向只有：

```text
Enterprise Extension -> aps_extension_sdk <- Runtime adapter -> APS Core
```

`aps_extension_sdk`只依赖Python标准库，不导入`app`、Backend、OR-Tools、FastAPI、Celery、SQLAlchemy、Redis、数据库或Runtime实现。Enterprise Extension只可导入`aps_extension_sdk`公开的`__all__`；不得导入`app.*`、ORM、migration、API router、worker内部消息或具体Solver/Validator builder。SDK不暴露数据库、网络、文件、时钟、authorization、publication或audit service；v1 manifest的`requested_services`必须为空。

Extension只在受信Runtime内部运行。宿主和Frontend仍只调用统一Headless HTTP API；请求不得携带module/class/path、artifact digest、SDK版本选择或代码。manifest中的entrypoint只可由Runtime从部署bootstrap显式提供的本地已批准artifact在build/deploy/startup阶段解析。

## 4. 不可变输入和返回

Runtime必须先把已授权、已裁剪的scope、facts与provenance复制为`ExtensionInputView`；嵌套object转换为`FrozenJsonObject`，array转换为tuple，非有限数、可变容器引用和非JSON对象拒绝。Extension不能获得Snapshot、PlanningProblem、ScheduleVersion或audit的可写引用。

所有SPI返回SDK frozen dataclass和递归不可变值。返回`dict/list/set`、非有限数、错误Protocol输出类型、伪造contribution ID或与manifest不一致的pair/stage时，Runtime通过`validate_protocol_output`拒绝整个调用，不产生部分constraint、candidate、version或audit成功结论。

## 5. 六类稳定SPI

| Extension point | Protocol方法 | 输入 | 返回 | v1封闭边界 |
|---|---|---|---|---|
| `CONSTRAINT` | `contribute(ConstraintContext)` | solver-neutral裁剪事实 | `ConstraintOutput` | 必须`affects_feasibility=true`并列出本artifact内独立Validation Rule |
| `OBJECTIVE` | `evaluate(ObjectiveContext)` | candidate及批准authority view | `ObjectiveOutput` | 只允许确定性整数与显式positive scale，stage=`ENTERPRISE_TIE_BREAK` |
| `PLANNING_RULE` | `apply(PlanningRuleContext)` | Problem构建前后具名view | `PlanningRuleOutput` | 输出具名版本；影响可行性时必须配Validator |
| `VALIDATION_RULE` | `validate(ValidationContext)` | Problem/Solution/authority事实 | `ValidationOutput` | 独立重算，不能信任Solver status或调用Solver builder |
| `REPLAN_POLICY` | `decide(ReplanContext)` | event/fact/lock/freeze/state/authority引用 | `ReplanDecision` | 只能返回`NO_REPLAN`或`REQUEST_REPLAN`，不能直接修改计划/状态/发布 |
| `PLUGIN_REGISTRY` | `resolve(manifests, compatibility)` | 已批准本地manifest集合 | `RegistryResolution` | duplicate/unknown/conflict/mixed/incompatible全部fail closed；不负责下载或执行 |

Protocol以结构化typing提供稳定签名；descriptor必须是对应`ContributionManifest`。P8-13 Runtime按resolved order建立adapter并提供有界调用、输出校验、metrics与readiness；P8-14 conformance已验证两个独立synthetic项目可经该入口运行。不得从synthetic调用PASS推断真实企业规则、行业默认或Production适用性已形成。

## 6. Constraint、Planning Rule与独立Validation

每个Constraint恒为feasibility-affecting。Planning Rule必须显式声明是否影响可行性。影响可行性的贡献必须：

1. 在`validation_rule_ids`列出一个或多个同artifact Validation Rule；
2. 对应Validation Rule在`validates_contribution_ids`反向列出目标，形成对称pair；
3. Solver/Planning entrypoint与Validator entrypoint不同，execution domain分别为`SOLVER|PLANNING`与`VALIDATOR`；
4. Validator从独立Problem/Solution/authority view重算，不导入或复用Solver constraint builder；
5. Validation FAIL时整个candidate拒绝，不能降级为warning或使用Solver status覆盖。

该结构证明可检查的配对和执行域分离，不证明任意企业实现的公式已经独立。P8-14 conformance会检查源码/import、正反fixture、mutation/property和独立实现结果；企业仍须为自己的规则提供业务验收证据。

## 7. Objective层级

Core目标顺序继续为`OBJ-001 Delivery -> OBJ-002 Stability -> OBJ-003 Makespan`。SDK v1唯一批准企业插槽是其后的`ENTERPRISE_TIE_BREAK`，只能在全部Core objective值相等时区分候选；因此Enterprise Objective不能插入Delivery/Stability/Makespan之前或之间，也不能删除、重权、混合或改写Core目标。

`ObjectiveOutput`必须给出stable metric ID、`MINIMIZE|MAXIMIZE`、整数value、正整数scale、authority reference和不可变evidence。float、隐式权重、Big-M blend、未批准stage或缺失authority均无有效输出。

## 8. Replan Policy边界

`ReplanContext`和`ReplanDecision`逐字绑定execution fact、HARD lock、freeze window、state machine与publication authority reference。`validate_protocol_output`要求返回绑定与输入完全相同；任何替换或遗漏以`FORBIDDEN_BOUNDARY_ACCESS`拒绝。

Replan Policy只能决定是否向既有application workflow请求一次重排，不能移动COMPLETED/RUNNING事实、放松HARD/freeze lock、添加状态转移、创建/发布ScheduleVersion、批准结果或直写数据库。实际候选仍必须走既有Solver、fresh Core Validator及配对Extension Validation Rule。

## 9. Manifest与确定性Registry resolution

`extension-manifest.v1`要求精确字段：SDK/Extension版本、artifact digest/package、configuration contract/schema digest、SDK/Runtime半开兼容区间、Registry protocol、contributions、空service集合、source commit/dependency lock、固定execution boundary及排除自身字段后的canonical SHA-256。

每个contribution固定stable ID、extension point、SPI version、entrypoint、execution domain、0～10000 order、capability、feasibility/pair与objective stage。数组必须无重复且按规范顺序；contribution按`(order, contribution_id)`排序。一个resolved set中extension ID和contribution ID全局唯一，且v1最多一个Replan Policy和一个Plugin Registry。

`resolve_manifest_set`先拒绝空集合、mixed SDK、重复ID、exclusive冲突、unsupported manifest/Registry或不包含locked SDK的range，再按extension ID和contribution order确定性排序；resolution fingerprint覆盖SDK、排序后的artifact manifest fingerprints和贡献identity。它不导入entrypoint，也不证明artifact签名、allow-list或Runtime readiness。

## 10. SemVer、兼容与弃用

SDK只接受canonical `MAJOR.MINOR.PATCH`，不接受`latest`、alias、caret、prerelease或浮动范围。v1 compatibility carrier把SDK精确锁为`1.0.0`并声明区间`[1.0.0, 2.0.0)`：

- patch：只允许缺陷、文档或安全修复，不改变业务可观察语义；
- minor：只允许optional additive API/contract，旧Extension replay仍须通过；
- major：任何删除、重命名、签名/返回/错误/层级或语义breaking change；必须生成新Developer Kit候选；
- 企业artifact必须按Developer Kit锁定exact Runtime/SDK/config/digest，不因兼容range自动升级；
- deprecated API在同一major内保留，必须给出replacement；移除只能发生于新major；
- support end必须由具名版本发布，不允许静默替换或原地覆盖已发布artifact。

SDK兼容只表示contract层面可测试，不替代Runtime、Enterprise Extension、Developer Kit、安全、license、rollback或Production兼容结论。

## 11. 稳定错误与原子失败

`extension-error-code-registry.v1`是`APS_EXTENSION_SDK`命名空间的唯一v1错误列表。主要失败映射为：

| 条件 | Code | 必须结果 |
|---|---|---|
| unknown point/SPI/manifest/Registry | `UNKNOWN_EXTENSION_POINT` / `UNSUPPORTED_*` | 装载前拒绝 |
| duplicate Extension/contribution、exclusive冲突 | `DUPLICATE_*` / `REGISTRY_CONFLICT` | 无resolution |
| 缺失或非对称Validator pair | `MISSING_VALIDATION_PAIR` / `INVALID_VALIDATION_PAIR` | 无constraint/candidate |
| 非法Objective stage/值 | `INVALID_OBJECTIVE_STAGE` | 无objective term |
| mutable/错误返回类型 | `MUTABLE_VALUE` | 丢弃完整调用结果 |
| mixed/incompatible SDK | `MIXED_SDK_VERSION` / `INCOMPATIBLE_SDK_VERSION` | Runtime调用Core前拒绝 |
| fingerprint或边界伪造 | `FINGERPRINT_MISMATCH` / `FORBIDDEN_BOUNDARY_ACCESS` | 无部分artifact或业务副作用 |
| 已移除/unsupported弃用项 | `DEPRECATED_UNSUPPORTED` | 显式升级/回退决定 |

错误只携带safe field/message，不得泄漏raw payload、配置、token、DSN、路径、stack或企业secret。P8-13必须把这些内部错误映射到既有Runtime错误边界；不得借本注册表新增外部HTTP envelope。

## 12. 生命周期和信任

Enterprise Extension是受信任的in-process部署代码，不是安全沙箱。v1固定`load_phase=BUILD_DEPLOY_STARTUP_ONLY`、`trusted_in_process=true`、`sandboxed=false`、`request_code_selection=false`、`network_install=false`、`external_api=false`、`database_access=false`。禁止请求级上传、URL/git/pip下载、entry-point全局扫描、hot reload、浏览器/宿主执行或插件自授capability。

Runtime必须在任何业务副作用前验证artifact digest/HMAC allow-list标签、manifest/config、SDK/Runtime compatibility和resolution fingerprint；API与Worker必须得到同一resolution。Extension异常、timeout或无效输出拒绝完整调用并将对应readiness置为DOWN，不能吞错或产生部分成功。当前同进程timeout只丢弃晚到结果，不能强制终止恶意实现。

## 13. Machine acceptance与回滚

`scripts/p8_extension_sdk_contract_check.py`生成`p8-extension-sdk-contract-report.v1`，绑定TASK、Test ID、Diff base、版本和七项检查：Schema/positive resolution、四项negative vector、错误注册、六SPI/immutability、import boundary、Task scope/历史bytes、SDK artifact manifest。CI的FULL required topology中该步骤不可跳过。

`scripts/p8_runtime_extension_registry_check.py`生成Registry主报告、resolved-extension manifest、安全报告和threshold-null工程benchmark，绑定`TASK-P8-13`、`TEST-P8-PLUGIN-REGISTRY-001`、Diff base、十项检查及signature/digest/config/runtime compatibility/duplicate/conflict/mixed/unknown/crash/timeout/no-side-effect负例。报告只含稳定identity、fingerprint、计数和耗时，不含artifact/config payload、HMAC key、DSN、路径或异常细节；该步骤同样进入FULL required topology。

`scripts/aps_extension_conformance.py`提供`scaffold`、`check`和`check-set`三个用户入口。`check`必须验证strict项目描述、owner/repository/license、exact SDK hash lock、manifest/config/schema/source identity、import/Core-copy/确定性边界、双构建、clean SDK-only安装和项目测试，再通过P8-13 Runtime执行六类SPI；`check-set`还验证跨项目duplicate/conflict/compatibility和确定性resolution。`scripts/p8_enterprise_extension_kit_check.py`生成P8-14主报告、依赖/import扫描、Extension-set manifest和threshold-null benchmark，绑定`TASK-P8-14`、`TEST-P8-ENTERPRISE-EXTENSION-KIT-001`、Diff base、十二项检查及八类负例。FULL required topology必须不可跳过地生成并上传这些证据。

分层测试覆盖contract、unit、property、security与validation mutation；同时完整相关Backend suite、Ruff、Pyright、SCA/license、docs/diff、CI preflight及exact Provider HIGH_RISK evidence必须通过。样例仅为synthetic contract evidence，不代表真实企业规则、容量、质量或Production授权。

P8-13形成consumer后，回滚非空Extension应移除服务端catalog/artifact配置并恢复上一已验证default-empty Runtime artifact，而不是在请求中禁用校验或删除Core。P8-14项目或artifact不合格时应停止交付并保留失败报告；任何版本一旦进入已验证Kit或企业artifact，不得覆盖，修复必须发布新版本并保留旧bytes/replay。P8-14的`0.0.0-not-published`不得包装或命名为正式Developer Kit。
