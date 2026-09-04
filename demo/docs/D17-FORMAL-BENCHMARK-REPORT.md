---
doc_id: DEMO-D17-FORMAL-BENCHMARK-REPORT
title: CNC Demo 正式专项基准与参数冻结报告
status: accepted
baseline_version: cnc-demo-formal-benchmark-baseline.v1
profile_set_version: cnc-demo-benchmark-profiles.v2
last_reviewed: 2026-09-04
---

# CNC Demo 正式专项基准与参数冻结报告

## 1. 结论

D17 在本地演示参考机上通过。SMOKE、SHOWCASE、UPPER 三档各完成 1 次 preflight、1 次 warmup 和 5 次 measured，共封存 21 个独立后端进程样本；真实 Chromium 另完成已发布基线与重排比较页各 1 次 warmup、5 次 measured，共 12 个首屏样本。33 个样本、环境签名、源码 SHA-256、汇总统计和阈值均已复算并封存。

默认现场档冻结为 `CNC-DEMO-SHOWCASE`：132 单、610 总工序、24 台设备，初排求解上限 20 秒、加急重排上限 30 秒。Showcase 的 5 次初排均为 `OPTIMAL + Validator PASS`；5 次加急重排为 4 次 `OPTIMAL`、1 次 `FEASIBLE`，且全部为 `Validator PASS + ChangeReport PASS`。因此页面必须继续区分“已证明最优”和“已找到并验证可行”。

Showcase 的正式结果为：初排端到端 p95 7.517 秒，重排端到端 p95 22.601 秒，非求解阶段 p95 5.782 秒，服务端展示读取 p95 0.839 秒，job/state 读取 p95 0.013 秒，后端进程树 RSS p95 277.3 MiB。7 项 Demo 发布目标全部通过，未调整阈值、未缩小规模。

UPPER 的 700 工序表征也通过：初排 p95 12.181 秒、重排 p95 32.014 秒、RSS p95 292.8 MiB，5/5 measured 均为 `OPTIMAL + Validator PASS + ChangeReport PASS`。UPPER 仍只是离线上界表征，不是默认现场 profile。

这些结论只适用于固定合成数据、当前软件版本和当前参考机，不建立真实生产容量、跨环境性能或 SLA。最终现场机复跑和一键交付审计仍属于 D18；Demo 尚不能标记为 ready。

## 2. 冻结项

| 项目 | 冻结值 |
|---|---|
| profile set | `cnc-demo-benchmark-profiles.v2` |
| 默认 profile | `showcase` / `CNC-DEMO-SHOWCASE` |
| 固定 seed | `20260902` |
| 求解 worker | 1 |
| Smoke 初排 / 重排上限 | 5 / 10 秒 |
| Showcase 初排 / 重排上限 | 20 / 30 秒 |
| Upper 初排 / 重排上限 | 60 / 90 秒 |
| 加急 fixture | `CNC-DEMO-URGENT-FIXTURE-001` / `1.0.0` |
| 加急输入 | `CNC-ROUTE-5`，5 件，`2026-09-09T18:00:00 Asia/Shanghai`，`URGENT` |
| 加急备注 | `Showcase 固定加急精密套筒` |

冻结表示 D18 应按这些参数重放，而不是表示参数适用于生产。后续任何规模、求解上限、fixture 或统计口径变化，都必须升级 profile/protocol/baseline 版本并重新完成全量样本。

## 3. 测量方法

每个后端样本都在新建临时 runtime 和独立 Python 进程中执行正式 Demo 链：B1 reset/import、B2 initial plan、B3 显式基线激活、B4 固定加急重排、B5 Factory/Schedule/Comparison 读取、B6 `BEFORE_SWITCH` 受控 reset 失败恢复。没有直接调用简化求解入口，也没有把 warmup 纳入统计。

父进程每 20 ms 枚举 worker 进程树并累计 Windows Working Set；这避免把 `.venv` 启动器约 5 MiB 的壳进程误当成后端 RSS。每个样本结束后删除隔离 runtime，只保留去路径、去 token 的规范 JSON。

p50 为普通中位数，p95 使用 nearest-rank。每档只有 5 个 measured，因此 p95 等于该组最大值；报告同时保留 raw、p50、p95 和 max，不把小样本 p95 包装为统计承诺。求解器未提供本链可可靠采集的 first-feasible callback，故该指标固定为 `NOT_REPORTED_NO_RELIABLE_CALLBACK`，不做推断。

