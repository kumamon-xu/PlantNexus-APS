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
