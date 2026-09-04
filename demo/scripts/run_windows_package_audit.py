"""Verify the sealed Windows standalone Demo ZIP without executing it."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
from typing import Any, cast
from zipfile import BadZipFile, ZipFile


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(DEMO_ROOT / "backend"))
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from plantnexus_demo.standalone_settings import (  # noqa: E402
    DEFAULT_SETTINGS_DOCUMENT,
    StandaloneSettings,
)
from plantnexus_demo.windows_launcher import WINDOWS_PACKAGE_VERSION  # noqa: E402


AUDIT_VERSION = "cnc-demo-windows-package-audit.v1"
MANIFEST_VERSION = "cnc-demo-windows-package-manifest.v1"
PACKAGE_NAME = f"PlantNexus-CNC-Demo-Windows-x64-{WINDOWS_PACKAGE_VERSION}"
DEFAULT_ZIP = DEMO_ROOT / "dist" / f"{PACKAGE_NAME}.zip"
DEFAULT_REPORT = DEMO_ROOT / "build" / "validation" / "windows-package-audit-demo-11.json"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PackageAuditError(RuntimeError):
    pass


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_fingerprint(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _json_object(payload: bytes, *, field: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PackageAuditError(f"invalid JSON: {field}") from error
    if not isinstance(value, dict):
        raise PackageAuditError(f"JSON object required: {field}")
    return cast(dict[str, Any], value)


def _verify_pe_x64(payload: bytes) -> None:
    if len(payload) < 256 or payload[:2] != b"MZ":
        raise PackageAuditError("entrypoint is not a PE executable")
    pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
    if pe_offset + 6 > len(payload) or payload[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise PackageAuditError("entrypoint PE header is invalid")
    machine = struct.unpack_from("<H", payload, pe_offset + 4)[0]
    if machine != 0x8664:
        raise PackageAuditError("entrypoint is not Windows x64")


def audit(zip_path: Path) -> dict[str, Any]:
    resolved_zip = zip_path.resolve()
    digest_path = resolved_zip.with_suffix(".zip.sha256")
    if not resolved_zip.is_file() or not digest_path.is_file():
        raise PackageAuditError("package ZIP or SHA-256 sidecar is missing")
    zip_digest = _file_sha256(resolved_zip)
    sidecar_parts = digest_path.read_text(encoding="ascii").strip().split()
    if (
        len(sidecar_parts) != 2
        or sidecar_parts[0] != zip_digest
        or sidecar_parts[1] != resolved_zip.name
    ):
        raise PackageAuditError("package SHA-256 sidecar does not match")

    with ZipFile(resolved_zip) as archive:
        if archive.testzip() is not None:
            raise PackageAuditError("package ZIP CRC validation failed")
        file_infos = [info for info in archive.infolist() if not info.is_dir()]
        names = [info.filename for info in file_infos]
        if len(names) != len(set(names)) or len({name.casefold() for name in names}) != len(names):
            raise PackageAuditError("package contains duplicate Windows paths")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != PACKAGE_NAME:
                raise PackageAuditError("package contains an unsafe path")

        prefix = f"{PACKAGE_NAME}/"
        manifest_path = prefix + "package-manifest.json"
        if manifest_path not in names:
            raise PackageAuditError("package manifest is missing")
        manifest = _json_object(archive.read(manifest_path), field="package-manifest")
        fingerprint = manifest.pop("manifest_fingerprint", None)
        if fingerprint != _canonical_fingerprint(manifest):
            raise PackageAuditError("package manifest fingerprint differs")
        manifest["manifest_fingerprint"] = fingerprint
        if (
            manifest.get("manifest_version") != MANIFEST_VERSION
            or manifest.get("package_name") != PACKAGE_NAME
            or manifest.get("package_version") != WINDOWS_PACKAGE_VERSION
            or manifest.get("platform") != "Windows-x64"
            or manifest.get("simulation_only") is not True
            or manifest.get("synthetic_only") is not True
            or manifest.get("frontend_api_topology") != "SAME_ORIGIN_SINGLE_PORT"
            or manifest.get("default_access") != "LOOPBACK_ONLY"
            or manifest.get("lan_access") != "EXPLICIT_PRIVATE_CIDR_ALLOWLIST"
        ):
            raise PackageAuditError("package manifest boundary is invalid")
        runtime_dependencies = manifest.get("runtime_dependencies")
        if not isinstance(runtime_dependencies, dict) or any(
            runtime_dependencies.get(name) is not False
            for name in (
                "python_required",
                "node_required",
                "npm_required",
                "uv_required",
                "network_required",
            )
        ):
            raise PackageAuditError("runtime dependency boundary is invalid")

        inventory = manifest.get("files")
        if not isinstance(inventory, list):
            raise PackageAuditError("package inventory is invalid")
        declared: dict[str, dict[str, Any]] = {}
        for item in inventory:
            if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
                raise PackageAuditError("package inventory entry is invalid")
            relative = item.get("path")
            size = item.get("bytes")
            digest = item.get("sha256")
            if (
                not isinstance(relative, str)
                or not relative
                or relative in declared
                or isinstance(size, bool)
                or not isinstance(size, int)
                or size < 0
                or not isinstance(digest, str)
                or _SHA256_PATTERN.fullmatch(digest) is None
            ):
                raise PackageAuditError("package inventory value is invalid")
            declared[relative] = item
        actual_relative = {
            name.removeprefix(prefix)
            for name in names
            if name != manifest_path
        }
        if set(declared) != actual_relative:
            raise PackageAuditError("package inventory paths differ from ZIP")
        for relative, item in declared.items():
            payload = archive.read(prefix + relative)
            if len(payload) != item["bytes"] or sha256(payload).hexdigest() != item["sha256"]:
                raise PackageAuditError(f"package payload digest differs: {relative}")
            lowered = relative.casefold()
            if (
                lowered.startswith("runtime/")
                or "/node_modules/" in f"/{lowered}/"
                or lowered.endswith(".map")
                or lowered.endswith("session.token")
                or lowered.endswith((".db", ".sqlite", ".sqlite3"))
            ):
                raise PackageAuditError(f"forbidden runtime/development file: {relative}")

        required = {
            "PlantNexusCncDemo.exe",
            "启动演示.cmd",
            "停止演示.cmd",
            "查看状态.cmd",
            "配置演示.ps1",
            "README-启动说明.txt",
            "config/demo-settings.json",
        }
        if not required.issubset(declared):
            raise PackageAuditError("required package entry is missing")
        _verify_pe_x64(archive.read(prefix + "PlantNexusCncDemo.exe"))
        settings_document = _json_object(
            archive.read(prefix + "config/demo-settings.json"), field="settings"
        )
        settings = StandaloneSettings.from_document(settings_document)
        if settings.to_document() != DEFAULT_SETTINGS_DOCUMENT:
            raise PackageAuditError("sealed package must default to loopback-only settings")
        if (
            manifest.get("file_count") != len(declared)
            or manifest.get("payload_bytes")
            != sum(cast(int, item["bytes"]) for item in declared.values())
        ):
            raise PackageAuditError("package inventory totals differ")

    checks = {
        "zip_sha256": True,
        "zip_crc": True,
        "safe_windows_paths": True,
        "manifest_fingerprint": True,
        "manifest_boundaries": True,
        "runtime_dependency_independence": True,
        "inventory_exact": True,
        "payload_sha256": True,
        "forbidden_files_absent": True,
        "required_launchers_present": True,
        "windows_x64_pe": True,
        "default_loopback_settings": True,
    }
    return {
        "audit_version": AUDIT_VERSION,
        "status": "PASS",
        "package_name": PACKAGE_NAME,
        "package_version": WINDOWS_PACKAGE_VERSION,
        "zip_path": str(resolved_zip.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        "zip_bytes": resolved_zip.stat().st_size,
        "zip_sha256": zip_digest,
        "manifest_fingerprint": fingerprint,
        "file_count": len(declared),
        "payload_bytes": manifest["payload_bytes"],
        "checks": checks,
        "passed_checks": sum(checks.values()),
        "total_checks": len(checks),
        "simulation_only": True,
        "production_ready": False,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    payload = dict(report)
    payload["report_fingerprint"] = _canonical_fingerprint(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()
    try:
        report = audit(arguments.zip)
    except (OSError, BadZipFile, PackageAuditError, ValueError) as error:
        report = {
            "audit_version": AUDIT_VERSION,
            "status": "FAIL",
            "code": type(error).__name__,
            "message": str(error),
            "simulation_only": True,
            "production_ready": False,
        }
        _write_report(arguments.report, report)
        print(json.dumps(report, ensure_ascii=False))
        return 2
    _write_report(arguments.report, report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
