---
doc_id: ADR-0010
title: PlanningProblem v2 合同演进
status: accepted
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [13, 14, 24, 25, 26, 28, 89, 97, 103]
last_reviewed: 2026-08-20
---

# ADR-0010 — PlanningProblem v2 合同演进

Status: accepted

Date: 2026-08-20

Decision owners: project governance；TASK-P2-01 user authorization

Requirement/NFR/ENG: REQ-002、REQ-003、REQ-004、REQ-009、REQ-012；NFR-COR-001、NFR-DET-001、NFR-TRC-001；ENG-SOL-001、ENG-ERR-001、ENG-VER-001

Supersedes: none；extends ADR-0003 without changing its solver-neutral boundary

## Context

Published `planning-problem.v1` can deterministically project active operations, candidate durations, active-active precedence, RUNNING remainder and calendar intervals. It cannot carry the inputs needed by C-008 and OBJ-001: active HARD/SOFT locks, explicit demand due/priority facts, or a completed predecessor's authoritative completion instant for a completed-to-active lag. It also exposes only resource IDs, which is insufficient for a backend and an independent Validator to consume the same capacity-1 resource/topology/calendar/capability facts.

Silently recovering those facts in a CP-SAT backend would violate ADR-0003 and make Problem replay incomplete. Supplying an implicit priority of one would guess OPEN-006 policy; changing `planning-problem.v1` in place would invalidate its published bytes and P1 replay vectors.

## Decision

1. Publish `planning-problem.v2` as a new, non-interchangeable document in additive schema set `2.3.0`. Preserve the v1 Schema, sample, builder, hash projection, public entry point and fixed replay bytes exactly.
2. Keep both versions JSON-serializable, deterministic and solver-neutral. No ORM, API, persistence or OR-Tools object may enter either Problem value.
3. V2 carries explicit `delivery_demands`. Due time and its source lineage are copied from the immutable Snapshot. Priority is a positive integer weight plus explicit source system/version/record ID supplied to the v2 builder. The builder rejects missing, extra, boolean, non-positive or unversioned priority facts; it never inserts a business default. Production use remains blocked by OPEN-006/015 until authority is closed. Versioned synthetic policy values may be used only as Simulation evidence.
4. V2 replaces `resource_ids` with complete capacity-1 resource facts: stable identity/code/type/status, Factory→Workshop→Line→Group topology, calendar, capabilities and explicit `capacity=1`. The value `1` implements the already accepted V1 primary-resource boundary; it is not inferred from a synthetic distribution and does not enable C-012 secondary capacity.
5. V2 carries active future locks as first-class records. A referenced lock is active for the Problem when `end_at_utc > horizon_start_utc`; expired locks are historical and excluded. Active locks retain type, operation/resource, full interval and source lineage even when their interval lies partly or wholly outside the configured horizon, so a later model/Validator can report the real conflict instead of losing the fact. HARD and SOFT semantics remain distinct; this Task does not implement either in a Solver or OBJ-002.
6. COMPLETED operations remain outside the future operation set. When a completed predecessor points to an active successor, V2 retains the edge and adds one immutable historical completion anchor containing the execution fact ID, resource, actual start/end and source lineage. Completed-to-completed edges are historical and excluded. Active-to-completed edges are rejected as an inconsistent future boundary rather than reordered or ignored.
7. V2 hash identity uses `canonical-json.v1` and `planning-problem-hash-projection.v2`. The projection covers the schema/document/builder/hash-projection versions, Snapshot identity, explicit priority lineage, complete resources, operations/options, historical anchors, active locks, edges, calendar intervals, capabilities and tick/horizon configuration; only the self hash and non-contract runtime noise are excluded.
8. `build_planning_problem` and all v1 constants/functions remain the legacy default. V2 is opt-in through version-specific types/functions until a later authorized application Task migrates a consumer. Backends may consume only a verified versioned Problem and may not reconstruct omitted facts from Snapshot or policy side channels.

## Alternatives considered

- Extend v1 in place: rejected because it would reinterpret a published contract and invalidate P1 fingerprints.
- Let the backend read Snapshot, locks or policy separately: rejected because the replayed Problem would no longer be the complete solver input.
- Default every missing priority to one: rejected because OPEN-006 is unresolved and Schema defaults are forbidden.
- Copy all completed history into every Problem: rejected because only completed predecessors that constrain active successors belong to the future model boundary.
- Clip lock/calendar timestamps to the horizon: rejected because clipping changes authoritative facts and hides infeasibility or validation evidence.

## Consequences

- Schema set metadata, human contracts, data dictionary, tests and provider machine evidence advance to `2.3.0`; Import/Snapshot/Error/rule document versions remain unchanged.
- There is no database or data migration because PlanningProblem is not persisted. Existing v1 consumers continue unchanged; v2 consumers must select the new builder and provide complete priority facts explicitly.
- Problem size grows by demand/resource/lock/anchor records. TASK-P2-01 records counts and hashes only; real correctness/quality/runtime/memory comparison begins when TASK-P2-12 has a Solver and fixed Scenario baseline.
- C-008 and OBJ-001 input contracts become formed, while Solver, PlanningPolicy, ScheduleValidator, feasibility, objective and Benchmark evidence remain planned.
- Any future change to these fields, active-lock selection, completed-edge projection, canonical ordering or priority authority requires a new Problem/builder/hash version and ADR/replay/benchmark review.

## Rollback / Revisit gate

Before a downstream v2 consumer exists, rollback may remove the v2 Schema/sample/code and restore global schema set metadata to `2.2.0`; v1 artifacts and hashes remain untouched. Once a v2 artifact is consumed, it becomes immutable history and rollback must publish a later version with an explicit compatibility/migration rule.

Revisit this decision only with evidence that the contract lacks a fact required by C-001～C-011/OBJ-001, that field authority has changed through a closed PROD_OPEN record, or that fixed Scenario replay shows a material correctness/size/performance problem. Solver-specific convenience alone is not a revisit gate.
