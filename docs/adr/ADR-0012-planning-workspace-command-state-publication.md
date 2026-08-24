---
doc_id: ADR-0012
title: Planning Workspace Command State 与 Publication 边界
status: accepted
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [12, 33, 34, 65, 66, 68, 69, 77, 78, 94, 97]
last_reviewed: 2026-08-24
---

# ADR-0012 — Planning Workspace Command State 与 Publication 边界

Status: accepted

Date: 2026-08-24

Decision owners: PlantNexus APS repository governance；P3 transition与TASK-P3-01执行由repository owner明确授权

Requirement/NFR/ENG: REQ-006、REQ-007、REQ-009；NFR-TRC-001、NFR-ISO-001、NFR-SEC-001、NFR-HUM-001；ENG-ARCH-001、ENG-ERR-001、ENG-VER-001

Supersedes: none；落实ADR-0002、ADR-0005、ADR-0007和ADR-0009

## Context

P2已形成provider-verified PlanningSolution、formal ValidationReport、KPI和non-publishable internal package，但没有ScheduleVersion持久化、Workspace API/UI、人工审批、publication、ExportJob或Production authority。P3需要在人类操作进入代码前固定以下冲突边界：

- Gantt编辑若直接UPDATE，会破坏ADR-0007的不可变版本与审计lineage；
- UI/router若自行判定constraint或权限，会破坏ADR-0002/0005的依赖方向和独立Validator；
- approve、publish和export若合并为一个side effect，会导致重试double publish且无法区分状态/文件/外部target；
- 真实角色、identity provider与MES/ERP target仍受OPEN-002/010/015阻塞，不能由test actor或UI按钮补猜；
- P4的ExecutionEvent/Replan/freeze/OBJ-002/ChangeReport/Execution Simulator不能借P3编辑功能提前进入。

TASK-P3-01只作合同与ADR决定，不修改Schema、migration、dependency、业务代码、测试断言或CI。

## Decision

### 1. ScheduleVersion content采用append-only copy-on-write

ScheduleVersion的业务content一经创建即不可原地修改。Gantt move/assign/lock/unlock等人工意图必须成为versioned command，读取一个source Version并原子产生具有新ID、父版本、content fingerprint、fresh ValidationReport和audit的新`DRAFT`。

source Version的state/content/current-publication不因编辑改变。DRAFT→READY_FOR_REVIEW仍要求完整provenance、fresh independent Validator PASS和hard violation count=0。PUBLISHED content绝无UPDATE路径；历史Version若作为参考，也只能派生新DRAFT并重新走完整评审链。

### 2. 采用Query/Command分离且server authority

Workspace query只产生稳定排序、分页、versioned、solver-neutral read models。Command必须依次通过认证/capability、data-plane、state/content precondition、idempotency、domain validation和fresh independent Validator。UI、HTTP router和worker只调用application service；它们不得直接写repository、复制Solver/Validator/KPI公式或自行推进状态。

状态、权限、错误和`allowed_actions`以server结果为准。客户端optimistic preview只能是非权威视觉状态。

### 3. 保留`state-machines.v1`全部既有state与pair

不新增state、pair或self-transition：

- ScheduleVersion：DRAFT→READY_FOR_REVIEW；READY_FOR_REVIEW→APPROVED/REJECTED；APPROVED→PUBLISHED；PUBLISHED→SUPERSEDED。
- ExportJob：CREATED→EXPORTING/CANCELLED；EXPORTING→EXPORTED/EXPORT_FAILED/CANCELLED；EXPORT_FAILED→EXPORTING。
- PlanningRun计算状态与ScheduleVersion评审/发布状态分离。

REJECTED、SUPERSEDED以及ExportJob的EXPORTED/CANCELLED保持既有terminal语义。幂等replay由unique key/request fingerprint/result persistence实现，不伪造成state self-transition。

### 4. Authorization采用capability和Production default-deny

应用能力词汇固定为`view/edit/lock/approve/reject/publish/export/audit`，每次判定同时检查authenticated principal reference、environment、data plane、resource scope、state/fingerprint和target。该词汇与Solver工厂capability registry分namespace。

P3可以为隔离Simulation plane配置`production_binding=false`的test principal/capability policy。Production没有明确principal→capability mapping或target时全部写/决策/副作用DENY。ADR不选择角色名、组织职责、SSO/OIDC/RBAC provider，也不关闭OPEN-010。

### 5. Approve、Publish与Export是分离事务/副作用

- approve/reject只允许READY_FOR_REVIEW并记录actor reference、capability、reason和append-only audit；
- publish只允许APPROVED且P3 target仅为明确的`SIMULATION_INTERNAL`；成功时原子写PUBLISHED/current reference/audit，并在新current替代旧current时执行旧PUBLISHED→SUPERSEDED；
- export只从PUBLISHED创建独立ExportJob和标准成果包，Job状态绝不改变ScheduleVersion publication；
- external MES/ERP/storage side effect没有在本ADR中形成。

approve/reject、publish和export分别拥有基于plane/action/resource/target/key的idempotency scope。same key+same request返回同一logical result且不重复state/audit/side effect；same key+different request返回conflict。Worker retry不得double publish。

### 6. State、idempotency与audit遵循同一一致性边界

每个成功command必须在同一事务或可证明的一致性边界提交业务结果、idempotency result和append-only audit；任一失败整体不成功。Audit event保存actor reference/capability、reason、action、aggregate、before/after、source/new Version、target、request fingerprint、correlation、result/error及contract/code versions，不保存token、Secret、raw credential、SQL或stack。

