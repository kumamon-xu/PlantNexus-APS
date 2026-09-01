---
doc_id: DOC-CONTRACT-P6-DURATION-MACHINE
title: Duration Prediction Machine Contract v1
status: baseline
spec_version: 0.3.0
phase: P6
normative: true
source_sections: [15, 20, 83, 90, 98, 99, 100, 110, 111]
last_reviewed: 2026-09-01
---

# Duration Prediction Machine Contract v1

Contract status: `FORMED_SIMULATION_CONTRACT_V1` in additive schema set `2.9.0`

Human authority: [ADR-0016](../adr/ADR-0016-ai-duration-data-model-governance.md) and [Duration Prediction Governance Contract](duration-prediction-governance.md)

Capability status: `AI_DURATION_PREDICTION = DEFERRED / CONTRACT_V1 + SIMULATION_DATASET_V1 + BASELINE_MODEL_V1 + OFFLINE_GATE_READY + LOCAL_RUNTIME_V1 / NO_PLANNING_INGRESS`

## TASK-P6-06 local prediction runtime and exact fallback

`SIM-P6-DURATION-RUNTIME-001@1.0.0` / `SIM-ASSUMPTION-025` is the only approved runtime policy. Its content identity binds exact P6-04 model `1.0.0`, artifact/manifest, the P6-05 READY Gate/profile/measurement, schema set `2.9.0`, `SIMULATION/TEST`, caller-explicit UTC, the exact `9/10` confidence threshold, all 19 non-`NONE` fallback reasons, and bounded development-only resources. Recomputed-but-unapproved policy bytes, Production shape, unknown environment, missing Gate, model mismatch or incomplete authority fail closed.

The provider is an immutable in-process object with no network, external service, cache, persistence, global enablement or business-state side effect. A request supplies factory/operation/resource-option/resource IDs, predicted/as-of UTC, one strict FeatureRecord and a separately validated standard-duration authority. The standard carrier must be positive integer seconds with source/version/record/fingerprint and must match the same FeatureRecord option; the provider never mutates either input. Invalid standard authority prevents creation of a Prediction carrier.

After strict input/model/Gate/policy checks, the fixed P6-04 predictor returns p50/p90 and runtime computes the P6-05 exact interval-tightness confidence. Confidence at or above `9/10` admits `fallback_reason=NONE` and selects model p50. Missing/unavailable/timeout, invalid/non-finite quantiles or confidence, low confidence, model/scope/version, feature/dataset/contract, digest/provenance, Gate/drift, authority or privacy failure produces a fresh valid fallback carrier with candidate fields null and exact standard duration selected. Unknown exceptions are sanitized to `PROVIDER_UNAVAILABLE`; an unknown reason is never emitted.

Every carrier contains all existing P6-02 fields and exact Feature/Model/Evaluation/Policy lineage, then derives `prediction_id` and fingerprint from canonical content. Same input, explicit time and provider outcome replay byte-exactly; return-value mutation cannot poison later calls. The machine report performs 12 checks across eight tracked synthetic features, all 19 reasons, replay, timeout, tamper/version, privacy/authority, immutability, schema and development performance while reporting zero label semantic reads and no raw rows/features/source IDs.

The 50 ms per-call post-check, 16 KiB FeatureRecord, four features, one source, 32 KiB output, 256 measured/16 warmup, P95 20 ms and 16 MiB peak limits are fixed Simulation/Test safety evidence, not a Production SLA. No PlanningProblem, Solver, Validator, API/UI, state, promotion or monitoring consumer is formed; P6-07 and P6-08 remain separately authorized successors.

## TASK-P6-05 offline evaluation, confidence, and fallback Gate

`duration-evaluation-profile.v1` / `SIM-P6-OFFLINE-EVALUATION-001@1.0.0` binds the exact P6-03 dataset file/bundle/manifest and P6-04 model file/bundle/manifest/artifact/config, plus `SIM-ASSUMPTION-021` through `024`. It includes only validation and test labels, two rows per partition and operation family, with a hard train-label read limit of zero. Raw file digests are checked before semantic evaluation; held-out row identities, feature privacy/plane, model scope, authorization and all cross-lineage references then fail closed independently.

