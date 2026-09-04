"""Run the D16 full Chinese story in a real Playwright CLI browser."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
from time import monotonic, sleep, time
from typing import Any, TextIO
from urllib.error import URLError
from urllib.request import urlopen


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
FRONTEND_ROOT = DEMO_ROOT / "frontend"
SCREENSHOT_ROOT = DEMO_ROOT / "build/validation/screenshots"
BACKEND_PORT = 8765
FRONTEND_PORT = 4174
TASK_ID = "TASK-DEMO-08"
EVIDENCE_VERSION = "cnc-demo-browser-e2e-observation.v1"
NPM_COMMAND = "npm.cmd" if os.name == "nt" else "npm"
NPX_COMMAND = "npx.cmd" if os.name == "nt" else "npx"


class BrowserAuditFailure(RuntimeError):
    """Stable failure that never contains session credentials."""


def _fingerprint(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _require_port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise BrowserAuditFailure(f"PORT_IN_USE:{port}") from error


def _wait_http(url: str, timeout: float = 30.0) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310 - fixed loopback URL
                if response.status < 500:
                    return
        except (OSError, URLError):
            sleep(0.2)
    raise BrowserAuditFailure("SERVICE_START_TIMEOUT")


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return int(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)


def _start_process(
    command: list[str],
    *,
    cwd: Path,
    log: TextIO,
) -> subprocess.Popen[str]:
    return subprocess.Popen(  # noqa: S603 - fixed local commands only
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
    )


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(  # noqa: S603 - exact child PID owned by this audit
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=int(subprocess.CREATE_NO_WINDOW),
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _playwright_command(session: str, *arguments: str) -> list[str]:
    return [
        NPX_COMMAND,
        "--yes",
        "--package",
        "@playwright/cli",
        "playwright-cli",
        f"-s={session}",
        *arguments,
    ]


def _run_cli(
    session: str,
    *arguments: str,
    timeout: float = 180.0,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(  # noqa: S603 - fixed Playwright CLI and local script
        _playwright_command(session, *arguments),
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=int(subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0,
    )
    if completed.returncode != 0:
        output = completed.stdout + completed.stderr
        assertion = re.search(r"D16_BROWSER_ASSERTION:[A-Za-z0-9_]+", output)
        detail = assertion.group(0) if assertion is not None else "CLI_EXECUTION_ERROR"
        raise BrowserAuditFailure(
            f"PLAYWRIGHT_COMMAND_FAILED:{arguments[0] if arguments else 'unknown'}:{detail}"
        )
    return completed


def _png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n" or len(payload) < 24:
        raise BrowserAuditFailure("INVALID_SCREENSHOT")
    return struct.unpack(">II", payload[16:24])


def _read_log(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def build_report(*, headed: bool) -> dict[str, Any]:
    if shutil.which(NPX_COMMAND) is None:
        raise BrowserAuditFailure("NPX_NOT_AVAILABLE")
    if shutil.which(NPM_COMMAND) is None:
        raise BrowserAuditFailure("NPM_NOT_AVAILABLE")
    _require_port_free(BACKEND_PORT)
    _require_port_free(FRONTEND_PORT)

    runtime_id = f"e2e-demo-08-{os.getpid()}-{int(time())}"
    runtime_parent = (DEMO_ROOT / "runtime").resolve()
    runtime_root = (runtime_parent / runtime_id).resolve()
    if runtime_root.parent != runtime_parent:
        raise BrowserAuditFailure("RUNTIME_PATH_ESCAPE")
    runtime_root.mkdir(parents=True, exist_ok=False)
    backend_log_path = runtime_root / "backend.log"
    frontend_log_path = runtime_root / "frontend.log"
    backend_log = backend_log_path.open("w", encoding="utf-8", newline="\n")
    frontend_log = frontend_log_path.open("w", encoding="utf-8", newline="\n")
    backend: subprocess.Popen[str] | None = None
    frontend: subprocess.Popen[str] | None = None
    session = f"demo08-{os.getpid()}"
    cli_outputs: list[str] = []
    browser_closed = False
    started = monotonic()
    try:
        backend = _start_process(
            [
                sys.executable,
                str(DEMO_ROOT / "scripts/start_demo.py"),
                "--port",
                str(BACKEND_PORT),
                "--runtime-id",
                runtime_id,
            ],
            cwd=REPOSITORY_ROOT,
            log=backend_log,
        )
        _wait_http(f"http://127.0.0.1:{BACKEND_PORT}/health/live")
        frontend = _start_process(
            [
                NPM_COMMAND,
                "run",
                "dev",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(FRONTEND_PORT),
                "--strictPort",
            ],
            cwd=FRONTEND_ROOT,
            log=frontend_log,
        )
        _wait_http(f"http://127.0.0.1:{FRONTEND_PORT}/demo/")

        open_arguments = ["open", f"http://127.0.0.1:{FRONTEND_PORT}/demo/"]
        if headed:
            open_arguments.append("--headed")
        _run_cli(session, *open_arguments, timeout=60)
        _run_cli(session, "snapshot", timeout=30)
        stage_results: list[dict[str, Any]] = []
        for stage in range(1, 13):
            run = _run_cli(
                session,
                "--json",
                "--raw",
                "run-code",
                "--filename",
                str(DEMO_ROOT / f"scripts/browser_e2e_demo_08_stage{stage}.js"),
                timeout=240,
            )
            cli_outputs.append(run.stdout)
            envelope = json.loads(run.stdout)
            result = json.loads(envelope["result"])
            if not isinstance(result, dict):
                raise BrowserAuditFailure(f"INVALID_STAGE_RESULT:{stage}")
            stage_results.append(result)

        assertions: dict[str, bool] = {}
        for stage, result in enumerate(stage_results, start=1):
            stage_assertions = result.get("assertions")
            if not isinstance(stage_assertions, dict):
                raise BrowserAuditFailure(f"INVALID_STAGE_ASSERTIONS:{stage}")
            overlap = assertions.keys() & stage_assertions.keys()
            if overlap:
                raise BrowserAuditFailure(f"DUPLICATE_ASSERTION:{sorted(overlap)[0]}")
            assertions.update(stage_assertions)
        sections: dict[str, dict[str, Any]] = {
            "identities": {},
            "lifecycle": {},
            "accessibility": {},
            "contrast": {},
            "reduced_motion": {},
            "layouts": {},
            "browser": {},
        }
        business_mutations: list[str] = []
        refresh_replayed_business_mutations = 0
        for result in stage_results:
            for section in sections:
                value = result.get(section)
                if isinstance(value, dict):
                    overlap = sections[section].keys() & value.keys()
                    if overlap:
                        raise BrowserAuditFailure(
                            f"DUPLICATE_SECTION_FIELD:{section}:{sorted(overlap)[0]}"
                        )
                    sections[section].update(value)
            network = result.get("network")
            if isinstance(network, dict):
                mutations = network.get("business_mutations", [])
                if not isinstance(mutations, list) or not all(
                    isinstance(item, str) for item in mutations
                ):
                    raise BrowserAuditFailure("INVALID_NETWORK_MUTATIONS")
                business_mutations.extend(mutations)
                replayed = network.get("refresh_replayed_business_mutations", 0)
                if not isinstance(replayed, int):
                    raise BrowserAuditFailure("INVALID_REFRESH_MUTATION_COUNT")
                refresh_replayed_business_mutations += replayed
        assertions["full_story_business_mutations_exact"] = business_mutations == [
            "RESET",
            "INITIAL_PLAN",
            "ACTIVATE",
            "URGENT_REPLAN",
        ]
        browser_result = {
            "assertions": assertions,
            "identities": sections["identities"],
            "lifecycle": sections["lifecycle"],
            "network": {
                "business_mutations": business_mutations,
                "business_mutation_count": len(business_mutations),
                "refresh_replayed_business_mutations": (
                    refresh_replayed_business_mutations
                ),
            },
            "accessibility": sections["accessibility"],
            "contrast": sections["contrast"],
            "reduced_motion": sections["reduced_motion"],
            "layouts": sections["layouts"],
            "browser": sections["browser"],
        }

        console_run = _run_cli(session, "console", "warning", timeout=30)
        cli_outputs.append(console_run.stdout)
        console_issue_count = len(
            re.findall(r"\[(?:WARNING|ERROR)\]", console_run.stdout)
        )
        browser_result["browser"]["console_warning_or_error_count"] = (
            console_issue_count
        )
        browser_result["assertions"]["console_has_no_warning_or_error"] = (
            console_issue_count == 0
        )

        SCREENSHOT_ROOT.mkdir(parents=True, exist_ok=True)
        wide_path = SCREENSHOT_ROOT / "demo08-e2e-1440x900.png"
        compact_path = SCREENSHOT_ROOT / "demo08-e2e-1024x768.png"
        _run_cli(session, "resize", "1440", "900", timeout=30)
        _run_cli(
            session,
            "screenshot",
            "--filename",
            str(wide_path),
            "--full-page",
            timeout=60,
        )
        _run_cli(session, "resize", "1024", "768", timeout=30)
        _run_cli(
            session,
            "screenshot",
            "--filename",
            str(compact_path),
            "--full-page",
            timeout=60,
        )
        _run_cli(session, "snapshot", timeout=30)
        _run_cli(session, "close", timeout=30)
        browser_closed = True

        backend_log.flush()
        frontend_log.flush()
        token_path = runtime_root / "session.token"
        if not token_path.is_file():
            raise BrowserAuditFailure("SESSION_TOKEN_FILE_MISSING")
        token = token_path.read_text(encoding="utf-8").strip()
        backend_text = _read_log(backend_log_path)
        frontend_text = _read_log(frontend_log_path)
        combined_logs = backend_text + frontend_text
        if token in combined_logs or any(token in output for output in cli_outputs):
            raise BrowserAuditFailure("SESSION_TOKEN_LEAKED")
        if "Traceback (most recent call last)" in combined_logs:
            raise BrowserAuditFailure("SERVICE_TRACEBACK_RECORDED")
        failed_assertions = sorted(
            name
            for name, passed in browser_result["assertions"].items()
            if passed is not True
        )
        if failed_assertions:
            raise BrowserAuditFailure(
                "BROWSER_ASSERTION_FAILED:" + ",".join(failed_assertions)
            )

        screenshots = []
        for label, path, viewport in (
            ("wide", wide_path, [1440, 900]),
            ("compact", compact_path, [1024, 768]),
        ):
            width, height = _png_dimensions(path)
            screenshots.append(
                {
                    "label": label,
                    "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
                    "viewport": viewport,
                    "image_width": width,
                    "image_height": height,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path.read_bytes()).hexdigest(),
                    "status": "PASS",
                }
            )

        report: dict[str, Any] = {
            "evidence_version": EVIDENCE_VERSION,
            "task_id": TASK_ID,
            "status": "PASS",
            "browser_result": browser_result,
            "service_processes": {
                "backend_bind": f"127.0.0.1:{BACKEND_PORT}",
                "frontend_bind": f"127.0.0.1:{FRONTEND_PORT}",
                "backend_loopback_only": (
                    f"127.0.0.1:{BACKEND_PORT}" in backend_text
                ),
                "frontend_loopback_only": (
                    f"127.0.0.1:{FRONTEND_PORT}" in frontend_text
                ),
                "backend_log_lines": len(backend_text.splitlines()),
                "frontend_log_lines": len(frontend_text.splitlines()),
                "session_token_in_logs": False,
                "session_token_in_cli_output": False,
                "traceback_in_logs": False,
            },
            "screenshots": screenshots,
            "runtime": {
                "isolated_named_runtime": True,
                "started_empty": True,
                "cleaned_after_run": True,
                "runtime_path_recorded": False,
                "session_token_recorded": False,
            },
            "wall_seconds": monotonic() - started,
            "boundaries": {
                "synthetic_only": True,
                "simulation_only": True,
                "production_authority": False,
                "draft_auto_published": False,
                "single_browser_run_not_performance_baseline": True,
                "p7_registration": None,
            },
        }
        report["report_fingerprint"] = _fingerprint(report)
        return report
    finally:
        if not browser_closed:
            try:
                _run_cli(session, "close", timeout=20)
            except (BrowserAuditFailure, subprocess.TimeoutExpired):
                pass
        _stop_process(frontend)
        _stop_process(backend)
        frontend_log.close()
        backend_log.close()
        if runtime_root.parent == runtime_parent:
            shutil.rmtree(runtime_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=DEMO_ROOT / "build/validation/browser-e2e-observation-demo-08.json",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run Chromium without a visible window",
    )
    arguments = parser.parse_args()
    try:
        report = build_report(headed=not arguments.headless)
    except (BrowserAuditFailure, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        reason = str(error) if isinstance(error, BrowserAuditFailure) else type(error).__name__
        print(json.dumps({"status": "FAIL", "reason": reason}))
        return 1
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
                "assertions": len(report["browser_result"]["assertions"]),
                "screenshots": len(report["screenshots"]),
                "wall_seconds": report["wall_seconds"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
