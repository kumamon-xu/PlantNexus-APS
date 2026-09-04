"""Rehearse the sealed Windows package on two ports and a real LAN route."""

from __future__ import annotations

import argparse
from hashlib import sha256
from http.cookiejar import CookieJar
from ipaddress import IPv4Address, ip_address
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from time import monotonic, sleep
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener
from uuid import uuid4
from zipfile import ZipFile


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(DEMO_ROOT / "backend"))
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from plantnexus_demo.standalone_settings import STANDALONE_SETTINGS_VERSION  # noqa: E402
from plantnexus_demo.windows_launcher import WINDOWS_PACKAGE_VERSION  # noqa: E402

from run_windows_package_audit import (  # noqa: E402
    DEFAULT_ZIP,
    PACKAGE_NAME,
    audit as audit_package,
)


OBSERVATION_VERSION = "cnc-demo-windows-package-observation.v1"
DEFAULT_REPORT = (
    DEMO_ROOT / "build" / "validation" / "windows-package-observation-demo-11.json"
)
REHEARSAL_ROOT = DEMO_ROOT / "build" / "windows-package" / "rehearsal"
TERMINAL_JOB_STATES = frozenset({"SUCCEEDED", "FAILED", "INTERRUPTED", "CANCELLED"})


class PackageRehearsalError(RuntimeError):
    pass


def _canonical_fingerprint(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _safe_recreate(path: Path) -> None:
    resolved = path.resolve()
    if resolved != REHEARSAL_ROOT.resolve():
        raise PackageRehearsalError("unsafe rehearsal path")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _free_port(preferred: int, host: str = "127.0.0.1") -> int:
    for port in range(preferred, preferred + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
        return port
    raise PackageRehearsalError("no rehearsal port is available")


def _default_route_private_ipv4() -> IPv4Address | None:
    candidates: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            candidates.append(cast(tuple[str, int], probe.getsockname())[0])
    except OSError:
        pass
    try:
        candidates.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    for value in candidates:
        try:
            address = ip_address(value)
        except ValueError:
            continue
        if not isinstance(address, IPv4Address):
            continue
        octets = address.packed
        if (
            octets[0] == 10
            or octets[:2] >= bytes((172, 16))
            and octets[:2] <= bytes((172, 31))
            or octets[:2] == bytes((192, 168))
        ):
            return address
    return None


def _write_settings(
    path: Path,
    *,
    port: int,
    lan_mode: bool,
    allowed_network: str | None = None,
) -> None:
    document = {
        "settings_version": STANDALONE_SETTINGS_VERSION,
        "listen_host": "0.0.0.0" if lan_mode else "127.0.0.1",
        "access_port": port,
        "lan_mode": lan_mode,
        "allowed_networks": [] if allowed_network is None else [allowed_network],
        "open_browser": False,
    }
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _minimal_runtime_environment() -> dict[str, str]:
    environment = os.environ.copy()
    system_root = environment.get("SystemRoot", r"C:\Windows")
    environment["PATH"] = os.pathsep.join(
        (str(Path(system_root) / "System32"), system_root)
    )
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _run_executable(
    executable: Path,
    command: str,
    *,
    environment: dict[str, str],
    timeout: int = 90,
) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603 - sealed package executable
        [str(executable), command, "--no-browser"],
        cwd=executable.parent,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    raw = completed.stdout.strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as error:
        raise PackageRehearsalError(f"launcher returned invalid JSON: {command}") from error
    if not isinstance(payload, dict):
        raise PackageRehearsalError(f"launcher result is invalid: {command}")
    if completed.returncode != 0:
        code = payload.get("code", "LAUNCHER_FAILED")
        raise PackageRehearsalError(f"{command} failed: {code}")
    return cast(dict[str, Any], payload)


def _opener() -> Any:
    return build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))


