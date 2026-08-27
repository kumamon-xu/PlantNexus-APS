---
doc_id: TEMPLATE-TASK
title: Task Card Template
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [98, 99, 100, 111]
last_reviewed: 2026-08-27
---

# TASK-Px-yy — Title

本模板只保存所有 Task 共用的字段。专项语义来自当前 Contract、ADR、Constraint、Milestone 和 agents/review-checklists.md；不得把每个历史 Phase 的实现细节继续追加到模板。

Task batch role: phase-plan-member | phase-planning-owner | phase-plan-amendment-owner

Requirement IDs: 明确列出

NFR / ENG IDs: 明确列出

Depends on: 只列直接依赖

Start gate: P2+必填；授权、直接依赖 compact manifest、clean/synchronized HEAD

Goal: 一个可独立验收的结果

Non-goals: 防止顺带实现

Inputs: 直接 Contract、Schema、ADR、artifact 或业务输入

Diff base: 进入 in_progress 前的完整 40 字符 HEAD

Validation profile: DOCS_ONLY | STANDARD | HIGH_RISK | PHASE_GATE

Files allowed to change: 精确文件或有界目录；Documents to update 必须包含在内

Files forbidden to change: 明确高风险与后续阶段边界

Implementation steps: 最小有界步骤

Outputs: 代码、合同、报告或 artifact

Documentation impact: required | none

Documents to update: 只列预计实际修改的语义所有者和 change-impact matrix 的最小 required documents

Documentation impact rationale: 说明真实对外语义；none 时给出简短可验证理由

Change-impact matrix rows reviewed: 实际命中的 IMPACT-* Rule ID

Traceability updates: Requirement/NFR/ENG → Task → Test → Artifact

Schema changes: version、compatibility、preserved bytes；没有则说明 none

Migration: upgrade/downgrade/data loss；没有则说明 none

Dependency changes: P2+必填；exact pin/lock 或 none

ADR impact: P2+必填；required/none 与触发条件

State-machine impact: changed/none 与 pair/version

Error behavior: fail-closed code/category/stage 与无副作用边界

Tests: 目标 positive/negative/property/integration/e2e

Test IDs: 已登记 Test ID

Benchmark impact: profile/baseline/threshold 或 none

Simulation scenarios: version/seed/plane 或 none

Acceptance commands: 与 Validation profile 对应的本地命令和 Provider gate

Artifacts: machine report、Task report、Provider manifest

Provider evidence: P2+必填；configured provider/repository/workflow/required job，或治理批准的 local-only manifest，与 exact SHA 绑定

Completion conditions: P1+必填；使用可二值判断的目标、边界、测试、文档和 trace 条件

Failure handling: 失败后状态、corrective scope 与禁止掩盖方式

Explicitly excluded: 后续能力、Production、外部 authority 等

PROD_OPEN: 真实变化或保持项

SIM_ASSUMPTIONS: 真实变化或保持项

Rollback: 可执行回退与不可改写历史

## 使用规则

1. Task 只拥有一个主要 Goal；发现独立目标时创建单独 Task，不把不相关实现并入当前卡。
2. 直接依赖只通过 compact manifest 验证；普通 Task 不递归下载全部祖先 artifact。
3. Documents to update 不是所有可能相关文档的清单。候选文档未发生语义变化时不加入，也不要求逐份写无变化说明。
4. Task 引用哪个 ADR、Contract 或 Constraint，就完整读取哪个决策单元；大注册表只读取命中行。
5. Validation profile 不能低于风险：Solver/Constraint/State/Migration/Security/Publication/Dependency 默认为 HIGH_RISK，Exit Audit 为 PHASE_GATE。
6. Implementation exact Provider 是业务证据主体。纯 evidence-only closure 只有在 diff 证明没有代码、Schema、test、workflow、dependency、migration 或合同语义变化时才可使用轻量 Gate。
7. 失败 run 保留；corrective 使用新 SHA。禁止只 rerun 旧 SHA、skip、降低断言或改写历史。
8. Task Done 不自动启动下一 Task，也不等于 Milestone/Production ready。

## Acceptance 最小集

所有 Task：

~~~text
targeted positive and negative checks
uv run python scripts/check_docs.py
uv run python scripts/check_docs.py --task <task-card> --check-diff --report <report-path>
git diff --check
forbidden-scope check
~~~

STANDARD：

~~~text
affected lint and type checks
targeted unit / contract / integration
one exact Provider run for the affected stack
~~~

HIGH_RISK 在 STANDARD 之上增加适用项：

~~~text
full relevant backend or frontend suite
migration upgrade / downgrade / replay
Golden / Mutation / Property / Benchmark
security / SCA / license / browser evidence
non-skippable exact Provider artifact
~~~

PHASE_GATE 还必须独立 fresh replay，不得复用实现 Task 的 PASS 代替 Audit。

## Completion evidence

保持简洁，只填写：

- completed_at；
- implementation SHA、可选 closure SHA；
- Validation profile 和 PASS/FAIL；
- machine report、Task report、Provider manifest 路径；
- 实际更新的语义文档；
- traceability、OPEN、SIM、ADR 变化；
- blocking issues 与 rollback。

changed paths 全表、每条命令 stdout、所有 run/job/artifact/digest 和失败诊断保存在机器报告或专用 Audit，不复制到 Task、Current Phase、README、Milestone 和多个 registry。
