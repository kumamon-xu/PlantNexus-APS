# CNC Demo 当前实施状态

状态日期：2026-09-02  
最新完成任务：TASK-DEMO-03  
任务族：demo-exclusive（不注册 P7，不改变根项目阶段）  
结论：固定数据、初排规模门、durable runtime、显式 current `PUBLISHED` 基线，以及加急事实到 v2 `DRAFT` 的动态重排后端闭环均 `PASS`；D11 展示模型、剩余查询 API 和前端仍开放

## 1. 已交付闭环

- TASK-DEMO-01：严格行业资产、固定 CNC 生成器、标准 import/validation/expansion/Snapshot/Problem v2 链、Solver/Validator benchmark 和契约 probes。
- TASK-DEMO-02：Demo-only `control.db`、per-run SQLite、根 Alembic `head`、Demo 辅助 migration、run/job/stage/idempotency/artifact/command audit persistence。
- TASK-DEMO-03：严格 `UrgentOrderCommand v1`、四个批准路线模板的确定性展开、additive-only Standard Import candidate、精确 `URGENT_DEMAND_RECEIVED`、event projection/checkpoint、新 Snapshot/ReplanRequest、真实六轮 CP-SAT 重排、fresh Validator、before/after KPI 和 ChangeReport。
- Reset：新数据库迁移、自检后以 active-run CAS 切换；失败不替换旧 run；仅清理路径验证后的过期非活动 run，默认保留最近 3 个。
- Job：单 worker、最大并发 1、QUEUED 可恢复、遗留 RUNNING 标记 INTERRUPTED、同 key 精确重放、不同输入冲突、stale run 与 active-job mutex。
- 授权：本地 HttpOnly cookie session、SimulationLocalAuthorizationProvider、capability/scope 检查和拒绝审计；错 token/capability/scope 与 Production 均 fail closed。
- 初排：正式 `GlobalCpSatStrategy`、批准的 Simulation policy/limits、再次独立 Validator、KPI，以及 `ValidatedSolutionToScheduleVersionService.create_reviewable`。
- 基线：显式 `ACTIVATE_SIMULATION_BASELINE` 确认，正式 APPROVE/PUBLISH 服务，APPROVED 后发布失败可沿同一身份恢复，current Publication 精确读回。
- 加急写前校验：active run、expected run/current base、`PUBLISHED` 状态、horizon、时区、数量、模板与 candidate 都在正式 command-side 写入前 fail closed。
- 动态重排：同 key formal replay 不重复 event/checkpoint/request/attempt/result/version；新版本固定为 v2 `DRAFT`，current `PUBLISHED` 的 ID 与 fingerprint 不变。
- HTTP：独立 create_app 组合根与 `/api/demo/v1` 的 session、bootstrap、state、resets、initial-plans、baseline-activations、urgent-orders、jobs；默认产品 app.py 不变。
- P4 装配：ExecutionEvent、projection checkpoint、ReplanRequest/attempt/result 与 audit 均接真实 repository；Demo manual cancel/retry 仍明确 `SERVICE_UNAVAILABLE`。

所有新增和修改仍限定在 `demo/**`。进入 Demo 实现前已有的 10 个非 Demo 工作区文件继续由 SHA-256 基线保护。

## 2. Showcase 端到端证据

证据：`demo/build/validation/runtime-evidence-demo-02.json`。

| 项目 | 实测结果 |
|---|---|
| 场景 | CNC-DEMO-SHOWCASE / seed 20260902 |
| 输入规模 | 132 单 / 610 总工序 / 580 active / 24 设备 |
| active resource options | 1,253 |
| Reset job | SUCCEEDED / 10 stages / exact replay PASS |
| Initial-plan job | SUCCEEDED / 10 stages / exact replay PASS |
| Solver | OPTIMAL（仅限本 synthetic instance） |
| 独立 Validator | PASS / 0 hard violations |
| 规范 artifact | 7 类：Quality、Snapshot、Problem、Solution、SolverReport、Validation、KPI |
| 初始版本 | READY_FOR_REVIEW / state revision 1 |
| 激活后版本 | PUBLISHED / state revision 3 |
| Publication current | version id 与 content fingerprint 精确一致 |
| Activation replay | PASS |
| 最终故事状态 | BASELINE_PUBLISHED |

本次完整 harness 耗时约为 reset 2.74 秒、initial-plan 6.22 秒、activation 0.19 秒；其中 initial-plan 包含重新生成、标准 ingress、求解、Validator、KPI、artifact 和版本事务，不能与 TASK-DEMO-01 单独 Solver total 直接等同。

## 3. Showcase 加急动态重排证据

证据：`demo/build/validation/runtime-evidence-demo-03.json`。

