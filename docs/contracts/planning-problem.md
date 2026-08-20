---
doc_id: DOC-CONTRACT-003
title: PlanningProblem 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 14, 24, 25, 26, 45, 89]
last_reviewed: 2026-08-20
---

# PlanningProblem 合同

PlanningProblem 必须可序列化、Solver-neutral、deterministic，不包含 OR-Tools 类型。

## 顶层结构

```json
{
  "problem_version": "planning-problem.v1",
  "snapshot_id": "canonical-id",
  "problem_builder_version": "...",
  "problem_hash": "...",
  "tick_seconds": 60,
  "horizon_start_utc": "...",
  "horizon_end_utc": "...",
  "resource_ids": [],
  "operation_instances": [],
  "precedence_edges": [],
  "resource_unavailable_intervals": [],
  "required_capabilities": []
}
```

[`planning-problem.schema.json`](../../schemas/json/planning-problem.schema.json)继续固定v1 candidate options、NOT_STARTED/RUNNING execution facts、min/max/transport lag、resource unavailable intervals和capability declarations。TASK-P2-01另行发布[`planning-problem.v2.schema.json`](../../schemas/json/planning-problem.v2.schema.json)，不在v1对象中追加字段或重解释既有hash。

## 不变量

- operation/resource/edge 引用完整；
- routing/operation precedence 无环；
- NOT_STARTED Operation 有至少一个合法候选资源；
- duration 秒到 tick 的转换显式且可复算；
- max_lag 一旦存在就必须被 Solver 和 Validator 使用；
- horizon 不静默截断任务；
- unsupported capability 在 solve 前明确拒绝；
- 同 Snapshot 与 rule/problem builder version 得到同 `problem_hash`。

## 边界

PlanningProblem 不含数据库 Session、ORM Model、API DTO、CpModel、IntervalVar 或求解过程统计。修改本合同必须 ADR、problem version 更新、contract/golden/scenario replay 和 benchmark comparison。

P0 纯类型位于 `backend/app/planning/problem/contracts.py`；`backend/app/domain/validation.py` 只做 ID 引用、UTC interval、duration 和 lag range 的最小 precheck，不实现 C-001～C-011 或 Solver。TASK-P1-09 已形成 builder/hash、active DAG 和 Golden replay；Constraint rule sheet语义未改，正式 ScheduleValidator、Solver 与 Benchmark仍未形成。

## TASK-P1-09 builder and hash contract

`planning-problem-builder.v1`只接受已通过`verify_snapshot`的immutable PlanningSnapshot v2，并显式接收builder version、正整数`tick_seconds`及second-precision UTC horizon。`horizon_start_utc`必须精确等于Snapshot cutoff；RUNNING remainder和每个NOT_STARTED实例至少一个candidate必须以`ceil(seconds/tick_seconds)`完整落入horizon，Problem仍逐字保留权威秒，不写入派生tick或静默截断。

Builder按operation ID、candidate值、edge端点、resource/time与capability name稳定排序。COMPLETED不进入未来Problem；两端均COMPLETED的edge一并排除，COMPLETED与active之间的edge因v1无法保留历史完成时刻和lag边界而明确`UNSUPPORTED_PROBLEM_FACT`。RUNNING从其`execution_fact_id`解析actual start、assigned resource和positive remaining seconds。Calendar只投影与horizon相交的显式interval并保留原UTC端点；完全历史/未来的interval不进入当前Problem。与horizon相交的HARD/SOFT lock无法由v1表达，必须拒绝；已结束或horizon外lock不改变当前future domain。

顶层`required_capabilities`是从本Problem实际使用的platform能力确定性推导的声明，例如`DAG_ROUTING`、`RELEASE_AND_MATERIAL_GATE`、`RUNNING_OPERATION`、`MACHINE_CALENDAR`和`ALTERNATIVE_RESOURCE`；Operation的CUTTING等业务能力已由Data Validation确定candidate eligibility，不混入platform capability registry。多Factory保持显式unsupported。

`planning-problem-hash-projection.v1`使用`canonical-json.v1 + SHA-256`覆盖除self `problem_hash`外的完整canonical Problem，并加入projection version；不属于Problem合同的generated/run/runtime字段不参与。Snapshot的content-derived `snapshot_id`已绑定Snapshot hash、rule、facts及全部上游版本，因此Problem hash同时绑定Snapshot identity、builder version和tick/horizon config。`ImmutablePlanningProblem`仅保存canonical bytes/hash/metadata，document访问返回copy，`verify_problem`复核exact shape、pure precheck、platform capability、active DAG、bytes与hash。

