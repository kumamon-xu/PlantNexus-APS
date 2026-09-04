---
doc_id: DOC-ARCH-010
title: Headless Productization and Platform Integration
status: active
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [3, 4, 9, 10, 12, 15, 63, 65, 66, 67, 68, 84, 85, 97, 105, 106, 107, 109, 112, 113]
last_reviewed: 2026-09-04
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
 APS API -> contract/data validation -> immutable Snapshot/Problem
                    |                         |
                    |                         v
                    +-> durable PlanningRun -> Solver Worker
                                              |
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

The ingress sequence is fail closed:

1. authenticate and derive host principal/scope;
2. validate media type, size, contract name/version and machine schema;
3. validate tenant/factory scope, authority references and idempotency;
4. run the existing business Data Validation boundary;
5. persist immutable source payload identity and derived Snapshot/Problem lineage;
6. accept an asynchronous command or return a stable, sanitized error.

Unknown versions, missing authority, cross-scope identifiers, duplicate idempotency conflicts, invalid lineage and business-invalid records are rejected. The service must not guess, silently coerce to a third-party format, or fall back to a reference adapter.

CSV/XLSX/reference adapters and synthetic generators remain allowed only as internal or non-Production producers of canonical data. Before reaching scheduling logic, their output must traverse the same canonical contract and validation behavior used by the host.

## 3. Runtime ownership

The API process owns transport, authentication hooks, request validation and application-port invocation. The application layer owns use-case orchestration and transaction boundaries. Repositories own APS persistence behind ports. The worker owns durable asynchronous execution and may call the same domain/application capabilities without changing their semantics. The formal Validator remains independent from the solver.

APS persistence is private to APS and migrated by APS release artifacts. Host systems receive stable identifiers, statuses, errors and read models through the API. A database connection, shared ORM entity or direct queue message is not an integration contract.

Long-running planning uses a durable `PlanningRun` request and observable status. Timeout, retry, cancellation, duplicate delivery and worker restart must preserve idempotency and immutable evidence. The existing PlanningRun, ScheduleVersion, ExportJob and replanning state semantics remain authoritative until a separately approved Task/ADR changes them.

## 4. Identity, authority and audit

The host authenticates to the APS boundary using a later approved mechanism and supplies or enables derivation of a stable subject and factory scope. APS maps that context through an adapter and independently enforces authorization at every command/query. Client-supplied scope is never trusted by itself.

Audit evidence binds subject, action, scope, canonical payload fingerprint, source/version references, correlation/idempotency key, resulting entity/version and outcome. Secrets and raw Production payloads do not belong in logs or CI artifacts. Concrete providers, retention and named Production authorities remain open until their closure records exist.

## 5. Dual delivery without backend forks

The owning platform may render every APS result in its own UI. An optional industry frontend may later package workflows such as input review, run monitoring, Gantt views, comparison and export, but is only another API consumer. It must not require server behavior unavailable to the host and must use generated/versioned client contracts rather than copy domain logic.

Frontend release cadence may differ from backend cadence if the API compatibility window is honored. Deployment may omit the optional frontend entirely; headless API, worker, database/migrations and operations controls remain a complete backend distribution.

## 6. P8 delivery slices

P8 proceeds through contract baseline, machine contracts, durable ingress, PlanningRun orchestration, worker reliability, runtime composition, complete API, host authorization, release packaging, operations, optional frontend isolation, a synthetic vertical Gate and an independent exit audit. Exact ownership and dependencies live in `MILESTONE-P8` and TASK-P8-00～13.

P8-12 synthetic evidence proves contract-to-publication engineering behavior only. P7 independently proves reality gap, Planner usefulness and capacity on authorized real inputs. Production release requires both exit gates plus the total-specification Production Gate; no document in P8 closes that requirement early.

Unimplemented advanced scheduling capabilities remain explicit `UNSUPPORTED_CAPABILITY` responses and are not prerequisites for packaging this stable Headless baseline. Each later capability must arrive through its own compatible contract/implementation/test Task without forking the API or core state semantics.

## 7. Current-state disclaimer

At P8 planning activation the repository still exposes the previously documented 29-operation API surface and unavailable default application adapters. Canonical submission, durable orchestration, host identity, packaging and runbooks are planned, not implemented. This architecture is a normative target and must never be described as current runtime capability before its owning Task and evidence are done.
