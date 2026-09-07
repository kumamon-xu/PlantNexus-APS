"""Strict contracts for immutable APS Runtime release distributions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from typing import Any, NoReturn, cast


type JsonObject = dict[str, Any]

RELEASE_MANIFEST_VERSION = "aps-runtime-release-manifest.v1"
COMPATIBILITY_MANIFEST_VERSION = "aps-runtime-compatibility-manifest.v1"
MIGRATION_MANIFEST_VERSION = "aps-runtime-migration-manifest.v1"
LICENSE_REPORT_VERSION = "aps-runtime-license-report.v1"
SBOM_SPEC_VERSION = "1.5"
CHECKSUM_PATH = "metadata/checksums.sha256"
MANIFEST_PATH = "metadata/release-manifest.json"
COMPATIBILITY_PATH = "metadata/compatibility-manifest.json"
MIGRATION_PATH = "metadata/migration-manifest.json"
LICENSE_PATH = "metadata/license-report.json"
SBOM_PATH = "metadata/sbom.cdx.json"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_MAX_MEMBER_COUNT = 16_384
_MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


class ReleaseContractError(ValueError):
    """Sanitized release validation error with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _reject_constant(value: str) -> NoReturn:
    raise ReleaseContractError("INVALID_JSON", f"unsupported JSON constant: {value}")


