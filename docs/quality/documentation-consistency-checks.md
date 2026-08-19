---
doc_id: DOC-QUAL-007
title: 文档一致性自动检查合同
status: baseline
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [6, 98, 99, 100, 101, 103, 104]
last_reviewed: 2026-08-19
---

# 文档一致性自动检查合同

本文件定义由 TASK-P0-02 建立的文档/追踪校验器合同。实现入口为
[`scripts/check_docs.py`](../../scripts/check_docs.py)，负向和回归测试入口为
[`TEST-TRACEABILITY-VALIDATOR`](../../backend/tests/unit/test_check_docs.py)。该检查器只使用 Python
标准库；P0-02 提供本地/Task acceptance 能力，PR 与 Release 自动执行仍分别由 P0-08、P0-09 接入。

## 命令接口

仓库全量一致性检查：

```text
uv run python scripts/check_docs.py
```

当前 Task 从不可变基线至 HEAD、再联合 working tree 的影响矩阵检查，并生成机器可读报告：

```text
uv run python scripts/check_docs.py --task <task-card> --check-diff --report <report-path>
```

校验器单元测试：

```text
uv run python -m unittest discover -s backend/tests/unit -p "test_check_docs.py"
```

## 输入

- `--task` 指定的当前 Task Card及其中在进入 `in_progress` 时记录的完整 `Diff base`；
- `git diff --name-only Diff-base..HEAD` 的已提交路径；
- `git status --porcelain` 相对 `HEAD` 的 tracked/untracked working tree 路径；
- `change-impact-matrix.md`；
- 文档元数据、治理注册表、追踪矩阵和测试 ID 表；
- 当前 Phase 和 Milestone。

## 必须检查

1. Task Card 包含非空 `Documentation impact`、`Documents to update`、`Traceability updates`；
2. `required` 时文档路径明确存在或由本 Task 创建，并包含在 Files allowed to change；
3. `none` 时有非空理由和已审查的 impact-matrix 行；
4. `Diff base` 是存在且为当前 HEAD 祖先的完整 40 字符 commit SHA；已提交范围与 working tree 并集命中的 `IMPACT-*` 行已在 Task 声明，规则要求的文档已列入 Documents to update；
5. 实际 changed paths 全部位于 Task 允许范围；`.gitkeep` 由矩阵显式忽略；
6. 文档 metadata、唯一 doc ID、source sections、相对链接和 Markdown fence 有效；
7. `registry_version: 1.0.0` 存在，注册表 ID 唯一，Requirement/NFR/ENG/C/OBJ/TASK/TEST/ADR/OPEN/SIM/RISK 引用可解析；
8. 追踪矩阵对所有 Requirement/NFR/ENG 根 ID 一一覆盖，且只链接真实存在的代码、测试和 artifact；
9. 当前 Task 的 dependency、Phase、状态和当前阶段约束一致；
10. `PROD_OPEN-*` 关闭时包含权威来源、证据、决定日期、影响面和迁移/回放结论；
11. `PROD_OPEN-*` 与 `SIM_ASSUMPTION-*` 没有混用，模拟假设不能关闭生产开放项；
12. 只有当前 Phase 存在详细 Task Card，其他阶段只能保留计划级条目。

## CI 分层

| 层 | 行为 |
|---|---|
| Local/Task acceptance | 对当前 Task 的 `Diff base..HEAD` + working tree 运行；提交前后均须可复验，失败不得标记 Done |
| Pull Request | P0-08 接入后成为必需检查；阻止缺失文档影响、断链、版本漏更和越阶段任务 |
| Release | P0-09 接入后在 PR 检查上增加 Artifact/manifest、Milestone Gate 和 production readiness 一致性 |

## 输出

`--report` 写出 `traceability-report.v1` JSON，包含总体状态、Task、Git HEAD、`diff_base`、
`diff_source_counts`、changed paths、matched matrix rows、expected docs、observed docs、检查统计、
带 check ID/severity/message/hint 的 issues。
任一 error 均返回非零退出码；通过时终端输出 `PASS repository governance` 及关键计数。

## 已知边界

校验器验证治理结构、引用、范围和影响同步，不判断业务规则是否正确，也不替代 Schema
兼容性、Solver 正确性、迁移回放或 benchmark 结果。上述语义验证由对应 Task 和后续 CI/Release
Gate 负责；P0-02 不据此声称任何业务能力已实现。

机器治理检查不解析 JSON Schema 语义或 YAML data dictionary。TASK-P0-03 由 `TEST-CONTRACT-001` 使用锁定的 `jsonschema` Draft 2020-12 validator、PyYAML、Ruff 与 Pyright 补充这层证据；后续 Schema Task 必须同时运行治理检查和对应 contract tests。

TASK-P0-04 增加独立的规则合同入口：

```text
uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-04-rule-contracts.json
```

该命令校验 C-001～C-018 rule sheet、20 capability、七类/19 code、三套 state/42 transitions、三份新增 JSON Schema、schema set version 和 validation package 的 Solver import boundary。报告为 `rule-contract-report.v1`，只证明 metadata/registry/schema 一致，不判断 candidate schedule、业务 guard、持久化或 Solver 正确性。

TASK-P0-05 增加 Simulation 合同入口：

```text
uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P0-05-simulation-contracts.json
```

该命令生成 `simulation-contract-report.v1`，验证 empty Standard Import package 的 same-input bytes/hash、generated-at hash exclusion、Generator version change、named layer seed、Production target 和 unsupported capability rejection。Schema/sample 语义由 pytest/jsonschema 补充。报告不验证非空 Factory/Order/Routing records、Import pipeline、Snapshot/Problem、DB/API isolation、Solver 或 Benchmark。

## Override

不允许用自由文本 CI skip 绕过。确需例外时必须在 Task Card 记录理由，提交 ADR 或明确批准记录，并仍保留检查报告。正确性、状态语义、数据隔离和发布门不得豁免。
