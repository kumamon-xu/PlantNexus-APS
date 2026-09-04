---
doc_id: TASK-DEMO-10
title: One-command Delivery Runbook and Release Audit
status: in_progress
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-04
---

# TASK-DEMO-10 — One-command Delivery Runbook and Release Audit

Task family: demo-exclusive

Depends on: TASK-DEMO-08, TASK-DEMO-09

Start gate: 用户于 2026-09-04 明确要求正式关闭 TASK-DEMO-09、不复跑其机器报告并继续 D18。D17 参数与本地参考基准已冻结；原 TASK-DEMO-09 scope `FAIL` 报告继续作为审计事实保留，不作为 D18 的范围豁免。

Goal: 完成 D18 的可重复交付切片：提供从仓库根目录可调用的一键 doctor/start/stop/status/health/reset/smoke 控制面，默认安装锁定前端依赖、构建 production bundle、只在 loopback 启动后端与中文前端、持久化并安全核对进程身份；完成冷启动、固定 Showcase 重置、真实 Chromium 中文首屏、停止后同 runtime 重启恢复和既有中断恢复审计；形成中文演示人员 Runbook、版本化 release manifest 与 machine-readable release audit。

Non-goals: 不部署公网或 Production；不修改 root backend/frontend/schema、P8/P7 或正式 phase 文档；不自动批准或发布重排 DRAFT；不新增第三方服务、容器、安装器或操作系统服务；不把当前本地交付候选机冒充用户尚未指定的最终现场机；不把 D17 的用户 closure 授权解释为 D18 scope 或 release gate 豁免。

Inputs: D18 任务清单；D16 E2E/安全/恢复证据；D17 formal protocol、冻结 baseline、fixture 与中文报告；现有 Demo start composition、runtime path、session/reset/job API、production Vite preview 和 Playwright CLI 模式；仓库锁定的 Python/Node 依赖与 Demo-only boundary。

Diff base: a9109e905fbc051666fcd3bc43322ae2c53e619d

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 建立 TASK-DEMO-10 context manifest；实现无 secret 的 delivery controller 与 PowerShell/portable wrappers；doctor 核对 Python、uv、Node、npm、npx、锁文件、资产、正式 baseline/evidence、端口和 runtime 写权限；start 默认执行 `npm ci`、production build、loopback backend/preview，等待 readiness 后原子写 launcher state；state 保存 PID 与进程创建标记，stop 只终止精确匹配的任务自有进程树；health/status 对 stale state fail closed；reset 建立本地 HttpOnly session、提交固定 Showcase reset 并轮询 durable job；smoke 用 Playwright CLI 验证中文页面、Simulation 边界、固定计数和浏览器无错误；rehearsal 从空 runtime 完成冷启动→重置→浏览器 smoke→停止→同 runtime 重启恢复，并复核中断 job 原 identity 语义；release audit 从权威 JSON 复算版本、指纹、冻结参数、文档数字、源码清单、git 状态和外部共享差异；更新中文 Runbook、README、任务与实施状态。

Outputs: `demo/scripts/democtl.py`、`demo/demo.ps1`、`demo/demo.sh`、D18 Playwright smoke 与 delivery rehearsal/release audit 脚本及测试；`demo/docs/D18-DEMO-RUNBOOK.md`；`demo/release/cnc-demo-release-manifest.v1.json`；TASK-DEMO-10 context/evidence/machine reports；更新后的 Demo 中文文档。

Documentation impact: required

Documents to update: `demo/docs/README.md`、`demo/docs/TASKS.md`、`demo/docs/IMPLEMENTATION-STATUS.md`、`demo/docs/04-ux-and-demo-script.md`、`demo/docs/05-benchmark-and-acceptance.md`、本任务卡、D18 中文 Runbook。

Traceability updates: D18；Gate A～F；M4；one-command start/reset；cold start；restart recovery；target-machine smoke；release manifest；known limitations；Simulation-only release verdict。

Schema changes: formal schema none。Demo-local launcher state、delivery observation、release manifest 与 release audit 均使用严格版本字段、规范 JSON 和 SHA-256；不得写 session token、绝对 runtime 路径、SQL 或 traceback。

Migration: none。默认 named runtime 为 `cnc-showcase`；重置继续通过现有迁移和 active-run CAS，launcher 不直写业务数据库。

Dependency changes: none。使用 Python 标准库、仓库既有 uv/npm/Vite 和已批准 Playwright CLI；不修改 root lock，不提交 node_modules、dist、浏览器或运行时数据库。

ADR impact: none。

State-machine impact: none。launcher 只调用正式 Demo HTTP/API 和现有 runtime；reset/initial/replan 状态语义不变，DRAFT 不自动发布。

Error behavior: 缺依赖、版本不符、asset/baseline 指纹漂移、端口占用、runtime 不可写、已有未知 launcher、PID 创建标记不匹配、服务启动失败、health 非 ready、reset/job 失败、浏览器中文/Simulation/计数断言失败或 release source 漂移均 fail closed。失败必须保留安全错误码和任务自有日志；不得杀死未知进程、泄漏 token、删除未验证路径或把 partial start 写成成功。

Tests: delivery contract/unit tests；strict launcher state；runtime-id/path；dependency/version；port collision；process creation marker/PID reuse；atomic state；partial-start cleanup；idempotent start/stop；health stale state；session cookie不输出；reset polling/counts；Playwright中文 smoke；cold start/restart recovery；D16 interruption replay；release manifest/evidence fingerprints；docs/baseline一致性；shared-worktree external-diff reporting；全量 Demo Python/frontend/static/diff hygiene。

