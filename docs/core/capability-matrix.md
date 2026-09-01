---
doc_id: DOC-CORE-004
title: 能力矩阵
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [7, 8, 27, 43, 81, 82, 107]
last_reviewed: 2026-09-01
---

# 能力矩阵

## TASK-P6-01 governance baseline

ADR-0016与`duration-prediction-governance`已形成accepted人类治理基线，覆盖标准工时authority、completed-label/censoring、feature as-of/leakage、privacy/retention、immutable provenance、human promotion/rollback和fallback。该基线只约束后继实现，不是capability evidence。

`AI_DURATION_PREDICTION`继续为`DEFERRED/NOT_FORMED`：没有machine Schema、dataset、model、dependency、training、evaluation、runtime或planning adapter。调用方必须继续default-deny；OPEN-010/011/014/015全部`OPEN`，P6-02仍`planned/NOT_STARTED`。Accepted ADR或docs/provider PASS不得被解释为AI输出可用或Production ready。

## P6 activation status

P6 Milestone已按用户明确授权激活，但激活和完整规划不会改变能力状态。`AI_DURATION_PREDICTION`继续为`DEFERRED/NOT_FORMED`，本次没有创建或修改预测Schema、model、dataset、runtime、planning adapter、migration、dependency或workflow；调用方不得因存在TASK-P6-00～10而启用、模拟支持或绕过既有`UNSUPPORTED_CAPABILITY`/default-deny边界。

未来P6合同计划输出`p50_seconds`、`p90_seconds`、`confidence`、`model_version`、`feature_schema_version`与`fallback_reason`。低置信度、invalid、缺失、超时或不兼容必须回退标准duration；AI只可提供候选duration/risk/confidence，不能改变routing、resource compatibility、hard constraints、schedule state或业务权重，也不能替代权威工艺数据。

P6依次规划数据/model governance、machine contract/Schema、dataset、versioned model、offline evaluation/fallback Gate、local runtime、standard ingress integration、drift monitoring、vertical Gate和独立Exit Audit。每张成员卡需要直接依赖双exact provider与新的用户授权。P6 active或未来Gate/Exit PASS都不形成P7 Reality Calibration、Production/UAT、真实data/model authority、external integration/deployment、capacity或SLA。

## TASK-P5-22 independent Exit audit

Fresh Exit审计没有改变能力状态。P5 qualification仍为九项`DEFERRED`、selected=`[]`，P5-03～20均为证据化`cancelled`；C-012～C-018的七个公开precheck继续逐项返回`UNSUPPORTED_CAPABILITY`，Decomposition与Rolling Horizon没有owner invocation，Global仍是唯一已形成策略。

本地15/15 READY只证明P5空portfolio与既有Simulation/development边界可独立复验；implementation/closure provider仍待闭环。它不形成advanced capability、P6+或Production能力，也不改变default-deny。

## TASK-P5-21 aggregate rejection evidence

Empty-selected P5 Gate没有改变能力矩阵。它在fresh run中对SECONDARY_CAPACITY、SEQUENCE_DEPENDENT_SETUP、MATERIAL_COMPETITION、BATCH_PROCESSING、SPLIT_MERGE、BUFFER_CAPACITY和PREEMPTIVE_OPERATION分别调用公开capability precheck，C-012～C-018全部精确返回`UNSUPPORTED_CAPABILITY`。Decomposition和Rolling Horizon仍为DEFERRED且没有owner invocation；selected-owner evidence manifest的report count为0。

该结果只证明未选能力持续默认关闭，不把DEFERRED解释为已支持或已取消真实需求。TASK-P5-22尚未启动，P6+和Production能力未形成。

## TASK-P5-01 qualification result

九项候选当前组合决定均为`DEFERRED`：SECONDARY_CAPACITY、SEQUENCE_DEPENDENT_SETUP、MATERIAL_COMPETITION、BATCH_PROCESSING、SPLIT_MERGE、BUFFER_CAPACITY、PREEMPTIVE_OPERATION，以及Decomposition、Rolling Horizon。原因不是已证明不需要，而是本次没有合格真实需求，现有versioned Simulation/XS-S-M Benchmark也没有证明当前显式拒绝或Global策略不可接受。selected portfolio为空；DEFERRED允许未来以新版本证据重新提案，但不授权TASK-P5-02或任何能力实现。

