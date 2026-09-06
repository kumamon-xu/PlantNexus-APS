"""Machine-checkable identity, authorization, audit, and overhead evidence for P8-08."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from statistics import median
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, NoReturn, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.application.host_authorization import (
    HEADLESS_OPERATION_CAPABILITIES,
    HOST_AUTHORIZATION_AUDIT_VERSION,
    HOST_AUTHORIZATION_POLICY_VERSION,
    VERIFIED_HOST_IDENTITY_VERSION,
    AuthorizedHostPrincipal,
    HostAuthorizationAdapter,
    HostAuthorizationAuditRecord,
    HostAuthorizationError,
    HostAuthorizationPolicyCatalog,
    HostAuthorizationReason,
    HostAuthorizationRequest,
    HostIdentityProvider,
    UnavailableHostAuthorizationAdapter,
    VerifiedHostIdentity,
)
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.infrastructure.host_authorization_audit_repository import (
    HostAuthorizationAuditPersistenceError,
    SqlAlchemyHostAuthorizationAuditRepository,
)


type JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-08"
DIFF_BASE = "54be7af6efdb78f751b8aa4a66bc080bdd04407f"
REPORT_VERSION = "p8-host-authorization-report.v1"
AUDIT_REPORT_VERSION = "p8-host-authorization-audit-report.v1"
BENCHMARK_VERSION = "p8-host-authorization-engineering-benchmark.v1"

_TOKEN = "synthetic-p8-host-authorization-token"
_TOKEN_REFERENCE = f"sha256:{sha256(_TOKEN.encode('utf-8')).hexdigest()}"
_SUBJECT = "subject:p8-host-authorization-check"
_ACTOR = "actor:p8-host-authorization-check"
_SCOPE = (
    "TENANT-P8-HOST-AUTHORIZATION",
    "FACTORY-P8-HOST-AUTHORIZATION",
    "PLANNING-P8-HOST-AUTHORIZATION",
)
_AUDIT_FIELDS = frozenset(
    {
        "audit_version",
        "audit_event_id",
        "occurred_at_utc",
        "operation_id",
        "required_capability",
        "outcome",
        "reason",
        "actor_ref",
        "subject_ref",
        "identity_provider_reference",
        "assertion_reference",
        "auth_policy_version",
        "auth_policy_fingerprint",
        "requested_scope",
        "scope_fingerprint",
        "resource_type",
        "resource_reference",
        "data_plane",
        "environment",
        "correlation_id",
    }
)


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


class _IdentityProvider:
    def __init__(self, identity: VerifiedHostIdentity | None = None) -> None:
        self.identity = identity or _identity()

    def verify(self, bearer_token: str) -> VerifiedHostIdentity | None:
        return self.identity if bearer_token == _TOKEN else None


class _UnavailableIdentityProvider:
    def verify(self, bearer_token: str) -> NoReturn:
        del bearer_token
        raise RuntimeError("provider diagnostic and credential must not escape")


class _RecordingAuditSink:
    def __init__(self) -> None:
        self.records: list[HostAuthorizationAuditRecord] = []

    def append(self, record: HostAuthorizationAuditRecord) -> None:
        self.records.append(record)


class _CountingAuditSink:
    def __init__(self) -> None:
        self.count = 0

    def append(self, record: HostAuthorizationAuditRecord) -> None:
        del record
        self.count += 1


class _FailingAuditSink:
    def append(self, record: HostAuthorizationAuditRecord) -> NoReturn:
        del record
        raise RuntimeError("persistence secret must not escape")


class _AuditIdentityFactory:
    def __init__(self) -> None:
        self._next = 0

    def __call__(self) -> str:
        self._next += 1
        return f"host-authz-event-{self._next:032x}"


def _identity(
    *,
    subject_ref: str = _SUBJECT,
    identity_provider_reference: str = "identity-provider:p8-host-check",
    issuer: str = "https://identity.test.invalid/p8-host-check",
    audience: str = "plantnexus-aps-p8-host-check",
    issued_at_utc: str = "2026-09-06T00:30:00Z",
    expires_at_utc: str = "2026-09-06T01:30:00Z",
) -> VerifiedHostIdentity:
    return VerifiedHostIdentity.create(
        subject_ref=subject_ref,
        identity_provider_reference=identity_provider_reference,
        issuer=issuer,
        audience=audience,
        issued_at_utc=issued_at_utc,
        expires_at_utc=expires_at_utc,
    )


def _policy(
    *,
    operations: Sequence[str] = tuple(HEADLESS_OPERATION_CAPABILITIES),
    scopes: Sequence[tuple[str, str, str]] = (_SCOPE,),
    subject_ref: str = _SUBJECT,
    revoked_subjects: Sequence[str] = (),
    revoked_assertions: Sequence[str] = (),
) -> HostAuthorizationPolicyCatalog:
    return HostAuthorizationPolicyCatalog.create(
        {
            "host_authorization_policy_version": HOST_AUTHORIZATION_POLICY_VERSION,
            "policy_id": "p8-host-authorization-check.v1",
            "identity_provider_reference": "identity-provider:p8-host-check",
            "issuer": "https://identity.test.invalid/p8-host-check",
            "audience": "plantnexus-aps-p8-host-check",
            "environment": "TEST",
            "data_plane": "SIMULATION",
            "production_binding": False,
            "max_assertion_lifetime_seconds": 3_600,
            "revoked_subject_references": list(revoked_subjects),
            "revoked_assertion_references": list(revoked_assertions),
            "principals": [
                {
                    "subject_ref": subject_ref,
                    "actor_ref": _ACTOR,
                    "operations": list(operations),
                    "scopes": [
                        {
                            "tenant_id": tenant_id,
                            "factory_id": factory_id,
                            "planning_scope_id": planning_scope_id,
                        }
                        for tenant_id, factory_id, planning_scope_id in scopes
                    ],
                }
            ],
        }
    )


def _request(
    operation_id: str,
    *,
    scope: tuple[str, str, str] = _SCOPE,
    resource_id: str = "planning-run-p8-host-check",
) -> HostAuthorizationRequest:
    return HostAuthorizationRequest.create(
        operation_id=operation_id,
        tenant_id=scope[0],
        factory_id=scope[1],
        planning_scope_id=scope[2],
        resource_type="PLANNING_RUN",
        resource_id=resource_id,
        correlation_id=f"CORRELATION-P8-HOST-{operation_id}",
        occurred_at_utc="2026-09-06T01:00:00Z",
    )


def _adapter(
    *,
    sink: _RecordingAuditSink,
    identity_factory: _AuditIdentityFactory,
    provider: HostIdentityProvider | None = None,
    policy: HostAuthorizationPolicyCatalog | None = None,
) -> HostAuthorizationAdapter:
    return HostAuthorizationAdapter(
        provider=provider or _IdentityProvider(),
        policy=policy or _policy(),
        audit_sink=sink,
        environment="TEST",
        data_plane="SIMULATION",
        simulation_api_enabled=True,
        audit_id_factory=identity_factory,
    )


def _denial_reason(
    adapter: HostAuthorizationAdapter | UnavailableHostAuthorizationAdapter,
    header: str | None,
    request: HostAuthorizationRequest,
) -> HostAuthorizationReason | None:
    try:
        adapter.authorize(header, request)
    except HostAuthorizationError as error:
        return error.reason
    return None


def _router_authorization_coverage(root: Path) -> bool:
    tree = ast.parse(
        (root / "backend/app/api/routers/headless_planning_runs.py").read_text(
            encoding="utf-8"
        )
    )
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    create = functions.get("create_headless_planning_run")
    context = functions.get("_command_context")
    if create is None or context is None:
        return False

    def call_lines(function: ast.AST, name: str) -> list[int]:
        return [
            node.lineno
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        ]

    create_auth = call_lines(create, "authorize_headless_request")
    create_ports = call_lines(create, "_ports")
    context_auth = call_lines(context, "authorize_headless_request")
    context_ports = call_lines(context, "_ports")
    if not (
        len(create_auth) == len(create_ports) == 1
        and len(context_auth) == len(context_ports) == 1
        and create_auth[0] < create_ports[0]
        and context_auth[0] < context_ports[0]
    ):
        return False

    routed_operations: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if (
                keyword.arg == "operation_id"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
                and keyword.value.value in HEADLESS_OPERATION_CAPABILITIES
            ):
                routed_operations.add(keyword.value.value)
    return routed_operations == set(HEADLESS_OPERATION_CAPABILITIES)


def _migration_evidence(root: Path, record: HostAuthorizationAuditRecord) -> JsonObject:
    result: JsonObject = {
        "upgrade_created_table": False,
        "exact_replay_idempotent": False,
        "update_rejected": False,
        "delete_rejected": False,
        "data_plane_isolated": False,
        "downgrade_removed_only_p8_08_table": False,
        "reupgrade_empty": False,
    }
    with TemporaryDirectory(prefix="p8-host-authorization-") as temporary:
        database_path = Path(temporary) / "audit.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        configuration = Config(str(root / "alembic.ini"))
        configuration.set_main_option(
            "script_location", str(root / "backend" / "migrations")
        )
        configuration.set_main_option(
            "sqlalchemy.url", database_url.replace("%", "%%")
        )
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            tables = set(inspect(engine).get_table_names())
            result["upgrade_created_table"] = (
                "headless_authorization_audit_records" in tables
            )
            repository = SqlAlchemyHostAuthorizationAuditRepository(
                engine, data_plane="SIMULATION"
            )
            repository.append(record)
            repository.append(record)
            result["exact_replay_idempotent"] = repository.count() == 1
            production = SqlAlchemyHostAuthorizationAuditRepository(
                engine, data_plane="PRODUCTION"
            )
            result["data_plane_isolated"] = production.get(
                cast(str, record.document["audit_event_id"])
            ) is None
            try:
                production.append(record)
            except HostAuthorizationAuditPersistenceError:
                result["data_plane_isolated"] = bool(result["data_plane_isolated"])
            else:
                result["data_plane_isolated"] = False
            for action in ("UPDATE", "DELETE"):
                try:
                    with engine.begin() as connection:
                        if action == "UPDATE":
                            connection.execute(
                                text(
                                    "UPDATE headless_authorization_audit_records "
                                    "SET outcome = 'DENIED'"
                                )
                            )
                        else:
                            connection.execute(
                                text("DELETE FROM headless_authorization_audit_records")
                            )
                except SQLAlchemyError:
                    result[f"{action.lower()}_rejected"] = True
            preexisting = tables - {"headless_authorization_audit_records"}
        finally:
            engine.dispose()

        try:
            command.downgrade(configuration, "0008_planning_run_solver_worker")
            downgraded = create_engine(database_url)
            try:
                downgraded_tables = set(inspect(downgraded).get_table_names())
                result["downgrade_removed_only_p8_08_table"] = (
                    "headless_authorization_audit_records" not in downgraded_tables
                    and preexisting <= downgraded_tables
                )
            finally:
                downgraded.dispose()
            command.upgrade(configuration, "head")
            upgraded = create_engine(database_url)
            try:
                repository = SqlAlchemyHostAuthorizationAuditRepository(
                    upgraded, data_plane="SIMULATION"
                )
                result["reupgrade_empty"] = repository.count() == 0
            finally:
                upgraded.dispose()
        finally:
            command.downgrade(configuration, "base")
    return result


def _benchmark() -> JsonObject:
    iterations = 1_000
    sink = _CountingAuditSink()
    adapter = HostAuthorizationAdapter(
        provider=_IdentityProvider(),
        policy=_policy(),
        audit_sink=sink,
        environment="TEST",
        data_plane="SIMULATION",
        simulation_api_enabled=True,
        audit_id_factory=lambda: f"host-authz-event-{'f' * 32}",
    )
    request = _request("getHeadlessPlanningRunStatus")
    elapsed: list[float] = []
    passed = True
    for _ in range(iterations):
        started = perf_counter()
        try:
            principal = adapter.authorize(f"Bearer {_TOKEN}", request)
            passed = passed and principal.application_capability == "view"
        except HostAuthorizationError:
            passed = False
        elapsed.append((perf_counter() - started) * 1_000)
    ordered = sorted(elapsed)
    p95_index = max(0, int(iterations * 0.95) - 1)
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "task_id": TASK_ID,
        "profile": "SYNTHETIC_ENGINEERING_NOT_PRODUCTION_SLA",
        "iterations": iterations,
        "threshold_ms": None,
        "median_elapsed_ms": round(median(elapsed), 6),
        "p95_elapsed_ms": round(ordered[p95_index], 6),
        "decision_count": sink.count,
        "all_decisions_allowed_and_audited": passed and sink.count == iterations,
        "status": "PASS" if passed and sink.count == iterations else "FAIL",
    }


def run_checks(root: Path) -> tuple[JsonObject, JsonObject, JsonObject]:
    sink = _RecordingAuditSink()
    identity_factory = _AuditIdentityFactory()
    adapter = _adapter(sink=sink, identity_factory=identity_factory)
    operation_matrix: list[JsonObject] = []
    principals: list[AuthorizedHostPrincipal] = []
    for operation_id, capability in HEADLESS_OPERATION_CAPABILITIES.items():
        principal = adapter.authorize(f"Bearer {_TOKEN}", _request(operation_id))
        principals.append(principal)
        operation_matrix.append(
            {
                "operation_id": operation_id,
                "required_capability": capability,
                "derived_capability": principal.application_capability,
                "outcome": "ALLOWED",
            }
        )

    denial_matrix: list[JsonObject] = []

    def add_denial(
        check_id: str,
        expected: HostAuthorizationReason,
        *,
        header: str | None = f"Bearer {_TOKEN}",
        request: HostAuthorizationRequest | None = None,
        provider: HostIdentityProvider | None = None,
        policy: HostAuthorizationPolicyCatalog | None = None,
    ) -> None:
        denied = _adapter(
            sink=sink,
            identity_factory=identity_factory,
            provider=provider,
            policy=policy,
        )
        observed = _denial_reason(
            denied,
            header,
            request or _request("getHeadlessPlanningRunStatus"),
        )
        denial_matrix.append(
            {
                "check_id": check_id,
                "expected_reason": expected.value,
                "observed_reason": observed.value if observed is not None else None,
                "passed": observed is expected,
            }
        )

    add_denial(
        "missing-identity",
        HostAuthorizationReason.AUTHENTICATION_REQUIRED,
        header=None,
    )
    add_denial(
        "malformed-bearer",
        HostAuthorizationReason.INVALID_AUTHENTICATION,
        header=f"Bearer {_TOKEN} with-whitespace",
    )
    add_denial(
        "forged-bearer",
        HostAuthorizationReason.INVALID_AUTHENTICATION,
        header="Bearer forged-token",
    )
    add_denial(
        "provider-unavailable",
        HostAuthorizationReason.IDENTITY_PROVIDER_UNAVAILABLE,
        provider=_UnavailableIdentityProvider(),
    )
    add_denial(
        "issuer-mismatch",
        HostAuthorizationReason.ISSUER_MISMATCH,
        provider=_IdentityProvider(_identity(issuer="https://issuer.invalid/untrusted")),
    )
    add_denial(
        "audience-mismatch",
        HostAuthorizationReason.AUDIENCE_MISMATCH,
        provider=_IdentityProvider(_identity(audience="another-service")),
    )
    add_denial(
        "expired-assertion",
        HostAuthorizationReason.ASSERTION_EXPIRED,
        provider=_IdentityProvider(
            _identity(
                issued_at_utc="2026-09-06T00:00:00Z",
                expires_at_utc="2026-09-06T01:00:00Z",
            )
        ),
    )
    add_denial(
        "revoked-assertion",
        HostAuthorizationReason.ASSERTION_REVOKED,
        policy=_policy(revoked_assertions=(_TOKEN_REFERENCE,)),
    )
    add_denial(
        "revoked-subject",
        HostAuthorizationReason.SUBJECT_REVOKED,
        policy=_policy(revoked_subjects=(_SUBJECT,)),
    )
    add_denial(
        "unmapped-subject",
        HostAuthorizationReason.SUBJECT_UNMAPPED,
        provider=_IdentityProvider(_identity(subject_ref="subject:unmapped")),
    )
    add_denial(
        "operation-denied",
        HostAuthorizationReason.OPERATION_DENIED,
        policy=_policy(operations=("createHeadlessPlanningRun",)),
    )
    for index, scope in enumerate(
        (
            ("TENANT-OTHER", _SCOPE[1], _SCOPE[2]),
            (_SCOPE[0], "FACTORY-OTHER", _SCOPE[2]),
            (_SCOPE[0], _SCOPE[1], "PLANNING-OTHER"),
        )
    ):
        add_denial(
            f"composite-scope-dimension-{index + 1}",
            HostAuthorizationReason.FACTORY_SCOPE_DENIED,
            request=_request("getHeadlessPlanningRunStatus", scope=scope),
        )

    unavailable_sink = _RecordingAuditSink()
    production = UnavailableHostAuthorizationAdapter(
        audit_sink=unavailable_sink,
        environment="PRODUCTION",
        data_plane="PRODUCTION",
        audit_id_factory=identity_factory,
    )
    production_reason = _denial_reason(
        production,
        f"Bearer {_TOKEN}",
        _request("getHeadlessPlanningRunStatus"),
    )
    sink.records.extend(unavailable_sink.records)

    failure = HostAuthorizationAdapter(
        provider=_IdentityProvider(),
        policy=_policy(),
        audit_sink=_FailingAuditSink(),
        environment="TEST",
        data_plane="SIMULATION",
        simulation_api_enabled=True,
        audit_id_factory=identity_factory,
    )
    audit_failure_reason = _denial_reason(
        failure,
        f"Bearer {_TOKEN}",
        _request("createHeadlessPlanningRun"),
    )

    stable_policy = _policy(
        operations=tuple(reversed(tuple(HEADLESS_OPERATION_CAPABILITIES)))
    )
    policy_deterministic = stable_policy.canonical_bytes == _policy().canonical_bytes
    wildcard_rejected = False
    try:
        _policy(scopes=((_SCOPE[0], "*", _SCOPE[2]),))
    except ValueError:
        wildcard_rejected = True

    audit_documents = [record.document for record in sink.records]
    audit_bytes = b"\n".join(record.canonical_bytes for record in sink.records)
    audit_complete = all(set(document) == _AUDIT_FIELDS for document in audit_documents)
    audit_versions = {
        cast(str, document["audit_version"]) for document in audit_documents
    }
    raw_values_absent = all(
        value not in audit_bytes
        for value in (
            _TOKEN.encode(),
            b"forged-token",
            b"provider diagnostic",
            b"persistence secret",
            b"planning-run-p8-host-check",
        )
    )
    allowed_records = [
        document for document in audit_documents if document["outcome"] == "ALLOWED"
    ]
    denied_records = [
        document for document in audit_documents if document["outcome"] == "DENIED"
    ]
    reference_binding = all(
        document["assertion_reference"] == _TOKEN_REFERENCE
        for document in allowed_records
    )
    migration = _migration_evidence(root, sink.records[0])
    migration_passed = all(value is True for value in migration.values())

    checks = [
        {
            "check_id": "provider-neutral-verified-identity-contract",
            "passed": all(
                principal.subject_reference == _SUBJECT
                and principal.actor_reference == _ACTOR
                and principal.production_binding is False
                for principal in principals
            ),
        },
        {
            "check_id": "five-operation-server-derived-capability-matrix",
            "passed": len(operation_matrix) == 5
            and all(
                row["required_capability"] == row["derived_capability"]
                for row in operation_matrix
            ),
        },
        {
            "check_id": "router-authorizes-before-application-lookup",
            "passed": _router_authorization_coverage(root),
        },
        {
            "check_id": "strict-deterministic-server-policy",
            "passed": policy_deterministic and wildcard_rejected,
        },
        {
            "check_id": "identity-and-provider-failure-matrix",
            "passed": all(row["passed"] for row in denial_matrix[:10]),
        },
        {
            "check_id": "operation-and-composite-scope-default-deny",
            "passed": all(row["passed"] for row in denial_matrix[10:]),
        },
        {
            "check_id": "production-authority-default-deny",
            "passed": production_reason
            is HostAuthorizationReason.PRODUCTION_AUTHORITY_UNAVAILABLE,
        },
        {
            "check_id": "audit-failure-blocks-authorization",
            "passed": audit_failure_reason
            is HostAuthorizationReason.AUDIT_PERSISTENCE_FAILED,
        },
        {
            "check_id": "complete-sanitized-decision-carrier",
            "passed": audit_complete
            and audit_versions == {HOST_AUTHORIZATION_AUDIT_VERSION}
            and raw_values_absent
            and reference_binding,
        },
        {
            "check_id": "durable-append-only-migration-and-plane-isolation",
            "passed": migration_passed,
        },
    ]
    issues = [cast(str, row["check_id"]) for row in checks if not row["passed"]]
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "code_commit": _git_head(root),
        "diff_base": DIFF_BASE,
        "validation_profile": "HIGH_RISK",
        "identity_contract_version": VERIFIED_HOST_IDENTITY_VERSION,
        "policy_contract_version": HOST_AUTHORIZATION_POLICY_VERSION,
        "operation_matrix": operation_matrix,
        "denial_matrix": denial_matrix,
        "checks": checks,
        "check_count": len(checks),
        "issues": issues,
        "production_boundary": (
            "TEST_PROVIDER_ONLY_PRODUCTION_IDENTITY_AND_AUTHORITY_REMAIN_OPEN"
        ),
        "status": "PASS" if not issues else "FAIL",
    }
    audit_report: JsonObject = {
        "audit_report_version": AUDIT_REPORT_VERSION,
        "task_id": TASK_ID,
        "audit_contract_version": HOST_AUTHORIZATION_AUDIT_VERSION,
        "decision_count": len(audit_documents),
        "allowed_count": len(allowed_records),
        "denied_count": len(denied_records),
        "required_fields": sorted(_AUDIT_FIELDS),
        "redaction": {
            "raw_bearer_absent": _TOKEN.encode() not in audit_bytes,
            "forged_bearer_absent": b"forged-token" not in audit_bytes,
            "provider_diagnostic_absent": b"provider diagnostic" not in audit_bytes,
            "raw_resource_id_absent": b"planning-run-p8-host-check" not in audit_bytes,
            "assertion_hash_reference_present": reference_binding,
        },
        "persistence": migration,
        "issues": [] if audit_complete and raw_values_absent and migration_passed else [
            "audit-completeness-redaction-or-persistence"
        ],
        "status": (
            "PASS"
            if audit_complete and raw_values_absent and migration_passed
            else "FAIL"
        ),
    }
    benchmark = _benchmark()
    return report, audit_report, benchmark


def _write(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document) + b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    report, audit_report, benchmark = run_checks(root)
    _write(arguments.report, report)
    _write(arguments.audit_report, audit_report)
    _write(arguments.benchmark_report, benchmark)
    print(
        f"{report['status']} {TASK_ID}: checks={report['check_count']} "
        f"decisions={audit_report['decision_count']} issues={len(report['issues'])}"
    )
    return (
        0
        if report["status"] == audit_report["status"] == benchmark["status"] == "PASS"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AUDIT_REPORT_VERSION",
    "BENCHMARK_VERSION",
    "DIFF_BASE",
    "REPORT_VERSION",
    "TASK_ID",
    "main",
    "run_checks",
]
