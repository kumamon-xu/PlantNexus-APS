---
doc_id: D18-DEMO-RUNBOOK
title: CNC 仿真 Demo 交付与现场运行手册
status: local_candidate_verified
spec_version: cnc-demo-runbook.v1
last_reviewed: 2026-09-04
---

# CNC 仿真 Demo 交付与现场运行手册

本手册面向演示人员和现场支持人员。当前包是 `LOCAL_DELIVERY_CANDIDATE`：本地候选机已通过冷启动、production build、固定数据重置、真实 Chromium 中文首屏、停止后同 runtime 恢复和 D16 中断任务恢复复核。最终现场机尚未由用户确认，因此发布状态必须保持 `PENDING_FINAL_SITE_REPLAY`；本机结果不构成最终现场放行，更不构成生产容量或 SLA。

## 1. 固定交付口径

- 行业：精密机械零部件 / CNC 机加工车间。
- 默认场景：`CNC-DEMO-SHOWCASE`，132 单 / 610 道工序 / 24 台设备，3 个车间，10 天排程周期。
- 固定 seed：`20260902`。
- 初始排产 / 加急重排求解上限：20 / 30 秒。
- 固定加急样本：`CNC-ROUTE-5`、数量 5、北京时间 `2026-09-09 18:00`、`URGENT`。
- 后端 / 前端：只绑定 `127.0.0.1:8765` / `127.0.0.1:4174`。
- 数据：全部为合成数据；无生产授权；加急重排结果保持 `DRAFT`，不会自动替换当前已发布的仿真基线。

## 2. 现场前置条件

在仓库根目录运行命令。Windows 是本次已验证的主要交付路径；portable shell 只是等价转发入口。

1. Python 必须由 `uv` 解析为 3.12；Node.js 不低于 24.19.0；npm 不低于 11.17.0。
2. 端口 8765、4174 必须空闲；不要改成公网地址或 `0.0.0.0`。
3. 首次运行需要能从锁文件安装前端依赖，且 Playwright CLI / Chromium 必须已经缓存或可下载安装。离线现场应提前完成缓存与 smoke。
4. 不得修改 `demo/benchmarks/formal-protocol.v1.json`、冻结 baseline、Showcase 数据资产或两个 lockfile。
5. 演示前关闭可能占用上述端口的旧终端或服务，但不要手工结束不明 PID。

## 3. 五分钟快速路径

以下命令都从仓库根目录执行，并返回中文 JSON。任一步 `status=FAIL` 即停止继续演示。

```powershell
.\demo\demo.ps1 doctor
.\demo\demo.ps1 start
.\demo\demo.ps1 health
.\demo\demo.ps1 reset
.\demo\demo.ps1 smoke
.\demo\demo.ps1 status
```

浏览器打开 `http://127.0.0.1:4174/demo/`。演示结束后执行：

```powershell
.\demo\demo.ps1 stop
```

需要现场看到 Chromium 时可用：

```powershell
.\demo\demo.ps1 smoke --headed
```

portable shell 的等价调用是 `./demo/demo.sh doctor`、`./demo/demo.sh start`、`./demo/demo.sh reset`、`./demo/demo.sh smoke` 和 `./demo/demo.sh stop`。

`start` 默认执行锁定的 `npm ci`、TypeScript 检查与 Vite production build，然后启动回环后端和 production preview。`--skip-install`、`--skip-build` 只用于同一已验证 checkout 的受控重启，不用于首次交付或现场放行。

## 4. D18 现场运行

### 4.1 开场前

1. 执行 `doctor`，确认依赖、锁文件、D17 参数冻结及证据指纹、资产、写权限和两个端口全部通过。
2. 执行 `start`，等待 `status=RUNNING`；再执行 `health`，确认后端 live/ready、SQLite runtime 和 `zh-CN` production 页面可用。
3. 执行 `reset`，确认 `profile_id=CNC-DEMO-SHOWCASE`、seed `20260902`、计数精确为 132 / 610 / 24，且 `simulation_only=true`、`production_authority=false`。
4. 执行 `smoke`，确认真实 Chromium 返回 `story_state=INITIALIZED`、中文环境标记、固定数据及浏览器 0 page/console/server error。

### 4.2 正式讲解

1. 首页先指出“仿真环境 · 非生产”、单工厂三车间和固定种子。
2. 点击“开始自动排产”，等待真实 Job 阶段结束；只在 Validator `PASS` 后展示结果。`OPTIMAL` 可称“本实例已证明最优”，`FEASIBLE` 只能称“限时内找到并经独立 Validator 验证的可行方案”。
3. 显式确认“设为仿真基线”；强调它只发布到仿真内部目标。
4. 点击“插入加急订单”，使用冻结的路线、数量、交期和优先级；确认后等待自动重排。
5. 展示前后甘特、移动/未变化工序、设备变化、开始时间偏移、交期和稳定性、ChangeReport 与 Validator。
6. 强调新版本为未发布 `DRAFT`，current `PUBLISHED` 仿真基线保持不变。

### 4.3 结束后

执行 `stop`。停止逻辑只处理 launcher state 中 PID 与操作系统创建标记同时匹配的两个任务自有进程树；成功后删除 launcher state，但保留具名 runtime，以便同一 checkout 下再次启动恢复故事状态。

