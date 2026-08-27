---
doc_id: DOC-FRONTEND-003
title: P3 Approval Publication 与 Export 人工控制流程
status: baseline
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 66, 67, 68, 77, 78, 94]
last_reviewed: 2026-08-27
---

# P3 Approval Publication 与 Export 人工控制流程

## TASK-P3-16 localization boundary

Approve/Reject/Publish/Export、确认/失败/unknown-outcome与Audit文案已按[`official-zh-cn-terminology.v1`](official-zh-cn-terminology-map.md)提供`zh-CN`/`en-US`展示；reason仍是用户原文且不机器翻译。`APPROVE/REJECT/PUBLISH/REQUEST_EXPORT`、ScheduleVersion/ExportJob state、target、error code/reason、idempotency/correlation和package facts继续为英文机器值，并在未知时显示raw值。中文按钮不增加capability，也不把Simulation TEST actor、`SIMULATION_INTERNAL`或PUBLISHED翻译成Production authority/approval。本地双语human-control E2E通过，exact provider待形成，最终由TASK-P3-17独立审计。

## TASK-P3-14 control-flow Gate

两轮Chromium与Backend replay共同复验READY_FOR_REVIEW decision、APPROVED-only publication、REJECTED/DRAFT fail closed、PUBLISHED immutable、ExportJob retry/download及audit可见性。Gate不修改control surface或actor模型，也不把Simulation TEST actor升级为真实审批/发布权威。

## TASK-P3-13 browser control flow

READY_FOR_REVIEW只在server允许时显示Approve/Reject并要求credential-safe reason；APPROVED publication必须打开accessible dialog、再次输入reason并勾选`SIMULATION_INTERNAL`确认。成功仅接受server authoritative Version，失败不产生success toast。PUBLISHED export与publication分离：create后显示Job事实，`EXPORT_FAILED`只提供显式same-contract retry，只有`EXPORTED`且artifact manifest完整时提供download。

Double click由同步in-flight guard收敛为一次request。对network/5xx，UI显示“outcome unknown”、保留exact command/key/fingerprint并禁用retry；完成authority refresh后才允许原请求重放。401/403/409/422属于已知失败且不保留blind retry。Audit link只读取append-only event，不修改或补写decision/publication/export事实。

本文件固定人机控制流程和UI可见边界。TASK-P3-01没有批准任何真实人、组织、身份提供商、Production target或发布行为。

## 控制原则

- UI按钮不是authority；server依据已认证principal、capability、environment/data plane、Version state和target重新判定。
- 每个状态改变命令必须包含非空`reason`、idempotency key、expected state/content fingerprint和correlation ID。
- ScheduleVersion content不可变；decision只改变既有允许pair的state，修订只创建新DRAFT。
- internal Publish与Export是两个不同副作用。Publish改变ScheduleVersion/current reference；Export创建ExportJob与成果包，不能调用或推断Publish。
- Production authority/target未配置时default-deny；Simulation test policy不能映射成真实角色。

## 决策与副作用矩阵

| UI action | Source state | capability | 成功结果 | 明确拒绝 |
|---|---|---|---|---|
| Approve | `READY_FOR_REVIEW` | `approve` | `APPROVED` + one audit event | 其他state、缺reason、stale、unauthorized |
| Reject | `READY_FOR_REVIEW` | `reject` | `REJECTED` + one audit event | 其他state、缺reason、stale、unauthorized |
| Publish | `APPROVED` | `publish` | internal `PUBLISHED`、current reference、必要时旧current `SUPERSEDED`、audit | DRAFT/READY/REJECTED/PUBLISHED/SUPERSEDED、unknown/Production target |
| Export | `PUBLISHED` | `export` | 新建或重放ExportJob；不改ScheduleVersion state | 非PUBLISHED、unknown target、unauthorized、mixed plane |
| View audit/history | 任意 | `audit` | append-only projection | unauthorized/cross-plane |

`PUBLISHED → SUPERSEDED`只能作为一次新Version成功成为current的原子publication transaction的一部分，不能由普通UI单独触发。历史rollback只允许“以历史Version为参考派生并重新走审批/发布”，不得把旧PUBLISHED原行改回current状态；P4 Replan不在本流程中。

## UI序列

### Approve / Reject

1. 刷新Version、ValidationReport、state和server `allowed_actions`；
2. 显示Version/lineage、决策影响与必填reason；
3. 提交expected state/fingerprint、idempotency key和correlation；
4. 仅在server返回已提交state与audit ID后显示成功；
5. `409/403/422/500`保持明确失败，刷新后由用户决定是否重试。

### Publish

