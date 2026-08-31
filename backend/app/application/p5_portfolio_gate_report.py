"""Build the TASK-P5-21 empty-selected portfolio integration Gate report."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Never, cast

from app.application.p4_gate_report import (
    run_p4_vertical_slice_gate,
    validate_p4_vertical_slice_report,
)
from app.domain.capabilities import (
    CapabilityContractError,
    CapabilityName,
    require_v1_capability_contract,
)
from app.domain.errors import ProductErrorCode
from app.simulation.benchmarks import run_benchmark, validate_benchmark_report


type JsonObject = dict[str, Any]

REPORT_VERSION = "p5-portfolio-gate-report.v1"
SELECTED_OWNER_MANIFEST_VERSION = "p5-selected-owner-evidence-manifest.v1"
TASK_ID = "TASK-P5-21"
DIFF_BASE = "d7779c014351d41909322b967c5c8eca68713e8b"
PORTFOLIO_MANIFEST_VERSION = "p5-portfolio-amendment-manifest.v1"
PORTFOLIO_MANIFEST_PATH = "docs/core/p5-portfolio-amendment-manifest.md"
IMPACT_RULES = (
    "IMPACT-APPLICATION",
    "IMPACT-TESTS",
    "IMPACT-INFRA",
    "IMPACT-DOCS",
)
P5_TEST_IDS = (
    "TEST-P5-PORTFOLIO-GATE-001",
    "TEST-VALIDATOR-MUTATION",
    "TEST-BENCHMARK",
    "TEST-REPLAN",
    "TEST-DISRUPTION-REPLAY-001",
    "TEST-P4-VERTICAL-SLICE-001",
)

_P5_02_PROVIDER: JsonObject = {
    "implementation": {
        "commit": "ed9ee75122341c1a71b641edc445e2a58cac70de",
        "run_id": 33389105900,
        "required_job_id": 99478441483,
        "required_check": "validate",
        "required_check_app_id": 15368,
        "artifacts": [
            {
                "artifact_id": 9756735835,
                "digest": "sha256:bbda3d87f66e92ca2be68a7bb47cae53a59f007ff6712a2878fed39883a15fcd",
            },
            {
                "artifact_id": 9756730213,
                "digest": "sha256:1a32c6a134181501271ced74d8e513a1d06322b02392e532d1d14d180062b303",
            },
        ],
    },
    "closure": {
        "commit": DIFF_BASE,
        "run_id": 33389544474,
        "required_job_id": 99479834853,
        "required_check": "validate",
        "required_check_app_id": 15368,
        "artifacts": [
            {
                "artifact_id": 9756904126,
                "digest": "sha256:92f14930150c63e588c292169cd0cb14a15309ab2cf68ffae09ba381713b491b",
            },
            {
                "artifact_id": 9756899489,
                "digest": "sha256:dba9eab9342ff27071ff56e5b523e0bcd999751b6e4d11b58a5b5fa8f31f04b5",
            },
        ],
    },
}

_DISPOSITIONS = (
    (
        "P5-CANDIDATE-SECONDARY-RESOURCE",
        "sha256:6161806c96612c32ed855df3a9d873b078d7b1a7582fdadd02e9fcc4e490c567",
        ("TASK-P5-03", "TASK-P5-04"),
    ),
    (
        "P5-CANDIDATE-SEQUENCE-SETUP",
        "sha256:c8eca75e419d0fcb5f3741935c1a4693f6add29fff1caae65ba5d303edf336b3",
        ("TASK-P5-05", "TASK-P5-06"),
    ),
    (
        "P5-CANDIDATE-MATERIAL-COMPETITION",
        "sha256:414be83f191008ef000aaa44403cd79539f617c840b0667d95855ae78ef7f137",
        ("TASK-P5-07", "TASK-P5-08"),
    ),
    (
        "P5-CANDIDATE-BATCH",
        "sha256:3c66f9cd6ba51e1f736a1ffc73d0639af87e9fc59323542f16c101da159cb34e",
        ("TASK-P5-09", "TASK-P5-10"),
    ),
    (
        "P5-CANDIDATE-SPLIT-MERGE",
        "sha256:3b98f5cd962c61a1f84e45baee0e6c929d940fa6c9809fec7e0e370d5828d2af",
        ("TASK-P5-11", "TASK-P5-12"),
    ),
    (
        "P5-CANDIDATE-BUFFER",
        "sha256:3530dc17db9223d1aad3f1a9fee3cd8462ff637a3e8dccc19fecc37162358de0",
        ("TASK-P5-13", "TASK-P5-14"),
    ),
    (
        "P5-CANDIDATE-PREEMPTION",
        "sha256:b88cc4b5d1a4534020f1b5d4a5d515f66dbde6d208a7fbdd11daa13aa25fa788",
        ("TASK-P5-15", "TASK-P5-16"),
    ),
    (
        "P5-CANDIDATE-DECOMPOSITION",
        "sha256:967cb6eadb37daf9fb08d0d60c7913e11cc2d59933b17b1430a82423fc69687b",
        ("TASK-P5-17", "TASK-P5-18"),
    ),
    (
        "P5-CANDIDATE-ROLLING-HORIZON",
        "sha256:1654b6015d14c8922a9a460a3ecb4953977173c1256954bc48743d4ea7a7aa2d",
        ("TASK-P5-19", "TASK-P5-20"),
    ),
)
_CANCELLED_TASKS = tuple(task for _, _, tasks in _DISPOSITIONS for task in tasks)
_UNSUPPORTED_CONSTRAINTS = (
    ("C-012", CapabilityName.SECONDARY_CAPACITY),
    ("C-013", CapabilityName.SEQUENCE_DEPENDENT_SETUP),
    ("C-014", CapabilityName.MATERIAL_COMPETITION),
    ("C-015", CapabilityName.BATCH_PROCESSING),
    ("C-016", CapabilityName.SPLIT_MERGE),
    ("C-017", CapabilityName.BUFFER_CAPACITY),
    ("C-018", CapabilityName.PREEMPTIVE_OPERATION),
)
_EXPECTED_CHECKS = (
    "p5-02-exact-provider-and-portfolio-source",
    "empty-selected-owner-evidence-manifest",
    "nine-deferred-dispositions-and-eighteen-cancelled-owners",
    "no-unselected-owner-invocation-or-capability-support-change",
    "c012-c018-exact-unsupported-negative-boundary",
    "global-only-strategy-and-no-advanced-fallback",
    "fresh-formal-validator-and-mutation-replay",
    "fresh-xs-s-m-development-benchmark-replay",
    "fresh-independent-p4-vertical-slice-regression",
    "p4-event-replan-freeze-stability-change-report-simulator-boundary",
    "empty-combination-is-vacuous-and-fail-closed",
    "p5-gate-non-exit-p6-production-and-no-auto-start-boundary",
)
_BOUNDARIES: JsonObject = {
    "current_phase": "P5",
    "data_plane": "SIMULATION_DEVELOPMENT_ONLY",
    "gate_kind": "P5_PORTFOLIO_INTEGRATION_GATE_NOT_EXIT_AUDIT",
    "selected_portfolio": "EMPTY_PROVIDER_VERIFIED",
    "p5_22_exit_gate_audit": "NOT_STARTED",
    "p6_plus": "NOT_ENTERED",
    "hybrid_planning": "EXCLUDED",
    "production_identity_and_approval_authority": "NOT_FORMED",
    "external_publish_integration_or_transfer": "NONE",
    "deployment": "NOT_PERFORMED",
    "capacity_and_sla": "NOT_ESTABLISHED",
    "uat": "NOT_PERFORMED",
    "schema_migration_dependency_adr_state_changes": "NONE",
    "remediation": "NONE_MIXED_INTO_GATE",
}


class P5PortfolioGateContractError(ValueError):
    """Raised when a P5 portfolio Gate input or output fails closed."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"P5_PORTFOLIO_GATE_CONTRACT at {field}: {message}")


