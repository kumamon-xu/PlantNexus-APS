# P2-GOLDEN-JSSP@1.0.0 手工计算

两个工件使用相反的两机路线：J1为R1两tick后接R2一tick，J2为R2两tick后接R1一tick。两条首工序可在`[0,2)`并行，两条尾工序可在`[2,3)`并行；每个工件的串行工时下界均为3 tick，故makespan与两张订单完成时刻的下界均为3 tick。Due均为tick 3，因此weighted tardiness下界为0，列出的schedule达到该下界并由OBJ-001证明最优。

这些显式synthetic数值受`SIM-ASSUMPTION-011`约束。本资产只用于可手算correctness，不是XS性能profile、Production分布或SLA。任何字段或expected变化必须发布新asset version，不得覆盖`1.0.0`。
