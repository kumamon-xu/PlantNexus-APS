"""Validate the observed Showcase workspace and emit fingerprinted D14 evidence."""

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
        raise ValueError(f"workspace evidence path escapes demo: {relative}")
    return candidate


def _source_assertions() -> tuple[dict[str, bool], dict[str, str]]:
    paths = {
        "html": DEMO_ROOT / "frontend/index.html",
        "client": DEMO_ROOT / "frontend/src/api/client.ts",
        "controller": DEMO_ROOT / "frontend/src/app/useScheduleWorkspace.ts",
        "workspace": DEMO_ROOT / "frontend/src/components/ScheduleWorkspace.tsx",
        "gantt": DEMO_ROOT
        / "frontend/src/components/workspace/GanttWorkspaceView.tsx",
        "capacity": DEMO_ROOT
        / "frontend/src/components/workspace/CapacityWorkspaceView.tsx",
        "evidence": DEMO_ROOT
        / "frontend/src/components/workspace/EvidenceWorkspaceView.tsx",
    }
    text = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    assertions = {
        "html_language": '<html lang="zh-CN">' in text["html"],
        "same_origin_credentials": 'credentials: "same-origin"' in text["client"],
        "consumer_page_cap": "limit > 200" in text["client"],
        "bounded_default_page": "DEMO_SCHEDULE_PAGE_LIMIT = 160"
        in text["controller"],
        "read_only_workspace": "只读 · GET" in text["workspace"],
        "four_workspace_tabs": all(
            label in text["workspace"]
            for label in ("订单与交期", "排程甘特", "计划负荷", "校验与证据")
        ),
        "gantt_semantic_attributes": all(
            token in text["gantt"]
            for token in (
                'data-testid="gantt-assignment"',
                "data-protection={assignment.protection}",
                'data-testid="gantt-completed"',
                "无障碍等价明细",
            )
        ),
        "capacity_not_oee": "这是计划负荷，不是设备综合效率（OEE）。"
        in text["capacity"],
        "chinese_evidence_copy": "求解器、独立校验器与关键指标"
        in text["evidence"],
    }
    hashes = {name: _sha256(path) for name, path in paths.items()}
    return assertions, hashes


