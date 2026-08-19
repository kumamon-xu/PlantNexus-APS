"""TEST-CONTRACT-001: executable P0 schema and domain contract evidence."""

from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from app import SCHEMA_VERSION
from app.domain.types import (
    ContractValueError,
    canonical_id,
    duration_to_ticks,
    format_utc_instant,
    parse_utc_instant,
)
from app.domain.validation import (
    ContractViolation,
    validate_planning_problem_contract,
    validate_snapshot_contract,
)
from app.planning.problem.contracts import PlanningProblemDocument
from app.snapshots.contracts import PlanningSnapshotDocument


TEST_ID = "TEST-CONTRACT-001"
ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"
SAMPLE_ROOT = ROOT / "schemas" / "samples"
SCHEMA_FILES = (
    "import-package.schema.json",
    "planning-snapshot.schema.json",
    "planning-problem.schema.json",
    "kpi.schema.json",
    "error.schema.json",
    "validation-report.schema.json",
)


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validator(name: str) -> Draft202012Validator:
    schema = load_json(SCHEMA_ROOT / name)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def valid_problem() -> dict[str, Any]:
    return {
        "problem_version": "planning-problem.v1",
        "snapshot_id": "SNAPSHOT-001",
        "problem_builder_version": "builder.v1",
        "problem_hash": "hash-001",
        "tick_seconds": 60,
        "horizon_start_utc": "2026-08-19T00:00:00Z",
        "horizon_end_utc": "2026-08-20T00:00:00Z",
        "resource_ids": ["RESOURCE-001"],
        "operation_instances": [
            {
                "operation_id": "OPERATION-001",
                "status": "NOT_STARTED",
                "release_at_utc": "2026-08-19T00:00:00Z",
                "material_ready_at_utc": "2026-08-19T00:00:00Z",
                "resource_options": [
                    {
                        "resource_id": "RESOURCE-001",
                        "setup_seconds": 0,
                        "cycle_seconds_per_unit": 60,
                        "final_duration_seconds": 61,
                        "duration_source": "schema-contract-test",
                        "source_version": "1.0.0",
                    }
                ],
            }
        ],
        "precedence_edges": [],
        "resource_unavailable_intervals": [],
        "required_capabilities": [],
    }


def walk_json(value: Any):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def test_schema_documents_are_valid_draft_2020_12_with_unique_ids() -> None:
    schema_ids: set[str] = set()
    for filename in SCHEMA_FILES:
        schema = load_json(SCHEMA_ROOT / filename)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] not in schema_ids
        schema_ids.add(schema["$id"])


def test_schemas_do_not_encode_implicit_defaults() -> None:
    for filename in SCHEMA_FILES:
        schema = load_json(SCHEMA_ROOT / filename)
        assert all("default" not in node for node in walk_json(schema))


def test_published_versions_are_consistent() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert SCHEMA_VERSION == "1.0.0"
    assert pyproject["tool"]["plantnexus-aps"]["versions"]["schema"] == SCHEMA_VERSION


def test_synthetic_samples_validate_and_round_trip() -> None:
    samples = {
        "planning-snapshot.schema.json": "planning-snapshot.synthetic.json",
        "planning-problem.schema.json": "planning-problem.synthetic.json",
    }
    for schema_name, sample_name in samples.items():
        sample = load_json(SAMPLE_ROOT / sample_name)
        validator(schema_name).validate(sample)
        serialized = json.dumps(sample, sort_keys=True, separators=(",", ":"))
        assert json.loads(serialized) == sample


def test_unknown_root_fields_are_rejected() -> None:
    sample = load_json(SAMPLE_ROOT / "planning-snapshot.synthetic.json")
    sample["guessed_production_default"] = True
    with pytest.raises(ValidationError):
        validator("planning-snapshot.schema.json").validate(sample)


def test_wrong_contract_version_is_rejected() -> None:
    sample = load_json(SAMPLE_ROOT / "planning-snapshot.synthetic.json")
    sample["snapshot_version"] = "planning-snapshot.v2"
    with pytest.raises(ValidationError):
        validator("planning-snapshot.schema.json").validate(sample)


def test_snapshot_requires_utc_and_separates_synthetic_provenance() -> None:
    sample = load_json(SAMPLE_ROOT / "planning-snapshot.synthetic.json")
    non_utc = copy.deepcopy(sample)
    non_utc["cutoff_at"] = "2026-08-19T08:00:00+08:00"
    with pytest.raises(ValidationError):
        validator("planning-snapshot.schema.json").validate(non_utc)

    production_with_scenario = copy.deepcopy(sample)
    production_with_scenario["synthetic"] = False
    with pytest.raises(ValidationError):
        validator("planning-snapshot.schema.json").validate(production_with_scenario)

    with pytest.raises(ContractViolation, match="SYNTHETIC_REFERENCE_IN_PRODUCTION"):
        validate_snapshot_contract(
            cast(PlanningSnapshotDocument, production_with_scenario)
        )


