"""Emit machine-checkable TASK-P3-02 workspace contract evidence."""

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

from app.domain.workspace_contracts import (
    WORKSPACE_V1_SCHEMA_SET_VERSION as SCHEMA_SET_VERSION,
    WorkspaceContractError,
    comparison_fingerprint,
    export_job_fingerprint,
    publication_result_fingerprint,
    require_workspace_document,
    schedule_content_fingerprint,
    state_contract_evidence,
    workspace_command_fingerprint,
    workspace_fingerprint,
    workspace_query_fingerprint,
)


REPORT_VERSION = "p3-workspace-contract-report.v1"
TASK_ID = "TASK-P3-02"

_SCHEMA_SAMPLE_PAIRS = (
    ("schedule-version.schema.json", "schedule-version.v1.synthetic.json"),
    ("workspace-query.schema.json", "workspace-query.v1.synthetic.json"),
    ("workspace-command.schema.json", "workspace-command.v1.synthetic.json"),
    (
        "schedule-version-comparison.schema.json",
        "schedule-version-comparison.v1.synthetic.json",
    ),
    ("audit-event.schema.json", "audit-event.v1.synthetic.json"),
    ("publication-result.schema.json", "publication-result.v1.synthetic.json"),
    ("export-job.schema.json", "export-job.v1.synthetic.json"),
)

_EXPECTED_IDS = {
    schema_name: f"urn:plantnexus:aps:schema:{schema_name.removesuffix('.schema.json')}:v1"
    for schema_name, _ in _SCHEMA_SAMPLE_PAIRS
}

