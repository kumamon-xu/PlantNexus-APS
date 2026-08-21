# P2-GOLDEN-FJSP@1.0.0 手工计算

J1在R1/R2分别耗时1/3 tick，J2在R1/R2分别耗时2/1 tick；两张订单due均为tick 1。把J1分配至R1、J2分配至R2并同时执行`[0,1)`可使两项tardiness均为0。weighted tardiness非负，因此0为全局下界；任何慢candidate都无法在due前完成，故列出的resource选择是唯一零目标选择。

这些显式synthetic数值受`SIM-ASSUMPTION-011`约束。本资产只用于可手算FJSP correctness，不是XS性能profile、Production分布或SLA。任何字段或expected变化必须发布新asset version，不得覆盖`1.0.0`。
