"""Materialize and verify the P0 invalid schedule mutation suite.

Mutation construction is intentionally formula-free and separate from the
independent evaluator.  The command checks exact committed outcomes, JSON
Schema conformance, Rule Sheet metadata, deterministic replay, and complete
C-001..C-011 / required-mutation coverage.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.planning.validation.schedule_validator import (
    RULE_METADATA,
    ValidationInputError,
    fixture_problem_hash,
    validate_fixture_schedule,
    validation_error_from_report,
)


type JsonObject = dict[str, Any]

MUTATION_SUITE_VERSION = "validator-mutation-suite.v1"
EXPECTED_OUTCOMES_VERSION = "validator-expected-outcomes.v1"
COVERAGE_MATRIX_VERSION = "validator-coverage-matrix.v1"
REPORT_VERSION = "validator-mutation-report.v1"
CONSTRAINT_IDS = tuple(f"C-{number:03d}" for number in range(1, 12))
REQUIRED_MUTATION_CLASSES = (
    "missing_operation",
    "duplicate_operation",
    "wrong_resource",
    "machine_overlap",
    "calendar_overlap",
    "material_early_start",
    "completed_operation_rescheduled",
    "running_fact_changed",
    "hard_lock_movement",
    "max_lag_violation",
    "cross_workshop_transport_lag",
    "wrong_duration",
    "horizon_overflow",
)
MUTATION_ROOT = Path("fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS")


class MutationCheckError(ValueError):
    """The committed mutation plan, result, or coverage evidence is invalid."""


def _object(value: object, location: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MutationCheckError(f"{location} must be a string-keyed object")
    return cast(JsonObject, value)


def _array(value: object, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise MutationCheckError(f"{location} must be an array")
    return cast(list[Any], value)


def _text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise MutationCheckError(f"{location} must be a non-empty string")
    return value


def _integer(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MutationCheckError(f"{location} must be an integer")
    return value


def _load_json(path: Path) -> JsonObject:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), path.as_posix())
    except (OSError, json.JSONDecodeError) as error:
        raise MutationCheckError(f"cannot load {path.as_posix()}: {error}") from error


def _repository_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise MutationCheckError(f"artifact path escapes repository root: {relative}") from error
    return path


def _assignment_list(schedule: JsonObject) -> list[Any]:
    return _array(schedule.get("assignments"), "candidate_schedule.assignments")


def _find_assignment(schedule: JsonObject, operation_id: str) -> JsonObject:
    matches = [
        _object(value, f"assignment[{index}]")
        for index, value in enumerate(_assignment_list(schedule))
        if _object(value, f"assignment[{index}]").get("operation_id") == operation_id
    ]
    if len(matches) != 1:
        raise MutationCheckError(
            f"mutation expected one base assignment for {operation_id}, found {len(matches)}"
        )
    return matches[0]


def _record_collections(package: JsonObject) -> JsonObject:
    return _object(package.get("records"), "import_package.records")


def _record_list(package: JsonObject, collection: str) -> list[Any]:
    records = _record_collections(package)
    if collection not in records:
        raise MutationCheckError(f"unknown record collection {collection}")
    return _array(records[collection], f"import_package.records.{collection}")


def _select_record(records: Sequence[Any], operation: JsonObject) -> JsonObject:
    if "record_index" in operation:
        index = _integer(operation["record_index"], "mutation.record_index")
        if index < 0 or index >= len(records):
            raise MutationCheckError("mutation.record_index is out of range")
        return _object(records[index], f"records[{index}]")
    id_field = _text(operation.get("record_id_field"), "mutation.record_id_field")
    record_id = _text(operation.get("record_id"), "mutation.record_id")
    matches = [
        _object(record, f"records[{index}]")
        for index, record in enumerate(records)
        if _object(record, f"records[{index}]").get(id_field) == record_id
    ]
    if len(matches) != 1:
        raise MutationCheckError(
            f"mutation expected one {id_field}={record_id} record, found {len(matches)}"
        )
    return matches[0]


def _apply_operation(
    package: JsonObject, schedule: JsonObject, raw_operation: object, index: int
) -> None:
    operation = _object(raw_operation, f"mutation.operations[{index}]")
    kind = _text(operation.get("kind"), f"mutation.operations[{index}].kind")
    if kind == "remove_assignment":
        operation_id = _text(operation.get("operation_id"), "mutation.operation_id")
        values = _assignment_list(schedule)
        retained = [
            value
            for value in values
            if _object(value, "assignment").get("operation_id") != operation_id
        ]
        if len(values) - len(retained) != 1:
            raise MutationCheckError(
                f"remove_assignment expected one {operation_id} assignment"
            )
        schedule["assignments"] = retained
    elif kind == "duplicate_assignment":
        operation_id = _text(operation.get("operation_id"), "mutation.operation_id")
        _assignment_list(schedule).append(
            copy.deepcopy(_find_assignment(schedule, operation_id))
        )
    elif kind == "replace_assignment":
        operation_id = _text(operation.get("operation_id"), "mutation.operation_id")
        changes = _object(operation.get("changes"), "mutation.changes")
        if not changes or not set(changes).issubset({"resource_id", "start_tick", "end_tick"}):
            raise MutationCheckError("replace_assignment uses unsupported or empty changes")
        _find_assignment(schedule, operation_id).update(copy.deepcopy(changes))
    elif kind == "append_assignment":
        assignment = _object(operation.get("assignment"), "mutation.assignment")
        _assignment_list(schedule).append(copy.deepcopy(assignment))
    elif kind == "append_record":
        collection = _text(operation.get("collection"), "mutation.collection")
        record = _object(operation.get("record"), "mutation.record")
        _record_list(package, collection).append(copy.deepcopy(record))
    elif kind == "replace_record_field":
        collection = _text(operation.get("collection"), "mutation.collection")
        field = _text(operation.get("field"), "mutation.field")
        if "value" not in operation:
            raise MutationCheckError("replace_record_field requires value")
        record = _select_record(_record_list(package, collection), operation)
        if field not in record:
            raise MutationCheckError(f"replace_record_field cannot add absent field {field}")
        record[field] = copy.deepcopy(operation["value"])
    elif kind == "replace_schedule_field":
        field = _text(operation.get("field"), "mutation.field")
        if field not in schedule or "value" not in operation:
            raise MutationCheckError("replace_schedule_field requires existing field and value")
        schedule[field] = copy.deepcopy(operation["value"])
    else:
        raise MutationCheckError(f"unsupported mutation operation {kind}")


def materialize_case(
    base_package: Mapping[str, object],
    base_schedule: Mapping[str, object],
    case: Mapping[str, object],
) -> tuple[JsonObject, JsonObject]:
    """Apply one formula-free declarative mutation to fresh JSON copies."""

    package = cast(JsonObject, copy.deepcopy(dict(base_package)))
    schedule = cast(JsonObject, copy.deepcopy(dict(base_schedule)))
    case_object = _object(dict(case), "mutation case")
    operations = _array(case_object.get("operations"), "mutation.operations")
    if not operations:
        raise MutationCheckError("mutation case must contain at least one operation")
    for index, operation in enumerate(operations):
        _apply_operation(package, schedule, operation, index)
    return package, schedule


def _validate_schemas(
    root: Path, report: Mapping[str, object], error: Mapping[str, object] | None
) -> None:
    from jsonschema import Draft202012Validator, SchemaError, ValidationError

    schema_root = root / "schemas" / "json"
    report_schema = _load_json(schema_root / "validation-report.v2.schema.json")
    error_schema = _load_json(schema_root / "error.v2.schema.json")
    try:
        Draft202012Validator.check_schema(report_schema)
        Draft202012Validator.check_schema(error_schema)
        Draft202012Validator(report_schema).validate(report)
        if error is not None:
            Draft202012Validator(error_schema).validate(error)
    except (SchemaError, ValidationError) as schema_error:
        raise MutationCheckError(
            f"validator output does not satisfy a v2 JSON Schema: {schema_error.message}"
        ) from schema_error


def _validate_rule_metadata(root: Path) -> None:
    import yaml

    path = root / "schemas" / "rules" / "constraint-rule-sheet.v1.yaml"
    try:
        raw_document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise MutationCheckError(f"cannot parse {path.as_posix()}: {error}") from error
    document = _object(raw_document, path.as_posix())
    rules = _array(document.get("active_rules"), "active_rules")
    observed: dict[str, tuple[str, str]] = {}
    for index, raw_rule in enumerate(rules):
        rule = _object(raw_rule, f"active_rules[{index}]")
        violation = _object(rule.get("violation"), f"active_rules[{index}].violation")
        constraint_id = _text(
            rule.get("constraint_id"), f"active_rules[{index}].constraint_id"
        )
        observed[constraint_id] = (
            _text(violation.get("expected_rule"), "violation.expected_rule"),
            _text(violation.get("message"), "violation.message"),
        )
    if observed != RULE_METADATA:
        raise MutationCheckError("evaluator violation metadata differs from Rule Sheet")


def _case_map(document: JsonObject, location: str) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for index, raw_case in enumerate(_array(document.get("cases"), f"{location}.cases")):
        case = _object(raw_case, f"{location}.cases[{index}]")
        case_id = _text(case.get("case_id"), f"{location}.cases[{index}].case_id")
        if case_id in result:
            raise MutationCheckError(f"{location} duplicates case_id {case_id}")
        result[case_id] = case
    return result


def _strings(value: object, location: str) -> tuple[str, ...]:
    values = _array(value, location)
    if not all(isinstance(item, str) and item for item in values):
        raise MutationCheckError(f"{location} must be a string array")
    result = tuple(cast(list[str], values))
    if len(result) != len(set(result)):
        raise MutationCheckError(f"{location} contains duplicates")
    return result


def _validate_coverage(suite: JsonObject, coverage: JsonObject) -> None:
    if coverage.get("coverage_matrix_version") != COVERAGE_MATRIX_VERSION:
        raise MutationCheckError("unexpected coverage matrix version")
    if coverage.get("suite_id") != suite.get("suite_id"):
        raise MutationCheckError("coverage suite_id mismatch")
    cases = _case_map(suite, "mutation suite")

    expected_by_constraint: dict[str, list[str]] = {
        constraint_id: [] for constraint_id in CONSTRAINT_IDS
    }
    expected_by_class: dict[str, list[str]] = {
        mutation_class: [] for mutation_class in REQUIRED_MUTATION_CLASSES
    }
    for case_id, case in cases.items():
        mutation_class = _text(case.get("mutation_class"), f"{case_id}.mutation_class")
        if mutation_class not in expected_by_class:
            raise MutationCheckError(f"{case_id} has unsupported mutation_class")
        expected_by_class[mutation_class].append(case_id)
        for constraint_id in _strings(
            case.get("target_constraint_ids"), f"{case_id}.target_constraint_ids"
        ):
            if constraint_id not in expected_by_constraint:
                raise MutationCheckError(f"{case_id} targets unknown {constraint_id}")
            expected_by_constraint[constraint_id].append(case_id)

    observed_by_constraint: dict[str, list[str]] = {}
    for index, raw_entry in enumerate(
        _array(coverage.get("constraint_coverage"), "constraint_coverage")
    ):
        entry = _object(raw_entry, f"constraint_coverage[{index}]")
        constraint_id = _text(
            entry.get("constraint_id"), f"constraint_coverage[{index}].constraint_id"
        )
        if constraint_id in observed_by_constraint:
            raise MutationCheckError(
                f"constraint_coverage duplicates {constraint_id}"
            )
        observed_by_constraint[constraint_id] = list(
            _strings(entry.get("case_ids"), f"constraint_coverage[{index}].case_ids")
        )
    observed_by_class: dict[str, list[str]] = {}
    for index, raw_entry in enumerate(
        _array(
            coverage.get("required_mutation_coverage"),
            "required_mutation_coverage",
        )
    ):
        entry = _object(raw_entry, f"required_mutation_coverage[{index}]")
        mutation_class = _text(
            entry.get("mutation_class"),
            f"required_mutation_coverage[{index}].mutation_class",
        )
        if mutation_class in observed_by_class:
            raise MutationCheckError(
                f"required_mutation_coverage duplicates {mutation_class}"
            )
        observed_by_class[mutation_class] = list(
            _strings(
                entry.get("case_ids"),
                f"required_mutation_coverage[{index}].case_ids",
            )
        )
    expected_by_constraint = {
        key: sorted(value) for key, value in expected_by_constraint.items()
    }
    expected_by_class = {key: sorted(value) for key, value in expected_by_class.items()}
    observed_by_constraint = {
        key: sorted(value) for key, value in observed_by_constraint.items()
    }
    observed_by_class = {key: sorted(value) for key, value in observed_by_class.items()}
    if observed_by_constraint != expected_by_constraint:
        raise MutationCheckError("constraint coverage matrix differs from mutation suite")
    if observed_by_class != expected_by_class:
        raise MutationCheckError("required mutation coverage differs from mutation suite")
    if any(not case_ids for case_ids in expected_by_constraint.values()):
        raise MutationCheckError("one or more C-001..C-011 constraints lack mutation evidence")
    if any(not case_ids for case_ids in expected_by_class.values()):
        raise MutationCheckError("one or more required mutation classes lack evidence")
    if _strings(coverage.get("uncovered_constraints"), "uncovered_constraints"):
        raise MutationCheckError("coverage matrix declares uncovered constraints")
    if _strings(
        coverage.get("uncovered_required_mutations"),
        "uncovered_required_mutations",
    ):
        raise MutationCheckError("coverage matrix declares uncovered required mutations")


def run_mutation_checks(root: Path) -> JsonObject:
    """Verify positive, negative, exact-outcome, schema, and coverage evidence."""

    root = root.resolve()
    fixture_root = root / MUTATION_ROOT
    suite = _load_json(fixture_root / "mutation-suite.json")
    expected = _load_json(fixture_root / "expected-outcomes.json")
    coverage = _load_json(fixture_root / "coverage-matrix.json")
    if suite.get("mutation_suite_version") != MUTATION_SUITE_VERSION:
        raise MutationCheckError("unexpected mutation suite version")
    if expected.get("expected_outcomes_version") != EXPECTED_OUTCOMES_VERSION:
        raise MutationCheckError("unexpected expected outcomes version")
    suite_id = _text(suite.get("suite_id"), "mutation_suite.suite_id")
    if expected.get("suite_id") != suite_id:
        raise MutationCheckError("expected outcomes suite_id mismatch")

    base = _object(suite.get("base_fixture"), "mutation_suite.base_fixture")
    package = _load_json(
        _repository_path(
            root,
            _text(base.get("import_package"), "base_fixture.import_package"),
        )
    )
    schedule = _load_json(
        _repository_path(
            root,
            _text(base.get("candidate_schedule"), "base_fixture.candidate_schedule"),
        )
    )
    expected_dataset_hash = _text(
        base.get("canonical_dataset_hash"), "base_fixture.canonical_dataset_hash"
    )
    observed_problem_hash = fixture_problem_hash(package)
    if observed_problem_hash != f"fixture-problem:{expected_dataset_hash}":
        raise MutationCheckError("base fixture hash differs from mutation suite pin")

    _validate_rule_metadata(root)
    _validate_coverage(suite, coverage)
    positive_report = validate_fixture_schedule(package, schedule)
    positive_error = validation_error_from_report(positive_report)
    _validate_schemas(root, positive_report, positive_error)
    expected_positive = _object(expected.get("positive"), "expected_outcomes.positive")
    if positive_report != expected_positive.get("validation_report"):
        raise MutationCheckError("positive Golden report differs from expected outcome")
    if positive_error != expected_positive.get("error"):
        raise MutationCheckError("positive Golden error mapping differs from expected outcome")

    cases = _case_map(suite, "mutation suite")
    expected_cases = _case_map(expected, "expected outcomes")
    if set(cases) != set(expected_cases):
        raise MutationCheckError("mutation and expected outcome case IDs differ")

    summaries: list[JsonObject] = []
    for case_id, case in cases.items():
        mutated_package, mutated_schedule = materialize_case(package, schedule, case)
        report = validate_fixture_schedule(mutated_package, mutated_schedule)
        error = validation_error_from_report(report)
        replay_report = validate_fixture_schedule(mutated_package, mutated_schedule)
        if replay_report != report:
            raise MutationCheckError(f"{case_id} evaluator output is nondeterministic")
        _validate_schemas(root, report, error)
        expected_case = expected_cases[case_id]
        if report != expected_case.get("validation_report"):
            raise MutationCheckError(f"{case_id} report differs from expected outcome")
        if error != expected_case.get("error"):
            raise MutationCheckError(f"{case_id} error differs from expected outcome")
        if report["status"] != "FAIL" or error is None:
            raise MutationCheckError(f"{case_id} did not produce a mapped validation failure")
        actual_constraint_ids = sorted(
            {str(value["constraint_id"]) for value in report["violations"]}
        )
        target_constraint_ids = sorted(
            _strings(case.get("target_constraint_ids"), f"{case_id}.target_constraint_ids")
        )
        if actual_constraint_ids != target_constraint_ids:
            raise MutationCheckError(
                f"{case_id} constraints differ: "
                f"actual={actual_constraint_ids}, target={target_constraint_ids}"
            )
        summaries.append(
            {
                "case_id": case_id,
                "mutation_class": case["mutation_class"],
                "status": report["status"],
                "hard_violation_count": report["hard_violation_count"],
                "constraint_ids": actual_constraint_ids,
                "problem_hash": report["problem_hash"],
            }
        )

    return {
        "schema_version": REPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "result": "PASS",
        "scope": "P0 fixture-local independent rule evaluator",
        "suite_id": suite_id,
        "counts": {
            "cases": len(cases),
            "constraints_covered": len(CONSTRAINT_IDS),
            "required_mutation_classes": len(REQUIRED_MUTATION_CLASSES),
            "hard_violations": sum(
                int(summary["hard_violation_count"]) for summary in summaries
            ),
        },
        "positive": {
            "status": positive_report["status"],
            "hard_violation_count": positive_report["hard_violation_count"],
            "problem_hash": positive_report["problem_hash"],
        },
        "cases": summaries,
        "test_ids": [
            "TEST-VALIDATOR-MUTATION",
            "TEST-CALENDAR",
            "TEST-MATERIAL",
            "TEST-RUNNING",
            "TEST-INF-LOCK",
            "TEST-MAX-LAG",
            "TEST-CROSS-WORKSHOP",
            "TEST-INF-HORIZON",
            "TEST-INF-NO-RESOURCE",
        ],
        "issues": [],
    }


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
    root = cast(Path, args.root)
    report_path = cast(Path | None, args.report)
    try:
        report = run_mutation_checks(root)
    except (
        MutationCheckError,
        ValidationInputError,
        OSError,
        ValueError,
        KeyError,
    ) as error:
        report = {
            "schema_version": REPORT_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "result": "FAIL",
            "issues": [str(error)],
        }
        if report_path is not None:
            _write_report(report_path, report)
        print(f"FAIL validator mutations: {error}")
        return 1
    if report_path is not None:
        _write_report(report_path, report)
    counts = _object(report["counts"], "report.counts")
    print(
        "PASS validator mutations: "
        f"cases={counts['cases']} constraints={counts['constraints_covered']} "
        f"classes={counts['required_mutation_classes']} "
        f"violations={counts['hard_violations']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CONSTRAINT_IDS",
    "COVERAGE_MATRIX_VERSION",
    "EXPECTED_OUTCOMES_VERSION",
    "MUTATION_SUITE_VERSION",
    "MutationCheckError",
    "materialize_case",
    "run_mutation_checks",
]
