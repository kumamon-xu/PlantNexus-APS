---
doc_id: DOC-ARCH-013
title: CI execution and evidence
status: active
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [2, 58, 89, 98, 99, 100, 101]
last_reviewed: 2026-09-14
---

# CI execution and evidence

The required shared enterprise-image step additionally runs `infra/enterprise/scripts/verify_container.py` and seals `ci-enterprise-image-operations.json`. It executes the nine POSIX Shell entrypoints with host Python/uv/npm denied, binds exact image/tar and deployment payload fingerprints, and verifies migration idempotence, dependency recovery, PostgreSQL/Redis persistence, quiesced backup, isolated restore, same-image validated-slot rollback and fail-closed negative targets. Backup bytes, secrets and raw logs remain temporary and are never uploaded. This adds no Production, queue replay, final offline bundle or clean-server acceptance claim.

## Offline enterprise candidate evidence

The shared required enterprise-image step runs `scripts/enterprise_bundle.py build` and `infra/enterprise/bundle/verify_container.py`, sealing `ci-enterprise-image-bundle.json` and `ci-enterprise-image-bundle-container.json`. The candidate consumes that run's exact Runtime tar and SBOM, exports the pinned PostgreSQL/Redis images, inventories their scan/license results and verifies the safe archive, payload fingerprint and mapped deployment. A forced dependency lookup miss exercises real docker load without deleting unrelated images; this is explicitly not P8-28 clean-daemon acceptance. Host development tools and build/pull commands are denied during operator replay.

The large candidate and sidecar are uploaded separately as `plantnexus-enterprise-bundle-<run_id>`; canonical JSON/JUnit limits stay unchanged. Consumers bind exact run/commit through the canonical Provider manifest, verify the binary artifact digest, then the archive against the sealed bundle report. Candidate payloads remain in staging; final authority and Production claims are not emitted.


## Enterprise Runtime image evidence

The same required image step runs `infra/enterprise/compose/verify_container.py` and seals `ci-enterprise-image-compose.json`. It binds the exact image/tar and deployment payload hashes to dual-mode config/startup, named Worker and actual API/Worker descriptors, TLS readiness, offline formal Validator, migration/unready/image rejection and PostgreSQL/Redis volume persistence. External dependencies are represented by isolated synthetic fixtures; deployment networks have no egress and preloaded images use `pull_policy: never`. Only the build-side driver may explicitly acquire the already locked dependency images. Raw credentials, payloads, rendered host paths and logs remain outside artifacts. This is deployment engineering evidence, not a final offline bundle, clean-server acceptance or Production approval.

The shared image step also runs `infra/enterprise/bootstrap/verify_container.py` against that exact image. Its required `ci-enterprise-image-bootstrap.json` is sealed by both selected routes and binds packaging SHA, image/tar identity, bootstrap template hashes and sanitized container outcomes. Backend suites include configuration/Secret negative tests; type checks include the bootstrap. Synthetic keys and fixtures remain in temporary directories outside uploaded evidence, and only safe result fields are retained. The driver checks real read-only mounts, fail-before-client behavior, local Extension loading, Compose interpolation and saved-layer canaries; it does not claim a complete offline package or live business deployment.

The selected current solver/runtime job and the explicit phase-audit validation job share one immutable enterprise image build/upload step. Backend checks include `tests/enterprise` and the image builder/probe type checks. `actions: read` permits downloading the exact historical Runtime artifact named in `infra/enterprise/image-inputs.v1.json`; its archive and payload hashes are mandatory. Expired inputs fail closed, with explicit same-hash retained archive support for local builds.

A new nscd-specific component assessment is independent of the frozen unresolved OS policy. The producer records a fresh exact-image package/filesystem absence probe and its code hash in the sealed image report. Only CVE-2026-89092 on the exact sibling glibc packages may use that evidence; missing or mismatched proof, an installed nscd component, changed finding identity or a fixable version still fails. The original unresolved OS risks and Production rejection remain visible.

The current image producer records the versioned `nscd-advisory.v2.json` reassessment for CVE-2026-89092 severity enrichment from UNKNOWN to MEDIUM, together with the fresh exact-image component absence proof. The old v1 assessment and unresolved OS risk inventory remain unchanged; missing/changed provenance, other finding changes or available fixes still block the step. Failed SHA evidence is retained and is never rerun to green.

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

## 企业 clean acceptance 必需证据

solver_validation/full_validation 的企业镜像共享步骤在封包后执行独立 clean consumer，生成 ci-enterprise-image-acceptance.json。seal 与 aggregate 均要求它与 ci-enterprise-image-bundle.json 成对存在且唯一，核对 exact code SHA、候选 archive/payload/manifest/checksums 摘要、三镜像身份、双模式三十项 PASS 和 READY。development、skip/BLOCKED、入口未验证、非空 store、缺失/重复报告均拒绝；P8-27 Provider 不替代 P8-28 的新证据。
