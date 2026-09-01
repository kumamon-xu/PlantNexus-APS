"""TEST-DATA-QUALITY-001 contract evidence for Error v3 and quality report v1."""

from __future__ import annotations

import copy
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

from app import SCHEMA_VERSION
from app.data_validation import (
    ERROR_REGISTRY_VERSION,
    SCHEMA_SET_VERSION,
    QualityReportContractError,
    validate_import_package,
    validate_quality_report_contract,
)
from app.domain.errors import (
    ERROR_CATEGORY_BY_CODE,
    ERROR_CATEGORY_BY_CODE_V2,
    ProductErrorCodeV2,
)


TEST_ID = "TEST-DATA-QUALITY-001"
ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"
RULE_ROOT = ROOT / "schemas" / "rules"
SAMPLE_ROOT = ROOT / "schemas" / "samples"
PRESERVED_SHA256 = {
    "schemas/json/canonical-records.v1.schema.json": (
        "fd13b188b7317eb92f14489fdc6c7976cc24b5b03cfcb2fa9d9f1eabdd4b3f9e"
    ),
    "schemas/json/import-package.v2.schema.json": (
        "166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56"
    ),
    "schemas/json/error.schema.json": (
        "fcf00d95ee746814ca1b1c20d0f23c08a10e003184f0614811dec4ce8da1b53c"
    ),
    "schemas/json/error.v2.schema.json": (
        "8b6c3ff4f2eef937b5444d43e4c8da8fe63ff398302e50ce2346244745a8ff29"
    ),
    "schemas/rules/error-code-registry.v1.yaml": (
        "2b059bbfa19cf239875cf40009b8eb91dcef8d2649fa680bf1efd1af1e2d991c"
    ),
    "schemas/rules/unit-conversion-registry.v1.yaml": (
        "faa20954bcfa8d61ad1f8609f05d89baf38af278b2ba1b7890f50455c9e0e8d2"
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def load_yaml(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def validator(name: str) -> Draft202012Validator:
    error_schema = load_json(SCHEMA_ROOT / "error.v3.schema.json")
    registry = Registry().with_resource(
        error_schema["$id"], Resource.from_contents(error_schema)
    )
    return Draft202012Validator(
        load_json(SCHEMA_ROOT / name),
        registry=registry,
        format_checker=FormatChecker(),
    )


def valid_import() -> dict[str, Any]:
    return load_json(SAMPLE_ROOT / "import-package.v2.synthetic.json")


def invalid_import_with_four_gate_failures() -> dict[str, Any]:
    document = valid_import()
    edge = copy.deepcopy(document["records"]["routing_precedence_edges"][0])
    edge["routing_precedence_edge_id"] = "ROUTING-EDGE-002"
    edge["predecessor_routing_operation_id"] = "ROUTING-OP-002"
    edge["successor_routing_operation_id"] = "ROUTING-OP-001"
    edge["source"]["source_record_id"] = "SRC-ROUTING-EDGE-002"
    document["records"]["routing_precedence_edges"].append(edge)
    option = document["records"]["routing_resource_options"][0]
    option["resource_id"] = "RESOURCE-MISSING"
    option["quantity_unit"] = "kg"
    del option["final_duration_seconds"]
    return document


def test_new_schemas_are_valid_draft_2020_12_with_explicit_cross_ref_registry() -> None:
    error_schema = load_json(SCHEMA_ROOT / "error.v3.schema.json")
    report_schema = load_json(SCHEMA_ROOT / "import-quality-report.schema.json")

    Draft202012Validator.check_schema(error_schema)
    Draft202012Validator.check_schema(report_schema)
    assert error_schema["$id"] == "urn:plantnexus:aps:schema:error:v3"
    assert report_schema["$id"] == (
        "urn:plantnexus:aps:schema:import-quality-report:v1"
    )
    assert report_schema["properties"]["errors"]["items"]["$ref"] == error_schema["$id"]
    assert "default" not in json.dumps(error_schema)
    assert "default" not in json.dumps(report_schema)


def test_error_registry_v2_matches_python_mapping_and_retains_v1_rows() -> None:
    v1 = load_yaml(RULE_ROOT / "error-code-registry.v1.yaml")
    v2 = load_yaml(RULE_ROOT / "error-code-registry.v2.yaml")
    v1_mapping = {row["code"]: row["category"] for row in v1["codes"]}
    v2_mapping = {row["code"]: row["category"] for row in v2["codes"]}
    python_mapping = {
        code.value: category.value
        for code, category in ERROR_CATEGORY_BY_CODE_V2.items()
    }

    assert v2["error_registry_version"] == ERROR_REGISTRY_VERSION
    assert v2["compatibility"] == "additive"
    assert v2["supersedes"] == "error-code-registry.v1"
    assert v2_mapping == python_mapping
    assert len(v2_mapping) == len(ProductErrorCodeV2) == 23
    assert all(v2_mapping[code] == category for code, category in v1_mapping.items())
    assert len(ERROR_CATEGORY_BY_CODE) == len(v1_mapping) == 19
    assert {
        "ROUTE_CYCLE",
        "MISSING_RESOURCE",
        "UNIT_CONVERSION_ERROR",
        "MISSING_DURATION",
    } == set(v2_mapping) - set(v1_mapping)
    assert all(
        v2_mapping[code] == "DATA_ERROR"
        for code in set(v2_mapping) - set(v1_mapping)
    )


def test_pass_and_fail_samples_validate_and_match_evaluator_replay() -> None:
    report_validator = validator("import-quality-report.schema.json")
    pass_sample = load_json(SAMPLE_ROOT / "import-quality-report.v1.pass.json")
    fail_sample = load_json(SAMPLE_ROOT / "import-quality-report.v1.fail.json")

    report_validator.validate(pass_sample)
    report_validator.validate(fail_sample)
    validate_quality_report_contract(pass_sample)
    validate_quality_report_contract(fail_sample)
    assert validate_import_package(valid_import()).document == pass_sample
    assert (
        validate_import_package(invalid_import_with_four_gate_failures()).document
        == fail_sample
    )
    assert fail_sample["error_count"] == len(fail_sample["errors"]) == 7
    assert {
        "ROUTE_CYCLE",
        "MISSING_RESOURCE",
        "UNIT_CONVERSION_ERROR",
        "MISSING_DURATION",
    }.issubset({error["code"] for error in fail_sample["errors"]})


def test_error_v1_v2_v3_are_explicitly_non_interchangeable() -> None:
    error_v1 = validator("error.schema.json")
    error_v2 = validator("error.v2.schema.json")
    error_v3 = validator("error.v3.schema.json")
    v3 = load_json(SAMPLE_ROOT / "import-quality-report.v1.fail.json")["errors"][0]
    v2 = {
        "error_version": "error.v2",
        "category": "DATA_ERROR",
        "code": "INVALID_REFERENCE",
        "message": "historical v2",
        "details": [],
    }

    error_v3.validate(v3)
    error_v2.validate(v2)
    with pytest.raises(ValidationError):
        error_v1.validate(v3)
    with pytest.raises(ValidationError):
        error_v2.validate(v3)
    with pytest.raises(ValidationError):
        error_v3.validate(v2)


def test_report_schema_enforces_status_shape_and_rich_error_details() -> None:
    report_validator = validator("import-quality-report.schema.json")
    passed = load_json(SAMPLE_ROOT / "import-quality-report.v1.pass.json")
    failed = load_json(SAMPLE_ROOT / "import-quality-report.v1.fail.json")

    pass_with_error = copy.deepcopy(failed)
    pass_with_error["status"] = "PASS"
    with pytest.raises(ValidationError):
        report_validator.validate(pass_with_error)

    fail_without_error = copy.deepcopy(passed)
    fail_without_error["status"] = "FAIL"
    with pytest.raises(ValidationError):
        report_validator.validate(fail_without_error)

    missing_action = copy.deepcopy(failed)
    del missing_action["errors"][0]["details"][0]["action"]
    with pytest.raises(ValidationError):
        report_validator.validate(missing_action)

    wrong_count = copy.deepcopy(failed)
    wrong_count["error_count"] += 1
    report_validator.validate(wrong_count)
    with pytest.raises(QualityReportContractError, match="error_count"):
        validate_quality_report_contract(wrong_count)


def test_additive_schema_set_versions_and_dictionary_are_explicit() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dictionary = load_yaml(ROOT / "schemas" / "data_dictionary.yaml")
    import_schema = load_json(SCHEMA_ROOT / "import-package.v2.schema.json")
    unit_registry = load_yaml(RULE_ROOT / "unit-conversion-registry.v1.yaml")

    assert SCHEMA_VERSION == "2.9.0"
    assert SCHEMA_SET_VERSION == "2.2.0"
    assert pyproject["tool"]["plantnexus-aps"]["versions"]["schema"] == "2.9.0"
    assert dictionary["schema_set_version"] == "2.9.0"
    assert import_schema["properties"]["schema_set_version"]["const"] == "2.0.0"
    assert unit_registry["schema_set_version"] == "2.1.0"
    assert {
        "error.v3",
        "import-quality-report.v1",
        "error-code-registry.v2",
        "planning-policy.v1",
        "solve-limits.v1",
        "planning-solution.v1",
        "solver-report.v1",
        "kpi.v2",
        "export-manifest.v1",
        "execution-event.v1",
        "planning-policy.v2",
        "replan-request.v1",
        "solver-report.v2",
        "change-report.v1",
        "schedule-version.v2",
        "execution-simulation-manifest.v1",
        "export-manifest.v3",
        "export-job.v3",
    }.issubset(dictionary["schemas"])


def test_historical_machine_artifacts_are_byte_for_byte_preserved() -> None:
    for relative_path, expected in PRESERVED_SHA256.items():
        observed = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert observed == expected
