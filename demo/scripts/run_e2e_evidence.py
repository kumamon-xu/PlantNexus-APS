"""Verify D16 API and browser observations and emit one fingerprinted evidence file."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
from typing import Any


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
TASK_ID = "TASK-DEMO-08"
EVIDENCE_VERSION = "cnc-demo-e2e-evidence.v1"


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fingerprint(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _load_verified(path: Path, version: str) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    observed = document.get("report_fingerprint")
    unsigned = {
        key: value for key, value in document.items() if key != "report_fingerprint"
    }
    if observed != _fingerprint(unsigned):
        raise ValueError(f"fingerprint mismatch: {path.name}")
    if (
        document.get("task_id") != TASK_ID
        or document.get("evidence_version") != version
    ):
        raise ValueError(f"identity mismatch: {path.name}")
    return document


def _safe_demo_path(relative: str) -> Path:
    path = (REPOSITORY_ROOT / relative).resolve()
    if not path.is_relative_to(DEMO_ROOT.resolve()):
        raise ValueError(f"evidence path escapes demo: {relative}")
    return path


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if (
        len(header) != 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        raise ValueError(f"invalid PNG: {path.name}")
    return struct.unpack(">II", header[16:24])


def _source_evidence() -> tuple[dict[str, bool], dict[str, str]]:
    paths = {
        "job_runner": DEMO_ROOT / "backend/plantnexus_demo/jobs.py",
        "persistence": DEMO_ROOT / "backend/plantnexus_demo/persistence.py",
        "startup": DEMO_ROOT / "scripts/start_demo.py",
        "identity": DEMO_ROOT / "frontend/src/app/commandIdentity.ts",
        "controller": DEMO_ROOT / "frontend/src/app/useDemoStory.ts",
        "modal_focus": DEMO_ROOT / "frontend/src/app/useModalFocus.ts",
        "schedule_workspace": DEMO_ROOT
        / "frontend/src/components/ScheduleWorkspace.tsx",
        "urgent_form": DEMO_ROOT / "frontend/src/components/UrgentOrderPanel.tsx",
        "comparison": DEMO_ROOT / "frontend/src/components/ComparisonWorkspace.tsx",
        "copy": DEMO_ROOT / "frontend/src/domain/copy.ts",
        "api_audit": DEMO_ROOT / "scripts/run_e2e_audit.py",
        "browser_runner": DEMO_ROOT / "scripts/run_browser_e2e.py",
    }
    for stage in range(1, 13):
        paths[f"browser_stage_{stage}"] = (
            DEMO_ROOT / f"scripts/browser_e2e_demo_08_stage{stage}.js"
        )
    text = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    assertions = {
        "loopback_startup_fixed": 'host="127.0.0.1"' in text["startup"],
        "named_runtime_resolver_used": "resolve_named_runtime_root" in text["startup"],
        "runtime_id_allowlist": "_RUNTIME_ID.fullmatch(runtime_id)"
        in text["persistence"],
        "running_job_interruption_persisted": "PROCESS_INTERRUPTED"
        in text["persistence"],
        "interrupted_identity_retry": text["job_runner"].count(
            'status == "INTERRUPTED"'
        )
        >= 3,
        "pending_job_persisted": "savePendingJob" in text["controller"]
        and "pendingJob" in text["identity"],
        "modal_focus_trap_shared": "useModalFocus" in text["modal_focus"]
        and 'event.key !== "Tab"' in text["modal_focus"]
        and "event.shiftKey" in text["modal_focus"],
        "urgent_errors_described": "urgent-quantity-error" in text["urgent_form"]
        and "aria-describedby" in text["urgent_form"],
        "comparison_focus_managed": "headingRef.current?.focus()" in text["comparison"],
        "all_tab_panels_resolve": "tabs.map((tab)" in text["schedule_workspace"]
        and "hidden={activeTab !== tab.id}" in text["schedule_workspace"],
        "interrupted_copy_chinese": "服务重启中断了后台任务" in text["copy"],
        "api_audit_isolated": "tempfile.mkdtemp" in text["api_audit"]
        and "TestClient" in text["api_audit"],
        "browser_runner_loopback": "127.0.0.1" in text["browser_runner"]
        and "runtime_id" in text["browser_runner"],
        "browser_scripts_complete": all(
            text[f"browser_stage_{stage}"].startswith("async (page)")
            for stage in range(1, 13)
        ),
    }
    return assertions, {name: _sha256(path) for name, path in paths.items()}


def build_report(api_path: Path, browser_path: Path) -> dict[str, Any]:
    api_path = api_path.resolve()
    browser_path = browser_path.resolve()
    api = _load_verified(api_path, "cnc-demo-e2e-audit.v1")
    browser = _load_verified(browser_path, "cnc-demo-browser-e2e-observation.v1")
    api_assertions = api["main_flow"]["assertions"]
    browser_assertions = browser["browser_result"]["assertions"]
    result = browser["browser_result"]
    lifecycle = result["lifecycle"]
    service = browser["service_processes"]
    runtime = browser["runtime"]

    screenshot_checks: list[dict[str, Any]] = []
    for item in browser["screenshots"]:
        path = _safe_demo_path(item["path"])
        width, height = _png_dimensions(path)
        passed = (
            item["status"] == "PASS"
            and _sha256(path) == item["sha256"]
            and width == item["image_width"]
            and height == item["image_height"]
            and item["viewport"] in ([1440, 900], [1024, 768])
        )
        screenshot_checks.append(
            {
                "label": item["label"],
                "path": item["path"],
                "status": "PASS" if passed else "FAIL",
                "sha256": _sha256(path),
                "image_width": width,
                "image_height": height,
                "viewport": item["viewport"],
            }
        )

    source_assertions, source_hashes = _source_evidence()
    api_jobs = api["main_flow"]["jobs"]
    api_comparison = api["main_flow"]["comparison"]
    accessibility = result["accessibility"]
    browser_facts = result["browser"]
    boundaries = browser["boundaries"]
    assertions = {
        "api_status_and_assertions": api["status"] == "PASS"
        and len(api_assertions) == 50
        and all(api_assertions.values()),
        "browser_status_and_assertions": browser["status"] == "PASS"
        and len(browser_assertions) == 68
        and all(browser_assertions.values()),
        "api_full_story_lineage": api["main_flow"]["story_state"]
        == "DRAFT_COMPARISON_READY"
        and api["main_flow"]["before_schedule_version_id"]
        != api["main_flow"]["after_schedule_version_id"],
        "api_validator_boundary": api_jobs["initial_plan"]["validation_status"]
        == "PASS"
        and api_jobs["urgent_replan"]["validation_status"] == "PASS"
        and api_jobs["initial_plan"]["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and api_jobs["urgent_replan"]["solver_status"] in {"OPTIMAL", "FEASIBLE"},
        "api_comparison_boundary": api_comparison["change_counts"]["added"] == 5
        and api_comparison["validation_status"] == "PASS"
        and api_comparison["page_limit"] <= 200,
        "concurrent_reset_fail_closed": api["concurrency"]
        == {"durable_jobs": 1, "outcomes": ["ACCEPTED", "ACTIVE_JOB_CONFLICT"]},
        "interrupted_retry_exact": api["recovery"]["interrupted_status"]
        == "INTERRUPTED"
        and api["recovery"]["error_code"] == "PROCESS_INTERRUPTED"
        and api["recovery"]["same_job_identity"] is True
        and api["recovery"]["retry_status"] == "SUCCEEDED"
        and api["recovery"]["attempt"] == 2,
        "failed_reset_preserves_active": api["reset_failure"]["failed_candidate_status"]
        == "FAILED"
        and api["reset_failure"]["previous_active_preserved"] is True,
        "security_matrix_passes": api["production_binding"][
            "production_binding_granted"
        ]
        is False
        and api["path_security"]["broad_delete_target_exposed"] is False
        and api["secret_hygiene"]["control_database_contains_token"] is False
        and api["secret_hygiene"]["repository_matches"] == [],
        "browser_business_mutations_exact": result["network"]["business_mutations"]
        == ["RESET", "INITIAL_PLAN", "ACTIVATE", "URGENT_REPLAN"]
        and result["network"]["business_mutation_count"] == 4
        and result["network"]["refresh_replayed_business_mutations"] == 0,
        "browser_draft_lineage": lifecycle["story_state"] == "DRAFT_COMPARISON_READY"
        and lifecycle["current_publication_unchanged"] is True
        and lifecycle["before_schedule_version_id"]
        != lifecycle["after_schedule_version_id"],
        "browser_validator_boundary": lifecycle["solver_status"]
        in {"OPTIMAL", "FEASIBLE"}
        and lifecycle["validation_status"] == "PASS"
        and lifecycle["job_stage_count"] == 10,
        "browser_change_report": lifecycle["comparison_change_counts"]["added"] == 5
        and lifecycle["comparison_change_counts"]["changed"] > 0
        and lifecycle["comparison_change_counts"]["unchanged"] > 0,
        "accessibility_structure": accessibility["unnamed_interactive_count"] == 0
        and accessibility["duplicate_ids"] == []
        and accessibility["broken_aria_references"] == []
        and accessibility["heading_jump_count"] == 0
        and accessibility["main_count"] == 1
        and accessibility["navigation_landmark_count"] >= 1,
        "accessible_non_color_status": accessibility["status_without_text_count"] == 0
        and accessibility["empty_change_badge_count"] == 0,
        "critical_contrast": all(
            item["pass"] is True for item in result["contrast"].values()
        ),
        "reduced_motion": result["reduced_motion"]["media_matches"] is True
        and result["reduced_motion"]["scroll_behavior"] == "auto"
        and result["reduced_motion"]["animation_iteration_count"] == "1",
        "responsive_layouts": set(result["layouts"]) == {"wide", "compact"}
        and all(
            item["horizontal_overflow_px"] <= 1 for item in result["layouts"].values()
        ),
        "browser_security_hygiene": browser_facts["console_warning_or_error_count"] == 0
        and browser_facts["visible_text_has_credential_marker"] is False
        and browser_facts["visible_text_has_internal_path"] is False
        and browser_facts["visible_text_has_traceback"] is False,
        "session_cookie_boundary": len(browser_facts["cookies"]) == 1
        and browser_facts["cookies"][0]["http_only"] is True
        and browser_facts["cookies"][0]["same_site"] == "Strict"
        and browser_facts["cookies"][0]["value_recorded"] is False,
        "loopback_and_log_hygiene": service["backend_loopback_only"] is True
        and service["frontend_loopback_only"] is True
        and service["session_token_in_logs"] is False
        and service["session_token_in_cli_output"] is False
        and service["traceback_in_logs"] is False,
        "isolated_runtime_cleaned": runtime
        == {
            "cleaned_after_run": True,
            "isolated_named_runtime": True,
            "runtime_path_recorded": False,
            "session_token_recorded": False,
            "started_empty": True,
        },
        "screenshots_valid": len(screenshot_checks) == 2
        and all(item["status"] == "PASS" for item in screenshot_checks),
        "response_and_dom_sizes_recorded": browser_facts["response_sizes_bytes"][
            "bootstrap"
        ]
        > 0
        and browser_facts["response_sizes_bytes"]["comparison"] > 0
        and browser_facts["dom_node_count"] > 0
        and browser_facts["observed_resource_request_count"] > 0,
        "simulation_boundary": api["boundaries"]
        == {
            "draft_auto_published": False,
            "p7_registration": None,
            "performance_baseline_established": False,
            "production_authority": False,
            "simulation_only": True,
            "synthetic_only": True,
        }
        and boundaries
        == {
            "draft_auto_published": False,
            "p7_registration": None,
            "production_authority": False,
            "simulation_only": True,
            "single_browser_run_not_performance_baseline": True,
            "synthetic_only": True,
        },
        **source_assertions,
    }
    passed = all(assertions.values())
    report: dict[str, Any] = {
        "evidence_version": EVIDENCE_VERSION,
        "task_id": TASK_ID,
        "status": "PASS" if passed else "FAIL",
        "inputs": {
            "api_audit": {
                "path": api_path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": _sha256(api_path),
                "assertion_count": len(api_assertions),
            },
            "browser_observation": {
                "path": browser_path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": _sha256(browser_path),
                "assertion_count": len(browser_assertions),
            },
        },
        "story": {
            "state": lifecycle["story_state"],
            "solver_status": lifecycle["solver_status"],
            "validation_status": lifecycle["validation_status"],
            "change_counts": lifecycle["comparison_change_counts"],
            "business_mutations": result["network"]["business_mutations"],
            "api_wall_seconds": api["audit_wall_seconds"],
            "browser_wall_seconds": browser["wall_seconds"],
        },
        "security_and_recovery": {
            "concurrency": api["concurrency"],
            "recovery": api["recovery"],
            "reset_failure": api["reset_failure"],
            "path_security": api["path_security"],
            "production_binding": api["production_binding"],
            "secret_hygiene": api["secret_hygiene"],
        },
        "accessibility": accessibility,
        "contrast": result["contrast"],
        "reduced_motion": result["reduced_motion"],
        "layouts": result["layouts"],
        "browser_metrics": {
            "console_warning_or_error_count": browser_facts[
                "console_warning_or_error_count"
            ],
            "dom_node_count": browser_facts["dom_node_count"],
            "observed_resource_request_count": browser_facts[
                "observed_resource_request_count"
            ],
            "response_sizes_bytes": browser_facts["response_sizes_bytes"],
        },
        "screenshots": screenshot_checks,
        "assertions": assertions,
        "source_sha256": source_hashes,
        "boundaries": {
            "synthetic_only": True,
            "simulation_only": True,
            "production_authority": False,
            "draft_auto_published": False,
            "single_runs_not_performance_baseline": True,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "p7_registration": None,
        },
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-audit", type=Path, required=True)
    parser.add_argument("--browser-observation", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    report = build_report(arguments.api_audit, arguments.browser_observation)
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
                "assertions": len(report["assertions"]),
                "screenshots": len(report["screenshots"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
