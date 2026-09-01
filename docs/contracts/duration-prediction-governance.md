---
doc_id: DOC-CONTRACT-P6-DURATION-GOVERNANCE
title: Duration Prediction Governance Contract
status: baseline
spec_version: 0.3.0
phase: P6
normative: true
source_sections: [15, 20, 83, 90, 98, 99, 100, 110, 111]
last_reviewed: 2026-09-01
---

# Duration Prediction Governance Contract

Contract status: accepted human governance baseline

Decision authority: [ADR-0016](../adr/ADR-0016-ai-duration-data-model-governance.md)

Machine contract status: additive `2.9.0` / `FORMED_SIMULATION_CONTRACT_V1`；见[Duration Prediction Machine Contract v1](duration-prediction-machine-contract.md)。TASK-P6-03/04形成有界Simulation dataset与baseline model/replay，TASK-P6-05形成独立development offline evaluation/fallback Gate；仍无runtime或Production authority

Capability status: `AI_DURATION_PREDICTION = DEFERRED / CONTRACT_V1 + SIMULATION_DATASET_V1 + BASELINE_MODEL_V1 + OFFLINE_GATE_READY / NO_RUNTIME`

## TASK-P6-05 executable evaluation-governance projection

`SIM-P6-OFFLINE-EVALUATION-001@1.0.0` / `SIM-ASSUMPTION-024`在任何held-out label读取前冻结validation/test-only selection、train-label zero-read、exact metrics、partition/family slices、model-versus-standard no-regression、coverage、`9/10` confidence和fallback precedence。Frozen结果为model/standard MAE `11/20`秒、P90 coverage `4/4`与最低confidence `55/57`，所有slice满足门槛，因此只形成`READY_FOR_SIMULATION_RUNTIME`。

任何missing/invalid/low-confidence、quantile、lineage/version/digest、model、timeout、authority或privacy错误都选择同resource option的exact standard duration并产生stable reason；invalid standard duration fail closed。Gate不调参、不读取train label、不换split、不修改P6-02 carrier，也没有promotion、runtime、Planning或Production authority。OPEN-010/011/014/015仍阻塞真实policy/owner/data，P6-06必须独立授权。

## TASK-P6-04 executable model-governance projection

`SIM-P6-BASELINE-MODEL-001@1.0.0`把本合同的model provenance部分投影为可执行fail-closed规则：只消费P6-03 exact dataset/manifest和4条train row；固定required/active/zero-weight feature、exact rational grouped-median算法、rounding、margin、dependency lock、normalized-LF code identity、scope与deterministic timestamp。Validation/test label不进入训练，RNG、host clock、environment default和未声明dependency均不可成为隐式输入。

Safe model、ModelManifest、configuration、decision、standard-duration rollback和replay全部使用content-derived identity。Loader拒绝unsafe executable serialization及version/digest/config/dataset/dependency/code/scope漂移，atomic writer在complete validation/build后才replace。Provider只保存safe model、manifest和无raw-row/no-label replay/report；baseline estimate没有confidence/evaluation/promotion/runtime authority。OPEN-010/011/014/015继续阻断Production model/promotion，P6-05仍须独立授权。

## TASK-P6-03 executable policy projection

`SIM-P6-FEATURE-DATASET-001@1.0.0`把本合同的数据部分投影为可执行fail-closed规则：只允许已登记Simulation/Test source；只以`COMPLETED/NORMAL`显式actual-processing seconds为label；RUNNING/INTERRUPTED稳定排除；feature逐项满足available-at不晚于decision cutoff；split按label availability的UTC half-open window且同一lineage group不可跨partition。标准工时只是as-of feature，不是label或预测授权。

Purpose/access、no-PII/no-target、retention/deletion、source/record fingerprint、builder code revision和完整manifest均为强制输入/输出。Atomic writer在全量验证及canonical build完成后才同目录replace，任何错误保持既有target且不留partial artifact。Source和完整rows不进入Provider artifact；OPEN-010/011/014/015继续阻断Production extraction/training/promotion。

## 1. Purpose and scope

本合同是P6数据、label、feature、privacy、dataset/model/evaluation provenance、promotion/rollback及标准工时fallback的唯一人类语义入口。TASK-P6-02已用四份严格Simulation v1 carrier逐项承载可机器表达的部分；TASK-P6-03/04已分别形成dataset与baseline model边界，TASK-P6-05～09仍必须引用并实现各自边界。若后继机器设计无法表达，必须停止并提交新ADR或扩卡，不能在代码中增加默认语义。

