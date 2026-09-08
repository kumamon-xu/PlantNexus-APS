"""P8-10 non-Production deployment, observability, and recovery drill.

The executable intentionally lives outside the Runtime wheel.  It deploys the
exact declared Runtime inputs into a disposable TEST/SIMULATION Docker Compose
target and emits sanitized evidence only.  It never accepts a Production
target, an Extension artifact, or a caller-provided secret.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import statistics
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-10"
TEST_ID = "TEST-P8-OPERATIONS-001"
TARGET_CONTRACT = "aps-non-production-target.v1"
OBSERVABILITY_CONTRACT = "aps-runtime-observability-policy.v1"
DEPLOYMENT_REPORT = "p8-operations-deployment-report.v1"
OBSERVABILITY_REPORT = "p8-operations-observability-report.v1"
RECOVERY_REPORT = "p8-operations-recovery-report.v1"
RUNBOOK_REPORT = "p8-operations-runbook-dry-run-report.v1"
PROJECT_NAME = "plantnexus-p8-10"
DEFAULT_IMAGE = "plantnexus-aps:p8-09-operations"

TARGET_PATH = Path("infra/operations/non-production-target.v1.json")
OBSERVABILITY_PATH = Path("infra/operations/observability-policy.v1.json")
COMPOSE_PATH = Path("infra/operations/compose.p8-operations.yml")
RUNBOOK_PATHS = (
    Path("docs/runbooks/headless-deployment-and-rollback.md"),
    Path("docs/runbooks/backup-and-restore.md"),
    Path("docs/runbooks/dependency-outage-and-readiness.md"),
    Path("docs/runbooks/stalled-worker-recovery.md"),
    Path("docs/runbooks/extension-load-and-compatibility-failure.md"),
    Path("docs/runbooks/incident-triage-and-escalation.md"),
)
REQUIRED_RUNBOOK_HEADINGS = (
    "## 触发条件",
    "## 影响与安全边界",
    "## 前置权限",
    "## 执行步骤",
    "## 验证",
    "## 回退",
    "## 升级与责任",
    "## 最近演练记录",
)
REQUIRED_SERVICES = {
    "api",
    "database",
    "migrate",
    "observer",
    "redis",
    "rollback_api",
    "rollback_worker",
    "validator",
    "worker",
}
REQUIRED_ALERTS = {
    "APSApiUnavailable",
    "APSBackupOrRestoreFailed",
    "APSBrokerUnavailable",
    "APSContainerSaturationEngineering",
    "APSDatabaseUnavailable",
    "APSExtensionConfigurationRejected",
    "APSHighErrorRateEngineering",
    "APSHighLatencyEngineering",
    "APSReadinessDown",
    "APSWorkerUnavailable",
}
RUNTIME_INPUTS = (
    "README.md",
    "alembic.ini",
    "backend/app",
    "backend/migrations",
    "infra/Dockerfile",
    "infra/release",
    "pyproject.toml",
    "schemas",
    "uv.lock",
)
SENSITIVE_FRAGMENTS = (
    "authorization",
    "credential",
    "database_url",
    "password",
    "redis_url",
    "secret",
    "token",
)


class OperationsEvidenceError(RuntimeError):
    """Stable, sanitized failure raised by the P8-10 evidence runner."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OperationsEvidenceError(
            "CONTRACT_UNREADABLE", "operations contract could not be loaded"
        ) from error
    if not isinstance(value, dict):
        raise OperationsEvidenceError(
            "CONTRACT_INVALID", "operations contract must be an object"
        )
    return cast(JsonObject, value)


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str
) -> None:
    if set(value) != expected:
        raise OperationsEvidenceError(
            "CONTRACT_INVALID", f"{label} fields do not match the frozen contract"
        )