浏览器使用 Vite production build/preview、loopback API、真实 Chromium、1440×900 视口。已发布基线和 `DRAFT_COMPARISON_READY` 两个状态各先 warmup 一次，再完整 reload 五次；就绪时间以 navigation 起点到中文排程摘要及相应比较列表可见、字体 ready 为止。每个样本同时记录 Navigation Timing、Resource Timing、API 状态、响应体字节和 DOM 大小。协议没有为浏览器首屏设置数值发布门槛，这些数值只作 D18 现场对照。

## 4. 参考环境

| 项目 | 值 |
|---|---|
| 环境角色 | `LOCAL_DEMO_REFERENCE_MACHINE` |
| 操作系统 | Windows 11，build `10.0.26200`，AMD64 |
| CPU | Intel Core i9-13980HX，24 物理核 / 32 逻辑核 |
| 物理内存 | 63.6 GiB |
| 电源方案 | Turbo（环境文件同时封存 scheme GUID） |
| Python / OR-Tools | 3.12.13 / 9.15.6755 |
| Node / npm | v24.19.0 / 12.0.2 |
| Chromium / Playwright CLI | 152.0.7977.77 / 0.1.19 |
| Git 基点 | `a9109e905fbc051666fcd3bc43322ae2c53e619d` |
| 目标现场确认 | `PENDING_D18_SITE_REPLAY` |

正式环境文件为 `environment.json`；其环境指纹和被测源码 SHA-256 由 evidence assembler 重新验证。基准执行期间没有并发运行其他项目校验负载。

## 5. 后端结果

### 5.1 端到端与 RSS

| Profile | 初排 p50 / p95 / max（秒） | 重排 p50 / p95 / max（秒） | RSS p50 / p95 / max（MiB） | 展示 API p50 / p95 / max（秒） |
|---|---:|---:|---:|---:|
| Smoke（108 工序） | 0.969 / 2.076 / 2.076 | 4.437 / 5.115 / 5.115 | 194.0 / 194.3 / 194.3 | 0.143 / 0.253 / 0.253 |
| Showcase（610 工序） | 6.051 / 7.517 / 7.517 | 22.309 / 22.601 / 22.601 | 272.5 / 277.3 / 277.3 | 0.769 / 0.839 / 0.839 |
| Upper（700 工序） | 10.394 / 12.181 / 12.181 | 28.884 / 32.014 / 32.014 | 291.8 / 292.8 / 292.8 | 0.900 / 0.926 / 0.926 |

### 5.2 Showcase 发布目标

| 检查 | 实测 | 上限/要求 | 结果 |
|---|---:|---:|---|
| 初排端到端 p95 | 7.517 秒 | 30 秒 | PASS |
| 加急重排端到端 p95 | 22.601 秒 | 45 秒 | PASS |
| 初排/重排非求解阶段 p95 最大值 | 5.782 秒 | 8 秒 | PASS |
| 展示读取 p95 | 0.839 秒 | 1.5 秒 | PASS |
| job/state 读取 p95 | 0.013 秒 | 0.25 秒 | PASS |
| 后端进程树 RSS p95 | 277.3 MiB | 2 GiB | PASS |
| Validator + ChangeReport | 5/5 | 5/5 | PASS |

这些阈值的分类是 `DEMO_RELEASE_TARGET_NOT_PRODUCTION_SLA`。

### 5.3 状态、模型与 gap

| Profile | 初排状态 | 重排状态 | 初排模型（变量 / 约束 / optional intervals） | 重排模型范围 | 已记录 relative gap |
|---|---|---|---:|---:|---:|
| Smoke | 5 OPTIMAL | 5 OPTIMAL | 462 / 923 / 209 | 1,107～1,108 / 1,905～1,910 / 216～217 | 0.0 |
| Showcase | 5 OPTIMAL | 4 OPTIMAL + 1 FEASIBLE | 2,678 / 4,984 / 1,253 | 6,217～6,219 / 10,368～10,376 / 1,262～1,264 | 0.0 |
| Upper | 5 OPTIMAL | 5 OPTIMAL | 3,066 / 5,738 / 1,435 | 7,121～7,123 / 11,901～11,907 / 1,442～1,444 | 0.0 |

