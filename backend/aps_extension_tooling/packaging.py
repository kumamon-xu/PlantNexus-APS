"""Deterministic pure-Python wheels and source archives for conformance."""

from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from aps_extension_sdk import SDK_API_VERSION

from aps_extension_tooling.project import EnterpriseExtensionProject


_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_ARCHIVE_EXCLUDES = {
    ".git",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
    "vendor",
}


def digest_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _record_digest(value: bytes) -> str:
    encoded = urlsafe_b64encode(sha256(value).digest()).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


def deterministic_zip(files: dict[str, bytes]) -> bytes:
    target = BytesIO()
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, value in sorted(files.items()):
            if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                raise ValueError("archive member is not a safe relative POSIX path")
            info = ZipInfo(name, date_time=_ZIP_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, value)
    return target.getvalue()


def _wheel(
    *,
    distribution_name: str,
    version: str,
    files: dict[str, bytes],
    metadata: str,
    generator: str = "plantnexus-aps-extension-tooling-p8-14",
) -> tuple[str, bytes]:
    normalized = re.sub(r"[-_.]+", "_", distribution_name)
    dist_info = f"{normalized}-{version}.dist-info"
    wheel_files = dict(files)
    wheel_files[f"{dist_info}/METADATA"] = metadata.encode("utf-8")
    wheel_files[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        f"Generator: {generator}\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")
    record_name = f"{dist_info}/RECORD"
    record_lines = [
        f"{name},{_record_digest(value)},{len(value)}"
        for name, value in sorted(wheel_files.items())
    ]
    record_lines.append(f"{record_name},,")
    wheel_files[record_name] = ("\n".join(record_lines) + "\n").encode("utf-8")
    filename = f"{normalized}-{version}-py3-none-any.whl"
    return filename, deterministic_zip(wheel_files)


def sdk_wheel(repository_root: Path) -> tuple[str, bytes]:
    package_root = repository_root / "backend/aps_extension_sdk"
    files: dict[str, bytes] = {}
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".json"}:
            continue
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(package_root.parent).as_posix()
        files[relative] = path.read_bytes().replace(b"\r\n", b"\n")
    metadata = (
        "Metadata-Version: 2.3\n"
        "Name: aps-extension-sdk\n"
        f"Version: {SDK_API_VERSION}\n"
        "Summary: Stable PlantNexus APS Enterprise Extension contracts\n"
        "Requires-Python: >=3.12,<3.13\n"
    )
    return _wheel(
        distribution_name="aps-extension-sdk",
        version=SDK_API_VERSION,
        files=files,
        metadata=metadata,
    )


def extension_wheel(project: EnterpriseExtensionProject) -> tuple[str, bytes]:
    return extension_wheel_for_source(
        distribution_name=project.distribution_name,
        package_name=project.package_name,
        owner=project.owner,
        repository_url=project.repository_url,
        license_expression=project.license_expression,
        source_root=project.source_root,
    )


def extension_wheel_for_source(
    *,
    distribution_name: str,
    package_name: str,
    owner: str,
    repository_url: str,
    license_expression: str,
    source_root: Path,
) -> tuple[str, bytes]:
    package_root = source_root / package_name
    source_files = tuple(sorted(package_root.rglob("*.py")))
    files = {
        path.relative_to(source_root).as_posix(): path.read_bytes().replace(
            b"\r\n", b"\n"
        )
        for path in source_files
    }
    metadata = (
        "Metadata-Version: 2.3\n"
        f"Name: {distribution_name}\n"
        "Version: 1.0.0\n"
        f"Author: {owner}\n"
        f"License: {license_expression}\n"
        f"Project-URL: Repository, {repository_url}\n"
        "Requires-Python: >=3.12,<3.13\n"
        f"Requires-Dist: aps-extension-sdk (=={SDK_API_VERSION})\n"
    )
    return _wheel(
        distribution_name=distribution_name,
        version="1.0.0",
        files=files,
        metadata=metadata,
    )


def tooling_wheel(
    repository_root: Path,
    *,
    developer_kit_version: str,
) -> tuple[str, bytes]:
    """Build the exact standalone conformance-tooling wheel for one Kit."""

    package_root = repository_root / "backend/aps_extension_tooling"
    files = {
        path.relative_to(package_root.parent).as_posix(): path.read_bytes().replace(
            b"\r\n", b"\n"
        )
        for path in sorted(package_root.rglob("*.py"))
        if path.is_file() and "__pycache__" not in path.parts
    }
    metadata = (
        "Metadata-Version: 2.3\n"
        "Name: aps-developer-kit-tools\n"
        f"Version: {developer_kit_version}\n"
        "Summary: Locked PlantNexus APS Enterprise Extension conformance tools\n"
        "Requires-Python: >=3.12,<3.13\n"
        f"Requires-Dist: aps-extension-sdk (=={SDK_API_VERSION})\n"
        "Requires-Dist: plantnexus-aps (==0.0.0)\n"
        "Requires-Dist: jsonschema (==4.25.1)\n"
    )
    return _wheel(
        distribution_name="aps-developer-kit-tools",
        version=developer_kit_version,
        files=files,
        metadata=metadata,
        generator="plantnexus-aps-developer-kit-builder-p8-15",
    )


def project_archive(root: Path) -> bytes:
    files: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in _ARCHIVE_EXCLUDES for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        files[relative] = path.read_bytes().replace(b"\r\n", b"\n")
    return deterministic_zip(files)


def write_artifact(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


__all__ = [
    "deterministic_zip",
    "digest_bytes",
    "extension_wheel",
    "extension_wheel_for_source",
    "project_archive",
    "sdk_wheel",
    "tooling_wheel",
    "write_artifact",
]
