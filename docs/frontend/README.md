---
doc_id: DOC-FRONTEND-INDEX
title: Frontend 文档形成计划
status: baseline
spec_version: 0.3.0
phase: P3
normative: false
source_sections: [68, 69, 77, 78]
last_reviewed: 2026-08-27
---

# Frontend 文档形成计划

## TASK-P3-17 audit conclusion

P3 Frontend已由67项Vitest、三组Chromium各12/12、SCA/license、build与machine evidence独立复验；18 routes、human controls、read-only visualizations和双语display均PASS。TASK-P3-17只审计冻结实现，不增加P4 route、client Solver/Validator或Production authority。

## TASK-P3-16 bilingual implementation boundary

[`official-zh-cn-terminology.v1`](official-zh-cn-terminology-map.md)是P3展示层唯一官方中文术语基线。TASK-P3-16以`1636fe9c909b728d49f9907ed9f53030b5921914`为Diff base实现默认`zh-CN`、可切换/恢复`en-US`、非敏感locale preference、document/Ant Design locale同步、typed词典、Intl格式、unknown raw fallback及双语accessibility/browser证据。API path/key/operationId、state/command/error/C-ID、ID/fingerprint/raw UTC与canonical bytes继续为英文机器合同，严禁从中文label反向构造request。67项Vitest、三组各12/12 Chromium与8/8 i18n machine checks已由implementation/closure provider复验；dependency/lock零差异。TASK-P3-17已完成独立Audit并由exact implementation provider支持为`done`。

## TASK-P3-14 browser Gate

Gate在Node `24.19.0`/npm `11.17.0`下对同一P3-13 12-spec Chromium suite执行两次独立replay，并由`p3-frontend-gate-report.v1`核对两轮12 expected/12 passed、8 human-control specs、JSON/JUnit/HTML文件与stable semantic fingerprint。既有failure-only screenshot/video/trace策略不变；本Task不新增用户能力或support browser matrix。

## TASK-P3-13 human-control slice

P3-13在development-only `SIMULATION`/`TEST`/synthetic runtime内新增command producer、action state hook与schedule/approval/publication/export/audit controls。Browser只提交server contract，不复制Validator、state transition或authority；成功后跟随server返回的新Version或重新读取authority。401/403/409/422/500、unknown network outcome与ExportJob failure均显式可见且不显示成功状态；只有unknown outcome在完成mandatory refresh后可复用原command/idempotency key。

Gantt drag只产生±24小时内、5分钟量化的Move proposal；最终时间仍作为command交由server validation，并导航到authoritative new DRAFT。PUBLISHED只显示immutable提示。Export下载只在authoritative Job=`EXPORTED`且artifact manifest存在时显示，并在browser核对package/manifest/archive header与bytes后保存。`.env.e2e`只打开versioned `SIM-P3-HUMAN-CONTROL-001@1.0.0`测试面，不含credential且不改变Production默认拒绝。

首个corrective implementation artifact `9589931373`已复验54 Vitest、12 expected/0 unexpected/0 flaky/0 skipped Chromium与Frontend machine 12/12；这些Frontend事实继续有效。首次closure发现的Backend XLSX determinism缺口由独立corrective `3538d46f8b73ae434057bcbca9037436aa91f2c7` / artifact `9590625358`修复并再次复验同一Frontend证据，故TASK-P3-13=`done`。真实identity/authority、external adapter、P4和Production仍未形成。

TASK-P3-01已在任何Frontend dependency或实现前形成：

- `planning-workspace.md`：Data Health、Runs、Orders、Resources、Gantt、Diagnostics、Approval、Publication 等信息架构；
- `gantt-command-contract.md`：拖拽命令、服务端验证、新 Draft 和 Validator 流程；
- `approval-publication-flow.md`：capability、状态门、幂等发布/导出和审计。

