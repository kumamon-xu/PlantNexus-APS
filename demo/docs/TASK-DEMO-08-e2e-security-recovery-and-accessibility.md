---
doc_id: TASK-DEMO-08
title: End-to-End Security Recovery and Accessibility Closure
status: complete
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-04
---

# TASK-DEMO-08 — End-to-End Security Recovery and Accessibility Closure

Task family: demo-exclusive

Depends on: TASK-DEMO-05, TASK-DEMO-06, TASK-DEMO-07

Start gate: 用户要求继续实施。TASK-DEMO-07 machine report 为 `PASS`，中文主故事已能从 current `PUBLISHED` 提交真实加急命令并恢复 v2 `DRAFT` 比较；D16 现在负责把分散的成功路径、失败路径、安全边界、重启恢复和可访问性证据收束为一个可重复验收闭环。

Goal: 完成 D16：从隔离的空 SQLite runtime 运行 reset→initial plan→activate→urgent→comparison 的真实服务与浏览器主线，并以可执行矩阵证明双击/幂等、刷新、服务重启、stale run/base、并发 reset、受控失败、Simulation 授权、scope、production binding、token/log 消毒、路径逃逸、键盘、焦点、ARIA、非颜色表达、reduced motion 和双宽度布局均符合 fail-closed 边界。

Non-goals: 本任务不执行 D17 的 warmup + 5 measured 正式性能基准或调优，不形成 p95、目标机容量或 SLA；不修改 root backend/frontend、正式 schema、求解器、Validator、publication 状态机或 P7；不实现自动发布 DRAFT、连续多次不同插单、manual cancel/retry 或生产授权。

Inputs: `demo/docs/04-ux-and-demo-script.md` 可访问性、失败恢复和完整故事章节；`demo/docs/05-benchmark-and-acceptance.md` Gate E/F 与测试矩阵；`demo/docs/TASKS.md` D16；TASK-DEMO-05/06/07 completion evidence；现有 Demo API、SQLite control/run store、job runner、安全 provider、启动入口、中文前端、测试和证据脚本。

Diff base: 9a8f2e556b4b0adfdef3f88e1d442f805e9d4628

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 建立 D16 context manifest；补统一的可执行 E2E/安全审计器与严格 evidence contract；用隔离 runtime 验证完整 HTTP/SQLite 主线和权威 lineage；补 concurrent reset、stale、interrupted restart、受控 reset failure、路径与授权负向矩阵；收紧本地启动参数与证据消毒；修复并测试 dialog focus trap/restore、错误字段关联、键盘和状态的非颜色表达；用 Playwright CLI 从空 runtime 走完整中文浏览器流程，覆盖刷新恢复、双击保护、键盘和 1440×900/1024×768；记录控制台、网络 mutation、DOM/a11y 和截图；把 D16 evidence 接入 machine validator 并更新状态文档。

Outputs: `TASK-DEMO-08` task/context/machine reports；D16 audit/evidence scripts；隔离 runtime 的 E2E/security/recovery/a11y evidence；必要的 `demo/backend/**`、`demo/frontend/**` 和测试修复；真实浏览器 observation 与截图；更新后的 Demo 中文文档。

Documentation impact: required

Documents to update: `demo/docs/README.md`、`demo/docs/TASKS.md`、`demo/docs/IMPLEMENTATION-STATUS.md`、`demo/docs/03-architecture-and-api.md`、`demo/docs/04-ux-and-demo-script.md`、`demo/docs/05-benchmark-and-acceptance.md`、本任务卡。

Traceability updates: D16；Gate E 完整展示/视觉子集；Gate F 全部恢复与安全条目；E2E、Concurrency、Security、Visual 和 Accessibility 测试矩阵；M3 退出条件。

Schema changes: formal schema none。新增证据 JSON 仅为 Demo-local machine evidence；所有消费者严格校验版本、task id、状态、断言、指纹和 synthetic/production 边界。

Migration: none。

Dependency changes: none expected。浏览器自动化使用已批准的 Playwright CLI wrapper；不把浏览器二进制、node_modules、runtime 或 trace 引入仓库。

ADR impact: none。

State-machine impact: none。服务重启后，尚未执行的 `QUEUED` job 以原 identity 精确续跑，遗留 `RUNNING/CANCELLING` job 明确标记为 `INTERRUPTED`；不得伪造成功、生成新 identity 或自动发布。失败 reset 必须保留原 active run；DRAFT 必须保持未发布。

Error behavior: 所有负向路径返回稳定 code/field/correlation，不暴露 token、SQL、路径、堆栈或原始异常；浏览器只显示中文安全文案。契约漂移停止展示；stale、并发和越权不产生 durable business write；中断与失败保留可解释恢复边界。

Tests: 完整空 runtime API/SQLite E2E；重复点击只形成一个命令；active-job mutex 与 concurrent reset；stale run/base；restart→INTERRUPTED；reset fault before switch；path escape/absolute runtime；wrong token/capability/scope/production binding；response/log/repository token scan；dialog focus trap/restore/Escape；字段错误 aria-describedby；skip link、landmark、heading、interactive accessible name、aria-pressed/live status、reduced motion；双宽度无横向滚动；刷新恢复同一 job/comparison；console 0 error/warning。