Metrics use exact rational arithmetic: MAE, nearest-rank median absolute error, and actual-at-or-below-p90 coverage. Overall model MAE must be strictly below the authoritative standard-duration MAE; each partition and operation-family MAE must be no worse. Coverage must be at least `3/4` overall and `1/2` per slice. Confidence is exactly `max(0,1-(p90-p50)/p50)` and every evaluated candidate must meet `9/10`. The frozen result is model/standard MAE `11/20` seconds, median error `10`, coverage `4/4`, minimum confidence `55/57`, and no slice regression, yielding `READY_FOR_SIMULATION_RUNTIME` with no gap.

Missing, invalid or low confidence; invalid quantiles; incompatible lineage; invalid model; timeout; unavailable model authority; or privacy failure selects the exact positive standard duration and one stable fallback reason. Invalid standard duration fails closed. The unchanged P6-02 `duration-evaluation-report.v1` remains the measurement carrier with `NOT_EVALUATED_BY_P6_02` and no embedded thresholds. P6-05 decisions live in strict `p6-duration-offline-gate-report.v1`, which contains aggregate metrics, checks and fallback evidence but no rows, labels or FeatureRecords. READY grants no model promotion, runtime, Planning or Production authority.

## TASK-P6-04 deterministic baseline model and replay

The trainer accepts exactly the P6-03 dataset bundle fingerprint `sha256:137ed52753f8decfcc2b0903c37e697f18c0e5a20369458aabddba6e7df81d98` and manifest fingerprint `sha256:d02f7818d4744e8a86205cfafe25efe1b39e2f1db6edc485a38e10aea8470bda`. It validates all eight rows and the exact feature contract but trains only the four `train` rows. Validation and test labels are never read by the fitting path. `standard_duration_seconds` and `operation_family` are active; `planned_quantity` and `setup_seconds` remain required, typed and range-checked zero-weight features.

`grouped-median-residual-baseline.v1` uses exact rational arithmetic, the per-operation-family median of `actual_processing_seconds - standard_duration_seconds`, half-away-from-zero rounding, and a 0.90 nearest-rank absolute training-residual margin. The fixed result has milling offset `-40/1`, turning offset `-45/2`, and p90 margin 20 seconds. There is no RNG, seed, host clock or new dependency; training time is the deterministic contract value `2026-09-01T09:00:00Z`.

`duration-baseline-artifact.v1` is a maximum-64-KiB `plantnexus-safe-canonical-json@1.0.0` data-only envelope. The loader rejects executable/pickle/joblib formats, symlinks, non-regular or oversized files, duplicate keys, non-finite values, non-canonical framing, unknown fields and every version/digest/config/dataset/dependency/code/scope mismatch. The existing ModelManifest binds the resulting artifact digest, exact dataset and feature contract, normalized-LF training-code identity, lock, configuration, algorithm, cutoff, scope, decision, rollback and replay reference. The writer validates and builds complete canonical bytes before same-directory fsync and atomic replace; a validation or replace failure preserves the previous target and leaves no partial file.

The replay proves two same-input trainings, one source-order permutation and eight sanitized `duration-baseline-estimate.v1` results. Those estimates deliberately carry `confidence_status=NOT_ESTABLISHED_BY_P6_04`, `evaluation_gate=NOT_EVALUATED_BY_P6_04` and `planning_authority=NONE`; they are not `duration-prediction.v1` carriers and have no promotion or runtime meaning. Provider artifacts may contain only the safe model, ModelManifest, sanitized replay and report—never raw source, dataset rows or labels. `p6-duration-model-report.v1` requires 10/10 checks, 14 mutation rejections, two atomic-failure rejections and `issues=[]`.

## TASK-P6-03 dataset builder and manifest

The executable builder accepts exactly `duration-dataset-source.v1` / `SIM-P6-DURATION-HISTORY@1.0.0` in `SIMULATION/TEST`, with synthetic true and Production binding/authorization false. Source authority, label authority, purpose/access, retention/deletion, split, feature, privacy and assumption profiles are exact allow-list values. Every source record and the order-normalized source document carry content-derived fingerprints. Unknown fields, duplicate JSON keys, non-finite values, mixed versions, sensitive/target fields and identity tampering fail closed.

