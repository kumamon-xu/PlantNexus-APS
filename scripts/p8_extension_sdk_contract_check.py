"""Deterministic TASK-P8-12 Extension SDK contract evidence runner."""

from __future__ import annotations

import argparse
import ast
import copy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator

from aps_extension_sdk import (
    ERROR_NAMESPACE,
    ERROR_REGISTRY_VERSION,
    EXTENSION_COMPATIBILITY_VERSION,
    EXTENSION_MANIFEST_VERSION,
    PROTOCOLS_BY_POINT,
    REGISTRY_PROTOCOL_VERSION,
    SDK_API_VERSION,
    CompatibilityPolicy,
    ExtensionContractError,
    ExtensionErrorCode,
    ExtensionInputView,
    ExtensionPoint,
    FrozenJsonObject,
    ObjectiveOutput,
    ObjectiveSense,
    ObjectiveStage,
    ReplanAction,
    ReplanContext,
    ReplanDecision,
    fingerprint_json,
    freeze_json,
    parse_compatibility_policy,
    parse_extension_manifest,
    resolve_manifest_set,
    validate_protocol_output,
)


TASK_ID = "TASK-P8-12"
TEST_ID = "TEST-P8-EXTENSION-CONTRACT-001"
DIFF_BASE = "475e46e6e7e140600b0302a21d594443f91d7853"
EVIDENCE_SHA = "4d37dba068c86230f6009820d6cbc7ff10a73495"
REPORT_VERSION = "p8-extension-sdk-contract-report.v1"
CONTRACT_ROOT = Path("backend/aps_extension_sdk/contracts")
SAMPLE_ROOT = CONTRACT_ROOT / "samples"
MANIFEST_SCHEMA = CONTRACT_ROOT / "extension-manifest.v1.schema.json"
COMPATIBILITY_SCHEMA = CONTRACT_ROOT / "extension-compatibility.v1.schema.json"
ERROR_REGISTRY = CONTRACT_ROOT / "extension-error-code-registry.v1.json"
POSITIVE_MANIFEST = SAMPLE_ROOT / "extension-manifest.v1.synthetic.json"
POSITIVE_COMPATIBILITY = SAMPLE_ROOT / "extension-compatibility.v1.synthetic.json"
NEGATIVE_VECTORS = SAMPLE_ROOT / "extension-contract-negative-vectors.v1.json"

HISTORICAL_MANIFESTS = {
    "schemas": (117, "sha256:5a746ca79ae5a630dc3104da0cdb6c23fdf6589a2af8de7047782232e3fae3bb"),
    "core": (82, "sha256:916da1fd7a6322c7a94050122f36cd92bc002faa36b036dfe58adf7fc3138d21"),
    "api": (19, "sha256:4aa922d9ca2068e5fb805657ec3dadb81e5b025add282d5ad343644fb0e0bd62"),
    "migrations": (12, "sha256:d756e0ff39f3a8489548d597bed865772a5141a6846ed286ebc3e01073e6f961"),
    "runtime_seam": (4, "sha256:058bd86c7ae797066023ff729db3ac3fdb6c4afc1c7c46f0fe9036c7330ea1f6"),
    "dependency": (2, "sha256:4c6c245d5a2638efba0c37925798ebc312a9b7e8a2a70249ddb87961b701d562"),
}

ALLOWED_EXACT_PATHS = {
    ".github/workflows/ci.yml",
    "backend/aps_extension_sdk/__init__.py",
    "backend/aps_extension_sdk/errors.py",
    "backend/aps_extension_sdk/manifest.py",
    "backend/aps_extension_sdk/protocols.py",
    "backend/aps_extension_sdk/values.py",
    "backend/tests/contract/test_p8_extension_sdk_contract.py",
    "backend/tests/integration/test_ci_contract.py",
    "backend/tests/property/test_p8_extension_sdk_properties.py",
    "backend/tests/security/test_p8_extension_sdk_security.py",
    "backend/tests/unit/test_p8_extension_sdk.py",
    "backend/tests/validation/test_p8_extension_sdk_mutations.py",
    "docs/architecture/extension-sdk-runtime-and-developer-kit.md",
    "docs/architecture/module-boundaries.md",
    "docs/architecture/provenance-and-versioning.md",
    "docs/contracts/README.md",
    "docs/contracts/extension-sdk-and-developer-kit.md",
    "docs/contracts/schema-versioning.md",
    "docs/planning/schedule-validator.md",
    "scripts/p8_extension_sdk_contract_check.py",
    "tests/p6/p6_exit_gate_audit.py",
}
ALLOWED_PREFIXES = ("backend/aps_extension_sdk/contracts/",)
FORBIDDEN_PREFIXES = (
    "backend/app/",
    "backend/migrations/",
    "demo/",
    "frontend/",
    "schemas/",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.as_posix()} must contain one JSON object")
    return value


