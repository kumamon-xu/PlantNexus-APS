---
doc_id: DOC-QUAL-007
title: 文档一致性自动检查合同
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 98, 99, 100, 101, 103, 104]
last_reviewed: 2026-08-27
---

# 文档一致性自动检查合同

## 目标

`scripts/check_docs.py` 是依赖最小、fail-closed 的文档与 Task scope 校验入口。它验证当前事实是否一致，不负责保存每个 Task 的历史验收叙述。

## 两种运行模式

### Repository governance

~~~powershell
uv run python scripts/check_docs.py
~~~

用于检查整个正式文档集的结构和登记关系，不读取 Git diff 作为变更范围。

### Current Task diff

~~~powershell
uv run python scripts/check_docs.py `
  --task docs/tasks/Px/TASK-Px-yy-name.md `
  --check-diff `
  --report build/traceability/TASK-Px-yy-report.json
~~~

用于把 Task 的不可变 Diff base..HEAD 与当前 tracked/untracked working tree 合并，检查真实路径、Impact Rule、Documents to update 和 exact allow-list。

只有一个 current-phase Task 为 `in_progress` 时可以省略 `--task`。CI event 场景可以使用：

~~~powershell
uv run python scripts/check_docs.py `
  --discover-task-from <event-base-sha> `
  --check-diff `
  --report build/traceability/ci-current-task-report.json
~~~

## Repository governance 检查

校验器至少覆盖：

- YAML front matter、doc_id、status、phase、spec_version；
- Markdown 标题、代码围栏、相对链接与目标路径；
- registry_version 与 machine-readable 表格；
- Requirement、NFR/ENG、Test、ADR、Constraint、Objective、PROD_OPEN、SIM_ASSUMPTION、Risk ID；
- traceability root 与 landing/evidence 路径；
- Task 必填字段、状态、phase policy、直接依赖和引用；
- 唯一 current-phase `in_progress` owner；
- document inventory 的新增、删除、重命名一致性；
- Production open 与 Simulation assumption 分离；
- CLOSED 项的 authority/evidence/decision 记录。

机器结果是权威明细。README、Current Phase、Milestone 和规则正文不再复制每次运行的所有计数。

## Task diff 检查

`--check-diff` 必须 fail closed 验证：

1. Diff base 是完整 40 字符 commit，存在且为 HEAD ancestor；
2. changed path union 同时包含 committed range 和当前 working tree；
3. 每个路径至少命中一个 change-impact rule；
4. 所有实际命中的 Rule ID 都在 Task 声明；
5. Task 没有声明未实际命中的已知 Rule ID；
6. 每条规则的最低 Required documentation 都在 Documents to update；
7. 所有 changed path 均在 Files allowed to change；
8. Files forbidden to change 保持零差异；
9. report 中 issues 为空才是 PASS。

纯 `.gitkeep` 不产生 impact requirement。

## 精简后的文档影响语义

Change-impact matrix 的 Required documentation 是机器强制最低集合。Task 卡的 Documents to update 只应包含：

- 实际要修改的直接语义所有者；
- 机器规则要求的最低文档；
- 因高风险行为变化而必须同步的 Contract、ADR、state、security、migration 或 benchmark 文档。

不再要求：

- 把所有“可能相关”文档列成候选全集；
- 对几十份未修改文档逐份写无变化说明；
- 因修改任一 `docs/**` 而重写 inventory、matrix、traceability、CI 和 Task 模板全家桶；
- 在 registry 中追加 Task-specific run/artifact 历史。

若最低文档复核后无需改正文，可以在 Task rationale 中说明；但它仍须出现在 Documents to update，供机器确认已纳入审查。

## Task report 合同

`--report` 输出 `traceability-report.v1` JSON，至少包含：

- result、Task ID、Diff base、git_head；
- committed range / working tree source counts；
- changed paths；
- matched impact rows；
- expected / observed documents；
- registry counts；
- checks；
- issues。

报告路径必须位于仓库内。完整路径清单和检查明细只保存在该报告与 Provider manifest，不复制到多个 Markdown。

## 任务发现

自动发现只在“唯一且可证明”时成功：

- current phase 恰有一个 `in_progress` Task；或
- event base 之后的 changed Task cards 能唯一解析为 current owner。

多 owner、无 owner、phase 不一致或 Task card 缺失时必须报错，不猜测。

## 失败处理

- 结构或引用错误：修正文档源，不跳过检查。
- 未匹配路径：新增有界 Rule ID/glob 或修正错误路径。
- 漏声明 Rule/文档：先修订 Task 卡，再继续实现。
- 越界路径：回退越界变更或明确扩展 Task scope。
- stale declaration：删除未命中的 Rule，不用未来计划伪装当前影响。
- invalid Diff base：恢复正确的 pre-Task ancestor，不使用短 SHA 或移动基线。

禁止删除校验、降低断言、伪造 report 或手工把 FAIL 改为 PASS。

## 校验器变更

修改 `scripts/check_docs.py` 或其单元测试时必须：

1. 声明 IMPACT-GOVERNANCE-VALIDATOR；
2. 更新本合同与必要的 agent/template 规则；
3. 添加或更新 focused unit tests；
4. 运行完整 repository governance 与 Task diff；
5. 若 machine table 格式改变，同步 registry_version 和 parser tests。

只修改规则正文、不修改校验器行为时，不需要运行无关业务回归。

## 已知边界

校验器证明结构、登记、路径和声明一致，不证明业务算法正确、文档内容真实或 Provider 身份可信。业务正确性由对应 Validation profile、测试、machine report 和 Provider/local manifest 证明。

## 记录边界

本文件只保存稳定检查合同。每个 Task 的 SHA、run/job/artifact、digest、精确计数、临时异常与完成历史保存在 Task report、Provider manifest、专项 Audit 或 Git 历史，禁止继续追加到本文件。
