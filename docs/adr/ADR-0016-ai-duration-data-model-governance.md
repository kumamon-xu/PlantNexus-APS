---
doc_id: ADR-0016
title: AI Duration Data and Model Governance
status: accepted
spec_version: 0.3.0
phase: P6
normative: true
source_sections: [15, 20, 83, 90, 97, 98, 99, 100, 110, 111]
last_reviewed: 2026-09-01
---

# ADR-0016 — AI Duration Data and Model Governance

Status: accepted

Date: 2026-09-01

Decision owners: PlantNexus APS repository governance；Production data、model promotion、rollback与retention的具名authority仍受OPEN-010/011/014/015阻塞

Requirement/NFR/ENG: REQ-003、REQ-010、REQ-011、REQ-012、REQ-014；NFR-COR-001、NFR-DET-001、NFR-TRC-001、NFR-ISO-001、NFR-SEC-001、NFR-HUM-001；ENG-ARCH-001、ENG-VER-001、ENG-ERR-001、ENG-LOG-001

Supersedes: none；落实ADR-0001、ADR-0007、ADR-0008、ADR-0009与既有OperationResourceOption duration authority

## Context

P6要形成版本化的工时预测，但现有Planning链已把每个`OperationResourceOption`的`final_duration_seconds`、`duration_source`和`source_version`定义为资源相关的标准工时事实。未来模型只能返回`p50_seconds`、`p90_seconds`、`confidence`、`model_version`、`feature_schema_version`和`fallback_reason`候选；它不是routing、resource compatibility、hard constraint、schedule state或业务权重的authority。

若直接把历史开始/结束时间、运行中记录或标准工时拼成label，会混入删失、返工、停机和未来信息；若训练/评估没有as-of cutoff、不可变版本和时间切分，结果不可复算且可能泄漏；若模型可以自动promotion、覆盖标准工时或在低置信度时继续参与计划，错误会沿Solver与重排链静默传播。真实历史范围、字段冲突决策、Production审批责任、retention期限和fallback阈值尚无closure record，不能由P6补猜。

本ADR必须在任何P6机器Schema、dataset、ML dependency、训练、runtime或规划接入之前，冻结人类可审阅的authority、privacy、provenance、promotion/rollback与fallback边界。它不授权取得或使用真实生产历史，也不创建模型生命周期业务状态机。

## Decision

### 1. 标准工时继续是唯一回退authority

每个可执行资源选项的权威标准工时仍是经过既有Data Validation的`OperationResourceOption.final_duration_seconds`，并绑定`duration_source`和`source_version`。它是resource-specific事实；不同资源选项不得共享一个无来源的全局默认工时。

模型输出是derived、advisory candidate。预测不得原地修改Import、canonical record、Snapshot、Problem、ExecutionFact或OperationResourceOption，也不得回写标准工时来源。后继P6 consumer只能在明确的预测carrier和lineage中选择“使用候选”或“回退标准工时”；历史输入字节和标准工时引用保持不变。若标准工时自身缺失、无效或来源冲突，必须由既有数据质量边界拒绝，不能由模型或通用常量补值。

COMPLETED事实中的实际资源和时间不得被预测改写；RUNNING事实的权威`remaining_seconds`及P4 freeze/effective-lock优先于预测。AI不得改变routing、resource compatibility、hard constraints、PlanningRun/ScheduleVersion/ExportJob state、OBJ-001/002/003或业务权重。

### 2. Label只来自可证明的已完成执行事实

可进入训练或评估的一个label必须同时满足：

- 记录代表一个已完成且可唯一识别的执行发生，精确关联factory、operation instance、实际resource与source record；
- source system、source version、record identity、数据平面、采集/修订顺序和as-of cutoff可追溯；
- label值来自source明确提供的权威实际处理秒数，或来自经批准、版本化的label policy对actual timestamps的确定性推导；
- timestamp推导政策明确是否包含暂停、停机、交接、等待、返工或跨班时间；没有该政策时不得默认使用`actual_end - actual_start`；
- 值通过整数秒、正值、一致时间顺序、重复/冲突和resource linkage检查；
- label eligibility、exclusion reason与policy version可重放。

RUNNING、未完成、取消、未知结束、冲突重复、无法关联实际resource、来源被撤回或只含标准工时的记录不得当作completed label。Interrupted、rework、scrap、manual correction和right-censored记录只有在authority owner明确分类、单独版本化政策并保留原始disposition后才可进入相应slice；不得静默当作普通完成样本。标准工时和模型历史输出不得复制成ground-truth label。