class P5PortfolioGateExecutionError(RuntimeError):
    """Sanitized wrapper for a failed subordinate replay."""

    def __init__(self, stage: str, error: Exception) -> None:
        self.stage = stage
        self.error_type = type(error).__name__
        super().__init__(f"P5_PORTFOLIO_GATE_STAGE_FAILED at {stage}: {self.error_type}")


def _fail(field: str, message: str) -> Never:
    raise P5PortfolioGateContractError(field, message)


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, Mapping):
        _fail(field, "expected object")
    return dict(value)


def _items(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(field, "expected array")
    return value


def _code_commit() -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    if value == "uncommitted" or (
        len(value) == 40 and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return "uncommitted"


def _generated_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _sha256_json(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _run(stage: str, operation: Any) -> JsonObject:
    try:
        value = operation()
    except Exception as error:
        raise P5PortfolioGateExecutionError(stage, error) from error
    return _object(value, stage)


def _run_owner_machine_contract(
    *, root: Path, stage: str, module: str, report_name: str
) -> JsonObject:
    """Run a frozen owner machine contract without crossing application imports."""

    resolved_root = root.resolve()
    report_path = resolved_root / "build" / "validation" / report_name
    try:
        report_path.unlink(missing_ok=True)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                module,
                "--root",
                str(resolved_root),
                "--report",
                str(report_path),
            ],
            cwd=resolved_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"owner machine contract failed at {stage}") from error
    if completed.returncode != 0 or not report_path.is_file():
        raise RuntimeError(f"owner machine contract failed at {stage}")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"owner machine report invalid at {stage}") from error
    return _object(report, stage)