外部network exactly-once、outbox、retention、SIEM、Production backup/restore均未决定。若后续需要这些topology，必须在migration/adapter前提交新ADR。

### 7. 分层与持久化分配

依赖方向固定为：

```text
domain contracts/state
→ plane-scoped infrastructure repositories
→ application query/command/decision/publication services
→ API/jobs/exporters
→ frontend
```

TASK-P3-02发布strict machine contracts；P3-03形成migration/repository/CAS/unique/index；P3-04～09形成application/state/export behavior；P3-10只序列化application；P3-11～13只消费HTTP合同；P3-14/15分别执行纵向Gate与独立Audit。

### 8. Frontend工具链组合

P3 Frontend架构选择React + TypeScript + Ant Design + TanStack Query；单页构建选择Vite；package manager选择npm并以`package-lock.json`执行`npm ci`；unit/component测试选择Vitest + Testing Library；browser E2E选择Playwright。

本ADR只决定组合，不引入依赖或锁定版本。TASK-P3-11必须在独立授权和clean Diff base上逐字固定Node/npm及全部direct pins、生成lock、执行point-in-time SCA/license review，并接入required CI。P3-12/13不得绕过该Gate私增Gantt/E2E依赖。SSR、microfrontend、client-side solver和直接DB访问不采用。

### 9. Error和HTTP计划不改写现有registry

现有七类error category保持。P3使用既有`INVALID_STATE_TRANSITION`/`SCHEDULE_VALIDATION_FAILED`，并规划module-local `AUTHORIZATION_DENIED`、`IDEMPOTENCY_CONFLICT`、`EXPORT_FAILED` reason；后者在TASK-P3-02前不是global registry code。HTTP计划分别为409、422、403、409和500；任何机器carrier扩展必须版本化且不得改写P2 registry/Schema bytes。Solver UNKNOWN继续是NO_SOLUTION_WITHIN_LIMIT，不是INFEASIBLE。

### 10. P3、P4和Production边界

P3只形成Workspace read/command、ScheduleVersion、comparison、manual lock、approval/reject、internal Simulation publish、ExportJob/standard package和audit。ExecutionEvent、ReplanRequest、freeze window、OBJ-002、ChangeReport和Execution Simulator属于P4。真实Production identity/role、external target/adapter、deployment/UAT/approval/publish/readiness、capacity/SLA继续未形成。

## Alternatives considered

### Mutable ScheduleVersion row

拒绝。它无法稳定重放父子lineage，会使PUBLISHED/审计/并发边界不可信，并违反ADR-0007。

### UI直接调用repository或在client重算Validator

拒绝。它造成多套业务事实、绕过application authorization和formal Validator，且无法由API/provider统一验证。

### Approve时自动Publish，或Publish时同步Export/外部发送

拒绝。组合副作用使重试语义、责任、failure recovery和audit不可分辨，并增加double publish风险。

### 在P3-01直接选定Production角色、SSO或MES target

拒绝。仓库没有authority evidence，OPEN-002/010/015仍OPEN；猜测将把Simulation test policy冒充Production事实。

### 在原状态机增加EDITING、PUBLISH_FAILED或self-transition

拒绝。当前需求可由command attempt、idempotency result和ExportJob既有pair表达；新state会触发Schema/migration/consumer升级，暂无证据。

### 立即实现dynamic Replan/freeze/OBJ-002

拒绝。它属于P4且需要ExecutionEvent/Replan/ChangeReport与新的优化/状态证据。

## Consequences

正面结果：

- 所有人工动作、审批、发布和导出拥有确定的server guard、版本lineage和audit；
- PUBLISHED保持不可变，retry可由key/fingerprint证明不重复；
- Schema、persistence、application、API和UI后续Task拥有清晰依赖和失败边界；
- Production未知authority继续fail closed，P3 test evidence不会越界成为Production evidence。

代价与限制：

- 每次编辑都产生新Version，repository/query/UI必须处理lineage、比较、清理与分页；
- state/idempotency/audit原子性要求严格migration/transaction/CAS测试；
- external side effect若未来形成，可能需要outbox/adapter新ADR；
- Frontend依赖只有P3-11完成exact lock/provider evidence后才能声称已安装；
- TASK-P3-01只使合同和ADR形成，所有机器Schema、行为、测试和Production能力仍为`PLANNED`。

Schema：本Task none；P3-02新增strict documents且保留P2 bytes。Migration：本Task none；P3-03负责。Dependency：本Task none；P3-11负责frontend exact pins/lock。Benchmark：只规划synthetic规模维度，不设置Production阈值。Operations：audit/transaction/idempotency规范形成，retention/SIEM/external recovery未形成。

## Rollback / Revisit gate

accepted ADR不得删除或原地改写历史决定。若在任何consumer形成前发现合同矛盾，可提交有界更正并保留本记录；一旦Schema/DB/API/UI消费，变化必须使用new/superseding ADR、document version和必要migration。

以下证据触发revisit：必须增加state/pair；需要mutable Version；真实identity/role/target获批准；external side effect需要outbox/exactly-once topology；Frontend必须偏离React/TypeScript/Vite/npm/Vitest/Playwright；P4能力被正式授权。回滚实现时不得删除已创建Version、decision、publication、ExportJob、artifact或audit；只能停止新入口、保留可读历史并通过新Version/补偿event修正。
