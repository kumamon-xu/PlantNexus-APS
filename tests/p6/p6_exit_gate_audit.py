"""Build the independent TASK-P6-10 P6 Exit Gate audit evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Never, cast

from scripts.provider_evidence import (
    GhClient,
    artifact_filename,
    inspect_artifact_zip,
    select_exact_run,
    validate_artifact_metadata,
)
from tests.p6.p6_duration_gate_report import (
    build_p6_duration_gate_manifest,
    run_p6_duration_vertical_slice_gate,
    validate_p6_duration_gate_manifest,
    validate_p6_duration_vertical_slice_report,
)


type JsonObject = dict[str, Any]

REPORT_VERSION = "p6-exit-gate-audit-report.v1"
MANIFEST_VERSION = "p6-exit-gate-evidence-manifest.v1"
OBSERVATION_VERSION = "p6-exit-provider-observation.v1"
TASK_ID = "TASK-P6-10"
DIFF_BASE = "dc38f0156b154652b192a671c959b0da71aab08f"
VALIDATION_PROFILE = "PHASE_GATE"
ACTIVATION_VERIFIED_AT = "2026-09-02T00:00:00Z"

IMPACT_RULES = ("IMPACT-TESTS", "IMPACT-DOCS")
TEST_IDS = (
    "TEST-P6-EXIT-GATE-001",
    "TEST-P6-VERTICAL-SLICE-001",
    "TEST-P6-FALLBACK-001",
    "TEST-P4-VERTICAL-SLICE-001",
    "TEST-TRACEABILITY-VALIDATOR",
)
EXPECTED_CHECK_IDS = (
    "p6-task-topology-and-dag-terminality",
    "provider-exact-run-check-app-topology",
    "provider-artifact-download-expiry-digest-and-json-semantics",
    "retained-failure-and-direct-corrective-chain",
    "adr-governance-and-machine-contract-frozen",
    "schema-migration-dependency-state-and-workflow-frozen",
    "fresh-complete-p6-owner-chain-replay",
    "fresh-p6-gate-independent-validation",
    "data-label-feature-privacy-and-lineage-boundary",
    "model-evaluation-quality-and-deterministic-replay",
    "runtime-fallback-and-standard-duration-authority",
    "planning-ingress-p2-formal-validator-regression",
    "monitoring-default-disable-and-no-automatic-action",
    "p4-dynamic-replanning-regression",
    "open-sim-risk-and-traceability-carry-forward",
    "task-scope-and-forbidden-owner-boundary",
    "p6-p7-production-and-phase-transition-boundary",
)

_EXPECTED_PROVIDER_INVENTORY_FINGERPRINT = (
    "sha256:c837a9666388b7868795eca51457c7e8c1af7ad29c50603b99a4305b0581cbb7"
)

_ALLOWED_TRACKED_PATHS = frozenset(
    {
        "README.md",
        "conftest.py",
        "docs/README.md",
        "docs/architecture/end-to-end-planning-flow.md",
        "docs/core/capability-matrix.md",
        "docs/p6-exit-gate-audit-observations.v1.json",
        "docs/simulation/benchmark-harness.md",
        "tests/p6/p6_exit_gate_audit.py",
        "tests/p6/test_p6_exit_gate_audit.py",
        "tests/p6/test_p6_exit_gate_rejections.py",
    }
)

_EXPECTED_TASK_STATUSES: Mapping[str, str] = {
    **{f"TASK-P6-{index:02d}": "done" for index in range(10)},
    "TASK-P6-10": "in_progress",
    "TASK-P6-11": "done",
}
_EXPECTED_DAG_EDGES = (
    ("TASK-P6-00", "TASK-P6-01"),
    ("TASK-P6-01", "TASK-P6-02"),
    ("TASK-P6-02", "TASK-P6-03"),
    ("TASK-P6-03", "TASK-P6-04"),
    ("TASK-P6-04", "TASK-P6-05"),
    ("TASK-P6-04", "TASK-P6-11"),
    ("TASK-P6-11", "TASK-P6-05"),
    ("TASK-P6-05", "TASK-P6-06"),
    ("TASK-P6-06", "TASK-P6-07"),
    ("TASK-P6-06", "TASK-P6-08"),
    ("TASK-P6-07", "TASK-P6-09"),
    ("TASK-P6-08", "TASK-P6-09"),
    ("TASK-P6-09", "TASK-P6-10"),
)


def _provider_run(
    task_id: str,
    evidence_kind: str,
    commit_sha: str,
    run_id: int,
    required_job_id: int,
    profile: str,
    artifact_count: int,
    expected_conclusion: str = "success",
) -> JsonObject:
    return {
        "task_id": task_id,
        "evidence_kind": evidence_kind,
        "commit_sha": commit_sha,
        "run_id": run_id,
        "required_job_id": required_job_id,
        "profile": profile,
        "artifact_count": artifact_count,
        "expected_conclusion": expected_conclusion,
    }


_EXPECTED_PROVIDER_RUNS: tuple[JsonObject, ...] = (
    _provider_run(
        "TASK-P6-00",
        "implementation",
        "5a58356d8df45c9156223d2b4ca935cc3e5f2f7a",
        33456013298,
        99696075050,
        "DOCS_ONLY",
        2,
    ),
    _provider_run(
        "TASK-P6-00",
        "closure",
        "e854c5bbea784f513863ae55d6b872a7a7d1b928",
        33456198117,
        99696621103,
        "DOCS_ONLY",
        2,
    ),
    _provider_run(
        "TASK-P6-01",
        "implementation",
        "856aac53cefa9477eb2b5906958f0a14775a950c",
        33457799580,
        99701440089,
        "DOCS_ONLY",
        2,
    ),
    _provider_run(
        "TASK-P6-01",
        "closure",
        "e74099ca24ed59140f6490c84025b7299b5f201d",
        33458046556,
        99702170559,
        "DOCS_ONLY",
        2,
    ),
    _provider_run(
        "TASK-P6-02",
        "retained_failed_candidate",
        "969891710add4133f2cf1e52362a360ef6a7fc29",
        33462987751,
        99718412135,
        "FULL",
        2,
        "failure",
    ),
    _provider_run(
        "TASK-P6-02",
        "corrective_implementation",
        "093e6e1057458850eae11334b3015778f35bf273",
        33464029827,
        99722215840,
        "FULL",
        2,
    ),
    _provider_run(
        "TASK-P6-02",
        "closure",
        "4360746f2712012a0aa4f52a40c189837a2097b3",
        33465136714,
        99723376173,
        "DOCS_ONLY",
        2,
    ),
    _provider_run(
        "TASK-P6-03",
        "implementation",
        "19c80dac7cf298b423d9e22add2268421520ef75",
        33468228427,
        99734830107,
        "FULL",
        2,
    ),
    _provider_run(
        "TASK-P6-03",
        "closure",
        "1d184d082544454436a5558bc39a6a0a38f0fb1b",
        33469395721,
        99735949548,
        "DOCS_ONLY",
        2,
    ),
    _provider_run(
        "TASK-P6-04",
        "implementation",
        "bf75f601b0a8138ab80304bee68e9bbe34b124fd",
        33474633364,
        99753251628,
        "FULL",
        2,
    ),
    _provider_run(
        "TASK-P6-04",
        "closure",
        "73eb8d6fcdf1400994d0c82f20242bef48694519",
        33475962188,
        99755241062,
        "DOCS_ONLY",
        2,
    ),
    _provider_run(
        "TASK-P6-11",
        "implementation",
        "03a0b4dd4de9398aa02746b736c3cf6e7fab9b0d",
        33485901085,
        99788329852,
        "FULL",
        4,
    ),
    _provider_run(
        "TASK-P6-05",
        "implementation",
        "aafcfafbd9fdebc2a76620122fe17e1c97473a2f",
        33494418602,
        99815480685,
        "FULL",
        4,
    ),
    _provider_run(
        "TASK-P6-05",
        "closure",
        "9921e57034defc26c0a08b7b0c27da3398a0fc7e",
        33496017952,
        99818420023,
        "DOCS_ONLY",
        2,
    ),
    _provider_run(
        "TASK-P6-06",
        "implementation",
        "e54e103e9c15cf672d8bcefdfcee5b5775757922",
        33502648559,
        99841390941,
        "FULL",
        4,
    ),
    _provider_run(
        "TASK-P6-07",
        "implementation",
        "e5d63fcf54c841ed93ef7c62084bcdeeda63abd4",
        33512511801,
        99874314670,
        "FULL",
        4,
    ),
    _provider_run(
        "TASK-P6-08",
        "implementation",
        "a8984dd3e961fe03dad543d9ce6b9b5266c6ab09",
        33522642120,
        99908691371,
        "FULL",
        4,
    ),
    _provider_run(
        "TASK-P6-09",
        "implementation",
        DIFF_BASE,
        33570562236,
        100065332717,
        "FULL",
        4,
    ),
)

_FROZEN_MARKERS: Mapping[str, tuple[str, ...]] = {
    "docs/adr/ADR-0016-ai-duration-data-model-governance.md": (
        "标准工时继续是唯一回退authority",
        "Promotion、retraining与rollback必须由人控制",
        "P2 formal Validator和P4 facts/HARD/freeze/ChangeReport",
    ),
    "docs/contracts/duration-prediction-governance.md": (
        "Standard duration",
        "Synthetic、provider success、local Gate或P6 Exit不能证明Production",
        "Provider与ignored closure按TASK-P6-11",
    ),
    "docs/contracts/duration-prediction-machine-contract.md": (
        "FORMED_SIMULATION_CONTRACT_V1",
        "TASK-P6-07 default-off Planning ingress",
        "TASK-P6-09 and later require separate authorization",
    ),
    "docs/contracts/planning-problem.md": (
        "TASK-P6-07 default-off duration selection",
        "planning-problem-builder.v2",
        "任何非duration差异",
    ),
}
_DURATION_SCHEMAS = (
    "schemas/json/duration-feature-record.schema.json",
    "schemas/json/duration-model-manifest.schema.json",
    "schemas/json/duration-evaluation-report.schema.json",
    "schemas/json/duration-prediction.schema.json",
)
_FROZEN_OWNER_PATHS = (
    ".github/workflows/ci.yml",
    "backend/app/duration_prediction",
    "backend/app/planning",
    "backend/app/simulation",
    "backend/migrations",
    "benchmarks/p6",
    "fixtures/p6",
    "pyproject.toml",
    "schemas/json/duration-evaluation-report.schema.json",
    "schemas/json/duration-feature-record.schema.json",
    "schemas/json/duration-model-manifest.schema.json",
    "schemas/json/duration-prediction.schema.json",
    "schemas/rules/state-machines.v1.yaml",
    "scripts/p6_duration_contract_check.py",
    "scripts/p6_duration_dataset_check.py",
    "scripts/p6_duration_evaluation_check.py",
    "scripts/p6_duration_model_check.py",
    "scripts/p6_duration_monitoring_check.py",
    "scripts/p6_duration_runtime_check.py",
    "scripts/p6_planning_integration_check.py",
    "uv.lock",
)

_POST_P6_ADDITIVE_OWNER_SHA256: Mapping[str, str] = {
    ".github/workflows/ci.yml": (
        "b8b3cbcdf399f626d22e91d29c98501ce360df6987b4c5fcf842a154243d8249"
    ),
    "backend/app/planning/backends/cp_sat/replan_solver_check.py": (
        "562cda6cde4dc1e22a5321597ecb1d0d0a1a38ed334ad34df79b156d9d203cdc"
    ),
    "backend/app/planning/problem/freeze_window_check.py": (
        "0f11a654836f687e512f6ce2574c954d2f290716ac16edaca61d382edee831bf"
    ),
    "backend/app/planning/reporting/stability_change_report_check.py": (
        "dbe4e346e9ccdf5adc726f58a7a55c9a75fd765a2b85c078a54675bef38fb638"
    ),
    "backend/app/simulation/execution/simulator_check.py": (
        "8d05e552e3e2ff07d4a1d7d8d9da356417bb87dc7b31b5c12879aef760b6f2ce"
    ),
    "pyproject.toml": (
        "4b511b70bae195debce23cd99149af059aaa1ab3694218f553d115ba3ca8bd09"
    ),
    "scripts/p6_duration_contract_check.py": (
        "372d78725477838a33a75330202c26465059f33259eb9fc65b0f2eb9c23fc341"
    ),
    "backend/migrations/versions/0006_canonical_ingress_application.py": (
        "2262edeedb93557a9b01e3d790aaea76463c81f02df417b4dae04858fccc5bac"
    ),
    "backend/migrations/versions/0007_planning_run_orchestration.py": (
        "2ac97f99fa2393624a6d0664e4bb20fc938f3533475cd0558972db299e8e31f0"
    ),
    "backend/migrations/versions/0008_planning_run_solver_worker.py": (
        "a816913add759fcee9a9232157f28bbbd370eb103cdcbb21c76117c1b867f699"
    ),
}

_BOUNDARIES: JsonObject = {
    "current_phase": "P6",
    "p6_milestone": "ACTIVE_AWAITING_USER_TRANSITION",
    "p7_reality_calibration": "NOT_ENTERED",
    "production_readiness": "NOT_CLAIMED",
    "production_data_model_approval_authority": "NOT_FORMED",
    "external_integration_or_deployment": "NONE",
    "uat": "NOT_PERFORMED",
    "capacity_and_sla": "NOT_ESTABLISHED",
    "data_plane": "SIMULATION_DEVELOPMENT_ONLY",
    "default_enabled": False,
    "automatic_phase_transition": "PROHIBITED",
    "automatic_retraining_promotion_rollback": "NONE",
    "standard_duration_authority": "UNCHANGED_EXACT_FALLBACK",
    "routing_resource_constraints_state_weights": "UNCHANGED",
}


class P6ExitGateAuditError(ValueError):
    """A P6 Exit observation, report, or manifest failed closed."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"P6_EXIT_GATE at {field}: {message}")


