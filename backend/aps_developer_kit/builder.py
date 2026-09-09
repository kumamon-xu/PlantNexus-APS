"""Deterministic assembly of a version-locked APS Developer Kit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
import tomllib
from typing import Any, cast
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

from aps_extension_sdk import SDK_API_VERSION
from aps_extension_tooling.conformance import conform_extension_set, conform_project
from aps_extension_tooling.packaging import (
    deterministic_zip,
    digest_bytes,
    extension_wheel,
    project_archive,
    sdk_wheel,
    tooling_wheel,
)
from app import APPLICATION_VERSION, CORE_VERSION, RUNTIME_VERSION, SCHEMA_VERSION, SPEC_VERSION
from app.infrastructure.release.contracts import verify_release_archive

from aps_developer_kit.contracts import (
    CHECKSUM_PATH,
    COMPATIBILITY_MATRIX_VERSION,
    COMPATIBILITY_PATH,
    CORE_SOURCE_INVENTORY_PATH,
    CORE_SOURCE_INVENTORY_VERSION,
    DeveloperKitContractError,
    KIT_LOCK_VERSION,
    KIT_MANIFEST_VERSION,
    LICENSE_PATH,
    LICENSE_REPORT_VERSION,
    LOCK_PATH,
    MANIFEST_PATH,
    SBOM_PATH,
    SIGNING_PATH,
    SIGNING_REQUEST_VERSION,
    SUPPORT_PATH,
    SUPPORT_POLICY_VERSION,
    canonical_json_bytes,
    sha256_fingerprint,
    strict_json_document,
    verify_kit_archive,
)


type JsonObject = dict[str, Any]

BUILDER_VERSION = "aps-developer-kit-builder.v1"
KIT_VERSION = "1.0.0"
TOOLING_VERSION = "1.0.0"
TEMPLATE_VERSION = "1.0.0"
DEFAULT_POLICY_PATH = Path("infra/release/developer-kit-release-policy.v1.json")
PREDECESSOR_PATH = Path("fixtures/developer-kit/p8-14-unpublished-predecessor.v1.json")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_P8_14_KIT_VERSION = "0.0.0-not-published"
_TOOL_DEPENDENCIES = (
    "attrs",
    "jsonschema",
    "jsonschema-specifications",
    "referencing",
    "rpds-py",
)
_DOCUMENTS = (
    "docs/contracts/extension-sdk-and-developer-kit.md",
    "docs/architecture/extension-sdk-runtime-and-developer-kit.md",
    "docs/architecture/enterprise-extension-development-guide.md",
    "docs/operations/developer-kit-release-upgrade-and-rollback.md",
    "docs/operations/security.md",
)


@dataclass(frozen=True, slots=True)
class DeveloperKitArtifact:
    archive_path: Path
    checksum_path: Path
    registry_path: Path
    archive_sha256: str
    archive_bytes: int
    release_fingerprint: str
    archive_root: str
    kit_version: str
    code_commit: str
    payload_file_count: int


def load_policy(root: Path) -> JsonObject:
    try:
        policy = strict_json_document((root / DEFAULT_POLICY_PATH).read_bytes())
    except OSError as error:
        raise DeveloperKitContractError(
            "KIT_POLICY_INVALID", "Developer Kit policy is unavailable"
        ) from error
    if policy.get("policy_version") != "aps-developer-kit-release-policy.v1":
        raise DeveloperKitContractError("KIT_POLICY_INVALID", "policy version is unsupported")
    expected = {
        "developer_kit": KIT_VERSION,
        "runtime": RUNTIME_VERSION,
        "application": APPLICATION_VERSION,
        "core": CORE_VERSION,
        "extension_sdk": SDK_API_VERSION,
        "extension_tooling": TOOLING_VERSION,
        "enterprise_template": TEMPLATE_VERSION,
        "schema_set": SCHEMA_VERSION,
        "spec": SPEC_VERSION,
    }
    versions = policy.get("versions")
    if not isinstance(versions, dict) or any(versions.get(key) != value for key, value in expected.items()):
        raise DeveloperKitContractError(
            "KIT_VERSION_MISMATCH", "policy versions differ from implementation"
        )
    return policy


def _normalized_tree(root: Path, *, prefix: str) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise DeveloperKitContractError("KIT_BUILD_INPUT_INVALID", "input tree is unavailable")
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise DeveloperKitContractError("KIT_BUILD_INPUT_INVALID", "input tree contains symlink")
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        if path.suffix.lower() in {".json", ".md", ".py", ".toml", ".txt", ".lock"}:
            raw = raw.replace(b"\r\n", b"\n")
        result[f"{prefix}/{relative}"] = raw
    return result


def _relock_project(source: Path, target: Path) -> Path:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    for relative in (
        "enterprise-extension-project.v1.json",
        "pyproject.toml",
        "README.md",
    ):
        path = target / relative
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(_P8_14_KIT_VERSION, KIT_VERSION),
            encoding="utf-8",
            newline="\n",
        )
    return target


def _relocked_template(source: Path, target: Path) -> Path:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    for path in sorted(
        candidate
        for candidate in target.rglob("*")
        if candidate.is_file() and candidate.suffix != ".pyc"
    ):
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(_P8_14_KIT_VERSION, KIT_VERSION),
            encoding="utf-8",
            newline="\n",
        )
    return target


def _core_inventory(root: Path) -> JsonObject:
    entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_fingerprint(path.read_bytes().replace(b"\r\n", b"\n")),
        }
        for path in sorted((root / "backend/app").rglob("*.py"))
        if path.is_file() and path.stat().st_size > 100
    ]
    if not entries:
        raise DeveloperKitContractError("KIT_BUILD_INPUT_INVALID", "Core source inventory is empty")
    return {
        "inventory_version": CORE_SOURCE_INVENTORY_VERSION,
        "algorithm": "sha256-normalized-lf",
        "entry_count": len(entries),
        "entries": entries,
    }


def _lock_packages(root: Path, policy: Mapping[str, object]) -> tuple[bytes, list[JsonObject]]:
    try:
        lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise DeveloperKitContractError("KIT_LOCK_INVALID", "uv.lock is unavailable or invalid") from error
    raw_packages = lock.get("package")
    expected = policy.get("tool_dependencies")
    if not isinstance(raw_packages, list) or not isinstance(expected, dict):
        raise DeveloperKitContractError("KIT_LOCK_INVALID", "tool dependency inventory is invalid")
    indexed = {
        row.get("name"): row
        for row in raw_packages
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    output: list[JsonObject] = []
    lines: list[str] = []
    for name in _TOOL_DEPENDENCIES:
        row = indexed.get(name)
        version = expected.get(name)
        if not isinstance(row, dict) or not isinstance(version, str) or row.get("version") != version:
            raise DeveloperKitContractError("KIT_LOCK_INVALID", "tool version differs from uv.lock")
        artifacts: list[Mapping[str, object]] = []
        sdist = row.get("sdist")
        wheels = row.get("wheels")
        if isinstance(sdist, dict):
            artifacts.append(cast(Mapping[str, object], sdist))
        if isinstance(wheels, list):
            artifacts.extend(cast(list[Mapping[str, object]], wheels))
        hashes = sorted(
            {
                cast(str, artifact["hash"])
                for artifact in artifacts
                if isinstance(artifact.get("hash"), str)
                and cast(str, artifact["hash"]).startswith("sha256:")
            }
        )
        if not hashes:
            raise DeveloperKitContractError("KIT_LOCK_INVALID", "tool artifact hashes are missing")
        line = f"{name}=={version}" + "".join(f" --hash={value}" for value in hashes)
        lines.append(line)
        output.append({"name": name, "version": version, "artifact_hashes": hashes})
    return ("\n".join(lines) + "\n").encode("utf-8"), output


def _artifact_entry(path: str, raw: bytes) -> JsonObject:
    return {"path": path, "sha256": sha256_fingerprint(raw), "bytes": len(raw)}


def _license_report(policy: Mapping[str, object], versions: Mapping[str, object]) -> JsonObject:
    license_policy = policy.get("license_policy")
    if not isinstance(license_policy, dict):
        raise DeveloperKitContractError("KIT_POLICY_INVALID", "license policy is missing")
    reviewed = license_policy.get("reviewed_expressions")
    allowed = license_policy.get("allowed_identifiers")
    if not isinstance(reviewed, dict) or not isinstance(allowed, list):
        raise DeveloperKitContractError("KIT_POLICY_INVALID", "license inventory is malformed")
    component_versions = {
        "plantnexus-aps-runtime": versions["runtime"],
        "aps-extension-sdk": versions["extension_sdk"],
        "aps-developer-kit-tools": versions["extension_tooling"],
        "enterprise-extension-template": versions["enterprise_template"],
        "example-alpha-aps-extension": "1.0.0",
        "example-beta-aps-extension": "1.0.0",
        **cast(dict[str, str], policy["tool_dependencies"]),
    }
    if set(reviewed) != set(component_versions):
        raise DeveloperKitContractError("KIT_LICENSE_POLICY_FAILED", "license inventory is not exact")
    allowed_set = set(cast(list[str], allowed))
    components: list[JsonObject] = []
    issues: list[str] = []
    for name in sorted(component_versions):
        expression = reviewed[name]
        if not isinstance(expression, str) or expression not in allowed_set:
            issues.append(name)
        components.append(
            {
                "name": name,
                "version": component_versions[name],
                "license_expression": expression,
                "review_source": "PINNED_DEVELOPER_KIT_POLICY",
                "status": "PASS" if name not in issues else "FAIL",
            }
        )
    return {
        "report_version": LICENSE_REPORT_VERSION,
        "component_count": len(components),
        "components": components,
        "unknown_license_count": len(issues),
        "repository_public_license_present": license_policy.get(
            "repository_public_license_present"
        ),
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    }


def _purl(name: str, version: object) -> str:
    return f"pkg:pypi/{quote(name, safe='-._')}@{quote(str(version), safe='-._')}"


def _sbom(
    licenses: Mapping[str, object],
    *,
    kit_version: str,
    lock_digest: str,
    epoch: int,
    runtime_sbom_digest: str,
) -> JsonObject:
    rows = licenses.get("components")
    if not isinstance(rows, list):
        raise DeveloperKitContractError("KIT_LICENSE_POLICY_FAILED", "license rows are missing")
    components = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise DeveloperKitContractError("KIT_LICENSE_POLICY_FAILED", "license row is malformed")
        name = cast(str, raw["name"])
        version = raw["version"]
        reference = _purl(name, version)
        components.append(
            {
                "type": "application" if name == "plantnexus-aps-runtime" else "library",
                "bom-ref": reference,
                "name": name,
                "version": version,
                "purl": reference,
                "licenses": [{"expression": raw["license_expression"]}],
            }
        )
    timestamp = datetime.fromtimestamp(epoch, tz=UTC).isoformat().replace("+00:00", "Z")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid5(NAMESPACE_URL, f'plantnexus-kit:{kit_version}:{lock_digest}')}" ,
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "component": {
                "type": "application",
                "bom-ref": f"pkg:generic/plantnexus-aps-developer-kit@{kit_version}",
                "name": "plantnexus-aps-developer-kit",
                "version": kit_version,
            },
            "properties": [
                {"name": "plantnexus:kit-lock-sha256", "value": lock_digest},
                {"name": "plantnexus:nested-runtime-sbom-sha256", "value": runtime_sbom_digest},
            ],
        },
        "components": components,
    }


def build_developer_kit_files(
    root: Path,
    runtime_archive: Path,
    *,
    code_commit: str,
    epoch: int,
) -> tuple[str, dict[str, bytes], str]:
    """Build the canonical in-memory Kit file map from exact immutable inputs."""

    if _COMMIT.fullmatch(code_commit) is None:
        raise DeveloperKitContractError("KIT_PROVENANCE_INVALID", "code commit is not immutable")
    policy = load_policy(root)
    versions = cast(JsonObject, policy["versions"])
    runtime = verify_release_archive(
        runtime_archive,
        expected_runtime_version=RUNTIME_VERSION,
        expected_code_commit=code_commit,
    )
    runtime_bytes = runtime_archive.read_bytes()
    sdk_name, sdk_bytes = sdk_wheel(root)
    tooling_name, tooling_bytes = tooling_wheel(
        root, developer_kit_version=TOOLING_VERSION
    )
    core_inventory = _core_inventory(root)
    core_digests = frozenset(
        cast(str, entry["sha256"]).removeprefix("sha256:")
        for entry in cast(list[JsonObject], core_inventory["entries"])
    )
    tool_lock_bytes, tool_packages = _lock_packages(root, policy)

    with TemporaryDirectory(prefix="aps-developer-kit-inputs-") as temporary:
        workspace = Path(temporary)
        template = _relocked_template(
            root / "templates/enterprise-extension", workspace / "template"
        )
        alpha_root = _relock_project(
            root / "examples/enterprise-extensions/alpha-resource-tag",
            workspace / "alpha",
        )
        beta_root = _relock_project(
            root / "examples/enterprise-extensions/beta-priority-policy",
            workspace / "beta",
        )
        alpha = conform_project(
            alpha_root,
            repository_root=root,
            clean_install=False,
            expected_runtime_version=RUNTIME_VERSION,
            expected_developer_kit_version=KIT_VERSION,
            forbidden_core_digests=core_digests,
        )
        beta = conform_project(
            beta_root,
            repository_root=root,
            clean_install=False,
            expected_runtime_version=RUNTIME_VERSION,
            expected_developer_kit_version=KIT_VERSION,
            forbidden_core_digests=core_digests,
        )
        with TemporaryDirectory(prefix="aps-developer-kit-runtime-") as runtime_directory:
            _, extension_set_report = conform_extension_set(
                (alpha, beta), runtime_directory=Path(runtime_directory)
            )
        template_archive = project_archive(template)
        alpha_archive = project_archive(alpha_root)
        beta_archive = project_archive(beta_root)
        _, alpha_wheel = extension_wheel(alpha.project)
        _, beta_wheel = extension_wheel(beta.project)
        files = {
            **_normalized_tree(template, prefix="templates/enterprise-extension"),
            **_normalized_tree(alpha_root, prefix="examples/alpha-resource-tag"),
            **_normalized_tree(beta_root, prefix="examples/beta-priority-policy"),
        }

    runtime_path = f"artifacts/runtime/{runtime_archive.name}"
    sdk_path = f"artifacts/sdk/{sdk_name}"
    tooling_path = f"artifacts/tooling/{tooling_name}"
    template_path = f"artifacts/template/enterprise-extension-template-{TEMPLATE_VERSION}.zip"
    alpha_path = f"artifacts/extensions/{alpha.extension_wheel_name}"
    beta_path = f"artifacts/extensions/{beta.extension_wheel_name}"
    files.update(
        {
            runtime_path: runtime_bytes,
            sdk_path: sdk_bytes,
            tooling_path: tooling_bytes,
            template_path: template_archive,
            alpha_path: alpha_wheel,
            beta_path: beta_wheel,
            "artifacts/examples/alpha-resource-tag-1.0.0.zip": alpha_archive,
            "artifacts/examples/beta-priority-policy-1.0.0.zip": beta_archive,
            "reports/alpha.conformance.json": canonical_json_bytes(alpha.report) + b"\n",
            "reports/beta.conformance.json": canonical_json_bytes(beta.report) + b"\n",
            "reports/extension-set.conformance.json": (
                canonical_json_bytes(extension_set_report) + b"\n"
            ),
            "tools/aps_extension_conformance.py": (
                root / "scripts/aps_extension_conformance.py"
            ).read_bytes().replace(b"\r\n", b"\n"),
            "locks/developer-tools-requirements.lock": tool_lock_bytes,
            "policy/developer-kit-release-policy.v1.json": (
                root / DEFAULT_POLICY_PATH
            ).read_bytes(),
            "policy/p8-14-unpublished-predecessor.v1.json": (
                root / PREDECESSOR_PATH
            ).read_bytes(),
        }
    )
    for document in _DOCUMENTS:
        try:
            files[document] = (root / document).read_bytes().replace(b"\r\n", b"\n")
        except OSError as error:
            raise DeveloperKitContractError(
                "KIT_BUILD_INPUT_INVALID", "required Developer Kit document is unavailable"
            ) from error
    files[CORE_SOURCE_INVENTORY_PATH] = canonical_json_bytes(core_inventory) + b"\n"

    runtime_sbom = strict_json_document(runtime.files["metadata/sbom.cdx.json"])
    runtime_sbom_digest = sha256_fingerprint(canonical_json_bytes(runtime_sbom) + b"\n")
    artifact_entries = {
        "runtime": _artifact_entry(runtime_path, runtime_bytes),
        "sdk": _artifact_entry(sdk_path, sdk_bytes),
        "tooling": _artifact_entry(tooling_path, tooling_bytes),
        "template": _artifact_entry(template_path, template_archive),
        "alpha_extension": _artifact_entry(alpha_path, alpha_wheel),
        "beta_extension": _artifact_entry(beta_path, beta_wheel),
    }
    lock: JsonObject = {
        "lock_version": KIT_LOCK_VERSION,
        "code_commit": code_commit,
        "versions": versions,
        "runtime_identity": {
            "code_commit": runtime.code_commit,
            "release_fingerprint": runtime.release_fingerprint,
            "archive_sha256": sha256_fingerprint(runtime_bytes),
            "nested_sbom_sha256": runtime_sbom_digest,
        },
        "artifacts": artifact_entries,
        "tool_dependencies": tool_packages,
        "tool_requirements_path": "locks/developer-tools-requirements.lock",
        "tool_requirements_sha256": sha256_fingerprint(tool_lock_bytes),
    }
    files[LOCK_PATH] = canonical_json_bytes(lock) + b"\n"
    compatibility: JsonObject = {
        "matrix_version": COMPATIBILITY_MATRIX_VERSION,
        "kit_version": KIT_VERSION,
        "versions": versions,
        "selection": cast(JsonObject, policy["compatibility"])["selection"],
        "automatic_upgrade": False,
        "supported_combinations": cast(JsonObject, policy["compatibility"])[
            "supported_combinations"
        ],
        "upgrade_from": cast(JsonObject, policy["compatibility"])["upgrade_from"],
        "extension_set": {
            "extension_ids": sorted(
                [alpha.project.project_id, beta.project.project_id]
            ),
            "extension_set_fingerprint": extension_set_report[
                "extension_set_fingerprint"
            ],
            "synthetic": True,
        },
        "invalid_combination_action": "REJECT_BEFORE_INSTALL_OR_RUNTIME_LOAD",
        "production_authorized": False,
    }
    files[COMPATIBILITY_PATH] = canonical_json_bytes(compatibility) + b"\n"
    support_policy = cast(JsonObject, policy["support"])
    support: JsonObject = {
        "support_policy_version": SUPPORT_POLICY_VERSION,
        **support_policy,
        "automatic_upgrade": False,
        "predecessor_replay": "P8_14_SYNTHETIC_UNPUBLISHED_ONLY",
        "rollback": "RETAIN_IMMUTABLE_BYTES_AND_RESTORE_EXPLICIT_PROJECT_LOCK",
    }
    files[SUPPORT_PATH] = canonical_json_bytes(support) + b"\n"
    signing = cast(JsonObject, policy["signing"])
    signing_request: JsonObject = {
        "request_version": SIGNING_REQUEST_VERSION,
        "kit_version": KIT_VERSION,
        "code_commit": code_commit,
        "state": signing["state"],
        "signature_present": False,
        "approved_external_key": False,
        "subject": {
            "manifest_path": MANIFEST_PATH,
            "sidecar": "EXTERNAL_ARCHIVE_SHA256_SIDECAR",
            "binding": "VERIFY_MANIFEST_FINGERPRINT_AT_SIGNING_TIME",
        },
        "next_action": "EXTERNAL_RELEASE_AUTHORITY_MUST_SIGN_WITHOUT_OVERWRITING_BYTES",
    }
    files[SIGNING_PATH] = canonical_json_bytes(signing_request) + b"\n"
    licenses = _license_report(policy, versions)
    if licenses["status"] != "PASS":
        raise DeveloperKitContractError(
            "KIT_LICENSE_POLICY_FAILED", "Developer Kit license policy failed"
        )
    files[LICENSE_PATH] = canonical_json_bytes(licenses) + b"\n"
    sbom = _sbom(
        licenses,
        kit_version=KIT_VERSION,
        lock_digest=sha256_fingerprint(files[LOCK_PATH]),
        epoch=epoch,
        runtime_sbom_digest=runtime_sbom_digest,
    )
    files[SBOM_PATH] = canonical_json_bytes(sbom) + b"\n"

    payload = [
        {"path": path, "bytes": len(raw), "sha256": sha256_fingerprint(raw)}
        for path, raw in sorted(files.items())
    ]
    artifact_policy = cast(JsonObject, policy["artifact"])
    manifest_basis: JsonObject = {
        "manifest_version": KIT_MANIFEST_VERSION,
        "distribution_name": artifact_policy["distribution_name"],
        "kit_version": KIT_VERSION,
        "code_commit": code_commit,
        "source_date_epoch": epoch,
        "release_owner": cast(JsonObject, policy["support"])["owner"],
        "registry": {
            "policy": artifact_policy["registry_policy"],
            "content_address_algorithm": artifact_policy["content_address_algorithm"],
            "remote_publication": artifact_policy["remote_publication"],
        },
        "versions": versions,
        "signing": {
            "state": signing["state"],
            "signature_present": signing["signature_present"],
            "approved_external_key": signing["approved_external_key"],
            "public_promotion_allowed": signing["public_promotion_allowed"],
            "production_promotion_allowed": signing["production_promotion_allowed"],
        },
        "build": {
            "builder_version": BUILDER_VERSION,
            "archive_format": "zip",
            "policy_sha256": sha256_fingerprint((root / DEFAULT_POLICY_PATH).read_bytes()),
            "root_lock_sha256": sha256_fingerprint((root / "uv.lock").read_bytes()),
            "kit_lock_sha256": sha256_fingerprint(files[LOCK_PATH]),
            "core_source_inventory_sha256": sha256_fingerprint(
                files[CORE_SOURCE_INVENTORY_PATH]
            ),
            "documentation_count": len(_DOCUMENTS),
            "clean_inputs_required": True,
        },
        "payload_files": payload,
    }
    fingerprint = sha256_fingerprint(canonical_json_bytes(manifest_basis))
    files[MANIFEST_PATH] = canonical_json_bytes(
        {**manifest_basis, "release_fingerprint": fingerprint}
    ) + b"\n"
    files[CHECKSUM_PATH] = "".join(
        f"{sha256_fingerprint(raw).removeprefix('sha256:')}  {path}\n"
        for path, raw in sorted(files.items())
        if path != CHECKSUM_PATH
    ).encode("utf-8")
    return f"plantnexus-aps-developer-kit-{KIT_VERSION}", files, fingerprint


def deterministic_archive(archive_root: str, files: Mapping[str, bytes]) -> bytes:
    return deterministic_zip({f"{archive_root}/{path}": raw for path, raw in files.items()})


def _publish_immutable(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise DeveloperKitContractError(
                "KIT_REGISTRY_CONFLICT", "immutable Developer Kit path conflicts"
            )
        return
    path.write_bytes(raw)


def _publish_registry(
    path: Path,
    *,
    kit_version: str,
    archive_sha256: str,
    release_fingerprint: str,
    archive_path: Path,
    code_commit: str,
) -> None:
    entries: list[JsonObject] = []
    if path.exists():
        document = strict_json_document(path.read_bytes())
        raw_entries = document.get("entries")
        if (
            document.get("registry_version") != "aps-developer-kit-registry.v1"
            or not isinstance(raw_entries, list)
            or not all(isinstance(entry, dict) for entry in raw_entries)
        ):
            raise DeveloperKitContractError("KIT_REGISTRY_INVALID", "Kit registry is malformed")
        entries = cast(list[JsonObject], raw_entries)
    same_version = [entry for entry in entries if entry.get("kit_version") == kit_version]
    expected = {
        "kit_version": kit_version,
        "archive_sha256": archive_sha256,
        "release_fingerprint": release_fingerprint,
        "relative_path": archive_path.relative_to(path.parent).as_posix(),
        "code_commit": code_commit,
        "channel": "UNSIGNED_ENGINEERING_CANDIDATE",
    }
    if same_version and same_version != [expected]:
        raise DeveloperKitContractError(
            "KIT_REGISTRY_CONFLICT", "Kit version already maps to different immutable bytes"
        )
    if not same_version:
        entries.append(expected)
    output = canonical_json_bytes(
        {
            "registry_version": "aps-developer-kit-registry.v1",
            "append_only": True,
            "remote_publication": False,
            "entries": sorted(entries, key=lambda entry: cast(str, entry["kit_version"])),
        }
    ) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(output)
    temporary.replace(path)


def build_developer_kit(
    root: Path,
    runtime_archive: Path,
    output_directory: Path,
    *,
    code_commit: str,
    epoch: int,
) -> DeveloperKitArtifact:
    archive_root, files, fingerprint = build_developer_kit_files(
        root,
        runtime_archive,
        code_commit=code_commit,
        epoch=epoch,
    )
    archive = deterministic_archive(archive_root, files)
    archive_sha256 = digest_bytes(archive)
    digest_hex = archive_sha256.removeprefix("sha256:")
    filename = f"{archive_root}-{digest_hex[:16]}.zip"
    destination = output_directory / "registry" / "versions" / KIT_VERSION / "sha256" / digest_hex
    archive_path = destination / filename
    checksum_path = destination / f"{filename}.sha256"
    _publish_immutable(archive_path, archive)
    _publish_immutable(
        checksum_path,
        f"{digest_hex}  {filename}\n".encode("utf-8"),
    )
    verified = verify_kit_archive(
        archive_path,
        expected_kit_version=KIT_VERSION,
        expected_code_commit=code_commit,
    )
    registry_path = output_directory / "registry" / "developer-kit-registry.v1.json"
    _publish_registry(
        registry_path,
        kit_version=KIT_VERSION,
        archive_sha256=archive_sha256,
        release_fingerprint=fingerprint,
        archive_path=archive_path,
        code_commit=code_commit,
    )
    return DeveloperKitArtifact(
        archive_path=archive_path,
        checksum_path=checksum_path,
        registry_path=registry_path,
        archive_sha256=archive_sha256,
        archive_bytes=len(archive),
        release_fingerprint=fingerprint,
        archive_root=archive_root,
        kit_version=KIT_VERSION,
        code_commit=code_commit,
        payload_file_count=verified.payload_file_count,
    )


__all__ = [
    "BUILDER_VERSION",
    "DEFAULT_POLICY_PATH",
    "DeveloperKitArtifact",
    "KIT_VERSION",
    "TEMPLATE_VERSION",
    "TOOLING_VERSION",
    "build_developer_kit",
    "build_developer_kit_files",
    "deterministic_archive",
    "load_policy",
]
