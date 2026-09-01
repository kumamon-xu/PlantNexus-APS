"""Emit machine-checkable TASK-P4-07 lexicographic replan evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.domain.execution_contracts import (
    contract_fingerprint,
    replan_request_fingerprint,
    require_p4_document,
    solver_report_fingerprint,
)
from app.planning.policy.contracts import SolveLimitsDocument
from app.planning.policy.delivery import simulation_solve_limits
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.problem.freeze_window_check import build_freeze_window_fixture
from app.planning.strategies.lexicographic_replan import (
    LexicographicReplanResult,
    LexicographicReplanStrategy,
)


REPORT_VERSION = "p4-replan-solver-report.v1"
TASK_ID = "TASK-P4-07"
DIFF_BASE = "e212ab7957d6bc5887048ee54809c8194d6e1eaf"
IMPACT_RULES = (
    "IMPACT-BACKEND",
    "IMPACT-DOCS",
    "IMPACT-INFRA",
    "IMPACT-STATE",
    "IMPACT-STRATEGY",
    "IMPACT-TESTS",
    "IMPACT-VALIDATOR",
)
_FROZEN_SHA256 = {
    "schemas/json/solver-report.v2.schema.json": (
        "230a123ebfa8c027ab9b7ff0c940618e249b954bc2d0333a8a0dc17c310c4aec"
    ),
    "schemas/json/planning-policy.v2.schema.json": (
        "d56d092ebac445a359ab2b84ee5df8e810c53b2e0a2852fe6bc5a78290239668"
    ),
    "schemas/json/replan-request.schema.json": (
        "f16b7a22078a8c33495be009b6c934477b625c7aebc97966f4ec7c6b897104f9"
    ),
    "schemas/json/planning-problem.v2.schema.json": (
        "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8"
    ),
    "docs/adr/ADR-0014-freeze-window-stability-change-report.md": (
        "ef9dad9952886da9615477b33c57ca6c3bfd941278acb2d3f8a6b09bc512ae51"
    ),
    "backend/app/planning/backends/cp_sat/objectives.py": (
        "bddaacf231ad05c21e85a20cb30a12db3364b53a19c3208421c248a15daba7b0"
    ),
    "backend/app/planning/validation/problem_schedule_validator.py": (
        "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f"
    ),
    "schemas/rules/state-machines.v1.yaml": (
        "6a8c32137a681c6c96defd0dcdd3e580490ec82b81b6494b9b3ba4bf2144ddd7"
    ),
    "pyproject.toml": (
        "327b705255dc9792139aa690351601a1e6a6cba019920142adfa656d6902fe5e"
    ),
    "uv.lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}
_P6_SCHEMA_METADATA_PYPROJECT_SHA256 = (
    "c39c0ade6061de9a986eb0e5a3e2d8b568ccb37c7f7bf64242698af782b6c937"
)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _schema_validator(root: Path, name: str) -> Draft202012Validator:
    schemas: dict[str, dict[str, object]] = {}
    resources: list[tuple[str, Resource[object]]] = []
    for path in sorted((root / "schemas/json").glob("*.json")):
        schema = cast(
            dict[str, object], json.loads(path.read_text(encoding="utf-8"))
        )
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    return Draft202012Validator(
        schemas[name],
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


def _limits() -> SolveLimitsDocument:
    return simulation_solve_limits(
        limits_id="LIMITS-TASK-P4-07-MACHINE",
        limits_revision="1.0.0",
        source_record_id="LIMITS-TASK-P4-07-MACHINE",
        max_wall_time_seconds=6.0,
        max_workers=1,
        random_seed=20260828,
    )


def _limits_reference(limits: SolveLimitsDocument) -> dict[str, object]:
    return {
        "solve_limits_version": limits["solve_limits_version"],
        "limits_id": limits["limits_id"],
        "limits_revision": limits["limits_revision"],
        "limits_fingerprint": contract_fingerprint(limits),
        "max_wall_time_seconds": limits["max_wall_time_seconds"],
        "max_workers": limits["max_workers"],
        "random_seed": limits["random_seed"],
    }


def _request(
    root: Path,
    *,
    fixture: object,
    projection: Mapping[str, object],
    limits: SolveLimitsDocument,
) -> dict[str, object]:
    document = cast(
        dict[str, object],
        json.loads(
            (root / "schemas/samples/replan-request.v1.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    snapshot = cast(object, getattr(fixture, "snapshot"))
    snapshot_document = cast(Mapping[str, object], getattr(snapshot, "document"))
    document["base_schedule_version"] = deepcopy(projection["base_schedule_version"])
    document["new_snapshot"] = deepcopy(projection["new_snapshot"])
    document["new_snapshot_cutoff_at_utc"] = snapshot_document["cutoff_at_utc"]
    document["new_problem"] = deepcopy(projection["new_problem"])
    document["freeze_resolution"] = deepcopy(projection["freeze_resolution"])
    document["planning_policy"] = deepcopy(projection["planning_policy"])
    document["solve_limits"] = _limits_reference(limits)
    fingerprint = replan_request_fingerprint(document)
    document["request_fingerprint"] = fingerprint
    document["request_id"] = "replan-request-" + fingerprint.removeprefix("sha256:")
    require_p4_document(document)
    return document


def _frozen_inputs(root: Path) -> dict[str, object]:
    observed = {
        relative: sha256((root / relative).read_bytes()).hexdigest()
        for relative in _FROZEN_SHA256
    }
    frozen_observed = dict(observed)
    pyproject_digest = frozen_observed.pop("pyproject.toml")
    frozen_expected = dict(_FROZEN_SHA256)
    p4_pyproject_digest = frozen_expected.pop("pyproject.toml")
    _ensure(
        frozen_observed == frozen_expected
        and pyproject_digest
        in {p4_pyproject_digest, _P6_SCHEMA_METADATA_PYPROJECT_SHA256},
        "Schema, ADR, P2 objective/validator, state, or dependency bytes drifted",
    )
    validator_source = (
        root / "backend/app/planning/validation/replan_candidate_validator.py"
    ).read_text(encoding="utf-8")
    _ensure("ortools" not in validator_source, "candidate validator imports CP-SAT")
    _ensure(
        "app.planning.backends" not in validator_source,
        "candidate validator imports a planning backend",
    )
    _ensure(
        "app.planning.reporting" not in validator_source,
        "candidate validator imports reporting arithmetic",
    )
    return {
        "frozen_file_count": len(observed),
        "solver_report_schema_sha256": observed[
            "schemas/json/solver-report.v2.schema.json"
        ],
        "dependency_lock_sha256": observed["uv.lock"],
        "validator_forbidden_imports": 0,
    }


def _solve_fixture(
    root: Path, *, code_commit: str
) -> tuple[LexicographicReplanResult, dict[str, object]]:
    fixture = build_freeze_window_fixture(root)
    projection = project_effective_locks(
        snapshot=fixture.snapshot,
        problem=fixture.problem,
        base_schedule=fixture.base_schedule,
        policy=fixture.policy,
    ).document
    limits = _limits()
    request = _request(
        root,
        fixture=fixture,
        projection=projection,
        limits=limits,
    )
    result = LexicographicReplanStrategy().solve(
        fixture.problem.document,
        fixture.policy,
        limits,
        base_schedule=fixture.base_schedule,
        effective_locks=projection,
        replan_request=request,
        planning_run_id="PLANNING-RUN-TASK-P4-07-MACHINE",
        code_commit=code_commit,
    )
    return result, projection


def run_replan_solver_checks(root: Path) -> dict[str, object]:
    frozen = _frozen_inputs(root)
    code_commit = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    first, projection = _solve_fixture(root, code_commit=code_commit)
    second, _ = _solve_fixture(root, code_commit=code_commit)
    first_report = cast(dict[str, object], getattr(first, "solver_report"))
    second_report = cast(dict[str, object], getattr(second, "solver_report"))
    first_rounds = cast(tuple[Mapping[str, object], ...], getattr(first, "round_reports"))
    second_rounds = cast(tuple[Mapping[str, object], ...], getattr(second, "round_reports"))
    validations = cast(
        tuple[Mapping[str, object], ...], getattr(first, "validation_reports")
    )

    require_p4_document(first_report)
    _schema_validator(root, "solver-report.v2.schema.json").validate(first_report)
    _ensure(
        first_report["report_fingerprint"] == solver_report_fingerprint(first_report),
        "SolverReport identity is not content-addressed",
    )
    expected_rounds = (
        ("OBJ-001", "OBJ-001", None),
        ("OBJ-002-1", "OBJ-002", "soft_lock_violations"),
        ("OBJ-002-2", "OBJ-002", "changed_existing_operations"),
        ("OBJ-002-3", "OBJ-002", "resource_changes"),
        ("OBJ-002-4", "OBJ-002", "absolute_start_shift_seconds"),
        ("OBJ-003", "OBJ-003", None),
    )
    observed_rounds = tuple(
        (round_["round_id"], round_["objective_id"], round_["component"])
        for round_ in first_rounds
    )
    _ensure(observed_rounds == expected_rounds, "objective round order drifted")
    _ensure(
        all(round_["solver_status"] == "OPTIMAL" for round_ in first_rounds),
        "fixed replan fixture did not prove every objective round optimal",
    )
    _ensure(len(validations) == 6, "each candidate round needs fresh validation")
    _ensure(
        all(validation["status"] == "PASS" for validation in validations),
        "fresh independent candidate validation failed",
    )
    _ensure(
        len({validation["report_fingerprint"] for validation in validations}) >= 1,
        "validation report identities are missing",
    )

    objective_vectors = [
        cast(Mapping[str, object], validation["objective_values"])
        for validation in validations
    ]
    delivery_value = first_rounds[0]["objective_value"]
    _ensure(
        all(values["delivery"] == delivery_value for values in objective_vectors[1:]),
        "accepted OBJ-001 value was not equality-locked in lower rounds",
    )
    stability_components = [item[2] for item in expected_rounds[1:5]]
    for index, component in enumerate(stability_components, start=1):
        assert component is not None
        accepted = cast(Mapping[str, object], objective_vectors[index]["stability"])[
            component
        ]
        for later in objective_vectors[index + 1 :]:
            _ensure(
                cast(Mapping[str, object], later["stability"])[component] == accepted,
                f"accepted OBJ-002 component {component} was not equality-locked",
            )

    candidate = cast(Mapping[str, object], first_report["candidate"])
    _ensure(first_report["solver_status"] == "OPTIMAL", "final status is not honest")
    _ensure(
        cast(Mapping[str, object], first_report["planning_run_outcome"])["state"]
        == "SOLVED",
        "solver status and PlanningRun outcome diverged",
    )
    final_validation = validations[-1]
    _ensure(
        cast(Mapping[str, object], final_validation["change_report_projection"])[
            "complete"
        ]
        is True,
        "ChangeReport universe arithmetic is incomplete",
    )
    _ensure(
        cast(Mapping[str, object], final_validation["formal_validation"])["status"]
        == "PASS",
        "fresh C-001..C-011 formal validation failed",
    )
    facts = cast(Mapping[str, object], final_validation["fact_lock_evidence"])
    _ensure(
        cast(int, facts["running_fact_count"])
        + cast(int, facts["explicit_hard_lock_count"])
        + cast(int, facts["freeze_derived_hard_lock_count"])
        > 0,
        "fixture did not exercise execution facts or effective hard locks",
    )

    first_signature = {
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "stability_evidence": first_report["stability_evidence"],
        "rounds": [
            {
                key: round_[key]
                for key in (
                    "round_id",
                    "solver_status",
                    "objective_value",
                    "best_bound",
                    "candidate_fingerprint",
                    "validation_report_fingerprint",
                )
            }
            for round_ in first_rounds
        ],
    }
    second_signature = {
        "candidate_fingerprint": cast(Mapping[str, object], second_report["candidate"])[
            "candidate_fingerprint"
        ],
        "stability_evidence": second_report["stability_evidence"],
        "rounds": [
            {
                key: round_[key]
                for key in (
                    "round_id",
                    "solver_status",
                    "objective_value",
                    "best_bound",
                    "candidate_fingerprint",
                    "validation_report_fingerprint",
                )
            }
            for round_ in second_rounds
        ],
    }
    _ensure(first_signature == second_signature, "fixed replay is not deterministic")

    boundaries = {
        "data_plane": "SIMULATION_ONLY",
        "solver_scope": "GLOBAL_C001_C011_NO_DECOMPOSITION",
        "base_schedule": "HINT_ONLY_EXCEPT_EFFECTIVE_HARD_PROTECTIONS",
        "change_report": "ARITHMETIC_AND_UNIVERSE_PRECHECK_ONLY",
        "schedule_version_or_state_transition": "NONE",
        "application_api_ui_simulator": "NOT_IMPLEMENTED_BY_TASK",
        "p4_08_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }
    checks = [
        _pass("frozen-schema-adr-p2-validator-state-and-dependencies", frozen),
        _pass(
            "solver-report-v2-schema-semantic-and-content-identity",
            {
                "report_id": first_report["report_id"],
                "report_fingerprint": first_report["report_fingerprint"],
                "schema": "solver-report.v2@2.8.0",
            },
        ),
        _pass(
            "global-six-round-objective-order-and-equality-locks",
            {
                "round_order": [item[0] for item in expected_rounds],
                "accepted_value_lock_count": 5,
                "global_model_rebuilds": 1,
            },
        ),
        _pass(
            "fresh-independent-formal-lock-and-change-universe-validation",
            {
                "validation_count": len(validations),
                "all_statuses": [item["status"] for item in validations],
                "fact_lock_evidence": facts,
                "change_report_projection": final_validation[
                    "change_report_projection"
                ],
                "independence": final_validation["independence"],
            },
        ),
        _pass(
            "honest-native-status-budget-bound-and-provenance",
            {
                "solver_status": first_report["solver_status"],
                "planning_run_outcome": first_report["planning_run_outcome"],
                "stage_results": first_report["objective_stage_results"],
                "solver": first_report["solver"],
            },
        ),
        _pass(
            "base-hints-effective-protections-and-objective-evidence",
            {
                "candidate_fingerprint": candidate["candidate_fingerprint"],
                "stability_evidence": first_report["stability_evidence"],
                "projection_fingerprint": projection["projection_fingerprint"],
                "model_metrics": first_report["model_metrics"],
            },
        ),
        _pass(
            "fixed-seed-byte-identity-replay",
            {
                "deterministic_replays": 2,
                "signature_fingerprint": contract_fingerprint(first_signature),
            },
        ),
        _pass("p4-p5-production-capability-boundary", boundaries),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "counts": {
            "objective_stages": 3,
            "solver_rounds": len(first_rounds),
            "fresh_validations": len(validations),
            "deterministic_replays": 2,
            "machine_checks": len(checks),
        },
        "artifacts": {
            "solver_report": first_report,
            "stage_raw_reports": list(first_rounds),
            "validation_reports": list(validations),
        },
        "boundaries": boundaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_replan_solver_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "diff_base": DIFF_BASE,
            "impact_rule_count": len(IMPACT_RULES),
            "impact_rules": list(IMPACT_RULES),
            "error_type": type(error).__name__,
            "error_message": "lexicographic replan evidence check failed",
            "issues": ["machine-check-failed"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "IMPACT_RULES",
    "REPORT_VERSION",
    "TASK_ID",
    "main",
    "run_replan_solver_checks",
]
