---
doc_id: DOC-ARCH-010
title: Headless Productization and Platform Integration
status: active
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [3, 4, 5, 9, 10, 12, 15, 30, 63, 65, 66, 67, 68, 84, 85, 93, 95, 97, 101, 103, 105, 106, 107, 109, 112, 113, 114]
last_reviewed: 2026-09-06
---

# Headless Productization and Platform Integration

## 1. Stable product boundary

PlantNexus APS is one Headless scheduling backend with two permitted client forms: the owning host platform and an optional independently packaged industry frontend. Both clients use the same versioned HTTP API. Neither client may write APS persistence directly, invoke the solver as an ungoverned library call, or introduce a second scheduling state machine.

```text
ERP / MES / WMS / CAM / files / human input
                    |
                    v
        Host platform acquisition + mapping
                    |
          versioned canonical JSON
                    |
                    v
 APS Runtime: API -> contract/data validation -> immutable Snapshot/Problem
       |                         |                         |
       |                         |                         v
       |                         +-> durable PlanningRun -> Solver Worker
       |                                                   |
       +-> Extension Registry -> Enterprise Extension      |
                 through versioned SDK                     |
                                              Formal Validator + publication
                                              |
                                read models / export representation
                                              |
                   +--------------------------+------------------+
                   |                                             |
          Host platform display                       Optional APS frontend
```

The left-most systems are outside APS. APS does not own their credentials, SDKs, polling, event subscriptions, database schemas or vendor-specific field mappings.

## 2. Canonical JSON ingress

Canonical JSON is the only supported external product input. A request must identify its contract version, tenant/factory scope, source/version references, idempotency/correlation context and canonical records required by the selected operation. Exact wire fields and evolution rules are owned by TASK-P8-02; this document does not invent them.

The ingress sequence is fail closed. TASK-P8-07 now binds it to `POST /api/v1/planning-runs` using strict UTF-8 `application/json` with no content encoding, an 8 MiB byte limit, JSON depth 64 and at most 100000 aggregate `payload.records`:

1. authenticate and derive host principal/scope;
2. validate media type, size, contract name/version and machine schema;
3. validate tenant/factory scope, authority references and idempotency;
4. run the existing business Data Validation boundary;
5. persist immutable source payload identity and derived Snapshot/Problem lineage;
6. accept an asynchronous command or return a stable, sanitized error.

Unknown versions, missing authority, cross-scope identifiers, duplicate idempotency conflicts, invalid lineage and business-invalid records are rejected. The service must not guess, silently coerce to a third-party format, or fall back to a reference adapter.

CSV/XLSX/reference adapters and synthetic generators remain allowed only as internal or non-Production producers of canonical data. Before reaching scheduling logic, their output must traverse the same canonical contract and validation behavior used by the host.

## 3. Runtime ownership

APS Runtime is the deployable execution boundary. The API process owns transport, authentication hooks, request validation and application-port invocation. The application layer owns use-case orchestration and transaction boundaries. Repositories own APS persistence behind ports. The worker owns durable asynchronous execution and may call the same domain/application capabilities without changing their semantics. Runtime may load an approved Enterprise Extension through the versioned Extension SDK; API and worker must resolve the same extension fingerprint. The formal Validator and every extension Validation Rule remain independent from solver constraint construction.

APS persistence is private to APS and migrated by APS release artifacts. Host systems receive stable identifiers, statuses, errors and read models through the API. A database connection, shared ORM entity or direct queue message is not an integration contract.

Long-running planning uses a durable `PlanningRun` request and observable status. Timeout, retry, cancellation, duplicate delivery and worker restart must preserve idempotency and immutable evidence. The existing PlanningRun, ScheduleVersion, ExportJob and replanning state semantics remain authoritative until a separately approved Task/ADR changes them.

TASK-P8-04 now implements the transport-neutral portion of that boundary: a P8-03 CREATED carrier is materialized atomically with a mutable-CAS run row, one operational attempt, one immutable queue-ready work item, its initial transition, command receipt and audit. Legal run updates are limited to the frozen 16 states/31 pairs; published artifact references are monotonic, terminal runs cannot reopen, and dispatch failure/timeout retry appends a new attempt without changing run state. The work item freezes Scope, Policy/Limits, prepared Snapshot/Problem and server-owned Runtime/Extension-set fingerprints, but no broker or Solver consumes it until P8-05.

TASK-P8-05 now consumes that immutable work through one strict JSON Celery task. A durable binding and generic lease/heartbeat CAS protect the exact run/attempt/work identity; the existing Global CP-SAT strategy is followed by an independent fresh Validator, and canonical result bytes are checkpointed before terminal run transitions. Only a validated `COMPLETED` run may invoke the existing ScheduleVersion application, producing one `READY_FOR_REVIEW` version before task acknowledgement. Redelivery resumes the same checkpoint and never selects code or creates an automatic business attempt. The Worker slice itself remains an internal, server-composed edge; HTTP and composition are supplied only by P8-06/07, while Enterprise Extension loading and Production queue/database evidence remain later work.

