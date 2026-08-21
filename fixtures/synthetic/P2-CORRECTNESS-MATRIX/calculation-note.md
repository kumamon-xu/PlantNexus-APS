# P2-CORRECTNESS-MATRIX@1.0.0 手工边界

本目录固定五个独立Scenario，均使用60秒tick和单订单最小模型：

- Cross Workshop：O1=`[0,1)`，transport lag=2，故O2最早且为零迟交的区间为`[3,4)`；
- Calendar：R1在`[0,2)`不可用，duration=2，故零迟交区间为`[2,4)`；
- Material Delay：material ready=tick 2，duration=1，故区间为`[2,3)`；
- Running：O1历史已开工，未来remaining固定为R1的`[0,2)`，O2在R2接续`[2,3)`；
- Hard Lock：O1虽有更快R2 candidate，但HARD_LOCK固定R1与`[1,3)`。

五例与Golden JSSP/FJSP共同覆盖P2 Synthetic Solver Gate的七类correctness输入，全部显式数值受`SIM-ASSUMPTION-011`约束。目录中的`XS`标签仅表示可手算大小，不进入`benchmarks/profiles.yaml`，不得解释为性能、容量、Production分布或SLA。任何语义变化必须新建catalog/Scenario/Profile/assembler version。
