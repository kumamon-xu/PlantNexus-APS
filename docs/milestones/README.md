---
doc_id: DOC-MILESTONE-INDEX
title: Milestone 索引
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84]
last_reviewed: 2026-08-21
---

# Milestone 索引

项目沿用总规 P0～P7，不建立 M0～M7 平行编号。

| Phase | 名称 | 主要结果 |
|---|---|---|
| P0 | Executable Specification | 固定排什么、什么算正确 |
| P1 | Data & Snapshot | 正式/仿真输入走同一确定性数据链 |
| P2 | CP-SAT Vertical Slice | C-001～C-011 + OBJ-001 闭环 |
| P3 | Planning Workspace | 版本、比较、审批、发布和导出 |
| P4 | Dynamic Replanning | 执行异常、事实保护、稳定性与 ChangeReport |
| P5 | Advanced Capabilities | 仅按证据逐项增加高级能力 |
| P6 | AI Duration Prediction | 核心稳定后的版本化预测接口 |
| P7 | Reality Calibration | 历史重放、现实差距与生产边界 |

Milestone 定义 outcome 和 exit gate，不等同 Sprint。只有当前 Phase 创建详细 Task Card；更新 `current_phase.md` 需要 Gate 的真实证据和用户确认。

P0 当前状态：TASK-P0-01～10 全部完成；[superseding audit](P0-exit-gate-audit-report.md) 的 Schema、Golden、Validator Rule Sheet、Scenario replay、Repository Build、CI 和 PROD_OPEN registration全部 `PASS`，P0 Gate=`READY`。用户于 2026-08-19 明确批准 phase transition后，P0转为 `completed`，历史失败/修复/provider evidence继续保留。

P1当前状态：[`P1 — Data & Snapshot`](P1-data-and-snapshot.md)为`completed`，TASK-P1-01～12全部`done`。[P1 audit](P1-exit-gate-audit-report.md)的271项回归、14/14 pipeline、全部machine/build/docs/provider证据均PASS；TASK-P1-12 implementation `a5d7e4a68dc12d48e36cb692500f59446f8097b4` / run `32326616525` / artifact `9391591718`已闭环，Gate=`READY`且无blocking gap。用户于2026-08-20明确批准transition。

P2当前状态：[`P2 — CP-SAT Vertical Slice`](P2-cp-sat-vertical-slice.md)为`active`。TASK-P2-00～05均已闭环为`done`；P2-03的ADR/dependency/backend、P2-04 formal Validator及P2-05 five-C-ID core Solver local/provider证据完整。用户于2026-08-21明确授权TASK-P2-06，该Task以`c55aa294977a6cafad85741f425d46cd36e9af1a`为Diff base并处于`in_progress`；P2-07～14仍为`planned`且未获启动授权。P2-14必须为最后的Exit Gate Audit，不得自动进入P3。

TASK-P2-03 implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的run `32346208046`、required job `96355386111`和artifact `9398128763`均success；P2 phase保持active，后续Task不自动启动。

TASK-P2-04 implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的run `32350068318`、required job `96367085099`与artifact `9399519368`均success；artifact formal report为6/6且Task report为38 paths/6 rows/0 issues，故Task=`done`。P2-05的启动来自用户新的明确授权，不是依赖完成后的自动过渡。

TASK-P2-05本地实现和治理验收均PASS：64 focused、360 full、core/formal各6/6、Task diff 49 paths/6 rows/0 issues及compose/build/immutable。Implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的run `32354050257` / job `96379299455` / artifact `9400957897`也精确PASS，故Task=`done`。TASK-P2-06的启动来自用户新的明确授权；其启动基线run `32354521904` / job `96380738933` / artifact `9401134902`精确绑定Diff base并成功，不会自动启动P2-07。
