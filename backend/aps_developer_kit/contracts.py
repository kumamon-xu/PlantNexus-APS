"""Strict contracts for immutable APS Developer Kit engineering releases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
from tempfile import TemporaryDirectory
from typing import Any, NoReturn, cast
from zipfile import BadZipFile, ZipFile

from app.infrastructure.release.contracts import verify_release_archive


type JsonObject = dict[str, Any]

KIT_MANIFEST_VERSION = "aps-developer-kit-release-manifest.v1"
COMPATIBILITY_MATRIX_VERSION = "aps-developer-kit-compatibility-matrix.v1"
KIT_LOCK_VERSION = "aps-developer-kit-lock.v1"
SUPPORT_POLICY_VERSION = "aps-developer-kit-support-policy.v1"
SIGNING_REQUEST_VERSION = "aps-developer-kit-signing-request.v1"
LICENSE_REPORT_VERSION = "aps-developer-kit-license-report.v1"
CORE_SOURCE_INVENTORY_VERSION = "aps-core-source-hash-inventory.v1"
SBOM_SPEC_VERSION = "1.5"

MANIFEST_PATH = "metadata/developer-kit-manifest.json"
COMPATIBILITY_PATH = "metadata/compatibility-matrix.json"
LOCK_PATH = "metadata/developer-kit-lock.json"
SUPPORT_PATH = "metadata/support-deprecation-policy.json"
SIGNING_PATH = "metadata/signing-request.json"
LICENSE_PATH = "metadata/license-report.json"
SBOM_PATH = "metadata/sbom.cdx.json"
CORE_SOURCE_INVENTORY_PATH = "metadata/core-source-hashes.json"
CHECKSUM_PATH = "metadata/checksums.sha256"

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
_MAX_MEMBER_COUNT = 16_384
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


class DeveloperKitContractError(ValueError):
    """Payload-free Developer Kit rejection with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _reject(code: str, message: str) -> NoReturn:
    raise DeveloperKitContractError(code, message)


def _reject_constant(value: str) -> NoReturn:
    del value
    _reject("KIT_JSON_INVALID", "unsupported JSON constant")