def _fail(field: str, message: str) -> Never:
    raise P6ExitGateAuditError(field, message)


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, Mapping):
        _fail(field, "expected object")
    return dict(value)


def _items(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(field, "expected array")
    return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(_canonical_bytes(value)).hexdigest()}"


def _bytes_fingerprint(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _with_fingerprint(value: Mapping[str, object], field: str) -> JsonObject:
    result = dict(value)
    result[field] = _fingerprint(result)
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
        _fail("git", f"{' '.join(arguments)} failed")
    return completed.stdout.strip()


def _code_commit(root: Path) -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT") or _git(
        root, "rev-parse", "HEAD"
    )
    if not (
        len(value) == 40
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    ):
        _fail("code_commit", "expected full lowercase Git SHA")
    return value


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path, field: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise P6ExitGateAuditError(field, "invalid UTF-8 JSON") from error
    return _object(value, field)


def _task_topology_snapshot(root: Path) -> JsonObject:
    statuses: list[JsonObject] = []
    for task_id, expected_status in _EXPECTED_TASK_STATUSES.items():
        matches = sorted((root / "docs/tasks/P6").glob(f"{task_id}-*.md"))
        if len(matches) != 1:
            _fail("task_topology", f"expected one card for {task_id}")
        text = matches[0].read_text(encoding="utf-8")
        match = re.search(r"(?m)^status:\s*([^\s]+)\s*$", text)
        if match is None or match.group(1) != expected_status:
            _fail("task_topology", f"{task_id} status drifted")
        statuses.append({"task_id": task_id, "status": expected_status})
    return {
        "tasks": statuses,
        "task_count": len(statuses),
        "terminal_done_count": 11,
        "active_task": TASK_ID,
        "active_diff_base": DIFF_BASE,
        "dag_edges": [list(edge) for edge in _EXPECTED_DAG_EDGES],
        "dag_edge_count": len(_EXPECTED_DAG_EDGES),
        "cycle_count": 0,
        "p6_09_direct_dependency": "done/PROVIDER_VERIFIED_DONE",
    }


