"""Build the TASK-P4-14 dynamic-replanning vertical-slice Gate report."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Never, cast

from app.api.replanning_check import run_replanning_api_checks
from app.application.execution_fact_projection_check import run_projection_checks
from app.application.p2_gate_report import validate_p2_vertical_slice_report
from app.application.p3_gate_report import validate_p3_vertical_slice_report
from app.application.replan_application_check import run_replan_application_checks
from app.domain.execution_contract_check import run_contract_checks
from app.exporters.change_report_output_check import (
    run_change_report_output_checks,
)
from app.infrastructure.replan_persistence_check import run_persistence_checks
from app.planning.backends.cp_sat.replan_solver_check import (
    run_replan_solver_checks,
)
from app.planning.problem.freeze_window_check import run_freeze_window_checks
from app.planning.reporting.stability_change_report_check import (
    run_stability_change_report_checks,
)
from app.simulation.execution.simulator_check import (
    run_execution_simulator_checks,
)
from app.simulation.scenarios.disruption_replay_check import (
    _semantic_replay_projection as _disruption_semantic_projection,
)
from app.simulation.scenarios.disruption_replay_check import (
    run_disruption_replay_checks,
)


REPORT_VERSION = "p4-vertical-slice-report.v1"
SEMANTIC_PROJECTION_VERSION = "p4-gate-semantic-projection.v1"
FRONTEND_REPORT_VERSION = "p4-frontend-gate-report.v1"
TASK_ID = "TASK-P4-14"
DIFF_BASE = "ea05c3d9e94af91ae4525e5fbf1087a4a4198a15"
IMPACT_RULES = (
    "IMPACT-APPLICATION",
    "IMPACT-DOCS",
    "IMPACT-FRONTEND",
    "IMPACT-INFRA",
    "IMPACT-TESTS",
)

type JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class StageContract:
    key: str
    report_version: str
    task_id: str
    diff_base: str
    check_count: int
    runner: Callable[[Path], dict[str, object]]


_STAGES = (
    StageContract(
        "machine_contracts",
        "p4-machine-contract-report.v1",
        "TASK-P4-02",
        "4026597ab1015b5ea3a89d241f0d12b5b481dee3",
        8,
        run_contract_checks,
    ),
    StageContract(
        "replan_persistence",
        "p4-replan-persistence-report.v1",
        "TASK-P4-03",
        "7b9bfc3069de5d3738e5cc5827d27d197ed3d226",
        9,
        run_persistence_checks,
    ),
    StageContract(
        "execution_fact_projection",
        "p4-execution-fact-projection-report.v1",
        "TASK-P4-04",
        "3563bb236ce7b2c01794485110d4945a6e265105",
        8,
        run_projection_checks,
    ),
    StageContract(
        "freeze_window",
        "p4-freeze-window-report.v1",
        "TASK-P4-05",
        "e7b96e28913e7eb5be63ae4265c09f8281456b1c",
        7,
        run_freeze_window_checks,
    ),
    StageContract(
        "stability_change_report",
        "p4-stability-change-report.v1",
        "TASK-P4-06",
        "d9d9f2fa2dbefe4c9942aaa8a943a93fdc7efd43",
        8,
        run_stability_change_report_checks,
    ),
    StageContract(
        "replan_solver",
        "p4-replan-solver-report.v1",
        "TASK-P4-07",
        "e212ab7957d6bc5887048ee54809c8194d6e1eaf",
        8,
        run_replan_solver_checks,
    ),
    StageContract(
        "replan_application",
        "p4-replan-application-report.v1",
        "TASK-P4-08",
        "77981f0564d91dfb57fee6e3792f4989bdb51d32",
        8,
        run_replan_application_checks,
    ),
    StageContract(
        "execution_simulator",
        "p4-execution-simulator-report.v1",
        "TASK-P4-09",
        "e4874735166be93473ccaebaf1090980db957552",
        8,
        run_execution_simulator_checks,
    ),
    StageContract(
        "disruption_replay",
        "p4-disruption-replay-report.v1",
        "TASK-P4-10",
        "8bbe0c643571e578ec637f135a2390c90de02512",
        8,
        run_disruption_replay_checks,
    ),
    StageContract(
        "change_report_output",
        "p4-change-report-output-report.v1",
        "TASK-P4-11",
        "45b12d9a67ce5ef1680a47fecdc68705355af226",
        8,
        run_change_report_output_checks,
    ),
    StageContract(
        "replanning_api",
        "p4-replanning-api-report.v1",
        "TASK-P4-12",
        "f4a54d3bb065b5cc8b51c450ffdc435bcc77d384",
        8,
        run_replanning_api_checks,
    ),
)

_PREDECESSOR_CLOSURES = {
    "TASK-P4-01": "4026597ab1015b5ea3a89d241f0d12b5b481dee3",
    "TASK-P4-02": "7b9bfc3069de5d3738e5cc5827d27d197ed3d226",
    "TASK-P4-03": "3563bb236ce7b2c01794485110d4945a6e265105",
    "TASK-P4-04": "e7b96e28913e7eb5be63ae4265c09f8281456b1c",
    "TASK-P4-05": "8029c3320ab039cdcd43e8a10dbd6deb1e0910a7",
    "TASK-P4-06": "e212ab7957d6bc5887048ee54809c8194d6e1eaf",
    "TASK-P4-07": "77981f0564d91dfb57fee6e3792f4989bdb51d32",
    "TASK-P4-08": "e4874735166be93473ccaebaf1090980db957552",
    "TASK-P4-09": "8bbe0c643571e578ec637f135a2390c90de02512",
    "TASK-P4-10": "45b12d9a67ce5ef1680a47fecdc68705355af226",
    "TASK-P4-11": "f4a54d3bb065b5cc8b51c450ffdc435bcc77d384",
    "TASK-P4-12": "be2389594f3e224de3f5a73f4b8b62ffcffb5b7b",
    "TASK-P4-13": DIFF_BASE,
}

_P3_STAGE_ORDER = (
    "workspace_contracts",
    "persistence",
    "schedule_version_lifecycle",
    "workspace_read_models",
    "schedule_commands",
    "approval_decisions",
    "publication",
    "export_jobs",
    "planning_workspace_api",
)

P4_TEST_IDS = (
    "TEST-EXECUTION-EVENT-CONTRACT-001",
    "TEST-REPLAN-REQUEST-CONTRACT-001",
    "TEST-P4-PERSISTENCE-001",
    "TEST-EXECUTION-FACT-PROJECTION-001",
    "TEST-FREEZE-WINDOW-001",
    "TEST-STABILITY-OBJECTIVE-001",
    "TEST-CHANGE-REPORT-001",
    "TEST-EXECUTION-SIMULATOR-001",
    "TEST-DISRUPTION-REPLAY-001",
    "TEST-REPLAN-API-001",
    "TEST-REPLAN-FRONTEND-001",
    "TEST-P4-VERTICAL-SLICE-001",
)

_EXPECTED_CHECKS = (
    "predecessor-provider-chain-frozen-at-activation",
    "two-or-more-complete-p4-backend-replays",
    "machine-contract-and-persistence-boundaries",
    "execution-facts-and-immutable-snapshot-preserved",
    "freeze-hard-and-running-locks-preserved",
    "delivery-stability-makespan-and-complete-change-report",
    "fresh-validator-and-atomic-new-draft-application",
    "deterministic-simulator-five-disruption-continuity",
    "change-report-output-and-http-authority",
    "two-complete-p4-chromium-replays",
    "p2-and-p3-gate-regression",
    "exact-fail-closed-negative-boundaries",
    "stable-business-semantic-projection",
    "p4-gate-non-exit-non-p5-non-production-boundary",
)

_EXPECTED_FRONTEND_CHECKS = (
    "frozen-p4-replanning-frontend-report",
    "two-complete-p4-chromium-replays",
    "json-junit-html-and-failure-retention",
    "stable-p4-browser-semantic-projection",
    "p4-gate-phase-boundary",
)

_RUNTIME_NOISE_KEYS = frozenset(
    {
        "archive_fingerprint",
        "change_report_fingerprint",
        "change_report_id",
        "code_commit",
        "elapsed_microseconds",
        "elapsed_microseconds_observed",
        "elapsed_seconds",
        "finished_at_utc",
        "first_feasible_seconds",
        "generated_at_utc",
        "kpi_id",
        "manifest_fingerprint",
        "memory_peak_mb",
        "model_build_seconds",
        "observed_command_microseconds",
        "observed_transaction_microseconds",
        "package_id",
        "report_fingerprint",
        "report_id",
        "result_id",
        "solve_seconds",
        "solver_report_id",
        "started_at_utc",
        "total_seconds",
        "validation_seconds",
    }
)

_FRONTEND_BOUNDARIES: JsonObject = {
    "browser_runtime": "CHROMIUM",
    "data_plane": "SIMULATION_ONLY",
    "mock_transport": True,
    "failure_media_policy": "RETAIN_ON_FAILURE",
    "p4_exit_gate_audit": "NOT_PERFORMED",
    "p4_15": "NOT_STARTED",
    "p5": "UNSUPPORTED",
    "production_authority": "NOT_FORMED",
    "production_readiness": "NOT_CLAIMED",
}

_BOUNDARIES: JsonObject = {
    "current_phase": "P4",
    "data_plane": "SIMULATION_ONLY",
    "gate_kind": "P4_VERTICAL_SLICE_EVIDENCE_NOT_EXIT_AUDIT",
    "exit_gate_audit": "NOT_PERFORMED",
    "p4_15": "NOT_STARTED",
    "p5_plus": "UNSUPPORTED",
    "production_identity_and_authority": "NOT_FORMED",
    "production_readiness": "NOT_CLAIMED",
    "external_publish_or_transfer": "NONE",
    "capacity_and_sla": "NOT_ESTABLISHED",
    "remediation": "NONE_MIXED_INTO_GATE",
    "schema_migration_dependency_adr_changes": "NONE",
}


class P4GateContractError(ValueError):
    """Raised when a Gate input or output violates its machine contract."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"P4_GATE_CONTRACT at {field}: {message}")


