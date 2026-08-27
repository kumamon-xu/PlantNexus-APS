---
doc_id: MILESTONE-P3-AUDIT-001
title: P3 Exit Gate Audit Report
status: baseline
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 66, 67, 68, 69, 77, 78, 86, 87, 94, 100, 106, 110, 111]
last_reviewed: 2026-08-27
---

# P3 Exit Gate Audit Report

## Decision

| Field | Audited value |
|---|---|
| Audit Task | TASK-P3-17 |
| Task lifecycle | `done`；audit implementation exact provider已验证，本evidence-only closure写回事实；closure提交自身仍须push后exact provider复验 |
| Audit date | 2026-08-27 (Asia/Hong_Kong) |
| Local execution window | 2026-08-27T09:45～10:10+08:00 |
| Immutable Diff base | `0933e10760096cdf8e812b2d41b34916e9db5750` |
| Audited business baseline | `0933e10760096cdf8e812b2d41b34916e9db5750`；TASK-P3-16 evidence-only closure |
| Audit execution head | `0933e10760096cdf8e812b2d41b34916e9db5750`；工作树只含TASK-P3-17 activation/audit治理文档，业务代码、Schema、migration、dependency、test assertion与workflow均与Diff base相同 |
| Audit implementation commit | `201be9c6fd1b433a9d0a629a3ae7d4ffe1107476`；parent=`0933e10760096cdf8e812b2d41b34916e9db5750` |
| Runtime / contract baseline | CPython `3.12.13`、uv `0.11.32`、Node `24.19.0`、npm `11.17.0`、schema set `2.7.0`、OR-Tools `9.15.6755`、Frontend direct pins exact |
| P3-16 closure provider | run `33028998495` / required job `98376876640` / artifact `9629623182` / digest `sha256:e1aaab824dd529459e986b2a8ea1bd0e643ac5cc8ba5fa8849727faf365861ba` / not expired |
| Predecessor provider audit | P3的39个push SHA、39个`validate` check-run与36个可用artifact逐项查询；35 success与4个保留的historical failure一致 |
| Download audit | 36个artifact、1052个文件、1010份JSON；0 parse error、0 SHA mismatch；983份successful-chain JSON均顶层PASS/0 issue/0 gap，27份失败候选partial JSON保留为负证据 |
| Branch protection | `main.protected=true`；required status check `validate`绑定GitHub Actions app ID `15368`；`strict=false` |
| Audit implementation provider | run `33033591189` / required job `98391337626` / artifact `9631260796` / digest `sha256:49833cdb63c9703a3837a194fd05d648b721d23719f0096a96fbbe0642937852` / not expired；44 files/38 JSON全部一致 |
| Overall P3 Exit Gate | `READY` |
| Blocking gaps | `[]` |
| Recommendation | 本evidence-only closure provider复验后，请求用户另行批准P3→P4；本Task不切换phase、不创建或执行P4 |
| Auditor | Codex execution agent |

机器可读结论见
[`P3-exit-gate-evidence-manifest.json`](P3-exit-gate-evidence-manifest.json)。本审计把本地命令、Git提交拓扑、GitHub API/provider metadata和下载后的artifact内容分别核验；这是透明的非密码学审计声明，credential未写入仓库或artifact。

`READY`只表示总规P3 Planning Workspace Gate的已批准范围具备可复验证据。它不表示Production readiness、真实组织审批责任、Production publish authority、外部ERP/MES side effect、真实工厂capacity/SLA、UAT、deployment，亦不表示P4 Dynamic Replanning已经授权或形成。

冻结的`p3-vertical-slice-report.v1`仍包含`gate_kind=P3_VERTICAL_SLICE_EVIDENCE_NOT_EXIT_AUDIT`、`exit_gate_audit=NOT_PERFORMED`和历史编号边界。这些是TASK-P3-14生成时的真实字节，不应被追写。本报告与manifest才是TASK-P3-17的独立Exit判定载体；历史Gate、失败run和provider artifact均未改写。

## Gate evidence

