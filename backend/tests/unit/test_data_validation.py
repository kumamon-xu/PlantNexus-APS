"""TEST-DATA-QUALITY-001: deterministic canonical Import quality evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.data_validation import (
    QualityReportContractError,
    report_id_for,
    validate_import_package,
    validate_quality_report_contract,
)


TEST_IDS = (
    "TEST-DATA-QUALITY-001",
    "TEST-INF-NO-RESOURCE",
    "TEST-CAPABILITY-001",
)
ROOT = Path(__file__).resolve().parents[3]
SAMPLE_PATH = ROOT / "schemas" / "samples" / "import-package.v2.synthetic.json"


def valid_import() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))


def error_codes(document: dict[str, Any]) -> list[str]:
    return [error["code"] for error in document["errors"]]


def add_reverse_edge(document: dict[str, Any]) -> None:
    edge = copy.deepcopy(document["records"]["routing_precedence_edges"][0])
    edge["routing_precedence_edge_id"] = "ROUTING-EDGE-002"
    edge["predecessor_routing_operation_id"] = "ROUTING-OP-002"
    edge["successor_routing_operation_id"] = "ROUTING-OP-001"
    edge["source"]["source_record_id"] = "SRC-ROUTING-EDGE-002"
    document["records"]["routing_precedence_edges"].append(edge)


def mutate_gate(document: dict[str, Any], code: str) -> None:
    if code == "ROUTE_CYCLE":
        add_reverse_edge(document)
    elif code == "MISSING_RESOURCE":
        document["records"]["routing_resource_options"][0]["resource_id"] = (
            "RESOURCE-MISSING"
        )
    elif code == "UNIT_CONVERSION_ERROR":
        document["records"]["routing_resource_options"][0]["quantity_unit"] = "kg"
    elif code == "MISSING_DURATION":
        del document["records"]["routing_resource_options"][0][
            "final_duration_seconds"
        ]
    else:
        raise AssertionError(f"unknown gate mutation: {code}")


def test_valid_canonical_import_has_zero_errors_and_stable_bytes() -> None:
    first = validate_import_package(valid_import())
    second = validate_import_package(valid_import())

    assert first.passed
    assert first.document["status"] == "PASS"
    assert first.document["error_count"] == 0
    assert first.document["errors"] == []
    assert first.document["report_id"] == report_id_for(first.document)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.document == second.document
    assert json.loads(first.canonical_bytes) == first.document


@pytest.mark.parametrize(
    "expected_code",
    [
        "ROUTE_CYCLE",
        "MISSING_RESOURCE",
        "UNIT_CONVERSION_ERROR",
        "MISSING_DURATION",
    ],
)
def test_p1_exit_gate_errors_have_exact_data_error_codes(expected_code: str) -> None:
    document = valid_import()
    mutate_gate(document, expected_code)

    report = validate_import_package(document).document

    assert report["status"] == "FAIL"
    matching = [error for error in report["errors"] if error["code"] == expected_code]
    assert matching
    assert all(error["category"] == "DATA_ERROR" for error in matching)


def test_multi_error_order_and_report_identity_ignore_input_collection_order() -> None:
    document = valid_import()
    for code in (
        "ROUTE_CYCLE",
        "MISSING_RESOURCE",
        "UNIT_CONVERSION_ERROR",
        "MISSING_DURATION",
    ):
        mutate_gate(document, code)
    expected = validate_import_package(document)

    reordered = copy.deepcopy(document)
    for value in reordered["records"].values():
        if isinstance(value, list):
            value.reverse()
    reordered["records"]["calendars"][0]["unavailable_intervals"].reverse()
    reordered["records"]["resources"][0]["capabilities"].reverse()
    reordered["records"]["routing_operations"][0][
        "required_capabilities"
    ].reverse()
    observed = validate_import_package(reordered)

    assert expected.document == observed.document
    assert expected.canonical_bytes == observed.canonical_bytes
    assert {
        "ROUTE_CYCLE",
        "MISSING_RESOURCE",
        "UNIT_CONVERSION_ERROR",
        "MISSING_DURATION",
    }.issubset(error_codes(cast(dict[str, Any], observed.document)))
    assert error_codes(cast(dict[str, Any], observed.document)) == sorted(
        error_codes(cast(dict[str, Any], observed.document))
    )


def test_orphan_duplicate_self_edge_and_cycle_are_all_explicit() -> None:
    document = valid_import()
    document["records"]["resources"][0]["calendar_id"] = "CALENDAR-MISSING"
    duplicate = copy.deepcopy(document["records"]["resources"][0])
    duplicate["source"]["source_record_id"] = "SRC-RESOURCE-DUPLICATE"
    document["records"]["resources"].append(duplicate)
    self_edge = copy.deepcopy(document["records"]["routing_precedence_edges"][0])
    self_edge["routing_precedence_edge_id"] = "ROUTING-EDGE-SELF"
    self_edge["successor_routing_operation_id"] = self_edge[
        "predecessor_routing_operation_id"
    ]
    self_edge["source"]["source_record_id"] = "SRC-ROUTING-EDGE-SELF"
    document["records"]["routing_precedence_edges"].append(self_edge)

    codes = error_codes(cast(dict[str, Any], validate_import_package(document).document))

    assert "INVALID_REFERENCE" in codes
    assert "DUPLICATE_ID" in codes
    assert "ROUTE_CYCLE" in codes


def test_invalid_duration_calendar_lag_and_execution_fact_are_collected() -> None:
    document = valid_import()
    document["records"]["routing_resource_options"][0][
        "final_duration_seconds"
    ] = 0
    document["records"]["routing_precedence_edges"][0]["min_lag_seconds"] = 120
    document["records"]["routing_precedence_edges"][0]["max_lag_seconds"] = 60
    calendar = document["records"]["calendars"][0]
    overlap = copy.deepcopy(calendar["unavailable_intervals"][0])
    overlap["interval_id"] = "CALENDAR-001-DOWN-002"
    overlap["start_at_utc"] = "2026-08-19T08:30:00Z"
    overlap["end_at_utc"] = "2026-08-19T09:30:00Z"
    calendar["unavailable_intervals"].append(overlap)
    del document["records"]["execution_facts"][0]["remaining_seconds"]

    codes = error_codes(cast(dict[str, Any], validate_import_package(document).document))

    assert "INVALID_DURATION" in codes
    assert "INVALID_LAG_RANGE" in codes
    assert "INVALID_TIME_RANGE" in codes
    assert "MISSING_DURATION" in codes


def test_unsupported_platform_capability_and_operational_mismatch_differ() -> None:
    unsupported = valid_import()
    unsupported["records"]["routing_operations"][0][
        "required_capabilities"
    ].append("SECONDARY_CAPACITY")
    unsupported_report = validate_import_package(unsupported).document
    unsupported_errors = [
        error
        for error in unsupported_report["errors"]
        if error["code"] == "UNSUPPORTED_CAPABILITY"
    ]
    assert unsupported_errors
    assert all(
        error["category"] == "UNSUPPORTED_CAPABILITY"
        for error in unsupported_errors
    )

    mismatch = valid_import()
    mismatch["records"]["routing_operations"][0][
        "required_capabilities"
    ] = ["POLISHING"]
    mismatch_report = validate_import_package(mismatch).document
    assert "MISSING_RESOURCE" in error_codes(cast(dict[str, Any], mismatch_report))
    assert "UNSUPPORTED_CAPABILITY" not in error_codes(
        cast(dict[str, Any], mismatch_report)
    )

    supported_platform = valid_import()
    supported_platform["records"]["routing_operations"][0][
        "required_capabilities"
    ].append("DAG_ROUTING")
    assert validate_import_package(supported_platform).passed


def test_fact_and_lock_resources_must_be_explicit_routing_options() -> None:
    document = valid_import()
    extra = copy.deepcopy(document["records"]["resources"][0])
    extra["resource_id"] = "RESOURCE-002"
    extra["resource_code"] = "R002"
    extra["source"]["source_record_id"] = "SRC-RESOURCE-002"
    document["records"]["resources"].append(extra)
    document["records"]["execution_facts"][0]["resource_id"] = "RESOURCE-002"
    document["records"]["operation_locks"][0]["resource_id"] = "RESOURCE-002"

    report = validate_import_package(document).document
    membership = [
        error
        for error in report["errors"]
        if error["code"] == "MISSING_RESOURCE"
        and error["details"][0]["field"] == "resource_id"
    ]

    assert {error["details"][0]["entity_type"] for error in membership} == {
        "ExecutionFact",
        "OperationLock",
    }


def test_malformed_structure_returns_report_instead_of_crashing() -> None:
    document = valid_import()
    del document["records"]["resources"]
    del document["records"]["routing_resource_options"][0]["resource_id"]
    document["source_versions"] = []

    result = validate_import_package(document)

    assert not result.passed
    assert result.document["error_count"] == len(result.document["errors"])
    validate_quality_report_contract(result.document)


def test_error_details_have_stable_source_evidence_and_required_actions() -> None:
    document = valid_import()
    document["records"]["routing_resource_options"][0]["resource_id"] = (
        "RESOURCE-MISSING"
    )

    report = validate_import_package(document).document
    error = next(
        error
        for error in report["errors"]
        if error["code"] == "MISSING_RESOURCE"
        and error["details"][0]["entity_type"] == "RoutingResourceOption"
    )
    detail = error["details"][0]

    assert set(detail) == {
        "entity_type",
        "entity_id",
        "field",
        "observed_value",
        "expected_contract",
        "source_location",
        "action",
    }
    assert detail["entity_id"] == "ROUTING-OPTION-001"
    assert detail["field"] == "resource_id"
    assert detail["source_location"] == (
        "schema_sample@1.0.0:SRC-ROUTING-OPTION-001#"
        "routing_resource_options.resource_id"
    )
    assert detail["action"]


def test_report_contract_rejects_count_status_and_identity_tampering() -> None:
    report = cast(dict[str, Any], validate_import_package(valid_import()).document)

    wrong_count = copy.deepcopy(report)
    wrong_count["error_count"] = 1
    with pytest.raises(QualityReportContractError, match="error_count"):
        validate_quality_report_contract(wrong_count)

    wrong_status = copy.deepcopy(report)
    wrong_status["status"] = "FAIL"
    with pytest.raises(QualityReportContractError, match="status"):
        validate_quality_report_contract(wrong_status)

    wrong_id = copy.deepcopy(report)
    wrong_id["report_id"] = "import-quality-" + "0" * 64
    with pytest.raises(QualityReportContractError, match="report_id"):
        validate_quality_report_contract(wrong_id)


def test_data_validation_package_has_no_planning_solver_or_ortools_dependency() -> None:
    package_root = ROOT / "backend" / "app" / "data_validation"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(package_root.glob("*.py"))
    ).lower()

    assert "app.planning" not in source
    assert "ortools" not in source
    assert "cpsat" not in source
    assert "schedulevalidator" not in source
