"""Aggregate the complete P3 Planning Workspace slice into one Gate report.

The module only orchestrates already-published P3 machine boundaries.  It does
not repair business behavior, change schemas, or make a Phase Exit decision.
"""

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

from app.api.planning_workspace_check import run_http_api_checks
from app.application.approval_decision_check import run_approval_decision_checks
from app.application.export_job_check import build_report as build_export_job_report
from app.application.publication_check import run_publication_checks
from app.application.schedule_command_check import run_command_checks
from app.application.schedule_version_lifecycle_check import run_lifecycle_checks
from app.application.workspace_read_model_check import (
    run_workspace_read_model_checks,
)
from app.domain.errors import ProductErrorCategory
from app.domain.export_job import (
    ExportJobContext,
    ExportJobError,
    ExportJobFailure,
    ExportJobRequest,
    build_created_export_job,
    export_job_identity,
)
from app.domain.state_machines.contracts import (
    StateMachineName,
    StateTransitionError,
    require_transition,
)
from app.domain.state_machines.schedule_version import (
    ScheduleVersionPersistenceTransitionError,
    require_schedule_version_transition,
)
from app.domain.workspace_contract_check import run_contract_checks
from app.infrastructure.workspace_persistence_check import run_persistence_checks


REPORT_VERSION = "p3-vertical-slice-report.v1"
SEMANTIC_PROJECTION_VERSION = "p3-gate-semantic-projection.v1"
FRONTEND_REPORT_VERSION = "p3-frontend-gate-report.v1"
TASK_ID = "TASK-P3-14"
DIFF_BASE = "6a3e02f00bf46f19915cb59c3c4af7daaac95be4"

type JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class StageContract:
    key: str
    report_version: str
    task_id: str
    check_ids: tuple[str, ...]
    runner: Callable[[Path], dict[str, object]]


_STAGES = (
    StageContract(
        "workspace_contracts",
        "p3-workspace-contract-report.v1",
        "TASK-P3-02",
        (
            "p2-schema-and-sample-byte-preservation",
            "draft-2020-12-schema-meta-and-offline-references",
            "strict-no-default-and-plane-provenance-conditionals",
            "positive-samples-and-canonical-fingerprints",
            "negative-and-non-interchangeability-vectors",
            "state-and-error-namespace-alignment",
            "pure-prechecks-and-round-trip",
            "dependency-and-phase-boundary",
        ),
        run_contract_checks,
    ),
    StageContract(
        "persistence",
        "p3-persistence-report.v1",
        "TASK-P3-03",
        (
            "migration-topology-and-indexes",
            "schedule-version-insert-immutability-and-cas",
            "append-only-audit-and-exact-replay",
            "publication-result-and-current-reference",
            "export-job-state-attempt-and-lease",
            "database-immutability-guards",
            "transaction-rollback-and-plane-isolation",
            "populated-downgrade-and-phase-boundary",
        ),
        run_persistence_checks,
    ),
    StageContract(
        "schedule_version_lifecycle",
        "p3-schedule-version-lifecycle-report.v1",
        "TASK-P3-04",
        (
            "P3-04-LINEAGE",
            "P3-04-DRAFT-READY",
            "P3-04-ATOMIC-AUDIT",
            "P3-04-EXACT-REPLAY",
            "P3-04-NEGATIVE-NO-SIDE-EFFECT",
            "P3-04-TRANSACTION-ROLLBACK",
            "P3-04-IDEMPOTENCY-CONCURRENCY",
            "P3-04-PLANE-STATE-BOUNDARY",
        ),
        run_lifecycle_checks,
    ),
    StageContract(
        "workspace_read_models",
        "p3-workspace-read-model-report.v1",
        "TASK-P3-05",
        (
            "P3-05-READ-MODEL-COVERAGE",
            "P3-05-LOAD-KPI-CONSISTENCY",
            "P3-05-LINEAGE-AUTHORITY",
            "P3-05-SCALE-OBSERVATION",
            "P3-05-COMPARISON-REPLAY",
            "P3-05-FILTER-SORT-PAGE-REPLAY",
            "P3-05-NEGATIVE-AND-EMPTY",
            "P3-05-READ-ONLY-BOUNDARY",
        ),
        run_workspace_read_model_checks,
    ),
    StageContract(
        "schedule_commands",
        "p3-schedule-command-report.v1",
        "TASK-P3-06",
        (
            "P3-06-MOVE-COPY-ON-WRITE",
            "P3-06-IDEMPOTENCY",
            "P3-06-LOCK-COPY-ON-WRITE",
            "P3-06-ASSIGN-RESOURCE",
            "P3-06-HISTORICAL-IMMUTABILITY",
            "P3-06-NEGATIVE-NO-SIDE-EFFECT",
            "P3-06-ATOMIC-ROLLBACK",
            "P3-06-BOUNDARY-OBSERVATION",
        ),
        run_command_checks,
    ),
    StageContract(
        "approval_decisions",
        "p3-approval-decision-report.v1",
        "TASK-P3-07",
        (
            "approve-ready-atomic-same-content",
            "decision-exact-replay-and-conflict",
            "reject-terminal-and-no-second-decision",
            "authorization-scope-denial-audit-and-production-default-deny",
            "stale-missing-reason-and-secret-redaction",
            "audit-failure-rolls-back-state",
            "concurrent-decision-single-cas-winner",
            "append-only-lineage-redaction-and-phase-boundary",
        ),
        run_approval_decision_checks,
    ),
    StageContract(
        "publication",
        "p3-publication-report.v1",
        "TASK-P3-08",
        (
            "approved-only-first-publish-atomic",
            "exact-replay-conflict-and-double-publish",
            "current-switch-and-supersession-atomic",
            "draft-ready-rejected-negative-no-side-effect",
            "authorization-prelookup-and-production-default-deny",
            "audit-failure-rolls-back-entire-publication",
            "concurrent-publication-single-current-cas-winner",
            "immutable-lineage-redaction-and-phase-boundary",
        ),
        run_publication_checks,
    ),
    StageContract(
        "export_jobs",
        "p3-export-job-report.v1",
        "TASK-P3-09",
        (
            "additive-v2-schema-and-offline-samples",
            "v1-byte-preservation",
            "deterministic-json-csv-xlsx-package",
            "manifest-last-atomic-replay-and-cleanup",
            "durable-lifecycle-lease-retry-cancel-recovery",
            "authorization-audit-and-rollback",
            "worker-publish-separation",
            "phase-boundary",
        ),
        build_export_job_report,
    ),
    StageContract(
        "planning_workspace_api",
        "p3-planning-workspace-api-report.v1",
        "TASK-P3-10",
        (
            "versioned-route-and-openapi-inventory",
            "all-routes-delegate-to-application-port",
            "strict-carrier-route-and-idempotency-binding",
            "server-derived-capability-scope-and-production-default-deny",
            "stable-http-error-mapping-and-sanitization",
            "correlation-and-denial-audit-redaction",
            "simulation-plane-and-phase-boundary",
            "health-compatibility-and-thin-router-boundary",
        ),
        run_http_api_checks,
    ),
)