def load_portfolio_manifest(path: Path) -> tuple[JsonObject, str]:
    """Load the single fenced JSON projection from the public P5-02 document."""

    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise P5PortfolioGateContractError(
            "portfolio_manifest", "public manifest cannot be loaded as UTF-8"
        ) from error
    matches = re.findall(r"~~~json\s*\n(.*?)\n~~~", text, flags=re.DOTALL)
    if len(matches) != 1:
        _fail("portfolio_manifest", "expected exactly one fenced JSON payload")
    try:
        payload = json.loads(matches[0])
    except json.JSONDecodeError as error:
        raise P5PortfolioGateContractError(
            "portfolio_manifest", "fenced payload is not valid JSON"
        ) from error
    return _object(payload, "portfolio_manifest"), _sha256_bytes(raw)


def validate_portfolio_manifest(manifest: Mapping[str, object]) -> None:
    """Validate the exact provider-resolved empty P5 portfolio topology."""

    for field, expected in (
        ("manifest_version", PORTFOLIO_MANIFEST_VERSION),
        ("task_id", "TASK-P5-02"),
        ("status", "PASS"),
        ("validation_profile", "DOCS_ONLY"),
        ("diff_base", "01b8918db62cc9f5c4421d0b90d93151ddc552f1"),
        ("issues", []),
        ("blocking_issues", []),
    ):
        if manifest.get(field) != expected:
            _fail(f"portfolio_manifest.{field}", f"expected {expected!r}")

    implementation = _object(
        manifest.get("implementation_evidence"),
        "portfolio_manifest.implementation_evidence",
    )
    if (
        implementation.get("commit")
        != _P5_02_PROVIDER["implementation"]["commit"]
        or implementation.get("run_id")
        != _P5_02_PROVIDER["implementation"]["run_id"]
        or _object(implementation.get("jobs"), "implementation_evidence.jobs")
        .get("validate", {})
        .get("app_id")
        != 15368
    ):
        _fail("portfolio_manifest.implementation_evidence", "exact Provider changed")

    portfolio = _object(manifest.get("portfolio"), "portfolio_manifest.portfolio")
    if portfolio != {"selected": [], "selected_count": 0, "deferred_count": 9}:
        _fail("portfolio_manifest.portfolio", "must resolve to empty selected / nine deferred")

    rows = _items(manifest.get("dispositions"), "portfolio_manifest.dispositions")
    observed: list[tuple[str, str, tuple[str, ...]]] = []
    for index, raw in enumerate(rows):
        row = _object(raw, f"portfolio_manifest.dispositions[{index}]")
        if row.get("decision") != "DEFERRED" or row.get("terminal_status") != "cancelled":
            _fail(
                f"portfolio_manifest.dispositions[{index}]",
                "every disposition must remain DEFERRED/cancelled",
            )
        tasks = tuple(cast(list[str], _items(row.get("owner_tasks"), "owner_tasks")))
        observed.append(
            (
                cast(str, row.get("candidate_id")),
                cast(str, row.get("decision_fingerprint")),
                tasks,
            )
        )
    if tuple(observed) != _DISPOSITIONS:
        _fail("portfolio_manifest.dispositions", "decision identities or owner mapping changed")

    dag = _object(manifest.get("resolved_dag"), "portfolio_manifest.resolved_dag")
    expected_dag = {
        "selected_contract_tasks": [],
        "selected_implementation_tasks": [],
        "cancelled_tasks": list(_CANCELLED_TASKS),
        "p5_21_direct_dependencies": ["TASK-P5-02"],
        "p5_21_status": "planned",
        "p5_22_direct_dependencies": ["TASK-P5-21"],
        "p5_22_status": "planned",
        "next_task_authorized": False,
    }
    if dag != expected_dag:
        _fail("portfolio_manifest.resolved_dag", "resolved dependency topology changed")

    boundaries = _object(
        manifest.get("preserved_boundaries"),
        "portfolio_manifest.preserved_boundaries",
    )
    if (
        boundaries.get("capability_support_changes") != []
        or boundaries.get("unsupported_constraints")
        != [constraint for constraint, _ in _UNSUPPORTED_CONSTRAINTS]
        or boundaries.get("formed_strategy") != "GLOBAL_ONLY"
        or boundaries.get("p6_plus") != "NOT_ENTERED"
        or boundaries.get("production_readiness") != "NOT_FORMED"
    ):
        _fail("portfolio_manifest.preserved_boundaries", "phase boundary changed")


