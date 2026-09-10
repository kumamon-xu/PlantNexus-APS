"""Independent TASK-P8-19 Headless + Extension requalification Gate.

The Gate preserves the immutable TASK-P8-16 ``NOT_READY`` history, consumes
the exact TASK-P8-18 corrective lineage, and performs a fresh product replay.
It never repairs product code or changes the frozen P8-16 profile/thresholds.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Never, cast
from unittest.mock import patch
import xml.etree.ElementTree as ET

from aps_extension_tooling.conformance import ConformanceResult, conform_project
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from scripts import p8_headless_extension_platform_gate as frozen_gate
from scripts import p8_runtime_product_integration_check as corrective


type JsonObject = dict[str, Any]

TASK_ID = "TASK-P8-19"
TEST_ID = "TEST-P8-VERTICAL-SLICE-001"
DIFF_BASE = "5f67501d9d3cf75313edff250c8a7fdb74c56c30"
VALIDATION_PROFILE = "PHASE_GATE"

REPORT_VERSION = "p8-headless-extension-platform-requalification-report.v1"
DISPOSITION_VERSION = "p8-headless-extension-blocker-disposition.v1"
PROVENANCE_VERSION = "p8-headless-extension-requalification-provenance.v1"
COMPATIBILITY_VERSION = "p8-headless-extension-requalification-compatibility.v1"
SECURITY_VERSION = "p8-headless-extension-requalification-security.v1"
RECOVERY_VERSION = "p8-headless-extension-requalification-recovery.v1"
BENCHMARK_VERSION = "p8-headless-extension-requalification-benchmark.v1"

P8_16_FINAL_SHA = "b80f44be094aaf5b673481dde9d81867ef49a11d"
P8_16_PROVIDER_RUN_ID = 34340039154
P8_16_REQUIRED_VALIDATE_JOB_ID = 102432349847
P8_18_PROVIDER_RUN_ID = 34429068832
P8_18_REQUIRED_VALIDATE_JOB_ID = 102723359648
P8_18_RUNTIME_IMPLEMENTATION_SHA = "7369e9c1238bae36f278423edb1977124d07faa9"

PROFILE_FINGERPRINT = (
    "sha256:da5ee7830e37f86569897a80685d25e59414f05153499b3effed37b483503043"
)
DEVELOPER_KIT_VERSION = "1.0.0"
DEVELOPER_KIT_FINGERPRINT = (
    "sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361"
)
P8_15_RUNTIME_RELEASE_FINGERPRINT = (
    "sha256:3e9a70c415bf94c5ba8ae9ffdb426005b756f560c439c1222df56862189f687c"
)

_FROZEN_RUNNER_SHA256 = (
    "sha256:082a4c9e2b471ddd37d96d7d026dc2290868e14e4297cb2c96bedaa0942bbe05"
)
_FROZEN_PROFILE_BYTES_SHA256 = (
    "sha256:38d8ec073fb21afd30eb3d4beb9ecffcfda2c4760ad94297a7fe309176b1b19b"
)
_MAX_JSON_BYTES = 32 * 1024 * 1024
_MINIMUM_TARGETED_TESTS = 283
_MAXIMUM_GATE_RUNTIME_MS = 120_000
_MAXIMUM_SINGLE_CHAIN_MS = 30_000
_FROZEN_NEGATIVE_COMPATIBILITY_ADAPTER = "DEVELOPER_KIT_VERSION_PAIRING_ONLY"

_P8_16_BLOCKERS = (
    "P8-GATE-BLOCKER-EXTENSION-EXECUTION-001",
    "P8-GATE-BLOCKER-KIT-RUNTIME-PROVENANCE-002",
    "P8-GATE-BLOCKER-HEADLESS-OUTPUT-003",
    "P8-GATE-BLOCKER-EXTENSION-DEPLOYMENT-004",
)

_P8_16_REPORTS: Mapping[str, tuple[str, str]] = {
    "gate": (
        frozen_gate.REPORT_VERSION,
        "sha256:5a0e75606ff94114b44b4a2d2c9bf7f50459ae1b7be57c299e2c6c2ffad3993c",
    ),
    "provenance": (
        frozen_gate.PROVENANCE_VERSION,
        "sha256:a1334731dd5b91193e2af20a141f12b8d01c9e23f0dc83b122e7e3de53ffe6eb",
    ),
    "compatibility": (
        frozen_gate.COMPATIBILITY_VERSION,
        "sha256:e91c1d4a12db3f39cd2039a0730e71e2069d12faf1e991e9fb2557f24e0c908b",
    ),
    "security": (
        frozen_gate.SECURITY_VERSION,
        "sha256:e7ff3af41859de792f9c84398d6bd24cb856d3bd898607324bcab4b9dd0cf466",
    ),
    "recovery": (
        frozen_gate.RECOVERY_VERSION,
        "sha256:88216c77e93b500fb55fdbe7cd9f05f8665e9f9aa5a36544546ba76f7c46193d",
    ),
    "benchmark": (
        frozen_gate.BENCHMARK_VERSION,
        "sha256:0d9a0d9330f7b7b9dc582866b2996f1d57a386e2c6bc174194ee9e1698178edb",
    ),
}

_P8_18_PROVIDER_REPORTS: Mapping[str, tuple[str, str]] = {
    "corrective": (
        "p8-runtime-product-corrective-report.v1",
        "sha256:ace53c67463794867a1f833f1729cea36be53c4f4579df56bda2140ded1a63c6",
    ),
    "invocation": (
        "p8-runtime-extension-product-invocation-report.v1",
        "sha256:24b9ef5f2d88e80b5bf87b7cb0cd7bc81e0f854159e65ee3ceb0a61f1605babb",
    ),
    "kit": (
        "p8-runtime-developer-kit-binding-report.v1",
        "sha256:d2a197e0585932ef916cb072e33c3f1e2d950136faeaa49a0c694d28e670f6cd",
    ),
    "output": (
        "p8-headless-output-corrective-report.v1",
        "sha256:cd93e1d75553377d30a74177bcd44579332d30af3170729f39d35a3a64b654a9",
    ),
    "deployment": (
        "p8-extension-deployment-recovery-corrective-report.v1",
        "sha256:bdc95ac02f34108316791aefcec123842591d1b01aac91021e4c69fcc03e3ae5",
    ),
    "security": (
        "p8-runtime-product-corrective-security-report.v1",
        "sha256:e6b6c9efa4295440d623a56557175edc5352d93b176d6906be7f391cffd5524a",
    ),
    "benchmark": (
        "p8-runtime-product-corrective-benchmark-report.v1",
        "sha256:b662c5fca6e0e8c5b4bf59cd19bb1fadfa6bf8ee0a5e834f8a1177648ddaa96b",
    ),
}

_EXTENSIONS: tuple[JsonObject, JsonObject] = (
    {
        "extension_id": "com.example.aps.alpha",
        "path": "examples/enterprise-extensions/alpha-resource-tag",
        "artifact_digest": (
            "sha256:b436aeabfe97943a69d73fe8238439641e72a8300503e5fb02aac7591c0fddea"
        ),
        "manifest_fingerprint": (
            "sha256:778ec6c56d08814f8c3d924061a71fdcf6ed306322abc09f0406e704c5b59754"
        ),
    },
    {
        "extension_id": "com.example.aps.beta",
        "path": "examples/enterprise-extensions/beta-priority-policy",
        "artifact_digest": (
            "sha256:b9b286befe1a3e0076fb96500172605b2c3259c5735d04239927219804674ae4"
        ),
        "manifest_fingerprint": (
            "sha256:0051184d253afca8313b1964cf3c1c42aadebcf399c39af56f6b48cb5e7aac12"
        ),
    },
)

_PLATFORM_CHECK_IDS = (
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

_CLOSURE_CHECKS: Mapping[str, str] = {
    _P8_16_BLOCKERS[0]: "runtime-invokes-selected-extension-contributions",
    _P8_16_BLOCKERS[1]: "runtime-binds-published-developer-kit-identity",
    _P8_16_BLOCKERS[2]: "headless-result-supports-publication-read-export",
    _P8_16_BLOCKERS[3]: "target-deployment-loads-verified-extension",
}

_CURRENT_REPORTS: Mapping[str, tuple[str, str]] = {
    "runtime_release": ("p8-runtime-release-report.v1", "status"),
    "runtime_security": ("p8-runtime-release-security-report.v1", "status"),
    "runtime_migration": ("p8-runtime-release-migration-report.v1", "status"),
    "formal_validator": ("formal-schedule-validator-report.v1", "status"),
    "validator_mutations": ("validator-mutation-report.v1", "result"),
    "frontend_distribution": ("p8-frontend-distribution-report.v1", "status"),
    "frontend_client": ("p8-frontend-client-isolation-report.v1", "status"),
    "frontend_security": ("p8-frontend-browser-security-report.v1", "status"),
    "frontend_backend_only": ("p8-frontend-backend-only-report.v1", "status"),
    "operations_deployment": ("p8-operations-deployment-report.v1", "status"),
    "operations_observability": ("p8-operations-observability-report.v1", "status"),
    "operations_recovery": ("p8-operations-recovery-report.v1", "status"),
    "operations_runbooks": ("p8-operations-runbook-dry-run-report.v1", "status"),
    "corrective": (_P8_18_PROVIDER_REPORTS["corrective"][0], "status"),
    "corrective_invocation": (_P8_18_PROVIDER_REPORTS["invocation"][0], "status"),
    "corrective_kit": (_P8_18_PROVIDER_REPORTS["kit"][0], "status"),
    "corrective_output": (_P8_18_PROVIDER_REPORTS["output"][0], "status"),
    "corrective_deployment": (_P8_18_PROVIDER_REPORTS["deployment"][0], "status"),
    "corrective_security": (_P8_18_PROVIDER_REPORTS["security"][0], "status"),
    "corrective_benchmark": (_P8_18_PROVIDER_REPORTS["benchmark"][0], "status"),
}

_SUPPORT_VERSIONS: Mapping[str, str] = {
    "blocker_disposition": DISPOSITION_VERSION,
    "provenance": PROVENANCE_VERSION,
    "compatibility": COMPATIBILITY_VERSION,
    "security": SECURITY_VERSION,
    "recovery": RECOVERY_VERSION,
    "benchmark": BENCHMARK_VERSION,
}

_EXPECTED_HTTP_STATUSES: Mapping[str, int] = {
    "unauthorized_create": 401,
    "created": 202,
    "replayed": 202,
    "result": 200,
    "unauthorized_schedule_read": 401,
    "ready_schedule_read": 200,
    "approved": 200,
    "published": 200,
    "export_created": 202,
    "export_read": 200,
    "export_replay": 202,
    "published_schedule_read": 200,
}


class RequalificationError(RuntimeError):
    """Stable payload-free P8-19 failure."""

    def __init__(self, code: str, *, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.safe_message = message
        super().__init__(f"{code}: {field}: {message}")


def _fail(code: str, *, field: str, message: str) -> Never:
    raise RequalificationError(code, field=field, message=message)


def _strict_pairs(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail(
                "REQUALIFICATION_INPUT_INVALID",
                field="json",
                message="duplicate JSON keys are forbidden",
            )
        result[key] = value
    return result


def _reject_constant(_: str) -> Never:
    _fail(
        "REQUALIFICATION_INPUT_INVALID",
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
    except RequalificationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RequalificationError(
            "REQUALIFICATION_INPUT_UNAVAILABLE",
            field=field,
            message="required requalification evidence is unavailable",
        ) from error
    if not isinstance(value, dict):
        _fail(
            "REQUALIFICATION_INPUT_INVALID",
            field=field,
            message="requalification evidence root must be an object",
        )
    return cast(JsonObject, value)


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_json_bytes(document) + b"\n")
    temporary.replace(path)


def _fingerprinted(document: JsonObject) -> JsonObject:
    projection = dict(document)
    projection.pop("report_fingerprint", None)
    document["report_fingerprint"] = canonical_fingerprint(projection)
    return document


def _bytes_fingerprint(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _mapping(value: object, *, field: str) -> JsonObject:
    if not isinstance(value, dict):
        _fail(
            "REQUALIFICATION_EVIDENCE_INVALID",
            field=field,
            message="required evidence object is missing",
        )
    return cast(JsonObject, value)


def _items(value: object, *, field: str) -> list[JsonObject]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        _fail(
            "REQUALIFICATION_EVIDENCE_INVALID",
            field=field,
            message="required evidence list is missing",
        )
    return cast(list[JsonObject], value)


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *arguments),
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _git_head(root: Path) -> str:
    result = _git(root, "rev-parse", "HEAD")
    head = result.stdout.strip()
    if (
        result.returncode != 0
        or len(head) != 40
        or any(character not in "0123456789abcdef" for character in head)
        or _git(root, "merge-base", "--is-ancestor", DIFF_BASE, head).returncode != 0
    ):
        _fail(
            "REQUALIFICATION_PROVENANCE_INVALID",
            field="git_head",
            message="HEAD does not descend from the P8-18 exact closure",
        )
    return head


def validate_requalification_profile(document: Mapping[str, object]) -> JsonObject:
    try:
        validated = frozen_gate.validate_profile(document)
    except Exception as error:  # noqa: BLE001 - normalized to the P8-19 boundary
        raise RequalificationError(
            "REQUALIFICATION_PROFILE_INVALID",
            field="profile",
            message="the frozen P8-16 profile failed validation",
        ) from error
    if validated.get("profile_fingerprint") != PROFILE_FINGERPRINT:
        _fail(
            "REQUALIFICATION_PROFILE_INVALID",
            field="profile.profile_fingerprint",
            message="the P8-16 profile fingerprint changed",
        )
    return validated


def _verify_frozen_history(root: Path, profile_path: Path) -> JsonObject:
    runner_path = root / "scripts/p8_headless_extension_platform_gate.py"
    if (
        _bytes_fingerprint(runner_path) != _FROZEN_RUNNER_SHA256
        or _bytes_fingerprint(profile_path) != _FROZEN_PROFILE_BYTES_SHA256
        or tuple(cast(Sequence[str], frozen_gate._EXPECTED_CHECK_IDS))
        != _PLATFORM_CHECK_IDS
    ):
        _fail(
            "REQUALIFICATION_HISTORY_DRIFT",
            field="p8_16.runner_profile",
            message="the immutable P8-16 procedure or profile changed",
        )
    for commit in (P8_16_FINAL_SHA, DIFF_BASE, P8_18_RUNTIME_IMPLEMENTATION_SHA):
        if _git(root, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
            _fail(
                "REQUALIFICATION_HISTORY_DRIFT",
                field="git_history",
                message="a required immutable P8 commit is unavailable",
            )
    if _git(root, "merge-base", "--is-ancestor", P8_16_FINAL_SHA, DIFF_BASE).returncode:
        _fail(
            "REQUALIFICATION_HISTORY_DRIFT",
            field="git_history",
            message="the P8-16 to P8-18 corrective chain is not linear",
        )
    return {
        "p8_16": {
            "final_sha": P8_16_FINAL_SHA,
            "provider_run_id": P8_16_PROVIDER_RUN_ID,
            "required_validate_job_id": P8_16_REQUIRED_VALIDATE_JOB_ID,
            "verdict": "NOT_READY",
            "check_summary": {
                "check_count": 18,
                "pass_count": 14,
                "blocked_count": 4,
                "error_count": 0,
            },
            "blocking_gaps": list(_P8_16_BLOCKERS),
            "reports": {
                name: {"report_version": version, "report_fingerprint": fingerprint}
                for name, (version, fingerprint) in _P8_16_REPORTS.items()
            },
        },
        "p8_18": {
            "runtime_implementation_sha": P8_18_RUNTIME_IMPLEMENTATION_SHA,
            "closure_sha": DIFF_BASE,
            "provider_run_id": P8_18_PROVIDER_RUN_ID,
            "required_validate_job_id": P8_18_REQUIRED_VALIDATE_JOB_ID,
            "reports": {
                name: {"report_version": version, "report_fingerprint": fingerprint}
                for name, (version, fingerprint) in _P8_18_PROVIDER_REPORTS.items()
            },
        },
        "runner_sha256": _FROZEN_RUNNER_SHA256,
        "profile_bytes_sha256": _FROZEN_PROFILE_BYTES_SHA256,
        "status": "PASS",
    }


def _require_report(
    document: Mapping[str, object],
    *,
    name: str,
    report_version: str,
    status_field: str,
    code_commit: str,
) -> JsonObject:
    observed_version = document.get("report_version", document.get("schema_version"))
    issues = document.get("issues")
    if (
        observed_version != report_version
        or document.get(status_field) != "PASS"
        or (issues is not None and issues != [])
    ):
        _fail(
            "REQUALIFICATION_DEPENDENCY_FAILED",
            field=name,
            message="a current dependency report failed or is incompatible",
        )
    observed_commit = document.get("code_commit", document.get("evidence_commit"))
    if observed_commit is not None and observed_commit != code_commit:
        _fail(
            "REQUALIFICATION_PROVENANCE_INVALID",
            field=name,
            message="a current dependency report is not bound to HEAD",
        )
    provided_fingerprint = document.get("report_fingerprint")
    if provided_fingerprint is not None:
        projection = dict(document)
        projection.pop("report_fingerprint", None)
        if provided_fingerprint != canonical_fingerprint(projection):
            _fail(
                "REQUALIFICATION_DEPENDENCY_FAILED",
                field=name,
                message="a dependency report fingerprint is invalid",
            )
    return dict(document)


def _load_current_reports(
    paths: Mapping[str, Path], *, code_commit: str
) -> dict[str, JsonObject]:
    reports: dict[str, JsonObject] = {}
    for name, (version, status_field) in _CURRENT_REPORTS.items():
        path = paths.get(name)
        if path is None:
            _fail(
                "REQUALIFICATION_INPUT_UNAVAILABLE",
                field=name,
                message="a required current evidence path is missing",
            )
        reports[name] = _require_report(
            _read_json(path, field=name),
            name=name,
            report_version=version,
            status_field=status_field,
            code_commit=code_commit,
        )
    return reports


def _junit_summary(path: Path) -> JsonObject:
    try:
        xml_root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as error:
        raise RequalificationError(
            "REQUALIFICATION_SUITE_INVALID",
            field="targeted_p8_junit",
            message="fresh targeted P8 JUnit evidence is unavailable",
        ) from error
    suites = (
        [xml_root]
        if xml_root.tag == "testsuite"
        else list(xml_root.findall("testsuite"))
    )
    if not suites:
        _fail(
            "REQUALIFICATION_SUITE_INVALID",
            field="targeted_p8_junit",
            message="fresh targeted P8 JUnit evidence contains no suite",
        )

    def total(attribute: str) -> int:
        try:
            return sum(int(float(suite.attrib.get(attribute, "0"))) for suite in suites)
        except ValueError:
            _fail(
                "REQUALIFICATION_SUITE_INVALID",
                field="targeted_p8_junit",
                message="fresh targeted P8 JUnit counters are invalid",
            )

    testcases = list(xml_root.iter("testcase"))
    identity_text = "\n".join(
        f"{case.attrib.get('classname', '')}.{case.attrib.get('name', '')}"
        for case in testcases
    )
    required_families = (
        "test_p8_headless",
        "test_p8_runtime_extension",
        "test_p8_enterprise_extension",
        "test_p8_developer_kit",
        "test_p8_operations",
        "test_p8_headless_extension_platform_requalification_gate",
    )
    family_coverage = {family: family in identity_text for family in required_families}
    summary = {
        "tests": total("tests"),
        "failures": total("failures"),
        "errors": total("errors"),
        "skipped": total("skipped"),
        "minimum_tests": _MINIMUM_TARGETED_TESTS,
        "required_family_coverage": family_coverage,
    }
    if (
        summary["tests"] < _MINIMUM_TARGETED_TESTS
        or summary["failures"]
        or summary["errors"]
        or summary["skipped"]
        or not all(family_coverage.values())
    ):
        _fail(
            "REQUALIFICATION_SUITE_FAILED",
            field="targeted_p8_junit",
            message="fresh targeted P8 suite failed, skipped, or lost required coverage",
        )
    return {**summary, "status": "PASS"}


def _corrective_report_map(reports: Sequence[JsonObject]) -> dict[str, JsonObject]:
    if len(reports) != 7:
        _fail(
            "REQUALIFICATION_REPLAY_FAILED",
            field="corrective_replay",
            message="independent product replay returned an incomplete report set",
        )
    return dict(
        zip(
            (
                "corrective",
                "corrective_invocation",
                "corrective_kit",
                "corrective_output",
                "corrective_deployment",
                "corrective_security",
                "corrective_benchmark",
            ),
            reports,
            strict=True,
        )
    )


def _validate_corrective_links(reports: Mapping[str, JsonObject]) -> None:
    main = reports["corrective"]
    supports = {
        cast(str, reports[name]["report_version"]): reports[name]["report_fingerprint"]
        for name in (
            "corrective_invocation",
            "corrective_kit",
            "corrective_output",
            "corrective_deployment",
            "corrective_security",
            "corrective_benchmark",
        )
    }
    closed = _items(main.get("closed_blockers"), field="corrective.closed_blockers")
    observed_ids = tuple(cast(str, row.get("blocker_id")) for row in closed)
    if (
        main.get("blocker_count") != 4
        or main.get("pass_count") != 4
        or observed_ids != _P8_16_BLOCKERS
        or any(
            row.get("status") != "PASS"
            or row.get("historical_p8_16_verdict_changed") is not False
            or not _is_sha256(row.get("evidence_fingerprint"))
            for row in closed
        )
        or main.get("reports") != supports
    ):
        _fail(
            "REQUALIFICATION_CORRECTIVE_INVALID",
            field="corrective",
            message="P8-18 closure linkage is incomplete or rewrites P8-16 history",
        )


def _semantic_corrective_projection(reports: Mapping[str, JsonObject]) -> JsonObject:
    invocation = reports["corrective_invocation"]
    chains = _items(invocation.get("chains"), field="corrective_invocation.chains")
    return {
        "closed_blockers": [
            {
                "blocker_id": row.get("blocker_id"),
                "status": row.get("status"),
                "historical_p8_16_verdict_changed": row.get(
                    "historical_p8_16_verdict_changed"
                ),
            }
            for row in _items(
                reports["corrective"].get("closed_blockers"),
                field="corrective.closed_blockers",
            )
        ],
        "extension_point_coverage": invocation.get("extension_point_coverage"),
        "chains": [
            {
                "extension_id": chain.get("extension_id"),
                "artifact_digest": chain.get("artifact_digest"),
                "manifest_fingerprint": chain.get("manifest_fingerprint"),
                "selected_contributions": chain.get("selected_contributions"),
                "all_selected_contributions_invoked": chain.get(
                    "all_selected_contributions_invoked"
                ),
                "http_statuses": chain.get("http_statuses"),
                "durability": chain.get("durability"),
                "output": chain.get("output"),
                "runtime_resolution": chain.get("runtime_resolution"),
                "status": chain.get("status"),
            }
            for chain in chains
        ],
        "negative_validation": invocation.get("negative_validation"),
        "negative_replan": invocation.get("negative_replan"),
        "kit": {
            key: reports["corrective_kit"].get(key)
            for key in (
                "developer_kit_version",
                "developer_kit_fingerprint",
                "provider_baseline",
                "api_worker_mismatch_negative",
                "automatic_upgrade",
            )
        },
        "output": {
            key: reports["corrective_output"].get(key)
            for key in (
                "authorization_default_deny",
                "explicit_approve_publish_export",
                "automatic_publication",
                "idempotent_export",
            )
        },
        "deployment": {
            key: reports["corrective_deployment"].get(key)
            for key in (
                "extension_identity",
                "candidate_api_worker_match",
                "backup_restore_status",
                "restore_identity_match",
                "rollback_identity_match",
            )
        },
        "security": {
            key: reports["corrective_security"].get(key)
            for key in (
                "authorization_default_deny",
                "extension_validation_failure",
                "extension_replan_failure",
                "kit_mismatch_failure",
                "core_reverse_import_count",
                "enterprise_branch_count",
                "payload_or_secret_in_metrics",
            )
        },
    }


def _run_fresh_corrective_replay(
    root: Path,
    *,
    junit_path: Path,
    operations_deployment: Path,
    operations_recovery: Path,
    code_commit: str,
) -> dict[str, JsonObject]:
    replay_arguments = argparse.Namespace(
        root=root,
        junit=junit_path,
        operations_deployment=operations_deployment,
        operations_recovery=operations_recovery,
    )
    try:
        replay = _corrective_report_map(corrective.run(replay_arguments))
    except Exception as error:  # noqa: BLE001 - normalized to a stable Gate failure
        raise RequalificationError(
            "REQUALIFICATION_REPLAY_FAILED",
            field="corrective_replay",
            message="independent P8 product replay failed",
        ) from error
    for name, document in replay.items():
        expected_name = name.removeprefix("corrective_")
        expected = _P8_18_PROVIDER_REPORTS[expected_name]
        _require_report(
            document,
            name=f"replay.{name}",
            report_version=expected[0],
            status_field="status",
            code_commit=code_commit,
        )
    _validate_corrective_links(replay)
    return replay


@dataclass(frozen=True, slots=True)
class _FrozenKitIdentity:
    kit_version: str = DEVELOPER_KIT_VERSION
    release_fingerprint: str = DEVELOPER_KIT_FINGERPRINT
    runtime_release_fingerprint: str = P8_15_RUNTIME_RELEASE_FINGERPRINT


def _extension_results(root: Path) -> tuple[ConformanceResult, ConformanceResult]:
    results: list[ConformanceResult] = []
    for expected in _EXTENSIONS:
        result = conform_project(
            root / cast(str, expected["path"]),
            repository_root=root,
            clean_install=False,
        )
        if (
            result.project.project_id != expected["extension_id"]
            or result.report["artifact_digest"] != expected["artifact_digest"]
            or result.project.manifest.manifest_fingerprint
            != expected["manifest_fingerprint"]
        ):
            _fail(
                "REQUALIFICATION_EXTENSION_IDENTITY_MISMATCH",
                field=cast(str, expected["extension_id"]),
                message="an Enterprise Extension differs from the frozen Kit input",
            )
        results.append(result)
    return results[0], results[1]


def _frozen_runner_negatives(
    root: Path, *, code_commit: str
) -> tuple[JsonObject, JsonObject]:
    alpha, beta = _extension_results(root)
    runtime_mismatch = cast(Any, frozen_gate._runtime_mismatch)
    duplicate_rejection = cast(Any, frozen_gate._duplicate_extension_rejection)
    frozen_runtime_settings = cast(Any, frozen_gate.runtime_settings)

    def versioned_runtime_settings(*args: Any, **kwargs: Any) -> Any:
        """Pair the Kit version added after P8-16 without changing its procedure."""

        settings = frozen_runtime_settings(*args, **kwargs)
        return settings.model_copy(
            update={"developer_kit_version": DEVELOPER_KIT_VERSION}
        )

    try:
        with (
            patch.object(
                frozen_gate,
                "runtime_settings",
                versioned_runtime_settings,
            ),
            TemporaryDirectory(prefix="plantnexus-p8-19-negatives-") as value,
        ):
            base = Path(value)
            mixed = cast(
                JsonObject,
                runtime_mismatch(
                    base / "mixed",
                    alpha=alpha,
                    beta=beta,
                    verified_kit=_FrozenKitIdentity(),
                    code_commit=code_commit,
                ),
            )
            duplicate = cast(
                JsonObject,
                duplicate_rejection(base / "duplicate", alpha),
            )
    except Exception as error:  # noqa: BLE001 - normalized to a stable Gate failure
        raise RequalificationError(
            "REQUALIFICATION_NEGATIVE_FAILED",
            field="frozen_p8_16_negatives",
            message="a frozen mixed or duplicate Extension negative failed",
        ) from error
    mixed["fixture_compatibility_adapter"] = _FROZEN_NEGATIVE_COMPATIBILITY_ADAPTER
    return mixed, duplicate


def _report_projection(reports: Mapping[str, JsonObject]) -> JsonObject:
    return {
        name: {
            "report_version": report.get(
                "report_version", report.get("schema_version")
            ),
            "status": report.get("status", report.get("result")),
            "fingerprint": canonical_fingerprint(report),
        }
        for name, report in sorted(reports.items())
    }


def _chain_map(invocation: Mapping[str, object]) -> dict[str, JsonObject]:
    chains = _items(invocation.get("chains"), field="invocation.chains")
    result = {
        cast(str, chain.get("extension_id")): chain
        for chain in chains
        if isinstance(chain.get("extension_id"), str)
    }
    if set(result) != {item["extension_id"] for item in _EXTENSIONS}:
        _fail(
            "REQUALIFICATION_REPLAY_FAILED",
            field="invocation.chains",
            message="the independent Alpha/Beta chain inventory is incomplete",
        )
    return result


def _chain_passed(chain: Mapping[str, object]) -> bool:
    output = chain.get("output")
    durability = chain.get("durability")
    metrics = chain.get("metrics_after")
    if (
        not isinstance(output, dict)
        or not isinstance(durability, dict)
        or not isinstance(metrics, dict)
    ):
        return False
    contribution_rows = metrics.get("contributions")
    if not isinstance(contribution_rows, list) or not contribution_rows:
        return False
    return (
        chain.get("status") == "PASS"
        and chain.get("conformance_status") == "PASS"
        and chain.get("all_selected_contributions_invoked") is True
        and chain.get("http_statuses") == _EXPECTED_HTTP_STATUSES
        and durability
        == {
            "canonical_ingress_records": 1,
            "planning_runs": 1,
            "planning_run_worker_results": 1,
            "schedule_versions": 1,
            "publication_results": 1,
            "export_jobs": 1,
        }
        and output.get("final_schedule_state") == "PUBLISHED"
        and output.get("publication_count") == 1
        and output.get("export_count") == 1
        and output.get("idempotent_export_replay") is True
        and all(
            isinstance(row, dict)
            and row.get("call_count", 0) >= 1
            and row.get("success_count", 0) >= 1
            and row.get("failure_count") == 0
            and row.get("timeout_count") == 0
            and _is_sha256(row.get("last_input_fingerprint"))
            and _is_sha256(row.get("last_output_fingerprint"))
            for row in contribution_rows
        )
        and metrics.get("payloads_recorded") is False
        and metrics.get("exception_details_recorded") is False
        and metrics.get("unhealthy_contribution_ids") == []
    )


def _check(check_id: str, passed: bool, evidence: Mapping[str, object]) -> JsonObject:
    return {
        "check_id": check_id,
        "status": "PASS" if passed else "BLOCKED",
        "evidence": dict(evidence),
    }


def _build_checks(
    *,
    profile: Mapping[str, object],
    history: Mapping[str, object],
    suite: Mapping[str, object],
    reports: Mapping[str, JsonObject],
    replay: Mapping[str, JsonObject],
    mixed: Mapping[str, object],
    duplicate: Mapping[str, object],
    elapsed_ms: float,
) -> list[JsonObject]:
    invocation = replay["corrective_invocation"]
    chains = _chain_map(invocation)
    alpha = chains["com.example.aps.alpha"]
    beta = chains["com.example.aps.beta"]
    chain_values = (alpha, beta)
    source_audit = _mapping(invocation.get("source_audit"), field="source_audit")
    kit = replay["corrective_kit"]
    output = replay["corrective_output"]
    deployment = replay["corrective_deployment"]
    security = replay["corrective_security"]
    benchmark = replay["corrective_benchmark"]
    formal_counts = _mapping(
        reports["formal_validator"].get("counts"), field="formal_validator.counts"
    )
    mutation_counts = _mapping(
        reports["validator_mutations"].get("counts"),
        field="validator_mutations.counts",
    )
    extension_identity = _mapping(
        deployment.get("extension_identity"), field="deployment.extension_identity"
    )
    runtime_release = reports["runtime_release"]
    release = _mapping(runtime_release.get("release"), field="runtime_release.release")
    maximum_chain_ms = max(cast(float, chain["elapsed_ms"]) for chain in chain_values)

    checks = [
        _check(
            _PLATFORM_CHECK_IDS[0],
            profile.get("profile_fingerprint") == PROFILE_FINGERPRINT
            and history.get("status") == "PASS",
            {
                "profile_fingerprint": profile.get("profile_fingerprint"),
                "p8_16_provider_run_id": P8_16_PROVIDER_RUN_ID,
                "historical_verdict": "NOT_READY",
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[1],
            release.get("runtime_version") == "0.1.0"
            and kit.get("developer_kit_version") == DEVELOPER_KIT_VERSION
            and kit.get("developer_kit_fingerprint") == DEVELOPER_KIT_FINGERPRINT
            and all(_chain_passed(chain) for chain in chain_values),
            {
                "runtime_version": release.get("runtime_version"),
                "developer_kit_version": kit.get("developer_kit_version"),
                "extension_ids": sorted(chains),
            },
        ),
        _check(_PLATFORM_CHECK_IDS[2], suite.get("status") == "PASS", suite),
        _check(
            _PLATFORM_CHECK_IDS[3],
            _chain_passed(alpha),
            {"result_fingerprint": alpha.get("result_fingerprint")},
        ),
        _check(
            _PLATFORM_CHECK_IDS[4],
            _chain_passed(beta),
            {"result_fingerprint": beta.get("result_fingerprint")},
        ),
        _check(
            _PLATFORM_CHECK_IDS[5],
            all(
                _mapping(chain.get("http_statuses"), field="chain.http_statuses").get(
                    "replayed"
                )
                == 202
                and _mapping(chain.get("output"), field="chain.output").get(
                    "idempotent_export_replay"
                )
                is True
                for chain in chain_values
            ),
            {"chain_count": len(chain_values), "duplicate_business_results": 0},
        ),
        _check(
            _PLATFORM_CHECK_IDS[6],
            all(
                _mapping(chain.get("http_statuses"), field="chain.http_statuses").get(
                    "unauthorized_create"
                )
                == 401
                and _mapping(
                    chain.get("http_statuses"), field="chain.http_statuses"
                ).get("unauthorized_schedule_read")
                == 401
                for chain in chain_values
            )
            and security.get("authorization_default_deny") is True
            and security.get("payload_or_secret_in_metrics") is False
            and source_audit.get("status") == "PASS",
            {
                "authorization_default_deny": True,
                "payload_or_secret_recorded": False,
                "targeted_headless_family": cast(
                    JsonObject, suite.get("required_family_coverage", {})
                ).get("test_p8_headless"),
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[7],
            mixed.get("status") == "PASS"
            and mixed.get("error_code") == "RUNTIME_MISMATCH"
            and mixed.get("worker_result_count") == 0
            and mixed.get("partial_result") is False,
            mixed,
        ),
        _check(
            _PLATFORM_CHECK_IDS[8],
            duplicate.get("status") == "PASS"
            and duplicate.get("error_code") == "EXT_SET_CONFLICT",
            duplicate,
        ),
        _check(
            _PLATFORM_CHECK_IDS[9],
            formal_counts.get("mutation_cases") == 13
            and mutation_counts.get("cases") == 13,
            {
                "formal_mutations": formal_counts.get("mutation_cases"),
                "fixture_mutations": mutation_counts.get("cases"),
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[10],
            reports["runtime_migration"].get("status") == "PASS"
            and reports["operations_recovery"].get("status") == "PASS"
            and deployment.get("backup_restore_status") == "PASS"
            and deployment.get("restore_identity_match") is True
            and deployment.get("rollback_identity_match") is True
            and kit.get("automatic_upgrade") is False,
            {
                "runtime_migration": reports["runtime_migration"].get("status"),
                "backup_restore": deployment.get("backup_restore_status"),
                "restore_identity_match": deployment.get("restore_identity_match"),
                "rollback_identity_match": deployment.get("rollback_identity_match"),
                "automatic_upgrade": kit.get("automatic_upgrade"),
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[11],
            all(
                reports[name].get("status") == "PASS"
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
            _PLATFORM_CHECK_IDS[12],
            deployment.get("status") == "PASS"
            and deployment.get("candidate_api_worker_match") is True
            and extension_identity.get("extension_ids") == ["com.example.aps.alpha"]
            and extension_identity.get("developer_kit_fingerprint")
            == DEVELOPER_KIT_FINGERPRINT,
            {
                "extension_ids": extension_identity.get("extension_ids"),
                "candidate_api_worker_match": deployment.get(
                    "candidate_api_worker_match"
                ),
                "restore_identity_match": deployment.get("restore_identity_match"),
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[13],
            invocation.get("extension_point_coverage")
            == [
                "CONSTRAINT",
                "OBJECTIVE",
                "PLANNING_RULE",
                "PLUGIN_REGISTRY",
                "REPLAN_POLICY",
                "VALIDATION_RULE",
            ]
            and all(
                chain.get("all_selected_contributions_invoked") is True
                for chain in chain_values
            )
            and source_audit.get("observed_methods")
            == [
                "invoke_constraints",
                "invoke_objectives",
                "invoke_planning_rules",
                "invoke_plugin_registry",
                "invoke_replan_policy",
                "invoke_validation_rules",
            ],
            {
                "extension_point_coverage": invocation.get("extension_point_coverage"),
                "chain_count": len(chain_values),
                "all_selected_contributions_invoked": all(
                    chain.get("all_selected_contributions_invoked") is True
                    for chain in chain_values
                ),
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[14],
            kit.get("developer_kit_version") == DEVELOPER_KIT_VERSION
            and kit.get("developer_kit_fingerprint") == DEVELOPER_KIT_FINGERPRINT
            and kit.get("automatic_upgrade") is False
            and all(
                _mapping(
                    chain.get("runtime_resolution"), field="chain.runtime_resolution"
                ).get("developer_kit_version")
                == DEVELOPER_KIT_VERSION
                and _mapping(
                    chain.get("runtime_resolution"), field="chain.runtime_resolution"
                ).get("developer_kit_fingerprint")
                == DEVELOPER_KIT_FINGERPRINT
                for chain in chain_values
            ),
            {
                "developer_kit_version": kit.get("developer_kit_version"),
                "developer_kit_fingerprint": kit.get("developer_kit_fingerprint"),
                "automatic_upgrade": kit.get("automatic_upgrade"),
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[15],
            output.get("authorization_default_deny") is True
            and output.get("explicit_approve_publish_export") is True
            and output.get("automatic_publication") is False
            and output.get("idempotent_export") is True
            and all(
                _mapping(chain.get("output"), field="chain.output").get(
                    "final_schedule_state"
                )
                == "PUBLISHED"
                for chain in chain_values
            ),
            {
                "published_chain_count": sum(
                    _mapping(chain.get("output"), field="chain.output").get(
                        "final_schedule_state"
                    )
                    == "PUBLISHED"
                    for chain in chain_values
                ),
                "explicit_approve_publish_export": output.get(
                    "explicit_approve_publish_export"
                ),
                "idempotent_export": output.get("idempotent_export"),
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[16],
            elapsed_ms <= _MAXIMUM_GATE_RUNTIME_MS
            and maximum_chain_ms <= _MAXIMUM_SINGLE_CHAIN_MS
            and benchmark.get("status") == "PASS",
            {
                "gate_runtime_ms": elapsed_ms,
                "maximum_gate_runtime_ms": _MAXIMUM_GATE_RUNTIME_MS,
                "maximum_chain_ms": maximum_chain_ms,
                "maximum_single_chain_ms": _MAXIMUM_SINGLE_CHAIN_MS,
            },
        ),
        _check(
            _PLATFORM_CHECK_IDS[17],
            profile.get("boundaries")
            == {
                "canonical_json_only": True,
                "real_data": False,
                "production_authorized": False,
                "p7_reality_calibration": False,
                "demo_included": False,
                "third_party_connector": False,
                "capacity_or_sla": False,
            },
            cast(JsonObject, profile.get("boundaries", {})),
        ),
    ]
    if tuple(check["check_id"] for check in checks) != _PLATFORM_CHECK_IDS:
        raise AssertionError("P8-19 platform check inventory drifted")
    return checks


def _closure_assertions(checks: Sequence[JsonObject]) -> list[JsonObject]:
    by_id = {cast(str, check["check_id"]): check for check in checks}
    return [
        {
            "blocker_id": blocker_id,
            "historical_p8_16_status": "BLOCKED",
            "corrective_p8_18_status": "PASS",
            "requalification_p8_19_status": by_id[check_id]["status"],
            "status": by_id[check_id]["status"],
            "source_check_id": check_id,
            "historical_verdict_changed": False,
        }
        for blocker_id, check_id in _CLOSURE_CHECKS.items()
    ]


def _blocking_gaps(
    checks: Sequence[JsonObject], closure_assertions: Sequence[JsonObject]
) -> list[JsonObject]:
    closure_by_check = {
        check_id: blocker_id for blocker_id, check_id in _CLOSURE_CHECKS.items()
    }
    gaps: list[JsonObject] = []
    for index, check in enumerate(checks, start=1):
        if check["status"] == "PASS":
            continue
        check_id = cast(str, check["check_id"])
        gap_id = closure_by_check.get(
            check_id, f"P8-REQUALIFICATION-REGRESSION-{index:03d}"
        )
        gaps.append(
            {
                "gap_id": gap_id,
                "source_check_id": check_id,
                "category": (
                    "HISTORICAL_BLOCKER_REOPENED"
                    if check_id in closure_by_check
                    else "P8_16_PASS_REGRESSION"
                ),
                "status": "BLOCKED",
                "evidence": check["evidence"],
                "production_waiver_allowed": False,
                "corrective_owner": "FUTURE_BOUNDED_CORRECTIVE_TASK",
            }
        )
    for assertion in closure_assertions:
        if assertion["status"] != "PASS" and not any(
            gap["gap_id"] == assertion["blocker_id"] for gap in gaps
        ):
            gaps.append(
                {
                    "gap_id": assertion["blocker_id"],
                    "source_check_id": assertion["source_check_id"],
                    "category": "HISTORICAL_BLOCKER_REOPENED",
                    "status": "BLOCKED",
                    "evidence": dict(assertion),
                    "production_waiver_allowed": False,
                    "corrective_owner": "FUTURE_BOUNDED_CORRECTIVE_TASK",
                }
            )
    return gaps


def _base(report_version: str, *, code_commit: str) -> JsonObject:
    return {
        "report_version": report_version,
        "status": "PASS",
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "validation_profile": VALIDATION_PROFILE,
        "diff_base": DIFF_BASE,
        "code_commit": code_commit,
        "issues": [],
        "production_ready": False,
    }


def _write_outputs(
    *,
    paths: Mapping[str, Path],
    main: JsonObject,
    supports: Mapping[str, JsonObject],
) -> None:
    for name, report in supports.items():
        _fingerprinted(report)
        _write_json(paths[name], report)
    main["evidence"] = {
        name: {
            "report_version": report["report_version"],
            "report_fingerprint": report["report_fingerprint"],
        }
        for name, report in supports.items()
    }
    _fingerprinted(main)
    validate_requalification_report(main)
    _write_json(paths["report"], main)


def run_gate(
    root: Path,
    *,
    profile_path: Path,
    junit_path: Path,
    input_paths: Mapping[str, Path],
    output_paths: Mapping[str, Path],
) -> JsonObject:
    started = perf_counter()
    root = root.resolve()
    code_commit = _git_head(root)
    profile = validate_requalification_profile(
        _read_json(profile_path, field="profile")
    )
    history = _verify_frozen_history(root, profile_path)
    suite = _junit_summary(junit_path)
    reports = _load_current_reports(input_paths, code_commit=code_commit)
    current_corrective = {
        name: reports[name]
        for name in (
            "corrective",
            "corrective_invocation",
            "corrective_kit",
            "corrective_output",
            "corrective_deployment",
            "corrective_security",
            "corrective_benchmark",
        )
    }
    _validate_corrective_links(current_corrective)
    replay = _run_fresh_corrective_replay(
        root,
        junit_path=junit_path,
        operations_deployment=input_paths["operations_deployment"],
        operations_recovery=input_paths["operations_recovery"],
        code_commit=code_commit,
    )
    if _semantic_corrective_projection(
        current_corrective
    ) != _semantic_corrective_projection(replay):
        _fail(
            "REQUALIFICATION_REPLAY_DRIFT",
            field="corrective_replay",
            message="independent product replay differs from the current P8-18 carrier",
        )
    mixed, duplicate = _frozen_runner_negatives(root, code_commit=code_commit)
    elapsed_ms = round((perf_counter() - started) * 1_000, 3)
    checks = _build_checks(
        profile=profile,
        history=history,
        suite=suite,
        reports=reports,
        replay=replay,
        mixed=mixed,
        duplicate=duplicate,
        elapsed_ms=elapsed_ms,
    )
    closures = _closure_assertions(checks)
    gaps = _blocking_gaps(checks, closures)
    blocked_checks = sum(check["status"] == "BLOCKED" for check in checks)
    blocked_closures = sum(row["status"] == "BLOCKED" for row in closures)
    verdict = "READY" if not gaps else "NOT_READY"

    disposition = _base(DISPOSITION_VERSION, code_commit=code_commit)
    disposition.update(
        {
            "historical_p8_16_verdict": "NOT_READY",
            "historical_p8_16_verdict_changed": False,
            "assertions": closures,
            "summary": {
                "assertion_count": len(closures),
                "pass_count": len(closures) - blocked_closures,
                "blocked_count": blocked_closures,
            },
            "requalification_verdict": verdict,
        }
    )
    provenance = _base(PROVENANCE_VERSION, code_commit=code_commit)
    provenance.update(
        {
            "immutable_history": history,
            "current_inputs": _report_projection(reports),
            "independent_replay": _report_projection(replay),
            "semantic_replay_match": True,
            "frozen_p8_16_runner_reused_read_only": True,
        }
    )
    compatibility = _base(COMPATIBILITY_VERSION, code_commit=code_commit)
    compatibility.update(
        {
            "developer_kit": {
                "version": DEVELOPER_KIT_VERSION,
                "fingerprint": DEVELOPER_KIT_FINGERPRINT,
                "automatic_upgrade": False,
            },
            "extensions": [
                {
                    "extension_id": item["extension_id"],
                    "artifact_digest": item["artifact_digest"],
                    "manifest_fingerprint": item["manifest_fingerprint"],
                }
                for item in _EXTENSIONS
            ],
            "mixed_runtime_extension_negative": dict(mixed),
            "duplicate_extension_negative": dict(duplicate),
            "runtime_kit_binding": checks[14]["status"],
        }
    )
    security = _base(SECURITY_VERSION, code_commit=code_commit)
    security.update(
        {
            "runtime_security": reports["runtime_security"].get("status"),
            "frontend_security": reports["frontend_security"].get("status"),
            "operations_observability": reports["operations_observability"].get(
                "status"
            ),
            "product_security": replay["corrective_security"],
            "source_audit": replay["corrective_invocation"].get("source_audit"),
            "payload_or_secret_recorded": False,
        }
    )
    recovery = _base(RECOVERY_VERSION, code_commit=code_commit)
    recovery.update(
        {
            "runtime_migration": reports["runtime_migration"].get("status"),
            "operations_recovery": reports["operations_recovery"].get("status"),
            "operations_runbooks": reports["operations_runbooks"].get("status"),
            "extension_deployment_recovery": replay["corrective_deployment"],
            "kit_mismatch_negative": replay["corrective_kit"].get(
                "api_worker_mismatch_negative"
            ),
            "mixed_extension_negative": mixed,
            "duplicate_extension_negative": duplicate,
        }
    )
    benchmark = _base(BENCHMARK_VERSION, code_commit=code_commit)
    benchmark.update(
        {
            "profile_version": profile["profile_version"],
            "profile_fingerprint": profile["profile_fingerprint"],
            "environment": "SYNTHETIC_ENGINEERING_ONLY",
            "observations": {
                "gate_runtime_ms": elapsed_ms,
                "maximum_chain_ms": replay["corrective_benchmark"].get(
                    "maximum_chain_ms"
                ),
                "targeted_p8_tests": suite["tests"],
            },
            "thresholds": {
                "maximum_gate_runtime_ms": _MAXIMUM_GATE_RUNTIME_MS,
                "maximum_single_chain_ms": _MAXIMUM_SINGLE_CHAIN_MS,
                "minimum_targeted_p8_tests": _MINIMUM_TARGETED_TESTS,
            },
            "thresholds_passed": checks[16]["status"] == "PASS",
            "p7_reality_or_production_capacity": "NOT_ESTABLISHED",
        }
    )
    supports = {
        "blocker_disposition": disposition,
        "provenance": provenance,
        "compatibility": compatibility,
        "security": security,
        "recovery": recovery,
        "benchmark": benchmark,
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
        },
        "historical_p8_16": cast(JsonObject, history["p8_16"]),
        "direct_dependency_p8_18": cast(JsonObject, history["p8_18"]),
        "platform_checks": checks,
        "closure_assertions": closures,
        "check_summary": {
            "platform_check_count": len(checks),
            "platform_pass_count": len(checks) - blocked_checks,
            "platform_blocked_count": blocked_checks,
            "closure_assertion_count": len(closures),
            "closure_pass_count": len(closures) - blocked_closures,
            "closure_blocked_count": blocked_closures,
            "error_count": 0,
        },
        "blocking_gaps": gaps,
        "issues": [],
        "scope": {
            "synthetic_engineering_requalification": True,
            "canonical_json_only": True,
            "real_data": False,
            "p7_reality_calibration": False,
            "production_ready": False,
            "capacity_or_sla": False,
            "demo_included": False,
            "third_party_connector": False,
        },
        "next": {
            "p8_exit_gate_task": "TASK-P8-17",
            "eligible_to_request": verdict == "READY",
            "p8_exit_gate_authorized": False,
            "automatic_start": False,
            "production_ready": False,
        },
    }
    _write_outputs(paths=output_paths, main=main, supports=supports)
    return main


def validate_requalification_report(document: Mapping[str, object]) -> None:
    expected_keys = {
        "report_version",
        "audit_status",
        "verdict",
        "task_id",
        "test_id",
        "validation_profile",
        "diff_base",
        "code_commit",
        "profile",
        "historical_p8_16",
        "direct_dependency_p8_18",
        "platform_checks",
        "closure_assertions",
        "check_summary",
        "blocking_gaps",
        "issues",
        "scope",
        "next",
        "evidence",
        "report_fingerprint",
    }
    code_commit = document.get("code_commit")
    if set(document) != expected_keys or (
        document.get("report_version") != REPORT_VERSION
        or document.get("audit_status") != "PASS"
        or document.get("verdict") not in {"READY", "NOT_READY"}
        or document.get("task_id") != TASK_ID
        or document.get("test_id") != TEST_ID
        or document.get("validation_profile") != VALIDATION_PROFILE
        or document.get("diff_base") != DIFF_BASE
        or document.get("issues") != []
        or not isinstance(code_commit, str)
        or len(code_commit) != 40
        or any(character not in "0123456789abcdef" for character in code_commit)
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.identity",
            message="requalification report identity is invalid",
        )
    checks = document.get("platform_checks")
    if (
        not isinstance(checks, list)
        or tuple(
            check.get("check_id") if isinstance(check, dict) else None
            for check in checks
        )
        != _PLATFORM_CHECK_IDS
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.platform_checks",
            message="the 18-item P8 platform check inventory is incomplete",
        )
    if any(
        not isinstance(check, dict)
        or set(check) != {"check_id", "status", "evidence"}
        or check.get("status") not in {"PASS", "BLOCKED"}
        or not isinstance(check.get("evidence"), dict)
        for check in checks
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.platform_checks",
            message="a platform check carrier is invalid",
        )
    closures = document.get("closure_assertions")
    if (
        not isinstance(closures, list)
        or tuple(
            row.get("blocker_id") if isinstance(row, dict) else None for row in closures
        )
        != _P8_16_BLOCKERS
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.closure_assertions",
            message="the four historical blocker assertions are incomplete",
        )
    if any(
        not isinstance(row, dict)
        or set(row)
        != {
            "blocker_id",
            "historical_p8_16_status",
            "corrective_p8_18_status",
            "requalification_p8_19_status",
            "status",
            "source_check_id",
            "historical_verdict_changed",
        }
        or row.get("historical_p8_16_status") != "BLOCKED"
        or row.get("corrective_p8_18_status") != "PASS"
        or row.get("status") not in {"PASS", "BLOCKED"}
        or row.get("status") != row.get("requalification_p8_19_status")
        or row.get("historical_verdict_changed") is not False
        or _CLOSURE_CHECKS.get(cast(str, row.get("blocker_id")))
        != row.get("source_check_id")
        for row in closures
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.closure_assertions",
            message="a historical blocker disposition is invalid",
        )
    blocked_checks = sum(check["status"] == "BLOCKED" for check in checks)
    blocked_closures = sum(row["status"] == "BLOCKED" for row in closures)
    expected_summary = {
        "platform_check_count": 18,
        "platform_pass_count": 18 - blocked_checks,
        "platform_blocked_count": blocked_checks,
        "closure_assertion_count": 4,
        "closure_pass_count": 4 - blocked_closures,
        "closure_blocked_count": blocked_closures,
        "error_count": 0,
    }
    if document.get("check_summary") != expected_summary:
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.check_summary",
            message="requalification check totals are inconsistent",
        )
    gaps = document.get("blocking_gaps")
    if not isinstance(gaps, list) or any(not isinstance(gap, dict) for gap in gaps):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.blocking_gaps",
            message="blocking gap inventory is invalid",
        )
    if gaps != _blocking_gaps(
        cast(list[JsonObject], checks), cast(list[JsonObject], closures)
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.blocking_gaps",
            message="blocking gaps do not match failed checks and closure assertions",
        )
    if (
        document.get("verdict") == "READY"
        and (gaps or blocked_checks or blocked_closures)
    ) or (
        document.get("verdict") == "NOT_READY"
        and (not gaps or (not blocked_checks and not blocked_closures))
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.verdict",
            message="binary verdict does not match the blocking evidence",
        )
    historical = document.get("historical_p8_16")
    if (
        not isinstance(historical, dict)
        or historical.get("final_sha") != P8_16_FINAL_SHA
        or historical.get("provider_run_id") != P8_16_PROVIDER_RUN_ID
        or historical.get("required_validate_job_id") != P8_16_REQUIRED_VALIDATE_JOB_ID
        or historical.get("verdict") != "NOT_READY"
        or historical.get("blocking_gaps") != list(_P8_16_BLOCKERS)
        or historical.get("reports")
        != {
            name: {"report_version": version, "report_fingerprint": fingerprint}
            for name, (version, fingerprint) in _P8_16_REPORTS.items()
        }
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.historical_p8_16",
            message="immutable P8-16 history differs from exact Provider evidence",
        )
    dependency = document.get("direct_dependency_p8_18")
    if (
        not isinstance(dependency, dict)
        or dependency.get("closure_sha") != DIFF_BASE
        or dependency.get("runtime_implementation_sha")
        != P8_18_RUNTIME_IMPLEMENTATION_SHA
        or dependency.get("provider_run_id") != P8_18_PROVIDER_RUN_ID
        or dependency.get("required_validate_job_id") != P8_18_REQUIRED_VALIDATE_JOB_ID
    ):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.direct_dependency_p8_18",
            message="P8-18 exact dependency identity is invalid",
        )
    if document.get("scope") != {
        "synthetic_engineering_requalification": True,
        "canonical_json_only": True,
        "real_data": False,
        "p7_reality_calibration": False,
        "production_ready": False,
        "capacity_or_sla": False,
        "demo_included": False,
        "third_party_connector": False,
    }:
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.scope",
            message="requalification crossed the P7 or Production boundary",
        )
    expected_next = {
        "p8_exit_gate_task": "TASK-P8-17",
        "eligible_to_request": document.get("verdict") == "READY",
        "p8_exit_gate_authorized": False,
        "automatic_start": False,
        "production_ready": False,
    }
    if document.get("next") != expected_next:
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.next",
            message="P8-17 successor disposition is invalid",
        )
    evidence = document.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != set(_SUPPORT_VERSIONS):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.evidence",
            message="six support report references are incomplete",
        )
    for name, version in _SUPPORT_VERSIONS.items():
        item = evidence[name]
        if (
            not isinstance(item, dict)
            or item.get("report_version") != version
            or set(item) != {"report_version", "report_fingerprint"}
            or not _is_sha256(item.get("report_fingerprint"))
        ):
            _fail(
                "REQUALIFICATION_REPORT_INVALID",
                field=f"report.evidence.{name}",
                message="a support report reference is invalid",
            )
    projection = dict(document)
    provided = projection.pop("report_fingerprint", None)
    if provided != canonical_fingerprint(projection):
        _fail(
            "REQUALIFICATION_REPORT_INVALID",
            field="report.report_fingerprint",
            message="requalification report fingerprint differs from content",
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
            "error_code": getattr(error, "code", "REQUALIFICATION_EXECUTION_FAILED"),
            "error_field": getattr(error, "field", "gate"),
            "issues": [getattr(error, "code", "REQUALIFICATION_EXECUTION_FAILED")],
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
    for name in _CURRENT_REPORTS:
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--blocker-disposition-report", type=Path, required=True)
    parser.add_argument("--provenance-report", type=Path, required=True)
    parser.add_argument("--compatibility-report", type=Path, required=True)
    parser.add_argument("--security-report", type=Path, required=True)
    parser.add_argument("--recovery-report", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report_path = args.report.resolve()
    input_paths = {
        name: cast(Path, getattr(args, name)).resolve() for name in _CURRENT_REPORTS
    }
    output_paths = {
        "report": report_path,
        "blocker_disposition": args.blocker_disposition_report.resolve(),
        "provenance": args.provenance_report.resolve(),
        "compatibility": args.compatibility_report.resolve(),
        "security": args.security_report.resolve(),
        "recovery": args.recovery_report.resolve(),
        "benchmark": args.benchmark_report.resolve(),
    }
    try:
        report = run_gate(
            args.root,
            profile_path=args.profile.resolve(),
            junit_path=args.junit.resolve(),
            input_paths=input_paths,
            output_paths=output_paths,
        )
    except Exception as error:  # noqa: BLE001 - CLI emits only stable safe fields
        failure = _failure_report(error)
        _write_json(report_path, failure)
        print(json.dumps(failure, ensure_ascii=False, separators=(",", ":")))
        return 1
    summary = cast(JsonObject, report["check_summary"])
    print(
        f"{report['verdict']} {TASK_ID}: "
        f"platform={summary['platform_pass_count']}/18 "
        f"closures={summary['closure_pass_count']}/4"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BENCHMARK_VERSION",
    "COMPATIBILITY_VERSION",
    "DIFF_BASE",
    "DISPOSITION_VERSION",
    "PROFILE_FINGERPRINT",
    "PROVENANCE_VERSION",
    "RECOVERY_VERSION",
    "REPORT_VERSION",
    "RequalificationError",
    "SECURITY_VERSION",
    "TASK_ID",
    "TEST_ID",
    "VALIDATION_PROFILE",
    "main",
    "run_gate",
    "validate_requalification_profile",
    "validate_requalification_report",
]
