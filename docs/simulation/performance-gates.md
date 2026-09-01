---
doc_id: DOC-SIM-007
title: 性能与现实校准门
status: baseline
spec_version: 0.3.0
phase: P2-P7
normative: true
source_sections: [57, 58, 76, 80, 84, 85, 89, 105, 106]
last_reviewed: 2026-09-01
---

# 性能与现实校准门

## TASK-P6-08 development monitoring overhead

Monitor性能证据只测256次同一8-observation aggregate window的pure in-process validation/report构造并记录observed elapsed time；输入上限由固定8项window与strict field/count bounds限定，不接收raw rows或unbounded stream。Machine Gate只要求调用完成、报告可canonicalize且不会触发network/storage/automatic action，本机时间不进入semantic identity。

该观察用于发现明显development regression，不形成Production latency、throughput、ingestion capacity、availability、retention或SLO，也不允许为了通过而降低drift/privacy threshold。真实telemetry volume、clock skew、concurrency、backpressure和alert delivery仍未测试。

## TASK-P6-06 local runtime resource boundary

P6-06以固定Simulation/Test pure-model调用验证50 ms timeout post-check、32 KiB输出、256-call P95≤20 ms与peak allocation≤16 MiB；machine report保存actual observations且任何超界均FAIL/fallback。输入大小与feature/source count在调用model前拒绝，避免unbounded payload；provider没有remote timeout、worker pool或concurrency claim。

这些数值只用于development regression与fail-closed，不是Production latency、throughput、capacity、availability或SLA，也不关闭OPEN-006/011/012/014/015。P6-08后来只形成上节aggregate development observation；P7 Reality Calibration和真实load profile仍是独立门。

## TASK-P6-05 offline quality Gate boundary

P6-05新增的是duration quality/confidence/fallback Gate，不是Solver performance Gate。Frozen synthetic profile要求model总MAE严格优于standard baseline、partition/family MAE不劣化、P90 coverage总体≥`3/4`/slice≥`1/2`、confidence≥`9/10`；当前aggregate全部满足并输出`READY_FOR_SIMULATION_RUNTIME`。

该READY不表示P7 Reality Calibration、真实历史有效性、runtime latency/memory、Production capacity或SLA，也不改变Gate A/B/C。OPEN-010/011/012/014/015关闭前不得把4条held-out观测外推；threshold变化必须新profile/SIM assumption和独立Gate，禁止原地调低baseline。

## TASK-P5-01 qualification observation boundary

P5-01在不改变profile、baseline或threshold的前提下fresh重放P2 XS/S/M；三项均PASS且无warning，qualification report保存runtime、memory peak、model metrics、solver/reference quality、validation、environment和baseline identity。该重放只能说明冻结开发样本未给出候选必要性证据，不能证明L/XL、历史业务分布、Production capacity或SLA，也不能关闭OPEN-003/004/006/011/012。

七个约束候选因没有可执行candidate case而不伪造比较数值；Decomposition/Rolling仅引用原始Global replay。没有新增数值SIM假设或performance budget。

## TASK-P4-14 Gate B aggregate evidence boundary

P4-14本地Gate B aggregate现以两轮完整P4 owner replay证明fact/lock preservation、fresh Validator PASS、complete ChangeReport和tardiness/Stability业务语义一致；所有per-stage runtime/memory原值均保存在raw reports。该结果复用且冻结P2 XS/S/M baseline，不新增profile、threshold、fixture expected、L/XL或Nightly，并不把本机/CI runner观测外推为Production capacity/SLA。

这仍是P4 Vertical Slice Gate而非P4-15 Exit Audit。只有implementation/closure provider闭环后TASK-P4-14才能完成；即使完成也不能关闭OPEN-003/004/005/006/011/012或形成Production readiness。

## TASK-P4-10 correctness observation boundary

五步continuous replay记录before/after synthetic tardiness、完整四分量Stability及机器运行证据，只用于determinism/correctness回归。它不增加或修改Benchmark threshold，不替代P2 XS/S/M baseline，也不形成P4 Gate B aggregate或Exit Audit。真实历史分布、L/XL、capacity和SLA继续由OPEN-003/004/006/011/012阻塞。

## P4 planned gate boundary

P4-14必须在功能完整性、determinism、fact/lock preservation、Validator PASS和ChangeReport completeness均通过后才比较replan timing/tardiness/stability；P4-15独立重放。OPEN-003/004/005/006及真实数据校准未关闭前，任何结果都不能声明Production capacity或SLA。本次不修改阈值、fixture或benchmark evidence。

## TASK-P3-17 audit boundary

独立Audit复验P2 XS/S/M及P3 development observations，但不建立L/XL、真实历史回放、Production capacity或SLA。OPEN-011/012继续OPEN，所有时延/内存/bundle只作为原始开发证据保留。

## Gate A — P2 Synthetic Solver

完整验证 Snapshot → Problem → Solver → Validator → Export，至少运行 Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock 和 XS/S/M，并记录 build、first feasible、runtime、gap、memory、model size 和 validator result。

## Gate B — P4 Dynamic Replanning

通过 ExecutionSimulator 连续注入异常，确认 Execution Facts/HARD_LOCK 不变、新 Version Validator PASS、ChangeReport 完整。

## Gate C — P7 Reality Calibration