def _selected_owner_manifest(portfolio_fingerprint: str) -> JsonObject:
    return {
        "manifest_version": SELECTED_OWNER_MANIFEST_VERSION,
        "status": "PASS_EMPTY_SELECTED",
        "source_task_id": "TASK-P5-02",
        "source_portfolio_fingerprint": portfolio_fingerprint,
        "selected_candidates": [],
        "selected_contract_tasks": [],
        "selected_implementation_tasks": [],
        "owner_reports": [],
        "owner_report_count": 0,
        "cancelled_tasks": list(_CANCELLED_TASKS),
        "unselected_owner_invocations": [],
        "execution_policy": "DEFERRED_AND_CANCELLED_OWNERS_PROHIBITED",
    }


def _unsupported_rejections() -> list[JsonObject]:
    rows: list[JsonObject] = []
    for constraint_id, capability in _UNSUPPORTED_CONSTRAINTS:
        try:
            require_v1_capability_contract([capability])
        except CapabilityContractError as error:
            if (
                error.code is not ProductErrorCode.UNSUPPORTED_CAPABILITY
                or error.capability_names != (capability.value,)
            ):
                _fail(
                    f"unsupported_rejections.{constraint_id}",
                    "unexpected capability rejection identity",
                )
        else:
            _fail(
                f"unsupported_rejections.{constraint_id}",
                "unselected capability was accepted",
            )
        rows.append(
            {
                "constraint_id": constraint_id,
                "capability": capability.value,
                "status": "PASS",
                "error_code": ProductErrorCode.UNSUPPORTED_CAPABILITY.value,
            }
        )
    return rows


def _validate_strategy(report: Mapping[str, object], code_commit: str) -> None:
    boundaries = _object(report.get("boundaries"), "global_strategy.boundaries")
    if (
        report.get("report_version") != "objective-strategy-report.v1"
        or report.get("task_id") != "TASK-P2-08"
        or report.get("status") != "PASS"
        or report.get("code_commit") != code_commit
        or report.get("check_count") != 7
        or boundaries.get("strategy")
        != "ONE_GLOBAL_CP_SAT_MODEL_NO_DECOMPOSITION_OR_FALLBACK"
        or boundaries.get("formal_validator_changes") != "NONE"
    ):
        _fail("global_strategy", "Global-only strategy evidence changed")


def _validate_validator_reports(
    formal: Mapping[str, object], mutation: Mapping[str, object], code_commit: str
) -> None:
    if (
        formal.get("report_version") != "formal-schedule-validator-report.v1"
        or formal.get("task_id") != "TASK-P2-04"
        or formal.get("status") != "PASS"
        or formal.get("code_commit") != code_commit
        or formal.get("check_count") != 6
    ):
        _fail("formal_validator", "formal Validator evidence changed")
    mutation_counts = _object(mutation.get("counts"), "validator_mutation.counts")
    if (
        mutation.get("schema_version") != "validator-mutation-report.v1"
        or mutation.get("result") != "PASS"
        or mutation.get("issues") != []
        or mutation_counts.get("cases") != 13
        or mutation_counts.get("constraints_covered") != 11
        or "TEST-VALIDATOR-MUTATION" not in _items(
            mutation.get("test_ids"), "validator_mutation.test_ids"
        )
    ):
        _fail("validator_mutation", "mutation evidence changed")