_EXPECTED_CHECKS = (
    "predecessor-provider-chain-frozen-at-activation",
    "p2-validated-solution-regression",
    "two-or-more-complete-backend-replays",
    "workspace-contract-persistence-and-immutability",
    "version-lineage-read-model-and-comparison",
    "gantt-command-new-draft-and-fresh-validator",
    "approval-rejection-and-append-only-audit",
    "approved-only-publication-supersession-and-replay",
    "export-job-standard-package-and-idempotency",
    "api-server-authority-and-thin-router",
    "two-complete-chromium-human-control-replays",
    "four-exact-fail-closed-exit-rejections",
    "stable-business-semantic-projection",
    "p3-gate-non-exit-non-p4-non-production-boundary",
)

_EXPECTED_REJECTION_IDS = (
    "DRAFT_CANNOT_PUBLISH",
    "REJECTED_CANNOT_PUBLISH",
    "PUBLISHED_CONTENT_CANNOT_MUTATE",
    "UNPUBLISHED_VERSION_CANNOT_EXPORT",
)

_PREDECESSOR_CLOSURES = {
    "TASK-P3-01": "a8fcec3383ea0f8d9dca4101056aff37d7eea08c",
    "TASK-P3-02": "9621fda535f66393beab88efc13c100fc805c993",
    "TASK-P3-03": "62604d05964413a0aa7f763afd720afa2d53a887",
    "TASK-P3-04": "fc5011f78a242160097521259a1914d864d9ad17",
    "TASK-P3-05": "67d38d030f8b129de7f1b2f6e5b75bd706655396",
    "TASK-P3-06": "514224b8ff2d507b613797ae697245bab14f79eb",
    "TASK-P3-07": "a53c0f7d4a0f0bcd4e02bfeaaa0f6fc4b93157b9",
    "TASK-P3-08": "b9c0b1694448a4ec348b0b02107926f6213560c9",
    "TASK-P3-09": "f71c4a5a11a3fac0e203e2e92198c26124755927",
    "TASK-P3-10": "26dd519b1f1f84e08d415cfdfce43f286fa82988",
    "TASK-P3-11": "3bca1cc10ebedc4d47227bafb2f3f66854ccb526",
    "TASK-P3-12": "3dacf83c0f0bf87a9fa673aa75d61f8ad8659386",
    "TASK-P3-13": "6a3e02f00bf46f19915cb59c3c4af7daaac95be4",
}

_RUNTIME_NOISE_KEYS = frozenset(
    {
        "code_commit",
        "elapsed_microseconds",
        "elapsed_microseconds_observed",
        "kpi_id",
        "observed_command_microseconds",
        "observed_transaction_microseconds",
        "projected_payload_bytes",
        "solver_report_id",
        "source_bytes",
    }
)

_APPROVAL_CONCURRENCY_EQUIVALENCE = {
    "winner": ["APPROVE", "REJECT"],
    "loser_failure": ["INVALID_STATE_TRANSITION", "STALE_SOURCE"],
}

_PUBLICATION_CONCURRENCY_EQUIVALENCE = {
    "loser_failure": ["CURRENT_REFERENCE_CONFLICT", "STALE_SOURCE"],
}

_FRONTEND_BOUNDARIES: JsonObject = {
    "browser_runtime": "CHROMIUM",
    "data_plane": "SIMULATION_ONLY",
    "mock_transport": True,
    "failure_media_policy": "RETAIN_ON_FAILURE",
    "p3_15_exit_gate_audit": "NOT_PERFORMED",
    "p4": "NOT_STARTED",
    "production_authority": "NOT_FORMED",
    "production_readiness": "NOT_CLAIMED",
}

_BOUNDARIES: JsonObject = {
    "current_phase": "P3",
    "data_plane": "SIMULATION_ONLY",
    "gate_kind": "P3_VERTICAL_SLICE_EVIDENCE_NOT_EXIT_AUDIT",
    "exit_gate_audit": "NOT_PERFORMED",
    "p3_15": "NOT_STARTED",
    "p4": "NOT_STARTED",
    "production_identity_and_authority": "NOT_FORMED",
    "production_readiness": "NOT_CLAIMED",
    "external_publish_or_transfer": "NONE",
    "remediation": "NONE_MIXED_INTO_GATE",
    "schema_migration_dependency_adr_changes": "NONE",
}


