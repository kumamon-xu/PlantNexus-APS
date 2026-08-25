---
doc_id: DOC-OPS-001
title: P0 工程安全边界
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [58, 62, 93, 95, 100]
last_reviewed: 2026-08-25
---

# P0 工程安全边界

## 已形成控制

- `Settings` 只从显式参数与 `PLANTNEXUS_*` environment 读取；不隐式载入 `.env`，Secret endpoints 使用 `SecretStr`。
- Production runtime/data plane 必须同时选择且 Simulation API 必须 disabled；Production 还要求 PostgreSQL 与不可变 40 字符 code commit。配置错误在连接外部服务前 fail closed。
- structured log processor 递归屏蔽 password/token/authorization/API key/credential、DB/Redis URL 字段，并移除 URL userinfo 和 free-text secret assignment；health/readiness 不回显 driver exception 或 endpoint。
- SQLAlchemy probe 使用固定 `SELECT 1`，Alembic 使用静态 migration；当前没有用户输入 SQL、shell 拼接、上传文件、宏/公式执行或外部 command adapter。
- direct dependencies 与 dev tools 在 `pyproject.toml` exact pin，并由 `uv.lock`、CI contract test 和 `uv sync --locked` 验证；TASK-P2-03新增的OR-Tools也必须exact pin并限制在CP-SAT namespace。
- Compose 只接受外部注入的 PostgreSQL password；`.env.example` 的 `replace-me-local-only` 是非生产 placeholder，应用不会自动读取它。

## 验证证据

[`test_config_and_health.py`](../../backend/tests/integration/test_config_and_health.py) 验证 Production/config fail closed、Secret repr/summary 与 readiness no-leak；[`test_logging.py`](../../backend/tests/integration/test_logging.py) 验证 recursive/free-text/URL redaction；[`test_ci_contract.py`](../../backend/tests/integration/test_ci_contract.py) 验证 exact dependency、solver-free lock、development-only Compose 和 non-root container。`engineering-skeleton-report.v1` 另提供 machine summary。

## 尚未形成

P0-08 没有 authentication/authorization、Import size/type/macro controls、network policy、TLS/mTLS、secret manager integration/rotation、container/image vulnerability scan、SBOM/signing、digest-pinned actions/images、database roles、backup/restore、production incident response 或第三方 threat assessment。Action/image patch tags与 read-only GitHub permission 是工程起点，不是 supply-chain/production security certification。

真实 Import/API/Publish/Production Task 必须补充其威胁模型、negative tests、权限和平台 evidence；不得用本文件关闭 OPEN-002/010/015 或声称 NFR-SEC-001 已全阶段完成。

## TASK-P1-03 Raw Staging controls

- source name只接受leaf name，禁止路径片段；digest必须为lowercase SHA-256，received-at必须显式UTC，row payload必须为immutable bytes。
- SQLAlchemy Core使用静态table/parameterized statement；没有拼接SQL、shell command、文件执行、macro或formula evaluation。
- raw bytes可以合法包含非UTF-8或敏感业务内容，因此异常统一为稳定sanitized code并从driver exception断链；rollback test用含secret-like文本的数据库错误验证不泄漏。
- repository按data plane过滤所有读写，数据库CHECK同步约束synthetic provenance；raw payload没有直接Canonical/Snapshot/Problem/Solver入口。

本Task没有实现上传格式/大小上限、malware scanning、CSV injection/XLSX macro/external formula防护、authentication/authorization、encryption、retention/erasure、database role或Production audit。这些控制不能从`media_type/content_length` metadata存在推断，文件入口由TASK-P1-04继续形成。

## TASK-P1-04 file import controls

- 只接受source root内可解析的relative `.csv/.xlsx` regular file；拒绝absolute/`..`/symlink escape、legacy `.xls`、macro-enabled `.xlsm`和其他extension，读取最多4 MiB+1 byte后fail closed。
- CSV固定strict UTF-8无BOM和comma/double-quote dialect；header/order/column、row与cell length显式限界，formula-like prefix不进入staging。
- XLSX先检查OOXML ZIP member count/total expansion、duplicate/traversal/encryption、DTD/entity、VBA content type/member和external links/relationships，再以`openpyxl==3.1.5` read-only、`data_only=false`读取单一`records` sheet；`defusedxml==0.7.1`已锁定并由测试确认启用。
- source异常统一返回sanitized DATA_ERROR，不拼SQL/shell、不加载macro、不取formula cached value；测试文件只在temporary directory生成。

