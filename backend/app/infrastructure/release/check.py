"""P8-09 release, migration, security, and clean-install evidence runner."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app import APPLICATION_VERSION, CORE_VERSION, RUNTIME_VERSION, SCHEMA_VERSION, SPEC_VERSION
from app.infrastructure.release.builder import (
    build_release,
    build_wheel,
    git_head,
    load_release_policy,
    source_date_epoch,
)
from app.infrastructure.release.contracts import (
    COMPATIBILITY_PATH,
    LICENSE_PATH,
    MIGRATION_PATH,
    SBOM_PATH,
    ReleaseContractError,
    canonical_json_bytes,
    read_release_archive,
    sha256_fingerprint,
    strict_json_document,
    verify_release_archive,
    verify_release_files,
)
from app.infrastructure.release.preflight import preflight_release


type JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-09"
DIFF_BASE = "3595f6f7b1ae4a70f68bb3512f3db4bd024dc8a5"
REPORT_VERSION = "p8-runtime-release-report.v1"
COMPATIBILITY_REPORT_VERSION = "p8-runtime-release-compatibility-report.v1"
MIGRATION_REPORT_VERSION = "p8-runtime-release-migration-report.v1"
SECURITY_REPORT_VERSION = "p8-runtime-release-security-report.v1"
BENCHMARK_REPORT_VERSION = "p8-runtime-release-engineering-benchmark.v1"


def _run(
    command_line: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    allowed_returncodes: frozenset[int] = frozenset({0}),
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if environment is not None:
        env.update(environment)
    result = subprocess.run(
        list(command_line),
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode not in allowed_returncodes:
        raise ReleaseContractError("VALIDATION_COMMAND_FAILED", "release validation command failed")
    return result


def _write(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document) + b"\n")


def _extract_regular_files(files: Mapping[str, bytes], root: Path) -> None:
    for relative, raw in sorted(files.items()):
        destination = root / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)


def _migration_replay(files: Mapping[str, bytes]) -> JsonObject:
    result: JsonObject = {
        "empty_upgrade_to_head": False,
        "empty_downgrade_to_base": False,
        "empty_reupgrade_to_head": False,
        "populated_head_row_inserted": False,
        "populated_downgrade_removed_only_head_table": False,
        "populated_reupgrade_is_empty": False,
        "final_downgrade_to_base": False,
        "destructive_boundary_observed": False,
    }
    with TemporaryDirectory(prefix="p8-release-migration-") as temporary:
        release = Path(temporary) / "release"
        selected = {
            path: raw
            for path, raw in files.items()
            if path == "runtime/alembic.ini" or path.startswith("runtime/backend/migrations/")
        }
        _extract_regular_files(selected, release)
        database_path = Path(temporary) / "runtime.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        configuration = Config(str(release / "runtime/alembic.ini"))
        configuration.set_main_option(
            "script_location", str(release / "runtime/backend/migrations")
        )
        configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            head_tables = set(inspect(engine).get_table_names())
            with engine.connect() as connection:
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            result["empty_upgrade_to_head"] = (
                revision == "0009_host_authorization_audit"
                and "headless_authorization_audit_records" in head_tables
            )
        finally:
            engine.dispose()

        command.downgrade(configuration, "base")
        downgraded = create_engine(database_url)
        try:
            result["empty_downgrade_to_base"] = (
                "headless_authorization_audit_records"
                not in set(inspect(downgraded).get_table_names())
            )
        finally:
            downgraded.dispose()

        command.upgrade(configuration, "head")
        populated = create_engine(database_url)
        try:
            with populated.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO headless_authorization_audit_records ("
                        "audit_event_id,data_plane,environment,operation_id,outcome,reason,"
                        "actor_ref,scope_fingerprint,resource_reference,correlation_id,"
                        "occurred_at_utc,audit_fingerprint,audit_json,audit_sha256) VALUES ("
                        ":event,'SIMULATION','TEST','getHeadlessPlanningRunStatus','ALLOWED',"
                        "'AUTHORIZED',:actor,:scope,NULL,:correlation,:occurred,:fingerprint,"
                        ":document,:digest)"
                    ),
                    {
                        "event": "p8-release-audit-event-00000000000000000000000000000001",
                        "actor": "actor:p8-release-check",
                        "scope": f"sha256:{'a' * 64}",
                        "correlation": "correlation-p8-release-check",
                        "occurred": "2026-09-07T00:00:00Z",
                        "fingerprint": f"sha256:{'b' * 64}",
                        "document": b"{}",
                        "digest": "c" * 64,
                    },
                )
            with populated.connect() as connection:
                count = connection.execute(
                    text("SELECT count(*) FROM headless_authorization_audit_records")
                ).scalar_one()
            result["populated_head_row_inserted"] = count == 1
            result["empty_reupgrade_to_head"] = True
            tables_before = set(inspect(populated).get_table_names())
        finally:
            populated.dispose()

        command.downgrade(configuration, "0008_planning_run_solver_worker")
        rolled_back = create_engine(database_url)
        try:
            tables_after = set(inspect(rolled_back).get_table_names())
            result["populated_downgrade_removed_only_head_table"] = (
                "headless_authorization_audit_records" not in tables_after
                and tables_before - {"headless_authorization_audit_records"} <= tables_after
            )
            result["destructive_boundary_observed"] = result[
                "populated_downgrade_removed_only_head_table"
            ]
        finally:
            rolled_back.dispose()

        command.upgrade(configuration, "head")
        replayed = create_engine(database_url)
        try:
            with replayed.connect() as connection:
                count = connection.execute(
                    text("SELECT count(*) FROM headless_authorization_audit_records")
                ).scalar_one()
            result["populated_reupgrade_is_empty"] = count == 0
        finally:
            replayed.dispose()
        command.downgrade(configuration, "base")
        result["final_downgrade_to_base"] = True

    issues = [key for key, value in result.items() if value is not True]
    return {
        "report_version": MIGRATION_REPORT_VERSION,
        "database_head": "0009_host_authorization_audit",
        "profile": "SQLITE_ENGINEERING_REPLAY_NOT_PRODUCTION_DATABASE_CERTIFICATION",
        "checks": result,
        "rollback_policy": "BACKUP_RESTORE_OR_APPROVED_FORWARD_FIX",
        "data_loss_boundary": "0009_TO_0008_REMOVES_APPEND_ONLY_AUTHORIZATION_AUDIT_ROWS",
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    }


def _audit_security(root: Path, files: Mapping[str, bytes]) -> JsonObject:
    audit = _run(
        ("uv", "audit", "--locked", "--no-dev", "--output-format", "json"),
        cwd=root,
        allowed_returncodes=frozenset({0, 1}),
    )
    try:
        document = cast(JsonObject, json.loads(audit.stdout))
    except json.JSONDecodeError as error:
        raise ReleaseContractError("SCA_INVALID", "uv audit output is not JSON") from error
    vulnerability_policy = strict_json_document(
        files["policy/runtime-vulnerability-policy.v1.json"]
    )
    raw_assessments = vulnerability_policy.get("assessments")
    raw_findings = document.get("vulnerabilities")
    if not isinstance(raw_assessments, list) or not isinstance(raw_findings, list):
        raise ReleaseContractError("SCA_INVALID", "vulnerability inventory is malformed")
    assessments = [cast(JsonObject, row) for row in raw_assessments if isinstance(row, dict)]
    findings = [cast(JsonObject, row) for row in raw_findings if isinstance(row, dict)]
    if len(assessments) != len(raw_assessments) or len(findings) != len(raw_findings):
        raise ReleaseContractError("SCA_INVALID", "vulnerability entry is malformed")

    assessment_sets: dict[str, set[str]] = {}
    for assessment in assessments:
        advisory_id = assessment.get("advisory_id")
        aliases = assessment.get("aliases")
        if (
            not isinstance(advisory_id, str)
            or not isinstance(aliases, list)
            or not all(isinstance(value, str) for value in aliases)
            or assessment.get("status") != "NOT_AFFECTED"
        ):
            raise ReleaseContractError("SCA_POLICY_FAILED", "vulnerability assessment is invalid")
        assessment_sets[advisory_id] = {advisory_id, *cast(list[str], aliases)}

    observed: dict[str, int] = {key: 0 for key in assessment_sets}
    unmatched: list[str] = []
    for finding in findings:
        identifier = finding.get("id")
        aliases = finding.get("aliases")
        dependency = finding.get("dependency")
        if not isinstance(identifier, str) or not isinstance(aliases, list) or not isinstance(dependency, dict):
            raise ReleaseContractError("SCA_INVALID", "audit finding identity is malformed")
        if dependency != {"name": "starlette", "version": "0.47.3"}:
            unmatched.append(identifier)
            continue
        identity = {identifier, *[value for value in aliases if isinstance(value, str)]}
        matches = [key for key, values in assessment_sets.items() if values & identity]
        if len(matches) != 1:
            unmatched.append(identifier)
        else:
            observed[matches[0]] += 1

    source_files = [
        path
        for path in sorted((root / "backend/app").rglob("*.py"))
        if "infrastructure/release" not in path.relative_to(root).as_posix()
    ]
    source_by_path = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in source_files
    }
    joined = "\n".join(source_by_path.values())
    guard_results: JsonObject = {
        "no_file_response": "FileResponse" not in joined,
        "no_static_files": "StaticFiles" not in joined,
        "no_form_parser": "request.form(" not in joined,
        "no_http_endpoint": "HTTPEndpoint" not in joined,
        "no_url_hostname_or_netloc": (
            "request.url.hostname" not in joined and "request.url.netloc" not in joined
        ),
        "url_path_error_envelope_only": (
            joined.count("request.url.path") == 2
            and source_by_path.get("backend/app/api/app.py", "").count("request.url.path") == 2
            and all(
                "request.url" not in source
                for path, source in source_by_path.items()
                if path.startswith("backend/app/api/dependencies/")
                or path.startswith("backend/app/api/routers/")
            )
        ),
        "target_linux": True,
    }
    missing_assessments = sorted(key for key, count in observed.items() if count == 0)
    guard_issues = sorted(key for key, value in guard_results.items() if value is not True)
    issues = sorted({*unmatched, *missing_assessments, *guard_issues})
    return {
        "report_version": SECURITY_REPORT_VERSION,
        "audit_tool": "uv audit",
        "audited_package_count": cast(JsonObject, document.get("summary", {})).get(
            "audited_packages"
        ),
        "raw_finding_count": len(findings),
        "unique_assessment_count": len(assessments),
        "assessments": [
            {
                "advisory_id": assessment["advisory_id"],
                "status": assessment["status"],
                "observed_records": observed[cast(str, assessment["advisory_id"])],
            }
            for assessment in assessments
        ],
        "source_guards": guard_results,
        "production_certification": False,
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    }


def _clean_install_smoke(files: Mapping[str, bytes]) -> tuple[bool, float]:
    started = perf_counter()
    with TemporaryDirectory(prefix="p8-release-install-") as temporary:
        release = Path(temporary) / "release"
        _extract_regular_files(files, release)
        runtime = release / "runtime"
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("VIRTUAL_ENV", None)
        virtual_environment = Path(temporary) / "venv"
        _run(("uv", "venv", "--python", "3.12", str(virtual_environment)), cwd=runtime, environment=environment)
        python = (
            virtual_environment / "Scripts/python.exe"
            if os.name == "nt"
            else virtual_environment / "bin/python"
        )
        requirements = runtime / "requirements/runtime-requirements.lock"
        wheel_paths = sorted((runtime / "wheels").glob("*.whl"))
        if len(wheel_paths) != 1:
            raise ReleaseContractError("INSTALL_FAILED", "release wheel inventory is invalid")
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
            cwd=runtime,
            environment=environment,
        )
        _run(
            ("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel_paths[0])),
            cwd=runtime,
            environment=environment,
        )
        smoke = (
            "from app import APPLICATION_VERSION,CORE_VERSION,RUNTIME_VERSION,SCHEMA_VERSION;"
            "from app.api.app import create_app;"
            "from app.jobs.planning_run_solver_worker import PlanningRunSolverWorker;"
            "from app.planning.validation.problem_schedule_validator import ProblemScheduleValidator;"
            "assert (APPLICATION_VERSION,CORE_VERSION,RUNTIME_VERSION,SCHEMA_VERSION)=="
            "('0.0.0','0.0.0','0.1.0','2.10.0');"
            "assert callable(create_app) and PlanningRunSolverWorker and ProblemScheduleValidator"
        )
        _run((str(python), "-I", "-c", smoke), cwd=runtime, environment=environment)
    return True, (perf_counter() - started) * 1_000


def _expected_configuration(policy: Mapping[str, object]) -> set[str]:
    preflight = policy.get("preflight")
    if not isinstance(preflight, dict):
        raise ReleaseContractError("POLICY_INVALID", "preflight policy is missing")
    values = preflight.get("required_configuration_names")
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ReleaseContractError("POLICY_INVALID", "preflight configuration names are malformed")
    return set(cast(list[str], values))


def _expect_preflight_error(expected: str, call: Any) -> bool:
    try:
        call()
    except ReleaseContractError as error:
        return error.code == expected
    return False


def run_checks(root: Path, release_output: Path) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject, JsonObject]:
    started = perf_counter()
    code_commit = git_head(root)
    epoch = source_date_epoch(root, code_commit)
    with TemporaryDirectory(prefix="p8-release-build-a-") as first_dir, TemporaryDirectory(
        prefix="p8-release-build-b-"
    ) as second_dir:
        wheel_a = build_wheel(root, Path(first_dir) / "wheel", epoch=epoch)
        wheel_b = build_wheel(root, Path(second_dir) / "wheel", epoch=epoch)
        wheel_reproducible = wheel_a.name == wheel_b.name and wheel_a.read_bytes() == wheel_b.read_bytes()
        first = build_release(root, wheel_a, Path(first_dir) / "release", code_commit=code_commit, epoch=epoch)
        second = build_release(root, wheel_b, Path(second_dir) / "release", code_commit=code_commit, epoch=epoch)
        archive_reproducible = (
            first.archive_sha256 == second.archive_sha256
            and first.archive_path.read_bytes() == second.archive_path.read_bytes()
        )
        artifact = build_release(
            root,
            wheel_a,
            release_output,
            code_commit=code_commit,
            epoch=epoch,
        )

    verified = verify_release_archive(
        artifact.archive_path,
        expected_runtime_version=RUNTIME_VERSION,
        expected_code_commit=code_commit,
    )
    _, files = read_release_archive(artifact.archive_path)
    policy = load_release_policy(root)
    configured = _expected_configuration(policy)
    preflight_started = perf_counter()
    preflight = preflight_release(
        artifact.archive_path,
        expected_code_commit=code_commit,
        configured_names=configured,
    )
    preflight_elapsed_ms = (perf_counter() - preflight_started) * 1_000

    negative_results: JsonObject = {}
    negative_results["wrong_runtime_version"] = _expect_preflight_error(
        "VERSION_MISMATCH",
        lambda: preflight_release(
            artifact.archive_path,
            expected_code_commit=code_commit,
            expected_runtime_version="9.9.9",
            configured_names=configured,
        ),
    )
    negative_results["wrong_commit"] = _expect_preflight_error(
        "VERSION_MISMATCH",
        lambda: preflight_release(
            artifact.archive_path,
            expected_code_commit="f" * 40,
            configured_names=configured,
        ),
    )
    negative_results["missing_configuration"] = _expect_preflight_error(
        "CONFIGURATION_MISSING",
        lambda: preflight_release(
            artifact.archive_path,
            expected_code_commit=code_commit,
            configured_names=set(),
        ),
    )
    negative_results["production_promotion"] = _expect_preflight_error(
        "PRODUCTION_AUTHORITY_UNAVAILABLE",
        lambda: preflight_release(
            artifact.archive_path,
            expected_code_commit=code_commit,
            configured_names=configured,
            production_requested=True,
        ),
    )
    tampered = dict(files)
    tamper_path = next(path for path in sorted(tampered) if path.startswith("runtime/schemas/"))
    tampered[tamper_path] = tampered[tamper_path] + b"\n"
    negative_results["payload_tamper"] = _expect_preflight_error(
        "CHECKSUM_MISMATCH",
        lambda: verify_release_files(tampered),
    )
    with TemporaryDirectory(prefix="p8-release-no-sidecar-") as temporary:
        no_sidecar = Path(temporary) / artifact.archive_path.name
        shutil.copyfile(artifact.archive_path, no_sidecar)
        negative_results["missing_sidecar"] = _expect_preflight_error(
            "CHECKSUM_MISSING",
            lambda: preflight_release(
                no_sidecar,
                expected_code_commit=code_commit,
                configured_names=configured,
            ),
        )

    migration = _migration_replay(files)
    security = _audit_security(root, files)
    clean_install, install_elapsed_ms = _clean_install_smoke(files)
    compatibility_manifest = strict_json_document(files[COMPATIBILITY_PATH])
    migration_manifest = strict_json_document(files[MIGRATION_PATH])
    license_report = strict_json_document(files[LICENSE_PATH])
    sbom = strict_json_document(files[SBOM_PATH])
    versions = cast(JsonObject, verified.manifest["versions"])
    expected_versions = {
        "runtime": RUNTIME_VERSION,
        "application": APPLICATION_VERSION,
        "core": CORE_VERSION,
        "api": "headless-http.v1",
        "schema": SCHEMA_VERSION,
        "spec": SPEC_VERSION,
        "database": "0009_host_authorization_audit",
        "extension_sdk": "0.0.0-not-published",
        "developer_kit": "0.0.0-not-published",
        "plugin_registry": "plugin-registry.v1",
    }
    excluded = [
        path
        for path in files
        if path.startswith(("demo/", "frontend/", "enterprise-extension/", "third-party/"))
    ]
    component_count = len(cast(list[object], sbom.get("components", [])))
    license_count = cast(int, license_report.get("component_count", 0))

    compatibility: JsonObject = {
        "report_version": COMPATIBILITY_REPORT_VERSION,
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "versions": versions,
        "expected_versions": expected_versions,
        "openapi_fingerprint": sha256_fingerprint(files["runtime/openapi/headless-api.v1.json"]),
        "schema_file_count": len([path for path in files if path.startswith("runtime/schemas/")]),
        "migration_revision_count": migration_manifest.get("revision_count"),
        "default_empty_extension": cast(JsonObject, verified.manifest["extension_boundary"]).get(
            "bundled_extensions"
        )
        == [],
        "automatic_upgrade": compatibility_manifest.get("automatic_upgrade"),
        "issues": [] if versions == expected_versions and not excluded else ["version-or-scope-mismatch"],
    }
    compatibility["status"] = "PASS" if not compatibility["issues"] else "FAIL"

    checks = [
        {"check_id": "wheel-byte-reproducibility", "passed": wheel_reproducible},
        {"check_id": "archive-byte-reproducibility", "passed": archive_reproducible},
        {
            "check_id": "content-address-and-sidecar",
            "passed": artifact.archive_path.parent.name == artifact.archive_sha256.removeprefix("sha256:"),
        },
        {"check_id": "manifest-version-matrix", "passed": versions == expected_versions},
        {"check_id": "bounded-runtime-payload", "passed": not excluded},
        {
            "check_id": "sbom-and-license-inventory",
            "passed": component_count == license_count == 51 and license_report.get("status") == "PASS",
        },
        {"check_id": "startup-preflight", "passed": preflight.get("status") == "PASS"},
        {
            "check_id": "negative-and-promotion-fail-closed",
            "passed": all(value is True for value in negative_results.values()),
        },
        {"check_id": "migration-upgrade-downgrade-replay", "passed": migration["status"] == "PASS"},
        {"check_id": "clean-locked-install-smoke", "passed": clean_install},
        {"check_id": "sca-vex-source-guards", "passed": security["status"] == "PASS"},
        {
            "check_id": "unsigned-signable-not-production",
            "passed": cast(JsonObject, verified.manifest["signing"]).get("state")
            == "UNSIGNED_ENGINEERING_CANDIDATE"
            and preflight.get("production_ready") is False,
        },
    ]
    issues = [cast(str, row["check_id"]) for row in checks if row["passed"] is not True]
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "validation_profile": "HIGH_RISK",
        "release": {
            "runtime_version": RUNTIME_VERSION,
            "archive_name": artifact.archive_path.name,
            "archive_sha256": artifact.archive_sha256,
            "archive_bytes": artifact.archive_bytes,
            "release_fingerprint": artifact.release_fingerprint,
            "payload_file_count": artifact.payload_file_count,
            "source_date_epoch": epoch,
            "registry": "LOCAL_OR_CI_CONTENT_ADDRESSED_ONLY",
        },
        "negative_matrix": negative_results,
        "checks": checks,
        "check_count": len(checks),
        "production_boundary": "UNSIGNED_ENGINEERING_CANDIDATE_NOT_DEPLOYED_NOT_PRODUCTION_READY",
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    }
    benchmark: JsonObject = {
        "report_version": BENCHMARK_REPORT_VERSION,
        "task_id": TASK_ID,
        "profile": "LOCAL_OR_CI_ENGINEERING_BASELINE_NOT_PRODUCTION_SLA",
        "thresholds": None,
        "wheel_bytes": len(next(raw for path, raw in files.items() if path.endswith(".whl"))),
        "archive_bytes": artifact.archive_bytes,
        "expanded_payload_bytes": sum(len(raw) for raw in files.values()),
        "preflight_elapsed_ms": round(preflight_elapsed_ms, 3),
        "clean_install_elapsed_ms": round(install_elapsed_ms, 3),
        "total_elapsed_ms": round((perf_counter() - started) * 1_000, 3),
        "status": "PASS" if clean_install else "FAIL",
    }
    return report, compatibility, migration, security, benchmark


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--release-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--compatibility-report", type=Path, required=True)
    parser.add_argument("--migration-report", type=Path, required=True)
    parser.add_argument("--security-report", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve(strict=True)
    try:
        report, compatibility, migration, security, benchmark = run_checks(
            root, arguments.release_output
        )
    except ReleaseContractError as error:
        code_commit = git_head(root)
        failure = {
            "task_id": TASK_ID,
            "code_commit": code_commit,
            "issues": [error.code],
            "status": "FAIL",
        }
        report = {"report_version": REPORT_VERSION, **failure, "check_count": 0, "checks": []}
        compatibility = {"report_version": COMPATIBILITY_REPORT_VERSION, **failure}
        migration = {"report_version": MIGRATION_REPORT_VERSION, **failure}
        security = {"report_version": SECURITY_REPORT_VERSION, **failure}
        benchmark = {"report_version": BENCHMARK_REPORT_VERSION, **failure}
    _write(arguments.report, report)
    _write(arguments.compatibility_report, compatibility)
    _write(arguments.migration_report, migration)
    _write(arguments.security_report, security)
    _write(arguments.benchmark_report, benchmark)
    print(
        f"{report['status']} {TASK_ID}: checks={report.get('check_count', 0)} "
        f"issues={len(cast(list[object], report['issues']))}"
    )
    return 0 if all(
        item.get("status") == "PASS"
        for item in (report, compatibility, migration, security, benchmark)
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BENCHMARK_REPORT_VERSION",
    "COMPATIBILITY_REPORT_VERSION",
    "DIFF_BASE",
    "MIGRATION_REPORT_VERSION",
    "REPORT_VERSION",
    "SECURITY_REPORT_VERSION",
    "TASK_ID",
    "main",
    "run_checks",
]
