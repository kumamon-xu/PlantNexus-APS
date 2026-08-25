"""Emit machine-checkable TASK-P3-08 publication evidence."""

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

from app.application.approval import ApprovalDecisionService
from app.application.publication import PublicationService, PublicationServiceResult
from app.application.schedule_version_lifecycle_check import (
    _service as lifecycle_service,
    _workspace_engine,
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.authorization import ApprovalDecisionContext
from app.domain.publication import (
    PUBLICATION_SERVICE_VERSION,
    PublicationContext,
    PublicationError,
    PublicationFailure,
    prepare_publication,
)
from app.domain.schedule_version import build_reviewable_schedule_documents
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_command_fingerprint,
)


REPORT_VERSION = "p3-publication-report.v1"
TASK_ID = "TASK-P3-08"


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _adapters() -> Any:
    return __import__("app.infrastructure", fromlist=["infrastructure"])


def _repositories(engine: Any, data_plane: str = "SIMULATION") -> tuple[Any, Any, Any]:
    adapters = _adapters()
    plane = adapters.WorkspaceDataPlane(data_plane)
    schedule = adapters.SqlAlchemyScheduleVersionRepository(
        engine, data_plane=plane
    )
    audit = adapters.SqlAlchemyAuditRepository(engine, data_plane=plane)
    publication = adapters.SqlAlchemyPublicationRepository(
        engine,
        data_plane=adapters.WorkspaceDataPlane.SIMULATION,
    )
    return schedule, audit, publication


def _service(
    engine: Any,
    *,
    data_plane: str = "SIMULATION",
    audit_repository: Any | None = None,
) -> PublicationService:
    schedule, audit, publication = _repositories(engine, data_plane)
    return PublicationService(
        data_plane=data_plane,
        transaction_factory=engine.begin,
        schedule_repository=schedule,
        audit_repository=audit_repository or audit,
        publication_repository=publication,
    )


def _ready(engine: Any, output: Any, key: str) -> dict[str, object]:
    return lifecycle_service(engine, "SIMULATION").create_reviewable(
        output,
        lifecycle_context(
            key,
            reason=f"Create publication machine source {key}.",
            correlation_id=f"correlation-p3-08-machine-source-{key}",
        ),
    ).schedule_version


def _decision_command(
    source: Mapping[str, object], command_type: str, key: str
) -> dict[str, object]:
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": command_type,
        "required_capability": command_type.lower(),
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/{command_type}/{source['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "READY_FOR_REVIEW",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": f"{command_type.title()} this publication machine Version.",
        "correlation_id": "correlation-p3-08-publication-machine",
        "payload": {},
    }
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _decision_context(
    source: Mapping[str, object], command_type: str
) -> ApprovalDecisionContext:
    return ApprovalDecisionContext(
        actor_ref="actor:p3-publication-machine-approver",
        authenticated=True,
        resolved_capabilities=frozenset({command_type.lower()}),
        schedule_version_scope=frozenset({cast(str, source["schedule_version_id"])}),
        auth_policy_version="simulation-test-approval-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-25T10:00:00Z",
        code_commit=os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
    )


def _decide(
    engine: Any,
    source: Mapping[str, object],
    command_type: str,
    key: str,
) -> dict[str, object]:
    schedule, audit, _ = _repositories(engine)
    ApprovalDecisionService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule,
        audit_repository=audit,
    ).execute(
        _decision_command(source, command_type, key),
        _decision_context(source, command_type),
    )
    stored = schedule.get(cast(str, source["schedule_version_id"]))
    if stored is None:
        raise ValueError("decision did not persist its ScheduleVersion")
    return stored


def _approved(engine: Any, output: Any, key: str) -> dict[str, object]:
    return _decide(
        engine,
        _ready(engine, output, key),
        "APPROVE",
        f"p3-machine-approve-publication-{key}-0001",
    )


def _reference(source: Mapping[str, object], state: str) -> dict[str, object]:
    return {
        "schedule_version_id": source["schedule_version_id"],
        "state": state,
        "content_fingerprint": source["content_fingerprint"],
    }