Label eligibility is `status=COMPLETED`, `disposition=NORMAL`, and an explicit positive `actual_processing_seconds` with `decision_cutoff < observed <= available`. The builder has no start/end derivation path. RUNNING/IN_PROGRESS has no label and is excluded as `RUNNING_NOT_LABEL_ELIGIBLE`; COMPLETED/INTERRUPTED is excluded as `INTERRUPTED_NOT_LABEL_ELIGIBLE`. Standard duration and model output are forbidden as label sources.

The four frozen features are `planned_quantity/COUNT`, `setup_seconds/SECONDS`, `standard_duration_seconds/SECONDS`, and `operation_family/CATEGORY`. Each feature uses an identity transform and an availability time no later than the record decision cutoff. The FeatureRecord source is a deterministic `<label-source-id>-feature-context` pre-cutoff envelope with its own fingerprint; the full completed record fingerprint remains only on the dataset label, so future label content cannot enter feature-source identity. Output FeatureRecords remain byte-compatible with `duration-feature-record.v1`; the Schema-required profile/ref 021 is retained and ref 022 is additive. FeatureRecords contain neither PII nor target fields.

`group-safe-time-split.v1` uses label availability and `lineage_group_id`, with half-open train `[2026-07-01,2026-08-01)`, validation `[2026-08-01,2026-08-16)`, and test `[2026-08-16,2026-09-01)` UTC windows. The frozen correctness profile yields 4/2/2 rows and forbids a lineage group from crossing partitions. These dates and counts are `SIM-ASSUMPTION-022`, not a Production window, distribution or threshold.

Each dataset row, `duration-dataset-manifest.v1`, and `duration-dataset-bundle.v1` has canonical content identity. The manifest is compatible with the P6-02 ModelManifest reference shape and binds source/version/fingerprint, builder contract/code digest, schema/feature/label/privacy/split policy, plane/environment/factory, cutoff, partition/group/count and exclusion evidence. The atomic writer validates/builds first, writes canonical UTF-8 JSON in the target directory, fsyncs and replaces; failure preserves the old target and removes temporary bytes.

`p6-duration-dataset-report.v1` independently replays the P6-02 contract package, published source/bundle, FeatureRecord Schema, eligibility/split/as-of/provenance, canonical reordering, mutation matrix and atomic cleanup. Provider artifacts contain the safe report/manifest only—not source records or dataset rows. No model is trained or selected, and no evaluation, prediction runtime, Planning authority, P7 calibration or Production authority is formed.

## 1. Published package

| Document | Schema / stable URN | Positive sample | Purpose |
|---|---|---|---|
| DurationFeatureRecord v1 | [`duration-feature-record.schema.json`](../../schemas/json/duration-feature-record.schema.json) / `urn:plantnexus:aps:schema:duration-feature-record:v1` | [`duration-feature-record.v1.synthetic.json`](../../schemas/samples/duration-feature-record.v1.synthetic.json) | immutable as-of feature/source/transform evidence |
| DurationModelManifest v1 | [`duration-model-manifest.schema.json`](../../schemas/json/duration-model-manifest.schema.json) / `urn:plantnexus:aps:schema:duration-model-manifest:v1` | [`duration-model-manifest.v1.synthetic.json`](../../schemas/samples/duration-model-manifest.v1.synthetic.json) | immutable artifact/dataset/feature/code/dependency/config/replay/scope/decision lineage |
| DurationEvaluationReport v1 | [`duration-evaluation-report.schema.json`](../../schemas/json/duration-evaluation-report.schema.json) / `urn:plantnexus:aps:schema:duration-evaluation-report:v1` | [`duration-evaluation-report.v1.synthetic.json`](../../schemas/samples/duration-evaluation-report.v1.synthetic.json) | offline measurements bound to model/dataset/split/baseline/privacy evidence |
| DurationPrediction v1 | [`duration-prediction.schema.json`](../../schemas/json/duration-prediction.schema.json) / `urn:plantnexus:aps:schema:duration-prediction:v1` | [`candidate`](../../schemas/samples/duration-prediction.v1.candidate.synthetic.json) / [`fallback`](../../schemas/samples/duration-prediction.v1.fallback.synthetic.json) | advisory quantiles/confidence plus exact standard-duration selection evidence |

All four documents use Draft 2020-12, exact document/set/canonicalization versions, self-contained offline refs, no `default`, and `additionalProperties=false` for every typed object. The only admitted plane is `SIMULATION`; environment is Development/Test/Benchmark, `synthetic=true`, `production_binding=false`, `production_authorized=false`, and OPEN-010/011/014/015 must all remain visible. A v1 consumer rejects unknown fields, unknown versions, mixed set versions and any Production-shaped mutation.

