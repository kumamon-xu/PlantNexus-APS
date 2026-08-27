---
doc_id: DOC-CONTRACT-003
title: PlanningProblem 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 14, 24, 25, 26, 45, 89]
last_reviewed: 2026-08-21
---

# PlanningProblem 合同

## TASK-P4-01 future Replan input boundary

ADR-0013/0014要求P4 Replan仍只从verified new PlanningSnapshot构建solver-neutral Problem；ExecutionEvent不得作为Backend隐藏参数。Problem必须显式绑定base PUBLISHED reference、new Snapshot/fact checkpoint、freeze policy/resolved effective locks及OBJ-002 base assignments所需版本化引用。TASK-P4-02决定是否发布新Problem document或独立referenced carrier；不得原地扩写`planning-problem.v2`或改变其hash。

P4-05/06/07消费这些新版本前，v1/v2 builder、Schema/sample/hash、C-001～C-011、OBJ-001和P2 XS/S/M baseline全部保持只读。本Task没有Problem builder、Schema、Solver或Validator变化；Production freeze/fact authority仍未形成。

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

## TASK-P2-02 downstream reference boundary

PlanningSolution/SolverReport v1只以`problem_version`、builder/hash-projection version、Problem hash、Snapshot ID、tick与horizon形成对Problem v2的精确引用，不复制或重算Problem事实。P2-02没有修改上述v1/v2 Schema/sample/builder/hash；Problem v2固定Schema/sample和builder replay继续由P2-01 machine report单独证明。Policy/Limits/Solution/Report合同存在不表示Problem已经被Backend消费，也不产生candidate、C-ID或Validator证据。

## TASK-P2-05 core consumer boundary

CP-SAT Backend现以Problem v2的operation/resource/options、`final_duration_seconds`、tick与horizon实现C-001/003/004/010/011。每个operation必须有至少一个显式candidate，所有candidate duration必须完整落入horizon；不允许通过删除overflow option改变输入可行域。

Problem v2 Schema、sample、builder、hash projection和canonicalization均未修改。P2-05只接受precedence/calendar/locks为空、NOT_STARTED且release/material gate不晚于horizon start的bounded slice；非空未来事实稳定拒绝并留给P2-06/07，不能据此声称Problem合同不支持这些事实。

## TASK-P2-06 temporal consumer boundary

CP-SAT Backend现消费Problem v2既有`precedence_edges`、historical completion anchors、resource unavailable intervals及operation release/material-ready gates。全部权威instant必须保持canonical whole-second UTC；min/transport下界向上取tick、max上界向下取tick，calendar原始half-open interval投影为与tick-grid精确等价的固定占用。

Problem v2 Schema/sample、builder、canonicalization与hash projection仍字节不变；Solver不得裁剪或改写Problem事实。RUNNING与operation locks仍在build前拒绝并留给P2-07，合同支持这些字段不等于当前Solver已经实现它们。

## TASK-P2-07 execution fact and lock consumer boundary

CP-SAT Backend现消费Problem v2既有RUNNING `actual_start_at_utc`、`assigned_resource_id`、`remaining_seconds`、historical completion anchors与operation locks。RUNNING从horizon start占用`ceil(remaining_seconds/tick_seconds)`且只允许assigned resource；COMPLETED仍只以historical anchor参与active successor lag，不进入future assignments。

HARD lock start/end必须位于exact tick grid且interval ticks与该resource权威duration（RUNNING时为remainder）一致；同operation多个冲突HARD lock或RUNNING/HARD tuple冲突在model build前MODEL_INVALID。Grid-aligned但与calendar/resource/horizon冲突的完整事实进入模型并由native solver认证INFEASIBLE。SOFT lock不形成硬约束或hint，只作为稳定排序metadata reference保留。

Problem v2 Schema/sample、builder、canonicalization与hash projection仍字节不变。RUNNING Problem记录不含execution fact ID，Backend不得从operation/source猜造；事实历史由Problem hash和actual/resource/remainder字段绑定。OBJ-001、OBJ-002、dynamic Replan与Production authority均不由本Task形成。

## TASK-P2-14 Exit audit

审计以full contract/property/golden/integration回归和两次Gate确认PlanningProblem v2仍是所有七correctness场景与XS/S/M的唯一solver-neutral输入；固定Problem hashes、历史v1/v2 fingerprints、C-001～C-011事实投影与row-order replay均PASS。Problem Schema/builder/hash、migration与ADR-0010无差异；READY不扩展capacity>1、C-012～018、OBJ-002/003、dynamic Replan或Production authority。
