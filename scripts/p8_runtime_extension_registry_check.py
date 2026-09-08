"""Machine evidence for TASK-P8-13 Runtime Extension Registry and SPI adapters."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import time
import tomllib
from typing import Any, cast


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for candidate in (ROOT, BACKEND):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from aps_extension_sdk import (  # noqa: E402
    ExtensionContractError,
    ExtensionPoint,
    parse_compatibility_policy,
    parse_extension_manifest,
    resolve_manifest_set,
)

from app.data_validation.canonical_ingress import (  # noqa: E402
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.extensions.contracts import RuntimeExtensionError  # noqa: E402
from app.extensions.loader import load_runtime_extensions  # noqa: E402
from app.runtime_composition import (  # noqa: E402
    RuntimeCompositionError,
    RuntimeProcess,
    compose_runtime,
)
from backend.tests.fixtures.p8_synthetic_extension import (  # noqa: E402
    CrashingObjective,
    DivergentRegistry,
    SlowObjective,
)
from backend.tests.p8_runtime_extension_support import (  # noqa: E402
    VERIFICATION_KEY,
    VERIFICATION_KEY_ID,
    runtime_extension_fixture,
    synthetic_artifact,
    synthetic_configuration_document,
    synthetic_manifest_document,
    write_runtime_extension_bundle,
)


TASK_ID = "TASK-P8-13"
TEST_ID = "TEST-P8-PLUGIN-REGISTRY-001"
DIFF_BASE = "4d37dba068c86230f6009820d6cbc7ff10a73495"
REPORT_VERSION = "p8-runtime-extension-registry-report.v1"
MANIFEST_VERSION = "p8-runtime-extension-resolution-manifest.v1"
SECURITY_REPORT_VERSION = "p8-runtime-extension-security-report.v1"
BENCHMARK_REPORT_VERSION = "p8-runtime-extension-benchmark-report.v1"

type JsonObject = dict[str, Any]

_OBJECTIVE_ID = "com.example.cost.objective"
_ALLOWED_EXACT_PATHS = {
    ".github/workflows/ci.yml",
    "pyproject.toml",
    "backend/app/api/app.py",
    "backend/app/application/execution_fact_projection_check.py",
    "backend/app/jobs/celery_app.py",
    "backend/app/infrastructure/config.py",
    "backend/app/infrastructure/health.py",
    "backend/app/runtime_composition.py",
    "backend/app/extensions/__init__.py",
    "backend/app/extensions/contracts.py",
    "backend/app/extensions/loader.py",
    "backend/app/extensions/registry.py",
    "backend/app/planning/backends/cp_sat/replan_solver_check.py",
    "backend/app/planning/problem/freeze_window_check.py",
    "backend/app/planning/reporting/stability_change_report_check.py",
    "backend/app/simulation/execution/simulator_check.py",
    "backend/tests/fixtures/p8_synthetic_extension.py",
    "backend/tests/p8_runtime_extension_support.py",
    "backend/tests/contract/test_p8_runtime_extension_contract.py",
    "backend/tests/unit/test_p8_runtime_extension_registry.py",
    "backend/tests/property/test_p8_runtime_extension_properties.py",
    "backend/tests/integration/test_p8_runtime_extension_integration.py",
    "backend/tests/security/test_p8_runtime_extension_security.py",
    "backend/tests/validation/test_p8_runtime_extension_mutations.py",
    "backend/tests/unit/test_p8_operations_policy.py",
    "backend/tests/integration/test_ci_contract.py",
    "infra/operations/compose.p8-operations.yml",
    "infra/operations/non-production-target.v1.json",
    "scripts/p8_extension_sdk_contract_check.py",
    "scripts/p8_operations_check.py",
    "scripts/p8_runtime_extension_registry_check.py",
    "tests/p6/p6_exit_gate_audit.py",
    "docs/README.md",
    "docs/architecture/configuration-environments-and-isolation.md",
    "docs/architecture/end-to-end-planning-flow.md",
    "docs/architecture/extension-sdk-runtime-and-developer-kit.md",
    "docs/architecture/headless-productization-and-platform-integration.md",
    "docs/architecture/module-boundaries.md",
    "docs/architecture/provenance-and-versioning.md",
    "docs/architecture/system-context.md",
    "docs/architecture/technology-stack.md",
    "docs/contracts/README.md",
    "docs/contracts/extension-sdk-and-developer-kit.md",
    "docs/contracts/headless-platform-integration.md",
    "docs/contracts/planning-problem.md",
    "docs/contracts/schema-versioning.md",
    "docs/domain/error-model.md",
    "docs/domain/kpi-contract.md",
    "docs/domain/state-machines/export-job.md",
    "docs/operations/observability-and-audit.md",
    "docs/operations/deployment.md",
    "docs/operations/security.md",
    "docs/planning/solver-backend-contract.md",
    "docs/simulation/execution-simulator-and-disruptions.md",
}
_ALLOWED_PREFIXES: tuple[str, ...] = ()
_FROZEN_PREFIXES = (
    "backend/app/domain/",
    "backend/app/planning/",
    "backend/app/snapshots/",
    "backend/migrations/",
    "schemas/",
)
_SUCCESSOR_METADATA_CHECKERS = {
    "backend/app/application/execution_fact_projection_check.py",
    "backend/app/planning/backends/cp_sat/replan_solver_check.py",
    "backend/app/planning/problem/freeze_window_check.py",
    "backend/app/planning/reporting/stability_change_report_check.py",
    "backend/app/simulation/execution/simulator_check.py",
}


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def _changed_paths(root: Path) -> tuple[str, ...]:
    values: set[str] = set()
    for arguments in (
        ("diff", "--name-only", f"{DIFF_BASE}...HEAD"),
        ("diff", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        values.update(
            line.replace("\\", "/")
            for line in _git(root, *arguments).splitlines()
            if line
        )
    return tuple(sorted(values))


def _expect_code(operation: Callable[[], object], expected: str) -> bool:
    try:
        operation()
    except RuntimeExtensionError as error:
        return error.code == expected and "do-not-leak" not in str(error)
    except ExtensionContractError as error:
        return error.code.value == expected and "do-not-leak" not in str(error)
    return False


def _rewrite_manifest(document: JsonObject) -> JsonObject:
    value = deepcopy(document)
    value["manifest_fingerprint"] = ""
    projection = dict(value)
    projection.pop("manifest_fingerprint")
    value["manifest_fingerprint"] = canonical_fingerprint(projection)
    return value


def _replace_identity(value: object, source: str, target: str) -> object:
    if isinstance(value, str):
        return value.replace(source, target)
    if isinstance(value, list):
        return [_replace_identity(item, source, target) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_identity(item, source, target)
            for key, item in value.items()
        }
    return value


def _negative_matrix(root: Path, temporary: Path) -> JsonObject:
    del root
    results: JsonObject = {}
    signature_fixture = runtime_extension_fixture(
        temporary / "signature",
        database_url=f"sqlite:///{(temporary / 'signature.db').as_posix()}",
    )
    signature_catalog = deepcopy(signature_fixture.catalog)
    signature_catalog["extensions"][0]["signature"] = f"hmac-sha256:{'0' * 64}"
    projection = dict(signature_catalog)
    projection.pop("catalog_fingerprint")
    signature_catalog["catalog_fingerprint"] = canonical_fingerprint(projection)
    signature_fixture.catalog_path.write_bytes(
        canonical_json_bytes(signature_catalog) + b"\n"
    )
    results["signature_tamper"] = _expect_code(
        signature_fixture.load, "EXTENSION_ARTIFACT_SIGNATURE_INVALID"
    )
    signature_database = temporary / "signature.db"
    try:
        compose_runtime(
            signature_fixture.settings,
            process=RuntimeProcess.WORKER,
            extension_artifacts=(signature_fixture.artifact,),
        )
    except RuntimeCompositionError as error:
        results["startup_rejection_no_business_side_effect"] = (
            error.code == "EXTENSION_ARTIFACT_SIGNATURE_INVALID"
            and not signature_database.exists()
        )
    else:
        results["startup_rejection_no_business_side_effect"] = False

    digest_fixture = runtime_extension_fixture(
        temporary / "digest",
        database_url=f"sqlite:///{(temporary / 'digest.db').as_posix()}",
    )
    tampered_artifact = replace(
        digest_fixture.artifact,
        artifact_bytes=digest_fixture.artifact.artifact_bytes + b"tamper",
    )
    results["artifact_tamper"] = _expect_code(
        lambda: load_runtime_extensions(
            digest_fixture.catalog_path,
            artifacts=(tampered_artifact,),
            runtime_version="0.1.0",
            verification_key_id=VERIFICATION_KEY_ID,
            verification_key=VERIFICATION_KEY,
        ),
        "EXTENSION_ARTIFACT_INTEGRITY_FAILED",
    )
    results["duplicate_provider"] = _expect_code(
        lambda: load_runtime_extensions(
            digest_fixture.catalog_path,
            artifacts=(digest_fixture.artifact, digest_fixture.artifact),
            runtime_version="0.1.0",
            verification_key_id=VERIFICATION_KEY_ID,
            verification_key=VERIFICATION_KEY,
        ),
        "EXTENSION_ARTIFACT_NOT_ALLOW_LISTED",
    )

    incompatible_manifest = synthetic_manifest_document()
    incompatible_manifest["compatibility"]["runtime"][
        "minimum_inclusive"
    ] = "0.2.0"
    incompatible_manifest = _rewrite_manifest(incompatible_manifest)
    incompatible_configuration = synthetic_configuration_document(
        incompatible_manifest
    )
    incompatible_path, _ = write_runtime_extension_bundle(
        temporary / "incompatible",
        manifest=incompatible_manifest,
        configuration=incompatible_configuration,
    )
    results["incompatible_runtime"] = _expect_code(
        lambda: load_runtime_extensions(
            incompatible_path,
            artifacts=(synthetic_artifact(incompatible_manifest),),
            runtime_version="0.1.0",
            verification_key_id=VERIFICATION_KEY_ID,
            verification_key=VERIFICATION_KEY,
        ),
        "EXTENSION_RUNTIME_INCOMPATIBLE",
    )

    configuration_fixture = runtime_extension_fixture(
        temporary / "configuration",
        database_url=f"sqlite:///{(temporary / 'configuration.db').as_posix()}",
    )
    configuration_path = configuration_fixture.catalog_path.parent / cast(
        str,
        configuration_fixture.catalog["extensions"][0]["configuration_path"],
    )
    tampered_configuration = deepcopy(configuration_fixture.configuration)
    tampered_configuration["values"] = {"capacity_mode": "TAMPERED"}
    configuration_path.write_bytes(
        canonical_json_bytes(tampered_configuration) + b"\n"
    )
    results["configuration_tamper"] = _expect_code(
        configuration_fixture.load,
        "EXTENSION_CONFIGURATION_INVALID",
    )

    divergent = runtime_extension_fixture(
        temporary / "divergent",
        database_url=f"sqlite:///{(temporary / 'divergent.db').as_posix()}",
        overrides={"com.example.registry": DivergentRegistry},
    )
    results["divergent_registry"] = _expect_code(
        divergent.load, "EXTENSION_REGISTRY_RESOLUTION_MISMATCH"
    )

    crashing = runtime_extension_fixture(
        temporary / "crash",
        database_url=f"sqlite:///{(temporary / 'crash.db').as_posix()}",
        overrides={_OBJECTIVE_ID: CrashingObjective},
    ).load()
    common = {
        "scope": {"tenant_id": "TENANT-MACHINE"},
        "facts": {"synthetic": True},
        "provenance": {"planning_run_id": "planning-run-machine"},
    }
    results["crash_redacted"] = _expect_code(
        lambda: crashing.invoke_objectives(**common),
        "EXTENSION_EXECUTION_FAILED",
    )
    results["crash_readiness_down"] = _expect_code(
        crashing.probe, "EXTENSION_UNHEALTHY"
    )

    timeout = runtime_extension_fixture(
        temporary / "timeout",
        database_url=f"sqlite:///{(temporary / 'timeout.db').as_posix()}",
        overrides={_OBJECTIVE_ID: SlowObjective},
        invocation_timeout_ms=30,
    ).load()
    results["timeout"] = _expect_code(
        lambda: timeout.invoke_objectives(**common), "EXTENSION_TIMEOUT"
    )

    base_document = synthetic_manifest_document()
    unknown = deepcopy(base_document)
    unknown["contributions"][0]["extension_point"] = "UNKNOWN"
    unknown = _rewrite_manifest(unknown)
    results["unknown_point"] = _expect_code(
        lambda: parse_extension_manifest(unknown), "UNKNOWN_EXTENSION_POINT"
    )

    policy_document = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "backend/aps_extension_sdk/contracts/samples/extension-compatibility.v1.synthetic.json"
        ).read_text(encoding="utf-8")
    )
    policy = parse_compatibility_policy(policy_document)
    first = parse_extension_manifest(base_document)
    second_document = cast(
        JsonObject, _replace_identity(base_document, "com.example", "com.acme")
    )
    second_document["extension_id"] = "com.acme.manufacturing"
    second_document["sdk_api_version"] = "1.1.0"
    second_document = _rewrite_manifest(second_document)
    second = parse_extension_manifest(second_document)
    results["mixed_sdk"] = _expect_code(
        lambda: resolve_manifest_set((first, second), policy), "MIXED_SDK_VERSION"
    )
    conflict_document = deepcopy(second_document)
    conflict_document["sdk_api_version"] = "1.0.0"
    conflict_document = _rewrite_manifest(conflict_document)
    conflict = parse_extension_manifest(conflict_document)
    results["exclusive_registry_conflict"] = _expect_code(
        lambda: resolve_manifest_set((first, conflict), policy), "REGISTRY_CONFLICT"
    )
    return results


def _core_boundary(root: Path) -> JsonObject:
    forbidden = ("app.extensions", "aps_extension_sdk", "enterprise_extension")
    violations: list[str] = []
    scanned = 0
    for relative in ("backend/app/domain", "backend/app/planning", "backend/app/snapshots"):
        for path in sorted((root / relative).rglob("*.py")):
            scanned += 1
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
            for node in ast.walk(tree):
                modules: tuple[str, ...] = ()
                if isinstance(node, ast.Import):
                    modules = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = (node.module,)
                if any(module.startswith(forbidden) for module in modules):
                    violations.append(path.relative_to(root).as_posix())
    validator_source = (
        root / "backend/tests/fixtures/p8_synthetic_extension.py"
    ).read_text(encoding="utf-8")
    return {
        "core_python_files_scanned": scanned,
        "reverse_import_violations": violations,
        "synthetic_validator_imports_core_or_solver": any(
            marker in validator_source
            for marker in ("app.planning", "ortools", "ProblemScheduleValidator")
        ),
    }


def _scope_and_history(root: Path) -> JsonObject:
    changed = _changed_paths(root)
    unexpected = [
        path
        for path in changed
        if path not in _ALLOWED_EXACT_PATHS
        and not any(path.startswith(prefix) for prefix in _ALLOWED_PREFIXES)
    ]
    frozen = [
        path
        for path in changed
        if path.startswith(_FROZEN_PREFIXES)
        and path not in _SUCCESSOR_METADATA_CHECKERS
    ]
    base_lock = subprocess.run(
        ["git", "show", f"{DIFF_BASE}:uv.lock"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    current_project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    packages = cast(
        list[str],
        current_project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"],
    )
    return {
        "changed_paths": list(changed),
        "unexpected_paths": unexpected,
        "frozen_owner_changes": frozen,
        "dependency_lock_unchanged": base_lock == (root / "uv.lock").read_bytes(),
        "runtime_wheel_packages": packages,
        "sdk_internal_runtime_package_included": packages
        == ["backend/app", "backend/aps_extension_sdk"],
    }


def _write(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document) + b"\n")


def run_checks(
    root: Path,
    *,
    temporary: Path,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    started = time.perf_counter()
    fixture = runtime_extension_fixture(
        temporary / "positive",
        database_url=f"sqlite:///{(temporary / 'runtime.db').as_posix()}",
    )
    load_started = time.perf_counter()
    adapter = fixture.load()
    load_elapsed_ms = (time.perf_counter() - load_started) * 1_000

    api = compose_runtime(
        fixture.settings,
        process=RuntimeProcess.API,
        extension_artifacts=(fixture.artifact,),
    )
    worker = compose_runtime(
        fixture.settings,
        process=RuntimeProcess.WORKER,
        extension_artifacts=(fixture.artifact,),
    )
    try:
        parity = api.descriptor.canonical_bytes == worker.descriptor.canonical_bytes
        runtime_fingerprint = api.descriptor.fingerprint
    finally:
        worker.close()
        api.close()

    common: dict[str, Mapping[str, object]] = {
        "scope": {"tenant_id": "TENANT-MACHINE"},
        "facts": {"candidate_count": 1, "synthetic": True},
        "provenance": {"planning_run_id": "planning-run-machine"},
    }
    constraints = adapter.invoke_constraints(**common)
    objectives = adapter.invoke_objectives(**common)
    planning_rules = adapter.invoke_planning_rules(**common)
    validation_rules = adapter.invoke_validation_rules(**common)
    replan = adapter.invoke_replan_policy(
        **common,
        execution_fact_fingerprint=f"sha256:{'1' * 64}",
        hard_lock_fingerprint=f"sha256:{'2' * 64}",
        freeze_window_fingerprint=f"sha256:{'3' * 64}",
        state_machine_version="planning.run.state.v1",
        publication_authority_reference="authority.synthetic",
    )
    registry = adapter.invoke_plugin_registry()
    negatives = _negative_matrix(root, temporary / "negative")
    boundary = _core_boundary(root)
    scope = _scope_and_history(root)
    metrics = adapter.safe_metrics()

    checks = [
        {
            "check_id": "catalog-allow-list-digest-signature-preflight",
            "passed": adapter.document["extension_count"] == 1,
        },
        {
            "check_id": "deterministic-registry-resolution",
            "passed": registry.contributions
            == tuple(
                sorted(
                    registry.contributions,
                    key=lambda item: (item.order, item.contribution_id),
                )
            ),
        },
        {"check_id": "api-worker-composition-parity", "passed": parity},
        {
            "check_id": "six-spi-controlled-invocation",
            "passed": (
                len(constraints) == 1
                and len(objectives) == 1
                and len(planning_rules) == 1
                and len(validation_rules) == 2
                and replan is not None
                and set(item.extension_point for item in registry.contributions)
                == set(ExtensionPoint)
            ),
        },
        {
            "check_id": "independent-validator-domain",
            "passed": (
                all(item.passed for item in validation_rules)
                and boundary["synthetic_validator_imports_core_or_solver"] is False
            ),
        },
        {
            "check_id": "negative-matrix-fail-closed",
            "passed": all(value is True for value in negatives.values()),
        },
        {
            "check_id": "core-reverse-import-boundary",
            "passed": boundary["reverse_import_violations"] == [],
        },
        {
            "check_id": "task-scope-and-frozen-public-contracts",
            "passed": (
                scope["unexpected_paths"] == []
                and scope["frozen_owner_changes"] == []
            ),
        },
        {
            "check_id": "dependency-and-runtime-package-boundary",
            "passed": (
                scope["dependency_lock_unchanged"] is True
                and scope["sdk_internal_runtime_package_included"] is True
            ),
        },
        {
            "check_id": "sanitized-observability-and-readiness",
            "passed": (
                metrics["payloads_recorded"] is False
                and metrics["exception_details_recorded"] is False
                and metrics["unhealthy_contribution_ids"] == []
            ),
        },
    ]
    issues = [cast(str, check["check_id"]) for check in checks if check["passed"] is not True]
    code_commit = (
        "uncommitted"
        if _git(root, "status", "--porcelain")
        else _git(root, "rev-parse", "HEAD").strip()
    )
    manifest: JsonObject = {
        "manifest_version": MANIFEST_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "code_commit": code_commit,
        "runtime_composition_fingerprint": runtime_fingerprint,
        "extension_set": adapter.extension_set_reference,
        "registry_resolution_fingerprint": registry.resolution_fingerprint,
        "extension_ids": list(registry.extension_ids),
        "contributions": [
            {
                "contribution_id": item.contribution_id,
                "extension_point": item.extension_point.value,
                "spi_version": item.spi_version,
                "order": item.order,
                "execution_domain": item.execution_domain.value,
            }
            for item in registry.contributions
        ],
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    }
    security: JsonObject = {
        "report_version": SECURITY_REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "negative_matrix": negatives,
        "core_boundary": boundary,
        "scope": scope,
        "trust_model": {
            "trusted_in_process": True,
            "sandboxed": False,
            "request_code_selection": False,
            "remote_download": False,
            "runtime_install": False,
            "hmac_secret_recorded": False,
        },
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    }
    benchmark: JsonObject = {
        "report_version": BENCHMARK_REPORT_VERSION,
        "task_id": TASK_ID,
        "profile": "SYNTHETIC_ENGINEERING_NOT_PRODUCTION_SLA",
        "thresholds": None,
        "startup_elapsed_ms": round(load_elapsed_ms, 3),
        "total_elapsed_ms": round((time.perf_counter() - started) * 1_000, 3),
        "runtime_metrics": metrics,
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    }
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "code_commit": code_commit,
        "validation_profile": "HIGH_RISK",
        "environment": "TEST",
        "data_plane": "SIMULATION",
        "synthetic": True,
        "checks": checks,
        "check_count": len(checks),
        "negative_count": len(negatives),
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
        "result": "PASS" if not issues else "FAIL",
        "production_boundary": (
            "TRUSTED_IN_PROCESS_ENGINEERING_EVIDENCE_NOT_SANDBOX_NOT_PRODUCTION_READY"
        ),
    }
    return report, manifest, security, benchmark


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--security-report", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve(strict=True)
    from tempfile import TemporaryDirectory

    with TemporaryDirectory(prefix="plantnexus-p8-runtime-extension-") as directory:
        report, manifest, security, benchmark = run_checks(
            root, temporary=Path(directory)
        )
    _write(arguments.report, report)
    _write(arguments.manifest, manifest)
    _write(arguments.security_report, security)
    _write(arguments.benchmark_report, benchmark)
    print(
        f"{report['status']} {TASK_ID}: checks={report['check_count']} "
        f"negatives={report['negative_count']} issues={len(report['issues'])}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BENCHMARK_REPORT_VERSION",
    "DIFF_BASE",
    "MANIFEST_VERSION",
    "REPORT_VERSION",
    "SECURITY_REPORT_VERSION",
    "TASK_ID",
    "TEST_ID",
    "main",
    "run_checks",
]