本合同本身不授权读取真实历史或形成Production data/model authority。P6-03/04的独立授权只允许仓库内synthetic dataset与dependency-neutral baseline训练/replay；不运行formal evaluation/Benchmark、不接入Planning，也不改变P0～P5合同、Schema、状态机、Solver、Validator或Execution/Replan链。

## 2. Authority table

| Subject | Authoritative source | Derived/advisory use | Fail-closed rule |
|---|---|---|---|
| Standard duration | validated `OperationResourceOption.final_duration_seconds` + `duration_source` + `source_version` | 同resource option的fallback与baseline | 缺失、无效或来源冲突时拒绝该选项；不得猜默认值 |
| Actual execution | versioned completed ExecutionFact/source record及其实际resource/time lineage | eligible label candidate | 未完成、冲突、删失或resource不明时排除 |
| Label | authority-approved observed processing seconds，或versioned label policy的确定性推导 | dataset target | 不得用标准工时、模型输出、host time或未定义`end-start`替代 |
| Feature | as-of cutoff前可获得的versioned authoritative field + transform | prediction input | future、target-derived、unknown authority或unversioned transform一律拒绝 |
| Prediction | immutable approved model对固定feature contract的derived output | candidate duration/risk/confidence | 不得覆盖authority；任何不确定性回退标准工时 |
| Routing/resource compatibility/constraint/state/weight | P0～P4既有owner | 可作为只读边界或输入 | 模型不得生成、修改或绕过 |
| Promotion/rollback | 具名人类authority的immutable decision record | 选择approved model或禁用provider | OPEN未关闭或记录不完整时Production default-deny |

“Data Authority Approver”“Model Quality/Risk Approver”“APS Release Authority”“Operations rollback authority”只是必须在closure record中绑定的责任类别，不是仓库内已获授权的角色或principal。

## 3. Label eligibility and censoring contract

### 3.1 Required eligibility

每个eligible row必须绑定：

- factory、operation instance、actual resource和唯一execution occurrence；
- source system/version/record identity、plane、revision/order与as-of cutoff；
- completed disposition及权威actual processing duration，或获批准的label policy/version；
- label unit=`integer seconds`、正值、时间顺序与resource linkage检查；
- eligibility decision、exclusion reason、policy version和row/content fingerprint。

若source只提供actual start/end，label policy必须明确pause、downtime、waiting、handoff、rework和calendar crossing的包含关系。没有逐字政策即row ineligible，不得默认以wall-clock差计算。Source明确提供的actual processing duration与timestamp推导冲突时，按OPEN-015的field-authority closure处理；未关闭时排除并报告冲突。

### 3.2 Mandatory exclusions

以下记录不得进入普通completed-duration label slice：RUNNING/未完成、取消、右删失、结束未知、重复且fingerprint冲突、实际resource未知、source被撤回、人工修订无lineage、只有标准工时、由旧模型生成、或prediction cutoff之后才形成的信息。

Interrupted、rework、scrap、manual correction与多资源执行必须保留自己的disposition。只有在独立authority和versioned label policy明确后才可作为专门slice；不得丢弃标签后混入普通完成样本。Excluded row要保留sanitized reason/count和source fingerprint，不能静默过滤。

### 3.3 Historical scope

OPEN-011/015 closure前，真实Production history、字段映射和冲突优先级未授权。P6-03只能消费明确获授权的数据平面；synthetic记录必须携带synthetic provenance和`production_binding=false`，不得promotion为Production evidence或现实精度声明。P7 Reality Calibration不由本合同提前执行。

## 4. Feature as-of and leakage contract

预测决策时刻记为`as-of cutoff`的人类概念；TASK-P6-02才定义机器carrier。Feature row只能包含cutoff时已存在并可被consumer合法读取的authority字段。Transform必须pure、versioned、deterministic，并记录source field/version、event/record time与code revision。

禁止项包括：actual completion/end或duration target、事后downtime/rework原因、未来订单/日历/排程/修订、未来聚合、test slice统计、target encoding跨越cutoff、evaluation outcome、后继model output，以及由未来ScheduleVersion或ChangeReport回填的值。