class P3GateContractError(ValueError):
    """A subordinate or aggregate P3 Gate report violates its contract."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"P3_GATE_CONTRACT at {field}: {message}")


class P3GateExecutionError(RuntimeError):
    """One frozen public boundary failed during Gate replay."""

    def __init__(self, stage: str, error: Exception) -> None:
        self.stage = stage
        self.error_type = type(error).__name__
        super().__init__(f"P3_GATE_STAGE_FAILED at {stage}: {self.error_type}: {error}")


def _fail(field: str, message: str) -> Never:
    raise P3GateContractError(field, message)


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict):
        _fail(field, "expected a JSON object")
    return cast(JsonObject, value)


def _items(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(field, "expected a JSON array")
    return cast(list[Any], value)


def _exact_keys(document: Mapping[str, object], expected: set[str], field: str) -> None:
    observed = set(document)
    if observed != expected:
        _fail(
            field,
            f"missing={sorted(expected - observed)} extra={sorted(observed - expected)}",
        )


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
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


def _stage_semantic_projection(stage: str, report: Mapping[str, object]) -> object:
    projection = _stable_projection(report)
    if stage == "approval_decisions":
        projected_report = _object(projection, "approval_decisions.projection")
        for index, raw in enumerate(
            _items(
                projected_report.get("checks"),
                "approval_decisions.projection.checks",
            )
        ):
            check = _object(raw, f"approval_decisions.projection.checks[{index}]")
            if check.get("check_id") != "concurrent-decision-single-cas-winner":
                continue
            evidence = _evidence(
                check,
                f"approval_decisions.projection.checks[{index}].evidence",
            )
            evidence["winner"] = "ONE_OF_APPROVE_OR_REJECT"
            evidence["loser_failure"] = (
                "ONE_OF_INVALID_STATE_TRANSITION_OR_STALE_SOURCE"
            )
            return projected_report
        _fail(
            "approval_decisions.projection",
            "concurrent decision check is absent",
        )
    if stage == "publication":
        projected_report = _object(projection, "publication.projection")
        for index, raw in enumerate(
            _items(projected_report.get("checks"), "publication.projection.checks")
        ):
            check = _object(raw, f"publication.projection.checks[{index}]")
            if (
                check.get("check_id")
                != "concurrent-publication-single-current-cas-winner"
            ):
                continue
            evidence = _evidence(
                check,
                f"publication.projection.checks[{index}].evidence",
            )
            evidence["loser_failure"] = (
                "ONE_OF_CURRENT_REFERENCE_CONFLICT_OR_STALE_SOURCE"
            )
            return projected_report
        _fail(
            "publication.projection",
            "concurrent publication check is absent",
        )
    return projection


def _check_id(check: Mapping[str, object], field: str) -> str:
    value = check.get("check_id") or check.get("name") or check.get("id")
    if not isinstance(value, str) or not value:
        _fail(field, "check has no stable identity")
    return value


def _checks_by_id(report: Mapping[str, object], field: str) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for index, raw in enumerate(_items(report.get("checks"), f"{field}.checks")):
        check = _object(raw, f"{field}.checks[{index}]")
        identity = _check_id(check, f"{field}.checks[{index}]")
        if identity in result:
            _fail(f"{field}.checks[{index}]", "duplicate check identity")
        if check.get("status") != "PASS":
            _fail(f"{field}.checks[{index}].status", "subordinate check failed")
        result[identity] = check
    if report.get("check_count") != len(result):
        _fail(f"{field}.check_count", "does not match unique checks")
    return result


def _counts(report: Mapping[str, object], field: str) -> JsonObject:
    return _object(report.get("counts"), f"{field}.counts")


def _boundaries(report: Mapping[str, object], field: str) -> JsonObject:
    return _object(report.get("boundaries"), f"{field}.boundaries")


def _evidence(check: Mapping[str, object], field: str) -> JsonObject:
    value = check.get("evidence", check.get("details"))
    return _object(value, field)


def _expect_values(
    observed: Mapping[str, object], expected: Mapping[str, object], field: str
) -> None:
    for key, value in expected.items():
        if observed.get(key) != value:
            _fail(f"{field}.{key}", f"expected {value!r}")


def _validate_business_stage(
    contract: StageContract,
    report: Mapping[str, object],
    checks: Mapping[str, JsonObject],
) -> None:
    counts = _counts(report, contract.key)
    boundaries = _boundaries(report, contract.key)
    if contract.key == "workspace_contracts":
        _expect_values(
            counts,
            {"new_schemas": 7, "new_samples": 7, "negative_schema_rejections": 24},
            f"{contract.key}.counts",
        )
        _expect_values(
            boundaries,
            {"later_phase_contracts": "ABSENT", "runtime_dependency_change": "NONE"},
            f"{contract.key}.boundaries",
        )
    elif contract.key == "persistence":
        _expect_values(
            counts,
            {
                "tables": 5,
                "database_mutation_rejections": 4,
                "plane_mismatch_rejections": 2,
            },
            f"{contract.key}.counts",
        )
        _expect_values(
            boundaries,
            {"external_side_effects": "NONE", "production_readiness": "NOT_CLAIMED"},
            f"{contract.key}.boundaries",
        )
    elif contract.key == "schedule_version_lifecycle":
        _expect_values(
            counts,
            {
                "fresh_validation_and_kpi_gate": 1,
                "reviewable_schedule_versions": 1,
                "lifecycle_service_solver_invocations": 0,
            },
            f"{contract.key}.counts",
        )
    elif contract.key == "workspace_read_models":
        _expect_values(
            counts,
            {
                "workspace_views": 14,
                "comparison_results": 1,
                "product_service_solver_invocations": 0,
            },
            f"{contract.key}.counts",
        )
        _expect_values(
            boundaries,
            {"repository_writes_from_queries": "FORBIDDEN_AND_ABSENT"},
            f"{contract.key}.boundaries",
        )
    elif contract.key == "schedule_commands":
        _expect_values(
            counts,
            {
                "command_types": 5,
                "fresh_validator_passes": 5,
                "historical_source_states": 2,
            },
            f"{contract.key}.counts",
        )
        historical = _evidence(
            checks["P3-06-HISTORICAL-IMMUTABILITY"],
            f"{contract.key}.historical_immutability",
        )
        _expect_values(
            historical,
            {
                "derived_state": "DRAFT",
                "source_mutations": 0,
                "source_states": ["REJECTED", "PUBLISHED"],
            },
            f"{contract.key}.historical_immutability",
        )
    elif contract.key == "approval_decisions":
        _expect_values(
            counts,
            {
                "decision_types": 2,
                "successful_decisions": 3,
                "authorization_denials": 3,
                "product_service_solver_invocations": 0,
            },
            f"{contract.key}.counts",
        )
        concurrency = _evidence(
            checks["concurrent-decision-single-cas-winner"],
            f"{contract.key}.concurrent_decision",
        )
        if concurrency.get("winner") not in _APPROVAL_CONCURRENCY_EQUIVALENCE["winner"]:
            _fail(f"{contract.key}.concurrent_decision.winner", "unexpected winner")
        if (
            concurrency.get("loser_failure")
            not in (_APPROVAL_CONCURRENCY_EQUIVALENCE["loser_failure"])
        ):
            _fail(
                f"{contract.key}.concurrent_decision.loser_failure",
                "unexpected loser failure",
            )
        _expect_values(
            concurrency,
            {"decision_audits": 1, "winner_exact_replay": True},
            f"{contract.key}.concurrent_decision",
        )
    elif contract.key == "publication":
        _expect_values(
            counts,
            {
                "successful_publications": 3,
                "supersessions": 2,
                "exact_replays": 1,
                "rejected_requests_without_business_state": 4,
            },
            f"{contract.key}.counts",
        )
        negative = _evidence(
            checks["draft-ready-rejected-negative-no-side-effect"],
            f"{contract.key}.negative",
        )
        _expect_values(
            negative,
            {
                "invalid_states": ["DRAFT", "READY_FOR_REVIEW", "REJECTED"],
                "rejections": 3,
                "publication_side_effects": 0,
            },
            f"{contract.key}.negative",
        )
        concurrency = _evidence(
            checks["concurrent-publication-single-current-cas-winner"],
            f"{contract.key}.concurrent_publication",
        )
        if (
            concurrency.get("loser_failure")
            not in _PUBLICATION_CONCURRENCY_EQUIVALENCE["loser_failure"]
        ):
            _fail(
                f"{contract.key}.concurrent_publication.loser_failure",
                "unexpected loser failure",
            )
        _expect_values(
            concurrency,
            {
                "candidate_states": ["APPROVED", "PUBLISHED"],
                "losers": 1,
                "winners": 1,
            },
            f"{contract.key}.concurrent_publication",
        )
        _expect_values(
            boundaries,
            {"source_state": "APPROVED_ONLY", "published_content": "IMMUTABLE"},
            f"{contract.key}.boundaries",
        )
    elif contract.key == "export_jobs":
        _expect_values(
            counts,
            {
                "package_payloads": 12,
                "export_states": 5,
                "export_allowed_pairs": 6,
                "provider_side_effects": 0,
            },
            f"{contract.key}.counts",
        )
        focused = counts.get("focused_tests")
        if isinstance(focused, bool) or not isinstance(focused, int) or focused < 18:
            _fail(f"{contract.key}.counts.focused_tests", "expected at least 18")
    elif contract.key == "planning_workspace_api":
        _expect_values(
            counts,
            {
                "api_paths": 18,
                "http_operations": 18,
                "successful_delegations": 18,
                "production_provider_lookups": 0,
                "production_application_calls": 0,
                "router_business_state_transitions": 0,
                "solver_validator_invocations": 0,
            },
            f"{contract.key}.counts",
        )
        _expect_values(
            boundaries,
            {
                "p3_10_frozen_operations": 17,
                "p3_13_additive_operations": 1,
                "p4_capabilities": "NOT_IMPLEMENTED",
                "production_readiness": "NOT_CLAIMED",
            },
            f"{contract.key}.boundaries",
        )


def _validate_stage_report(
    report: JsonObject, contract: StageContract, code_commit: str
) -> None:
    field = contract.key
    if report.get("report_version") != contract.report_version:
        _fail(f"{field}.report_version", f"expected {contract.report_version}")
    if report.get("task_id") != contract.task_id:
        _fail(f"{field}.task_id", f"expected {contract.task_id}")
    if report.get("status") != "PASS":
        _fail(f"{field}.status", "subordinate report is not PASS")
    if report.get("code_commit") != code_commit:
        _fail(f"{field}.code_commit", "report is not bound to Gate code commit")
    if report.get("issues", []) != []:
        _fail(f"{field}.issues", "subordinate report contains issues")
    checks = _checks_by_id(report, field)
    if tuple(checks) != contract.check_ids:
        _fail(f"{field}.checks", "check identity/order changed")
    _validate_business_stage(contract, report, checks)


def _run_stage(stage: str, operation: Callable[[], object]) -> object:
    try:
        return operation()
    except (P3GateContractError, P3GateExecutionError):
        raise
    except Exception as error:
        raise P3GateExecutionError(stage, error) from error


def _run_backend_replay(root: Path, index: int, code_commit: str) -> JsonObject:
    reports: JsonObject = {}
    stage_microseconds: JsonObject = {}
    replay_started = perf_counter_ns()
    for contract in _STAGES:
        started = perf_counter_ns()
        report = cast(
            JsonObject,
            _run_stage(
                f"backend-replay-{index}.{contract.key}",
                lambda contract=contract: contract.runner(root),
            ),
        )
        stage_microseconds[contract.key] = (perf_counter_ns() - started) // 1_000
        _validate_stage_report(report, contract, code_commit)
        reports[contract.key] = report
    projections = {
        contract.key: _stage_semantic_projection(
            contract.key, cast(JsonObject, reports[contract.key])
        )
        for contract in _STAGES
    }
    fingerprints = {key: _sha256(value) for key, value in projections.items()}
    fingerprints["combined"] = _sha256(projections)
    return {
        "replay_index": index,
        "status": "PASS",
        "stage_order": [contract.key for contract in _STAGES],
        "stage_microseconds": stage_microseconds,
        "total_microseconds": (perf_counter_ns() - replay_started) // 1_000,
        "raw_subreports": reports,
        "stable_fingerprints": fingerprints,
    }


def _state_rejection(case_id: str, source: str) -> JsonObject:
    try:
        require_transition(StateMachineName.SCHEDULE_VERSION, source, "PUBLISHED")
    except StateTransitionError as error:
        if error.code.value != "INVALID_STATE_TRANSITION":
            _fail(case_id, "state-machine error code changed")
        return {
            "case_id": case_id,
            "status": "PASS",
            "stage": "schedule_version.publication_precondition",
            "category": error.category.value,
            "code": error.code.value,
            "behavior": "REJECTED_BEFORE_PUBLICATION_SIDE_EFFECT",
            "details": {"source_state": source, "target_state": "PUBLISHED"},
        }
    _fail(case_id, "invalid publication transition was accepted")


def _published_mutation_rejection() -> JsonObject:
    current: JsonObject = {
        "schedule_version_id": "schedule-version-p3-gate-published",
        "state": "PUBLISHED",
        "content": {"operation": "immutable"},
    }
    candidate = deepcopy(current)
    candidate["state"] = "SUPERSEDED"
    candidate["content"] = {"operation": "mutated"}
    try:
        require_schedule_version_transition(current, candidate)
    except ScheduleVersionPersistenceTransitionError as error:
        if "immutable" not in str(error).lower():
            _fail("PUBLISHED_CONTENT_CANNOT_MUTATE", "immutable cause was lost")
        return {
            "case_id": "PUBLISHED_CONTENT_CANNOT_MUTATE",
            "status": "PASS",
            "stage": "workspace_persistence.transition",
            "category": "WORKSPACE_CONTROL",
            "code": "STATE_CONFLICT",
            "behavior": "REJECTED_BEFORE_PERSISTENCE_WRITE",
            "details": {
                "source_state": "PUBLISHED",
                "target_state": "SUPERSEDED",
                "repository_mapping": "STATE_CONFLICT",
            },
        }
    _fail("PUBLISHED_CONTENT_CANNOT_MUTATE", "published content mutation passed")


def _unpublished_export_rejection(root: Path) -> JsonObject:
    schedule = cast(
        JsonObject,
        json.loads(
            (root / "schemas/samples/schedule-version.v1.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    publication = cast(
        JsonObject,
        json.loads(
            (root / "schemas/samples/publication-result.v1.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    request = ExportJobRequest(
        schedule_version_id=cast(str, schedule["schedule_version_id"]),
        expected_content_fingerprint=cast(str, schedule["content_fingerprint"]),
        raw_idempotency_key="p3-gate-unpublished-export-key-0001",
        reason="Prove that an unpublished Version cannot create an ExportJob.",
        correlation_id="correlation-p3-gate-unpublished-export",
        environment="TEST",
        synthetic_provenance=cast(
            Mapping[str, object], schedule["synthetic_provenance"]
        ),
    )
    identity = export_job_identity(request)
    context = ExportJobContext(
        actor_ref="actor:p3-gate-synthetic-exporter",
        authenticated=True,
        resolved_capabilities=frozenset({"export"}),
        schedule_version_scope=frozenset({request.schedule_version_id}),
        export_job_scope=frozenset(),
        auth_policy_version="p3-gate-simulation-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-26T00:00:00Z",
        code_commit=_code_commit(),
    )
    try:
        build_created_export_job(request, identity, context, schedule, publication)
    except ExportJobError as error:
        if error.reason is not ExportJobFailure.STALE_SOURCE:
            _fail("UNPUBLISHED_VERSION_CANNOT_EXPORT", "export reason changed")
        return {
            "case_id": "UNPUBLISHED_VERSION_CANNOT_EXPORT",
            "status": "PASS",
            "stage": "export_job.source_precondition",
            "category": "WORKSPACE_CONTROL",
            "code": error.reason.value,
            "behavior": "REJECTED_BEFORE_EXPORT_JOB_CREATION",
            "details": {
                "source_state": schedule["state"],
                "required_state": "PUBLISHED",
                "field": error.field,
            },
        }
    _fail("UNPUBLISHED_VERSION_CANNOT_EXPORT", "unpublished export was accepted")


def run_exit_rejection_checks(root: Path) -> list[JsonObject]:
    """Execute four exact P3 Exit precondition rejections without side effects."""

    rows = [
        _state_rejection("DRAFT_CANNOT_PUBLISH", "DRAFT"),
        _state_rejection("REJECTED_CANNOT_PUBLISH", "REJECTED"),
        _published_mutation_rejection(),
        _unpublished_export_rejection(root.resolve()),
    ]
    _validate_rejection_cases(rows)
    return rows


def _validate_rejection_cases(rows: Sequence[Mapping[str, object]]) -> None:
    if tuple(row.get("case_id") for row in rows) != _EXPECTED_REJECTION_IDS:
        _fail("rejection_cases", "rejection identity/order changed")
    expected = {
        "DRAFT_CANNOT_PUBLISH": (
            "schedule_version.publication_precondition",
            ProductErrorCategory.DATA_ERROR.value,
            "INVALID_STATE_TRANSITION",
        ),
        "REJECTED_CANNOT_PUBLISH": (
            "schedule_version.publication_precondition",
            ProductErrorCategory.DATA_ERROR.value,
            "INVALID_STATE_TRANSITION",
        ),
        "PUBLISHED_CONTENT_CANNOT_MUTATE": (
            "workspace_persistence.transition",
            "WORKSPACE_CONTROL",
            "STATE_CONFLICT",
        ),
        "UNPUBLISHED_VERSION_CANNOT_EXPORT": (
            "export_job.source_precondition",
            "WORKSPACE_CONTROL",
            "STALE_SOURCE",
        ),
    }
    for index, row in enumerate(rows):
        case_id = cast(str, row["case_id"])
        observed = (row.get("stage"), row.get("category"), row.get("code"))
        if row.get("status") != "PASS" or observed != expected[case_id]:
            _fail(
                f"rejection_cases[{index}]",
                "exact stage/category/code or PASS status changed",
            )


def _load_json_report(path: Path, field: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise P3GateExecutionError(field, error) from error
    return _object(value, field)


def validate_p3_frontend_gate_report(
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
        "human_control_report",
        "replays",
        "hash_consistency",
        "checks",
        "check_count",
        "issues",
        "blocking_gaps",
        "boundaries",
    }
    _exact_keys(report, expected_keys, "frontend_evidence")
    if (
        report.get("report_version") != FRONTEND_REPORT_VERSION
        or report.get("task_id") != TASK_ID
        or report.get("status") != "PASS"
        or report.get("code_commit") != code_commit
        or report.get("diff_base") != DIFF_BASE
    ):
        _fail("frontend_evidence", "identity/status/SHA/base changed")
    repeat = report.get("repeat_count")
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 2:
        _fail("frontend_evidence.repeat_count", "expected integer >= 2")
    if report.get("issues") != [] or report.get("blocking_gaps") != []:
        _fail("frontend_evidence", "PASS report contains issues or blocking gaps")
    if report.get("boundaries") != _FRONTEND_BOUNDARIES:
        _fail("frontend_evidence.boundaries", "phase/browser boundary changed")
    human = _object(
        report.get("human_control_report"), "frontend_evidence.human_control_report"
    )
    _expect_values(
        human,
        {
            "report_version": "p3-frontend-human-control-report.v1",
            "task_id": "TASK-P3-13",
            "code_commit": code_commit,
            "status": "PASS",
            "browser_spec_count": 12,
            "human_control_browser_spec_count": 8,
        },
        "frontend_evidence.human_control_report",
    )
    replays = _items(report.get("replays"), "frontend_evidence.replays")
    if len(replays) != repeat:
        _fail("frontend_evidence.replays", "repeat count mismatch")
    fingerprints: list[str] = []
    for index, raw in enumerate(replays):
        replay = _object(raw, f"frontend_evidence.replays[{index}]")
        if (
            replay.get("replay_index") != index + 1
            or replay.get("status") != "PASS"
            or replay.get("project_name") != "chromium-p3-human-control"
            or replay.get("spec_count") != 12
            or replay.get("human_control_spec_count") != 8
        ):
            _fail(f"frontend_evidence.replays[{index}]", "browser replay changed")
        fingerprint = replay.get("semantic_fingerprint")
        if not _is_sha256(fingerprint):
            _fail(
                f"frontend_evidence.replays[{index}].semantic_fingerprint",
                "expected sha256",
            )
        projection = replay.get("semantic_projection")
        if _sha256(projection) != fingerprint:
            _fail(
                f"frontend_evidence.replays[{index}].semantic_fingerprint",
                "does not match the semantic projection",
            )
        fingerprints.append(cast(str, fingerprint))
        raw_evidence = _object(
            replay.get("raw_evidence"),
            f"frontend_evidence.replays[{index}].raw_evidence",
        )
        for kind in ("json", "junit", "html"):
            artifact = _object(
                raw_evidence.get(kind),
                f"frontend_evidence.replays[{index}].raw_evidence.{kind}",
            )
            if not _is_sha256(artifact.get("sha256")):
                _fail(
                    f"frontend_evidence.replays[{index}].raw_evidence.{kind}",
                    "raw artifact hash is absent",
                )
    consistency = _object(
        report.get("hash_consistency"), "frontend_evidence.hash_consistency"
    )
    if (
        len(set(fingerprints)) != 1
        or consistency.get("status") != "PASS"
        or consistency.get("semantic_fingerprints") != fingerprints
        or consistency.get("unique_semantic_fingerprints") != 1
    ):
        _fail("frontend_evidence.hash_consistency", "browser semantics differ")
    checks = _checks_by_id(report, "frontend_evidence")
    if tuple(checks) != (
        "frozen-human-control-report",
        "two-complete-chromium-replays",
        "json-junit-html-and-failure-retention",
        "stable-browser-semantic-projection",
        "phase-boundary",
    ):
        _fail("frontend_evidence.checks", "frontend Gate checks changed")


def _validate_p2_regression(report: JsonObject, code_commit: str) -> None:
    from app.application.p2_gate_report import validate_p2_vertical_slice_report

    validate_p2_vertical_slice_report(report)
    if report.get("code_commit") != code_commit:
        _fail("p2_regression.code_commit", "P2 Gate report is not bound to Gate SHA")
    if report.get("status") != "PASS" or report.get("blocking_gaps") != []:
        _fail("p2_regression", "P2 Gate regression did not pass")


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def _aggregate_checks(
    replays: Sequence[JsonObject],
    frontend: JsonObject,
    p2: JsonObject,
    rejections: Sequence[JsonObject],
) -> list[JsonObject]:
    first_reports = _object(replays[0]["raw_subreports"], "backend_replays[0]")
    command_counts = _counts(
        _object(first_reports["schedule_commands"], "schedule_commands"),
        "schedule_commands",
    )
    approval_counts = _counts(
        _object(first_reports["approval_decisions"], "approval_decisions"),
        "approval_decisions",
    )
    publication_counts = _counts(
        _object(first_reports["publication"], "publication"), "publication"
    )
    export_counts = _counts(
        _object(first_reports["export_jobs"], "export_jobs"), "export_jobs"
    )
    fingerprints = [
        cast(JsonObject, replay["stable_fingerprints"])["combined"]
        for replay in replays
    ]
    return [
        _pass(
            _EXPECTED_CHECKS[0],
            {
                "status": "PASS",
                "audit_kind": "ACTIVATION_PROVIDER_AUDIT",
                "task_count": len(_PREDECESSOR_CLOSURES),
                "closure_commits": dict(_PREDECESSOR_CLOSURES),
                "provider_reports_embedded": False,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[1],
            {
                "report_version": p2["report_version"],
                "full_replays": p2["repeat_count"],
                "blocking_gaps": p2["blocking_gaps"],
                "validated_solution_input": True,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[2],
            {
                "repeat_count": len(replays),
                "stage_order": replays[0]["stage_order"],
                "raw_subreports_per_replay": len(_STAGES),
            },
        ),
        _pass(
            _EXPECTED_CHECKS[3],
            {
                "schemas": 7,
                "persistence_tables": 5,
                "database_mutation_rejections_per_replay": 4,
                "state_pair_changes": 0,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[4],
            {
                "workspace_views_per_replay": 14,
                "comparisons_per_replay": 1,
                "planning_run_mutations": 0,
                "source_version_mutations": 0,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[5],
            {
                "command_types_per_replay": command_counts["command_types"],
                "fresh_validator_passes_per_replay": command_counts[
                    "fresh_validator_passes"
                ],
                "derived_state": "DRAFT",
            },
        ),
        _pass(
            _EXPECTED_CHECKS[6],
            {
                "decision_types_per_replay": approval_counts["decision_types"],
                "authorization_denials_per_replay": approval_counts[
                    "authorization_denials"
                ],
                "append_only_audit": True,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[7],
            {
                "successful_publications_per_replay": publication_counts[
                    "successful_publications"
                ],
                "exact_replays_per_replay": publication_counts["exact_replays"],
                "source_state": "APPROVED_ONLY",
                "published_content": "IMMUTABLE",
            },
        ),
        _pass(
            _EXPECTED_CHECKS[8],
            {
                "package_payloads_per_replay": export_counts["package_payloads"],
                "export_allowed_pairs": export_counts["export_allowed_pairs"],
                "provider_side_effects": export_counts["provider_side_effects"],
            },
        ),
        _pass(
            _EXPECTED_CHECKS[9],
            {
                "http_operations_per_replay": 18,
                "frozen_plus_additive": "17+1",
                "router_business_state_transitions": 0,
                "production_provider_lookups": 0,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[10],
            {
                "frontend_report_version": frontend["report_version"],
                "browser_replays": frontend["repeat_count"],
                "browser_spec_executions": cast(int, frontend["repeat_count"]) * 12,
                "raw_formats": ["JSON", "JUNIT", "HTML"],
            },
        ),
        _pass(
            _EXPECTED_CHECKS[11],
            {
                "case_ids": [row["case_id"] for row in rejections],
                "case_count": len(rejections),
                "exact_stage_category_code": True,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[12],
            {
                "projection_version": SEMANTIC_PROJECTION_VERSION,
                "combined_fingerprints": fingerprints,
                "unique_combined_fingerprints": len(set(fingerprints)),
                "raw_timing_and_identity_retained": True,
            },
        ),
        _pass(_EXPECTED_CHECKS[13], dict(_BOUNDARIES)),
    ]


def run_p3_vertical_slice_gate(
    *,
    root: Path,
    frontend_report: Mapping[str, object],
    p2_report: Mapping[str, object],
    repeat: int = 2,
) -> JsonObject:
    """Run at least two complete P3 Backend replays and aggregate browser evidence."""

    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 2:
        _fail("repeat", "P3 Gate requires at least two complete replays")
    code_commit = _code_commit()
    frontend = dict(frontend_report)
    p2 = dict(p2_report)
    validate_p3_frontend_gate_report(frontend, code_commit)
    _validate_p2_regression(p2, code_commit)
    replays = [
        _run_backend_replay(root.resolve(), index, code_commit)
        for index in range(1, repeat + 1)
    ]
    stage_fingerprints = {
        contract.key: [
            cast(JsonObject, replay["stable_fingerprints"])[contract.key]
            for replay in replays
        ]
        for contract in _STAGES
    }
    combined = [
        cast(JsonObject, replay["stable_fingerprints"])["combined"]
        for replay in replays
    ]
    unstable_stages = [
        key for key, values in stage_fingerprints.items() if len(set(values)) != 1
    ]
    if len(set(combined)) != 1 or unstable_stages:
        _fail(
            "semantic_consistency",
            "stable business semantics changed across complete P3 replays: "
            + ", ".join(unstable_stages),
        )
    rejections = cast(
        list[JsonObject],
        _run_stage("exit-rejection-contracts", lambda: run_exit_rejection_checks(root)),
    )
    checks = _aggregate_checks(replays, frontend, p2, rejections)
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "generated_at_utc": _generated_at(),
        "versions": {
            "gate_contract": REPORT_VERSION,
            "semantic_projection": SEMANTIC_PROJECTION_VERSION,
            "frontend_gate": FRONTEND_REPORT_VERSION,
            "p2_gate": "p2-vertical-slice-report.v1",
            "schema_set": "2.7.0",
        },
        "frozen_inputs": {
            "diff_base": DIFF_BASE,
            "predecessor_closure_commits": dict(_PREDECESSOR_CLOSURES),
            "activation_provider_audit": "PASS",
        },
        "repeat_count": repeat,
        "execution": {
            "minimum_repeat_count": 2,
            "backend_full_replays_complete": repeat,
            "frontend_full_replays_complete": frontend["repeat_count"],
            "all_public_backend_boundaries_reexecuted": True,
            "stage_order": replays[0]["stage_order"],
        },
        "backend_replays": replays,
        "frontend_evidence": frontend,
        "p2_regression": p2,
        "rejection_cases": rejections,
        "semantic_consistency": {
            "projection_version": SEMANTIC_PROJECTION_VERSION,
            "status": "PASS",
            "stage_fingerprints": stage_fingerprints,
            "combined_fingerprints": combined,
            "unique_combined_fingerprints": len(set(combined)),
            "excluded_runtime_noise_keys": sorted(_RUNTIME_NOISE_KEYS),
            "normalized_concurrency_outcomes": dict(_APPROVAL_CONCURRENCY_EQUIVALENCE),
            "raw_evidence_policy": (
                "ALL_SUBREPORTS_AND_RUNTIME_OBSERVATIONS_RETAINED;_ONLY_"
                "VERSIONED_RUNTIME_NOISE_DERIVED_COMMIT_IDENTITY_AND_VALID_"
                "CONCURRENCY_INTERLEAVING_NORMALIZED_FOR_SEMANTIC_COMPARISON"
            ),
        },
        "checks": checks,
        "check_count": len(checks),
        "counts": {
            "backend_full_replays": repeat,
            "backend_stage_executions": repeat * len(_STAGES),
            "backend_subreport_checks": repeat
            * sum(len(contract.check_ids) for contract in _STAGES),
            "frontend_full_replays": frontend["repeat_count"],
            "browser_spec_executions": cast(int, frontend["repeat_count"]) * 12,
            "human_control_browser_spec_executions": cast(int, frontend["repeat_count"])
            * 8,
            "p2_gate_full_replays": p2["repeat_count"],
            "exit_rejection_cases": len(rejections),
            "predecessor_tasks": len(_PREDECESSOR_CLOSURES),
        },
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
    }
    validate_p3_vertical_slice_report(report)
    return report


def validate_p3_vertical_slice_report(report: Mapping[str, object]) -> None:
    """Validate the strict internal ``p3-vertical-slice-report.v1`` contract."""

    expected_keys = {
        "report_version",
        "status",
        "task_id",
        "code_commit",
        "diff_base",
        "generated_at_utc",
        "versions",
        "frozen_inputs",
        "repeat_count",
        "execution",
        "backend_replays",
        "frontend_evidence",
        "p2_regression",
        "rejection_cases",
        "semantic_consistency",
        "checks",
        "check_count",
        "counts",
        "blocking_gaps",
        "boundaries",
    }
    _exact_keys(report, expected_keys, "$")
    if (
        report.get("report_version") != REPORT_VERSION
        or report.get("status") != "PASS"
        or report.get("task_id") != TASK_ID
        or report.get("diff_base") != DIFF_BASE
    ):
        _fail("$", "Gate identity/status/base changed")
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
    recomputed: dict[str, list[str]] = {contract.key: [] for contract in _STAGES}
    combined: list[str] = []
    for index, raw in enumerate(replays):
        replay = _object(raw, f"backend_replays[{index}]")
        if replay.get("replay_index") != index + 1 or replay.get("status") != "PASS":
            _fail(f"backend_replays[{index}]", "identity/status changed")
        reports = _object(
            replay.get("raw_subreports"), f"backend_replays[{index}].raw_subreports"
        )
        if tuple(reports) != tuple(contract.key for contract in _STAGES):
            _fail(f"backend_replays[{index}].raw_subreports", "stage order changed")
        projections: JsonObject = {}
        for contract in _STAGES:
            subreport = _object(
                reports[contract.key],
                f"backend_replays[{index}].{contract.key}",
            )
            _validate_stage_report(subreport, contract, cast(str, code_commit))
            projection = _stage_semantic_projection(contract.key, subreport)
            projections[contract.key] = projection
            recomputed[contract.key].append(_sha256(projection))
        stable = _object(
            replay.get("stable_fingerprints"),
            f"backend_replays[{index}].stable_fingerprints",
        )
        expected = {
            **{key: values[-1] for key, values in recomputed.items()},
            "combined": _sha256(projections),
        }
        if stable != expected:
            _fail(f"backend_replays[{index}].stable_fingerprints", "hash mismatch")
        combined.append(cast(str, expected["combined"]))
    unstable_stages = [
        key for key, values in recomputed.items() if len(set(values)) != 1
    ]
    if len(set(combined)) != 1 or unstable_stages:
        _fail(
            "semantic_consistency",
            "replay semantics differ: " + ", ".join(unstable_stages),
        )
    consistency = _object(report.get("semantic_consistency"), "semantic_consistency")
    if (
        consistency.get("status") != "PASS"
        or consistency.get("projection_version") != SEMANTIC_PROJECTION_VERSION
        or consistency.get("stage_fingerprints") != recomputed
        or consistency.get("combined_fingerprints") != combined
        or consistency.get("unique_combined_fingerprints") != 1
    ):
        _fail("semantic_consistency", "aggregate hash evidence changed")
    validate_p3_frontend_gate_report(
        _object(report.get("frontend_evidence"), "frontend_evidence"),
        cast(str, code_commit),
    )
    _validate_p2_regression(
        _object(report.get("p2_regression"), "p2_regression"),
        cast(str, code_commit),
    )
    rejections = [
        _object(row, f"rejection_cases[{index}]")
        for index, row in enumerate(
            _items(report.get("rejection_cases"), "rejection_cases")
        )
    ]
    _validate_rejection_cases(rejections)
    checks = _checks_by_id(report, "$")
    if tuple(checks) != _EXPECTED_CHECKS or report.get("check_count") != len(
        _EXPECTED_CHECKS
    ):
        _fail("checks", "aggregate check identity/count changed")
    if report.get("blocking_gaps") != []:
        _fail("blocking_gaps", "PASS report contains blocking gaps")
    if report.get("boundaries") != _BOUNDARIES:
        _fail("boundaries", "P3/Exit/P4/Production boundary changed")
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in (
        '"exit_gate_audit": "READY"',
        '"p3_15": "STARTED"',
        '"p4": "STARTED"',
        '"production_readiness": "READY"',
    ):
        if forbidden in serialized:
            _fail("boundaries", f"forbidden claim present: {forbidden}")


def _failure_report(error: Exception, repeat: int) -> JsonObject:
    stage = getattr(error, "stage", "orchestrator")
    return {
        "report_version": REPORT_VERSION,
        "status": "FAIL",
        "task_id": TASK_ID,
        "code_commit": _code_commit(),
        "diff_base": DIFF_BASE,
        "generated_at_utc": _generated_at(),
        "repeat_count": repeat,
        "error": {
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error),
        },
        "blocking_gaps": [
            {
                "gap_id": "P3-GATE-EXECUTION-001",
                "stage": stage,
                "status": "BLOCKING",
                "remediation": "REQUIRES_SEPARATE_BOUNDED_TASK",
            }
        ],
        "boundaries": dict(_BOUNDARIES),
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--frontend-report", type=Path, required=True)
    parser.add_argument("--p2-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        frontend = _load_json_report(arguments.frontend_report, "frontend-report")
        p2 = _load_json_report(arguments.p2_report, "p2-report")
        report = run_p3_vertical_slice_gate(
            root=arguments.root,
            frontend_report=frontend,
            p2_report=p2,
            repeat=arguments.repeat,
        )
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
    "REPORT_VERSION",
    "SEMANTIC_PROJECTION_VERSION",
    "TASK_ID",
    "P3GateContractError",
    "P3GateExecutionError",
    "main",
    "run_exit_rejection_checks",
    "run_p3_vertical_slice_gate",
    "validate_p3_frontend_gate_report",
    "validate_p3_vertical_slice_report",
]