真实历史数据范围与source binding仍由OPEN-011/015控制。本ADR只定义eligibility contract；没有closure record时，Production历史不能进入P6 dataset。Simulation/Test可使用明确标为synthetic、non-Production的版本化事实，但不能据此宣称现实分布或Production质量。

### 3. Feature必须满足authority与as-of可得性

Feature只能从预测决策时刻或其之前已存在、可版本化且有authority的字段派生。每个feature必须绑定source field、transform、feature schema version、event/record time和as-of cutoff；unknown、conflict、unversioned mapping或cutoff不明确时fail closed。

禁止使用actual completion/end、事后停机原因、未来订单/日历/排程结果、目标值派生字段、未来修订、评估slice统计或任何在预测时刻不可获得的信息。Routing、resource compatibility、hard constraint、schedule state和权重只能作为既有authority输入或validator边界，不可由模型推断或改写。

Train、validation和test必须按时间因果顺序形成，并把同一physical occurrence、重放副本、修订链或可互相泄漏的lineage group放在同一partition。切分cutoff、grouping key、排除规则和dataset fingerprint全部版本化；具体日期、比例、窗口和最小样本门槛留给后继经授权的versioned policy，不在本ADR补值。

### 4. Privacy、retention与删除默认最小化和拒绝

Dataset、model/evaluation manifest、prediction evidence和日志只保存完成任务所需的最小字段。训练身份使用稳定的pseudonymous reference；直接姓名、邮箱、电话、自由文本、credential、token、外部endpoint和不必要的customer payload不得进入feature、label、model artifact、CI artifact或日志。

原始受控数据留在获授权的数据平面；provider/CI evidence只允许schema、fingerprint、计数、聚合指标、disposition与sanitized stable reference，不上传raw Production rows。任何extract必须绑定purpose、authority/consent或其他适用授权依据、retention policy reference、访问范围和deletion procedure。实际期限、法域和责任人未关闭时，Production extraction、训练和长期保留均default-deny。

收到权威删除/撤回要求时，后继dataset版本必须排除相关payload，并以不含原始内容的tombstone/disposition保留可审计lineage；既有模型是否需retire/retrain由具名authority记录决定，不能静默忽略。Simulation、Test、Benchmark与Production数据、credentials、storage、model registry和evidence namespace必须隔离，synthetic artifact不得promotion到Production。

### 5. Dataset、model与evaluation均不可变、可复算

每个dataset版本必须由不可变manifest绑定输入source/version/cutoff、eligibility与exclusion、label policy、feature schema、split/grouping policy、plane、code revision和content fingerprint。相同已冻结输入必须产生相同semantic fingerprint；host time、临时路径和秘密不得进入identity。

每个model artifact必须使用新版本而非覆盖，至少绑定dataset manifest、feature schema、训练代码revision、dependency/lock、algorithm/config、determinism inputs、训练environment、artifact digest和生成Task。每份evaluation必须绑定独立dataset/split、baseline标准工时、slice definitions、metric policy、model digest和完整原始machine evidence。具体ML stack、seed、metric threshold与profile分别由后继Task在使用前版本化；本ADR不选择依赖或数值。

### 6. Promotion、retraining与rollback必须由人控制

训练成功或评价通过都不自动promotion。每次可用性决定必须有一份不可变approval record，具名绑定Data Authority Approver、Model Quality/Risk Approver、APS Release Authority及适用Operations rollback authority，记录dataset/model/evaluation版本、允许的数据平面与factory scope、fallback policy、有效期/复核条件及决定理由。这些名称是待绑定的责任类别，不授予任何现有principal权限；OPEN-010/011/014/015关闭前Production promotion不可用。

定时或drift触发可生成review/retraining request，但不得自动训练后切换active model。Retraining总是生成新的dataset/model/evaluation/decision lineage。Rollback是选择先前已批准的不可变artifact，或禁用prediction provider并回退标准工时；不得覆盖artifact、删除失败证据或把rollback写成PlanningRun/ScheduleVersion/ExportJob状态。Machine model-lifecycle carrier若需要，由后继独立Task/ADR决定，本Task不创建状态机。

### 7. 任何不确定性都回退权威标准工时

