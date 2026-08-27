---
doc_id: DOC-QUAL-004
title: Property Test 规范
status: baseline
spec_version: 0.3.0
phase: P1-P4
normative: true
source_sections: [45, 86, 87]
last_reviewed: 2026-08-21
---

# Property Test 规范

## TASK-P4-01 property contract

ADR-0013～0015现把后继property边界固定为：同identity同fingerprint exact replay、同identity不同fingerprint拒绝、source position gap/倒退fail closed、确定性事实投影与Snapshot identity、freeze/HARD preservation、OBJ-002四元向量与ChangeReport算术、新Version immutable，以及同scenario/seed/virtual clock得到同一event stream与逐步结果。Urgent新增Operation不计movement，因事实消失的Operation必须显式分类，不能偷改比较分母。

这些断言仍由TASK-P4-02～10实现；TASK-P4-01不修改测试代码、generator、fixture、expected或既有property结果，也不得生成P5能力并静默近似。

## TASK-P3-17 audit conclusion

registered property suites随621项全仓测试重新执行，覆盖determinism、copy-on-write、idempotency、CAS/并发、plane与Validator边界；全部PASS且断言未变。Audit没有新增assumption或以property样本替代Production证据。

Property Test 随机生成合法 V1 PlanningProblem 或合法 canonical input，检验跨大量组合保持的不变量。

## 核心性质

- 任何被接受的 Schedule 必须 `validator_passed=true`；
- 每个未完成 Operation 恰排一次；
- 同 resource interval 不重叠且尊重 calendar；
- precedence、material/release、lock、duration 和 horizon 均成立；
- 同 canonical input 和版本产生相同 hash；
- unsupported capability 被明确拒绝；
- 序列化 round-trip 不改变语义。

## 非性质

不要求相同 schedule ordering、相同 Solver search path 或相同 runtime，因为多个同质量解可能正确。

随机失败必须保存最小化 example、seed、Schema/Generator/Problem version 和 Problem hash，确保可回归。

TASK-P0-03 已对两个明确 synthetic sample 执行 JSON serialization round-trip，并验证 UTC/duration/reference 的确定性 helper；这只是 `TEST-CONTRACT-001` 的固定样例证据，不是随机 Property Test、Snapshot/Problem hash replay 或 TEST-PROPERTY 完成。完整性质测试仍为 P1/P2 `PLANNED`。

TASK-P0-06 对固定 `SIM-MINIMAL-001@1.0.0` 复算 canonical non-empty Import round-trip/hash、C-ID 与 KPI；这属于 Golden/Scenario replay，不包含随机生成、shrinking 或多组合不变量，因此不能标记 TEST-PROPERTY 已形成。未来 Property Test 可使用该 fixture 的稳定 ID/hash 作为最小回归种子，但不得改写历史版本。

TASK-P0-07 的 13 个声明式 mutation 验证 deterministic replay、base immutability、C-001～C-011 完整负例 coverage 与固定关键算术；它们仍是枚举的 Mutation Test，不是随机 Property Test。`SIM-MINIMAL-001-MUTATIONS@1.0.0` 可作为未来 generator/shrinker 的固定 regression corpus，但 TEST-PROPERTY 和合法 PlanningProblem 跨组合生成仍为 P2 `PLANNED`。

TASK-P1-02对两份固定synthetic v2 sample执行serialization round-trip，并对canonical reference/unit/time/duration/provenance与Snapshot count/copy不变量做明确mutation负例。这只形成TEST-CONTRACT-001的deterministic contract evidence；在该Task完成时没有Hypothesis/random generator、shrinking、seed corpus或Snapshot/Problem hash性质，因此当时TASK-P1-07/08的P1 property tests与P2 TEST-PROPERTY均为`PLANNED`。

TASK-P1-05以固定构造覆盖三项deterministic properties：row/input order与volatile batch metadata不改变canonical bytes/hash；mapping profile version改变必然改变bytes/hash；namespaced source identity稳定派生ID且不同namespace/authority不碰撞。另以枚举负例覆盖unit integer arithmetic、DST offsets和schema field-set invariant。这些是TEST-NORMALIZATION-001/TEST-CONTRACT-001的固定property-style evidence，不含随机生成、shrinking或seed corpus；截至该Task完成时P1-07/08与P2 TEST-PROPERTY继续`PLANNED`。

TASK-P1-06以固定canonical sample和显式mutations验证三项deterministic properties：合法输入重复运行得到同report bytes/ID；collection/record/list顺序重排不改变有序Error/report；四类Gate与多错误组合保持exact code/category/source evidence。另覆盖DAG SCC、orphan/duplicate、calendar/lag/fact和capability/resource负例。