| Gate | Result | Evidence actually observed | Boundary |
|---|---|---|---|
| P3 Task lineage and finality | `PASS` | TASK-P3-00～16均`done`；39个P3 first-parent push commit全部是Diff base后祖先；TASK-P3-17仍是Milestone最后一项 | 不重写P3-00～16卡、提交或失败历史 |
| Required provider topology | `PASS` | 39个exact `validate` check-run均来自app `15368`；35 success、4 historical failure；36个artifact均未过期 | 失败候选不伪装成功，也不对旧SHA rerun |
| Downloaded provider contents | `PASS` | 36个artifact共1052文件/1010 JSON；success chain 983 JSON均可解析、顶层PASS、SHA一致、0 issue/0 gap；35份Task report均精确绑定Task/Diff base/SHA及19 checks | P3-13失败候选的27份partial JSON单独计数，缺失Task report符合失败点 |
| Contracts, Schema and compatibility | `PASS` | P2 frozen bytes、P3 `2.6.0` workspace carriers、`2.7.0` export carriers、strict/offline refs、fingerprints、positive/negative vectors全部回归 | 本Task无Schema、state pair、wire vocabulary或migration变化 |
| Persistence and migration | `PASS` | revision `0004_schedule_versions_audit_export_jobs` upgrade/downgrade/re-upgrade、5 tables、4 repositories、CAS/lease/plane/rollback与DB immutability guards通过；focused migration 8/8 | SQLite test evidence不等于PostgreSQL Production capacity/backup/restore证据 |
| Reviewable version lifecycle | `PASS` | validated lineage→immutable DRAFT→READY_FOR_REVIEW、fresh Validator/KPI、atomic audit、exact replay/conflict/rollback/concurrency通过 | 不修改PlanningRun，不把READY_FOR_REVIEW等同批准 |
| Read models and comparison | `PASS` | 18 HTTP read/write operations中的read projection、14 workspace views、stable filter/sort/cursor、two-Version comparison、found-empty/missing/stale/plane/tamper通过 | Router/UI不拥有business state或Solver/Validator逻辑 |
| Gantt edit and lock commands | `PASS` | 四类content command均copy-on-write生成新DRAFT；SUBMIT进行第二次fresh Validator；旧Version与PUBLISHED保持immutable | 不形成P4 replan、ExecutionEvent、OBJ-002或ChangeReport |
| Approval, rejection and audit | `PASS` | READY_FOR_REVIEW→APPROVED/REJECTED、authority-neutral scope、Production default-deny、success/denial append-only audit、same-key/conflict/rollback/concurrent single winner通过 | OPEN-010仍OPEN；真实RBAC/SSO和组织责任未形成 |
| Publication and supersession | `PASS` | 仅APPROVED可`SIMULATION_INTERNAL` publish；current reference CAS、旧PUBLISHED→SUPERSEDED、same-key replay/conflict、atomic rollback通过 | 无external publish/transfer；Production authority未形成 |
| ExportJob and standard package | `PASS` | 五state/六pair、lease/heartbeat/retry/cancel/recovery、12 payload、manifest-last、canonical XLSX、verified EXPORTED download与atomic cleanup通过 | P4 ChangeReport仍deferred；package不构成Production发布 |
| HTTP API authority | `PASS` | 18 operations=17 frozen P3-10+1 bounded P3-13 download；18 delegations、8 mapped reasons、0 router transition、0 Solver/Validator调用、0 Production provider lookup/application call | API仍为内部Simulation边界；external identity/MES/storage未形成 |
| Frontend human control | `PASS` | 67 Vitest；三组Chromium均12/12，其中8 human-control；401/403/409/422/500、unknown outcome refresh/retry、PUBLISHED guard及verified download通过 | 浏览器不保存credential，不复制server authority |
| Bilingual localization | `PASS` | `zh-CN`/`en-US`各243 keys、225 static refs、22 surface files、139 registered machine values、8/8 i18n checks；默认/切换/恢复、document lang、Ant locale、unknown raw fallback与English wire zero drift通过 | 仅display localization；无backend locale negotiation或中文server export |
| P2 regression | `PASS` | 621项full Python包含P2/P3；P2 Gate 11/11、repeat=2、C-001～C-011、OBJ-001、XS/S/M、Validator与internal output均通过 | 不扩展P2能力，不把synthetic benchmark外推Production |
| P3 deterministic Gate replay | `PASS` | Backend两次完整9-stage replay、144 subordinate checks；Frontend两次12-spec replay；P3 aggregate 14/14、四类exact rejection、combined semantic fingerprint唯一、0 gaps | raw timing/observations保留；只对versioned semantic projection比较 |
| Dependency, ADR, SCA and license | `PASS` | Python/npm locked install、accepted ADR链、exact runtime pins、Frontend SCA 0 vulnerability、license allow-list通过 | point-in-time检查不等于持续供应链或SBOM承诺 |
| Repository quality and build | `PASS` | Ruff、Pyright、621 pytest、67 Vitest、36 Playwright、Compose config、Frontend build、sdist/wheel、version `0.0.0`全部通过 | bundle/timing为development observation，不是SLA |
| Governance and frozen scope | `PASS` | 审计前full governance为168 docs/30 roots/30 trace rows/49 Test IDs/15 OPEN/15 SIM/14 risks/55 Tasks；业务/Schema/frontend/tests/workflow/dependencies/migrations相对Diff base零差异 | 最终文档写回仍须full/diff docs、`git diff --check`和scope复验 |
| PROD_OPEN, Simulation and risk truthfulness | `PASS` | OPEN-001～015继续OPEN；SIM-ASSUMPTION-001～015继续ACTIVE；RISK-001～014继续MONITORED | READY不关闭任何Production未知项、assumption或风险 |