以下任一条件出现时，consumer必须记录原因并使用同一resource option的权威标准工时：prediction缺失、provider unavailable/timeout、非有限或非正quantile、`p90_seconds < p50_seconds`、confidence缺失/无效/低于已批准版本化门槛、model/feature/dataset/contract版本未知或不兼容、artifact digest不符、model未批准或超出scope、privacy/authority检查失败、drift/evaluation Gate要求disable，或provenance不完整。

如果没有被批准的confidence/drift/fallback policy，等同于不可使用预测并回退。未来`fallback_reason`必须是稳定、可区分且fail-closed的机器枚举，但枚举、Schema和版本属于TASK-P6-02；阈值与evaluation policy属于TASK-P6-05。若权威标准工时也不可用，则停止该选项/计划输入并返回既有可区分数据错误，不得继续猜测。

### 8. 每次预测与消费都必须有完整lineage

后继machine contract至少要能关联：factory/operation/resource option、prediction decision time与as-of cutoff、standard duration/source/version、feature schema与dataset/model artifact、contract/code/config版本、p50/p90/confidence、provider outcome、候选是否被消费、fallback decision/reason、下游Snapshot/Problem/PlanningRun引用及correlation/audit reference。

结构化日志不是唯一provenance；raw/sanitized evidence、immutable manifest和content fingerprint必须可独立核对。Prediction lineage不得暴露秘密或raw Production payload。P2 formal Validator和P4 facts/HARD/freeze/ChangeReport regressions仍是下游独立边界，model confidence不能替代它们。

## Alternatives considered

### 让模型覆盖标准工时字段

拒绝。它会丢失工艺authority、破坏immutable Snapshot/Problem重放，并让rollback无法恢复原始来源。

### 用所有有开始时间的记录训练并将结束缺失填为当前时间或标准工时

拒绝。这把删失样本和自我复制的标准工时伪装成ground truth，且引入host-time非确定性。

### 随机切分全部历史记录

拒绝。未来修订、同一执行的副本和时间漂移会跨partition泄漏，离线结果不能代表as-of使用。

### 训练或drift触发后自动promotion

拒绝。真实approval、data scope、fallback和rollback authority未形成，自动切换会把模型风险静默传播到计划。

### 先发布Schema、选择ML依赖或运行训练，再补治理

拒绝。机器字段会提前固化未批准的authority、privacy和fallback语义；TASK-P6-02～05必须消费本ADR，而不能反向定义它。

### 用synthetic Gate代表Production历史与现实质量

拒绝。Synthetic只证明determinism和contract behavior；现实校准属于P7且仍需独立数据authority。

## Consequences

正面结果：标准工时始终可审计且可回退；label/feature leakage和删失处理有统一fail-closed语义；dataset/model/evaluation可复算；promotion与rollback保留人类控制；privacy与环境隔离在任何真实历史进入前成立。

代价与限制：没有Production authority/retention/threshold closure时只能使用synthetic或明确授权的非Production数据；dataset pipeline需保存更多disposition与lineage；同一模型不能跨plane/factory scope默认复用；低置信度或治理证据不完整会增加fallback率。上述限制是安全边界，不得用默认值放宽。

Schema、migration、dependency、训练、runtime、planning integration和model lifecycle state在TASK-P6-01中均为none。TASK-P6-02只可发布additive机器合同；P6-03～09逐Task实现与验证。`AI_DURATION_PREDICTION`继续`DEFERRED/NOT_FORMED`，本ADR的`accepted`不表示dataset、model、provider、Production authority或P6 capability已经形成。

## Rollback / Revisit gate

Accepted ADR不得删除或原地改写；语义变化必须提交新的superseding ADR。若尚无consumer，回滚TASK-P6-01可移除本ADR/合同并让P6-02保持blocked；consumer形成后，回滚必须禁用prediction provider、使用权威标准工时、保留既有dataset/model/evaluation/prediction/decision evidence，并通过新版本而非覆盖修正。

以下证据触发revisit：获得真实Production authority/retention closure；label需要明确处理暂停、返工或多资源执行；time split/grouping不足以阻止leakage；新privacy/deletion义务出现；模型需要跨factory/plane promotion；或fallback/rollback无法在不改业务状态机的情况下实现。任何revisit都必须保持标准工时authority、immutable lineage、human-controlled promotion、default-deny Production与formal Validator独立性。
