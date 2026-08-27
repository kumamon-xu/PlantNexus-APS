"""TASK-P4-02 strict dynamic-replanning machine-contract evidence."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
import pytest
from referencing import Registry, Resource

from app.domain.execution_contract_check import run_contract_checks
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


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"
SAMPLE_ROOT = ROOT / "schemas" / "samples"

TEST_CONTRACT_ID = "TEST-CONTRACT-001"
TEST_EXECUTION_EVENT_ID = "TEST-EXECUTION-EVENT-CONTRACT-001"
TEST_REPLAN_REQUEST_ID = "TEST-REPLAN-REQUEST-CONTRACT-001"
TEST_CHANGE_REPORT_ID = "TEST-CHANGE-REPORT-001"

PAIRS = (
    ("execution-event.schema.json", "execution-event.v1.synthetic.json"),
    ("replan-request.schema.json", "replan-request.v1.synthetic.json"),
    ("change-report.schema.json", "change-report.v1.synthetic.json"),
    (
        "execution-simulation-manifest.schema.json",
        "execution-simulation-manifest.v1.synthetic.json",
    ),
    ("planning-policy.v2.schema.json", "planning-policy.v2.synthetic.json"),
    ("solver-report.v2.schema.json", "solver-report.v2.synthetic.json"),
    ("schedule-version.v2.schema.json", "schedule-version.v2.synthetic.json"),
    ("export-manifest.v3.schema.json", "export-manifest.v3.synthetic.json"),
    ("export-job.v3.schema.json", "export-job.v3.synthetic.json"),
)

VERSIONS = {
    EXECUTION_EVENT_VERSION,
    REPLAN_REQUEST_VERSION,
    CHANGE_REPORT_VERSION,
    EXECUTION_SIMULATION_MANIFEST_VERSION,
    PLANNING_POLICY_VERSION,
    SOLVER_REPORT_VERSION,
    SCHEDULE_VERSION,
    EXPORT_MANIFEST_VERSION,
    EXPORT_JOB_VERSION,
}


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sample(name: str) -> dict[str, Any]:
    return _json(SAMPLE_ROOT / name)


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
        schemas[name],
        registry=registry,
        format_checker=FormatChecker(),
    )


def _documents() -> dict[str, dict[str, Any]]:
    return {
        p4_document_version(document): document
        for _, sample_name in PAIRS
        if (document := _sample(sample_name))
    }


def _walk_strict(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        assert "default" not in value, path
        if value.get("type") == "object":
            assert value.get("additionalProperties") is False, path
        for key, nested in value.items():
            _walk_strict(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_strict(nested, f"{path}[{index}]")


def test_nine_p4_schemas_are_strict_offline_and_non_interchangeable() -> None:
    registry, schemas = _registry()
    observed_versions: set[str] = set()
    for schema_name, sample_name in PAIRS:
        schema = schemas[schema_name]
        sample = _sample(sample_name)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["properties"]["schema_set_version"] == {
            "const": SCHEMA_SET_VERSION
        }
        _walk_strict(schema)
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FormatChecker(),
        ).validate(sample)
        observed_versions.add(require_p4_document(sample))

        unknown = deepcopy(sample)
        unknown["unexpected_field"] = True
        with pytest.raises(ValidationError):
            _validator(schema_name).validate(unknown)

        old_set = deepcopy(sample)
        old_set["schema_set_version"] = "2.7.0"
        with pytest.raises(ValidationError):
            _validator(schema_name).validate(old_set)

    assert observed_versions == VERSIONS
    with pytest.raises(ValidationError):
        _validator("execution-event.schema.json").validate(
            _sample("replan-request.v1.synthetic.json")
        )
    assert TEST_CONTRACT_ID == "TEST-CONTRACT-001"


def test_bundle_fingerprints_and_cross_document_lineage_are_exact() -> None:
    documents = _documents()
    validate_p4_bundle(documents)
    policy = documents[PLANNING_POLICY_VERSION]
    event = documents[EXECUTION_EVENT_VERSION]
    request = documents[REPLAN_REQUEST_VERSION]
    solver = documents[SOLVER_REPORT_VERSION]
    change = documents[CHANGE_REPORT_VERSION]
    schedule = documents[SCHEDULE_VERSION]
    simulation = documents[EXECUTION_SIMULATION_MANIFEST_VERSION]
    manifest = documents[EXPORT_MANIFEST_VERSION]
    job = documents[EXPORT_JOB_VERSION]

    assert request["planning_policy"]["policy_fingerprint"] == contract_fingerprint(
        policy
    )
    assert request["freeze_resolution"][
        "freeze_policy_fingerprint"
    ] == freeze_policy_fingerprint(policy["freeze_policy"])
    assert event["event_fingerprint"] == execution_event_fingerprint(event)
    assert request["event_stream"]["stream_fingerprint"] == event_stream_fingerprint(
        [event["event_fingerprint"]]
    )
    assert request["request_fingerprint"] == replan_request_fingerprint(request)
    assert solver["report_fingerprint"] == solver_report_fingerprint(solver)
    assert change["report_fingerprint"] == change_report_fingerprint(change)
    assert schedule["content_fingerprint"] == schedule_content_fingerprint(schedule)
    assert simulation["manifest_fingerprint"] == simulation_manifest_fingerprint(
        simulation
    )
    assert manifest["manifest_fingerprint"] == export_manifest_fingerprint(manifest)
    assert job["job_fingerprint"] == export_job_fingerprint(job)


def test_execution_event_identity_excludes_receive_observation_but_not_authority() -> None:
    event = _sample("execution-event.v1.synthetic.json")
    later_receive = deepcopy(event)
    later_receive["received_at_utc"] = "2026-08-27T06:00:10Z"
    assert execution_event_fingerprint(later_receive) == event["event_fingerprint"]
    require_p4_document(later_receive)

    changed_authority = deepcopy(event)
    changed_authority["authority"]["authority_id"] = "authority-sim-execution-002"
    changed_authority["source_stream"]["authority_id"] = "authority-sim-execution-002"
    with pytest.raises(P4ContractError):
        require_p4_document(changed_authority)

    wrong_scope = deepcopy(event)
    wrong_scope["authority"]["authority_scope"] = "SIMULATION/other/scope"
    wrong_scope["event_fingerprint"] = execution_event_fingerprint(wrong_scope)
    wrong_scope["event_id"] = "execution-event-" + wrong_scope[
        "event_fingerprint"
    ].removeprefix("sha256:")
    with pytest.raises(P4ContractError):
        require_p4_document(wrong_scope)

    production = deepcopy(event)
    production["data_plane"] = "PRODUCTION"
    with pytest.raises(ValidationError):
        _validator("execution-event.schema.json").validate(production)
    assert TEST_EXECUTION_EVENT_ID == "TEST-EXECUTION-EVENT-CONTRACT-001"


def test_replan_request_has_no_state_and_freeze_is_exact_half_open() -> None:
    request = _sample("replan-request.v1.synthetic.json")
    assert "state" not in request
    assert request["base_schedule_version"]["state"] == "PUBLISHED"
    require_p4_document(request)

    stale = deepcopy(request)
    stale["base_schedule_version"]["state"] = "DRAFT"
    with pytest.raises(ValidationError):
        _validator("replan-request.schema.json").validate(stale)

    wrong_end = deepcopy(request)
    wrong_end["freeze_resolution"]["effective_until_utc"] = (
        "2026-08-27T06:14:59Z"
    )
    wrong_end["request_fingerprint"] = replan_request_fingerprint(wrong_end)
    wrong_end["request_id"] = "replan-request-" + wrong_end[
        "request_fingerprint"
    ].removeprefix("sha256:")
    with pytest.raises(P4ContractError):
        require_p4_document(wrong_end)

    gap = deepcopy(request)
    gap["event_stream"]["through_position"] = 2
    gap["request_fingerprint"] = replan_request_fingerprint(gap)
    gap["request_id"] = "replan-request-" + gap[
        "request_fingerprint"
    ].removeprefix("sha256:")
    with pytest.raises(P4ContractError):
        require_p4_document(gap)
    assert TEST_REPLAN_REQUEST_ID == "TEST-REPLAN-REQUEST-CONTRACT-001"


def test_policy_and_solver_report_preserve_exact_objective_and_status_order() -> None:
    policy = _sample("planning-policy.v2.synthetic.json")
    solver = _sample("solver-report.v2.synthetic.json")
    assert [stage["objective_id"] for stage in policy["objective_stages"]] == [
        "OBJ-001",
        "OBJ-002",
        "OBJ-003",
    ]
    assert policy["objective_stages"][1]["components"] == [
        "SOFT_LOCK_VIOLATIONS",
        "CHANGED_EXISTING_OPERATIONS",
        "RESOURCE_CHANGES",
        "ABSOLUTE_START_SHIFT_SECONDS",
    ]
    require_p4_document(policy)
    require_p4_document(solver)

    weighted = deepcopy(policy)
    weighted["objective_stages"][1]["sense"] = "MINIMIZE"
    with pytest.raises(ValidationError):
        _validator("planning-policy.v2.schema.json").validate(weighted)

    dishonest = deepcopy(solver)
    dishonest["planning_run_outcome"]["state"] = "INFEASIBLE"
    dishonest["report_fingerprint"] = solver_report_fingerprint(dishonest)
    dishonest["report_id"] = "solver-report-" + dishonest[
        "report_fingerprint"
    ].removeprefix("sha256:")
    with pytest.raises(P4ContractError):
        require_p4_document(dishonest)


def test_change_report_requires_complete_sorted_universe_and_exact_ratio() -> None:
    report = _sample("change-report.v1.synthetic.json")
    require_p4_document(report)
    assert [item["classification"] for item in report["operations"]] == [
        "UNCHANGED",
        "CHANGED",
    ]
    assert report["stability"]["unchanged_ratio"] == {
        "status": "APPLICABLE",
        "numerator": 1,
        "denominator": 2,
    }

    incomplete = deepcopy(report)
    incomplete["operations"].pop()
    incomplete["report_fingerprint"] = change_report_fingerprint(incomplete)
    incomplete["report_id"] = "change-report-" + incomplete[
        "report_fingerprint"
    ].removeprefix("sha256:")
    with pytest.raises(P4ContractError):
        require_p4_document(incomplete)

    guessed_ratio = deepcopy(report)
    guessed_ratio["stability"]["unchanged_ratio"]["numerator"] = 0
    guessed_ratio["report_fingerprint"] = change_report_fingerprint(guessed_ratio)
    guessed_ratio["report_id"] = "change-report-" + guessed_ratio[
        "report_fingerprint"
    ].removeprefix("sha256:")
    with pytest.raises(P4ContractError):
        require_p4_document(guessed_ratio)
    assert TEST_CHANGE_REPORT_ID == "TEST-CHANGE-REPORT-001"


def test_schedule_simulator_and_export_carriers_do_not_add_business_authority() -> None:
    schedule = _sample("schedule-version.v2.synthetic.json")
    simulation = _sample("execution-simulation-manifest.v1.synthetic.json")
    manifest = _sample("export-manifest.v3.synthetic.json")
    job = _sample("export-job.v3.synthetic.json")
    for document in (schedule, simulation, manifest, job):
        require_p4_document(document)

    assert schedule["state"] == "DRAFT"
    assert schedule["decision"] is schedule["publication"] is None
    assert simulation["production_binding"] is False
    assert "state" not in simulation
    assert manifest["publishable"] is False
    assert manifest["target"] == job["target"] == "SIMULATION_INTERNAL"
    assert job["state"] == "CREATED"
    assert job["attempt"] == 0

    checkpoint_drift = deepcopy(simulation)
    checkpoint_drift["checkpoint"]["last_applied_position"] = 0
    checkpoint_drift["manifest_fingerprint"] = simulation_manifest_fingerprint(
        checkpoint_drift
    )
    checkpoint_drift["manifest_id"] = "execution-simulation-" + checkpoint_drift[
        "manifest_fingerprint"
    ].removeprefix("sha256:")
    with pytest.raises(P4ContractError):
        require_p4_document(checkpoint_drift)

    external = deepcopy(manifest)
    external["target"] = "MES"
    with pytest.raises(ValidationError):
        _validator("export-manifest.v3.schema.json").validate(external)


def test_machine_report_freezes_history_dependencies_and_phase_boundaries() -> None:
    report = run_contract_checks(ROOT)
    assert report["report_version"] == "p4-machine-contract-report.v1"
    assert report["task_id"] == "TASK-P4-02"
    assert report["diff_base"] == "4026597ab1015b5ea3a89d241f0d12b5b481dee3"
    assert report["schema_set_version"] == "2.8.0"
    assert report["status"] == report["result"] == "PASS"
    assert report["check_count"] == 8
    assert report["counts"] == {
        "new_schemas": 9,
        "new_samples": 9,
        "frozen_historical_artifacts": 58,
        "schema_rejections": 35,
        "semantic_rejections": 7,
    }
    assert report["issues"] == []
    boundaries = cast(dict[str, Any], report["boundaries"])
    migration = cast(dict[str, Any], boundaries["migration"])
    assert boundaries["runtime_dependency_change"] == "NONE"
    assert boundaries["development_dependency_change"] == "NONE"
    assert migration["p4_migration"] == "NONE"
    assert boundaries[
        "production_authority_external_integration_capacity_sla"
    ] == "NOT_FORMED"
    assert boundaries["p5_plus_fields"] == "ABSENT"