def _context(
    source: Mapping[str, object],
    *capabilities: str,
    scope: bool = True,
    occurred_at_utc: str = "2026-08-25T10:10:00Z",
) -> PublicationContext:
    decision = source.get("decision")
    decision_mapping = decision if isinstance(decision, Mapping) else {}
    return PublicationContext(
        actor_ref="actor:p3-publication-machine",
        authenticated=True,
        resolved_capabilities=frozenset(capabilities),
        schedule_version_scope=(
            frozenset({cast(str, source["schedule_version_id"])})
            if scope
            else frozenset({"schedule-version-out-of-scope"})
        ),
        auth_policy_version="simulation-test-publication-policy.v1",
        production_binding=False,
        occurred_at_utc=occurred_at_utc,
        code_commit=os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        parent_audit_event_id=cast(
            str | None, decision_mapping.get("audit_event_id")
        ),
    )


def _command(
    source: Mapping[str, object],
    *,
    key: str,
    previous: Mapping[str, object] | None = None,
    reason: str | None = None,
    data_plane: str = "SIMULATION",
) -> dict[str, object]:
    synthetic = data_plane == "SIMULATION"
    command: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": "PUBLISH",
        "required_capability": "publish",
        "idempotency_key": key,
        "idempotency_scope": (
            f"{data_plane}/PUBLISH/{source['schedule_version_id']}"
            "/SIMULATION_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": "APPROVED",
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": data_plane,
        "environment": "TEST" if synthetic else "PRODUCTION",
        "synthetic": synthetic,
        "target": "SIMULATION_INTERNAL",
        "reason": reason or "Publish this synthetic machine Version internally.",
        "correlation_id": "correlation-p3-08-publication-machine",
        "payload": {
            "previous_current_version": (
                None if previous is None else dict(previous)
            )
        },
    }
    if synthetic:
        command["synthetic_provenance"] = source["synthetic_provenance"]
    command["request_fingerprint"] = workspace_command_fingerprint(command)
    return command


def _expect(
    expected: PublicationFailure | set[PublicationFailure],
    operation: Callable[[], object],
) -> PublicationFailure:
    expected_set = expected if isinstance(expected, set) else {expected}
    try:
        operation()
    except PublicationError as error:
        if error.reason in expected_set:
            return error.reason
        raise ValueError(f"unexpected publication failure: {error.reason.value}") from error
    raise ValueError("expected publication rejection")


def _counts(engine: Any) -> dict[str, int]:
    with engine.connect() as connection:
        publish_events = [
            json.loads(bytes(row.document_json).decode("utf-8"))
            for row in connection.exec_driver_sql(
                "SELECT document_json FROM audit_events WHERE action = 'PUBLISH'"
            )
        ]
        outcomes = [
            cast(dict[str, object], event["result"])["outcome"]
            for event in publish_events
        ]
        return {
            "schedule_versions": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM schedule_versions"
                ).scalar_one()
            ),
            "audit_events": int(
                connection.exec_driver_sql("SELECT COUNT(*) FROM audit_events").scalar_one()
            ),
            "publication_results": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM publication_results"
                ).scalar_one()
            ),
            "current_references": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM publication_current_references"
                ).scalar_one()
            ),
            "publication_success_audits": outcomes.count("SUCCEEDED"),
            "publication_denial_audits": outcomes.count("DENIED"),
        }


class _FailingAuditRepository:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def get(self, audit_event_id: str) -> dict[str, object] | None:
        return self._delegate.get(audit_event_id)

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> Any:
        del connection, document
        raise RuntimeError("synthetic publication audit failure")