Train/validation/test必须按时间因果顺序切分。相同execution occurrence、重复/修订链、同一source record的派生副本和其他可互相泄漏的lineage group必须位于同一partition。Split cutoff、group key、eligibility snapshot和dataset fingerprint不可变且可复算。P6-03/04现只允许各自versioned synthetic policy与train-only baseline；任何其他日期、比例、window或sample policy未获批准时不得训练，且当前训练PASS绝不等于评价通过。

## 5. Privacy, retention, consent/authority and deletion

### 5.1 Data minimization

仅保留预测和审计所需字段。稳定pseudonymous references替代人员或客户直接标识；姓名、邮箱、电话、自由文本、credential、token、secret、外部endpoint及无关payload不得进入feature/label、model、evaluation、prediction evidence、CI artifact或log。

### 5.2 Authorized purpose and retention

每个extract/dataset必须绑定purpose、source authority、适用的consent或其他获批准使用依据、访问scope、retention policy reference、deletion procedure和owner closure record。Repository不猜测法域、期限或个人责任。任一引用缺失时，Production extract、training、长期storage与artifact upload全部拒绝。

Raw controlled rows保留在获授权数据平面。Provider/CI只保存schema、version、fingerprint、sanitized reference、count、aggregate metric和disposition；不得上传raw Production row。Simulation/Test/Benchmark/Production使用独立database、credential、namespace、model registry和evidence location，禁止跨plane join或promotion。

### 5.3 Deletion and withdrawal

权威删除或撤回请求到达后，新dataset必须排除相关payload并记录不含原始内容的tombstone/disposition。已有model的retire/retrain决定必须由具名authority形成新记录；不得原地修改artifact或删除audit lineage。Retention/deletion细节未形成时Production保持default-deny。

## 6. Immutable provenance contract

### 6.1 Dataset manifest

P6-03 dataset manifest已绑定source/version/cutoff、plane/factory scope、eligibility/exclusion与label policy、feature schema、split/group policy、code revision、row/content counts及content fingerprint。相同冻结输入必须得到相同semantic fingerprint；wall clock、host path和secret不得参与identity。后继dataset只能发布新version/identity，不能改写该manifest。

### 6.2 Model manifest

P6-04 ModelManifest已绑定dataset manifest、feature schema、training code revision、dependency lock、algorithm/config、determinism inputs、training environment、model version和artifact digest，并引用decision、rollback与replay。Retraining只能生成新版本，不能覆盖旧artifact；当前`SIMULATION_EVALUATION_ONLY`不是lifecycle state或Production approval。

### 6.3 Evaluation and prediction lineage

未来evaluation至少绑定independent split、standard-duration baseline、slice definitions、metric policy、model digest和machine evidence。每次prediction/consumption至少关联operation/resource option、decision time/cutoff、standard duration/source/version、feature/dataset/model/contract/code/config版本、p50/p90/confidence、provider outcome、consume/fallback decision与reason、correlation/audit以及下游Snapshot/Problem/PlanningRun reference。

结构化日志只作关联入口，不是唯一provenance。Lineage必须可用manifest/fingerprint独立核对，并不得泄漏raw Production payload。

## 7. Model review, promotion, retraining and rollback

Training PASS、evaluation PASS或drift signal都不自动改变可用model。一次promotion decision必须是immutable且具名，绑定data/model/evaluation versions、allowed plane/factory scope、fallback policy、expiry/review condition、决定理由和四类责任authority。OPEN-010/011/014/015任一适用closure缺失时，Production promotion不可表示、不可执行。

Monitoring可以生成review或retraining request，但不得自动切换模型。Retraining产生全新的dataset/model/evaluation/decision chain。Rollback只允许选择scope相容且先前approved的immutable model，或disable provider并回退标准工时；禁止覆盖artifact、擦除失败证据或借PlanningRun/ScheduleVersion/ExportJob状态表达model lifecycle。

## 8. Standard-duration fallback contract

后继consumer必须按下列决策表fail closed：