这些控制仍不包含antivirus/content disarm、MIME magic/signature policy、upload quarantine、auth/RBAC、rate limit、encryption、retention/erasure、production audit或第三方安全评估。Reference Adapter的`production_binding=false`和negative tests不能声称NFR-SEC-001全阶段完成。

## TASK-P2-03 solver dependency review

`ortools==9.15.6755`由accepted ADR-0011、exact direct pin、`uv.lock` transitive versions和CPython 3.12多平台wheel SHA-256共同约束；AST检查确认native import只存在于`planning/backends/cp_sat/`。Repository-level upstream advisory查询在2026-08-20为空，`pip-audit==2.10.1 --skip-editable`的point-in-time结果中，新增OR-Tools依赖子树无记录。

同一次全环境审计仍检出Diff base已存在的`pytest==8.4.1`一个advisory和`starlette==0.47.3`六个唯一advisory（原始记录含alias/duplicate共8条）；两者不在OR-Tools依赖子树，本Task不越界升级FastAPI/Starlette或pytest。该债务登记为RISK-011并阻止Production安全认证，但不否定P2-03新增solver子树的有界审查。仓库尚无持续SCA、SBOM/signing、binary provenance attestation或Production threat assessment。

## P3 security planning

P3采用authority-neutral capability与Production default-deny；actor credential不得进入Schema、日志或artifact。P3-01固定permission/error/audit合同，P3-07/10/13验证未授权和跨plane拒绝，P3-11对frontend exact lock执行SCA/license review。OPEN-010与既有advisory债务保持开放，因此任何P3成功都不能声明Production security approval。

TASK-P3-01合同现要求每个action同时校验authenticated principal reference、environment、data plane、capability、resource/state/fingerprint和target；客户端role/capability声明无效。Production缺少mapping/target时DENY，Simulation test policy必须`production_binding=false`且只作用于synthetic resource/`SIMULATION_INTERNAL`。高风险拒绝可写sanitized audit，但not-found不得泄漏跨scope资源。

Audit/log/error/artifact不得包含token、cookie、authorization header、Secret、raw DSN/SQL/stack或未清洗PII；actor使用稳定reference。TASK-P3-01未形成authentication provider、RBAC/SSO、rate limit、CSRF/CSP、frontend dependency lock、SCA结果或Production threat model，OPEN-002/010/015和RISK-011/012/013均不因此关闭。

## TASK-P3-03 storage security review

Write前的carrier precheck拒绝unknown/missing top-level field、plane/environment/provenance drift和已登记secret-bearing key；repository错误只公开module-local reason/field/sanitized message，SQL/DSN/credential/stack不会向外透传。Plane进入全部identity/query/CAS；Publication/Export的Production constructor/DB约束双重default-deny。Append-only与immutable trigger提供绕过repository时的第二层保护。

这些不是authentication/RBAC、encryption、retention、SCA、SIEM或Production threat-model证据；test actor和`SIMULATION_INTERNAL`仍无Production binding，OPEN-002/010/015与RISK-011～013保持开放/监控。

## TASK-P3-06 command security review

Authorization在source lookup和exact replay前执行；只有server-resolved `edit`/`lock` capability可继续，`SUBMIT_FOR_REVIEW`由server固定要求`edit`，client `required_capability`仅作一致性校验。Raw idempotency key不进入AuditEvent/machine report，event仅保存hashed key reference；reason/actor/correlation受bounded/control-character guard，adapter异常统一清洗。Production即使携带`edit` capability也固定`PRODUCTION_AUTHORITY_UNAVAILABLE`，OPEN-010未关闭。

该slice没有authentication provider、RBAC/SSO、rate limit、CSRF/CSP、external publish target或Production threat model。Failed command不保存成功audit，未来拒绝attempt审计必须避免not-found/authorization侧信道。

## TASK-P3-07 decision security controls

APPROVE/REJECT先验证strict carrier与server context，再按authenticated flag、exact derived capability、ScheduleVersion scope、Simulation test policy与Production binding授权；未授权时绝不读取ScheduleVersion或成功result。高风险DENY只追加aggregate ID、request/key reference和generic error，不保存source existence、lineage或before/after state；same denied request不重复event。普通authorized not-found仍不写denial audit，避免混淆resource existence。