## Provider implementation and closure history

下表列出每个Task在最终first-parent链上承担业务/治理事实的成功SHA；所有失败候选与corrective链另列并完整保留。括号为`run / required job / artifact`。

| Task | Successful implementation or corrective | Evidence-only closure |
|---|---|---|
| P3-00 | `1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7` (`32681493976/97298850740/9504310381`) | `7f65f88b620ea1e8d2f4693911be3b52f4052d5d` (`32682015727/97300206924/9504453154`) |
| P3-01 | `3bf99cbafdad983795a83a88646240dbb0b24509` (`32684713630/97307562801/9505303054`) | `a8fcec3383ea0f8d9dca4101056aff37d7eea08c` (`32685213833/97308956420/9505465582`) |
| P3-02 | `aff27d3d6b63fb9f216c9a2687408a6c676fa96a` (`32689832111/97321420908/9506913562`) | `9621fda535f66393beab88efc13c100fc805c993` (`32690302424/97322642627/9507045338`) |
| P3-03 | `e315dbf4f6c079df6d19b52f0403b00827126232` (`32694644036/97334382152/9508445635`) | `62604d05964413a0aa7f763afd720afa2d53a887` (`32695127644/97335699708/9508601189`) |
| P3-04 | `a9be974855bb825784d639b7f6675e5a33e4273d` (`32700005280/97349447107/9510215582`) | `fc5011f78a242160097521259a1914d864d9ad17` (`32700684160/97351382226/9510431988`) |
| P3-05 | `f236fab47aa2565b87a060b2c8bde8f2e8d66229` (`32706258281/97367902547/9512423712`) | `67d38d030f8b129de7f1b2f6e5b75bd706655396` (`32707242260/97370830393/9512779675`) |
| P3-06 | `08317637c7fbb51d46880d32523545bb0b4fe1c0` (`32713635045/97390177509/9515126567`) | `514224b8ff2d507b613797ae697245bab14f79eb` (`32714501727/97392773902/9515436874`) |
| P3-07 | corrective `9aed9d8c5dd86a9a9b972f8e9c5491fd6d2dbaa6` (`32794370664/97642478274/9544333991`) | `a53c0f7d4a0f0bcd4e02bfeaaa0f6fc4b93157b9` (`32794963626/97644228513/9544539992`) |
| P3-08 | `e90475f462b365d2e031445ad28a02ea0b89d2f5` (`32798679852/97655144411/9545782727`) | `b9c0b1694448a4ec348b0b02107926f6213560c9` (`32799416669/97657208631/9546020704`) |
| P3-09 | `42278239332e61e55a4e0305705534db768dc22f` (`32805450589/97674572006/9548027237`) | `f71c4a5a11a3fac0e203e2e92198c26124755927` (`32806050713/97676254558/9548222852`) |
| P3-10 | `4958ce5759812331f13fab2608fbec37f1f1ff76` (`32812163430/97693443111/9550224090`) | `26dd519b1f1f84e08d415cfdfce43f286fa82988` (`32812850599/97695423162/9550448943`) |
| P3-11 | `567e8693db881ea3dfffa011de9021fef9641361` (`32818657951/97712018632/9552386549`) | `3bca1cc10ebedc4d47227bafb2f3f66854ccb526` (`32819640902/97714885416/9552720216`) |
| P3-12 | `a719fe5bf2c2ea2d59e1582e8f4dfd3f2674ac69` (`32826371613/97735176425/9555196470`) | `3dacf83c0f0bf87a9fa673aa75d61f8ad8659386` (`32827724754/97739345886/9555662914`) |
| P3-13 | corrective `13e16e36fc0a06a079d6832f419950c830f2b96e` (`32921059019/98034581212/9589931373`) + corrective `3538d46f8b73ae434057bcbca9037436aa91f2c7` (`32923203227/98040743610/9590625358`) | `6a3e02f00bf46f19915cb59c3c4af7daaac95be4` (`32924265508/98043825128/9591007369`) |
| P3-14 | corrective `54a25646053979a69734a3148030830d49c04c1e` (`32931418903/98064264595/9593460266`) | `06e7f794f486ac34c505237b847462c7c7c36d44` (`32932504153/98067309501/9593831442`) |
| P3-15 | `c84e1aa1a81473f65d9f7906a6d2c67a94e7bb2f` (`32944633958/98102640242/9597967232`) | `1636fe9c909b728d49f9907ed9f53030b5921914` (`32948633841/98114798738/9599442770`) |
| P3-16 | `b3ba999e83f4e8b0f96c7ce5bc72eba01432d791` (`33027761343/98373002264/9629193057`) | `0933e10760096cdf8e812b2d41b34916e9db5750` (`33028998495/98376876640/9629623182`) |

