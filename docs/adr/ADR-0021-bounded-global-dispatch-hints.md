---
doc_id: ADR-0021
title: Bounded Global CP-SAT Dispatch Hints
status: accepted
spec_version: 0.3.0
phase: P9
normative: true
source_sections: [14, 24, 97, 104, 116]
last_reviewed: 2026-09-20
---

# ADR-0021 — Bounded Global CP-SAT Dispatch Hints

## Context

P9-09 exposed a valid but poor incumbent on the immutable v1 M holdout (14940 weighted tardiness versus reference 3900). The user explicitly authorized general Solver correction and a new independent holdout. The v1 failure and its original limits remain regression evidence.

## Decision

Amend the historical P2 prohibition on initial hints for Global delivery search. A deterministic backend-local dispatch portfolio supplies only `CpModel.add_hint` values to the existing complete model and its OBJ-001 auxiliary variables. It performs no native solve, imports no Simulation/Reference scheduler, and never returns a product candidate. The normal single native solve and fresh independent Validator remain authoritative. UNKNOWN still has no candidate even when hints exist.

The versioned `global-dispatch-hints.v1` search policy uses earliest finish, due date, shortest duration, priority/due date and release order; stable IDs break ties. It selects the lowest exact weighted tardiness complete placement. Calendar/capacity gaps are jumped rather than scanning horizon ticks. Work is bounded to 128 operations, 4096 options/edges/calendar intervals each, and 200000 dispatch work steps across the portfolio. Exhausted or ineligible inputs simply receive no hint. RUNNING operations, any locks, historical anchors or maximum-lag edges are ineligible; the full existing model still solves them unchanged.

No constraints, objectives, parameter mapping, solver dependency, backend protocol or public identity version change. Code commit identifies the compatible search implementation. Feasibility-only and lexicographic replan paths are unchanged. No reference fallback, decomposition, rolling strategy, objective cap or hidden time-limit increase is introduced.

## Validation and rollback

Prove hint application leaves variables/constraints/objective unchanged; test deterministic permutation, calendar/transport/release/material handling, unsupported hint shapes, work cap, and honest non-candidate states. Replay existing Solver Golden/Scenario/Property/Mutation contracts and the exposed v1 regression under original limits. Seal v2 independent seeds before tuning, freeze its development budget before first holdout access, and require the unchanged quality gate. Windows and exact Linux Provider evidence remain required. Revert only the hint call/module on regression, preserving failed observations, sealed catalogs and this decision record.