def _strict_pairs(pairs: Sequence[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseContractError("INVALID_JSON", "duplicate JSON object key")
        result[key] = value
    return result


def strict_json_document(raw: bytes) -> JsonObject:
    """Parse one strict object without duplicate keys or non-finite numbers."""

    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_constant,
        )
    except ReleaseContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseContractError("INVALID_JSON", "document is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ReleaseContractError("INVALID_JSON", "top-level JSON value must be an object")
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
        raise ReleaseContractError("INVALID_JSON", "document is not canonicalizable") from error


def sha256_hex(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def sha256_fingerprint(raw: bytes) -> str:
    return f"sha256:{sha256_hex(raw)}"


def _member_path(raw: str) -> PurePosixPath:
    if "\\" in raw or raw.startswith("/") or "\x00" in raw:
        raise ReleaseContractError("UNSAFE_ARCHIVE", "archive member path is unsafe")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseContractError("UNSAFE_ARCHIVE", "archive member path is unsafe")
    return path


def read_release_archive(path: Path) -> tuple[str, dict[str, bytes]]:
    """Read regular files from a bounded, single-root tar+gzip archive."""

    try:
        archive_size = path.stat().st_size
    except OSError as error:
        raise ReleaseContractError("ARCHIVE_UNAVAILABLE", "release archive is unavailable") from error
    if archive_size <= 0 or archive_size > _MAX_ARCHIVE_BYTES:
        raise ReleaseContractError("ARCHIVE_SIZE_INVALID", "release archive size is outside policy")

    result: dict[str, bytes] = {}
    roots: set[str] = set()
    total = 0
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > _MAX_MEMBER_COUNT:
                raise ReleaseContractError("ARCHIVE_SIZE_INVALID", "archive member count exceeds policy")
            for member in members:
                member_path = _member_path(member.name)
                roots.add(member_path.parts[0])
                if member.isdir():
                    continue
                if not member.isfile() or member.issym() or member.islnk():
                    raise ReleaseContractError("UNSAFE_ARCHIVE", "archive contains a non-regular member")
                if len(member_path.parts) < 2:
                    raise ReleaseContractError("UNSAFE_ARCHIVE", "archive file is outside its release root")
                relative = PurePosixPath(*member_path.parts[1:]).as_posix()
                if relative in result:
                    raise ReleaseContractError("UNSAFE_ARCHIVE", "archive contains duplicate members")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ReleaseContractError("ARCHIVE_INVALID", "archive member cannot be read")
                raw = extracted.read(_MAX_ARCHIVE_BYTES + 1)
                total += len(raw)
                if total > _MAX_ARCHIVE_BYTES:
                    raise ReleaseContractError("ARCHIVE_SIZE_INVALID", "expanded archive exceeds policy")
                result[relative] = raw
    except ReleaseContractError:
        raise
    except (OSError, tarfile.TarError) as error:
        raise ReleaseContractError("ARCHIVE_INVALID", "release archive cannot be decoded") from error
    if len(roots) != 1 or not result:
        raise ReleaseContractError("ARCHIVE_INVALID", "release archive must have one non-empty root")
    return next(iter(roots)), result


def read_release_directory(path: Path) -> dict[str, bytes]:
    """Read a release directory without following symlinks."""

    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ReleaseContractError("ARCHIVE_UNAVAILABLE", "release directory is unavailable") from error
    if not resolved.is_dir() or resolved.is_symlink():
        raise ReleaseContractError("UNSAFE_ARCHIVE", "release directory is not a regular directory")
    result: dict[str, bytes] = {}
    total = 0
    for candidate in sorted(resolved.rglob("*")):
        if candidate.is_symlink():
            raise ReleaseContractError("UNSAFE_ARCHIVE", "release directory contains a symlink")
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(resolved).as_posix()
        _member_path(relative)
        raw = candidate.read_bytes()
        total += len(raw)
        if len(result) >= _MAX_MEMBER_COUNT or total > _MAX_ARCHIVE_BYTES:
            raise ReleaseContractError("ARCHIVE_SIZE_INVALID", "release directory exceeds policy")
        result[relative] = raw
    return result


def _required_object(document: Mapping[str, object], key: str) -> JsonObject:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ReleaseContractError("MANIFEST_INVALID", f"{key} must be an object")
    return cast(JsonObject, value)


def _parse_checksums(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ReleaseContractError("CHECKSUM_INVALID", "checksum file is not UTF-8") from error
    if not lines:
        raise ReleaseContractError("CHECKSUM_INVALID", "checksum file is empty")
    result: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        if match is None:
            raise ReleaseContractError("CHECKSUM_INVALID", "checksum line is malformed")
        digest, raw_path = match.groups()
        normalized = _member_path(raw_path).as_posix()
        if normalized in result or normalized == CHECKSUM_PATH:
            raise ReleaseContractError("CHECKSUM_INVALID", "checksum path is duplicated or recursive")
        result[normalized] = digest
    return result


@dataclass(frozen=True, slots=True)
class VerifiedRelease:
    release_root: str
    release_fingerprint: str
    code_commit: str
    runtime_version: str
    payload_file_count: int
    files: Mapping[str, bytes]
    manifest: Mapping[str, object]


def verify_release_files(
    files: Mapping[str, bytes],
    *,
    release_root: str = "directory",
    expected_runtime_version: str | None = None,
    expected_code_commit: str | None = None,
) -> VerifiedRelease:
    """Verify checksums, manifest fingerprint, versions, and embedded reports."""

    required = {
        MANIFEST_PATH,
        CHECKSUM_PATH,
        COMPATIBILITY_PATH,
        MIGRATION_PATH,
        LICENSE_PATH,
        SBOM_PATH,
    }
    missing = sorted(required - set(files))
    if missing:
        raise ReleaseContractError("RELEASE_INCOMPLETE", "required release metadata is missing")

    manifest = strict_json_document(files[MANIFEST_PATH])
    expected_manifest_keys = {
        "manifest_version",
        "distribution_name",
        "code_commit",
        "source_date_epoch",
        "target",
        "versions",
        "extension_boundary",
        "support_window",
        "signing",
        "build",
        "payload_files",
        "release_fingerprint",
    }
    if set(manifest) != expected_manifest_keys:
        raise ReleaseContractError("MANIFEST_INVALID", "release manifest fields are not exact")
    if manifest["manifest_version"] != RELEASE_MANIFEST_VERSION:
        raise ReleaseContractError("VERSION_MISMATCH", "release manifest version is unsupported")
    fingerprint = manifest.get("release_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:"):
        raise ReleaseContractError("MANIFEST_INVALID", "release fingerprint is malformed")
    fingerprint_basis = {key: value for key, value in manifest.items() if key != "release_fingerprint"}
    if fingerprint != sha256_fingerprint(canonical_json_bytes(fingerprint_basis)):
        raise ReleaseContractError("FINGERPRINT_MISMATCH", "release manifest fingerprint does not match")

    code_commit = manifest.get("code_commit")
    if not isinstance(code_commit, str) or _COMMIT.fullmatch(code_commit) is None:
        raise ReleaseContractError("MANIFEST_INVALID", "code commit is not immutable")
    versions = _required_object(manifest, "versions")
    runtime_version = versions.get("runtime")
    if not isinstance(runtime_version, str):
        raise ReleaseContractError("MANIFEST_INVALID", "runtime version is missing")
    if expected_runtime_version is not None and runtime_version != expected_runtime_version:
        raise ReleaseContractError("VERSION_MISMATCH", "runtime version does not match expectation")
    if expected_code_commit is not None and code_commit != expected_code_commit:
        raise ReleaseContractError("VERSION_MISMATCH", "code commit does not match expectation")

    payload = manifest.get("payload_files")
    if not isinstance(payload, list) or not payload:
        raise ReleaseContractError("MANIFEST_INVALID", "payload inventory is missing")
    expected_payload_paths = set(files) - {MANIFEST_PATH, CHECKSUM_PATH}
    observed_payload_paths: set[str] = set()
    for entry in payload:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise ReleaseContractError("MANIFEST_INVALID", "payload entry is malformed")
        path = entry.get("path")
        size = entry.get("bytes")
        digest = entry.get("sha256")
        if not isinstance(path, str) or path not in files or path in observed_payload_paths:
            raise ReleaseContractError("MANIFEST_INVALID", "payload path is invalid")
        if not isinstance(size, int) or isinstance(size, bool) or size != len(files[path]):
            raise ReleaseContractError("CHECKSUM_MISMATCH", "payload size does not match")
        if not isinstance(digest, str) or digest != sha256_fingerprint(files[path]):
            raise ReleaseContractError("CHECKSUM_MISMATCH", "payload digest does not match")
        observed_payload_paths.add(path)
    if observed_payload_paths != expected_payload_paths:
        raise ReleaseContractError("RELEASE_INCOMPLETE", "payload inventory is not exact")

    checksums = _parse_checksums(files[CHECKSUM_PATH])
    expected_checksum_paths = set(files) - {CHECKSUM_PATH}
    if set(checksums) != expected_checksum_paths:
        raise ReleaseContractError("RELEASE_INCOMPLETE", "checksum inventory is not exact")
    for path, digest in checksums.items():
        if digest != sha256_hex(files[path]):
            raise ReleaseContractError("CHECKSUM_MISMATCH", "release file checksum does not match")

    compatibility = strict_json_document(files[COMPATIBILITY_PATH])
    migration = strict_json_document(files[MIGRATION_PATH])
    license_report = strict_json_document(files[LICENSE_PATH])
    sbom = strict_json_document(files[SBOM_PATH])
    if compatibility.get("manifest_version") != COMPATIBILITY_MANIFEST_VERSION:
        raise ReleaseContractError("VERSION_MISMATCH", "compatibility manifest version is unsupported")
    if migration.get("manifest_version") != MIGRATION_MANIFEST_VERSION:
        raise ReleaseContractError("VERSION_MISMATCH", "migration manifest version is unsupported")
    if license_report.get("report_version") != LICENSE_REPORT_VERSION or license_report.get("status") != "PASS":
        raise ReleaseContractError("LICENSE_POLICY_FAILED", "license report is missing or failed")
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != SBOM_SPEC_VERSION:
        raise ReleaseContractError("SBOM_INVALID", "CycloneDX SBOM is missing or unsupported")
    if compatibility.get("versions") != versions or migration.get("database_head") != versions.get("database"):
        raise ReleaseContractError("VERSION_MISMATCH", "embedded compatibility metadata disagrees")

    signing = _required_object(manifest, "signing")
    if signing.get("state") != "UNSIGNED_ENGINEERING_CANDIDATE" or signing.get("signature_present") is not False:
        raise ReleaseContractError("SIGNATURE_INVALID", "engineering candidate signing state is invalid")

    return VerifiedRelease(
        release_root=release_root,
        release_fingerprint=fingerprint,
        code_commit=code_commit,
        runtime_version=runtime_version,
        payload_file_count=len(payload),
        files=dict(files),
        manifest=manifest,
    )


def verify_release_archive(
    path: Path,
    *,
    expected_runtime_version: str | None = None,
    expected_code_commit: str | None = None,
) -> VerifiedRelease:
    release_root, files = read_release_archive(path)
    return verify_release_files(
        files,
        release_root=release_root,
        expected_runtime_version=expected_runtime_version,
        expected_code_commit=expected_code_commit,
    )


__all__ = [
    "CHECKSUM_PATH",
    "COMPATIBILITY_MANIFEST_VERSION",
    "COMPATIBILITY_PATH",
    "LICENSE_PATH",
    "LICENSE_REPORT_VERSION",
    "MANIFEST_PATH",
    "MIGRATION_MANIFEST_VERSION",
    "MIGRATION_PATH",
    "RELEASE_MANIFEST_VERSION",
    "ReleaseContractError",
    "SBOM_PATH",
    "VerifiedRelease",
    "canonical_json_bytes",
    "read_release_archive",
    "read_release_directory",
    "sha256_fingerprint",
    "sha256_hex",
    "strict_json_document",
    "verify_release_archive",
    "verify_release_files",
]
