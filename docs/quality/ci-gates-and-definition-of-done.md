---
doc_id: DOC-QUAL-006
title: CI Gate 与 Definition of Done
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [58, 72, 74, 76, 78, 80, 89, 100, 101]
last_reviewed: 2026-08-27
---

# CI Gate 与 Definition of Done

## 目标

Gate 要证明当前变更安全、可追溯且可复现，不以重复运行全部历史检查来制造“证据数量”。验证范围由风险和真实影响决定，质量底线不因 Profile 降低。

## Validation profiles

| Profile | 使用条件 | 必须证明 |
| --- | --- | --- |
| DOCS_ONLY | 仅正文、索引、状态或证据写回；无代码、Schema、test、workflow、lock、migration、fixture/baseline 变化 | 文档结构/链接、Task diff、allow/forbidden scope、无语义实现变化 |
| STANDARD | 有界实现，不改变高风险合同 | 目标正负例、受影响 static/type、相关集成、machine report、受影响技术栈 Provider |
| HIGH_RISK | Schema compatibility、PlanningProblem、Constraint、Solver、Validator、state、migration、security、publication、dependency | STANDARD 加完整相关 suite、失败/回滚路径及适用的 property/mutation/golden/benchmark/security/replay |
| PHASE_GATE | Vertical Gate、Exit Audit、Production readiness | 对阶段要求做 fresh independent replay，并生成独立 evidence manifest |

最低 Profile 由风险决定。Task 可以上调，不能为了节省时间下调。

## 通用必过项

所有 Profile 都必须：

1. Task ID、完整 Diff base、当前 SHA 或 working-tree 状态可识别；
2. allowed/forbidden scope 无越界；
3. 目标正向路径与直接负向路径通过；
4. full documentation governance 通过；
5. Task diff governance 通过且 issues 为空；
6. git diff check 通过；
7. blocking issue 显式记录，失败不得被描述为 PASS。

DOCS_ONLY 的“目标测试”可以是文档结构、链接、registry parse 与 machine diff；不要求运行无关业务 suite。

## 按影响选择检查

| 实际影响 | 追加检查 |
| --- | --- |
| Python/backend | 受影响 Ruff、Pyright、unit/contract/integration；HIGH_RISK 才要求完整相关 backend suite |
| Frontend | lint、typecheck、Vitest；用户路径或跨栈合同变化时运行对应 E2E |
| Schema/serialization | compatibility、sample、round-trip、preserved bytes、version/migration |
| Solver/Constraint/Validator | independent negative oracle、property/mutation、determinism；性能受影响时 Benchmark |
| State/persistence/migration | transition/CAS、atomicity、upgrade/downgrade/replay、无数据丢失 |
| Security/publication/authority | authorization、negative access、audit、SCA/license 及 fail-closed 行为 |
| Dependency/runtime | locked install、build、license/SCA、兼容性与回退 |
| Workflow/CI | required job、permissions、artifact、failure semantics 和 exact SHA binding |

Backend-only Task 不默认运行浏览器；Frontend-only Task 不默认运行 Solver Benchmark。跨栈行为和 PHASE_GATE 除外。

## 本地与 Provider

本地验证用于快速反馈和提交前证明。配置了远程 Provider 的项目，以 exact implementation SHA 上的 required job 和 artifact 作为可共享证据；本地 PASS 不冒充 Provider PASS。

Provider artifact 的最小字段：

- Task ID；
- Diff base；
- exact code commit；
- Validation profile；
- required job conclusion；
- Task diff report；
- Task-specific machine report；
- blocking issues。

大段 stdout、完整 changed-path 列表、每个文件 digest 和全部历史 run 不进入本规范正文；保存在 machine report、Provider manifest 或专项 Audit。

若项目明确采用 local-only Git：

- Task 卡写明 provider=local-only；
- 使用不可变本地 commit 和 machine manifest 绑定证据；
- 不要求伪造远程 run/job/artifact；
- Phase Gate 仍须 fresh replay，并由独立 manifest 记录。

Provider 模式的改变必须由治理 Task 明确修改，不能在业务 Task 中临时降级。

## Implementation gate

业务实现以 implementation SHA 为证据主体：

1. 运行对应 Profile；
2. machine report 绑定 Task、base、SHA、checks 和 issues；
3. required Provider 对 exact SHA 成功；
4. 下载或读取 artifact manifest，核对身份与结论；
5. 失败时保留失败记录，以新 corrective SHA 修复并重跑。

禁止通过 rerun 旧 SHA、skip、continue-on-error、降低断言、改写 baseline 或只修改文档来把失败变成 PASS。

## Evidence-only closure

Implementation Provider 已成功后，closure 只允许更新 Task/Phase/Milestone/registry/evidence 文档。只有机器 diff 证明以下路径均无变化时，才可以使用轻量 closure gate：

- 产品代码；
- Schema 与 migration；
- test assertion；
- workflow；
- dependency 与 lock；
- fixture、golden、benchmark baseline；
- Contract/ADR 的实现语义。

轻量 closure gate 仍须运行 full docs、Task diff、scope、git diff check，并校验 implementation manifest。若任何上述边界变化，closure 就是新的 implementation/corrective，必须重跑原 Profile。

## Task Definition of Done

Task 只有同时满足以下条件才可标记 done：

- Goal 与 Completion conditions 全部满足；
- Non-goals 和 forbidden scope 未被突破；
- 对应 Validation profile 通过；
- 配置的 Provider 或 local-only manifest 绑定 exact implementation commit；
- 文档、traceability、OPEN、SIM、ADR 真实同步；
- 未关闭 blocker 为零；
- rollback 可执行；
- completion evidence 已以紧凑形式写回。

Task Done 不自动启动下一 Task，也不代表 Milestone、Production 或外部 authority 已就绪。

## Phase Definition of Done

Phase Gate 不能复用单个实现 Task 的 PASS 代替独立审计。至少需要：

- Milestone exit criteria 全部满足；
- 阶段 Requirement/NFR/ENG → Task → Test → Artifact 可追溯；
- fresh replay 对当前 immutable SHA 通过；
- 前序 manifest 身份、有效性和结论可核对；
- 跨 Task 回归、关键失败路径和 unresolved register 已审计；
- 独立 Exit report/manifest 给出 READY 或 BLOCKED；
- 用户明确授权下一阶段。

## 当前迁移边界

现有 workflow 仍以 `validate` 作为统一 required job，尚未实现按 Profile 的 Provider 路由。因此：

- 正在执行的 TASK-P4-05 保持原 HIGH_RISK 全量 Provider 合同和 freeze-window machine evidence，不在本次文档优化中降级；
- 新规则立即减少本地无关读取、文档扩散和重复证据抄写；
- 轻量 closure Provider 只有在后续独立 CI 治理 Task 实现并测试后才能启用；
- 在该实现完成前，远程 closure 仍沿用现有 `validate`。

## 记录边界

本文件只保存稳定的 Gate 与 Done 定义。Task-specific run ID、job ID、artifact ID、digest、测试计数、失败诊断和完成历史属于 Task 卡、machine report、Provider manifest、Milestone Exit report 或 Git 历史，禁止继续追加到本文件。
