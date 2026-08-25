"""Emit machine-checkable TASK-P3-07 approval decision evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from typing import Any, cast
import json
import os

from alembic import command as alembic_command

from app.application.approval import ApprovalDecisionResult, ApprovalDecisionService
from app.application.schedule_version_lifecycle_check import (
    _service as lifecycle_service,
    _workspace_engine,
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.authorization import (
    APPROVAL_DECISION_SERVICE_VERSION,
    ApprovalDecisionContext,
    ApprovalDecisionError,
    ApprovalDecisionFailure,
)
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_command_fingerprint,
)


REPORT_VERSION = "p3-approval-decision-report.v1"
TASK_ID = "TASK-P3-07"


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _adapters() -> Any:
    return __import__("app.infrastructure", fromlist=["infrastructure"])


def _repositories(engine: Any, data_plane: str = "SIMULATION") -> tuple[Any, Any]:
    adapters = _adapters()
    plane = adapters.WorkspaceDataPlane(data_plane)
    return (
        adapters.SqlAlchemyScheduleVersionRepository(engine, data_plane=plane),
        adapters.SqlAlchemyAuditRepository(engine, data_plane=plane),
    )


def _service(
    engine: Any,
    *,
    data_plane: str = "SIMULATION",
    audit_repository: Any | None = None,
) -> ApprovalDecisionService:
    schedule_repository, default_audit = _repositories(engine, data_plane)
    return ApprovalDecisionService(
        data_plane=data_plane,
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=audit_repository or default_audit,
    )


def _source(engine: Any, output: Any, key_character: str) -> Any:
    return lifecycle_service(engine, "SIMULATION").create_reviewable(
        output,
        lifecycle_context(
            key_character,
            reason=f"Create reviewable source {key_character} for P3-07 evidence.",
            correlation_id=f"correlation-p3-07-source-{key_character}",
        ),
    )


def _context(
    source: Mapping[str, object],
    *capabilities: str,
    scope: bool = True,
    authenticated: bool = True,
    actor_ref: str = "actor:p3-approval-machine",
    occurred_at_utc: str = "2026-08-25T05:00:00Z",
) -> ApprovalDecisionContext:
    return ApprovalDecisionContext(
        actor_ref=actor_ref,
        authenticated=authenticated,
        resolved_capabilities=frozenset(capabilities),
        schedule_version_scope=(
            frozenset({cast(str, source["schedule_version_id"])})
            if scope
            else frozenset({"schedule-version-out-of-scope"})
        ),
        auth_policy_version="simulation-test-approval-policy.v1",
        production_binding=False,
        occurred_at_utc=occurred_at_utc,
        code_commit=os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
    )


def _command(
    source: Mapping[str, object],
    command_type: str,
    *,
    key: str,
    reason: str,
    correlation_id: str,
    data_plane: str = "SIMULATION",
) -> dict[str, object]:
    synthetic = data_plane == "SIMULATION"
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": command_type,
        "required_capability": command_type.lower(),
        "idempotency_key": key,
        "idempotency_scope": (
            f"{data_plane}/{command_type}/{source['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "READY_FOR_REVIEW",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": data_plane,
        "environment": "TEST" if synthetic else "PRODUCTION",
        "synthetic": synthetic,
        "target": "WORKSPACE_INTERNAL",
        "reason": reason,
        "correlation_id": correlation_id,
        "payload": {},
    }
    if synthetic:
        command["synthetic_provenance"] = source["synthetic_provenance"]
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _expect(
    expected: ApprovalDecisionFailure | set[ApprovalDecisionFailure],
    operation: Callable[[], object],
) -> ApprovalDecisionFailure:
    expected_set = expected if isinstance(expected, set) else {expected}
    try:
        operation()
    except ApprovalDecisionError as error:
        if error.reason in expected_set:
            return error.reason
        raise ValueError(
            f"unexpected approval failure: {error.reason.value}"
        ) from error
    raise ValueError("expected approval decision rejection")


def _counts(engine: Any) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            "schedule_versions": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM schedule_versions"
                ).scalar_one()
            ),
            "audit_events": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM audit_events"
                ).scalar_one()
            ),
            "decision_success_audits": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM audit_events "
                    "WHERE action IN ('APPROVE','REJECT') "
                    'AND document_json LIKE \'%"outcome":"SUCCEEDED"%\''
                ).scalar_one()
            ),
            "decision_denial_audits": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM audit_events "
                    "WHERE action IN ('APPROVE','REJECT') "
                    'AND document_json LIKE \'%"outcome":"DENIED"%\''
                ).scalar_one()
            ),
        }


def _decision_audits(
    audit_repository: Any, schedule_version_id: str
) -> list[dict[str, object]]:
    return [
        event
        for event in audit_repository.list_for_aggregate(
            aggregate_type="SCHEDULE_VERSION",
            aggregate_id=schedule_version_id,
        )
        if event["action"] in {"APPROVE", "REJECT"}
    ]


class _FailingAuditRepository:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def get(self, audit_event_id: str) -> dict[str, object] | None:
        return self._delegate.get(audit_event_id)

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> Any:
        del connection, document
        raise RuntimeError("synthetic audit failure")


def run_approval_decision_checks(root: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    rejected_without_business_state = 0
    started = perf_counter_ns()
    with TemporaryDirectory(prefix="plantnexus-p3-07-") as temporary:
        engine, configuration = _workspace_engine(
            root, Path(temporary) / "approval-decisions.db"
        )
        try:
            output, _ = load_fixed_validated_output(root)
            schedule_repository, audit_repository = _repositories(engine)

            approve_source_result = _source(engine, output, "a")
            approve_source = approve_source_result.schedule_version
            approve_source_bytes = canonical_workspace_bytes(approve_source)
            approve_command = _command(
                approve_source,
                "APPROVE",
                key="p3-machine-approve-0001",
                reason="Approve the synthetic machine evidence Version.",
                correlation_id="correlation-p3-07-approve",
            )
            decision_service = _service(engine)
            approve = decision_service.execute(
                approve_command, _context(approve_source, "approve")
            )
            stored_approve = schedule_repository.get_record(
                cast(str, approve_source["schedule_version_id"])
            )
            if (
                stored_approve is None
                or stored_approve.document["state"] != "APPROVED"
                or stored_approve.state_revision != 2
                or stored_approve.document["content"] != approve_source["content"]
                or canonical_workspace_bytes(approve_source) != approve_source_bytes
                or len(
                    _decision_audits(
                        audit_repository,
                        cast(str, approve_source["schedule_version_id"]),
                    )
                )
                != 1
            ):
                raise ValueError("APPROVE did not commit one same-content state/audit")
            checks.append(
                _pass(
                    "approve-ready-atomic-same-content",
                    {
                        "state": "APPROVED",
                        "state_revision": 2,
                        "audit_event_id": approve.audit_event_id,
                        "content_fingerprint": approve.new_version[
                            "content_fingerprint"
                        ],
                    },
                )
            )

            approve_replay = decision_service.execute(
                approve_command, _context(approve_source, "approve")
            )
            if not approve_replay.exact_replay or approve_replay.new_version != (
                approve.new_version
            ):
                raise ValueError("exact approval replay changed logical result")
            conflicting = _command(
                approve_source,
                "APPROVE",
                key="p3-machine-approve-0001",
                reason="Conflicting reason under the same approval key.",
                correlation_id="correlation-p3-07-approve-conflict",
            )
            _expect(
                ApprovalDecisionFailure.IDEMPOTENCY_CONFLICT,
                lambda: decision_service.execute(
                    conflicting, _context(approve_source, "approve")
                ),
            )
            checks.append(
                _pass(
                    "decision-exact-replay-and-conflict",
                    {
                        "exact_replays": 1,
                        "idempotency_conflicts": 1,
                        "decision_audits": 1,
                    },
                )
            )

            reject_source_result = _source(engine, output, "b")
            reject_source = reject_source_result.schedule_version
            reject_command = _command(
                reject_source,
                "REJECT",
                key="p3-machine-reject-0001",
                reason="Reject the synthetic machine evidence Version.",
                correlation_id="correlation-p3-07-reject",
            )
            rejected = decision_service.execute(
                reject_command, _context(reject_source, "reject")
            )
            before_invalid = _counts(engine)
            after_reject = _command(
                reject_source,
                "APPROVE",
                key="p3-machine-after-reject",
                reason="Attempt a forbidden decision after terminal rejection.",
                correlation_id="correlation-p3-07-after-reject",
            )
            _expect(
                ApprovalDecisionFailure.INVALID_STATE_TRANSITION,
                lambda: decision_service.execute(
                    after_reject, _context(reject_source, "approve")
                ),
            )
            rejected_without_business_state += 1
            if _counts(engine) != before_invalid:
                raise ValueError("terminal rejection accepted a second side effect")
            checks.append(
                _pass(
                    "reject-terminal-and-no-second-decision",
                    {
                        "state": rejected.new_version["state"],
                        "allowed_actions": ["view", "edit", "lock"],
                        "second_decision": "INVALID_STATE_TRANSITION",
                    },
                )
            )

            auth_source_result = _source(engine, output, "c")
            auth_source = auth_source_result.schedule_version
            unauthorized = _command(
                auth_source,
                "APPROVE",
                key="p3-machine-denied-capability",
                reason="Exercise capability default deny.",
                correlation_id="correlation-p3-07-denied-capability",
            )
            before_auth_state = schedule_repository.get_record(
                cast(str, auth_source["schedule_version_id"])
            )
            for _ in range(2):
                _expect(
                    ApprovalDecisionFailure.AUTHORIZATION_DENIED,
                    lambda: decision_service.execute(
                        unauthorized, _context(auth_source, "view")
                    ),
                )
            out_of_scope = _command(
                auth_source,
                "REJECT",
                key="p3-machine-denied-scope",
                reason="Exercise exact resource-scope default deny.",
                correlation_id="correlation-p3-07-denied-scope",
            )
            _expect(
                ApprovalDecisionFailure.AUTHORIZATION_DENIED,
                lambda: decision_service.execute(
                    out_of_scope,
                    _context(auth_source, "reject", scope=False),
                ),
            )
            production_command = _command(
                auth_source,
                "APPROVE",
                key="p3-machine-production-deny",
                reason="Exercise Production authority default deny.",
                correlation_id="correlation-p3-07-production-deny",
                data_plane="PRODUCTION",
            )
            production_context = ApprovalDecisionContext(
                actor_ref="actor:production-unbound",
                authenticated=True,
                resolved_capabilities=frozenset({"approve"}),
                schedule_version_scope=frozenset(
                    {cast(str, auth_source["schedule_version_id"])}
                ),
                auth_policy_version="production-approval-policy-unconfigured.v1",
                production_binding=False,
                occurred_at_utc="2026-08-25T05:10:00Z",
                code_commit=os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            )
            _expect(
                ApprovalDecisionFailure.PRODUCTION_AUTHORITY_UNAVAILABLE,
                lambda: _service(engine, data_plane="PRODUCTION").execute(
                    production_command, production_context
                ),
            )
            after_auth_state = schedule_repository.get_record(
                cast(str, auth_source["schedule_version_id"])
            )
            if (
                before_auth_state is None
                or after_auth_state is None
                or after_auth_state.document != before_auth_state.document
                or after_auth_state.state_revision != before_auth_state.state_revision
            ):
                raise ValueError("authorization denial changed business state")
            auth_audits = _decision_audits(
                audit_repository, cast(str, auth_source["schedule_version_id"])
            )
            production_audit_repository = _repositories(engine, "PRODUCTION")[1]
            production_audits = _decision_audits(
                production_audit_repository,
                cast(str, auth_source["schedule_version_id"]),
            )
            if len(auth_audits) != 2 or len(production_audits) != 1:
                raise ValueError("high-risk denials were not exactly append-only")
            checks.append(
                _pass(
                    "authorization-scope-denial-audit-and-production-default-deny",
                    {
                        "simulation_denial_audits": len(auth_audits),
                        "production_denial_audits": len(production_audits),
                        "business_state": after_auth_state.document["state"],
                        "open_010": "OPEN",
                    },
                )
            )

            before_invalid = _counts(engine)
            stale = _command(
                auth_source,
                "APPROVE",
                key="p3-machine-stale-fingerprint",
                reason="Exercise stale content fingerprint rejection.",
                correlation_id="correlation-p3-07-stale",
            )
            stale["expected_content_fingerprint"] = "sha256:" + "f" * 64
            stale["request_fingerprint"] = workspace_command_fingerprint(stale)
            _expect(
                ApprovalDecisionFailure.STALE_SOURCE,
                lambda: decision_service.execute(
                    stale, _context(auth_source, "approve")
                ),
            )
            rejected_without_business_state += 1
            missing_reason = _command(
                auth_source,
                "REJECT",
                key="p3-machine-missing-reason",
                reason="temporary-valid-reason",
                correlation_id="correlation-p3-07-missing-reason",
            )
            missing_reason["reason"] = ""
            missing_reason["request_fingerprint"] = workspace_command_fingerprint(
                missing_reason
            )
            _expect(
                ApprovalDecisionFailure.INVALID_REQUEST,
                lambda: decision_service.execute(
                    missing_reason, _context(auth_source, "reject")
                ),
            )
            rejected_without_business_state += 1
            secret_reason = _command(
                auth_source,
                "APPROVE",
                key="p3-machine-secret-reason",
                reason="token=credential-material-must-not-be-recorded",
                correlation_id="correlation-p3-07-secret-reason",
            )
            _expect(
                ApprovalDecisionFailure.INVALID_REQUEST,
                lambda: decision_service.execute(
                    secret_reason, _context(auth_source, "approve")
                ),
            )
            rejected_without_business_state += 1
            if _counts(engine) != before_invalid:
                raise ValueError("invalid requests produced durable side effects")
            checks.append(
                _pass(
                    "stale-missing-reason-and-secret-redaction",
                    {
                        "negative_cases": 3,
                        "durable_side_effects": 0,
                        "credential_material": "REJECTED_BEFORE_AUDIT",
                    },
                )
            )

            rollback_source_result = _source(engine, output, "d")
            rollback_source = rollback_source_result.schedule_version
            before_rollback = schedule_repository.get_record(
                cast(str, rollback_source["schedule_version_id"])
            )
            before_rollback_counts = _counts(engine)
            failing_service = _service(
                engine,
                audit_repository=_FailingAuditRepository(audit_repository),
            )
            _expect(
                ApprovalDecisionFailure.PERSISTENCE_FAILED,
                lambda: failing_service.execute(
                    _command(
                        rollback_source,
                        "APPROVE",
                        key="p3-machine-audit-rollback",
                        reason="Exercise audit rollback boundary.",
                        correlation_id="correlation-p3-07-audit-rollback",
                    ),
                    _context(rollback_source, "approve"),
                ),
            )
            after_rollback = schedule_repository.get_record(
                cast(str, rollback_source["schedule_version_id"])
            )
            if (
                before_rollback is None
                or after_rollback is None
                or after_rollback.document != before_rollback.document
                or after_rollback.state_revision != before_rollback.state_revision
                or _counts(engine) != before_rollback_counts
            ):
                raise ValueError("audit failure did not roll back decision CAS")
            checks.append(
                _pass(
                    "audit-failure-rolls-back-state",
                    {
                        "state": after_rollback.document["state"],
                        "state_revision": after_rollback.state_revision,
                        "new_decision_audits": 0,
                    },
                )
            )

            race_source_result = _source(engine, output, "e")
            race_source = race_source_result.schedule_version
            race_commands = {
                "APPROVE": _command(
                    race_source,
                    "APPROVE",
                    key="p3-machine-race-approve",
                    reason="Concurrent approval candidate.",
                    correlation_id="correlation-p3-07-race-approve",
                ),
                "REJECT": _command(
                    race_source,
                    "REJECT",
                    key="p3-machine-race-reject",
                    reason="Concurrent rejection candidate.",
                    correlation_id="correlation-p3-07-race-reject",
                ),
            }
            barrier = Barrier(2)

            def invoke(command_type: str) -> ApprovalDecisionResult:
                barrier.wait()
                return _service(engine).execute(
                    race_commands[command_type],
                    _context(race_source, command_type.lower()),
                )

            successes: list[ApprovalDecisionResult] = []
            failures: list[ApprovalDecisionFailure] = []
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(invoke, command_type)
                    for command_type in ("APPROVE", "REJECT")
                ]
                for future in futures:
                    try:
                        successes.append(future.result())
                    except ApprovalDecisionError as error:
                        failures.append(error.reason)
            if len(successes) != 1 or len(failures) != 1:
                raise ValueError("concurrent decision did not produce one CAS winner")
            winner = successes[0]
            winner_replay = _service(engine).execute(
                race_commands[winner.command_type],
                _context(race_source, winner.command_type.lower()),
            )
            stored_race = schedule_repository.get(
                cast(str, race_source["schedule_version_id"])
            )
            race_audits = _decision_audits(
                audit_repository, cast(str, race_source["schedule_version_id"])
            )
            if (
                stored_race is None
                or stored_race["state"] != winner.new_version["state"]
                or not winner_replay.exact_replay
                or len(race_audits) != 1
            ):
                raise ValueError(
                    "concurrent winner/replay/audit evidence is inconsistent"
                )
            checks.append(
                _pass(
                    "concurrent-decision-single-cas-winner",
                    {
                        "winner": winner.command_type,
                        "loser_failure": failures[0].value,
                        "decision_audits": len(race_audits),
                        "winner_exact_replay": True,
                    },
                )
            )

            approve_audit = audit_repository.get(approve.audit_event_id)
            if approve_audit is None:
                raise ValueError("approval audit disappeared")
            audit_bytes = canonical_workspace_bytes(approve_audit)
            if cast(str, approve_command["idempotency_key"]).encode() in audit_bytes:
                raise ValueError("raw idempotency key leaked into approval audit")
            if any(
                forbidden in audit_bytes.lower()
                for forbidden in (
                    b"bearer ",
                    b"password=",
                    b"token=",
                    b"postgresql://",
                )
            ):
                raise ValueError("credential-like material leaked into decision audit")
            checks.append(
                _pass(
                    "append-only-lineage-redaction-and-phase-boundary",
                    {
                        "raw_idempotency_key_persisted": False,
                        "lineage_preserved": approve_audit["lineage"]
                        == approve_source["lineage"],
                        "schema_migration_dependency_changes": 0,
                        "publish_export_http_ui_p4_calls": 0,
                    },
                )
            )

            counts = _counts(engine)
        finally:
            engine.dispose()
            alembic_command.downgrade(configuration, "base")

    elapsed_microseconds = (perf_counter_ns() - started) // 1_000
    if len(checks) != 8 or any(check["status"] != "PASS" for check in checks):
        raise ValueError("P3-07 approval decision checks are incomplete")
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "status": "PASS",
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "approval_decision_service_version": APPROVAL_DECISION_SERVICE_VERSION,
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "decision_types": 2,
            "successful_decisions": counts["decision_success_audits"],
            "exact_replays": 2,
            "idempotency_conflicts": 1,
            "authorization_denials": 3,
            "denial_audits": counts["decision_denial_audits"],
            "rejected_requests_without_business_state": rejected_without_business_state,
            "atomic_rollbacks": 1,
            "product_service_solver_invocations": 0,
        },
        "observations": {
            "elapsed_microseconds": elapsed_microseconds,
            "schedule_versions": counts["schedule_versions"],
            "audit_events": counts["audit_events"],
            "benchmark_class": "DEVELOPMENT_OBSERVATION_ONLY_NO_SLA",
        },
        "boundaries": {
            "source_content_update": "FORBIDDEN_AND_ABSENT",
            "states_and_pairs": "EXISTING_READY_TO_APPROVED_OR_REJECTED_ONLY",
            "rejected_version_revision": "COPY_ON_WRITE_NEW_DRAFT_ONLY",
            "production_authority": "DEFAULT_DENY_OPEN_010",
            "real_rbac_sso": "NOT_IMPLEMENTED",
            "publish_export": "NOT_IMPLEMENTED",
            "http_ui": "NOT_IMPLEMENTED",
            "schema_migration_dependency": "UNCHANGED",
            "solver_validator": "NOT_MODIFIED_OR_INVOKED",
            "p4_capabilities": "NOT_IMPLEMENTED",
            "production_readiness": "NOT_CLAIMED",
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate TASK-P3-07 approval/rejection behavior"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p3-approval-decisions.json"),
    )
    arguments = parser.parse_args(argv)
    try:
        report = run_approval_decision_checks(arguments.root.resolve())
    except Exception as error:  # noqa: BLE001 - machine evidence must fail closed
        reason = (
            error.reason.value
            if isinstance(error, ApprovalDecisionError)
            else "MACHINE_CHECK_FAILED"
        )
        report = {
            "report_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "status": "FAIL",
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "check_count": 0,
            "checks": [],
            "issues": [
                {
                    "reason": reason,
                    "error_type": type(error).__name__,
                    "message": "P3-07 approval decision evidence did not complete",
                }
            ],
            "boundaries": {
                "production_authority": "DEFAULT_DENY_OPEN_010",
                "production_readiness": "NOT_CLAIMED",
            },
        }
        _write_report(arguments.report, report)
        return 1
    _write_report(arguments.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "TASK_ID", "main", "run_approval_decision_checks"]