## 5. 状态、日志与恢复

| 现象 | 行为 | 现场处理 |
|---|---|---|
| `STOPPED` | 没有有效 launcher state | 可执行 `start` |
| `RUNNING` | 前后端 PID 与创建标记都匹配 | 执行 `health` 后继续 |
| `STALE` | 一个进程已停或身份不一致 | 先执行 `stop`；不要再次 `start` |
| `DELIVERY_PORT_IN_USE` | 固定端口被占用 | 找到明确归属的占用程序并正常关闭；不得改公网监听 |
| `DELIVERY_PROCESS_IDENTITY_MISMATCH` | PID 已复用或状态被篡改 | 系统已拒绝误杀；保留 state 和日志，交由维护人员核对 |
| `DELIVERY_SETUP_COMMAND_FAILED` | `npm ci` 或 production build 失败 | 查看本次 `setup.log`，修复依赖/缓存后重新 `start` |
| `DELIVERY_SERVICE_START_TIMEOUT` | 服务未按时就绪 | 检查本次 backend/frontend 日志，确认端口与依赖 |
| `DELIVERY_RESET_*` | reset、Job 或固定计数失败 | 不进入正式讲解；保留旧 active run，排查后重试 reset |
| `D18_BROWSER_ASSERTION:*` | 中文、Simulation、计数或浏览器错误断言失败 | 不使用截图替代；修复后重新跑真实 `smoke` |

任务自有日志位于 `demo/runtime/launcher/logs/<instance>/`，包含 `setup.log`、`backend.log`、`frontend.log`。launcher state 位于 `demo/runtime/launcher/state.json`。这些路径已忽略，不进入 release manifest，也不应复制会话文件。命令输出、证据和日志不得包含 Cookie 值、Bearer token、SQL、traceback 或绝对 runtime 数据路径。

进程部分启动失败时，控制器会清理它刚创建的确切子进程且不写成功 state；未知 PID 或创建标记不匹配时则 fail closed。不要删除 state 来绕过身份校验，也不要使用通配符批量结束 Python、Node 或浏览器进程。

同 runtime 的受控恢复顺序为 `stop → start --skip-install --skip-build → health → smoke`。D18 本地演练确认 `INITIALIZED` run identity 在停止与重启后保持一致；D16 恢复审计同时确认遗留执行任务变为 `INTERRUPTED / PROCESS_INTERRUPTED`，并以原 job identity、attempt 2 重试成功。

## 6. 发布清单与审计

交付前只读复核：

```powershell
uv run python demo/scripts/run_delivery_rehearsal.py --verify-only
uv run python demo/scripts/run_release_audit.py --verify-only
```

版本化清单位于 `demo/release/cnc-demo-release-manifest.v1.json`，发布审计位于 `demo/build/validation/release-audit-demo-10.json`。清单记录 Demo-only 文件 SHA-256、锁文件身份、固定场景、D16/D17/D18 证据和边界；runtime、node_modules、dist、Playwright session 与临时 benchmark 不进入清单。

D17 原 TASK-DEMO-09 machine report 因共享工作区外部差异保持 `FAIL / SCOPE_CHECK`，但功能项为 `PASS`。用户已明确授权不复跑并正式关闭 D17；D18 发布审计必须原样保留该事实，不能把它改写为机器 PASS，也不能将其 closure 授权复用为 D18 豁免。

## 7. 最终现场放行清单

只有用户确认的最终现场机完成以下项目，状态才可从 `PENDING_FINAL_SITE_REPLAY` 变更为最终 ready：

- 在目标 checkout 上验证 release manifest 与两个 lockfile 指纹；
- `doctor` 全部通过，端口与 runtime 权限满足；
- 默认 `start` 完成真实依赖安装和 production build；
- `reset` 精确恢复 Showcase 132 / 610 / 24 与 seed；
- 真实目标机 Chromium `smoke` 通过且中文、Simulation 边界、console/page/server error 均为 0；
- 记录目标机环境签名和交付时延，并与 D17 本地参考机做显式差异说明；
- `stop` 成功且没有遗留监听进程；
- 提交后的源状态与最终 release audit 闭合。

当前本地候选机实测：含 `npm ci` 与 production build 的 cold ready 约 10.735 秒，固定 Showcase reset 约 4.718 秒，首轮 Chromium smoke 约 7.953 秒；同 runtime 无重复安装/构建的 restart ready 约 3.234 秒，重启后 Chromium smoke 约 7.625 秒，整次 D18 observation 约 59.360 秒。这些是单次交付可操作性观察，不是 D17 Solver p95，也不构成生产容量或 SLA。

## 8. 已知限制

- 当前没有离线安装包、容器或系统服务；首次 `npm ci` / Playwright CLI 可能依赖网络或预热缓存。
- Windows PowerShell 是已完成正式本地演练的入口；portable shell 只通过语法和等价转发检查，尚未形成跨平台目标机证据。
- 固定使用 8765/4174；没有动态端口或公网部署能力。
- 只支持 synthetic Simulation，不能连接生产数据库、生产授权或真实客户数据。
- 新加急方案不自动批准/发布；同一 run 的连续不同插单、manual cancel/retry 仍不在本切片范围。
- D17 本地参考机结果不能直接外推最终现场机，更不能外推 Production。