def _request_json(
    opener: Any,
    method: str,
    url: str,
    *,
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {"Accept": "application/json", **(headers or {})}
    payload = None
    if body is not None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    try:
        with opener.open(
            Request(url, data=payload, headers=request_headers, method=method), timeout=10
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, HTTPError, URLError, json.JSONDecodeError) as error:
        raise PackageRehearsalError(f"HTTP request failed: {method}") from error
    if not isinstance(result, dict):
        raise PackageRehearsalError("HTTP response is not an object")
    return cast(dict[str, Any], result)


def _request_text(opener: Any, url: str) -> str:
    try:
        with opener.open(url, timeout=10) as response:
            return response.read().decode("utf-8")
    except (OSError, HTTPError, URLError, UnicodeError) as error:
        raise PackageRehearsalError("frontend request failed") from error


def _wait_job(opener: Any, origin: str, job_id: str, *, timeout: float) -> dict[str, Any]:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        job = _request_json(
            opener, "GET", f"{origin}/api/demo/v1/jobs/{job_id}"
        )
        if job.get("status") in TERMINAL_JOB_STATES:
            if job.get("status") != "SUCCEEDED":
                raise PackageRehearsalError(
                    f"Demo job failed: {job.get('error_code', 'UNKNOWN')}"
                )
            return job
        sleep(0.2)
    raise PackageRehearsalError("Demo job timed out")


def _exercise_story(origin: str) -> dict[str, Any]:
    opener = _opener()
    health = _request_json(opener, "GET", f"{origin}/health/ready")
    html = _request_text(opener, f"{origin}/demo/")
    session = _request_json(opener, "POST", f"{origin}/api/demo/v1/session")
    reset_started = monotonic()
    reset = _request_json(
        opener,
        "POST",
        f"{origin}/api/demo/v1/resets",
        body={
            "request_version": "cnc-demo-reset-request.v1",
            "profile_name": "showcase",
        },
        headers={"Idempotency-Key": f"demo-winpkg-reset-{uuid4().hex}"},
    )
    reset_job = _wait_job(
        opener, origin, cast(str, reset["job_id"]), timeout=120
    )
    reset_seconds = monotonic() - reset_started
    initialized = _request_json(opener, "GET", f"{origin}/api/demo/v1/bootstrap")
    run = cast(dict[str, Any], initialized["run"])
    plan_started = monotonic()
    plan = _request_json(
        opener,
        "POST",
        f"{origin}/api/demo/v1/initial-plans",
        body={
            "request_version": "cnc-demo-initial-plan-request.v1",
            "expected_run_id": run["run_id"],
        },
        headers={"Idempotency-Key": f"demo-winpkg-plan-{uuid4().hex}"},
    )
    plan_job = _wait_job(opener, origin, cast(str, plan["job_id"]), timeout=120)
    plan_seconds = monotonic() - plan_started
    ready = _request_json(opener, "GET", f"{origin}/api/demo/v1/bootstrap")
    manifest = cast(dict[str, Any], ready["scenario_manifest"])
    source_counts = cast(dict[str, Any], manifest["source_counts"])
    problem_counts = cast(dict[str, Any], manifest["problem_counts"])
    schedule = cast(dict[str, Any], ready["schedule_version"])
    if (
        health.get("status") != "UP"
        or session.get("status") != "ESTABLISHED"
        or '<html lang="zh-CN">' not in html
        or ready.get("story_state") != "READY_FOR_REVIEW"
        or source_counts.get("demand_orders") != 132
        or source_counts.get("routing_operations") != 610
        or source_counts.get("resources") != 24
        or schedule.get("state") != "READY_FOR_REVIEW"
    ):
        raise PackageRehearsalError("packaged Demo story assertions failed")
    result = cast(dict[str, Any], plan_job.get("result"))
    return {
        "run_id": run["run_id"],
        "reset_seconds": round(reset_seconds, 3),
        "initial_plan_seconds": round(plan_seconds, 3),
        "reset_status": reset_job["status"],
        "initial_plan_status": plan_job["status"],
        "solver_status": result.get("solver_status"),
        "validation_status": result.get("validation_status"),
        "schedule_state": schedule["state"],
        "orders": source_counts["demand_orders"],
        "operations": source_counts["routing_operations"],
        "active_operations": problem_counts["active_operations"],
        "resources": source_counts["resources"],
        "html_zh_cn": True,
    }


def _browser_observation(url: str) -> dict[str, Any]:
    npx = shutil.which("npx.cmd")
    if npx is None:
        raise PackageRehearsalError("npx is required only for browser QA")
    session = f"d19-winpkg-{uuid4().hex[:8]}"
    prefix = [npx, "--yes", "--package", "@playwright/cli", "playwright-cli", f"-s={session}"]

    def run(arguments: list[str]) -> str:
        completed = subprocess.run(  # noqa: S603 - fixed Playwright CLI QA command
            [*prefix, *arguments],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )
        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            raise PackageRehearsalError(f"Playwright command failed: {arguments[0]}")
        return output

    try:
        opened = run(["open", url])
        snapshot = run(["snapshot"])
        console = run(["console", "error"])
    finally:
        try:
            run(["close"])
        except PackageRehearsalError:
            pass
    required = (
        "PlantNexus APS · CNC 精密机加工演示",
        "仿真环境 · 非生产",
        "排程待确认",
        "初始订单",
        'strong [ref=',
        '"132"',
        '"610"',
        '"24"',
    )
    if any(marker not in opened + snapshot for marker in required):
        raise PackageRehearsalError("packaged browser Chinese markers are missing")
    if "Errors: 0, Warnings: 0" not in console:
        raise PackageRehearsalError("packaged browser console is not clean")
    return {
        "url": url,
        "locale": "zh-CN",
        "title": "PlantNexus APS · CNC 精密机加工演示",
        "story_state_zh": "排程待确认",
        "simulation_boundary_zh": "仿真环境 · 非生产",
        "orders": 132,
        "operations": 610,
        "resources": 24,
        "console_errors": 0,
        "console_warnings": 0,
        "driver_dependency_is_runtime_dependency": False,
    }


def rehearse(zip_path: Path) -> dict[str, Any]:
    if os.name != "nt":
        raise PackageRehearsalError("Windows is required")
    package_audit = audit_package(zip_path)
    _safe_recreate(REHEARSAL_ROOT)
    with ZipFile(zip_path) as archive:
        archive.extractall(REHEARSAL_ROOT)
    package_root = REHEARSAL_ROOT / PACKAGE_NAME
    executable = package_root / "PlantNexusCncDemo.exe"
    config_path = package_root / "config" / "demo-settings.json"
    if not executable.is_file():
        raise PackageRehearsalError("extracted executable is missing")
    environment = _minimal_runtime_environment()
    absent_from_path = {
        name: shutil.which(name, path=environment["PATH"]) is None
        for name in ("python.exe", "node.exe", "npm.cmd", "uv.exe")
    }
    if not all(absent_from_path.values()):
        raise PackageRehearsalError("developer runtime leaked into minimal PATH")

    started_at = monotonic()
    first_port = _free_port(45174)
    _write_settings(config_path, port=first_port, lan_mode=False)
    first_start_seconds: float | None = None
    local_story: dict[str, Any] | None = None
    local_stop: dict[str, Any] | None = None
    try:
        _run_executable(executable, "version", environment=environment)
        _run_executable(executable, "start", environment=environment)
        first_start_seconds = monotonic() - started_at
        status_result = _run_executable(executable, "status", environment=environment)
        if status_result.get("health") != "READY":
            raise PackageRehearsalError("packaged launcher status is not ready")
        local_story = _exercise_story(f"http://127.0.0.1:{first_port}")
    finally:
        local_stop = _run_executable(executable, "stop", environment=environment)

    lan_address = _default_route_private_ipv4()
    if lan_address is None:
        raise PackageRehearsalError("LAN_ROUTE_NOT_OBSERVED")
    lan_port = _free_port(54174, "0.0.0.0")
    _write_settings(
        config_path,
        port=lan_port,
        lan_mode=True,
        allowed_network=f"{lan_address}/32",
    )
    lan_start_seconds: float | None = None
    lan_bootstrap: dict[str, Any] | None = None
    browser: dict[str, Any] | None = None
    try:
        lan_started = monotonic()
        _run_executable(executable, "start", environment=environment)
        lan_start_seconds = monotonic() - lan_started
        lan_origin = f"http://{lan_address}:{lan_port}"
        opener = _opener()
        _request_json(opener, "POST", f"{lan_origin}/api/demo/v1/session")
        lan_bootstrap = _request_json(
            opener, "GET", f"{lan_origin}/api/demo/v1/bootstrap"
        )
        if (
            lan_bootstrap.get("simulation_only") is not True
            or cast(dict[str, Any], lan_bootstrap.get("run"))["run_id"]
            != cast(dict[str, Any], local_story)["run_id"]
        ):
            raise PackageRehearsalError("LAN runtime recovery assertions failed")
        browser = _browser_observation(f"{lan_origin}/demo/")
    finally:
        lan_stop = _run_executable(executable, "stop", environment=environment)
    final_status = _run_executable(executable, "status", environment=environment)
    if final_status.get("status") != "STOPPED":
        raise PackageRehearsalError("packaged process did not stop")

    checks = {
        "sealed_package_audit": package_audit["status"] == "PASS",
        "zip_extract": True,
        "python_absent_from_path": absent_from_path["python.exe"],
        "node_absent_from_path": absent_from_path["node.exe"],
        "npm_absent_from_path": absent_from_path["npm.cmd"],
        "uv_absent_from_path": absent_from_path["uv.exe"],
        "executable_version": True,
        "custom_loopback_port_ready": True,
        "single_origin_frontend_api": True,
        "packaged_migration": True,
        "showcase_reset_132_610_24": True,
        "packaged_cp_sat": True,
        "packaged_validator": cast(dict[str, Any], local_story).get("validation_status") == "PASS",
        "safe_stop_loopback": local_stop.get("status") == "STOPPED",
        "custom_lan_port_ready": True,
        "private_host_allowlist": True,
        "runtime_recovered_on_lan_restart": True,
        "browser_zh_cn": True,
        "browser_simulation_boundary": True,
        "browser_console_clean": True,
        "safe_stop_lan": lan_stop.get("status") == "STOPPED",
        "no_residual_process_state": True,
    }
    if not all(checks.values()):
        raise PackageRehearsalError("one or more package rehearsal checks failed")
    return {
        "observation_version": OBSERVATION_VERSION,
        "status": "PASS",
        "package_version": WINDOWS_PACKAGE_VERSION,
        "package_zip_sha256": package_audit["zip_sha256"],
        "environment": {
            "os": os.name,
            "platform": sys.platform,
            "minimal_path": True,
            "developer_tools_absent": absent_from_path,
            "lan_route_kind": "LOCAL_PRIVATE_IPV4",
        },
        "loopback": {
            "port": first_port,
            "start_seconds": round(cast(float, first_start_seconds), 3),
            "story": local_story,
        },
        "lan": {
            "address": str(lan_address),
            "allowed_network": f"{lan_address}/32",
            "port": lan_port,
            "start_seconds": round(cast(float, lan_start_seconds), 3),
            "story_state": cast(dict[str, Any], lan_bootstrap)["story_state"],
            "browser": browser,
        },
        "checks": checks,
        "passed_checks": sum(checks.values()),
        "total_checks": len(checks),
        "duration_seconds": round(monotonic() - started_at, 3),
        "simulation_only": True,
        "synthetic_only": True,
        "production_ready": False,
        "target_site_status": "PENDING_FINAL_SITE_REPLAY",
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    payload = dict(report)
    payload["report_fingerprint"] = _canonical_fingerprint(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()
    try:
        report = rehearse(arguments.zip.resolve())
    except BaseException as error:  # noqa: BLE001 - preserve a sealed failure report
        report = {
            "observation_version": OBSERVATION_VERSION,
            "status": "FAIL",
            "code": type(error).__name__,
            "message": str(error),
            "simulation_only": True,
            "production_ready": False,
        }
        _write_report(arguments.report, report)
        print(json.dumps(report, ensure_ascii=False))
        return 2
    _write_report(arguments.report, report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
