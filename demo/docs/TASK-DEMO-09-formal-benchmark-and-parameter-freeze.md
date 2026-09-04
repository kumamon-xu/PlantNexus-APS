---
doc_id: TASK-DEMO-09
title: Formal Benchmark and Demo Parameter Freeze
status: in_progress
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-04
---

# TASK-DEMO-09 — Formal Benchmark and Demo Parameter Freeze

Task family: demo-exclusive

Depends on: TASK-DEMO-01, TASK-DEMO-08

Start gate: 用户要求继续实施。TASK-DEMO-08 已完成并提交，D16 的完整中文浏览器主线、安全、恢复和可访问性 machine report 为 `PASS`；D04 已证明 610/700 工序的单次 early feasibility，但 warmup + 5、独立进程 RSS、浏览器首屏、目标环境签名和不可变 baseline 仍未形成。

Goal: 完成 D17：在当前明确标识的本地演示参考环境中，按固定协议对 CNC-SMOKE、CNC-SHOWCASE、CNC-UPPER 运行 preflight、1 次 warmup 与 5 次 measured，形成原始样本、环境签名、可复算汇总、阈值判定和中文技术报告；冻结经证据支持的默认 Showcase profile、初排/重排 solve limits 与 scripted urgent fixture，同时保持 synthetic-only、Simulation-only、非生产容量和无 SLA 边界。

Non-goals: 本任务不执行 D18 的一键打包、现场 runbook 或发布审计；不修改 root backend/frontend、正式 schema、求解器/Validator/状态机、P7 或生产配置；不因基准结果反向放宽阈值、隐藏失败或自动批准/发布 DRAFT；不宣称跨硬件、跨 OR-Tools 版本或真实生产负载性能。

Inputs: `demo/docs/05-benchmark-and-acceptance.md` B1～B6、运行协议、指标和阈值；`demo/docs/04-ux-and-demo-script.md` 固定加急样本；`demo/docs/TASKS.md` D17；TASK-DEMO-01 early spike 与 TASK-DEMO-08 completion summary；root benchmark harness/performance gate 规范；现有 Demo benchmark、orchestration、presentation、API、浏览器和 machine-validation 代码。

Diff base: a9109e905fbc051666fcd3bc43322ae2c53e619d

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 建立 D17 context manifest；定义不可变 benchmark suite/sample/summary contracts 与 nearest-rank p95；用独立子进程测量每个样本的进程树 peak RSS、退出状态和原始阶段指标；复用正式 Demo reset→initial plan→activate→urgent→presentation 链而非旁路求解；按 preflight、warmup、5 measured 运行三档并隔离 runtime；用真实 Chromium/Playwright CLI 采集 Showcase 初排与比较首屏 warmup + 5；验证确定性、Validator、ChangeReport、状态/目标/gap/模型规模、SQLite/artifact/API/DOM 大小；只在失败有明确证据时做版本化调优；生成不可变 JSON baseline、环境文件、raw samples、中文 Markdown 技术报告与 evidence；冻结参数与 fixture；更新状态、验收和 README；接入 D17 machine report。

Outputs: `TASK-DEMO-09` task/context/machine reports；正式 benchmark suite/worker/summary/browser scripts 和测试；版本化 raw samples、environment、baseline/evidence JSON；中文技术报告；冻结的 Demo profile/solve limits/scripted urgent fixture 记录；更新后的 Demo 中文文档。

Documentation impact: required

Documents to update: `demo/docs/README.md`、`demo/docs/TASKS.md`、`demo/docs/IMPLEMENTATION-STATUS.md`、`demo/docs/04-ux-and-demo-script.md`、`demo/docs/05-benchmark-and-acceptance.md`、本任务卡、D17 中文基准报告。

Traceability updates: D17；B1～B6；Showcase 暂定性能门；Upper characterization；Benchmark 测试矩阵；M4 的 D17 子项。D18 和 Demo ready 保持开放。

Schema changes: formal schema none。新增 Demo-local benchmark/evidence JSON 使用显式版本、严格字段、样本角色、profile revision、环境指纹、source fingerprint 和 synthetic/production 边界。

Migration: none。每个 measured sample 使用新建隔离 SQLite runtime，结束后只清理任务自有临时目录；不可变 baseline 不依赖保留 runtime。

Dependency changes: none expected。RSS 使用操作系统/标准库可获得的进程指标或仓库已有依赖；浏览器使用已批准 Playwright CLI，不下载或提交浏览器/node_modules。

ADR impact: none。

State-machine impact: none。每个样本仍使用正式 READY_FOR_REVIEW→APPROVED→PUBLISHED 和 urgent→DRAFT 语义；current PUBLISHED 不被 DRAFT 替换。

Error behavior: 任一 measured sample 出现 UNKNOWN/INFEASIBLE/Validator FAIL、ChangeReport FAIL、进程异常、样本缺失、环境/输入漂移或统计不可复算即使 suite fail closed；原始失败样本必须保留并进入报告，不得以补跑成功静默替换。敏感 token、绝对 runtime 路径、SQL 和 traceback 不进入持久 baseline。

Tests: benchmark contract/unit tests；统计与 p95 边界；子进程/RSS sampler；preflight/warmup/measured 角色与样本数；profile/fixture/dataset fingerprint；B1～B6 stage completeness；状态/Validator/ChangeReport hard gate；determinism rules；threshold calculation；failed sample preservation；browser timing/DOM/network contract；isolated runtime cleanup；中文报告一致性；全量 Demo Python/frontend/scope/protected-root regression。