def _table_snapshot(
    path: Path,
    prefix: str,
    status_index: int,
    expected_count: int,
    expected_status: str,
) -> JsonObject:
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {prefix}"):
            rows.append([part.strip() for part in line.strip().strip("|").split("|")])
    if len(rows) != expected_count:
        _fail("registers", f"{prefix} expected {expected_count} rows")
    expected_ids = [f"{prefix}{index:03d}" for index in range(1, expected_count + 1)]
    if [row[0] for row in rows] != expected_ids:
        _fail("registers", f"{prefix} identities drifted")
    if any(row[status_index] != expected_status for row in rows):
        _fail("registers", f"{prefix} status drifted")
    return {
        "count": len(rows),
        "first_id": rows[0][0],
        "last_id": rows[-1][0],
        "status": f"ALL_{expected_status}",
    }


def _register_snapshot(root: Path) -> JsonObject:
    return {
        "prod_open": _table_snapshot(
            root / "docs/governance/prod-open-register.md", "OPEN-", 2, 15, "OPEN"
        ),
        "sim_assumptions": _table_snapshot(
            root / "docs/governance/sim-assumption-register.md",
            "SIM-ASSUMPTION-",
            2,
            26,
            "ACTIVE",
        ),
        "risks": _table_snapshot(
            root / "docs/governance/risk-register.md",
            "RISK-",
            1,
            19,
            "MONITORED",
        ),
        "allocated_requirement_nfr_eng_roots": 30,
        "new_prod_open": [],
        "new_sim_assumptions": [],
        "new_risks": [],
        "closed_by_audit": [],
    }


def _find_required_check(
    checks: Sequence[Mapping[str, object]],
    *,
    commit_sha: str,
    run_id: int,
) -> JsonObject:
    matching: list[JsonObject] = []
    for raw in checks:
        check = dict(raw)
        app = check.get("app")
        app_id = app.get("id") if isinstance(app, Mapping) else None
        if (
            check.get("name") == "validate"
            and str(check.get("head_sha", "")).lower() == commit_sha
            and app_id == 15368
            and f"/actions/runs/{run_id}/" in str(check.get("details_url", ""))
        ):
            matching.append(check)
    if len(matching) != 1:
        _fail("provider.required_check", "expected one validate/app 15368 check")
    return matching[0]


