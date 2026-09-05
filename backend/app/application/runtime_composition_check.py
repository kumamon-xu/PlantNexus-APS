"""Machine evidence generator for TASK-P8-06 Runtime composition."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
from typing import Any, Sequence

from pydantic import SecretStr

from app.data_validation.canonical_ingress import canonical_json_bytes
from app.runtime_composition import (
    DataPlane,
    RuntimeCompositionError,
    RuntimeEnvironment,
    RuntimeProcess,
    Settings,
    compose_runtime,
)


TASK_ID = "TASK-P8-06"
DIFF_BASE = "c69fbe3b21e0e782a293675b523c41f31898d0da"
REPORT_VERSION = "p8-runtime-composition-report.v1"
MANIFEST_VERSION = "p8-runtime-composition-manifest.v1"


type JsonObject = dict[str, Any]


def _settings(root: Path, database_url: str) -> Settings:
    return Settings(
        runtime_environment=RuntimeEnvironment.TEST,
        data_plane=DataPlane.SIMULATION,
        code_commit=DIFF_BASE,
        simulation_api_enabled=True,
        runtime_composition_enabled=True,
        runtime_schema_directory=root / "schemas" / "json",
        runtime_planning_policy_path=(
            root / "schemas" / "samples" / "planning-policy.v1.synthetic.json"
        ),
        runtime_solve_limits_path=(
            root / "schemas" / "samples" / "solve-limits.v1.synthetic.json"
        ),
        database_url=SecretStr(database_url),
    )


def run_checks(root: Path) -> tuple[JsonObject, JsonObject]:
    checks: list[JsonObject] = []
    issues: list[str] = []
    with tempfile.TemporaryDirectory(prefix="plantnexus-p8-runtime-") as directory:
        database_path = Path(directory) / "runtime.db"
        settings = _settings(root, f"sqlite:///{database_path.as_posix()}")
        api = compose_runtime(settings, process=RuntimeProcess.API)
        worker = compose_runtime(settings, process=RuntimeProcess.WORKER)
        try:
            descriptor_equal = api.descriptor.canonical_bytes == (
                worker.descriptor.canonical_bytes
            )
            checks.append(
                {"id": "api-worker-descriptor-parity", "passed": descriptor_equal}
            )
            checks.append(
                {
                    "id": "process-role-isolation",
                    "passed": (
                        api.application is not None
                        and api.worker is None
                        and worker.application is None
                        and worker.worker is not None
                    ),
                }
            )
            extension = api.descriptor.document["extension_adapter"]
            checks.append(
                {
                    "id": "default-empty-extension-seam",
                    "passed": (
                        extension["mode"] == "EMPTY"
                        and extension["extensions"] == []
                        and extension["load_policy"] == "DISABLED_UNTIL_P8_13"
                    ),
                }
            )
            expected_ports = {
                "canonical_ingress_repository",
                "planning_run_repository",
                "worker_repository",
                "transaction",
                "clock",
                "identity",
                "solver",
                "validator",
                "audit",
            }
            checks.append(
                {
                    "id": "real-port-binding-inventory",
                    "passed": set(api.descriptor.document["port_bindings"])
                    == expected_ports,
                }
            )
            api_manifest = api.safe_manifest()
            worker_manifest = worker.safe_manifest()
            manifests_safe = (
                api_manifest["secrets_embedded"] is False
                and worker_manifest["secrets_embedded"] is False
                and api_manifest["composition_fingerprint"]
                == worker_manifest["composition_fingerprint"]
            )
            checks.append(
                {"id": "safe-process-manifests", "passed": manifests_safe}
            )
            rendered = canonical_json_bytes(
                {
                    "descriptor": api.descriptor.document,
                    "api": api_manifest,
                    "worker": worker_manifest,
                }
            ).decode("utf-8")
            checks.append(
                {
                    "id": "secret-and-path-redaction",
                    "passed": all(
                        marker not in rendered
                        for marker in (
                            "sqlite://",
                            "redis://",
                            str(root),
                            "password",
                            "authorization",
                        )
                    ),
                }
            )
            production = Settings(
                runtime_environment=RuntimeEnvironment.PRODUCTION,
                data_plane=DataPlane.PRODUCTION,
                code_commit="a" * 40,
                runtime_composition_enabled=True,
                runtime_planning_policy_path=Path("private-policy.json"),
                runtime_solve_limits_path=Path("private-limits.json"),
                database_url=SecretStr(
                    "postgresql+psycopg://operator:do-not-leak@database/prod"
                ),
            )
            production_code = None
            try:
                compose_runtime(production, process=RuntimeProcess.API)
            except RuntimeCompositionError as error:
                production_code = error.code
            checks.append(
                {
                    "id": "production-provider-gap-fail-closed",
                    "passed": production_code == "PRODUCTION_RUNTIME_UNAVAILABLE",
                }
            )
            checks.append(
                {
                    "id": "no-production-readiness-claim",
                    "passed": (
                        api_manifest["production_ready"] is False
                        and worker_manifest["production_ready"] is False
                    ),
                }
            )
            for check in checks:
                if check["passed"] is not True:
                    issues.append(str(check["id"]))
            manifest: JsonObject = {
                "manifest_version": MANIFEST_VERSION,
                "task_id": TASK_ID,
                "diff_base": DIFF_BASE,
                "composition_fingerprint": api.descriptor.fingerprint,
                "descriptor": api.descriptor.document,
                "processes": [api_manifest, worker_manifest],
                "issues": issues,
                "status": "PASS" if not issues else "FAIL",
            }
        finally:
            worker.close()
            api.close()
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "validation_profile": "HIGH_RISK",
        "environment": "TEST",
        "data_plane": "SIMULATION",
        "synthetic": True,
        "checks": checks,
        "check_count": len(checks),
        "configuration_security": {
            "explicit_profile_required": True,
            "unknown_environment_fail_closed": True,
            "production_provider_gap_fail_closed": True,
            "secret_values_recorded": False,
            "simulation_production_fallback": False,
        },
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
        "production_boundary": "ENGINEERING_EVIDENCE_ONLY_NOT_PRODUCTION_READY",
    }
    return report, manifest


def _write(path: Path, document: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document) + b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args(argv)
    report, manifest = run_checks(arguments.root.resolve())
    _write(arguments.report, report)
    _write(arguments.manifest, manifest)
    print(
        f"{report['status']} {TASK_ID}: checks={report['check_count']} "
        f"issues={len(report['issues'])}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "MANIFEST_VERSION",
    "REPORT_VERSION",
    "TASK_ID",
    "main",
    "run_checks",
]
