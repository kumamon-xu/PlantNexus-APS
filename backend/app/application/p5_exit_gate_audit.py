"""Build the independent TASK-P5-22 Exit Gate audit report."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Never

import yaml

from app.application.p4_gate_report import validate_p4_vertical_slice_report
from app.application.p5_portfolio_gate_report import (
    validate_p5_portfolio_gate_report,
)


type JsonObject = dict[str, Any]

REPORT_VERSION = "p5-exit-gate-evidence-manifest.v1"
OBSERVATION_VERSION = "p5-exit-gate-audit-observations.v1"
TASK_ID = "TASK-P5-22"
DIFF_BASE = "d0a83c58cb4a2d4afa76e8c8cff08441574e2e30"
P4_CLOSURE = "892c46d660a6bf3cde8ed473199f38746d041e47"
P5_QUALIFICATION_FINGERPRINT = (
    "sha256:9d6bacb5888ed5a92219935463d5e67177a8fa52965beccb5463ce943276b6d1"
)
PROVIDER_RUN_INVENTORY_FINGERPRINT = (
    "sha256:a702ad11aeba9d8ee90a2b0cee1df8e859f4eb000df2761a2e21cfb31a47827d"
)

IMPACT_RULES = (
    "IMPACT-APPLICATION",
    "IMPACT-TESTS",
    "IMPACT-INFRA",
    "IMPACT-DOCS",
)
TEST_IDS = (
    "TEST-P5-EXIT-GATE-001",
    "TEST-P5-PORTFOLIO-GATE-001",
    "TEST-TRACEABILITY-VALIDATOR",
    "TEST-P4-VERTICAL-SLICE-001",
)

_CANCELLED_TASKS = tuple(f"TASK-P5-{index:02d}" for index in range(3, 21))
_P5_CANDIDATES = (
    "P5-CANDIDATE-SECONDARY-RESOURCE",
    "P5-CANDIDATE-SEQUENCE-SETUP",
    "P5-CANDIDATE-MATERIAL-COMPETITION",
    "P5-CANDIDATE-BATCH",
    "P5-CANDIDATE-SPLIT-MERGE",
    "P5-CANDIDATE-BUFFER",
    "P5-CANDIDATE-PREEMPTION",
    "P5-CANDIDATE-DECOMPOSITION",
    "P5-CANDIDATE-ROLLING-HORIZON",
)
_UNSUPPORTED_CONSTRAINTS = tuple(f"C-{index:03d}" for index in range(12, 19))
_P4_STAGE_ORDER = (
    "machine_contracts",
    "replan_persistence",
    "execution_fact_projection",
    "freeze_window",
    "stability_change_report",
    "replan_solver",
    "replan_application",
    "execution_simulator",
    "disruption_replay",
    "change_report_output",
    "replanning_api",
)
_EXPECTED_FROZEN_OBJECTS: JsonObject = {
    "schemas": "3a6a73c6df46048e2c053355959a3c684525cbe9",
    "backend/migrations": "bc11121cc424bb6014c8cc82f89af8890582207a",
    "backend/app/planning": "ab99c3c170e9d5fe4c06e1d266f234dd24e95510",
    "docs/adr": "ed1d8a2032a7f6715c18476bafcd16eeab5fe8cf",
    "schemas/rules/state-machines.v1.yaml": (
        "cd9fedc3a9c4b521646b16ec5628b00d99d249f2"
    ),
    "schemas/rules/capability-registry.v1.yaml": (
        "0077cfcbfff9c67d747ae3e97dddcd1f3ece0d6f"
    ),
    "schemas/rules/constraint-rule-sheet.v1.yaml": (
        "3d6940fcb5f8135232fa818d3f60962b6b85f648"
    ),
    "pyproject.toml": "241ccc5d343c4527c4e7a419ae0c282fe29e6086",
    "uv.lock": "a04b1285e0e1da0d2a2341a879d5e8cc718522b7",
    "frontend/package.json": "ff9879bcec4095edb44e53bc45783e5de9d3d5e6",
    "frontend/package-lock.json": "6e053d1aa2db87fb789015f0a01807f326a0749f",
}
_EXPECTED_CHECKS = (
    "p5-task-topology-and-terminality",
    "p5-required-provider-run-and-app-topology",
    "p5-provider-download-expiry-digest-and-json-semantics",
    "p5-historical-failure-corrective-chain",
    "p5-capability-qualification-fresh-replay",
    "p5-empty-selected-nine-deferred-eighteen-cancelled-portfolio",
    "p5-no-selected-owner-or-advanced-package-activation",
    "p5-c012-c018-unsupported-and-global-only-boundary",
    "p5-portfolio-gate-fresh-independent-validation",
    "p4-dynamic-replanning-fresh-independent-regression",
    "schema-migration-dependency-adr-and-state-byte-preservation",
    "formal-validator-benchmark-and-simulation-boundaries",
    "open-sim-risk-and-traceability-register-carry-forward",
    "p5-p6-production-authority-external-deployment-capacity-boundary",
    "p5-exit-ready-does-not-transition-phase-or-start-p6",
)
_ALLOWED_TASK_PATHS = frozenset(
    {
        ".github/workflows/ci.yml",
        "backend/app/application/p5_exit_gate_audit.py",
        "backend/tests/contract/test_p5_exit_gate_rejections.py",
        "backend/tests/integration/test_p5_exit_gate.py",
        "backend/tests/integration/test_ci_contract.py",
        "docs/p5-exit-gate-audit-observations.v1.json",
        "README.md",
        "docs/README.md",
        "docs/architecture/configuration-environments-and-isolation.md",
        "docs/architecture/end-to-end-planning-flow.md",
        "docs/core/capability-matrix.md",
        "docs/planning/planning-strategies.md",
        "docs/planning/replanning.md",
        "docs/simulation/benchmark-harness.md",
        "docs/simulation/execution-simulator-and-disruptions.md",
    }
)
_BOUNDARIES: JsonObject = {
    "current_phase": "P5",
    "p5_milestone": "ACTIVE_AWAITING_USER_TRANSITION",
    "p6_plus": "NOT_ENTERED",
    "production_readiness": "NOT_CLAIMED",
    "production_identity_and_approval_authority": "NOT_FORMED",
    "external_publish_integration_or_transfer": "NONE",
    "uat": "NOT_PERFORMED",
    "deployment": "NOT_PERFORMED",
    "capacity_and_sla": "NOT_ESTABLISHED",
    "data_plane": "SIMULATION_DEVELOPMENT_ONLY",
    "automatic_phase_transition": "PROHIBITED",
}


class P5ExitGateAuditError(ValueError):
    """Raised when an Exit audit input or result fails closed."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"P5_EXIT_GATE_AUDIT at {field}: {message}")