def collect_provider_observation(
    *,
    root: Path,
    artifacts_dir: Path,
    client: GhClient | None = None,
    observed_at: datetime | None = None,
) -> JsonObject:
    """Fresh-download and summarize the immutable P6 Provider topology."""

    root = root.resolve()
    artifacts_dir = artifacts_dir.resolve()
    if not artifacts_dir.is_relative_to(root):
        _fail("collector.artifacts_dir", "must remain inside repository")
    provider = client or GhClient()
    timestamp = observed_at or datetime.now(UTC)
    provider_runs: list[JsonObject] = []
    for expected in _EXPECTED_PROVIDER_RUNS:
        commit_sha = cast(str, expected["commit_sha"])
        run_id = cast(int, expected["run_id"])
        run = select_exact_run(
            provider.list_runs("kumamon-xu/PlantNexus-APS", "ci.yml", commit_sha),
            commit_sha,
        )
        if (
            run.get("databaseId") != run_id
            or run.get("status") != "completed"
            or run.get("conclusion") != expected["expected_conclusion"]
        ):
            _fail("provider.run", f"run identity/status drifted for {commit_sha}")
        jobs = [dict(item) for item in provider.jobs("kumamon-xu/PlantNexus-APS", run_id)]
        validate_jobs = [item for item in jobs if item.get("name") == "validate"]
        if len(validate_jobs) != 1:
            _fail("provider.jobs", f"validate job topology drifted for {run_id}")
        required_job = validate_jobs[0]
        required_check = _find_required_check(
            provider.check_runs("kumamon-xu/PlantNexus-APS", commit_sha),
            commit_sha=commit_sha,
            run_id=run_id,
        )
        expected_conclusion = cast(str, expected["expected_conclusion"])
        if (
            required_job.get("id") != expected["required_job_id"]
            or required_job.get("conclusion") != expected_conclusion
            or required_check.get("id") != expected["required_job_id"]
            or required_check.get("status") != "completed"
            or required_check.get("conclusion") != expected_conclusion
        ):
            _fail("provider.required_check", f"required check drifted for {run_id}")

        metadata = sorted(
            (
                dict(item)
                for item in provider.artifacts("kumamon-xu/PlantNexus-APS", run_id)
                if str(item.get("name", "")).startswith("plantnexus-ci-")
            ),
            key=lambda item: str(item.get("name", "")),
        )
        if len(metadata) != expected["artifact_count"]:
            _fail("provider.artifacts", f"artifact count drifted for {run_id}")
        run_dir = artifacts_dir / f"{run_id}-{expected['evidence_kind']}"
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact_rows: list[JsonObject] = []
        for artifact in metadata:
            validate_artifact_metadata(artifact, timestamp)
            artifact_id = artifact.get("id")
            name = artifact.get("name")
            if not isinstance(artifact_id, int) or not isinstance(name, str):
                _fail("provider.artifacts", "missing artifact identity")
            data = provider.download_artifact(
                "kumamon-xu/PlantNexus-APS", artifact_id
            )
            downloaded_digest = _bytes_fingerprint(data)
            provider_digest = artifact.get("digest")
            if provider_digest != downloaded_digest:
                _fail("provider.artifacts", f"download digest mismatch for {artifact_id}")
            entries, zip_issues = inspect_artifact_zip(data, commit_sha)
            if expected_conclusion == "success" and zip_issues:
                _fail("provider.artifacts", f"successful artifact issues for {artifact_id}")
            archive_name = artifact_filename(artifact_id, name)
            (run_dir / archive_name).write_bytes(data)
            artifact_rows.append(
                {
                    "id": artifact_id,
                    "name": name,
                    "expires_at": artifact.get("expires_at"),
                    "bytes": len(data),
                    "provider_digest": provider_digest,
                    "downloaded_sha256": downloaded_digest,
                    "digest_match": True,
                    "entry_count": len(entries),
                    "json_entry_count": sum(
                        str(entry.get("path", "")).lower().endswith(".json")
                        for entry in entries
                    ),
                    "entry_inventory_fingerprint": _fingerprint(entries),
                    "zip_issue_count": len(zip_issues),
                }
            )
        provider_runs.append(
            {
                **expected,
                "run_status": run.get("status"),
                "run_conclusion": run.get("conclusion"),
                "run_attempt": run.get("attempt", 1),
                "created_at": run.get("createdAt"),
                "updated_at": run.get("updatedAt"),
                "required_check": {
                    "id": required_check.get("id"),
                    "name": "validate",
                    "app_id": 15368,
                    "status": required_check.get("status"),
                    "conclusion": required_check.get("conclusion"),
                },
                "jobs": [
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "status": item.get("status"),
                        "conclusion": item.get("conclusion"),
                    }
                    for item in jobs
                ],
                "artifacts": artifact_rows,
                "issues": [],
            }
        )

    success_rows = [
        row for row in provider_runs if row["expected_conclusion"] == "success"
    ]
    failed_rows = [
        row for row in provider_runs if row["expected_conclusion"] == "failure"
    ]
    all_artifacts = [
        artifact for row in provider_runs for artifact in cast(list[JsonObject], row["artifacts"])
    ]
    successful_artifacts = [
        artifact for row in success_rows for artifact in cast(list[JsonObject], row["artifacts"])
    ]
    observation: JsonObject = {
        "report_version": OBSERVATION_VERSION,
        "audit_task": TASK_ID,
        "immutable_diff_base": DIFF_BASE,
        "observed_at_utc": timestamp.isoformat(timespec="seconds"),
        "repository": "kumamon-xu/PlantNexus-APS",
        "workflow": "ci.yml",
        "required_check": {"name": "validate", "app_id": 15368},
        "task_topology": _task_topology_snapshot(root),
        "provider_runs": provider_runs,
        "provider_audit": {
            "run_count": len(provider_runs),
            "successful_run_count": len(success_rows),
            "retained_failed_run_count": len(failed_rows),
            "artifact_count": len(all_artifacts),
            "successful_artifact_count": len(successful_artifacts),
            "expired_artifact_count": 0,
            "digest_mismatch_count": 0,
            "successful_zip_issue_count": sum(
                cast(int, artifact["zip_issue_count"])
                for artifact in successful_artifacts
            ),
            "retained_failure_zip_issue_count": sum(
                cast(int, artifact["zip_issue_count"])
                for row in failed_rows
                for artifact in cast(list[JsonObject], row["artifacts"])
            ),
            "json_entry_count": sum(
                cast(int, artifact["json_entry_count"])
                for artifact in all_artifacts
            ),
            "provider_inventory_fingerprint": _fingerprint(provider_runs),
        },
        "failure_corrective_chain": [
            {
                "task_id": "TASK-P6-02",
                "failed_sha": "969891710add4133f2cf1e52362a360ef6a7fc29",
                "failed_run_id": 33462987751,
                "corrective_sha": "093e6e1057458850eae11334b3015778f35bf273",
                "corrective_run_id": 33464029827,
                "status": "CORRECTED_BY_NEW_SHA",
                "rerun_used": False,
            }
        ],
        "registers": _register_snapshot(root),
        "contracts": {
            "accepted_adr": "ADR-0016",
            "schema_set_version": "2.9.0",
            "duration_schema_count": 4,
            "fallback_reason_count_excluding_none": 19,
            "standard_duration_authority": "UNCHANGED",
            "capability": (
                "DEFERRED_DEFAULT_OFF_SIMULATION_ONLY_WITH_AGGREGATE_MONITOR"
            ),
            "p6_gate_reference_policy": (
                "HISTORICAL_REFERENCE_ONLY_FRESH_REPLAY_REQUIRED"
            ),
        },
        "boundaries": dict(_BOUNDARIES),
        "issues": [],
    }
    return _with_fingerprint(observation, "observation_fingerprint")


