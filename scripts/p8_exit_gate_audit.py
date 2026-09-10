"""Build the independent TASK-P8-17 P8 Exit Gate audit evidence.

The auditor deliberately owns no product implementation.  It validates a
sanitized predecessor-provider observation, replays the frozen P8-19 platform
procedure on fresh current-SHA inputs, checks the public product boundaries,
and emits a strict binary READY/NOT_READY report plus compact manifest.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from time import perf_counter
from typing import Any, Never, cast
from zipfile import BadZipFile, ZipFile

from scripts.p8_headless_extension_platform_requalification_gate import (
    PROFILE_FINGERPRINT,
    run_gate as run_p8_requalification_gate,
    validate_requalification_report,
)


type JsonObject = dict[str, Any]

REPORT_VERSION = "p8-exit-gate-audit-report.v1"
MANIFEST_VERSION = "p8-exit-gate-evidence-manifest.v1"
OBSERVATION_VERSION = "p8-exit-provider-observation.v1"
TASK_ID = "TASK-P8-17"
TEST_ID = "TEST-P8-EXIT-GATE-001"
DIFF_BASE = "2438870a928b5b5cf79aa9a1b9c528c102c36c31"
VALIDATION_PROFILE = "PHASE_GATE"
ACTIVATION_CUTOFF = "2026-09-10T00:00:00+00:00"
REQUIRED_APP_ID = 15368
OBSERVATION_FINGERPRINT = (
    "sha256:fe7c76fd8ba13d1a267f3e62e0cf44b66ae098814e90089961bf254078565b8e"
)

IMPACT_RULES = (
    "IMPACT-DOCS",
    "IMPACT-INFRA",
    "IMPACT-P8-EXIT-GATE-CHECKER",
    "IMPACT-REPOSITORY-HYGIENE",
    "IMPACT-TESTS",
)

EXPECTED_CHECK_IDS = (
    "p8-task-topology-and-exact-lineage",
    "predecessor-provider-manifests-and-required-checks",
    "provider-artifact-expiry-digest-and-json-semantics",
    "retained-failure-and-corrective-history",
    "accepted-adrs-and-contract-boundary",
    "canonical-json-only-and-no-third-party-connectors",
    "durable-ingress-problem-run-and-publication-lineage",
    "api-worker-separation-and-fresh-formal-validator",
    "identity-scope-authorization-and-audit",
    "runtime-release-sbom-license-and-migration-replay",
    "deployment-observability-backup-restore-and-runbooks",
    "backend-only-and-optional-frontend-isolation",
    "extension-sdk-and-deterministic-plugin-registry",
    "core-has-no-enterprise-reverse-dependency",
    "independent-extension-validation-and-fail-closed-negatives",
    "two-independent-enterprise-extension-conformance-paths",
    "immutable-developer-kit-old-kit-replay-and-no-auto-upgrade",
    "fresh-p8-19-platform-requalification-replay",
    "open-sim-risk-inventory-and-traceability-carry-forward",
    "audit-scope-and-p7-production-boundary",
)

_INPUT_REPORTS = (
    "runtime_release",
    "runtime_security",
    "runtime_migration",
    "formal_validator",
    "validator_mutations",
    "frontend_distribution",
    "frontend_client",
    "frontend_security",
    "frontend_backend_only",
    "operations_deployment",
    "operations_observability",
    "operations_recovery",
    "operations_runbooks",
    "corrective",
    "corrective_invocation",
    "corrective_kit",
    "corrective_output",
    "corrective_deployment",
    "corrective_security",
    "corrective_benchmark",
)

_ALLOWED_TRACKED_PATHS = frozenset(
    {
        ".gitignore",
        ".github/workflows/ci.yml",
        "backend/tests/integration/test_ci_contract.py",
        "docs/.gitignore",
        "docs/README.md",
        "docs/architecture/configuration-environments-and-isolation.md",
        "docs/architecture/extension-sdk-runtime-and-developer-kit.md",
        "docs/architecture/headless-productization-and-platform-integration.md",
        "docs/contracts/extension-sdk-and-developer-kit.md",
        "docs/contracts/headless-platform-integration.md",
        "docs/operations/deployment.md",
        "docs/operations/developer-kit-release-upgrade-and-rollback.md",
        "docs/p8-exit-gate-audit-observations.v1.json",
        "scripts/p8_exit_gate_audit.py",
        "tests/p6/p6_exit_gate_audit.py",
        "tests/p8/test_p8_exit_gate_audit.py",
        "tests/p8/test_p8_exit_gate_audit_rejections.py",
    }
)

_BOUNDARIES: Mapping[str, object] = {
    "p8_engineering_productization_ready": True,
    "canonical_json_only": True,
    "runtime_internal_extensions_only": True,
    "core_fork_or_copy_allowed": False,
    "automatic_enterprise_upgrade": False,
    "real_data_validated": False,
    "p7_reality_calibration_complete": False,
    "production_ready": False,
    "uat_complete": False,
    "capacity_or_sla_established": False,
    "third_party_connector_in_scope": False,
    "demo_included": False,
    "external_signature_required_for_internal_delivery": False,
}

_EXPECTED_DAG_EDGES = (
    ("TASK-P8-00", "TASK-P8-01"),
    ("TASK-P8-01", "TASK-P8-02"),
    ("TASK-P8-02", "TASK-P8-03"),
    ("TASK-P8-03", "TASK-P8-04"),
    ("TASK-P8-04", "TASK-P8-05"),
    ("TASK-P8-03", "TASK-P8-06"),
    ("TASK-P8-04", "TASK-P8-06"),
    ("TASK-P8-05", "TASK-P8-06"),
    ("TASK-P8-06", "TASK-P8-07"),
    ("TASK-P8-01", "TASK-P8-08"),
    ("TASK-P8-02", "TASK-P8-08"),
    ("TASK-P8-07", "TASK-P8-08"),
    ("TASK-P8-07", "TASK-P8-09"),
    ("TASK-P8-08", "TASK-P8-09"),
    ("TASK-P8-09", "TASK-P8-10"),
    ("TASK-P8-07", "TASK-P8-11"),
    ("TASK-P8-01", "TASK-P8-12"),
    ("TASK-P8-02", "TASK-P8-12"),
    ("TASK-P8-06", "TASK-P8-13"),
    ("TASK-P8-12", "TASK-P8-13"),
    ("TASK-P8-13", "TASK-P8-14"),
    ("TASK-P8-09", "TASK-P8-15"),
    ("TASK-P8-13", "TASK-P8-15"),
    ("TASK-P8-14", "TASK-P8-15"),
    ("TASK-P8-05", "TASK-P8-16"),
    ("TASK-P8-07", "TASK-P8-16"),
    ("TASK-P8-08", "TASK-P8-16"),
    ("TASK-P8-09", "TASK-P8-16"),
    ("TASK-P8-10", "TASK-P8-16"),
    ("TASK-P8-11", "TASK-P8-16"),
    ("TASK-P8-15", "TASK-P8-16"),
    ("TASK-P8-16", "TASK-P8-18"),
    ("TASK-P8-18", "TASK-P8-19"),
    ("TASK-P8-19", "TASK-P8-17"),
)


@dataclass(frozen=True)
class ProviderInputSpec:
    key: str
    task_id: str
    evidence_kind: str
    source_path: str
    implementation_sha: str
    run_id: int
    required_job_id: int
    task_profile: str
    workflow_profile: str
    artifact_count: int
    gate_verdict: str | None = None


_PROVIDER_INPUTS = (
    ProviderInputSpec(
        "p8-00-implementation",
        "TASK-P8-00",
        "implementation",
        "build/provider/P8-00-exact-provider-manifest.json",
        "3916e35922838dfd0e55c7aeebe914ccecc0dfa9",
        33858563951,
        100977561619,
        "DOCS_ONLY",
        "DOCS_ONLY",
        2,
    ),
    ProviderInputSpec(
        "p8-01-implementation",
        "TASK-P8-01",
        "implementation",
        "build/provider/P8-01-exact-provider-manifest.json",
        "43ff13429b2bb79854f976c0a1f5a72b1b069607",
        33860531213,
        100983788899,
        "DOCS_ONLY",
        "DOCS_ONLY",
        2,
    ),
    ProviderInputSpec(
        "p8-02-implementation",
        "TASK-P8-02",
        "implementation",
        "build/provider/P8-02-exact-provider-manifest.json",
        "c9efc2e8d35e29c139b9c819368047625f31724c",
        33876276068,
        101035958351,
        "HIGH_RISK",
        "FULL",
        4,
    ),
    ProviderInputSpec(
        "p8-03-implementation",
        "TASK-P8-03",
        "corrective_implementation",
        "build/provider/P8-03-exact-provider-manifest.json",
        "cc846fbb34f5b22bcec027f7c7cb55e1ab8027a3",
        33901523581,
        101119346329,
        "HIGH_RISK",
        "FULL",
        4,
    ),
    ProviderInputSpec(
        "p8-03-closure",
        "TASK-P8-03",
        "closure",
        "build/provider/P8-03-closure-exact-provider-manifest.json",
        "29000eeaf73fb1306f1bcb6f7cb7ab761283d682",
        33903442112,
        101122774253,
        "DOCS_ONLY",
        "DOCS_ONLY",
        2,
    ),
    ProviderInputSpec(
        "p8-04-implementation",
        "TASK-P8-04",
        "implementation",
        "build/provider/P8-04-exact-provider-manifest.json",
        "f8c962188295c6e9d3852cc8bb8708caf3203adc",
        33942941111,
        101244735504,
        "HIGH_RISK",
        "FULL",
        4,
    ),
    ProviderInputSpec(
        "p8-05-implementation",
        "TASK-P8-05",
        "implementation",
        "build/provider-audit/P8-05-implementation-provider/provider-evidence-manifest.json",
        "c69fbe3b21e0e782a293675b523c41f31898d0da",
        33951471792,
        101268372489,
        "HIGH_RISK",
        "FULL",
        4,
    ),
    ProviderInputSpec(
        "p8-06-implementation",
        "TASK-P8-06",
        "implementation",
        "build/provider-audit/P8-06-implementation-provider/provider-evidence-manifest.json",
        "3a4fa8e972e35fea6464031ac1a6e89027eeec5e",
        33958321784,
        101286548369,
        "HIGH_RISK",
        "FULL",
        4,
    ),
    ProviderInputSpec(
        "p8-07-implementation",
        "TASK-P8-07",
        "implementation",
        "build/provider-audit/P8-07-implementation-provider/provider-evidence-manifest.json",
        "54be7af6efdb78f751b8aa4a66bc080bdd04407f",
        34009912309,
        101424801432,
        "HIGH_RISK",
        "FULL",
        4,
    ),
    ProviderInputSpec(
        "p8-08-corrective",
        "TASK-P8-08",
        "corrective_implementation",
        "build/provider-audit/P8-08-implementation-provider/provider-evidence-manifest.json",
        "3595f6f7b1ae4a70f68bb3512f3db4bd024dc8a5",
        34018123165,
        101446809915,
        "HIGH_RISK",
        "FULL",
        4,
    ),
    ProviderInputSpec(
        "p8-09-implementation",
        "TASK-P8-09",
        "implementation",
        "build/validation/P8-09-provider-evidence-manifest.json",
        "3af39dbc97128634af729d6cb744b95b96cec18f",
        34080998300,
        101617450539,
        "HIGH_RISK",
        "FULL",
        4,
    ),
    ProviderInputSpec(
        "p8-10-implementation",
        "TASK-P8-10",
        "implementation",
        "build/validation/P8-10-provider-evidence-manifest.json",
        "491a5decab217001d4be06f06be9645ef2911269",
        34091144691,
        101646750337,
        "HIGH_RISK",
        "FULL",
        5,
    ),
    ProviderInputSpec(
        "p8-11-corrective",
        "TASK-P8-11",
        "corrective_implementation",
        "build/validation/P8-11-provider-evidence-manifest.json",
        "475e46e6e7e140600b0302a21d594443f91d7853",
        34180636204,
        101920343916,
        "HIGH_RISK",
        "FULL",
        5,
    ),
    ProviderInputSpec(
        "p8-12-corrective",
        "TASK-P8-12",
        "corrective_implementation",
        "build/provider/P8-12-exact-provider-manifest.json",
        "4d37dba068c86230f6009820d6cbc7ff10a73495",
        34192999691,
        101956763253,
        "HIGH_RISK",
        "FULL",
        5,
    ),
    ProviderInputSpec(
        "p8-13-corrective",
        "TASK-P8-13",
        "corrective_implementation",
        "build/validation/P8-13-provider-evidence-manifest.json",
        "2682a2235f33d37cc909a1ad8ca3c52a6dffab05",
        34213714197,
        102023732906,
        "HIGH_RISK",
        "FULL",
        5,
    ),
    ProviderInputSpec(
        "p8-14-implementation",
        "TASK-P8-14",
        "implementation",
        "build/validation/P8-14-provider-evidence-manifest.json",
        "d0bf00da4af0f73befd2e9c833ffd837c63cedca",
        34307037409,
        102327664199,
        "HIGH_RISK",
        "FULL",
        5,
    ),
    ProviderInputSpec(
        "p8-15-corrective",
        "TASK-P8-15",
        "corrective_implementation",
        "build/validation/P8-15-provider-evidence-manifest.json",
        "87e2f1e814c75fbc25e82a89288f14b80831209b",
        34320622291,
        102368573448,
        "HIGH_RISK",
        "FULL",
        5,
    ),
    ProviderInputSpec(
        "p8-16-gate",
        "TASK-P8-16",
        "provider_verified_gate",
        "build/validation/P8-16-provider-evidence-manifest.json",
        "b80f44be094aaf5b673481dde9d81867ef49a11d",
        34340039154,
        102432349847,
        "PHASE_GATE",
        "FULL",
        5,
        "NOT_READY",
    ),
    ProviderInputSpec(
        "p8-18-closure",
        "TASK-P8-18",
        "corrective_closure",
        "build/validation/P8-18-provider-evidence-manifest.json",
        "5f67501d9d3cf75313edff250c8a7fdb74c56c30",
        34429068832,
        102723359648,
        "HIGH_RISK",
        "FULL",
        5,
    ),
    ProviderInputSpec(
        "p8-19-requalification",
        "TASK-P8-19",
        "provider_verified_gate",
        "build/validation/P8-19-provider-evidence-manifest.json",
        DIFF_BASE,
        34438523111,
        102751414544,
        "PHASE_GATE",
        "FULL",
        5,
        "READY",
    ),
)

_RETAINED_HISTORY = (
    (
        "TASK-P8-03",
        "055042b62f0fb5020a9c3670b739644514cb5adf",
        33898015147,
        "failure",
        "FROZEN_P4_REPLAY_REJECTED_NEW_MIGRATION",
    ),
    (
        "TASK-P8-08",
        "fa8256678c60ba066f06d889cf4c5e014b295472",
        34017333487,
        "failure",
        "FROZEN_P3_REPLAY_REJECTED_AGGREGATE_EXPORT",
    ),
    (
        "TASK-P8-11",
        "f33243f3c89d5b8f24fc6a6ca959cd0c2dcbfa46",
        34112349881,
        "failure",
        "FROZEN_P3_PACKAGE_SCRIPT_BOUNDARY",
    ),
    (
        "TASK-P8-11",
        "e39afa49c2983e5c389407d017273e86f2d30401",
        34114263425,
        "failure",
        "FROZEN_P4_PACKAGE_REPLAY_BOUNDARY",
    ),
    (
        "TASK-P8-12",
        "bf6cd0936a09fb063639307db959ebbae893658b",
        34191436658,
        "failure",
        "FROZEN_P4_SDK_PATH_ISOLATION",
    ),
    (
        "TASK-P8-13",
        "9818d0b6686ff005d0ea48ae81f3a306a5b36172",
        34212046893,
        "failure",
        "RUNTIME_INPUT_DRIFT",
    ),
    (
        "TASK-P8-15",
        "9cc44ba687f4deeb8cb79c714a48ecfea440a005",
        34319621745,
        "failure",
        "RUNTIME_INPUT_DRIFT_FALSE_POSITIVE",
    ),
    (
        "TASK-P8-16",
        "6996fbdcd51d06d2f197ec2ee1fc614146a06555",
        34334644319,
        "success",
        "AUDIT_PASS_GATE_NOT_READY_COLLECTOR_REJECTED",
    ),
    (
        "TASK-P8-18",
        "f9c308cc415299a7686bf55329d2b4b4ab4b9353",
        34427220042,
        "failure",
        "KIT_BOUNDARY_VIOLATION",
    ),
)


class P8ExitGateAuditError(RuntimeError):
    """Stable fail-closed error without payload or local-path disclosure."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(code)
        self.code = code
        self.field = field