Actor必须是`actor:<stable-ref>`且不能含邮箱显示身份；reason拒绝control characters以及Authorization/Bearer/password/token/secret/cookie/DSN样式，raw idempotency key只计算SHA-256 reference。Adapter错误统一清洗。Production始终`PRODUCTION_AUTHORITY_UNAVAILABLE`并记录sanitized denial，OPEN-010保持OPEN；本Task没有authentication provider、RBAC/SSO、rate limit、CSRF/CSP或Production threat-model closure。

## TASK-P3-08 publication security controls

PUBLISH先验证strict carrier与server context，再按authenticated、publish capability、exact Version scope、Simulation test policy与Production binding授权；未授权不得读取success audit、ScheduleVersion或current reference。Production只能追加无source/lineage/state的generic `WORKSPACE_INTERNAL` denial，same denied request不重复event。Raw key只存hash reference，reason/actor/adapter error沿用credential与resource-existence清洗。

Current/supersession precondition由server repository事实决定，客户端payload只能作为CAS expectation，不能授权或覆盖。没有authentication provider、RBAC/SSO、external publisher、rate limit、CSRF/CSP或Production threat-model closure；OPEN-002/010保持OPEN。

Export authorization在job/source/replay lookup前检查actor/authenticated/`export` capability/Schedule或Job scope/policy与Production binding；raw idempotency key只保留SHA-256 reference。Package防护包含canonical hashes、path allow-list、XLSX formula/macro/external-link拒绝、same-parent temp及escape check；carrier不含Secret、SQL、stack、absolute path。真实RBAC/SSO、download authorization、malware pipeline及Production threat model仍未形成。

## TASK-P3-10 HTTP security boundary

Bearer只交给server-side provider，router/body不接收role或capability authority。认证缺失/失败、scope/capability拒绝、Production default-deny和malformed provider result均在application前终止；provider或denial sink自身失败也只返回sanitized 503/500且不进入application。Denial sink只收集sanitized reference，测试证明Bearer/provider exception/audit DSN不泄漏；成功与错误响应均`no-store`。CORS/session/CSRF/rate-limit、真实OIDC/SSO/RBAC、secret rotation、gateway/WAF和Production threat model未形成，OPEN-010/015保持OPEN。

## TASK-P3-11 Frontend security boundary

Browser client仅GET、`credentials=omit`、`cache=no-store`，token只能由内存中的注入provider即时返回；源码与machine scan拒绝localStorage/sessionStorage/cookie和command carrier。默认provider返回null，authorization error保持显式denied，不以synthetic/empty缓存替代。Production runtime固定non-synthetic且navigation没有Simulation入口。

Artifact `9552386549`复验SCA 0 vulnerability、336 package license/0 issue、no-token persistence与Production non-synthetic boundary。真实OIDC/SSO/RBAC、CSP/WAF、browser matrix、Production threat model和security approval仍未形成，OPEN-010/015保持OPEN。

Dependency Gate锁定24个direct pins和npm v3 integrity，SCA当前0 advisory，336个locked package license无unknown/deny-listed项；用户批准的typescript-eslint固定组与peer被lock/CI contract复验。这不是CSP/XSS penetration、real session/OIDC、CSRF/CORS、gateway/WAF、browser matrix或Production threat-model证据，OPEN-010/015和RISK-011～013不关闭。

## TASK-P3-12 visualization security boundary

新增页面继续依赖React text rendering与strict runtime parser，不使用raw HTML、eval、local/session storage或cookie。Gantt/load只GET；comparison POST严格属于read-query，先校验两个Version exact reference、不带Idempotency-Key，也不装配commands/approve/reject/publish/export carrier。Authorization、stale、contract和server failure均显式可见，不用cached/synthetic empty伪装成功。

Read-only Chromium覆盖authorization denial和no-command/no-idempotency transport；source/machine scan验证client Solver/Validator/KPI/Resource Load/delta authority及P4/control模块不存在。该bounded evidence不等于CSP/XSS penetration、真实session/OIDC/RBAC、CSRF/CORS、gateway/WAF、browser matrix或Production threat-model approval；OPEN-010/015与RISK-011～013继续保持原状态。
