---
doc_id: DOC-ARCH-013
title: CI execution and evidence
status: active
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [2, 58, 89, 98, 99, 100, 101]
last_reviewed: 2026-09-11
---

# CI execution and evidence

The required GitHub Actions check remains `validate`. Execution selection is global: it applies to every change, independently of the phase that originally introduced a module. The workflow and `scripts/ci_execution.py` define the executable contract.

| Change or request | Selected checks |
| --- | --- |
| Proven public Markdown only | Public documentation validation |
| Only added/modified regular `.ts`, `.tsx`, `.css` files under frontend src/tests/e2e | Preflight and current frontend regression |
| Backend, shared configuration, dependencies, scripts, workflow, unknown paths, renames, deletions, empty or untrusted diff | Preflight, backend suites, frontend regression, current solver/runtime contracts and XS benchmark, non-Production operations |
| Manual `phase_audit=true` | Preflight, backend with explicit repository phase suites, operations, independent phase audit (including frontend and contract checks) |

The initial narrow route deliberately stops at proven frontend edits. There is no backend-module test selector. A Markdown extension does not authorize an agent to treat a business-contract change as low risk; policy risk assessment remains separate from machine file routing.

The versioned execution plan records base/head identity, selected jobs, expected results, artifact prefixes and its SHA-256. `validate` recomputes that plan from the checked-out commit and event inputs, compares the uploaded plan, then checks every selected job and evidence seal. Missing, failed, cancelled or skipped selected jobs fail the required check. Unselected jobs must be skipped. An unidentified head is rejected; an unavailable base expands current coverage.

Each producer seals authoritative reports only after its commands succeed. Seals bind commit, run ID, run attempt, Python/OS, workflow and lockfile digests, and report digests. The aggregator downloads same-run artifacts and verifies their identity, bytes, successful JSON/JUnit and nonempty test execution. Dependency caches accelerate installation; they never stand in for test results. Cross-commit result caching is not supported.

Ordinary backend collection no longer appends historical P5/P6 evidence suites implicitly. `--phase-audit` explicitly opts into those suites; individual test paths can still be requested directly. Current contract checks retain independent Validator, solver correctness, deterministic replay, authorization and isolation checks. Normal frontend validation runs component tests, browser tests and both builds once. Historical frozen replay and corrective/requalification/Exit audit run only on explicit dispatch.

In the phase audit, a single P8 JUnit report feeds corrective, requalification and Exit consumers. Generic operations reports come from the same-run operations job, and are verified before consumption. Independent fresh procedures inside Gate implementations remain intact; they are not replaced by cached verdicts. An audit remains a candidate revalidation and can reject changed frozen boundaries; successful current regression does not claim a new phase Exit verdict.

The Provider collector uses a new run's plan to select required jobs and artifacts and independently verifies aggregate/seal/report consistency. Runs without a plan retain the old FULL evidence contract. Exact SHA, required GitHub app/context, expiry, ZIP safety and manifest digests remain required. Failure history is retained. Product assertions are never rerun automatically until green. Provider transport reads retry only explicit transient network/502/503/504 errors, at most three attempts, with recorded retry classifications. Authentication failures, invalid JSON, failed checks and product assertions do not retry. Automatic job-attempt retry and cross-attempt evidence mixing are not supported.

A manual run may supply `base_sha`; leaving it empty selects all current checks. `phase_audit` defaults to false. No Production deployment, credentials or product settings are introduced by this workflow.