def _run_benchmarks(root: Path, code_commit: str) -> list[JsonObject]:
    reports: list[JsonObject] = []
    for profile in ("xs", "s", "m"):
        report = _run(
            f"benchmark.{profile}",
            lambda profile=profile: run_benchmark(
                root=root, profile_name=profile, require_baseline=True
            ),
        )
        try:
            validate_benchmark_report(report)
        except Exception as error:
            raise P5PortfolioGateExecutionError(f"benchmark.{profile}", error) from error
        if (
            report.get("status") != "PASS"
            or report.get("code_commit") != code_commit
            or _object(report.get("global_solver"), f"benchmark.{profile}.global_solver")
            .get("validation", {})
            .get("status")
            != "PASS"
        ):
            _fail(f"benchmark.{profile}", "fresh Global/Validator benchmark changed")
        reports.append(report)
    if [cast(JsonObject, report["profile"])["size"] for report in reports] != [
        "XS",
        "S",
        "M",
    ]:
        _fail("benchmarks", "profile order changed")
    return reports


def _pass(check_id: str, evidence: object) -> JsonObject:
    return {"check_id": check_id, "status": "PASS", "evidence": evidence}


def run_p5_portfolio_gate(
    *,
    root: Path,
    portfolio_manifest: Mapping[str, object],
    portfolio_document_sha256: str,
    frontend_report: Mapping[str, object],
    p2_report: Mapping[str, object],
    p3_report: Mapping[str, object],
    repeat: int = 2,
) -> JsonObject:
    """Fresh-run the empty-selected P5 portfolio Gate and all frozen regressions."""

    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 2:
        _fail("repeat", "P5 portfolio Gate requires at least two complete P4 replays")
    if not _is_sha256(portfolio_document_sha256):
        _fail("portfolio_document_sha256", "expected sha256 identity")
    validate_portfolio_manifest(portfolio_manifest)
    code_commit = _code_commit()
    portfolio_fingerprint = _sha256_json(portfolio_manifest)
    selected_manifest = _selected_owner_manifest(portfolio_fingerprint)
    rejections = _unsupported_rejections()

    strategy = _run(
        "global_strategy",
        lambda: _run_owner_machine_contract(
            root=root,
            stage="global_strategy",
            module="app.planning.backends.cp_sat.objective_strategy_check",
            report_name="p5-global-strategy.json",
        ),
    )
    _validate_strategy(strategy, code_commit)
    formal = _run(
        "formal_validator",
        lambda: _run_owner_machine_contract(
            root=root,
            stage="formal_validator",
            module="app.planning.validation.problem_validator_check",
            report_name="p5-formal-validator.json",
        ),
    )
    mutation = _run(
        "validator_mutation",
        lambda: _run_owner_machine_contract(
            root=root,
            stage="validator_mutation",
            module="app.planning.validation.mutation_check",
            report_name="p5-validator-mutation.json",
        ),
    )
    _validate_validator_reports(formal, mutation, code_commit)
    benchmarks = _run_benchmarks(root, code_commit)
    p4_regression = _run(
        "p4_regression",
        lambda: run_p4_vertical_slice_gate(
            root=root,
            frontend_report=frontend_report,
            p2_report=p2_report,
            p3_report=p3_report,
            repeat=repeat,
        ),
    )
    try:
        validate_p4_vertical_slice_report(p4_regression)
    except Exception as error:
        raise P5PortfolioGateExecutionError("p4_regression", error) from error

    p4_counts = _object(p4_regression.get("counts"), "p4_regression.counts")
    combination = {
        "status": "PASS",
        "selected_count": 0,
        "dependency_order": [],
        "combination_edges": [],
        "owner_invocations": [],
        "composition_result": "VACUOUS_EMPTY_PORTFOLIO_IDENTITY",
        "global_strategy_remains": "GLOBAL_CP_SAT",
        "advanced_strategy_fallback": "NOT_APPLICABLE_EMPTY_SELECTED",
    }
    checks = [
        _pass(
            _EXPECTED_CHECKS[0],
            {
                "provider": _P5_02_PROVIDER,
                "manifest_path": PORTFOLIO_MANIFEST_PATH,
                "document_sha256": portfolio_document_sha256,
                "payload_fingerprint": portfolio_fingerprint,
            },
        ),
        _pass(_EXPECTED_CHECKS[1], selected_manifest),
        _pass(
            _EXPECTED_CHECKS[2],
            {"disposition_count": 9, "cancelled_tasks": list(_CANCELLED_TASKS)},
        ),
        _pass(
            _EXPECTED_CHECKS[3],
            {
                "selected": [],
                "owner_invocations": [],
                "capability_support_changes": [],
            },
        ),
        _pass(
            _EXPECTED_CHECKS[4],
            {"rejection_count": len(rejections), "cases": rejections},
        ),
        _pass(
            _EXPECTED_CHECKS[5],
            {
                "strategy_report": "objective-strategy-report.v1",
                "strategy": _object(strategy["boundaries"], "strategy.boundaries")[
                    "strategy"
                ],
                "decomposition": "ABSENT",
                "rolling_horizon": "ABSENT",
            },
        ),
        _pass(
            _EXPECTED_CHECKS[6],
            {
                "formal_checks": formal["check_count"],
                "mutation_cases": _object(mutation["counts"], "mutation.counts")[
                    "cases"
                ],
            },
        ),
        _pass(
            _EXPECTED_CHECKS[7],
            {
                "profiles": [report["profile"]["size"] for report in benchmarks],
                "statuses": [report["status"] for report in benchmarks],
                "production_sla": "NOT_ESTABLISHED_OPEN_012",
            },
        ),
        _pass(
            _EXPECTED_CHECKS[8],
            {
                "report_version": p4_regression["report_version"],
                "repeat_count": p4_regression["repeat_count"],
                "raw_report_sha256": _sha256_json(p4_regression),
            },
        ),
        _pass(
            _EXPECTED_CHECKS[9],
            {
                "continuous_scenario_steps": p4_counts["continuous_scenario_step_executions"],
                "standard_events": p4_counts["standard_event_executions"],
                "fresh_validator_passes": p4_counts["fresh_validator_passes"],
                "complete_change_reports": p4_counts["complete_change_reports"],
                "execution_simulator": "FRESH_REPLAY_PASS",
                "freeze_and_obj_002": "FRESH_REPLAY_PASS",
            },
        ),
        _pass(_EXPECTED_CHECKS[10], combination),
        _pass(_EXPECTED_CHECKS[11], dict(_BOUNDARIES)),
    ]
    if tuple(check["check_id"] for check in checks) != _EXPECTED_CHECKS:
        _fail("checks", "aggregate check order changed")

    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "generated_at_utc": _generated_at(),
        "validation_profile": "PHASE_GATE",
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "test_ids": list(P5_TEST_IDS),
        "versions": {
            "gate_contract": REPORT_VERSION,
            "selected_owner_manifest": SELECTED_OWNER_MANIFEST_VERSION,
            "portfolio_manifest": PORTFOLIO_MANIFEST_VERSION,
            "p4_gate": "p4-vertical-slice-report.v1",
            "formal_validator": "formal-schedule-validator-report.v1",
            "validator_mutation": "validator-mutation-report.v1",
            "benchmark": "benchmark-report.v1",
        },
        "frozen_inputs": {
            "diff_base": DIFF_BASE,
            "direct_dependencies": ["TASK-P5-02"],
            "p5_02_provider": _P5_02_PROVIDER,
            "portfolio_manifest_path": PORTFOLIO_MANIFEST_PATH,
            "portfolio_document_sha256": portfolio_document_sha256,
            "portfolio_payload_fingerprint": portfolio_fingerprint,
        },
        "portfolio": {
            "selected": [],
            "selected_count": 0,
            "deferred_count": 9,
            "cancelled_task_count": len(_CANCELLED_TASKS),
        },
        "selected_owner_evidence_manifest": selected_manifest,
        "combination": combination,
        "unsupported_rejections": rejections,
        "global_strategy_evidence": strategy,
        "formal_validator_evidence": formal,
        "validator_mutation_evidence": mutation,
        "benchmark_evidence": benchmarks,
        "p4_regression_evidence": p4_regression,
        "checks": checks,
        "check_count": len(checks),
        "issues": [],
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
    }