def build_report(observation_path: Path) -> dict[str, Any]:
    observation_path = observation_path.resolve()
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    workspace = observation["workspace"]
    summary = workspace["summary"]
    page = workspace["page"]
    gantt = workspace["gantt"]
    order = workspace["order_interaction"]
    capacity = workspace["capacity"]
    evidence = workspace["evidence"]
    runtime = observation["runtime_result"]
    network = observation["network"]

    screenshot_checks: list[dict[str, Any]] = []
    for entry in observation["screenshots"]:
        path = _safe_demo_path(entry["path"])
        width, height = _png_dimensions(path)
        passed = (
            width == entry["png_width"]
            and height == entry["png_height"]
            and height >= entry["viewport_height"]
            and entry["view"] in {"orders", "gantt", "capacity", "evidence"}
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
    request_limits = [item["limit"] for item in network["workspace_requests"]]
    viewport_pairs = {
        (item["width"], item["height"]) for item in observation["viewports"]
    }
    assertions = {
        "observation_contract": observation["observation_version"]
        == "cnc-demo-browser-workspace-observation.v1",
        "task_identity": observation["task_id"] == "TASK-DEMO-06",
        "chinese_document": observation["document"]
        == {
            "lang": "zh-CN",
            "title": "PlantNexus APS · CNC 精密机加工演示",
            "interface_language": "中文",
        },
        "published_showcase": observation["profile"] == "showcase"
        and runtime["story_state"] == "BASELINE_PUBLISHED"
        and runtime["schedule_state"] == "PUBLISHED",
        "showcase_counts": summary
        == {
            "orders": 132,
            "routing_operations": 610,
            "scheduled_assignments": 580,
            "window_filtered_assignments": 546,
            "resources": 24,
            "workshops": 3,
        },
        "honest_solver_result": runtime["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and runtime["validation_status"] == "PASS"
        and runtime["hard_violation_count"] == 0,
        "simulation_boundary": runtime["simulation_only"] is True
        and runtime["production_authority"] is False
        and runtime["schedule_publishable"] is False,
        "four_tabs_observed": workspace["tabs"]
        == ["订单与交期", "排程甘特", "计划负荷", "校验与证据"],
        "bounded_page": page["limit"] == 160
        and page["returned"] == 160
        and page["unfiltered_total"] == 580
        and page["filtered_total"] == 546
        and page["window_hours"] == 72
        and page["sort"] == "ORDER_START_ASC",
        "bounded_gantt_dom": gantt["assignment_nodes"] == page["returned"]
        and gantt["assignment_nodes"] <= 200
        and gantt["assignment_nodes"] < page["unfiltered_total"]
        and gantt["dom_nodes"] < 2_000
        and gantt["resource_rows"] == 24,
        "gantt_semantics": gantt["completed_nodes"] > 0
        and gantt["running_nodes"] > 0
        and gantt["hard_lock_nodes"] > 0
        and gantt["soft_lock_nodes"] > 0
        and gantt["freeze_windows"] == 24
        and gantt["shift_blocks"] > 0
        and gantt["maintenance_blocks"] > 0
        and gantt["hierarchy_filters"] is True
        and gantt["text_equivalent_available"] is True,
        "order_to_gantt": order["query"] == "demand-order-cnc-036"
        and order["visible_orders"] == 1
        and order["focus_status"] is True
        and order["focus_assignment_nodes"] == 5,
        "capacity_view": capacity["rows"] == 24
        and capacity["top_resource_code"] == "GRD-01"
        and capacity["sorted_descending"] is True
        and capacity["non_oee_copy"] is True
        and capacity["server_evidence_version_visible"] is True,
        "evidence_view": evidence["solver_copy_chinese"] is True
        and evidence["validator_copy_chinese"] is True
        and evidence["hard_violation_count"] == 0
        and evidence["kpi_authority_visible"] is True
        and evidence["simulation_boundary_visible"] is True,
        "workspace_get_only": bool(network["workspace_requests"])
        and all(item["method"] == "GET" for item in network["workspace_requests"])
        and all(item["status"] == 200 for item in network["workspace_requests"])
        and max(request_limits) <= 200
        and network["mutation_requests_during_workspace_actions"] == 0,
        "responsive_without_page_overflow": viewport_pairs
        == {(1440, 900), (1024, 768)}
        and all(
            item["client_width"] == item["scroll_width"]
            for item in observation["viewports"]
        )
        and observation["viewports"][1]["gantt_scroll_width"]
        > observation["viewports"][1]["gantt_client_width"],
        "early_performance_only": observation["performance"]["sample_count"] == 1
        and observation["performance"]["workspace_ready_response_end_ms"] > 0
        and observation["performance"]["workspace_payload_bytes"] > 0
        and observation["boundaries"]["single_showcase_browser_run_not_p95"]
        is True,
        "clean_console": observation["console"] == {"errors": 0, "warnings": 0},
        "no_visible_credentials": observation["security"]["visible_bearer"] is False
        and observation["security"]["visible_authorization_header"] is False,
        "screenshots_valid": len(screenshot_checks) == 5
        and all(item["status"] == "PASS" for item in screenshot_checks),
        "scope_boundary": observation["boundaries"]
        == {
            "synthetic_only": True,
            "d14_schedule_workspace": "IMPLEMENTED",
            "d15_urgent_replan_ui": "NOT_IMPLEMENTED",
            "single_showcase_browser_run_not_p95": True,
            "production_capacity_claim": "NOT_ESTABLISHED",
        },
        **source_assertions,
    }
    passed = all(assertions.values())
    report: dict[str, Any] = {
        "evidence_version": "cnc-demo-workspace-evidence.v1",
        "task_id": "TASK-DEMO-06",
        "status": "PASS" if passed else "FAIL",
        "observation": {
            "path": observation_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(observation_path),
            "observed_at_utc": observation["observed_at_utc"],
            "tool": observation["tool"],
            "profile": observation["profile"],
        },
        "runtime_result": runtime,
        "workspace": workspace,
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
                "assertion_count": len(report["assertions"]),
                "screenshot_count": len(report["screenshots"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