这些属于TEST-DATA-QUALITY-001的固定property-style evidence，不使用Hypothesis/random generator/shrinking，也不生成合法PlanningProblem或candidate schedule。截至TASK-P1-06完成时，P1-07/08的Expansion/Snapshot property与P2 TEST-PROPERTY继续`PLANNED`。

## TASK-P1-07 generated expansion properties

本Task首次锁定`hypothesis==6.165.10`并使用generation/shrinking。Positive property以replay seed`20260819`和64 max examples生成显式synthetic canonical inputs：1～3 lots、固定4-operation branch/merge DAG、2 workshops/resources、每operation 1～2 candidates、RUNNING/COMPLETED/NONE fact与locks；验证重复运行和collection重排的bytes/hash相同、实例/edge cardinality、ID唯一、同lot edge、candidate duration/source copy与transport lag不丢失。Negative property以seed`20260820`和24 max examples删除随机operation的全部candidate，要求收缩后仍精确`MISSING_RESOURCE_OPTION`。

所有生成输入显式`synthetic=true`并在provenance记录generated scenario seed；无失败，因此没有保存虚构的minimized failure/corpus。失败时Hypothesis会报告最小example和reproduction seed，修复后应把最小反例版本化为回归fixture或保留reproduction metadata。TASK-P1-07形成P1 TEST-ORDER-EXPANSION-001的property evidence，但没有生成PlanningProblem/candidate schedule，故P2 `TEST-PROPERTY`仍为`PLANNED`；Snapshot replay property当时留给TASK-P1-08并已由下节形成。Implementation commit `5a3dbc14c12a107abf4052cca935e3ef59009d3d`已由GitHub Actions run `32265257468`的required `validate`成功重放，包含property目录的repository suite及中性machine evidence artifact均成功。

## TASK-P1-08 generated Snapshot properties

`test_snapshot_properties.py`复用锁定Hypothesis并固定四组seed：`20260820`以32 max examples重排16个canonical collections及inner capability lists，要求完整Snapshot bytes/hash/ID不变；`20260821`以32 examples改变factory business fact并重新走package/quality/expansion链，要求deterministic replay且hash/ID变化；`20260822`以24 examples改变cutoff秒值，要求facts不变而hash变化；`20260823`以24 examples注入received/generated/runtime/self噪声，要求semantic hash不变。

定向property执行4项全部PASS且没有Hypothesis failure，因此没有伪造minimized corpus；如未来失败，必须保留reproduction seed与最小反例。该证据形成P1 `TEST-SNAPSHOT-REPLAY-001`的generated slice，不生成PlanningProblem或candidate Schedule，故P2 `TEST-PROPERTY`继续`PLANNED`。Test值来自P1-02 synthetic schema sample，不成为Profile distribution、Benchmark baseline或Production事实。

Implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`已由GitHub Actions run `32310098594`的required `validate`成功重放，repository suite实际包含上述property目录；无provider failure或额外minimized corpus。

## TASK-P1-09 generated Problem properties

`test_planning_problem_properties.py`固定seed `20260820/20260821/20260822`与48/32/32 max examples：1～3600秒tick下重复build必须bytes/hash完全一致且260/420秒candidate按整数ceiling可复算；operation/capability/resource/option顺序与self/runtime噪声不得改变canonical bytes/hash；两个不同显式tick config必须产生不同Problem identity。全部性质只使用verified P1 canonical synthetic Snapshot并保留权威秒，不生成candidate schedule。

定向property 3项及其全部examples PASS，无Hypothesis failure/minimized corpus。它形成P1 `TEST-PROBLEM-REPLAY-001`的builder/hash性质证据；P2 `TEST-PROPERTY`仍为`PLANNED`，因为尚未生成/验证合法candidate solution或跨Solver组合。

## TASK-P1-10 generator replay properties

P1-10以版本化asset和固定seed `20260820`执行deterministic property-style checks：相同Profile/Scenario/generator/seed在不同generated-at下产生byte-identical Import/hash；seed或Profile version改变使hash变化，unknown generator version明确拒绝；unrelated child-seed调用不改变topology，orders/calendars及execution/locks以相反调用顺序生成时各自collection相同。Profile ranges与0.5 quota确保七层都有非空回归记录。

本Task没有新增Hypothesis策略或candidate Schedule/Problem随机生成，因此没有shrinking failure/minimized corpus，也不改变P2 `TEST-PROPERTY=PLANNED`。若未来生成失败，必须保存Scenario/Profile/generator version、seed和最小source/canonical反例，而不能改变约束使其通过。

## TASK-P1-11 end-to-end replay properties

P1-11用固定Scenario/Profile/Generator/seed和显式cutoff/horizon/tick验证三项跨层性质：两次公开staging generation得到相同batch与Import/Snapshot/Problem完整bytes/hash；同义Reference CSV的transport bytes/provenance不同但三个业务artifact相同；四类source mutation都在首个所属stage以exact code终止。

这些是fixed deterministic replay/negative properties，没有新Hypothesis strategy、shrinking、candidate Schedule或Solver输出；P2 `TEST-PROPERTY`继续`PLANNED`。

## TASK-P1-12 property audit

审计没有新增Hypothesis strategy或改变seed/example数；full 271项回归重新执行P1-07 Expansion、P1-08 Snapshot和P1-09 Problem generated properties且全部PASS。另以P1 gate CLI `repeat=2`复核同Scenario/Profile/Generator/seed的Import/Snapshot/Problem完整bytes/hash，并以Reference transport验证业务artifact parity；四类source mutation均精确终止。

未出现property failure，因此没有虚构minimized corpus。P1 property evidence足以支持Data & Snapshot Gate=`READY`，但没有candidate Schedule/Solver output，故P2 `TEST-PROPERTY`仍为`PLANNED`。

## TASK-P2-01 generated Problem v2 properties

P2-01扩展`test_planning_problem_properties.py`，保留v1 seeds `20260820/21/22`并新增v2 seeds `20260823/24`。32 examples随机反转operation/edge/anchor/lock/resource/capability与nested option顺序并注入runtime nonce，要求v2 canonical bytes/hash不变；另32 examples选择两个不相等的正整数priority weight，要求Problem identity必然变化。固定unit mutation还覆盖due、Resource status、historical end和lock end的hash sensitivity。

当前property文件5项PASS且无Hypothesis failure/minimized corpus。该证据只形成Problem input/canonicalization的`TEST-PROPERTY` slice，不生成candidate solution、不运行Solver/Validator，也不形成P2-04/09完整schedule property证据；后继Task仍须保留seed、shrinking和最小反例。

## TASK-P2-04 generated formal Validator properties

[`test_schedule_validator_properties.py`](../../backend/tests/property/test_schedule_validator_properties.py) 固定seed `20260820/21/22`。48个examples生成1～600秒权威duration与tick 6～300的合法NOT_STARTED interval，验证整数ceiling、UTC projection、calendar/resource/horizon边界和formal report PASS；另48个examples从12类C-ID mutation中采样，要求至少一个hard violation；32个examples反转Problem六类collection及candidate assignments，要求报告完全相同。

机器检查另用显式表`(1,1)/(59,1)/(60,1)/(61,2)/(119,2)/(120,2)`复核duration ceiling与reordered replay，避免把随机生成本身作为唯一oracle。当前没有Hypothesis failure，因此没有伪造minimized corpus；若后续出现失败，必须保存seed、Problem hash、candidate和最小反例。该证据形成formal Validator的TEST-PROPERTY slice，不包含Solver生成candidate、objective equivalence、XS/S/M runtime/memory或Production distribution；这些仍由P2-09/P2-12承接。

## TASK-P2-05 core model properties

[`test_cp_sat_core_properties.py`](../../backend/tests/property/test_cp_sat_core_properties.py) 使用固定seed `20260820`生成36个1～5 operations、1～3 resources、horizon 1～10 ticks的tiny cases，并与不导入OR-Tools的candidate-choice/unary-load穷举oracle逐例比较可行性。seed `20260821`用24例证明任一candidate duration超过horizon都会在build前拒绝；seed `20260822`用24例证明每条accepted assignment使用所选resource option的duration并完整落入horizon。

这些properties只覆盖C-001/003/004/010/011的有限正确性，不采样precedence/calendar/material/RUNNING/lock、objective质量、XS/S/M或Production distribution。若出现失败，必须保存seed、Problem hash、options/horizon与Hypothesis最小反例；不得扩大为未注册fixture或Benchmark基线。

## TASK-P2-06 temporal model properties

[`test_cp_sat_temporal_properties.py`](../../backend/tests/property/test_cp_sat_temporal_properties.py)使用固定seed：80例验证任意signed seconds的ceil/floor包络；36例把CP-SAT exact min/max lag窗口与不导入OR-Tools的tick oracle逐一比较；60例比较原始秒级half-open calendar相交与grid projection固定interval判定。

属性范围只覆盖C-002/005/006/009的整数边界，不采样RUNNING/lock、objective质量、XS/S/M或Production distribution。失败时必须保留seed、tick/offset、Problem hash和Hypothesis最小反例；当前in-memory cases不得注册为Golden或Benchmark baseline。

## TASK-P2-07 fact/lock properties

[`test_cp_sat_fact_lock_properties.py`](../../backend/tests/property/test_cp_sat_fact_lock_properties.py)使用固定seed：36例生成任意tick/remainder/assigned resource并验证RUNNING exact tuple；36例生成grid-aligned start/duration/resource与non-integral authoritative seconds并验证HARD exact tuple；24例生成shifted RUNNING/HARD冲突并要求稳定MODEL_INVALID。Hypothesis generation/shrinking与Problem hash均可重放。

属性范围只覆盖C-007/C-008的bounded整数事实，不采样OBJ-001/002质量、事件流、freeze policy、XS/S/M或Production distribution。失败时必须保留seed、tick/remainder/lock tuple、Problem hash和最小反例；in-memory cases不得注册为Golden或Benchmark baseline。

## TASK-P2-08 delivery objective properties

[`test_delivery_objective_properties.py`](../../backend/tests/property/test_delivery_objective_properties.py)使用deterministic Hypothesis生成2～5个单资源单工序Demand、1～3 tick duration、显式due tick与1～5正整数priority；每例枚举全部permutation并要求Global Strategy的OPTIMAL value/bound与独立oracle完全相等、gap=0且formal Validator PASS。另生成单Demand duration/slack/weight缩放，并固定非grid due的exact秒级例。

这些值只属于test-local shrinkable correctness vectors，不新增Scenario/Profile/fixture或Production weight distribution。属性不覆盖OBJ-002/003、Reference、XS/S/M或动态Replan；失败必须保留Hypothesis反例、Problem hash、Policy/Limits版本及SolverReport。

## TASK-P2-09 versioned Scenario properties

[`test_p2_solver_properties.py`](../../backend/tests/property/test_p2_solver_properties.py)对七个固定Scenario以Hypothesis布尔row-order选择重放source rows，要求Import dataset、Snapshot、Problem、assignment与ValidationReport完全一致；另一属性从Scenario ID集合生成Solver candidate，并再次调用formal independent Validator，要求PASS且零hard violation。`derandomize=True`、固定asset seed与Hypothesis shrinking确保反例可复现。

该属性集只覆盖七个tiny correctness assets。XS/S/M随机规模、性能分布、Reference比较和Production默认仍由P2-12+承担。

## TASK-P2-10 Reference Scheduler properties

[`test_reference_scheduler_properties.py`](../../backend/tests/property/test_reference_scheduler_properties.py)使用seed `20260821`生成60组可收缩的duration、release/material gate、non-grid due、priority和algorithm组合，逐例验证ceil tick placement、exact weighted tardiness/makespan、完整candidate、deterministic replay与fresh formal Validator PASS。另从七个冻结Scenario ID×五algorithm中生成35组sampled replay，要求active operation集合精确完整且零hard violation。

Unit边界同时固定五种primary/resource tie-break、calendar/transport/RUNNING/HARD facts、invalid hash与blocked-horizon failure。Generated值只属于test-local correctness，不新增Profile/Scenario/fixture或Production distribution；它不采样XS/S/M规模、runtime分布或Global comparison。失败必须保留Hypothesis反例、Problem hash、algorithm/policy version及candidate/Validator report。

## TASK-P3-05 pagination/filter properties

[`test_workspace_read_model_properties.py`](../../backend/tests/property/test_workspace_read_model_properties.py)在冻结P2→ScheduleVersion input上生成page size 1～4与ASC/DESC组合，逐页重建strict request并要求collection fingerprint稳定、same-page exact replay、item不重不漏且最终observed count一致；另生成resource选择，要求Operations filter绝不泄露其他resource。失败保留Hypothesis反例、Version/source/query/collection fingerprint与cursor，不修改fixture或设置Production分布/阈值。

## TASK-P3-06 command properties

[`test_schedule_command_properties.py`](../../backend/tests/property/test_schedule_command_properties.py)以24个可收缩safe key/lock suffix生成SOFT-lock commands，要求同source/command/context两次得到逐值相同Prepared candidate、fresh ValidationReport、DRAFT/Audit documents和identity，同时source canonical bytes不变、新ID/content fingerprint不同。Generated key只用于test-local Simulation，不建立Production idempotency分布、capacity或SLA。