def validate_p5_portfolio_gate_report(report: Mapping[str, object]) -> None:
    """Validate one successful ``p5-portfolio-gate-report.v1`` report."""

    expected_keys = {
        "report_version",
        "status",
        "task_id",
        "code_commit",
        "diff_base",
        "generated_at_utc",
        "validation_profile",
        "impact_rule_count",
        "impact_rules",
        "test_ids",
        "versions",
        "frozen_inputs",
        "portfolio",
        "selected_owner_evidence_manifest",
        "combination",
        "unsupported_rejections",
        "global_strategy_evidence",
        "formal_validator_evidence",
        "validator_mutation_evidence",
        "benchmark_evidence",
        "p4_regression_evidence",
        "checks",
        "check_count",
        "issues",
        "blocking_gaps",
        "boundaries",
    }
    if set(report) != expected_keys:
        _fail(
            "$",
            f"keys changed; missing={sorted(expected_keys - set(report))} "
            f"extra={sorted(set(report) - expected_keys)}",
        )
    for field, expected in (
        ("report_version", REPORT_VERSION),
        ("status", "PASS"),
        ("task_id", TASK_ID),
        ("diff_base", DIFF_BASE),
        ("validation_profile", "PHASE_GATE"),
        ("impact_rule_count", len(IMPACT_RULES)),
        ("impact_rules", list(IMPACT_RULES)),
        ("test_ids", list(P5_TEST_IDS)),
        ("issues", []),
        ("blocking_gaps", []),
        ("boundaries", _BOUNDARIES),
    ):
        if report.get(field) != expected:
            _fail(field, f"expected {expected!r}")
    code_commit = report.get("code_commit")
    if code_commit != "uncommitted" and not (
        isinstance(code_commit, str)
        and len(code_commit) == 40
        and all(character in "0123456789abcdef" for character in code_commit)
    ):
        _fail("code_commit", "expected uncommitted or full lowercase Git SHA")

    frozen = _object(report.get("frozen_inputs"), "frozen_inputs")
    if (
        frozen.get("diff_base") != DIFF_BASE
        or frozen.get("direct_dependencies") != ["TASK-P5-02"]
        or frozen.get("p5_02_provider") != _P5_02_PROVIDER
        or frozen.get("portfolio_manifest_path") != PORTFOLIO_MANIFEST_PATH
        or not _is_sha256(frozen.get("portfolio_document_sha256"))
        or not _is_sha256(frozen.get("portfolio_payload_fingerprint"))
    ):
        _fail("frozen_inputs", "provider or portfolio identity changed")

    portfolio = _object(report.get("portfolio"), "portfolio")
    if portfolio != {
        "selected": [],
        "selected_count": 0,
        "deferred_count": 9,
        "cancelled_task_count": 18,
    }:
        _fail("portfolio", "resolved topology changed")
    selected = _object(
        report.get("selected_owner_evidence_manifest"),
        "selected_owner_evidence_manifest",
    )
    expected_selected = _selected_owner_manifest(
        cast(str, frozen["portfolio_payload_fingerprint"])
    )
    if selected != expected_selected:
        _fail("selected_owner_evidence_manifest", "empty owner manifest changed")

    rejection_rows = [
        _object(raw, f"unsupported_rejections[{index}]")
        for index, raw in enumerate(
            _items(report.get("unsupported_rejections"), "unsupported_rejections")
        )
    ]
    expected_rejections = [
        {
            "constraint_id": constraint_id,
            "capability": capability.value,
            "status": "PASS",
            "error_code": ProductErrorCode.UNSUPPORTED_CAPABILITY.value,
        }
        for constraint_id, capability in _UNSUPPORTED_CONSTRAINTS
    ]
    if rejection_rows != expected_rejections:
        _fail("unsupported_rejections", "C-012..C-018 rejection set changed")

    combination = _object(report.get("combination"), "combination")
    if combination != {
        "status": "PASS",
        "selected_count": 0,
        "dependency_order": [],
        "combination_edges": [],
        "owner_invocations": [],
        "composition_result": "VACUOUS_EMPTY_PORTFOLIO_IDENTITY",
        "global_strategy_remains": "GLOBAL_CP_SAT",
        "advanced_strategy_fallback": "NOT_APPLICABLE_EMPTY_SELECTED",
    }:
        _fail("combination", "empty-selected composition boundary changed")

    if report.get("versions") != {
        "gate_contract": REPORT_VERSION,
        "selected_owner_manifest": SELECTED_OWNER_MANIFEST_VERSION,
        "portfolio_manifest": PORTFOLIO_MANIFEST_VERSION,
        "p4_gate": "p4-vertical-slice-report.v1",
        "formal_validator": "formal-schedule-validator-report.v1",
        "validator_mutation": "validator-mutation-report.v1",
        "benchmark": "benchmark-report.v1",
    }:
        _fail("versions", "embedded contract versions changed")

    _validate_strategy(
        _object(report.get("global_strategy_evidence"), "global_strategy_evidence"),
        cast(str, code_commit),
    )
    _validate_validator_reports(
        _object(report.get("formal_validator_evidence"), "formal_validator_evidence"),
        _object(report.get("validator_mutation_evidence"), "validator_mutation_evidence"),
        cast(str, code_commit),
    )
    benchmarks = _items(report.get("benchmark_evidence"), "benchmark_evidence")
    if [cast(JsonObject, row["profile"])["size"] for row in benchmarks] != [
        "XS",
        "S",
        "M",
    ]:
        _fail("benchmark_evidence", "expected exact XS/S/M order")
    for index, raw in enumerate(benchmarks):
        benchmark = _object(raw, f"benchmark_evidence[{index}]")
        try:
            validate_benchmark_report(benchmark)
        except Exception as error:
            raise P5PortfolioGateContractError(
                f"benchmark_evidence[{index}]", "benchmark contract changed"
            ) from error
        if benchmark.get("code_commit") != code_commit:
            _fail(f"benchmark_evidence[{index}].code_commit", "exact SHA changed")

    p4 = _object(report.get("p4_regression_evidence"), "p4_regression_evidence")
    try:
        validate_p4_vertical_slice_report(p4)
    except Exception as error:
        raise P5PortfolioGateContractError(
            "p4_regression_evidence", "P4 regression contract changed"
        ) from error
    if p4.get("code_commit") != code_commit:
        _fail("p4_regression_evidence.code_commit", "exact SHA changed")

    checks = _items(report.get("checks"), "checks")
    identities = [
        _object(raw, f"checks[{index}]").get("check_id")
        for index, raw in enumerate(checks)
    ]
    if (
        tuple(identities) != _EXPECTED_CHECKS
        or report.get("check_count") != len(_EXPECTED_CHECKS)
        or any(_object(raw, "check").get("status") != "PASS" for raw in checks)
    ):
        _fail("checks", "aggregate check identity/count/status changed")
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in (
        '"p5_22_exit_gate_audit": "READY"',
        '"p6_plus": "ENTERED"',
        '"production_identity_and_approval_authority": "FORMED"',
        '"capacity_and_sla": "ESTABLISHED"',
        '"deployment": "PERFORMED"',
    ):
        if forbidden in serialized:
            _fail("boundaries", f"forbidden claim present: {forbidden}")


