"""Run repeatable D17 first-screen measurements in real Chromium."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from time import monotonic, sleep, time
from typing import Any, TextIO, cast
from urllib.error import URLError
from urllib.request import urlopen


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
FRONTEND_ROOT = DEMO_ROOT / "frontend"
BACKEND_PORT = 8765
FRONTEND_PORT = 4174
TASK_ID = "TASK-DEMO-09"
OBSERVATION_VERSION = "cnc-demo-browser-benchmark-observation.v1"
NPM_COMMAND = "npm.cmd" if os.name == "nt" else "npm"
NPX_COMMAND = "npx.cmd" if os.name == "nt" else "npx"
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from plantnexus_demo.formal_benchmark import (  # noqa: E402
    distribution,
    fingerprint,
    load_formal_protocol,
)


class BrowserBenchmarkFailure(RuntimeError):
    """Stable browser benchmark failure without local secrets or paths."""


def _require_port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise BrowserBenchmarkFailure(f"PORT_IN_USE:{port}") from error


def _wait_http(url: str, timeout: float = 30.0) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310 - fixed loopback URL
                if response.status < 500:
                    return
        except (OSError, URLError):
            sleep(0.2)
    raise BrowserBenchmarkFailure("SERVICE_START_TIMEOUT")


def _creation_flags(*, process_group: bool = False) -> int:
    if os.name != "nt":
        return 0
    flags = int(subprocess.CREATE_NO_WINDOW)
    if process_group:
        flags |= int(subprocess.CREATE_NEW_PROCESS_GROUP)
    return flags


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
        creationflags=_creation_flags(process_group=True),
    )


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(  # noqa: S603 - exact task-owned PID
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=_creation_flags(),
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
    timeout: float = 600.0,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(  # noqa: S603 - fixed CLI and task-owned script
        _playwright_command(session, *arguments),
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=_creation_flags(),
    )
    if completed.returncode != 0:
        output = completed.stdout + completed.stderr
        assertion = re.search(r"D17_BROWSER_ASSERTION:[A-Za-z0-9_]+", output)
        detail = assertion.group(0) if assertion is not None else "CLI_EXECUTION_ERROR"
        raise BrowserBenchmarkFailure(
            f"PLAYWRIGHT_COMMAND_FAILED:{arguments[0] if arguments else 'unknown'}:{detail}"
        )
    return completed


def _playwright_version() -> str:
    completed = subprocess.run(  # noqa: S603 - fixed local version command
        [
            NPX_COMMAND,
            "--yes",
            "--package",
            "@playwright/cli",
            "playwright-cli",
            "--version",
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
        creationflags=_creation_flags(),
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def _build_frontend() -> float:
    started = monotonic()
    completed = subprocess.run(  # noqa: S603 - fixed package script
        [NPM_COMMAND, "run", "build"],
        cwd=FRONTEND_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
        creationflags=_creation_flags(),
    )
    if completed.returncode != 0:
        raise BrowserBenchmarkFailure("FRONTEND_BUILD_FAILED")
    return monotonic() - started


def _read_log(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _numeric(sample: Mapping[str, Any], key: str) -> float:
    value = sample.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise BrowserBenchmarkFailure(f"INVALID_SAMPLE_METRIC:{key}")
    return float(value)


def _dom_numeric(sample: Mapping[str, Any], key: str) -> float:
    dom = sample.get("dom")
    if not isinstance(dom, Mapping):
        raise BrowserBenchmarkFailure("INVALID_SAMPLE_DOM")
    return _numeric(cast(Mapping[str, Any], dom), key)


def _prepare_samples(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = result.get("samples")
    if not isinstance(raw, list) or len(raw) != 12:
        raise BrowserBenchmarkFailure("INVALID_BROWSER_SAMPLE_COUNT")
    samples: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("status") != "PASS":
            raise BrowserBenchmarkFailure("INVALID_BROWSER_SAMPLE")
        sample = cast(dict[str, Any], item)
        responses = sample.get("responses")
        resources = sample.get("api_resources")
        if not isinstance(responses, list) or not isinstance(resources, list):
            raise BrowserBenchmarkFailure("INVALID_BROWSER_RESPONSE_EVIDENCE")
        sample["api_response_count"] = len(responses)
        sample["api_encoded_body_bytes_total"] = sum(
            int(resource.get("encoded_body_bytes", 0))
            for resource in resources
            if isinstance(resource, Mapping)
        )
        sample["sample_fingerprint"] = fingerprint(sample)
        samples.append(sample)
    for state in ("BASELINE_PUBLISHED", "DRAFT_COMPARISON_READY"):
        selected = [sample for sample in samples if sample.get("state") == state]
        roles = [sample.get("role") for sample in selected]
        sequences = sorted(
            int(sample["sequence"])
            for sample in selected
            if sample.get("role") == "measured"
        )
        if roles.count("warmup") != 1 or roles.count("measured") != 5:
            raise BrowserBenchmarkFailure(f"INVALID_SAMPLE_PLAN:{state}")
        if sequences != [1, 2, 3, 4, 5]:
            raise BrowserBenchmarkFailure(f"INVALID_MEASURED_SEQUENCE:{state}")
    return samples


def _state_summary(
    state: str,
    samples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    measured = [
        sample
        for sample in samples
        if sample.get("state") == state and sample.get("role") == "measured"
    ]
    if len(measured) != 5:
        raise BrowserBenchmarkFailure(f"MEASURED_SAMPLE_COUNT_MISMATCH:{state}")
    return {
        "status": "PASS",
        "measured_sample_count": 5,
        "warmup_excluded": True,
        "percentile_method": "nearest-rank",
        "distributions": {
            "ready_milliseconds": distribution(
                [_numeric(sample, "ready_milliseconds") for sample in measured]
            ),
            "navigation_dom_content_loaded_milliseconds": distribution(
                [
                    _numeric(sample, "navigation_dom_content_loaded_milliseconds")
                    for sample in measured
                ]
            ),
            "navigation_load_event_milliseconds": distribution(
                [
                    _numeric(sample, "navigation_load_event_milliseconds")
                    for sample in measured
                ]
            ),
            "api_max_milliseconds": distribution(
                [_numeric(sample, "api_max_milliseconds") for sample in measured]
            ),
            "api_response_count": distribution(
                [_numeric(sample, "api_response_count") for sample in measured]
            ),
            "api_encoded_body_bytes_total": distribution(
                [
                    _numeric(sample, "api_encoded_body_bytes_total")
                    for sample in measured
                ]
            ),
            "dom_element_count": distribution(
                [_dom_numeric(sample, "element_count") for sample in measured]
            ),
            "document_html_bytes": distribution(
                [_dom_numeric(sample, "document_html_bytes") for sample in measured]
            ),
        },
    }


def _source_sha256() -> dict[str, str]:
    paths = (
        "demo/scripts/run_browser_benchmark.py",
        "demo/scripts/browser_benchmark_demo_09.js",
        "demo/scripts/browser_benchmark_demo_09_initial.js",
        "demo/scripts/browser_benchmark_demo_09_activate.js",
        "demo/scripts/browser_benchmark_demo_09_measure_baseline.js",
        "demo/scripts/browser_benchmark_demo_09_stage2.js",
        "demo/scripts/browser_benchmark_demo_09_poll.js",
        "demo/scripts/browser_benchmark_demo_09_ready.js",
        "demo/scripts/browser_benchmark_demo_09_measure_comparison.js",
        "demo/frontend/package.json",
        "demo/frontend/package-lock.json",
        "demo/frontend/src/DemoApp.tsx",
        "demo/frontend/src/app/useDemoStory.ts",
        "demo/frontend/src/app/useScheduleWorkspace.ts",
        "demo/frontend/src/components/ScheduleWorkspace.tsx",
        "demo/frontend/src/components/ComparisonWorkspace.tsx",
        "demo/frontend/src/components/UrgentOrderPanel.tsx",
    )
    return {
        path: sha256((REPOSITORY_ROOT / path).read_bytes()).hexdigest()
        for path in paths
    }


def build_report(*, headed: bool) -> dict[str, Any]:
    if shutil.which(NPX_COMMAND) is None:
        raise BrowserBenchmarkFailure("NPX_NOT_AVAILABLE")
    if shutil.which(NPM_COMMAND) is None:
        raise BrowserBenchmarkFailure("NPM_NOT_AVAILABLE")
    _require_port_free(BACKEND_PORT)
    _require_port_free(FRONTEND_PORT)
    frontend_build_seconds = _build_frontend()
    protocol = load_formal_protocol(DEMO_ROOT)

    runtime_id = f"benchmark-demo-09-{os.getpid()}-{int(time())}"
    runtime_parent = (DEMO_ROOT / "runtime").resolve()
    runtime_root = (runtime_parent / runtime_id).resolve()
    if runtime_root.parent != runtime_parent or not runtime_root.name.startswith(
        "benchmark-demo-09-"
    ):
        raise BrowserBenchmarkFailure("RUNTIME_PATH_ESCAPE")
    runtime_root.mkdir(parents=True, exist_ok=False)
    backend_log_path = runtime_root / "backend.log"
    frontend_log_path = runtime_root / "frontend.log"
    backend_log = backend_log_path.open("w", encoding="utf-8", newline="\n")
    frontend_log = frontend_log_path.open("w", encoding="utf-8", newline="\n")
    backend: subprocess.Popen[str] | None = None
    frontend: subprocess.Popen[str] | None = None
    session = f"demo09-benchmark-{os.getpid()}"
    cli_output = ""
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
                "preview",
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
        def run_script(
            script_name: str, *, announce: bool = True
        ) -> dict[str, Any]:
            nonlocal cli_output
            if announce:
                print(
                    json.dumps(
                        {"event": "browser_stage_started", "script": script_name},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            run = _run_cli(
                session,
                "--json",
                "--raw",
                "run-code",
                "--filename",
                str(DEMO_ROOT / f"scripts/{script_name}"),
                timeout=600,
            )
            cli_output += run.stdout
            envelope = json.loads(run.stdout)
            raw_result = json.loads(envelope["result"])
            if not isinstance(raw_result, dict) or raw_result.get("status") != "PASS":
                raise BrowserBenchmarkFailure("INVALID_BROWSER_RESULT")
            if announce:
                print(
                    json.dumps(
                        {"event": "browser_stage_completed", "script": script_name},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            return cast(dict[str, Any], raw_result)

        reset_result = run_script("browser_benchmark_demo_09.js")
        initial_result = run_script("browser_benchmark_demo_09_initial.js")
        activation_result = run_script("browser_benchmark_demo_09_activate.js")
        baseline_samples = [
            run_script("browser_benchmark_demo_09_measure_baseline.js")["sample"]
            for _ in range(6)
        ]
        urgent_result = run_script("browser_benchmark_demo_09_stage2.js")
        print(
            json.dumps(
                {"event": "browser_stage_started", "script": "comparison_ready_poll"},
                ensure_ascii=False,
            ),
            flush=True,
        )
        ready_deadline = monotonic() + 300
        while True:
            poll_result = run_script(
                "browser_benchmark_demo_09_poll.js", announce=False
            )
            if poll_result.get("ready") is True:
                break
            if monotonic() >= ready_deadline:
                raise BrowserBenchmarkFailure("COMPARISON_READY_TIMEOUT")
            sleep(0.5)
        print(
            json.dumps(
                {"event": "browser_stage_completed", "script": "comparison_ready_poll"},
                ensure_ascii=False,
            ),
            flush=True,
        )
        comparison_result = run_script("browser_benchmark_demo_09_ready.js")
        comparison_samples = [
            run_script("browser_benchmark_demo_09_measure_comparison.js")["sample"]
            for _ in range(6)
        ]
        combined_result: dict[str, Any] = {
            "samples": [*baseline_samples, *comparison_samples]
        }
        samples = _prepare_samples(combined_result)
        _run_cli(session, "close", timeout=30)
        browser_closed = True

        backend_log.flush()
        frontend_log.flush()
        token_path = runtime_root / "session.token"
        if not token_path.is_file():
            raise BrowserBenchmarkFailure("SESSION_TOKEN_FILE_MISSING")
        token = token_path.read_text(encoding="utf-8").strip()
        backend_text = _read_log(backend_log_path)
        frontend_text = _read_log(frontend_log_path)
        combined_logs = backend_text + frontend_text
        if token in combined_logs or token in cli_output:
            raise BrowserBenchmarkFailure("SESSION_TOKEN_LEAKED")
        if "Traceback (most recent call last)" in combined_logs:
            raise BrowserBenchmarkFailure("SERVICE_TRACEBACK_RECORDED")
        observed_fixture = urgent_result.get("fixed_urgent_fixture")
        fixture_fields = (
            "route_template_id",
            "quantity",
            "due_at_local",
            "timezone",
            "priority_class",
            "note",
        )
        expected_observed_fixture = {
            key: protocol.urgent_fixture[key] for key in fixture_fields
        }
        if observed_fixture != expected_observed_fixture:
            raise BrowserBenchmarkFailure("FIXED_URGENT_FIXTURE_MISMATCH")
        mutation_kinds = [
            *cast(list[object], reset_result.get("mutation_kinds", [])),
            *cast(list[object], initial_result.get("mutation_kinds", [])),
            *cast(list[object], activation_result.get("mutation_kinds", [])),
            *cast(list[object], urgent_result.get("mutation_kinds", [])),
        ]
        if mutation_kinds != [
            "RESET",
            "INITIAL_PLAN",
            "ACTIVATE",
            "URGENT_REPLAN",
        ]:
            raise BrowserBenchmarkFailure("BUSINESS_MUTATION_SEQUENCE_MISMATCH")

        report: dict[str, Any] = {
            "observation_version": OBSERVATION_VERSION,
            "task_id": TASK_ID,
            "status": "PASS",
            "protocol": {
                "version": protocol.document["protocol_version"],
                "fingerprint": protocol.fingerprint,
            },
            "measurement_plan": {
                "states": ["BASELINE_PUBLISHED", "DRAFT_COMPARISON_READY"],
                "warmup_per_state": 1,
                "measured_per_state": 5,
                "percentile_method": "nearest-rank",
                "viewport": [1440, 900],
                "frontend_delivery": "VITE_PRODUCTION_BUILD_AND_PREVIEW",
            },
            "samples": samples,
            "summaries": {
                state: _state_summary(state, samples)
                for state in ("BASELINE_PUBLISHED", "DRAFT_COMPARISON_READY")
            },
            "lifecycle": comparison_result["lifecycle"],
            "fixed_urgent_fixture": protocol.urgent_fixture,
            "observed_urgent_command": observed_fixture,
            "business_mutations": mutation_kinds,
            "browser": {
                **cast(dict[str, Any], activation_result["browser"]),
                "playwright_cli": _playwright_version(),
                "headless": not headed,
            },
            "build": {
                "status": "PASS",
                "seconds": frontend_build_seconds,
            },
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
                "session_token_recorded": False,
                "session_token_in_logs_or_cli_output": False,
                "traceback_in_logs": False,
            },
            "runtime": {
                "isolated_named_runtime": True,
                "started_empty": True,
                "cleaned_after_run": True,
                "runtime_path_recorded": False,
            },
            "source_sha256": _source_sha256(),
            "wall_seconds": monotonic() - started,
            "boundaries": {
                "environment_role": "LOCAL_DEMO_REFERENCE_MACHINE",
                "target_machine_confirmation": "PENDING_D18_SITE_REPLAY",
                "synthetic_only": True,
                "simulation_only": True,
                "production_capacity_claim": "NOT_ESTABLISHED",
                "production_sla_claim": "NOT_ESTABLISHED",
                "browser_first_screen_has_numeric_gate": False,
                "p7_registration": None,
            },
        }
        report["report_fingerprint"] = fingerprint(report)
        return report
    finally:
        if not browser_closed:
            try:
                _run_cli(session, "close", timeout=20)
            except (BrowserBenchmarkFailure, subprocess.TimeoutExpired):
                pass
        _stop_process(frontend)
        _stop_process(backend)
        frontend_log.close()
        backend_log.close()
        if (
            runtime_root.parent == runtime_parent
            and runtime_root.name.startswith("benchmark-demo-09-")
        ):
            shutil.rmtree(runtime_root, ignore_errors=True)


def _write_exclusive(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    except FileExistsError as error:
        raise BrowserBenchmarkFailure("IMMUTABLE_OUTPUT_EXISTS") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=(
            DEMO_ROOT / "build/validation/browser-benchmark-observation-demo-09.json"
        ),
    )
    parser.add_argument("--headless", action="store_true")
    arguments = parser.parse_args()
    try:
        report = build_report(headed=not arguments.headless)
        _write_exclusive(arguments.report.resolve(), report)
    except (
        BrowserBenchmarkFailure,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        OSError,
    ) as error:
        reason = (
            str(error)
            if isinstance(error, BrowserBenchmarkFailure)
            else type(error).__name__
        )
        print(json.dumps({"status": "FAIL", "reason": reason}), flush=True)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(arguments.report.resolve()),
                "samples": len(cast(list[object], report["samples"])),
                "wall_seconds": report["wall_seconds"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
