# PlantNexus APS Agent 入口

本文件只负责项目规则自动发现。所有实质性 Agent 规范位于 `docs/agents/AGENTS.md`。

开始任何任务前按顺序读取：

1. `docs/agents/AGENTS.md`
2. `docs/current_phase.md`
3. 当前任务卡
4. 任务卡引用的 Contract、Constraint 与 ADR

如果当前任务卡不存在、阶段不允许该工作，或需要修改任务卡禁止范围之外的文件，必须停止并先修订任务边界。

每张任务卡还必须声明 `Documentation impact`、`Documents to update` 和 `Traceability updates`。任务结束时，要么同步更新列出的文档和追踪记录，要么以可验证理由声明 `Documentation impact: none`；不得省略该判断。