def test_import_envelope_does_not_guess_canonical_record_fields() -> None:
    package = {
        "import_package_version": "import-package.v1",
        "package_id": "IMPORT-SAMPLE-001",
        "source_versions": {"schema_sample": "1.0.0"},
        "synthetic": True,
        "scenario_id": "SCHEMA-SAMPLE-P0-03",
        "records": {"future_p1_entity": [{"field_not_yet_authoritative": "sample"}]},
    }
    validator("import-package.schema.json").validate(package)

    production = copy.deepcopy(package)
    production["synthetic"] = False
    with pytest.raises(ValidationError):
        validator("import-package.schema.json").validate(production)


def test_planning_problem_schema_rejects_invalid_duration_and_running_facts() -> None:
    problem = valid_problem()
    validator("planning-problem.schema.json").validate(problem)

    invalid_duration = copy.deepcopy(problem)
    invalid_duration["operation_instances"][0]["resource_options"][0][
        "final_duration_seconds"
    ] = 0
    with pytest.raises(ValidationError):
        validator("planning-problem.schema.json").validate(invalid_duration)

    missing_running_facts = copy.deepcopy(problem)
    missing_running_facts["operation_instances"][0]["status"] = "RUNNING"
    with pytest.raises(ValidationError):
        validator("planning-problem.schema.json").validate(missing_running_facts)

    unknown_nested_field = copy.deepcopy(problem)
    unknown_nested_field["operation_instances"][0]["guessed_default"] = True
    with pytest.raises(ValidationError):
        validator("planning-problem.schema.json").validate(unknown_nested_field)


def test_semantic_precheck_rejects_broken_references_and_time_ranges() -> None:
    problem = valid_problem()
    validate_planning_problem_contract(cast(PlanningProblemDocument, problem))

    broken_reference = copy.deepcopy(problem)
    broken_reference["operation_instances"][0]["resource_options"][0][
        "resource_id"
    ] = "RESOURCE-MISSING"
    with pytest.raises(ContractViolation, match="INVALID_REFERENCE"):
        validate_planning_problem_contract(
            cast(PlanningProblemDocument, broken_reference)
        )

    invalid_horizon = copy.deepcopy(problem)
    invalid_horizon["horizon_end_utc"] = invalid_horizon["horizon_start_utc"]
    with pytest.raises(ContractViolation, match="INVALID_TIME_RANGE"):
        validate_planning_problem_contract(cast(PlanningProblemDocument, invalid_horizon))


def test_utc_and_duration_value_helpers_are_explicit() -> None:
    instant = parse_utc_instant("2026-08-19T00:00:00Z")
    assert format_utc_instant(instant) == "2026-08-19T00:00:00Z"
    assert duration_to_ticks(61, 60) == 2
    assert canonical_id("RESOURCE-001") == "RESOURCE-001"

    with pytest.raises(ContractValueError):
        parse_utc_instant("2026-08-19T08:00:00+08:00")
    with pytest.raises(ContractValueError):
        duration_to_ticks(-1, 60)
    with pytest.raises(ContractValueError):
        duration_to_ticks(60, 0)
    with pytest.raises(ContractValueError):
        canonical_id("RESOURCE 001")


def test_error_validation_and_kpi_envelopes_validate() -> None:
    validator("error.schema.json").validate(
        {
            "error_version": "error.v1",
            "category": "DATA_ERROR",
            "code": "INVALID_REFERENCE",
            "message": "candidate resource is missing",
            "details": [
                {
                    "entity_id": "OPERATION-001",
                    "field": "resource_id",
                    "expected_contract": "resource must exist",
                }
            ],
        }
    )
    validator("validation-report.schema.json").validate(
        {
            "validation_report_version": "validation-report.v1",
            "problem_hash": "hash-001",
            "status": "PASS",
            "violations": [],
        }
    )
    validator("kpi.schema.json").validate(
        {
            "kpi_version": "kpi.v1",
            "problem_hash": "hash-001",
            "tick_seconds": 60,
            "delivery": {
                "on_time_order_ratio": 1.0,
                "total_tardiness_seconds": 0,
                "weighted_tardiness": 0.0,
                "late_order_count": 0,
            },
            "planning": {
                "makespan_seconds": 0,
                "scheduled_operation_count": 0,
                "unscheduled_operation_count": 0,
            },
            "resources": [],
            "stability": {
                "changed_operation_count": 0,
                "resource_changed_count": 0,
                "start_shift_seconds": 0,
                "schedule_stability_ratio": 1.0,
            },
            "solver": {
                "model_build_seconds": 0.0,
                "first_feasible_seconds": None,
                "solve_seconds": 0.0,
                "objective": None,
                "best_bound": None,
                "relative_gap": None,
                "variables": 0,
                "constraints": 0,
                "optional_intervals": 0,
                "memory_peak_mb": 0.0,
            },
        }
    )


def test_data_dictionary_covers_every_published_schema() -> None:
    dictionary = yaml.safe_load((ROOT / "schemas" / "data_dictionary.yaml").read_text("utf-8"))
    assert dictionary["schema_set_version"] == "1.0.0"
    assert set(dictionary["schemas"]) == {
        "import-package.v1",
        "planning-snapshot.v1",
        "planning-problem.v1",
        "kpi.v1",
        "error.v1",
        "validation-report.v1",
    }
