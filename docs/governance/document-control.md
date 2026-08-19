---
doc_id: DOC-GOV-001
title: 文档控制规则
status: baseline
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [1, 2, 6, 97, 101, 103, 104]
last_reviewed: 2026-08-19
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
