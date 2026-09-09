"""Strict standalone-project metadata and source-boundary validation."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import Any, NoReturn
from urllib.parse import urlsplit

from aps_extension_sdk import (
    SDK_API_VERSION,
    ExtensionManifest,
    SemanticVersion,
    parse_extension_manifest,
)


PROJECT_CONTRACT_VERSION = "enterprise-extension-project.v1"
LOCK_CONTRACT_VERSION = "aps-extension-lock.v1"
RUNTIME_VERSION = "0.1.0"
DEVELOPER_KIT_VERSION = "0.0.0-not-published"
MAX_PROJECT_DOCUMENT_BYTES = 256 * 1024
MAX_SOURCE_FILE_BYTES = 256 * 1024
MAX_SOURCE_FILES = 128
MAX_PROJECT_FILES = 512
MAX_PROJECT_FILE_BYTES = 4 * 1024 * 1024

_PROJECT_KEYS = {
    "project_contract_version",
    "project_id",
    "distribution_name",
    "package_name",
    "owner",
    "repository_url",
    "license_expression",
    "source_commit",
    "sdk_api_version",
    "runtime_version",
    "developer_kit_version",
    "manifest_path",
    "configuration_path",
    "configuration_schema_path",
    "dependency_lock_path",
    "conformance_fixture_path",
    "source_root",
    "tests_root",
}
_DISTRIBUTION_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
_PACKAGE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_LICENSE_RE = re.compile(
    r"^(?:LicenseRef-[A-Za-z0-9.-]+|[A-Za-z0-9.-]+(?:\s+(?:AND|OR|WITH)\s+[A-Za-z0-9.-]+)*)$"
)
_LOCK_LINE_RE = re.compile(r"^aps-extension-sdk==1\.0\.0 --hash=sha256:([0-9a-f]{64})$")
_FORBIDDEN_IMPORTS = {
    "app",
    "backend",
    "aps_core",
    "ortools",
    "sqlalchemy",
    "celery",
    "fastapi",
    "pydantic",
    "requests",
    "aiohttp",
}
_NONDETERMINISTIC_OR_IO_IMPORTS = {
    "asyncio",
    "datetime",
    "http",
    "multiprocessing",
    "os",
    "pathlib",
    "random",
    "secrets",
    "socket",
    "subprocess",
    "tempfile",
    "threading",
    "time",
    "urllib",
    "uuid",
}
_FORBIDDEN_CALL_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "input",
    "open",
}
_FORBIDDEN_ATTRIBUTE_CALLS = {
    "__import__",
    "compile",
    "connect",
    "eval",
    "exec",
    "getenv",
    "import_module",
    "now",
    "open",
    "popen",
    "randint",
    "random",
    "read_bytes",
    "read_text",
    "run",
    "sleep",
    "system",
    "time",
    "today",
    "urlopen",
    "urandom",
    "utcnow",
    "uuid4",
    "write_bytes",
    "write_text",
}
_PROJECT_SCAN_EXCLUDES = {
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
}


class ExtensionToolingErrorCode(StrEnum):
    PROJECT_INVALID = "EXT_PROJECT_INVALID"
    VERSION_INCOMPATIBLE = "EXT_VERSION_INCOMPATIBLE"
    OWNER_UNDECLARED = "EXT_OWNER_UNDECLARED"
    LICENSE_UNDECLARED = "EXT_LICENSE_UNDECLARED"
    DEPENDENCY_LOCK_INVALID = "EXT_DEPENDENCY_LOCK_INVALID"
    SOURCE_INVALID = "EXT_SOURCE_INVALID"
    SOURCE_IMPORT_FORBIDDEN = "EXT_SOURCE_IMPORT_FORBIDDEN"
    SOURCE_NONDETERMINISTIC = "EXT_SOURCE_NONDETERMINISTIC"
    CORE_COPY_DETECTED = "EXT_CORE_COPY_DETECTED"
    MANIFEST_INVALID = "EXT_MANIFEST_INVALID"
    ENTRYPOINT_INVALID = "EXT_ENTRYPOINT_INVALID"
    BUILD_NONDETERMINISTIC = "EXT_BUILD_NONDETERMINISTIC"
    CLEAN_INSTALL_FAILED = "EXT_CLEAN_INSTALL_FAILED"
    PROJECT_TEST_FAILED = "EXT_PROJECT_TEST_FAILED"
    RUNTIME_LOAD_FAILED = "EXT_RUNTIME_LOAD_FAILED"
    VALIDATION_REJECTED = "EXT_VALIDATION_REJECTED"
    SET_CONFLICT = "EXT_SET_CONFLICT"
    SCA_POLICY_FAILED = "EXT_SCA_POLICY_FAILED"


class ConformanceError(RuntimeError):
    """Stable, payload-free rejection from the Developer Kit tooling."""

    def __init__(
        self,
        code: ExtensionToolingErrorCode | str,
        *,
        field: str,
        message: str,
    ) -> None:
        self.code = str(code)
        self.field = field
        self.safe_message = message
        super().__init__(f"{self.code}: {field}: {message}")


def reject(
    code: ExtensionToolingErrorCode | str,
    *,
    field: str,
    message: str,
) -> NoReturn:
    raise ConformanceError(code, field=field, message=message)


@dataclass(frozen=True, slots=True)
class EnterpriseExtensionProject:
    root: Path
    project_id: str
    distribution_name: str
    package_name: str
    owner: str
    repository_url: str
    license_expression: str
    source_commit: str
    sdk_api_version: str
    runtime_version: str
    developer_kit_version: str
    manifest_path: Path
    configuration_path: Path
    configuration_schema_path: Path
    dependency_lock_path: Path
    conformance_fixture_path: Path
    source_root: Path
    tests_root: Path
    manifest_document: dict[str, Any]
    manifest: ExtensionManifest
    dependency_lock_digest: str
    sdk_wheel_digest: str
    source_files: tuple[Path, ...]
    test_files: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class SourceScan:
    source_file_count: int
    test_file_count: int
    import_roots: tuple[str, ...]
    source_digest: str
    core_copy_count: int
    forbidden_import_count: int
    nondeterministic_reference_count: int

    @property
    def document(self) -> dict[str, object]:
        return {
            "source_file_count": self.source_file_count,
            "test_file_count": self.test_file_count,
            "import_roots": list(self.import_roots),
            "source_digest": self.source_digest,
            "core_copy_count": self.core_copy_count,
            "forbidden_import_count": self.forbidden_import_count,
            "nondeterministic_reference_count": self.nondeterministic_reference_count,
        }


def _json_object(path: Path, *, field: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ConformanceError(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="required project document is unavailable",
        ) from error
    if not 1 <= len(raw) <= MAX_PROJECT_DOCUMENT_BYTES:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="project document is empty or exceeds the size limit",
        )

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                reject(
                    ExtensionToolingErrorCode.PROJECT_INVALID,
                    field=field,
                    message="duplicate JSON object key is forbidden",
                )
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=pairs_hook)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConformanceError(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="project document is not strict UTF-8 JSON",
        ) from error
    if not isinstance(value, dict):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="project document root must be an object",
        )
    return value


def _exact_keys(document: dict[str, Any], expected: set[str], *, field: str) -> None:
    if set(document) != expected:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="project document keys differ from the closed v1 contract",
        )


def _text(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value or len(value) > 512:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=key,
            message="field must be a bounded non-empty string",
        )
    return value


def _relative(root: Path, value: str, *, field: str, directory: bool) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="path must be a normalized project-relative path",
        )
    candidate = root.joinpath(relative)
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if not resolved.is_relative_to(resolved_root):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="path escapes the project root",
        )
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            reject(
                ExtensionToolingErrorCode.PROJECT_INVALID,
                field=field,
                message="symbolic links are forbidden in Extension projects",
            )
    if directory and not candidate.is_dir():
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="declared project directory is unavailable",
        )
    if not directory and not candidate.is_file():
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="declared project file is unavailable",
        )
    return candidate


def _validate_identity(document: dict[str, Any]) -> None:
    if _ID_RE.fullmatch(_text(document, "project_id")) is None:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="project_id",
            message="project identity must be a stable reverse-DNS identifier",
        )
    if _DISTRIBUTION_RE.fullmatch(_text(document, "distribution_name")) is None:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="distribution_name",
            message="distribution name must use canonical lowercase dash form",
        )
    if _PACKAGE_RE.fullmatch(_text(document, "package_name")) is None:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="package_name",
            message="package name must use canonical lowercase underscore form",
        )
    owner = _text(document, "owner")
    if owner.startswith("__") or owner.lower() in {"todo", "unknown", "example"}:
        reject(
            ExtensionToolingErrorCode.OWNER_UNDECLARED,
            field="owner",
            message="an accountable enterprise owner is required",
        )
    repository_url = _text(document, "repository_url")
    parsed = urlsplit(repository_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="repository_url",
            message="repository URL must be an explicit credential-free HTTPS URL",
        )
    license_expression = _text(document, "license_expression")
    if _LICENSE_RE.fullmatch(
        license_expression
    ) is None or license_expression.lower() in {"unlicensed", "unknown", "todo"}:
        reject(
            ExtensionToolingErrorCode.LICENSE_UNDECLARED,
            field="license_expression",
            message="an explicit SPDX identifier or LicenseRef is required",
        )
    if _COMMIT_RE.fullmatch(_text(document, "source_commit")) is None:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="source_commit",
            message="source commit must be an exact lowercase 40-character SHA",
        )


def _validate_versions(document: dict[str, Any]) -> None:
    expected = {
        "sdk_api_version": SDK_API_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "developer_kit_version": DEVELOPER_KIT_VERSION,
    }
    for field, value in expected.items():
        if document.get(field) != value:
            reject(
                ExtensionToolingErrorCode.VERSION_INCOMPATIBLE,
                field=field,
                message="project version lock differs from this verified tooling set",
            )


def _validate_pyproject(root: Path, document: dict[str, Any]) -> None:
    path = root / "pyproject.toml"
    try:
        project_file = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ConformanceError(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="pyproject.toml",
            message="pyproject is unavailable or invalid",
        ) from error
    build = project_file.get("build-system")
    project = project_file.get("project")
    tool = project_file.get("tool")
    if (
        not isinstance(build, dict)
        or not isinstance(project, dict)
        or not isinstance(tool, dict)
    ):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="pyproject.toml",
            message="pyproject is missing required tables",
        )
    if build != {
        "requires": ["hatchling==1.27.0"],
        "build-backend": "hatchling.build",
    }:
        reject(
            ExtensionToolingErrorCode.DEPENDENCY_LOCK_INVALID,
            field="build-system.requires",
            message="build backend must be exact and non-floating",
        )
    expected_project = {
        "name": document["distribution_name"],
        "version": "1.0.0",
        "requires-python": ">=3.12,<3.13",
        "dependencies": [f"aps-extension-sdk=={SDK_API_VERSION}"],
    }
    for field, expected in expected_project.items():
        if project.get(field) != expected:
            reject(
                ExtensionToolingErrorCode.DEPENDENCY_LOCK_INVALID,
                field=f"project.{field}",
                message="project metadata differs from the exact Extension contract",
            )
    authors = project.get("authors")
    license_value = project.get("license")
    urls = project.get("urls")
    if authors != [{"name": document["owner"]}]:
        reject(
            ExtensionToolingErrorCode.OWNER_UNDECLARED,
            field="project.authors",
            message="package owner differs from the project owner",
        )
    if license_value != {"text": document["license_expression"]}:
        reject(
            ExtensionToolingErrorCode.LICENSE_UNDECLARED,
            field="project.license",
            message="package license differs from the declared LicenseRef or SPDX value",
        )
    if urls != {"Repository": document["repository_url"]}:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="project.urls.Repository",
            message="package repository identity differs from the project contract",
        )
    plantnexus = tool.get("plantnexus-enterprise-extension")
    if not isinstance(plantnexus, dict):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="tool.plantnexus-enterprise-extension",
            message="pyproject lacks Extension metadata",
        )
    expected_tool = {
        "contract-version": PROJECT_CONTRACT_VERSION,
        "project-id": document["project_id"],
        "sdk-api-version": SDK_API_VERSION,
        "runtime-version": RUNTIME_VERSION,
        "developer-kit-version": DEVELOPER_KIT_VERSION,
        "manifest": document["manifest_path"],
    }
    if plantnexus != expected_tool:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="tool.plantnexus-enterprise-extension",
            message="pyproject Extension metadata differs from the project descriptor",
        )
    hatch = tool.get("hatch")
    expected_package = f"src/{document['package_name']}"
    packages: object = None
    if isinstance(hatch, dict):
        hatch_build = hatch.get("build")
        if isinstance(hatch_build, dict):
            targets = hatch_build.get("targets")
            if isinstance(targets, dict):
                wheel = targets.get("wheel")
                if isinstance(wheel, dict):
                    packages = wheel.get("packages")
    if packages != [expected_package]:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="tool.hatch.build.targets.wheel.packages",
            message="wheel package must be the one declared Extension source package",
        )


def _lock(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    try:
        lines = [
            line.strip()
            for line in raw.decode("utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except UnicodeDecodeError as error:
        raise ConformanceError(
            ExtensionToolingErrorCode.DEPENDENCY_LOCK_INVALID,
            field="dependency_lock_path",
            message="dependency lock must be UTF-8 text",
        ) from error
    match = _LOCK_LINE_RE.fullmatch(lines[0]) if len(lines) == 1 else None
    if match is None:
        reject(
            ExtensionToolingErrorCode.DEPENDENCY_LOCK_INVALID,
            field="dependency_lock_path",
            message="lock must contain exactly one hash-pinned APS Extension SDK dependency",
        )
    return f"sha256:{sha256(raw).hexdigest()}", f"sha256:{match.group(1)}"


def _python_files(directory: Path) -> tuple[Path, ...]:
    files = tuple(sorted(path for path in directory.rglob("*.py") if path.is_file()))
    if not files or len(files) > MAX_SOURCE_FILES:
        reject(
            ExtensionToolingErrorCode.SOURCE_INVALID,
            field=directory.name,
            message="Python source file count is empty or exceeds the project limit",
        )
    for path in files:
        if path.is_symlink() or not 1 <= path.stat().st_size <= MAX_SOURCE_FILE_BYTES:
            reject(
                ExtensionToolingErrorCode.SOURCE_INVALID,
                field=path.name,
                message="source file is empty, linked, or exceeds the size limit",
            )
    return files


def _source_scan(
    *,
    root: Path,
    source_root: Path,
    tests_root: Path,
    package_name: str,
    core_root: Path,
) -> tuple[tuple[Path, ...], tuple[Path, ...], SourceScan]:
    package_root = source_root / package_name
    if not package_root.is_dir() or not (package_root / "__init__.py").is_file():
        reject(
            ExtensionToolingErrorCode.SOURCE_INVALID,
            field="source_root",
            message="declared package and __init__.py are required under source_root",
        )
    source_files = _python_files(package_root)
    test_files = _python_files(tests_root)
    undeclared_source_files = sorted(
        set(path for path in source_root.rglob("*.py") if path.is_file())
        - set(source_files)
    )
    if undeclared_source_files:
        reject(
            ExtensionToolingErrorCode.SOURCE_INVALID,
            field="source_root",
            message="source_root contains Python modules outside the declared package",
        )
    core_hashes = {
        sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for path in core_root.rglob("*.py")
        if path.is_file() and path.stat().st_size > 100
    }
    project_files: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative_parts = path.relative_to(root).parts
        if any(part in _PROJECT_SCAN_EXCLUDES for part in relative_parts):
            continue
        if "vendor" in relative_parts:
            reject(
                ExtensionToolingErrorCode.SOURCE_IMPORT_FORBIDDEN,
                field="project",
                message="vendored source is forbidden in an Enterprise Extension project",
            )
        if path.is_symlink():
            reject(
                ExtensionToolingErrorCode.SOURCE_INVALID,
                field="project",
                message="symbolic links are forbidden in an Enterprise Extension project",
            )
        if path.is_file():
            if path.stat().st_size > MAX_PROJECT_FILE_BYTES:
                reject(
                    ExtensionToolingErrorCode.SOURCE_INVALID,
                    field="project",
                    message="project file exceeds the conformance size limit",
                )
            project_files.append(path)
    if len(project_files) > MAX_PROJECT_FILES:
        reject(
            ExtensionToolingErrorCode.SOURCE_INVALID,
            field="project",
            message="project file count exceeds the conformance limit",
        )
    for path in project_files:
        raw = path.read_bytes()
        if (
            len(raw) > 100
            and sha256(raw.replace(b"\r\n", b"\n")).hexdigest() in core_hashes
        ):
            reject(
                ExtensionToolingErrorCode.CORE_COPY_DETECTED,
                field=path.relative_to(root).as_posix(),
                message="project contains a byte-equivalent APS Core source file",
            )
    imports: set[str] = set()
    digest = sha256()
    for path in source_files + test_files:
        raw = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8") + b"\0" + raw + b"\0")
        try:
            source = raw.decode("utf-8")
            tree = ast.parse(source, filename=relative)
            compile(tree, relative, "exec")
        except (UnicodeDecodeError, SyntaxError, ValueError) as error:
            raise ConformanceError(
                ExtensionToolingErrorCode.SOURCE_INVALID,
                field=relative,
                message="source is not valid deterministic UTF-8 Python",
            ) from error
        is_product_source = path in source_files
        lowered = source.lower()
        if is_product_source and any(
            marker in lowered
            for marker in ("backend.app", "aps_core", "aps-core", "site-packages")
        ):
            reject(
                ExtensionToolingErrorCode.SOURCE_IMPORT_FORBIDDEN,
                field=relative,
                message="Extension source references a forbidden Core or environment boundary",
            )
        for node in ast.walk(tree):
            imported: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported = (node.module,)
            for imported_name in imported:
                top = imported_name.partition(".")[0]
                imports.add(top)
                if top in _FORBIDDEN_IMPORTS:
                    reject(
                        ExtensionToolingErrorCode.SOURCE_IMPORT_FORBIDDEN,
                        field=relative,
                        message="Extension imports an APS internal or undeclared dependency",
                    )
                if is_product_source and top in _NONDETERMINISTIC_OR_IO_IMPORTS:
                    reject(
                        ExtensionToolingErrorCode.SOURCE_NONDETERMINISTIC,
                        field=relative,
                        message="Extension runtime source imports nondeterministic or I/O capability",
                    )
                if top not in sys.stdlib_module_names and top not in {
                    package_name,
                    "aps_extension_sdk",
                }:
                    reject(
                        ExtensionToolingErrorCode.SOURCE_IMPORT_FORBIDDEN,
                        field=relative,
                        message="Extension declares a dependency other than the locked SDK",
                    )
            if is_product_source and isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in _FORBIDDEN_CALL_NAMES
                ):
                    reject(
                        ExtensionToolingErrorCode.SOURCE_NONDETERMINISTIC,
                        field=relative,
                        message="Extension runtime source calls a forbidden dynamic or I/O primitive",
                    )
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in _FORBIDDEN_ATTRIBUTE_CALLS
                ):
                    reject(
                        ExtensionToolingErrorCode.SOURCE_NONDETERMINISTIC,
                        field=relative,
                        message="Extension runtime source calls a nondeterministic or I/O primitive",
                    )
        if is_product_source:
            for node in tree.body:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    reject(
                        ExtensionToolingErrorCode.SOURCE_NONDETERMINISTIC,
                        field=relative,
                        message="import-time calls are forbidden",
                    )
    return (
        source_files,
        test_files,
        SourceScan(
            source_file_count=len(source_files),
            test_file_count=len(test_files),
            import_roots=tuple(sorted(imports)),
            source_digest=f"sha256:{digest.hexdigest()}",
            core_copy_count=0,
            forbidden_import_count=0,
            nondeterministic_reference_count=0,
        ),
    )


def _entrypoint_contract(
    project: EnterpriseExtensionProject,
) -> None:
    modules: dict[str, tuple[Path, set[str]]] = {}
    for descriptor in project.manifest.contributions:
        module_name, _, object_name = descriptor.implementation.partition(":")
        if not module_name.startswith(project.package_name + "."):
            reject(
                ExtensionToolingErrorCode.ENTRYPOINT_INVALID,
                field=descriptor.contribution_id,
                message="entrypoint must remain inside the declared standalone package",
            )
        module_path = project.source_root / (module_name.replace(".", "/") + ".py")
        if not module_path.is_file() or not module_path.resolve().is_relative_to(
            project.source_root.resolve()
        ):
            reject(
                ExtensionToolingErrorCode.ENTRYPOINT_INVALID,
                field=descriptor.contribution_id,
                message="declared entrypoint module is unavailable",
            )
        if module_name not in modules:
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            modules[module_name] = (
                module_path,
                {
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                },
            )
        if object_name not in modules[module_name][1]:
            reject(
                ExtensionToolingErrorCode.ENTRYPOINT_INVALID,
                field=descriptor.contribution_id,
                message="declared entrypoint object is unavailable",
            )
    by_id = {item.contribution_id: item for item in project.manifest.contributions}
    for descriptor in project.manifest.contributions:
        if not descriptor.affects_feasibility:
            continue
        source_module = descriptor.implementation.partition(":")[0]
        for validation_id in descriptor.validation_rule_ids:
            validation = by_id[validation_id]
            validation_module = validation.implementation.partition(":")[0]
            if source_module == validation_module:
                reject(
                    ExtensionToolingErrorCode.ENTRYPOINT_INVALID,
                    field=descriptor.contribution_id,
                    message="feasibility and Validation implementations require separate modules",
                )
            validation_text = modules[validation_module][0].read_text(encoding="utf-8")
            if (
                source_module in validation_text
                or descriptor.implementation in validation_text
            ):
                reject(
                    ExtensionToolingErrorCode.SOURCE_IMPORT_FORBIDDEN,
                    field=validation_id,
                    message="Validation implementation reuses its paired feasibility module",
                )


def load_project(
    project_root: Path,
    *,
    repository_root: Path,
    expected_sdk_wheel_digest: str | None = None,
) -> tuple[EnterpriseExtensionProject, SourceScan]:
    """Load and validate a closed Enterprise Extension project contract."""

    root = project_root.resolve()
    descriptor_path = root / "enterprise-extension-project.v1.json"
    document = _json_object(
        descriptor_path, field="enterprise-extension-project.v1.json"
    )
    _exact_keys(document, _PROJECT_KEYS, field="$project")
    if document.get("project_contract_version") != PROJECT_CONTRACT_VERSION:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="project_contract_version",
            message="only enterprise-extension-project.v1 is supported",
        )
    _validate_identity(document)
    _validate_versions(document)
    _validate_pyproject(root, document)
    manifest_path = _relative(
        root, _text(document, "manifest_path"), field="manifest_path", directory=False
    )
    configuration_path = _relative(
        root,
        _text(document, "configuration_path"),
        field="configuration_path",
        directory=False,
    )
    configuration_schema_path = _relative(
        root,
        _text(document, "configuration_schema_path"),
        field="configuration_schema_path",
        directory=False,
    )
    dependency_lock_path = _relative(
        root,
        _text(document, "dependency_lock_path"),
        field="dependency_lock_path",
        directory=False,
    )
    conformance_fixture_path = _relative(
        root,
        _text(document, "conformance_fixture_path"),
        field="conformance_fixture_path",
        directory=False,
    )
    source_root = _relative(
        root, _text(document, "source_root"), field="source_root", directory=True
    )
    tests_root = _relative(
        root, _text(document, "tests_root"), field="tests_root", directory=True
    )
    dependency_lock_digest, sdk_wheel_digest = _lock(dependency_lock_path)
    if (
        expected_sdk_wheel_digest is not None
        and sdk_wheel_digest != expected_sdk_wheel_digest
    ):
        reject(
            ExtensionToolingErrorCode.DEPENDENCY_LOCK_INVALID,
            field="dependency_lock_path",
            message="SDK wheel hash differs from the exact tooling input",
        )
    manifest_document = _json_object(manifest_path, field="manifest_path")
    try:
        manifest = parse_extension_manifest(manifest_document)
    except Exception as error:
        code = getattr(error, "code", ExtensionToolingErrorCode.MANIFEST_INVALID)
        field = getattr(error, "field", "manifest_path")
        raise ConformanceError(
            str(code),
            field=str(field),
            message="Extension manifest violates the SDK contract",
        ) from error
    if (
        manifest.extension_id != document["project_id"]
        or str(manifest.extension_version) != "1.0.0"
        or str(manifest.sdk_api_version) != SDK_API_VERSION
        or manifest.artifact_package != document["distribution_name"]
        or manifest.source_commit != document["source_commit"]
        or manifest.dependency_lock_digest != dependency_lock_digest
    ):
        reject(
            ExtensionToolingErrorCode.MANIFEST_INVALID,
            field="manifest_path",
            message="manifest identity or provenance differs from the project contract",
        )
    if not manifest.runtime_compatibility.contains(
        SemanticVersion.parse(RUNTIME_VERSION)
    ):
        reject(
            ExtensionToolingErrorCode.VERSION_INCOMPATIBLE,
            field="compatibility.runtime",
            message="manifest excludes the locked Runtime version",
        )
    schema_digest = (
        f"sha256:{sha256(configuration_schema_path.read_bytes()).hexdigest()}"
    )
    if manifest.configuration_schema_digest != schema_digest:
        reject(
            ExtensionToolingErrorCode.MANIFEST_INVALID,
            field="configuration.schema_digest",
            message="configuration schema digest differs from the declared file",
        )
    package_name = _text(document, "package_name")
    source_files, test_files, scan = _source_scan(
        root=root,
        source_root=source_root,
        tests_root=tests_root,
        package_name=package_name,
        core_root=repository_root / "backend/app",
    )
    project = EnterpriseExtensionProject(
        root=root,
        project_id=_text(document, "project_id"),
        distribution_name=_text(document, "distribution_name"),
        package_name=package_name,
        owner=_text(document, "owner"),
        repository_url=_text(document, "repository_url"),
        license_expression=_text(document, "license_expression"),
        source_commit=_text(document, "source_commit"),
        sdk_api_version=SDK_API_VERSION,
        runtime_version=RUNTIME_VERSION,
        developer_kit_version=DEVELOPER_KIT_VERSION,
        manifest_path=manifest_path,
        configuration_path=configuration_path,
        configuration_schema_path=configuration_schema_path,
        dependency_lock_path=dependency_lock_path,
        conformance_fixture_path=conformance_fixture_path,
        source_root=source_root,
        tests_root=tests_root,
        manifest_document=manifest_document,
        manifest=manifest,
        dependency_lock_digest=dependency_lock_digest,
        sdk_wheel_digest=sdk_wheel_digest,
        source_files=source_files,
        test_files=test_files,
    )
    _entrypoint_contract(project)
    return project, scan


__all__ = [
    "DEVELOPER_KIT_VERSION",
    "LOCK_CONTRACT_VERSION",
    "PROJECT_CONTRACT_VERSION",
    "RUNTIME_VERSION",
    "ConformanceError",
    "EnterpriseExtensionProject",
    "ExtensionToolingErrorCode",
    "SourceScan",
    "load_project",
    "reject",
]