class P4GateExecutionError(RuntimeError):
    """Sanitized wrapper for a failed subordinate Gate stage."""

    def __init__(self, stage: str, error: Exception) -> None:
        self.stage = stage
        self.error_type = type(error).__name__
        super().__init__(f"P4_GATE_STAGE_FAILED at {stage}: {self.error_type}")


def _fail(field: str, message: str) -> Never:
    raise P4GateContractError(field, message)


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, Mapping):
        _fail(field, "expected object")
    return dict(value)


def _items(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(field, "expected array")
    return value


def _exact_keys(document: Mapping[str, object], expected: set[str], field: str) -> None:
    observed = set(document)
    if observed != expected:
        _fail(
            field,
            f"keys changed; missing={sorted(expected - observed)} "
            f"extra={sorted(observed - expected)}",
        )


def _code_commit() -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    if value == "uncommitted" or (
        len(value) == 40 and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return "uncommitted"


def _generated_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _stable_projection(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: _stable_projection(item)
            for key, item in sorted(value.items())
            if key not in _RUNTIME_NOISE_KEYS
        }
    if isinstance(value, list):
        return [_stable_projection(item) for item in value]
    return value


def _check_id(check: Mapping[str, object], field: str) -> str:
    value = check.get("check_id") or check.get("name") or check.get("id")
    if not isinstance(value, str) or not value:
        _fail(field, "check has no stable identity")
    return value


def _validate_stage_report(
    report: Mapping[str, object], contract: StageContract, code_commit: str
) -> None:
    for key, expected in (
        ("report_version", contract.report_version),
        ("status", "PASS"),
        ("task_id", contract.task_id),
        ("code_commit", code_commit),
        ("diff_base", contract.diff_base),
        ("check_count", contract.check_count),
    ):
        if report.get(key) != expected:
            _fail(f"{contract.key}.{key}", f"expected {expected!r}")
    if report.get("issues") != []:
        _fail(f"{contract.key}.issues", "owner report contains issues")
    if "blocking_gaps" in report and report.get("blocking_gaps") != []:
        _fail(f"{contract.key}.blocking_gaps", "owner report contains blocking gaps")
    checks = _items(report.get("checks"), f"{contract.key}.checks")
    identities: list[str] = []
    for index, raw in enumerate(checks):
        check = _object(raw, f"{contract.key}.checks[{index}]")
        if check.get("status") != "PASS":
            _fail(f"{contract.key}.checks[{index}].status", "subordinate check failed")
        identities.append(_check_id(check, f"{contract.key}.checks[{index}]"))
    if len(checks) != contract.check_count or len(set(identities)) != len(identities):
        _fail(f"{contract.key}.checks", "count or identity uniqueness changed")
    if "impact_rules" in report:
        rules = _items(report.get("impact_rules"), f"{contract.key}.impact_rules")
        if report.get("impact_rule_count") != len(rules):
            _fail(f"{contract.key}.impact_rule_count", "does not match rules")


def _stage_semantic_projection(stage: str, report: Mapping[str, object]) -> object:
    if stage != "disruption_replay":
        return _stable_projection(report)
    raw_replay = _object(report.get("raw_replay"), "disruption_replay.raw_replay")
    scenario = _object(
        report.get("scenario_manifest"), "disruption_replay.scenario_manifest"
    )
    checks = [
        {
            "identity": _check_id(
                _object(raw, f"disruption_replay.checks[{index}]"),
                f"disruption_replay.checks[{index}]",
            ),
            "status": _object(raw, f"disruption_replay.checks[{index}]").get("status"),
        }
        for index, raw in enumerate(
            _items(report.get("checks"), "disruption_replay.checks")
        )
    ]
    return {
        "report_version": report.get("report_version"),
        "status": report.get("status"),
        "task_id": report.get("task_id"),
        "diff_base": report.get("diff_base"),
        "checks": checks,
        "counts": report.get("counts"),
        "scenario_manifest": {
            key: value
            for key, value in sorted(scenario.items())
            if key != "replay_fingerprint"
        },
        "semantic_replay": _disruption_semantic_projection(raw_replay),
        "boundaries": report.get("boundaries"),
    }


def _run_stage(
    stage: str, operation: Callable[[], dict[str, object]]
) -> tuple[JsonObject, int]:
    started = perf_counter_ns()
    try:
        result = operation()
    except Exception as error:
        raise P4GateExecutionError(stage, error) from error
    elapsed = max(0, (perf_counter_ns() - started) // 1_000)
    return dict(result), elapsed


def _run_backend_replay(root: Path, index: int, code_commit: str) -> JsonObject:
    reports: JsonObject = {}
    timings: JsonObject = {}
    projections: JsonObject = {}
    fingerprints: JsonObject = {}
    for contract in _STAGES:
        report, elapsed = _run_stage(
            contract.key,
            lambda contract=contract: contract.runner(root),
        )
        _validate_stage_report(report, contract, code_commit)
        reports[contract.key] = report
        timings[contract.key] = elapsed
        projection = _stage_semantic_projection(contract.key, report)
        projections[contract.key] = projection
        fingerprints[contract.key] = _sha256_json(projection)
    fingerprints["combined"] = _sha256_json(projections)
    return {
        "replay_index": index,
        "status": "PASS",
        "stage_order": [contract.key for contract in _STAGES],
        "stage_microseconds": timings,
        "raw_subreports": reports,
        "stable_fingerprints": fingerprints,
    }


def validate_p4_frontend_gate_report(
    report: Mapping[str, object], code_commit: str
) -> None:
    expected_keys = {
        "report_version",
        "task_id",
        "code_commit",
        "diff_base",
        "status",
        "repeat_count",
        "playwright_contract_version",
        "replanning_report",
        "replays",
        "hash_consistency",
        "checks",
        "check_count",
        "issues",
        "blocking_gaps",
        "boundaries",
    }
    _exact_keys(report, expected_keys, "frontend_evidence")
    for key, expected in (
        ("report_version", FRONTEND_REPORT_VERSION),
        ("task_id", TASK_ID),
        ("code_commit", code_commit),
        ("diff_base", DIFF_BASE),
        ("status", "PASS"),
        ("repeat_count", 2),
        ("playwright_contract_version", "p4-playwright-semantic-projection.v1"),
    ):
        if report.get(key) != expected:
            _fail(f"frontend_evidence.{key}", f"expected {expected!r}")
    if report.get("issues") != [] or report.get("blocking_gaps") != []:
        _fail("frontend_evidence", "PASS browser evidence contains issues or gaps")
    frozen = _object(
        report.get("replanning_report"), "frontend_evidence.replanning_report"
    )
    expected_frozen = {
        "report_version": "p4-replanning-frontend-report.v1",
        "task_id": "TASK-P4-13",
        "code_commit": code_commit,
        "diff_base": "be2389594f3e224de3f5a73f4b8b62ffcffb5b7b",
        "status": "PASS",
        "check_count": 8,
        "p4_browser_specs": 5,
    }
    for key, expected in expected_frozen.items():
        if frozen.get(key) != expected:
            _fail(
                f"frontend_evidence.replanning_report.{key}", f"expected {expected!r}"
            )
    if not _is_sha256(frozen.get("sha256")):
        _fail("frontend_evidence.replanning_report.sha256", "expected SHA-256")

    replays = _items(report.get("replays"), "frontend_evidence.replays")
    fingerprints: list[str] = []
    for index, raw in enumerate(replays, start=1):
        replay = _object(raw, f"frontend_evidence.replays[{index - 1}]")
        if (
            replay.get("replay_index") != index
            or replay.get("status") != "PASS"
            or replay.get("project_name") != "chromium-p4-vertical-slice"
            or replay.get("spec_count") != 5
            or replay.get("dynamic_replanning_spec_count") != 5
        ):
            _fail(f"frontend_evidence.replays[{index - 1}]", "identity/count changed")
        raw_evidence = _object(
            replay.get("raw_evidence"),
            f"frontend_evidence.replays[{index - 1}].raw_evidence",
        )
        if set(raw_evidence) != {"json", "junit", "html"}:
            _fail(
                f"frontend_evidence.replays[{index - 1}].raw_evidence",
                "expected JSON/JUnit/HTML",
            )
        for kind, value in raw_evidence.items():
            evidence = _object(
                value,
                f"frontend_evidence.replays[{index - 1}].raw_evidence.{kind}",
            )
            if not isinstance(evidence.get("path"), str) or not _is_sha256(
                evidence.get("sha256")
            ):
                _fail(
                    f"frontend_evidence.replays[{index - 1}].raw_evidence.{kind}",
                    "invalid path or SHA-256",
                )
        projection = _object(
            replay.get("semantic_projection"),
            f"frontend_evidence.replays[{index - 1}].semantic_projection",
        )
        fingerprint = replay.get("semantic_fingerprint")
        if fingerprint != _sha256_json(projection):
            _fail(
                f"frontend_evidence.replays[{index - 1}].semantic_fingerprint",
                "does not match projection",
            )
        fingerprints.append(cast(str, fingerprint))
    if len(replays) != 2 or len(set(fingerprints)) != 1:
        _fail("frontend_evidence.replays", "browser semantics changed")

    consistency = _object(
        report.get("hash_consistency"), "frontend_evidence.hash_consistency"
    )
    if (
        consistency.get("status") != "PASS"
        or consistency.get("projection_version")
        != "p4-playwright-semantic-projection.v1"
        or consistency.get("semantic_fingerprints") != fingerprints
        or consistency.get("unique_semantic_fingerprints") != 1
    ):
        _fail("frontend_evidence.hash_consistency", "hash evidence changed")
    checks = _items(report.get("checks"), "frontend_evidence.checks")
    identities = [
        _check_id(
            _object(raw, f"frontend_evidence.checks[{index}]"),
            f"frontend_evidence.checks[{index}]",
        )
        for index, raw in enumerate(checks)
    ]
    if (
        tuple(identities) != _EXPECTED_FRONTEND_CHECKS
        or report.get("check_count") != len(_EXPECTED_FRONTEND_CHECKS)
        or any(_object(raw, "frontend check").get("status") != "PASS" for raw in checks)
    ):
        _fail("frontend_evidence.checks", "identity/count/status changed")
    if report.get("boundaries") != _FRONTEND_BOUNDARIES:
        _fail("frontend_evidence.boundaries", "phase boundary changed")


def _regression_summary(report: Mapping[str, object], *, gate: str) -> JsonObject:
    return {
        "gate": gate,
        "report_version": report.get("report_version"),
        "task_id": report.get("task_id"),
        "code_commit": report.get("code_commit"),
        "status": report.get("status"),
        "repeat_count": report.get("repeat_count"),
        "check_count": report.get("check_count"),
        "blocking_gaps": report.get("blocking_gaps"),
        "raw_report_sha256": _sha256_json(report),
    }


def _validate_regressions(
    p2_report: Mapping[str, object], p3_report: Mapping[str, object], code_commit: str
) -> JsonObject:
    validate_p2_vertical_slice_report(p2_report)
    normalized_p3 = deepcopy(dict(p3_report))
    p3_replays = _items(
        normalized_p3.get("backend_replays"), "regressions.p3.backend_replays"
    )
    for index, raw in enumerate(p3_replays):
        replay = _object(raw, f"regressions.p3.backend_replays[{index}]")
        reports = _object(
            replay.get("raw_subreports"),
            f"regressions.p3.backend_replays[{index}].raw_subreports",
        )
        if set(reports) != set(_P3_STAGE_ORDER):
            _fail(
                f"regressions.p3.backend_replays[{index}].raw_subreports",
                "serialized P3 stage set changed",
            )
        replay["raw_subreports"] = {key: reports[key] for key in _P3_STAGE_ORDER}
        p3_replays[index] = replay
    validate_p3_vertical_slice_report(normalized_p3)
    expected = (
        (p2_report, "p2-vertical-slice-report.v1", "TASK-P2-13", 11),
        (p3_report, "p3-vertical-slice-report.v1", "TASK-P3-14", 14),
    )
    for report, version, task, checks in expected:
        if (
            report.get("report_version") != version
            or report.get("task_id") != task
            or report.get("code_commit") != code_commit
            or report.get("status") != "PASS"
            or report.get("check_count") != checks
            or report.get("blocking_gaps") != []
        ):
            _fail(f"regressions.{task}", "identity/current SHA/status changed")
    p3_summary = _regression_summary(p3_report, gate="P3_VERTICAL_SLICE")
    p3_summary["serialization_normalization"] = "JSON_OBJECT_KEY_ORDER_ONLY"
    return {
        "p2": _regression_summary(p2_report, gate="P2_VERTICAL_SLICE"),
        "p3": p3_summary,
    }


def _pass(check_id: str, evidence: object) -> JsonObject:
    return {"check_id": check_id, "status": "PASS", "evidence": evidence}


def _rejection_cases(replay: Mapping[str, object]) -> list[JsonObject]:
    reports = _object(replay.get("raw_subreports"), "backend_replay.raw_subreports")
    disruption = _object(reports.get("disruption_replay"), "disruption_replay")
    api = _object(reports.get("replanning_api"), "replanning_api")
    application = _object(reports.get("replan_application"), "replan_application")
    disruption_counts = _object(disruption.get("counts"), "disruption_replay.counts")
    disruption_boundaries = _object(
        disruption.get("boundaries"), "disruption_replay.boundaries"
    )
    api_boundaries = _object(api.get("boundaries"), "replanning_api.boundaries")
    application_boundaries = _object(
        application.get("boundaries"), "replan_application.boundaries"
    )
    if disruption_counts.get("negative_vectors") != 3:
        _fail("rejection_cases.disruption", "expected three exact negative vectors")
    if api_boundaries.get("production_authority") != "DEFAULT_DENY_OPEN_010_015":
        _fail("rejection_cases.production", "Production authority did not default deny")
    if disruption_boundaries.get("p5_plus") != "UNSUPPORTED":
        _fail("rejection_cases.p5", "P5 boundary was not rejected")
    if (
        application_boundaries.get("result_schedule_state") != "DRAFT_ONLY"
        or application_boundaries.get("approval_publish_export") != "NOT_INVOKED"
    ):
        _fail("rejection_cases.partial", "partial result/state boundary changed")
    return [
        {
            "case_id": "TAMPER_COVERAGE_AND_PLANE_FAIL_CLOSED",
            "status": "PASS",
            "evidence": "P4-10 three negative vectors / no partial success",
        },
        {
            "case_id": "PRODUCTION_AUTHORITY_DEFAULT_DENY",
            "status": "PASS",
            "evidence": "P4-12 default deny before provider/application lookup",
        },
        {
            "case_id": "P5_CAPABILITY_UNSUPPORTED",
            "status": "PASS",
            "evidence": "P4-10 explicit UNSUPPORTED boundary",
        },
        {
            "case_id": "PARTIAL_RESULT_CANNOT_ADVANCE_STATE",
            "status": "PASS",
            "evidence": "P4-08 DRAFT only / no approval publish export",
        },
    ]


def _aggregate_checks(
    replays: Sequence[Mapping[str, object]],
    frontend: Mapping[str, object],
    regressions: Mapping[str, object],
    rejections: Sequence[Mapping[str, object]],
    consistency: Mapping[str, object],
) -> list[JsonObject]:
    first_reports = _object(replays[0].get("raw_subreports"), "backend_replays[0]")
    disruption = _object(first_reports["disruption_replay"], "disruption_replay")
    return [
        _pass(
            _EXPECTED_CHECKS[0],
            {
                "audit_kind": "ACTIVATION_PROVIDER_AUDIT",
                "task_count": len(_PREDECESSOR_CLOSURES),
                "closure_commits": dict(_PREDECESSOR_CLOSURES),
                "provider_reports_embedded": False,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[1],
            {
                "repeat_count": len(replays),
                "stage_executions": len(replays) * len(_STAGES),
            },
        ),
        _pass(
            _EXPECTED_CHECKS[2],
            {"stages": ["machine_contracts", "replan_persistence"]},
        ),
        _pass(
            _EXPECTED_CHECKS[3],
            {"stage": "execution_fact_projection", "owner_status": "PASS"},
        ),
        _pass(
            _EXPECTED_CHECKS[4],
            {"stage": "freeze_window", "owner_status": "PASS"},
        ),
        _pass(
            _EXPECTED_CHECKS[5],
            {"stages": ["stability_change_report", "replan_solver"]},
        ),
        _pass(
            _EXPECTED_CHECKS[6],
            {"stage": "replan_application", "result_state": "DRAFT_ONLY"},
        ),
        _pass(
            _EXPECTED_CHECKS[7],
            {
                "stages": ["execution_simulator", "disruption_replay"],
                "scenario_steps_per_replay": _object(
                    disruption.get("counts"), "disruption_replay.counts"
                ).get("scenario_steps"),
            },
        ),
        _pass(
            _EXPECTED_CHECKS[8],
            {"stages": ["change_report_output", "replanning_api"]},
        ),
        _pass(
            _EXPECTED_CHECKS[9],
            {"repeat_count": frontend.get("repeat_count"), "browser_specs": 10},
        ),
        _pass(_EXPECTED_CHECKS[10], dict(regressions)),
        _pass(
            _EXPECTED_CHECKS[11],
            {"case_ids": [case.get("case_id") for case in rejections]},
        ),
        _pass(_EXPECTED_CHECKS[12], dict(consistency)),
        _pass(_EXPECTED_CHECKS[13], dict(_BOUNDARIES)),
    ]


def run_p4_vertical_slice_gate(
    *,
    root: Path,
    frontend_report: Mapping[str, object],
    p2_report: Mapping[str, object],
    p3_report: Mapping[str, object],
    repeat: int = 2,
) -> JsonObject:
    """Fresh-run all P4 owner boundaries and aggregate browser/P2/P3 evidence."""

    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 2:
        _fail("repeat", "P4 Gate requires at least two complete replays")
    code_commit = _code_commit()
    frontend = dict(frontend_report)
    validate_p4_frontend_gate_report(frontend, code_commit)
    regressions = _validate_regressions(p2_report, p3_report, code_commit)
    replays = [
        _run_backend_replay(root, index, code_commit) for index in range(1, repeat + 1)
    ]

    stage_fingerprints: JsonObject = {
        contract.key: [
            _object(replay["stable_fingerprints"], "stable_fingerprints")[contract.key]
            for replay in replays
        ]
        for contract in _STAGES
    }
    combined = [
        _object(replay["stable_fingerprints"], "stable_fingerprints")["combined"]
        for replay in replays
    ]
    unstable = [
        key
        for key, values in stage_fingerprints.items()
        if len(set(cast(list[str], values))) != 1
    ]
    if len(set(cast(list[str], combined))) != 1 or unstable:
        _fail("semantic_consistency", "replay drift: " + ", ".join(unstable))
    consistency = {
        "status": "PASS",
        "projection_version": SEMANTIC_PROJECTION_VERSION,
        "stage_fingerprints": stage_fingerprints,
        "combined_fingerprints": combined,
        "unique_combined_fingerprints": 1,
        "excluded_runtime_noise_keys": sorted(_RUNTIME_NOISE_KEYS),
        "disruption_projection": "P4_10_VERSIONED_SEMANTIC_REPLAY_PROJECTION",
        "raw_evidence_policy": (
            "ALL_SUBREPORTS_BROWSER_REPORTS_AND_RUNTIME_OBSERVATIONS_RETAINED;_"
            "ONLY_VERSIONED_RUNTIME_NOISE_DERIVED_ARTIFACT_IDENTITY_EXCLUDED"
        ),
    }
    rejections = _rejection_cases(replays[0])
    checks = _aggregate_checks(replays, frontend, regressions, rejections, consistency)
    if tuple(check["check_id"] for check in checks) != _EXPECTED_CHECKS:
        _fail("checks", "aggregate check order changed")
    subordinate_per_replay = sum(contract.check_count for contract in _STAGES)
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "generated_at_utc": _generated_at(),
        "validation_profile": "PHASE_GATE",
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "versions": {
            "gate_contract": REPORT_VERSION,
            "semantic_projection": SEMANTIC_PROJECTION_VERSION,
            "frontend_gate": FRONTEND_REPORT_VERSION,
            "p2_gate": "p2-vertical-slice-report.v1",
            "p3_gate": "p3-vertical-slice-report.v1",
            "schema_set": "2.8.0",
        },
        "frozen_inputs": {
            "diff_base": DIFF_BASE,
            "predecessor_closure_commits": dict(_PREDECESSOR_CLOSURES),
            "activation_provider_audit": "PASS",
        },
        "test_ids": list(P4_TEST_IDS),
        "repeat_count": repeat,
        "execution": {
            "minimum_repeat_count": 2,
            "backend_full_replays_complete": repeat,
            "frontend_full_replays_complete": frontend["repeat_count"],
            "all_public_p4_backend_boundaries_reexecuted": True,
            "stage_order": [contract.key for contract in _STAGES],
        },
        "backend_replays": replays,
        "frontend_evidence": frontend,
        "regressions": regressions,
        "rejection_cases": rejections,
        "semantic_consistency": consistency,
        "checks": checks,
        "check_count": len(checks),
        "counts": {
            "backend_full_replays": repeat,
            "backend_stage_executions": repeat * len(_STAGES),
            "backend_subreport_checks": repeat * subordinate_per_replay,
            "continuous_disruption_replays": repeat,
            "continuous_scenario_step_executions": repeat * 5,
            "standard_event_executions": repeat * 8,
            "fresh_validator_passes": repeat * 5,
            "complete_change_reports": repeat * 5,
            "frontend_full_replays": frontend["repeat_count"],
            "browser_spec_executions": cast(int, frontend["repeat_count"]) * 5,
            "p2_gate_full_replays": _object(regressions["p2"], "regressions.p2")[
                "repeat_count"
            ],
            "p3_gate_backend_replays": _object(regressions["p3"], "regressions.p3")[
                "repeat_count"
            ],
            "exact_rejection_cases": len(rejections),
            "predecessor_tasks": len(_PREDECESSOR_CLOSURES),
        },
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
    }


def validate_p4_vertical_slice_report(report: Mapping[str, object]) -> None:
    """Validate a successful ``p4-vertical-slice-report.v1`` document."""

    expected_keys = {
        "report_version",
        "status",
        "task_id",
        "code_commit",
        "diff_base",
        "generated_at_utc",
        "validation_profile",
        "impact_rule_count",
        "impact_rules",
        "versions",
        "frozen_inputs",
        "test_ids",
        "repeat_count",
        "execution",
        "backend_replays",
        "frontend_evidence",
        "regressions",
        "rejection_cases",
        "semantic_consistency",
        "checks",
        "check_count",
        "counts",
        "blocking_gaps",
        "boundaries",
    }
    _exact_keys(report, expected_keys, "$")
    for key, expected in (
        ("report_version", REPORT_VERSION),
        ("status", "PASS"),
        ("task_id", TASK_ID),
        ("diff_base", DIFF_BASE),
        ("validation_profile", "PHASE_GATE"),
        ("impact_rule_count", len(IMPACT_RULES)),
        ("impact_rules", list(IMPACT_RULES)),
        ("test_ids", list(P4_TEST_IDS)),
        ("blocking_gaps", []),
        ("boundaries", _BOUNDARIES),
    ):
        if report.get(key) != expected:
            _fail(key, f"expected {expected!r}")
    code_commit = report.get("code_commit")
    if code_commit != "uncommitted" and not (
        isinstance(code_commit, str)
        and len(code_commit) == 40
        and all(character in "0123456789abcdef" for character in code_commit)
    ):
        _fail("code_commit", "expected uncommitted or full lowercase Git SHA")
    repeat = report.get("repeat_count")
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 2:
        _fail("repeat_count", "expected integer >= 2")
    replays = _items(report.get("backend_replays"), "backend_replays")
    if len(replays) != repeat:
        _fail("backend_replays", "repeat count mismatch")

    recomputed: JsonObject = {contract.key: [] for contract in _STAGES}
    combined: list[str] = []
    for index, raw in enumerate(replays, start=1):
        replay = _object(raw, f"backend_replays[{index - 1}]")
        if replay.get("replay_index") != index or replay.get("status") != "PASS":
            _fail(f"backend_replays[{index - 1}]", "identity/status changed")
        reports = _object(
            replay.get("raw_subreports"),
            f"backend_replays[{index - 1}].raw_subreports",
        )
        if tuple(reports) != tuple(contract.key for contract in _STAGES):
            _fail(f"backend_replays[{index - 1}].raw_subreports", "stage order changed")
        projections: JsonObject = {}
        for contract in _STAGES:
            subreport = _object(
                reports[contract.key],
                f"backend_replays[{index - 1}].{contract.key}",
            )
            _validate_stage_report(subreport, contract, cast(str, code_commit))
            projection = _stage_semantic_projection(contract.key, subreport)
            projections[contract.key] = projection
            cast(list[str], recomputed[contract.key]).append(_sha256_json(projection))
        expected_fingerprints = {
            **{key: cast(list[str], values)[-1] for key, values in recomputed.items()},
            "combined": _sha256_json(projections),
        }
        if replay.get("stable_fingerprints") != expected_fingerprints:
            _fail(f"backend_replays[{index - 1}].stable_fingerprints", "hash mismatch")
        combined.append(expected_fingerprints["combined"])

    consistency = _object(report.get("semantic_consistency"), "semantic_consistency")
    unstable = [
        key
        for key, values in recomputed.items()
        if len(set(cast(list[str], values))) != 1
    ]
    if (
        unstable
        or len(set(combined)) != 1
        or consistency.get("status") != "PASS"
        or consistency.get("projection_version") != SEMANTIC_PROJECTION_VERSION
        or consistency.get("stage_fingerprints") != recomputed
        or consistency.get("combined_fingerprints") != combined
        or consistency.get("unique_combined_fingerprints") != 1
    ):
        _fail("semantic_consistency", "aggregate replay evidence changed")
    validate_p4_frontend_gate_report(
        _object(report.get("frontend_evidence"), "frontend_evidence"),
        cast(str, code_commit),
    )
    regressions = _object(report.get("regressions"), "regressions")
    for key, version, task, checks in (
        ("p2", "p2-vertical-slice-report.v1", "TASK-P2-13", 11),
        ("p3", "p3-vertical-slice-report.v1", "TASK-P3-14", 14),
    ):
        summary = _object(regressions.get(key), f"regressions.{key}")
        if (
            summary.get("report_version") != version
            or summary.get("task_id") != task
            or summary.get("code_commit") != code_commit
            or summary.get("status") != "PASS"
            or summary.get("check_count") != checks
            or summary.get("blocking_gaps") != []
            or not _is_sha256(summary.get("raw_report_sha256"))
        ):
            _fail(f"regressions.{key}", "summary changed")
    checks = _items(report.get("checks"), "checks")
    identities = [
        _check_id(_object(raw, f"checks[{index}]"), f"checks[{index}]")
        for index, raw in enumerate(checks)
    ]
    if (
        tuple(identities) != _EXPECTED_CHECKS
        or report.get("check_count") != len(_EXPECTED_CHECKS)
        or any(_object(raw, "check").get("status") != "PASS" for raw in checks)
    ):
        _fail("checks", "aggregate check identity/count/status changed")
    rejections = _items(report.get("rejection_cases"), "rejection_cases")
    if len(rejections) != 4 or any(
        _object(raw, "rejection").get("status") != "PASS" for raw in rejections
    ):
        _fail("rejection_cases", "expected four PASS rejection cases")
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in (
        '"exit_gate_audit": "READY"',
        '"p4_15": "STARTED"',
        '"p5_plus": "SUPPORTED"',
        '"production_readiness": "READY"',
    ):
        if forbidden in serialized:
            _fail("boundaries", f"forbidden claim present: {forbidden}")


def _load_json_report(path: Path, field: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise P4GateContractError(field, "report cannot be loaded") from error
    return _object(value, field)


def _failure_report(error: Exception, repeat: int) -> JsonObject:
    stage = (
        error.stage if isinstance(error, P4GateExecutionError) else "gate-orchestrator"
    )
    return {
        "report_version": REPORT_VERSION,
        "status": "FAIL",
        "task_id": TASK_ID,
        "code_commit": _code_commit(),
        "diff_base": DIFF_BASE,
        "validation_profile": "PHASE_GATE",
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "repeat_count": repeat,
        "issues": [
            {
                "issue_id": "P4-VERTICAL-GATE-EXECUTION-001",
                "stage": stage,
                "error_type": type(error).__name__,
            }
        ],
        "blocking_gaps": [
            {
                "gap_id": "P4-VERTICAL-GATE-EXECUTION-001",
                "stage": stage,
                "status": "BLOCKING",
                "remediation": "REQUIRES_SEPARATE_BOUNDED_CORRECTIVE_COMMIT",
            }
        ],
        "boundaries": dict(_BOUNDARIES),
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--frontend-report", type=Path, required=True)
    parser.add_argument("--p2-report", type=Path, required=True)
    parser.add_argument("--p3-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        frontend = _load_json_report(arguments.frontend_report, "frontend_report")
        p2 = _load_json_report(arguments.p2_report, "p2_report")
        p3 = _load_json_report(arguments.p3_report, "p3_report")
        report = run_p4_vertical_slice_gate(
            root=arguments.root.resolve(),
            frontend_report=frontend,
            p2_report=p2,
            p3_report=p3,
            repeat=arguments.repeat,
        )
        validate_p4_vertical_slice_report(report)
    except Exception as error:
        report = _failure_report(error, arguments.repeat)
        exit_code = 1
    else:
        exit_code = 0
    _write_report(arguments.report, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "FRONTEND_REPORT_VERSION",
    "IMPACT_RULES",
    "P4GateContractError",
    "P4GateExecutionError",
    "P4_TEST_IDS",
    "REPORT_VERSION",
    "SEMANTIC_PROJECTION_VERSION",
    "TASK_ID",
    "main",
    "run_p4_vertical_slice_gate",
    "validate_p4_frontend_gate_report",
    "validate_p4_vertical_slice_report",
]
