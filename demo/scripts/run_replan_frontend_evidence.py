"""Validate the observed Showcase urgent-replan UI and emit D15 evidence."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
from typing import Any


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if (
        len(header) != 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        raise ValueError(f"not a PNG with an IHDR header: {path}")
    return struct.unpack(">II", header[16:24])


def _safe_demo_path(relative: str) -> Path:
    candidate = (REPOSITORY_ROOT / relative).resolve()
    if not candidate.is_relative_to(DEMO_ROOT.resolve()):
        raise ValueError(f"replan evidence path escapes demo: {relative}")
    return candidate


def _source_assertions() -> tuple[dict[str, bool], dict[str, str]]:
    paths = {
        "html": DEMO_ROOT / "frontend/index.html",
        "client": DEMO_ROOT / "frontend/src/api/client.ts",
        "contracts": DEMO_ROOT / "frontend/src/api/contracts.ts",
        "identity": DEMO_ROOT / "frontend/src/app/commandIdentity.ts",
        "controller": DEMO_ROOT / "frontend/src/app/useDemoStory.ts",
        "app": DEMO_ROOT / "frontend/src/DemoApp.tsx",
        "urgent_form": DEMO_ROOT / "frontend/src/components/UrgentOrderPanel.tsx",
        "comparison": DEMO_ROOT
        / "frontend/src/components/ComparisonWorkspace.tsx",
        "schedule_workspace": DEMO_ROOT
        / "frontend/src/components/ScheduleWorkspace.tsx",
        "schedule_evidence": DEMO_ROOT
        / "frontend/src/components/workspace/EvidenceWorkspaceView.tsx",
    }
    text = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    assertions = {
        "html_language": '<html lang="zh-CN">' in text["html"],
        "same_origin_credentials": 'credentials: "same-origin"' in text["client"],
        "urgent_command_endpoint": 'requestJson("/urgent-orders"' in text["client"]
        and 'headers: { "Idempotency-Key": idempotencyKey }' in text["client"],
        "comparison_consumer_cap": "limit > 200" in text["client"]
        and "page.limit > 200" in text["contracts"],
        "persistent_urgent_identity": "plantnexus-demo:urgent:${runId}"
        in text["identity"]
        and "saveUrgentOrder" in text["identity"],
        "draft_recovery": 'next.story_state === "DRAFT_COMPARISON_READY"'
        in text["controller"]
        and "clearUrgentOrder" in text["controller"],
        "automatic_comparison": 'bootstrap?.story_state === "DRAFT_COMPARISON_READY"'
        in text["app"]
        and "ComparisonWorkspace" in text["app"],
        "asset_driven_routes": "configuration.route_templates.map"
        in text["urgent_form"],
        "chinese_business_form": all(
            label in text["urgent_form"]
            for label in (
                "插入加急订单",
                "订单数量",
                "要求交期（北京时间）",
                "优先级",
                "核对并提交插单",
            )
        ),
        "confirmation_boundary": "新方案只会保存为草稿" in text["urgent_form"]
        and "不会自动发布，也不会替换当前仿真基线" in text["urgent_form"],
        "server_authoritative_comparison": "服务端权威比较" in text["comparison"]
        and "limit: 120" in text["comparison"],
        "chinese_change_modes": all(
            label in text["comparison"]
            for label in ("仅看变化", "保持不变", "全部工序")
        ),
        "validator_and_stability_copy": "独立 Validator 仍为通过"
        in text["comparison"]
        and "无硬约束违规" in text["comparison"],
        "dynamic_replan_workspace_copy": "重排草稿工作区"
        in text["schedule_workspace"]
        and "稳定性详见版本比较" in text["schedule_evidence"]
        and "加急重排结果" in text["schedule_evidence"],
    }
    hashes = {name: _sha256(path) for name, path in paths.items()}
    return assertions, hashes


def build_report(observation_path: Path) -> dict[str, Any]:
    observation_path = observation_path.resolve()
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    runtime = observation["runtime_result"]
    urgent = observation["urgent_order"]
    job = observation["job"]
    comparison = observation["comparison"]
    filters = comparison["filters"]
    network = observation["network"]

    screenshot_checks: list[dict[str, Any]] = []
    for entry in observation["screenshots"]:
        path = _safe_demo_path(entry["path"])
        width, height = _png_dimensions(path)
        passed = (
            width == entry["png_width"]
            and height == entry["png_height"]
            and entry["view"] in {"urgent-form", "comparison"}
        )
        screenshot_checks.append(
            {
                "status": "PASS" if passed else "FAIL",
                "view": entry["view"],
                "path": entry["path"],
                "sha256": _sha256(path),
                "png_width": width,
                "png_height": height,
                "viewport_width": entry["viewport_width"],
                "viewport_height": entry["viewport_height"],
            }
        )

    source_assertions, source_hashes = _source_assertions()
    viewport_pairs = {
        (item["width"], item["height"]) for item in observation["viewports"]
    }
    counts = comparison["change_counts"]
    stability = comparison["stability"]
    assertions = {
        "observation_contract": observation["observation_version"]
        == "cnc-demo-browser-replan-observation.v1",
        "task_identity": observation["task_id"] == "TASK-DEMO-07",
        "chinese_document": observation["document"]
        == {
            "lang": "zh-CN",
            "title": "PlantNexus APS · CNC 精密机加工演示",
            "interface_language": "中文",
        },
        "showcase_draft_ready": observation["profile"] == "showcase"
        and runtime["story_state"] == "DRAFT_COMPARISON_READY"
        and runtime["after_schedule_state"] == "DRAFT",
        "published_baseline_preserved": runtime["before_schedule_state"]
        == "PUBLISHED"
        and runtime["current_publication_unchanged"] is True
        and runtime["before_schedule_version_id"]
        == runtime["current_publication_schedule_version_id"]
        == runtime["after_parent_schedule_version_id"]
        and runtime["after_schedule_version_id"]
        != runtime["before_schedule_version_id"],
        "simulation_boundary": runtime["simulation_only"] is True
        and runtime["production_authority"] is False
        and runtime["schedule_publishable"] is False,
        "approved_route_configuration": urgent["available_route_templates"]
        == ["CNC-ROUTE-3", "CNC-ROUTE-4", "CNC-ROUTE-5", "CNC-ROUTE-6"],
        "scripted_urgent_payload": urgent["command_version"]
        == "cnc-demo-urgent-order-command.v1"
        and urgent["route_template_id"] == "CNC-ROUTE-5"
        and urgent["quantity"] == 5
        and urgent["priority_class"] == "URGENT"
        and urgent["accepted_status"] == 202,
        "business_only_form": urgent["base_version_read_only"] is True
        and urgent["confirmation_boundary_visible"] is True
        and urgent["technical_identity_fields_hidden"] is True
        and urgent["idempotency_header_present"] is True,
        "durable_job_completed": job["job_kind"] == "URGENT_REPLAN"
        and job["status"] == "SUCCEEDED"
        and job["stage"] == "COMPLETE"
        and job["stage_count"] == 10
        and job["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and job["validation_status"] == "PASS"
        and job["hard_violation_count"] == 0,
        "comparison_lineage": job["request_id"] == comparison["request_id"]
        and job["change_report_id"] == comparison["change_report_id"]
        and comparison["validation_status"] == "PASS",
        "change_report_counts": counts
        == {"unchanged": 555, "changed": 25, "added": 5, "removed_by_fact": 0},
        "stability_consistency": stability["changed_existing_operations"]
        == counts["changed"]
        and stability["unchanged_existing"] == counts["unchanged"]
        and stability["comparable_existing"] == 580
        and stability["resource_changes"] == 3
        and abs(
            stability["unchanged_ratio"]
            - stability["unchanged_existing"] / stability["comparable_existing"]
        )
        < 1e-12,
        "delivery_evidence": comparison["delivery"]
        == {
            "before_order_count": 132,
            "after_order_count": 133,
            "before_on_time_order_ratio": 1.0,
            "after_on_time_order_ratio": 1.0,
            "before_late_order_count": 0,
            "after_late_order_count": 0,
            "makespan_delta_seconds": 3000,
        },
        "classification_modes": filters["observed_classifications"]
        == ["ADDED", "CHANGED", "UNCHANGED"],
        "bounded_changed_page": filters["changed_page"]
        == {"limit": 120, "returned": 30, "filtered_total": 30, "offset": 0},
        "unchanged_server_pagination": filters["unchanged_first_page"]["limit"]
        == 120
        and filters["unchanged_first_page"]["returned"] == 120
        and filters["unchanged_first_page"]["filtered_total"] == 555
        and filters["unchanged_first_page"]["has_more"] is True
        and filters["unchanged_second_page"]["offset"] == 120
        and filters["unchanged_second_page"]["returned"] == 120,
        "resource_filter": filters["cmm_01_unchanged"]["resource_code"]
        == "CMM-01"
        and filters["cmm_01_unchanged"]["returned"] == 17
        and filters["cmm_01_unchanged"]["filtered_total"] == 17
        and filters["cmm_01_unchanged"]["offset"] == 0,
        "bounded_comparison_dom": comparison["visible_operation_cards"] == 30
        and comparison["comparison_dom_nodes"] < 1_000,
        "draft_workspace_copy_observed": comparison["draft_workspace_copy"]
        == {
            "replan_workspace_label_visible": True,
            "comparison_stability_handoff_visible": True,
            "urgent_replan_source_label_visible": True,
        },
        "refresh_recovery": comparison["refresh_recovered_same_run"] is True
        and comparison["refresh_recovered_same_reference"] is True
        and comparison["refresh_replayed_mutations"] == 0
        and runtime["active_job_after_refresh"] is None,
        "network_boundary": network["urgent_mutation_requests"] == 1
        and network["urgent_request_method"] == "POST"
        and network["urgent_request_status"] == 202
        and network["job_poll_method"] == "GET"
        and network["comparison_request_method"] == "GET"
        and network["comparison_request_status"] == 200
        and network["maximum_comparison_limit"] <= 200,
        "responsive_without_page_overflow": viewport_pairs
        == {(1440, 900), (1024, 768)}
        and all(
            item["client_width"] == item["scroll_width"]
            and item["page_horizontal_overflow"] is False
            for item in observation["viewports"]
        ),
        "clean_console": observation["console"] == {"errors": 0, "warnings": 0},
        "no_visible_credentials": observation["security"]["visible_bearer"]
        is False
        and observation["security"]["visible_authorization_header"] is False,
        "screenshots_valid": len(screenshot_checks) == 3
        and all(item["status"] == "PASS" for item in screenshot_checks),
        "early_performance_only": observation["performance"]["sample_count"] == 1
        and observation["performance"]["urgent_job_wall_seconds"] > 0
        and observation["performance"]["changed_comparison_payload_bytes"] > 0
        and observation["boundaries"]["single_showcase_browser_run_not_p95"]
        is True,
        "scope_boundary": observation["boundaries"]
        == {
            "synthetic_only": True,
            "d15_urgent_replan_ui": "IMPLEMENTED",
            "draft_auto_published": False,
            "current_publication_replaced": False,
            "single_showcase_browser_run_not_p95": True,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "d16_full_failure_security_accessibility_matrix": "NOT_IMPLEMENTED",
        },
        **source_assertions,
    }
    passed = all(assertions.values())
    report: dict[str, Any] = {
        "evidence_version": "cnc-demo-replan-frontend-evidence.v1",
        "task_id": "TASK-DEMO-07",
        "status": "PASS" if passed else "FAIL",
        "observation": {
            "path": observation_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(observation_path),
            "observed_at_utc": observation["observed_at_utc"],
            "tool": observation["tool"],
            "profile": observation["profile"],
        },
        "runtime_result": runtime,
        "urgent_order": urgent,
        "job": job,
        "comparison": comparison,
        "network": network,
        "performance": observation["performance"],
        "viewports": observation["viewports"],
        "screenshots": screenshot_checks,
        "assertions": assertions,
        "frontend_source_sha256": source_hashes,
        "boundaries": observation["boundaries"],
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    report = build_report(arguments.observation)
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
