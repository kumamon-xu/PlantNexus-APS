---
doc_id: DOC-GOV-001
title: 文档控制规则
status: baseline
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [1, 2, 6, 97, 101, 103, 104]
last_reviewed: 2026-08-26
---

# 文档控制规则

## 目的

保证拆分文档不会制造第二套互相冲突的事实来源，并使每个实现决策可追溯到规格、ADR、任务和验证证据。

## 必需元数据

每份正式 Markdown 文档至少声明：

```yaml
doc_id: stable-id
title: human-readable title
status: baseline | living | draft | planned | superseded
spec_version: 0.3.0
phase: P0 | P1 | ... | cross-phase
normative: true | false
source_sections: []
last_reviewed: YYYY-MM-DD
```

未知责任人不得猜测；在项目角色明确前可以不填写 `owner`。

## 权威与变更

- `core/APS_IMPLEMENTATION_SPEC.md` 保存上游总规原文和版本，不在拆分文档中暗改其语义。
- 拆分文档用于给特定职责提供更小、可操作的上下文。
- 修改架构、Solver Backend、Constraint 语义、目标层级、PlanningProblem、状态机、数据权威、分解策略、高级能力或生产性能阈值，必须提交 ADR。
- Schema、Simulation 资产和依赖升级必须使用各自版本号，不能只依赖 Git 提交号。
- 文档被取代时标记 `superseded` 并指向替代文档，不删除历史决策。
- 用户可见术语/locale字典也必须版本化。`official-zh-cn-terminology.v1`只治理展示语义，不能改变英文wire值；新机器值必须先由权威Contract/Schema/状态机发布，术语表不得抢先创造或猜测语义。

## 一致性规则

每个规范性结论应至少满足一项：

1. 可定位到总规章节；
2. 可定位到已接受 ADR；
3. 明确标记为 `PROD_OPEN`；
4. 明确标记为 `SIM_ASSUMPTION`；
5. 明确标记为非规范性建议。

禁止把推断、推荐技术栈或模拟参数伪装成已经确认的生产事实。

## 变更影响协议

每张 Task Card 在实施前必须完成三项声明：

```text
Documentation impact: required | none
Documents to update: explicit paths
Traceability updates: explicit IDs/matrix rows
```

`required` 时，所有目标文档必须进入 `Files allowed to change`；实施发现新影响时先修订 Task Card。`none` 时必须说明为什么变更不影响合同、行为、运行、测试口径、版本或使用方式，并引用 `change-impact-matrix.md` 的审查结果。

不能使用宽泛的“相关 docs”代替明确路径。文档影响分析本身是 Definition of Done 的必要证据。

## 文件命名

- 路径和文件名使用小写 kebab-case；
- 保留外部约定的固定名：`README.md`、`AGENTS.md`、`TASK_TEMPLATE.md`、`current_phase.md`；
- Requirement、Constraint、Objective、Task、Test、ADR 等 ID 一经发布不得复用；
- P0-P7 沿用总规编号，不再增加 M0-M7 的平行编号。

## 审查触发条件

以下事件必须检查受影响文档：

- `spec_version` 变化；
- Schema 或状态机变化；
- Constraint、Objective、Validator 或 SolverBackend 变化；
- 新增或关闭 `PROD_OPEN`；
- 进入新 Phase；
- Solver 或 Generator 升级；
- Release Gate、Benchmark Profile 或生产边界变化。

具体的代码目录、变更类型和必审文档映射见 `change-impact-matrix.md`。

进入新 Phase后，已完成的历史 Task Card继续保留并保持 terminal状态；当前 Phase可创建详细 Task；未来 Phase仍只能保留 Milestone。`docs/current_phase.md` 的 front matter `phase` 是机器校验的当前阶段来源，不能在校验器或 CI中另行硬编码。

## 仓库治理检查

基础全仓检查：

```text
uv run python scripts/check_docs.py
```

当前检查范围为：必需 metadata、唯一文档 ID、与总规一致的 `spec_version`、Markdown fence、本地链接、inventory metadata、版本化 registry、完整 ID 引用、Task 依赖、逐根 traceability、OPEN closure 证据和 PROD_OPEN/SIM_ASSUMPTION 隔离。

Task 进入 `in_progress` 时先记录当时完整 40 字符 HEAD SHA 为 `Diff base`。当前 Task 的 diff 检查：

```text
uv run python scripts/check_docs.py --task <task-card> --check-diff --report <report-path>
```

change-impact matrix 使用稳定 `IMPACT-*` Rule ID。实际 changed path 是 `Diff base..HEAD` 已提交路径与 working tree 路径的并集，必须命中机器规则；Task 必须声明全部命中行并把 Required documentation 列入 `Documents to update`。报告为 `traceability-report.v1`，记录 diff base 和两个来源的计数；机器 PASS 仍须在 Completion evidence 中记录实际文档更新、未修改理由和语义审查结论。

P1及以后 Task Card还必须填写 `Completion conditions`，把实现、负向路径、文档/追踪、治理验收与排除项写成可核验完成门；历史 P0 Task不追补该字段。

CI event attribution使用 `--discover-task-from <40-char-event-base>`：只允许选择唯一 current-phase Task Card，或在没有 changed Task Card时回退到唯一 `in_progress` current Task；event base只负责归属，scope仍由卡片 `Diff base`决定。历史/未来 Task、多个 current Task、无唯一归属、非完整/非祖先 SHA都必须非零失败。

## P3 planning control

P3首次batch只允许TASK-P3-00为唯一phase-planning owner，原P3-01～15为同range新建planned members；P0～P2卡保持terminal，P4+禁止详细卡。每个P3 member以后必须由新用户授权、clean synchronized/provider-verified HEAD和新Diff base单独激活；不允许用本batch批量实现。

用户批准后续计划修订时，event range必须由唯一已存在的`phase-plan-amendment-owner`归属；owner为`in_progress/done`并持有完整不可变Diff base。其他逻辑Task只能是`phase-plan-member`、`planned/ready`且无implementation SHA；允许稳定Task ID不变的文件重命名，禁止纯删除、重复存活路径和对base中active/done成员的改写。修订owner的provider成功不等于成员实现授权。独立Exit Audit仍须作为P3最后一项，READY后也需用户批准才能进入P4。