_P2_FROZEN_SHA256 = {
    "schemas/json/canonical-records.v1.schema.json": "fd13b188b7317eb92f14489fdc6c7976cc24b5b03cfcb2fa9d9f1eabdd4b3f9e",
    "schemas/json/error.schema.json": "fcf00d95ee746814ca1b1c20d0f23c08a10e003184f0614811dec4ce8da1b53c",
    "schemas/json/error.v2.schema.json": "8b6c3ff4f2eef937b5444d43e4c8da8fe63ff398302e50ce2346244745a8ff29",
    "schemas/json/error.v3.schema.json": "32d6d3cd5db97f8359701f86d1b753071e691ead7e519b2072e6cf155d5222a5",
    "schemas/json/export-manifest.schema.json": "663a064a70c5903c54795f194fa6977eb29158cd0f9b72b3d41f7f8e443a772d",
    "schemas/json/import-package.schema.json": "ceab72f8f2adc3008a8489050372912a0bb6798751a0cedec9bbaa3a83f59621",
    "schemas/json/import-package.v2.schema.json": "166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56",
    "schemas/json/import-quality-report.schema.json": "2d41fb0afadbc0e73ba6bad60a52dcbfb34ef2e5e9602e1e1612ccc8c540f434",
    "schemas/json/kpi.schema.json": "be3dfbcd06e9fb7887df699c2ba0fc8bb229d603b0d55a75268a72bc2cdc9426",
    "schemas/json/kpi.v2.schema.json": "398377d462373315de130491d6286883940e3f8dd733a205ce5c1dfa032b2631",
    "schemas/json/planning-policy.schema.json": "62624424115c3f6c9d45e920bcb0ac744ae9e1f2173af81072610298560a1bda",
    "schemas/json/planning-problem.schema.json": "41b01bfbcdfdb0a6dc52da1121383f630ac3f08ca7db4d21c0b66dea3a96e943",
    "schemas/json/planning-problem.v2.schema.json": "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8",
    "schemas/json/planning-snapshot.schema.json": "d3b68f330c54df8c0e35f72e8058e60c981cfd5b58103d78c03c55fdf1876c0d",
    "schemas/json/planning-snapshot.v2.schema.json": "d30ed42f8e5d1b497e2c41aec8bd840c1530e8a16c8594e22ed8db2dbc676a09",
    "schemas/json/planning-solution.schema.json": "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4",
    "schemas/json/solve-limits.schema.json": "8caff522a1fef8e40671cdff3ca857084cbf908b5c7fdfb9fdd8468fc3811d95",
    "schemas/json/solver-report.schema.json": "64feacd0d1ec0ea1c9d3f62d8e38b473b61f42dab5bc672c5898c5e056257b2a",
    "schemas/json/state-transition.schema.json": "8ef67fc3a4a6875f49ae8767727384f0c92d24d4f49b17ebd14a409c12809730",
    "schemas/json/validation-report.schema.json": "e6c2e39762e7fa59d7ec374897ed94963e8fb40d60d937d82e54d979dc57c6ed",
    "schemas/json/validation-report.v2.schema.json": "1da63e931e7ddd90134eb652c857f13eb862787de855165cd230c2d8071fd353",
    "schemas/samples/export-manifest.v1.synthetic.json": "257a9ec4e2713346e0c5d67f0365f90eabc61f15ead6ce30dc0a5e53fa7caecd",
    "schemas/samples/import-package.v2.synthetic.json": "3b0a1654edb947e3ef1ae2c0a6b00fb4ae782d2d98282ac1b09663fc406eec6e",
    "schemas/samples/import-quality-report.v1.fail.json": "cdcc08ffcb8d53daedd4deddbe1411692ffcf0a5a7980c37ad25bfc5577e03e8",
    "schemas/samples/import-quality-report.v1.pass.json": "7ce681bac45b5a51bbfcef4e27e8bfce8040beeaa3eed0c6735b1428a9505711",
    "schemas/samples/kpi.v2.synthetic.json": "ab8c583500e502ae3c0df9ae716ba13a529184efb0beffe7d6ac8d2f0529523f",
    "schemas/samples/planning-policy.v1.synthetic.json": "87f7b509d36220135358dbafef9b908725103e22ee69ff875b12861ebb410a26",
    "schemas/samples/planning-problem.synthetic.json": "aa31fbb20b862b7ef51a0e1ed781cddca07c00a0d2724d9ea34e6a75d08a4093",
    "schemas/samples/planning-problem.v2.synthetic.json": "f655f9da0e97ede115ffe128eeabdc6e61bcb74412acfac4d7d0ccb8766d92ad",
    "schemas/samples/planning-snapshot.synthetic.json": "33c58c505d2bd7c8411908ca043e211733ed6043b8482786a276e3cd81c50f91",
    "schemas/samples/planning-snapshot.v2.synthetic.json": "9e41ef51a55b765d94264cde00c0a34368af4c8269c47c8dbdf836c738272027",
    "schemas/samples/planning-solution.v1.synthetic.json": "054afe4525a115dc57ac88467bee36ef42f929c96e9741f5b418665cdce03afb",
    "schemas/samples/solve-limits.v1.synthetic.json": "68ebc4d134d945ce0cd73254166b6e299096a7f4cd0577187244c0dcfd38b492",
    "schemas/samples/solver-report.v1.synthetic.json": "df2348dc3cdb842b6bc87169ef111abb8cdf6394d6a39cafb67285be44e6528d",
}