| 项目 | 实测结果 |
|---|---|
| 基线与插单 | 132 个初始订单、580 个基线 active assignments；新增 1 个 demand、5 道工序 |
| 正式事件 | 1 条 `URGENT_DEMAND_RECEIVED` / exact schema PASS / `route_template_id` 与 note 不在 payload |
| Projection | 1 checkpoint；12 running、4 explicit hard、8 freeze-derived hard、8 soft 均有证据 |
| 历史 completed | 基线前 30 道 completed Snapshot tuples byte-for-byte 保留 |
| Replan Solver | FEASIBLE（不称为最优） |
| 独立 Validator | PASS |
| 新版本 | schedule-version.v2 `DRAFT` |
| current Publication | 原 PUBLISHED version id/fingerprint 不变 |
| ChangeReport universe | 585 = 5 ADDED + 23 CHANGED + 557 UNCHANGED |
| 稳定性 | 580 个可比较既有工序中 557 未变化；2 次设备变化、3 次软锁违反 |
| Durable lineage | event/checkpoint/request/request-event/attempt/result 各 1，schedule versions 共 2 |
| Formal replay | exact replay PASS；未增加第二套 lineage |
| Urgent job | SUCCEEDED / 10 个真实阶段 / 约 24.16 秒 |
| 最终故事状态 | DRAFT_COMPARISON_READY |

本次 urgent job 包含标准导入、event append、projection、request、求解、fresh Validator、KPI、ChangeReport、事务提交与 artifact。它是当前开发机上的单次 synthetic early evidence，不是 warmup + 5、p95、目标机基线、生产容量或 SLA。

## 4. 固定数据与早期规模门

Showcase 固定为 132 个订单、610 道工序、30 已完成、12 正在加工、568 未开始、24 台设备、1,311 个 source resource options、96/29/7 普通/重点/加急订单、18 个物料延迟订单、4 个硬锁、8 个软锁、10 天 horizon、300 秒 tick。

TASK-DEMO-01 当前开发机单次结果仍为：Showcase 20 秒预算下 solve 2.427 秒、Solver total 2.924 秒、`OPTIMAL`、Validator `PASS`；Upper 700/665 工序在 30 秒预算下 solve 6.304 秒、total 6.947 秒、`OPTIMAL`、Validator `PASS`。它们不是 warmup + 5、RSS、目标机或 Production SLA 证据。

## 5. 验证状态

- `uv run pytest demo/tests -q`：31 passed。
- `uv run ruff check demo/backend demo/scripts demo/tests`：PASS。
- `uv run pyright -p demo/pyrightconfig.json`：0 errors。
- `git diff --check -- demo`：PASS。
- Demo contract probes：5/5 PASS。
- Showcase TASK-DEMO-03 runtime evidence：PASS。
- 根受保护文件 hash 与 Demo-only scope：由 TASK-DEMO-03 machine report 复核。

新增 TASK-DEMO-03 测试覆盖 additive-only candidate 与旧记录规范字节不变、严格命令/DST gap/DST overlap/offset/horizon、事件字段隔离、stale base 写前失败、真实 replan、formal exact replay、lineage 单例、completed/running/hard/freeze 保留、ChangeReport universe、v2 `DRAFT`、current Publication 不变，以及 HTTP urgent job/auth 主流程。

## 6. 当前边界与后续工作

- 当前批准的数据资产只有 `CNC-ROUTE-3`～`CNC-ROUTE-6` 四个路线模板；前端应据资产生成四张路线卡，不宣称已有六条路线。
- 当前 D09/D10 切片允许每个 deterministic run 提交一个不同的加急事件，并支持该命令精确重放；第二个不同插单在同一 run 中以 `BASELINE_STATE_CONFLICT` fail closed。多次连续插单需要先明确 DRAFT 取舍或新 current 基线的链式语义。
- 根 `project_effective_locks` 会把 Snapshot 中基线前的历史 completed 事实带入 projection，而版本比较 universe 只包含基线 active assignments。Demo 不改根实现、不删除历史事实；它保留 Snapshot anchors 原字节，并在单 worker、单次服务调用范围内把 effective-lock 的 completed comparison view 收窄为 base→new 实际移除集合。该兼容 adapter 是显式技术边界，未来应由正式 projector injection 或统一 universe 语义替代。
- D11 与 D12 剩余项：v1/v2 统一 presentation DTO，以及 factory、versions、comparisons 等只读查询。
- D13～D16：故事首页、甘特图/负荷、加急表单与比较、浏览器 E2E 和可访问性。
- D04/D17 剩余证据：B4 warmup + 5 measured、独立进程 RSS、目标演示机和 immutable performance baseline。
- Demo manual cancel/retry 仍保持 fail closed；本切片没有把它包装为可用功能。

下一实施切片应是 Demo 专属 D11，并补齐 D12 剩余的展示查询 API。DRAFT 仍不可自动批准、发布或替换 current baseline。

## 7. 可复现命令

```powershell
uv run pytest demo/tests -q
uv run ruff check demo/backend demo/scripts demo/tests
uv run pyright -p demo/pyrightconfig.json
uv run python demo/scripts/run_replan_evidence.py --report demo/build/validation/runtime-evidence-demo-03.json
uv run python demo/scripts/task_context_manifest.py --task-id TASK-DEMO-03 --report demo/build/validation/task-context-manifest-demo-03.json
uv run python demo/scripts/validate_demo.py --task-id TASK-DEMO-03 --context demo/build/validation/task-context-manifest-demo-03.json --report demo/build/validation/task-machine-report-demo-03.json
uv run python demo/scripts/start_demo.py
```

`OPTIMAL` 只适用于对应 synthetic instance；`FEASIBLE` 只有在独立 Validator `PASS` 时可展示，且不得称为最优。
