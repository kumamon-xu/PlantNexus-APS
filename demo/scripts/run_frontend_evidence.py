"""Validate the observed Demo browser smoke and emit fingerprinted evidence."""

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
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"not a PNG with an IHDR header: {path}")
    return struct.unpack(">II", header[16:24])


def _safe_repository_path(relative: str) -> Path:
    candidate = (REPOSITORY_ROOT / relative).resolve()
    if not candidate.is_relative_to(DEMO_ROOT.resolve()):
        raise ValueError(f"browser evidence path escapes demo: {relative}")
    return candidate


def build_report(observation_path: Path) -> dict[str, Any]:
    observation_path = observation_path.resolve()
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    package_path = DEMO_ROOT / "frontend/package.json"
    lock_path = DEMO_ROOT / "frontend/package-lock.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    index_text = (DEMO_ROOT / "frontend/index.html").read_text(encoding="utf-8")
    client_text = (DEMO_ROOT / "frontend/src/api/client.ts").read_text(encoding="utf-8")
    app_text = (DEMO_ROOT / "frontend/src/DemoApp.tsx").read_text(encoding="utf-8")

    screenshot_checks: list[dict[str, Any]] = []
    for entry in observation["screenshots"]:
        path = _safe_repository_path(entry["path"])
        width, height = _png_dimensions(path)
        passed = (
            width == entry["client_width"]
            and height >= entry["viewport_height"]
            and entry["state"] in {"EMPTY", "BASELINE_PUBLISHED"}
        )
        screenshot_checks.append(
            {
                "status": "PASS" if passed else "FAIL",
                "state": entry["state"],
                "path": entry["path"],
                "sha256": _sha256(path),
                "png_width": width,
                "png_height": height,
                "viewport_width": entry["viewport_width"],
                "viewport_height": entry["viewport_height"],
            }
        )

    workflow = observation["workflow"]
    runtime = observation["runtime_result"]
    network = observation["network"]
    assertions = {
        "observation_contract": observation["observation_version"]
        == "cnc-demo-browser-smoke-observation.v1",
        "task_identity": observation["task_id"] == "TASK-DEMO-05",
        "chinese_document": observation["document"]
        == {
            "lang": "zh-CN",
            "title": "PlantNexus APS · CNC 精密机加工演示",
        },
        "complete_story": workflow["observed_states"]
        == ["EMPTY", "INITIALIZED", "READY_FOR_REVIEW", "BASELINE_PUBLISHED"],
        "keyboard_path": all(
            workflow[key]
            for key in (
                "initialization_enter_key",
                "initial_plan_enter_key",
                "activation_enter_key",
                "activation_confirmation_autofocus",
            )
        ),
        "refresh_same_run": workflow["refresh_recovered_published_story"] is True
        and workflow["run_id_before_refresh"] == workflow["run_id_after_refresh"],
        "post_fix_chain": workflow["post_fix_full_chain_completed"] is True,
        "honest_result": runtime["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        and runtime["validation_status"] == "PASS"
        and runtime["hard_violation_count"] == 0,
        "simulation_boundary": runtime["simulation_only"] is True
        and runtime["production_authority"] is False
        and runtime["schedule_publishable"] is False,
        "network_contract": network
        == {
            "session_status": 200,
            "bootstrap_status": 200,
            "reset_status": 202,
            "initial_plan_status": 202,
            "job_status": 200,
            "schedule_view_status": 200,
            "baseline_activation_status": 200,
        },
        "clean_console": observation["console"] == {"errors": 0, "warnings": 0},
        "no_visible_credentials": observation["security"]["visible_bearer"] is False
        and observation["security"]["visible_authorization_header"] is False,
        "responsive_without_page_overflow": all(
            viewport["client_width"] == viewport["scroll_width"]
            for viewport in observation["viewports"]
        )
        and {(item["width"], item["height"]) for item in observation["viewports"]}
        == {(1440, 900), (1024, 768)},
        "screenshots_valid": all(item["status"] == "PASS" for item in screenshot_checks),
        "same_origin_credentials": 'credentials: "same-origin"' in client_text,
        "html_language": '<html lang="zh-CN">' in index_text,
        "future_features_disabled": "下一阶段" in app_text,
        "locked_frontend_dependencies": package["name"] == "@plantnexus/aps-cnc-demo"
        and lock["name"] == package["name"]
        and lock["lockfileVersion"] == 3
        and all(
            script in package["scripts"]
            for script in ("build", "lint", "typecheck", "test:run")
        ),
        "scope_boundary": observation["boundaries"]
        == {
            "synthetic_only": True,
            "d14_schedule_workspace": "NOT_IMPLEMENTED",
            "d15_urgent_replan_ui": "NOT_IMPLEMENTED",
            "production_capacity_claim": "NOT_ESTABLISHED",
        },
    }
    passed = all(assertions.values())
    report: dict[str, Any] = {
        "evidence_version": "cnc-demo-frontend-evidence.v1",
        "task_id": "TASK-DEMO-05",
        "status": "PASS" if passed else "FAIL",
        "observation": {
            "path": observation_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(observation_path),
            "observed_at_utc": observation["observed_at_utc"],
            "tool": observation["tool"],
            "profile": observation["profile"],
        },
        "workflow": workflow,
        "runtime_result": runtime,
        "viewports": observation["viewports"],
        "screenshots": screenshot_checks,
        "assertions": assertions,
        "frontend_sources": {
            "package_json_sha256": _sha256(package_path),
            "package_lock_sha256": _sha256(lock_path),
            "test_framework": "Vitest + Testing Library",
            "browser_smoke": "@playwright/cli + Chromium",
        },
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