| Condition | Required action | Required evidence |
|---|---|---|
| Approved、compatible、完整lineage，且confidence/evaluation/drift policy允许 | 候选可进入后继独立validation；仍不得覆盖authority | model/feature/dataset/contract版本、quantiles、confidence、decision reference |
| Prediction缺失、provider unavailable或timeout | 使用同resource option标准工时 | stable unavailable reason、standard source/version |
| Quantile非有限、非正或`p90_seconds < p50_seconds` | 拒绝candidate并回退 | invalid-output reason与sanitized observed shape |
| Confidence缺失/无效/低于approved threshold，或threshold policy不存在 | 回退 | confidence/fallback policy version或policy-missing reason |
| Version unknown/incompatible、digest mismatch、model unapproved/out-of-scope | 回退并报告治理错误 | exact mismatch/scope reason |
| Privacy/authority/provenance检查失败 | 不调用或不消费model；回退 | fail-closed governance reason |
| Drift/evaluation Gate要求disable | 禁用该model scope并回退，等待人类决定 | gate/evaluation reference |
| 权威标准工时也缺失/无效/冲突 | 停止该option/input并返回既有可区分数据错误 | data-quality evidence；禁止默认值 |

`fallback_reason`稳定枚举、unknown-field policy与exact Schema/version compatibility已由TASK-P6-02的`duration-prediction.v1`形成；confidence与drift阈值仍属于TASK-P6-05/08。未形成approved policy等同于必须fallback，不得用代码常量或环境变量补猜。

## 9. Boundary invariants

- AI只生成duration/risk/confidence候选，不改变routing、resource compatibility、hard constraints、schedule state或业务权重。
- P2 formal Validator始终独立执行；confidence不能替代Validation PASS。
- P4 ExecutionFact、effective HARD/freeze locks、OBJ-002、ChangeReport和Simulator共同路径逐字冻结。
- COMPLETED actual与RUNNING authoritative remaining/freeze语义优先于预测。
- Model governance不新增业务state machine，不改变PlanningRun、ScheduleVersion或ExportJob pair。
- Synthetic、provider success、local Gate或P6 Exit不能证明Production authority、现实精度、UAT、deployment、capacity或SLA。

## 10. OPEN closure conditions

本合同不关闭任何OPEN。后继要解除对应default-deny，必须形成：

| OPEN | P6 minimum closure record |
|---|---|
| OPEN-010 | 具名principal/role/capability与Data、Model Quality/Risk、Release、rollback职责；approval/reject/expiry/audit规则及授权证据 |
| OPEN-011 | 获授权的历史source、factory/time/scope、representativeness限制、extract/replay依据、retention/deletion和P7现实校准计划 |
| OPEN-014 | resource-option标准工时authority、confidence/evaluation/drift thresholds的versioned policy、完整fallback reason、disable/rollback owner和负例证据 |
| OPEN-015 | feature/label/actual/standard-duration逐字段source mapping、冲突优先级、revision/cutoff语义、consent/retention依据与authority签署 |

Closure必须含Authority、Evidence、scope、effective version和rollback；仅有代码、Schema、synthetic data、test、provider artifact或本ADR均不足。四项继续`OPEN`。

## 11. Verification obligations

`TEST-P6-DATA-GOVERNANCE-001`静态证明本文与ADR-0016覆盖：标准工时authority、completed-label eligibility、censoring/exclusion、as-of leakage、time/group split、privacy/retention/deletion、immutable dataset/model/evaluation lineage、human promotion/rollback、fallback decision table、OPEN closure conditions及P6/P7/Production负边界。`TEST-P6-PREDICTION-CONTRACT-001`另行机器验证四份v1 carrier的strict schema、round-trip、canonical identity、quantile/confidence、fallback、leakage、tamper、mixed-version与cross-lineage拒绝。

TASK-P6-01历史上只允许文档/治理检查，TASK-P6-02只形成Schema/sample与contract checker。P6-03/04现经各自独立授权增加synthetic dataset、baseline model/training、safe artifacts、test和CI证据；仍没有migration、dependency lock变化、formal Benchmark/evaluation、runtime、planning integration或state变化。P6-05+证据必须继续逐Task独立授权并取得双exact provider后才能升级状态。

## 12. Compatibility and rollback

本合同已由additive schema set `2.9.0`的新v1 carrier表达；70份既有Schema/sample bytes和所有历史document set字段逐字不变，不能重新解释P0～P4字段。P6-03/04已消费FeatureRecord/ModelManifest边界，因此v1 bytes与已引用dataset/model identities不可改写，只能由后继版本supersede。

当前没有prediction runtime可启用；P6-04回滚只能retire受影响synthetic model artifact或保持provider disabled，并继续使用权威标准工时，同时保留全部不可变dataset/model/replay/decision evidence。语义修改只能由superseding ADR、合同或artifact版本完成。
