"""Emit machine-checkable TASK-P2-03 CP-SAT foundation evidence."""

from __future__ import annotations

import argparse
import ast
from datetime import UTC, datetime
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import platform
import sys
import tomllib
from typing import Any, cast

from app.planning.backends.contracts import (
    BackendFailureReason,
    SolverBackendError,
)
from app.planning.backends.cp_sat.backend import (
    ORTOOLS_VERSION,
    CpSatBackend,
    backend_identity,
    parameters_for_limits,
    probe_empty_model,
    probe_model_invalid,
)
from app.planning.backends.cp_sat.status import native_status_contract
from app.planning.contracts import SolverStatus
from app.planning.policy.contracts import (
    PlanningPolicyDocument,
    SolveLimitsDocument,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2


REPORT_VERSION = "solver-backend-foundation-report.v1"
TASK_ID = "TASK-P2-03"
_DIRECT_PIN = f"ortools=={ORTOOLS_VERSION}"
_TRANSITIVE_NAMES = (
    "absl-py",
    "immutabledict",
    "numpy",
    "pandas",
    "protobuf",
    "typing-extensions",
)
_REQUIRED_CP312_WHEEL_MARKERS = (
    "cp312-cp312-win_amd64",
    "cp312-cp312-manylinux_2_27_x86_64",
    "cp312-cp312-manylinux_2_26_aarch64",
    "cp312-cp312-macosx_10_15_x86_64",
    "cp312-cp312-macosx_11_0_arm64",
)


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _pass(name: str, details: object) -> dict[str, object]:
    return {"name": name, "status": "PASS", "details": details}


def _dependency_evidence(root: Path) -> dict[str, object]:
    project = cast(
        dict[str, Any],
        tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")),
    )
    direct_dependencies = cast(list[str], project["project"]["dependencies"])
    if _DIRECT_PIN not in direct_dependencies:
        raise ValueError("accepted exact OR-Tools direct pin is absent")
    if any("==" not in dependency for dependency in direct_dependencies):
        raise ValueError("a direct runtime dependency is not exact-pinned")

    lock_content = (root / "uv.lock").read_bytes()
    lock = cast(dict[str, Any], tomllib.loads(lock_content.decode("utf-8")))
    packages = cast(list[dict[str, Any]], lock["package"])
    package_rows = [row for row in packages if row.get("name") == "ortools"]
    if len(package_rows) != 1:
        raise ValueError("uv.lock must contain exactly one OR-Tools package")
    ortools_row = package_rows[0]
    if ortools_row.get("version") != ORTOOLS_VERSION:
        raise ValueError("uv.lock OR-Tools version differs from the accepted pin")

    locked_dependencies = tuple(
        sorted(
            cast(str, dependency["name"])
            for dependency in cast(list[dict[str, Any]], ortools_row["dependencies"])
        )
    )
    if locked_dependencies != _TRANSITIVE_NAMES:
        raise ValueError("OR-Tools transitive dependency names changed")
    version_by_name = {
        cast(str, row["name"]): cast(str, row["version"])
        for row in packages
        if row.get("name") in _TRANSITIVE_NAMES
    }
    if tuple(sorted(version_by_name)) != _TRANSITIVE_NAMES:
        raise ValueError("an OR-Tools transitive dependency is not locked")

    wheels = cast(list[dict[str, Any]], ortools_row["wheels"])
    wheel_evidence = []
    filenames = []
    for wheel in wheels:
        url = cast(str, wheel["url"])
        filename = url.rsplit("/", 1)[-1]
        digest = cast(str, wheel["hash"])
        if not digest.startswith("sha256:"):
            raise ValueError("an OR-Tools wheel lacks a SHA-256 lock hash")
        filenames.append(filename)
        wheel_evidence.append({"filename": filename, "sha256": digest})
    for marker in _REQUIRED_CP312_WHEEL_MARKERS:
        if not any(marker in filename for filename in filenames):
            raise ValueError(f"required CPython 3.12 wheel is absent: {marker}")

    return {
        "direct_pin": _DIRECT_PIN,
        "uv_lock_sha256": sha256(lock_content).hexdigest(),
        "transitive_versions": dict(sorted(version_by_name.items())),
        "wheels": sorted(wheel_evidence, key=lambda item: item["filename"]),
    }


def _ortools_import_evidence(root: Path) -> dict[str, object]:
    source_root = root / "backend" / "app"
    allowed_prefix = "backend/app/planning/backends/cp_sat/"
    imports: list[dict[str, object]] = []
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for module in modules:
                if module == "ortools" or module.startswith("ortools."):
                    imports.append({"path": relative, "module": module})
                    if not relative.startswith(allowed_prefix):
                        violations.append(relative)
    if not imports:
        raise ValueError("CP-SAT package contains no explicit OR-Tools import")
    if violations:
        raise ValueError(
            "OR-Tools import escaped the CP-SAT namespace: "
            + ", ".join(sorted(set(violations)))
        )
    return {
        "allowed_prefix": allowed_prefix,
        "imports": imports,
        "violations": [],
    }


def _sample_documents(
    root: Path,
) -> tuple[
    PlanningProblemDocumentV2,
    PlanningPolicyDocument,
    SolveLimitsDocument,
]:
    problem = cast(
        PlanningProblemDocumentV2,
        _load_json(root / "schemas" / "samples" / "planning-problem.v2.synthetic.json"),
    )
    policy = cast(
        PlanningPolicyDocument,
        _load_json(
            root
            / "schemas"
            / "samples"
            / "planning-policy.v1.synthetic.json"
        ),
    )
    limits = cast(
        SolveLimitsDocument,
        _load_json(root / "schemas" / "samples" / "solve-limits.v1.synthetic.json"),
    )
    return problem, policy, limits


def _protocol_evidence(root: Path) -> dict[str, object]:
    problem, policy, limits = _sample_documents(root)
    backend = CpSatBackend()
    signature = inspect.signature(CpSatBackend.solve)
    if tuple(signature.parameters) != ("self", "problem", "policy", "limits"):
        raise ValueError("CpSatBackend.solve differs from SolverBackend protocol")
    try:
        backend.solve(problem, policy, limits)
    except SolverBackendError as error:
        if (
            error.reason is not BackendFailureReason.MODEL_BUILDER_NOT_IMPLEMENTED
            or error.solver_status is not SolverStatus.MODEL_INVALID
        ):
            raise ValueError("foundation solve rejection changed") from error
        rejection = {
            "reason": error.reason.value,
            "solver_status": error.solver_status.value,
            "diagnostic": error.diagnostic(),
        }
    else:
        raise ValueError("foundation unexpectedly produced a PlanningSolution")
    return {
        "solve_parameters": list(signature.parameters),
        "identity": backend.identity,
        "foundation_rejection": rejection,
        "candidate_produced": False,
    }


def run_contract_checks(root: Path) -> dict[str, object]:
    """Validate exact dependency, namespace, status, parameter, and smoke facts."""

    root = root.resolve()
    _, _, limits = _sample_documents(root)
    identity = backend_identity()
    status_mapping = list(native_status_contract())
    if {row["solver_status"] for row in status_mapping} != {
        "UNKNOWN",
        "MODEL_INVALID",
        "FEASIBLE",
        "INFEASIBLE",
        "OPTIMAL",
    }:
        raise ValueError("native CP-SAT status mapping is incomplete")
    parameters = parameters_for_limits(limits)
    if [parameter["name"] for parameter in parameters] != sorted(
        parameter["name"] for parameter in parameters
    ):
        raise ValueError("solver parameters are not in canonical name order")

    empty_smoke = probe_empty_model(limits)
    invalid_smoke = probe_model_invalid(limits)
    if (
        empty_smoke["solver_status"] != SolverStatus.OPTIMAL.value
        or invalid_smoke["solver_status"] != SolverStatus.MODEL_INVALID.value
        or empty_smoke["candidate_produced"]
        or invalid_smoke["candidate_produced"]
    ):
        raise ValueError("engineering smoke status or candidate boundary changed")
    json.dumps(
        {
            "identity": identity,
            "parameters": parameters,
            "empty": empty_smoke,
            "invalid": invalid_smoke,
        },
        sort_keys=True,
    )

    checks = [
        _pass("exact-dependency-and-lock", _dependency_evidence(root)),
        _pass(
            "solver-identity-and-platform",
            {
                "identity": identity,
                "python_version": platform.python_version(),
                "python_implementation": platform.python_implementation(),
                "system": platform.system(),
                "machine": platform.machine(),
                "executable_bits": 64 if sys.maxsize > 2**32 else 32,
            },
        ),
        _pass(
            "namespace-and-protocol-boundary",
            {
                "namespace": _ortools_import_evidence(root),
                "protocol": _protocol_evidence(root),
            },
        ),
        _pass(
            "seven-status-adapter-contract",
            {
                "native": status_mapping,
                "adapter_only": {
                    "CANCELLED": "adapter control/cancellation path",
                    "FAILED": "version, native-status, or adapter failure",
                },
            },
        ),
        _pass("solve-limits-parameter-capture", parameters),
        _pass(
            "engineering-smoke-and-serialization-isolation",
            {"empty_model": empty_smoke, "model_invalid": invalid_smoke},
        ),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "check_count": len(checks),
        "checks": checks,
        "boundaries": {
            "schema_change": "NONE",
            "business_constraints": "NOT_IMPLEMENTED",
            "objective_execution": "NOT_IMPLEMENTED",
            "candidate_solution": "NONE",
            "schedule_validator": "NOT_IMPLEMENTED_BY_TASK",
            "benchmark": "NOT_APPLICABLE_FOUNDATION_ONLY",
            "business_feasibility": "NOT_EVALUATED",
            "database_api_worker": "NOT_IMPLEMENTED",
            "production_readiness": "NOT_CLAIMED",
            "security_review": "POINT_IN_TIME_2026-08-20_NOT_CONTINUOUS_MONITORING",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_contract_checks(arguments.root)
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get(
                "PLANTNEXUS_CODE_COMMIT", "uncommitted"
            ),
            "error_type": type(error).__name__,
            "error_message": str(error),
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


__all__ = ["REPORT_VERSION", "TASK_ID", "main", "run_contract_checks"]