Test IDs: DEMO-E2E-001～012, DEMO-SEC-001～010, DEMO-RECOVERY-001～008, DEMO-A11Y-001～014, DEMO-VISUAL-001～004

Benchmark impact: 只记录本次端到端 wall time、每个 durable job 耗时、网络请求数、DOM 节点和响应规模，作为 D16 功能/恢复证据。不得升级为 D17 多样本性能结论。

Simulation scenarios: 主浏览器链使用 `CNC-DEMO-SHOWCASE`、seed 20260902、四条批准路线与固定 route 5 / quantity 5 / URGENT 样本；负向矩阵优先使用 Smoke 以控制回归耗时；全部是合成数据和 `Asia/Shanghai`。

Acceptance commands: TASK-DEMO-08 context manifest；D16 API/security audit evidence；真实 Playwright CLI 空 runtime E2E；D16 evidence assembler；frontend lint/typecheck/test/build；Python Demo regression、Ruff、Pyright；`git diff --check -- demo`；protected-root 与 demo-only scope；TASK-DEMO-08 machine report。

Artifacts: `demo/build/validation/task-context-manifest-demo-08.json`、`e2e-audit-demo-08.json`、`browser-e2e-observation-demo-08.json`、`e2e-evidence-demo-08.json`、`task-machine-report-demo-08.json`；截图放 `demo/build/validation/screenshots/`；临时 runtime、服务日志、Playwright session/trace 放忽略目录。

Provider evidence: local Demo-only。所有服务只绑定 `127.0.0.1`；浏览器只访问本机 Vite proxy/Demo API；不部署、不提交、不 push、不注册或恢复 P7。

Completion conditions: 从全新隔离 runtime 的中文页面一次完成初始化、初排、显式发布、加急和 DRAFT 比较；刷新不丢失 identity，重复交互不产生第二个 mutation；Gate F 每一条均有独立可执行 PASS；受控失败和重启不破坏 current run/publication；token、内部路径、SQL、堆栈不进入响应、日志或证据；dialog/表单/筛选/状态满足键盘、focus、ARIA 和非颜色表达；1440×900/1024×768 无页面级横向滚动；无预录 schedule fallback；全部截图只含合成数据；frontend/Python/evidence/scope/protected-root gates 全 PASS。

Completion evidence: D16 已完成。服务端增加安全具名 runtime 解析并继续固定 loopback；遗留 `RUNNING/CANCELLING` job 在重启时持久化为 `INTERRUPTED / PROCESS_INTERRUPTED`，reset、initial plan 与 urgent 均可在原 job/idempotency identity 上显式进入下一 attempt。中文前端保存已接受 job identity、同步阻止双击重入，并为重置/发布/加急确认提供共享的焦点环绕、Escape 和焦点还原；首错字段、tabpanel 与全部 ARIA 引用闭合。

独立 API/SQLite Smoke 审计 50/50 assertions `PASS`，覆盖完整命令链、exact replay/conflict、stale run/base、并发 reset、重启 attempt 2、切换前 reset failure、错误 token/capability/scope、非 loopback、Production binding、路径逃逸与 token 消毒。真实 Playwright CLI/Chromium 从空 Showcase runtime 只通过中文页面完成 reset→initial plan→activate→route 5 quantity 5 urgent→comparison；68/68 assertions、四次业务 mutation 各一次、刷新 0 重放、控制台 0 error/warning、八组关键文字 AA 对比度、reduced motion、1440×900/1024×768 0 页面溢出及 2/2 截图 `PASS`。该次结果为 `FEASIBLE + Validator PASS` 的 v2 `DRAFT`，5 `ADDED` / 23 `CHANGED` / 557 `UNCHANGED`，原 current `PUBLISHED` 不变。

汇总 `e2e-evidence-demo-08.json` 为 39/39 assertions `PASS`，输入 fingerprint、截图哈希和 24 个实现源文件 SHA-256 闭合；Python Demo regression 40 passed，前端 5 files / 36 tests、lint、typecheck、build、Ruff、Pyright、diff hygiene、protected-root 和 demo-only scope 由 `task-machine-report-demo-08.json` 验证。浏览器约 79.89 秒与 API Smoke 约 14.45 秒只是单次 synthetic 功能证据，不是 D17 warmup + 5、p95、目标机、Production capacity 或 SLA。

Failure handling: 任一断言、浏览器步骤、服务启动、截图、日志消毒、lineage、fingerprint 或 scope 检查失败则 D16 保持 in_progress；保留原始失败类别但不把 secret/raw exception 写入持久证据。自动清理临时服务和隔离 runtime；不得用旧 D15 截图或预录 schedule 替代本次失败。

Explicitly excluded: D17/D18、Production、真实客户数据、生产容量/SLA、root 代码或 schema、自动发布 DRAFT、连续插单、manual cancel/retry、外部网络服务和 P7。

Simulation assumptions: 本地 loopback、单进程单 worker、固定 seed、isolated runtime、same-origin HttpOnly session、浏览器 `zh-CN`、Showcase 主线、Smoke 负向矩阵；颜色仅作辅助，状态必须同时有文字/符号。

Rollback: 删除 TASK-DEMO-08 新增的审计器、证据、截图与测试，恢复其对 Demo 前后端和文档的可访问性/启动收紧；保留 TASK-DEMO-07 已完成的中文加急比较能力，不触碰 root、P7 或用户其他差异。