def _manifest_digest(root: Path, paths: list[Path]) -> tuple[int, str]:
    rows: list[str] = []
    for path in sorted(set(paths), key=lambda item: item.as_posix()):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            relative = path.relative_to(root).as_posix()
            rows.append(f"{relative}\0{sha256(path.read_bytes()).hexdigest()}\n")
    return len(rows), f"sha256:{sha256(''.join(rows).encode()).hexdigest()}"


def _git_tree_paths(root: Path, *pathspecs: str) -> list[str]:
    output = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", EVIDENCE_SHA, "--", *pathspecs],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    return [
        path.replace("\\", "/")
        for path in output.splitlines()
        if path
        and "__pycache__" not in Path(path).parts
        and not path.endswith(".pyc")
    ]


def _historical_tree_paths(root: Path) -> dict[str, list[str]]:
    core = _git_tree_paths(
        root,
        "backend/app/domain",
        "backend/app/planning",
        "backend/app/snapshots",
    )
    return {
        "schemas": _git_tree_paths(root, "schemas"),
        "core": [path for path in core if path.endswith(".py")],
        "api": _git_tree_paths(root, "backend/app/api"),
        "migrations": _git_tree_paths(root, "backend/migrations"),
        "runtime_seam": [
            "backend/app/runtime_composition.py",
            "backend/app/application/runtime_facade.py",
            "backend/app/application/runtime_http_adapter.py",
            "backend/app/jobs/runtime_adapters.py",
        ],
        "dependency": ["pyproject.toml", "uv.lock"],
    }