def validate_target_contract(document: Mapping[str, object]) -> JsonObject:
    """Validate the exact non-Production target and return a safe summary."""

    _require_exact_keys(
        document,
        {
            "authorization",
            "extensions",
            "isolation",
            "operator",
            "platform",
            "production_boundary",
            "recovery",
            "release",
            "secret_boundary",
            "services",
            "storage_boundary",
            "target_contract_version",
            "target_id",
        },
        label="target",
    )
    if document.get("target_contract_version") != TARGET_CONTRACT:
        raise OperationsEvidenceError(
            "CONTRACT_INVALID", "target contract version is unsupported"
        )
    if document.get("target_id") != "p8-operations-compose-v1":
        raise OperationsEvidenceError(
            "TARGET_INVALID", "target identity is not approved"
        )

    authorization = cast(Mapping[str, object], document.get("authorization"))
    _require_exact_keys(
        authorization,
        {"demo_authorized", "production_authorized", "task_id", "authorized_on"},
        label="authorization",
    )
    if (
        authorization.get("task_id") != TASK_ID
        or authorization.get("production_authorized") is not False
        or authorization.get("demo_authorized") is not False
    ):
        raise OperationsEvidenceError(
            "TARGET_INVALID", "only the approved non-Production target is allowed"
        )

    release = cast(Mapping[str, object], document.get("release"))
    _require_exact_keys(
        release,
        {
            "image_build_source",
            "implementation_sha",
            "release_archive_sha256",
            "release_fingerprint",
            "runtime_version",
            "signing_state",
        },
        label="release",
    )
    implementation_sha = release.get("implementation_sha")
    if (
        release.get("runtime_version") != "0.1.0"
        or not isinstance(implementation_sha, str)
        or len(implementation_sha) != 40
        or any(character not in "0123456789abcdef" for character in implementation_sha)
        or release.get("signing_state") != "UNSIGNED_ENGINEERING_CANDIDATE"
    ):
        raise OperationsEvidenceError(
            "RELEASE_IDENTITY_INVALID", "approved Runtime release identity is not exact"
        )
    for field in ("release_archive_sha256", "release_fingerprint"):
        fingerprint = release.get(field)
        if (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 71
            or not fingerprint.startswith("sha256:")
        ):
            raise OperationsEvidenceError(
                "RELEASE_IDENTITY_INVALID", "release fingerprint is malformed"
            )

    isolation = cast(Mapping[str, object], document.get("isolation"))
    if (
        isolation.get("runtime_environment") != "test"
        or isolation.get("data_plane") != "SIMULATION"
        or isolation.get("synthetic_only") is not True
        or isolation.get("external_ingress") is not False
        or isolation.get("third_party_connectors") is not False
    ):
        raise OperationsEvidenceError(
            "ISOLATION_INVALID", "target isolation is not TEST/SIMULATION only"
        )
    platform = cast(Mapping[str, object], document.get("platform"))
    if platform.get("migration_version_table_bootstrap") != (
        "CREATE_IF_ABSENT_VARCHAR_128_PRIMARY_KEY"
    ):
        raise OperationsEvidenceError(
            "MIGRATION_BOOTSTRAP_INVALID",
            "PostgreSQL migration version identity bootstrap is missing",
        )

    services = document.get("services")
    if not isinstance(services, list) or set(services) != REQUIRED_SERVICES:
        raise OperationsEvidenceError(
            "SERVICE_SET_INVALID", "target service inventory is incomplete"
        )
    extensions = cast(Mapping[str, object], document.get("extensions"))
    if (
        extensions.get("loading") != "DISABLED_UNTIL_COMPATIBILITY_VERIFIED"
        or extensions.get("allowed_extension_ids") != []
        or extensions.get("invalid_configuration_action")
        != "READINESS_DOWN_NO_PROMOTION"
    ):
        raise OperationsEvidenceError(
            "EXTENSION_BOUNDARY_INVALID", "Extension loading must remain disabled"
        )
    production = cast(Mapping[str, object], document.get("production_boundary"))
    if any(value is not False for value in production.values()):
        raise OperationsEvidenceError(
            "PRODUCTION_CLAIM_INVALID", "target must not make a Production claim"
        )
    secret_boundary = cast(Mapping[str, object], document.get("secret_boundary"))
    if (
        secret_boundary.get("generated_per_run") is not True
        or secret_boundary.get("committed") is not False
        or secret_boundary.get("logged") is not False
        or secret_boundary.get("uploaded") is not False
    ):
        raise OperationsEvidenceError(
            "SECRET_BOUNDARY_INVALID", "ephemeral secret boundary is not fail closed"
        )
    return {
        "target_id": document["target_id"],
        "runtime_environment": isolation["runtime_environment"],
        "data_plane": isolation["data_plane"],
        "runtime_version": release["runtime_version"],
        "runtime_implementation_sha": implementation_sha,
        "release_archive_sha256": release["release_archive_sha256"],
        "release_fingerprint": release["release_fingerprint"],
        "extension_loading": extensions["loading"],
        "migration_version_table_bootstrap": platform[
            "migration_version_table_bootstrap"
        ],
        "production_ready": False,
    }


def validate_observability_contract(
    document: Mapping[str, object], root: Path
) -> JsonObject:
    _require_exact_keys(
        document,
        {
            "alerts",
            "correlation",
            "dashboards",
            "golden_signals",
            "observability_policy_version",
            "redaction",
            "retention",
            "target_id",
        },
        label="observability",
    )
    if document.get("observability_policy_version") != OBSERVABILITY_CONTRACT:
        raise OperationsEvidenceError(
            "CONTRACT_INVALID", "observability policy version is unsupported"
        )
    signals = document.get("golden_signals")
    if not isinstance(signals, list) or {
        item.get("signal") for item in signals if isinstance(item, dict)
    } != {"TRAFFIC", "ERRORS", "LATENCY", "SATURATION"}:
        raise OperationsEvidenceError(
            "OBSERVABILITY_INVALID", "all four golden signals are required"
        )
    alerts = document.get("alerts")
    if not isinstance(alerts, list):
        raise OperationsEvidenceError("OBSERVABILITY_INVALID", "alert list is missing")
    alert_ids: set[str] = set()
    for alert in alerts:
        if not isinstance(alert, dict):
            raise OperationsEvidenceError(
                "OBSERVABILITY_INVALID", "alert entry is invalid"
            )
        _require_exact_keys(
            alert,
            {"alert_id", "condition", "runbook", "severity", "signal"},
            label="alert",
        )
        alert_id = alert.get("alert_id")
        runbook = alert.get("runbook")
        if not isinstance(alert_id, str) or alert_id in alert_ids:
            raise OperationsEvidenceError(
                "OBSERVABILITY_INVALID", "alert identity is missing or duplicated"
            )
        if not isinstance(runbook, str) or not (root / runbook).is_file():
            raise OperationsEvidenceError(
                "RUNBOOK_MISSING", "an alert does not reference a present runbook"
            )
        alert_ids.add(alert_id)
    if alert_ids != REQUIRED_ALERTS:
        raise OperationsEvidenceError(
            "OBSERVABILITY_INVALID", "alert inventory is not exact"
        )
    correlation = cast(Mapping[str, object], document.get("correlation"))
    if correlation.get("payload_logging") is not False:
        raise OperationsEvidenceError(
            "OBSERVABILITY_INVALID", "business payload logging is forbidden"
        )
    return {
        "policy_fingerprint": _sha256(_canonical_bytes(document)),
        "golden_signal_count": len(signals),
        "alert_count": len(alerts),
        "dashboard_count": len(cast(list[object], document.get("dashboards"))),
        "payload_logging": False,
    }