```text
Historical Snapshot
→ Replay
→ Synthetic Comparison
→ FactoryProfile Calibration
→ Production Capacity Boundary
```

Reality Gap Report 比较 routing depth、candidate density、calendar fragmentation、bottleneck 和 solver runtime 等真实/合成分布。

## 禁止承诺

在 OPEN-011/012 未关闭前，禁止“5 分钟一定排完”“秒级排程”“99% 最优”“任意规模”等表述。P7 不能成为第一次性能测试。

TASK-P0-05 只形成可供未来 Gate 引用的 versioned Scenario manifest 和 dataset hash；empty Import replay 不包含 operations/resources，不是 XS profile 或性能运行。Gate A/B/C、TEST-BENCHMARK、runtime/memory/quality baseline 和 OPEN-012 production threshold 均未改变。

TASK-P0-06 的 `SIM-MINIMAL-001@1.0.0` 使用 XS 标签只表示三道工序可手算 correctness；验收记录测试通过与 hash，不采集 Solver runtime、gap、memory/model size，也不进入 `benchmarks/**`。因此 Gate A/B/C、TEST-BENCHMARK、OPEN-012 和任何 performance baseline 均未改变。

TASK-P1-10的`SIM-P1-INGRESS-001@1.0.0`同样只验证49条canonical record的生成/Normalization/Data Validation replay；没有调用Problem/Solver、采集runtime/gap/memory/model size或修改`benchmarks/**`。因此它不是Gate A的XS run，也不改变Gate A/B/C、TEST-BENCHMARK、OPEN-011/012或任何容量/SLA结论。

## TASK-P2-08 tiny objective evidence boundary

`objective-strategy-report.v1`开始记录真实build/first-feasible/solve/validation/total、objective/bound/gap、model size与memory，并以4个至多3-operation的in-memory vectors证明OBJ-001数值/状态/Validator correctness。它没有使用`benchmarks/profiles.yaml`、正式Scenario Library、Reference Scheduler、warm-up/repetition/percentile或XS/S/M，因此不是Gate A/B/C performance run。

CI新增该correctness report只为防止objective/strategy/status回归；任何runtime或memory单值不得转成threshold、capacity或SLA。P2-12仍独占XS/S/M Benchmark，OPEN-011/012继续OPEN。

## TASK-P2-09 performance boundary

七个新Scenario均标记`XS`只是表达可手算correctness，报告虽透传model size/timing/memory，但不执行warm-up、repeat、percentile、Reference comparison或`benchmarks/profiles.yaml`。CI中的`ci-p2-correctness.json`只是一致性Gate，不能形成Gate A/B/C baseline、threshold、capacity或SLA；P2-12与OPEN-011/012保持不变。

## TASK-P2-12 Gate A scale slice

XS/S/M三个versioned profile现已各自在正式source→Problem链上运行Global和五Reference，并记录build/first feasible/solve/validation/total、objective/bound/gap、memory、model/Problem complexity与Validator结果。每个scheduler执行1次warm-up和3次measured repetition；本地三份`benchmark-report.v1`均8/8 PASS且无warning，CI PR slice真实执行XS。

这只关闭Gate A的XS/S/M scale-measurement子项，不替代P2-09 Golden/Cross/Calendar/Material/Running/Hard Lock evidence整合，也不形成完整Gate report。TASK-P2-13仍须把所有子项、exact provider artifact与phase trace组合后判定；TASK-P2-14才可审计。Development ceiling和same-environment factor不是Production SLA，OPEN-011/012继续OPEN。

## TASK-P2-13 Gate A aggregate evidence

`p2-vertical-slice-report.v1`现把Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock与XS/S/M组合为两次完整replay；每个XS/S/M再次运行Global+五Reference的1 warm-up/3 measured、fresh Validator、共享KPI和internal Export，并保留build/first/solve/validation/total、objective/bound/gap、memory、model/Problem scale、environment及package hashes。两次versioned business projection一致且11/11 aggregate checks PASS。

这构成TASK-P2-13本地Gate A aggregate evidence，不是TASK-P2-14 Exit audit或Production performance Gate。Run-specific SolverReport/KPI/package hash包含时间证据并逐次保留，不错误要求相等；Problem/candidate/业务投影必须一致。OPEN-011/012、L/XL、Nightly schedule、Production capacity/SLA仍未形成。

Required run `32465737712` / artifact `9440650646`已在provider精确复现两次Gate A aggregate且无warning/gap，故TASK-P2-13=`done`。该结果仍不关闭OPEN-011/012，不形成L/XL、Nightly或Production SLA，也不替代P2-14 Audit。

## TASK-P2-14 Exit audit

独立audit已再次执行两次完整Gate及单独XS/S/M，并补充七correctness场景×两轮的逐次model/build/first/objective/bound/gap/memory/Validator观测。所有required case、三档8/8 reports、稳定业务投影与4类exit rejection均PASS，blocking gaps为空，因此P2 Synthetic Solver Gate=`READY`。Audit implementation run `32677741558` / artifact `9503227240`已精确复验Gate 11/11与provider内两轮稳定投影，TASK-P2-14=`done`。Raw timing/memory仍保留且不作跨环境相等声明；OPEN-011/012、L/XL、Nightly provider schedule与Production capacity/SLA继续未形成。
