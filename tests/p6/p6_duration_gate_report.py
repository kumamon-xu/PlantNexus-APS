"""Build the TASK-P6-09 AI-duration vertical-slice integration Gate report."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, Never, cast

from app.simulation.scenarios.disruption_replay_check import (
    run_disruption_replay_checks,
)
from scripts.p6_duration_contract_check import run_contract_checks
from scripts.p6_duration_dataset_check import run_dataset_checks
from scripts.p6_duration_evaluation_check import run_evaluation_checks
from scripts.p6_duration_model_check import run_model_checks
from scripts.p6_duration_monitoring_check import run_monitoring_checks
from scripts.p6_duration_runtime_check import run_runtime_checks
from scripts.p6_planning_integration_check import run_planning_integration_checks


type JsonObject = dict[str, Any]

REPORT_VERSION = "p6-ai-duration-vertical-slice-report.v1"
MANIFEST_VERSION = "p6-ai-duration-vertical-slice-manifest.v1"
GOVERNANCE_REPORT_VERSION = "p6-duration-governance-frozen-report.v1"
TASK_ID = "TASK-P6-09"
DIFF_BASE = "a8984dd3e961fe03dad543d9ce6b9b5266c6ab09"
VALIDATION_PROFILE = "PHASE_GATE"
ACTIVATION_VERIFIED_AT = "2026-09-02T00:00:00Z"

IMPACT_RULES = (
    "IMPACT-TESTS",
    "IMPACT-DOCS",
)
TEST_IDS = (
    "TEST-P6-VERTICAL-SLICE-001",
    "TEST-P6-FALLBACK-001",
    "TEST-P6-PLANNING-INTEGRATION-001",
    "TEST-P6-DRIFT-MONITORING-001",
    "TEST-P4-VERTICAL-SLICE-001",
    "TEST-TRACEABILITY-VALIDATOR",
)
STAGE_ORDER = (
    "governance",
    "contract",
    "dataset",
    "model",
    "evaluation",
    "runtime",
    "planning",
    "monitoring",
    "p4_dynamic",
)
EXPECTED_CHECK_IDS = (
    "dependency-provider-identities",
    "governance-and-owner-bytes-frozen",
    "two-complete-owner-replays",
    "two-run-semantic-determinism",
    "cross-stage-lineage-closure",
    "evaluation-quality-and-standard-baseline",
    "default-off-and-exact-standard-fallback",
    "tamper-mixed-version-privacy-fail-closed",
    "p2-problem-solver-formal-validator-regression",
    "p4-dynamic-replanning-regression",
    "monitoring-default-disable-and-no-auto-action",
    "task-scope-and-forbidden-owner-boundary",
    "raw-safe-simulation-only-production-default-deny",
)
NEGATIVE_CASE_IDS = (
    "contract-mixed-version",
    "contract-identity-tamper",
    "low-confidence-standard-fallback",
    "runtime-lineage-tamper",
    "runtime-privacy-default-deny",
    "monitor-version-drift",
    "monitor-privacy-default-disable",
    "monitor-no-automatic-action",
    "formal-validator-c003-c010",
    "p4-tamper-coverage-plane",
)

_ALLOWED_TRACKED_PATHS = frozenset(
    {
        "README.md",
        "conftest.py",
        "docs/README.md",
        "docs/architecture/end-to-end-planning-flow.md",
        "docs/core/capability-matrix.md",
        "docs/simulation/benchmark-harness.md",
        "tests/p6/p6_duration_gate_report.py",
        "tests/p6/test_p6_duration_gate.py",
        "tests/p6/test_p6_duration_gate_rejections.py",
    }
)
_GOVERNANCE_FILES: Mapping[str, tuple[str, ...]] = {
    "docs/adr/ADR-0016-ai-duration-data-model-governance.md": (
        "标准工时继续是唯一回退authority",
        "Promotion、retraining与rollback必须由人控制",
        "P2 formal Validator和P4 facts/HARD/freeze/ChangeReport",
    ),
    "docs/contracts/duration-prediction-governance.md": (
        "TASK-P6-08 aggregate monitoring governance projection",
        "Standard duration",
        "Synthetic、provider success、local Gate或P6 Exit不能证明Production",
    ),
    "docs/contracts/duration-prediction-machine-contract.md": (
        "TASK-P6-08 deterministic aggregate monitoring",
        "TASK-P6-07 default-off Planning ingress",
        "TASK-P6-09 and later require separate authorization",
    ),
    "docs/contracts/planning-problem.md": (
        "TASK-P6-07 default-off duration selection",
        "planning-problem-builder.v2",
        "任何非duration差异",
    ),
}
_STAGE_CONTRACTS: Mapping[str, tuple[str, str, int]] = {
    "governance": (GOVERNANCE_REPORT_VERSION, "TASK-P6-01", 5),
    "contract": ("p6-duration-contract-report.v1", "TASK-P6-02", 10),
    "dataset": ("p6-duration-dataset-report.v1", "TASK-P6-03", 10),
    "model": ("p6-duration-model-report.v1", "TASK-P6-04", 10),
    "evaluation": ("p6-duration-evaluation-check-report.v1", "TASK-P6-05", 8),
    "runtime": ("p6-duration-runtime-check-report.v1", "TASK-P6-06", 12),
    "planning": ("p6-planning-integration-report.v1", "TASK-P6-07", 11),
    "monitoring": ("p6-duration-monitoring-check-report.v1", "TASK-P6-08", 12),
    "p4_dynamic": ("p4-disruption-replay-report.v1", "TASK-P4-10", 8),
}
_BOUNDARIES: JsonObject = {
    "data_plane": "SIMULATION_TEST_ONLY",
    "default_enabled": False,
    "standard_duration_authority": "UNCHANGED_EXACT_FALLBACK",
    "planning_authority": "ADVISORY_DURATION_ONLY",
    "routing_resource_hard_constraints_state_weights": "UNCHANGED",
    "p2_formal_validator": "FRESH_INDEPENDENT_REQUIRED",
    "p4_facts_freeze_stability_change_report_simulator": "PRESERVED",
    "automatic_retraining_promotion_rollback": "NONE",
    "external_alert_persistence_api_ui": "NONE",
    "schema_migration_dependency_lock_workflow_change": "NONE",
    "owner_semantics_changed": False,
    "p6_exit_decision": "NOT_MADE",
    "p6_10_started": False,
    "p7_reality_calibration_entered": False,
    "production_authorized": False,
    "uat_deployment_capacity_sla_claimed": False,
}

_DEPENDENCIES: tuple[JsonObject, ...] = (
    {
        "task_id": "TASK-P6-07",
        "manifest_schema": "provider-evidence-manifest.v1",
        "implementation_sha": "e5d63fcf54c841ed93ef7c62084bcdeeda63abd4",
        "run_id": 33512511801,
        "required_job_id": 99874314670,
        "required_check": "validate",
        "required_app_id": 15368,
        "artifacts": [
            {
                "id": 9802402997,
                "name": "plantnexus-ci-backend-33512511801",
                "sha256": "e50710b5bff26b364865c831a6b70876fd5dfd5f8cad22eca06b471ecaf823c1",
                "expires_at": "2026-11-30T13:17:40Z",
            },
            {
                "id": 9802549913,
                "name": "plantnexus-ci-evidence-33512511801",
                "sha256": "8db9b96da70d9be20bf495ba61ef43396c2bd72ad760fa57bfe96815c4fa4cce",
                "expires_at": "2026-11-30T13:17:40Z",
            },
            {
                "id": 9802216672,
                "name": "plantnexus-ci-preflight-33512511801",
                "sha256": "6ae30b38bbaa91b3454e29a7a860f0e697e2aec9c3a792f7bc20d5c52357be57",
                "expires_at": "2026-11-30T13:17:40Z",
            },
            {
                "id": 9802210502,
                "name": "plantnexus-ci-profile-33512511801",
                "sha256": "c4f460a121a29f89b8fcce985bb58d8038d4103f45e37bcedd0acf2b1d816c6f",
                "expires_at": "2026-11-30T13:17:40Z",
            },
        ],
        "issues": [],
    },
    {
        "task_id": "TASK-P6-08",
        "manifest_schema": "provider-evidence-manifest.v1",
        "implementation_sha": DIFF_BASE,
        "run_id": 33522642120,
        "required_job_id": 99908691371,
        "required_check": "validate",
        "required_app_id": 15368,
        "artifacts": [
            {
                "id": 9806507757,
                "name": "plantnexus-ci-backend-33522642120",
                "sha256": "5c94655086d177fbda633f7a8d8394cdeccd471779722adc68b7a01a88d7e4e3",
                "expires_at": "2026-11-30T14:56:36Z",
            },
            {
                "id": 9806698308,
                "name": "plantnexus-ci-evidence-33522642120",
                "sha256": "d2c0862de67d9d09ee7e33e4cad9e4505a011a1726a64a154f0a7b36accfbf59",
                "expires_at": "2026-11-30T14:56:36Z",
            },
            {
                "id": 9806327925,
                "name": "plantnexus-ci-preflight-33522642120",
                "sha256": "7b58daa018d79abd4e4e41c873bbf1a139bc1dd1d3c300a6e37de5db2ccb7c61",
                "expires_at": "2026-11-30T14:56:36Z",
            },
            {
                "id": 9806320723,
                "name": "plantnexus-ci-profile-33522642120",
                "sha256": "91d0f645614493952cc3090209d3a3813ba0cfb391fabc0e638969b6ea8299af",
                "expires_at": "2026-11-30T14:56:36Z",
            },
        ],
        "issues": [],
    },
)


class P6DurationGateContractError(ValueError):
    """A strict P6 Gate report or manifest violated its machine contract."""


class P6DurationGateExecutionError(RuntimeError):
    """An owner stage failed during a fresh P6 Gate replay."""

    def __init__(self, stage: str, error: Exception) -> None:
        super().__init__(f"{stage}: {type(error).__name__}: {error}")
        self.stage = stage
        self.error = error


def _fail(field: str, message: str) -> Never:
    raise P6DurationGateContractError(f"{field}: {message}")


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, Mapping):
        _fail(field, "expected an object")
    return dict(value)


def _items(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(field, "expected an array")
    return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_json(value: object) -> str:
    return f"sha256:{sha256(_canonical_bytes(value)).hexdigest()}"


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _with_fingerprint(value: Mapping[str, object], field: str) -> JsonObject:
    result = dict(value)
    result[field] = _sha256_json(result)
    return result


def _git(root: Path, *arguments: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and completed.returncode != 0:
        raise P6DurationGateContractError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _code_commit(root: Path) -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT") or _git(root, "rev-parse", "HEAD")
    if not (
        len(value) == 40
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    ):
        _fail("code_commit", "expected a full lowercase Git SHA")
    return value


def _generated_at() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _check(check_id: str, evidence: object) -> JsonObject:
    return {"check_id": check_id, "status": "PASS", "evidence": evidence}


def _check_id(check: Mapping[str, object], field: str) -> str:
    value = check.get("check_id", check.get("name"))
    if not isinstance(value, str) or not value:
        _fail(field, "missing check_id/name")
    return value


def _check_result(check: Mapping[str, object], field: str) -> str:
    value = check.get("result", check.get("status"))
    if value != "PASS":
        _fail(field, "owner check is not PASS")
    return cast(str, value)


def _find_check(report: Mapping[str, object], check_id: str) -> JsonObject:
    for index, raw in enumerate(_items(report.get("checks"), "checks")):
        check = _object(raw, f"checks[{index}]")
        if _check_id(check, f"checks[{index}]") == check_id:
            return check
    _fail("checks", f"missing {check_id}")


def _check_evidence(check: Mapping[str, object]) -> object:
    for key in ("evidence", "details", "observation"):
        if key in check:
            return check[key]
    return None


def _stage_version(report: Mapping[str, object]) -> object:
    return report.get("report_version", report.get("schema_version"))


def _owner_check_count(report: Mapping[str, object]) -> int:
    return len(_items(report.get("checks"), "checks"))


def _validate_owner_stage(
    stage: str, report: Mapping[str, object], code_commit: str
) -> None:
    expected_version, expected_task, expected_checks = _STAGE_CONTRACTS[stage]
    if _stage_version(report) != expected_version:
        _fail(f"{stage}.version", f"expected {expected_version}")
    if report.get("task_id") != expected_task:
        _fail(f"{stage}.task_id", f"expected {expected_task}")
    if report.get("status", report.get("result")) != "PASS":
        _fail(f"{stage}.status", "owner report is not PASS")
    if "result" in report and report.get("result") != "PASS":
        _fail(f"{stage}.result", "owner report result is not PASS")
    if report.get("issues") != []:
        _fail(f"{stage}.issues", "owner report contains issues")
    if "blocking_gaps" in report and report.get("blocking_gaps") != []:
        _fail(f"{stage}.blocking_gaps", "owner report contains blocking gaps")
    checks = _items(report.get("checks"), f"{stage}.checks")
    if len(checks) != expected_checks or (
        "check_count" in report and report.get("check_count") != expected_checks
    ):
        _fail(f"{stage}.check_count", f"expected {expected_checks}")
    identities: list[str] = []
    for index, raw in enumerate(checks):
        check = _object(raw, f"{stage}.checks[{index}]")
        identities.append(_check_id(check, f"{stage}.checks[{index}]"))
        _check_result(check, f"{stage}.checks[{index}]")
    if len(set(identities)) != len(identities):
        _fail(f"{stage}.checks", "duplicate check identity")
    if "code_commit" in report and report.get("code_commit") not in {
        code_commit,
        "uncommitted",
    }:
        _fail(f"{stage}.code_commit", "owner report commit does not match Gate")


def _dependency_evidence(root: Path) -> list[JsonObject]:
    activation = datetime.fromisoformat(ACTIVATION_VERIFIED_AT.replace("Z", "+00:00"))
    evidence = deepcopy(list(_DEPENDENCIES))
    for index, item in enumerate(evidence):
        if (
            item.get("manifest_schema") != "provider-evidence-manifest.v1"
            or item.get("required_check") != "validate"
            or item.get("required_app_id") != 15368
            or item.get("issues") != []
        ):
            _fail(f"dependencies[{index}]", "provider identity drifted")
        commit = item.get("implementation_sha")
        if not isinstance(commit, str):
            _fail(f"dependencies[{index}].implementation_sha", "missing SHA")
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            _fail(f"dependencies[{index}].implementation_sha", "not a HEAD ancestor")
        artifacts = _items(item.get("artifacts"), f"dependencies[{index}].artifacts")
        if len(artifacts) != 4:
            _fail(f"dependencies[{index}].artifacts", "expected four artifacts")
        for artifact_index, raw in enumerate(artifacts):
            artifact = _object(
                raw, f"dependencies[{index}].artifacts[{artifact_index}]"
            )
            digest = artifact.get("sha256")
            if not (
                isinstance(digest, str)
                and len(digest) == 64
                and all(character in "0123456789abcdef" for character in digest)
            ):
                _fail(
                    f"dependencies[{index}].artifacts[{artifact_index}].sha256",
                    "invalid digest",
                )
            expires = artifact.get("expires_at")
            if not isinstance(expires, str):
                _fail(
                    f"dependencies[{index}].artifacts[{artifact_index}].expires_at",
                    "missing expiry",
                )
            expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if expiry <= activation:
                _fail(
                    f"dependencies[{index}].artifacts[{artifact_index}].expires_at",
                    "artifact was expired at activation",
                )
        item["artifact_count"] = len(artifacts)
        item["activation_verified_at"] = ACTIVATION_VERIFIED_AT
        item["activation_result"] = "PASS"
    return evidence


def _governance_report(root: Path, code_commit: str) -> JsonObject:
    files: list[JsonObject] = []
    marker_checks: list[JsonObject] = []
    for index, (relative, markers) in enumerate(_GOVERNANCE_FILES.items(), start=1):
        path = root / relative
        if not path.is_file():
            _fail("governance", f"missing {relative}")
        current = path.read_bytes()
        base = subprocess.run(
            ["git", "show", f"{DIFF_BASE}:{relative}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if base.returncode != 0 or base.stdout != current:
            _fail("governance", f"frozen owner changed: {relative}")
        text = current.decode("utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            _fail("governance", f"{relative} missing semantic markers")
        files.append({"path": relative, "sha256": _sha256_bytes(current)})
        marker_checks.append(
            _check(
                f"frozen-governance-owner-{index}",
                {"path": relative, "marker_count": len(markers)},
            )
        )
    checks = [
        *marker_checks,
        _check(
            "standard-authority-privacy-human-control-boundary",
            {
                "standard_duration_authority": "UNCHANGED",
                "production_authorized": False,
                "promotion_or_rollback_automatic": False,
                "formal_validator_independent": True,
            },
        ),
    ]
    return {
        "report_version": GOVERNANCE_REPORT_VERSION,
        "task_id": "TASK-P6-01",
        "diff_base": DIFF_BASE,
        "code_commit": code_commit,
        "status": "PASS",
        "check_count": len(checks),
        "checks": checks,
        "files": files,
        "counts": {"frozen_governance_files": len(files), "semantic_markers": 12},
        "boundaries": {
            "standard_duration_authority": "UNCHANGED",
            "production_authorized": False,
            "p7_entered": False,
            "owner_semantics_changed": False,
        },
        "issues": [],
    }


_NOISE_KEYS = frozenset(
    {
        "allocated_wall_time_seconds",
        "code_commit",
        "elapsed_microseconds",
        "finished_at_utc",
        "generated_at",
        "generated_at_utc",
        "max_latency_ns",
        "memory_peak_mb",
        "model_build_seconds",
        "p50_latency_ns",
        "p6_median_ns",
        "p6_p95_ns",
        "p95_latency_ns",
        "peak_allocated_bytes",
        "report_fingerprint",
        "report_id",
        "replay_fingerprint",
        "run_fingerprint",
        "solve_seconds",
        "stage_microseconds",
        "standard_median_ns",
        "standard_p95_ns",
        "started_at_utc",
        "total_seconds",
        "validation_seconds",
    }
)


def _strip_runtime_noise(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_runtime_noise(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in _NOISE_KEYS
        }
    if isinstance(value, list):
        return [_strip_runtime_noise(item) for item in value]
    return value


def _stable_checks(
    report: Mapping[str, object], *, exclude: frozenset[str] = frozenset()
) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for index, raw in enumerate(_items(report.get("checks"), "checks")):
        check = _object(raw, f"checks[{index}]")
        identity = _check_id(check, f"checks[{index}]")
        if identity in exclude:
            continue
        rows.append(
            {
                "check_id": identity,
                "result": _check_result(check, f"checks[{index}]"),
                "evidence": _strip_runtime_noise(_check_evidence(check)),
            }
        )
    return rows


def _monitor_decisions(report: Mapping[str, object]) -> JsonObject:
    reports = _object(report.get("monitor_reports"), "monitor_reports")
    selected: JsonObject = {}
    for name in (
        "healthy",
        "inclusive_boundary",
        "fallback_breach",
        "privacy_default_disable",
    ):
        row = _object(reports.get(name), f"monitor_reports.{name}")
        selected[name] = _strip_runtime_noise(
            {
                "result": row.get("result"),
                "counts": row.get("counts"),
                "metrics": row.get("metrics"),
                "thresholds": row.get("thresholds"),
                "version_checks": row.get("version_checks"),
                "monitoring_decision": row.get("monitoring_decision"),
                "privacy_retention": row.get("privacy_retention"),
            }
        )
    return selected


def _stage_projection(stage: str, report: Mapping[str, object]) -> JsonObject:
    base: JsonObject = {
        "version": _stage_version(report),
        "task_id": report.get("task_id"),
        "status": report.get("status", report.get("result")),
        "check_count": _owner_check_count(report),
        "counts": _strip_runtime_noise(report.get("counts")),
        "boundaries": _strip_runtime_noise(report.get("boundaries")),
    }
    if stage == "governance":
        base["files"] = report.get("files")
        base["checks"] = _stable_checks(report)
    elif stage == "contract":
        base.update(
            {
                "schema_set_version": report.get("schema_set_version"),
                "artifacts": report.get("artifacts"),
                "fallback_reasons": report.get("fallback_reasons"),
                "checks": _stable_checks(report),
            }
        )
    elif stage in {"dataset", "model"}:
        base.update(
            {
                "schema_set_version": report.get("schema_set_version"),
                "artifacts": report.get("artifacts"),
                "checks": _stable_checks(report),
            }
        )
    elif stage == "evaluation":
        base.update(
            {
                "profile_reference": report.get("profile_reference"),
                "input_lineage": report.get("input_lineage"),
                "measurement_report_reference": report.get(
                    "measurement_report_reference"
                ),
                "metrics": report.get("metrics"),
                "gate_decision": report.get("gate_decision"),
                "fallback_summary": report.get("fallback_summary"),
                "safe_artifact_boundary": report.get("safe_artifact_boundary"),
                "checks": _stable_checks(report),
            }
        )
    elif stage == "runtime":
        base.update(
            {
                "identities": report.get("identities"),
                "fallback_summary": report.get("fallback_summary"),
                "safe_artifact_boundary": report.get("safe_artifact_boundary"),
                "checks": _stable_checks(
                    report, exclude=frozenset({"development-resource-profile"})
                ),
            }
        )
    elif stage == "planning":
        base["checks"] = _stable_checks(
            report,
            exclude=frozenset({"development-standard-vs-p6-runtime-observation"}),
        )
    elif stage == "monitoring":
        base.update(
            {
                "identities": report.get("identities"),
                "safe_artifact_boundary": report.get("safe_artifact_boundary"),
                "monitor_decisions": _monitor_decisions(report),
                "checks": _stable_checks(
                    report, exclude=frozenset({"development-overhead-observation"})
                ),
            }
        )
    elif stage == "p4_dynamic":
        scenario = _object(report.get("scenario_manifest"), "scenario_manifest")
        base.update(
            {
                "scenario_manifest": {
                    key: value
                    for key, value in scenario.items()
                    if key not in {"run_fingerprint", "replay_fingerprint"}
                },
                "checks": _stable_checks(report),
            }
        )
    else:
        _fail("stage", f"unknown {stage}")
    return cast(JsonObject, _strip_runtime_noise(base))


def _performance_observations(reports: Mapping[str, JsonObject]) -> JsonObject:
    planning_check = _find_check(
        reports["planning"], "development-standard-vs-p6-runtime-observation"
    )
    return {
        "evaluation_metrics": reports["evaluation"].get("metrics"),
        "runtime": reports["runtime"].get("performance"),
        "planning_standard_vs_p6": _check_evidence(planning_check),
        "monitoring": reports["monitoring"].get("performance"),
        "p4_dynamic_counts": reports["p4_dynamic"].get("counts"),
        "interpretation": "DEVELOPMENT_OBSERVATION_ONLY_NOT_PRODUCTION_SLA",
    }


def _cross_stage_lineage(reports: Mapping[str, JsonObject]) -> JsonObject:
    dataset_artifacts = _object(reports["dataset"].get("artifacts"), "dataset.artifacts")
    dataset_manifest = _object(
        dataset_artifacts.get("dataset_manifest"), "dataset.artifacts.dataset_manifest"
    )
    dataset_bundle = _object(
        dataset_artifacts.get("expected_bundle"), "dataset.artifacts.expected_bundle"
    )
    model_artifacts = _object(reports["model"].get("artifacts"), "model.artifacts")
    model_dataset = _object(
        model_artifacts.get("dataset_bundle"), "model.artifacts.dataset_bundle"
    )
    model_artifact = _object(
        model_artifacts.get("model_artifact"), "model.artifacts.model_artifact"
    )
    model_manifest = _object(
        model_artifacts.get("model_manifest"), "model.artifacts.model_manifest"
    )
    evaluation = reports["evaluation"]
    evaluation_lineage = _object(
        evaluation.get("input_lineage"), "evaluation.input_lineage"
    )
    evaluation_gate = _object(evaluation.get("gate_report"), "evaluation.gate_report")
    evaluation_measurement = _object(
        evaluation.get("measurement_report_reference"),
        "evaluation.measurement_report_reference",
    )
    runtime_ids = _object(reports["runtime"].get("identities"), "runtime.identities")
    planning_accepted = _object(
        _check_evidence(
            _find_check(
                reports["planning"], "accepted-model-candidate-and-complete-lineage"
            )
        ),
        "planning.accepted",
    )
    monitor_ids = _object(
        reports["monitoring"].get("identities"), "monitoring.identities"
    )
    expected_equalities = (
        (
            dataset_bundle.get("bundle_fingerprint"),
            model_dataset.get("fingerprint"),
            "dataset bundle → model",
        ),
        (
            dataset_bundle.get("bundle_fingerprint"),
            evaluation_lineage.get("dataset_bundle_fingerprint"),
            "dataset bundle → evaluation",
        ),
        (
            dataset_manifest.get("fingerprint"),
            evaluation_lineage.get("dataset_manifest_fingerprint"),
            "dataset manifest → evaluation",
        ),
        (
            model_artifact.get("digest"),
            evaluation_lineage.get("model_artifact_digest"),
            "model artifact → evaluation",
        ),
        (
            model_artifact.get("digest"),
            runtime_ids.get("model_artifact_digest"),
            "model artifact → runtime",
        ),
        (
            model_manifest.get("fingerprint"),
            evaluation_lineage.get("model_manifest_fingerprint"),
            "model manifest → evaluation",
        ),
        (
            model_manifest.get("fingerprint"),
            runtime_ids.get("model_manifest_fingerprint"),
            "model manifest → runtime",
        ),
        (
            evaluation_gate.get("gate_report_fingerprint"),
            runtime_ids.get("offline_gate_report_fingerprint"),
            "evaluation Gate → runtime",
        ),
        (
            evaluation_measurement.get("evaluation_report_fingerprint"),
            runtime_ids.get("measurement_report_fingerprint"),
            "evaluation measurement → runtime",
        ),
        (
            runtime_ids.get("runtime_policy_fingerprint"),
            planning_accepted.get("policy_fingerprint"),
            "runtime policy → Planning",
        ),
        (
            runtime_ids.get("runtime_policy_fingerprint"),
            monitor_ids.get("runtime_policy_fingerprint"),
            "runtime policy → monitoring",
        ),
        (
            runtime_ids.get("runtime_code_digest"),
            monitor_ids.get("runtime_code_digest"),
            "runtime code → monitoring",
        ),
    )
    for left, right, name in expected_equalities:
        if not isinstance(left, str) or left != right:
            _fail("cross_stage_lineage", f"{name} mismatch")
    return {
        "status": "PASS",
        "equality_count": len(expected_equalities),
        "dataset_bundle_fingerprint": dataset_bundle["bundle_fingerprint"],
        "dataset_manifest_fingerprint": dataset_manifest["fingerprint"],
        "model_artifact_digest": model_artifact["digest"],
        "model_manifest_fingerprint": model_manifest["fingerprint"],
        "evaluation_gate_fingerprint": evaluation_gate["gate_report_fingerprint"],
        "measurement_report_fingerprint": evaluation_measurement[
            "evaluation_report_fingerprint"
        ],
        "runtime_policy_fingerprint": runtime_ids["runtime_policy_fingerprint"],
        "monitoring_policy_fingerprint": monitor_ids[
            "monitoring_policy_fingerprint"
        ],
        "selected_problem_hash": planning_accepted["selected_problem_hash"],
        "standard_problem_hash": planning_accepted["standard_problem_hash"],
    }


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _run_stage(stage: str, operation: Any) -> JsonObject:
    try:
        return dict(operation())
    except Exception as error:
        raise P6DurationGateExecutionError(stage, error) from error


def _run_owner_replay(
    root: Path,
    *,
    replay_index: int,
    code_commit: str,
    subreport_dir: Path | None,
) -> tuple[JsonObject, Mapping[str, JsonObject]]:
    reports: dict[str, JsonObject] = {}
    reports["governance"] = _run_stage(
        "governance", lambda: _governance_report(root, code_commit)
    )
    reports["contract"] = _run_stage(
        "contract", lambda: run_contract_checks(root)
    )
    reports["dataset"] = _run_stage("dataset", lambda: run_dataset_checks(root))
    reports["model"] = _run_stage("model", lambda: run_model_checks(root))
    reports["evaluation"] = _run_stage(
        "evaluation", lambda: run_evaluation_checks(root)
    )
    with TemporaryDirectory(prefix=f"p6-gate-{replay_index}-") as temporary:
        offline_path = Path(temporary) / "evaluation.json"
        _write_json(offline_path, reports["evaluation"])
        reports["runtime"] = _run_stage(
            "runtime", lambda: run_runtime_checks(root, offline_path)
        )
    reports["planning"] = _run_stage(
        "planning", lambda: run_planning_integration_checks(root)
    )
    reports["monitoring"] = _run_stage(
        "monitoring", lambda: run_monitoring_checks(root)
    )
    reports["p4_dynamic"] = _run_stage(
        "p4_dynamic", lambda: run_disruption_replay_checks(root)
    )

    if tuple(reports) != STAGE_ORDER:
        _fail("stage_order", "owner replay stage order drifted")
    projections: JsonObject = {}
    fingerprints: JsonObject = {}
    summaries: JsonObject = {}
    for stage in STAGE_ORDER:
        report = reports[stage]
        _validate_owner_stage(stage, report, code_commit)
        projection = _stage_projection(stage, report)
        fingerprint = _sha256_json(projection)
        projections[stage] = projection
        fingerprints[stage] = fingerprint
        summaries[stage] = {
            "version": _stage_version(report),
            "task_id": report.get("task_id"),
            "status": "PASS",
            "check_count": _owner_check_count(report),
            "raw_safe_report_sha256": _sha256_json(report),
            "semantic_fingerprint": fingerprint,
            "semantic_projection": projection,
        }
        if subreport_dir is not None:
            _write_json(
                subreport_dir / f"replay-{replay_index}" / f"{stage}.json",
                report,
            )
    lineage = _cross_stage_lineage(reports)
    fingerprints["combined"] = _sha256_json(projections)
    return (
        {
            "replay_index": replay_index,
            "status": "PASS",
            "stage_order": list(STAGE_ORDER),
            "raw_safe_subreports": summaries,
            "semantic_fingerprints": fingerprints,
            "cross_stage_lineage": lineage,
            "performance_observations": _performance_observations(reports),
        },
        reports,
    )


def _negative_evidence(reports: Mapping[str, JsonObject]) -> list[JsonObject]:
    planning_fallback = _object(
        _check_evidence(
            _find_check(
                reports["planning"],
                "low-unavailable-invalid-exact-standard-fallback",
            )
        ),
        "planning.fallback",
    )
    runtime_tamper = _object(
        _check_evidence(
            _find_check(reports["runtime"], "tamper-and-version-default-deny")
        ),
        "runtime.tamper",
    )
    runtime_privacy = _object(
        _check_evidence(
            _find_check(reports["runtime"], "privacy-and-authority-default-deny")
        ),
        "runtime.privacy",
    )
    monitor_version = _check_evidence(
        _find_check(reports["monitoring"], "version-drift-default-disable")
    )
    monitor_privacy = _object(
        _check_evidence(
            _find_check(reports["monitoring"], "privacy-redaction-aggregate-only")
        ),
        "monitoring.privacy",
    )
    monitor_auto = _object(
        _check_evidence(
            _find_check(
                reports["monitoring"], "standard-fallback-and-no-auto-action"
            )
        ),
        "monitoring.auto",
    )
    validator = _items(
        _check_evidence(
            _find_check(
                reports["planning"], "formal-validator-c003-c010-mutations"
            )
        ),
        "planning.validator_mutations",
    )
    p4_tamper = _check_evidence(
        _find_check(
            reports["p4_dynamic"], "tamper-coverage-and-plane-fail-closed"
        )
    )
    rows = [
        {
            "case_id": "contract-mixed-version",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": _check_evidence(
                _find_check(reports["contract"], "mixed_lineage_rejection")
            ),
        },
        {
            "case_id": "contract-identity-tamper",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": _check_evidence(
                _find_check(reports["contract"], "canonical_tamper_rejection")
            ),
        },
        {
            "case_id": "low-confidence-standard-fallback",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": planning_fallback,
        },
        {
            "case_id": "runtime-lineage-tamper",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": runtime_tamper,
        },
        {
            "case_id": "runtime-privacy-default-deny",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": runtime_privacy,
        },
        {
            "case_id": "monitor-version-drift",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": monitor_version,
        },
        {
            "case_id": "monitor-privacy-default-disable",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": monitor_privacy,
        },
        {
            "case_id": "monitor-no-automatic-action",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": monitor_auto,
        },
        {
            "case_id": "formal-validator-c003-c010",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": validator,
        },
        {
            "case_id": "p4-tamper-coverage-plane",
            "status": "REJECTED_AS_REQUIRED",
            "evidence": p4_tamper,
        },
    ]
    if tuple(row["case_id"] for row in rows) != NEGATIVE_CASE_IDS:
        _fail("negative_rejections", "case order drifted")
    fallback_reasons = planning_fallback.get("fallback_reasons")
    if fallback_reasons != [
        "LOW_CONFIDENCE",
        "PROVIDER_UNAVAILABLE",
        "INVALID_QUANTILES",
    ]:
        _fail("negative_rejections.low_confidence", "fallback reasons drifted")
    constraints = {
        _object(row, "validator mutation").get("constraint_id") for row in validator
    }
    if constraints != {"C-003", "C-010"}:
        _fail("negative_rejections.validator", "C-003/C-010 coverage drifted")
    if (
        runtime_tamper.get("gate_tamper") != "EVALUATION_GATE_NOT_PASSED"
        or runtime_tamper.get("model_version_tamper")
        != "MODEL_VERSION_INCOMPATIBLE"
        or runtime_privacy.get("privacy_fallback_reason")
        != "PRIVACY_GOVERNANCE_FAILED"
        or monitor_auto.get("automatic_actions") != 0
        or monitor_auto.get("runtime_fallback_reason") != "DRIFT_GATE_DISABLED"
    ):
        _fail("negative_rejections", "runtime/monitor fail-closed evidence drifted")
    return rows


def _working_tree_changed_paths(root: Path) -> list[str]:
    commands = (
        ("diff", "--name-only", f"{DIFF_BASE}..HEAD"),
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    changed: set[str] = set()
    for arguments in commands:
        output = _git(root, *arguments)
        changed.update(
            line.strip().replace("\\", "/")
            for line in output.splitlines()
            if line.strip()
        )
    return sorted(changed)


def _task_scope_paths(root: Path) -> tuple[list[str], str, str]:
    gate_source = "tests/p6/p6_duration_gate_report.py"
    introduction_output = _git(
        root,
        "log",
        "--diff-filter=A",
        "--format=%H",
        "--",
        gate_source,
        check=False,
    )
    introduction_commits = [
        line.strip() for line in introduction_output.splitlines() if line.strip()
    ]
    if introduction_commits:
        implementation_commit = introduction_commits[0]
        changed = _git(
            root,
            "diff",
            "--name-only",
            f"{DIFF_BASE}..{implementation_commit}",
        )
        return (
            sorted(
                line.strip().replace("\\", "/")
                for line in changed.splitlines()
                if line.strip()
            ),
            "GATE_INTRODUCTION_COMMIT",
            implementation_commit,
        )
    return _working_tree_changed_paths(root), "WORKING_TREE", _code_commit(root)


def _scope_evidence(root: Path) -> JsonObject:
    changed, source, implementation_commit = _task_scope_paths(root)
    unexpected = sorted(set(changed) - _ALLOWED_TRACKED_PATHS)
    missing = sorted(_ALLOWED_TRACKED_PATHS - set(changed))
    if unexpected:
        _fail("task_scope", f"paths outside exact allow-list: {unexpected}")
    if missing:
        _fail("task_scope", f"required Gate paths missing from diff: {missing}")
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
        "forbidden_owner_changes": 0,
    }


def _raw_safe_boundary(reports: Mapping[str, JsonObject]) -> JsonObject:
    evaluation = _object(
        reports["evaluation"].get("safe_artifact_boundary"),
        "evaluation.safe_artifact_boundary",
    )
    runtime = _object(
        reports["runtime"].get("safe_artifact_boundary"),
        "runtime.safe_artifact_boundary",
    )
    monitoring = _object(
        reports["monitoring"].get("safe_artifact_boundary"),
        "monitoring.safe_artifact_boundary",
    )
    required_false = (
        (evaluation, "labels_included"),
        (evaluation, "raw_rows_included"),
        (runtime, "feature_records_included"),
        (runtime, "labels_included"),
        (runtime, "raw_rows_included"),
        (runtime, "source_record_ids_included"),
        (monitoring, "feature_records_included"),
        (monitoring, "operation_or_resource_ids_included"),
        (monitoring, "raw_predictions_included"),
        (monitoring, "source_record_ids_included"),
    )
    for boundary, key in required_false:
        if boundary.get(key) is not False:
            _fail("raw_safe_boundary", f"{key} must be false")
    for stage in STAGE_ORDER:
        boundaries = reports[stage].get("boundaries")
        if isinstance(boundaries, Mapping) and boundaries.get(
            "production_authorized"
        ) is True:
            _fail("raw_safe_boundary", f"{stage} claimed Production authority")
    return {
        "status": "PASS",
        "p6_raw_rows_included": False,
        "p6_feature_records_included": False,
        "p6_labels_included": False,
        "p6_source_operation_resource_identifiers_included": False,
        "credentials_secrets_free_text_included": False,
        "subreports": "OWNER_REPORTS_ARE_SYNTHETIC_OR_AGGREGATE_SAFE_EVIDENCE",
        "production_authorized": False,
    }


def _evaluation_quality(reports: Mapping[str, JsonObject]) -> JsonObject:
    evaluation = reports["evaluation"]
    gate = _object(evaluation.get("gate_decision"), "evaluation.gate_decision")
    metrics = _object(evaluation.get("metrics"), "evaluation.metrics")
    overall = _object(metrics.get("overall"), "evaluation.metrics.overall")
    model_mae = _object(
        overall.get("model_mae_seconds"), "evaluation.metrics.overall.model_mae"
    )
    standard_mae = _object(
        overall.get("standard_duration_mae_seconds"),
        "evaluation.metrics.overall.standard_mae",
    )
    model_fraction = (
        cast(int, model_mae["numerator"]),
        cast(int, model_mae["denominator"]),
    )
    standard_fraction = (
        cast(int, standard_mae["numerator"]),
        cast(int, standard_mae["denominator"]),
    )
    if (
        gate.get("decision") != "READY_FOR_SIMULATION_RUNTIME"
        or gate.get("blocking_gaps") != []
        or model_fraction[0] * standard_fraction[1]
        >= standard_fraction[0] * model_fraction[1]
    ):
        _fail("evaluation_quality", "evaluation Gate or standard baseline drifted")
    return {
        "decision": gate["decision"],
        "blocking_gaps": [],
        "model_mae_seconds": model_mae,
        "standard_duration_mae_seconds": standard_mae,
        "model_strictly_better_than_standard": True,
        "interpretation": "SYNTHETIC_DEVELOPMENT_ONLY",
    }


def _default_off_fallback(reports: Mapping[str, JsonObject]) -> JsonObject:
    default_off = _object(
        _check_evidence(
            _find_check(
                reports["planning"], "default-off-standard-problem-byte-identity"
            )
        ),
        "planning.default_off",
    )
    fallback = _object(
        _check_evidence(
            _find_check(
                reports["planning"],
                "low-unavailable-invalid-exact-standard-fallback",
            )
        ),
        "planning.fallback",
    )
    runtime_fallback = _object(
        reports["runtime"].get("fallback_summary"), "runtime.fallback_summary"
    )
    if (
        not isinstance(default_off.get("problem_hash"), str)
        or fallback.get("problem_hash") != default_off.get("problem_hash")
        or runtime_fallback.get("all_select_exact_standard_duration") is not True
        or runtime_fallback.get("invalid_standard_authority")
        != "FAIL_CLOSED_NO_CARRIER"
    ):
        _fail("default_off_fallback", "standard Problem/fallback drifted")
    return {
        "default_enabled": False,
        "standard_problem_hash": default_off["problem_hash"],
        "fallback_problem_hash": fallback["problem_hash"],
        "fallback_reasons": fallback["fallback_reasons"],
        "registered_runtime_fallback_reasons": len(
            _items(runtime_fallback.get("reason_codes"), "runtime.reason_codes")
        ),
        "all_fallbacks_select_exact_standard_duration": True,
        "invalid_standard_authority": "FAIL_CLOSED_NO_CARRIER",
    }


def _aggregate_checks(
    *,
    dependencies: Sequence[Mapping[str, object]],
    replays: Sequence[Mapping[str, object]],
    first_reports: Mapping[str, JsonObject],
    negative_rejections: Sequence[Mapping[str, object]],
    semantic_consistency: Mapping[str, object],
    scope: Mapping[str, object],
    raw_safe: Mapping[str, object],
) -> list[JsonObject]:
    planning_counts = _object(first_reports["planning"].get("counts"), "planning.counts")
    p4_counts = _object(first_reports["p4_dynamic"].get("counts"), "p4.counts")
    monitor_counts = _object(
        first_reports["monitoring"].get("counts"), "monitoring.counts"
    )
    total_owner_checks = sum(contract[2] for contract in _STAGE_CONTRACTS.values())
    checks = [
        _check(
            EXPECTED_CHECK_IDS[0],
            {
                "tasks": [item.get("task_id") for item in dependencies],
                "implementations": [
                    item.get("implementation_sha") for item in dependencies
                ],
                "required_check": "validate",
                "required_app_id": 15368,
                "artifact_count": sum(
                    cast(int, item.get("artifact_count", 0)) for item in dependencies
                ),
                "activation_verified_at": ACTIVATION_VERIFIED_AT,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[1],
            {
                "frozen_files": len(_GOVERNANCE_FILES),
                "standard_duration_authority": "UNCHANGED",
                "owner_semantics_changed": False,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[2],
            {
                "repeat_count": len(replays),
                "stage_order": list(STAGE_ORDER),
                "owner_checks_per_replay": total_owner_checks,
                "owner_checks_total": total_owner_checks * len(replays),
            },
        ),
        _check(EXPECTED_CHECK_IDS[3], dict(semantic_consistency)),
        _check(
            EXPECTED_CHECK_IDS[4],
            _object(replays[0].get("cross_stage_lineage"), "replay.lineage"),
        ),
        _check(EXPECTED_CHECK_IDS[5], _evaluation_quality(first_reports)),
        _check(EXPECTED_CHECK_IDS[6], _default_off_fallback(first_reports)),
        _check(
            EXPECTED_CHECK_IDS[7],
            {
                "case_ids": [row.get("case_id") for row in negative_rejections],
                "case_count": len(negative_rejections),
                "all_rejected_as_required": True,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[8],
            {
                "fresh_validator_passes": planning_counts["fresh_validator_passes"],
                "formal_validator_mutations": planning_counts[
                    "formal_validator_mutations"
                ],
                "constraint_ids": ["C-003", "C-010"],
                "p2_problem_and_solver_replayed": True,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[9],
            {
                "scenario_steps": p4_counts["scenario_steps"],
                "standard_events": p4_counts["standard_events"],
                "fresh_validator_passes": p4_counts["fresh_validator_passes"],
                "complete_change_reports": p4_counts["complete_change_reports"],
                "negative_vectors": p4_counts["negative_vectors"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[10],
            {
                "drift_scenarios": monitor_counts["drift_scenarios"],
                "invalid_or_tamper_scenarios": monitor_counts[
                    "invalid_or_tamper_scenarios"
                ],
                "automatic_actions": monitor_counts["automatic_actions"],
                "runtime_fallback_reason": "DRIFT_GATE_DISABLED",
            },
        ),
        _check(EXPECTED_CHECK_IDS[11], dict(scope)),
        _check(EXPECTED_CHECK_IDS[12], dict(raw_safe)),
    ]
    if tuple(check["check_id"] for check in checks) != EXPECTED_CHECK_IDS:
        _fail("checks", "aggregate check order drifted")
    return checks


def run_p6_duration_vertical_slice_gate(
    *,
    root: Path,
    repeat: int = 2,
    subreport_dir: Path | None = None,
) -> JsonObject:
    """Fresh-run the complete P6 owner chain and applicable P2/P4 regressions."""

    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat != 2:
        _fail("repeat", "TASK-P6-09 requires exactly two complete replays")
    root = root.resolve()
    code_commit = _code_commit(root)
    dependencies = _dependency_evidence(root)
    scope = _scope_evidence(root)
    replays: list[JsonObject] = []
    first_reports: Mapping[str, JsonObject] | None = None
    for index in range(1, repeat + 1):
        replay, reports = _run_owner_replay(
            root,
            replay_index=index,
            code_commit=code_commit,
            subreport_dir=subreport_dir,
        )
        replays.append(replay)
        if first_reports is None:
            first_reports = reports
    if first_reports is None:
        _fail("replays", "no owner replay executed")

    stage_fingerprints: JsonObject = {
        stage: [
            _object(replay["semantic_fingerprints"], "semantic_fingerprints")[
                stage
            ]
            for replay in replays
        ]
        for stage in STAGE_ORDER
    }
    combined = [
        _object(replay["semantic_fingerprints"], "semantic_fingerprints")[
            "combined"
        ]
        for replay in replays
    ]
    unstable = [
        stage
        for stage, values in stage_fingerprints.items()
        if len(set(cast(list[str], values))) != 1
    ]
    if len(set(cast(list[str], combined))) != 1 or unstable:
        _fail("semantic_consistency", f"replay drift: {unstable}")
    semantic_consistency = {
        "status": "PASS",
        "repeat_count": repeat,
        "stage_fingerprints": stage_fingerprints,
        "combined_fingerprints": combined,
        "unique_combined_fingerprints": 1,
        "runtime_noise_policy": (
            "TIMESTAMPS_CODE_COMMIT_REPORT_IDS_AND_DEVELOPMENT_PERFORMANCE_"
            "OBSERVATIONS_RETAINED_BUT_EXCLUDED_FROM_SEMANTIC_COMPARISON"
        ),
    }
    negative_rejections = _negative_evidence(first_reports)
    raw_safe = _raw_safe_boundary(first_reports)
    checks = _aggregate_checks(
        dependencies=dependencies,
        replays=replays,
        first_reports=first_reports,
        negative_rejections=negative_rejections,
        semantic_consistency=semantic_consistency,
        scope=scope,
        raw_safe=raw_safe,
    )
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "generated_at_utc": _generated_at(),
        "validation_profile": VALIDATION_PROFILE,
        "status": "PASS",
        "impact_rules": list(IMPACT_RULES),
        "test_ids": list(TEST_IDS),
        "dependency_evidence": dependencies,
        "repeat_count": repeat,
        "stage_order": list(STAGE_ORDER),
        "owner_replays": replays,
        "semantic_consistency": semantic_consistency,
        "negative_rejections": negative_rejections,
        "scope_evidence": scope,
        "raw_safe_boundary": raw_safe,
        "checks": checks,
        "check_count": len(checks),
        "counts": {
            "complete_replays": repeat,
            "owner_stages_per_replay": len(STAGE_ORDER),
            "owner_stage_executions": repeat * len(STAGE_ORDER),
            "owner_checks_per_replay": sum(
                contract[2] for contract in _STAGE_CONTRACTS.values()
            ),
            "owner_checks_total": repeat
            * sum(contract[2] for contract in _STAGE_CONTRACTS.values()),
            "negative_rejections": len(negative_rejections),
            "p2_fresh_validator_passes_per_replay": 3,
            "p4_fresh_validator_passes_per_replay": 5,
            "p4_dynamic_scenario_steps_per_replay": 5,
        },
        "issues": [],
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
    }
    report = _with_fingerprint(report, "report_fingerprint")
    validate_p6_duration_vertical_slice_report(report)
    return report


def validate_p6_duration_vertical_slice_report(
    report: Mapping[str, object],
) -> None:
    """Validate a successful strict TASK-P6-09 Gate report."""

    expected_keys = {
        "report_version",
        "task_id",
        "code_commit",
        "diff_base",
        "generated_at_utc",
        "validation_profile",
        "status",
        "impact_rules",
        "test_ids",
        "dependency_evidence",
        "repeat_count",
        "stage_order",
        "owner_replays",
        "semantic_consistency",
        "negative_rejections",
        "scope_evidence",
        "raw_safe_boundary",
        "checks",
        "check_count",
        "counts",
        "issues",
        "blocking_gaps",
        "boundaries",
        "report_fingerprint",
    }
    if set(report) != expected_keys:
        _fail("$", f"expected exact keys; got {sorted(report)}")
    for key, expected in (
        ("report_version", REPORT_VERSION),
        ("task_id", TASK_ID),
        ("diff_base", DIFF_BASE),
        ("validation_profile", VALIDATION_PROFILE),
        ("status", "PASS"),
        ("impact_rules", list(IMPACT_RULES)),
        ("test_ids", list(TEST_IDS)),
        ("repeat_count", 2),
        ("stage_order", list(STAGE_ORDER)),
        ("issues", []),
        ("blocking_gaps", []),
        ("boundaries", _BOUNDARIES),
    ):
        if report.get(key) != expected:
            _fail(key, f"expected {expected!r}")
    code_commit = report.get("code_commit")
    if not (
        isinstance(code_commit, str)
        and len(code_commit) == 40
        and all(character in "0123456789abcdef" for character in code_commit)
    ):
        _fail("code_commit", "expected full lowercase SHA")
    projection = dict(report)
    fingerprint = projection.pop("report_fingerprint")
    if fingerprint != _sha256_json(projection):
        _fail("report_fingerprint", "does not match canonical report projection")

    dependencies = _items(report.get("dependency_evidence"), "dependency_evidence")
    if len(dependencies) != 2:
        _fail("dependency_evidence", "expected P6-07 and P6-08")
    for index, expected in enumerate(_DEPENDENCIES):
        dependency = _object(dependencies[index], f"dependency_evidence[{index}]")
        for key in (
            "task_id",
            "manifest_schema",
            "implementation_sha",
            "run_id",
            "required_job_id",
            "required_check",
            "required_app_id",
            "artifacts",
            "issues",
        ):
            if dependency.get(key) != expected.get(key):
                _fail(f"dependency_evidence[{index}].{key}", "identity drifted")
        if (
            dependency.get("artifact_count") != 4
            or dependency.get("activation_verified_at") != ACTIVATION_VERIFIED_AT
            or dependency.get("activation_result") != "PASS"
        ):
            _fail(f"dependency_evidence[{index}]", "activation evidence drifted")

    replays = _items(report.get("owner_replays"), "owner_replays")
    if len(replays) != 2:
        _fail("owner_replays", "expected exactly two")
    recomputed_stage: dict[str, list[str]] = {stage: [] for stage in STAGE_ORDER}
    recomputed_combined: list[str] = []
    for replay_index, raw_replay in enumerate(replays, start=1):
        replay = _object(raw_replay, f"owner_replays[{replay_index - 1}]")
        if (
            replay.get("replay_index") != replay_index
            or replay.get("status") != "PASS"
            or replay.get("stage_order") != list(STAGE_ORDER)
        ):
            _fail(f"owner_replays[{replay_index - 1}]", "identity/status drifted")
        summaries = _object(
            replay.get("raw_safe_subreports"),
            f"owner_replays[{replay_index - 1}].raw_safe_subreports",
        )
        fingerprints = _object(
            replay.get("semantic_fingerprints"),
            f"owner_replays[{replay_index - 1}].semantic_fingerprints",
        )
        if set(summaries) != set(STAGE_ORDER) or set(fingerprints) != {
            *STAGE_ORDER,
            "combined",
        }:
            _fail(f"owner_replays[{replay_index - 1}]", "stage set drifted")
        projections: JsonObject = {}
        for stage in STAGE_ORDER:
            summary = _object(
                summaries[stage],
                f"owner_replays[{replay_index - 1}].{stage}",
            )
            expected_version, expected_task, expected_count = _STAGE_CONTRACTS[stage]
            if (
                summary.get("version") != expected_version
                or summary.get("task_id") != expected_task
                or summary.get("status") != "PASS"
                or summary.get("check_count") != expected_count
            ):
                _fail(
                    f"owner_replays[{replay_index - 1}].{stage}",
                    "owner contract drifted",
                )
            projection_value = _object(
                summary.get("semantic_projection"),
                f"owner_replays[{replay_index - 1}].{stage}.semantic_projection",
            )
            semantic = _sha256_json(projection_value)
            if (
                summary.get("semantic_fingerprint") != semantic
                or fingerprints.get(stage) != semantic
            ):
                _fail(
                    f"owner_replays[{replay_index - 1}].{stage}",
                    "semantic fingerprint mismatch",
                )
            raw_sha = summary.get("raw_safe_report_sha256")
            if not (
                isinstance(raw_sha, str)
                and raw_sha.startswith("sha256:")
                and len(raw_sha) == 71
            ):
                _fail(
                    f"owner_replays[{replay_index - 1}].{stage}",
                    "invalid raw-safe report digest",
                )
            projections[stage] = projection_value
            recomputed_stage[stage].append(semantic)
        combined = _sha256_json(projections)
        if fingerprints.get("combined") != combined:
            _fail(
                f"owner_replays[{replay_index - 1}].semantic_fingerprints",
                "combined mismatch",
            )
        recomputed_combined.append(combined)
        lineage = _object(
            replay.get("cross_stage_lineage"),
            f"owner_replays[{replay_index - 1}].cross_stage_lineage",
        )
        if lineage.get("status") != "PASS" or lineage.get("equality_count") != 12:
            _fail(
                f"owner_replays[{replay_index - 1}].cross_stage_lineage",
                "lineage closure drifted",
            )
        performance = _object(
            replay.get("performance_observations"),
            f"owner_replays[{replay_index - 1}].performance_observations",
        )
        if (
            performance.get("interpretation")
            != "DEVELOPMENT_OBSERVATION_ONLY_NOT_PRODUCTION_SLA"
        ):
            _fail(
                f"owner_replays[{replay_index - 1}].performance_observations",
                "Production interpretation drifted",
            )

    consistency = _object(
        report.get("semantic_consistency"), "semantic_consistency"
    )
    if (
        consistency.get("status") != "PASS"
        or consistency.get("repeat_count") != 2
        or consistency.get("stage_fingerprints") != recomputed_stage
        or consistency.get("combined_fingerprints") != recomputed_combined
        or consistency.get("unique_combined_fingerprints") != 1
        or len(set(recomputed_combined)) != 1
    ):
        _fail("semantic_consistency", "two-run determinism drifted")

    rejections = _items(report.get("negative_rejections"), "negative_rejections")
    if (
        tuple(_object(row, "negative rejection").get("case_id") for row in rejections)
        != NEGATIVE_CASE_IDS
        or any(
            _object(row, "negative rejection").get("status")
            != "REJECTED_AS_REQUIRED"
            for row in rejections
        )
    ):
        _fail("negative_rejections", "negative matrix drifted")
    scope = _object(report.get("scope_evidence"), "scope_evidence")
    if (
        scope.get("status") != "PASS"
        or set(_items(scope.get("changed_paths"), "scope.changed_paths"))
        != _ALLOWED_TRACKED_PATHS
        or scope.get("unexpected_paths") != []
        or scope.get("missing_paths") != []
        or scope.get("forbidden_owner_changes") != 0
    ):
        _fail("scope_evidence", "exact task scope drifted")
    raw_safe = _object(report.get("raw_safe_boundary"), "raw_safe_boundary")
    if (
        raw_safe.get("status") != "PASS"
        or raw_safe.get("production_authorized") is not False
        or any(
            raw_safe.get(key) is not False
            for key in (
                "p6_raw_rows_included",
                "p6_feature_records_included",
                "p6_labels_included",
                "p6_source_operation_resource_identifiers_included",
                "credentials_secrets_free_text_included",
            )
        )
    ):
        _fail("raw_safe_boundary", "raw/Production boundary drifted")
    checks = _items(report.get("checks"), "checks")
    if (
        report.get("check_count") != len(EXPECTED_CHECK_IDS)
        or len(checks) != len(EXPECTED_CHECK_IDS)
        or tuple(
            _object(raw, f"checks[{index}]").get("check_id")
            for index, raw in enumerate(checks)
        )
        != EXPECTED_CHECK_IDS
        or any(
            _object(raw, "aggregate check").get("status") != "PASS"
            for raw in checks
        )
    ):
        _fail("checks", "aggregate identity/count/status drifted")


def build_p6_duration_gate_manifest(
    report: Mapping[str, object],
) -> JsonObject:
    """Build the compact machine manifest bound to one validated Gate report."""

    validate_p6_duration_vertical_slice_report(report)
    consistency = _object(
        report.get("semantic_consistency"), "semantic_consistency"
    )
    stage_fingerprints = _object(
        consistency.get("stage_fingerprints"),
        "semantic_consistency.stage_fingerprints",
    )
    replays = _items(report.get("owner_replays"), "owner_replays")
    subreports: list[JsonObject] = []
    for replay_index, raw_replay in enumerate(replays, start=1):
        replay = _object(raw_replay, f"owner_replays[{replay_index - 1}]")
        summaries = _object(
            replay.get("raw_safe_subreports"),
            f"owner_replays[{replay_index - 1}].raw_safe_subreports",
        )
        for stage in STAGE_ORDER:
            summary = _object(summaries[stage], f"subreports.{stage}")
            subreports.append(
                {
                    "replay_index": replay_index,
                    "stage": stage,
                    "version": summary["version"],
                    "task_id": summary["task_id"],
                    "raw_safe_report_sha256": summary["raw_safe_report_sha256"],
                    "semantic_fingerprint": summary["semantic_fingerprint"],
                }
            )
    manifest: JsonObject = {
        "schema_version": MANIFEST_VERSION,
        "task_id": TASK_ID,
        "code_commit": report["code_commit"],
        "diff_base": DIFF_BASE,
        "validation_profile": VALIDATION_PROFILE,
        "status": "PASS",
        "report_version": REPORT_VERSION,
        "report_fingerprint": report["report_fingerprint"],
        "report_sha256": _sha256_json(report),
        "semantic_fingerprint": _items(
            consistency.get("combined_fingerprints"),
            "semantic_consistency.combined_fingerprints",
        )[0],
        "repeat_count": report["repeat_count"],
        "stage_order": list(STAGE_ORDER),
        "stage_fingerprints": {
            stage: _items(stage_fingerprints[stage], f"stage_fingerprints.{stage}")[
                0
            ]
            for stage in STAGE_ORDER
        },
        "raw_safe_subreports": subreports,
        "check_ids": list(EXPECTED_CHECK_IDS),
        "check_count": len(EXPECTED_CHECK_IDS),
        "impact_rules": list(IMPACT_RULES),
        "issues": [],
        "blocking_gaps": [],
        "provider_binding": {
            "required_context": "validate",
            "required_app_id": 15368,
            "validation_profile": "FULL",
            "gate_execution_evidence": (
                "FULL_BACKEND_JUNIT_TESTCASE_AND_TASK_BASE_CHECK_GAP_PROPERTIES"
            ),
            "owner_replay_evidence": (
                "FULL_VALIDATION_BUILD_VALIDATION_JSON_ARTIFACTS"
            ),
            "workflow_changed": False,
        },
    }
    return _with_fingerprint(manifest, "manifest_fingerprint")


def validate_p6_duration_gate_manifest(
    manifest: Mapping[str, object],
    report: Mapping[str, object] | None = None,
) -> None:
    """Validate the compact TASK-P6-09 machine manifest."""

    expected_keys = {
        "schema_version",
        "task_id",
        "code_commit",
        "diff_base",
        "validation_profile",
        "status",
        "report_version",
        "report_fingerprint",
        "report_sha256",
        "semantic_fingerprint",
        "repeat_count",
        "stage_order",
        "stage_fingerprints",
        "raw_safe_subreports",
        "check_ids",
        "check_count",
        "impact_rules",
        "issues",
        "blocking_gaps",
        "provider_binding",
        "manifest_fingerprint",
    }
    if set(manifest) != expected_keys:
        _fail("manifest", "unexpected or missing field")
    for key, expected in (
        ("schema_version", MANIFEST_VERSION),
        ("task_id", TASK_ID),
        ("diff_base", DIFF_BASE),
        ("validation_profile", VALIDATION_PROFILE),
        ("status", "PASS"),
        ("report_version", REPORT_VERSION),
        ("repeat_count", 2),
        ("stage_order", list(STAGE_ORDER)),
        ("check_ids", list(EXPECTED_CHECK_IDS)),
        ("check_count", len(EXPECTED_CHECK_IDS)),
        ("impact_rules", list(IMPACT_RULES)),
        ("issues", []),
        ("blocking_gaps", []),
    ):
        if manifest.get(key) != expected:
            _fail(f"manifest.{key}", f"expected {expected!r}")
    projection = dict(manifest)
    fingerprint = projection.pop("manifest_fingerprint")
    if fingerprint != _sha256_json(projection):
        _fail("manifest.manifest_fingerprint", "canonical fingerprint mismatch")
    stages = _object(manifest.get("stage_fingerprints"), "manifest.stages")
    if set(stages) != set(STAGE_ORDER):
        _fail("manifest.stage_fingerprints", "stage set drifted")
    subreports = _items(
        manifest.get("raw_safe_subreports"), "manifest.raw_safe_subreports"
    )
    if len(subreports) != 2 * len(STAGE_ORDER):
        _fail("manifest.raw_safe_subreports", "subreport count drifted")
    provider = _object(manifest.get("provider_binding"), "manifest.provider_binding")
    expected_provider = {
        "required_context": "validate",
        "required_app_id": 15368,
        "validation_profile": "FULL",
        "gate_execution_evidence": (
            "FULL_BACKEND_JUNIT_TESTCASE_AND_TASK_BASE_CHECK_GAP_PROPERTIES"
        ),
        "owner_replay_evidence": "FULL_VALIDATION_BUILD_VALIDATION_JSON_ARTIFACTS",
        "workflow_changed": False,
    }
    if provider != expected_provider:
        _fail("manifest.provider_binding", "provider binding drifted")
    if report is not None:
        validate_p6_duration_vertical_slice_report(report)
        if (
            manifest.get("code_commit") != report.get("code_commit")
            or manifest.get("report_fingerprint") != report.get("report_fingerprint")
            or manifest.get("report_sha256") != _sha256_json(report)
        ):
            _fail("manifest.report", "report binding mismatch")


def _safe_error(error: Exception, root: Path) -> str:
    text = f"{type(error).__name__}: {error}".replace(str(root), "<ROOT>")
    return " ".join(text.split())[:512]


def _failure_report(error: Exception, root: Path, repeat: int) -> JsonObject:
    message = _safe_error(error, root)
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "code_commit": _code_commit(root),
        "diff_base": DIFF_BASE,
        "generated_at_utc": _generated_at(),
        "validation_profile": VALIDATION_PROFILE,
        "status": "FAIL",
        "repeat_count": repeat,
        "issues": [{"code": "P6_VERTICAL_SLICE_GATE_FAILED", "detail": message}],
        "blocking_gaps": [
            {"gap_id": "P6-09-GATE-FAILURE", "status": "BLOCKING", "detail": message}
        ],
        "boundaries": dict(_BOUNDARIES),
    }


def _failure_manifest(report: Mapping[str, object]) -> JsonObject:
    value: JsonObject = {
        "schema_version": MANIFEST_VERSION,
        "task_id": TASK_ID,
        "code_commit": report["code_commit"],
        "diff_base": DIFF_BASE,
        "validation_profile": VALIDATION_PROFILE,
        "status": "FAIL",
        "report_sha256": _sha256_json(report),
        "issues": report["issues"],
        "blocking_gaps": report["blocking_gaps"],
    }
    return _with_fingerprint(value, "manifest_fingerprint")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--subreport-dir", type=Path)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    try:
        report = run_p6_duration_vertical_slice_gate(
            root=root,
            repeat=arguments.repeat,
            subreport_dir=arguments.subreport_dir,
        )
        manifest = build_p6_duration_gate_manifest(report)
    except Exception as error:
        report = _failure_report(error, root, arguments.repeat)
        manifest = _failure_manifest(report)
        _write_json(arguments.report, report)
        _write_json(arguments.manifest, manifest)
        print(
            f"FAIL P6 duration vertical slice: gaps={len(report['blocking_gaps'])}"
        )
        return 1
    _write_json(arguments.report, report)
    _write_json(arguments.manifest, manifest)
    print(
        f"PASS P6 duration vertical slice: replays={report['repeat_count']} "
        f"stages={report['counts']['owner_stage_executions']} "
        f"checks={report['check_count']} gaps=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "EXPECTED_CHECK_IDS",
    "MANIFEST_VERSION",
    "NEGATIVE_CASE_IDS",
    "P6DurationGateContractError",
    "P6DurationGateExecutionError",
    "REPORT_VERSION",
    "STAGE_ORDER",
    "TASK_ID",
    "build_p6_duration_gate_manifest",
    "main",
    "run_p6_duration_vertical_slice_gate",
    "validate_p6_duration_gate_manifest",
    "validate_p6_duration_vertical_slice_report",
]
