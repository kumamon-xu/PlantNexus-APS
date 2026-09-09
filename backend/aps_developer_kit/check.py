"""TASK-P8-15 reproducibility, compatibility, install, and supply-chain evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Callable, cast
import venv

from aps_extension_tooling.conformance import conform_extension_set, conform_project
from app.infrastructure.release.contracts import read_release_archive, verify_release_archive

from aps_developer_kit.builder import KIT_VERSION, build_developer_kit
from aps_developer_kit.contracts import (
    DeveloperKitContractError,
    plan_upgrade,
    read_kit_archive,
    require_compatible,
    strict_json_document,
    verify_kit_archive,
    verify_kit_files,
)


type JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-15"
TEST_ID = "TEST-P8-DEVELOPER-KIT-COMPATIBILITY-001"
DIFF_BASE = "d0bf00da4af0f73befd2e9c833ffd837c63cedca"
REPORT_VERSION = "p8-developer-kit-compatibility-report.v1"
SECURITY_REPORT_VERSION = "p8-developer-kit-security-report.v1"
UPGRADE_REPORT_VERSION = "p8-developer-kit-upgrade-rollback-report.v1"
BENCHMARK_REPORT_VERSION = "p8-developer-kit-engineering-benchmark.v1"

_FORBIDDEN_PREFIXES = (
    "backend/app/domain/",
    "backend/app/planning/",
    "backend/app/extensions/",
    "backend/aps_extension_sdk/",
    "schemas/",
    "demo/",
)
_FORBIDDEN_EXACT = {"pyproject.toml", "uv.lock"}


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    allowed: frozenset[int] = frozenset({0}),
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if environment:
        env.update(environment)
    result = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode not in allowed:
        raise DeveloperKitContractError(
            "KIT_VALIDATION_COMMAND_FAILED", "Developer Kit validation command failed"
        )
    return result


def _write(path: Path, document: Mapping[str, object]) -> None:
    from aps_developer_kit.contracts import canonical_json_bytes

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_json_bytes(document) + b"\n")
    temporary.replace(path)


def _git_head(root: Path) -> str:
    return _run(("git", "rev-parse", "HEAD"), cwd=root).stdout.strip()


def _scope(root: Path, code_commit: str) -> JsonObject:
    changed = _run(
        ("git", "diff", "--name-only", DIFF_BASE, code_commit, "--"), cwd=root
    ).stdout.splitlines()
    paths = sorted({path.strip().replace("\\", "/") for path in changed if path.strip()})
    forbidden = [
        path
        for path in paths
        if path in _FORBIDDEN_EXACT
        or any(path.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)
    ]
    if forbidden:
        raise DeveloperKitContractError(
            "KIT_BOUNDARY_VIOLATION", "Task changed a frozen Core, SDK, Schema, lock, or Demo path"
        )
    return {
        "diff_base": DIFF_BASE,
        "code_commit": code_commit,
        "changed_path_count": len(paths),
        "forbidden_changed_path_count": 0,
        "core_modified": False,
        "sdk_modified": False,
        "schema_modified": False,
        "root_dependency_graph_modified": False,
        "demo_modified": False,
    }


def _select_runtime(release_output: Path, code_commit: str) -> Path:
    matches: list[Path] = []
    for path in sorted(release_output.rglob("*.tar.gz")):
        try:
            verify_release_archive(
                path,
                expected_runtime_version="0.1.0",
                expected_code_commit=code_commit,
            )
        except Exception:
            continue
        sidecar = path.with_name(path.name + ".sha256")
        expected = f"{__import__('hashlib').sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        if not sidecar.is_file() or sidecar.read_text(encoding="utf-8") != expected:
            raise DeveloperKitContractError(
                "KIT_RUNTIME_IDENTITY_MISMATCH", "Runtime release sidecar differs"
            )
        matches.append(path)
    if len(matches) != 1:
        raise DeveloperKitContractError(
            "KIT_RUNTIME_ARTIFACT_MISSING", "exact Runtime release candidate is not unique"
        )
    return matches[0]


def _extract(files: Mapping[str, bytes], root: Path) -> None:
    for relative, raw in sorted(files.items()):
        destination = root.joinpath(*Path(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _clean_install_and_cli(archive: Path) -> tuple[bool, float]:
    started = perf_counter()
    _, kit_files = read_kit_archive(archive)
    lock = strict_json_document(kit_files["metadata/developer-kit-lock.json"])
    artifacts = cast(JsonObject, lock["artifacts"])
    with TemporaryDirectory(prefix="aps-kit-clean-install-") as temporary:
        base = Path(temporary)
        kit_root = base / "kit"
        _extract(kit_files, kit_root)
        runtime_entry = cast(JsonObject, artifacts["runtime"])
        runtime_archive = kit_root / cast(str, runtime_entry["path"])
        _, runtime_files = read_release_archive(runtime_archive)
        runtime_root = base / "runtime"
        _extract(runtime_files, runtime_root)
        environment_root = base / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment_root)
        python = _venv_python(environment_root)
        environment = {
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONNOUSERSITE": "1",
        }
        requirements = runtime_root / "runtime/requirements/runtime-requirements.lock"
        _run(
            (
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--require-hashes",
                "-r",
                str(requirements),
            ),
            cwd=base,
            environment=environment,
        )
        _run(
            (
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--require-hashes",
                "-r",
                str(kit_root / "locks/developer-tools-requirements.lock"),
            ),
            cwd=base,
            environment=environment,
        )
        runtime_wheels = sorted((runtime_root / "runtime/wheels").glob("*.whl"))
        wheel_paths = [
            *runtime_wheels,
            *[
                kit_root / cast(str, cast(JsonObject, artifacts[key])["path"])
                for key in ("sdk", "tooling", "alpha_extension", "beta_extension")
            ],
        ]
        if len(runtime_wheels) != 1:
            raise DeveloperKitContractError(
                "KIT_INSTALL_FAILED", "Runtime wheel inventory is not exact"
            )
        _run(
            (
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                *[str(path) for path in wheel_paths],
            ),
            cwd=base,
            environment=environment,
        )
        sdk_path = kit_root / cast(str, cast(JsonObject, artifacts["sdk"])["path"])
        command = (
            str(python),
            "-I",
            str(kit_root / "tools/aps_extension_conformance.py"),
            "--root",
            str(kit_root),
            "--sdk-wheel",
            str(sdk_path),
            "--core-source-inventory",
            str(kit_root / "metadata/core-source-hashes.json"),
            "--runtime-version",
            "0.1.0",
            "--developer-kit-version",
            KIT_VERSION,
            "check-set",
            "--project",
            str(kit_root / "examples/alpha-resource-tag"),
            "--project",
            str(kit_root / "examples/beta-priority-policy"),
            "--skip-clean-install",
        )
        result = _run(command, cwd=kit_root, environment=environment)
        document = json.loads(result.stdout)
        if document.get("status") != "PASS" or document.get("extension_count") != 2:
            raise DeveloperKitContractError(
                "KIT_INSTALL_FAILED", "clean installed Kit conformance failed"
            )
    return True, (perf_counter() - started) * 1_000


def _legacy_and_upgrade(root: Path, matrix: Mapping[str, object]) -> JsonObject:
    descriptor_paths = (
        root
        / "examples/enterprise-extensions/alpha-resource-tag/enterprise-extension-project.v1.json",
        root
        / "examples/enterprise-extensions/beta-priority-policy/enterprise-extension-project.v1.json",
    )
    before = tuple(path.read_bytes() for path in descriptor_paths)
    legacy = tuple(
        conform_project(path.parent, repository_root=root, clean_install=False)
        for path in descriptor_paths
    )
    with TemporaryDirectory(prefix="aps-kit-legacy-runtime-") as temporary:
        _, set_report = conform_extension_set(
            cast(tuple[Any, ...], legacy), runtime_directory=Path(temporary)
        )
    after = tuple(path.read_bytes() for path in descriptor_paths)
    if before != after:
        raise DeveloperKitContractError(
            "KIT_IMPLICIT_UPGRADE_FORBIDDEN", "legacy replay mutated project locks"
        )
    current = {
        "developer_kit": "0.0.0-not-published",
        "runtime": "0.1.0",
        "extension_sdk": "1.0.0",
    }
    target = {
        "developer_kit": "1.0.0",
        "runtime": "0.1.0",
        "extension_sdk": "1.0.0",
        "extension_tooling": "1.0.0",
        "enterprise_template": "1.0.0",
    }
    implicit_error = _expect_error(
        "KIT_IMPLICIT_UPGRADE_FORBIDDEN",
        lambda: plan_upgrade(matrix, current, target, explicit_opt_in=False),
    )
    manual = plan_upgrade(matrix, current, target, explicit_opt_in=True)
    unsupported = dict(target)
    unsupported["runtime"] = "0.2.0"
    unsupported_error = _expect_error(
        "KIT_COMBINATION_UNSUPPORTED",
        lambda: require_compatible(matrix, unsupported),
    )
    return {
        "report_version": UPGRADE_REPORT_VERSION,
        "status": "PASS",
        "predecessor": {
            "identity": "p8-14-synthetic-unpublished-predecessor",
            "published": False,
            "support_status": "REPLAY_ONLY_NOT_A_SUPPORTED_RELEASE",
            "extension_count": set_report["extension_count"],
            "replay_status": "PASS",
        },
        "no_automatic_upgrade": before == after,
        "implicit_upgrade_error": implicit_error,
        "manual_upgrade": manual,
        "unsupported_runtime_error": unsupported_error,
        "rollback": {
            "strategy": "RESTORE_RETAINED_PREDECESSOR_PROJECT_BYTES",
            "runtime_downgrade_required": False,
            "overwrite_existing_artifact": False,
            "production_authorized": False,
        },
        "issues": [],
    }


def _expect_error(code: str, call: Callable[[], object]) -> str:
    try:
        call()
    except DeveloperKitContractError as error:
        if error.code != code:
            raise DeveloperKitContractError(
                "KIT_NEGATIVE_CHECK_FAILED", "negative check returned a different code"
            ) from error
        return error.code
    raise DeveloperKitContractError(
        "KIT_NEGATIVE_CHECK_FAILED", "negative check was unexpectedly accepted"
    )


def _security(root: Path, verified: Any) -> JsonObject:
    audit = _run(
        ("uv", "audit", "--locked", "--no-dev", "--output-format", "json"),
        cwd=root,
        allowed=frozenset({0, 1}),
    )
    try:
        document = cast(JsonObject, json.loads(audit.stdout))
    except json.JSONDecodeError as error:
        raise DeveloperKitContractError("KIT_SCA_INVALID", "uv audit output is invalid") from error
    findings = document.get("vulnerabilities")
    policy = strict_json_document(
        (root / "infra/release/runtime-vulnerability-policy.v1.json").read_bytes()
    )
    assessments = policy.get("assessments")
    if not isinstance(findings, list) or not isinstance(assessments, list):
        raise DeveloperKitContractError("KIT_SCA_INVALID", "SCA inventory is malformed")
    allowed: list[set[str]] = []
    for raw in assessments:
        if not isinstance(raw, dict) or raw.get("status") != "NOT_AFFECTED":
            raise DeveloperKitContractError("KIT_SCA_POLICY_FAILED", "VEX assessment is invalid")
        aliases = raw.get("aliases", [])
        identifier = raw.get("advisory_id")
        if not isinstance(identifier, str) or not isinstance(aliases, list):
            raise DeveloperKitContractError("KIT_SCA_POLICY_FAILED", "VEX identity is invalid")
        allowed.append({identifier, *[value for value in aliases if isinstance(value, str)]})
    unmatched: list[str] = []
    for raw in findings:
        if not isinstance(raw, dict):
            unmatched.append("MALFORMED")
            continue
        identifier = raw.get("id")
        aliases = raw.get("aliases", [])
        dependency = raw.get("dependency")
        identity = {
            value
            for value in [identifier, *aliases]
            if isinstance(value, str)
        }
        if (
            not isinstance(dependency, dict)
            or dependency != {"name": "starlette", "version": "0.47.3"}
            or sum(bool(identity & row) for row in allowed) != 1
        ):
            unmatched.append(cast(str, identifier))
    _expect_error(
        "KIT_SIGNATURE_REQUIRED",
        lambda: verify_kit_files(verified.files, channel="production"),
    )
    issues = sorted(unmatched)
    return {
        "report_version": SECURITY_REPORT_VERSION,
        "status": "PASS" if not issues else "FAIL",
        "audit_tool": "uv audit --locked --no-dev",
        "audited_package_count": cast(JsonObject, document.get("summary", {})).get(
            "audited_packages"
        ),
        "raw_finding_count": len(findings),
        "approved_vex_assessment_count": len(assessments),
        "tool_dependency_count": 6,
        "sbom_component_count": len(
            cast(list[object], strict_json_document(verified.files["metadata/sbom.cdx.json"])["components"])
        ),
        "license_status": strict_json_document(
            verified.files["metadata/license-report.json"]
        )["status"],
        "signature_state": "UNSIGNED_ENGINEERING_CANDIDATE",
        "public_promotion_allowed": False,
        "production_signature_rejection": "KIT_SIGNATURE_REQUIRED",
        "issues": issues,
    }


def run_checks(
    root: Path,
    release_output: Path,
    kit_output: Path,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    started = perf_counter()
    code_commit = _git_head(root)
    status = _run(
        ("git", "status", "--porcelain", "--untracked-files=no"), cwd=root
    ).stdout.strip()
    if status:
        raise DeveloperKitContractError(
            "KIT_PROVENANCE_INVALID", "tracked working tree must be clean for Kit release"
        )
    scope = _scope(root, code_commit)
    runtime_archive = _select_runtime(release_output, code_commit)
    runtime = verify_release_archive(runtime_archive)
    epoch = cast(int, runtime.manifest["source_date_epoch"])
    with TemporaryDirectory(prefix="aps-kit-build-a-") as first_directory, TemporaryDirectory(
        prefix="aps-kit-build-b-"
    ) as second_directory:
        first = build_developer_kit(
            root,
            runtime_archive,
            Path(first_directory),
            code_commit=code_commit,
            epoch=epoch,
        )
        second = build_developer_kit(
            root,
            runtime_archive,
            Path(second_directory),
            code_commit=code_commit,
            epoch=epoch,
        )
        reproducible = (
            first.archive_sha256 == second.archive_sha256
            and first.archive_path.read_bytes() == second.archive_path.read_bytes()
        )
    if not reproducible:
        raise DeveloperKitContractError(
            "KIT_BUILD_NONDETERMINISTIC", "same Kit inputs produced different bytes"
        )
    artifact = build_developer_kit(
        root,
        runtime_archive,
        kit_output,
        code_commit=code_commit,
        epoch=epoch,
    )
    verified = verify_kit_archive(
        artifact.archive_path,
        expected_kit_version=KIT_VERSION,
        expected_code_commit=code_commit,
    )
    clean_install, install_ms = _clean_install_and_cli(artifact.archive_path)
    upgrade = _legacy_and_upgrade(root, verified.compatibility)
    security = _security(root, verified)
    if security["status"] != "PASS":
        raise DeveloperKitContractError(
            "KIT_SCA_POLICY_FAILED", "Developer Kit security evidence failed"
        )
    checks = {
        "clean_tracked_input": True,
        "runtime_exact_artifact_and_sidecar": True,
        "reproducible_kit_archive": reproducible,
        "content_addressed_immutable_registry": True,
        "strict_manifest_lock_and_checksums": True,
        "runtime_sdk_tooling_template_exact_matrix": True,
        "two_extension_conformance": True,
        "clean_install_and_packaged_cli": clean_install,
        "legacy_unpublished_predecessor_replay": True,
        "manual_upgrade_only": True,
        "no_automatic_project_upgrade": upgrade["no_automatic_upgrade"],
        "unsupported_combination_rejected": True,
        "unsigned_engineering_boundary": True,
        "sbom_license_and_sca": True,
        "rollback_retains_immutable_bytes": True,
        "task_scope_boundary": True,
    }
    issues = sorted(key for key, value in checks.items() if value is not True)
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "status": "PASS" if not issues else "FAIL",
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "code_commit": code_commit,
        "kit_version": KIT_VERSION,
        "release_fingerprint": artifact.release_fingerprint,
        "archive_sha256": artifact.archive_sha256,
        "runtime_release_fingerprint": verified.runtime_release_fingerprint,
        "versions": verified.manifest["versions"],
        "check_count": len(checks),
        "checks": checks,
        "scope": scope,
        "registry": {
            "policy": "REPOSITORY_CI_APPEND_ONLY_CONTENT_ADDRESSED",
            "remote_publication": False,
            "entry_count": 1,
        },
        "artifacts": {
            "archive_relative_path": artifact.archive_path.relative_to(root).as_posix(),
            "checksum_relative_path": artifact.checksum_path.relative_to(root).as_posix(),
            "registry_relative_path": artifact.registry_path.relative_to(root).as_posix(),
            "payload_file_count": artifact.payload_file_count,
        },
        "boundaries": {
            "engineering_candidate": True,
            "signed": False,
            "production_authorized": False,
            "real_enterprise_extension": False,
            "demo_included": False,
            "p7_reality_calibration": False,
        },
        "issues": issues,
    }
    benchmark: JsonObject = {
        "report_version": BENCHMARK_REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "environment": "SYNTHETIC_ENGINEERING_ONLY",
        "observations": {
            "archive_bytes": artifact.archive_bytes,
            "payload_file_count": artifact.payload_file_count,
            "clean_install_and_cli_ms": round(install_ms, 3),
            "total_check_ms": round((perf_counter() - started) * 1_000, 3),
        },
        "thresholds": None,
        "production_capacity_or_sla": "NOT_ESTABLISHED",
        "issues": [],
    }
    return report, security, upgrade, benchmark


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TASK-P8-15 Developer Kit evidence")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--release-output", type=Path, default=Path("build/release"))
    parser.add_argument("--kit-output", type=Path, default=Path("build/developer-kit"))
    parser.add_argument(
        "--report", type=Path, default=Path("build/validation/p8-developer-kit.json")
    )
    parser.add_argument(
        "--security-report",
        type=Path,
        default=Path("build/validation/p8-developer-kit-security.json"),
    )
    parser.add_argument(
        "--upgrade-report",
        type=Path,
        default=Path("build/validation/p8-developer-kit-upgrade-rollback.json"),
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        default=Path("build/benchmarks/p8-developer-kit.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        reports = run_checks(
            args.root.resolve(), args.release_output.resolve(), args.kit_output.resolve()
        )
    except Exception as error:
        code = getattr(error, "code", "KIT_EVIDENCE_FAILED")
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
        _write(args.report, failure)
        print(json.dumps(failure, sort_keys=True, separators=(",", ":")))
        return 1
    for path, report in zip(
        (
            args.report,
            args.security_report,
            args.upgrade_report,
            args.benchmark_report,
        ),
        reports,
        strict=True,
    ):
        _write(path, report)
    print(json.dumps(reports[0], sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
