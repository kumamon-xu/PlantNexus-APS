"""Run the Demo-local quality gate and emit one machine-readable report."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    started = perf_counter()
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
    )
    output = (completed.stdout + completed.stderr).strip()
    return {
        "command": command,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "exit_code": completed.returncode,
        "duration_seconds": perf_counter() - started,
        "output": output[-8_000:],
    }


def _outside_demo_paths() -> set[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    result: set[str] = set()
    for line in completed.stdout.splitlines():
        path = line[3:].strip().replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path != "demo" and not path.startswith("demo/"):
            result.add(path)
    return result


def _verify_benchmark(path: Path, expected: tuple[int, int, int]) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    observed_fingerprint = report.pop("report_fingerprint", None)
    payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    expected_fingerprint = f"sha256:{sha256(payload).hexdigest()}"
    profile_tuple = (
        report["profile"]["operation_count"],
        report["profile"]["active_operation_count"],
        report["profile"]["resource_count"],
    )
    passed = (
        report["status"] == "PASS"
        and observed_fingerprint == expected_fingerprint
        and profile_tuple == expected
        and report["solver"]["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and report["solver"]["validator"]["status"] == "PASS"
        and report["boundaries"]["synthetic_only"] is True
        and report["boundaries"]["production_capacity_claim"] == "NOT_ESTABLISHED"
    )
    return {
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "status": "PASS" if passed else "FAIL",
        "sha256": _sha256(path),
        "profile_counts": profile_tuple,
        "solver_status": report["solver"]["solver_status"],
        "validator_status": report["solver"]["validator"]["status"],
        "solve_seconds": report["solver"]["timings"]["solve_seconds"],
        "total_solver_seconds": report["solver"]["timings"]["total_seconds"],
        "result_classification": report["solver"]["result_classification"],
    }


def _text_hygiene() -> dict[str, Any]:
    suffixes = {".py", ".md", ".json"}
    violations: list[str] = []
    for path in sorted(DEMO_ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            violations.append(f"{path.relative_to(REPOSITORY_ROOT).as_posix()}: invalid UTF-8")
            continue
        if text and not text.endswith("\n"):
            violations.append(f"{path.relative_to(REPOSITORY_ROOT).as_posix()}: missing final newline")
        for index, line in enumerate(text.splitlines(), start=1):
            markdown_hard_break = path.suffix == ".md" and line.endswith("  ") and not line.endswith("   ")
            if line.endswith("\t") or (line.endswith(" ") and not markdown_hard_break):
                violations.append(
                    f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{index}: trailing whitespace"
                )
    return {"status": "PASS" if not violations else "FAIL", "violations": violations}


def _verify_runtime_evidence(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    observed_fingerprint = report.pop("report_fingerprint", None)
    payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    expected_fingerprint = f"sha256:{sha256(payload).hexdigest()}"
    passed = (
        report["status"] == "PASS"
        and report["task_id"] == "TASK-DEMO-02"
        and report["profile"] == "showcase"
        and report["story_state"] == "BASELINE_PUBLISHED"
        and report["initial_plan"]["validation_status"] == "PASS"
        and report["initial_plan"]["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and report["activation"]["state"] == "PUBLISHED"
        and report["activation"]["exact_replay"] is True
        and len(report["artifacts"]) == 7
        and observed_fingerprint == expected_fingerprint
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(path),
        "solver_status": report["initial_plan"]["solver_status"],
        "validation_status": report["initial_plan"]["validation_status"],
        "story_state": report["story_state"],
    }


def _verify_replan_runtime_evidence(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    observed_fingerprint = report.pop("report_fingerprint", None)
    payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    expected_fingerprint = f"sha256:{sha256(payload).hexdigest()}"
    result = report["urgent_job"]["result"]
    rows = report["row_counts"]
    passed = (
        report["status"] == "PASS"
        and report["task_id"] == "TASK-DEMO-03"
        and report["profile"] == "showcase"
        and report["story_state"] == "DRAFT_COMPARISON_READY"
        and result["schedule_state"] == "DRAFT"
        and result["validation_status"] == "PASS"
        and result["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and report["formal_replay"]["exact_replay"] is True
        and report["current_publication"]["unchanged"] is True
        and report["event"]["formal_payload_exact"] is True
        and report["event"]["route_template_in_formal_event"] is False
        and report["projection"]["completed_prebaseline_preserved"] is True
        and report["change_report"]["classifications"]["ADDED"] == 5
        and rows["execution_event_ledger"] == 1
        and rows["replan_projection_checkpoints"] == 1
        and rows["replan_requests"] == 1
        and rows["replan_attempts"] == 1
        and rows["replan_results"] == 1
        and rows["schedule_versions"] == 2
        and report["boundaries"]["single_showcase_run_not_p95"] is True
        and observed_fingerprint == expected_fingerprint
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(path),
        "solver_status": result["solver_status"],
        "validation_status": result["validation_status"],
        "story_state": report["story_state"],
        "operation_changes": result["operation_changes"],
        "urgent_replan_seconds": report["timings"]["urgent_replan_seconds"],
    }


def build_report(*, task_id: str, context_path: Path) -> dict[str, Any]:
    baseline_path = DEMO_ROOT / "build/validation/protected-root-baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    expected_outside = set(baseline["files"])
    observed_outside = _outside_demo_paths()
    protected_files: list[dict[str, Any]] = []
    for relative_path, expected_digest in baseline["files"].items():
        path = REPOSITORY_ROOT / relative_path
        observed_digest = _sha256(path)
        protected_files.append(
            {
                "path": relative_path,
                "status": "PASS" if observed_digest == expected_digest else "FAIL",
                "expected_sha256": expected_digest,
                "observed_sha256": observed_digest,
            }
        )
    scope_status = (
        "PASS"
        if observed_outside == expected_outside
        and all(item["status"] == "PASS" for item in protected_files)
        else "FAIL"
    )

    benchmark_checks = [
        _verify_benchmark(DEMO_ROOT / "benchmarks/results/smoke.json", (108, 102, 12)),
        _verify_benchmark(DEMO_ROOT / "benchmarks/results/showcase.json", (610, 580, 24)),
        _verify_benchmark(DEMO_ROOT / "benchmarks/results/upper.json", (700, 665, 30)),
    ]
    contract_report_path = DEMO_ROOT / "build/validation/contract-probes.json"
    contract_report = json.loads(contract_report_path.read_text(encoding="utf-8"))
    context_report = json.loads(context_path.read_text(encoding="utf-8"))

    command_checks = [
        _run(["uv", "run", "pytest", "demo/tests", "-q"]),
        _run(["uv", "run", "ruff", "check", "demo/backend", "demo/scripts", "demo/tests"]),
        _run(["uv", "run", "pyright", "-p", "demo/pyrightconfig.json"]),
        _run(["git", "diff", "--check", "--", "demo"]),
    ]
    hygiene = _text_hygiene()
    artifact_checks: dict[str, dict[str, Any]] = {
        "contract_probes": {
            "status": contract_report["status"],
            "probe_count": contract_report["probe_count"],
            "sha256": _sha256(contract_report_path),
        },
        "task_context_manifest": {
            "status": (
                "PASS"
                if context_report["task_id"] == task_id
                and context_report["task_family"] == "demo-exclusive"
                and context_report["phase_registration"] is None
                else "FAIL"
            ),
            "selected_input_count": context_report["selected_input_count"],
            "sha256": _sha256(context_path),
        },
        "text_hygiene": hygiene,
    }
    if task_id == "TASK-DEMO-02":
        artifact_checks["runtime_evidence"] = _verify_runtime_evidence(
            DEMO_ROOT / "build/validation/runtime-evidence-demo-02.json"
        )
    elif task_id == "TASK-DEMO-03":
        artifact_checks["runtime_evidence"] = _verify_replan_runtime_evidence(
            DEMO_ROOT / "build/validation/runtime-evidence-demo-03.json"
        )
    passed = (
        scope_status == "PASS"
        and all(item["status"] == "PASS" for item in benchmark_checks)
        and all(item["status"] == "PASS" for item in command_checks)
        and all(item["status"] == "PASS" for item in artifact_checks.values())
    )

    demo_files = [
        {
            "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(DEMO_ROOT.rglob("*"))
        if path.is_file()
        and not path.name.startswith("task-machine-report")
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    ]
    return {
        "machine_report_version": "cnc-demo-task-machine-report.v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "task_id": task_id,
        "task_family": "demo-exclusive",
        "status": "PASS" if passed else "FAIL",
        "scope_check": {
            "status": scope_status,
            "allowed": ["demo/**"],
            "outside_demo_paths_expected": sorted(expected_outside),
            "outside_demo_paths_observed": sorted(observed_outside),
            "protected_files": protected_files,
        },
        "benchmark_checks": benchmark_checks,
        "artifact_checks": artifact_checks,
        "command_checks": command_checks,
        "demo_file_count": len(demo_files),
        "demo_files": demo_files,
        "boundaries": {
            "synthetic_only": True,
            "production_capacity": "NOT_ESTABLISHED",
            "provider_evidence": "NOT_APPLICABLE_DEMO_LOCAL",
            "p7_registration": "NONE",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--task-id",
        choices=("TASK-DEMO-01", "TASK-DEMO-02", "TASK-DEMO-03"),
        default="TASK-DEMO-01",
    )
    parser.add_argument("--context", type=Path)
    arguments = parser.parse_args()
    context_path = (
        arguments.context
        if arguments.context is not None
        else DEMO_ROOT
        / "build"
        / "validation"
        / {
            "TASK-DEMO-01": "task-context-manifest.json",
            "TASK-DEMO-02": "task-context-manifest-demo-02.json",
            "TASK-DEMO-03": "task-context-manifest-demo-03.json",
        }[arguments.task_id]
    )
    report = build_report(task_id=arguments.task_id, context_path=context_path)
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(arguments.report.resolve()),
                "benchmark_checks": len(report["benchmark_checks"]),
                "command_checks": len(report["command_checks"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
