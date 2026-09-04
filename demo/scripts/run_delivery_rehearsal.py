"""Run and verify the D18 cold-start and restart delivery rehearsal."""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import TextIOWrapper
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import monotonic
from typing import Any, cast
from uuid import uuid4


for stream in (sys.stdout, sys.stderr):
    if isinstance(stream, TextIOWrapper):
        stream.reconfigure(encoding="utf-8", errors="replace")


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
VALIDATION_ROOT = DEMO_ROOT / "build" / "validation"
RUNTIME_ROOT = DEMO_ROOT / "runtime"
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from plantnexus_demo.delivery import (  # noqa: E402
    DeliveryController,
    DemoDeliveryError,
    canonical_fingerprint,
    load_launcher_state,
    run_browser_smoke,
    utc_now,
    verify_fingerprinted_document,
)
from plantnexus_demo.persistence import resolve_named_runtime_root  # noqa: E402


EVIDENCE_VERSION = "cnc-demo-delivery-observation.v1"
TASK_ID = "TASK-DEMO-10"
SOURCE_PATHS = (
    "demo/backend/plantnexus_demo/delivery.py",
    "demo/scripts/democtl.py",
    "demo/scripts/browser_delivery_demo_10.js",
    "demo/scripts/run_delivery_rehearsal.py",
    "demo/demo.ps1",
    "demo/demo.sh",
)


class RehearsalFailure(RuntimeError):
    """Stable D18 rehearsal failure."""


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_hashes() -> dict[str, str]:
    return {
        relative: _sha256(REPOSITORY_ROOT / relative)
        for relative in sorted(SOURCE_PATHS)
    }


def _run_d16_recovery() -> dict[str, Any]:
    temporary = (
        DEMO_ROOT / "benchmarks" / "tmp" / f"d18-d16-recovery-{uuid4().hex}.json"
    ).resolve()
    expected_parent = (DEMO_ROOT / "benchmarks" / "tmp").resolve()
    if temporary.parent != expected_parent:
        raise RehearsalFailure("D18_D16_REPORT_PATH_ESCAPE")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    command = [
        shutil.which("uv") or "uv",
        "run",
        "python",
        str(DEMO_ROOT / "scripts" / "run_e2e_audit.py"),
        "--report",
        str(temporary),
    ]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed repository audit command
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
            creationflags=(
                int(subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
            ),
        )
        if completed.returncode != 0 or not temporary.is_file():
            raise RehearsalFailure("D18_D16_RECOVERY_AUDIT_FAILED")
        document = verify_fingerprinted_document(temporary, "report_fingerprint")
        recovery = document.get("recovery")
        if (
            document.get("status") != "PASS"
            or not isinstance(recovery, dict)
            or recovery.get("interrupted_status") != "INTERRUPTED"
            or recovery.get("retry_status") != "SUCCEEDED"
            or recovery.get("same_job_identity") is not True
            or recovery.get("replayed") is not True
            or recovery.get("attempt") != 2
        ):
            raise RehearsalFailure("D18_D16_RECOVERY_SEMANTICS_INVALID")
        return {
            "status": "PASS",
            "evidence_version": document["evidence_version"],
            "recovery": cast(dict[str, Any], recovery),
            "report_fingerprint": document["report_fingerprint"],
        }
    finally:
        temporary.unlink(missing_ok=True)


def _remove_owned_runtime(runtime_id: str) -> None:
    candidate = resolve_named_runtime_root(DEMO_ROOT, runtime_id).resolve()
    parent = RUNTIME_ROOT.resolve()
    if candidate.parent != parent or not candidate.name.startswith("delivery-demo-10-"):
        raise RehearsalFailure("D18_RUNTIME_CLEANUP_TARGET_INVALID")
    if candidate.exists():
        shutil.rmtree(candidate)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RehearsalFailure(code)