保留的失败事实为：P3-07初始implementation `3f85959e91e74966f6482426b9db296a45d715ef` / `32793980039/97641324105`无artifact；P3-13初始implementation `672529c97780d7f9dd64b517df075db05d8a45d9` / `32920462781/98032902570`产生partial artifact `9589702993`，首次closure `87d47c7483185483ac8027100c1c664d18011a7c` / `32921871460/98036888624`无artifact；P3-14初始implementation `0617141e411eea146cd9fc1c512ade900710be7c` / `32930677030/98062166642`无artifact。旧失败SHA未重跑，corrective均为新提交。

## Local acceptance record

| Command / evidence | Exit | Observed result |
|---|---:|---|
| `uv sync --locked` | 0 | 69 packages resolved/checked from lock |
| exact Frontend `npm@11.17.0 ci --ignore-scripts` | 0 | 310 packages installed from lock |
| `uv run ruff check .` | 0 | all checks passed |
| `uv run pyright backend/app backend/tests` | 0 | 0 errors / 0 warnings |
| full registered pytest directories | 0 | 621 passed in 195.29s |
| Frontend Vitest | 0 | 15 files / 67 tests passed |
| migration-focused replay | 0 | 8 passed |
| all required machine CLIs | 0 | 33 TASK-P3-17 JSON reports top-level PASS；0 SHA mismatch / 0 issue / 0 blocking gap |
| P2 vertical Gate, repeat 2 | 0 | 11/11 checks / 2 replays / 0 gaps |
| P3 vertical Gate, repeat 2 | 0 | 14/14 checks / 2 Backend replays / 1 combined semantic fingerprint / 4 exact rejections / 0 gaps |
| base + Gate Chromium replays | 0 | 12/12 + 12/12 + 12/12；each 8 human-control |
| bilingual i18n evidence | 0 | 8/8；2×243 keys / 139 machine values / 22 surfaces / 0 issues |
| Frontend SCA / licenses | 0 | 0 vulnerabilities；license policy PASS |
| P3 API / Frontend evidence | 0 | API 18/18 operations；Frontend 18 routes；bundle 1,133,290 JS / 4,798 CSS bytes |
| XS benchmark | 0 | 8/8 / 0 warnings；fixed Problem hash matched |
| `docker compose --env-file .env.example config --quiet` | 0 | configuration valid |
| `npm --prefix frontend run build` | 0 | production bundle built；size warning retained as development observation |
| `uv build` + installed version assertion | 0 | sdist/wheel built；`plantnexus-aps==0.0.0` |
| prerequisite GitHub API/download audit | 0 | 39 runs/jobs/checks；36 unexpired artifacts；1010 JSON；all expected success/failure facts matched |
| full docs governance before writeback | 0 | 168 docs / 30 roots / 30 trace rows / 49 tests / 15 OPEN / 15 SIM / 14 risks / 55 Tasks |
| full docs governance after writeback | 0 | 169 docs / 30 roots / 30 trace rows / 49 tests / 15 OPEN / 15 SIM / 14 risks / 55 Tasks |
| TASK-P3-17 final diff governance | 0 | 61 paths / 4 Impact Rules / 19 checks / 0 issues |
| `git diff --check` | 0 | no whitespace errors |
| forbidden-scope audit relative to Diff base | 0 | 61 documentation/governance paths；0 backend/Schema/frontend implementation/test/workflow/dependency/migration path |

