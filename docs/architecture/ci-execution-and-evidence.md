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

## Enterprise Runtime image evidence

The shared image step also runs `infra/enterprise/bootstrap/verify_container.py` against that exact image. Its required `ci-enterprise-image-bootstrap.json` is sealed by both selected routes and binds packaging SHA, image/tar identity, bootstrap template hashes and sanitized container outcomes. Backend suites include configuration/Secret negative tests; type checks include the bootstrap. Synthetic keys and fixtures remain in temporary directories outside uploaded evidence, and only safe result fields are retained. The driver checks real read-only mounts, fail-before-client behavior, local Extension loading, Compose interpolation and saved-layer canaries; it does not claim a complete offline package or live business deployment.

The selected current solver/runtime job and the explicit phase-audit validation job share one immutable enterprise image build/upload step. Backend checks include `tests/enterprise` and the image builder/probe type checks. `actions: read` permits downloading the exact historical Runtime artifact named in `infra/enterprise/image-inputs.v1.json`; its archive and payload hashes are mandatory. Expired inputs fail closed, with explicit same-hash retained archive support for local builds.

The producer seals `ci-enterprise-image.json`, its raw image scan and CycloneDX SBOM. The image report binds the current packaging commit, distinct Runtime source identity, image ID and exported tar SHA-256. Building an image and probing its entrypoints does not establish live deployment or Production security approval.

The roughly 459 MB image tar exceeds the canonical collector's per-entry limit. It is uploaded separately as `plantnexus-enterprise-runtime-image-<run_id>` with only the exact tar and checksum sidecar, after a successful build and before the producer seal. This required step cannot silently skip missing files. It deliberately uses a separate artifact prefix: the existing JSON/JUnit collector and its size limits remain unchanged. Consumers must first verify the exact run/SHA through the canonical Provider manifest, then verify the separate artifact's run identity and download digest and the tar against the sealed image report before loading it. A separate binary download alone is insufficient evidence. Build contexts, caches and raw build logs are excluded from that upload.

The required GitHub Actions check remains `validate`. Execution selection is global: it applies to every change, independently of the phase that originally introduced a module. The workflow and `scripts/ci_execution.py` define the executable contract.

| Change or request | Selected checks |
| --- | --- |
| Proven public Markdown only | Public documentation validation |
| Only added/modified regular `.ts`, `.tsx`, `.css` files under frontend src/tests/e2e | Preflight and current frontend regression |
| Backend, shared configuration, dependencies, scripts, workflow, unknown paths, renames, deletions, empty or untrusted diff | Preflight, backend suites, frontend regression, current solver/runtime contracts and XS benchmark, non-Production operations |
| Manual `phase_audit=true` | Preflight, backend with explicit repository phase suites, operations, independent phase audit (including frontend and contract checks) |

The initial narrow route deliberately stops at proven frontend edits. There is no backend-module test selector. A Markdown extension does not authorize an agent to treat a business-contract change as low risk; policy risk assessment remains separate from machine file routing.

The versioned execution plan records base/head identity, selected jobs, expected results, artifact prefixes and its SHA-256. `validate` recomputes that plan from the checked-out commit and event inputs, compares the uploaded plan, then checks every selected job and evidence seal. Missing, failed, cancelled or skipped selected jobs fail the required check. Unselected jobs must be skipped. An unidentified head is rejected; an unavailable base expands current coverage.

Each producer seals authoritative reports only after its commands succeed. Seals bind commit, run ID, run attempt, Python/OS, workflow and lockfile digests, and report digests. Seal v2 identifies each report by its canonical path under `build/`, resolved within its own producer artifact; identically named validation and benchmark files remain distinct. The aggregator downloads same-run artifacts and verifies their identity, bytes, successful JSON/JUnit and nonempty test execution. Dependency caches accelerate installation; they never stand in for test results. Cross-commit result caching is not supported.

Ordinary backend collection no longer appends historical P5/P6 evidence suites implicitly. `--phase-audit` explicitly opts into those suites; individual test paths can still be requested directly. Current contract checks retain independent Validator, solver correctness, deterministic replay, authorization and isolation checks. Normal frontend validation runs component tests, browser tests and both builds once. Historical frozen replay and corrective/requalification/Exit audit run only on explicit dispatch.

In the phase audit, a single P8 JUnit report feeds corrective, requalification and Exit consumers. Generic operations reports come from the same-run operations job, and are verified before consumption. Independent fresh procedures inside Gate implementations remain intact; they are not replaced by cached verdicts. An audit remains a candidate revalidation and can reject changed frozen boundaries; successful current regression does not claim a new phase Exit verdict.

The Provider collector uses a new run's plan to select required jobs and artifacts and independently verifies aggregate/seal/report consistency. Runs without a plan retain the old FULL evidence contract. If ordinary and manually dispatched audit runs share a SHA, use the collector’s `--run-id` to select the intended run explicitly; the default rejects ambiguity, and selection never relaxes SHA, required-check or failure checks. Exact SHA, required GitHub app/context, expiry, ZIP safety and manifest digests remain required. Failure history is retained. Product assertions are never rerun automatically until green. Provider transport reads retry only explicit transient network/502/503/504 errors, at most three attempts, with recorded retry classifications. Authentication failures, invalid JSON, failed checks and product assertions do not retry. Automatic job-attempt retry and cross-attempt evidence mixing are not supported.

A manual run may supply `base_sha`; leaving it empty selects all current checks. `phase_audit` defaults to false. No Production deployment, credentials or product settings are introduced by this workflow.

The retained operations target builds its declared historical Runtime. In ephemeral Actions checkouts only, CI stages that target’s packaging README and records both digests, then restores the current README after the drill. All other Runtime source, Schema, migration, lock and build-policy drift is rejected before staging. This preserves the frozen build identity without treating later delivery prose as a product-source change. It does not update the target or certify a changed Runtime.