## 2. Canonical identity and exact lineage

`canonical-json.v1` is UTF-8 JSON with object keys sorted, compact separators, finite JSON numbers and no self identity fields. Each document removes its own `*_id` and `*_fingerprint`, hashes the remaining projection with SHA-256, stores `sha256:<lower-hex>` and derives its ID from the same digest. Any allowed-field tamper without a refreshed identity fails; a refreshed identity still fails when cross-document references no longer match.

The bundle requires exact links:

- Prediction → FeatureRecord ID/fingerprint/schema and identical factory/operation/resource-option/resource;
- Prediction/Evaluation → ModelManifest ID/fingerprint/version/artifact digest;
- Evaluation → the ModelManifest dataset and feature schema, plus an independent split and standard-duration baseline;
- Prediction → Evaluation ID/fingerprint and the authoritative standard-duration source record/fingerprint present in FeatureRecord;
- FeatureRecord factory/resource must fall inside the ModelManifest scope.

References are evidence carriers, not proof that a future dataset, trained model, approval principal, retention policy or Production source exists. Placeholder Simulation references in the published sample are governed only by `SIM-ASSUMPTION-021`.

## 3. Feature record fail-closed rules

Every source record carries system/version/record identity, content fingerprint, observation time and availability time. Every feature carries a stable name, explicit value type/unit, source-record IDs, availability time and transform version. `observed_at <= available_at <= as_of_cutoff` is mandatory; every feature source must exist in the same record, feature names must be unique, and value/type must agree.

`pii_fields_present=false` and `target_fields_present=false` are constants. Actual/target duration, completion, label/future data and direct personal identifiers are rejected by the semantic checker. P6-03 has separately published the exact synthetic dataset/feature policy; P6-04 consumes only that allow-listed contract and four train rows. Neither package permits treating sample values as a real feature distribution or Production training authority.

## 4. Model and evaluation boundary

ModelManifest binds an opaque artifact digest, dataset manifest, feature schema, code revision, exact dependency lock, configuration, algorithm version, deterministic replay reference, cutoff, scope, human decision reference and standard-duration rollback reference. It contains no `state`, promotion/deployment status or runtime endpoint. `SIMULATION_EVALUATION_ONLY` is use evidence, not a model lifecycle state or Production approval.

P6-04 supplies one synthetic ModelManifest and safe artifact that satisfy this lineage envelope. It does not itself supply an EvaluationReport, confidence policy, approved threshold, prediction carrier, runtime endpoint or promotion decision; its p50/p90 baseline estimates are replay evidence only. P6-05 subsequently forms a separately authorized development-only evaluation/fallback Gate without changing those P6-04 bytes or granting runtime/promotion authority.

EvaluationReport carries exact model/dataset/split/baseline/code/config/privacy lineage and typed aggregate metrics/slices. Metric units/directions are fixed and ratios stay within `[0,1]`. `gate_assessment.decision=NOT_EVALUATED_BY_P6_02` and `thresholds_embedded=false` remain immutable carrier semantics: P6-05 preserves them and places its actual thresholds, fallback evidence and READY/NOT_READY decision in the separate strict offline Gate envelope. P6-02 itself does not train, evaluate or promote a model—the sample only verifies the carrier shape and lineage.

## 5. Prediction and fallback semantics

DurationPrediction always includes `unit=SECONDS`, `p50_seconds`, `p90_seconds`, `confidence`, `model_version`, `feature_schema_version`, `fallback_reason`, selected source/seconds, full standard-duration authority and exact Feature/Model/Evaluation/Policy references. A non-null candidate is atomic: all three of p50/p90/confidence are present, positive/finite, confidence is in `[0,1]`, and `p90_seconds >= p50_seconds`.

`fallback_reason=NONE` is the only case that may select `MODEL_CANDIDATE`, and its selected seconds must equal p50. Every other registered reason must select the exact `STANDARD_DURATION` seconds carried with `duration_source`, `source_version`, source record ID and fingerprint:

