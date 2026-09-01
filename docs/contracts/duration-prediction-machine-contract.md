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

Capability status: `AI_DURATION_PREDICTION = DEFERRED / CONTRACT_ONLY / NO_RUNTIME`

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

`pii_fields_present=false` and `target_fields_present=false` are constants. Actual/target duration, completion, label/future data and direct personal identifiers are rejected by the semantic checker. This is an envelope contract only: TASK-P6-03 must publish the real dataset/feature policy and cannot treat these sample values as a feature distribution or training authority.

## 4. Model and evaluation boundary

ModelManifest binds an opaque artifact digest, dataset manifest, feature schema, code revision, exact dependency lock, configuration, algorithm version, deterministic replay reference, cutoff, scope, human decision reference and standard-duration rollback reference. It contains no `state`, promotion/deployment status or runtime endpoint. `SIMULATION_EVALUATION_ONLY` is use evidence, not a model lifecycle state or Production approval.

EvaluationReport carries exact model/dataset/split/baseline/code/config/privacy lineage and typed aggregate metrics/slices. Metric units/directions are fixed and ratios stay within `[0,1]`. `gate_assessment.decision=NOT_EVALUATED_BY_P6_02` and `thresholds_embedded=false`; the planned P6-05 Gate and all confidence/evaluation thresholds remain unformed. P6-02 does not train, evaluate or promote a model—the sample only verifies the carrier shape and lineage.

## 5. Prediction and fallback semantics

DurationPrediction always includes `unit=SECONDS`, `p50_seconds`, `p90_seconds`, `confidence`, `model_version`, `feature_schema_version`, `fallback_reason`, selected source/seconds, full standard-duration authority and exact Feature/Model/Evaluation/Policy references. A non-null candidate is atomic: all three of p50/p90/confidence are present, positive/finite, confidence is in `[0,1]`, and `p90_seconds >= p50_seconds`.

`fallback_reason=NONE` is the only case that may select `MODEL_CANDIDATE`, and its selected seconds must equal p50. Every other registered reason must select the exact `STANDARD_DURATION` seconds carried with `duration_source`, `source_version`, source record ID and fingerprint:

`PREDICTION_MISSING`, `PROVIDER_UNAVAILABLE`, `PROVIDER_TIMEOUT`, `INVALID_QUANTILES`, `CONFIDENCE_MISSING`, `CONFIDENCE_INVALID`, `LOW_CONFIDENCE`, `MODEL_NOT_APPROVED`, `MODEL_OUT_OF_SCOPE`, `MODEL_VERSION_INCOMPATIBLE`, `FEATURE_VERSION_INCOMPATIBLE`, `DATASET_VERSION_INCOMPATIBLE`, `CONTRACT_VERSION_INCOMPATIBLE`, `ARTIFACT_DIGEST_MISMATCH`, `PROVENANCE_INCOMPLETE`, `EVALUATION_GATE_NOT_PASSED`, `DRIFT_GATE_DISABLED`, `AUTHORITY_NOT_ESTABLISHED`, `PRIVACY_GOVERNANCE_FAILED`.

Unknown reason/unit/version is rejected. A malformed candidate such as p90 below p50 is never admitted as valid evidence; a runtime consumer must instead create a new valid fallback carrier with candidate fields absent and the applicable registered reason. If authoritative standard duration is itself missing or invalid, the option fails through the existing data-error path—this contract defines no guessed value.

## 6. Negative vectors and machine evidence

Five published mutation descriptors isolate future-data leakage, missing dataset lineage, reversed quantiles, mixed `2.8.0/2.9.0` payload and unknown fallback. [`p6_duration_contract_check.py`](../../scripts/p6_duration_contract_check.py) applies them without side effects, validates positive round trips/fingerprints/cross-lineage, and emits deterministic `p6-duration-contract-report.v1`.

The report requires 10/10 checks, 4 schemas, 5 positive samples, 5 negative vectors, 20 schema rejections, 7 semantic/lineage rejections, 5 tamper rejections and `issues=[]`. It also freezes the 70 pre-P6 Schema/sample artifacts under POSIX-path+LF manifest `sha256:ada3e2a0498bb5b42ef81aba01693a949cd41deac229ebad8ea6f9334e901c64`, `uv.lock` at `sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`, five migrations at `sha256:37a43d34e7db40456c314e428e985f86a62a051d1a36c0d2d5570aaa46bb3425`, and head `0005_replan_event_persistence`.

CI runs the checker as a non-skippable FULL step and uploads the report through the existing `build/validation/*.json` artifact path. `TEST-P6-PREDICTION-CONTRACT-001` covers strict schema, round-trip, property, fallback, leakage, tamper and lineage behavior; `TEST-CONTRACT-001` registers the additive documents globally.

## 7. Compatibility, authority and rollback

Schema set `2.9.0` is additive. All 70 earlier Schema/sample bytes and every earlier document-level `schema_set_version` remain unchanged; P3/P4 checkers now distinguish their historical carrier version from the current global metadata. A consumer selects these four exact v1 documents explicitly—there is no alias, coercion from `2.8.0`, permissive fallback enum or in-place rewrite.

This package does not implement a dataset, model, training, evaluation Gate, provider runtime, Planning ingress, API, migration, business state or Production authority. It cannot alter routing, resource compatibility, hard constraints, PlanningRun/ScheduleVersion/ExportJob state or weights. `AI_DURATION_PREDICTION` therefore remains DEFERRED.

Before any durable consumer exists, rollback may remove only these additive files and restore current metadata/indexes while preserving audit evidence. Once consumed, v1 bytes are immutable and semantic change requires a new document/set version; operational rollback disables prediction and selects authoritative standard duration, never overwrites model/evaluation/prediction evidence. TASK-P6-03 and later require separate authorization and a new Diff base.
