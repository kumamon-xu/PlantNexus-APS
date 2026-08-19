"""Completeness checks for P0 rule/state/error/capability contract artifacts.

This module validates metadata and cross-registry consistency only. It does not
accept a candidate schedule and is not the independent ScheduleValidator.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app import SCHEMA_VERSION, SPEC_VERSION
from app.domain.capabilities import (
    CAPABILITY_STATUS_BY_NAME,
    CapabilityName,
    CapabilityStatus,
)
from app.domain.errors import (
    ERROR_CATEGORY_BY_CODE,
    ProductErrorCategory,
    ProductErrorCode,
)
from app.domain.state_machines import (
    StateMachineName,
    states_for,
    terminal_states_for,
    transitions_for,
)


RULE_SHEET_VERSION = "constraint-rule-sheet.v1"
V1_CONSTRAINT_IDS = tuple(f"C-{number:03d}" for number in range(1, 12))
DEFERRED_CONSTRAINT_IDS = tuple(f"C-{number:03d}" for number in range(12, 19))


class RuleSheetContractError(ValueError):
    """A machine-readable P0 rule contract is incomplete or inconsistent."""


@dataclass(frozen=True)
class RuleSheetSummary:
    active_constraints: int
    deferred_constraints: int
    capabilities: int
    error_categories: int
    error_codes: int
    state_machines: int
    states: int
    transitions: int


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise RuleSheetContractError(f"{location} must be a string-keyed object")
    return cast(Mapping[str, Any], value)


def _items(value: object, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise RuleSheetContractError(f"{location} must be an array")
    return cast(list[Any], value)


def _strings(value: object, location: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    items = _items(value, location)
    if (not allow_empty and not items) or not all(
        isinstance(item, str) and item for item in items
    ):
        qualifier = "possibly empty" if allow_empty else "non-empty"
        raise RuleSheetContractError(f"{location} must be a {qualifier} string array")
    return tuple(cast(list[str], items))


def _text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuleSheetContractError(f"{location} must be a non-empty string")
    return value


def _exact_keys(document: Mapping[str, Any], keys: set[str], location: str) -> None:
    actual = set(document)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise RuleSheetContractError(
            f"{location} keys differ; missing={missing}, extra={extra}"
        )


def _unique(values: tuple[str, ...], location: str) -> None:
    if len(values) != len(set(values)):
        raise RuleSheetContractError(f"{location} contains duplicates")


def validate_constraint_rule_sheet(document: Mapping[str, Any]) -> RuleSheetSummary:
    """Validate completeness without evaluating any schedule formula."""

    _exact_keys(
        document,
        {
            "rule_sheet_version",
            "spec_version",
            "validation_report_contract",
            "active_rules",
            "deferred_rules",
        },
        "constraint rule sheet",
    )
    if document["rule_sheet_version"] != RULE_SHEET_VERSION:
        raise RuleSheetContractError("unexpected constraint rule sheet version")
    if document["spec_version"] != SPEC_VERSION:
        raise RuleSheetContractError("constraint rule sheet spec version mismatch")
    if document["validation_report_contract"] != "validation-report.v2":
        raise RuleSheetContractError("rule sheet must target validation-report.v2")

    active = _items(document["active_rules"], "active_rules")
    active_ids: list[str] = []
    active_keys = {
        "constraint_id",
        "title",
        "status",
        "contract_status",
        "inputs",
        "formula",
        "positive_example",
        "negative_example",
        "violation",
        "test_ids",
        "open_questions",
    }
    violation_keys = {
        "error_category",
        "error_code",
        "severity",
        "observed_value",
        "expected_rule",
        "message",
    }
    for index, raw_rule in enumerate(active):
        location = f"active_rules[{index}]"
        rule = _mapping(raw_rule, location)
        _exact_keys(rule, active_keys, location)
        constraint_id = _text(rule["constraint_id"], f"{location}.constraint_id")
        active_ids.append(constraint_id)
        if rule["status"] != "V1_REQUIRED":
            raise RuleSheetContractError(f"{location}.status must be V1_REQUIRED")
        for field in (
            "title",
            "contract_status",
            "formula",
            "positive_example",
            "negative_example",
        ):
            _text(rule[field], f"{location}.{field}")
        _strings(rule["inputs"], f"{location}.inputs")
        test_ids = _strings(rule["test_ids"], f"{location}.test_ids")
        _unique(test_ids, f"{location}.test_ids")
        if "TEST-RULE-SHEET-001" not in test_ids:
            raise RuleSheetContractError(f"{location} lacks TEST-RULE-SHEET-001")
        open_questions = _strings(
            rule["open_questions"], f"{location}.open_questions", allow_empty=True
        )
        if any(not value.startswith("OPEN-") for value in open_questions):
            raise RuleSheetContractError(f"{location} has invalid PROD_OPEN reference")

        violation = _mapping(rule["violation"], f"{location}.violation")
        _exact_keys(violation, violation_keys, f"{location}.violation")
        if (
            violation["error_category"] != ProductErrorCategory.VALIDATION_FAILED.value
            or violation["error_code"]
            != ProductErrorCode.SCHEDULE_VALIDATION_FAILED.value
            or violation["severity"] != "HARD"
        ):
            raise RuleSheetContractError(f"{location} has an invalid violation mapping")
        for field in ("observed_value", "expected_rule", "message"):
            _text(violation[field], f"{location}.violation.{field}")

    active_id_tuple = tuple(active_ids)
    _unique(active_id_tuple, "active constraint IDs")
    if set(active_id_tuple) != set(V1_CONSTRAINT_IDS):
        raise RuleSheetContractError("active rules must cover exactly C-001 through C-011")

    deferred = _items(document["deferred_rules"], "deferred_rules")
    deferred_ids: list[str] = []
    deferred_keys = {
        "constraint_id",
        "title",
        "status",
        "capability",
        "behavior",
        "error_category",
        "error_code",
        "test_ids",
    }
    for index, raw_rule in enumerate(deferred):
        location = f"deferred_rules[{index}]"
        rule = _mapping(raw_rule, location)
        _exact_keys(rule, deferred_keys, location)
        constraint_id = _text(rule["constraint_id"], f"{location}.constraint_id")
        deferred_ids.append(constraint_id)
        for field in ("title", "capability", "behavior"):
            _text(rule[field], f"{location}.{field}")
        if (
            rule["status"] != "UNSUPPORTED"
            or rule["error_category"]
            != ProductErrorCategory.UNSUPPORTED_CAPABILITY.value
            or rule["error_code"] != ProductErrorCode.UNSUPPORTED_CAPABILITY.value
        ):
            raise RuleSheetContractError(f"{location} must explicitly reject capability")
        test_ids = _strings(rule["test_ids"], f"{location}.test_ids")
        if not {"TEST-RULE-SHEET-001", "TEST-CAPABILITY-001"}.issubset(test_ids):
            raise RuleSheetContractError(f"{location} lacks capability contract tests")

    deferred_id_tuple = tuple(deferred_ids)
    _unique(deferred_id_tuple, "deferred constraint IDs")
    if set(deferred_id_tuple) != set(DEFERRED_CONSTRAINT_IDS):
        raise RuleSheetContractError("deferred rules must cover exactly C-012 through C-018")

    return RuleSheetSummary(
        active_constraints=len(active),
        deferred_constraints=len(deferred),
        capabilities=0,
        error_categories=0,
        error_codes=0,
        state_machines=0,
        states=0,
        transitions=0,
    )


def validate_capability_registry(document: Mapping[str, Any]) -> int:
    _exact_keys(
        document,
        {"capability_registry_version", "implementation_claim", "capabilities"},
        "capability registry",
    )
    if document["capability_registry_version"] != "capability-registry.v1":
        raise RuleSheetContractError("unexpected capability registry version")
    if document["implementation_claim"] is not False:
        raise RuleSheetContractError("capability registry must not claim implementation")

    entries = _items(document["capabilities"], "capabilities")
    names: list[CapabilityName] = []
    keys = {"capability", "status", "phase", "constraint_ids", "precheck_behavior"}
    for index, raw_entry in enumerate(entries):
        location = f"capabilities[{index}]"
        entry = _mapping(raw_entry, location)
        _exact_keys(entry, keys, location)
        raw_name = _text(entry["capability"], f"{location}.capability")
        try:
            name = CapabilityName(raw_name)
            status = CapabilityStatus(_text(entry["status"], f"{location}.status"))
        except ValueError as error:
            raise RuleSheetContractError(f"{location} uses an unknown enum value") from error
        names.append(name)
        if status is not CAPABILITY_STATUS_BY_NAME[name]:
            raise RuleSheetContractError(f"{location} status differs from pure registry")
        _text(entry["phase"], f"{location}.phase")
        constraint_ids = _strings(
            entry["constraint_ids"], f"{location}.constraint_ids", allow_empty=True
        )
        if any(
            value not in V1_CONSTRAINT_IDS + DEFERRED_CONSTRAINT_IDS
            for value in constraint_ids
        ):
            raise RuleSheetContractError(f"{location} references an unknown C-ID")
        expected_behavior = (
            "ALLOW_CONTRACT_DECLARATION"
            if status is CapabilityStatus.V1_SUPPORTED
            else ProductErrorCode.UNSUPPORTED_CAPABILITY.value
        )
        if entry["precheck_behavior"] != expected_behavior:
            raise RuleSheetContractError(f"{location} has the wrong precheck behavior")

    if len(names) != len(set(names)) or set(names) != set(CAPABILITY_STATUS_BY_NAME):
        raise RuleSheetContractError("capability registry must cover each pure enum once")
    return len(entries)


def validate_error_registry(document: Mapping[str, Any]) -> tuple[int, int]:
    _exact_keys(document, {"error_registry_version", "categories", "codes"}, "error registry")
    if document["error_registry_version"] != "error-code-registry.v1":
        raise RuleSheetContractError("unexpected error registry version")
    categories = _strings(document["categories"], "error categories")
    _unique(categories, "error categories")
    if set(categories) != {category.value for category in ProductErrorCategory}:
        raise RuleSheetContractError("error registry must contain exactly seven categories")

    entries = _items(document["codes"], "error codes")
    registered: dict[ProductErrorCode, ProductErrorCategory] = {}
    for index, raw_entry in enumerate(entries):
        location = f"codes[{index}]"
        entry = _mapping(raw_entry, location)
        _exact_keys(entry, {"code", "category", "meaning"}, location)
        try:
            code = ProductErrorCode(_text(entry["code"], f"{location}.code"))
            category = ProductErrorCategory(
                _text(entry["category"], f"{location}.category")
            )
        except ValueError as error:
            raise RuleSheetContractError(f"{location} uses an unknown enum value") from error
        if code in registered:
            raise RuleSheetContractError(f"{location} duplicates {code.value}")
        registered[code] = category
        _text(entry["meaning"], f"{location}.meaning")
    if registered != dict(ERROR_CATEGORY_BY_CODE):
        raise RuleSheetContractError("error YAML and pure code mappings differ")
    return len(categories), len(entries)


def validate_state_registry(document: Mapping[str, Any]) -> tuple[int, int, int]:
    _exact_keys(
        document,
        {"state_registry_version", "invalid_transition_error_code", "machines"},
        "state registry",
    )
    if document["state_registry_version"] != "state-machines.v1":
        raise RuleSheetContractError("unexpected state registry version")
    if document["invalid_transition_error_code"] != ProductErrorCode.INVALID_STATE_TRANSITION.value:
        raise RuleSheetContractError("state registry uses the wrong rejection code")

    entries = _items(document["machines"], "machines")
    seen: set[StateMachineName] = set()
    state_count = 0
    transition_count = 0
    for index, raw_entry in enumerate(entries):
        location = f"machines[{index}]"
        entry = _mapping(raw_entry, location)
        _exact_keys(entry, {"machine", "states", "terminal_states", "transitions"}, location)
        try:
            machine = StateMachineName(_text(entry["machine"], f"{location}.machine"))
        except ValueError as error:
            raise RuleSheetContractError(f"{location} names an unknown machine") from error
        if machine in seen:
            raise RuleSheetContractError(f"{location} duplicates {machine.value}")
        seen.add(machine)
        states = _strings(entry["states"], f"{location}.states")
        terminals = _strings(entry["terminal_states"], f"{location}.terminal_states")
        _unique(states, f"{location}.states")
        _unique(terminals, f"{location}.terminal_states")
        if set(states) != states_for(machine):
            raise RuleSheetContractError(f"{location} states differ from pure enums")
        if set(terminals) != terminal_states_for(machine):
            raise RuleSheetContractError(f"{location} terminal states differ from pure table")

        transitions: set[tuple[str, str]] = set()
        for transition_index, raw_transition in enumerate(
            _items(entry["transitions"], f"{location}.transitions")
        ):
            transition_location = f"{location}.transitions[{transition_index}]"
            transition = _mapping(raw_transition, transition_location)
            _exact_keys(transition, {"from", "to", "guard", "evidence"}, transition_location)
            pair = (
                _text(transition["from"], f"{transition_location}.from"),
                _text(transition["to"], f"{transition_location}.to"),
            )
            if pair in transitions:
                raise RuleSheetContractError(f"{transition_location} is duplicated")
            transitions.add(pair)
            _text(transition["guard"], f"{transition_location}.guard")
            _text(transition["evidence"], f"{transition_location}.evidence")
        if transitions != transitions_for(machine):
            raise RuleSheetContractError(f"{location} transitions differ from pure table")
        state_count += len(states)
        transition_count += len(transitions)

    if seen != set(StateMachineName):
        raise RuleSheetContractError("state registry must contain all three machines")
    return len(entries), state_count, transition_count


def _load_yaml(path: Path) -> Mapping[str, Any]:
    import yaml

    return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), path.as_posix())


def _load_json(path: Path) -> Mapping[str, Any]:
    return _mapping(json.loads(path.read_text(encoding="utf-8")), path.as_posix())


def _validate_json_schemas(root: Path) -> None:
    from jsonschema import Draft202012Validator, ValidationError

    schema_root = root / "schemas" / "json"
    schema_names = (
        "error.v2.schema.json",
        "validation-report.v2.schema.json",
        "state-transition.schema.json",
    )
    schemas = {name: _load_json(schema_root / name) for name in schema_names}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
        if schema["$schema"] != "https://json-schema.org/draft/2020-12/schema":
            raise RuleSheetContractError("rule contract schema uses the wrong dialect")

    error_validator = Draft202012Validator(schemas["error.v2.schema.json"])
    for code, category in ERROR_CATEGORY_BY_CODE.items():
        error_validator.validate(
            {
                "error_version": "error.v2",
                "category": category.value,
                "code": code.value,
                "message": code.value,
                "details": [],
            }
        )
    try:
        error_validator.validate(
            {
                "error_version": "error.v2",
                "category": "SYSTEM_ERROR",
                "code": "INVALID_REFERENCE",
                "message": "mismatch",
                "details": [],
            }
        )
    except ValidationError:
        pass
    else:
        raise RuleSheetContractError("error.v2 accepts a code/category mismatch")

    validation_validator = Draft202012Validator(
        schemas["validation-report.v2.schema.json"]
    )
    validation_validator.validate(
        {
            "validation_report_version": "validation-report.v2",
            "problem_hash": "contract-check",
            "status": "PASS",
            "hard_violation_count": 0,
            "violations": [],
        }
    )
    state_validator = Draft202012Validator(schemas["state-transition.schema.json"])
    for machine in StateMachineName:
        source, target = sorted(transitions_for(machine))[0]
        state_validator.validate(
            {
                "state_transition_version": "state-transition.v1",
                "machine": machine.value,
                "from_state": source,
                "to_state": target,
            }
        )


def validate_contract_artifacts(root: Path) -> RuleSheetSummary:
    rule_root = root / "schemas" / "rules"
    base = validate_constraint_rule_sheet(
        _load_yaml(rule_root / "constraint-rule-sheet.v1.yaml")
    )
    capability_count = validate_capability_registry(
        _load_yaml(rule_root / "capability-registry.v1.yaml")
    )
    error_category_count, error_code_count = validate_error_registry(
        _load_yaml(rule_root / "error-code-registry.v1.yaml")
    )
    state_machine_count, state_count, transition_count = validate_state_registry(
        _load_yaml(rule_root / "state-machines.v1.yaml")
    )
    _validate_json_schemas(root)

    dictionary = _load_yaml(root / "schemas" / "data_dictionary.yaml")
    if dictionary.get("schema_set_version") != SCHEMA_VERSION:
        raise RuleSheetContractError("data dictionary schema set version mismatch")
    if SCHEMA_VERSION != "1.1.0":
        raise RuleSheetContractError("package schema set version mismatch")

    validation_sources = root / "backend" / "app" / "planning" / "validation"
    backend_module = "app.planning." + "backends"
    solver_module = "or" + "tools"
    forbidden_imports = (
        f"from {backend_module}",
        f"import {backend_module}",
        f"from {solver_module}",
        f"import {solver_module}",
    )
    for source_path in validation_sources.glob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        if any(token in source for token in forbidden_imports):
            raise RuleSheetContractError(
                f"validation contract imports a solver/backend: {source_path.name}"
            )

    return RuleSheetSummary(
        active_constraints=base.active_constraints,
        deferred_constraints=base.deferred_constraints,
        capabilities=capability_count,
        error_categories=error_category_count,
        error_codes=error_code_count,
        state_machines=state_machine_count,
        states=state_count,
        transitions=transition_count,
    )


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    root = cast(Path, args.root).resolve()
    report_path = cast(Path | None, args.report)
    generated_at = datetime.now(UTC).isoformat()
    try:
        summary = validate_contract_artifacts(root)
    except (RuleSheetContractError, OSError, ValueError, KeyError) as error:
        report: dict[str, object] = {
            "schema_version": "rule-contract-report.v1",
            "generated_at": generated_at,
            "result": "FAIL",
            "schema_set_version": SCHEMA_VERSION,
            "issues": [str(error)],
        }
        if report_path is not None:
            _write_report(report_path, report)
        print(f"FAIL rule contracts: {error}")
        return 1

    report = {
        "schema_version": "rule-contract-report.v1",
        "generated_at": generated_at,
        "result": "PASS",
        "schema_set_version": SCHEMA_VERSION,
        "counts": asdict(summary),
        "test_ids": [
            "TEST-RULE-SHEET-001",
            "TEST-STATE-TRANSITION-001",
            "TEST-ERROR-MAPPING-001",
            "TEST-CAPABILITY-001",
        ],
        "issues": [],
    }
    if report_path is not None:
        _write_report(report_path, report)
    print(
        "PASS rule contracts: "
        f"active={summary.active_constraints} deferred={summary.deferred_constraints} "
        f"capabilities={summary.capabilities} error_codes={summary.error_codes} "
        f"machines={summary.state_machines} states={summary.states} "
        f"transitions={summary.transitions}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFERRED_CONSTRAINT_IDS",
    "RULE_SHEET_VERSION",
    "V1_CONSTRAINT_IDS",
    "RuleSheetContractError",
    "RuleSheetSummary",
    "main",
    "validate_capability_registry",
    "validate_constraint_rule_sheet",
    "validate_contract_artifacts",
    "validate_error_registry",
    "validate_state_registry",
]