已确定的不变量：React 不复制 Solver Logic；Gantt 不直接更新 PUBLISHED schedule；开发环境额外页面不进入生产入口。审批角色受 OPEN-010 阻塞。

## P3 formation plan

TASK-P3-01已形成Planning Workspace、Gantt command与approval/publication三份详细规范以及页面/API/permission矩阵，并由[ADR-0012](../adr/ADR-0012-planning-workspace-command-state-publication.md)接受server authority、copy-on-write new DRAFT和Frontend组合。P3-01当时没有创建`frontend/**`；TASK-P3-11现建立exact-pinned React/TypeScript/Ant Design/TanStack Query/npm/Vite/Vitest/Playwright foundation和read-only workspace，P3-12已实现read-only visualization/comparison，P3-13才可接入edit/lock/approve/reject/publish/export并执行control E2E。UI只发送server command、显示权威状态/错误，不计算排程、绕过Validator或提供PUBLISHED update。

页面规范形成不等于API payload Schema、OpenAPI、组件、bundle、dependency lock、accessibility/E2E或Production UI已经形成。所有行为证据继续由P3-02/05/10～15按序负责；OPEN-010未关闭前Production action default-deny。

## TASK-P3-05 backend read availability

14个Planning Workspace read model的application结果已形成，包含stable carrier reference、完整payload page、lineage/freshness、found-empty/missing和opaque cursor语义；Version Comparison保持P3 DTO。P3-05交接时`frontend/**`仍为零差异；P3-11现只能经P3-10 HTTP适配消费其中获授权的read-only subset，P3-12仍负责Gantt/load/comparison。

## TASK-P3-11 completed read-only boundary

TASK-P3-11已于2026-08-25获明确授权并从不可变Diff base `26dd519b1f1f84e08d415cfdfce43f286fa82988`完成locked foundation与read-only workspace。Gantt、Resource Load与Version Comparison已由P3-12完成；全部edit/lock/approve/reject/publish/export control仍归P3-13且未自动启动。

Node/npm/direct pins、lockfile v3、SCA/license命令以Task卡逐字清单为准。特别地，用户批准的typescript-eslint门禁是固定三元组`typescript-eslint=8.68.0`、`eslint=10.9.1`、`typescript=6.0.3`，而不是latest range；TypeScript必须满足`>=4.8.4 <6.1.0`，CI拒绝range、drift、peer conflict和未审查升级。

Implementation `567e8693db881ea3dfffa011de9021fef9641361`已形成13条read-only route、GET-only canonical query client、default no-token session、strict carrier/reference检查、exact Version precondition、raw UTC/lineage/fingerprint authority、seven-state UI、virtual table和25个Vitest/component/contract/accessibility tests；npm v3 lock来自npm `11.17.0`。Artifact `9552386549`精确复验Frontend 9/9、SCA 0 advisory、336 package license/0 issue及只读阶段边界，故Task=`done`。

## TASK-P3-12 provider-verified visualization boundary

TASK-P3-12已从不可变Diff base `3bca1cc10ebedc4d47227bafb2f3f66854ccb526`完成factory/workshop/machine Gantt、Resource Load和two-Version comparison，且未增加dependency或改lock。现有route inventory为18条；Gantt按server UTC/tick/duration定位并做vertical windowing，完整table fallback保留所有operation，load/utilization与comparison change/KPI/summary均逐字显示server事实。

Local 37项Vitest、4项read-only Chromium及12/12 machine已通过；client还把response query fingerprint/correlation/authoritative Version与outbound request及compared Version逐字绑定。Implementation artifact `9555196470`已精确复验Frontend 12/12、Playwright 4/4与Task 55/0/6/19/0，故Task=`done`。`VERSIONED_SYNTHETIC_UI_120@1.0.0`只观察120 total/最多24 mounted rows，不是Production规模或SLA。Client仍无command/action carrier、无token persistence、无Solver/Validator/KPI/Resource Load/delta authority；P3-13 actions、P4与Production均未启动。
