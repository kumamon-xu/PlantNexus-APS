"""Machine-checkable OpenAPI and HTTP boundary evidence for TASK-P8-07."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
import subprocess
from time import perf_counter
from typing import Any, cast

import yaml
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.dependencies.authorization import PrincipalContext
from app.api.headless_contracts import headless_error_document
from app.api.headless_openapi import HEADLESS_OPERATION_INVENTORY
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


type JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-07"
DIFF_BASE = "3a4fa8e972e35fea6464031ac1a6e89027eeec5e"
REPORT_VERSION = "p8-headless-http-api-report.v1"
DIFF_REPORT_VERSION = "p8-headless-openapi-diff.v1"
BENCHMARK_VERSION = "p8-headless-api-engineering-benchmark.v1"
DEFAULT_SNAPSHOT = Path("backend/app/api/openapi/headless-api.v1.json")
DEFAULT_BASELINE = Path("backend/app/api/openapi/pre-p8-07-operation-baseline.v1.json")


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def _operation_hash(operation: Mapping[str, object]) -> str:
    return _fingerprint(operation)


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def build_openapi(root: Path) -> JsonObject:
    application = create_app(
        Settings(runtime_schema_directory=root / "schemas" / "json"), probes={}
    )
    return cast(JsonObject, application.openapi())


def _operations(schema: Mapping[str, object]) -> dict[tuple[str, str], JsonObject]:
    paths = cast(Mapping[str, object], schema["paths"])
    result: dict[tuple[str, str], JsonObject] = {}
    for path, raw_item in paths.items():
        item = cast(Mapping[str, object], raw_item)
        for method, raw_operation in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            result[(method.upper(), path)] = cast(JsonObject, raw_operation)
    return result


def _load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document is not an object: {path.name}")
    return cast(JsonObject, value)


def _resolve_pointer(root: object, pointer: str) -> object:
    target = root
    for raw_part in pointer.removeprefix("#/ ").removeprefix("#/").split("/"):
        if not raw_part:
            continue
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, Mapping) or part not in target:
            raise KeyError(pointer)
        target = target[part]
    return target


def _internal_references(schema: object) -> list[str]:
    references: list[str] = []
    pending = [schema]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            reference = current.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/"):
                references.append(reference)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return references


def _registry_tuples(root: Path) -> bool:
    registry = yaml.safe_load(
        (root / "schemas/rules/headless-error-code-registry.v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    for row in registry["codes"]:
        document = headless_error_document(
            row["code"], correlation_id="CORRELATION-P8-07-CHECK"
        )
        if (
            document["category"],
            document["stage"],
            document["retryability"],
            document["action"],
        ) != (
            row["category"],
            row["stage"],
            row["retryability"],
            row["action"],
        ):
            return False
    return True


def _layering_is_bounded(root: Path) -> bool:
    router_path = root / "backend/app/api/routers/headless_planning_runs.py"
    adapter_path = root / "backend/app/application/runtime_http_adapter.py"
    router_tree = ast.parse(router_path.read_text(encoding="utf-8"))
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8"))
    forbidden_router_prefixes = (
        "app.infrastructure",
        "app.jobs",
        "app.planning.backends",
        "app.planning.strategies",
    )
    for node in ast.walk(router_tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.startswith(forbidden_router_prefixes):
                return False
    for node in ast.walk(adapter_tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.startswith(("fastapi", "app.infrastructure", "app.jobs")):
                return False
    return True


class _BenchmarkAuthorizationProvider:
    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        if bearer_token != "synthetic-benchmark-token":
            return None
        return PrincipalContext(
            actor_ref="actor:p8-headless-benchmark",
            resolved_capabilities=frozenset({"view"}),
            planning_run_scope=frozenset({"planning-run-benchmark"}),
            schedule_version_scope=frozenset(),
            export_job_scope=frozenset(),
            auth_policy_version="headless-benchmark-auth.v1",
            planning_scope_scope=frozenset(),
        )


def _http_probe_benchmark(root: Path) -> JsonObject:
    application = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
            runtime_schema_directory=root / "schemas" / "json",
        ),
        probes={},
        authorization_provider=_BenchmarkAuthorizationProvider(),
        headless_clock=lambda: "2026-09-06T00:00:00Z",
    )
    headers = {
        "Authorization": "Bearer synthetic-benchmark-token",
        "X-APS-Tenant-Id": "TENANT-P8-BENCHMARK",
        "X-APS-Factory-Id": "FACTORY-P8-BENCHMARK",
        "X-APS-Planning-Scope-Id": "PLANNING-P8-BENCHMARK",
        "X-Correlation-Id": "CORRELATION-P8-BENCHMARK",
    }
    elapsed: list[float] = []
    statuses: list[int] = []
    with TestClient(application) as client:
        client.get(
            "/api/v1/planning-runs/planning-run-benchmark/status",
            headers=headers,
        )
        for _ in range(25):
            started = perf_counter()
            response = client.get(
                "/api/v1/planning-runs/planning-run-benchmark/status",
                headers=headers,
            )
            elapsed.append((perf_counter() - started) * 1_000)
            statuses.append(response.status_code)
    ordered = sorted(elapsed)
    p95_index = max(0, int(len(ordered) * 0.95) - 1)
    return {
        "probe": "AUTHORIZED_FAIL_CLOSED_STATUS_WITHOUT_RUNTIME",
        "iterations": len(elapsed),
        "expected_status": 503,
        "all_statuses_expected": all(status == 503 for status in statuses),
        "median_elapsed_ms": round(median(elapsed), 3),
        "p95_elapsed_ms": round(ordered[p95_index], 3),
    }


def run_checks(
    root: Path,
    *,
    snapshot_path: Path | None = None,
) -> tuple[JsonObject, JsonObject, JsonObject]:
    resolved_snapshot = snapshot_path or root / DEFAULT_SNAPSHOT
    baseline = _load_json(root / DEFAULT_BASELINE)
    started = perf_counter()
    schema = build_openapi(root)
    first_elapsed_ms = round((perf_counter() - started) * 1_000, 3)
    second_started = perf_counter()
    repeated = build_openapi(root)
    second_elapsed_ms = round((perf_counter() - second_started) * 1_000, 3)
    http_probe = _http_probe_benchmark(root)
    operations = _operations(schema)
    baseline_keys: set[tuple[str, str]] = set()
    preserved = True
    for row in cast(list[JsonObject], baseline["operations"]):
        key = (cast(str, row["method"]), cast(str, row["path"]))
        baseline_keys.add(key)
        operation = operations.get(key)
        if (
            operation is None
            or operation.get("operationId") != row["operation_id"]
            or _operation_hash(operation) != row["operation_sha256"]
        ):
            preserved = False
    expected_additions = {
        (method, path): (operation_id, status)
        for method, path, operation_id, status in HEADLESS_OPERATION_INVENTORY
    }
    additions = set(operations) - baseline_keys
    additions_exact = additions == set(expected_additions)
    create_responses = cast(
        Mapping[str, object],
        operations[("POST", "/api/v1/planning-runs")].get("responses", {}),
    )
    canonical_rejections_documented = all(
        "CanonicalIngressResult" in json.dumps(create_responses.get(status, {}))
        for status in ("403", "409", "422", "500", "503")
    )
    success_contracts = all(
        operations[key].get("operationId") == operation_id
        and str(status)
        in cast(Mapping[str, object], operations[key].get("responses", {}))
        for key, (operation_id, status) in expected_additions.items()
    ) and canonical_rejections_documented
    refs_resolve = True
    for reference in _internal_references(schema):
        try:
            _resolve_pointer(schema, reference)
        except KeyError:
            refs_resolve = False
            break
    components = cast(Mapping[str, object], schema["components"])
    component_schemas = cast(Mapping[str, object], components["schemas"])
    strict_carriers = all(
        cast(Mapping[str, object], component_schemas[name]).get("additionalProperties")
        is False
        for name in (
            "CanonicalIngressRequest",
            "CanonicalIngressResult",
            "PlanningRun",
        )
    )
    metadata = cast(Mapping[str, object], schema.get("x-aps-headless-contract", {}))
    envelope_exact = metadata.get("transport_envelope") == {
        "canonical_request_max_bytes": 8_388_608,
        "action_request_max_bytes": 16_384,
        "json_max_depth": 64,
        "canonical_record_max_count": 100_000,
        "content_encoding": "FORBIDDEN",
        "media_type": "application/json",
    }
    rendered_headless = json.dumps(
        {
            path: cast(Mapping[str, object], schema["paths"])[path]
            for _, path in expected_additions
        },
        sort_keys=True,
    ).lower()
    canonical_only = all(
        marker not in rendered_headless
        for marker in ("multipart/form-data", "application/zip", "text/csv")
    ) and not any(
        "extension" in path.lower() or "plugin" in path.lower()
        for _, path in operations
    )
    snapshot_matches = (
        resolved_snapshot.is_file()
        and resolved_snapshot.read_bytes() == canonical_json_bytes(schema) + b"\n"
    )
    checks = [
        {
            "check_id": "preexisting-29-operation-byte-preservation",
            "passed": preserved and len(baseline_keys) == 29,
        },
        {
            "check_id": "additive-five-operation-inventory",
            "passed": additions_exact and len(operations) == 34,
        },
        {"check_id": "operation-id-and-success-status", "passed": success_contracts},
        {
            "check_id": "bundled-openapi-reference-resolution",
            "passed": refs_resolve,
        },
        {"check_id": "strict-machine-carrier-projection", "passed": strict_carriers},
        {"check_id": "canonical-json-only-surface", "passed": canonical_only},
        {"check_id": "transport-envelope-exact", "passed": envelope_exact},
        {"check_id": "error-registry-tuple-parity", "passed": _registry_tuples(root)},
        {
            "check_id": "thin-router-and-adapter-layering",
            "passed": _layering_is_bounded(root),
        },
        {
            "check_id": "deterministic-committed-openapi-snapshot",
            "passed": repeated == schema and snapshot_matches,
        },
        {
            "check_id": "synthetic-http-fail-closed-overhead-probe",
            "passed": http_probe["all_statuses_expected"] is True,
        },
    ]
    issues = [cast(str, check["check_id"]) for check in checks if not check["passed"]]
    additions_rows = [
        {
            "method": method,
            "path": path,
            "operation_id": operation_id,
            "success_status": status,
            "operation_sha256": _operation_hash(operations[(method, path)]),
        }
        for method, path, operation_id, status in HEADLESS_OPERATION_INVENTORY
    ]
    diff_report: JsonObject = {
        "diff_report_version": DIFF_REPORT_VERSION,
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "baseline_operation_count": len(baseline_keys),
        "final_operation_count": len(operations),
        "preserved_operation_count": 29 if preserved else 0,
        "additions": additions_rows,
        "breaking_changes": [],
        "removed_operations": [],
        "renamed_operation_ids": [],
        "status": "PASS" if preserved and additions_exact else "FAIL",
    }
    benchmark: JsonObject = {
        "benchmark_version": BENCHMARK_VERSION,
        "task_id": TASK_ID,
        "profile": "SYNTHETIC_ENGINEERING_NOT_PRODUCTION_SLA",
        "iterations": 2,
        "openapi_generation_elapsed_ms": [first_elapsed_ms, second_elapsed_ms],
        "operation_count": len(operations),
        "snapshot_bytes": len(canonical_json_bytes(schema)) + 1,
        "transport_envelope": metadata.get("transport_envelope"),
        "http_transport_probe": http_probe,
        "status": (
            "PASS"
            if repeated == schema and http_probe["all_statuses_expected"] is True
            else "FAIL"
        ),
    }
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "code_commit": _git_head(root),
        "diff_base": DIFF_BASE,
        "validation_profile": "HIGH_RISK",
        "http_contract_version": "headless-http.v1",
        "openapi_version": schema["openapi"],
        "openapi_fingerprint": _fingerprint(schema),
        "operation_count": len(operations),
        "preexisting_operation_count": len(baseline_keys),
        "headless_operation_count": len(additions_rows),
        "checks": checks,
        "check_count": len(checks),
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
        "production_boundary": "ENGINEERING_EVIDENCE_ONLY_PRODUCTION_AUTHORITY_REMAINS_P8_08",
    }
    return report, diff_report, benchmark


def _write(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document) + b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--diff-report", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    snapshot = arguments.snapshot
    if not snapshot.is_absolute():
        snapshot = root / snapshot
    report, diff_report, benchmark = run_checks(root, snapshot_path=snapshot)
    _write(arguments.report, report)
    _write(arguments.diff_report, diff_report)
    _write(arguments.benchmark_report, benchmark)
    print(
        f"{report['status']} {TASK_ID}: operations={report['operation_count']} "
        f"checks={report['check_count']} issues={len(report['issues'])}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BENCHMARK_VERSION",
    "DIFF_BASE",
    "DIFF_REPORT_VERSION",
    "REPORT_VERSION",
    "TASK_ID",
    "build_openapi",
    "main",
    "run_checks",
]