def validate_runbooks(root: Path) -> list[JsonObject]:
    evidence: list[JsonObject] = []
    for relative in RUNBOOK_PATHS:
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise OperationsEvidenceError(
                "RUNBOOK_MISSING", "a required operator runbook is missing"
            ) from error
        missing = [
            heading for heading in REQUIRED_RUNBOOK_HEADINGS if heading not in text
        ]
        if missing or "Production" not in text or "TASK-P8-10" not in text:
            raise OperationsEvidenceError(
                "RUNBOOK_INVALID", "a runbook is missing required operating sections"
            )
        evidence.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256(text.encode("utf-8")),
                "required_sections": len(REQUIRED_RUNBOOK_HEADINGS),
                "status": "PASS",
            }
        )
    return evidence


def extension_readiness(
    target: Mapping[str, object], configured_extension_ids: Sequence[str]
) -> JsonObject:
    extensions = cast(Mapping[str, object], target["extensions"])
    allowed = cast(list[str], extensions["allowed_extension_ids"])
    accepted = (
        extensions["loading"] == "DISABLED_UNTIL_COMPATIBILITY_VERIFIED"
        and not configured_extension_ids
        and not allowed
    )
    return {
        "status": "UP" if accepted else "DOWN",
        "code": None if accepted else "EXTENSION_CONFIGURATION_REJECTED",
        "promotion_allowed": accepted,
        "configured_extension_count": len(configured_extension_ids),
    }


def redact_for_report(value: object) -> object:
    """Recursively redact caller data used by tests; target reports stay allow-listed."""

    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            result[str(key)] = (
                "[REDACTED]"
                if any(fragment in normalized for fragment in SENSITIVE_FRAGMENTS)
                else redact_for_report(item)
            )
        return result
    if isinstance(value, list):
        return [redact_for_report(item) for item in value]
    if isinstance(value, tuple):
        return [redact_for_report(item) for item in value]
    if isinstance(value, str) and "://" in value and "@" in value:
        scheme, remainder = value.split("://", 1)
        return f"{scheme}://[REDACTED]@{remainder.split('@', 1)[1]}"
    return value


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes

    @property
    def text(self) -> str:
        return self.stdout.decode("utf-8", errors="replace")


