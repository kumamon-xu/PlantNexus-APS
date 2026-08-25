"""TASK-P3-02 strict workspace Schema and pure-precheck contracts."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
import pytest
from referencing import Registry, Resource

from app.domain.workspace_contract_check import run_contract_checks
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


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"
SAMPLE_ROOT = ROOT / "schemas" / "samples"

TEST_CONTRACT_ID = "TEST-CONTRACT-001"
TEST_WORKSPACE_CONTRACT_ID = "TEST-WORKSPACE-CONTRACT-001"
TEST_STATE_TRANSITION_ID = "TEST-STATE-TRANSITION-001"
TEST_ERROR_MAPPING_ID = "TEST-ERROR-MAPPING-001"

PAIRS = (
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

EXPECTED_IDS = {
    schema_name: f"urn:plantnexus:aps:schema:{schema_name.removesuffix('.schema.json')}:v1"
    for schema_name, _ in PAIRS
}


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _registry() -> tuple[Registry, dict[str, dict[str, Any]]]:
    schemas: dict[str, dict[str, Any]] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for path in sorted(SCHEMA_ROOT.glob("*.json")):
        schema = _json(path)
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    return Registry().with_resources(resources), schemas


def _validator(name: str) -> Draft202012Validator:
    registry, schemas = _registry()
    return Draft202012Validator(
        schemas[name], registry=registry, format_checker=FormatChecker()
    )


def _sample(name: str) -> dict[str, Any]:
    return _json(SAMPLE_ROOT / name)


def _walk_no_defaults_and_strict_objects(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        assert "default" not in value, path
        if value.get("type") == "object":
            assert value.get("additionalProperties") is False, path
        for key, nested in value.items():
            _walk_no_defaults_and_strict_objects(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_no_defaults_and_strict_objects(nested, f"{path}[{index}]")


def test_all_p3_schemas_are_strict_draft_2020_12_and_offline_resolvable() -> None:
    registry, schemas = _registry()
    for schema_name, sample_name in PAIRS:
        schema = schemas[schema_name]
        sample = _sample(sample_name)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] == EXPECTED_IDS[schema_name]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["schema_set_version"] == {"const": "2.6.0"}
        _walk_no_defaults_and_strict_objects(schema)
        Draft202012Validator(
            schema, registry=registry, format_checker=FormatChecker()
        ).validate(sample)
        assert require_workspace_document(sample).endswith(".v1")
    assert TEST_CONTRACT_ID == "TEST-CONTRACT-001"


def test_samples_are_canonical_and_projection_fingerprints_are_exact() -> None:
    schedule = _sample("schedule-version.v1.synthetic.json")
    query = _sample("workspace-query.v1.synthetic.json")
    command = _sample("workspace-command.v1.synthetic.json")
    comparison = _sample("schedule-version-comparison.v1.synthetic.json")
    publication = _sample("publication-result.v1.synthetic.json")
    export_job = _sample("export-job.v1.synthetic.json")

    assert schedule["content_fingerprint"] == schedule_content_fingerprint(schedule)
    assert query["query_fingerprint"] == workspace_query_fingerprint(query)
    assert command["request_fingerprint"] == workspace_command_fingerprint(command)
    assert comparison["comparison_fingerprint"] == comparison_fingerprint(comparison)
    assert publication["result_fingerprint"] == publication_result_fingerprint(
        publication
    )
    assert export_job["job_fingerprint"] == export_job_fingerprint(export_job)

    for _, sample_name in PAIRS:
        document = _sample(sample_name)
        reversed_document = dict(reversed(list(document.items())))
        assert workspace_fingerprint(document) == workspace_fingerprint(
            reversed_document
        )
        assert (
            json.loads(json.dumps(document, sort_keys=True, separators=(",", ":")))
            == document
        )
    assert TEST_WORKSPACE_CONTRACT_ID == "TEST-WORKSPACE-CONTRACT-001"


@pytest.mark.parametrize(("schema_name", "sample_name"), PAIRS)
def test_unknown_fields_versions_and_production_synthetic_mix_fail_closed(
    schema_name: str, sample_name: str
) -> None:
    validator = _validator(schema_name)
    sample = _sample(sample_name)

    unknown = deepcopy(sample)
    unknown["unknown_field"] = True
    with pytest.raises(ValidationError):
        validator.validate(unknown)

    version_field = next(field for field in sample if field.endswith("_version"))
    wrong_version = deepcopy(sample)
    wrong_version[version_field] = "unknown.v1"
    with pytest.raises(ValidationError):
        validator.validate(wrong_version)

    mixed_plane = deepcopy(sample)
    mixed_plane["data_plane"] = "PRODUCTION"
    with pytest.raises(ValidationError):
        validator.validate(mixed_plane)


def test_query_and_command_planes_have_explicit_non_default_boundaries() -> None:
    query = _sample("workspace-query.v1.synthetic.json")
    query["direction"] = "REQUEST"
    query["result"] = None
    query["data_plane"] = "PRODUCTION"
    query["environment"] = "PRODUCTION"
    query["synthetic"] = False
    query.pop("synthetic_provenance")
    query["query_fingerprint"] = workspace_query_fingerprint(query)
    _validator("workspace-query.schema.json").validate(query)
    require_workspace_document(query)

    invalid_environment = deepcopy(query)
    invalid_environment["environment"] = "TEST"
    invalid_environment["query_fingerprint"] = workspace_query_fingerprint(
        invalid_environment
    )
    with pytest.raises(ValidationError):
        _validator("workspace-query.schema.json").validate(invalid_environment)

    command = _sample("workspace-command.v1.synthetic.json")
    assert not {"actor", "actor_ref", "principal", "role"}.intersection(command)
    assert command["target"] == "WORKSPACE_INTERNAL"
    assert command["required_capability"] == "edit"


def test_documents_are_non_interchangeable_and_fingerprint_drift_is_rejected() -> None:
    schedule = _sample("schedule-version.v1.synthetic.json")
    query = _sample("workspace-query.v1.synthetic.json")
    with pytest.raises(ValidationError):
        _validator("workspace-query.schema.json").validate(schedule)
    with pytest.raises(ValidationError):
        _validator("schedule-version.schema.json").validate(query)

    for sample_name, field in (
        ("schedule-version.v1.synthetic.json", "content_fingerprint"),
        ("workspace-query.v1.synthetic.json", "query_fingerprint"),
        ("workspace-command.v1.synthetic.json", "request_fingerprint"),
        ("schedule-version-comparison.v1.synthetic.json", "comparison_fingerprint"),
        ("publication-result.v1.synthetic.json", "result_fingerprint"),
        ("export-job.v1.synthetic.json", "job_fingerprint"),
    ):
        drifted = _sample(sample_name)
        drifted[field] = "sha256:" + "f" * 64
        with pytest.raises(WorkspaceContractError):
            require_workspace_document(drifted)


def test_command_discriminators_capabilities_and_payloads_are_fail_closed() -> None:
    validator = _validator("workspace-command.schema.json")
    command = _sample("workspace-command.v1.synthetic.json")

    wrong_capability = deepcopy(command)
    wrong_capability["required_capability"] = "publish"
    wrong_capability["request_fingerprint"] = workspace_command_fingerprint(
        wrong_capability
    )
    with pytest.raises(ValidationError):
        validator.validate(wrong_capability)

    wrong_payload = deepcopy(command)
    wrong_payload["payload"]["unversioned"] = True
    with pytest.raises(ValidationError):
        validator.validate(wrong_payload)

    unknown_command = deepcopy(command)
    unknown_command["command_type"] = "UNALLOCATED_COMMAND"
    with pytest.raises(ValidationError):
        validator.validate(unknown_command)

    claimed_authority = deepcopy(command)
    claimed_authority["role"] = "planner"
    with pytest.raises(ValidationError):
        validator.validate(claimed_authority)


def test_comparison_publication_export_and_audit_cross_value_invariants() -> None:
    comparison = _sample("schedule-version-comparison.v1.synthetic.json")
    same_version = deepcopy(comparison)
    same_version["compared_version"] = deepcopy(same_version["base_version"])
    same_version["comparison_fingerprint"] = comparison_fingerprint(same_version)
    with pytest.raises(WorkspaceContractError):
        require_workspace_document(same_version)

    publication = _sample("publication-result.v1.synthetic.json")
    assert publication["target"] == "SIMULATION_INTERNAL"
    assert publication["data_plane"] == "SIMULATION"
    mismatched_publication = deepcopy(publication)
    mismatched_publication["published_version"]["schedule_version_id"] = (
        "schedule-version-sim-other"
    )
    mismatched_publication["result_fingerprint"] = publication_result_fingerprint(
        mismatched_publication
    )
    with pytest.raises(WorkspaceContractError):
        require_workspace_document(mismatched_publication)

    export_job = _sample("export-job.v1.synthetic.json")
    assert export_job["state"] == "CREATED"
    assert export_job["attempt"] == 0
    assert export_job["artifact_manifest"] is None
    assert export_job["target"] == "SIMULATION_INTERNAL"

    audit = _sample("audit-event.v1.synthetic.json")
    assert (
        audit["idempotency_reference"]["request_fingerprint"]
        == audit["request_fingerprint"]
    )
    leaked = deepcopy(audit)
    leaked["token"] = "forbidden"
    with pytest.raises(ValidationError):
        _validator("audit-event.schema.json").validate(leaked)


def test_state_pairs_and_workspace_control_namespace_are_exact_and_separate() -> None:
    state_evidence = state_contract_evidence()
    assert state_evidence["schedule_pairs"] == [
        ["APPROVED", "PUBLISHED"],
        ["DRAFT", "READY_FOR_REVIEW"],
        ["PUBLISHED", "SUPERSEDED"],
        ["READY_FOR_REVIEW", "APPROVED"],
        ["READY_FOR_REVIEW", "REJECTED"],
    ]
    assert state_evidence["export_pairs"] == [
        ["CREATED", "CANCELLED"],
        ["CREATED", "EXPORTING"],
        ["EXPORTING", "CANCELLED"],
        ["EXPORTING", "EXPORTED"],
        ["EXPORTING", "EXPORT_FAILED"],
        ["EXPORT_FAILED", "EXPORTING"],
    ]

    schedule_schema = _json(SCHEMA_ROOT / "schedule-version.schema.json")
    local_reasons = set(
        schedule_schema["$defs"]["workspaceControlError"]["properties"]["reason"][
            "enum"
        ]
    )
    assert local_reasons == {
        "AUTHORIZATION_DENIED",
        "IDEMPOTENCY_CONFLICT",
        "EXPORT_FAILED",
    }
    global_registry = (
        ROOT / "schemas" / "rules" / "error-code-registry.v2.yaml"
    ).read_text(encoding="utf-8")
    assert local_reasons.isdisjoint(global_registry.split())
    assert "NO_SOLUTION_WITHIN_LIMIT" in global_registry
    assert TEST_STATE_TRANSITION_ID == "TEST-STATE-TRANSITION-001"
    assert TEST_ERROR_MAPPING_ID == "TEST-ERROR-MAPPING-001"


def test_schema_release_contains_no_later_phase_machine_carriers() -> None:
    combined = "\n".join(
        (SCHEMA_ROOT / schema_name).read_text(encoding="utf-8").lower()
        for schema_name, _ in PAIRS
    )
    for deferred in (
        "execution-event",
        "replan-request",
        "freeze-window",
        "obj-002",
        "execution-simulator",
    ):
        assert deferred not in combined


def test_machine_report_is_complete_and_replays_frozen_p2_bytes() -> None:
    report = run_contract_checks(ROOT)
    assert report["report_version"] == "p3-workspace-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-02"
    assert report["schema_set_version"] == SCHEMA_SET_VERSION
    assert report["check_count"] == 8
    assert report["counts"] == {
        "new_schemas": 7,
        "new_samples": 7,
        "frozen_p2_artifacts": 34,
        "negative_schema_rejections": 24,
        "negative_fingerprint_rejections": 6,
    }
    checks = cast(list[dict[str, object]], report["checks"])
    boundaries = cast(dict[str, object], report["boundaries"])
    assert {check["status"] for check in checks} == {"PASS"}
    assert boundaries["runtime_dependency_change"] == "NONE"
    assert boundaries["persistence"] == "NOT_IMPLEMENTED"
    assert boundaries["external_or_production_publish"] == ("NOT_IMPLEMENTED")
