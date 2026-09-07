"""Reproducible APS Runtime release builder.

The authoritative P8-09 distribution is a deterministic tar+gzip archive.  It
contains the application wheel, exact dependency lock/export, immutable Schema
and OpenAPI bytes, the full Alembic chain, compatibility metadata, CycloneDX
SBOM, reviewed licenses, and the release policies that governed the build.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import gzip
from io import BytesIO
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tomllib
from typing import Any, cast
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

from app import (
    APPLICATION_VERSION,
    CORE_VERSION,
    RUNTIME_VERSION,
    SCHEMA_VERSION,
    SPEC_VERSION,
)
from app.infrastructure.release.contracts import (
    CHECKSUM_PATH,
    COMPATIBILITY_MANIFEST_VERSION,
    COMPATIBILITY_PATH,
    LICENSE_PATH,
    LICENSE_REPORT_VERSION,
    MANIFEST_PATH,
    MIGRATION_MANIFEST_VERSION,
    MIGRATION_PATH,
    RELEASE_MANIFEST_VERSION,
    SBOM_PATH,
    ReleaseContractError,
    canonical_json_bytes,
    sha256_fingerprint,
    sha256_hex,
    strict_json_document,
    verify_release_archive,
)


type JsonObject = dict[str, Any]

BUILDER_VERSION = "aps-runtime-release-builder.v1"
DEFAULT_POLICY_PATH = Path("infra/release/runtime-release-policy.v1.json")
DEFAULT_VULNERABILITY_POLICY_PATH = Path(
    "infra/release/runtime-vulnerability-policy.v1.json"
)
_MIN_ZIP_EPOCH = 315_532_800  # 1980-01-01; required by wheel ZIP metadata.
_COMMIT = re.compile(r"[0-9a-f]{40}")
_LICENSE_TOKEN = re.compile(r"(?:LicenseRef-)?[A-Za-z0-9][A-Za-z0-9.-]*")


@dataclass(frozen=True, slots=True)
class ReleaseArtifact:
    archive_path: Path
    checksum_path: Path
    archive_sha256: str
    archive_bytes: int
    release_fingerprint: str
    release_root: str
    runtime_version: str
    code_commit: str
    source_date_epoch: int
    payload_file_count: int


def _run(
    command: Sequence[str],
    *,
    root: Path,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if environment is not None:
        merged.update(environment)
    result = subprocess.run(
        list(command),
        cwd=root,
        env=merged,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise ReleaseContractError("BUILD_COMMAND_FAILED", "release build command failed")
    return result


def git_head(root: Path) -> str:
    value = _run(("git", "rev-parse", "HEAD"), root=root).stdout.strip()
    if _COMMIT.fullmatch(value) is None:
        raise ReleaseContractError("PROVENANCE_INVALID", "Git HEAD is not an immutable commit")
    return value


def source_date_epoch(root: Path, code_commit: str) -> int:
    if _COMMIT.fullmatch(code_commit) is None:
        raise ReleaseContractError("PROVENANCE_INVALID", "code commit is not immutable")
    raw = _run(("git", "show", "-s", "--format=%ct", code_commit), root=root).stdout.strip()
    try:
        observed = int(raw)
    except ValueError as error:
        raise ReleaseContractError("PROVENANCE_INVALID", "commit timestamp is unavailable") from error
    return max(_MIN_ZIP_EPOCH, observed)


def load_release_policy(root: Path) -> JsonObject:
    policy = strict_json_document((root / DEFAULT_POLICY_PATH).read_bytes())
    expected = {
        "policy_version",
        "artifact",
        "compatibility",
        "extension_boundary",
        "license_policy",
        "migration_policy",
        "preflight",
        "support_window",
        "target",
    }
    if set(policy) != expected or policy.get("policy_version") != "aps-runtime-release-policy.v1":
        raise ReleaseContractError("POLICY_INVALID", "release policy fields or version are invalid")
    return policy


def build_wheel(root: Path, destination: Path, *, epoch: int) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    _run(
        ("uv", "build", "--wheel", "--out-dir", str(destination)),
        root=root,
        environment={"SOURCE_DATE_EPOCH": str(max(_MIN_ZIP_EPOCH, epoch))},
    )
    wheels = sorted(destination.glob("*.whl"))
    if len(wheels) != 1 or wheels[0].is_symlink():
        raise ReleaseContractError("BUILD_OUTPUT_INVALID", "wheel build must produce one regular file")
    return wheels[0]


def export_runtime_requirements(root: Path) -> bytes:
    result = _run(
        (
            "uv",
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements.txt",
        ),
        root=root,
    )
    raw = result.stdout.encode("utf-8")
    active_lines = [line.strip().lower() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith(b"#")]
    if not raw or any(
        line.startswith((b"plantnexus-aps", b"-e ", b"--editable "))
        for line in active_lines
    ):
        raise ReleaseContractError("DEPENDENCY_EXPORT_INVALID", "runtime dependency export is invalid")
    return raw if raw.endswith(b"\n") else raw + b"\n"


def _package_index(lock: Mapping[str, object]) -> dict[str, JsonObject]:
    raw_packages = lock.get("package")
    if not isinstance(raw_packages, list):
        raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "uv.lock package inventory is missing")
    result: dict[str, JsonObject] = {}
    for raw in raw_packages:
        if not isinstance(raw, dict):
            raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "uv.lock package entry is malformed")
        package = cast(JsonObject, raw)
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or not isinstance(version, str) or name in result:
            raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "uv.lock package identity is invalid")
        result[name] = package
    return result


def _dependency_entries(package: Mapping[str, object], extras: set[str]) -> list[JsonObject]:
    result: list[JsonObject] = []
    dependencies = package.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "package dependencies are malformed")
    for raw in dependencies:
        if not isinstance(raw, dict):
            raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "dependency entry is malformed")
        result.append(cast(JsonObject, raw))
    optional = package.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "optional dependencies are malformed")
    for extra in sorted(extras):
        entries = optional.get(extra)
        if not isinstance(entries, list):
            raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "requested dependency extra is absent")
        for raw in entries:
            if not isinstance(raw, dict):
                raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "optional dependency is malformed")
            result.append(cast(JsonObject, raw))
    return result


def runtime_dependency_graph(lock_bytes: bytes) -> tuple[dict[str, JsonObject], dict[str, set[str]]]:
    try:
        lock = cast(JsonObject, tomllib.loads(lock_bytes.decode("utf-8")))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "uv.lock is not valid TOML") from error
    packages = _package_index(lock)
    root = packages.get("plantnexus-aps")
    if root is None:
        raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "project package is absent from uv.lock")

    requested_extras: dict[str, set[str]] = {"plantnexus-aps": set()}
    processed_extras: dict[str, set[str]] = {}
    graph: dict[str, set[str]] = {}
    pending = ["plantnexus-aps"]
    while pending:
        name = pending.pop()
        package = packages.get(name)
        if package is None:
            raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "dependency target is absent")
        extras = requested_extras.setdefault(name, set())
        if processed_extras.get(name) == extras:
            continue
        processed_extras[name] = set(extras)
        targets: set[str] = set()
        for dependency in _dependency_entries(package, extras):
            target = dependency.get("name")
            raw_extras = dependency.get("extra", [])
            if not isinstance(target, str) or not isinstance(raw_extras, list) or not all(
                isinstance(value, str) for value in raw_extras
            ):
                raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "dependency identity is malformed")
            if target not in packages:
                raise ReleaseContractError("DEPENDENCY_LOCK_INVALID", "dependency target is not locked")
            targets.add(target)
            target_extras = requested_extras.setdefault(target, set())
            before = set(target_extras)
            target_extras.update(cast(list[str], raw_extras))
            if target not in processed_extras or before != target_extras:
                pending.append(target)
        graph[name] = targets
    selected = {name: packages[name] for name in sorted(graph)}
    return selected, graph


def _license_tokens(expression: str) -> set[str]:
    return {
        token
        for token in _LICENSE_TOKEN.findall(expression)
        if token not in {"AND", "OR", "WITH"}
    }


def build_license_report(
    packages: Mapping[str, Mapping[str, object]], policy: Mapping[str, object]
) -> JsonObject:
    raw_policy = policy.get("license_policy")
    if not isinstance(raw_policy, dict):
        raise ReleaseContractError("POLICY_INVALID", "license policy is missing")
    allowed = raw_policy.get("allowed_identifiers")
    reviewed = raw_policy.get("reviewed_expressions")
    if not isinstance(allowed, list) or not all(isinstance(value, str) for value in allowed):
        raise ReleaseContractError("POLICY_INVALID", "allowed license identifiers are malformed")
    if not isinstance(reviewed, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in reviewed.items()
    ):
        raise ReleaseContractError("POLICY_INVALID", "reviewed license expressions are malformed")
    package_names = set(packages)
    if set(reviewed) != package_names:
        raise ReleaseContractError("LICENSE_POLICY_FAILED", "reviewed license inventory is not exact")
    allowed_set = set(cast(list[str], allowed))
    components: list[JsonObject] = []
    issues: list[str] = []
    for name in sorted(package_names):
        expression = cast(str, reviewed[name])
        tokens = _license_tokens(expression)
        passed = bool(tokens) and tokens <= allowed_set
        if not passed:
            issues.append(name)
        components.append(
            {
                "name": name,
                "version": packages[name]["version"],
                "license_expression": expression,
                "review_source": "PINNED_RELEASE_POLICY",
                "status": "PASS" if passed else "FAIL",
            }
        )
    return {
        "report_version": LICENSE_REPORT_VERSION,
        "policy_version": policy["policy_version"],
        "component_count": len(components),
        "components": components,
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    }


def _purl(name: str, version: str) -> str:
    return f"pkg:pypi/{quote(name, safe='-._')}@{quote(version, safe='-._')}"


def build_sbom(
    packages: Mapping[str, Mapping[str, object]],
    graph: Mapping[str, set[str]],
    *,
    lock_bytes: bytes,
    epoch: int,
    licenses: Mapping[str, object],
    target: Mapping[str, object],
) -> JsonObject:
    license_rows = licenses.get("components")
    if not isinstance(license_rows, list):
        raise ReleaseContractError("LICENSE_POLICY_FAILED", "license rows are unavailable")
    expressions = {
        cast(str, row["name"]): cast(str, row["license_expression"])
        for row in license_rows
        if isinstance(row, dict)
    }
    components: list[JsonObject] = []
    references: dict[str, str] = {}
    for name in sorted(packages):
        version = cast(str, packages[name]["version"])
        reference = _purl(name, version)
        references[name] = reference
        components.append(
            {
                "type": "application" if name == "plantnexus-aps" else "library",
                "bom-ref": reference,
                "name": name,
                "version": version,
                "purl": reference,
                "licenses": [{"expression": expressions[name]}],
                "properties": [
                    {
                        "name": "plantnexus:uv-lock-entry-sha256",
                        "value": sha256_hex(canonical_json_bytes(packages[name])),
                    },
                    {"name": "plantnexus:lock-scope", "value": "universal-runtime-superset"},
                ],
            }
        )
    dependencies = [
        {
            "ref": references[name],
            "dependsOn": sorted(references[target_name] for target_name in graph[name]),
        }
        for name in sorted(graph)
    ]
    lock_digest = sha256_hex(lock_bytes)
    timestamp = datetime.fromtimestamp(epoch, tz=UTC).isoformat().replace("+00:00", "Z")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid5(NAMESPACE_URL, f'plantnexus:{RUNTIME_VERSION}:{lock_digest}')}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "component": {
                "type": "application",
                "bom-ref": references["plantnexus-aps"],
                "name": "plantnexus-aps-runtime",
                "version": RUNTIME_VERSION,
            },
            "properties": [
                {"name": "plantnexus:target", "value": canonical_json_bytes(target).decode("utf-8")},
                {"name": "plantnexus:uv-lock-sha256", "value": f"sha256:{lock_digest}"},
            ],
        },
        "components": components,
        "dependencies": dependencies,
    }


def _assignment(tree: ast.Module, name: str) -> str | None:
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = ast.literal_eval(node.value) if node.value is not None else None
            if value is None or isinstance(value, str):
                return cast(str | None, value)
    raise ReleaseContractError("MIGRATION_INVALID", f"migration {name} assignment is missing")


def build_migration_manifest(root: Path, *, database_head: str) -> JsonObject:
    directory = root / "backend/migrations/versions"
    entries: dict[str, JsonObject] = {}
    for path in sorted(directory.glob("*.py")):
        if path.is_symlink():
            raise ReleaseContractError("MIGRATION_INVALID", "migration path is a symlink")
        raw = path.read_bytes()
        try:
            tree = ast.parse(raw)
        except SyntaxError as error:
            raise ReleaseContractError("MIGRATION_INVALID", "migration source cannot be parsed") from error
        revision = _assignment(tree, "revision")
        down_revision = _assignment(tree, "down_revision")
        if revision is None or revision in entries:
            raise ReleaseContractError("MIGRATION_INVALID", "migration revision identity is invalid")
        has_upgrade = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "upgrade" for node in tree.body)
        has_downgrade = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "downgrade" for node in tree.body)
        if not has_upgrade or not has_downgrade:
            raise ReleaseContractError("MIGRATION_INVALID", "migration lacks upgrade or downgrade")
        entries[revision] = {
            "revision": revision,
            "down_revision": down_revision,
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_fingerprint(raw),
            "downgrade_data_boundary": "POTENTIALLY_DESTRUCTIVE_REQUIRES_BACKUP",
        }
    ordered: list[JsonObject] = []
    current: str | None = database_head
    seen: set[str] = set()
    while current is not None:
        if current in seen or current not in entries:
            raise ReleaseContractError("MIGRATION_INVALID", "migration chain is cyclic or incomplete")
        seen.add(current)
        entry = entries[current]
        ordered.append(entry)
        current = cast(str | None, entry["down_revision"])
    ordered.reverse()
    if seen != set(entries):
        raise ReleaseContractError("MIGRATION_INVALID", "migration chain has multiple heads or branches")
    return {
        "manifest_version": MIGRATION_MANIFEST_VERSION,
        "database_head": database_head,
        "base_revision": cast(str, ordered[0]["revision"]),
        "revision_count": len(ordered),
        "linear_chain": ordered,
        "rollback": {
            "automatic_production_downgrade": False,
            "backup_required": True,
            "strategy": "BACKUP_RESTORE_OR_APPROVED_FORWARD_FIX",
        },
    }


def _copy_tree(files: dict[str, bytes], root: Path, source: Path, destination: str) -> None:
    resolved_source = root / source
    if resolved_source.is_symlink() or not resolved_source.is_dir():
        raise ReleaseContractError("BUILD_INPUT_INVALID", "release input directory is invalid")
    for path in sorted(resolved_source.rglob("*")):
        if path.is_symlink():
            raise ReleaseContractError("BUILD_INPUT_INVALID", "release input contains a symlink")
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        relative = path.relative_to(resolved_source).as_posix()
        files[f"{destination}/{relative}"] = path.read_bytes()


def _compatibility(policy: Mapping[str, object]) -> tuple[JsonObject, JsonObject]:
    raw = policy.get("compatibility")
    if not isinstance(raw, dict):
        raise ReleaseContractError("POLICY_INVALID", "compatibility policy is missing")
    compatibility = cast(JsonObject, raw)
    expected = {
        "runtime_version": RUNTIME_VERSION,
        "application_version": APPLICATION_VERSION,
        "core_version": CORE_VERSION,
        "schema_set_version": SCHEMA_VERSION,
        "spec_version": SPEC_VERSION,
    }
    for key, value in expected.items():
        if compatibility.get(key) != value:
            raise ReleaseContractError("VERSION_MISMATCH", f"{key} disagrees with package metadata")
    versions: JsonObject = {
        "runtime": RUNTIME_VERSION,
        "application": APPLICATION_VERSION,
        "core": CORE_VERSION,
        "api": compatibility["api_contract"],
        "schema": SCHEMA_VERSION,
        "spec": SPEC_VERSION,
        "database": compatibility["database_head"],
        "extension_sdk": compatibility["extension_sdk_version"],
        "developer_kit": compatibility["developer_kit_version"],
        "plugin_registry": compatibility["plugin_registry_protocol"],
    }
    document: JsonObject = {
        "manifest_version": COMPATIBILITY_MANIFEST_VERSION,
        "versions": versions,
        "upgrade_from": [],
        "automatic_upgrade": False,
        "runtime_core_compatibility": "EXACT_MATRIX_ONLY",
        "schema_compatibility": "EXACT_BUNDLED_SET_WITH_DOCUMENT_LEVEL_VERSIONS",
        "enterprise_extension_compatibility": "NOT_PUBLISHED_DEFAULT_EMPTY_ONLY",
        "production_approval": "REQUIRED_AND_NOT_GRANTED",
    }
    return versions, document


def build_release_files(
    root: Path,
    wheel: Path,
    *,
    code_commit: str,
    epoch: int,
) -> tuple[str, dict[str, bytes], str]:
    if _COMMIT.fullmatch(code_commit) is None:
        raise ReleaseContractError("PROVENANCE_INVALID", "code commit is not immutable")
    if wheel.is_symlink() or not wheel.is_file():
        raise ReleaseContractError("BUILD_INPUT_INVALID", "wheel input is unavailable")
    policy = load_release_policy(root)
    artifact_policy = cast(JsonObject, policy["artifact"])
    target = cast(JsonObject, policy["target"])
    if (
        artifact_policy.get("archive_format") != "tar+gzip"
        or artifact_policy.get("registry_policy") != "LOCAL_OR_CI_CONTENT_ADDRESSED_ONLY"
        or artifact_policy.get("remote_publication") is not False
    ):
        raise ReleaseContractError("POLICY_INVALID", "artifact publication policy is unsafe")

    lock_bytes = (root / "uv.lock").read_bytes()
    packages, graph = runtime_dependency_graph(lock_bytes)
    licenses = build_license_report(packages, policy)
    if licenses["status"] != "PASS":
        raise ReleaseContractError("LICENSE_POLICY_FAILED", "dependency license review failed")
    sbom = build_sbom(
        packages,
        graph,
        lock_bytes=lock_bytes,
        epoch=epoch,
        licenses=licenses,
        target=target,
    )
    versions, compatibility = _compatibility(policy)
    database_head = cast(str, versions["database"])
    migration = build_migration_manifest(root, database_head=database_head)
    requirements = export_runtime_requirements(root)

    files: dict[str, bytes] = {
        f"runtime/wheels/{wheel.name}": wheel.read_bytes(),
        "runtime/pyproject.toml": (root / "pyproject.toml").read_bytes(),
        "runtime/uv.lock": lock_bytes,
        "runtime/.python-version": (root / ".python-version").read_bytes(),
        "runtime/requirements/runtime-requirements.lock": requirements,
        "runtime/container/Dockerfile": (root / "infra/Dockerfile").read_bytes(),
        "runtime/alembic.ini": (root / "alembic.ini").read_bytes(),
        "runtime/openapi/headless-api.v1.json": (
            root / "backend/app/api/openapi/headless-api.v1.json"
        ).read_bytes(),
        "runtime/openapi/pre-p8-07-operation-baseline.v1.json": (
            root / "backend/app/api/openapi/pre-p8-07-operation-baseline.v1.json"
        ).read_bytes(),
        "policy/runtime-release-policy.v1.json": (root / DEFAULT_POLICY_PATH).read_bytes(),
        "policy/runtime-vulnerability-policy.v1.json": (
            root / DEFAULT_VULNERABILITY_POLICY_PATH
        ).read_bytes(),
        COMPATIBILITY_PATH: canonical_json_bytes(compatibility) + b"\n",
        MIGRATION_PATH: canonical_json_bytes(migration) + b"\n",
        LICENSE_PATH: canonical_json_bytes(licenses) + b"\n",
        SBOM_PATH: canonical_json_bytes(sbom) + b"\n",
    }
    _copy_tree(files, root, Path("backend/migrations"), "runtime/backend/migrations")
    _copy_tree(files, root, Path("schemas"), "runtime/schemas")

    payload = [
        {"path": path, "bytes": len(raw), "sha256": sha256_fingerprint(raw)}
        for path, raw in sorted(files.items())
    ]
    manifest_basis: JsonObject = {
        "manifest_version": RELEASE_MANIFEST_VERSION,
        "distribution_name": artifact_policy["distribution_name"],
        "code_commit": code_commit,
        "source_date_epoch": epoch,
        "target": target,
        "versions": versions,
        "extension_boundary": policy["extension_boundary"],
        "support_window": policy["support_window"],
        "signing": {
            "state": artifact_policy["signing_state"],
            "signature_present": False,
            "signable_input": "CANONICAL_MANIFEST_AND_SHA256_SIDECAR",
            "production_promotion_allowed": False,
        },
        "build": {
            "builder_version": BUILDER_VERSION,
            "archive_format": "tar+gzip",
            "dependency_lock_sha256": sha256_fingerprint(lock_bytes),
            "requirements_sha256": sha256_fingerprint(requirements),
            "wheel_sha256": sha256_fingerprint(files[f"runtime/wheels/{wheel.name}"]),
            "openapi_sha256": sha256_fingerprint(files["runtime/openapi/headless-api.v1.json"]),
        },
        "payload_files": payload,
    }
    release_fingerprint = sha256_fingerprint(canonical_json_bytes(manifest_basis))
    manifest = {**manifest_basis, "release_fingerprint": release_fingerprint}
    files[MANIFEST_PATH] = canonical_json_bytes(manifest) + b"\n"
    files[CHECKSUM_PATH] = "".join(
        f"{sha256_hex(raw)}  {path}\n"
        for path, raw in sorted(files.items())
        if path != CHECKSUM_PATH
    ).encode("utf-8")
    release_root = f"plantnexus-aps-runtime-{RUNTIME_VERSION}-linux-amd64"
    return release_root, files, release_fingerprint


def deterministic_archive(release_root: str, files: Mapping[str, bytes], *, epoch: int) -> bytes:
    tar_buffer = BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for path, raw in sorted(files.items()):
            info = tarfile.TarInfo(name=f"{release_root}/{path}")
            info.size = len(raw)
            info.mtime = epoch
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            archive.addfile(info, BytesIO(raw))
    output = BytesIO()
    with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=output, mtime=epoch) as compressed:
        compressed.write(tar_buffer.getvalue())
    return output.getvalue()


def _publish_immutable(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise ReleaseContractError("IMMUTABLE_CONFLICT", "content-addressed release path conflicts")
        return
    path.write_bytes(raw)


def build_release(
    root: Path,
    wheel: Path,
    output_directory: Path,
    *,
    code_commit: str | None = None,
    epoch: int | None = None,
) -> ReleaseArtifact:
    resolved_root = root.resolve(strict=True)
    resolved_commit = code_commit or git_head(resolved_root)
    resolved_epoch = epoch if epoch is not None else source_date_epoch(resolved_root, resolved_commit)
    if resolved_epoch < _MIN_ZIP_EPOCH:
        raise ReleaseContractError("PROVENANCE_INVALID", "SOURCE_DATE_EPOCH predates wheel support")
    release_root, files, fingerprint = build_release_files(
        resolved_root,
        wheel,
        code_commit=resolved_commit,
        epoch=resolved_epoch,
    )
    archive = deterministic_archive(release_root, files, epoch=resolved_epoch)
    digest = sha256_hex(archive)
    name = f"{release_root}.tar.gz"
    destination = output_directory / "sha256" / digest
    archive_path = destination / name
    checksum_path = destination / f"{name}.sha256"
    _publish_immutable(archive_path, archive)
    _publish_immutable(checksum_path, f"{digest}  {name}\n".encode("utf-8"))
    verified = verify_release_archive(
        archive_path,
        expected_runtime_version=RUNTIME_VERSION,
        expected_code_commit=resolved_commit,
    )
    return ReleaseArtifact(
        archive_path=archive_path,
        checksum_path=checksum_path,
        archive_sha256=f"sha256:{digest}",
        archive_bytes=len(archive),
        release_fingerprint=verified.release_fingerprint,
        release_root=release_root,
        runtime_version=RUNTIME_VERSION,
        code_commit=resolved_commit,
        source_date_epoch=resolved_epoch,
        payload_file_count=verified.payload_file_count,
    )


__all__ = [
    "BUILDER_VERSION",
    "DEFAULT_POLICY_PATH",
    "DEFAULT_VULNERABILITY_POLICY_PATH",
    "ReleaseArtifact",
    "build_license_report",
    "build_migration_manifest",
    "build_release",
    "build_release_files",
    "build_sbom",
    "build_wheel",
    "deterministic_archive",
    "export_runtime_requirements",
    "git_head",
    "load_release_policy",
    "runtime_dependency_graph",
    "source_date_epoch",
]
