---
doc_id: DOC-AGENT-001
title: PlantNexus APS Coding Agent 规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [1, 2, 6, 12, 30, 59, 90, 98, 99, 100, 110, 111]
last_reviewed: 2026-08-27
---

# PlantNexus APS Coding Agent 规则

根目录 AGENTS.md 只负责自动发现；本文件保存稳定、跨阶段的 Agent 规则。Task、run、artifact、测试数量和历史 SHA 不得写入本文件。

## 默认启动顺序

开始 Task 时按以下顺序读取：

1. 完整读取本文件；
2. 完整读取 ../current_phase.md；该文件只允许保存当前阶段快照；
3. 读取当前 Task Card 从 front matter 到 Rollback 的规范部分；
4. 只读取 Task 明确引用且与目标直接相关的 Schema、Contract、Constraint、ADR；
5. 读取受影响代码、邻接接口和对应测试。

Task Card 的 Activation evidence、Completion evidence 和历史失败记录默认不加载。只有启动证据核验、closure、remediation 或 Phase Audit 才读取对应段落。

根 README.md 只作为命令和仓库地图入口，不能覆盖 Task、Contract、ADR 或总规。

## 上下文预算

- 默认不读取历史 Phase、已完成 Task Card、完整 artifact 内容、完整注册表、完整 Test Matrix、Document Inventory 或 Change Impact 历史。
- 大型注册表和矩阵使用标题、稳定 ID、表格行或精确搜索定位；读取命中的规范段，不从第一行机械加载到文件末尾。
- ADR 和直接业务 Contract 应完整读取；仅被列为候选影响、但语义没有变化的文档只需核对相关章节。
- 已由 exact SHA 机器清单证明的依赖，默认读取清单摘要；只有摘要缺失、签名或 SHA 不一致、证据过期、Task 明确要求独立审计时才下载原始 artifact。
- 如果默认启动上下文超过约 30,000 字符，应先缩小到稳定 ID、章节和机器摘要，并在工作记录中说明扩大上下文的原因。

详细策略见 reading-order-and-context-policy.md。

## 完整总规触发条件

下列情况必须完整读取 ../core/APS_IMPLEMENTATION_SPEC.md：

- spec_version 变化；
- Task 直接修改总规或提出 superseding 的顶层规范决定；
- 架构、PlanningProblem、SolverBackend、Constraint、状态机、发布或 Exit Gate 的既有规范发生语义变化；
- Contract、ADR 与总规出现无法通过局部章节消解的冲突；
- Phase Exit Audit 明确要求对整份总规做独立合规重放。

实现已经由当前版本 Contract 或 accepted ADR 固定的 consumer，不因路径名称包含 problem、backend、state 等字样自动触发整份总规；仍须完整读取直接 Contract、ADR 和总规对应章节。

## 执行边界

- 只修改 Task Card 的 Files allowed to change。
- 需要额外文件时先说明原因并更新 Task 边界；不得无边界扩张。
- Task 必须填写 Documentation impact、Documents to update 和 Traceability updates。
- Documents to update 只列预计实际修改的语义所有者和机器规则要求的最小文档，不列所有可能相关文档。
- P1 以后必须填写可二值判断的 Completion conditions。
- 不得提前实施当前 Phase 以后的能力。
- 不得把 SIM_ASSUMPTION 写入 Production Business Policy。
- 不得猜生产数据、班次、冻结窗口、运输时间、标准工时、库存、资源能力或目标权重。
- 不得删除硬约束、修改断言掩盖缺陷、静默忽略能力或把 Hint 当约束。

Task 进入 in_progress 时必须记录启动前完整 40 字符 HEAD 为 Diff base。Diff acceptance 使用 Diff base..HEAD 与 working tree 的并集。

## 模块与语义底线

- CP-SAT 建模只进入 planning/backends/cp_sat。
- Domain、API Controller、React 和 ORM 不承载 CP-SAT 建模。
- Validator 不导入或复用 CpSatBackend 的约束实现。
- Simulation 必须走 Standard Import → Snapshot → Problem → same Solver/Validator。
- FEASIBLE 不称最优；UNKNOWN 不称无解；Synthetic Benchmark 不称生产容量。
- 未支持能力必须显式返回 UNSUPPORTED_CAPABILITY。

## 风险分级验收

验收按 task-execution-protocol.md 的 DOCS_ONLY、STANDARD、HIGH_RISK、PHASE_GATE 四级执行：

- 所有 Task 都运行目标测试、错误/边界测试、文档全仓检查和当前 Task diff 检查；
- STANDARD 至少在项目已配置的 Provider 上完成一次完整受影响技术栈回归；明确采用 local-only Git 时以 exact immutable local manifest 代替，不伪造远程证据；
- Solver、Constraint、状态机、migration、security、publication、依赖升级等 HIGH_RISK Task 保留完整本地相关回归、Benchmark 或 migration replay，并在 Provider 上全量执行；
- Phase Gate/Audit 保留独立 fresh replay，不复用实现 Task 的结论代替审计。

不得为了节省时间跳过直接受影响的测试、负向路径、Schema compatibility、独立 Validator 或 required Provider。

## 证据与完成

- Completion evidence 以机器报告和 manifest 为权威；Task Card 记录结论、exact SHA、报告路径和未关闭问题，不复制全部 changed paths、digest、测试清单和历史 run。
- 普通后继 Task 只验证直接依赖的 compact manifest 与当前 HEAD 祖先关系，不递归重放整条历史链。
- Implementation commit 必须取得 Task 风险级别要求的 exact configured Provider 证据；明确的 local-only 模式则绑定 exact commit 的本地 machine manifest。
- 纯 evidence-only closure 若机器证明相对 implementation 只修改 Task、Phase、Milestone、registry 或 evidence 文档，可以使用轻量 closure gate；若出现代码、Schema、测试、workflow、依赖、migration 或业务合同变化，必须恢复完整 Gate。
- 失败命令、失败 run 和缺失证据必须真实记录，不得写成 PASS。

Task 完成至少更新真实 traceability、开放问题、假设和必要文档。未修改候选文档不要求逐份写无变化说明；只需说明命中的 Impact Rule、实际文档和为何没有对外语义变化。

## 治理命令

全仓文档检查：

~~~text
uv run python scripts/check_docs.py
~~~

当前 Task 范围检查：

~~~text
uv run python scripts/check_docs.py --task <task-card> --check-diff --report <report-path>
~~~

CI 使用不可变 event base 自动发现唯一 current-phase Task。Task discovery、多卡 planning/amendment 的算法细节由 documentation-consistency-checks.md 和校验器测试负责；普通实现 Task 无需加载这些内部算法。

## 阶段边界

Task Done 不等于 Milestone Done。未经 Phase Gate 与用户确认，不更新到下一 Phase。

current_phase.md 只保存当前快照、当前 Task、直接依赖、当前禁止项和下一 Gate。历史 run、artifact、失败诊断和已完成 Task 详情保存在各 Task、Milestone Audit、机器 manifest 与 Git 历史中。