C-012～C-018的registry/precheck继续为`UNSUPPORTED`/`UNSUPPORTED_CAPABILITY`，Global仍是唯一已形成策略。此证据决定不形成partial support、近似支持或Production能力。

## P5 activation status

P5 Milestone现已激活，但激活与规划不改变任何能力状态。SECONDARY_CAPACITY、SEQUENCE_DEPENDENT_SETUP、MATERIAL_COMPETITION、BATCH_PROCESSING、SPLIT_MERGE、BUFFER_CAPACITY和PREEMPTIVE_OPERATION继续为`UNSUPPORTED`，DecomposedStrategy与RollingHorizonStrategy也尚未形成。调用方必须继续得到既有fail-closed rejection，不能因存在P5 Task卡而启用或近似能力。

TASK-P5-01只逐项给出必要性证据；TASK-P5-02只修订selected/deferred计划。只有对应合同包与vertical slice均取得双exact provider、feature flag保持default-off且能力registry/合同由该Task明确同步后，单项支持状态才可能改变。所有selected实现还必须保持P4 ExecutionEvent/Replan/freeze/Stability/ChangeReport/Simulator边界。Multi-Factory、alternative routing扩展、tools/fixtures专用语义、Hybrid和P6+不在本P5计划内。

## TASK-P4-12 local API capability status

ExecutionEvent append/query、ReplanRequest create/query/attempt-control/result与ChangeReport read现有`LOCAL_IMPLEMENTED_PROVIDER_PENDING`的HTTP/OpenAPI边界；这表示transport已能strict验证并委托既有P4 owner，不表示新的domain或Production capability。ReplanRequest仍无state，Simulator control、external publish、P5 candidates及Production identity/authority继续`NOT_FORMED/UNSUPPORTED`。

## P4 activation capability status

P4 Milestone已激活只表示DYNAMIC_REPLANNING进入已规划阶段，不表示能力已经实现。TASK-P4-01～13按合同、carrier、persistence、event/freeze/stability/replan、simulator、API/UI顺序形成证据，TASK-P4-14/15再分别Gate与独立审计；在此之前ExecutionEvent、ReplanRequest、ChangeReport和Execution Simulator均为`PLANNED_NOT_FORMED`。所有P5 candidate/UNSUPPORTED能力与Production capability继续保持原状态。

## TASK-P3-17 audit boundary

独立Audit确认P3范围内的version/read/comparison/edit-lock/approval-rejection/internal publish/export/API/UI/bilingual/audit能力证据完整并为READY；它不提升P4+ capability，也不改变Production capability的default-deny/PROD_OPEN条件。TASK-P3-17 audit implementation provider已验证并由本closure标为`done`，closure自身待push后复验。

## 状态定义

- `V1_SUPPORTED`：属于 V1 合同范围，但仍需按 Milestone 实现。
- `DEFERRED`：明确推迟，不能由当前实现近似。
- `UNSUPPORTED`：系统需要识别并返回 `UNSUPPORTED_CAPABILITY`。
- `PROD_OPEN`：能力边界依赖真实业务确认。

## V1 能力