def _failure_report(error: Exception, repeat: int) -> JsonObject:
    stage = (
        error.stage
        if isinstance(error, P5PortfolioGateExecutionError)
        else "gate-orchestrator"
    )
    return {
        "report_version": REPORT_VERSION,
        "status": "FAIL",
        "task_id": TASK_ID,
        "code_commit": _code_commit(),
        "diff_base": DIFF_BASE,
        "validation_profile": "PHASE_GATE",
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "repeat_count": repeat,
        "issues": [
            {
                "issue_id": "P5-PORTFOLIO-GATE-EXECUTION-001",
                "stage": stage,
                "error_type": type(error).__name__,
            }
        ],
        "blocking_gaps": [
            {
                "gap_id": "P5-PORTFOLIO-GATE-EXECUTION-001",
                "stage": stage,
                "status": "BLOCKING",
                "remediation": "REQUIRES_SEPARATE_BOUNDED_CORRECTIVE_COMMIT",
            }
        ],
        "boundaries": dict(_BOUNDARIES),
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path, field: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise P5PortfolioGateContractError(field, "report cannot be loaded") from error
    return _object(value, field)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument(
        "--portfolio-manifest",
        type=Path,
        default=Path(PORTFOLIO_MANIFEST_PATH),
    )
    parser.add_argument("--frontend-report", type=Path, required=True)
    parser.add_argument("--p2-report", type=Path, required=True)
    parser.add_argument("--p3-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        portfolio, document_sha256 = load_portfolio_manifest(
            arguments.portfolio_manifest
        )
        report = run_p5_portfolio_gate(
            root=arguments.root.resolve(),
            portfolio_manifest=portfolio,
            portfolio_document_sha256=document_sha256,
            frontend_report=_load_json(arguments.frontend_report, "frontend_report"),
            p2_report=_load_json(arguments.p2_report, "p2_report"),
            p3_report=_load_json(arguments.p3_report, "p3_report"),
            repeat=arguments.repeat,
        )
        validate_p5_portfolio_gate_report(report)
    except Exception as error:
        report = _failure_report(error, arguments.repeat)
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
    "P5PortfolioGateContractError",
    "P5PortfolioGateExecutionError",
    "P5_TEST_IDS",
    "PORTFOLIO_MANIFEST_PATH",
    "PORTFOLIO_MANIFEST_VERSION",
    "REPORT_VERSION",
    "SELECTED_OWNER_MANIFEST_VERSION",
    "TASK_ID",
    "load_portfolio_manifest",
    "main",
    "run_p5_portfolio_gate",
    "validate_p5_portfolio_gate_report",
    "validate_portfolio_manifest",
]
