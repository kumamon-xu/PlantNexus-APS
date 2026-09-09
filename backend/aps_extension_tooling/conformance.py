"""Scaffold and conformance harness for trusted Enterprise Extensions."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import importlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping, cast
import venv

from aps_extension_sdk import (
    SDK_API_VERSION,
    ConstraintOutput,
    ExtensionContractError,
    ExtensionPoint,
    ObjectiveOutput,
    ObjectiveStage,
    PlanningRuleOutput,
    RegistryResolution,
    ReplanDecision,
    ValidationOutput,
    canonical_json_bytes,
    fingerprint_json,
)
from app.extensions.contracts import RuntimeExtensionArtifact, RuntimeExtensionError
from app.extensions.loader import load_runtime_extensions, runtime_extension_signature
from app.extensions.registry import LoadedRuntimeExtensionAdapter
from jsonschema import Draft202012Validator

from aps_extension_tooling.packaging import (
    digest_bytes,
    extension_wheel,
    extension_wheel_for_source,
    sdk_wheel,
    write_artifact,
)
from aps_extension_tooling.project import (
    DEVELOPER_KIT_VERSION,
    RUNTIME_VERSION,
    ConformanceError,
    EnterpriseExtensionProject,
    ExtensionToolingErrorCode,
    SourceScan,
    load_project,
    reject,
)


CONFORMANCE_FIXTURE_VERSION = "enterprise-extension-conformance-fixture.v1"
CONFORMANCE_REPORT_VERSION = "enterprise-extension-conformance-report.v1"
CONFORMANCE_SET_REPORT_VERSION = "enterprise-extension-set-report.v1"
CONFORMANCE_KEY_ID = "p8.enterprise.conformance.key.v1"
_CONFORMANCE_KEY = b"P8-14-conformance-only-HMAC-key-not-for-production-v1"
_UNRESOLVED_TOKEN = re.compile(r"__[A-Z][A-Z0-9_]+__")
_FIXTURE_KEYS = {
    "conformance_fixture_version",
    "scope",
    "facts",
    "provenance",
    "negative_validation_facts",
    "expect_validation_rejection",
    "replan_bindings",
    "fixture_fingerprint",
}
_CONFIGURATION_KEYS = {
    "configuration_contract_version",
    "extension_id",
    "values",
    "configuration_fingerprint",
}


@dataclass(frozen=True, slots=True)
class ConformanceResult:
    project: EnterpriseExtensionProject
    source_scan: SourceScan
    sdk_wheel_name: str
    sdk_wheel_bytes: bytes
    extension_wheel_name: str
    extension_wheel_bytes: bytes
    configuration: dict[str, Any]
    fixture: dict[str, Any]
    implementations: tuple[tuple[str, object], ...]
    project_test_count: int
    report: dict[str, Any]

    @property
    def artifact(self) -> RuntimeExtensionArtifact:
        return RuntimeExtensionArtifact(
            extension_id=self.project.project_id,
            artifact_bytes=self.extension_wheel_bytes,
            implementations=self.implementations,
        )


def _json(path: Path, *, field: str) -> dict[str, Any]:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                reject(
                    ExtensionToolingErrorCode.PROJECT_INVALID,
                    field=field,
                    message="duplicate JSON key is forbidden",
                )
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=pairs_hook)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConformanceError(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="required document is not strict UTF-8 JSON",
        ) from error
    if not isinstance(value, dict):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field=field,
            message="required document root must be an object",
        )
    return value


def _configuration(project: EnterpriseExtensionProject) -> dict[str, Any]:
    document = _json(project.configuration_path, field="configuration_path")
    if set(document) != _CONFIGURATION_KEYS:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="configuration_path",
            message="configuration fields differ from the closed Runtime contract",
        )
    if (
        document.get("extension_id") != project.project_id
        or document.get("configuration_contract_version")
        != project.manifest.configuration_contract
        or not isinstance(document.get("values"), dict)
    ):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="configuration_path",
            message="configuration identity or values differ from the manifest",
        )
    provided = document.get("configuration_fingerprint")
    projection = dict(document)
    projection.pop("configuration_fingerprint")
    if provided != fingerprint_json(projection):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="configuration_fingerprint",
            message="configuration fingerprint differs from canonical content",
        )
    schema = _json(
        project.configuration_schema_path,
        field="configuration_schema_path",
    )
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
    ):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="configuration_schema_path",
            message="configuration schema must be a closed Draft 2020-12 object",
        )

    def references(value: object) -> tuple[str, ...]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "$ref" and isinstance(child, str):
                    found.append(child)
                found.extend(references(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(references(child))
        return tuple(found)

    if any(not reference.startswith("#/") for reference in references(schema)):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="configuration_schema_path.$ref",
            message="configuration schema references must remain local to the document",
        )
    try:
        Draft202012Validator.check_schema(schema)
        validation_error = next(
            Draft202012Validator(schema).iter_errors(document["values"]),
            None,
        )
    except Exception as error:
        raise ConformanceError(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="configuration_schema_path",
            message="configuration schema cannot be evaluated locally",
        ) from error
    if validation_error is not None:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="configuration_path.values",
            message="configuration values do not satisfy the declared schema",
        )
    return document


def _fixture(project: EnterpriseExtensionProject) -> dict[str, Any]:
    document = _json(project.conformance_fixture_path, field="conformance_fixture_path")
    if (
        set(document) != _FIXTURE_KEYS
        or document.get("conformance_fixture_version") != CONFORMANCE_FIXTURE_VERSION
    ):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="conformance_fixture_path",
            message="fixture fields or version differ from the closed conformance contract",
        )
    for field in ("scope", "facts", "provenance", "replan_bindings"):
        if not isinstance(document.get(field), dict):
            reject(
                ExtensionToolingErrorCode.PROJECT_INVALID,
                field=f"conformance_fixture_path.{field}",
                message="fixture value must be a JSON object",
            )
    negative = document.get("negative_validation_facts")
    expected_rejection = document.get("expect_validation_rejection")
    if (
        not isinstance(expected_rejection, bool)
        or (expected_rejection and not isinstance(negative, dict))
        or (not expected_rejection and negative is not None)
    ):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="conformance_fixture_path.negative_validation_facts",
            message="negative validation fixture and expectation are inconsistent",
        )
    provided = document.get("fixture_fingerprint")
    projection = dict(document)
    projection.pop("fixture_fingerprint")
    if provided != fingerprint_json(projection):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="fixture_fingerprint",
            message="fixture fingerprint differs from canonical content",
        )
    bindings = cast(dict[str, Any], document["replan_bindings"])
    expected_binding_keys = {
        "execution_fact_fingerprint",
        "hard_lock_fingerprint",
        "freeze_window_fingerprint",
        "state_machine_version",
        "publication_authority_reference",
    }
    if set(bindings) != expected_binding_keys:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="replan_bindings",
            message="replan fixture must bind all five protected authorities",
        )
    return document


def _materialize(project: EnterpriseExtensionProject) -> tuple[tuple[str, object], ...]:
    buffer = StringIO()
    inserted = str(project.source_root)
    for name in tuple(sys.modules):
        if name == project.package_name or name.startswith(project.package_name + "."):
            sys.modules.pop(name)
    sys.path.insert(0, inserted)
    try:
        implementations: list[tuple[str, object]] = []
        with redirect_stdout(buffer), redirect_stderr(buffer):
            importlib.invalidate_caches()
            for descriptor in project.manifest.contributions:
                module_name, _, object_name = descriptor.implementation.partition(":")
                module = importlib.import_module(module_name)
                factory = getattr(module, object_name)
                implementations.append((descriptor.implementation, factory(descriptor)))
    except Exception as error:
        raise ConformanceError(
            ExtensionToolingErrorCode.ENTRYPOINT_INVALID,
            field="manifest.contributions.implementation",
            message="explicit Extension entrypoint could not be materialized",
        ) from error
    finally:
        if sys.path and sys.path[0] == inserted:
            sys.path.pop(0)
    if buffer.getvalue():
        reject(
            ExtensionToolingErrorCode.SOURCE_NONDETERMINISTIC,
            field="manifest.contributions.implementation",
            message="Extension import emitted output or diagnostic side effects",
        )
    return tuple(sorted(implementations))


def _venv_python(directory: Path) -> Path:
    if os.name == "nt":
        return directory / "Scripts/python.exe"
    return directory / "bin/python"


def _run_clean_install(
    project: EnterpriseExtensionProject,
    *,
    sdk_name: str,
    sdk_bytes: bytes,
    extension_name: str,
    extension_bytes: bytes,
) -> int:
    with TemporaryDirectory(prefix="aps-extension-clean-") as temporary:
        base = Path(temporary)
        wheels = base / "wheels"
        wheels.mkdir()
        sdk_path = wheels / sdk_name
        extension_path = wheels / extension_name
        sdk_path.write_bytes(sdk_bytes)
        extension_path.write_bytes(extension_bytes)
        environment_path = base / "venv"
        try:
            venv.EnvBuilder(with_pip=True, clear=True).create(environment_path)
            python = _venv_python(environment_path)
            environment = dict(os.environ)
            environment.pop("PYTHONPATH", None)
            environment.pop("PYTHONHOME", None)
            environment.update(
                {
                    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                    "PIP_NO_INDEX": "1",
                    "PYTHONNOUSERSITE": "1",
                }
            )
            install = subprocess.run(
                [
                    str(python),
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    str(sdk_path),
                    str(extension_path),
                ],
                cwd=base,
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if install.returncode != 0:
                reject(
                    ExtensionToolingErrorCode.CLEAN_INSTALL_FAILED,
                    field="clean_install",
                    message="locked SDK and Extension wheels did not install in a clean environment",
                )
            tests = subprocess.run(
                [
                    str(python),
                    "-I",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    str(project.tests_root),
                    "-p",
                    "test*.py",
                ],
                cwd=project.root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if tests.returncode != 0:
                reject(
                    ExtensionToolingErrorCode.PROJECT_TEST_FAILED,
                    field="tests_root",
                    message="standalone Extension tests failed in the clean environment",
                )
            match = re.search(r"Ran ([0-9]+) tests?", tests.stdout + tests.stderr)
            if match is None or int(match.group(1)) < 1:
                reject(
                    ExtensionToolingErrorCode.PROJECT_TEST_FAILED,
                    field="tests_root",
                    message="clean test discovery did not execute a test",
                )
            return int(match.group(1))
        except ConformanceError:
            raise
        except (OSError, subprocess.SubprocessError) as error:
            raise ConformanceError(
                ExtensionToolingErrorCode.CLEAN_INSTALL_FAILED,
                field="clean_install",
                message="clean environment could not be created or executed",
            ) from error


def _write_runtime_bundle(
    results: tuple[ConformanceResult, ...],
    directory: Path,
) -> Path:
    compatibility = _json(
        Path(__file__).resolve().parents[1]
        / "aps_extension_sdk/contracts/samples/extension-compatibility.v1.synthetic.json",
        field="compatibility",
    )
    entries: list[dict[str, Any]] = []
    for index, result in enumerate(
        sorted(results, key=lambda item: item.project.project_id)
    ):
        manifest_name = f"extension-{index:02d}-manifest.json"
        configuration_name = f"extension-{index:02d}-configuration.json"
        (directory / manifest_name).write_bytes(
            canonical_json_bytes(result.project.manifest_document) + b"\n"
        )
        (directory / configuration_name).write_bytes(
            canonical_json_bytes(result.configuration) + b"\n"
        )
        capabilities = sorted(
            {
                capability
                for contribution in result.project.manifest.contributions
                for capability in contribution.capabilities
            }
        )
        entry: dict[str, Any] = {
            "extension_id": result.project.project_id,
            "extension_version": "1.0.0",
            "manifest_path": manifest_name,
            "artifact_digest": digest_bytes(result.extension_wheel_bytes),
            "manifest_fingerprint": result.project.manifest.manifest_fingerprint,
            "configuration_path": configuration_name,
            "configuration_fingerprint": result.configuration[
                "configuration_fingerprint"
            ],
            "allowed_capabilities": capabilities,
            "signature_key_id": CONFORMANCE_KEY_ID,
            "signature": "",
        }
        entry["signature"] = runtime_extension_signature(
            entry, verification_key=_CONFORMANCE_KEY
        )
        entries.append(entry)
    catalog: dict[str, Any] = {
        "catalog_version": "aps-runtime-extension-catalog.v1",
        "runtime_version": RUNTIME_VERSION,
        "sdk_api_version": SDK_API_VERSION,
        "registry_protocol_version": "plugin-registry.v1",
        "compatibility": compatibility,
        "invocation_timeout_ms": 1_000,
        "startup_timeout_ms": 30_000,
        "extensions": entries,
        "catalog_fingerprint": "",
    }
    projection = dict(catalog)
    projection.pop("catalog_fingerprint")
    catalog["catalog_fingerprint"] = fingerprint_json(projection)
    catalog_path = directory / "runtime-extension-catalog.json"
    catalog_path.write_bytes(canonical_json_bytes(catalog) + b"\n")
    return catalog_path


def _exercise_adapter(
    adapter: LoadedRuntimeExtensionAdapter,
    fixture: Mapping[str, Any],
) -> dict[str, int]:
    common = {
        "scope": cast(Mapping[str, object], fixture["scope"]),
        "facts": cast(Mapping[str, object], fixture["facts"]),
        "provenance": cast(Mapping[str, object], fixture["provenance"]),
    }
    first_constraints = adapter.invoke_constraints(**common)
    second_constraints = adapter.invoke_constraints(**common)
    first_objectives = adapter.invoke_objectives(**common)
    second_objectives = adapter.invoke_objectives(**common)
    first_rules = adapter.invoke_planning_rules(**common)
    second_rules = adapter.invoke_planning_rules(**common)
    first_validations = adapter.invoke_validation_rules(**common)
    second_validations = adapter.invoke_validation_rules(**common)
    if (
        first_constraints != second_constraints
        or first_objectives != second_objectives
        or first_rules != second_rules
        or first_validations != second_validations
    ):
        reject(
            ExtensionToolingErrorCode.SOURCE_NONDETERMINISTIC,
            field="runtime_invocation",
            message="same frozen input produced different Extension output",
        )
    if not all(isinstance(item, ConstraintOutput) for item in first_constraints):
        reject(
            ExtensionToolingErrorCode.RUNTIME_LOAD_FAILED,
            field="constraints",
            message="Runtime Constraint adapter returned an invalid output",
        )
    if not all(
        isinstance(item, ObjectiveOutput)
        and item.stage is ObjectiveStage.ENTERPRISE_TIE_BREAK
        and isinstance(item.integer_value, int)
        and not isinstance(item.integer_value, bool)
        for item in first_objectives
    ):
        reject(
            ExtensionToolingErrorCode.RUNTIME_LOAD_FAILED,
            field="objectives",
            message="Runtime Objective adapter violated the enterprise tie-break contract",
        )
    if not all(isinstance(item, PlanningRuleOutput) for item in first_rules):
        reject(
            ExtensionToolingErrorCode.RUNTIME_LOAD_FAILED,
            field="planning_rules",
            message="Runtime Planning Rule adapter returned an invalid output",
        )
    if not all(
        isinstance(item, ValidationOutput) and item.passed for item in first_validations
    ):
        reject(
            ExtensionToolingErrorCode.VALIDATION_REJECTED,
            field="validation_rules",
            message="positive conformance fixture was rejected by an independent validator",
        )
    bindings = cast(Mapping[str, Any], fixture["replan_bindings"])
    replan = adapter.invoke_replan_policy(**common, **bindings)
    if replan is not None:
        if not isinstance(replan, ReplanDecision) or any(
            getattr(replan, field) != value for field, value in bindings.items()
        ):
            reject(
                ExtensionToolingErrorCode.RUNTIME_LOAD_FAILED,
                field="replan_policy",
                message="Replan Policy changed a protected Runtime binding",
            )
        second_replan = adapter.invoke_replan_policy(**common, **bindings)
        if replan != second_replan:
            reject(
                ExtensionToolingErrorCode.SOURCE_NONDETERMINISTIC,
                field="replan_policy",
                message="same frozen input produced a different Replan decision",
            )
    resolution = adapter.invoke_plugin_registry()
    if (
        not isinstance(resolution, RegistryResolution)
        or resolution != adapter.registry.resolution
    ):
        reject(
            ExtensionToolingErrorCode.RUNTIME_LOAD_FAILED,
            field="plugin_registry",
            message="Plugin Registry differs from Runtime authority",
        )
    if fixture["expect_validation_rejection"]:
        negative_common = dict(common)
        negative_common["facts"] = cast(
            Mapping[str, object], fixture["negative_validation_facts"]
        )
        negative_outputs = adapter.invoke_validation_rules(**negative_common)
        if not negative_outputs or all(output.passed for output in negative_outputs):
            reject(
                ExtensionToolingErrorCode.VALIDATION_REJECTED,
                field="negative_validation_facts",
                message="negative fixture was not independently rejected",
            )
    metrics = adapter.safe_metrics()
    if (
        metrics.get("payloads_recorded") is not False
        or metrics.get("exception_details_recorded") is not False
    ):
        reject(
            ExtensionToolingErrorCode.RUNTIME_LOAD_FAILED,
            field="metrics",
            message="Runtime metrics crossed the safe evidence boundary",
        )
    return {
        "constraint_count": len(first_constraints),
        "objective_count": len(first_objectives),
        "planning_rule_count": len(first_rules),
        "validation_rule_count": len(first_validations),
        "replan_policy_count": int(replan is not None),
        "plugin_registry_count": len(
            adapter.registry.for_point(ExtensionPoint.PLUGIN_REGISTRY)
        ),
    }


def conform_project(
    project_root: Path,
    *,
    repository_root: Path,
    output_directory: Path | None = None,
    clean_install: bool = True,
) -> ConformanceResult:
    """Validate, reproducibly package, clean-install, and Runtime-load one project."""

    sdk_name, sdk_bytes = sdk_wheel(repository_root)
    sdk_digest = digest_bytes(sdk_bytes)
    project, scan = load_project(
        project_root,
        repository_root=repository_root,
        expected_sdk_wheel_digest=sdk_digest,
    )
    configuration = _configuration(project)
    fixture = _fixture(project)
    first_name, first_bytes = extension_wheel(project)
    second_name, second_bytes = extension_wheel(project)
    if first_name != second_name or first_bytes != second_bytes:
        reject(
            ExtensionToolingErrorCode.BUILD_NONDETERMINISTIC,
            field="artifact",
            message="repeated Extension package builds differ",
        )
    artifact_digest = digest_bytes(first_bytes)
    if artifact_digest != project.manifest.artifact_digest:
        reject(
            ExtensionToolingErrorCode.MANIFEST_INVALID,
            field="artifact.digest",
            message="manifest digest differs from the reproducible Extension artifact",
        )
    implementations = _materialize(project)
    project_test_count = 0
    if clean_install:
        project_test_count = _run_clean_install(
            project,
            sdk_name=sdk_name,
            sdk_bytes=sdk_bytes,
            extension_name=first_name,
            extension_bytes=first_bytes,
        )
    report: dict[str, Any] = {
        "report_version": CONFORMANCE_REPORT_VERSION,
        "status": "PASS",
        "project_id": project.project_id,
        "distribution_name": project.distribution_name,
        "extension_version": "1.0.0",
        "sdk_api_version": SDK_API_VERSION,
        "sdk_wheel_digest": sdk_digest,
        "runtime_version": RUNTIME_VERSION,
        "developer_kit_version": DEVELOPER_KIT_VERSION,
        "artifact_digest": artifact_digest,
        "manifest_fingerprint": project.manifest.manifest_fingerprint,
        "dependency_lock_digest": project.dependency_lock_digest,
        "source_scan": scan.document,
        "contribution_count": len(project.manifest.contributions),
        "project_test_count": project_test_count,
        "checks": {
            "strict_project_metadata": True,
            "exact_sdk_and_runtime_lock": True,
            "owner_repository_and_license": True,
            "sdk_only_import_boundary": True,
            "no_core_copy": True,
            "independent_validation_module": True,
            "reproducible_extension_wheel": True,
            "clean_install_and_tests": clean_install,
        },
        "boundaries": {
            "core_modified": False,
            "runtime_loader_modified": False,
            "network_install": False,
            "git_repository_created": False,
            "trusted_in_process": True,
            "sandboxed": False,
            "production_readiness": "NOT_CLAIMED",
            "developer_kit_release": "NOT_IMPLEMENTED_UNTIL_P8_15",
        },
        "issues": [],
    }
    result = ConformanceResult(
        project=project,
        source_scan=scan,
        sdk_wheel_name=sdk_name,
        sdk_wheel_bytes=sdk_bytes,
        extension_wheel_name=first_name,
        extension_wheel_bytes=first_bytes,
        configuration=configuration,
        fixture=fixture,
        implementations=implementations,
        project_test_count=project_test_count,
        report=report,
    )
    with TemporaryDirectory(prefix="aps-extension-runtime-") as temporary:
        conform_extension_set((result,), runtime_directory=Path(temporary))
    if output_directory is not None:
        write_artifact(output_directory / sdk_name, sdk_bytes)
        write_artifact(output_directory / first_name, first_bytes)
        report_path = output_directory / f"{project.distribution_name}.conformance.json"
        write_artifact(report_path, canonical_json_bytes(report) + b"\n")
    return result


def conform_extension_set(
    results: tuple[ConformanceResult, ...],
    *,
    runtime_directory: Path,
) -> tuple[LoadedRuntimeExtensionAdapter, dict[str, Any]]:
    """Load an exact Extension set into Runtime and execute each frozen SPI twice."""

    if not results:
        reject(
            ExtensionToolingErrorCode.SET_CONFLICT,
            field="extensions",
            message="Extension set must not be empty",
        )
    ids = tuple(result.project.project_id for result in results)
    if len(ids) != len(set(ids)):
        reject(
            ExtensionToolingErrorCode.SET_CONFLICT,
            field="extensions.extension_id",
            message="Extension set contains a duplicate identity",
        )
    if runtime_directory.exists() and any(runtime_directory.iterdir()):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="runtime_directory",
            message="Runtime conformance directory must be absent or empty",
        )
    runtime_directory.mkdir(parents=True, exist_ok=True)
    try:
        catalog_path = _write_runtime_bundle(results, runtime_directory)
        adapter = load_runtime_extensions(
            catalog_path,
            artifacts=tuple(result.artifact for result in results),
            runtime_version=RUNTIME_VERSION,
            verification_key_id=CONFORMANCE_KEY_ID,
            verification_key=_CONFORMANCE_KEY,
        )
        counts = {
            result.project.project_id: _exercise_adapter(adapter, result.fixture)
            for result in sorted(results, key=lambda item: item.project.project_id)
        }
    except ConformanceError:
        raise
    except (ExtensionContractError, RuntimeExtensionError) as error:
        code = getattr(error, "code", ExtensionToolingErrorCode.RUNTIME_LOAD_FAILED)
        field = getattr(error, "field", "runtime_extension_set")
        raise ConformanceError(
            str(code),
            field=str(field),
            message="Extension set failed the locked Runtime conformance boundary",
        ) from error
    report: dict[str, Any] = {
        "report_version": CONFORMANCE_SET_REPORT_VERSION,
        "status": "PASS",
        "sdk_api_version": SDK_API_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "extension_ids": sorted(ids),
        "extension_count": len(results),
        "contribution_count": len(adapter.contributions),
        "extension_set_fingerprint": adapter.document["extension_set_fingerprint"],
        "invocation_counts": counts,
        "checks": {
            "runtime_load": True,
            "deterministic_registry": True,
            "explicit_materialized_entrypoints": True,
            "all_declared_spi_invoked": True,
            "independent_validation_rejection": True,
            "replan_bindings_preserved": True,
            "safe_metrics": True,
        },
        "issues": [],
    }
    return adapter, report


def _replace_tokens(root: Path, values: Mapping[str, str]) -> None:
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ConformanceError(
                ExtensionToolingErrorCode.PROJECT_INVALID,
                field="template",
                message="template contains a non-UTF-8 file",
            ) from error
        for token, value in values.items():
            text = text.replace(token, value)
        path.write_text(text, encoding="utf-8", newline="\n")


def scaffold_project(
    *,
    template_root: Path,
    output_root: Path,
    repository_root: Path,
    extension_id: str,
    distribution_name: str,
    package_name: str,
    owner: str,
    repository_url: str,
    license_expression: str,
    source_commit: str,
) -> Path:
    """Materialize one local project without creating Git or remote repository state."""

    if output_root.exists() and any(output_root.iterdir()):
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="output",
            message="scaffold output must be absent or empty",
        )
    output_root.mkdir(parents=True, exist_ok=True)
    base_values = {
        "__PROJECT_ID__": extension_id,
        "__EXTENSION_ID__": extension_id,
        "__DISTRIBUTION_NAME__": distribution_name,
        "__PACKAGE_NAME__": package_name,
        "__OWNER__": owner,
        "__REPOSITORY_URL__": repository_url,
        "__LICENSE_EXPRESSION__": license_expression,
        "__SOURCE_COMMIT__": source_commit,
    }
    sdk_name, sdk_bytes = sdk_wheel(repository_root)
    del sdk_name
    base_values["__SDK_WHEEL_SHA256__"] = digest_bytes(sdk_bytes).removeprefix(
        "sha256:"
    )
    template_files = sorted(
        candidate
        for candidate in template_root.rglob("*")
        if candidate.is_file()
        and "__pycache__" not in candidate.parts
        and candidate.suffix != ".pyc"
    )
    for source in template_files:
        if source.is_symlink():
            reject(
                ExtensionToolingErrorCode.PROJECT_INVALID,
                field="template",
                message="template symbolic links are forbidden",
            )
        relative_text = source.relative_to(template_root).as_posix()
        for token, value in base_values.items():
            relative_text = relative_text.replace(token, value)
        destination = output_root.joinpath(*Path(relative_text).parts)
        if not destination.resolve().is_relative_to(output_root.resolve()):
            reject(
                ExtensionToolingErrorCode.PROJECT_INVALID,
                field="template",
                message="rendered template path escapes the output root",
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8")
        for token, value in base_values.items():
            text = text.replace(token, value)
        destination.write_text(text, encoding="utf-8", newline="\n")
    schema_path = output_root / "extension/configuration-contract.v1.json"
    lock_path = output_root / "requirements.lock"
    _replace_tokens(
        output_root,
        {
            "__CONFIG_SCHEMA_DIGEST__": digest_bytes(schema_path.read_bytes()),
            "__DEPENDENCY_LOCK_DIGEST__": digest_bytes(lock_path.read_bytes()),
        },
    )
    configuration_path = output_root / "extension/extension-configuration.json"
    configuration = _json(configuration_path, field="configuration")
    configuration.pop("configuration_fingerprint")
    _replace_tokens(
        output_root,
        {"__CONFIG_FINGERPRINT__": fingerprint_json(configuration)},
    )
    _, wheel_bytes = extension_wheel_for_source(
        distribution_name=distribution_name,
        package_name=package_name,
        owner=owner,
        repository_url=repository_url,
        license_expression=license_expression,
        source_root=output_root / "src",
    )
    _replace_tokens(
        output_root,
        {"__ARTIFACT_DIGEST__": digest_bytes(wheel_bytes)},
    )
    manifest_path = output_root / "extension/extension-manifest.json"
    manifest = _json(manifest_path, field="manifest")
    manifest.pop("manifest_fingerprint")
    _replace_tokens(
        output_root,
        {"__MANIFEST_FINGERPRINT__": fingerprint_json(manifest)},
    )
    fixture_path = output_root / "conformance/fixture.v1.json"
    fixture = _json(fixture_path, field="fixture")
    fixture.pop("fixture_fingerprint")
    _replace_tokens(
        output_root,
        {"__FIXTURE_FINGERPRINT__": fingerprint_json(fixture)},
    )
    unresolved = [
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file() and _UNRESOLVED_TOKEN.search(path.read_text(encoding="utf-8"))
    ]
    if unresolved:
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="template",
            message="rendered project contains unresolved template tokens",
        )
    if (output_root / ".git").exists():
        reject(
            ExtensionToolingErrorCode.PROJECT_INVALID,
            field="output",
            message="scaffolding must not create a Git repository",
        )
    load_project(
        output_root,
        repository_root=repository_root,
        expected_sdk_wheel_digest=digest_bytes(sdk_bytes),
    )
    return output_root


__all__ = [
    "CONFORMANCE_FIXTURE_VERSION",
    "CONFORMANCE_REPORT_VERSION",
    "CONFORMANCE_SET_REPORT_VERSION",
    "ConformanceResult",
    "conform_extension_set",
    "conform_project",
    "scaffold_project",
]