表中的 relative gap 是报告所选第一目标阶段的 objective/bound gap；Showcase 有一个多阶段重排的最终总状态仍为 `FEASIBLE`，因此不能根据该阶段的 0.0 gap 把它改写为“已证明最优”。所有候选均通过独立 Validator。

Showcase 的固定加急样本在 5 次 measured 中均新增 5 道工序；既有工序移动 22～23 道，保持不变 557～558 道。30 个已完成、12 个运行中、4 个显式硬锁和 8 个冻结派生硬锁均保持，current `PUBLISHED` 始终未被 `DRAFT` 替换。Upper 对应为新增 5、移动 29～30、保持不变 635～636。

## 6. 浏览器结果

| 页面状态 | 就绪 p50 / p95 / max（ms） | 单次最大 API p95（ms） | DOM p50（节点） |
|---|---:|---:|---:|
| 已发布基线排程 | 1,348.2 / 1,365.5 / 1,365.5 | 369.8 | 1,176 |
| 加急重排比较 | 2,391.9 / 2,398.5 / 2,398.5 | 1,561.3 | 1,843 |

12/12 样本均加载中文 `zh-CN` 页面，关键 `/bootstrap`、`/factory`、`/versions/...` 和比较页 `/comparisons/...` 响应均小于 400。浏览器实际提交的固定 fixture 与协议逐字段一致；最终比较为 5 `ADDED` / 22 `CHANGED` / 558 `UNCHANGED`，Validator PASS，current Publication 不变。

比较页的浏览器 API p95 高于服务端直接调用 p95，是因为浏览器路径还包含 HTTP、序列化、代理和同屏并发读取；它仍只是当前参考机观察值。D18 应在实际交付方式和现场机上复跑相同脚本后再决定是否建立独立首屏目标。

## 7. 证据与复算

- 协议：`demo/benchmarks/formal-protocol.v1.json`
- 版本化基线：`demo/benchmarks/baselines/cnc-demo-formal-benchmark.v1/baseline.json`
- 后端汇总：同目录 `backend-suite.json`
- 环境签名：同目录 `environment.json`
- 原始样本：同目录 `raw/`，共 21 个 JSON
- 浏览器观察：`demo/build/validation/browser-benchmark-observation-demo-09.json`
- 汇总证据：`demo/build/validation/benchmark-evidence-demo-09.json`

`run_benchmark_evidence.py --verify-only` 会重新读取 21 个后端样本和 12 个浏览器样本，复核每个 sample fingerprint、环境与源码 digest，从 measured 原始值重算所有分布和 Showcase 阈值，再核对 sealed baseline。当前 baseline fingerprint 为 `sha256:cf388a58bf6461e432e6b7f4132fcd6d617a66a5707fdfbf0abe2dc1af4830ce`。

## 8. 局限与后续

- 数据完全为 synthetic，不能证明真实客户订单、工艺波动、人员/刀具约束或生产容量。
- 5 个 measured 足以执行当前 Demo gate，但 p95 等于 max，不能外推长尾或 SLA。
- 当前只测单 worker、单工厂、单次加急事件；连续插单和多租户竞争不在范围内。
- RSS 是操作系统 Working Set 的进程树离散采样，不等于 Python heap，也不等于容器资源上限。
- 当前参考机不是已确认的最终现场机；D18 必须做目标机 smoke/首屏对照、冷启动、中断恢复和打包审计。
- D17 没有修改 root backend/frontend/schema，也没有注册、恢复或推进 P7。

D18 完成前，发布结论只能写为“D17 参数与本地参考基准已冻结”，不能写为“CNC Simulation Demo ready”。

## 9. 任务闭环状态

本报告的基准结论已通过复算；TASK-DEMO-09 的最终 machine report 仍因共享工作区中非本任务产生的 `demo/**` 外文档差异保持 `FAIL`。报告明确给出 `functional_status=PASS`、`closure_blockers=[SCOPE_CHECK]`，不把外部差异吸收到 Demo 允许范围，也不改写既有 protected-root hash。待外部差异所有者处理后，应重新生成 task context 并复跑 machine report；只有整体 `status=PASS` 才把任务卡改为 complete。