def _fail(field: str, message: str) -> Never:
    raise P5ExitGateAuditError(field, message)


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, Mapping):
        _fail(field, "expected object")
    return dict(value)


def _items(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(field, "expected array")
    return value


def _canonical_fingerprint(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(raw).hexdigest()}"


def _file_fingerprint(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _code_commit(root: Path) -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT")
    if value and len(value) == 40 and all(c in "0123456789abcdef" for c in value):
        return value
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    candidate = completed.stdout.strip()
    if len(candidate) != 40 or any(c not in "0123456789abcdef" for c in candidate):
        _fail("code_commit", "git HEAD is not an exact lowercase SHA")
    return candidate


def _git(root: Path, *arguments: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _load_json(path: Path, field: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise P5ExitGateAuditError(field, "cannot load valid UTF-8 JSON") from error
    return _object(value, field)


def validate_provider_observation(observation: Mapping[str, object]) -> None:
    """Validate the downloaded, exact P5 predecessor provider inventory."""

    for field, expected in (
        ("report_version", OBSERVATION_VERSION),
        ("audit_task", TASK_ID),
        ("immutable_diff_base", DIFF_BASE),
        ("audited_business_baseline", DIFF_BASE),
        ("validation_profile", "PHASE_GATE"),
        ("implementation_provider", "PENDING_EXACT_SHA"),
        (
            "evidence_only_closure_provider",
            "PENDING_AFTER_IMPLEMENTATION_PROVIDER",
        ),
    ):
        if observation.get(field) != expected:
            _fail(f"observation.{field}", f"expected {expected!r}")

    branch = _object(observation.get("branch_protection"), "observation.branch")
    if branch != {
        "required_context": "validate",
        "expected_app_id": 15368,
        "strict": False,
        "status": "PASS",
    }:
        _fail("observation.branch_protection", "required provider changed")

    topology = _object(observation.get("task_topology"), "observation.topology")
    done = _object(topology.get("done"), "observation.topology.done")
    if done != {
        "TASK-P5-00": {
            "implementation": "a316d7a5ebf2e8c7e33da46cf1d7c08f2dfbdfa3",
            "closure": "4ccb2ed99ffe73abeb0462efff4a5342cd7c5522",
        },
        "TASK-P5-01": {
            "implementation": "88fb9f53ab5425d72ee6659188b689a26d0e387a",
            "closure": "01b8918db62cc9f5c4421d0b90d93151ddc552f1",
        },
        "TASK-P5-02": {
            "implementation": "ed9ee75122341c1a71b641edc445e2a58cac70de",
            "closure": "d7779c014351d41909322b967c5c8eca68713e8b",
        },
        "TASK-P5-21": {
            "implementation": "c8ffd042738ffe79c350262aa7195daa9a7bf083",
            "closure": DIFF_BASE,
        },
    }:
        _fail("observation.task_topology.done", "done implementation chain changed")
    if (
        tuple(_items(topology.get("cancelled"), "topology.cancelled"))
        != _CANCELLED_TASKS
        or topology.get("active") != TASK_ID
        or topology.get("active_diff_base") != DIFF_BASE
        or topology.get("direct_dependency") != "TASK-P5-21"
        or topology.get("selected_owners") != []
        or topology.get("selected_count") != 0
        or topology.get("deferred_count") != 9
    ):
        _fail("observation.task_topology", "terminal or selected topology changed")

    provider = _object(
        observation.get("predecessor_provider_audit"), "observation.provider"
    )
    expected_counts = {
        "predecessor_base": P4_CLOSURE,
        "commit_count": 11,
        "workflow_run_count": 11,
        "successful_run_count": 8,
        "failed_run_count": 3,
        "artifact_count": 22,
        "expired_artifact_count": 0,
        "digest_mismatch_count": 0,
        "required_check_mismatch_count": 0,
        "json_count": 216,
        "successful_json_count": 126,
        "failed_json_count": 90,
        "machine_json_count": 187,
        "browser_json_count": 12,
        "json_parse_error_count": 0,
        "semantic_issue_count": 0,
        "run_inventory_fingerprint": PROVIDER_RUN_INVENTORY_FINGERPRINT,
    }
    for field, expected in expected_counts.items():
        if provider.get(field) != expected:
            _fail(f"observation.provider.{field}", f"expected {expected!r}")
    runs = _items(provider.get("runs"), "observation.provider.runs")
    if len(runs) != 11 or _canonical_fingerprint(runs) != PROVIDER_RUN_INVENTORY_FINGERPRINT:
        _fail("observation.provider.runs", "exact run/artifact inventory changed")
    for index, raw in enumerate(runs):
        run = _object(raw, f"observation.provider.runs[{index}]")
        artifacts = _items(run.get("artifacts"), f"provider.runs[{index}].artifacts")
        if (
            run.get("required_app_id") != 15368
            or run.get("conclusion") not in {"success", "failure"}
            or len(artifacts) != 2
            or any(_object(item, "artifact").get("expired") is not False for item in artifacts)
            or any(
                not str(_object(item, "artifact").get("digest", "")).startswith(
                    "sha256:"
                )
                for item in artifacts
            )
        ):
            _fail(f"observation.provider.runs[{index}]", "provider row changed")

    failures = _items(
        observation.get("historical_failure_corrective_chain"),
        "observation.failure_chain",
    )
    expected_failure_pairs = (
        (
            "c3761d0505690567ab6b60be1d04041dab0c0652",
            "88fb9f53ab5425d72ee6659188b689a26d0e387a",
        ),
        (
            "e0dee8544a27adcae7ca98fabe2665452bf38d4d",
            "d00386f42fbd366afa94dae4cc93096c0242ce0e",
        ),
        (
            "d00386f42fbd366afa94dae4cc93096c0242ce0e",
            "c8ffd042738ffe79c350262aa7195daa9a7bf083",
        ),
    )
    observed_failure_pairs = tuple(
        (
            _object(raw, "failure").get("failed_sha"),
            _object(raw, "failure").get("corrective_sha"),
        )
        for raw in failures
    )
    if observed_failure_pairs != expected_failure_pairs or any(
        _object(raw, "failure").get("status") != "CORRECTED" for raw in failures
    ):
        _fail("observation.failure_chain", "failure/corrective chain changed")

    frozen = _object(
        observation.get("frozen_git_objects"), "observation.frozen_git_objects"
    )
    if frozen != _EXPECTED_FROZEN_OBJECTS:
        _fail("observation.frozen_git_objects", "frozen object inventory changed")

    contracts = _object(observation.get("contracts"), "observation.contracts")
    if contracts != {
        "schema_set_version": "2.8.0",
        "latest_migration": "0005_replan_event_persistence",
        "state_machine_contract": "state-machines.v1",
        "accepted_adrs": ["ADR-0013", "ADR-0014", "ADR-0015"],
        "formed_strategy": "GLOBAL_ONLY",
        "unsupported_constraints": list(_UNSUPPORTED_CONSTRAINTS),
        "advanced_contract_schema_solver_validator_feature_flag_changes": [],
    }:
        _fail("observation.contracts", "contract boundary changed")

    registers = _object(observation.get("registers"), "observation.registers")
    expected_registers = {
        "requirement_roots": 30,
        "trace_rows": 30,
        "test_ids": 73,
        "prod_open_count": 15,
        "prod_open_status": "ALL_OPEN",
        "sim_assumption_count": 20,
        "sim_assumption_status": "ALL_ACTIVE",
        "risk_count": 17,
        "risk_status": "ALL_MONITORED",
        "owner_test_ids": "RETAINED_INACTIVE_FOR_FUTURE_REQUALIFICATION",
        "new_prod_open": [],
        "new_sim_assumptions": [],
        "new_risks": [],
    }
    if registers != expected_registers:
        _fail("observation.registers", "OPEN/SIM/risk/traceability changed")

    reference = _object(
        observation.get("p4_exit_reference"), "observation.p4_exit_reference"
    )
    if reference != {
        "decision": "READY",
        "blocking_gaps": [],
        "implementation": "3637f514947397f7ba04a6ff3061a48f1809b44e",
        "closure": P4_CLOSURE,
        "reuse_policy": "HISTORICAL_REFERENCE_ONLY_FRESH_P4_REGRESSION_REQUIRED",
    }:
        _fail("observation.p4_exit_reference", "P4 historical reference changed")

    boundaries = _object(observation.get("boundaries"), "observation.boundaries")
    if (
        boundaries.get("current_phase") != "P5"
        or boundaries.get("p6_plus") != "NOT_ENTERED"
        or boundaries.get("production_readiness") != "NOT_CLAIMED"
        or boundaries.get("production_identity_and_approval_authority")
        != "NOT_FORMED"
        or boundaries.get("external_publish_integration_or_transfer") != "NONE"
        or boundaries.get("uat") != "NOT_PERFORMED"
        or boundaries.get("deployment") != "NOT_PERFORMED"
        or boundaries.get("capacity_and_sla") != "NOT_ESTABLISHED"
        or boundaries.get("data_plane") != "SIMULATION_DEVELOPMENT_ONLY"
    ):
        _fail("observation.boundaries", "P5/P6/Production boundary changed")


def _validate_qualification(report: Mapping[str, object], code_commit: str) -> None:
    for field, expected in (
        ("report_version", "p5-capability-qualification-report.v1"),
        ("status", "PASS"),
        ("task_id", "TASK-P5-01"),
        ("code_commit", code_commit),
        ("diff_base", "4ccb2ed99ffe73abeb0462efff4a5342cd7c5522"),
        ("validation_profile", "HIGH_RISK"),
        ("semantic_projection_fingerprint", P5_QUALIFICATION_FINGERPRINT),
        ("check_count", 11),
        ("issues", []),
        ("blocking_issues", []),
    ):
        if report.get(field) != expected:
            _fail(f"qualification.{field}", f"expected {expected!r}")
    decisions = _items(report.get("decisions"), "qualification.decisions")
    if (
        tuple(_object(row, "decision").get("candidate_id") for row in decisions)
        != _P5_CANDIDATES
        or any(_object(row, "decision").get("decision") != "DEFERRED" for row in decisions)
    ):
        _fail("qualification.decisions", "nine independent DEFERRED decisions changed")
    portfolio = _object(report.get("portfolio"), "qualification.portfolio")
    if portfolio != {
        "selected": [],
        "deferred": list(_P5_CANDIDATES),
        "selected_count": 0,
        "deferred_count": 9,
        "p5_02_authorized": False,
    }:
        _fail("qualification.portfolio", "empty selected portfolio changed")
    benchmarks = _items(
        report.get("benchmark_observations"), "qualification.benchmarks"
    )
    if [
        _object(_object(row, "benchmark").get("profile"), "benchmark.profile").get(
            "size"
        )
        for row in benchmarks
    ] != ["XS", "S", "M"]:
        _fail("qualification.benchmarks", "XS/S/M identity changed")
    for index, raw in enumerate(benchmarks):
        benchmark = _object(raw, f"qualification.benchmarks[{index}]")
        quality = _object(benchmark.get("quality"), "benchmark.quality")
        validation = _object(quality.get("validation"), "benchmark.validation")
        boundaries = _object(benchmark.get("boundaries"), "benchmark.boundaries")
        if (
            benchmark.get("status") != "PASS"
            or validation.get("status") != "PASS"
            or boundaries.get("production_capacity_sla")
            != "NOT_ESTABLISHED_OPEN_012"
        ):
            _fail(f"qualification.benchmarks[{index}]", "benchmark boundary changed")
    checks = _items(report.get("checks"), "qualification.checks")
    if len(checks) != 11 or any(
        _object(check, "qualification.check").get("status") != "PASS"
        for check in checks
    ):
        _fail("qualification.checks", "qualification checks changed")


def _validate_gate_reports(
    p5_report: Mapping[str, object],
    p4_report: Mapping[str, object],
    code_commit: str,
) -> None:
    normalized_p4 = _normalize_p4_serialized_object_order(p4_report)
    normalized_p5 = deepcopy(dict(p5_report))
    embedded_p4 = _object(
        normalized_p5.get("p4_regression_evidence"), "p5_gate.p4_regression"
    )
    normalized_p5["p4_regression_evidence"] = (
        _normalize_p4_serialized_object_order(embedded_p4)
    )
    try:
        validate_p5_portfolio_gate_report(normalized_p5)
    except Exception as error:
        raise P5ExitGateAuditError("p5_gate", "P5 Gate contract rejected") from error
    try:
        validate_p4_vertical_slice_report(normalized_p4)
    except Exception as error:
        raise P5ExitGateAuditError("p4_gate", "P4 Gate contract rejected") from error
    if (
        p5_report.get("status") != "PASS"
        or p5_report.get("task_id") != "TASK-P5-21"
        or p5_report.get("code_commit") != code_commit
        or p5_report.get("check_count") != 12
        or p5_report.get("issues") != []
        or p5_report.get("blocking_gaps") != []
    ):
        _fail("p5_gate", "fresh P5 Gate identity or decision changed")
    portfolio = _object(p5_report.get("portfolio"), "p5_gate.portfolio")
    if portfolio != {
        "selected": [],
        "selected_count": 0,
        "deferred_count": 9,
        "cancelled_task_count": 18,
    }:
        _fail("p5_gate.portfolio", "resolved portfolio changed")
    owner_manifest = _object(
        p5_report.get("selected_owner_evidence_manifest"), "p5_gate.owners"
    )
    if (
        owner_manifest.get("owner_report_count") != 0
        or owner_manifest.get("owner_reports") != []
        or owner_manifest.get("unselected_owner_invocations") != []
        or tuple(owner_manifest.get("cancelled_tasks", [])) != _CANCELLED_TASKS
    ):
        _fail("p5_gate.owners", "an unselected owner entered the Gate")
    rejections = _items(
        p5_report.get("unsupported_rejections"), "p5_gate.rejections"
    )
    if (
        tuple(_object(row, "rejection").get("constraint_id") for row in rejections)
        != _UNSUPPORTED_CONSTRAINTS
        or any(
            _object(row, "rejection").get("error_code") != "UNSUPPORTED_CAPABILITY"
            for row in rejections
        )
    ):
        _fail("p5_gate.rejections", "C-012..C-018 rejection changed")

    if (
        p4_report.get("status") != "PASS"
        or p4_report.get("task_id") != "TASK-P4-14"
        or p4_report.get("code_commit") != code_commit
        or p4_report.get("repeat_count") != 2
        or p4_report.get("check_count") != 14
        or p4_report.get("blocking_gaps") != []
    ):
        _fail("p4_gate", "fresh P4 regression identity or decision changed")
    counts = _object(p4_report.get("counts"), "p4_gate.counts")
    expected_counts = {
        "continuous_scenario_step_executions": 10,
        "standard_event_executions": 16,
        "fresh_validator_passes": 10,
        "complete_change_reports": 10,
    }
    for field, expected in expected_counts.items():
        if counts.get(field) != expected:
            _fail(f"p4_gate.counts.{field}", f"expected {expected}")

    embedded_p4 = _object(
        p5_report.get("p4_regression_evidence"), "p5_gate.p4_regression"
    )
    embedded_semantic = _object(
        embedded_p4.get("semantic_consistency"), "p5_gate.p4_semantic"
    )
    independent_semantic = _object(
        p4_report.get("semantic_consistency"), "p4_gate.semantic"
    )
    for field in ("combined_fingerprints", "stage_fingerprints"):
        if embedded_semantic.get(field) != independent_semantic.get(field):
            _fail(
                f"p4_gate.semantic.{field}",
                "P5-embedded and independent P4 replays disagree",
            )


def _normalize_p4_serialized_object_order(
    report: Mapping[str, object],
) -> JsonObject:
    """Restore the normative P4 stage order after JSON object-key sorting.

    The P4/P5 writers retain all raw values but serialize object keys with
    ``sort_keys=True``.  The frozen P4 validator intentionally checks the
    producer's insertion order.  This audit entry point therefore verifies the
    exact stage-key set before restoring that order; values and array order are
    not changed.
    """

    normalized = deepcopy(dict(report))
    replays = normalized.get("backend_replays")
    if replays is None:
        return normalized
    for index, raw in enumerate(_items(replays, "p4_gate.backend_replays")):
        replay = _object(raw, f"p4_gate.backend_replays[{index}]")
        reports = _object(
            replay.get("raw_subreports"),
            f"p4_gate.backend_replays[{index}].raw_subreports",
        )
        if set(reports) != set(_P4_STAGE_ORDER):
            _fail(
                f"p4_gate.backend_replays[{index}].raw_subreports",
                "serialized P4 stage key set changed",
            )
        replay["raw_subreports"] = {
            stage: reports[stage] for stage in _P4_STAGE_ORDER
        }
        _items(replays, "p4_gate.backend_replays")[index] = replay
    normalized["backend_replays"] = replays
    return normalized


def _validate_p4_exit_reference(report: Mapping[str, object]) -> None:
    if (
        report.get("report_version") != "p4-exit-gate-audit-observations.v1"
        or report.get("audit_task") != "TASK-P4-15"
        or report.get("decision") != "READY"
        or report.get("blocking_gaps") != []
        or report.get("immutable_diff_base")
        != "60ac4c17c6de514c036be7bac63e66da589bfb4c"
    ):
        _fail("p4_exit_reference", "frozen P4 Exit reference changed")
    branch = _object(report.get("branch_protection"), "p4_exit.branch")
    if branch.get("required_context") != "validate" or branch.get(
        "expected_app_id"
    ) != 15368:
        _fail("p4_exit_reference.branch", "P4 provider identity changed")


def _verify_frozen_repository(root: Path) -> JsonObject:
    observed: JsonObject = {}
    for path, expected in _EXPECTED_FROZEN_OBJECTS.items():
        actual = _git(root, "rev-parse", f"HEAD:{path}")
        if actual != expected:
            _fail(f"repository.{path}", "frozen Git object changed")
        status = _git(root, "status", "--porcelain=v1", "--", path)
        if status:
            _fail(f"repository.{path}", "working tree changed a frozen path")
        observed[path] = actual

    data_dictionary = yaml.safe_load(
        (root / "schemas/data_dictionary.yaml").read_text(encoding="utf-8")
    )
    if data_dictionary.get("schema_set_version") != "2.8.0":
        _fail("repository.schema_set_version", "must remain 2.8.0")
    migrations = sorted(
        path.stem
        for path in (root / "backend/migrations/versions").glob("*.py")
        if not path.name.startswith("__")
    )
    if not migrations or migrations[-1] != "0005_replan_event_persistence":
        _fail("repository.latest_migration", "migration head changed")
    state_registry = yaml.safe_load(
        (root / "schemas/rules/state-machines.v1.yaml").read_text(encoding="utf-8")
    )
    if state_registry.get("state_registry_version") != "state-machines.v1":
        _fail("repository.state_machine", "state machine version changed")
    capability_registry = yaml.safe_load(
        (root / "schemas/rules/capability-registry.v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    advanced = {
        row["constraint_ids"][0]: (row["status"], row["precheck_behavior"])
        for row in capability_registry["capabilities"]
        if row.get("constraint_ids")
        and row["constraint_ids"][0] in _UNSUPPORTED_CONSTRAINTS
    }
    if advanced != {
        constraint: ("UNSUPPORTED", "UNSUPPORTED_CAPABILITY")
        for constraint in _UNSUPPORTED_CONSTRAINTS
    }:
        _fail("repository.capability_registry", "advanced support state changed")
    for adr_id in ("ADR-0013", "ADR-0014", "ADR-0015"):
        matches = list((root / "docs/adr").glob(f"{adr_id}-*.md"))
        if len(matches) != 1 or "status: accepted" not in matches[0].read_text(
            encoding="utf-8"
        ):
            _fail(f"repository.{adr_id}", "accepted ADR changed")
    return observed


def _task_changed_paths(root: Path) -> list[str]:
    commands = (
        ("diff", "--name-only", f"{DIFF_BASE}..HEAD"),
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    changed: set[str] = set()
    for command in commands:
        output = _git(root, *command)
        changed.update(line.replace("\\", "/") for line in output.splitlines() if line)
    forbidden = sorted(path for path in changed if path not in _ALLOWED_TASK_PATHS)
    if forbidden:
        _fail("task_scope", f"paths outside frozen allow-list: {forbidden}")
    return sorted(changed)


def run_p5_exit_gate_audit(
    *,
    root: Path,
    provider_observation: Mapping[str, object],
    qualification_report: Mapping[str, object],
    p5_gate_report: Mapping[str, object],
    p4_gate_report: Mapping[str, object],
    p4_exit_observation: Mapping[str, object],
) -> JsonObject:
    """Independently evaluate all P5 Exit inputs and return READY or raise."""

    root = root.resolve()
    code_commit = _code_commit(root)
    validate_provider_observation(provider_observation)
    _validate_qualification(qualification_report, code_commit)
    _validate_gate_reports(p5_gate_report, p4_gate_report, code_commit)
    _validate_p4_exit_reference(p4_exit_observation)
    frozen_objects = _verify_frozen_repository(root)
    changed_paths = _task_changed_paths(root)

    checks = [
        {"check_id": check_id, "status": "PASS"} for check_id in _EXPECTED_CHECKS
    ]
    p4_counts = _object(p4_gate_report.get("counts"), "p4_gate.counts")
    return {
        "manifest_version": REPORT_VERSION,
        "audit_task": TASK_ID,
        "task_status": "in_progress_provider_pending",
        "completion_pending": "IMPLEMENTATION_AND_EVIDENCE_ONLY_CLOSURE_PROVIDER",
        "audit_date": "2026-09-01",
        "timezone": "Asia/Hong_Kong",
        "diff_base": DIFF_BASE,
        "audited_business_baseline": DIFF_BASE,
        "repository_head_at_execution": code_commit,
        "validation_profile": "PHASE_GATE",
        "decision": "READY",
        "impact_rules": list(IMPACT_RULES),
        "impact_rule_count": len(IMPACT_RULES),
        "test_ids": list(TEST_IDS),
        "task_topology": _object(
            provider_observation.get("task_topology"), "observation.task_topology"
        ),
        "predecessor_provider_audit": {
            key: value
            for key, value in _object(
                provider_observation.get("predecessor_provider_audit"),
                "observation.provider",
            ).items()
            if key != "runs"
        },
        "historical_failure_corrective_chain": _items(
            provider_observation.get("historical_failure_corrective_chain"),
            "observation.failure_chain",
        ),
        "fresh_evidence": {
            "qualification": {
                "status": "PASS",
                "check_count": 11,
                "semantic_projection_fingerprint": P5_QUALIFICATION_FINGERPRINT,
                "profiles": ["XS", "S", "M"],
                "selected_count": 0,
                "deferred_count": 9,
                "raw_report_sha256": _canonical_fingerprint(qualification_report),
            },
            "p5_portfolio_gate": {
                "status": "PASS",
                "check_count": 12,
                "selected_count": 0,
                "deferred_count": 9,
                "cancelled_task_count": 18,
                "owner_invocation_count": 0,
                "serialization_normalization": "JSON_OBJECT_KEY_ORDER_ONLY",
                "raw_report_sha256": _canonical_fingerprint(p5_gate_report),
            },
            "p4_regression": {
                "status": "PASS",
                "check_count": 14,
                "repeat_count": 2,
                "continuous_scenario_step_executions": p4_counts[
                    "continuous_scenario_step_executions"
                ],
                "standard_event_executions": p4_counts["standard_event_executions"],
                "fresh_validator_passes": p4_counts["fresh_validator_passes"],
                "complete_change_reports": p4_counts["complete_change_reports"],
                "serialization_normalization": "JSON_OBJECT_KEY_ORDER_ONLY",
                "raw_report_sha256": _canonical_fingerprint(p4_gate_report),
            },
        },
        "contracts": _object(
            provider_observation.get("contracts"), "observation.contracts"
        ),
        "frozen_git_objects": frozen_objects,
        "registers": _object(
            provider_observation.get("registers"), "observation.registers"
        ),
        "governance": {
            "task_changed_paths": changed_paths,
            "task_changed_path_count": len(changed_paths),
            "forbidden_scope_paths": [],
            "issues": [],
        },
        "boundaries": dict(_BOUNDARIES),
        "checks": checks,
        "check_count": len(checks),
        "issues": [],
        "blocking_gaps": [],
        "implementation_provider": "PENDING_EXACT_SHA",
        "evidence_only_closure_provider": "PENDING_AFTER_IMPLEMENTATION_PROVIDER",
    }


def validate_p5_exit_gate_report(report: Mapping[str, object]) -> None:
    """Validate an emitted independent P5 Exit manifest."""

    for field, expected in (
        ("manifest_version", REPORT_VERSION),
        ("audit_task", TASK_ID),
        ("diff_base", DIFF_BASE),
        ("audited_business_baseline", DIFF_BASE),
        ("validation_profile", "PHASE_GATE"),
        ("decision", "READY"),
        ("impact_rules", list(IMPACT_RULES)),
        ("test_ids", list(TEST_IDS)),
        ("issues", []),
        ("blocking_gaps", []),
        ("implementation_provider", "PENDING_EXACT_SHA"),
        (
            "evidence_only_closure_provider",
            "PENDING_AFTER_IMPLEMENTATION_PROVIDER",
        ),
    ):
        if report.get(field) != expected:
            _fail(f"report.{field}", f"expected {expected!r}")
    checks = _items(report.get("checks"), "report.checks")
    if (
        report.get("check_count") != len(_EXPECTED_CHECKS)
        or tuple(_object(row, "check").get("check_id") for row in checks)
        != _EXPECTED_CHECKS
        or any(_object(row, "check").get("status") != "PASS" for row in checks)
    ):
        _fail("report.checks", "Exit check identity/count/status changed")
    boundaries = _object(report.get("boundaries"), "report.boundaries")
    if boundaries != _BOUNDARIES:
        _fail("report.boundaries", "P5/P6/Production boundary changed")
    governance = _object(report.get("governance"), "report.governance")
    if governance.get("forbidden_scope_paths") != [] or governance.get("issues") != []:
        _fail("report.governance", "scope issue present")
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in (
        '"p6_plus": "ENTERED"',
        '"production_readiness": "READY"',
        '"production_identity_and_approval_authority": "FORMED"',
        '"external_publish_integration_or_transfer": "FORMED"',
        '"deployment": "PERFORMED"',
        '"capacity_and_sla": "ESTABLISHED"',
    ):
        if forbidden in serialized:
            _fail("report.boundaries", f"forbidden claim present: {forbidden}")


def _failure_report(error: Exception, root: Path) -> JsonObject:
    field = error.field if isinstance(error, P5ExitGateAuditError) else "orchestrator"
    try:
        code_commit = _code_commit(root)
    except Exception:
        code_commit = "unavailable"
    return {
        "manifest_version": REPORT_VERSION,
        "audit_task": TASK_ID,
        "task_status": "in_progress_not_ready",
        "diff_base": DIFF_BASE,
        "repository_head_at_execution": code_commit,
        "validation_profile": "PHASE_GATE",
        "decision": "NOT_READY",
        "impact_rules": list(IMPACT_RULES),
        "issues": [
            {
                "issue_id": "P5-EXIT-GATE-AUDIT-001",
                "field": field,
                "error_type": type(error).__name__,
            }
        ],
        "blocking_gaps": [
            {
                "gap_id": "P5-EXIT-GATE-AUDIT-001",
                "field": field,
                "status": "BLOCKING",
                "remediation": "REQUIRES_SEPARATE_BOUNDED_CORRECTIVE_SHA",
            }
        ],
        "boundaries": dict(_BOUNDARIES),
        "implementation_provider": "NOT_ELIGIBLE",
        "evidence_only_closure_provider": "NOT_ELIGIBLE",
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--provider-observation", type=Path, required=True)
    parser.add_argument("--qualification-report", type=Path, required=True)
    parser.add_argument("--p5-gate-report", type=Path, required=True)
    parser.add_argument("--p4-gate-report", type=Path, required=True)
    parser.add_argument("--p4-exit-observation", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    try:
        report = run_p5_exit_gate_audit(
            root=root,
            provider_observation=_load_json(
                arguments.provider_observation, "provider_observation"
            ),
            qualification_report=_load_json(
                arguments.qualification_report, "qualification_report"
            ),
            p5_gate_report=_load_json(arguments.p5_gate_report, "p5_gate_report"),
            p4_gate_report=_load_json(arguments.p4_gate_report, "p4_gate_report"),
            p4_exit_observation=_load_json(
                arguments.p4_exit_observation, "p4_exit_observation"
            ),
        )
        validate_p5_exit_gate_report(report)
    except Exception as error:
        report = _failure_report(error, root)
        exit_code = 1
    else:
        exit_code = 0
    _write_report(arguments.report, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "IMPACT_RULES",
    "OBSERVATION_VERSION",
    "P5ExitGateAuditError",
    "REPORT_VERSION",
    "TASK_ID",
    "TEST_IDS",
    "main",
    "run_p5_exit_gate_audit",
    "validate_p5_exit_gate_report",
    "validate_provider_observation",
]