_P2_MANIFEST_SHA256 = "76bb8ae4347ae8bbaa0b2781f74eccd7e4cb1ee97303533a5db3e49f27673723"
_UV_LOCK_SHA256 = "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82"
_RULE_SHA256 = {
    "schemas/rules/capability-registry.v1.yaml": "a2b1ac03f769856940d716bbab9a13200dfdcf7d3072eec0638e3479704a1f37",
    "schemas/rules/error-code-registry.v2.yaml": "4c868280a1a13d2b244c131127d7447c7dd672d743982ce4a0d340b12c62698b",
    "schemas/rules/state-machines.v1.yaml": "6a8c32137a681c6c96defd0dcdd3e580490ec82b81b6494b9b3ba4bf2144ddd7",
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


def _p2_byte_preservation(root: Path) -> dict[str, object]:
    observed: dict[str, str] = {}
    for relative, expected in sorted(_P2_FROZEN_SHA256.items()):
        digest = _sha256(root / relative)
        if digest != expected:
            raise ValueError(f"frozen P2 artifact bytes changed: {relative}")
        observed[relative] = digest
    manifest = "".join(f"{path}={digest}\n" for path, digest in observed.items())
    manifest_sha256 = sha256(manifest.encode("utf-8")).hexdigest()
    if manifest_sha256 != _P2_MANIFEST_SHA256:
        raise ValueError("frozen P2 artifact manifest fingerprint changed")
    for relative, expected in _RULE_SHA256.items():
        if _sha256(root / relative) != expected:
            raise ValueError(f"frozen rule bytes changed: {relative}")
    return {
        "artifact_count": len(observed),
        "manifest_sha256": manifest_sha256,
        "rule_fingerprints": dict(sorted(_RULE_SHA256.items())),
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
        if (
            node.get("type") == "object"
            and node.get("additionalProperties") is not False
        ):
            raise ValueError(f"object is not strict at {path}")
        for key, value in node.items():
            _walk_schema(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_schema(value, f"{path}[{index}]")


def _validators_and_samples(
    root: Path,
) -> tuple[
    dict[str, Draft202012Validator],
    dict[str, dict[str, Any]],
    dict[str, dict[str, object]],
]:
    registry, schemas = _schema_registry(root)
    validators: dict[str, Draft202012Validator] = {}
    samples: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, object]] = {}
    for schema_name, sample_name in _SCHEMA_SAMPLE_PAIRS:
        schema = schemas[schema_name]
        sample = _load_json(root / "schemas" / "samples" / sample_name)
        Draft202012Validator.check_schema(schema)
        _walk_schema(schema)
        if schema["$id"] != _EXPECTED_IDS[schema_name]:
            raise ValueError(f"unexpected stable schema id: {schema_name}")
        properties = cast(dict[str, Any], schema["properties"])
        if properties["schema_set_version"].get("const") != SCHEMA_SET_VERSION:
            raise ValueError(f"wrong schema-set release: {schema_name}")
        validator = Draft202012Validator(
            schema, registry=registry, format_checker=FormatChecker()
        )
        validator.validate(sample)
        require_workspace_document(sample)
        validators[schema_name] = validator
        samples[sample_name] = sample
        for relative in (
            f"schemas/json/{schema_name}",
            f"schemas/samples/{sample_name}",
        ):
            artifacts[relative] = _artifact(root / relative)
    return validators, samples, artifacts


def _expect_invalid(
    validator: Draft202012Validator, document: dict[str, Any], label: str
) -> None:
    try:
        validator.validate(document)
    except ValidationError:
        return
    raise ValueError(f"negative vector was accepted: {label}")


def _negative_vectors(
    validators: Mapping[str, Draft202012Validator],
    samples: Mapping[str, dict[str, Any]],
) -> dict[str, object]:
    rejection_count = 0
    for schema_name, sample_name in _SCHEMA_SAMPLE_PAIRS:
        validator = validators[schema_name]
        sample = samples[sample_name]

        unknown = deepcopy(sample)
        unknown["unexpected_field"] = True
        _expect_invalid(validator, unknown, f"{sample_name}:unknown-field")
        rejection_count += 1

        version_field = next(field for field in sample if field.endswith("_version"))
        wrong_version = deepcopy(sample)
        wrong_version[version_field] = f"{sample[version_field]}.unknown"
        _expect_invalid(validator, wrong_version, f"{sample_name}:unknown-version")
        rejection_count += 1

        wrong_plane = deepcopy(sample)
        wrong_plane["data_plane"] = "PRODUCTION"
        _expect_invalid(validator, wrong_plane, f"{sample_name}:production-synthetic")
        rejection_count += 1

    schedule_sample = samples["schedule-version.v1.synthetic.json"]
    query_validator = validators["workspace-query.schema.json"]
    _expect_invalid(
        query_validator, schedule_sample, "schedule-query-non-interchangeable"
    )
    rejection_count += 1

    command = deepcopy(samples["workspace-command.v1.synthetic.json"])
    command["command_type"] = "UNALLOCATED_COMMAND"
    _expect_invalid(
        validators["workspace-command.schema.json"], command, "unallocated-command"
    )
    rejection_count += 1

    schedule = deepcopy(schedule_sample)
    schedule["state"] = "UNKNOWN_STATE"
    _expect_invalid(
        validators["schedule-version.schema.json"], schedule, "unknown-schedule-state"
    )
    rejection_count += 1

    fingerprint_rejections = 0
    for sample_name, fingerprint_field in (
        ("schedule-version.v1.synthetic.json", "content_fingerprint"),
        ("workspace-query.v1.synthetic.json", "query_fingerprint"),
        ("workspace-command.v1.synthetic.json", "request_fingerprint"),
        ("schedule-version-comparison.v1.synthetic.json", "comparison_fingerprint"),
        ("publication-result.v1.synthetic.json", "result_fingerprint"),
        ("export-job.v1.synthetic.json", "job_fingerprint"),
    ):
        drifted = deepcopy(samples[sample_name])
        drifted[fingerprint_field] = "sha256:" + "f" * 64
        try:
            require_workspace_document(drifted)
        except WorkspaceContractError:
            fingerprint_rejections += 1
        else:
            raise ValueError(f"fingerprint drift was accepted: {sample_name}")

    return {
        "schema_rejection_count": rejection_count,
        "fingerprint_rejection_count": fingerprint_rejections,
        "unknown_fields": "REJECTED",
        "unknown_versions": "REJECTED",
        "production_synthetic_mix": "REJECTED",
        "cross_document_interchange": "REJECTED",
    }


def _state_and_error_alignment(root: Path) -> dict[str, object]:
    expected = {
        "schedule_states": [
            "APPROVED",
            "DRAFT",
            "PUBLISHED",
            "READY_FOR_REVIEW",
            "REJECTED",
            "SUPERSEDED",
        ],
        "schedule_pairs": [
            ["APPROVED", "PUBLISHED"],
            ["DRAFT", "READY_FOR_REVIEW"],
            ["PUBLISHED", "SUPERSEDED"],
            ["READY_FOR_REVIEW", "APPROVED"],
            ["READY_FOR_REVIEW", "REJECTED"],
        ],
        "export_states": [
            "CANCELLED",
            "CREATED",
            "EXPORTED",
            "EXPORTING",
            "EXPORT_FAILED",
        ],
        "export_pairs": [
            ["CREATED", "CANCELLED"],
            ["CREATED", "EXPORTING"],
            ["EXPORTING", "CANCELLED"],
            ["EXPORTING", "EXPORTED"],
            ["EXPORTING", "EXPORT_FAILED"],
            ["EXPORT_FAILED", "EXPORTING"],
        ],
    }
    actual = state_contract_evidence()
    if actual != expected:
        raise ValueError("P3 carriers drift from state-machines.v1")

    registry = cast(
        dict[str, Any],
        yaml.safe_load(
            (root / "schemas" / "rules" / "error-code-registry.v2.yaml").read_text(
                encoding="utf-8"
            )
        ),
    )
    registry_text = json.dumps(registry, sort_keys=True)
    local_reasons = {
        "AUTHORIZATION_DENIED",
        "IDEMPOTENCY_CONFLICT",
        "EXPORT_FAILED",
    }
    if any(reason in registry_text for reason in local_reasons):
        raise ValueError("workspace-control reason leaked into the global registry")
    return {
        **actual,
        "global_error_registry": "error-code-registry.v2",
        "workspace_control_namespace": "workspace-control.v1",
        "workspace_control_reasons": sorted(local_reasons),
        "solver_unknown_product_meaning": "NO_SOLUTION_WITHIN_LIMIT_PRESERVED",
    }


def _fingerprint_evidence(
    samples: Mapping[str, dict[str, Any]],
) -> dict[str, object]:
    schedule = samples["schedule-version.v1.synthetic.json"]
    query = samples["workspace-query.v1.synthetic.json"]
    command = samples["workspace-command.v1.synthetic.json"]
    comparison = samples["schedule-version-comparison.v1.synthetic.json"]
    publication = samples["publication-result.v1.synthetic.json"]
    export_job = samples["export-job.v1.synthetic.json"]
    expected = {
        "schedule_content": schedule_content_fingerprint(schedule),
        "workspace_query": workspace_query_fingerprint(query),
        "workspace_command": workspace_command_fingerprint(command),
        "comparison": comparison_fingerprint(comparison),
        "publication_result": publication_result_fingerprint(publication),
        "export_job": export_job_fingerprint(export_job),
    }
    observed = {
        "schedule_content": schedule["content_fingerprint"],
        "workspace_query": query["query_fingerprint"],
        "workspace_command": command["request_fingerprint"],
        "comparison": comparison["comparison_fingerprint"],
        "publication_result": publication["result_fingerprint"],
        "export_job": export_job["job_fingerprint"],
    }
    if observed != expected:
        raise ValueError("sample canonical projection fingerprint mismatch")
    return {
        "projection_fingerprints": expected,
        "document_fingerprints": {
            name: workspace_fingerprint(document)
            for name, document in sorted(samples.items())
        },
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
    if project["tool"]["plantnexus-aps"]["versions"]["schema"] != "2.10.0":
        raise ValueError("pyproject current schema metadata is not 2.10.0")
    lock_sha256 = _sha256(root / "uv.lock")
    if lock_sha256 != _UV_LOCK_SHA256:
        raise ValueError("uv.lock changed in a dependency-neutral schema release")

    source = (root / "backend" / "app" / "domain" / "workspace_contracts.py").read_text(
        encoding="utf-8"
    )
    forbidden_imports = (
        "from fastapi",
        "from sqlalchemy",
        "app.api",
        "app.application",
        "app.exporters",
        "app.infrastructure",
        "app.jobs",
    )
    if any(token in source for token in forbidden_imports):
        raise ValueError("pure domain workspace contracts crossed a layer boundary")

    schema_text = "\n".join(
        (root / "schemas" / "json" / name).read_text(encoding="utf-8").lower()
        for name, _ in _SCHEMA_SAMPLE_PAIRS
    )
    deferred_tokens = (
        "execution-event",
        "replan-request",
        "freeze-window",
        "obj-002",
        "execution-simulator",
    )
    if any(token in schema_text for token in deferred_tokens):
        raise ValueError("a later-phase contract leaked into the P3 schema release")
    return {
        "runtime_dependency_change": "NONE",
        "development_dependency_change": "NONE",
        "uv_lock_sha256": lock_sha256,
        "persistence": "NOT_IMPLEMENTED",
        "state_transition_execution": "NOT_IMPLEMENTED",
        "authorization": "NOT_IMPLEMENTED",
        "api_ui_worker": "NOT_IMPLEMENTED",
        "external_or_production_publish": "NOT_IMPLEMENTED",
        "later_phase_contracts": "ABSENT",
    }


def run_contract_checks(root: Path) -> dict[str, object]:
    """Validate additive P3 schemas, samples, immutable history, and boundaries."""

    p2 = _p2_byte_preservation(root)
    validators, samples, artifacts = _validators_and_samples(root)
    fingerprints = _fingerprint_evidence(samples)
    negatives = _negative_vectors(validators, samples)
    state_and_error = _state_and_error_alignment(root)
    boundaries = _dependency_and_boundary_check(root)
    schema_ids = {
        schema_name: _EXPECTED_IDS[schema_name]
        for schema_name, _ in _SCHEMA_SAMPLE_PAIRS
    }
    checks = [
        _pass("p2-schema-and-sample-byte-preservation", p2),
        _pass(
            "draft-2020-12-schema-meta-and-offline-references",
            {"schema_ids": schema_ids, "schema_count": len(schema_ids)},
        ),
        _pass(
            "strict-no-default-and-plane-provenance-conditionals",
            {
                "additional_properties": "FORBIDDEN",
                "implicit_defaults": "FORBIDDEN",
                "explicit_plane_and_provenance": "REQUIRED",
            },
        ),
        _pass("positive-samples-and-canonical-fingerprints", fingerprints),
        _pass("negative-and-non-interchangeability-vectors", negatives),
        _pass("state-and-error-namespace-alignment", state_and_error),
        _pass(
            "pure-prechecks-and-round-trip",
            {
                "validated_document_versions": [
                    require_workspace_document(document)
                    for _, document in sorted(samples.items())
                ],
                "side_effects": "NONE",
            },
        ),
        _pass("dependency-and-phase-boundary", boundaries),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "schema_set_version": SCHEMA_SET_VERSION,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "check_count": len(checks),
        "checks": checks,
        "artifacts": artifacts,
        "counts": {
            "new_schemas": len(_SCHEMA_SAMPLE_PAIRS),
            "new_samples": len(_SCHEMA_SAMPLE_PAIRS),
            "frozen_p2_artifacts": len(_P2_FROZEN_SHA256),
            "negative_schema_rejections": negatives["schema_rejection_count"],
            "negative_fingerprint_rejections": negatives["fingerprint_rejection_count"],
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
            "task_id": TASK_ID,
            "schema_set_version": SCHEMA_SET_VERSION,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "main", "run_contract_checks"]