| Capability | 状态 | 主要阶段 | 说明 |
|---|---|---|---|
| SINGLE_FACTORY_MULTI_WORKSHOP | V1_SUPPORTED | P1-P3 | 单 PlanningRun 跨车间统一计划 |
| DAG_ROUTING | V1_SUPPORTED | P1-P2 | 必须校验无环，不只依赖 sequence_no |
| ALTERNATIVE_RESOURCE | V1_SUPPORTED | P2 | 候选设备 ExactlyOne，设备工时可不同 |
| MACHINE_CALENDAR | V1_SUPPORTED | P2 | 非抢占任务不得跨不可用区间 |
| RELEASE_AND_MATERIAL_GATE | V1_SUPPORTED | P1-P2 | Solver 不推断物料齐套 |
| RUNNING_OPERATION | V1_SUPPORTED | P2 | 历史事实保留，未来剩余占用固定 |
| HARD_SOFT_LOCK | V1_SUPPORTED | P2-P4 | HARD 为约束，SOFT 为稳定性目标 |
| APPROVAL_AND_PUBLICATION | V1_SUPPORTED | P3 | 仅 APPROVED 可发布，发布版本不可变 |
| DYNAMIC_REPLANNING | V1_SUPPORTED | P4 | 保留事实、锁定并输出 ChangeReport |
| SECONDARY_CAPACITY | UNSUPPORTED | P5 candidate | 不得忽略或近似 |
| SEQUENCE_DEPENDENT_SETUP | UNSUPPORTED | P5 candidate | PROFILE-C 用于验证拒绝路径 |
| BATCH_PROCESSING | UNSUPPORTED | P5 candidate | 需独立能力包 |
| SPLIT_MERGE | UNSUPPORTED | P5 candidate | lot splitting 仍为 PROD_OPEN |
| MATERIAL_COMPETITION | UNSUPPORTED | P5 candidate | V1 只接受 material_ready_at |
| PREEMPTIVE_OPERATION | UNSUPPORTED | P5 candidate | V1 为非抢占 |
| BUFFER_CAPACITY | UNSUPPORTED | P5 candidate | 不可静默忽略 |
| ALTERNATIVE_MATERIAL | UNSUPPORTED | future | 不做替代料优化 |
| MULTI_FACTORY | UNSUPPORTED | future | V1 仅单工厂 |
| AI_DURATION_PREDICTION | DEFERRED | P6 | 低置信度必须回退标准工时 |
| REALITY_CALIBRATION | DEFERRED | P7 | 需要真实匿名历史快照 |

## 新增高级能力的最小交付

每项能力必须独立提供 ADR、Schema、Capability Contract、Solver 实现、Validator 实现、正反 Fixture、Benchmark 和 Feature Flag。缺少任一部分不得宣称支持。

## P0 executable registry

[`capability-registry.v1`](../../schemas/rules/capability-registry.v1.yaml) 与 [`backend/app/domain/capabilities.py`](../../backend/app/domain/capabilities.py) 双向固定上述 20 个名称和状态。`implementation_claim: false` 是强制字段：`V1_SUPPORTED` 只表示属于 V1 合同范围，不能被解释成当前 P0 已有 Solver/API/业务实现。

`require_v1_capability_contract` 的行为：

- 已登记 `V1_SUPPORTED` declaration 通过合同边界，但不证明 phase-specific implementation ready；
- `UNSUPPORTED` 或 `DEFERRED` 返回 code/category `UNSUPPORTED_CAPABILITY`；
- 未登记名称返回 `INVALID_CAPABILITY_DECLARATION` / `DATA_ERROR`；重复声明返回 `DUPLICATE_CAPABILITY` / `DATA_ERROR`；
- C-012～C-018 分别映射 Secondary Capacity、Sequence-dependent Setup、Material Balance/Competition、Batch、Split/Merge、Buffer、Preemption，不得近似执行。

TEST-CAPABILITY-001 检查 YAML 与纯枚举一致以及 explicit rejection。它不是能力实现测试。

## TASK-P1-06 Data Validation capability behavior

Canonical RoutingOperation的`required_capabilities`同时容纳versioned platform declaration与普通设备能力标签。Data Validation对registry中`UNSUPPORTED/DEFERRED`名称输出`UNSUPPORTED_CAPABILITY`；`V1_SUPPORTED`只允许声明且不要求资源伪造同名设备标签。未登记但格式合法的名称按ordinary machine capability处理，至少一个显式resource option必须指向声明全部这些标签的现有Resource，否则输出`MISSING_RESOURCE/DATA_ERROR`。

重复/空/非文本声明分别保持`DUPLICATE_CAPABILITY`或`INVALID_CAPABILITY_DECLARATION`。该逻辑形成P1 input precheck，不把DAG_ROUTING/ALTERNATIVE_RESOURCE等合同状态提升为Solver实现，也不改变20项registry状态或C-012～C-018语义。

## P3 planning allocation

P3只消费P2已验证的C-001～C-011/OBJ-001结果并增加计划版本、人机控制、内部发布、导出和审计工作区；它不改变20项capability registry或支持C-012～C-018。ExecutionEvent、DYNAMIC_REPLANNING、OBJ-002、freeze和Execution Simulator仍属于P4；任何未支持能力继续显式拒绝，不能由UI/API静默忽略。
