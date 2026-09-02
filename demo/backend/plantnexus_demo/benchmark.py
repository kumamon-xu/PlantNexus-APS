"""Bounded, synthetic-only benchmark harness for the CNC demo profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import tracemalloc
from typing import Any

import ortools

from app.planning.contracts import contract_fingerprint
from app.planning.policy.delivery import (
    simulation_delivery_policy,
    simulation_solve_limits,
)
from app.planning.strategies.global_cp_sat import GlobalCpSatStrategy

from .generator import DemoPackageGenerator, source_record_counts
from .ingress import DemoIngressPipeline, problem_counts


BENCHMARK_REPORT_VERSION = "cnc-demo-benchmark-report.v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _git_state() -> dict[str, Any]:
    working_directory = str(Path(__file__).resolve().parents[3])
    try:
        repository = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            cwd=working_directory,
        ).stdout.strip()
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=repository,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--", "demo"],
                check=True,
                capture_output=True,
                text=True,
                cwd=repository,
            ).stdout.strip()
        )
        return {"head": head, "demo_worktree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"head": "unavailable", "demo_worktree_dirty": None}


def _environment() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "ortools_version": ortools.__version__,
        "logical_cpu_count": os.cpu_count(),
        "git": _git_state(),
    }


def _fingerprint(report: dict[str, Any]) -> str:
    payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def run_benchmark(
    profile_name: str,
    *,
    solve_seconds: float | None = None,
    run_solver: bool = True,
) -> dict[str, Any]:
    """Run one measured import/Snapshot/Problem/Solver path with explicit bounds."""

    generated_at = _utc_now()
    generator = DemoPackageGenerator()
    pipeline = DemoIngressPipeline()
    tracemalloc.start()
    overall_started = perf_counter()

    generation_started = perf_counter()
    generated = generator.prepare_batch(profile_name)
    generation_seconds = perf_counter() - generation_started

    ingress_started = perf_counter()
    artifacts = pipeline.run(generated)
    ingress_seconds = perf_counter() - ingress_started
    counts = problem_counts(artifacts)

    solver_section: dict[str, Any]
    if run_solver:
        bounded_seconds = (
            float(generated.profile.initial_solve_seconds)
            if solve_seconds is None
            else float(solve_seconds)
        )
        limits = simulation_solve_limits(
            limits_id=f"CNC-DEMO-LIMITS-{profile_name.upper()}",
            limits_revision="1.0.0",
            source_record_id=f"cnc-demo-limits-{profile_name}",
            max_wall_time_seconds=bounded_seconds,
            max_workers=1,
            random_seed=generated.profile.seed,
        )
        solve_started = perf_counter()
        result = GlobalCpSatStrategy().solve(
            artifacts.problem.document,
            simulation_delivery_policy(),
            limits,
            planning_run_id=f"cnc-demo-benchmark-{profile_name}",
            code_commit="uncommitted",
        )
        solve_wall_seconds = perf_counter() - solve_started
        solver_status = str(result.solution["solver_status"])
        validation_status = (
            None if result.validation_report is None else result.validation_report["status"]
        )
        if solver_status == "OPTIMAL":
            classification = "OPTIMAL_FOR_THIS_SYNTHETIC_INSTANCE"
        elif solver_status == "FEASIBLE" and validation_status == "PASS":
            classification = "VALIDATOR_VERIFIED_FEASIBLE"
        else:
            classification = "NO_VALIDATED_CANDIDATE"
        solver_section = {
            "executed": True,
            "limits": {
                "max_wall_time_seconds": bounded_seconds,
                "max_workers": limits["max_workers"],
                "random_seed": limits["random_seed"],
            },
            "solver_status": solver_status,
            "result_classification": classification,
            "assignment_count": len(result.solution["assignments"]),
            "solution_fingerprint": contract_fingerprint(result.solution),
            "objective_stage_results": result.solution["objective_stage_results"],
            "validator": {
                "status": validation_status,
                "hard_violation_count": (
                    None
                    if result.validation_report is None
                    else result.validation_report["hard_violation_count"]
                ),
                "independent_formal_validator": True,
            },
            "timings": {
                **result.solver_report["timings"],
                "harness_solve_wall_seconds": solve_wall_seconds,
            },
            "model_metrics": result.solver_report["model_metrics"],
            "memory_peak_mb": result.solver_report["memory_peak_mb"],
        }
    else:
        solver_section = {
            "executed": False,
            "limits": None,
            "solver_status": "NOT_RUN",
            "result_classification": "PIPELINE_ONLY",
            "validator": None,
        }

    _, python_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_seconds = perf_counter() - overall_started
    profile = generated.profile
    report: dict[str, Any] = {
        "benchmark_report_version": BENCHMARK_REPORT_VERSION,
        "generated_at_utc": generated_at,
        "status": (
            "PASS"
            if artifacts.quality.passed
            and (
                not run_solver
                or solver_section["validator"] is not None
                and solver_section["validator"]["status"] == "PASS"
            )
            else "FAIL"
        ),
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "synthetic_only": True,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
            "result_scope": "THIS_PROFILE_AND_CAPTURED_ENVIRONMENT_ONLY",
        },
        "profile": {
            "name": profile.name,
            "profile_id": profile.profile_id,
            "seed": profile.seed,
            "order_count": profile.order_count,
            "operation_count": profile.operation_count,
            "active_operation_count": profile.active_operation_count,
            "resource_count": profile.resource_count,
            "horizon_days": profile.horizon_days,
        },
        "assets_digest": generated.assets_digest,
        "source_batch": {
            "batch_id": generated.batch.batch_id,
            "request_fingerprint": generated.batch.request_fingerprint,
            "row_count": len(generated.batch.rows),
            "record_counts": source_record_counts(generated),
        },
        "standard_ingress": {
            "stages": [
                "RAW_STAGING",
                "NORMALIZATION",
                "DATA_VALIDATION",
                "ORDER_EXPANSION",
                "IMMUTABLE_SNAPSHOT",
                "PLANNING_PROBLEM_V2",
            ],
            "quality_status": artifacts.quality.document["status"],
            "dataset_hash": artifacts.normalization.dataset_hash,
            "snapshot_id": artifacts.snapshot.snapshot_id,
            "problem_hash": artifacts.problem.problem_hash,
            "problem_counts": counts,
        },
        "timings": {
            "generation_seconds": generation_seconds,
            "ingress_seconds": ingress_seconds,
            "total_harness_seconds": total_seconds,
        },
        "python_tracemalloc_peak_mb": python_peak_bytes / (1024 * 1024),
        "solver": solver_section,
        "environment": _environment(),
        "warnings": [
            "Synthetic benchmark evidence is not production capacity or SLA evidence.",
            "OPTIMAL applies only to this synthetic instance and captured configuration.",
            "Python tracemalloc excludes native allocations and is reported separately from solver telemetry.",
        ],
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


__all__ = ["BENCHMARK_REPORT_VERSION", "run_benchmark"]
