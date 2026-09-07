"""Fail-closed, secret-free APS Runtime release preflight."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence, Set
from pathlib import Path
import re
from typing import Any, NoReturn, cast

from app import RUNTIME_VERSION
from app.infrastructure.release.contracts import (
    ReleaseContractError,
    VerifiedRelease,
    canonical_json_bytes,
    read_release_directory,
    sha256_hex,
    strict_json_document,
    verify_release_archive,
    verify_release_files,
)


type JsonObject = dict[str, Any]

PREFLIGHT_REPORT_VERSION = "aps-runtime-preflight-report.v1"
_SIDECAR = re.compile(r"([0-9a-f]{64})  ([^\r\n]+)\n?")


class ReleasePreflightError(ReleaseContractError):
    """Stable preflight rejection that never contains secret values."""


def _fail(code: str, message: str) -> NoReturn:
    raise ReleasePreflightError(code, message)


def _verify_sidecar(path: Path) -> None:
    sidecar = path.with_name(f"{path.name}.sha256")
    try:
        raw = sidecar.read_text(encoding="utf-8")
    except OSError as error:
        raise ReleasePreflightError("CHECKSUM_MISSING", "archive checksum sidecar is missing") from error
    match = _SIDECAR.fullmatch(raw)
    if match is None or match.group(2) != path.name:
        _fail("CHECKSUM_INVALID", "archive checksum sidecar is malformed")
    if match.group(1) != sha256_hex(path.read_bytes()):
        _fail("CHECKSUM_MISMATCH", "archive checksum sidecar does not match")


def _verify_candidate(
    path: Path,
    *,
    expected_runtime_version: str,
    expected_code_commit: str,
) -> VerifiedRelease:
    if path.is_dir():
        return verify_release_files(
            read_release_directory(path),
            release_root=path.name,
            expected_runtime_version=expected_runtime_version,
            expected_code_commit=expected_code_commit,
        )
    _verify_sidecar(path)
    return verify_release_archive(
        path,
        expected_runtime_version=expected_runtime_version,
        expected_code_commit=expected_code_commit,
    )


def preflight_release(
    path: Path,
    *,
    expected_code_commit: str,
    configured_names: Set[str],
    expected_runtime_version: str = RUNTIME_VERSION,
    production_requested: bool = False,
) -> JsonObject:
    """Verify one release and the names (never values) of external settings."""

    if production_requested:
        _fail(
            "PRODUCTION_AUTHORITY_UNAVAILABLE",
            "engineering candidate cannot be promoted or started as Production",
        )
    verified = _verify_candidate(
        path,
        expected_runtime_version=expected_runtime_version,
        expected_code_commit=expected_code_commit,
    )
    embedded_policy = strict_json_document(
        verified.files["policy/runtime-release-policy.v1.json"]
    )
    target = verified.manifest.get("target")
    expected_target = embedded_policy.get("target")
    if target != expected_target or target != {
        "architecture": "amd64",
        "operating_system": "linux",
        "python_implementation": "CPython",
        "python_version": "3.12.13",
    }:
        _fail("TARGET_MISMATCH", "release target is unsupported")
    preflight = embedded_policy.get("preflight")
    if not isinstance(preflight, dict):
        _fail("POLICY_INVALID", "embedded preflight policy is missing")
    raw_required = preflight.get("required_configuration_names")
    if not isinstance(raw_required, list) or not all(
        isinstance(value, str) for value in raw_required
    ):
        _fail("POLICY_INVALID", "required configuration inventory is invalid")
    required = set(cast(list[str], raw_required))
    missing = sorted(required - set(configured_names))
    if missing:
        _fail(
            "CONFIGURATION_MISSING",
            "required external configuration names are absent: " + ",".join(missing),
        )
    extension = verified.manifest.get("extension_boundary")
    if not isinstance(extension, dict) or extension.get("bundled_extensions") != []:
        _fail("EXTENSION_BOUNDARY_INVALID", "release must use the default-empty Extension seam")
    if extension.get("frontend_bundled") is not False or extension.get("third_party_connectors_bundled") is not False:
        _fail("DISTRIBUTION_SCOPE_INVALID", "release contains a forbidden optional surface")

    required_payload = {
        "runtime/alembic.ini",
        "runtime/backend/migrations/env.py",
        "runtime/openapi/headless-api.v1.json",
        "runtime/requirements/runtime-requirements.lock",
        "runtime/schemas/json/canonical-ingress-request.schema.json",
    }
    if not required_payload <= set(verified.files):
        _fail("RELEASE_INCOMPLETE", "runtime payload is incomplete")
    wheel_paths = [name for name in verified.files if name.startswith("runtime/wheels/")]
    if len(wheel_paths) != 1 or not wheel_paths[0].endswith(".whl"):
        _fail("RELEASE_INCOMPLETE", "runtime wheel inventory is invalid")

    return {
        "report_version": PREFLIGHT_REPORT_VERSION,
        "runtime_version": verified.runtime_version,
        "code_commit": verified.code_commit,
        "release_fingerprint": verified.release_fingerprint,
        "target": target,
        "configuration": {
            "required_names": sorted(required),
            "configured_names": sorted(required & set(configured_names)),
            "secret_values_observed": False,
        },
        "checks": [
            {"check_id": "archive-and-sidecar-integrity", "passed": True},
            {"check_id": "manifest-and-payload-integrity", "passed": True},
            {"check_id": "exact-version-and-commit", "passed": True},
            {"check_id": "linux-amd64-cpython-target", "passed": True},
            {"check_id": "external-configuration-names-complete", "passed": True},
            {"check_id": "default-empty-extension-and-no-optional-ui", "passed": True},
            {"check_id": "migration-schema-openapi-wheel-present", "passed": True},
        ],
        "production_ready": False,
        "issues": [],
        "status": "PASS",
    }


def _write(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(document) + b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--expected-code-commit", required=True)
    parser.add_argument("--expected-runtime-version", default=RUNTIME_VERSION)
    parser.add_argument("--configured", action="append", default=[])
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = preflight_release(
            arguments.archive,
            expected_code_commit=arguments.expected_code_commit,
            expected_runtime_version=arguments.expected_runtime_version,
            configured_names=set(arguments.configured),
            production_requested=arguments.production,
        )
    except ReleaseContractError as error:
        report = {
            "report_version": PREFLIGHT_REPORT_VERSION,
            "runtime_version": arguments.expected_runtime_version,
            "code_commit": arguments.expected_code_commit,
            "checks": [],
            "production_ready": False,
            "issues": [error.code],
            "status": "FAIL",
        }
    _write(arguments.report, report)
    print(f"{report['status']} Runtime preflight: issues={len(cast(list[object], report['issues']))}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PREFLIGHT_REPORT_VERSION",
    "ReleasePreflightError",
    "main",
    "preflight_release",
]
