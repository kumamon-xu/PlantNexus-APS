---
doc_id: DOC-ARCH-009
title: Provenance 与版本规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [4, 23, 24, 40, 67, 93, 101, 102, 103, 104]
last_reviewed: 2026-08-19
---

# Provenance 与版本规则

## 计划结果最小来源链

```text
Snapshot ID / Hash
Source Versions
Rule Version
PlanningProblem Version / Hash
Solver Name / Exact Version / Parameters
Simulation Scenario / Profile / Generator / Seed（若适用）
Code Commit
Schema Versions
```

这些字段应进入数据库审计记录、成果包 `manifest.json` 和相应报告，而不是只存在于日志文本。

## 版本对象

| 对象 | 修改触发 |
|---|---|
| Implementation Spec | 规范语义变化，更新 `spec_version` |
| Data Schema | `schema_version++`、migration、compatibility rule、contract test |
| PlanningProblem | Contract/serializer 变化，更新 problem version 并回放 Benchmark |
| Solver | 精确依赖版本与参数进入 report；升级执行完整 replay |
| FactoryProfile | 任意语义/生成范围变化更新 profile version |
| ScenarioSpec | 能力、复杂度、期望行为或事件变化更新 scenario version |
| Generator | 生成逻辑变化更新 generator version |
| EventSimulator | 事件语义变化更新 simulator version |

## Hash 语义

Hash 输入必须 canonicalized，不能依赖无业务意义的对象顺序、运行时地址或 `generated_at`。同输入和同规则版本应得到相同 Snapshot/Problem hash；同 Scenario/Profile/Generator/seed 应得到相同 dataset hash。

不可追溯构建不得发布。

## P0-03 executable baseline

Schema set `1.0.0` 已同步写入 `pyproject.toml`、`app.SCHEMA_VERSION` 和 `schemas/data_dictionary.yaml`。每个 JSON Schema 使用稳定 URN `$id` 和显式 `*.v1` version field；Snapshot/Problem skeleton 要求 source/rule/builder/hash 引用字段，但 P0 不生成真实 hash。

Synthetic samples 明确携带 `scenario_id` 和非生产 hash 标记；Production Snapshot/Import envelope 禁止携带 scenario reference。Code commit、真实 source versions、canonical hash 和 end-to-end manifest 仍需在对应 builder/run/export Task 中形成，不能从 Schema 文件存在推断已完成。

## P0-04 rule contract release

Schema set `1.1.0` 在 `1.0.0` 上 additive 增加 error/validation v2、state-transition.v1 和四份 v1 YAML registries；既有 v1 文件与 URN 保留。Rule sheet、capability/error/state registry 各自携带独立 version，未来修改公式、状态 pair、code mapping 或 capability status 必须升对应版本并检查 Schema/Task/Test/Benchmark 影响。

`rule-contract-report.v1` 记录 contract counts 与 schema set，但不是 run provenance、ScheduleValidator report 或发布 manifest。P2/P3 真实运行必须引用 rule/state/error contract version 及 code commit；本 Task 不生成 Snapshot/Problem hash 或业务 audit。

## P0-05 Simulation contract release

Schema set `1.2.0` additive 增加 FactoryProfile/ScenarioSpec/ScenarioManifest v1，并保留 `1.0.0/1.1.0` artifacts。Profile/Scenario contract version、asset version、Generator version、canonicalization version、schema set 和 code commit 是独立维度；任一生成语义变化不得只借其他版本掩盖。

P0 empty package 的确定性输入为 Scenario ID/version、Profile ID/version、Generator ID/version、required capabilities 和 seed；输出为 Standard Import v1 canonical bytes 与 `sha256:` hash。Manifest `generated_at` 记录运行时间但不进入 dataset hash。`simulation-contract-report.v1` 证明同输入 replay、版本变化、命名 layer seed 与 isolation precheck；它不包含生产 source versions/code commit，不是发布 manifest、Snapshot/Problem hash 或历史 Benchmark artifact。

## P0-06 formal fixture provenance

`SIM-MINIMAL-001@1.0.0` 将 Profile `1.0.0`、Assembler `1.0.0`、seed 6001、required capabilities、Import package `SIMPKG-SIM-MINIMAL-001-1.0.0`、`canonical-json.v1`、SIM-ASSUMPTION-006～009 和 hash `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10` 连接为首个正式 fixture provenance chain。manifest `generated_at` 继续不进入 hash。

Golden Schedule/expected validation/KPI 各有 fixture-local version，并通过 Scenario/schedule ID 连接但不进入 dataset hash。任务验收的 Git Diff base/HEAD 记录代码来源；这些 artifact 仍不是 production run/export manifest、Snapshot/Problem hash 或 Benchmark baseline。任何语义改动必须发布新 asset version/hash，禁止覆盖 `1.0.0`。

## TASK-P0-08 build and logging provenance

`Settings.build_metadata()` 与 `health-report.v1` 固定公开 code/spec/schema/code-commit 四元组；Production 配置拒绝 `uncommitted` 或非 40 字符 commit。CI 将 `github.sha` 注入 code commit，local/development 可以显式使用 `uncommitted`。该字段使 API/Worker build 可关联，但不是 Snapshot/Problem/Solver/Scenario/Export manifest。

structured logs 可通过 contextvars 携带 `correlation_id`、可选 `run_id`/`job_id`，并从当前有效 OpenTelemetry span 注入 trace/span ID。日志不作为唯一 provenance 或 audit store；P0-08 没有 PlanningRun metric/audit persistence、source version、Snapshot/Problem hash、Solver version 或成果 manifest。Schema set 保持 `1.2.0`，code/spec/schema metadata 文件未改。

## TASK-P1-02 canonical provenance contract

Schema set`2.0.0`新增strict Import/Snapshot provenance。每条canonical record携带source system/version/record ID；Import v2携带source versions、normalization rule version和canonicalization version；Snapshot v2还携带rule/expansion version、Import package ID/version/dataset hash与quality report ID/version/PASS状态。Synthetic文档必须携带scenario/profile/generator各自版本和seed，Production文档禁止该引用。

这些字段只建立可追溯输入合同。Sample中的digest是符合格式的contract sentinel，不是builder计算结果；dataset hash、Snapshot canonical projection/ID/hash、code commit、persistence与发布manifest仍由后续Task形成。Import/Snapshot v1逐字保留，v1/v2不互换；Schema set、document、normalization、expansion、canonicalization、Scenario/Profile/Generator和code commit继续是独立版本维度。