1. 只在server确认`APPROVED`、`publish` capability、明确`SIMULATION_INTERNAL` target时展示P3动作；
2. 对话框展示将成为current的Version、当前Version、可能的supersession和“不是Production发布”；
3. 提交一次幂等请求；
4. same-key/same-request返回同一publication result且不重复audit/current switch；
5. same-key/different-request、并发冲突或target不明均显示失败，不自动换key重试。

### Export

1. 只从PUBLISHED Version创建ExportJob；
2. UI分别显示CREATED/EXPORTING/EXPORTED/EXPORT_FAILED/CANCELLED，不把Job排队或文件存在写成成功；
3. `EXPORT_FAILED → EXPORTING`必须是显式retry，使用可追踪attempt且不得触发Publish；
4. 下载只在EXPORTED且manifest/hash验证通过时可用；partial package不得暴露。

## Idempotency scope

| 动作 | 最低scope/fingerprint内容 | replay保证 |
|---|---|---|
| Approve/Reject | plane + action + Version + key；state/content/reason/actor capability | 相同decision/result/audit，不重复transition |
| Publish | plane + target + Version + key；approved fingerprint/current precondition | 相同publication result，不double publish/supersede |
| Export | plane + target + Version + package profile + key | 相同ExportJob/artifact identity，不重复成功包或Publish |

不同fingerprint复用key统一返回`IDEMPOTENCY_CONFLICT`/HTTP `409`。客户端不得通过生成新key掩盖不确定结果；必须先查询原result。

## 失败可见性

- `AUTHORIZATION_DENIED`=`403`：不显示成功、不过度透露所需角色；Production未配置时同样拒绝。
- `INVALID_STATE_TRANSITION`=`409`：显示实际state并要求刷新，不自动改变命令。
- `IDEMPOTENCY_CONFLICT`=`409`：显示原请求引用，不自动重放不同内容。
- `VALIDATION_FAILED`=`422`：Version不可进入批准/发布链。
- `EXPORT_FAILED`=`500`：显示ExportJob/attempt/correlation和显式retry条件，不改变ScheduleVersion。
- 网络超时结果未知时先按key查询，不显示成功toast，也不直接换key提交。

上面三个P3 module-local reason code在TASK-P3-02前不是global error registry新增项；机器carrier必须保留现有七类category兼容与sanitized details，不能静默扩写已发布registry bytes。

## Audit 与隐私

每次成功state change、publication/export attempt及允许记录的拒绝必须关联Version、before/after、actor reference/capability、reason、target、request fingerprint、idempotency reference、correlation、result/error和UTC时间。认证token、Secret、raw credential、SQL/stack trace和未经分类的敏感payload不得进入浏览器trace、日志或audit。

## 环境边界

P3 E2E只可使用隔离的Simulation plane、明确test principal和`SIMULATION_INTERNAL` target。Production UI不得暴露Simulation入口；OPEN-002/010/015未关闭前不存在真实approve/publish/export target。P3完成不等于UAT、Production approval、publish authorization或deployment readiness。

## TASK-P3-07 server decision status

Approve/Reject的server application guard现已形成：只接受READY、exact fingerprint、non-empty sanitized reason、对应capability与resource scope；成功state与audit原子，same-key exact replay不重复event，并发Approve/Reject只有一个CAS winner。APPROVED只开放未来`publish`动作，REJECTED保持终态且只能copy-on-write修订。

本Task没有实现按钮、dialog、route、HTTP transport或E2E；Frontend不能据此显示真实用户角色，也不能把test actor、carrier `allowed_actions`或APPROVED状态解释为Production authority/publish。P3-11～13仍须单独实现并验证上述UI序列。

## TASK-P3-08 server publication status

Server application现形成APPROVED-only internal publish guard：exact capability/scope/test policy、source fingerprint与previous-current precondition通过后，单事务提交新PUBLISHED、旧SUPERSEDED、current CAS、PublicationResult与audit；same-key replay不double publish/supersede，并发只有一个current CAS winner。DRAFT/READY/REJECTED以及已PUBLISHED source均无业务副作用地拒绝。

仍没有按钮、confirmation dialog、route、HTTP transport或E2E，Frontend不能自行拼装current、假设allowed action等于授权、自动Publish或把`SIMULATION_INTERNAL`显示成Production channel。Export按钮/Job/包仍等待P3-09/10/13。

## TASK-P3-10 control-flow transport

Approve、Reject、Publish、Export create/read/retry/cancel现有HTTP operation，但transport不改变已有application的authorization-before-lookup、state/CAS、idempotency、audit与Publish/Export分离。401表示缺失/非法认证，403表示capability/scope或Production default-deny，409表示stale/state/key conflict，422表示carrier/validation；UI不得将任一失败渲染为成功。本Task无Frontend/browser/E2E、真实identity或external publish，因此P3-13与Production门仍未形成。