def _fail(code: str, field: str) -> Never:
    raise P8ExitGateAuditError(code, field)


def _canonical_bytes(document: Mapping[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fingerprint(document: Mapping[str, object]) -> str:
    return "sha256:" + sha256(_canonical_bytes(document)).hexdigest()


def _with_fingerprint(document: JsonObject, field: str) -> JsonObject:
    projection = dict(document)
    projection.pop(field, None)
    document[field] = _fingerprint(projection)
    return document


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, field: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise P8ExitGateAuditError("JSON_INPUT_INVALID", field) from error
    if not isinstance(value, dict):
        _fail("JSON_INPUT_INVALID", field)
    return cast(JsonObject, value)


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _git(root: Path, *arguments: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and completed.returncode != 0:
        _fail("GIT_EVIDENCE_INVALID", "git")
    return completed.stdout.strip()


def _git_head(root: Path) -> str:
    head = _git(root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        _fail("GIT_EVIDENCE_INVALID", "git.head")
    return head


def _is_ancestor(root: Path, commit: str, head: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, head],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return completed.returncode == 0


def _normalize_sha256(value: object, field: str) -> str:
    if not isinstance(value, str):
        _fail("PROVIDER_MANIFEST_INVALID", field)
    normalized = value.removeprefix("sha256:").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        _fail("PROVIDER_MANIFEST_INVALID", field)
    return normalized


def _parse_time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        _fail("PROVIDER_MANIFEST_INVALID", field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise P8ExitGateAuditError("PROVIDER_MANIFEST_INVALID", field) from error
    if parsed.tzinfo is None:
        _fail("PROVIDER_MANIFEST_INVALID", field)
    return parsed.astimezone(UTC)


def _manifest_projection(
    document: Mapping[str, object], spec: ProviderInputSpec
) -> tuple[str, int, JsonObject, list[JsonObject]]:
    """Normalize both legacy DOCS_ONLY and canonical provider manifests."""

    if document.get("result") != "PASS" or document.get("issues") != []:
        _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.result")
    repository = document.get("repository")
    if repository != "kumamon-xu/PlantNexus-APS":
        _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.repository")

    required = document.get("required_check")
    if not isinstance(required, dict):
        _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.required")
    required_id = required.get("id", required.get("job_id"))
    if (
        required.get("name") != "validate"
        or required_id != spec.required_job_id
        or required.get("app_id") != REQUIRED_APP_ID
        or required.get("conclusion") != "success"
    ):
        _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.required")

    if isinstance(document.get("implementation_sha"), str):
        implementation_sha = cast(str, document["implementation_sha"])
        run = document.get("run")
        if not isinstance(run, dict) or run.get("id") != spec.run_id:
            _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.run")
        if run.get("conclusion") != "success":
            _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.run")
        raw_artifacts = document.get("artifacts")
    else:
        carrier_name = (
            "closure" if spec.evidence_kind == "closure" else "implementation"
        )
        carrier = document.get(carrier_name)
        if not isinstance(carrier, dict):
            _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.carrier")
        implementation_sha = cast(str, carrier.get("sha"))
        if (
            carrier.get("run_id") != spec.run_id
            or carrier.get("conclusion") != "success"
        ):
            _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.run")
        raw_artifacts = carrier.get("artifacts")

    if implementation_sha != spec.implementation_sha:
        _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.sha")
    if not isinstance(raw_artifacts, list) or len(raw_artifacts) != spec.artifact_count:
        _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.artifacts")
    if any(not isinstance(item, dict) for item in raw_artifacts):
        _fail("PROVIDER_MANIFEST_INVALID", f"provider_inputs.{spec.key}.artifacts")
    return (
        implementation_sha,
        cast(int, required_id),
        cast(JsonObject, required),
        cast(list[JsonObject], raw_artifacts),
    )


def _safe_zip_entry(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _verify_generic_artifact(
    root: Path, artifact: Mapping[str, object], field: str
) -> JsonObject:
    artifact_id = artifact.get("id")
    archive_file = artifact.get("archive_file")
    if not isinstance(artifact_id, int) or not isinstance(archive_file, str):
        _fail("PROVIDER_ARTIFACT_INVALID", field)
    expected_archive_sha = _normalize_sha256(artifact.get("sha256"), f"{field}.sha256")
    candidates = sorted((root / "build").rglob(archive_file))
    matching = [
        path for path in candidates if _file_sha256(path) == expected_archive_sha
    ]
    if not matching:
        _fail("PROVIDER_ARTIFACT_INVALID", f"{field}.archive")
    archive = matching[0]
    entries = artifact.get("entries")
    if not isinstance(entries, list) or any(
        not isinstance(row, dict) for row in entries
    ):
        _fail("PROVIDER_ARTIFACT_INVALID", f"{field}.entries")
    try:
        with ZipFile(archive) as zipped:
            names = [name for name in zipped.namelist() if not name.endswith("/")]
            if any(not _safe_zip_entry(name) for name in names) or len(names) != len(
                set(names)
            ):
                _fail("PROVIDER_ARTIFACT_UNSAFE", f"{field}.entries")
            expected_names = [cast(str, row.get("path")) for row in entries]
            if sorted(names) != sorted(expected_names):
                _fail("PROVIDER_ARTIFACT_INVALID", f"{field}.entries")
            for index, row in enumerate(entries):
                name = row.get("path")
                expected_bytes = row.get("bytes")
                if not isinstance(name, str) or not isinstance(expected_bytes, int):
                    _fail("PROVIDER_ARTIFACT_INVALID", f"{field}.entries[{index}]")
                payload = zipped.read(name)
                if len(payload) != expected_bytes or sha256(
                    payload
                ).hexdigest() != _normalize_sha256(
                    row.get("sha256"), f"{field}.entries[{index}].sha256"
                ):
                    _fail("PROVIDER_ARTIFACT_INVALID", f"{field}.entries[{index}]")
    except (BadZipFile, KeyError, OSError) as error:
        raise P8ExitGateAuditError("PROVIDER_ARTIFACT_INVALID", field) from error
    return {
        "artifact_id": artifact_id,
        "name": artifact.get("name"),
        "archive_sha256": "sha256:" + expected_archive_sha,
        "entry_count": len(entries),
        "expires_at": artifact.get("expires_at"),
        "verification": "ARCHIVE_AND_ENTRY_REHASH",
    }


def _verify_legacy_artifact(
    root: Path, artifact: Mapping[str, object], field: str
) -> JsonObject:
    artifact_id = artifact.get("id")
    entry_path = artifact.get("downloaded_entry")
    if (
        not isinstance(artifact_id, int)
        or not isinstance(entry_path, str)
        or artifact.get("expired") is not False
    ):
        _fail("PROVIDER_ARTIFACT_INVALID", field)
    path = root / entry_path
    expected_entry_sha = _normalize_sha256(
        artifact.get("entry_sha256"), f"{field}.entry_sha256"
    )
    if not path.is_file() or _file_sha256(path) != expected_entry_sha:
        _fail("PROVIDER_ARTIFACT_INVALID", f"{field}.entry")
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise P8ExitGateAuditError("PROVIDER_ARTIFACT_INVALID", field) from error
    return {
        "artifact_id": artifact_id,
        "name": artifact.get("name"),
        "archive_sha256": "sha256:"
        + _normalize_sha256(artifact.get("provider_digest"), f"{field}.digest"),
        "entry_count": 1,
        "expires_at": artifact.get("expires_at"),
        "verification": "DOWNLOADED_JSON_ENTRY_REHASH",
    }


def _artifact_set_fingerprint(artifacts: Sequence[Mapping[str, object]]) -> str:
    return _fingerprint({"artifacts": [dict(row) for row in artifacts]})


def _task_topology_from_internal_cards(root: Path) -> JsonObject:
    task_dir = root / "docs" / "tasks" / "P8"
    cards = sorted(task_dir.glob("TASK-P8-*.md"))
    if len(cards) != 20:
        _fail("TASK_TOPOLOGY_INVALID", "task_topology.task_count")
    statuses: dict[str, str] = {}
    for card in cards:
        text = card.read_text(encoding="utf-8")
        task = re.search(r"^doc_id:\s*(TASK-P8-\d{2})\s*$", text, re.MULTILINE)
        status = re.search(r"^status:\s*([a-z_]+)\s*$", text, re.MULTILINE)
        if task is None or status is None:
            _fail("TASK_TOPOLOGY_INVALID", "task_topology.cards")
        statuses[task.group(1)] = status.group(1)
    expected = {f"TASK-P8-{index:02d}": "done" for index in range(20)}
    expected["TASK-P8-17"] = "in_progress"
    if statuses != expected:
        _fail("TASK_TOPOLOGY_INVALID", "task_topology.statuses")
    return {
        "phase": "P8",
        "task_count": 20,
        "terminal_done_count": 19,
        "active_task": TASK_ID,
        "statuses": statuses,
        "dag_edges": [list(edge) for edge in _EXPECTED_DAG_EDGES],
        "dag_edge_count": len(_EXPECTED_DAG_EDGES),
        "cycle_count": 0,
    }


def collect_provider_observation(root: Path) -> JsonObject:
    """Re-hash all retained predecessor manifests and downloaded artifacts."""

    root = root.resolve()
    head = _git_head(root)
    rows: list[JsonObject] = []
    cutoff = _parse_time(ACTIVATION_CUTOFF, "activation_cutoff")
    for spec in _PROVIDER_INPUTS:
        source = root / spec.source_path
        document = _read_json(source, f"provider_inputs.{spec.key}")
        implementation_sha, _, _, artifacts = _manifest_projection(document, spec)
        if not _is_ancestor(root, implementation_sha, head):
            _fail("PROVIDER_LINEAGE_INVALID", f"provider_inputs.{spec.key}.sha")
        verified: list[JsonObject] = []
        for index, artifact in enumerate(artifacts):
            field = f"provider_inputs.{spec.key}.artifacts[{index}]"
            if "entries" in artifact:
                item = _verify_generic_artifact(root, artifact, field)
            else:
                item = _verify_legacy_artifact(root, artifact, field)
            if _parse_time(item["expires_at"], f"{field}.expires_at") <= cutoff:
                _fail("PROVIDER_ARTIFACT_EXPIRED", f"{field}.expires_at")
            verified.append(item)
        verified.sort(key=lambda item: cast(int, item["artifact_id"]))
        rows.append(
            {
                "key": spec.key,
                "task_id": spec.task_id,
                "evidence_kind": spec.evidence_kind,
                "implementation_sha": implementation_sha,
                "run_id": spec.run_id,
                "required_validate_job_id": spec.required_job_id,
                "required_app_id": REQUIRED_APP_ID,
                "task_profile": spec.task_profile,
                "workflow_profile": spec.workflow_profile,
                "provider_result": "PASS",
                "gate_verdict": spec.gate_verdict,
                "artifact_count": len(verified),
                "entry_count": sum(cast(int, row["entry_count"]) for row in verified),
                "earliest_expiry": min(
                    cast(str, row["expires_at"]) for row in verified
                ),
                "artifact_set_fingerprint": _artifact_set_fingerprint(verified),
                "source_manifest_sha256": "sha256:" + _file_sha256(source),
                "artifact_verification_modes": sorted(
                    {cast(str, row["verification"]) for row in verified}
                ),
                "issues": [],
            }
        )

    retained = [
        {
            "task_id": task,
            "commit_sha": commit,
            "run_id": run_id,
            "provider_conclusion": conclusion,
            "disposition": disposition,
            "retained": True,
            "rerun": False,
        }
        for task, commit, run_id, conclusion, disposition in _RETAINED_HISTORY
    ]
    if any(not _is_ancestor(root, row["commit_sha"], head) for row in retained):
        _fail("PROVIDER_LINEAGE_INVALID", "retained_history")
    observation: JsonObject = {
        "schema_version": OBSERVATION_VERSION,
        "audit_task": TASK_ID,
        "collected_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "activation_cutoff": ACTIVATION_CUTOFF,
        "repository": "kumamon-xu/PlantNexus-APS",
        "workflow": "ci.yml",
        "task_topology": _task_topology_from_internal_cards(root),
        "provider_inputs": rows,
        "retained_history": retained,
        "registers": {
            "open_count": 15,
            "open_status": "OPEN",
            "simulation_assumption_count": 26,
            "simulation_assumption_status": "ACTIVE",
            "risk_count": 19,
            "risk_status": "MONITORED",
            "production_closure_from_p8": False,
        },
        "summary": {
            "provider_input_count": len(rows),
            "provider_task_count": len({row["task_id"] for row in rows}),
            "artifact_count": sum(cast(int, row["artifact_count"]) for row in rows),
            "entry_count": sum(cast(int, row["entry_count"]) for row in rows),
            "retained_history_count": len(retained),
            "expired_artifact_count": 0,
            "digest_mismatch_count": 0,
            "unsafe_archive_count": 0,
            "issue_count": 0,
        },
        "issues": [],
    }
    _with_fingerprint(observation, "observation_fingerprint")
    validate_provider_observation(observation, root, enforce_frozen_fingerprint=False)
    return observation


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict):
        _fail("EVIDENCE_SHAPE_INVALID", field)
    return cast(JsonObject, value)


def _items(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("EVIDENCE_SHAPE_INVALID", field)
    return value


def _sha256_value(value: object, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        _fail("EVIDENCE_DIGEST_INVALID", field)
    return value


def validate_provider_observation(
    observation: Mapping[str, object],
    root: Path,
    *,
    enforce_frozen_fingerprint: bool = True,
) -> None:
    """Validate the sanitized, locally re-hashed predecessor observation."""

    expected_keys = {
        "schema_version",
        "audit_task",
        "collected_at_utc",
        "activation_cutoff",
        "repository",
        "workflow",
        "task_topology",
        "provider_inputs",
        "retained_history",
        "registers",
        "summary",
        "issues",
        "observation_fingerprint",
    }
    if set(observation) != expected_keys:
        _fail("PROVIDER_OBSERVATION_INVALID", "observation.keys")
    for key, expected in (
        ("schema_version", OBSERVATION_VERSION),
        ("audit_task", TASK_ID),
        ("activation_cutoff", ACTIVATION_CUTOFF),
        ("repository", "kumamon-xu/PlantNexus-APS"),
        ("workflow", "ci.yml"),
        ("issues", []),
    ):
        if observation.get(key) != expected:
            _fail("PROVIDER_OBSERVATION_INVALID", f"observation.{key}")
    collected_at = _parse_time(observation.get("collected_at_utc"), "collected_at_utc")
    if collected_at < _parse_time(ACTIVATION_CUTOFF, "activation_cutoff"):
        _fail("PROVIDER_OBSERVATION_INVALID", "observation.collected_at_utc")
    projection = dict(observation)
    observed_fingerprint = projection.pop("observation_fingerprint", None)
    if observed_fingerprint != _fingerprint(projection):
        _fail("PROVIDER_OBSERVATION_INVALID", "observation.observation_fingerprint")
    if enforce_frozen_fingerprint and observed_fingerprint != OBSERVATION_FINGERPRINT:
        _fail("PROVIDER_OBSERVATION_DRIFT", "observation.observation_fingerprint")

    topology = _object(observation.get("task_topology"), "task_topology")
    expected_statuses = {f"TASK-P8-{index:02d}": "done" for index in range(20)}
    expected_statuses[TASK_ID] = "in_progress"
    if topology != {
        "phase": "P8",
        "task_count": 20,
        "terminal_done_count": 19,
        "active_task": TASK_ID,
        "statuses": expected_statuses,
        "dag_edges": [list(edge) for edge in _EXPECTED_DAG_EDGES],
        "dag_edge_count": len(_EXPECTED_DAG_EDGES),
        "cycle_count": 0,
    }:
        _fail("TASK_TOPOLOGY_INVALID", "observation.task_topology")

    rows = _items(observation.get("provider_inputs"), "provider_inputs")
    if len(rows) != len(_PROVIDER_INPUTS):
        _fail("PROVIDER_OBSERVATION_INVALID", "provider_inputs.count")
    expected_row_keys = {
        "key",
        "task_id",
        "evidence_kind",
        "implementation_sha",
        "run_id",
        "required_validate_job_id",
        "required_app_id",
        "task_profile",
        "workflow_profile",
        "provider_result",
        "gate_verdict",
        "artifact_count",
        "entry_count",
        "earliest_expiry",
        "artifact_set_fingerprint",
        "source_manifest_sha256",
        "artifact_verification_modes",
        "issues",
    }
    head = _git_head(root.resolve())
    cutoff = _parse_time(ACTIVATION_CUTOFF, "activation_cutoff")
    for index, spec in enumerate(_PROVIDER_INPUTS):
        row = _object(rows[index], f"provider_inputs[{index}]")
        if set(row) != expected_row_keys:
            _fail("PROVIDER_OBSERVATION_INVALID", f"provider_inputs[{index}].keys")
        expected_values: Mapping[str, object] = {
            "key": spec.key,
            "task_id": spec.task_id,
            "evidence_kind": spec.evidence_kind,
            "implementation_sha": spec.implementation_sha,
            "run_id": spec.run_id,
            "required_validate_job_id": spec.required_job_id,
            "required_app_id": REQUIRED_APP_ID,
            "task_profile": spec.task_profile,
            "workflow_profile": spec.workflow_profile,
            "provider_result": "PASS",
            "gate_verdict": spec.gate_verdict,
            "artifact_count": spec.artifact_count,
            "issues": [],
        }
        if any(row.get(key) != value for key, value in expected_values.items()):
            _fail("PROVIDER_OBSERVATION_INVALID", f"provider_inputs[{index}].identity")
        if (
            not isinstance(row.get("entry_count"), int)
            or cast(int, row["entry_count"]) < 1
        ):
            _fail(
                "PROVIDER_OBSERVATION_INVALID", f"provider_inputs[{index}].entry_count"
            )
        if _parse_time(row.get("earliest_expiry"), "earliest_expiry") <= cutoff:
            _fail(
                "PROVIDER_ARTIFACT_EXPIRED", f"provider_inputs[{index}].earliest_expiry"
            )
        _sha256_value(row.get("artifact_set_fingerprint"), "artifact_set_fingerprint")
        _sha256_value(row.get("source_manifest_sha256"), "source_manifest_sha256")
        modes = row.get("artifact_verification_modes")
        if (
            not isinstance(modes, list)
            or not modes
            or any(
                mode not in {"ARCHIVE_AND_ENTRY_REHASH", "DOWNLOADED_JSON_ENTRY_REHASH"}
                for mode in modes
            )
        ):
            _fail("PROVIDER_OBSERVATION_INVALID", f"provider_inputs[{index}].modes")
        if not _is_ancestor(root, spec.implementation_sha, head):
            _fail("PROVIDER_LINEAGE_INVALID", f"provider_inputs[{index}].sha")

    retained = _items(observation.get("retained_history"), "retained_history")
    expected_retained = [
        {
            "task_id": task,
            "commit_sha": commit,
            "run_id": run_id,
            "provider_conclusion": conclusion,
            "disposition": disposition,
            "retained": True,
            "rerun": False,
        }
        for task, commit, run_id, conclusion, disposition in _RETAINED_HISTORY
    ]
    if retained != expected_retained:
        _fail("PROVIDER_OBSERVATION_INVALID", "retained_history")
    if any(
        not _is_ancestor(root, row["commit_sha"], head) for row in expected_retained
    ):
        _fail("PROVIDER_LINEAGE_INVALID", "retained_history")

    registers = {
        "open_count": 15,
        "open_status": "OPEN",
        "simulation_assumption_count": 26,
        "simulation_assumption_status": "ACTIVE",
        "risk_count": 19,
        "risk_status": "MONITORED",
        "production_closure_from_p8": False,
    }
    if observation.get("registers") != registers:
        _fail("PROVIDER_OBSERVATION_INVALID", "registers")
    summary = _object(observation.get("summary"), "summary")
    expected_summary = {
        "provider_input_count": len(rows),
        "provider_task_count": len(
            {cast(str, _object(row, "provider_input")["task_id"]) for row in rows}
        ),
        "artifact_count": sum(
            cast(int, _object(row, "provider_input")["artifact_count"]) for row in rows
        ),
        "entry_count": sum(
            cast(int, _object(row, "provider_input")["entry_count"]) for row in rows
        ),
        "retained_history_count": len(retained),
        "expired_artifact_count": 0,
        "digest_mismatch_count": 0,
        "unsafe_archive_count": 0,
        "issue_count": 0,
    }
    if summary != expected_summary:
        _fail("PROVIDER_OBSERVATION_INVALID", "summary")


def _working_tree_paths(root: Path) -> list[str]:
    changed: set[str] = set()
    for arguments in (
        ("diff", "--name-only", f"{DIFF_BASE}..HEAD"),
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        output = _git(root, *arguments)
        changed.update(
            line.strip().replace("\\", "/")
            for line in output.splitlines()
            if line.strip()
        )
    return sorted(changed)


def _task_scope_paths(root: Path) -> tuple[list[str], str, str]:
    source = "scripts/p8_exit_gate_audit.py"
    dirty = _git(
        root,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        source,
        check=False,
    )
    if dirty.strip():
        return _working_tree_paths(root), "WORKING_TREE", _git_head(root)
    output = _git(
        root,
        "log",
        "-1",
        "--format=%H",
        "--",
        source,
        check=False,
    )
    commits = [line.strip() for line in output.splitlines() if line.strip()]
    if commits:
        implementation_commit = commits[0]
        changed = _git(
            root, "diff", "--name-only", f"{DIFF_BASE}..{implementation_commit}"
        )
        return (
            sorted(
                line.strip().replace("\\", "/")
                for line in changed.splitlines()
                if line.strip()
            ),
            "LATEST_EXIT_AUDIT_COMMIT",
            implementation_commit,
        )
    return _working_tree_paths(root), "WORKING_TREE", _git_head(root)


def _scope_evidence(root: Path) -> JsonObject:
    changed, source, implementation_commit = _task_scope_paths(root)
    unexpected = sorted(set(changed) - _ALLOWED_TRACKED_PATHS)
    missing = sorted(_ALLOWED_TRACKED_PATHS - set(changed))
    if unexpected:
        _fail("AUDIT_SCOPE_INVALID", "scope.unexpected_paths")
    if missing:
        _fail("AUDIT_SCOPE_INVALID", "scope.missing_paths")
    return {
        "status": "PASS",
        "diff_base": DIFF_BASE,
        "scope_source": source,
        "implementation_commit": implementation_commit,
        "changed_paths": changed,
        "changed_path_count": len(changed),
        "exact_allow_list": sorted(_ALLOWED_TRACKED_PATHS),
        "unexpected_paths": [],
        "missing_paths": [],
        "impact_rules": list(IMPACT_RULES),
        "product_source_changes": 0,
        "forbidden_owner_changes": 0,
    }


_OWNER_FILES: Mapping[str, tuple[str, ...]] = {
    "docs/adr/ADR-0017-headless-canonical-json-and-dual-delivery.md": (
        "status: accepted",
        "Canonical JSON",
        "Headless API",
    ),
    "docs/adr/ADR-0018-extension-sdk-runtime-and-developer-kit.md": (
        "status: accepted",
        "APS Extension SDK",
        "APS Developer Kit",
    ),
    "docs/contracts/headless-platform-integration.md": (
        "versioned canonical JSON",
        "不直接连接第三方系统",
        "2.10.0",
    ),
    "docs/contracts/extension-sdk-and-developer-kit.md": (
        "Constraint",
        "Objective",
        "Replan Policy",
        "不得复制",
    ),
    "docs/architecture/extension-sdk-runtime-and-developer-kit.md": (
        "Enterprise Extension",
        "Runtime",
        "Developer Kit",
    ),
    "docs/architecture/headless-productization-and-platform-integration.md": (
        "Canonical JSON is the only supported external product input",
        "same versioned HTTP API",
        "automatically upgrades",
    ),
}


def _public_owner_evidence(root: Path) -> JsonObject:
    files: list[JsonObject] = []
    for relative, markers in _OWNER_FILES.items():
        path = root / relative
        try:
            payload = path.read_bytes()
            content = payload.decode("utf-8")
        except (OSError, UnicodeError) as error:
            raise P8ExitGateAuditError("PUBLIC_OWNER_INVALID", relative) from error
        if any(marker not in content for marker in markers):
            _fail("PUBLIC_OWNER_INVALID", relative)
        files.append(
            {
                "path": relative,
                "sha256": "sha256:" + sha256(payload).hexdigest(),
            }
        )
    migrations = sorted((root / "backend" / "migrations" / "versions").glob("*.py"))
    if len(migrations) != 9 or migrations[-1].stem != "0009_host_authorization_audit":
        _fail("PUBLIC_OWNER_INVALID", "database.migrations")
    schema_count = len(
        [path for path in (root / "schemas").rglob("*") if path.is_file()]
    )
    if schema_count != 117:
        _fail("PUBLIC_OWNER_INVALID", "schemas.count")
    return {
        "status": "PASS",
        "accepted_adrs": ["ADR-0017", "ADR-0018"],
        "schema_set_version": "2.10.0",
        "schema_document_count": schema_count,
        "migration_head": "0009_host_authorization_audit",
        "migration_count": len(migrations),
        "runtime_version": "0.1.0",
        "extension_sdk_version": "1.0.0",
        "developer_kit_version": "1.0.0",
        "headless_api": "headless-http.v1",
        "extension_points": [
            "Constraint",
            "Objective",
            "Planning Rule",
            "Validation Rule",
            "Replan Policy",
            "Plugin Registry",
        ],
        "owner_files": files,
        "owner_file_count": len(files),
    }


def _check(check_id: str, evidence: object) -> JsonObject:
    return {"check_id": check_id, "status": "PASS", "evidence": evidence}


def _fresh_output_paths(subreport_dir: Path) -> dict[str, Path]:
    return {
        "report": subreport_dir / "fresh-p8-19-requalification.json",
        "blocker_disposition": subreport_dir / "fresh-p8-19-blocker-disposition.json",
        "provenance": subreport_dir / "fresh-p8-19-provenance.json",
        "compatibility": subreport_dir / "fresh-p8-19-compatibility.json",
        "security": subreport_dir / "fresh-p8-19-security.json",
        "recovery": subreport_dir / "fresh-p8-19-recovery.json",
        "benchmark": subreport_dir / "fresh-p8-19-benchmark.json",
    }


def run_exit_audit(
    *,
    root: Path,
    provider_observation: Mapping[str, object],
    profile_path: Path,
    junit_path: Path,
    input_paths: Mapping[str, Path],
    subreport_dir: Path,
) -> JsonObject:
    """Replay the current P8 platform Gate and issue the independent Exit verdict."""

    started = perf_counter()
    root = root.resolve()
    validate_provider_observation(provider_observation, root)
    if set(input_paths) != set(_INPUT_REPORTS):
        _fail("CURRENT_REPORT_SET_INVALID", "input_paths")
    scope = _scope_evidence(root)
    owners = _public_owner_evidence(root)
    output_paths = _fresh_output_paths(subreport_dir)
    fresh = run_p8_requalification_gate(
        root,
        profile_path=profile_path,
        junit_path=junit_path,
        input_paths=input_paths,
        output_paths=output_paths,
    )
    validate_requalification_report(fresh)
    summary = _object(fresh.get("check_summary"), "fresh.check_summary")
    if (
        fresh.get("verdict") != "READY"
        or fresh.get("audit_status") != "PASS"
        or fresh.get("issues") != []
        or fresh.get("blocking_gaps") != []
        or summary.get("platform_check_count") != 18
        or summary.get("platform_pass_count") != 18
        or summary.get("platform_blocked_count") != 0
        or summary.get("closure_assertion_count") != 4
        or summary.get("closure_pass_count") != 4
        or summary.get("closure_blocked_count") != 0
        or summary.get("error_count") != 0
    ):
        _fail("FRESH_P8_REQUALIFICATION_NOT_READY", "fresh_p8_19")
    provider_summary = deepcopy(_object(provider_observation.get("summary"), "summary"))
    provider_summary.update(
        {
            "observation_version": OBSERVATION_VERSION,
            "observation_fingerprint": provider_observation["observation_fingerprint"],
            "required_context": "validate",
            "required_app_id": REQUIRED_APP_ID,
        }
    )
    fresh_summary: JsonObject = {
        "report_version": fresh["report_version"],
        "report_fingerprint": fresh["report_fingerprint"],
        "report_sha256": _fingerprint(fresh),
        "task_id": fresh["task_id"],
        "code_commit": fresh["code_commit"],
        "profile_fingerprint": PROFILE_FINGERPRINT,
        "audit_status": fresh["audit_status"],
        "verdict": fresh["verdict"],
        "platform_check_count": summary["platform_check_count"],
        "platform_pass_count": summary["platform_pass_count"],
        "platform_blocked_count": summary["platform_blocked_count"],
        "closure_assertion_count": summary["closure_assertion_count"],
        "closure_pass_count": summary["closure_pass_count"],
        "closure_blocked_count": summary["closure_blocked_count"],
        "error_count": summary["error_count"],
        "issues": [],
        "blocking_gaps": [],
    }
    topology = deepcopy(provider_observation["task_topology"])
    registers = deepcopy(provider_observation["registers"])
    checks = [
        _check(EXPECTED_CHECK_IDS[0], topology),
        _check(
            EXPECTED_CHECK_IDS[1],
            {
                "provider_input_count": provider_summary["provider_input_count"],
                "provider_task_count": provider_summary["provider_task_count"],
                "required_context": "validate",
                "required_app_id": REQUIRED_APP_ID,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[2],
            {
                "artifact_count": provider_summary["artifact_count"],
                "entry_count": provider_summary["entry_count"],
                "expired_artifact_count": 0,
                "digest_mismatch_count": 0,
                "unsafe_archive_count": 0,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[3], deepcopy(provider_observation["retained_history"])
        ),
        _check(
            EXPECTED_CHECK_IDS[4],
            {
                "accepted_adrs": owners["accepted_adrs"],
                "owner_file_count": owners["owner_file_count"],
                "schema_set_version": owners["schema_set_version"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[5],
            {
                "canonical_json_only": True,
                "third_party_connector_in_scope": False,
                "host_owns_mapping_and_display": True,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[6],
            {
                "durable_lineage": True,
                "planning_run": True,
                "publication_operations": 5,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[7],
            {"api_worker_separated": True, "fresh_formal_validator": True},
        ),
        _check(
            EXPECTED_CHECK_IDS[8],
            {"identity": "SERVER_TRUSTED", "scope": "DEFAULT_DENY", "audit": True},
        ),
        _check(
            EXPECTED_CHECK_IDS[9],
            {
                "runtime_version": owners["runtime_version"],
                "migration_head": owners["migration_head"],
                "sbom_and_license": True,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[10],
            {
                "deployment": True,
                "observability": True,
                "recovery": True,
                "runbooks": True,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[11],
            {
                "backend_only": True,
                "optional_frontend": True,
                "frontend_is_api_consumer": True,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[12],
            {
                "sdk_version": owners["extension_sdk_version"],
                "extension_points": owners["extension_points"],
                "registry": "DETERMINISTIC_FAIL_CLOSED",
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[13],
            {"core_reverse_dependency": False, "enterprise_core_copy_or_fork": False},
        ),
        _check(
            EXPECTED_CHECK_IDS[14],
            {"conformance": "PASS", "negative_boundary": "FAIL_CLOSED"},
        ),
        _check(
            EXPECTED_CHECK_IDS[15],
            {"independent_extension_projects": 2, "alpha": "PASS", "beta": "PASS"},
        ),
        _check(
            EXPECTED_CHECK_IDS[16],
            {
                "developer_kit_version": owners["developer_kit_version"],
                "immutable": True,
                "old_kit_replay": "PASS",
                "automatic_upgrade": False,
            },
        ),
        _check(EXPECTED_CHECK_IDS[17], fresh_summary),
        _check(EXPECTED_CHECK_IDS[18], registers),
        _check(
            EXPECTED_CHECK_IDS[19],
            {"scope": scope, "boundaries": dict(_BOUNDARIES)},
        ),
    ]
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "audit_task": TASK_ID,
        "test_id": TEST_ID,
        "task_status": "in_progress_ready_for_exact_provider",
        "code_commit": _git_head(root),
        "diff_base": DIFF_BASE,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_ms": round((perf_counter() - started) * 1_000, 3),
        "validation_profile": VALIDATION_PROFILE,
        "decision": "READY",
        "impact_rules": list(IMPACT_RULES),
        "provider_evidence": provider_summary,
        "task_topology": topology,
        "public_owner_evidence": owners,
        "fresh_p8_19": fresh_summary,
        "registers": registers,
        "scope_evidence": scope,
        "checks": checks,
        "check_count": len(checks),
        "issues": [],
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
        "implementation_provider": "PENDING_EXACT_SHA",
    }
    _with_fingerprint(report, "report_fingerprint")
    validate_exit_report(report)
    return report


def validate_exit_report(report: Mapping[str, object]) -> None:
    """Validate a strict successful TASK-P8-17 report."""

    expected_keys = {
        "report_version",
        "audit_task",
        "test_id",
        "task_status",
        "code_commit",
        "diff_base",
        "generated_at_utc",
        "duration_ms",
        "validation_profile",
        "decision",
        "impact_rules",
        "provider_evidence",
        "task_topology",
        "public_owner_evidence",
        "fresh_p8_19",
        "registers",
        "scope_evidence",
        "checks",
        "check_count",
        "issues",
        "blocking_gaps",
        "boundaries",
        "implementation_provider",
        "report_fingerprint",
    }
    if set(report) != expected_keys:
        _fail("EXIT_REPORT_INVALID", "report.keys")
    for key, expected in (
        ("report_version", REPORT_VERSION),
        ("audit_task", TASK_ID),
        ("test_id", TEST_ID),
        ("task_status", "in_progress_ready_for_exact_provider"),
        ("diff_base", DIFF_BASE),
        ("validation_profile", VALIDATION_PROFILE),
        ("decision", "READY"),
        ("impact_rules", list(IMPACT_RULES)),
        ("issues", []),
        ("blocking_gaps", []),
        ("boundaries", _BOUNDARIES),
        ("implementation_provider", "PENDING_EXACT_SHA"),
    ):
        if report.get(key) != expected:
            _fail("EXIT_REPORT_INVALID", f"report.{key}")
    code_commit = report.get("code_commit")
    if not isinstance(code_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", code_commit
    ):
        _fail("EXIT_REPORT_INVALID", "report.code_commit")
    projection = dict(report)
    observed = projection.pop("report_fingerprint", None)
    if observed != _fingerprint(projection):
        _fail("EXIT_REPORT_INVALID", "report.report_fingerprint")
    provider = _object(report.get("provider_evidence"), "provider_evidence")
    if (
        provider.get("observation_fingerprint") != OBSERVATION_FINGERPRINT
        or provider.get("provider_input_count") != len(_PROVIDER_INPUTS)
        or provider.get("provider_task_count") != 19
        or provider.get("artifact_count")
        != sum(row.artifact_count for row in _PROVIDER_INPUTS)
        or provider.get("retained_history_count") != len(_RETAINED_HISTORY)
        or provider.get("expired_artifact_count") != 0
        or provider.get("digest_mismatch_count") != 0
        or provider.get("unsafe_archive_count") != 0
        or provider.get("issue_count") != 0
        or provider.get("required_context") != "validate"
        or provider.get("required_app_id") != REQUIRED_APP_ID
    ):
        _fail("EXIT_REPORT_INVALID", "report.provider_evidence")
    fresh = _object(report.get("fresh_p8_19"), "fresh_p8_19")
    if (
        fresh.get("task_id") != "TASK-P8-19"
        or fresh.get("audit_status") != "PASS"
        or fresh.get("verdict") != "READY"
        or fresh.get("profile_fingerprint") != PROFILE_FINGERPRINT
        or fresh.get("platform_check_count") != 18
        or fresh.get("platform_pass_count") != 18
        or fresh.get("platform_blocked_count") != 0
        or fresh.get("closure_assertion_count") != 4
        or fresh.get("closure_pass_count") != 4
        or fresh.get("closure_blocked_count") != 0
        or fresh.get("error_count") != 0
        or fresh.get("issues") != []
        or fresh.get("blocking_gaps") != []
    ):
        _fail("EXIT_REPORT_INVALID", "report.fresh_p8_19")
    scope = _object(report.get("scope_evidence"), "scope_evidence")
    if (
        scope.get("status") != "PASS"
        or set(_items(scope.get("changed_paths"), "scope.changed_paths"))
        != _ALLOWED_TRACKED_PATHS
        or scope.get("unexpected_paths") != []
        or scope.get("missing_paths") != []
        or scope.get("product_source_changes") != 0
        or scope.get("forbidden_owner_changes") != 0
    ):
        _fail("EXIT_REPORT_INVALID", "report.scope_evidence")
    checks = _items(report.get("checks"), "checks")
    if (
        report.get("check_count") != len(EXPECTED_CHECK_IDS)
        or tuple(_object(row, "check").get("check_id") for row in checks)
        != EXPECTED_CHECK_IDS
        or any(
            set(_object(row, "check")) != {"check_id", "status", "evidence"}
            or _object(row, "check").get("status") != "PASS"
            for row in checks
        )
    ):
        _fail("EXIT_REPORT_INVALID", "report.checks")


def build_exit_manifest(report: Mapping[str, object]) -> JsonObject:
    """Build the compact exact-Provider carrier for the P8 Exit audit."""

    validate_exit_report(report)
    provider = _object(report.get("provider_evidence"), "provider_evidence")
    fresh = _object(report.get("fresh_p8_19"), "fresh_p8_19")
    manifest: JsonObject = {
        "schema_version": MANIFEST_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "code_commit": report["code_commit"],
        "diff_base": DIFF_BASE,
        "validation_profile": VALIDATION_PROFILE,
        "decision": "READY",
        "report_version": REPORT_VERSION,
        "report_fingerprint": report["report_fingerprint"],
        "report_sha256": _fingerprint(report),
        "provider_observation_fingerprint": provider["observation_fingerprint"],
        "fresh_p8_19_report_fingerprint": fresh["report_fingerprint"],
        "fresh_p8_19_report_sha256": fresh["report_sha256"],
        "check_ids": list(EXPECTED_CHECK_IDS),
        "check_count": len(EXPECTED_CHECK_IDS),
        "impact_rules": list(IMPACT_RULES),
        "issues": [],
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
        "provider_binding": {
            "required_context": "validate",
            "required_app_id": REQUIRED_APP_ID,
            "workflow_profile": "FULL",
            "fresh_phase_gate_replay": True,
            "historical_provider_evidence_reused_without_rerun": True,
        },
    }
    return _with_fingerprint(manifest, "manifest_fingerprint")


def validate_exit_manifest(
    manifest: Mapping[str, object], report: Mapping[str, object] | None = None
) -> None:
    expected_keys = {
        "schema_version",
        "task_id",
        "test_id",
        "code_commit",
        "diff_base",
        "validation_profile",
        "decision",
        "report_version",
        "report_fingerprint",
        "report_sha256",
        "provider_observation_fingerprint",
        "fresh_p8_19_report_fingerprint",
        "fresh_p8_19_report_sha256",
        "check_ids",
        "check_count",
        "impact_rules",
        "issues",
        "blocking_gaps",
        "boundaries",
        "provider_binding",
        "manifest_fingerprint",
    }
    if set(manifest) != expected_keys:
        _fail("EXIT_MANIFEST_INVALID", "manifest.keys")
    for key, expected in (
        ("schema_version", MANIFEST_VERSION),
        ("task_id", TASK_ID),
        ("test_id", TEST_ID),
        ("diff_base", DIFF_BASE),
        ("validation_profile", VALIDATION_PROFILE),
        ("decision", "READY"),
        ("report_version", REPORT_VERSION),
        ("provider_observation_fingerprint", OBSERVATION_FINGERPRINT),
        ("check_ids", list(EXPECTED_CHECK_IDS)),
        ("check_count", len(EXPECTED_CHECK_IDS)),
        ("impact_rules", list(IMPACT_RULES)),
        ("issues", []),
        ("blocking_gaps", []),
        ("boundaries", _BOUNDARIES),
        (
            "provider_binding",
            {
                "required_context": "validate",
                "required_app_id": REQUIRED_APP_ID,
                "workflow_profile": "FULL",
                "fresh_phase_gate_replay": True,
                "historical_provider_evidence_reused_without_rerun": True,
            },
        ),
    ):
        if manifest.get(key) != expected:
            _fail("EXIT_MANIFEST_INVALID", f"manifest.{key}")
    projection = dict(manifest)
    if projection.pop("manifest_fingerprint", None) != _fingerprint(projection):
        _fail("EXIT_MANIFEST_INVALID", "manifest.manifest_fingerprint")
    for field in (
        "report_fingerprint",
        "report_sha256",
        "fresh_p8_19_report_fingerprint",
        "fresh_p8_19_report_sha256",
    ):
        _sha256_value(manifest.get(field), f"manifest.{field}")
    if report is not None:
        validate_exit_report(report)
        fresh = _object(report.get("fresh_p8_19"), "fresh_p8_19")
        if (
            manifest.get("code_commit") != report.get("code_commit")
            or manifest.get("report_fingerprint") != report.get("report_fingerprint")
            or manifest.get("report_sha256") != _fingerprint(report)
            or manifest.get("fresh_p8_19_report_fingerprint")
            != fresh.get("report_fingerprint")
        ):
            _fail("EXIT_MANIFEST_INVALID", "manifest.report_binding")


def _failure_report(error: Exception, root: Path) -> JsonObject:
    try:
        code_commit = _git_head(root)
    except Exception:  # noqa: BLE001 - failure carrier remains path/payload safe
        code_commit = "unavailable"
    return {
        "report_version": REPORT_VERSION,
        "audit_task": TASK_ID,
        "test_id": TEST_ID,
        "task_status": "in_progress_not_ready",
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "validation_profile": VALIDATION_PROFILE,
        "decision": "NOT_READY",
        "issues": [
            {
                "issue_id": "P8-EXIT-GATE-AUDIT-001",
                "error_code": getattr(error, "code", "EXIT_AUDIT_EXECUTION_FAILED"),
                "error_field": getattr(error, "field", "orchestrator"),
                "payload_included": False,
                "path_included": False,
            }
        ],
        "blocking_gaps": [
            {
                "gap_id": "P8-EXIT-GATE-AUDIT-001",
                "status": "BLOCKING",
                "remediation": "REQUIRES_SEPARATE_BOUNDED_CORRECTIVE_SHA",
            }
        ],
        "boundaries": dict(_BOUNDARIES),
        "implementation_provider": "NOT_ELIGIBLE",
    }


def _failure_manifest(report: Mapping[str, object]) -> JsonObject:
    return {
        "schema_version": MANIFEST_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "code_commit": report.get("code_commit"),
        "diff_base": DIFF_BASE,
        "validation_profile": VALIDATION_PROFILE,
        "decision": "NOT_READY",
        "issues": deepcopy(report.get("issues")),
        "blocking_gaps": deepcopy(report.get("blocking_gaps")),
        "boundaries": dict(_BOUNDARIES),
        "provider_binding": "NOT_ELIGIBLE",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--provider-observation",
        type=Path,
        default=Path("docs/p8-exit-gate-audit-observations.v1.json"),
    )
    parser.add_argument("--collect-provider-observation", action="store_true")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--junit", type=Path)
    for name in _INPUT_REPORTS:
        parser.add_argument("--" + name.replace("_", "-"), type=Path)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p8-exit-gate-audit.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("build/validation/p8-exit-gate-evidence-manifest.json"),
    )
    parser.add_argument(
        "--subreport-dir",
        type=Path,
        default=Path("build/validation/p8-17-subreports"),
    )
    return parser


def _rooted(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    observation_path = _rooted(root, args.provider_observation)
    if args.collect_provider_observation:
        observation = collect_provider_observation(root)
        _write_json(observation_path, observation)
        print(json.dumps(observation["summary"], ensure_ascii=False, sort_keys=True))
        return 0
    report_path = _rooted(root, args.report)
    manifest_path = _rooted(root, args.manifest)
    subreport_dir = _rooted(root, args.subreport_dir)
    try:
        if args.profile is None or args.junit is None:
            _fail("CLI_INPUT_MISSING", "profile_or_junit")
        missing = [name for name in _INPUT_REPORTS if getattr(args, name) is None]
        if missing:
            _fail("CLI_INPUT_MISSING", "current_reports")
        input_paths = {
            name: _rooted(root, cast(Path, getattr(args, name)))
            for name in _INPUT_REPORTS
        }
        report = run_exit_audit(
            root=root,
            provider_observation=_read_json(observation_path, "provider_observation"),
            profile_path=_rooted(root, args.profile),
            junit_path=_rooted(root, args.junit),
            input_paths=input_paths,
            subreport_dir=subreport_dir,
        )
        manifest = build_exit_manifest(report)
        validate_exit_manifest(manifest, report)
    except Exception as error:  # noqa: BLE001 - CLI emits only stable safe fields
        report = _failure_report(error, root)
        manifest = _failure_manifest(report)
        exit_code = 1
    else:
        exit_code = 0
    _write_json(report_path, report)
    _write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "check_count": report.get("check_count", 0),
                "issues": report["issues"],
                "blocking_gaps": report["blocking_gaps"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACTIVATION_CUTOFF",
    "DIFF_BASE",
    "EXPECTED_CHECK_IDS",
    "IMPACT_RULES",
    "MANIFEST_VERSION",
    "OBSERVATION_FINGERPRINT",
    "OBSERVATION_VERSION",
    "P8ExitGateAuditError",
    "REPORT_VERSION",
    "TASK_ID",
    "TEST_ID",
    "VALIDATION_PROFILE",
    "build_exit_manifest",
    "collect_provider_observation",
    "main",
    "run_exit_audit",
    "validate_exit_manifest",
    "validate_exit_report",
    "validate_provider_observation",
]