def build_observation(*, headed: bool, install: bool, build: bool) -> dict[str, Any]:
    controller = DeliveryController()
    runtime_id = f"delivery-demo-10-{os.getpid()}-{uuid4().hex[:10]}"
    runtime_path = resolve_named_runtime_root(DEMO_ROOT, runtime_id)
    _require(not runtime_path.exists(), "D18_RUNTIME_NOT_FRESH")
    completed_cleanly = False
    started = monotonic()
    try:
        doctor = controller.doctor(require_free_ports=True)
        cold_start = controller.start(
            runtime_id=runtime_id,
            install=install,
            build=build,
        )
        cold_health = controller.health()
        reset_started = monotonic()
        reset = controller.reset(profile_name="showcase", timeout=180)
        reset_seconds = monotonic() - reset_started
        first_browser_started = monotonic()
        first_browser = run_browser_smoke(headed=headed)
        first_browser_seconds = monotonic() - first_browser_started
        first_stop = controller.stop()

        restart_started = monotonic()
        restart = controller.start(runtime_id=runtime_id, install=False, build=False)
        restart_seconds = monotonic() - restart_started
        restart_health = controller.health()
        second_browser_started = monotonic()
        second_browser = run_browser_smoke(headed=headed)
        second_browser_seconds = monotonic() - second_browser_started
        second_stop = controller.stop()

        d16_recovery = _run_d16_recovery()
        checks = {
            "doctor_pass": doctor["status"] == "PASS",
            "fresh_runtime": True,
            "cold_start_running": cold_start["status"] == "RUNNING",
            "cold_health_pass": cold_health["status"] == "PASS",
            "showcase_reset_pass": reset["status"] == "PASS",
            "showcase_profile_exact": (
                reset["profile_name"] == "showcase"
                and reset["profile_id"] == "CNC-DEMO-SHOWCASE"
                and reset["seed"] == 20260902
                and reset["counts"]
                == {"orders": 132, "operations": 610, "resources": 24}
            ),
            "simulation_boundary_exact": (
                reset["simulation_only"] is True
                and reset["production_authority"] is False
            ),
            "first_browser_pass": first_browser["status"] == "PASS",
            "first_browser_chinese": first_browser["locale"] == "zh-CN",
            "first_stop_pass": first_stop["status"] == "STOPPED",
            "restart_running": restart["status"] == "RUNNING",
            "restart_health_pass": restart_health["status"] == "PASS",
            "restart_preserved_run": second_browser["run_id"] == reset["run_id"],
            "second_browser_pass": second_browser["status"] == "PASS",
            "second_stop_pass": second_stop["status"] == "STOPPED",
            "launcher_state_removed": load_launcher_state() is None,
            "d16_interruption_recovery_pass": d16_recovery["status"] == "PASS",
        }
        _require(all(checks.values()), "D18_REHEARSAL_ASSERTION_FAILED")
        document: dict[str, Any] = {
            "observation_version": EVIDENCE_VERSION,
            "task_id": TASK_ID,
            "generated_at_utc": utc_now(),
            "status": "PASS",
            "environment_role": "LOCAL_DELIVERY_CANDIDATE",
            "target_site_status": "PENDING_FINAL_SITE_REPLAY",
            "source_head": subprocess.check_output(
                [shutil.which("git") or "git", "rev-parse", "HEAD"],
                cwd=REPOSITORY_ROOT,
                text=True,
                encoding="utf-8",
            ).strip(),
            "source_sha256": _source_hashes(),
            "environment": doctor["runtime"],
            "profile": doctor["profile"],
            "checks": checks,
            "cold_start": {
                "dependency_install_requested": install,
                "production_build_requested": build,
                "ready_seconds": cold_start["ready_seconds"],
                "health_status": cold_health["status"],
            },
            "reset": {
                "wall_seconds": reset_seconds,
                "story_state": reset["story_state"],
                "profile_id": reset["profile_id"],
                "seed": reset["seed"],
                "counts": reset["counts"],
            },
            "browser": {
                "engine": "Chromium via @playwright/cli",
                "headed": headed,
                "cold_start": {
                    "wall_seconds": first_browser_seconds,
                    **first_browser,
                },
                "restart": {
                    "wall_seconds": second_browser_seconds,
                    **second_browser,
                },
            },
            "restart": {
                "same_runtime": True,
                "dependency_install_requested": False,
                "production_build_requested": False,
                "ready_seconds": restart_seconds,
                "health_status": restart_health["status"],
                "run_identity_preserved": True,
            },
            "safe_stop": {
                "first": first_stop["processes"],
                "second": second_stop["processes"],
                "state_removed": True,
            },
            "interruption_recovery": d16_recovery,
            "observation_wall_seconds": monotonic() - started,
            "boundaries": {
                "loopback_only": True,
                "simulation_only": True,
                "synthetic_only": True,
                "production_authority": False,
                "draft_auto_published": False,
                "delivery_timings_are_solver_sla": False,
                "production_capacity_claim": "NOT_ESTABLISHED",
                "production_sla_claim": "NOT_ESTABLISHED",
                "p7_registration": None,
            },
        }
        serialized = json.dumps(document, ensure_ascii=False, sort_keys=True)
        _require("plantnexus_demo_session" not in serialized, "D18_SESSION_NAME_LEAKED")
        _require("session.token" not in serialized, "D18_SESSION_PATH_LEAKED")
        document["report_fingerprint"] = canonical_fingerprint(document)
        completed_cleanly = True
        return document
    finally:
        if load_launcher_state() is not None:
            try:
                controller.stop()
            except DemoDeliveryError:
                completed_cleanly = False
        if completed_cleanly:
            _remove_owned_runtime(runtime_id)


