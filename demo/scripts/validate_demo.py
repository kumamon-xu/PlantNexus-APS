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
NPM_COMMAND = "npm.cmd" if os.name == "nt" else "npm"
IGNORED_DIRECTORY_NAMES = {
    ".playwright-cli",
    ".pyright",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
    "playwright-report",
    "runtime",
    "test-results",
}


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _run(command: list[str], *, cwd: Path = REPOSITORY_ROOT) -> dict[str, Any]:
    started = perf_counter()
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=cwd,
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
        "cwd": cwd.relative_to(REPOSITORY_ROOT).as_posix() or ".",
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "exit_code": completed.returncode,
        "duration_seconds": perf_counter() - started,
        "output": output[-8_000:],
    }


def _is_ignored_artifact(path: Path) -> bool:
    relative = path.relative_to(DEMO_ROOT)
    if any(part in IGNORED_DIRECTORY_NAMES for part in relative.parts):
        return True
    return relative.parts[:2] in {("benchmarks", "tmp"), ("data", "generated")}


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
        if (
            not path.is_file()
            or path.suffix not in suffixes
            or _is_ignored_artifact(path)
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            violations.append(
                f"{path.relative_to(REPOSITORY_ROOT).as_posix()}: invalid UTF-8"
            )
            continue
        if text and not text.endswith("\n"):
            violations.append(
                f"{path.relative_to(REPOSITORY_ROOT).as_posix()}: missing final newline"
            )
        for index, line in enumerate(text.splitlines(), start=1):
            markdown_hard_break = (
                path.suffix == ".md"
                and line.endswith("  ")
                and not line.endswith("   ")
            )
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


def _verify_presentation_runtime_evidence(path: Path) -> dict[str, Any]:
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
    base = report["base_schedule"]
    draft = report["draft_schedule"]
    comparison = report["comparison"]
    invariant = report["read_only_invariant"]
    passed = (
        report["status"] == "PASS"
        and report["task_id"] == "TASK-DEMO-04"
        and report["profile"] == "showcase"
        and report["seed"] == 20260902
        and report["factory"]["workshops"] == 3
        and report["factory"]["resources"] == 24
        and base["contract_version"] == "schedule-version.v1"
        and base["state"] == "PUBLISHED"
        and base["assignments"] == 580
        and sum(base["page_counts"]) == 580
        and draft["contract_version"] == "schedule-version.v2"
        and draft["state"] == "DRAFT"
        and draft["assignments"] == 585
        and sum(draft["page_counts"]) == 585
        and base["validation_status"] == "PASS"
        and draft["validation_status"] == "PASS"
        and comparison["operation_universe_count"] == 585
        and comparison["change_counts"]["added"] == 5
        and comparison["change_counts"]["changed"] > 0
        and comparison["default_observed_classifications"] == ["ADDED", "CHANGED"]
        and sum(comparison["all_page_counts"]) == 585
        and comparison["deterministic_replay"] is True
        and report["filter_probe"]["all_rows_match"] is True
        and invariant["row_counts_before"] == invariant["row_counts_after"]
        and invariant["story_state_unchanged"] is True
        and invariant["current_publication_unchanged"] is True
        and report["contracts"]["strict_root_additional_properties"] is True
        and report["boundaries"]["publishable"] is False
        and report["boundaries"]["single_showcase_run_not_p95"] is True
        and observed_fingerprint == expected_fingerprint
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(path),
        "base_assignments": base["assignments"],
        "draft_assignments": draft["assignments"],
        "change_counts": comparison["change_counts"],
        "payload_bytes": report["payload_bytes"],
        "presentation_seconds": report["presentation_seconds"],
    }


def _verify_frontend_evidence(path: Path) -> dict[str, Any]:
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
    assertions = report["assertions"]
    runtime = report["runtime_result"]
    workflow = report["workflow"]
    passed = (
        report["status"] == "PASS"
        and report["task_id"] == "TASK-DEMO-05"
        and report["evidence_version"] == "cnc-demo-frontend-evidence.v1"
        and all(assertions.values())
        and workflow["observed_states"]
        == ["EMPTY", "INITIALIZED", "READY_FOR_REVIEW", "BASELINE_PUBLISHED"]
        and workflow["run_id_before_refresh"] == workflow["run_id_after_refresh"]
        and runtime["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and runtime["validation_status"] == "PASS"
        and runtime["hard_violation_count"] == 0
        and runtime["simulation_only"] is True
        and runtime["production_authority"] is False
        and runtime["schedule_publishable"] is False
        and len(report["screenshots"]) == 3
        and all(item["status"] == "PASS" for item in report["screenshots"])
        and report["boundaries"]["d14_schedule_workspace"] == "NOT_IMPLEMENTED"
        and report["boundaries"]["d15_urgent_replan_ui"] == "NOT_IMPLEMENTED"
        and observed_fingerprint == expected_fingerprint
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(path),
        "assertion_count": len(assertions),
        "screenshot_count": len(report["screenshots"]),
        "story_state": workflow["observed_states"][-1],
        "solver_status": runtime["solver_status"],
        "validation_status": runtime["validation_status"],
    }


def _verify_workspace_evidence(path: Path) -> dict[str, Any]:
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
    assertions = report["assertions"]
    runtime = report["runtime_result"]
    workspace = report["workspace"]
    summary = workspace["summary"]
    page = workspace["page"]
    gantt = workspace["gantt"]
    network = report["network"]
    passed = (
        report["status"] == "PASS"
        and report["task_id"] == "TASK-DEMO-06"
        and report["evidence_version"] == "cnc-demo-workspace-evidence.v1"
        and all(assertions.values())
        and runtime["story_state"] == "BASELINE_PUBLISHED"
        and runtime["schedule_state"] == "PUBLISHED"
        and runtime["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and runtime["validation_status"] == "PASS"
        and runtime["hard_violation_count"] == 0
        and runtime["simulation_only"] is True
        and runtime["production_authority"] is False
        and runtime["schedule_publishable"] is False
        and summary["orders"] == 132
        and summary["scheduled_assignments"] == 580
        and summary["resources"] == 24
        and summary["workshops"] == 3
        and page["limit"] <= 200
        and page["returned"] == gantt["assignment_nodes"]
        and gantt["assignment_nodes"] < summary["scheduled_assignments"]
        and network["mutation_requests_during_workspace_actions"] == 0
        and all(request["method"] == "GET" for request in network["workspace_requests"])
        and len(report["screenshots"]) == 5
        and all(item["status"] == "PASS" for item in report["screenshots"])
        and report["boundaries"]["d14_schedule_workspace"] == "IMPLEMENTED"
        and report["boundaries"]["d15_urgent_replan_ui"] == "NOT_IMPLEMENTED"
        and report["boundaries"]["single_showcase_browser_run_not_p95"] is True
        and observed_fingerprint == expected_fingerprint
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(path),
        "assertion_count": len(assertions),
        "screenshot_count": len(report["screenshots"]),
        "orders": summary["orders"],
        "assignments": summary["scheduled_assignments"],
        "rendered_assignment_nodes": gantt["assignment_nodes"],
        "resources": summary["resources"],
        "solver_status": runtime["solver_status"],
        "validation_status": runtime["validation_status"],
    }


def _verify_replan_frontend_evidence(path: Path) -> dict[str, Any]:
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
    assertions = report["assertions"]
    runtime = report["runtime_result"]
    job = report["job"]
    comparison = report["comparison"]
    counts = comparison["change_counts"]
    passed = (
        report["status"] == "PASS"
        and report["task_id"] == "TASK-DEMO-07"
        and report["evidence_version"] == "cnc-demo-replan-frontend-evidence.v1"
        and all(assertions.values())
        and runtime["story_state"] == "DRAFT_COMPARISON_READY"
        and runtime["before_schedule_state"] == "PUBLISHED"
        and runtime["after_schedule_state"] == "DRAFT"
        and runtime["current_publication_unchanged"] is True
        and runtime["simulation_only"] is True
        and runtime["production_authority"] is False
        and runtime["schedule_publishable"] is False
        and job["status"] == "SUCCEEDED"
        and job["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and job["validation_status"] == "PASS"
        and job["hard_violation_count"] == 0
        and counts["added"] == 5
        and counts["changed"] > 0
        and counts["unchanged"] > 0
        and comparison["filters"]["unchanged_first_page"]["limit"] <= 200
        and comparison["refresh_replayed_mutations"] == 0
        and len(report["screenshots"]) == 3
        and all(item["status"] == "PASS" for item in report["screenshots"])
        and report["boundaries"]["d15_urgent_replan_ui"] == "IMPLEMENTED"
        and report["boundaries"]["draft_auto_published"] is False
        and report["boundaries"]["single_showcase_browser_run_not_p95"] is True
        and observed_fingerprint == expected_fingerprint
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(path),
        "assertion_count": len(assertions),
        "screenshot_count": len(report["screenshots"]),
        "story_state": runtime["story_state"],
        "solver_status": job["solver_status"],
        "validation_status": job["validation_status"],
        "change_counts": counts,
        "urgent_job_wall_seconds": job["wall_seconds"],
    }


def _verify_e2e_evidence(path: Path) -> dict[str, Any]:
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
    assertions = report["assertions"]
    story = report["story"]
    accessibility = report["accessibility"]
    boundaries = report["boundaries"]
    passed = (
        report["status"] == "PASS"
        and report["task_id"] == "TASK-DEMO-08"
        and report["evidence_version"] == "cnc-demo-e2e-evidence.v1"
        and len(assertions) == 39
        and all(assertions.values())
        and report["inputs"]["api_audit"]["assertion_count"] == 50
        and report["inputs"]["browser_observation"]["assertion_count"] == 68
        and story["state"] == "DRAFT_COMPARISON_READY"
        and story["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and story["validation_status"] == "PASS"
        and story["change_counts"]["added"] == 5
        and story["change_counts"]["changed"] > 0
        and story["change_counts"]["unchanged"] > 0
        and story["business_mutations"]
        == ["RESET", "INITIAL_PLAN", "ACTIVATE", "URGENT_REPLAN"]
        and accessibility["unnamed_interactive_count"] == 0
        and accessibility["broken_aria_references"] == []
        and accessibility["duplicate_ids"] == []
        and all(item["pass"] is True for item in report["contrast"].values())
        and all(
            item["horizontal_overflow_px"] <= 1 for item in report["layouts"].values()
        )
        and len(report["screenshots"]) == 2
        and all(item["status"] == "PASS" for item in report["screenshots"])
        and len(report["source_sha256"]) == 24
        and boundaries
        == {
            "draft_auto_published": False,
            "p7_registration": None,
            "production_authority": False,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "simulation_only": True,
            "single_runs_not_performance_baseline": True,
            "synthetic_only": True,
        }
        and observed_fingerprint == expected_fingerprint
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(path),
        "assertion_count": len(assertions),
        "api_assertion_count": report["inputs"]["api_audit"]["assertion_count"],
        "browser_assertion_count": report["inputs"]["browser_observation"][
            "assertion_count"
        ],
        "screenshot_count": len(report["screenshots"]),
        "story_state": story["state"],
        "solver_status": story["solver_status"],
        "validation_status": story["validation_status"],
        "change_counts": story["change_counts"],
    }


def _verified_document(path: Path, fingerprint_field: str) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    observed = report.pop(fingerprint_field, None)
    payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    expected = f"sha256:{sha256(payload).hexdigest()}"
    report[fingerprint_field] = observed
    if observed != expected:
        raise ValueError(f"{fingerprint_field} mismatch")
    return report


def _verify_formal_benchmark_evidence() -> dict[str, Any]:
    evidence_path = DEMO_ROOT / "build/validation/benchmark-evidence-demo-09.json"
    browser_path = (
        DEMO_ROOT / "build/validation/browser-benchmark-observation-demo-09.json"
    )
    baseline_path = (
        DEMO_ROOT
        / "benchmarks/baselines/cnc-demo-formal-benchmark.v1/baseline.json"
    )
    evidence = _verified_document(evidence_path, "report_fingerprint")
    browser = _verified_document(browser_path, "report_fingerprint")
    baseline = _verified_document(baseline_path, "baseline_fingerprint")
    checks = evidence["checks"]
    backend = baseline["backend"]
    showcase = backend["profile_summaries"]["showcase"]
    upper = backend["profile_summaries"]["upper"]
    changes = browser["lifecycle"]["change_counts"]
    passed = (
        evidence["status"] == "PASS"
        and evidence["task_id"] == "TASK-DEMO-09"
        and evidence["evidence_version"] == "cnc-demo-benchmark-evidence.v1"
        and all(checks.values())
        and baseline["status"] == "PASS"
        and baseline["baseline_version"]
        == "cnc-demo-formal-benchmark-baseline.v1"
        and baseline["parameter_freeze"]["status"] == "FROZEN"
        and backend["raw_sample_count"] == 21
        and showcase["status"] == "PASS"
        and upper["status"] == "PASS"
        and backend["showcase_thresholds"]["status"] == "PASS"
        and browser["status"] == "PASS"
        and browser["observation_version"]
        == "cnc-demo-browser-benchmark-observation.v1"
        and len(browser["samples"]) == 12
        and changes["added"] == 5
        and changes["changed"] > 0
        and changes["unchanged"] > 0
        and browser["lifecycle"]["validation_status"] == "PASS"
        and browser["lifecycle"]["current_publication_unchanged"] is True
        and baseline["boundaries"]["synthetic_only"] is True
        and baseline["boundaries"]["production_capacity_claim"]
        == "NOT_ESTABLISHED"
        and baseline["boundaries"]["production_sla_claim"]
        == "NOT_ESTABLISHED"
        and baseline["boundaries"]["p7_registration"] is None
    )
    distributions = showcase["distributions"]
    return {
        "status": "PASS" if passed else "FAIL",
        "path": evidence_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(evidence_path),
        "baseline_path": baseline_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "baseline_sha256": _sha256(baseline_path),
        "browser_path": browser_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "browser_sha256": _sha256(browser_path),
        "backend_sample_count": backend["raw_sample_count"],
        "browser_sample_count": len(browser["samples"]),
        "showcase_initial_p95_seconds": distributions[
            "initial_end_to_end_seconds"
        ]["p95"],
        "showcase_replan_p95_seconds": distributions[
            "urgent_replan_end_to_end_seconds"
        ]["p95"],
        "showcase_rss_p95_bytes": distributions["backend_peak_rss_bytes"][
            "p95"
        ],
        "change_counts": changes,
        "parameter_freeze": baseline["parameter_freeze"]["status"],
    }


def _verify_delivery_release_evidence() -> dict[str, Any]:
    observation_path = DEMO_ROOT / "build/validation/delivery-observation-demo-10.json"
    manifest_path = DEMO_ROOT / "release/cnc-demo-release-manifest.v1.json"
    audit_path = DEMO_ROOT / "build/validation/release-audit-demo-10.json"
    observation = _verified_document(observation_path, "report_fingerprint")
    manifest = _verified_document(manifest_path, "manifest_fingerprint")
    audit = _verified_document(audit_path, "report_fingerprint")
    observation_checks = observation["checks"]
    audit_checks = audit["checks"]
    scenario = manifest["scenario"]
    passed = (
        observation["status"] == "PASS"
        and observation["task_id"] == "TASK-DEMO-10"
        and observation["observation_version"]
        == "cnc-demo-delivery-observation.v1"
        and len(observation_checks) == 17
        and all(observation_checks.values())
        and observation["target_site_status"] == "PENDING_FINAL_SITE_REPLAY"
        and manifest["manifest_version"] == "cnc-demo-release-manifest.v1"
        and manifest["task_id"] == "TASK-DEMO-10"
        and manifest["release_class"] == "LOCAL_DELIVERY_CANDIDATE"
        and manifest["target_site_status"] == "PENDING_FINAL_SITE_REPLAY"
        and manifest["file_count"] == len(manifest["files"])
        and all(item["path"].startswith("demo/") for item in manifest["files"])
        and scenario
        == {
            "profile_name": "showcase",
            "profile_id": "CNC-DEMO-SHOWCASE",
            "seed": 20260902,
            "orders": 132,
            "operations": 610,
            "resources": 24,
            "horizon_days": 10,
            "initial_solve_seconds": 20,
            "replan_solve_seconds": 30,
            "profile_set_version": "cnc-demo-benchmark-profiles.v2",
            "parameter_freeze_status": "FROZEN",
        }
        and audit["status"] == "PASS"
        and audit["task_id"] == "TASK-DEMO-10"
        and audit["audit_version"] == "cnc-demo-release-audit.v1"
        and audit["release_decision"] == "LOCAL_CANDIDATE_VERIFIED"
        and audit["local_candidate_ready"] is True
        and audit["final_release_ready"] is False
        and audit["target_site_status"] == "PENDING_FINAL_SITE_REPLAY"
        and len(audit_checks) == 16
        and all(audit_checks.values())
        and audit["manifest"]["fingerprint"] == manifest["manifest_fingerprint"]
        and audit["manifest"]["sha256"] == _sha256(manifest_path)
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "observation_path": observation_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "observation_sha256": _sha256(observation_path),
        "observation_fingerprint": observation["report_fingerprint"],
        "observation_check_count": len(observation_checks),
        "manifest_path": manifest_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "manifest_fingerprint": manifest["manifest_fingerprint"],
        "release_file_count": manifest["file_count"],
        "audit_path": audit_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "audit_sha256": _sha256(audit_path),
        "audit_fingerprint": audit["report_fingerprint"],
        "audit_check_count": len(audit_checks),
        "release_decision": audit["release_decision"],
        "target_site_status": audit["target_site_status"],
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
        if observed_outside.issubset(expected_outside)
        and all(item["status"] == "PASS" for item in protected_files)
        else "FAIL"
    )
    unexpected_outside = sorted(observed_outside - expected_outside)
    changed_protected = sorted(
        item["path"] for item in protected_files if item["status"] != "PASS"
    )

    benchmark_checks = [
        _verify_benchmark(DEMO_ROOT / "benchmarks/results/smoke.json", (108, 102, 12)),
        _verify_benchmark(
            DEMO_ROOT / "benchmarks/results/showcase.json", (610, 580, 24)
        ),
        _verify_benchmark(DEMO_ROOT / "benchmarks/results/upper.json", (700, 665, 30)),
    ]
    contract_report_path = DEMO_ROOT / "build/validation/contract-probes.json"
    contract_report = json.loads(contract_report_path.read_text(encoding="utf-8"))
    context_report = json.loads(context_path.read_text(encoding="utf-8"))

    command_checks = [
        _run(["uv", "run", "pytest", "demo/tests", "-q"]),
        _run(
            ["uv", "run", "ruff", "check", "demo/backend", "demo/scripts", "demo/tests"]
        ),
        _run(["uv", "run", "pyright", "-p", "demo/pyrightconfig.json"]),
        _run(["git", "diff", "--check", "--", "demo"]),
    ]
    if task_id in {
        "TASK-DEMO-05",
        "TASK-DEMO-06",
        "TASK-DEMO-07",
        "TASK-DEMO-08",
        "TASK-DEMO-09",
        "TASK-DEMO-10",
    }:
        frontend_root = DEMO_ROOT / "frontend"
        command_checks = [
            _run([NPM_COMMAND, "ci", "--no-audit", "--no-fund"], cwd=frontend_root),
            _run([NPM_COMMAND, "run", "lint"], cwd=frontend_root),
            _run([NPM_COMMAND, "run", "typecheck"], cwd=frontend_root),
            _run([NPM_COMMAND, "run", "test:run"], cwd=frontend_root),
            _run([NPM_COMMAND, "run", "build"], cwd=frontend_root),
            *command_checks,
        ]
    if task_id == "TASK-DEMO-09":
        command_checks.append(
            _run(
                [
                    "uv",
                    "run",
                    "python",
                    "demo/scripts/run_benchmark_evidence.py",
                    "--verify-only",
                    "--backend-suite",
                    "demo/benchmarks/baselines/cnc-demo-formal-benchmark.v1/backend-suite.json",
                    "--browser-observation",
                    "demo/build/validation/browser-benchmark-observation-demo-09.json",
                    "--baseline",
                    "demo/benchmarks/baselines/cnc-demo-formal-benchmark.v1/baseline.json",
                    "--report",
                    "demo/build/validation/benchmark-evidence-demo-09.json",
                ]
            )
        )
    if task_id == "TASK-DEMO-10":
        command_checks.extend(
            [
                _run(
                    [
                        "uv",
                        "run",
                        "python",
                        "demo/scripts/run_delivery_rehearsal.py",
                        "--verify-only",
                        "--report",
                        "demo/build/validation/delivery-observation-demo-10.json",
                    ]
                ),
                _run(
                    [
                        "uv",
                        "run",
                        "python",
                        "demo/scripts/run_release_audit.py",
                        "--verify-only",
                        "--manifest",
                        "demo/release/cnc-demo-release-manifest.v1.json",
                        "--report",
                        "demo/build/validation/release-audit-demo-10.json",
                    ]
                ),
                _run(["node", "--check", "demo/scripts/browser_delivery_demo_10.js"]),
                _run(["uv", "run", "python", "demo/scripts/democtl.py", "--help"]),
            ]
        )
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
    elif task_id == "TASK-DEMO-04":
        artifact_checks["runtime_evidence"] = _verify_presentation_runtime_evidence(
            DEMO_ROOT / "build/validation/runtime-evidence-demo-04.json"
        )
    elif task_id == "TASK-DEMO-05":
        artifact_checks["frontend_evidence"] = _verify_frontend_evidence(
            DEMO_ROOT / "build/validation/frontend-evidence-demo-05.json"
        )
    elif task_id == "TASK-DEMO-06":
        artifact_checks["frontend_evidence"] = _verify_workspace_evidence(
            DEMO_ROOT / "build/validation/frontend-evidence-demo-06.json"
        )
    elif task_id == "TASK-DEMO-07":
        artifact_checks["frontend_evidence"] = _verify_replan_frontend_evidence(
            DEMO_ROOT / "build/validation/frontend-evidence-demo-07.json"
        )
    elif task_id == "TASK-DEMO-08":
        artifact_checks["e2e_evidence"] = _verify_e2e_evidence(
            DEMO_ROOT / "build/validation/e2e-evidence-demo-08.json"
        )
    elif task_id == "TASK-DEMO-09":
        artifact_checks["formal_benchmark_evidence"] = (
            _verify_formal_benchmark_evidence()
        )
    elif task_id == "TASK-DEMO-10":
        artifact_checks["delivery_release_evidence"] = (
            _verify_delivery_release_evidence()
        )
    functional_passed = (
        all(item["status"] == "PASS" for item in benchmark_checks)
        and all(item["status"] == "PASS" for item in command_checks)
        and all(item["status"] == "PASS" for item in artifact_checks.values())
    )
    passed = scope_status == "PASS" and functional_passed

    demo_files = [
        {
            "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(DEMO_ROOT.rglob("*"))
        if path.is_file()
        and not path.name.startswith("task-machine-report")
        and not _is_ignored_artifact(path)
        and path.suffix not in {".pyc", ".pyo"}
    ]
    return {
        "machine_report_version": "cnc-demo-task-machine-report.v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "task_id": task_id,
        "task_family": "demo-exclusive",
        "status": "PASS" if passed else "FAIL",
        "functional_status": "PASS" if functional_passed else "FAIL",
        "closure_blockers": (
            []
            if passed
            else [
                blocker
                for blocker, is_blocked in (
                    ("SCOPE_CHECK", scope_status != "PASS"),
                    ("FUNCTIONAL_CHECKS", not functional_passed),
                )
                if is_blocked
            ]
        ),
        "scope_check": {
            "status": scope_status,
            "allowed": ["demo/**"],
            "outside_demo_paths_expected": sorted(expected_outside),
            "outside_demo_paths_observed": sorted(observed_outside),
            "unexpected_outside_paths": unexpected_outside,
            "changed_protected_paths": changed_protected,
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
        choices=(
            "TASK-DEMO-01",
            "TASK-DEMO-02",
            "TASK-DEMO-03",
            "TASK-DEMO-04",
            "TASK-DEMO-05",
            "TASK-DEMO-06",
            "TASK-DEMO-07",
            "TASK-DEMO-08",
            "TASK-DEMO-09",
            "TASK-DEMO-10",
        ),
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
            "TASK-DEMO-04": "task-context-manifest-demo-04.json",
            "TASK-DEMO-05": "task-context-manifest-demo-05.json",
            "TASK-DEMO-06": "task-context-manifest-demo-06.json",
            "TASK-DEMO-07": "task-context-manifest-demo-07.json",
            "TASK-DEMO-08": "task-context-manifest-demo-08.json",
            "TASK-DEMO-09": "task-context-manifest-demo-09.json",
            "TASK-DEMO-10": "task-context-manifest-demo-10.json",
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