本Task未修改`planning-problem.v1` Schema、C-ID、ADR-0003或Solver接口。Due/priority、完整Resource facts、active lock字段与completed-to-active historical lag若要成为可求解输入，必须先发布新Problem version并按ADR/replay/benchmark规则升级，不能在v1中藏字段。

## TASK-P1-11 terminal application artifact

Common ingress的最后一步仅调用`planning-problem-builder.v1`，并以Snapshot cutoff、60秒tick和24小时fixture-local horizon产生Problem hash `sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da`。两次Synthetic replay与ReferenceFileAdapter输入的Problem canonical bytes/hash完全一致。

`p1-data-pipeline-report.v1`明确记录terminal artifact为PlanningProblem，`solver_executed/candidate_schedule_created/schedule_validator_executed/p2_entered=false`。本Task不修改Problem Schema/builder/hash语义，也不将Problem replay写成feasibility、Solver或Validator证据。

## TASK-P1-12 Exit Gate audit

P1-12以同一Snapshot/cutoff/60秒tick/24小时fixture-local horizon重放两次Synthetic和一次Reference入口，完整Problem bytes digest均为`sha256:c3ff3f0cc810007da4dc251642896b0d8b6fab1f98d4d5bced743752904e9233`，problem hash均为`sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da`。Builder/hash/ordering/fact/config property与unsupported边界在271项回归中PASS。

依赖/code扫描再次确认没有OR-Tools、CpModel或IntervalVar，且没有P2 Task。P1 Gate=`READY`只证明solver-neutral Problem可确定性形成，不证明可解性、candidate Schedule、ScheduleValidator、目标值、性能或Production readiness。

## TASK-P2-01 PlanningProblem v2 contract

`planning-problem.v2`固定`schema_set_version=2.3.0`、`planning-problem-builder.v2`、`canonical-json.v1`和`planning-problem-hash-projection.v2`。它以opt-in `build_planning_problem_v2`消费verified Snapshot v2与一份精确覆盖active DemandOrder的priority fact mapping；既有`build_planning_problem`仍只产v1。两个document互不兼容，consumer必须按`problem_version`显式选择，禁止alias或latest升级。

v2新增四类P2输入事实：

- `delivery_demands`逐字复制DemandOrder `due_at_utc`及其source system/version/record ID；`priority_weight`必须是非boolean正整数，并携带独立source三元组。缺失、额外、零/负数、boolean或无版本来源均在Solver前以`INVALID_PRIORITY_FACT/DATA_ERROR`拒绝，不提供Production default；
- `resources`完整投影resource code/type/status、Factory→Workshop→Line→Group拓扑、calendar、business capabilities与`capacity=1`。该capacity只表达C-003 primary unary resource，不启用C-012 secondary capacity；
- referenced OperationLock只要`end_at_utc > horizon_start_utc`就以原始完整interval/source保留，已过期lock排除，跨越或完全位于horizon end之后的lock不裁剪；HARD/SOFT保持不同类型，合同形成不等于C-008 Solver或OBJ-002实现；
- COMPLETED operation仍不进入future instances；COMPLETED→active edge保留edge ID/lag并增加包含fact/resource/actual start/end/source的historical completion anchor，completed→completed edge排除，active→completed以`INVALID_HISTORICAL_FACT`拒绝。

Operation v2增加`demand_order_id`和business `required_capabilities`，calendar interval增加`calendar_id`。hash projection覆盖版本、Snapshot、due/priority、resources、operations/options、anchors、edges、locks、calendar与required platform capabilities，只排除self hash和非合同runtime噪声。固定v2向量为Problem hash `sha256:9927418a446dd046ddd1d835643da03fbf5cdcf8ca246ba22c3700563a17e9e8`、canonical bytes SHA-256 `2dbe06907952d6aba303977d67a7f5d7a6ef89c4be5ac5a6ac8d74e3f95d720a`、3366 bytes；v1固定向量和Schema/sample SHA-256保持不变。

本Task不安装OR-Tools，不建立Policy/Solution/status、Backend/Strategy、C-ID公式、formal ScheduleValidator、OBJ-001计算、Benchmark或DB migration。Production due/priority/lock authority继续受OPEN-004/005/006/007/009/010/015约束；synthetic priority只允许使用显式versioned Simulation policy。