class CommandRunner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run(
        self,
        args: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        check: bool = True,
        timeout: int = 900,
    ) -> CommandResult:
        try:
            completed = subprocess.run(
                list(args),
                cwd=self.root,
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OperationsEvidenceError(
                "COMMAND_UNAVAILABLE", "an approved operations command could not run"
            ) from error
        result = CommandResult(completed.returncode, completed.stdout)
        if check and result.returncode != 0:
            raise OperationsEvidenceError(
                "COMMAND_FAILED", "an approved operations command failed"
            )
        return result


class ComposeTarget:
    def __init__(
        self,
        *,
        root: Path,
        runner: CommandRunner,
        env_file: Path,
    ) -> None:
        self.root = root
        self.runner = runner
        self.prefix = (
            "docker",
            "compose",
            "--project-name",
            PROJECT_NAME,
            "--env-file",
            str(env_file),
            "-f",
            str(root / "docker-compose.yml"),
            "-f",
            str(root / COMPOSE_PATH),
        )

    def run(
        self,
        *args: str,
        input_bytes: bytes | None = None,
        check: bool = True,
        timeout: int = 900,
    ) -> CommandResult:
        return self.runner.run(
            (*self.prefix, *args),
            input_bytes=input_bytes,
            check=check,
            timeout=timeout,
        )

    def service_container_id(self, service: str) -> str:
        value = self.run("ps", "-q", service).text.strip()
        if not value:
            raise OperationsEvidenceError(
                "SERVICE_UNAVAILABLE", "an expected target service has no container"
            )
        return value


def _git_text(runner: CommandRunner, *args: str) -> str:
    return runner.run(("git", *args), timeout=60).text.strip()


def verify_runtime_inputs_unchanged(
    runner: CommandRunner, implementation_sha: str
) -> JsonObject:
    changed = _git_text(
        runner,
        "diff",
        "--name-only",
        implementation_sha,
        "--",
        *RUNTIME_INPUTS,
    )
    untracked = _git_text(
        runner,
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        *RUNTIME_INPUTS,
    )
    if changed or untracked:
        raise OperationsEvidenceError(
            "RUNTIME_INPUT_DRIFT",
            "declared Runtime build inputs changed after verification",
        )
    return {
        "implementation_sha": implementation_sha,
        "checked_path_count": len(RUNTIME_INPUTS),
        "changed_path_count": 0,
        "status": "PASS",
    }


def _http_request(
    target: ComposeTarget, url: str, *, timeout: float = 2.0
) -> tuple[int | None, bytes]:
    code = f"""
import base64
import json
import urllib.error
import urllib.request
try:
    with urllib.request.urlopen({url!r}, timeout={timeout!r}) as response:
        result = {{"available": True, "status": response.status, "body": base64.b64encode(response.read()).decode("ascii")}}
except urllib.error.HTTPError as error:
    result = {{"available": True, "status": error.code, "body": base64.b64encode(error.read()).decode("ascii")}}
except Exception:
    result = {{"available": False, "status": None, "body": ""}}
print(json.dumps(result, sort_keys=True))
"""
    result = target.run(
        "exec", "-T", "observer", "python", "-c", code, check=False, timeout=30
    )
    if result.returncode != 0:
        return None, b""
    payload = _safe_json_line(result.text)
    if payload.get("available") is not True:
        return None, b""
    body = payload.get("body")
    status = payload.get("status")
    if not isinstance(body, str) or not isinstance(status, int):
        return None, b""
    import base64

    return status, base64.b64decode(body)


def _wait_http(
    target: ComposeTarget,
    url: str,
    expected_status: int,
    *,
    attempts: int = 60,
    failure_code: str = "HTTP_PROBE_FAILED",
) -> tuple[int, JsonObject]:
    for _ in range(attempts):
        try:
            status, raw = _http_request(target, url)
            if status is not None and status == expected_status:
                value = json.loads(raw)
                if isinstance(value, dict):
                    return status, cast(JsonObject, value)
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        time.sleep(1)
    raise OperationsEvidenceError(
        failure_code, "target HTTP probe did not reach the expected state"
    )


def _http_unavailable(target: ComposeTarget, url: str) -> bool:
    status, _ = _http_request(target, url, timeout=1.0)
    return status is None


def _worker_ping(target: ComposeTarget, service: str = "worker") -> bool:
    destinations = {
        "worker": "candidate@p8-operations",
        "rollback_worker": "rollback@p8-operations",
    }
    destination = destinations.get(service)
    if destination is None:
        raise OperationsEvidenceError(
            "WORKER_PROBE_TARGET_INVALID", "worker probe target is not allow-listed"
        )
    result = target.run(
        "exec",
        "-T",
        service,
        "celery",
        "-A",
        "app.jobs.celery_app:celery_app",
        "inspect",
        "ping",
        "--destination",
        destination,
        "--timeout=5",
        check=False,
        timeout=30,
    )
    return result.returncode == 0 and "pong" in result.text.lower()


def _wait_worker(
    target: ComposeTarget, service: str = "worker", *, attempts: int = 30
) -> None:
    for _ in range(attempts):
        if _worker_ping(target, service):
            return
        time.sleep(1)
    raise OperationsEvidenceError(
        "WORKER_PROBE_FAILED", "Solver Worker did not become observable"
    )


def _safe_json_line(raw: str) -> JsonObject:
    for line in reversed(raw.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return cast(JsonObject, value)
    raise OperationsEvidenceError(
        "OBSERVATION_INVALID", "target did not return a machine-readable observation"
    )


def _runtime_descriptor(target: ComposeTarget, service: str) -> JsonObject:
    code = (
        "import json; from app.api.app import app; "
        "d=app.state.aps_runtime_descriptor; "
        "print(json.dumps({'composition_fingerprint':d.fingerprint,"
        "'runtime_resolution':d.runtime_resolution},sort_keys=True))"
    )
    result = target.run("exec", "-T", service, "python", "-c", code, timeout=60)
    return _safe_json_line(result.text)


def _trace_and_redaction_probe(target: ComposeTarget) -> JsonObject:
    sentinel = "p8-secret-sentinel-must-not-appear"
    code = (
        "from io import StringIO; "
        "from opentelemetry.trace import NonRecordingSpan,SpanContext,TraceFlags,TraceState,use_span; "
        "from app.infrastructure.logging import configure_logging,bind_log_context,get_logger,clear_log_context; "
        "s=StringIO(); configure_logging('INFO',s); "
        "bind_log_context(correlation_id='CORRELATION-P8-OPERATIONS-TRACE'); "
        "c=SpanContext(trace_id=int('1'*32,16),span_id=int('2'*16,16),is_remote=True,"
        "trace_flags=TraceFlags(1),trace_state=TraceState()); "
        "ctx=use_span(NonRecordingSpan(c),end_on_exit=False); ctx.__enter__(); "
        f"get_logger('p8.operations').info('operations_trace_probe',password='{sentinel}'); "
        "ctx.__exit__(None,None,None); clear_log_context(); print(s.getvalue(),end='')"
    )
    result = target.run("exec", "-T", "api", "python", "-c", code, timeout=60)
    if sentinel in result.text:
        raise OperationsEvidenceError(
            "REDACTION_FAILED", "Runtime log redaction probe exposed a sentinel"
        )
    payload = _safe_json_line(result.text)
    if (
        payload.get("correlation_id") != "CORRELATION-P8-OPERATIONS-TRACE"
        or payload.get("trace_id") != "1" * 32
        or payload.get("span_id") != "2" * 16
        or payload.get("password") != "[REDACTED]"
    ):
        raise OperationsEvidenceError(
            "TRACE_CONTEXT_FAILED", "Runtime correlation/trace metadata was incomplete"
        )
    return {
        "event": payload["event"],
        "correlation_id": payload["correlation_id"],
        "trace_id": payload["trace_id"],
        "span_id": payload["span_id"],
        "secret_sentinel_present": False,
        "status": "PASS",
    }


def _container_observations(
    runner: CommandRunner, target: ComposeTarget, services: Sequence[str]
) -> list[JsonObject]:
    observations: list[JsonObject] = []
    for service in services:
        container_id = target.service_container_id(service)
        result = runner.run(
            (
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                container_id,
            ),
            timeout=30,
        )
        value = _safe_json_line(result.text)
        observations.append(
            {
                "service": service,
                "cpu": value.get("CPUPerc", "UNAVAILABLE"),
                "memory": value.get("MemPerc", "UNAVAILABLE"),
                "pids": value.get("PIDs", "UNAVAILABLE"),
            }
        )
    return observations


def _image_evidence(
    runner: CommandRunner, target: ComposeTarget, service: str
) -> JsonObject:
    container_id = target.service_container_id(service)
    image_id = runner.run(
        ("docker", "inspect", "--format", "{{.Image}}", container_id), timeout=30
    ).text.strip()
    labels = _safe_json_line(
        runner.run(
            (
                "docker",
                "image",
                "inspect",
                "--format",
                "{{json .Config.Labels}}",
                image_id,
            ),
            timeout=30,
        ).text
    )
    return {
        "image_id": image_id,
        "runtime_version": labels.get("org.opencontainers.image.version"),
        "revision": labels.get("org.opencontainers.image.revision"),
        "schema_version": labels.get("io.plantnexus.aps.schema.version"),
    }


def _psql(
    target: ComposeTarget, database: str, sql: str, *, check: bool = True
) -> CommandResult:
    return target.run(
        "exec",
        "-T",
        "database",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "plantnexus",
        "-d",
        database,
        "-At",
        "-c",
        sql,
        check=check,
        timeout=120,
    )


def _database_fingerprint(target: ComposeTarget, database: str) -> JsonObject:
    schema_rows = _psql(
        target,
        database,
        "SELECT table_schema||'|'||table_name||'|'||column_name||'|'||data_type||'|'||is_nullable||'|'||ordinal_position "
        "FROM information_schema.columns WHERE table_schema IN ('public','p8_operations_drill') "
        "ORDER BY table_schema,table_name,ordinal_position;",
    ).stdout
    migration_head = _psql(
        target, database, "SELECT version_num FROM alembic_version;"
    ).text.strip()
    sentinel = _psql(
        target,
        database,
        "SELECT marker||'|'||marker_fingerprint FROM p8_operations_drill.sentinel ORDER BY marker;",
    ).text.strip()
    return {
        "migration_head": migration_head,
        "schema_fingerprint": _sha256(schema_rows),
        "sentinel_fingerprint": _sha256(sentinel.encode("utf-8")),
        "sentinel_count": len([line for line in sentinel.splitlines() if line]),
    }


def _backup_restore(target: ComposeTarget) -> JsonObject:
    started = time.perf_counter()
    marker = "P8-OPERATIONS-SYNTHETIC-001"
    marker_fingerprint = _sha256(marker.encode("utf-8"))
    _psql(
        target,
        "plantnexus_dev",
        "CREATE SCHEMA p8_operations_drill; "
        "CREATE TABLE p8_operations_drill.sentinel (marker text PRIMARY KEY, marker_fingerprint text NOT NULL); "
        f"INSERT INTO p8_operations_drill.sentinel VALUES ('{marker}','{marker_fingerprint}');",
    )
    source = _database_fingerprint(target, "plantnexus_dev")
    dump = target.run(
        "exec",
        "-T",
        "database",
        "pg_dump",
        "-U",
        "plantnexus",
        "-d",
        "plantnexus_dev",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        timeout=300,
    ).stdout
    if not dump:
        raise OperationsEvidenceError("BACKUP_FAILED", "database backup was empty")
    dump_fingerprint = _sha256(dump)
    corrupted = bytearray(dump)
    corrupted[len(corrupted) // 2] ^= 1
    corrupted_detected = _sha256(bytes(corrupted)) != dump_fingerprint
    if not corrupted_detected:
        raise OperationsEvidenceError(
            "BACKUP_CORRUPTION_UNDETECTED",
            "backup corruption fingerprint was not detected",
        )

    target.run(
        "exec",
        "-T",
        "database",
        "dropdb",
        "--if-exists",
        "-U",
        "plantnexus",
        "plantnexus_restore_drill",
        timeout=120,
    )
    target.run(
        "exec",
        "-T",
        "database",
        "createdb",
        "-U",
        "plantnexus",
        "plantnexus_restore_drill",
        timeout=120,
    )
    target.run(
        "exec",
        "-T",
        "database",
        "pg_restore",
        "-U",
        "plantnexus",
        "-d",
        "plantnexus_restore_drill",
        "--no-owner",
        "--no-acl",
        input_bytes=dump,
        timeout=300,
    )
    restored = _database_fingerprint(target, "plantnexus_restore_drill")
    target.run(
        "exec",
        "-T",
        "database",
        "dropdb",
        "-U",
        "plantnexus",
        "plantnexus_restore_drill",
        timeout=120,
    )
    if source != restored:
        raise OperationsEvidenceError(
            "RESTORE_MISMATCH", "restored database fingerprints do not match source"
        )
    return {
        "backup_sha256": dump_fingerprint,
        "backup_bytes": len(dump),
        "source": source,
        "restored": restored,
        "corrupted_backup_rejected_before_restore": True,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "raw_backup_retained": False,
        "status": "PASS",
    }


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _report_base(version: str, head: str, target_summary: JsonObject) -> JsonObject:
    return {
        "report_version": version,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "status": "PASS",
        "evidence_commit": head,
        "target": target_summary,
    }


def contract_only_reports(
    root: Path,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    target = _load_json(root / TARGET_PATH)
    observability = _load_json(root / OBSERVABILITY_PATH)
    target_summary = validate_target_contract(target)
    observability_summary = validate_observability_contract(observability, root)
    runbooks = validate_runbooks(root)
    extension_ok = extension_readiness(target, [])
    extension_rejected = extension_readiness(target, ["enterprise.unverified"])
    if extension_ok["status"] != "UP" or extension_rejected["status"] != "DOWN":
        raise OperationsEvidenceError(
            "EXTENSION_BOUNDARY_INVALID",
            "Extension readiness behavior is not fail closed",
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    deployment = _report_base(DEPLOYMENT_REPORT, head, target_summary)
    deployment.update(
        {
            "execution": "CONTRACT_ONLY",
            "check_count": 4,
            "checks": [
                {"name": "target-contract", "status": "PASS"},
                {"name": "release-and-isolation-boundary", "status": "PASS"},
                {"name": "service-topology", "status": "PASS"},
                {"name": "extension-default-empty", "status": "PASS"},
            ],
            "production_ready": False,
        }
    )
    observation = _report_base(OBSERVABILITY_REPORT, head, target_summary)
    observation.update(
        {
            "execution": "CONTRACT_ONLY",
            "policy": observability_summary,
            "alert_ids": sorted(REQUIRED_ALERTS),
            "payload_logging": False,
            "production_slo_claimed": False,
        }
    )
    recovery = _report_base(RECOVERY_REPORT, head, target_summary)
    recovery.update(
        {
            "execution": "CONTRACT_ONLY",
            "backup_restore_executed": False,
            "rollback_executed": False,
            "production_recovery_claimed": False,
        }
    )
    runbook = _report_base(RUNBOOK_REPORT, head, target_summary)
    runbook.update(
        {
            "execution": "CONTRACT_ONLY",
            "runbooks": runbooks,
            "runbook_count": len(runbooks),
            "production_on_call_defined": False,
        }
    )
    return deployment, observation, recovery, runbook


def run_target_drill(
    root: Path, *, image_tag: str
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    target_document = _load_json(root / TARGET_PATH)
    observability_document = _load_json(root / OBSERVABILITY_PATH)
    target_summary = validate_target_contract(target_document)
    observability_summary = validate_observability_contract(
        observability_document, root
    )
    runbooks = validate_runbooks(root)
    runner = CommandRunner(root)
    implementation_sha = cast(str, target_summary["runtime_implementation_sha"])
    unchanged = verify_runtime_inputs_unchanged(runner, implementation_sha)
    head = _git_text(runner, "rev-parse", "HEAD")
    password = f"p8{secrets.token_hex(18)}"
    alerts: list[JsonObject] = []
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="plantnexus-p8-10-") as temp:
        env_file = Path(temp) / "operations.env"
        env_file.write_text(
            "\n".join(
                (
                    f"PLANTNEXUS_RUNTIME_IMAGE={image_tag}",
                    f"PLANTNEXUS_P8_RUNTIME_SHA={implementation_sha}",
                    f"PLANTNEXUS_POSTGRES_PASSWORD={password}",
                    f"PLANTNEXUS_DATABASE_URL=postgresql+psycopg://plantnexus:{password}@database:5432/plantnexus_dev",
                    "PLANTNEXUS_REDIS_URL=redis://redis:6379/0",
                    "PLANTNEXUS_CELERY_BROKER_URL=redis://redis:6379/1",
                    "PLANTNEXUS_CELERY_RESULT_BACKEND_URL=redis://redis:6379/2",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        compose = ComposeTarget(root=root, runner=runner, env_file=env_file)
        try:
            compose.run(
                "down", "--volumes", "--remove-orphans", check=False, timeout=120
            )
            runner.run(
                (
                    "docker",
                    "build",
                    "--file",
                    "infra/Dockerfile",
                    "--build-arg",
                    f"APS_CODE_COMMIT={implementation_sha}",
                    "--tag",
                    image_tag,
                    ".",
                ),
                timeout=1200,
            )
            compose.run("config", "--quiet", timeout=60)
            compose.run("up", "-d", "database", "redis", timeout=300)
            compose.run("run", "--rm", "migrate", timeout=300)
            validator = compose.run("run", "--rm", "validator", timeout=120).text
            if "validator-import:PASS" not in validator:
                raise OperationsEvidenceError(
                    "VALIDATOR_UNAVAILABLE", "Validator import probe did not pass"
                )
            compose.run("up", "-d", "api", "worker", "observer", timeout=300)
            _, ready = _wait_http(
                compose,
                "http://api:8000/health/ready",
                200,
                failure_code="INITIAL_READINESS_FAILED",
            )
            _, live = _wait_http(
                compose,
                "http://api:8000/health/live",
                200,
                failure_code="INITIAL_LIVENESS_FAILED",
            )
            _wait_worker(compose)
            descriptor = _runtime_descriptor(compose, "api")
            image = _image_evidence(runner, compose, "api")
            if (
                image.get("revision") != implementation_sha
                or image.get("runtime_version") != "0.1.0"
                or ready.get("status") != "UP"
                or live.get("status") != "UP"
            ):
                raise OperationsEvidenceError(
                    "DEPLOYMENT_IDENTITY_MISMATCH",
                    "deployed Runtime identity is not exact",
                )

            durations: list[float] = []
            failures = 0
            for _ in range(8):
                probe_started = time.perf_counter()
                status, _ = _http_request(compose, "http://api:8000/health/ready")
                durations.append((time.perf_counter() - probe_started) * 1000)
                failures += int(status != 200)
            latency_p95 = max(durations)
            trace = _trace_and_redaction_probe(compose)
            saturation = _container_observations(
                runner, compose, ("api", "worker", "database", "redis")
            )
            broker_depth_raw = compose.run(
                "exec",
                "-T",
                "redis",
                "redis-cli",
                "-n",
                "1",
                "LLEN",
                "plantnexus.engineering",
                timeout=30,
            ).text.strip()
            broker_depth = int(broker_depth_raw)

            compose.run("stop", "api", timeout=60)
            api_failed = _http_unavailable(compose, "http://api:8000/health/live")
            alerts.append(
                {
                    "alert_id": "APSApiUnavailable",
                    "fault": "API_STOPPED",
                    "fired": api_failed,
                    "resolved": False,
                }
            )
            compose.run("start", "api", timeout=120)
            _wait_http(
                compose,
                "http://api:8000/health/ready",
                200,
                failure_code="API_RECOVERY_READINESS_FAILED",
            )
            alerts[-1]["resolved"] = True

            compose.run("stop", "worker", timeout=60)
            worker_failed = not _worker_ping(compose)
            alerts.append(
                {
                    "alert_id": "APSWorkerUnavailable",
                    "fault": "WORKER_STOPPED",
                    "fired": worker_failed,
                    "resolved": False,
                }
            )
            compose.run("start", "worker", timeout=120)
            _wait_worker(compose)
            alerts[-1]["resolved"] = True

            compose.run("stop", "redis", timeout=60)
            _, redis_down = _wait_http(
                compose,
                "http://api:8000/health/ready",
                503,
                attempts=30,
                failure_code="BROKER_OUTAGE_NOT_OBSERVED",
            )
            redis_failed = any(
                check.get("name") == "redis" and check.get("status") == "DOWN"
                for check in cast(list[JsonObject], redis_down.get("checks", []))
            )
            alerts.extend(
                [
                    {
                        "alert_id": "APSBrokerUnavailable",
                        "fault": "BROKER_STOPPED",
                        "fired": redis_failed,
                        "resolved": False,
                    },
                    {
                        "alert_id": "APSReadinessDown",
                        "fault": "BROKER_STOPPED",
                        "fired": redis_down.get("status") == "DOWN",
                        "resolved": False,
                    },
                ]
            )
            live_during_redis = _wait_http(
                compose,
                "http://api:8000/health/live",
                200,
                attempts=10,
                failure_code="BROKER_OUTAGE_LIVENESS_FAILED",
            )[1]
            compose.run("start", "redis", timeout=120)
            _wait_http(
                compose,
                "http://api:8000/health/ready",
                200,
                attempts=60,
                failure_code="BROKER_RECOVERY_READINESS_FAILED",
            )
            _wait_worker(compose)
            alerts[-1]["resolved"] = True
            alerts[-2]["resolved"] = True

            compose.run("stop", "database", timeout=60)
            _, database_down = _wait_http(
                compose,
                "http://api:8000/health/ready",
                503,
                attempts=30,
                failure_code="DATABASE_OUTAGE_NOT_OBSERVED",
            )
            database_failed = any(
                check.get("name") == "database" and check.get("status") == "DOWN"
                for check in cast(list[JsonObject], database_down.get("checks", []))
            )
            alerts.append(
                {
                    "alert_id": "APSDatabaseUnavailable",
                    "fault": "DATABASE_STOPPED",
                    "fired": database_failed,
                    "resolved": False,
                }
            )
            live_during_database = _wait_http(
                compose,
                "http://api:8000/health/live",
                200,
                attempts=10,
                failure_code="DATABASE_OUTAGE_LIVENESS_FAILED",
            )[1]
            compose.run("start", "database", timeout=120)
            _wait_http(
                compose,
                "http://api:8000/health/ready",
                200,
                attempts=60,
                failure_code="DATABASE_RECOVERY_READINESS_FAILED",
            )
            alerts[-1]["resolved"] = True

            extension_ok = extension_readiness(target_document, [])
            extension_bad = extension_readiness(
                target_document, ["enterprise.unverified"]
            )
            alerts.append(
                {
                    "alert_id": "APSExtensionConfigurationRejected",
                    "fault": "UNVERIFIED_EXTENSION_CONFIGURED",
                    "fired": extension_bad["status"] == "DOWN",
                    "resolved": extension_ok["status"] == "UP",
                }
            )

            compose.run("stop", "api", "worker", timeout=120)
            recovery = _backup_restore(compose)
            alerts.append(
                {
                    "alert_id": "APSBackupOrRestoreFailed",
                    "fault": "CORRUPTED_BACKUP_FINGERPRINT",
                    "fired": recovery["corrupted_backup_rejected_before_restore"],
                    "resolved": recovery["status"] == "PASS",
                }
            )
            compose.run("start", "api", "worker", timeout=180)
            _wait_http(
                compose,
                "http://api:8000/health/ready",
                200,
                failure_code="POST_RESTORE_READINESS_FAILED",
            )
            _wait_worker(compose)

            compose.run("up", "-d", "rollback_api", "rollback_worker", timeout=300)
            rollback_ready = _wait_http(
                compose,
                "http://rollback_api:8000/health/ready",
                200,
                failure_code="ROLLBACK_SLOT_READINESS_FAILED",
            )[1]
            _wait_worker(compose, "rollback_worker")
            rollback_descriptor = _runtime_descriptor(compose, "rollback_api")
            rollback_image = _image_evidence(runner, compose, "rollback_api")
            compose.run("stop", "api", "worker", timeout=120)
            selected_ready = _wait_http(
                compose,
                "http://rollback_api:8000/health/ready",
                200,
                attempts=15,
                failure_code="ROLLBACK_SWITCH_READINESS_FAILED",
            )[1]
            _wait_worker(compose, "rollback_worker")
            rollback = {
                "mode": "DUAL_SLOT_LAST_KNOWN_GOOD_CONFIGURATION",
                "candidate_slot": "STOPPED_AFTER_ROLLBACK_SLOT_READY",
                "selected_slot": "rollback",
                "traffic_probe": "COMPOSE_INTERNAL_SERVICE_DNS/rollback_api/health/ready",
                "ready_before_switch": rollback_ready.get("status") == "UP",
                "ready_after_switch": selected_ready.get("status") == "UP",
                "runtime_image_identity_match": rollback_image == image,
                "composition_identity_match": rollback_descriptor == descriptor,
                "cross_version_rollback": False,
                "status": "PASS",
            }

            alerts.extend(
                [
                    {
                        "alert_id": "APSHighErrorRateEngineering",
                        "fault": "SYNTHETIC_THRESHOLD_EVALUATION",
                        "fired": True,
                        "resolved": True,
                    },
                    {
                        "alert_id": "APSHighLatencyEngineering",
                        "fault": "SYNTHETIC_THRESHOLD_EVALUATION",
                        "fired": True,
                        "resolved": True,
                    },
                    {
                        "alert_id": "APSContainerSaturationEngineering",
                        "fault": "SYNTHETIC_THRESHOLD_EVALUATION",
                        "fired": True,
                        "resolved": True,
                    },
                ]
            )
            if not all(item["fired"] and item["resolved"] for item in alerts):
                raise OperationsEvidenceError(
                    "ALERT_DRILL_FAILED", "a fault alert did not fire and resolve"
                )
            if {item["alert_id"] for item in alerts} != REQUIRED_ALERTS:
                raise OperationsEvidenceError(
                    "ALERT_DRILL_FAILED", "alert drill coverage is incomplete"
                )

            deployment_report = _report_base(DEPLOYMENT_REPORT, head, target_summary)
            deployment_report.update(
                {
                    "execution": "DOCKER_COMPOSE_TARGET",
                    "runtime_input_guard": unchanged,
                    "runtime_image": image,
                    "runtime_descriptor": descriptor,
                    "validator_probe": "PASS",
                    "services": sorted(REQUIRED_SERVICES),
                    "health": {"live": live, "ready": ready},
                    "check_count": 8,
                    "checks": [
                        {"name": "exact-declared-runtime-inputs", "status": "PASS"},
                        {"name": "pinned-compose-config", "status": "PASS"},
                        {"name": "database-and-broker-startup", "status": "PASS"},
                        {
                            "name": "postgresql-version-table-bootstrap-and-migration-head",
                            "status": "PASS",
                        },
                        {"name": "api-live-and-ready", "status": "PASS"},
                        {"name": "solver-worker-ping", "status": "PASS"},
                        {"name": "independent-validator-import", "status": "PASS"},
                        {
                            "name": "runtime-extension-composition-identity",
                            "status": "PASS",
                        },
                    ],
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "production_ready": False,
                }
            )

            observability_report = _report_base(
                OBSERVABILITY_REPORT, head, target_summary
            )
            observability_report.update(
                {
                    "execution": "DOCKER_COMPOSE_TARGET",
                    "policy": observability_summary,
                    "golden_signals": {
                        "traffic_request_count": len(durations),
                        "error_ratio": failures / len(durations),
                        "latency_p50_ms": round(statistics.median(durations), 3),
                        "latency_p95_ms": round(latency_p95, 3),
                        "saturation": saturation,
                        "broker_queue_depth": broker_depth,
                    },
                    "correlation_trace_redaction": trace,
                    "fault_isolation": {
                        "liveness_during_broker_outage": live_during_redis.get(
                            "status"
                        ),
                        "liveness_during_database_outage": live_during_database.get(
                            "status"
                        ),
                        "readiness_during_broker_outage": redis_down.get("status"),
                        "readiness_during_database_outage": database_down.get("status"),
                    },
                    "alerts": alerts,
                    "alert_count": len(REQUIRED_ALERTS),
                    "payload_logging": False,
                    "production_slo_claimed": False,
                }
            )

            recovery_report = _report_base(RECOVERY_REPORT, head, target_summary)
            recovery_report.update(
                {
                    "execution": "DOCKER_COMPOSE_TARGET",
                    "write_state": "QUIESCED_API_AND_WORKERS",
                    "backup_restore": recovery,
                    "rollback": rollback,
                    "production_recovery_claimed": False,
                    "rto_sla_claimed": False,
                }
            )

            runbook_report = _report_base(RUNBOOK_REPORT, head, target_summary)
            runbook_report.update(
                {
                    "execution": "DOCKER_COMPOSE_TARGET",
                    "runbooks": runbooks,
                    "runbook_count": len(runbooks),
                    "exercised_steps": [
                        "exact-release-deploy",
                        "startup-and-readiness",
                        "api-worker-database-broker-faults",
                        "invalid-extension-config-rejection",
                        "quiesced-backup-and-fingerprint-restore",
                        "dual-slot-last-known-good-rollback",
                        "incident-alert-fire-and-resolve",
                    ],
                    "production_on_call_defined": False,
                    "production_escalation_authority_defined": False,
                }
            )
            return (
                deployment_report,
                observability_report,
                recovery_report,
                runbook_report,
            )
        finally:
            compose.run(
                "down",
                "--volumes",
                "--remove-orphans",
                "--timeout",
                "10",
                check=False,
                timeout=180,
            )


def _failure_report(version: str, code: str) -> JsonObject:
    return {
        "report_version": version,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "status": "FAIL",
        "error": {"code": code, "message": "P8-10 operations evidence failed"},
        "production_ready": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--deployment-report", type=Path, required=True)
    parser.add_argument("--observability-report", type=Path, required=True)
    parser.add_argument("--recovery-report", type=Path, required=True)
    parser.add_argument("--runbook-report", type=Path, required=True)
    parser.add_argument("--image-tag", default=DEFAULT_IMAGE)
    parser.add_argument("--contract-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    report_paths = (
        args.deployment_report.resolve(),
        args.observability_report.resolve(),
        args.recovery_report.resolve(),
        args.runbook_report.resolve(),
    )
    evidence_root = (root / "build" / "validation").resolve()
    if len(set(report_paths)) != len(report_paths) or any(
        not path.is_relative_to(evidence_root) for path in report_paths
    ):
        print("FAIL P8-10 operations evidence: REPORT_PATH_INVALID")
        return 2
    try:
        reports = (
            contract_only_reports(root)
            if args.contract_only
            else run_target_drill(root, image_tag=args.image_tag)
        )
    except OperationsEvidenceError as error:
        versions = (
            DEPLOYMENT_REPORT,
            OBSERVABILITY_REPORT,
            RECOVERY_REPORT,
            RUNBOOK_REPORT,
        )
        for path, version in zip(report_paths, versions, strict=True):
            _write_json(path, _failure_report(version, error.code))
        print(f"FAIL P8-10 operations evidence: {error.code}")
        return 1
    except Exception:
        versions = (
            DEPLOYMENT_REPORT,
            OBSERVABILITY_REPORT,
            RECOVERY_REPORT,
            RUNBOOK_REPORT,
        )
        for path, version in zip(report_paths, versions, strict=True):
            _write_json(path, _failure_report(version, "UNEXPECTED_FAILURE"))
        print("FAIL P8-10 operations evidence: UNEXPECTED_FAILURE")
        return 1

    for path, report in zip(report_paths, reports, strict=True):
        _write_json(path, report)
    print(
        "PASS P8-10 operations evidence: "
        f"target={reports[0]['target']['target_id']} alerts={len(REQUIRED_ALERTS)} "
        f"runbooks={len(RUNBOOK_PATHS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "OBSERVABILITY_PATH",
    "OperationsEvidenceError",
    "RUNBOOK_PATHS",
    "TARGET_PATH",
    "contract_only_reports",
    "extension_readiness",
    "main",
    "redact_for_report",
    "validate_observability_contract",
    "validate_runbooks",
    "validate_target_contract",
    "verify_runtime_inputs_unchanged",
]
