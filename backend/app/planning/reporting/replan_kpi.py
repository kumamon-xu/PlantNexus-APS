"""KPI v3 binds actual dynamic candidates without a static Solver alias."""

from __future__ import annotations

from typing import Any

from app.data_validation.canonical_ingress import canonical_fingerprint
from app.domain.execution_contracts import require_p4_document
from app.planning.problem.hashing import validate_built_problem_v2
from app.snapshots.canonical import snapshot_hash_for
from app.planning.reporting.kpi import calculate_schedule_kpi_metrics
from app.planning.validation.problem_schedule_validator import validate_problem_schedule


def build_replan_kpi(*, snapshot: Any, problem: Any, report: Any) -> dict[str, Any]:
    validate_built_problem_v2(problem)
    if snapshot_hash_for(snapshot) != snapshot.get("snapshot_hash"):
        raise ValueError("Replan KPI requires an intact snapshot")
    if require_p4_document(report) != "solver-report.v2":
        raise ValueError("Replan KPI requires a SolverReport v2")
    candidate = report["candidate"]
    if candidate is None or problem["snapshot_id"] != snapshot["snapshot_id"]:
        raise ValueError("Replan KPI requires an exact candidate and snapshot")
    problem_reference = {
        k: problem[k]
        for k in (
            "problem_version",
            "problem_builder_version",
            "problem_hash_projection_version",
            "problem_hash",
            "snapshot_id",
            "tick_seconds",
            "horizon_start_utc",
            "horizon_end_utc",
        )
    }
    if report["new_problem"]["fingerprint"] != problem["problem_hash"]:
        raise ValueError("Replan SolverReport belongs to a different Problem")
    validation = validate_problem_schedule(
        problem, {**candidate, "problem": problem_reference}
    )
    if validation["status"] != "PASS":
        raise ValueError("Replan candidate failed independent validation")
    metrics = calculate_schedule_kpi_metrics(problem, candidate["assignments"])
    basis = {
        "kpi_version": "kpi.v3",
        "schema_set_version": "2.11.0",
        "canonicalization_version": "canonical-json.v1",
        "planning_run_id": report["planning_run_id"],
        "inputs": {
            "snapshot": {
                k: snapshot[k]
                for k in ("snapshot_version", "snapshot_id", "snapshot_hash")
            },
            "problem": {k: problem[k] for k in ("problem_version", "problem_hash")},
            "candidate": {
                "document_version": "replan-candidate.v1",
                "artifact_id": "replan-candidate-"
                + candidate["candidate_fingerprint"][7:],
                "fingerprint": candidate["candidate_fingerprint"],
            },
            "solver_report": {
                "solver_report_version": "solver-report.v2",
                "report_id": report["report_id"],
                "solver_report_fingerprint": report["report_fingerprint"],
            },
            "validation_report": {
                "validation_report_version": "validation-report.v2",
                "validation_report_fingerprint": canonical_fingerprint(validation),
                "status": "PASS",
            },
        },
        "delivery": metrics.delivery_document,
        "planning": metrics.planning_document,
        "resources": metrics.resource_documents,
        "synthetic": True,
        "synthetic_provenance": snapshot["synthetic_provenance"],
    }
    return {"kpi_id": "kpi-" + canonical_fingerprint(basis)[7:], **basis}
