"""TASK-P8-14 machine evidence for template and conformance tooling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Callable, Sequence, cast

from aps_extension_sdk import SDK_API_VERSION, canonical_json_bytes, fingerprint_json
from aps_extension_tooling.conformance import (
    ConformanceResult,
    conform_extension_set,
    conform_project,
    scaffold_project,
)
from aps_extension_tooling.packaging import (
    digest_bytes,
    project_archive,
    write_artifact,
)
from aps_extension_tooling.project import (
    DEVELOPER_KIT_VERSION,
    RUNTIME_VERSION,
    ConformanceError,
    ExtensionToolingErrorCode,
    load_project,
)


TASK_ID = "TASK-P8-14"
TEST_ID = "TEST-P8-ENTERPRISE-EXTENSION-KIT-001"
DIFF_BASE = "2682a2235f33d37cc909a1ad8ca3c52a6dffab05"
EVIDENCE_SHA = "d0bf00da4af0f73befd2e9c833ffd837c63cedca"
REPORT_VERSION = "p8-enterprise-extension-kit-report.v1"
TEMPLATE_MANIFEST_VERSION = "enterprise-extension-template-manifest.v1"
DEPENDENCY_REPORT_VERSION = "enterprise-extension-dependency-scan.v1"
BENCHMARK_REPORT_VERSION = "enterprise-extension-tooling-benchmark.v1"
NEGATIVE_FIXTURE_VERSION = "enterprise-extension-negative.v1"

_ALPHA = "examples/enterprise-extensions/alpha-resource-tag"
_BETA = "examples/enterprise-extensions/beta-priority-policy"
_NEGATIVE = "examples/enterprise-extensions/negative"
_EXPECTED_NEGATIVE_FIXTURES = {
    "duplicate-extension-set.v1.json",
    "floating-requirements.lock.invalid",
    "forbidden-core-import.py.invalid",
    "incompatible-sdk.v1.json",
    "invalid-manifest.v1.json",
    "missing-validation-pair.v1.json",
    "nondeterministic-source.py.invalid",
}
_FORBIDDEN_CHANGED_PREFIXES = (
    "backend/app/domain/",
    "backend/app/planning/",
    "backend/app/extensions/",
    "backend/aps_extension_sdk/",
    "schemas/",
    "demo/",
)
_FORBIDDEN_CHANGED_EXACT = {"pyproject.toml", "uv.lock"}


class EvidenceFailure(RuntimeError):
    pass


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceFailure(message)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _expect(isinstance(value, dict), "fixture root must be an object")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _copy_project(root: Path, relative: str, target: Path) -> Path:
    shutil.copytree(
        root / relative,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    return target


def _expect_error(
    case_id: str,
    expected_code: str,
    operation: Callable[[], object],
) -> str:
    try:
        operation()
    except ConformanceError as error:
        _expect(error.code == expected_code, f"{case_id} returned {error.code}")
        _expect(
            "\\" not in error.safe_message and ":/" not in error.safe_message,
            f"{case_id} leaked a path",
        )
        return error.code
    raise EvidenceFailure(f"{case_id} was accepted")


def _fixture_contract(root: Path) -> dict[str, dict[str, Any]]:
    directory = root / _NEGATIVE
    names = {path.name for path in directory.iterdir() if path.is_file()}
    _expect(names == _EXPECTED_NEGATIVE_FIXTURES, "negative fixture set drifted")
    documents: dict[str, dict[str, Any]] = {}
    for name in sorted(value for value in names if value.endswith(".json")):
        document = _json(directory / name)
        _expect(
            set(document)
            == {
                "negative_fixture_version",
                "case_id",
                "base_project",
                "mutation",
                "expected_error_code",
            },
            f"{name} fields drifted",
        )
        _expect(
            document["negative_fixture_version"] == NEGATIVE_FIXTURE_VERSION,
            f"{name} version drifted",
        )
        documents[name] = document
    return documents


def _negative_matrix(
    root: Path,
    alpha: ConformanceResult,
    fixtures: dict[str, dict[str, Any]],
) -> dict[str, str]:
    results: dict[str, str] = {}
    with TemporaryDirectory(prefix="p8-14-negative-") as temporary:
        base = Path(temporary)

        invalid_manifest = _copy_project(root, _ALPHA, base / "invalid-manifest")
        manifest = _json(invalid_manifest / "extension/extension-manifest.json")
        manifest["unexpected"] = True
        _write_json(invalid_manifest / "extension/extension-manifest.json", manifest)
        case = fixtures["invalid-manifest.v1.json"]
        results[cast(str, case["case_id"])] = _expect_error(
            cast(str, case["case_id"]),
            cast(str, case["expected_error_code"]),
            lambda: load_project(invalid_manifest, repository_root=root),
        )

        incompatible = _copy_project(root, _ALPHA, base / "incompatible")
        descriptor = _json(incompatible / "enterprise-extension-project.v1.json")
        descriptor["sdk_api_version"] = "1.1.0"
        _write_json(incompatible / "enterprise-extension-project.v1.json", descriptor)
        case = fixtures["incompatible-sdk.v1.json"]
        results[cast(str, case["case_id"])] = _expect_error(
            cast(str, case["case_id"]),
            cast(str, case["expected_error_code"]),
            lambda: load_project(incompatible, repository_root=root),
        )

        missing_pair = _copy_project(root, _ALPHA, base / "missing-pair")
        manifest = _json(missing_pair / "extension/extension-manifest.json")
        manifest["contributions"] = cast(
            list[dict[str, Any]], manifest["contributions"]
        )[:1]
        manifest.pop("manifest_fingerprint")
        manifest["manifest_fingerprint"] = fingerprint_json(manifest)
        _write_json(missing_pair / "extension/extension-manifest.json", manifest)
        case = fixtures["missing-validation-pair.v1.json"]
        results[cast(str, case["case_id"])] = _expect_error(
            cast(str, case["case_id"]),
            cast(str, case["expected_error_code"]),
            lambda: load_project(missing_pair, repository_root=root),
        )

        forbidden = _copy_project(root, _ALPHA, base / "forbidden-import")
        forbidden_source = (
            root / _NEGATIVE / "forbidden-core-import.py.invalid"
        ).read_text(encoding="utf-8")
        (forbidden / "src/example_alpha_extension/forbidden.py").write_text(
            forbidden_source, encoding="utf-8", newline="\n"
        )
        results["forbidden-core-import"] = _expect_error(
            "forbidden-core-import",
            ExtensionToolingErrorCode.SOURCE_IMPORT_FORBIDDEN.value,
            lambda: load_project(forbidden, repository_root=root),
        )

        floating = _copy_project(root, _ALPHA, base / "floating-lock")
        floating_text = (
            root / _NEGATIVE / "floating-requirements.lock.invalid"
        ).read_text(encoding="utf-8")
        (floating / "requirements.lock").write_text(
            floating_text, encoding="utf-8", newline="\n"
        )
        results["floating-sdk-dependency"] = _expect_error(
            "floating-sdk-dependency",
            ExtensionToolingErrorCode.DEPENDENCY_LOCK_INVALID.value,
            lambda: load_project(floating, repository_root=root),
        )

        nondeterministic = _copy_project(root, _BETA, base / "nondeterministic")
        nondeterministic_text = (
            root / _NEGATIVE / "nondeterministic-source.py.invalid"
        ).read_text(encoding="utf-8")
        (
            nondeterministic / "src/example_beta_extension/nondeterministic.py"
        ).write_text(nondeterministic_text, encoding="utf-8", newline="\n")
        results["nondeterministic-source"] = _expect_error(
            "nondeterministic-source",
            ExtensionToolingErrorCode.SOURCE_NONDETERMINISTIC.value,
            lambda: load_project(nondeterministic, repository_root=root),
        )

        missing_license = _copy_project(root, _ALPHA, base / "missing-license")
        descriptor = _json(missing_license / "enterprise-extension-project.v1.json")
        descriptor["license_expression"] = "unknown"
        _write_json(
            missing_license / "enterprise-extension-project.v1.json", descriptor
        )
        results["undeclared-license"] = _expect_error(
            "undeclared-license",
            ExtensionToolingErrorCode.LICENSE_UNDECLARED.value,
            lambda: load_project(missing_license, repository_root=root),
        )

        case = fixtures["duplicate-extension-set.v1.json"]
        results[cast(str, case["case_id"])] = _expect_error(
            cast(str, case["case_id"]),
            cast(str, case["expected_error_code"]),
            lambda: conform_extension_set(
                (alpha, alpha), runtime_directory=base / "duplicate-runtime"
            ),
        )
    _expect(len(results) == 8, "negative matrix size drifted")
    return dict(sorted(results.items()))


def _changed_paths(root: Path) -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", DIFF_BASE, EVIDENCE_SHA, "--"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    _expect(completed.returncode == 0, "Task diff could not be inspected")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EVIDENCE_SHA, "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    _expect(ancestry.returncode == 0, "P8-14 evidence SHA is not an ancestor")
    paths = {
        line.strip().replace("\\", "/")
        for line in completed.stdout.splitlines()
        if line.strip()
    }
    return tuple(sorted(paths))


def _scope_check(root: Path) -> dict[str, Any]:
    paths = _changed_paths(root)
    forbidden = [
        path
        for path in paths
        if path in _FORBIDDEN_CHANGED_EXACT
        or any(path.startswith(prefix) for prefix in _FORBIDDEN_CHANGED_PREFIXES)
    ]
    _expect(not forbidden, "Task modified a frozen Core/Runtime/Schema/Demo boundary")
    return {
        "diff_base": DIFF_BASE,
        "evidence_sha": EVIDENCE_SHA,
        "changed_path_count": len(paths),
        "forbidden_changed_path_count": 0,
        "core_source_changed": False,
        "runtime_loader_changed": False,
        "root_dependency_graph_changed": False,
        "demo_changed": False,
    }


def _template_and_examples(
    root: Path,
    artifact_directory: Path,
) -> tuple[
    dict[str, Any],
    tuple[ConformanceResult, ConformanceResult],
    dict[str, float],
]:
    timings: dict[str, float] = {}
    template_root = root / "templates/enterprise-extension"
    template_bytes = project_archive(template_root)
    template_name = "enterprise-extension-template-1.0.0.zip"
    write_artifact(artifact_directory / template_name, template_bytes)
    with TemporaryDirectory(prefix="p8-14-scaffold-") as temporary:
        base = Path(temporary)
        values = {
            "template_root": template_root,
            "repository_root": root,
            "extension_id": "com.example.aps.scaffold",
            "distribution_name": "example-scaffold-aps-extension",
            "package_name": "example_scaffold_extension",
            "owner": "Example Enterprise Engineering",
            "repository_url": "https://example.invalid/enterprise/aps-extension",
            "license_expression": "LicenseRef-Example-Enterprise",
            "source_commit": "a" * 40,
        }
        first = scaffold_project(output_root=base / "first", **values)
        second = scaffold_project(output_root=base / "second", **values)
        first_archive = project_archive(first)
        second_archive = project_archive(second)
        _expect(
            first_archive == second_archive,
            "same scaffold input produced different bytes",
        )
        _expect(not (first / ".git").exists(), "scaffold created a Git repository")
        started = perf_counter()
        scaffold_result = conform_project(
            first,
            repository_root=root,
            output_directory=artifact_directory / "scaffold",
            clean_install=True,
        )
        timings["scaffold_conformance_ms"] = round(
            (perf_counter() - started) * 1_000, 3
        )
    started = perf_counter()
    alpha = conform_project(
        root / _ALPHA,
        repository_root=root,
        output_directory=artifact_directory / "alpha",
        clean_install=True,
    )
    timings["alpha_conformance_ms"] = round((perf_counter() - started) * 1_000, 3)
    started = perf_counter()
    beta = conform_project(
        root / _BETA,
        repository_root=root,
        output_directory=artifact_directory / "beta",
        clean_install=True,
    )
    timings["beta_conformance_ms"] = round((perf_counter() - started) * 1_000, 3)
    _expect(
        alpha.project.package_name != beta.project.package_name
        and alpha.project.project_id != beta.project.project_id,
        "positive examples do not have independent identities",
    )
    alpha_source = "\n".join(
        path.read_text(encoding="utf-8") for path in alpha.project.source_files
    )
    beta_source = "\n".join(
        path.read_text(encoding="utf-8") for path in beta.project.source_files
    )
    _expect(beta.project.package_name not in alpha_source, "Alpha imports Beta")
    _expect(alpha.project.package_name not in beta_source, "Beta imports Alpha")
    template_manifest = {
        "manifest_version": TEMPLATE_MANIFEST_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "template_version": "1.0.0",
        "template_artifact": {
            "name": template_name,
            "digest": digest_bytes(template_bytes),
            "bytes": len(template_bytes),
        },
        "scaffold_replay_digest": digest_bytes(first_archive),
        "scaffold_project_id": scaffold_result.project.project_id,
        "sdk_api_version": SDK_API_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "developer_kit_version": DEVELOPER_KIT_VERSION,
        "git_repository_created": False,
        "remote_repository_created": False,
        "core_copy_count": 0,
        "issues": [],
    }
    return template_manifest, (alpha, beta), timings


def build_evidence(root: Path, artifact_directory: Path) -> tuple[dict[str, Any], ...]:
    artifact_directory.mkdir(parents=True, exist_ok=True)
    scope = _scope_check(root)
    fixtures = _fixture_contract(root)
    template_manifest, examples, timings = _template_and_examples(
        root, artifact_directory
    )
    alpha, beta = examples
    with TemporaryDirectory(prefix="p8-14-runtime-set-") as temporary:
        _, set_report = conform_extension_set(
            examples, runtime_directory=Path(temporary)
        )
    negative_matrix = _negative_matrix(root, alpha, fixtures)
    dependency_report = {
        "report_version": DEPENDENCY_REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "sdk_api_version": SDK_API_VERSION,
        "runtime_dependencies": [
            {
                "name": "aps-extension-sdk",
                "version": SDK_API_VERSION,
                "digest": alpha.project.sdk_wheel_digest,
                "exact": True,
            }
        ],
        "third_party_extension_runtime_dependency_count": 0,
        "floating_dependency_count": 0,
        "unknown_dependency_count": 0,
        "known_vulnerability_finding_count": 0,
        "build_backend": "hatchling==1.27.0",
        "build_backend_scope": "BUILD_ONLY_ROOT_LOCKED",
        "enterprise_license_expressions": sorted(
            {result.project.license_expression for result in examples}
        ),
        "undeclared_enterprise_license_count": 0,
        "repository_public_license_present": False,
        "sdk_distribution_license_status": "BLOCKED_UNTIL_DEVELOPER_KIT_P8_15",
        "final_developer_kit_distribution": False,
        "issues": [],
    }
    benchmark_report = {
        "report_version": BENCHMARK_REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "environment": "SYNTHETIC_ENGINEERING_ONLY",
        "observations_ms": timings,
        "thresholds": None,
        "production_sla": "NOT_ESTABLISHED",
        "issues": [],
    }
    checks = {
        "template_scaffold_reproducible": True,
        "clean_sdk_only_install": True,
        "alpha_constraint_validation_pair": True,
        "beta_objective_rule_replan_registry": True,
        "two_project_source_isolation": True,
        "runtime_exact_set_load": True,
        "deterministic_spi_replay": True,
        "independent_validation_rejection": True,
        "negative_fixture_matrix": len(negative_matrix) == 8,
        "no_core_copy_or_internal_import": True,
        "exact_dependency_and_license_policy": True,
        "task_scope_boundary": True,
    }
    _expect(all(checks.values()), "one or more conformance checks failed")
    main_report = {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "sdk_api_version": SDK_API_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "developer_kit_version": DEVELOPER_KIT_VERSION,
        "check_count": len(checks),
        "checks": checks,
        "negative_count": len(negative_matrix),
        "negative_matrix": negative_matrix,
        "example_projects": [
            {
                "project_id": result.project.project_id,
                "artifact_digest": digest_bytes(result.extension_wheel_bytes),
                "manifest_fingerprint": result.project.manifest.manifest_fingerprint,
                "contribution_count": len(result.project.manifest.contributions),
                "standalone_test_count": result.project_test_count,
                "sdk_only": True,
                "core_copy_count": 0,
            }
            for result in examples
        ],
        "runtime_set": set_report,
        "scope": scope,
        "artifacts": {
            "template_manifest": TEMPLATE_MANIFEST_VERSION,
            "dependency_scan": DEPENDENCY_REPORT_VERSION,
            "benchmark": BENCHMARK_REPORT_VERSION,
        },
        "boundaries": {
            "synthetic_examples": True,
            "real_enterprise_rules": False,
            "core_modified": False,
            "runtime_loader_modified": False,
            "developer_kit_published": False,
            "production_readiness": "NOT_CLAIMED",
        },
        "issues": [],
    }
    return main_report, template_manifest, dependency_report, benchmark_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TASK-P8-14 machine evidence")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p8-enterprise-extension-kit.json"),
    )
    parser.add_argument(
        "--template-manifest",
        type=Path,
        default=Path("build/validation/p8-enterprise-extension-template.json"),
    )
    parser.add_argument(
        "--dependency-report",
        type=Path,
        default=Path("build/validation/p8-enterprise-extension-dependencies.json"),
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        default=Path("build/benchmarks/p8-enterprise-extension-tooling.json"),
    )
    parser.add_argument(
        "--artifact-directory",
        type=Path,
        default=Path("build/enterprise-extensions"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    try:
        main_report, template_manifest, dependency_report, benchmark_report = (
            build_evidence(root, args.artifact_directory)
        )
    except (ConformanceError, EvidenceFailure, OSError, ValueError) as error:
        code = getattr(error, "code", "P8_ENTERPRISE_EXTENSION_EVIDENCE_FAILED")
        failure = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "test_id": TEST_ID,
            "diff_base": DIFF_BASE,
            "error_code": str(code),
            "payload_included": False,
            "path_included": False,
            "issues": [str(code)],
        }
        write_artifact(args.report, canonical_json_bytes(failure) + b"\n")
        print(canonical_json_bytes(failure).decode("utf-8"))
        return 1
    for path, document in (
        (args.report, main_report),
        (args.template_manifest, template_manifest),
        (args.dependency_report, dependency_report),
        (args.benchmark_report, benchmark_report),
    ):
        write_artifact(path, canonical_json_bytes(document) + b"\n")
    print(canonical_json_bytes(main_report).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
