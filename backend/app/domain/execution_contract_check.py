"""Emit machine-checkable TASK-P4-02 execution-contract evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tomllib
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource
import yaml

from app import SCHEMA_VERSION
from app.domain.execution_contracts import (
    CHANGE_REPORT_VERSION,
    EXECUTION_EVENT_VERSION,
    EXECUTION_SIMULATION_MANIFEST_VERSION,
    EXPORT_JOB_VERSION,
    EXPORT_MANIFEST_VERSION,
    PLANNING_POLICY_VERSION,
    P4ContractError,
    REPLAN_REQUEST_VERSION,
    SCHEMA_SET_VERSION,
    SCHEDULE_VERSION,
    SOLVER_REPORT_VERSION,
    canonical_contract_bytes,
    change_report_fingerprint,
    contract_fingerprint,
    event_stream_fingerprint,
    execution_event_fingerprint,
    export_job_fingerprint,
    export_manifest_fingerprint,
    freeze_policy_fingerprint,
    p4_document_version,
    replan_request_fingerprint,
    require_p4_document,
    schedule_content_fingerprint,
    simulation_manifest_fingerprint,
    solver_report_fingerprint,
    validate_p4_bundle,
)


REPORT_VERSION = "p4-machine-contract-report.v1"
TASK_ID = "TASK-P4-02"
DIFF_BASE = "4026597ab1015b5ea3a89d241f0d12b5b481dee3"

_SCHEMA_SAMPLE_PAIRS = (
    (
        "execution-event.schema.json",
        "execution-event.v1.synthetic.json",
        "execution_event_version",
        EXECUTION_EVENT_VERSION,
    ),
    (
        "replan-request.schema.json",
        "replan-request.v1.synthetic.json",
        "replan_request_version",
        REPLAN_REQUEST_VERSION,
    ),
    (
        "change-report.schema.json",
        "change-report.v1.synthetic.json",
        "change_report_version",
        CHANGE_REPORT_VERSION,
    ),
    (
        "execution-simulation-manifest.schema.json",
        "execution-simulation-manifest.v1.synthetic.json",
        "execution_simulation_manifest_version",
        EXECUTION_SIMULATION_MANIFEST_VERSION,
    ),
    (
        "planning-policy.v2.schema.json",
        "planning-policy.v2.synthetic.json",
        "planning_policy_version",
        PLANNING_POLICY_VERSION,
    ),
    (
        "solver-report.v2.schema.json",
        "solver-report.v2.synthetic.json",
        "solver_report_version",
        SOLVER_REPORT_VERSION,
    ),
    (
        "schedule-version.v2.schema.json",
        "schedule-version.v2.synthetic.json",
        "schedule_version_version",
        SCHEDULE_VERSION,
    ),
    (
        "export-manifest.v3.schema.json",
        "export-manifest.v3.synthetic.json",
        "export_manifest_version",
        EXPORT_MANIFEST_VERSION,
    ),
    (
        "export-job.v3.schema.json",
        "export-job.v3.synthetic.json",
        "export_job_version",
        EXPORT_JOB_VERSION,
    ),
)

_EXPECTED_SCHEMA_IDS = {
    "execution-event.schema.json": "urn:plantnexus:aps:schema:execution-event:v1",
    "replan-request.schema.json": "urn:plantnexus:aps:schema:replan-request:v1",
    "change-report.schema.json": "urn:plantnexus:aps:schema:change-report:v1",
    "execution-simulation-manifest.schema.json": (
        "urn:plantnexus:aps:schema:execution-simulation-manifest:v1"
    ),
    "planning-policy.v2.schema.json": "urn:plantnexus:aps:schema:planning-policy:v2",
    "solver-report.v2.schema.json": "urn:plantnexus:aps:schema:solver-report:v2",
    "schedule-version.v2.schema.json": "urn:plantnexus:aps:schema:schedule-version:v2",
    "export-manifest.v3.schema.json": "urn:plantnexus:aps:schema:export-manifest:v3",
    "export-job.v3.schema.json": "urn:plantnexus:aps:schema:export-job:v3",
}

_NEW_ARTIFACT_PATHS = {
    *(f"schemas/json/{schema}" for schema, _, _, _ in _SCHEMA_SAMPLE_PAIRS),
    *(f"schemas/samples/{sample}" for _, sample, _, _ in _SCHEMA_SAMPLE_PAIRS),
}
_POST_P4_ADDITIVE_ARTIFACT_PATHS = {
    "schemas/json/duration-feature-record.schema.json",
    "schemas/json/duration-model-manifest.schema.json",
    "schemas/json/duration-evaluation-report.schema.json",
    "schemas/json/duration-prediction.schema.json",
    "schemas/samples/duration-feature-record.v1.synthetic.json",
    "schemas/samples/duration-model-manifest.v1.synthetic.json",
    "schemas/samples/duration-evaluation-report.v1.synthetic.json",
    "schemas/samples/duration-prediction.v1.candidate.synthetic.json",
    "schemas/samples/duration-prediction.v1.fallback.synthetic.json",
    "schemas/samples/duration-feature-record.v1.future-leakage.invalid.json",
    "schemas/samples/duration-model-manifest.v1.incomplete-lineage.invalid.json",
    "schemas/samples/duration-prediction.v1.invalid-quantiles.invalid.json",
    "schemas/samples/duration-prediction.v1.mixed-version.invalid.json",
    "schemas/samples/duration-prediction.v1.unknown-fallback.invalid.json",
}

_HISTORICAL_COUNT = 58
_HISTORICAL_MANIFEST_SHA256 = (
    "523ab38a466aa76c97ee39cfa52b7b1d43c77ba4dd622c3d27c409ee9af7242e"
)
_UV_LOCK_SHA256 = "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82"
_MIGRATION_MANIFEST_SHA256 = (
    "d9df0944263154a0de9dd896780b7ef571614635e879c39ad1cac48f19a53f5b"
)
_MIGRATION_PATHS = (
    "backend/migrations/.gitkeep",
    "backend/migrations/env.py",
    "backend/migrations/script.py.mako",
    "backend/migrations/versions/0001_engineering_job_metadata.py",
    "backend/migrations/versions/0002_raw_import_staging.py",
    "backend/migrations/versions/0003_planning_snapshots.py",
    "backend/migrations/versions/0004_schedule_versions_audit_export_jobs.py",
)

_RULE_SHA256 = {
    "schemas/rules/constraint-rule-sheet.v1.yaml": (
        "83fc3663dfd0ab3ca7361029ad288d4700ca6abdfd172df261da6873ef21f1e2"
    ),
    "schemas/rules/error-code-registry.v2.yaml": (
        "4c868280a1a13d2b244c131127d7447c7dd672d743982ce4a0d340b12c62698b"
    ),
    "schemas/rules/state-machines.v1.yaml": (
        "6a8c32137a681c6c96defd0dcdd3e580490ec82b81b6494b9b3ba4bf2144ddd7"
    ),
}

_EXPECTED_RUNTIME_DEPENDENCIES = {
    "alembic==1.16.5",
    "celery==5.5.3",
    "defusedxml==0.7.1",
    "fastapi==0.116.1",
    "openpyxl==3.1.5",
    "opentelemetry-api==1.36.0",
    "ortools==9.15.6755",
    "psycopg[binary]==3.2.9",
    "pydantic-settings==2.10.1",
    "redis==6.4.0",
    "sqlalchemy==2.0.43",
    "structlog==25.4.0",
    "uvicorn==0.35.0",
}

_EXPECTED_DEV_DEPENDENCIES = {
    "httpx==0.28.1",
    "hypothesis==6.165.10",
    "jsonschema==4.25.1",
    "pyright==1.1.411",
    "pytest==8.4.1",
    "PyYAML==6.0.2",
    "ruff==0.12.10",
}


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {"sha256": sha256(content).hexdigest(), "size_bytes": len(content)}


def _pass(name: str, details: object) -> dict[str, object]:
    return {"name": name, "status": "PASS", "details": details}


def _manifest(rows: Mapping[str, str]) -> str:
    payload = "".join(f"{path}={digest}\n" for path, digest in sorted(rows.items()))
    return sha256(payload.encode("utf-8")).hexdigest()


def _historical_freeze(root: Path) -> dict[str, object]:
    candidates = [
        *(root / "schemas" / "json").glob("*.json"),
        *(root / "schemas" / "samples").glob("*.json"),
        *(root / "schemas" / "scenario").glob("*.json"),
    ]
    observed: dict[str, str] = {}
    for path in sorted(candidates):
        relative = path.relative_to(root).as_posix()
        if relative not in _NEW_ARTIFACT_PATHS | _POST_P4_ADDITIVE_ARTIFACT_PATHS:
            observed[relative] = _sha256(path)
    if len(observed) != _HISTORICAL_COUNT:
        raise ValueError("historical Schema/sample inventory changed")
    manifest_sha256 = _manifest(observed)
    if manifest_sha256 != _HISTORICAL_MANIFEST_SHA256:
        raise ValueError("historical Schema/sample bytes changed")
    return {
        "artifact_count": len(observed),
        "manifest_sha256": manifest_sha256,
        "artifacts": observed,
    }


def _schema_registry(root: Path) -> tuple[Registry, dict[str, dict[str, Any]]]:
    schemas: dict[str, dict[str, Any]] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for path in sorted((root / "schemas" / "json").glob("*.json")):
        schema = _load_json(path)
        schema_id = cast(str, schema["$id"])
        schemas[path.name] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    return Registry().with_resources(resources), schemas


def _walk_schema(node: object, path: str = "$") -> None:
    if isinstance(node, dict):
        if "default" in node:
            raise ValueError(f"implicit default is forbidden at {path}")
        if node.get("type") == "object" and node.get("additionalProperties") is not False:
            raise ValueError(f"object is not strict at {path}")
        for key, value in node.items():
            _walk_schema(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_schema(value, f"{path}[{index}]")


def _validators_samples_and_artifacts(
    root: Path,
) -> tuple[
    dict[str, Draft202012Validator],
    dict[str, dict[str, Any]],
    dict[str, dict[str, object]],
    dict[str, str],
]:
    registry, schemas = _schema_registry(root)
    validators: dict[str, Draft202012Validator] = {}
    samples: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, object]] = {}
    schema_ids: dict[str, str] = {}
    for schema_name, sample_name, _, _ in _SCHEMA_SAMPLE_PAIRS:
        schema = schemas[schema_name]
        sample = _load_json(root / "schemas" / "samples" / sample_name)
        Draft202012Validator.check_schema(schema)
        _walk_schema(schema)
        if schema["$schema"] != "https://json-schema.org/draft/2020-12/schema":
            raise ValueError(f"wrong Schema dialect: {schema_name}")
        if schema["$id"] != _EXPECTED_SCHEMA_IDS[schema_name]:
            raise ValueError(f"unexpected stable URN: {schema_name}")
        properties = cast(dict[str, Any], schema["properties"])
        if properties["schema_set_version"].get("const") != SCHEMA_SET_VERSION:
            raise ValueError(f"wrong schema-set release: {schema_name}")
        validator = Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FormatChecker(),
        )
        validator.validate(sample)
        require_p4_document(sample)
        if json.loads(canonical_contract_bytes(sample)) != sample:
            raise ValueError(f"sample is not a canonical JSON value: {sample_name}")
        validators[schema_name] = validator
        samples[sample_name] = sample
        schema_ids[schema_name] = cast(str, schema["$id"])
        for relative in (
            f"schemas/json/{schema_name}",
            f"schemas/samples/{sample_name}",
        ):
            artifacts[relative] = _artifact(root / relative)
    return validators, samples, artifacts, schema_ids


def _bundle(samples: Mapping[str, dict[str, Any]]) -> dict[str, Mapping[str, object]]:
    return {
        p4_document_version(document): document
        for _, document in sorted(samples.items())
    }


def _fingerprint_evidence(samples: Mapping[str, dict[str, Any]]) -> dict[str, object]:
    policy = samples["planning-policy.v2.synthetic.json"]
    event = samples["execution-event.v1.synthetic.json"]
    request = samples["replan-request.v1.synthetic.json"]
    solver = samples["solver-report.v2.synthetic.json"]
    change = samples["change-report.v1.synthetic.json"]
    schedule = samples["schedule-version.v2.synthetic.json"]
    simulation = samples["execution-simulation-manifest.v1.synthetic.json"]
    manifest = samples["export-manifest.v3.synthetic.json"]
    job = samples["export-job.v3.synthetic.json"]
    return {
        "planning_policy": contract_fingerprint(policy),
        "freeze_policy": freeze_policy_fingerprint(
            cast(Mapping[str, object], policy["freeze_policy"])
        ),
        "execution_event": execution_event_fingerprint(event),
        "event_stream": event_stream_fingerprint([event["event_fingerprint"]]),
        "replan_request": replan_request_fingerprint(request),
        "solver_report": solver_report_fingerprint(solver),
        "change_report": change_report_fingerprint(change),
        "schedule_content": schedule_content_fingerprint(schedule),
        "execution_simulation_manifest": simulation_manifest_fingerprint(simulation),
        "export_manifest": export_manifest_fingerprint(manifest),
        "export_job": export_job_fingerprint(job),
    }


def _expect_schema_invalid(
    validator: Draft202012Validator,
    document: dict[str, Any],
    label: str,
) -> None:
    try:
        validator.validate(document)
    except ValidationError:
        return
    raise ValueError(f"negative Schema vector was accepted: {label}")


def _expect_semantic_invalid(document: Mapping[str, object], label: str) -> None:
    try:
        require_p4_document(document)
    except P4ContractError:
        return
    raise ValueError(f"negative semantic vector was accepted: {label}")


def _negative_vectors(
    validators: Mapping[str, Draft202012Validator],
    samples: Mapping[str, dict[str, Any]],
) -> dict[str, object]:
    schema_rejections = 0
    for schema_name, sample_name, version_field, _ in _SCHEMA_SAMPLE_PAIRS:
        validator = validators[schema_name]
        sample = samples[sample_name]
        unknown = deepcopy(sample)
        unknown["unexpected_field"] = True
        _expect_schema_invalid(validator, unknown, f"{sample_name}:unknown-field")
        schema_rejections += 1

        wrong_version = deepcopy(sample)
        wrong_version[version_field] = f"{sample[version_field]}.unknown"
        _expect_schema_invalid(validator, wrong_version, f"{sample_name}:version")
        schema_rejections += 1

        wrong_set = deepcopy(sample)
        wrong_set["schema_set_version"] = "2.7.0"
        _expect_schema_invalid(validator, wrong_set, f"{sample_name}:schema-set")
        schema_rejections += 1

        if "data_plane" in sample:
            production = deepcopy(sample)
            production["data_plane"] = "PRODUCTION"
            _expect_schema_invalid(validator, production, f"{sample_name}:production")
            schema_rejections += 1

    _expect_schema_invalid(
        validators["execution-event.schema.json"],
        samples["replan-request.v1.synthetic.json"],
        "cross-document-interchange",
    )
    schema_rejections += 1

    semantic_rejections = 0
    event = samples["execution-event.v1.synthetic.json"]
    later_receive = deepcopy(event)
    later_receive["received_at_utc"] = "2026-08-27T06:00:06Z"
    if execution_event_fingerprint(later_receive) != event["event_fingerprint"]:
        raise ValueError("received_at_utc leaked into ExecutionEvent identity")
    require_p4_document(later_receive)

    wrong_position = deepcopy(event)
    wrong_position["source_position"] = 2
    _expect_semantic_invalid(wrong_position, "event-position-fingerprint")
    semantic_rejections += 1

    request = deepcopy(samples["replan-request.v1.synthetic.json"])
    request["freeze_resolution"]["effective_until_utc"] = "2026-08-27T06:14:59Z"
    request["request_fingerprint"] = replan_request_fingerprint(request)
    request["request_id"] = "replan-request-" + request["request_fingerprint"].removeprefix("sha256:")
    _expect_semantic_invalid(request, "freeze-half-open-window")
    semantic_rejections += 1

    solver = deepcopy(samples["solver-report.v2.synthetic.json"])
    solver["planning_run_outcome"]["state"] = "INFEASIBLE"
    solver["report_fingerprint"] = solver_report_fingerprint(solver)
    solver["report_id"] = "solver-report-" + solver["report_fingerprint"].removeprefix("sha256:")
    _expect_semantic_invalid(solver, "unknown-is-not-infeasible")
    semantic_rejections += 1

    change = deepcopy(samples["change-report.v1.synthetic.json"])
    change["operations"].pop()
    change["report_fingerprint"] = change_report_fingerprint(change)
    change["report_id"] = "change-report-" + change["report_fingerprint"].removeprefix("sha256:")
    _expect_semantic_invalid(change, "incomplete-operation-universe")
    semantic_rejections += 1

    ratio = deepcopy(samples["change-report.v1.synthetic.json"])
    ratio["stability"]["unchanged_ratio"]["numerator"] = 0
    ratio["report_fingerprint"] = change_report_fingerprint(ratio)
    ratio["report_id"] = "change-report-" + ratio["report_fingerprint"].removeprefix("sha256:")
    _expect_semantic_invalid(ratio, "stability-ratio-drift")
    semantic_rejections += 1

    manifest = deepcopy(samples["execution-simulation-manifest.v1.synthetic.json"])
    manifest["checkpoint"]["last_applied_position"] = 0
    manifest["manifest_fingerprint"] = simulation_manifest_fingerprint(manifest)
    manifest["manifest_id"] = "execution-simulation-" + manifest[
        "manifest_fingerprint"
    ].removeprefix("sha256:")
    _expect_semantic_invalid(manifest, "checkpoint-position-drift")
    semantic_rejections += 1

    package = deepcopy(samples["export-manifest.v3.synthetic.json"])
    package["files"].reverse()
    package["manifest_fingerprint"] = export_manifest_fingerprint(package)
    package["package_id"] = "export-package-" + package[
        "manifest_fingerprint"
    ].removeprefix("sha256:")
    _expect_semantic_invalid(package, "export-file-order-drift")
    semantic_rejections += 1

    return {
        "schema_rejection_count": schema_rejections,
        "semantic_rejection_count": semantic_rejections,
        "received_at_identity": "EXCLUDED",
        "unknown_fields": "REJECTED",
        "unknown_versions": "REJECTED",
        "cross_document_interchange": "REJECTED",
        "production_shaped_samples": "REJECTED",
    }


def _rules_and_states(root: Path) -> dict[str, object]:
    for relative, expected in _RULE_SHA256.items():
        if _sha256(root / relative) != expected:
            raise ValueError(f"frozen rule bytes changed: {relative}")
    state_document = cast(
        dict[str, Any],
        yaml.safe_load(
            (root / "schemas" / "rules" / "state-machines.v1.yaml").read_text(
                encoding="utf-8"
            )
        ),
    )
    state_text = json.dumps(state_document, sort_keys=True)
    if "REPLAN_REQUEST" in state_text or "EXECUTION_SIMULATION" in state_text:
        raise ValueError("P4 carrier leaked a new business state machine")
    return {
        "rule_fingerprints": dict(sorted(_RULE_SHA256.items())),
        "replan_request_state_machine": "NONE",
        "execution_simulator_business_state_machine": "NONE",
        "schedule_and_export_pairs": "STATE_MACHINES_V1_UNCHANGED",
        "error_registry": "error-code-registry.v2 unchanged",
        "workspace_control_namespace": "UNCHANGED",
    }


def _migration_evidence(root: Path) -> dict[str, object]:
    rows = {relative: _sha256(root / relative) for relative in _MIGRATION_PATHS}
    manifest_sha256 = _manifest(rows)
    if manifest_sha256 != _MIGRATION_MANIFEST_SHA256:
        raise ValueError("migration history changed")
    return {
        "migration_count": len(rows),
        "manifest_sha256": manifest_sha256,
        "latest_revision": "0004",
        "p4_migration": "NONE",
    }


def _dependency_and_boundary_check(root: Path) -> dict[str, object]:
    project = cast(
        dict[str, Any],
        tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")),
    )
    runtime = set(cast(list[str], project["project"]["dependencies"]))
    development = set(cast(list[str], project["dependency-groups"]["dev"]))
    if runtime != _EXPECTED_RUNTIME_DEPENDENCIES:
        raise ValueError("runtime dependency set changed")
    if development != _EXPECTED_DEV_DEPENDENCIES:
        raise ValueError("development dependency set changed")
    if project["tool"]["plantnexus-aps"]["versions"]["schema"] != "2.9.0":
        raise ValueError("pyproject current schema metadata is not 2.9.0")
    if SCHEMA_VERSION != "2.9.0":
        raise ValueError("package current schema metadata is not 2.9.0")
    dictionary = cast(
        dict[str, Any],
        yaml.safe_load((root / "schemas" / "data_dictionary.yaml").read_text("utf-8")),
    )
    if dictionary.get("schema_set_version") != "2.9.0":
        raise ValueError("data dictionary current schema metadata is not 2.9.0")
    expected_documents = {version for _, _, _, version in _SCHEMA_SAMPLE_PAIRS}
    if not expected_documents.issubset(set(cast(dict[str, Any], dictionary["schemas"]))):
        raise ValueError("data dictionary omits a P4 document version")
    lock_sha256 = _sha256(root / "uv.lock")
    if lock_sha256 != _UV_LOCK_SHA256:
        raise ValueError("uv.lock changed in a dependency-neutral contract release")

    source = (root / "backend" / "app" / "domain" / "execution_contracts.py").read_text(
        encoding="utf-8"
    ).lower()
    forbidden_imports = (
        "from fastapi",
        "from sqlalchemy",
        "app.api",
        "app.application",
        "app.infrastructure",
        "app.planning.backends",
        "app.simulation.execution",
    )
    if any(token in source for token in forbidden_imports):
        raise ValueError("pure P4 contracts crossed a behavior layer boundary")

    contract_text = source + "\n" + "\n".join(
        (root / "schemas" / "json" / schema_name)
        .read_text(encoding="utf-8")
        .lower()
        for schema_name, _, _, _ in _SCHEMA_SAMPLE_PAIRS
    )
    p5_tokens = (
        "secondary_resource",
        "batch_policy",
        "sequence_setup",
        "tool_capacity",
        "fixture_capacity",
        "multi_factory",
        "alternative_route",
        "decomposition_strategy",
        "rolling_horizon",
        "hybrid_strategy",
    )
    if any(token in contract_text for token in p5_tokens):
        raise ValueError("P5+ capability leaked into P4 contracts")
    return {
        "runtime_dependency_change": "NONE",
        "development_dependency_change": "NONE",
        "uv_lock_sha256": lock_sha256,
        "migration": _migration_evidence(root),
        "pure_contract_side_effects": "NONE",
        "persistence_projection_solver_simulator_api_ui": "NOT_IMPLEMENTED",
        "production_authority_external_integration_capacity_sla": "NOT_FORMED",
        "p5_plus_fields": "ABSENT",
    }


def run_contract_checks(root: Path) -> dict[str, object]:
    """Validate the additive P4 release, retained history, and phase boundaries."""

    historical = _historical_freeze(root)
    validators, samples, artifacts, schema_ids = _validators_samples_and_artifacts(root)
    documents = _bundle(samples)
    validate_p4_bundle(documents)
    fingerprints = _fingerprint_evidence(samples)
    negatives = _negative_vectors(validators, samples)
    rules = _rules_and_states(root)
    boundaries = _dependency_and_boundary_check(root)
    new_manifest = {
        relative: cast(str, evidence["sha256"])
        for relative, evidence in sorted(artifacts.items())
    }
    checks = [
        _pass("historical-schema-and-sample-byte-preservation", historical),
        _pass(
            "draft-2020-12-strict-schema-and-offline-references",
            {"schema_count": len(schema_ids), "schema_ids": schema_ids},
        ),
        _pass(
            "positive-samples-canonical-round-trip-and-fingerprints",
            fingerprints,
        ),
        _pass(
            "event-authority-order-replan-freeze-and-lineage",
            {
                "authority": "SIMULATION_ONLY",
                "event_order": "MONOTONIC_POSITION",
                "freeze_interval": "HALF_OPEN_EXACT",
                "replan_state_machine": "NONE",
            },
        ),
        _pass(
            "delivery-stability-makespan-and-complete-change-report",
            {
                "objective_order": ["OBJ-001", "OBJ-002", "OBJ-003"],
                "stability_components": [
                    "SOFT_LOCK_VIOLATIONS",
                    "CHANGED_EXISTING_OPERATIONS",
                    "RESOURCE_CHANGES",
                    "ABSOLUTE_START_SHIFT_SECONDS",
                ],
                "operation_classifications": [
                    "UNCHANGED",
                    "CHANGED",
                    "ADDED",
                    "REMOVED_BY_FACT",
                ],
                "ratio": "EXACT_NUMERATOR_DENOMINATOR_OR_NOT_APPLICABLE",
            },
        ),
        _pass("negative-fail-closed-vectors", negatives),
        _pass("state-error-and-historical-authority", rules),
        _pass("dependency-migration-phase-and-production-boundary", boundaries),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "result": "PASS",
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "schema_set_version": SCHEMA_SET_VERSION,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "schema_inventory": {
            "historical": historical,
            "additive": {
                "artifact_count": len(new_manifest),
                "manifest_sha256": _manifest(new_manifest),
                "artifacts": new_manifest,
            },
        },
        "artifacts": artifacts,
        "counts": {
            "new_schemas": len(_SCHEMA_SAMPLE_PAIRS),
            "new_samples": len(_SCHEMA_SAMPLE_PAIRS),
            "frozen_historical_artifacts": historical["artifact_count"],
            "schema_rejections": negatives["schema_rejection_count"],
            "semantic_rejections": negatives["semantic_rejection_count"],
        },
        "boundaries": boundaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_contract_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "result": "FAIL",
            "task_id": TASK_ID,
            "diff_base": DIFF_BASE,
            "schema_set_version": SCHEMA_SET_VERSION,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "check_count": 0,
            "checks": [],
            "issues": [f"{type(error).__name__}:{error}"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DIFF_BASE", "REPORT_VERSION", "TASK_ID", "main", "run_contract_checks"]
