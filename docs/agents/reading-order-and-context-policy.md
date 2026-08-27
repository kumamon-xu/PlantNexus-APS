---
doc_id: DOC-AGENT-002
title: Agent 读取顺序与上下文策略
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [2]
last_reviewed: 2026-08-27
---

# Agent 读取顺序与上下文策略

## 目标

上下文必须足以保证正确性，但不得把仓库历史、机器证据和所有候选规范反复装入每个新 Session。

默认启动链：

~~~text
AGENTS.md thin entry
→ docs/agents/AGENTS.md
→ concise current_phase.md
→ current Task normative fields
→ direct Contract / Constraint / ADR
→ affected code and tests
~~~

## Task Card 分段读取

默认读取：

- front matter、Goal、Inputs、Diff base；
- allowed/forbidden scope；
- Implementation steps、Error behavior、Tests；
- Documents to update、Traceability、Completion conditions、Rollback。

按需读取：

- Activation evidence：仅启动门、依赖异常或 provenance 核验；
- Completion evidence：仅 closure、remediation、handoff 或 Audit；
- 历史失败：仅当前缺陷与其直接相关时。

不得因为 Task Card 中存在 run ID、artifact digest 或 frozen hashes，就在普通实现启动时逐项重新验证。

## 大文档读取规则

以下文档默认使用精确定位，不完整加载：

- governance registries；
- change-impact matrix 的历史记录；
- test strategy 的历史完成证据；
- CI/DoD 的历史 run 记录；
- document inventory；
- prior-phase milestone 和 audit；
- 已完成 Task Card。

定位顺序：

1. 使用稳定 ID、标题或路径搜索；
2. 读取命中表格行或完整规范章节；
3. 如果存在引用冲突，再扩展到相邻章节；
4. 只有 AGENTS.md 定义的触发条件成立时才完整读取总规。

文件较大不等于可以只读半条规范：一旦选中一个 ADR、Contract 或章节作为当前决策依据，必须完整读完该选中单元。

## 上下文扩大矩阵

| 变化 | 必需上下文 | 不默认加载 |
|---|---|---|
| 文档/证据更新 | 当前 Task、命中文档、机器报告摘要 | 代码、历史 Phase、全部测试历史 |
| 局部实现 | 直接 Contract、代码、目标测试、相关错误模型 | 全部架构与所有 registries |
| Schema/Contract 语义 | Schema、producer/consumer、versioning、compatibility、相关 ADR | 不相关 Phase 和 UI |
| Solver/Constraint/Validator | 对应 C-ID/OBJ、Problem/Policy、Backend、独立 Validator、Benchmark | Frontend、历史 provider 明细 |
| 状态/发布/security/migration | 状态或安全 Contract、ADR、事务/回滚测试、运维边界 | 不相关算法与历史 Task |
| Phase Gate/Audit | Milestone、全部直接 Task manifest、总规、fresh Gate | 不以实现 Task 摘要代替审计 |

## 证据复用

普通 Task 的依赖核验只需要：

- 直接依赖状态为 done；
- implementation/closure SHA 是当前 HEAD 祖先；
- compact manifest 绑定 Task、SHA、Diff base、required check 和零 blocking issue；
- artifact 未过期，或内容摘要已经以不可变 digest 固化。

只有以下情况下载原始 artifact：

- manifest 缺失、格式错误或 SHA 不匹配；
- required check/provider identity 异常；
- 失败 remediation 需要原始诊断；
- Phase Audit 明确要求独立复核；
- 用户要求完整取证。

## current_phase 维护预算

current_phase.md 应控制在 120 行和约 12,000 字符以内，只保留：

- 当前 Phase/Milestone 状态；
- 唯一当前 Task 与 Diff base；
- 直接依赖结论；
- 当前允许与禁止；
- 下一 Gate 和授权边界；
- 指向 Task、Milestone、Audit/manifest 的链接。

完成一个 Task 时替换当前快照，不追加完整历史。历史仍可从 Git、Task Card、Milestone 和机器 manifest 恢复。

## 规划修订

阶段计划的新建、增卡、改号或重命名仍使用 phase-planning owner / phase-plan-amendment owner 机制，并要求用户明确授权。普通实现 Task 只需要知道自己是唯一 current Task；多卡发现算法由治理校验器负责，不进入默认上下文。