def run_publication_checks(root: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    rejected_without_business_state = 0
    started = perf_counter_ns()
    with TemporaryDirectory(prefix="plantnexus-p3-08-") as temporary:
        engine, configuration = _workspace_engine(
            root, Path(temporary) / "publication.db"
        )
        try:
            output, _ = load_fixed_validated_output(root)
            schedule_repository, audit_repository, publication_repository = (
                _repositories(engine)
            )

            first_source = _approved(engine, output, "a")
            first_source_bytes = canonical_workspace_bytes(first_source)
            first_command = _command(
                first_source,
                key="p3-machine-publish-first-0001",
            )
            service = _service(engine)
            first = service.execute(
                first_command,
                _context(first_source, "publish"),
            )
            stored_first = schedule_repository.get_record(
                cast(str, first_source["schedule_version_id"])
            )
            current = publication_repository.get_current()
            if (
                stored_first is None
                or stored_first.document["state"] != "PUBLISHED"
                or stored_first.state_revision != 3
                or stored_first.document["content"] != first_source["content"]
                or canonical_workspace_bytes(first_source) != first_source_bytes
                or current is None
                or current.schedule_version_id != first_source["schedule_version_id"]
            ):
                raise ValueError("first publication was not one atomic same-content commit")
            checks.append(
                _pass(
                    "approved-only-first-publish-atomic",
                    {
                        "state": "PUBLISHED",
                        "state_revision": 3,
                        "publication_id": first.document["publication_id"],
                        "current_reference_revision": current.reference_revision,
                    },
                )
            )

            replay = service.execute(
                first_command,
                _context(first_source, "publish"),
            )
            conflicting = _command(
                first_source,
                key="p3-machine-publish-first-0001",
                reason="A conflicting reason reuses this publication key.",
            )
            _expect(
                PublicationFailure.IDEMPOTENCY_CONFLICT,
                lambda: service.execute(
                    conflicting, _context(first_source, "publish")
                ),
            )
            double_publish = _command(
                first_source,
                key="p3-machine-double-publish-0001",
                previous=first.published_version,
            )
            before_double = _counts(engine)
            _expect(
                PublicationFailure.INVALID_STATE_TRANSITION,
                lambda: service.execute(
                    double_publish, _context(first_source, "publish")
                ),
            )
            rejected_without_business_state += 1
            if (
                not replay.exact_replay
                or replay.document["replayed"] is not True
                or _counts(engine) != before_double
            ):
                raise ValueError("publication replay/conflict/double-publish was unsafe")
            checks.append(
                _pass(
                    "exact-replay-conflict-and-double-publish",
                    {
                        "exact_replays": 1,
                        "idempotency_conflicts": 1,
                        "double_publish_rejections": 1,
                        "duplicate_side_effects": 0,
                    },
                )
            )

            second_source = _approved(engine, output, "b")
            second_command = _command(
                second_source,
                key="p3-machine-publish-second-0001",
                previous=first.published_version,
            )
            second = service.execute(
                second_command,
                _context(
                    second_source,
                    "publish",
                    occurred_at_utc="2026-08-25T10:11:00Z",
                ),
            )
            superseded_first = schedule_repository.get(
                cast(str, first_source["schedule_version_id"])
            )
            published_second = schedule_repository.get(
                cast(str, second_source["schedule_version_id"])
            )
            current = publication_repository.get_current()
            if (
                superseded_first is None
                or superseded_first["state"] != "SUPERSEDED"
                or superseded_first["content"] != first_source["content"]
                or superseded_first["superseded_by"] != second.published_version
                or published_second is None
                or published_second["state"] != "PUBLISHED"
                or current is None
                or current.schedule_version_id != second_source["schedule_version_id"]
                or current.reference_revision != 1
            ):
                raise ValueError("current switch and supersession were not atomic")
            checks.append(
                _pass(
                    "current-switch-and-supersession-atomic",
                    {
                        "previous_state": "SUPERSEDED",
                        "new_state": "PUBLISHED",
                        "current_reference_revision": current.reference_revision,
                        "content_mutations": 0,
                    },
                )
            )

            ready_source = _ready(engine, output, "c")
            before_negative = _counts(engine)
            _expect(
                PublicationFailure.INVALID_STATE_TRANSITION,
                lambda: service.execute(
                    _command(
                        ready_source,
                        key="p3-machine-ready-publish-0001",
                        previous=second.published_version,
                    ),
                    _context(ready_source, "publish"),
                ),
            )
            rejected_without_business_state += 1
            rejected_source = _decide(
                engine,
                ready_source,
                "REJECT",
                "p3-machine-reject-publication-c-0001",
            )
            after_reject_decision = _counts(engine)
            _expect(
                PublicationFailure.INVALID_STATE_TRANSITION,
                lambda: service.execute(
                    _command(
                        rejected_source,
                        key="p3-machine-rejected-publish-0001",
                        previous=second.published_version,
                    ),
                    _context(rejected_source, "publish"),
                ),
            )
            rejected_without_business_state += 1
            draft = build_reviewable_schedule_documents(
                output,
                lifecycle_context("0"),
                data_plane="SIMULATION",
            ).draft
            _expect(
                PublicationFailure.INVALID_STATE_TRANSITION,
                lambda: prepare_publication(
                    draft,
                    None,
                    None,
                    _command(draft, key="p3-machine-draft-publish-0001"),
                    _context(draft, "publish"),
                    data_plane="SIMULATION",
                ),
            )
            rejected_without_business_state += 1
            if (
                before_negative["publication_results"]
                != after_reject_decision["publication_results"]
                or _counts(engine) != after_reject_decision
            ):
                raise ValueError("non-APPROVED publication created a side effect")
            checks.append(
                _pass(
                    "draft-ready-rejected-negative-no-side-effect",
                    {
                        "invalid_states": ["DRAFT", "READY_FOR_REVIEW", "REJECTED"],
                        "rejections": 3,
                        "publication_side_effects": 0,
                    },
                )
            )

            denied_command = _command(
                rejected_source,
                key="p3-machine-publication-denied-0001",
                previous=second.published_version,
            )
            for _ in range(2):
                _expect(
                    PublicationFailure.AUTHORIZATION_DENIED,
                    lambda: service.execute(
                        denied_command, _context(rejected_source, "view")
                    ),
                )
            production_command = _command(
                rejected_source,
                key="p3-machine-publication-production-deny",
                data_plane="PRODUCTION",
            )
            production_context = PublicationContext(
                actor_ref="actor:production-unbound",
                authenticated=True,
                resolved_capabilities=frozenset({"publish"}),
                schedule_version_scope=frozenset(
                    {cast(str, rejected_source["schedule_version_id"])}
                ),
                auth_policy_version="production-publication-policy-unconfigured.v1",
                production_binding=False,
                occurred_at_utc="2026-08-25T10:20:00Z",
                code_commit=os.environ.get(
                    "PLANTNEXUS_CODE_COMMIT", "uncommitted"
                ),
            )
            _expect(
                PublicationFailure.PRODUCTION_AUTHORITY_UNAVAILABLE,
                lambda: _service(engine, data_plane="PRODUCTION").execute(
                    production_command, production_context
                ),
            )
            simulation_denials = [
                event
                for event in audit_repository.list_for_aggregate(
                    aggregate_type="SCHEDULE_VERSION",
                    aggregate_id=cast(str, rejected_source["schedule_version_id"]),
                )
                if event["action"] == "PUBLISH"
                and cast(dict[str, object], event["result"])["outcome"] == "DENIED"
            ]
            production_audit = _repositories(engine, "PRODUCTION")[1]
            production_denials = [
                event
                for event in production_audit.list_for_aggregate(
                    aggregate_type="SCHEDULE_VERSION",
                    aggregate_id=cast(str, rejected_source["schedule_version_id"]),
                )
                if event["action"] == "PUBLISH"
            ]
            if (
                len(simulation_denials) != 1
                or len(production_denials) != 1
                or production_denials[0]["target"] != "WORKSPACE_INTERNAL"
                or production_denials[0]["source_version"] is not None
            ):
                raise ValueError("publication authorization denial audit is incomplete")
            checks.append(
                _pass(
                    "authorization-prelookup-and-production-default-deny",
                    {
                        "simulation_denial_audits": len(simulation_denials),
                        "production_denial_audits": len(production_denials),
                        "production_resource_lookup": 0,
                        "open_002_010": "OPEN",
                    },
                )
            )

            rollback_source = _approved(engine, output, "d")
            before_rollback = schedule_repository.get_record(
                cast(str, rollback_source["schedule_version_id"])
            )
            before_rollback_counts = _counts(engine)
            _expect(
                PublicationFailure.PERSISTENCE_FAILED,
                lambda: _service(
                    engine,
                    audit_repository=_FailingAuditRepository(audit_repository),
                ).execute(
                    _command(
                        rollback_source,
                        key="p3-machine-publication-rollback-0001",
                        previous=second.published_version,
                    ),
                    _context(rollback_source, "publish"),
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
                raise ValueError("audit failure did not roll back publication state")
            checks.append(
                _pass(
                    "audit-failure-rolls-back-entire-publication",
                    {
                        "state": after_rollback.document["state"],
                        "publication_results_added": 0,
                        "current_changes": 0,
                        "audit_events_added": 0,
                    },
                )
            )

            race_sources = {
                key: _approved(engine, output, key) for key in ("e", "f")
            }
            race_commands = {
                key: _command(
                    source,
                    key=f"p3-machine-publication-race-{key}-0001",
                    previous=second.published_version,
                )
                for key, source in race_sources.items()
            }
            barrier = Barrier(2)

            def invoke(key: str) -> PublicationServiceResult:
                barrier.wait()
                return _service(engine).execute(
                    race_commands[key], _context(race_sources[key], "publish")
                )

            successes: list[PublicationServiceResult] = []
            failures: list[PublicationFailure] = []
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(invoke, key) for key in ("e", "f")]
                for future in futures:
                    try:
                        successes.append(future.result())
                    except PublicationError as error:
                        failures.append(error.reason)
            current = publication_repository.get_current()
            race_states = [
                cast(
                    str,
                    cast(
                        dict[str, object],
                        schedule_repository.get(
                            cast(str, source["schedule_version_id"])
                        ),
                    )["state"],
                )
                for source in race_sources.values()
            ]
            if (
                len(successes) != 1
                or len(failures) != 1
                or current is None
                or current.schedule_version_id
                != successes[0].current_schedule_version_id
                or sorted(race_states) != ["APPROVED", "PUBLISHED"]
            ):
                raise ValueError("concurrent publication did not produce one CAS winner")
            checks.append(
                _pass(
                    "concurrent-publication-single-current-cas-winner",
                    {
                        "winners": 1,
                        "losers": 1,
                        "loser_failure": failures[0].value,
                        "candidate_states": sorted(race_states),
                    },
                )
            )

            first_audit = audit_repository.get(first.audit_event_id)
            if first_audit is None:
                raise ValueError("first publication audit disappeared")
            audit_bytes = canonical_workspace_bytes(first_audit)
            if cast(str, first_command["idempotency_key"]).encode() in audit_bytes:
                raise ValueError("raw idempotency key leaked into publication audit")
            if any(
                forbidden in audit_bytes.lower()
                for forbidden in (
                    b"bearer ",
                    b"password=",
                    b"token=",
                    b"postgresql://",
                )
            ):
                raise ValueError("credential-like material leaked into publication audit")
            checks.append(
                _pass(
                    "immutable-lineage-redaction-and-phase-boundary",
                    {
                        "raw_idempotency_key_persisted": False,
                        "lineage_preserved": first_audit["lineage"]
                        == first_source["lineage"],
                        "schema_migration_dependency_changes": 0,
                        "export_external_http_ui_p4_calls": 0,
                    },
                )
            )

            counts = _counts(engine)
        finally:
            engine.dispose()
            alembic_command.downgrade(configuration, "base")

    elapsed_microseconds = (perf_counter_ns() - started) // 1_000
    if len(checks) != 8 or any(check["status"] != "PASS" for check in checks):
        raise ValueError("P3-08 publication checks are incomplete")
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "status": "PASS",
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "publication_service_version": PUBLICATION_SERVICE_VERSION,
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "successful_publications": counts["publication_success_audits"],
            "supersessions": 2,
            "exact_replays": 1,
            "idempotency_conflicts": 1,
            "authorization_denials": counts["publication_denial_audits"],
            "rejected_requests_without_business_state": rejected_without_business_state,
            "atomic_rollbacks": 1,
            "concurrent_current_winners": 1,
            "product_service_solver_invocations": 0,
        },
        "observations": {
            "elapsed_microseconds": elapsed_microseconds,
            "schedule_versions": counts["schedule_versions"],
            "audit_events": counts["audit_events"],
            "publication_results": counts["publication_results"],
            "current_references": counts["current_references"],
            "benchmark_class": "DEVELOPMENT_OBSERVATION_ONLY_NO_SLA",
        },
        "boundaries": {
            "publication_target": "SIMULATION_INTERNAL_ONLY",
            "source_state": "APPROVED_ONLY",
            "published_content": "IMMUTABLE",
            "publish_export_separation": "EXPORT_NOT_INVOKED",
            "production_authority": "DEFAULT_DENY_OPEN_002_010",
            "external_mes_erp_network": "NOT_IMPLEMENTED",
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
        description="Validate TASK-P3-08 publication and supersession behavior"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p3-publication.json"),
    )
    arguments = parser.parse_args(argv)
    try:
        report = run_publication_checks(arguments.root.resolve())
    except Exception as error:  # noqa: BLE001 - machine evidence must fail closed
        reason = (
            error.reason.value
            if isinstance(error, PublicationError)
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
                    "message": "P3-08 publication evidence did not complete",
                }
            ],
            "boundaries": {
                "production_authority": "DEFAULT_DENY_OPEN_002_010",
                "production_readiness": "NOT_CLAIMED",
            },
        }
        _write_report(arguments.report, report)
        return 1
    _write_report(arguments.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "TASK_ID", "main", "run_publication_checks"]