`PREDICTION_MISSING`, `PROVIDER_UNAVAILABLE`, `PROVIDER_TIMEOUT`, `INVALID_QUANTILES`, `CONFIDENCE_MISSING`, `CONFIDENCE_INVALID`, `LOW_CONFIDENCE`, `MODEL_NOT_APPROVED`, `MODEL_OUT_OF_SCOPE`, `MODEL_VERSION_INCOMPATIBLE`, `FEATURE_VERSION_INCOMPATIBLE`, `DATASET_VERSION_INCOMPATIBLE`, `CONTRACT_VERSION_INCOMPATIBLE`, `ARTIFACT_DIGEST_MISMATCH`, `PROVENANCE_INCOMPLETE`, `EVALUATION_GATE_NOT_PASSED`, `DRIFT_GATE_DISABLED`, `AUTHORITY_NOT_ESTABLISHED`, `PRIVACY_GOVERNANCE_FAILED`.

Unknown reason/unit/version is rejected. A malformed candidate such as p90 below p50 is never admitted as valid evidence; a runtime consumer must instead create a new valid fallback carrier with candidate fields absent and the applicable registered reason. If authoritative standard duration is itself missing or invalid, the option fails through the existing data-error path—this contract defines no guessed value.

## 6. Negative vectors and machine evidence

Five published mutation descriptors isolate future-data leakage, missing dataset lineage, reversed quantiles, mixed `2.8.0/2.9.0` payload and unknown fallback. [`p6_duration_contract_check.py`](../../scripts/p6_duration_contract_check.py) applies them without side effects, validates positive round trips/fingerprints/cross-lineage, and emits deterministic `p6-duration-contract-report.v1`.

The report requires 10/10 checks, 4 schemas, 5 positive samples, 5 negative vectors, 20 schema rejections, 7 semantic/lineage rejections, 5 tamper rejections and `issues=[]`. It also freezes the 70 pre-P6 Schema/sample artifacts under POSIX-path+LF manifest `sha256:ada3e2a0498bb5b42ef81aba01693a949cd41deac229ebad8ea6f9334e901c64`, `uv.lock` at `sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`, five migrations at `sha256:37a43d34e7db40456c314e428e985f86a62a051d1a36c0d2d5570aaa46bb3425`, and head `0005_replan_event_persistence`.

CI runs the checker as a non-skippable FULL step and uploads the report through the existing `build/validation/*.json` artifact path. `TEST-P6-PREDICTION-CONTRACT-001` covers strict schema, round-trip, property, fallback, leakage, tamper and lineage behavior; `TEST-CONTRACT-001` registers the additive documents globally.

P6-03 and P6-04 add separate non-skippable FULL checks for the exact dataset and model/replay packages. `TEST-P6-MODEL-REPLAY-001` covers train-only selection, deterministic/property replay, safe serialization/load, artifact/config/dataset/dependency/code/scope mutation rejection, invalid output, atomic replacement and provider data minimization without changing any P6-02 Schema/sample bytes.

## 7. Compatibility, authority and rollback

Schema set `2.9.0` is additive. All 70 earlier Schema/sample bytes and every earlier document-level `schema_set_version` remain unchanged; P3/P4 checkers now distinguish their historical carrier version from the current global metadata. A consumer selects these four exact v1 documents explicitly—there is no alias, coercion from `2.8.0`, permissive fallback enum or in-place rewrite.

The separately authorized P6-03/P6-04 packages implement one synthetic contract-correctness dataset and one deterministic baseline model/training replay; those packages do not themselves implement an evaluation Gate or confidence policy. P6-05 adds the separate development-only offline evaluation/fallback Gate but does not itself grant runtime authority. P6-06 subsequently adds the explicit local Simulation/Test provider described above, without Planning ingress, API, migration, business state or Production authority. None can alter routing, resource compatibility, hard constraints, PlanningRun/ScheduleVersion/ExportJob state or weights. `AI_DURATION_PREDICTION` therefore remains DEFERRED with `LOCAL_RUNTIME_V1 / NO_PLANNING_INGRESS`.

The v1 contract bytes consumed by P6-03/P6-04/P6-05/P6-06 are immutable; semantic change requires a new document/set or artifact/policy version. Runtime rollback disables/removes the local provider and keeps authoritative standard duration while preserving dataset/model/evaluation/prediction/decision evidence. TASK-P6-07 and later require separate authorization and a new Diff base.
