"""Machine-checkable P0 engineering skeleton evidence."""

from __future__ import annotations

import argparse
import json
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings
from app.infrastructure.health import liveness_report, readiness_report
from app.infrastructure.logging import redact_mapping
from app.jobs.contracts import claim_job, heartbeat_job, mark_stalled, new_job
from app.jobs.idempotency import IdempotencyConflictError, InMemoryIdempotencyStore

REPORT_VERSION = "engineering-skeleton-report.v1"

_EXPECTED_RUNTIME_DEPENDENCIES = {
    "alembic==1.16.5",
    "celery==5.5.3",
    "defusedxml==0.7.1",
    "fastapi==0.116.1",
    "openpyxl==3.1.5",
    "opentelemetry-api==1.36.0",
    "ortools==9.15.6755",
    "psycopg[binary]==3.2.9",
    "pydantic-settings==2.10.1",
    "redis==6.4.0",
    "sqlalchemy==2.0.43",
    "structlog==25.4.0",
    "uvicorn==0.35.0",
}


def _pass(name: str, details: object) -> dict[str, object]:
    return {"name": name, "status": "PASS", "details": details}


def run_contract_checks(root: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    project_data = cast(
        dict[str, Any],
        tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")),
    )
    dependencies = set(cast(list[str], project_data["project"]["dependencies"]))
    if dependencies != _EXPECTED_RUNTIME_DEPENDENCIES:
        raise ValueError("runtime dependency pins do not match the repository contract")
    checks.append(_pass("exact-runtime-dependencies", sorted(dependencies)))

    settings = Settings()
    if settings.safe_summary()["data_plane"] != DataPlane.DEVELOPMENT.value:
        raise ValueError("default data plane must be development")
    production = Settings(
        runtime_environment=RuntimeEnvironment.PRODUCTION,
        data_plane=DataPlane.PRODUCTION,
        code_commit="a" * 40,
    )
    if production.build_metadata()["code_commit"] != "a" * 40:
        raise ValueError("production build metadata lost its commit")
    try:
        Settings(
            runtime_environment=RuntimeEnvironment.PRODUCTION,
            data_plane=DataPlane.PRODUCTION,
            code_commit="uncommitted",
            simulation_api_enabled=True,
        )
    except ValidationError:
        pass
    else:
        raise ValueError("production configuration did not fail closed")
    checks.append(_pass("environment-isolation", settings.safe_summary()))

    build = settings.build_metadata()
    live = liveness_report(service=settings.service_name, build=build)
    ready = readiness_report(
        service=settings.service_name,
        build=build,
        probes={"database": lambda: None, "redis": lambda: None},
    )

    def unavailable() -> None:
        raise RuntimeError("postgresql://operator:do-not-leak@host/database")

    unavailable_report = readiness_report(
        service=settings.service_name,
        build=build,
        probes={"database": unavailable, "redis": lambda: None},
    )
    unavailable_payload = unavailable_report.to_dict()
    if unavailable_report.ready or "do-not-leak" in json.dumps(unavailable_payload):
        raise ValueError("readiness did not sanitize a dependency failure")
    checks.append(
        _pass(
            "health-contract",
            {
                "liveness": live.to_dict(),
                "readiness": ready.to_dict(),
                "dependency_failure": unavailable_payload,
            },
        )
    )

    redacted = redact_mapping(
        {
            "correlation_id": "corr-engineering-check",
            "database_url": "postgresql://operator:do-not-leak@host/database",
            "nested": {"api_token": "do-not-leak", "message": "password=do-not-leak"},
        }
    )
    if "do-not-leak" in json.dumps(redacted):
        raise ValueError("logging redaction contract failed")
    checks.append(_pass("structured-log-redaction", redacted))

    start = datetime(2026, 8, 19, 0, 0, tzinfo=UTC)
    queued = new_job(
        job_id="job-contract-check",
        job_kind="engineering-contract-check",
        idempotency_key="idem-contract-check",
        request_fingerprint="a" * 64,
        now=start,
    )
    running = claim_job(
        queued,
        worker_id="worker-a",
        now=start,
        lease_seconds=120,
    )
    heartbeated = heartbeat_job(
        running,
        worker_id="worker-a",
        now=start + timedelta(seconds=30),
        lease_seconds=120,
    )
    stalled = mark_stalled(
        heartbeated,
        now=start + timedelta(seconds=150),
    )
    retried = claim_job(
        stalled,
        worker_id="worker-b",
        now=start + timedelta(seconds=151),
        lease_seconds=120,
    )
    if retried.attempt != 2:
        raise ValueError("job retry attempt was not incremented")

    idempotency = InMemoryIdempotencyStore()
    first = idempotency.register(
        scope="engineering-contract-check",
        key="key-1",
        request_fingerprint="b" * 64,
        logical_id="logical-1",
        now=start,
    )
    replay = idempotency.register(
        scope="engineering-contract-check",
        key="key-1",
        request_fingerprint="b" * 64,
        logical_id="ignored-replay-id",
        now=start + timedelta(seconds=1),
    )
    if replay != first or len(idempotency) != 1:
        raise ValueError("idempotent replay did not return the original record")
    try:
        idempotency.register(
            scope="engineering-contract-check",
            key="key-1",
            request_fingerprint="c" * 64,
            logical_id="logical-2",
            now=start + timedelta(seconds=2),
        )
    except IdempotencyConflictError:
        pass
    else:
        raise ValueError("idempotency conflict was not rejected")
    checks.append(
        _pass(
            "job-reliability-primitives",
            {
                "stalled_status": stalled.status.value,
                "retry_attempt": retried.attempt,
                "idempotent_logical_id": replay.logical_id,
            },
        )
    )

    required_paths = [
        "alembic.ini",
        "backend/migrations/versions/0001_engineering_job_metadata.py",
        "docker-compose.yml",
        "infra/Dockerfile",
        ".github/workflows/ci.yml",
    ]
    missing = [path for path in required_paths if not (root / path).is_file()]
    if missing:
        raise ValueError(f"missing engineering artifacts: {', '.join(missing)}")
    checks.append(_pass("engineering-artifact-layout", required_paths))

    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "task_id": "TASK-P0-08",
        "check_count": len(checks),
        "checks": checks,
        "boundaries": {
            "business_pipeline": "NOT_IMPLEMENTED",
            "distributed_persistence": "NOT_IMPLEMENTED",
            # Frozen P0-08 historical boundary; current solver evidence lives in
            # the TASK-P2-03 machine report.
            "solver": "NOT_INSTALLED",
            "production_deployment": "NOT_CLAIMED",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_contract_checks(arguments.root.resolve())
    except Exception as exc:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": "TASK-P0-08",
            "error_type": type(exc).__name__,
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "main", "run_contract_checks"]
