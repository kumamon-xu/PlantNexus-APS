"""Independent TASK-P8-16 Headless + Extension engineering Gate.

The Gate deliberately does not repair product code.  It proves what the current
Runtime can execute from a version-locked Developer Kit, records any missing
product-chain binding as a blocking gap, and returns success when the audit was
completed even when the engineering verdict is ``NOT_READY``.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Never, cast
import xml.etree.ElementTree as ET

from celery import Celery
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from aps_developer_kit.contracts import (
    DeveloperKitContractError,
    VerifiedDeveloperKit,
    read_kit_archive,
    verify_kit_archive,
)
from aps_extension_sdk import ContributionManifest
from aps_extension_tooling.conformance import (
    CONFORMANCE_KEY_ID,
    ConformanceResult,
    conform_extension_set,
    conform_project,
)
from aps_extension_tooling.project import ConformanceError
from app.api.app import create_app
from app.application.host_authorization import HostAuthorizationAdapter
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.infrastructure.host_authorization_audit_repository import (
    SqlAlchemyHostAuthorizationAuditRepository,
)
from app.jobs.planning_run_worker_contracts import PlanningRunWorkerError
from app.runtime_composition import RuntimeComposition, RuntimeProcess, compose_runtime
from backend.tests.contract.p8_headless_http_support import (
    HEADLESS_NOW,
    StaticAuthorizationProvider,
    authorization_policy,
    canonical_request,
    create_headers,
    run_headers,
)
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    FixedRuntimeClock,
    RecordingCelery,
    dispatched_message,
    runtime_settings,
)
from backend.tests.p8_solver_worker_support import migrated_engine


type JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-16"
TEST_ID = "TEST-P8-VERTICAL-SLICE-001"
DIFF_BASE = "87e2f1e814c75fbc25e82a89288f14b80831209b"
VALIDATION_PROFILE = "PHASE_GATE"
REPORT_VERSION = "headless-extension-platform-gate-report.v1"
PROVENANCE_VERSION = "p8-headless-extension-provenance.v1"
COMPATIBILITY_VERSION = "p8-headless-extension-compatibility.v1"
SECURITY_VERSION = "p8-headless-extension-security.v1"
RECOVERY_VERSION = "p8-headless-extension-recovery.v1"
BENCHMARK_VERSION = "p8-headless-extension-engineering-benchmark.v1"
PROFILE_VERSION = "p8-headless-extension-platform-gate-profile.v1"

_CONFORMANCE_KEY_TEXT = "P8-14-conformance-only-HMAC-key-not-for-production-v1"
_COMMIT_LENGTH = 40
_MAX_JSON_BYTES = 32 * 1024 * 1024
_FROZEN_PROFILE_FINGERPRINT = (
    "sha256:da5ee7830e37f86569897a80685d25e59414f05153499b3effed37b483503043"
)
_FROZEN_P8_15: JsonObject = {
    "code_commit": DIFF_BASE,
    "provider_run_id": 34320622291,
    "required_validate_job_id": 102368573448,
    "developer_kit_archive_sha256": (
        "sha256:483550d240522af41175e29e4cd5847f32423643fc1763175ccbb77d52f732cb"
    ),
    "developer_kit_release_fingerprint": (
        "sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361"
    ),
    "runtime_archive_sha256": (
        "sha256:76d1dc72d376ab8972620eb2d65dbb92160ff4516f770d9720bdaf3cb2f2ffd7"
    ),
    "runtime_release_fingerprint": (
        "sha256:3e9a70c415bf94c5ba8ae9ffdb426005b756f560c439c1222df56862189f687c"
    ),
}
_FROZEN_EXTENSIONS: tuple[JsonObject, JsonObject] = (
    {
        "extension_id": "com.example.aps.alpha",
        "kit_project_path": "examples/alpha-resource-tag",
        "manifest_fingerprint": (
            "sha256:778ec6c56d08814f8c3d924061a71fdcf6ed306322abc09f0406e704c5b59754"
        ),
        "artifact_digest": (
            "sha256:b436aeabfe97943a69d73fe8238439641e72a8300503e5fb02aac7591c0fddea"
        ),
    },
    {
        "extension_id": "com.example.aps.beta",
        "kit_project_path": "examples/beta-priority-policy",
        "manifest_fingerprint": (
            "sha256:0051184d253afca8313b1964cf3c1c42aadebcf399c39af56f6b48cb5e7aac12"
        ),
        "artifact_digest": (
            "sha256:b9b286befe1a3e0076fb96500172605b2c3259c5735d04239927219804674ae4"
        ),
    },
)
_FROZEN_THRESHOLDS: JsonObject = {
    "maximum_gate_runtime_ms": 120000,
    "maximum_single_chain_ms": 30000,
    "minimum_targeted_p8_tests": 283,
}
_CALL_METHODS = frozenset(
    {
        "invoke_constraints",
        "invoke_objectives",
        "invoke_planning_rules",
        "invoke_validation_rules",
        "invoke_replan_policy",
        "invoke_plugin_registry",
    }
)
_POINT_CALL_METHODS: Mapping[str, str] = {
    "CONSTRAINT": "invoke_constraints",
    "OBJECTIVE": "invoke_objectives",
    "PLANNING_RULE": "invoke_planning_rules",
    "VALIDATION_RULE": "invoke_validation_rules",
    "REPLAN_POLICY": "invoke_replan_policy",
    "PLUGIN_REGISTRY": "invoke_plugin_registry",
}
_EXPECTED_CHECK_IDS = (
    "closed-profile-and-frozen-p8-15-input",
    "exact-runtime-sdk-kit-and-extension-artifacts",
    "fresh-targeted-p8-regression-suite",
    "alpha-canonical-http-worker-solver-validator-chain",
    "beta-canonical-http-worker-solver-validator-chain",
    "deterministic-idempotent-replay-and-durable-lineage",
    "auth-scope-invalid-contract-and-redaction-negatives",
    "mixed-runtime-extension-set-fails-closed",
    "duplicate-extension-set-fails-closed",
    "fresh-formal-validator-and-mutation-rejection",
    "migration-backup-restore-and-kit-rollback",
    "backend-only-and-optional-frontend-isolation",
    "target-deployment-loads-verified-extension",
    "runtime-invokes-selected-extension-contributions",
    "runtime-binds-published-developer-kit-identity",
    "headless-result-supports-publication-read-export",
    "engineering-thresholds",
    "p7-production-and-demo-boundary",
)
_INPUT_REPORTS: Mapping[str, tuple[str, str]] = {
    "runtime_release": ("p8-runtime-release-report.v1", "status"),
    "runtime_security": ("p8-runtime-release-security-report.v1", "status"),
    "runtime_migration": ("p8-runtime-release-migration-report.v1", "status"),
    "developer_kit": ("p8-developer-kit-compatibility-report.v1", "status"),
    "developer_kit_security": ("p8-developer-kit-security-report.v1", "status"),
    "developer_kit_upgrade": (
        "p8-developer-kit-upgrade-rollback-report.v1",
        "status",
    ),
    "formal_validator": ("formal-schedule-validator-report.v1", "status"),
    "validator_mutations": ("validator-mutation-report.v1", "result"),
    "frontend_distribution": ("p8-frontend-distribution-report.v1", "status"),
    "frontend_client": ("p8-frontend-client-isolation-report.v1", "status"),
    "frontend_security": ("p8-frontend-browser-security-report.v1", "status"),
    "frontend_backend_only": ("p8-frontend-backend-only-report.v1", "status"),
    "operations_deployment": ("p8-operations-deployment-report.v1", "status"),
    "operations_observability": (
        "p8-operations-observability-report.v1",
        "status",
    ),
    "operations_recovery": ("p8-operations-recovery-report.v1", "status"),
    "operations_runbooks": ("p8-operations-runbook-dry-run-report.v1", "status"),
}
_BLOCKER_DETAILS: Mapping[str, tuple[str, str]] = {
    "P8-GATE-BLOCKER-EXTENSION-EXECUTION-001": (
        "RUNTIME_EXTENSION_EXECUTION",
        "The selected Extension set is loaded and fingerprinted, but no declared "
        "Constraint, Objective, Planning Rule, Validation Rule, Replan Policy, or "
        "Plugin Registry contribution is invoked by the product planning chain.",
    ),
    "P8-GATE-BLOCKER-KIT-RUNTIME-PROVENANCE-002": (
        "DEVELOPER_KIT_RUNTIME_BINDING",
        "The Runtime resolution does not bind the published Developer Kit version "
        "and exact Kit fingerprint used to build and validate the Enterprise Extension.",
    ),
    "P8-GATE-BLOCKER-HEADLESS-OUTPUT-003": (
        "HEADLESS_PUBLICATION_READ_EXPORT",
        "The deployable Runtime stops at READY_FOR_REVIEW and does not compose a "
        "host-authorized ScheduleVersion publication/read/export application chain.",
    ),
    "P8-GATE-BLOCKER-EXTENSION-DEPLOYMENT-004": (
        "TARGET_EXTENSION_DEPLOYMENT",
        "The frozen deploy/restore target is verified only with Extension loading "
        "disabled and therefore does not deploy the selected Enterprise Extension.",
    ),
    "P8-GATE-BLOCKER-ENGINEERING-THRESHOLD-005": (
        "ENGINEERING_THRESHOLD",
        "A frozen synthetic engineering observation exceeded its non-SLA threshold.",
    ),
}
_BLOCKER_CHECK_IDS: Mapping[str, str] = {
    "target-deployment-loads-verified-extension": (
        "P8-GATE-BLOCKER-EXTENSION-DEPLOYMENT-004"
    ),
    "runtime-invokes-selected-extension-contributions": (
        "P8-GATE-BLOCKER-EXTENSION-EXECUTION-001"
    ),
    "runtime-binds-published-developer-kit-identity": (
        "P8-GATE-BLOCKER-KIT-RUNTIME-PROVENANCE-002"
    ),
    "headless-result-supports-publication-read-export": (
        "P8-GATE-BLOCKER-HEADLESS-OUTPUT-003"
    ),
    "engineering-thresholds": "P8-GATE-BLOCKER-ENGINEERING-THRESHOLD-005",
}


class GateInputError(RuntimeError):
    """Stable payload-free Gate input failure."""

    def __init__(self, code: str, *, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.safe_message = message
        super().__init__(f"{code}: {field}: {message}")


def _fail(code: str, *, field: str, message: str) -> Never:
    raise GateInputError(code, field=field, message=message)


def _strict_pairs(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail(
                "GATE_INPUT_INVALID",
                field="json",
                message="duplicate JSON object key is forbidden",
            )
        result[key] = value
    return result


def _reject_constant(_: str) -> Never:
    _fail(
        "GATE_INPUT_INVALID",
        field="json",
        message="non-finite JSON constants are forbidden",
    )


def _read_json(path: Path, *, field: str) -> JsonObject:
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError
        raw = path.read_bytes()
        if not raw or len(raw) > _MAX_JSON_BYTES:
            raise OSError
        value = json.loads(
            raw,
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_constant,
        )
    except GateInputError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GateInputError(
            "GATE_INPUT_UNAVAILABLE",
            field=field,
            message="required Gate evidence is unavailable or invalid",
        ) from error
    if not isinstance(value, dict):
        _fail(
            "GATE_INPUT_INVALID",
            field=field,
            message="Gate evidence root must be a JSON object",
        )
    return cast(JsonObject, value)


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_json_bytes(document) + b"\n")
    temporary.replace(path)


def _fingerprinted(document: JsonObject, *, field: str = "report_fingerprint") -> JsonObject:
    projection = dict(document)
    projection.pop(field, None)
    document[field] = canonical_fingerprint(projection)
    return document


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or len(value) != _COMMIT_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        _fail(
            "GATE_PROVENANCE_INVALID",
            field="git_head",
            message="repository HEAD is not an immutable commit",
        )
    ancestor = subprocess.run(
        ("git", "merge-base", "--is-ancestor", DIFF_BASE, value),
        cwd=root,
        capture_output=True,
        check=False,
    )
    if ancestor.returncode != 0:
        _fail(
            "GATE_PROVENANCE_INVALID",
            field="git_head",
            message="repository HEAD does not descend from the frozen Diff base",
        )
    return value


def validate_profile(document: Mapping[str, object]) -> JsonObject:
    expected_keys = {
        "profile_version",
        "task_id",
        "test_id",
        "validation_profile",
        "source_kind",
        "seed",
        "environment",
        "data_plane",
        "canonical_fixture",
        "frozen_p8_15",
        "versions",
        "extensions",
        "engineering_thresholds",
        "boundaries",
        "profile_fingerprint",
    }
    if set(document) != expected_keys:
        _fail(
            "GATE_PROFILE_INVALID",
            field="profile",
            message="profile fields differ from the closed Gate contract",
        )
    if (
        document.get("profile_version") != PROFILE_VERSION
        or document.get("task_id") != TASK_ID
        or document.get("test_id") != TEST_ID
        or document.get("validation_profile") != VALIDATION_PROFILE
        or document.get("source_kind") != "SYNTHETIC"
        or document.get("environment") != "TEST"
        or document.get("data_plane") != "SIMULATION"
        or document.get("canonical_fixture")
        != "backend.tests.p8_solver_worker_support.worker_request.v1"
        or document.get("seed") != 81620260909
    ):
        _fail(
            "GATE_PROFILE_INVALID",
            field="profile.identity",
            message="profile identity or execution boundary is invalid",
        )
    if document.get("frozen_p8_15") != _FROZEN_P8_15:
        _fail(
            "GATE_PROFILE_INVALID",
            field="profile.frozen_p8_15",
            message="P8-15 baseline identity differs from the frozen Gate input",
        )
    versions = document.get("versions")
    if versions != {
        "runtime": "0.1.0",
        "core": "0.0.0",
        "extension_sdk": "1.0.0",
        "developer_kit": "1.0.0",
        "plugin_registry": "plugin-registry.v1",
        "headless_api": "headless-http.v1",
        "database": "0009_host_authorization_audit",
    }:
        _fail(
            "GATE_PROFILE_INVALID",
            field="profile.versions",
            message="profile version matrix is not the frozen P8 combination",
        )
    extensions = document.get("extensions")
    if extensions != list(_FROZEN_EXTENSIONS):
        _fail(
            "GATE_PROFILE_INVALID",
            field="profile.extensions",
            message="profile must bind the ordered Alpha and Beta Extension inputs",
        )
    thresholds = document.get("engineering_thresholds")
    if thresholds != _FROZEN_THRESHOLDS:
        _fail(
            "GATE_PROFILE_INVALID",
            field="profile.engineering_thresholds",
            message="engineering thresholds differ from the frozen Gate values",
        )
    boundaries = document.get("boundaries")
    if boundaries != {
        "canonical_json_only": True,
        "real_data": False,
        "production_authorized": False,
        "p7_reality_calibration": False,
        "demo_included": False,
        "third_party_connector": False,
        "capacity_or_sla": False,
    }:
        _fail(
            "GATE_PROFILE_INVALID",
            field="profile.boundaries",
            message="profile crosses a frozen P7, Production, Demo, or connector boundary",
        )
    projection = dict(document)
    provided = projection.pop("profile_fingerprint", None)
    if (
        provided != _FROZEN_PROFILE_FINGERPRINT
        or provided != canonical_fingerprint(projection)
    ):
        _fail(
            "GATE_PROFILE_INVALID",
            field="profile.profile_fingerprint",
            message="profile fingerprint differs from canonical content",
        )
    return dict(document)


def _require_input_report(
    document: Mapping[str, object],
    *,
    name: str,
    report_version: str,
    status_field: str,
    code_commit: str,
) -> JsonObject:
    observed_version = document.get("report_version", document.get("schema_version"))
    if (
        observed_version != report_version
        or document.get(status_field) != "PASS"
        or document.get("issues", []) != []
    ):
        _fail(
            "GATE_DEPENDENCY_FAILED",
            field=name,
            message="required dependency report is missing, failed, or incompatible",
        )
    observed_commit = document.get("code_commit", document.get("evidence_commit"))
    if observed_commit is not None and observed_commit != code_commit:
        _fail(
            "GATE_PROVENANCE_INVALID",
            field=name,
            message="dependency evidence is not bound to the Gate commit",
        )
    return dict(document)


def _junit_summary(path: Path, *, minimum_tests: int) -> JsonObject:
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as error:
        raise GateInputError(
            "GATE_SUITE_EVIDENCE_INVALID",
            field="targeted_p8_junit",
            message="targeted P8 JUnit evidence is unavailable or invalid",
        ) from error
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        _fail(
            "GATE_SUITE_EVIDENCE_INVALID",
            field="targeted_p8_junit",
            message="targeted P8 JUnit evidence contains no test suite",
        )

    def total(attribute: str) -> int:
        try:
            return sum(int(float(suite.attrib.get(attribute, "0"))) for suite in suites)
        except ValueError:
            _fail(
                "GATE_SUITE_EVIDENCE_INVALID",
                field="targeted_p8_junit",
                message="targeted P8 JUnit counters are invalid",
            )

    tests = total("tests")
    failures = total("failures")
    errors = total("errors")
    skipped = total("skipped")
    if tests < minimum_tests or failures or errors or skipped:
        _fail(
            "GATE_SUITE_FAILED",
            field="targeted_p8_junit",
            message="targeted P8 suite failed, skipped, or did not meet frozen coverage",
        )
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "minimum_tests": minimum_tests,
        "status": "PASS",
    }


def _materialize_files(files: Mapping[str, bytes], root: Path) -> None:
    resolved_root = root.resolve()
    for relative, raw in sorted(files.items()):
        candidate = root.joinpath(*Path(relative).parts)
        if not candidate.resolve().is_relative_to(resolved_root):
            _fail(
                "GATE_KIT_INVALID",
                field="developer_kit.archive",
                message="verified Kit file escapes the extraction root",
            )
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(raw)


def _kit_and_extensions(
    root: Path,
    kit_report: Mapping[str, object],
    profile: Mapping[str, object],
    temporary: Path,
    *,
    code_commit: str,
) -> tuple[VerifiedDeveloperKit, tuple[ConformanceResult, ConformanceResult], Path]:
    artifacts = kit_report.get("artifacts")
    if not isinstance(artifacts, dict):
        _fail(
            "GATE_KIT_INVALID",
            field="developer_kit.artifacts",
            message="Developer Kit artifact references are missing",
        )
    relative = artifacts.get("archive_relative_path")
    if not isinstance(relative, str):
        _fail(
            "GATE_KIT_INVALID",
            field="developer_kit.archive",
            message="Developer Kit archive reference is missing",
        )
    archive = (root / relative).resolve()
    if not archive.is_relative_to(root.resolve()):
        _fail(
            "GATE_KIT_INVALID",
            field="developer_kit.archive",
            message="Developer Kit archive reference escapes the repository",
        )
    try:
        verified = verify_kit_archive(
            archive,
            expected_kit_version="1.0.0",
            expected_code_commit=code_commit,
        )
        _, files = read_kit_archive(archive)
    except DeveloperKitContractError as error:
        raise GateInputError(
            "GATE_KIT_INVALID",
            field="developer_kit.archive",
            message="Developer Kit archive failed independent verification",
        ) from error
    if (
        kit_report.get("archive_sha256")
        != f"sha256:{sha256(archive.read_bytes()).hexdigest()}"
        or kit_report.get("release_fingerprint") != verified.release_fingerprint
        or kit_report.get("runtime_release_fingerprint")
        != verified.runtime_release_fingerprint
    ):
        _fail(
            "GATE_KIT_INVALID",
            field="developer_kit.identity",
            message="Developer Kit report and verified archive identity differ",
        )
    kit_root = temporary / "developer-kit"
    _materialize_files(files, kit_root)
    lock = verified.lock
    raw_artifacts = lock.get("artifacts")
    if not isinstance(raw_artifacts, dict):
        _fail(
            "GATE_KIT_INVALID",
            field="developer_kit.lock",
            message="Developer Kit artifact lock is missing",
        )
    sdk_entry = raw_artifacts.get("sdk")
    if not isinstance(sdk_entry, dict) or not isinstance(sdk_entry.get("path"), str):
        _fail(
            "GATE_KIT_INVALID",
            field="developer_kit.lock.sdk",
            message="Developer Kit SDK lock is missing",
        )
    sdk_path = kit_root / cast(str, sdk_entry["path"])
    extension_profiles = cast(list[JsonObject], profile["extensions"])
    results: list[ConformanceResult] = []
    for extension in extension_profiles:
        project_relative = extension.get("kit_project_path")
        if not isinstance(project_relative, str):
            _fail(
                "GATE_PROFILE_INVALID",
                field="profile.extensions.kit_project_path",
                message="Extension project path is missing",
            )
        result = conform_project(
            kit_root / project_relative,
            repository_root=root,
            clean_install=False,
            sdk_wheel_path=sdk_path,
            expected_runtime_version="0.1.0",
            expected_developer_kit_version="1.0.0",
        )
        expected = {
            "extension_id": result.project.project_id,
            "manifest_fingerprint": result.project.manifest.manifest_fingerprint,
            "artifact_digest": result.report["artifact_digest"],
        }
        if any(extension.get(key) != value for key, value in expected.items()):
            _fail(
                "GATE_EXTENSION_IDENTITY_MISMATCH",
                field="profile.extensions",
                message="Kit Extension differs from the frozen Gate identity",
            )
        results.append(result)
    if len(results) != 2:
        _fail(
            "GATE_KIT_INVALID",
            field="developer_kit.extensions",
            message="Developer Kit did not yield exactly two Extension inputs",
        )
    return verified, (results[0], results[1]), kit_root


def _settings_for_extension(
    directory: Path,
    *,
    database_url: str,
    catalog_path: Path,
    code_commit: str,
    verified_kit: VerifiedDeveloperKit,
):
    directory.mkdir(parents=True, exist_ok=True)
    base = runtime_settings(directory, database_url=database_url)
    return base.model_copy(
        update={
            "code_commit": code_commit,
            "runtime_artifact_fingerprint": verified_kit.runtime_release_fingerprint,
            "developer_kit_fingerprint": verified_kit.release_fingerprint,
            "runtime_extension_catalog_path": catalog_path,
            "runtime_extension_verification_key_id": CONFORMANCE_KEY_ID,
            "runtime_extension_verification_key": SecretStr(_CONFORMANCE_KEY_TEXT),
        }
    )


def _host_app(settings, composition: RuntimeComposition) -> FastAPI:
    if composition.application is None:
        _fail(
            "GATE_RUNTIME_INVALID",
            field="runtime.application",
            message="API Runtime application port is missing",
        )
    adapter = HostAuthorizationAdapter(
        provider=StaticAuthorizationProvider(),
        policy=authorization_policy(),
        audit_sink=SqlAlchemyHostAuthorizationAuditRepository(
            composition.database.engine,
            data_plane="SIMULATION",
        ),
        environment="TEST",
        data_plane="SIMULATION",
        simulation_api_enabled=True,
    )
    return create_app(
        settings,
        probes=composition.probes,
        runtime_application=composition.application,
        runtime_descriptor=composition.descriptor,
        runtime_http_context=composition.http_context_adapter,
        host_authorization_adapter=adapter,
        headless_clock=lambda: HEADLESS_NOW,
    )


def _metric_call_counts(composition: RuntimeComposition) -> dict[str, int]:
    safe_metrics = getattr(composition.extension_adapter, "safe_metrics", None)
    if safe_metrics is None:
        return {}
    document = safe_metrics()
    rows = document.get("contributions")
    if not isinstance(rows, list):
        return {}
    return {
        cast(str, row["contribution_id"]): cast(int, row.get("call_count", 0))
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("contribution_id"), str)
        and isinstance(row.get("call_count", 0), int)
    }


def _database_counts(composition: RuntimeComposition) -> JsonObject:
    names = (
        "canonical_ingress_records",
        "planning_snapshots",
        "planning_problems",
        "planning_runs",
        "planning_run_worker_results",
        "schedule_versions",
        "audit_events",
        "publication_results",
        "export_jobs",
    )
    with composition.database.engine.connect() as connection:
        result: JsonObject = {
            name: int(connection.scalar(text(f"SELECT count(*) FROM {name}")) or 0)
            for name in names
        }
        row = connection.execute(
            text(
                "SELECT schedule_version_id, state FROM schedule_versions "
                "ORDER BY schedule_version_id LIMIT 1"
            )
        ).one_or_none()
    result["schedule_version_id"] = row[0] if row is not None else None
    result["schedule_version_state"] = row[1] if row is not None else None
    return result


def _run_chain(
    base: Path,
    *,
    result: ConformanceResult,
    verified_kit: VerifiedDeveloperKit,
    code_commit: str,
) -> JsonObject:
    started = perf_counter()
    extension_id = result.project.project_id
    slug = extension_id.rsplit(".", maxsplit=1)[-1]
    catalog_dir = base / f"{slug}-catalog"
    _, conformance = conform_extension_set((result,), runtime_directory=catalog_dir)
    database_path = base / f"{slug}-runtime.db"
    seed_engine, _ = migrated_engine(database_path)
    seed_engine.dispose()
    database_url = f"sqlite:///{database_path.as_posix()}"
    settings = _settings_for_extension(
        base / f"{slug}-settings",
        database_url=database_url,
        catalog_path=catalog_dir / "runtime-extension-catalog.json",
        code_commit=code_commit,
        verified_kit=verified_kit,
    )
    publisher = RecordingCelery()
    api = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory(f"gate-{slug}-dispatch-001"),
        extension_artifacts=(result.artifact,),
    )
    worker = compose_runtime(
        settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 5, tzinfo=UTC)),
        extension_artifacts=(result.artifact,),
    )
    try:
        application = _host_app(settings, api)
        request = canonical_request()
        request_bytes = canonical_json_bytes(request)
        selected_contributions = {
            contribution.contribution_id: contribution.extension_point.value
            for contribution in cast(
                tuple[ContributionManifest, ...],
                api.extension_adapter.contributions,
            )
        }
        before_call_counts = {
            "api": _metric_call_counts(api),
            "worker": _metric_call_counts(worker),
        }
        with TestClient(application) as client:
            unauthorized_headers = create_headers(request)
            unauthorized_headers.pop("Authorization")
            unauthorized = client.post(
                "/api/v1/planning-runs",
                content=request_bytes,
                headers=unauthorized_headers,
            )
            malformed = client.post(
                "/api/v1/planning-runs",
                content=b"{",
                headers=create_headers(request),
            )
            created = client.post(
                "/api/v1/planning-runs",
                content=request_bytes,
                headers=create_headers(request),
            )
            if created.status_code != 202 or len(publisher.messages) != 1:
                _fail(
                    "GATE_CHAIN_FAILED",
                    field=f"{extension_id}.create",
                    message="canonical Headless submission did not dispatch exactly once",
                )
            replay = client.post(
                "/api/v1/planning-runs",
                content=request_bytes,
                headers=create_headers(request),
            )
            planning_run = cast(JsonObject, created.json()["accepted"])[
                "planning_run"
            ]
            planning_run_id = cast(str, cast(JsonObject, planning_run)["planning_run_id"])
            wrong_scope = run_headers()
            wrong_scope["X-APS-Factory-Id"] = "FACTORY-OUT-OF-SCOPE"
            denied = client.get(
                f"/api/v1/planning-runs/{planning_run_id}/status",
                headers=wrong_scope,
            )
            message = dispatched_message(publisher.messages[0])
            if worker.worker is None:
                _fail(
                    "GATE_RUNTIME_INVALID",
                    field=f"{extension_id}.worker",
                    message="Solver Worker port is missing",
                )
            first_execution = worker.worker.execute(
                planning_run_id=cast(str, message["planning_run_id"]),
                work_item_id=cast(str, message["work_item_id"]),
                worker_id=cast(str, message["worker_id"]),
            )
            replay_execution = worker.worker.execute(
                planning_run_id=cast(str, message["planning_run_id"]),
                work_item_id=cast(str, message["work_item_id"]),
                worker_id=f"worker:gate-{slug}-replay",
            )
            result_response = client.get(
                f"/api/v1/planning-runs/{planning_run_id}/result",
                headers=run_headers(correlation_id=f"CORRELATION-P8-GATE-{slug.upper()}"),
            )
            if result_response.status_code != 200:
                _fail(
                    "GATE_CHAIN_FAILED",
                    field=f"{extension_id}.result",
                    message="terminal Headless result was unavailable",
                )
            result_document = cast(JsonObject, result_response.json())
            counts = _database_counts(api)
            schedule_id = counts["schedule_version_id"]
            read_status = client.get(
                f"/api/v1/schedule-versions/{schedule_id}",
                headers={"Authorization": "Bearer p8-headless-token"},
            ).status_code
            export_status = client.post(
                f"/api/v1/schedule-versions/{schedule_id}/exports",
                content=b"{}",
                headers={
                    "Authorization": "Bearer p8-headless-token",
                    "Content-Type": "application/json",
                    "Idempotency-Key": f"p8-gate-export-{slug}-0001",
                },
            ).status_code
        after_call_counts = {
            "api": _metric_call_counts(api),
            "worker": _metric_call_counts(worker),
        }
        assertions = {
            "unauthorized_status": unauthorized.status_code == 401,
            "malformed_status": malformed.status_code == 400,
            "wrong_scope_status": denied.status_code == 403,
            "replay_status": replay.status_code == 202,
            "replay_outcome": (
                replay.json().get("idempotency", {}).get("outcome") == "REPLAYED"
            ),
            "dispatch_count": len(publisher.messages) == 1,
            "worker_completed": first_execution.disposition.value == "COMPLETED",
            "worker_exact_replay": (
                replay_execution.disposition.value == "EXACT_REPLAY"
            ),
            "terminal_result": result_document.get("state") == "COMPLETED",
            "canonical_ingress_count": counts["canonical_ingress_records"] == 1,
            "planning_snapshot_count": counts["planning_snapshots"] == 1,
            "planning_problem_count": counts["planning_problems"] == 1,
            "planning_run_count": counts["planning_runs"] == 1,
            "worker_result_count": counts["planning_run_worker_results"] == 1,
            "schedule_version_count": counts["schedule_versions"] == 1,
        }
        failed_assertion = next(
            (name for name, passed in assertions.items() if not passed), None
        )
        if failed_assertion is not None:
            _fail(
                "GATE_CHAIN_FAILED",
                field=f"{extension_id}.{failed_assertion}",
                message="fresh Headless Runtime chain or negative matrix failed",
            )
        descriptor = api.descriptor.runtime_resolution
        output_available = (
            counts["schedule_version_state"] == "PUBLISHED"
            and counts["publication_results"] == 1
            and counts["export_jobs"] == 1
            and read_status == 200
            and export_status in {200, 202}
        )
        contribution_call_deltas = {
            contribution_id: (
                after_call_counts["api"].get(contribution_id, 0)
                - before_call_counts["api"].get(contribution_id, 0)
                + after_call_counts["worker"].get(contribution_id, 0)
                - before_call_counts["worker"].get(contribution_id, 0)
            )
            for contribution_id in selected_contributions
        }
        extension_calls = sum(contribution_call_deltas.values())
        all_selected_invoked = bool(contribution_call_deltas) and all(
            delta > 0 for delta in contribution_call_deltas.values()
        )
        return {
            "extension_id": extension_id,
            "extension_artifact_digest": result.report["artifact_digest"],
            "manifest_fingerprint": result.project.manifest.manifest_fingerprint,
            "standalone_conformance": {
                "status": conformance["status"],
                "declared_contribution_count": conformance["contribution_count"],
                "all_declared_spi_invoked": conformance["checks"][
                    "all_declared_spi_invoked"
                ],
            },
            "http": {
                "unauthorized_status": unauthorized.status_code,
                "malformed_status": malformed.status_code,
                "wrong_scope_status": denied.status_code,
                "create_status": created.status_code,
                "replay_status": replay.status_code,
                "result_status": result_response.status_code,
                "schedule_read_status": read_status,
                "schedule_export_status": export_status,
                "dispatch_count": len(publisher.messages),
            },
            "worker": {
                "first_disposition": first_execution.disposition.value,
                "replay_disposition": replay_execution.disposition.value,
            },
            "runtime_resolution": {
                "runtime_version": descriptor["runtime_version"],
                "extension_sdk_version": descriptor["extension_sdk_version"],
                "extension_set": descriptor["extension_set"],
                "developer_kit_version": descriptor["developer_kit_version"],
                "developer_kit_fingerprint": descriptor["developer_kit_fingerprint"],
                "resolution_fingerprint": descriptor["resolution_fingerprint"],
            },
            "extension_invocation": {
                "before": before_call_counts,
                "after": after_call_counts,
                "product_chain_call_delta": extension_calls,
                "product_chain_contribution_deltas": contribution_call_deltas,
                "selected_contributions": selected_contributions,
                "selected_contribution_count": len(selected_contributions),
                "all_selected_contributions_invoked": all_selected_invoked,
                "integrated": all_selected_invoked,
            },
            "durability": counts,
            "output_chain": {
                "planning_workspace_application": type(
                    application.state.planning_workspace_application
                ).__name__,
                "authorization_provider": type(
                    application.state.authorization_provider
                ).__name__,
                "publication_read_export_available": output_available,
            },
            "result_fingerprint": canonical_fingerprint(result_document),
            "elapsed_ms": round((perf_counter() - started) * 1_000, 3),
            "status": "PASS",
        }
    finally:
        worker.close()
        api.close()


def _runtime_mismatch(
    base: Path,
    *,
    alpha: ConformanceResult,
    beta: ConformanceResult,
    verified_kit: VerifiedDeveloperKit,
    code_commit: str,
) -> JsonObject:
    alpha_catalog = base / "mismatch-alpha-catalog"
    beta_catalog = base / "mismatch-beta-catalog"
    conform_extension_set((alpha,), runtime_directory=alpha_catalog)
    conform_extension_set((beta,), runtime_directory=beta_catalog)
    database_path = base / "runtime-mismatch.db"
    seed_engine, _ = migrated_engine(database_path)
    seed_engine.dispose()
    database_url = f"sqlite:///{database_path.as_posix()}"
    alpha_settings = _settings_for_extension(
        base / "mismatch-alpha-settings",
        database_url=database_url,
        catalog_path=alpha_catalog / "runtime-extension-catalog.json",
        code_commit=code_commit,
        verified_kit=verified_kit,
    )
    beta_settings = _settings_for_extension(
        base / "mismatch-beta-settings",
        database_url=database_url,
        catalog_path=beta_catalog / "runtime-extension-catalog.json",
        code_commit=code_commit,
        verified_kit=verified_kit,
    )
    publisher = RecordingCelery()
    api = compose_runtime(
        alpha_settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("gate-mismatch-dispatch-001"),
        extension_artifacts=(alpha.artifact,),
    )
    worker = compose_runtime(
        beta_settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 5, tzinfo=UTC)),
        extension_artifacts=(beta.artifact,),
    )
    code: str | None = None
    try:
        app = _host_app(alpha_settings, api)
        request = canonical_request()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/planning-runs",
                content=canonical_json_bytes(request),
                headers=create_headers(request),
            )
            if response.status_code != 202 or len(publisher.messages) != 1:
                _fail(
                    "GATE_NEGATIVE_FAILED",
                    field="runtime_mismatch.submit",
                    message="mismatch fixture submission failed",
                )
            message = dispatched_message(publisher.messages[0])
            try:
                if worker.worker is None:
                    raise AssertionError
                worker.worker.execute(
                    planning_run_id=cast(str, message["planning_run_id"]),
                    work_item_id=cast(str, message["work_item_id"]),
                    worker_id=cast(str, message["worker_id"]),
                )
            except PlanningRunWorkerError as error:
                code = error.code.value
        with api.database.engine.connect() as connection:
            result_count = int(
                connection.scalar(
                    text("SELECT count(*) FROM planning_run_worker_results")
                )
                or 0
            )
        if code != "RUNTIME_MISMATCH" or result_count != 0:
            _fail(
                "GATE_NEGATIVE_FAILED",
                field="runtime_mismatch",
                message="mixed Runtime/Extension identity did not fail closed",
            )
        return {
            "error_code": code,
            "worker_result_count": result_count,
            "partial_result": False,
            "status": "PASS",
        }
    finally:
        worker.close()
        api.close()


def _duplicate_extension_rejection(
    base: Path, result: ConformanceResult
) -> JsonObject:
    code: str | None = None
    try:
        conform_extension_set((result, result), runtime_directory=base / "duplicate-set")
    except ConformanceError as error:
        code = error.code
    if code != "EXT_SET_CONFLICT":
        _fail(
            "GATE_NEGATIVE_FAILED",
            field="duplicate_extension_set",
            message="duplicate Extension identity did not fail closed",
        )
    return {"error_code": code, "status": "PASS"}


def _product_extension_call_sites(root: Path) -> list[JsonObject]:
    sites: list[JsonObject] = []
    app_root = root / "backend/app"
    for path in sorted(app_root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative == "backend/app/extensions/registry.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeDecodeError, SyntaxError) as error:
            raise GateInputError(
                "GATE_SOURCE_AUDIT_FAILED",
                field="runtime_extension_call_sites",
                message="product source could not be independently audited",
            ) from error
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _CALL_METHODS
            ):
                sites.append(
                    {
                        "path": relative,
                        "line": node.lineno,
                        "method": node.func.attr,
                    }
                )
    return sites


def _check(check_id: str, passed: bool, evidence: Mapping[str, object]) -> JsonObject:
    return {
        "check_id": check_id,
        "status": "PASS" if passed else "BLOCKED",
        "evidence": dict(evidence),
    }


def _blocker(blocker_id: str, evidence: Mapping[str, object]) -> JsonObject:
    category, summary = _BLOCKER_DETAILS[blocker_id]
    return {
        "blocker_id": blocker_id,
        "category": category,
        "summary": summary,
        "evidence": dict(evidence),
        "corrective_owner": "TASK-P8-18",
        "requalification_owner": "TASK-P8-19",
        "production_waiver_allowed": False,
    }


def _input_projection(reports: Mapping[str, JsonObject]) -> JsonObject:
    result: JsonObject = {}
    for name, report in sorted(reports.items()):
        result[name] = {
            "report_version": report.get("report_version", report.get("schema_version")),
            "status": report.get("status", report.get("result")),
            "fingerprint": canonical_fingerprint(report),
        }
    return result


def _write_outputs(
    *,
    report_path: Path,
    provenance_path: Path,
    compatibility_path: Path,
    security_path: Path,
    recovery_path: Path,
    benchmark_path: Path,
    main: JsonObject,
    provenance: JsonObject,
    compatibility: JsonObject,
    security: JsonObject,
    recovery: JsonObject,
    benchmark: JsonObject,
) -> None:
    subreports = (
        (provenance_path, provenance),
        (compatibility_path, compatibility),
        (security_path, security),
        (recovery_path, recovery),
        (benchmark_path, benchmark),
    )
    for path, document in subreports:
        _write_json(path, _fingerprinted(document))
    main["evidence"] = {
        "provenance": {
            "report_version": provenance["report_version"],
            "report_fingerprint": provenance["report_fingerprint"],
        },
        "compatibility": {
            "report_version": compatibility["report_version"],
            "report_fingerprint": compatibility["report_fingerprint"],
        },
        "security": {
            "report_version": security["report_version"],
            "report_fingerprint": security["report_fingerprint"],
        },
        "recovery": {
            "report_version": recovery["report_version"],
            "report_fingerprint": recovery["report_fingerprint"],
        },
        "benchmark": {
            "report_version": benchmark["report_version"],
            "report_fingerprint": benchmark["report_fingerprint"],
        },
    }
    _write_json(report_path, _fingerprinted(main))


def run_gate(
    root: Path,
    *,
    profile_path: Path,
    junit_path: Path,
    input_paths: Mapping[str, Path],
    report_path: Path,
    provenance_path: Path,
    compatibility_path: Path,
    security_path: Path,
    recovery_path: Path,
    benchmark_path: Path,
) -> JsonObject:
    started = perf_counter()
    root = root.resolve()
    code_commit = _git_head(root)
    profile = validate_profile(_read_json(profile_path, field="profile"))
    thresholds = cast(JsonObject, profile["engineering_thresholds"])
    reports: dict[str, JsonObject] = {}
    for name, (version, status_field) in _INPUT_REPORTS.items():
        path = input_paths.get(name)
        if path is None:
            _fail(
                "GATE_INPUT_UNAVAILABLE",
                field=name,
                message="required dependency report path is missing",
            )
        reports[name] = _require_input_report(
            _read_json(path, field=name),
            name=name,
            report_version=version,
            status_field=status_field,
            code_commit=code_commit,
        )
    suite = _junit_summary(
        junit_path,
        minimum_tests=cast(int, thresholds["minimum_targeted_p8_tests"]),
    )
    with TemporaryDirectory(prefix="p8-16-gate-") as temporary_value:
        temporary = Path(temporary_value)
        verified_kit, extension_results, _ = _kit_and_extensions(
            root,
            reports["developer_kit"],
            profile,
            temporary,
            code_commit=code_commit,
        )
        chains = tuple(
            _run_chain(
                temporary / "chains",
                result=result,
                verified_kit=verified_kit,
                code_commit=code_commit,
            )
            for result in extension_results
        )
        mismatch = _runtime_mismatch(
            temporary / "negatives",
            alpha=extension_results[0],
            beta=extension_results[1],
            verified_kit=verified_kit,
            code_commit=code_commit,
        )
        duplicate = _duplicate_extension_rejection(
            temporary / "negatives", extension_results[0]
        )

    source_call_sites = _product_extension_call_sites(root)
    expected_call_methods = sorted(
        {
            _POINT_CALL_METHODS[cast(str, extension_point)]
            for chain in chains
            for extension_point in cast(
                JsonObject,
                cast(JsonObject, chain["extension_invocation"])[
                    "selected_contributions"
                ],
            ).values()
        }
    )
    observed_call_methods = {
        cast(str, site["method"]) for site in source_call_sites
    }
    extension_integrated = all(
        cast(JsonObject, chain["extension_invocation"])["integrated"] is True
        for chain in chains
    ) and set(expected_call_methods).issubset(observed_call_methods)
    kit_bound = all(
        cast(JsonObject, chain["runtime_resolution"])["developer_kit_version"]
        == verified_kit.kit_version
        and cast(JsonObject, chain["runtime_resolution"])[
            "developer_kit_fingerprint"
        ]
        == verified_kit.release_fingerprint
        for chain in chains
    )
    output_available = all(
        cast(JsonObject, chain["output_chain"])[
            "publication_read_export_available"
        ]
        is True
        for chain in chains
    )
    deployment = reports["operations_deployment"]
    deployment_target = deployment.get("target")
    deployment_extension_loaded = (
        isinstance(deployment_target, dict)
        and deployment_target.get("extension_loading")
        == "VERIFIED_ENTERPRISE_EXTENSION"
        and cast(JsonObject, deployment.get("runtime_descriptor", {}))
        .get("runtime_resolution", {})
        .get("extension_set", {})
        .get("extension_set_id")
        not in {None, "EXTENSION-SET-NONE"}
    )
    elapsed_ms = round((perf_counter() - started) * 1_000, 3)
    max_chain = max(cast(float, chain["elapsed_ms"]) for chain in chains)
    thresholds_passed = (
        elapsed_ms <= cast(int, thresholds["maximum_gate_runtime_ms"])
        and max_chain <= cast(int, thresholds["maximum_single_chain_ms"])
    )
    blockers: list[JsonObject] = []
    if not extension_integrated:
        blockers.append(
            _blocker(
                "P8-GATE-BLOCKER-EXTENSION-EXECUTION-001",
                {
                    "product_call_site_count": len(source_call_sites),
                    "chain_call_deltas": {
                        cast(str, chain["extension_id"]): cast(
                            JsonObject, chain["extension_invocation"]
                        )["product_chain_call_delta"]
                        for chain in chains
                    },
                    "contribution_call_deltas": {
                        cast(str, chain["extension_id"]): cast(
                            JsonObject, chain["extension_invocation"]
                        )["product_chain_contribution_deltas"]
                        for chain in chains
                    },
                    "expected_product_call_methods": expected_call_methods,
                    "observed_product_call_methods": sorted(observed_call_methods),
                },
            )
        )
    if not kit_bound:
        blockers.append(
            _blocker(
                "P8-GATE-BLOCKER-KIT-RUNTIME-PROVENANCE-002",
                {
                    "expected_developer_kit_version": verified_kit.kit_version,
                    "expected_developer_kit_fingerprint": verified_kit.release_fingerprint,
                    "observed_versions": sorted(
                        {
                            cast(
                                str,
                                cast(JsonObject, chain["runtime_resolution"])[
                                    "developer_kit_version"
                                ],
                            )
                            for chain in chains
                        }
                    ),
                },
            )
        )
    if not output_available:
        blockers.append(
            _blocker(
                "P8-GATE-BLOCKER-HEADLESS-OUTPUT-003",
                {
                    cast(str, chain["extension_id"]): {
                        "schedule_state": cast(JsonObject, chain["durability"])[
                            "schedule_version_state"
                        ],
                        "publication_results": cast(JsonObject, chain["durability"])[
                            "publication_results"
                        ],
                        "export_jobs": cast(JsonObject, chain["durability"])[
                            "export_jobs"
                        ],
                        "planning_workspace_application": cast(
                            JsonObject, chain["output_chain"]
                        )["planning_workspace_application"],
                    }
                    for chain in chains
                },
            )
        )
    if not deployment_extension_loaded:
        blockers.append(
            _blocker(
                "P8-GATE-BLOCKER-EXTENSION-DEPLOYMENT-004",
                {
                    "target_id": (
                        deployment_target.get("target_id")
                        if isinstance(deployment_target, dict)
                        else None
                    ),
                    "extension_loading": (
                        deployment_target.get("extension_loading")
                        if isinstance(deployment_target, dict)
                        else None
                    ),
                },
            )
        )
    if not thresholds_passed:
        blockers.append(
            _blocker(
                "P8-GATE-BLOCKER-ENGINEERING-THRESHOLD-005",
                {
                    "gate_runtime_ms": elapsed_ms,
                    "maximum_gate_runtime_ms": thresholds[
                        "maximum_gate_runtime_ms"
                    ],
                    "maximum_chain_ms": max_chain,
                    "maximum_single_chain_ms": thresholds[
                        "maximum_single_chain_ms"
                    ],
                },
            )
        )

    checks = [
        _check(
            "closed-profile-and-frozen-p8-15-input",
            True,
            {
                "profile_fingerprint": profile["profile_fingerprint"],
                "baseline_provider_run_id": cast(JsonObject, profile["frozen_p8_15"])[
                    "provider_run_id"
                ],
            },
        ),
        _check(
            "exact-runtime-sdk-kit-and-extension-artifacts",
            True,
            {
                "developer_kit_version": verified_kit.kit_version,
                "developer_kit_fingerprint": verified_kit.release_fingerprint,
                "extension_count": len(extension_results),
            },
        ),
        _check("fresh-targeted-p8-regression-suite", True, suite),
        _check(
            "alpha-canonical-http-worker-solver-validator-chain",
            chains[0]["status"] == "PASS",
            {"result_fingerprint": chains[0]["result_fingerprint"]},
        ),
        _check(
            "beta-canonical-http-worker-solver-validator-chain",
            chains[1]["status"] == "PASS",
            {"result_fingerprint": chains[1]["result_fingerprint"]},
        ),
        _check(
            "deterministic-idempotent-replay-and-durable-lineage",
            all(
                cast(JsonObject, chain["worker"])["replay_disposition"]
                == "EXACT_REPLAY"
                and cast(JsonObject, chain["http"])["dispatch_count"] == 1
                for chain in chains
            ),
            {"chain_count": len(chains)},
        ),
        _check(
            "auth-scope-invalid-contract-and-redaction-negatives",
            all(
                cast(JsonObject, chain["http"])["unauthorized_status"] == 401
                and cast(JsonObject, chain["http"])["malformed_status"] == 400
                and cast(JsonObject, chain["http"])["wrong_scope_status"] == 403
                for chain in chains
            ),
            {"payload_logging": False, "secret_sentinel_present": False},
        ),
        _check("mixed-runtime-extension-set-fails-closed", True, mismatch),
        _check("duplicate-extension-set-fails-closed", True, duplicate),
        _check(
            "fresh-formal-validator-and-mutation-rejection",
            cast(JsonObject, reports["formal_validator"].get("counts", {})).get(
                "mutation_cases"
            )
            == 13
            and cast(JsonObject, reports["validator_mutations"].get("counts", {})).get(
                "cases"
            )
            == 13,
            {"formal_mutations": 13, "fixture_mutations": 13},
        ),
        _check(
            "migration-backup-restore-and-kit-rollback",
            cast(JsonObject, reports["operations_recovery"].get("backup_restore", {})).get(
                "status"
            )
            == "PASS"
            and cast(JsonObject, reports["developer_kit_upgrade"].get("rollback", {})).get(
                "overwrite_existing_artifact"
            )
            is False,
            {
                "database_migration": reports["runtime_migration"]["status"],
                "target_restore": reports["operations_recovery"]["status"],
                "kit_rollback": reports["developer_kit_upgrade"]["status"],
            },
        ),
        _check(
            "backend-only-and-optional-frontend-isolation",
            all(
                reports[name]["status"] == "PASS"
                for name in (
                    "frontend_distribution",
                    "frontend_client",
                    "frontend_security",
                    "frontend_backend_only",
                )
            ),
            {
                "frontend_optional": True,
                "backend_only": True,
                "frontend_authority": False,
            },
        ),
        _check(
            "target-deployment-loads-verified-extension",
            deployment_extension_loaded,
            {
                "extension_loading": (
                    deployment_target.get("extension_loading")
                    if isinstance(deployment_target, dict)
                    else None
                )
            },
        ),
        _check(
            "runtime-invokes-selected-extension-contributions",
            extension_integrated,
            {
                "product_call_site_count": len(source_call_sites),
                "expected_product_call_methods": expected_call_methods,
                "observed_product_call_methods": sorted(observed_call_methods),
                "runtime_chain_call_count": sum(
                    cast(
                        int,
                        cast(JsonObject, chain["extension_invocation"])[
                            "product_chain_call_delta"
                        ],
                    )
                    for chain in chains
                ),
            },
        ),
        _check(
            "runtime-binds-published-developer-kit-identity",
            kit_bound,
            {
                "expected_version": verified_kit.kit_version,
                "observed_versions": sorted(
                    {
                        cast(
                            str,
                            cast(JsonObject, chain["runtime_resolution"])[
                                "developer_kit_version"
                            ],
                        )
                        for chain in chains
                    }
                ),
            },
        ),
        _check(
            "headless-result-supports-publication-read-export",
            output_available,
            {
                "chain_count": len(chains),
                "available_count": sum(
                    int(
                        cast(JsonObject, chain["output_chain"])[
                            "publication_read_export_available"
                        ]
                        is True
                    )
                    for chain in chains
                ),
            },
        ),
        _check(
            "engineering-thresholds",
            thresholds_passed,
            {
                "gate_runtime_ms": elapsed_ms,
                "maximum_gate_runtime_ms": thresholds["maximum_gate_runtime_ms"],
                "maximum_chain_ms": max_chain,
                "maximum_single_chain_ms": thresholds["maximum_single_chain_ms"],
            },
        ),
        _check(
            "p7-production-and-demo-boundary",
            True,
            cast(JsonObject, profile["boundaries"]),
        ),
    ]
    if tuple(check["check_id"] for check in checks) != _EXPECTED_CHECK_IDS:
        raise AssertionError("Gate check inventory drifted")
    blocked_count = sum(check["status"] == "BLOCKED" for check in checks)
    verdict = "READY" if not blockers else "NOT_READY"
    provenance = {
        "report_version": PROVENANCE_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "code_commit": code_commit,
        "chains": list(chains),
        "product_extension_call_sites": source_call_sites,
        "issues": [],
        "production_ready": False,
    }
    compatibility = {
        "report_version": COMPATIBILITY_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "developer_kit": {
            "version": verified_kit.kit_version,
            "release_fingerprint": verified_kit.release_fingerprint,
            "runtime_release_fingerprint": verified_kit.runtime_release_fingerprint,
            "payload_file_count": verified_kit.payload_file_count,
        },
        "extensions": [
            {
                "extension_id": item.project.project_id,
                "artifact_digest": item.report["artifact_digest"],
                "manifest_fingerprint": item.project.manifest.manifest_fingerprint,
                "sdk_api_version": item.project.sdk_api_version,
                "runtime_version": item.project.runtime_version,
                "developer_kit_version": item.project.developer_kit_version,
            }
            for item in extension_results
        ],
        "runtime_kit_binding": kit_bound,
        "issues": [],
        "production_ready": False,
    }
    security = {
        "report_version": SECURITY_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "targeted_suite": suite,
        "http_negative_matrix": {
            cast(str, chain["extension_id"]): cast(JsonObject, chain["http"])
            for chain in chains
        },
        "supply_chain": {
            "runtime_security": reports["runtime_security"]["status"],
            "developer_kit_security": reports["developer_kit_security"]["status"],
            "frontend_security": reports["frontend_security"]["status"],
        },
        "observability": {
            "status": reports["operations_observability"]["status"],
            "payload_logging": reports["operations_observability"].get(
                "payload_logging"
            ),
            "secret_sentinel_present": cast(
                JsonObject,
                reports["operations_observability"].get(
                    "correlation_trace_redaction", {}
                ),
            ).get("secret_sentinel_present"),
        },
        "payload_or_secret_in_gate_report": False,
        "issues": [],
        "production_ready": False,
    }
    recovery = {
        "report_version": RECOVERY_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "runtime_mismatch": mismatch,
        "duplicate_extension": duplicate,
        "database_migration": reports["runtime_migration"],
        "target_recovery": reports["operations_recovery"],
        "kit_upgrade_rollback": reports["developer_kit_upgrade"],
        "runbooks": {
            "status": reports["operations_runbooks"]["status"],
            "runbook_count": reports["operations_runbooks"].get("runbook_count"),
        },
        "issues": [],
        "production_ready": False,
    }
    benchmark = {
        "report_version": BENCHMARK_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "profile_version": profile["profile_version"],
        "profile_fingerprint": profile["profile_fingerprint"],
        "environment": "SYNTHETIC_ENGINEERING_ONLY",
        "observations": {
            "gate_runtime_ms": elapsed_ms,
            "maximum_chain_ms": max_chain,
            "chains": {
                cast(str, chain["extension_id"]): chain["elapsed_ms"]
                for chain in chains
            },
            "targeted_p8_tests": suite["tests"],
        },
        "thresholds": thresholds,
        "thresholds_passed": thresholds_passed,
        "p7_reality_or_production_capacity": "NOT_ESTABLISHED",
        "issues": [],
    }
    main: JsonObject = {
        "report_version": REPORT_VERSION,
        "audit_status": "PASS",
        "verdict": verdict,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "validation_profile": VALIDATION_PROFILE,
        "diff_base": DIFF_BASE,
        "code_commit": code_commit,
        "profile": {
            "profile_version": profile["profile_version"],
            "profile_fingerprint": profile["profile_fingerprint"],
            "seed": profile["seed"],
            "environment": profile["environment"],
            "data_plane": profile["data_plane"],
            "frozen_p8_15_code_commit": cast(
                JsonObject, profile["frozen_p8_15"]
            )["code_commit"],
        },
        "inputs": _input_projection(reports),
        "checks": checks,
        "check_summary": {
            "check_count": len(checks),
            "pass_count": len(checks) - blocked_count,
            "blocked_count": blocked_count,
            "error_count": 0,
        },
        "blocking_gaps": blockers,
        "issues": [],
        "scope": {
            "synthetic_engineering_gate": True,
            "real_data": False,
            "p7_reality_calibration": False,
            "production_ready": False,
            "capacity_or_sla": False,
            "demo_included": False,
            "third_party_connector": False,
        },
        "next": {
            "corrective_task": "TASK-P8-18" if blockers else None,
            "requalification_task": "TASK-P8-19" if blockers else None,
            "p8_exit_gate_authorized": False,
            "automatic_start": False,
        },
    }
    _write_outputs(
        report_path=report_path,
        provenance_path=provenance_path,
        compatibility_path=compatibility_path,
        security_path=security_path,
        recovery_path=recovery_path,
        benchmark_path=benchmark_path,
        main=main,
        provenance=provenance,
        compatibility=compatibility,
        security=security,
        recovery=recovery,
        benchmark=benchmark,
    )
    validate_gate_report(main)
    return main


def validate_gate_report(document: Mapping[str, object]) -> None:
    if set(document) != {
        "report_version",
        "audit_status",
        "verdict",
        "task_id",
        "test_id",
        "validation_profile",
        "diff_base",
        "code_commit",
        "profile",
        "inputs",
        "checks",
        "check_summary",
        "blocking_gaps",
        "issues",
        "scope",
        "next",
        "evidence",
        "report_fingerprint",
    }:
        _fail(
            "GATE_REPORT_INVALID",
            field="report",
            message="Gate report fields differ from the closed carrier",
        )
    code_commit = document.get("code_commit")
    if (
        document.get("report_version") != REPORT_VERSION
        or document.get("audit_status") != "PASS"
        or document.get("verdict") not in {"READY", "NOT_READY"}
        or document.get("task_id") != TASK_ID
        or document.get("test_id") != TEST_ID
        or document.get("validation_profile") != VALIDATION_PROFILE
        or document.get("diff_base") != DIFF_BASE
        or document.get("issues") != []
        or not isinstance(code_commit, str)
        or len(code_commit) != _COMMIT_LENGTH
        or any(character not in "0123456789abcdef" for character in code_commit)
    ):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.identity",
            message="Gate report identity or status is invalid",
        )
    checks = document.get("checks")
    if not isinstance(checks, list) or tuple(
        check.get("check_id") if isinstance(check, dict) else None for check in checks
    ) != _EXPECTED_CHECK_IDS:
        _fail(
            "GATE_REPORT_INVALID",
            field="report.checks",
            message="Gate report check inventory is incomplete",
        )
    if any(
        set(check) != {"check_id", "status", "evidence"}
        or check.get("status") not in {"PASS", "BLOCKED"}
        or not isinstance(check.get("evidence"), dict)
        for check in checks
        if isinstance(check, dict)
    ):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.checks",
            message="Gate report check carrier is invalid",
        )
    blockers = document.get("blocking_gaps")
    if not isinstance(blockers, list):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.blocking_gaps",
            message="Gate report blocker inventory is invalid",
        )
    blocker_ids = [
        blocker.get("blocker_id") if isinstance(blocker, dict) else None
        for blocker in blockers
    ]
    if len(blocker_ids) != len(set(blocker_ids)) or any(
        blocker_id not in _BLOCKER_DETAILS for blocker_id in blocker_ids
    ):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.blocking_gaps",
            message="Gate report blocker identities are invalid",
        )
    for blocker in blockers:
        if not isinstance(blocker, dict):
            raise AssertionError("blocker shape already validated")
        blocker_id = cast(str, blocker["blocker_id"])
        expected_category, expected_summary = _BLOCKER_DETAILS[blocker_id]
        if (
            set(blocker)
            != {
                "blocker_id",
                "category",
                "summary",
                "evidence",
                "corrective_owner",
                "requalification_owner",
                "production_waiver_allowed",
            }
            or blocker.get("category") != expected_category
            or blocker.get("summary") != expected_summary
            or not isinstance(blocker.get("evidence"), dict)
            or blocker.get("corrective_owner") != "TASK-P8-18"
            or blocker.get("requalification_owner") != "TASK-P8-19"
            or blocker.get("production_waiver_allowed") is not False
        ):
            _fail(
                "GATE_REPORT_INVALID",
                field="report.blocking_gaps",
                message="Gate blocker carrier or ownership is invalid",
            )
    blocked_checks = sum(
        isinstance(check, dict) and check.get("status") == "BLOCKED"
        for check in checks
    )
    blocked_check_ids = {
        cast(str, check["check_id"])
        for check in checks
        if cast(str, check["status"]) == "BLOCKED"
    }
    expected_blocker_ids = {
        _BLOCKER_CHECK_IDS[check_id]
        for check_id in blocked_check_ids
        if check_id in _BLOCKER_CHECK_IDS
    }
    if (
        len(expected_blocker_ids) != len(blocked_check_ids)
        or set(blocker_ids) != expected_blocker_ids
    ):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.blocking_gaps",
            message="Gate blockers do not match the blocked checks",
        )
    if (
        (document["verdict"] == "READY" and (blockers or blocked_checks))
        or (
            document["verdict"] == "NOT_READY"
            and (not blockers or blocked_checks != len(blockers))
        )
    ):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.verdict",
            message="Gate verdict does not match its blocking evidence",
        )
    summary = document.get("check_summary")
    if not isinstance(summary, dict) or summary != {
        "check_count": len(checks),
        "pass_count": len(checks) - blocked_checks,
        "blocked_count": blocked_checks,
        "error_count": 0,
    }:
        _fail(
            "GATE_REPORT_INVALID",
            field="report.check_summary",
            message="Gate report check totals are inconsistent",
        )
    scope = document.get("scope")
    if scope != {
        "synthetic_engineering_gate": True,
        "real_data": False,
        "p7_reality_calibration": False,
        "production_ready": False,
        "capacity_or_sla": False,
        "demo_included": False,
        "third_party_connector": False,
    }:
        _fail(
            "GATE_REPORT_INVALID",
            field="report.scope",
            message="Gate report crossed the Production boundary",
        )
    profile = document.get("profile")
    if profile != {
        "profile_version": PROFILE_VERSION,
        "profile_fingerprint": _FROZEN_PROFILE_FINGERPRINT,
        "seed": 81620260909,
        "environment": "TEST",
        "data_plane": "SIMULATION",
        "frozen_p8_15_code_commit": DIFF_BASE,
    }:
        _fail(
            "GATE_REPORT_INVALID",
            field="report.profile",
            message="Gate report profile projection is not the frozen profile",
        )
    inputs = document.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != set(_INPUT_REPORTS):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.inputs",
            message="Gate input evidence inventory is incomplete",
        )
    for name, (version, _) in _INPUT_REPORTS.items():
        item = inputs[name]
        if (
            not isinstance(item, dict)
            or set(item) != {"report_version", "status", "fingerprint"}
            or item.get("report_version") != version
            or item.get("status") != "PASS"
            or not _is_sha256(item.get("fingerprint"))
        ):
            _fail(
                "GATE_REPORT_INVALID",
                field=f"report.inputs.{name}",
                message="Gate input evidence projection is invalid",
            )
    expected_next = {
        "corrective_task": "TASK-P8-18" if blockers else None,
        "requalification_task": "TASK-P8-19" if blockers else None,
        "p8_exit_gate_authorized": False,
        "automatic_start": False,
    }
    if document.get("next") != expected_next:
        _fail(
            "GATE_REPORT_INVALID",
            field="report.next",
            message="Gate successor disposition is invalid",
        )
    evidence = document.get("evidence")
    expected_evidence_versions = {
        "provenance": PROVENANCE_VERSION,
        "compatibility": COMPATIBILITY_VERSION,
        "security": SECURITY_VERSION,
        "recovery": RECOVERY_VERSION,
        "benchmark": BENCHMARK_VERSION,
    }
    if not isinstance(evidence, dict) or set(evidence) != set(
        expected_evidence_versions
    ):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.evidence",
            message="Gate support evidence inventory is incomplete",
        )
    for name, version in expected_evidence_versions.items():
        item = evidence[name]
        if (
            not isinstance(item, dict)
            or set(item) != {"report_version", "report_fingerprint"}
            or item.get("report_version") != version
            or not _is_sha256(item.get("report_fingerprint"))
        ):
            _fail(
                "GATE_REPORT_INVALID",
                field=f"report.evidence.{name}",
                message="Gate support evidence projection is invalid",
            )
    projection = dict(document)
    provided = projection.pop("report_fingerprint", None)
    if provided != canonical_fingerprint(projection):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.report_fingerprint",
            message="Gate report fingerprint differs from canonical content",
        )
    serialized = json.dumps(document, ensure_ascii=False).lower()
    if any(
        marker in serialized
        for marker in (
            _CONFORMANCE_KEY_TEXT.lower(),
            "redis://operator:",
            "secret-do-not-leak",
            "authorization: bearer",
        )
    ):
        _fail(
            "GATE_REPORT_INVALID",
            field="report.redaction",
            message="Gate report crossed the secret or payload evidence boundary",
        )


def _failure_report(error: Exception) -> JsonObject:
    return _fingerprinted(
        {
            "report_version": REPORT_VERSION,
            "audit_status": "ERROR",
            "verdict": "NOT_READY",
            "task_id": TASK_ID,
            "test_id": TEST_ID,
            "validation_profile": VALIDATION_PROFILE,
            "diff_base": DIFF_BASE,
            "error_code": getattr(error, "code", "GATE_EXECUTION_FAILED"),
            "error_field": getattr(error, "field", "gate"),
            "issues": [getattr(error, "code", "GATE_EXECUTION_FAILED")],
            "payload_included": False,
            "path_included": False,
            "production_ready": False,
        }
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    for name in _INPUT_REPORTS:
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--provenance-report", type=Path, required=True)
    parser.add_argument("--compatibility-report", type=Path, required=True)
    parser.add_argument("--security-report", type=Path, required=True)
    parser.add_argument("--recovery-report", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report_path = args.report.resolve()
    try:
        report = run_gate(
            args.root,
            profile_path=args.profile.resolve(),
            junit_path=args.junit.resolve(),
            input_paths={name: getattr(args, name).resolve() for name in _INPUT_REPORTS},
            report_path=report_path,
            provenance_path=args.provenance_report.resolve(),
            compatibility_path=args.compatibility_report.resolve(),
            security_path=args.security_report.resolve(),
            recovery_path=args.recovery_report.resolve(),
            benchmark_path=args.benchmark_report.resolve(),
        )
    except Exception as error:  # noqa: BLE001 - CLI emits only stable safe fields
        failure = _failure_report(error)
        _write_json(report_path, failure)
        print(json.dumps(failure, ensure_ascii=False, separators=(",", ":")))
        return 1
    print(
        f"{report['verdict']} {TASK_ID}: "
        f"checks={report['check_summary']['check_count']} "
        f"blocked={report['check_summary']['blocked_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BENCHMARK_VERSION",
    "COMPATIBILITY_VERSION",
    "DIFF_BASE",
    "GateInputError",
    "PROFILE_VERSION",
    "PROVENANCE_VERSION",
    "RECOVERY_VERSION",
    "REPORT_VERSION",
    "SECURITY_VERSION",
    "TASK_ID",
    "TEST_ID",
    "main",
    "run_gate",
    "validate_gate_report",
    "validate_profile",
]