TASK-P8-06 now provides the single Runtime composition root and immutable API/Worker descriptor. TASK-P8-07 binds that facade through five additive operations: create (202), status (200), cancel (200), retry (202) and terminal result (200, or 409 while nonterminal). The checked-in OpenAPI 3.1 snapshot contains 34 operations and preserves canonical hashes for all preceding 29 operation objects. Exact create/retry replay does not dispatch twice. The Runtime HTTP adapter derives trusted context, allowed scope, authority/mapping, build plan, Policy/Limits and dispatch windows from server-owned configuration; request headers and JSON remain requested coordinates rather than authority.

This transport is currently executable only with an explicit Simulation/Test Runtime and authorization provider. It does not provide host identity lifecycle, Production authority, extension upload/install endpoints, a second protocol or synchronous solving. TASK-P8-08 remains the owner of real host identity/scope/audit binding, and TASK-P8-09/10 remain the owners of release and deployment evidence.

## 4. Identity, authority and audit

The host authenticates to the APS boundary using a later approved mechanism and supplies or enables derivation of a stable subject and factory scope. P8-07 calls the existing server-side AuthorizationProvider before Runtime/application lookup and preserves its established error envelope; APS then maps that principal through a server-owned Runtime HTTP policy and independently enforces authorization at every command/query. Client-supplied body or `X-APS-*` scope is never trusted by itself. The real host adapter and Production binding remain P8-08 work.

Audit evidence binds subject, action, scope, canonical payload fingerprint, source/version references, correlation/idempotency key, resulting entity/version and outcome. Secrets and raw Production payloads do not belong in logs or CI artifacts. Concrete providers, retention and named Production authorities remain open until their closure records exist.

## 5. Dual delivery without backend forks

The owning platform may render every APS result in its own UI. An optional industry frontend may later package workflows such as input review, run monitoring, Gantt views, comparison and export, but is only another API consumer. It must not require server behavior unavailable to the host and must use generated/versioned client contracts rather than copy domain logic.

Frontend release cadence may differ from backend cadence if the API compatibility window is honored. Deployment may omit the optional frontend entirely; headless API, worker, database/migrations and operations controls remain a complete backend distribution.

## 6. Enterprise extension without Core forks

Enterprise-specific Constraint, Objective, Planning Rule, Validation Rule and Replan Policy contributions are server-side Runtime components registered through a deterministic Plugin Registry. The SDK is an internal SPI, not another network API. Extensions cannot be loaded by the host or browser, copy/modify APS Core, write the APS database, bypass canonical validation or introduce a private scheduling endpoint.

Core, Runtime, SDK, Extension artifact/config and Developer Kit have separate version identities. Each enterprise project locks a verified combination. A new Core or Runtime release produces a new Developer Kit candidate only after compatibility and old-Kit replay; it never mutates or automatically upgrades an enterprise project. Detailed trust, interface and delivery rules are in [APS Extension SDK、Runtime 与 Developer Kit 架构](extension-sdk-runtime-and-developer-kit.md) and ADR-0018.

## 7. P8 delivery slices

P8 proceeds through contract baseline, machine contracts, durable ingress, PlanningRun orchestration, worker reliability, runtime composition, complete API, host authorization, release packaging, operations, optional frontend isolation, Extension SDK contract, Runtime SPI/Registry, Enterprise Extension template/conformance, Developer Kit assembly, a synthetic vertical Gate and an independent exit audit. Exact ownership and dependencies live in `MILESTONE-P8` and TASK-P8-00～17.

P8-16 synthetic evidence proves Headless+Extension contract-to-publication engineering behavior only. P7 independently proves reality gap, Planner usefulness and capacity on authorized real inputs. Production release requires both exit gates plus the total-specification Production Gate; no document in P8 closes that requirement early.

Unimplemented advanced scheduling capabilities remain explicit `UNSUPPORTED_CAPABILITY` responses and are not prerequisites for packaging this stable Headless baseline. A capability may use the SDK only when the exposed extension point is sufficient and it supplies independent validation; otherwise it requires a normal Core ADR/Task. Neither path may fork the API or core state semantics.

## 8. Current-state disclaimer

The repository now exposes 34 OpenAPI operations: the preceding 29 remain byte-compatible at the operation-object level and P8-07 adds exactly five Headless PlanningRun operations. P8-03 formed the strict canonical consumer and durable Snapshot/PlanningProblem transaction; P8-04 added durable PlanningRun orchestration; P8-05 added Worker execution, independent validation, checkpoint recovery and one ScheduleVersion application; P8-06 formed the single Runtime composition; P8-07 connects these pieces through bounded canonical-only HTTP and a checked-in OpenAPI snapshot. The default/Production identity path remains fail closed. Real host identity, Production deployment, Extension SDK/Registry, Enterprise Extension template, Developer Kit, packaging and runbooks remain planned. Only capabilities whose owning Task and evidence are terminal may be described as production-ready runtime behavior.