Test IDs: DEMO-BENCH-001～020, DEMO-BENCH-BROWSER-001～008, DEMO-BENCH-REPORT-001～010

Benchmark impact: 这是 D17 的权威 Demo-local synthetic benchmark。Showcase 5 个 measured 全部必须是 `OPTIMAL` 或 `FEASIBLE + Validator PASS`；Upper 记录 60/90 秒候选预算下的真实行为。p50/p95/max、RSS、状态与 gap 必须由 raw samples 可复算；不存在 first-feasible 指标时保持未采集而非推断。

Simulation scenarios: 三档均使用 seed 20260902、单 worker、approved assets、设备日历/维护、物料、执行事实和锁。固定 urgent fixture 为 `CNC-ROUTE-5`、quantity 5、`2026-09-09T18:00:00 Asia/Shanghai`、`URGENT`、中文说明；只有通过 5 次稳定性检查后才标记 frozen。

Acceptance commands: TASK-DEMO-09 context manifest；benchmark unit/contract tests；三档 formal suite；真实 Playwright CLI Showcase 首屏套件；D17 evidence assembler；Python Demo regression、Ruff、Pyright；frontend lint/typecheck/test/build；`git diff --check -- demo`；protected-root 与 demo-only scope；TASK-DEMO-09 machine report。

Artifacts: `demo/build/validation/task-context-manifest-demo-09.json`、`benchmark-evidence-demo-09.json`、`browser-benchmark-observation-demo-09.json`、`task-machine-report-demo-09.json`；版本化 baseline 与 raw samples 放 `demo/benchmarks/baselines/`；中文报告放 `demo/docs/`；临时 runtime、日志和 Playwright session 放忽略目录。

Provider evidence: local Demo-only reference environment。环境身份必须记录且不得泛化为用户尚未指定的最终现场机器；如当前机器不是最终现场机，D18 仍须在实际目标机 replay/smoke。所有服务仅绑定 `127.0.0.1`，不部署、不提交、不 push、不注册或恢复 P7。

Completion conditions: 三档均具备 preflight、warmup 与 5 个 measured 原始样本；Showcase 5/5 初排与加急结果满足 Solver/Validator 强制门，固定 fixture 同时包含 ADDED、CHANGED、UNCHANGED 且保护 completed/running/hard/freeze；B1～B6 指标、independent process-tree RSS、浏览器首屏和环境签名完整；所有统计可从 raw samples 独立复算；暂定阈值逐项 PASS/FAIL 且失败未被掩盖；Upper 700 工序无 OOM/损坏并有状态分布；profile、solve limits 与 fixture 只有在证据通过后冻结；报告明确 synthetic-only、当前参考环境、无生产容量/SLA；全部代码、测试、证据和文档只在 `demo/**`；D18 与 Demo ready 仍开放。

Completion evidence: 实现与正式证据完成，strict scope closure pending。三档各完成 1 次 preflight、1 次 warmup、5 次 measured，共 21 个独立后端进程 raw samples；Showcase 初排/重排端到端 p95 为 7.517/22.601 秒、进程树 RSS p95 277.3 MiB，7 项门槛全部 `PASS`，初排 5/5 `OPTIMAL`，重排 4 `OPTIMAL` + 1 已验证 `FEASIBLE`，Validator/ChangeReport 5/5 `PASS`。Upper 700 工序初排/重排 p95 为 12.181/32.014 秒且 5/5 `OPTIMAL`。真实中文 Chromium 封存 12 个首屏样本；基线/比较页 measured 首屏 p95 为 1,365.5/2,398.5 ms。`benchmark-evidence-demo-09.json` 对 21+12 样本、环境/源码 digest、统计、阈值和冻结参数的复算为 `PASS`；Python 44 tests、前端 5 files/36 tests、Ruff、Pyright、lint、typecheck、build、脚本语法和 diff hygiene 均通过。

`task-machine-report-demo-09.json` 当前为 `FAIL`，唯一失败类别是 strict scope：共享工作区中观测到 18 个非 `demo` 文档差异，其中 5 个既有 protected 文件 hash 也已被外部工作改变；3/3 benchmark checks、10/10 commands、task context、formal benchmark evidence 和 text hygiene 全部 `PASS`。本任务未修改或回滚这些外部差异，也未放宽通用范围门；待其所有者处理后必须重新生成 context 并复跑 machine report，只有报告整体 `PASS` 才将本卡改为 `complete`。

Failure handling: suite 失败时保留原始 JSON 和原因，将 TASK 保持 `in_progress`；仅根据模型大小、日历碎片、候选密度、六轮预算、查询或渲染证据提出最小优化，并升级 profile/baseline version 后全量重跑。不得删除失败样本、用单次最佳值代替分布、静默降低规模或把 warmup 算入 measured。

Explicitly excluded: D18、Production、真实客户数据、生产容量/SLA、root 代码/schema、P7、自动发布 DRAFT、连续插单、manual cancel/retry、外部网络服务和跨环境通用性能承诺。

Simulation assumptions: 当前主机作为具名“本地演示参考环境”而非未经确认的最终现场机；Windows 11、loopback、单服务 worker、固定 seed、受限 solve wall time、系统调度可能导致 FEASIBLE 指纹变化；浏览器使用本机 Chromium；所有业务数据为 synthetic。

Rollback: 删除 TASK-DEMO-09 新增的 suite、baseline、报告、证据和测试，恢复本任务对 Demo profile/fixture/文档的冻结标记；保留 TASK-DEMO-08 已完成的中文主线、安全、恢复与可访问性能力，不触碰 root、P7 或用户其他差异。