Test IDs: DEMO-DELIVERY-001～024, DEMO-DELIVERY-BROWSER-001～008, DEMO-RELEASE-001～016

Benchmark impact: 不修改 D17 baseline。D18 只记录 cold start、production build、service ready、reset 与首屏 smoke 的交付时延作为目标机/候选机 observation；它们不是 Solver SLA。环境签名变化必须显式报告并先跑 Smoke，不得覆盖 D17 原始样本。

Simulation scenarios: 默认 `showcase` / `CNC-DEMO-SHOWCASE`、seed `20260902`、132 单、610 工序、24 设备；重置只生成固定 synthetic data。D18 浏览器 smoke 不需要自动完成加急求解；完整加急与恢复语义复用并重放 D16/D17 权威链。

Acceptance commands: TASK-DEMO-10 context manifest；delivery unit/contract tests；`demo.ps1 doctor/start/health/reset/smoke/stop`；D18 cold-start/restart rehearsal；release audit；Python Demo regression、Ruff、Pyright；frontend ci/lint/typecheck/test/build；shell/PowerShell syntax or parser checks；Playwright CLI 中文 smoke；`git diff --check -- demo`；Demo release inventory与shared-worktree外部差异显式报告；TASK-DEMO-10 machine report。

Artifacts: `demo/build/validation/task-context-manifest-demo-10.json`、`delivery-observation-demo-10.json`、`release-audit-demo-10.json`、`task-machine-report-demo-10.json`；release manifest 位于 `demo/release/`；运行日志、PID state、SQLite、node_modules、dist 与 Playwright session 位于已忽略的 Demo 目录。

Provider evidence: local Demo-only delivery candidate。所有服务只绑定 `127.0.0.1`，浏览器只访问 loopback。若用户未确认当前主机就是最终现场机，则 `target_site_status=PENDING_FINAL_SITE_REPLAY`，D18 可以完成实现与本地候选机证据，但不能给出最终 `CNC Simulation Demo ready` 判定。

Completion conditions: 从新 checkout 的等价依赖状态可用一条命令安装/构建并启动；doctor、start、status、health、reset、smoke、stop 均 fail-closed 且中文输出；固定 Showcase 重置精确恢复 132/610/24 与 seed；真实 Chromium 显示中文/Simulation 并无控制台错误；停止只作用于 exact PID+creation marker，partial/stale state 不误杀；同 runtime 重启恢复 active run；中断恢复语义再次通过；release manifest 与 baseline/evidence/source/docs 指纹闭合；运行产物全部忽略；外部共享差异被隔离和显式报告；若最终现场机已确认则其 smoke PASS，否则发布状态保持 pending；不修改 demo 外文件，不改变 P7/P8。

Completion evidence: 本地候选机 `doctor` 通过 Python 3.12.13、Node 24.19.0、npm 12.0.2、uv/npx/git、locks、asset、D17 baseline/evidence 指纹、runtime 写权限和端口检查；delivery contract 单测 11 项通过。`delivery-observation-demo-10.json` 封存 17/17 checks：含 `npm ci` 与 production build 的 cold ready 约 10.735 秒、Showcase reset 约 4.718 秒、两次真实 Chromium `zh-CN / INITIALIZED` smoke（page/console/server error 均 0）、同 runtime restart ready 约 3.234 秒且 run identity 不变、安全 stop 删除 launcher state，以及 D16 `INTERRUPTED / PROCESS_INTERRUPTED → same job attempt 2 SUCCEEDED`。中文 Runbook 已建立；版本化 release manifest 和 audit 对 Demo-only inventory、locks、D16/D17/D18 evidence、冻结参数、外部共享差异与边界完成闭合。本地结论为 `LOCAL_CANDIDATE_VERIFIED`。TASK-DEMO-10 machine report 的 13 个命令与全部功能产物为 `PASS`，但 strict scope 因 5 个受保护根文档的共享工作区外部变化为 `FAIL / SCOPE_CHECK`；D18 没有范围豁免。最终现场机也未确认，`PENDING_FINAL_SITE_REPLAY`，故任务保持 `in_progress`。

Failure handling: 任一交付断言失败即保留 TASK-DEMO-10 `in_progress`；安全停止已确认的任务自有进程，保留消毒日志与失败报告。不得用旧截图、D17 wall time、开发服务器或手工启动步骤替代本次 production delivery rehearsal。

Explicitly excluded: Production、公网监听、真实客户数据、P7/P8、root 代码/schema/lock、自动发布 DRAFT、容器/服务安装、连续插单、manual cancel/retry、跨平台最终签名和未经确认的现场 ready 宣称。

Simulation assumptions: 当前 Windows 11 主机是具名 `LOCAL_DELIVERY_CANDIDATE`；Python 3.12、Node/npm/uv/npx 已安装；PowerShell 是主要演示入口，portable shell wrapper 只提供等价转发；端口 8765/4174 可用；最终现场机身份尚未由用户明确确认。

Rollback: 先用 task-owned launcher state 安全停止精确进程树；删除 TASK-DEMO-10 新增的 controller、wrappers、smoke/rehearsal/audit、release manifest、Runbook、证据和测试；保留 TASK-DEMO-09 已冻结的 D17 baseline、中文前端与全部既有 Demo 能力，不触碰 root、P7/P8 或共享工作区外部差异。