def _strict_pairs(pairs: Sequence[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _reject("KIT_JSON_INVALID", "duplicate JSON object key")
        result[key] = value
    return result


def strict_json_document(raw: bytes) -> JsonObject:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_constant,
        )
    except DeveloperKitContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DeveloperKitContractError(
            "KIT_JSON_INVALID", "document is not strict UTF-8 JSON"
        ) from error
    if not isinstance(value, dict):
        _reject("KIT_JSON_INVALID", "top-level JSON value must be an object")
    return cast(JsonObject, value)


def canonical_json_bytes(document: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise DeveloperKitContractError(
            "KIT_JSON_INVALID", "document is not canonicalizable"
        ) from error


def sha256_fingerprint(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _safe_member(raw: str) -> PurePosixPath:
    if not raw or "\\" in raw or raw.startswith("/") or "\x00" in raw:
        _reject("KIT_ARCHIVE_UNSAFE", "archive member path is unsafe")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        _reject("KIT_ARCHIVE_UNSAFE", "archive member path is unsafe")
    return path


def read_kit_archive(path: Path) -> tuple[str, dict[str, bytes]]:
    """Read a bounded single-root Kit ZIP without following unsafe members."""

    try:
        archive_bytes = path.read_bytes()
    except OSError as error:
        raise DeveloperKitContractError(
            "KIT_ARCHIVE_UNAVAILABLE", "Developer Kit archive is unavailable"
        ) from error
    if not 1 <= len(archive_bytes) <= _MAX_ARCHIVE_BYTES:
        _reject("KIT_ARCHIVE_SIZE_INVALID", "archive size is outside policy")
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    total = 0
    try:
        with ZipFile(BytesIO(archive_bytes), "r") as archive:
            members = archive.infolist()
            if len(members) > _MAX_MEMBER_COUNT:
                _reject("KIT_ARCHIVE_SIZE_INVALID", "archive member count exceeds policy")
            seen: set[str] = set()
            for member in members:
                path_value = _safe_member(member.filename)
                normalized = path_value.as_posix()
                if normalized in seen:
                    _reject("KIT_ARCHIVE_UNSAFE", "archive contains duplicate members")
                seen.add(normalized)
                roots.add(path_value.parts[0])
                if member.is_dir():
                    continue
                if member.flag_bits & 0x1 or len(path_value.parts) < 2:
                    _reject("KIT_ARCHIVE_UNSAFE", "archive member is encrypted or unrooted")
                relative = PurePosixPath(*path_value.parts[1:]).as_posix()
                raw = archive.read(member)
                total += len(raw)
                if total > _MAX_ARCHIVE_BYTES:
                    _reject("KIT_ARCHIVE_SIZE_INVALID", "expanded archive exceeds policy")
                files[relative] = raw
    except DeveloperKitContractError:
        raise
    except (BadZipFile, OSError, RuntimeError) as error:
        raise DeveloperKitContractError(
            "KIT_ARCHIVE_INVALID", "Developer Kit archive cannot be decoded"
        ) from error
    if len(roots) != 1 or not files:
        _reject("KIT_ARCHIVE_INVALID", "archive must have one non-empty root")
    return next(iter(roots)), files


def _checksums(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise DeveloperKitContractError(
            "KIT_CHECKSUM_INVALID", "checksum file is not UTF-8"
        ) from error
    result: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        if match is None:
            _reject("KIT_CHECKSUM_INVALID", "checksum line is malformed")
        digest, raw_path = match.groups()
        normalized = _safe_member(raw_path).as_posix()
        if normalized == CHECKSUM_PATH or normalized in result:
            _reject("KIT_CHECKSUM_INVALID", "checksum inventory is recursive or duplicated")
        result[normalized] = digest
    if not result:
        _reject("KIT_CHECKSUM_INVALID", "checksum inventory is empty")
    return result


def _object(document: Mapping[str, object], key: str) -> JsonObject:
    value = document.get(key)
    if not isinstance(value, dict):
        _reject("KIT_MANIFEST_INVALID", f"{key} must be an object")
    return cast(JsonObject, value)


def _artifact(lock: Mapping[str, object], key: str, files: Mapping[str, bytes]) -> JsonObject:
    artifacts = _object(lock, "artifacts")
    value = artifacts.get(key)
    if not isinstance(value, dict) or set(value) != {"path", "sha256", "bytes"}:
        _reject("KIT_LOCK_INVALID", "locked artifact entry is malformed")
    entry = cast(JsonObject, value)
    path = entry.get("path")
    digest = entry.get("sha256")
    size = entry.get("bytes")
    if (
        not isinstance(path, str)
        or path not in files
        or not isinstance(digest, str)
        or _SHA256.fullmatch(digest) is None
        or digest != sha256_fingerprint(files[path])
        or not isinstance(size, int)
        or isinstance(size, bool)
        or size != len(files[path])
    ):
        _reject("KIT_LOCK_DRIFT", "locked artifact bytes differ from the Kit")
    return entry


@dataclass(frozen=True, slots=True)
class VerifiedDeveloperKit:
    archive_root: str
    kit_version: str
    code_commit: str
    release_fingerprint: str
    runtime_release_fingerprint: str
    payload_file_count: int
    files: Mapping[str, bytes]
    manifest: Mapping[str, object]
    compatibility: Mapping[str, object]
    lock: Mapping[str, object]


def require_compatible(
    matrix: Mapping[str, object],
    combination: Mapping[str, str],
) -> Mapping[str, object]:
    """Return the exact supported row or reject an unknown/mixed combination."""

    rows = matrix.get("supported_combinations")
    if not isinstance(rows, list):
        _reject("KIT_COMPATIBILITY_INVALID", "supported combination list is missing")
    version_fields = {
        "developer_kit",
        "runtime",
        "extension_sdk",
        "extension_tooling",
        "enterprise_template",
    }
    if set(combination) != version_fields or any(
        not isinstance(value, str) for value in combination.values()
    ):
        _reject("KIT_COMBINATION_INVALID", "combination fields are not exact")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and all(row.get(key) == combination[key] for key in version_fields)
    ]
    if len(matches) != 1 or matches[0].get("status") != "SUPPORTED_ENGINEERING":
        _reject("KIT_COMBINATION_UNSUPPORTED", "version combination is not supported")
    return cast(Mapping[str, object], matches[0])


def plan_upgrade(
    matrix: Mapping[str, object],
    current: Mapping[str, str],
    target: Mapping[str, str],
    *,
    explicit_opt_in: bool,
) -> JsonObject:
    """Plan a manual Kit transition; never mutate a project or infer latest."""

    require_compatible(matrix, target)
    if current == target:
        return {
            "action": "NO_CHANGE",
            "explicit_opt_in": explicit_opt_in,
            "project_mutated": False,
            "conformance_required": False,
        }
    if not explicit_opt_in:
        _reject("KIT_IMPLICIT_UPGRADE_FORBIDDEN", "Kit upgrade requires explicit opt in")
    rows = matrix.get("upgrade_from")
    if not isinstance(rows, list):
        _reject("KIT_COMPATIBILITY_INVALID", "upgrade predecessor list is missing")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("developer_kit") == current.get("developer_kit")
        and row.get("runtime") == current.get("runtime")
        and row.get("extension_sdk") == current.get("extension_sdk")
    ]
    if (
        len(matches) != 1
        or matches[0].get("explicit_opt_in_required") is not True
        or matches[0].get("status") != "SYNTHETIC_UNPUBLISHED_REPLAY_ONLY"
    ):
        _reject("KIT_UPGRADE_PATH_UNSUPPORTED", "upgrade predecessor is not approved")
    return {
        "action": "MANUAL_RELOCK_AND_REVALIDATE",
        "explicit_opt_in": True,
        "project_mutated": False,
        "conformance_required": True,
        "configuration_migration_required": False,
        "rollback": "RESTORE_RETAINED_PREDECESSOR_PROJECT_BYTES",
    }


def verify_kit_files(
    files: Mapping[str, bytes],
    *,
    archive_root: str = "directory",
    expected_kit_version: str | None = None,
    expected_code_commit: str | None = None,
    channel: str = "engineering",
) -> VerifiedDeveloperKit:
    """Verify checksums, locks, Runtime lineage, support, SBOM, and signing state."""

    required = {
        MANIFEST_PATH,
        COMPATIBILITY_PATH,
        LOCK_PATH,
        SUPPORT_PATH,
        SIGNING_PATH,
        LICENSE_PATH,
        SBOM_PATH,
        CORE_SOURCE_INVENTORY_PATH,
        CHECKSUM_PATH,
    }
    if required - set(files):
        _reject("KIT_INCOMPLETE", "required Developer Kit metadata is missing")
    if any(path.startswith("demo/") or "/demo/" in path for path in files):
        _reject("KIT_BOUNDARY_VIOLATION", "Demo content is forbidden in Developer Kit")

    manifest = strict_json_document(files[MANIFEST_PATH])
    expected_manifest_keys = {
        "manifest_version",
        "distribution_name",
        "kit_version",
        "code_commit",
        "source_date_epoch",
        "release_owner",
        "registry",
        "versions",
        "signing",
        "build",
        "payload_files",
        "release_fingerprint",
    }
    if set(manifest) != expected_manifest_keys:
        _reject("KIT_MANIFEST_INVALID", "release manifest fields are not exact")
    if manifest.get("manifest_version") != KIT_MANIFEST_VERSION:
        _reject("KIT_VERSION_MISMATCH", "release manifest version is unsupported")
    kit_version = manifest.get("kit_version")
    code_commit = manifest.get("code_commit")
    if not isinstance(kit_version, str) or _SEMVER.fullmatch(kit_version) is None:
        _reject("KIT_MANIFEST_INVALID", "Kit version is not stable SemVer")
    if not isinstance(code_commit, str) or _COMMIT.fullmatch(code_commit) is None:
        _reject("KIT_PROVENANCE_INVALID", "code commit is not immutable")
    if expected_kit_version is not None and kit_version != expected_kit_version:
        _reject("KIT_VERSION_MISMATCH", "Kit version differs from expectation")
    if expected_code_commit is not None and code_commit != expected_code_commit:
        _reject("KIT_VERSION_MISMATCH", "Kit code commit differs from expectation")
    fingerprint = manifest.get("release_fingerprint")
    basis = {key: value for key, value in manifest.items() if key != "release_fingerprint"}
    if (
        not isinstance(fingerprint, str)
        or _SHA256.fullmatch(fingerprint) is None
        or fingerprint != sha256_fingerprint(canonical_json_bytes(basis))
    ):
        _reject("KIT_FINGERPRINT_MISMATCH", "release manifest fingerprint differs")

    payload = manifest.get("payload_files")
    if not isinstance(payload, list) or not payload:
        _reject("KIT_MANIFEST_INVALID", "payload inventory is missing")
    expected_payload = set(files) - {MANIFEST_PATH, CHECKSUM_PATH}
    observed: set[str] = set()
    for raw_entry in payload:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {"path", "bytes", "sha256"}:
            _reject("KIT_MANIFEST_INVALID", "payload entry is malformed")
        entry = cast(JsonObject, raw_entry)
        path = entry.get("path")
        if not isinstance(path, str) or path not in files or path in observed:
            _reject("KIT_MANIFEST_INVALID", "payload path is invalid")
        if entry.get("bytes") != len(files[path]) or entry.get("sha256") != sha256_fingerprint(files[path]):
            _reject("KIT_CHECKSUM_MISMATCH", "payload identity differs")
        observed.add(path)
    if observed != expected_payload:
        _reject("KIT_INCOMPLETE", "payload inventory is not exact")
    checksums = _checksums(files[CHECKSUM_PATH])
    if set(checksums) != set(files) - {CHECKSUM_PATH}:
        _reject("KIT_INCOMPLETE", "checksum inventory is not exact")
    for path, digest in checksums.items():
        if digest != sha256(files[path]).hexdigest():
            _reject("KIT_CHECKSUM_MISMATCH", "Kit file checksum differs")

    compatibility = strict_json_document(files[COMPATIBILITY_PATH])
    lock = strict_json_document(files[LOCK_PATH])
    support = strict_json_document(files[SUPPORT_PATH])
    signing_request = strict_json_document(files[SIGNING_PATH])
    license_report = strict_json_document(files[LICENSE_PATH])
    sbom = strict_json_document(files[SBOM_PATH])
    core_inventory = strict_json_document(files[CORE_SOURCE_INVENTORY_PATH])
    versions = _object(manifest, "versions")
    if (
        compatibility.get("matrix_version") != COMPATIBILITY_MATRIX_VERSION
        or compatibility.get("kit_version") != kit_version
        or compatibility.get("automatic_upgrade") is not False
        or compatibility.get("versions") != versions
    ):
        _reject("KIT_COMPATIBILITY_INVALID", "compatibility matrix disagrees with manifest")
    combination = {
        key: cast(str, versions[key])
        for key in (
            "developer_kit",
            "runtime",
            "extension_sdk",
            "extension_tooling",
            "enterprise_template",
        )
    }
    require_compatible(compatibility, combination)
    if lock.get("lock_version") != KIT_LOCK_VERSION or lock.get("versions") != versions:
        _reject("KIT_LOCK_INVALID", "Kit lock disagrees with manifest")
    if (
        support.get("support_policy_version") != SUPPORT_POLICY_VERSION
        or support.get("current_supported_kit") != kit_version
        or support.get("automatic_upgrade") is not False
    ):
        _reject("KIT_SUPPORT_POLICY_INVALID", "support policy is invalid")
    signing = _object(manifest, "signing")
    if (
        signing_request.get("request_version") != SIGNING_REQUEST_VERSION
        or signing_request.get("kit_version") != kit_version
        or signing_request.get("code_commit") != code_commit
        or signing_request.get("subject")
        != {
            "manifest_path": MANIFEST_PATH,
            "sidecar": "EXTERNAL_ARCHIVE_SHA256_SIDECAR",
            "binding": "VERIFY_MANIFEST_FINGERPRINT_AT_SIGNING_TIME",
        }
        or signing_request.get("state") != "UNSIGNED_ENGINEERING_CANDIDATE"
        or signing_request.get("signature_present") is not False
        or signing
        != {
            "state": "UNSIGNED_ENGINEERING_CANDIDATE",
            "signature_present": False,
            "approved_external_key": False,
            "public_promotion_allowed": False,
            "production_promotion_allowed": False,
        }
    ):
        _reject("KIT_SIGNATURE_INVALID", "engineering signing declaration is invalid")
    if channel != "engineering":
        _reject("KIT_SIGNATURE_REQUIRED", "public or Production promotion requires external signature")
    if (
        license_report.get("report_version") != LICENSE_REPORT_VERSION
        or license_report.get("status") != "PASS"
        or license_report.get("unknown_license_count") != 0
    ):
        _reject("KIT_LICENSE_POLICY_FAILED", "license report is missing or failed")
    if (
        sbom.get("bomFormat") != "CycloneDX"
        or sbom.get("specVersion") != SBOM_SPEC_VERSION
        or not isinstance(sbom.get("components"), list)
    ):
        _reject("KIT_SBOM_INVALID", "CycloneDX SBOM is missing or invalid")
    if (
        core_inventory.get("inventory_version") != CORE_SOURCE_INVENTORY_VERSION
        or not isinstance(core_inventory.get("entries"), list)
        or not core_inventory["entries"]
    ):
        _reject("KIT_CORE_INVENTORY_INVALID", "Core source inventory is invalid")

    runtime_entry = _artifact(lock, "runtime", files)
    for key in ("sdk", "tooling", "template", "alpha_extension", "beta_extension"):
        _artifact(lock, key, files)
    runtime_path = cast(str, runtime_entry["path"])
    with TemporaryDirectory(prefix="aps-kit-runtime-verify-") as temporary:
        path = Path(temporary) / "runtime.tar.gz"
        path.write_bytes(files[runtime_path])
        verified_runtime = verify_release_archive(
            path,
            expected_runtime_version=cast(str, versions["runtime"]),
            expected_code_commit=code_commit,
        )
    runtime_identity = _object(lock, "runtime_identity")
    if (
        runtime_identity.get("release_fingerprint")
        != verified_runtime.release_fingerprint
        or runtime_identity.get("archive_sha256") != runtime_entry["sha256"]
        or runtime_identity.get("code_commit") != code_commit
    ):
        _reject("KIT_RUNTIME_IDENTITY_MISMATCH", "Runtime lineage differs from Kit lock")
    return VerifiedDeveloperKit(
        archive_root=archive_root,
        kit_version=kit_version,
        code_commit=code_commit,
        release_fingerprint=fingerprint,
        runtime_release_fingerprint=verified_runtime.release_fingerprint,
        payload_file_count=len(payload),
        files=dict(files),
        manifest=manifest,
        compatibility=compatibility,
        lock=lock,
    )


def verify_kit_archive(
    path: Path,
    *,
    expected_kit_version: str | None = None,
    expected_code_commit: str | None = None,
    channel: str = "engineering",
) -> VerifiedDeveloperKit:
    root, files = read_kit_archive(path)
    return verify_kit_files(
        files,
        archive_root=root,
        expected_kit_version=expected_kit_version,
        expected_code_commit=expected_code_commit,
        channel=channel,
    )


__all__ = [
    "CHECKSUM_PATH",
    "COMPATIBILITY_MATRIX_VERSION",
    "COMPATIBILITY_PATH",
    "CORE_SOURCE_INVENTORY_PATH",
    "DeveloperKitContractError",
    "KIT_LOCK_VERSION",
    "KIT_MANIFEST_VERSION",
    "LOCK_PATH",
    "MANIFEST_PATH",
    "SIGNING_PATH",
    "SUPPORT_PATH",
    "VerifiedDeveloperKit",
    "canonical_json_bytes",
    "plan_upgrade",
    "read_kit_archive",
    "require_compatible",
    "sha256_fingerprint",
    "strict_json_document",
    "verify_kit_archive",
    "verify_kit_files",
]