def _historical_manifest_digest(root: Path, paths: list[str]) -> tuple[int, str]:
    rows: list[str] = []
    for relative in sorted(set(paths)):
        content = subprocess.run(
            ["git", "show", f"{EVIDENCE_SHA}:{relative}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        rows.append(f"{relative}\0{sha256(content).hexdigest()}\n")
    return len(rows), f"sha256:{sha256(''.join(rows).encode()).hexdigest()}"


def _changed_paths(root: Path) -> tuple[str, ...]:
    committed = subprocess.run(
        ["git", "diff", "--name-only", f"{DIFF_BASE}...{EVIDENCE_SHA}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return tuple(
        sorted({path.replace("\\", "/") for path in committed if path})
    )


def _schema_and_positive_samples(root: Path) -> dict[str, object]:
    manifest_schema = _load_json(root / MANIFEST_SCHEMA)
    compatibility_schema = _load_json(root / COMPATIBILITY_SCHEMA)
    Draft202012Validator.check_schema(manifest_schema)
    Draft202012Validator.check_schema(compatibility_schema)
    manifest_document = _load_json(root / POSITIVE_MANIFEST)
    compatibility_document = _load_json(root / POSITIVE_COMPATIBILITY)
    Draft202012Validator(manifest_schema).validate(manifest_document)
    Draft202012Validator(compatibility_schema).validate(compatibility_document)
    manifest = parse_extension_manifest(manifest_document)
    policy = parse_compatibility_policy(compatibility_document)
    resolution = resolve_manifest_set((manifest,), policy)
    if set(item.extension_point for item in manifest.contributions) != set(ExtensionPoint):
        raise ValueError("positive manifest does not cover all six extension points")
    return {
        "extension_id": manifest.extension_id,
        "contribution_count": len(manifest.contributions),
        "compatibility_version": policy.compatibility_version,
        "resolution_fingerprint": resolution.resolution_fingerprint,
        "manifest_schema_id": manifest_schema["$id"],
        "compatibility_schema_id": compatibility_schema["$id"],
    }


def _apply_vector(base: dict[str, Any], vector: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    operation = vector["operation"]
    mutated = copy.deepcopy(base)
    if operation == "DUPLICATE_CONTRIBUTION":
        target = next(
            item for item in mutated["contributions"] if item["contribution_id"] == vector["target"]
        )
        mutated["contributions"].append(copy.deepcopy(target))
        mutated["contributions"].sort(
            key=lambda item: (item["order"], item["contribution_id"])
        )
        return (mutated,)
    if operation == "REPLACE_OBJECTIVE_STAGE":
        target = next(
            item for item in mutated["contributions"] if item["contribution_id"] == vector["target"]
        )
        target["objective_stage"] = vector["value"]
        return (mutated,)
    if operation == "REPLACE_VALIDATION_PAIR":
        target = next(
            item for item in mutated["contributions"] if item["contribution_id"] == vector["target"]
        )
        target["validation_rule_ids"] = [vector["value"]]
        return (mutated,)
    if operation == "MIX_MANIFEST_SET_SDK_VERSION":
        second = copy.deepcopy(base)
        second["sdk_api_version"] = vector["value"]
        second["extension_id"] = "com.example.second_extension"
        second.pop("manifest_fingerprint")
        second["manifest_fingerprint"] = fingerprint_json(second)
        return (base, second)
    raise ValueError(f"unknown negative vector operation: {operation}")


def _negative_samples(
    root: Path,
    policy: CompatibilityPolicy,
) -> dict[str, object]:
    base = _load_json(root / POSITIVE_MANIFEST)
    document = _load_json(root / NEGATIVE_VECTORS)
    if set(document) != {"negative_vector_version", "base_manifest", "vectors"}:
        raise ValueError("negative vector carrier has unknown fields")
    if document["negative_vector_version"] != "extension-contract-negative-vectors.v1":
        raise ValueError("negative vector version is unsupported")
    if document["base_manifest"] != POSITIVE_MANIFEST.name:
        raise ValueError("negative vector base sample is not exact")
    observed: dict[str, str] = {}
    for item in document["vectors"]:
        vector = dict(item)
        if set(vector) != {"vector_id", "operation", "target", "value", "expected_code"}:
            raise ValueError("negative vector has unknown fields")
        try:
            mutated = _apply_vector(base, vector)
            manifests = tuple(parse_extension_manifest(value) for value in mutated)
            if len(manifests) > 1:
                resolve_manifest_set(manifests, policy)
        except ExtensionContractError as error:
            observed[vector["vector_id"]] = error.code.value
        else:
            raise ValueError(f"negative vector unexpectedly passed: {vector['vector_id']}")
        if observed[vector["vector_id"]] != vector["expected_code"]:
            raise ValueError(f"negative vector returned wrong code: {vector['vector_id']}")
    return {"count": len(observed), "codes": sorted(observed.values())}


def _error_registry(root: Path) -> dict[str, object]:
    registry = _load_json(root / ERROR_REGISTRY)
    if set(registry) != {"registry_version", "namespace", "codes"}:
        raise ValueError("extension error registry has unknown fields")
    if registry["registry_version"] != ERROR_REGISTRY_VERSION:
        raise ValueError("extension error registry version mismatch")
    if registry["namespace"] != ERROR_NAMESPACE:
        raise ValueError("extension error registry namespace mismatch")
    rows = registry["codes"]
    if not isinstance(rows, list) or any(
        set(row) != {"code", "category", "retryable"} or row["retryable"] is not False
        for row in rows
    ):
        raise ValueError("extension error registry row is not strict")
    codes = [row["code"] for row in rows]
    expected = sorted(code.value for code in ExtensionErrorCode)
    if codes != expected:
        raise ValueError("extension error registry differs from the Python error enum")
    return {"registry_version": registry["registry_version"], "code_count": len(codes)}


def _protocol_and_immutability(root: Path) -> dict[str, object]:
    if set(PROTOCOLS_BY_POINT) != set(ExtensionPoint):
        raise ValueError("public protocol map does not contain exactly six extension points")
    source = {"nested": {"items": [1, 2]}, "name": "sample"}
    frozen = freeze_json(source)
    if not isinstance(frozen, FrozenJsonObject):
        raise ValueError("freeze_json did not return a FrozenJsonObject")
    source["nested"]["items"].append(3)
    frozen_nested = frozen["nested"]
    if not isinstance(frozen_nested, FrozenJsonObject):
        raise ValueError("nested immutable value is not an object")
    if frozen_nested["items"] != (1, 2):
        raise ValueError("immutable view retained a mutable caller reference")
    input_view = ExtensionInputView.from_json(
        view_contract_version="extension-input.v1",
        extension_id="com.example.manufacturing",
        contribution_id="com.example.disruption.replan",
        input_fingerprint="sha256:" + "a" * 64,
        scope={"factory_id": "factory-001"},
        facts={"candidate_id": "candidate-001"},
        provenance={"problem": "sha256:" + "b" * 64},
    )
    try:
        input_view.extension_id = "com.example.changed"  # type: ignore[misc]
    except FrozenInstanceError:
        pass
    else:
        raise ValueError("frozen SDK input could be reassigned")
    objective = ObjectiveOutput(
        contribution_id="com.example.cost.objective",
        metric_id="com.example.cost.metric",
        stage=ObjectiveStage.ENTERPRISE_TIE_BREAK,
        sense=ObjectiveSense.MINIMIZE,
        integer_value=42,
        integer_scale=100,
        authority_reference="com.example.cost.authority.v1",
        evidence=freeze_json({"amount_minor": 42}),  # type: ignore[arg-type]
    )
    replan_context = ReplanContext(
        input_view=input_view,
        execution_fact_fingerprint="sha256:" + "c" * 64,
        hard_lock_fingerprint="sha256:" + "d" * 64,
        freeze_window_fingerprint="sha256:" + "e" * 64,
        state_machine_version="state-machines.v1",
        publication_authority_reference="com.example.publication.authority.v1",
    )
    decision = ReplanDecision(
        contribution_id="com.example.disruption.replan",
        action=ReplanAction.REQUEST_REPLAN,
        reason_code="com.example.machine_down",
        trigger_references=("event-001",),
        execution_fact_fingerprint=replan_context.execution_fact_fingerprint,
        hard_lock_fingerprint=replan_context.hard_lock_fingerprint,
        freeze_window_fingerprint=replan_context.freeze_window_fingerprint,
        state_machine_version=replan_context.state_machine_version,
        publication_authority_reference=(
            replan_context.publication_authority_reference
        ),
    )
    manifest = parse_extension_manifest(_load_json(root / POSITIVE_MANIFEST))
    replan_descriptor = next(
        item
        for item in manifest.contributions
        if item.extension_point is ExtensionPoint.REPLAN_POLICY
    )
    validate_protocol_output(replan_descriptor, replan_context, decision)
    return {
        "protocol_count": len(PROTOCOLS_BY_POINT),
        "objective_value": objective.integer_value,
        "objective_stage": objective.stage.value,
        "replan_action": decision.action.value,
        "privileged_service_count": 0,
    }


def _import_boundary(root: Path) -> dict[str, object]:
    package = root / "backend/aps_extension_sdk"
    forbidden_import_roots = {
        "app",
        "backend",
        "celery",
        "fastapi",
        "importlib",
        "ortools",
        "psycopg",
        "redis",
        "sqlalchemy",
    }
    forbidden_calls = {"__import__", "eval", "exec", "open"}
    scanned = 0
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        scanned += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", 1)[0] for alias in node.names}
                if roots & forbidden_import_roots:
                    raise ValueError(f"forbidden SDK import in {path.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".", 1)[0] in forbidden_import_roots:
                    raise ValueError(f"forbidden SDK import in {path.name}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in forbidden_calls
            ):
                raise ValueError(f"forbidden dynamic or filesystem call in {path.name}")
    return {"python_files": scanned, "forbidden_imports": 0, "forbidden_calls": 0}


def _scope_and_history(root: Path) -> dict[str, object]:
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EVIDENCE_SHA, "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if ancestry.returncode != 0:
        raise ValueError("closed P8-12 evidence SHA is not an ancestor of HEAD")
    changed = _changed_paths(root)
    unexpected = [
        path
        for path in changed
        if path not in ALLOWED_EXACT_PATHS
        and not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)
    ]
    forbidden = [path for path in changed if path.startswith(FORBIDDEN_PREFIXES)]
    if unexpected or forbidden:
        raise ValueError(f"scope violation: unexpected={unexpected} forbidden={forbidden}")
    observed: dict[str, dict[str, object]] = {}
    for name, paths in _historical_tree_paths(root).items():
        count, digest = _historical_manifest_digest(root, paths)
        expected_count, expected_digest = HISTORICAL_MANIFESTS[name]
        if (count, digest) != (expected_count, expected_digest):
            raise ValueError(f"historical {name} bytes drifted")
        observed[name] = {"file_count": count, "manifest_sha256": digest}
    return {
        "changed_path_count": len(changed),
        "forbidden_path_count": len(forbidden),
        "evidence_sha": EVIDENCE_SHA,
        "historical_manifests": observed,
    }


def _package_contract_manifest(root: Path) -> dict[str, object]:
    paths = [
        *list((root / "backend/aps_extension_sdk").glob("*.py")),
        *list((root / CONTRACT_ROOT).rglob("*.json")),
    ]
    count, digest = _manifest_digest(root, paths)
    return {"artifact_count": count, "manifest_sha256": digest}


def run_contract_checks(root: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    issues: list[dict[str, str]] = []

    def run(check_id: str, operation: Any) -> object | None:
        try:
            evidence = operation()
        except Exception as error:  # report must survive direct negative failures
            checks.append({"check_id": check_id, "passed": False})
            issues.append({"check_id": check_id, "message": str(error)})
            return None
        checks.append({"check_id": check_id, "passed": True, "evidence": evidence})
        return evidence

    positive = run("schema-positive-and-resolution", lambda: _schema_and_positive_samples(root))
    policy = (
        parse_compatibility_policy(_load_json(root / POSITIVE_COMPATIBILITY))
        if isinstance(positive, dict)
        else None
    )
    run(
        "strict-negative-vectors",
        lambda: _negative_samples(root, policy)
        if isinstance(policy, CompatibilityPolicy)
        else (_ for _ in ()).throw(ValueError("positive compatibility policy unavailable")),
    )
    run("stable-error-registry", lambda: _error_registry(root))
    run("six-spi-and-immutable-values", lambda: _protocol_and_immutability(root))
    run("closed-import-boundary", lambda: _import_boundary(root))
    run("forbidden-scope-and-historical-bytes", lambda: _scope_and_history(root))
    run("sdk-contract-artifact-manifest", lambda: _package_contract_manifest(root))

    git_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    commit = (
        "uncommitted"
        if git_status
        else subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    result = "PASS" if not issues else "FAIL"
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "evidence_sha": EVIDENCE_SHA,
        "code_commit": commit,
        "validation_profile": "HIGH_RISK",
        "sdk_api_version": SDK_API_VERSION,
        "extension_manifest_version": EXTENSION_MANIFEST_VERSION,
        "extension_compatibility_version": EXTENSION_COMPATIBILITY_VERSION,
        "registry_protocol_version": REGISTRY_PROTOCOL_VERSION,
        "checks": checks,
        "check_count": len(checks),
        "boundaries": {
            "runtime_loader": "NOT_IMPLEMENTED_UNTIL_P8_13",
            "enterprise_extension_template": "NOT_IMPLEMENTED_UNTIL_P8_14",
            "developer_kit": "NOT_IMPLEMENTED_UNTIL_P8_15",
            "core_semantics": "PRESERVED",
            "external_http_api": "UNCHANGED",
            "migration": "NONE",
            "production_authority": "NOT_CLAIMED",
            "demo": "EXCLUDED",
        },
        "issues": issues,
        "status": result,
        "result": result,
    }


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    report_path = args.report if args.report.is_absolute() else root / args.report
    report = run_contract_checks(root)
    write_report(report_path, report)
    issues = report["issues"]
    if not isinstance(issues, list):
        raise TypeError("machine report issues must be a list")
    print(
        f"{report['result']} P8 Extension SDK contract: "
        f"checks={report['check_count']} issues={len(issues)}"
    )
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