def _is_ancestor(root: Path, commit_sha: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return completed.returncode == 0


def validate_provider_observation(
    observation: Mapping[str, object], root: Path
) -> None:
    """Validate the fresh-downloaded immutable P6 Provider observation."""

    expected_keys = {
        "report_version",
        "audit_task",
        "immutable_diff_base",
        "observed_at_utc",
        "repository",
        "workflow",
        "required_check",
        "task_topology",
        "provider_runs",
        "provider_audit",
        "failure_corrective_chain",
        "registers",
        "contracts",
        "boundaries",
        "issues",
        "observation_fingerprint",
    }
    if set(observation) != expected_keys:
        _fail("observation", "unexpected or missing field")
    for key, expected in (
        ("report_version", OBSERVATION_VERSION),
        ("audit_task", TASK_ID),
        ("immutable_diff_base", DIFF_BASE),
        ("repository", "kumamon-xu/PlantNexus-APS"),
        ("workflow", "ci.yml"),
        ("required_check", {"name": "validate", "app_id": 15368}),
        ("issues", []),
        ("boundaries", _BOUNDARIES),
    ):
        if observation.get(key) != expected:
            _fail(f"observation.{key}", "identity or boundary drifted")
    projection = dict(observation)
    observed_fingerprint = projection.pop("observation_fingerprint")
    if observed_fingerprint != _fingerprint(projection):
        _fail("observation.observation_fingerprint", "canonical mismatch")

    topology = _object(observation.get("task_topology"), "observation.topology")
    if (
        topology.get("tasks")
        != [
            {"task_id": task_id, "status": status}
            for task_id, status in _EXPECTED_TASK_STATUSES.items()
        ]
        or topology.get("task_count") != 12
        or topology.get("terminal_done_count") != 11
        or topology.get("active_task") != TASK_ID
        or topology.get("active_diff_base") != DIFF_BASE
        or topology.get("dag_edges") != [list(edge) for edge in _EXPECTED_DAG_EDGES]
        or topology.get("dag_edge_count") != len(_EXPECTED_DAG_EDGES)
        or topology.get("cycle_count") != 0
    ):
        _fail("observation.task_topology", "P6 task topology drifted")

    runs = _items(observation.get("provider_runs"), "observation.provider_runs")
    if len(runs) != len(_EXPECTED_PROVIDER_RUNS):
        _fail("observation.provider_runs", "run count drifted")
    activation = datetime.fromisoformat(ACTIVATION_VERIFIED_AT.replace("Z", "+00:00"))
    for index, expected in enumerate(_EXPECTED_PROVIDER_RUNS):
        row = _object(runs[index], f"observation.provider_runs[{index}]")
        for key, value in expected.items():
            if row.get(key) != value:
                _fail(f"observation.provider_runs[{index}].{key}", "identity drifted")
        if not _is_ancestor(root, cast(str, expected["commit_sha"])):
            _fail(f"observation.provider_runs[{index}].commit_sha", "not a HEAD ancestor")
        expected_conclusion = expected["expected_conclusion"]
        required = _object(row.get("required_check"), "provider.required_check")
        if (
            row.get("run_status") != "completed"
            or row.get("run_conclusion") != expected_conclusion
            or required.get("id") != expected["required_job_id"]
            or required.get("name") != "validate"
            or required.get("app_id") != 15368
            or required.get("status") != "completed"
            or required.get("conclusion") != expected_conclusion
            or row.get("issues") != []
        ):
            _fail(f"observation.provider_runs[{index}]", "run/check/app drifted")
        artifacts = _items(row.get("artifacts"), "provider.artifacts")
        if len(artifacts) != expected["artifact_count"]:
            _fail(f"observation.provider_runs[{index}].artifacts", "count drifted")
        for artifact_index, raw in enumerate(artifacts):
            artifact = _object(raw, "provider.artifact")
            expiry_raw = artifact.get("expires_at")
            if not isinstance(expiry_raw, str):
                _fail("provider.artifact.expires_at", "missing expiry")
            expiry = datetime.fromisoformat(expiry_raw.replace("Z", "+00:00"))
            if (
                expiry <= activation
                or artifact.get("digest_match") is not True
                or artifact.get("provider_digest")
                != artifact.get("downloaded_sha256")
            ):
                _fail(
                    f"observation.provider_runs[{index}].artifacts[{artifact_index}]",
                    "expiry or digest drifted",
                )
            if expected_conclusion == "success" and artifact.get("zip_issue_count") != 0:
                _fail("provider.artifact", "successful artifact contains issue")

    provider_audit = _object(
        observation.get("provider_audit"), "observation.provider_audit"
    )
    if (
        provider_audit.get("run_count") != 18
        or provider_audit.get("successful_run_count") != 17
        or provider_audit.get("retained_failed_run_count") != 1
        or provider_audit.get("artifact_count") != 48
        or provider_audit.get("successful_artifact_count") != 46
        or provider_audit.get("expired_artifact_count") != 0
        or provider_audit.get("digest_mismatch_count") != 0
        or provider_audit.get("successful_zip_issue_count") != 0
        or provider_audit.get("provider_inventory_fingerprint")
        != _EXPECTED_PROVIDER_INVENTORY_FINGERPRINT
        or _fingerprint(runs) != _EXPECTED_PROVIDER_INVENTORY_FINGERPRINT
    ):
        _fail("observation.provider_audit", "provider inventory drifted")
    failure_chain = _items(
        observation.get("failure_corrective_chain"), "observation.failure_chain"
    )
    if failure_chain != [
        {
            "task_id": "TASK-P6-02",
            "failed_sha": "969891710add4133f2cf1e52362a360ef6a7fc29",
            "failed_run_id": 33462987751,
            "corrective_sha": "093e6e1057458850eae11334b3015778f35bf273",
            "corrective_run_id": 33464029827,
            "status": "CORRECTED_BY_NEW_SHA",
            "rerun_used": False,
        }
    ]:
        _fail("observation.failure_corrective_chain", "failure history drifted")
    if observation.get("registers") != {
        "prod_open": {
            "count": 15,
            "first_id": "OPEN-001",
            "last_id": "OPEN-015",
            "status": "ALL_OPEN",
        },
        "sim_assumptions": {
            "count": 26,
            "first_id": "SIM-ASSUMPTION-001",
            "last_id": "SIM-ASSUMPTION-026",
            "status": "ALL_ACTIVE",
        },
        "risks": {
            "count": 19,
            "first_id": "RISK-001",
            "last_id": "RISK-019",
            "status": "ALL_MONITORED",
        },
        "allocated_requirement_nfr_eng_roots": 30,
        "new_prod_open": [],
        "new_sim_assumptions": [],
        "new_risks": [],
        "closed_by_audit": [],
    }:
        _fail("observation.registers", "OPEN/SIM/risk carry-forward drifted")
    if observation.get("contracts") != {
        "accepted_adr": "ADR-0016",
        "schema_set_version": "2.9.0",
        "duration_schema_count": 4,
        "fallback_reason_count_excluding_none": 19,
        "standard_duration_authority": "UNCHANGED",
        "capability": "DEFERRED_DEFAULT_OFF_SIMULATION_ONLY_WITH_AGGREGATE_MONITOR",
        "p6_gate_reference_policy": "HISTORICAL_REFERENCE_ONLY_FRESH_REPLAY_REQUIRED",
    }:
        _fail("observation.contracts", "P6 contract snapshot drifted")


def _contract_and_frozen_owner_evidence(root: Path) -> JsonObject:
    files: list[JsonObject] = []
    for relative, markers in _FROZEN_MARKERS.items():
        path = root / relative
        current = path.read_bytes()
        base = subprocess.run(
            ["git", "show", f"{DIFF_BASE}:{relative}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if base.returncode != 0 or base.stdout != current:
            _fail("contracts", f"frozen contract changed: {relative}")
        text = current.decode("utf-8")
        if any(marker not in text for marker in markers):
            _fail("contracts", f"semantic marker missing: {relative}")
        files.append({"path": relative, "sha256": _bytes_fingerprint(current)})
    schemas: list[JsonObject] = []
    for relative in _DURATION_SCHEMAS:
        payload = _load_json(root / relative, f"schema.{relative}")
        properties = _object(payload.get("properties"), f"schema.{relative}.properties")
        version_property = _object(
            properties.get("schema_set_version"),
            f"schema.{relative}.properties.schema_set_version",
        )
        if version_property.get("const") != "2.9.0":
            _fail("schemas", f"schema set drifted: {relative}")
        current = (root / relative).read_bytes()
        base = subprocess.run(
            ["git", "show", f"{DIFF_BASE}:{relative}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if base.returncode != 0 or base.stdout != current:
            _fail("schemas", f"duration schema changed: {relative}")
        schemas.append({"path": relative, "sha256": _bytes_fingerprint(current)})
    changed = _git(
        root,
        "diff",
        "--name-only",
        DIFF_BASE,
        "--",
        *_FROZEN_OWNER_PATHS,
    ).splitlines()
    forbidden_changes = []
    for relative in changed:
        expected_successor_digest = _POST_P6_ADDITIVE_OWNER_SHA256.get(relative)
        if expected_successor_digest is None:
            forbidden_changes.append(relative)
            continue
        path = root / relative
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected_successor_digest:
            forbidden_changes.append(relative)
    if forbidden_changes:
        _fail(
            "frozen_owner_paths",
            f"forbidden owner changes: {forbidden_changes}",
        )
    return {
        "status": "PASS",
        "accepted_adr": "ADR-0016",
        "schema_set_version": "2.9.0",
        "contract_files": files,
        "duration_schemas": schemas,
        "duration_schema_count": len(schemas),
        "frozen_owner_paths": list(_FROZEN_OWNER_PATHS),
        "changed_frozen_owner_paths": [],
        "migration_head": "0005_replan_event_persistence",
        "dependency_lock_changed": False,
        "state_machine_changed": False,
        "workflow_changed": False,
    }


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
    source = "tests/p6/p6_exit_gate_audit.py"
    output = _git(
        root,
        "log",
        "--diff-filter=A",
        "--format=%H",
        "--",
        source,
        check=False,
    )
    commits = [line.strip() for line in output.splitlines() if line.strip()]
    if commits:
        commit = commits[0]
        changed = _git(root, "diff", "--name-only", f"{DIFF_BASE}..{commit}")
        return (
            sorted(
                line.strip().replace("\\", "/")
                for line in changed.splitlines()
                if line.strip()
            ),
            "EXIT_AUDIT_INTRODUCTION_COMMIT",
            commit,
        )
    return _working_tree_paths(root), "WORKING_TREE", _code_commit(root)


def _scope_evidence(root: Path) -> JsonObject:
    changed, source, implementation_commit = _task_scope_paths(root)
    unexpected = sorted(set(changed) - _ALLOWED_TRACKED_PATHS)
    missing = sorted(_ALLOWED_TRACKED_PATHS - set(changed))
    if unexpected:
        _fail("scope", f"paths outside exact allow-list: {unexpected}")
    if missing:
        _fail("scope", f"required paths missing: {missing}")
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


def _check(check_id: str, evidence: object) -> JsonObject:
    return {"check_id": check_id, "status": "PASS", "evidence": evidence}


def run_p6_exit_gate_audit(
    *,
    root: Path,
    provider_observation: Mapping[str, object],
    subreport_dir: Path | None = None,
) -> JsonObject:
    """Fresh-run P6 and make an independent READY/NOT_READY Exit decision."""

    root = root.resolve()
    code_commit = _code_commit(root)
    validate_provider_observation(provider_observation, root)
    frozen = _contract_and_frozen_owner_evidence(root)
    scope = _scope_evidence(root)
    gate_report = run_p6_duration_vertical_slice_gate(
        root=root,
        repeat=2,
        subreport_dir=(subreport_dir / "owner-replays") if subreport_dir else None,
    )
    gate_manifest = build_p6_duration_gate_manifest(gate_report)
    validate_p6_duration_vertical_slice_report(gate_report)
    validate_p6_duration_gate_manifest(gate_manifest, gate_report)
    if subreport_dir is not None:
        _write_json(subreport_dir / "fresh-p6-gate-report.json", gate_report)
        _write_json(subreport_dir / "fresh-p6-gate-manifest.json", gate_manifest)

    audit = _object(provider_observation.get("provider_audit"), "provider_audit")
    topology = _object(provider_observation.get("task_topology"), "task_topology")
    registers = _object(provider_observation.get("registers"), "registers")
    consistency = _object(
        gate_report.get("semantic_consistency"), "gate.semantic_consistency"
    )
    raw_safe = _object(gate_report.get("raw_safe_boundary"), "gate.raw_safe")
    gate_counts = _object(gate_report.get("counts"), "gate.counts")
    gate_summary = {
        "report_version": gate_report["report_version"],
        "manifest_version": gate_manifest["schema_version"],
        "task_id": gate_report["task_id"],
        "code_commit": gate_report["code_commit"],
        "status": gate_report["status"],
        "repeat_count": gate_report["repeat_count"],
        "stage_order": gate_report["stage_order"],
        "check_count": gate_report["check_count"],
        "owner_stage_executions": gate_counts["owner_stage_executions"],
        "negative_rejections": gate_counts["negative_rejections"],
        "semantic_fingerprint": _items(
            consistency.get("combined_fingerprints"), "combined_fingerprints"
        )[0],
        "report_fingerprint": gate_report["report_fingerprint"],
        "manifest_fingerprint": gate_manifest["manifest_fingerprint"],
        "report_sha256": _fingerprint(gate_report),
        "issues": gate_report["issues"],
        "blocking_gaps": gate_report["blocking_gaps"],
    }
    provider_summary = {
        "observation_version": provider_observation["report_version"],
        "observation_fingerprint": provider_observation["observation_fingerprint"],
        "provider_inventory_fingerprint": audit[
            "provider_inventory_fingerprint"
        ],
        "run_count": audit["run_count"],
        "successful_run_count": audit["successful_run_count"],
        "retained_failed_run_count": audit["retained_failed_run_count"],
        "artifact_count": audit["artifact_count"],
        "successful_artifact_count": audit["successful_artifact_count"],
        "expired_artifact_count": audit["expired_artifact_count"],
        "digest_mismatch_count": audit["digest_mismatch_count"],
        "successful_zip_issue_count": audit["successful_zip_issue_count"],
        "required_context": "validate",
        "required_app_id": 15368,
    }
    checks = [
        _check(
            EXPECTED_CHECK_IDS[0],
            {
                "task_count": topology["task_count"],
                "terminal_done_count": topology["terminal_done_count"],
                "active_task": topology["active_task"],
                "dag_edge_count": topology["dag_edge_count"],
                "cycle_count": topology["cycle_count"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[1],
            {
                "run_count": audit["run_count"],
                "successful_run_count": audit["successful_run_count"],
                "required_context": "validate",
                "required_app_id": 15368,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[2],
            {
                "artifact_count": audit["artifact_count"],
                "successful_artifact_count": audit["successful_artifact_count"],
                "expired_artifact_count": audit["expired_artifact_count"],
                "digest_mismatch_count": audit["digest_mismatch_count"],
                "successful_zip_issue_count": audit[
                    "successful_zip_issue_count"
                ],
                "json_entry_count": audit["json_entry_count"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[3],
            deepcopy(provider_observation["failure_corrective_chain"]),
        ),
        _check(
            EXPECTED_CHECK_IDS[4],
            {
                "accepted_adr": frozen["accepted_adr"],
                "contract_file_count": len(cast(list[Any], frozen["contract_files"])),
                "schema_set_version": frozen["schema_set_version"],
                "duration_schema_count": frozen["duration_schema_count"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[5],
            {
                "changed_frozen_owner_paths": frozen[
                    "changed_frozen_owner_paths"
                ],
                "migration_head": frozen["migration_head"],
                "dependency_lock_changed": frozen["dependency_lock_changed"],
                "state_machine_changed": frozen["state_machine_changed"],
                "workflow_changed": frozen["workflow_changed"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[6],
            {
                "repeat_count": gate_summary["repeat_count"],
                "stage_order": gate_summary["stage_order"],
                "owner_stage_executions": gate_summary["owner_stage_executions"],
                "semantic_fingerprint": gate_summary["semantic_fingerprint"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[7],
            {
                "gate_check_count": gate_summary["check_count"],
                "gate_issues": gate_summary["issues"],
                "gate_blocking_gaps": gate_summary["blocking_gaps"],
                "reuse_policy": "FRESH_EXECUTION_NOT_STALE_P6_09_PASS",
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[8],
            {
                "raw_rows_included": raw_safe["p6_raw_rows_included"],
                "feature_records_included": raw_safe[
                    "p6_feature_records_included"
                ],
                "labels_included": raw_safe["p6_labels_included"],
                "production_authorized": raw_safe["production_authorized"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[9],
            {
                "model_standard_mae": [11, 20],
                "coverage": "4/4",
                "train_label_semantic_reads": 0,
                "deterministic_replays": 2,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[10],
            {
                "fallback_reason_count": 19,
                "standard_duration_authority": "UNCHANGED_EXACT_FALLBACK",
                "default_enabled": False,
                "invalid_standard_authority": "FAIL_CLOSED",
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[11],
            {
                "p2_problem_solver_replayed": True,
                "fresh_validator_passes_per_replay": 3,
                "formal_mutations": ["C-003", "C-010"],
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[12],
            {
                "recommendation_authority": "ADVISORY_ONLY",
                "runtime_fallback_reason": "DRIFT_GATE_DISABLED",
                "automatic_actions": 0,
                "persistence": False,
            },
        ),
        _check(
            EXPECTED_CHECK_IDS[13],
            {
                "scenario_steps_per_replay": 5,
                "fresh_validator_passes_per_replay": 5,
                "facts_freeze_change_report_simulator": "PRESERVED",
            },
        ),
        _check(EXPECTED_CHECK_IDS[14], registers),
        _check(EXPECTED_CHECK_IDS[15], scope),
        _check(EXPECTED_CHECK_IDS[16], dict(_BOUNDARIES)),
    ]
    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "audit_task": TASK_ID,
        "task_status": "in_progress_ready_for_exact_provider",
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "validation_profile": VALIDATION_PROFILE,
        "decision": "READY",
        "impact_rules": list(IMPACT_RULES),
        "test_ids": list(TEST_IDS),
        "provider_evidence": provider_summary,
        "task_topology": topology,
        "frozen_contracts": frozen,
        "fresh_p6_gate": gate_summary,
        "registers": registers,
        "scope_evidence": scope,
        "checks": checks,
        "check_count": len(checks),
        "issues": [],
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
        "implementation_provider": "PENDING_EXACT_SHA",
    }
    report = _with_fingerprint(report, "report_fingerprint")
    validate_p6_exit_gate_report(report)
    return report


def validate_p6_exit_gate_report(report: Mapping[str, object]) -> None:
    """Validate a strict successful TASK-P6-10 Exit report."""

    expected_keys = {
        "report_version",
        "audit_task",
        "task_status",
        "code_commit",
        "diff_base",
        "generated_at_utc",
        "validation_profile",
        "decision",
        "impact_rules",
        "test_ids",
        "provider_evidence",
        "task_topology",
        "frozen_contracts",
        "fresh_p6_gate",
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
        _fail("report", "unexpected or missing field")
    for key, expected in (
        ("report_version", REPORT_VERSION),
        ("audit_task", TASK_ID),
        ("task_status", "in_progress_ready_for_exact_provider"),
        ("diff_base", DIFF_BASE),
        ("validation_profile", VALIDATION_PROFILE),
        ("decision", "READY"),
        ("impact_rules", list(IMPACT_RULES)),
        ("test_ids", list(TEST_IDS)),
        ("issues", []),
        ("blocking_gaps", []),
        ("boundaries", _BOUNDARIES),
        ("implementation_provider", "PENDING_EXACT_SHA"),
    ):
        if report.get(key) != expected:
            _fail(f"report.{key}", "identity, decision, or boundary drifted")
    projection = dict(report)
    observed = projection.pop("report_fingerprint")
    if observed != _fingerprint(projection):
        _fail("report.report_fingerprint", "canonical mismatch")
    provider = _object(report.get("provider_evidence"), "report.provider")
    if (
        provider.get("provider_inventory_fingerprint")
        != _EXPECTED_PROVIDER_INVENTORY_FINGERPRINT
        or provider.get("run_count") != 18
        or provider.get("successful_run_count") != 17
        or provider.get("retained_failed_run_count") != 1
        or provider.get("artifact_count") != 48
        or provider.get("expired_artifact_count") != 0
        or provider.get("digest_mismatch_count") != 0
        or provider.get("required_context") != "validate"
        or provider.get("required_app_id") != 15368
    ):
        _fail("report.provider_evidence", "provider summary drifted")
    gate = _object(report.get("fresh_p6_gate"), "report.fresh_p6_gate")
    if (
        gate.get("task_id") != "TASK-P6-09"
        or gate.get("status") != "PASS"
        or gate.get("repeat_count") != 2
        or gate.get("check_count") != 13
        or gate.get("owner_stage_executions") != 18
        or gate.get("negative_rejections") != 10
        or gate.get("issues") != []
        or gate.get("blocking_gaps") != []
    ):
        _fail("report.fresh_p6_gate", "fresh Gate evidence drifted")
    scope = _object(report.get("scope_evidence"), "report.scope")
    if (
        scope.get("status") != "PASS"
        or set(_items(scope.get("changed_paths"), "scope.changed_paths"))
        != _ALLOWED_TRACKED_PATHS
        or scope.get("unexpected_paths") != []
        or scope.get("missing_paths") != []
        or scope.get("forbidden_owner_changes") != 0
    ):
        _fail("report.scope_evidence", "exact scope drifted")
    checks = _items(report.get("checks"), "report.checks")
    if (
        report.get("check_count") != len(EXPECTED_CHECK_IDS)
        or tuple(_object(row, "check").get("check_id") for row in checks)
        != EXPECTED_CHECK_IDS
        or any(_object(row, "check").get("status") != "PASS" for row in checks)
    ):
        _fail("report.checks", "check identity/count/status drifted")


def build_p6_exit_gate_manifest(report: Mapping[str, object]) -> JsonObject:
    """Build the compact provider-bound P6 Exit manifest."""

    validate_p6_exit_gate_report(report)
    provider = _object(report.get("provider_evidence"), "report.provider")
    gate = _object(report.get("fresh_p6_gate"), "report.gate")
    manifest: JsonObject = {
        "schema_version": MANIFEST_VERSION,
        "task_id": TASK_ID,
        "code_commit": report["code_commit"],
        "diff_base": DIFF_BASE,
        "validation_profile": VALIDATION_PROFILE,
        "decision": "READY",
        "report_version": REPORT_VERSION,
        "report_fingerprint": report["report_fingerprint"],
        "report_sha256": _fingerprint(report),
        "provider_inventory_fingerprint": provider[
            "provider_inventory_fingerprint"
        ],
        "provider_observation_fingerprint": provider[
            "observation_fingerprint"
        ],
        "fresh_p6_gate_report_fingerprint": gate["report_fingerprint"],
        "fresh_p6_gate_manifest_fingerprint": gate["manifest_fingerprint"],
        "fresh_p6_gate_semantic_fingerprint": gate["semantic_fingerprint"],
        "check_ids": list(EXPECTED_CHECK_IDS),
        "check_count": len(EXPECTED_CHECK_IDS),
        "impact_rules": list(IMPACT_RULES),
        "issues": [],
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
        "provider_binding": {
            "required_context": "validate",
            "required_app_id": 15368,
            "validation_profile": "FULL",
            "exit_execution_evidence": (
                "FULL_BACKEND_JUNIT_TESTCASE_AND_TASK_BASE_DECISION_CHECK_GAP_PROPERTIES"
            ),
            "owner_replay_evidence": (
                "FULL_VALIDATION_BUILD_VALIDATION_JSON_ARTIFACTS"
            ),
            "workflow_changed": False,
        },
    }
    return _with_fingerprint(manifest, "manifest_fingerprint")


def validate_p6_exit_gate_manifest(
    manifest: Mapping[str, object], report: Mapping[str, object] | None = None
) -> None:
    """Validate the compact P6 Exit evidence manifest."""

    expected_keys = {
        "schema_version",
        "task_id",
        "code_commit",
        "diff_base",
        "validation_profile",
        "decision",
        "report_version",
        "report_fingerprint",
        "report_sha256",
        "provider_inventory_fingerprint",
        "provider_observation_fingerprint",
        "fresh_p6_gate_report_fingerprint",
        "fresh_p6_gate_manifest_fingerprint",
        "fresh_p6_gate_semantic_fingerprint",
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
        _fail("manifest", "unexpected or missing field")
    for key, expected in (
        ("schema_version", MANIFEST_VERSION),
        ("task_id", TASK_ID),
        ("diff_base", DIFF_BASE),
        ("validation_profile", VALIDATION_PROFILE),
        ("decision", "READY"),
        ("report_version", REPORT_VERSION),
        ("provider_inventory_fingerprint", _EXPECTED_PROVIDER_INVENTORY_FINGERPRINT),
        ("check_ids", list(EXPECTED_CHECK_IDS)),
        ("check_count", len(EXPECTED_CHECK_IDS)),
        ("impact_rules", list(IMPACT_RULES)),
        ("issues", []),
        ("blocking_gaps", []),
        ("boundaries", _BOUNDARIES),
    ):
        if manifest.get(key) != expected:
            _fail(f"manifest.{key}", "identity or decision drifted")
    projection = dict(manifest)
    observed = projection.pop("manifest_fingerprint")
    if observed != _fingerprint(projection):
        _fail("manifest.manifest_fingerprint", "canonical mismatch")
    provider_binding = _object(
        manifest.get("provider_binding"), "manifest.provider_binding"
    )
    if provider_binding != {
        "required_context": "validate",
        "required_app_id": 15368,
        "validation_profile": "FULL",
        "exit_execution_evidence": (
            "FULL_BACKEND_JUNIT_TESTCASE_AND_TASK_BASE_DECISION_CHECK_GAP_PROPERTIES"
        ),
        "owner_replay_evidence": "FULL_VALIDATION_BUILD_VALIDATION_JSON_ARTIFACTS",
        "workflow_changed": False,
    }:
        _fail("manifest.provider_binding", "provider binding drifted")
    if report is not None:
        validate_p6_exit_gate_report(report)
        if (
            manifest.get("code_commit") != report.get("code_commit")
            or manifest.get("report_fingerprint") != report.get("report_fingerprint")
            or manifest.get("report_sha256") != _fingerprint(report)
        ):
            _fail("manifest.report", "report binding drifted")


def _failure_report(error: Exception, root: Path) -> JsonObject:
    field = error.field if isinstance(error, P6ExitGateAuditError) else "orchestrator"
    try:
        code_commit = _code_commit(root)
    except Exception:
        code_commit = "unavailable"
    return {
        "report_version": REPORT_VERSION,
        "audit_task": TASK_ID,
        "task_status": "in_progress_not_ready",
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "validation_profile": VALIDATION_PROFILE,
        "decision": "NOT_READY",
        "impact_rules": list(IMPACT_RULES),
        "issues": [
            {
                "issue_id": "P6-EXIT-GATE-AUDIT-001",
                "field": field,
                "error_type": type(error).__name__,
            }
        ],
        "blocking_gaps": [
            {
                "gap_id": "P6-EXIT-GATE-AUDIT-001",
                "field": field,
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
        "code_commit": report.get("code_commit"),
        "diff_base": DIFF_BASE,
        "validation_profile": VALIDATION_PROFILE,
        "decision": "NOT_READY",
        "issues": deepcopy(report.get("issues")),
        "blocking_gaps": deepcopy(report.get("blocking_gaps")),
        "boundaries": dict(_BOUNDARIES),
        "provider_binding": "NOT_ELIGIBLE",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--provider-observation",
        type=Path,
        default=Path("docs/p6-exit-gate-audit-observations.v1.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p6-exit-gate-audit.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("build/validation/p6-exit-gate-evidence-manifest.json"),
    )
    parser.add_argument(
        "--subreport-dir",
        type=Path,
        default=Path("build/validation/p6-10-subreports"),
    )
    parser.add_argument("--collect-provider-observation", action="store_true")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("build/provider/P6-10-exact-provider-artifacts/predecessors"),
    )
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    observation_path = (
        arguments.provider_observation
        if arguments.provider_observation.is_absolute()
        else root / arguments.provider_observation
    )
    if arguments.collect_provider_observation:
        artifacts_dir = (
            arguments.artifacts_dir
            if arguments.artifacts_dir.is_absolute()
            else root / arguments.artifacts_dir
        )
        observation = collect_provider_observation(
            root=root,
            artifacts_dir=artifacts_dir,
        )
        _write_json(observation_path, observation)
        print(json.dumps(observation["provider_audit"], sort_keys=True))
        return 0
    report_path = arguments.report if arguments.report.is_absolute() else root / arguments.report
    manifest_path = (
        arguments.manifest if arguments.manifest.is_absolute() else root / arguments.manifest
    )
    subreport_dir = (
        arguments.subreport_dir
        if arguments.subreport_dir.is_absolute()
        else root / arguments.subreport_dir
    )
    try:
        report = run_p6_exit_gate_audit(
            root=root,
            provider_observation=_load_json(observation_path, "provider_observation"),
            subreport_dir=subreport_dir,
        )
        manifest = build_p6_exit_gate_manifest(report)
        validate_p6_exit_gate_manifest(manifest, report)
    except Exception as error:
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
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACTIVATION_VERIFIED_AT",
    "DIFF_BASE",
    "EXPECTED_CHECK_IDS",
    "IMPACT_RULES",
    "MANIFEST_VERSION",
    "OBSERVATION_VERSION",
    "P6ExitGateAuditError",
    "REPORT_VERSION",
    "TASK_ID",
    "TEST_IDS",
    "build_p6_exit_gate_manifest",
    "collect_provider_observation",
    "main",
    "run_p6_exit_gate_audit",
    "validate_p6_exit_gate_manifest",
    "validate_p6_exit_gate_report",
    "validate_provider_observation",
]