最终写回后的full/diff governance、`git diff --check`与禁止范围已经执行并写入manifest；提交前还会做最终复核。审计Task自身provider结果来自implementation提交后的exact run，不以本地结果替代；evidence-only closure提交仍不能自我预填未来provider。

## Selected local machine artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| `TASK-P3-17-p3-vertical-slice-gate.json` | 467228 | `sha256:28b94a67f76a25f6fdff78453a3be9afa03d9da378f1e8ad2bf7478caa8f6ae6` |
| `TASK-P3-17-p2-vertical-slice-gate.json` | 307192 | `sha256:fc098c987d93416d004eb526303bb200ea6b0b471c8be789d9e121c9280d8416` |
| `TASK-P3-17-frontend-gate.json` | 20109 | `sha256:4bc9a5f4e4c950d339085c87bad4e9d87ca362596d23545940b7d1eaf1eb74d0` |
| `TASK-P3-17-frontend-i18n.json` | 2749 | `sha256:e3eb23c1a97e4666f60e24d1d76d0a94f5916a52089440d3ceb8435fd13cd852` |
| `TASK-P3-17-frontend.json` | 3667 | `sha256:3a6d30391e58b642061c11055eb4bd07f413ac08e354b84d11c679590765d41c` |
| `TASK-P3-17-p3-planning-workspace-api.json` | 3881 | `sha256:71359402b135695b15a9dd60265dc9c58e9cc34a82c8e770f065e2f54b403e74` |
| `TASK-P3-17-p3-persistence.json` | 3360 | `sha256:d82424c2dabf41f63515d6b5db681683b221645256bcf7de5415d768440bcb6d` |
| `TASK-P3-17-p3-export-jobs.json` | 2684 | `sha256:b16bbedb2401636164e6f96325f57529450d2ad7ef04164143568f2869d7416d` |
| `TASK-P3-17-xs.json` | 20815 | `sha256:c03ecfb33361afcaec32459d91eceb030f73be799e04ca0e158076c02d0b2e11` |

这些文件位于ignored `build/**`，均是冻结baseline上的本地审计输出，不是已提交产品artifact。Implementation provider已在clean exact implementation SHA上重新运行required workflow并上传、下载复核artifact。

## Audit implementation provider closure

Implementation `201be9c6fd1b433a9d0a629a3ae7d4ffe1107476`的parent恰为immutable Diff base；run `33033591189` / required `validate` job `98391337626`全部58 steps success，check-run绑定exact head SHA与GitHub Actions app `15368`。Artifact `9631260796` / `plantnexus-ci-evidence-33033591189`为814448 bytes，digest=`sha256:49833cdb63c9703a3837a194fd05d648b721d23719f0096a96fbbe0642937852`，未过期且expiry=`2026-11-25T02:32:29Z`。

下载后共有44 files、38份JSON与2701704 uncompressed bytes；全部JSON可解析，28份SHA-bound报告均绑定implementation SHA，0 mismatch、0顶层failure、0 issue、0 blocking gap。Task报告精确复现TASK-P3-17、Diff base、61 committed/0 working paths、四个Impact Rules、19 checks和0 issues；P3 Gate 14/14、双Backend/双Chromium、P2 Gate 11/11、i18n 8/8与三组Chromium各12 expected/0 unexpected均一致。该证据支持本evidence-only closure把Task标为`done`，不改变原审计baseline、失败历史或阶段边界。

## Gaps, boundaries and recommendation

`blocking_gaps=[]`。没有发现需要在本Audit内修复的P3业务、本地化、Schema、migration、state machine、test assertion、dependency、ADR、workflow或治理缺口。Audit implementation provider已exact成功，TASK-P3-17由本evidence-only closure标为`done`；closure提交自身仍须push后精确复验，若失败必须撤回`READY`并在P3内登记有界remediation，不能进入P4。

以下事项明确不被本结论关闭：OPEN-001～015、RISK-001～014、SIM-ASSUMPTION-001～015、真实source/field/topology/calendar/material/priority authority、独立Production数据库/角色、真实RBAC/SSO、external ERP/MES transfer、Production publish/approval、L/XL、Production capacity/SLA、UAT、deployment、ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport与Execution Simulator。

因此下一动作是：先让本evidence-only closure通过exact required `validate`和artifact下载复核；随后向用户报告P3 Exit Gate=`READY`并等待新的明确P3→P4授权。未经该授权，`current_phase`继续为P3，P3 Milestone继续`active`（Exit ready / awaiting transition），不得创建或执行P4 Task。
