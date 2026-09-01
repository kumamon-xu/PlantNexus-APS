"""P0 rule/state/error/capability contract evidence for TASK-P0-04."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

from app.domain.capabilities import (
    CAPABILITY_STATUS_BY_NAME,
    CapabilityContractError,
    CapabilityName,
    require_v1_capability_contract,
)
from app.domain.errors import (
    ERROR_CATEGORY_BY_CODE,
    ProductErrorCategory,
    ProductErrorCode,
)
from app.domain.state_machines import (
    StateMachineName,
    StateTransitionError,
    is_transition_allowed,
    require_transition,
    terminal_states_for,
    transitions_for,
)
from app.planning.validation.rule_sheet import (
    DEFERRED_CONSTRAINT_IDS,
    V1_CONSTRAINT_IDS,
    RuleSheetContractError,
    main,
    validate_capability_registry,
    validate_constraint_rule_sheet,
    validate_contract_artifacts,
    validate_error_registry,
    validate_state_registry,
)


TEST_IDS = (
    "TEST-RULE-SHEET-001",
    "TEST-STATE-TRANSITION-001",
    "TEST-ERROR-MAPPING-001",
    "TEST-CAPABILITY-001",
)
ROOT = Path(__file__).resolve().parents[3]
RULE_ROOT = ROOT / "schemas" / "rules"
SCHEMA_ROOT = ROOT / "schemas" / "json"


def load_yaml(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        yaml.safe_load((RULE_ROOT / name).read_text(encoding="utf-8")),
    )


def load_json(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8")),
    )


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_json(name))


def test_rule_sheet_is_complete_unique_and_does_not_claim_evaluation() -> None:
    summary = validate_constraint_rule_sheet(
        load_yaml("constraint-rule-sheet.v1.yaml")
    )
    assert summary.active_constraints == 11
    assert summary.deferred_constraints == 7
    assert V1_CONSTRAINT_IDS == tuple(f"C-{number:03d}" for number in range(1, 12))
    assert DEFERRED_CONSTRAINT_IDS == tuple(
        f"C-{number:03d}" for number in range(12, 19)
    )

    source = (
        ROOT / "backend" / "app" / "planning" / "validation" / "rule_sheet.py"
    ).read_text(encoding="utf-8")
    assert "does not\naccept a candidate schedule" in source.lower()
    assert "def validate_schedule" not in source


def test_rule_sheet_completeness_rejects_a_missing_or_duplicate_c_id() -> None:
    rule_sheet = load_yaml("constraint-rule-sheet.v1.yaml")
    missing = copy.deepcopy(rule_sheet)
    missing["active_rules"].pop()
    with pytest.raises(RuleSheetContractError, match="exactly C-001 through C-011"):
        validate_constraint_rule_sheet(missing)

    duplicate = copy.deepcopy(rule_sheet)
    duplicate["active_rules"][1]["constraint_id"] = "C-001"
    with pytest.raises(RuleSheetContractError, match="duplicates"):
        validate_constraint_rule_sheet(duplicate)


def test_lag_rules_compare_exact_observed_seconds_without_relaxing_max_lag() -> None:
    rule_sheet = load_yaml("constraint-rule-sheet.v1.yaml")
    rules = {rule["constraint_id"]: rule for rule in rule_sheet["active_rules"]}
    c002_formula = rules["C-002"]["formula"]
    assert "lag_seconds_observed" in c002_formula
    assert "<= max_lag_seconds" in c002_formula
    assert "ceil(max_lag_seconds" not in c002_formula
    assert "transport_seconds_observed" in rules["C-009"]["formula"]


def test_capability_registry_and_precheck_reject_explicitly() -> None:
    assert validate_capability_registry(load_yaml("capability-registry.v1.yaml")) == 20
    assert len(CAPABILITY_STATUS_BY_NAME) == 20
    assert require_v1_capability_contract(
        [CapabilityName.DAG_ROUTING, "ALTERNATIVE_RESOURCE"]
    ) == (CapabilityName.DAG_ROUTING, CapabilityName.ALTERNATIVE_RESOURCE)

    with pytest.raises(CapabilityContractError) as unsupported:
        require_v1_capability_contract(["SECONDARY_CAPACITY"])
    assert unsupported.value.code is ProductErrorCode.UNSUPPORTED_CAPABILITY
    assert unsupported.value.category is ProductErrorCategory.UNSUPPORTED_CAPABILITY
    assert unsupported.value.capability_names == ("SECONDARY_CAPACITY",)

    with pytest.raises(CapabilityContractError) as unknown:
        require_v1_capability_contract(["UNREGISTERED_CAPABILITY"])
    assert unknown.value.code is ProductErrorCode.INVALID_CAPABILITY_DECLARATION
    assert unknown.value.category is ProductErrorCategory.DATA_ERROR

    with pytest.raises(CapabilityContractError) as duplicate:
        require_v1_capability_contract(["DAG_ROUTING", "DAG_ROUTING"])
    assert duplicate.value.code is ProductErrorCode.DUPLICATE_CAPABILITY


def test_error_registry_matches_pure_mapping_and_error_v2_schema() -> None:
    category_count, code_count = validate_error_registry(
        load_yaml("error-code-registry.v1.yaml")
    )
    assert category_count == 7
    assert code_count == len(ProductErrorCode) == len(ERROR_CATEGORY_BY_CODE) == 19

    error_validator = validator("error.v2.schema.json")
    for code, category in ERROR_CATEGORY_BY_CODE.items():
        error_validator.validate(
            {
                "error_version": "error.v2",
                "category": category.value,
                "code": code.value,
                "message": "contract test",
                "details": [],
            }
        )

    with pytest.raises(ValidationError):
        error_validator.validate(
            {
                "error_version": "error.v2",
                "category": "SYSTEM_ERROR",
                "code": "INVALID_REFERENCE",
                "message": "mismatch",
                "details": [],
            }
        )


def test_error_v1_is_preserved_and_v2_is_not_silently_interchangeable() -> None:
    v1_schema = load_json("error.schema.json")
    v2_schema = load_json("error.v2.schema.json")
    assert v1_schema["$id"] == "urn:plantnexus:aps:schema:error:v1"
    assert v2_schema["$id"] == "urn:plantnexus:aps:schema:error:v2"
    v1 = {
        "error_version": "error.v1",
        "category": "DATA_ERROR",
        "code": "FUTURE_V1_CODE",
        "message": "v1 envelope remains separately valid",
        "details": [],
    }
    Draft202012Validator(v1_schema).validate(v1)
    with pytest.raises(ValidationError):
        Draft202012Validator(v2_schema).validate(v1)


def test_validation_report_v2_enforces_hard_c001_to_c011_shape() -> None:
    report_validator = validator("validation-report.v2.schema.json")
    passed = {
        "validation_report_version": "validation-report.v2",
        "problem_hash": "problem-hash",
        "status": "PASS",
        "hard_violation_count": 0,
        "violations": [],
    }
    report_validator.validate(passed)
    failed = {
        "validation_report_version": "validation-report.v2",
        "problem_hash": "problem-hash",
        "status": "FAIL",
        "hard_violation_count": 1,
        "violations": [
            {
                "constraint_id": "C-004",
                "severity": "HARD",
                "entity_ids": ["RESOURCE-001", "OP-001", "OP-002"],
                "observed_value": {"overlap_ticks": 1},
                "expected_rule": "resource intervals do not overlap",
                "message": "overlap",
            }
        ],
    }
    report_validator.validate(failed)

    pass_with_violation = copy.deepcopy(failed)
    pass_with_violation["status"] = "PASS"
    with pytest.raises(ValidationError):
        report_validator.validate(pass_with_violation)

    deferred_as_violation = copy.deepcopy(failed)
    deferred_as_violation["violations"][0]["constraint_id"] = "C-012"
    with pytest.raises(ValidationError):
        report_validator.validate(deferred_as_violation)


def test_state_registry_matches_enums_and_allows_only_explicit_pairs() -> None:
    machines, states, transitions = validate_state_registry(
        load_yaml("state-machines.v1.yaml")
    )
    assert (machines, states, transitions) == (3, 27, 42)
    for machine in StateMachineName:
        for source, target in transitions_for(machine):
            assert is_transition_allowed(machine, source, target)
            require_transition(machine, source, target)
        for terminal in terminal_states_for(machine):
            assert not any(
                source == terminal for source, _target in transitions_for(machine)
            )

    with pytest.raises(StateTransitionError) as invalid:
        require_transition(StateMachineName.SCHEDULE_VERSION, "DRAFT", "PUBLISHED")
    assert invalid.value.code is ProductErrorCode.INVALID_STATE_TRANSITION
    assert invalid.value.category is ProductErrorCategory.DATA_ERROR


def test_state_transition_schema_validates_names_while_table_authorizes_pairs() -> None:
    state_validator = validator("state-transition.schema.json")
    shape = {
        "state_transition_version": "state-transition.v1",
        "machine": "SCHEDULE_VERSION",
        "from_state": "DRAFT",
        "to_state": "PUBLISHED",
    }
    state_validator.validate(shape)
    assert not is_transition_allowed("SCHEDULE_VERSION", "DRAFT", "PUBLISHED")

    wrong_machine_state = copy.deepcopy(shape)
    wrong_machine_state["from_state"] = "SOLVING"
    with pytest.raises(ValidationError):
        state_validator.validate(wrong_machine_state)


def test_rule_contract_cli_writes_a_real_pass_report(tmp_path: Path) -> None:
    summary = validate_contract_artifacts(ROOT)
    assert summary == summary.__class__(11, 7, 20, 7, 19, 3, 27, 42)

    report_path = tmp_path / "rule-contract-report.json"
    assert main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "PASS"
    assert report["schema_set_version"] == "2.9.0"
    assert tuple(report["test_ids"]) == TEST_IDS
    assert report["issues"] == []