def verify_observation(path: Path) -> dict[str, Any]:
    document = verify_fingerprinted_document(path, "report_fingerprint")
    checks = document.get("checks")
    reset = document.get("reset")
    browser = document.get("browser")
    restart = document.get("restart")
    safe_stop = document.get("safe_stop")
    interruption = document.get("interruption_recovery")
    if (
        document.get("observation_version") != EVIDENCE_VERSION
        or document.get("task_id") != TASK_ID
        or document.get("status") != "PASS"
        or not isinstance(checks, dict)
        or len(checks) != 17
        or not all(checks.values())
        or document.get("source_sha256") != _source_hashes()
        or document.get("target_site_status") != "PENDING_FINAL_SITE_REPLAY"
        or not isinstance(reset, dict)
        or reset.get("story_state") != "INITIALIZED"
        or reset.get("profile_id") != "CNC-DEMO-SHOWCASE"
        or reset.get("seed") != 20260902
        or reset.get("counts")
        != {"orders": 132, "operations": 610, "resources": 24}
        or not isinstance(browser, dict)
        or any(
            browser.get(stage, {}).get("status") != "PASS"
            or browser.get(stage, {}).get("locale") != "zh-CN"
            or browser.get(stage, {}).get("story_state") != "INITIALIZED"
            or browser.get(stage, {}).get("page_error_count") != 0
            or browser.get(stage, {}).get("console_error_count") != 0
            or browser.get(stage, {}).get("server_error_response_count") != 0
            or browser.get(stage, {}).get("simulation_only") is not True
            or browser.get(stage, {}).get("production_authority") is not False
            for stage in ("cold_start", "restart")
        )
        or not isinstance(restart, dict)
        or restart.get("same_runtime") is not True
        or restart.get("run_identity_preserved") is not True
        or not isinstance(safe_stop, dict)
        or safe_stop.get("state_removed") is not True
        or not isinstance(interruption, dict)
        or interruption.get("status") != "PASS"
        or interruption.get("recovery", {}).get("interrupted_status")
        != "INTERRUPTED"
        or interruption.get("recovery", {}).get("retry_status") != "SUCCEEDED"
        or interruption.get("recovery", {}).get("same_job_identity") is not True
        or interruption.get("recovery", {}).get("attempt") != 2
        or document.get("boundaries")
        != {
            "loopback_only": True,
            "simulation_only": True,
            "synthetic_only": True,
            "production_authority": False,
            "draft_auto_published": False,
            "delivery_timings_are_solver_sla": False,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
            "p7_registration": None,
        }
    ):
        raise RehearsalFailure("D18_OBSERVATION_INVALID")
    return document


def _report_path(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.parent != VALIDATION_ROOT.resolve():
        raise RehearsalFailure("D18_REPORT_PATH_ESCAPE")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=VALIDATION_ROOT / "delivery-observation-demo-10.json",
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    arguments = parser.parse_args()
    try:
        report_path = _report_path(arguments.report)
        if arguments.verify_only:
            report = verify_observation(report_path)
        else:
            if report_path.exists():
                raise RehearsalFailure("D18_REPORT_ALREADY_EXISTS")
            report = build_observation(
                headed=arguments.headed,
                install=not arguments.skip_install,
                build=not arguments.skip_build,
            )
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with report_path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "message_zh": "D18 冷启动与重启恢复演练通过",
                    "report": report_path.relative_to(REPOSITORY_ROOT).as_posix(),
                    "target_site_status": report["target_site_status"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (DemoDeliveryError, RehearsalFailure) as error:
        code = error.code if isinstance(error, DemoDeliveryError) else str(error)
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "code": code,
                    "message_zh": "D18 交付演练未通过，已保留安全日志供排查",
                },
                ensure_ascii=False,
            )
        )
        return 1
    except Exception:  # noqa: BLE001 - terminal output must never expose traceback/secrets
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "code": "D18_REHEARSAL_UNEXPECTED",
                    "message_zh": "D18 交付演练发生未分类错误，已隐藏内部细节",
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
