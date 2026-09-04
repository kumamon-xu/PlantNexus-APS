"""Run the D17 multi-process formal CNC benchmark suite."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from typing import cast

import ortools


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = REPOSITORY_ROOT / "demo"
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from plantnexus_demo.formal_benchmark import (  # noqa: E402
    FORMAL_SAMPLE_VERSION,
    FORMAL_SUITE_VERSION,
    PROFILE_NAMES,
    FormalBenchmarkError,
    attach_rss_measurement,
    fingerprint,
    load_formal_protocol,
    run_formal_sample,
    showcase_thresholds,
    summarize_profile,
)


RSS_INTERVAL_SECONDS = 0.02
TASK_ID = "TASK-DEMO-09"


class RunnerFailure(RuntimeError):
    """Stable runner failure without child paths or credentials."""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    except FileExistsError as error:
        raise RunnerFailure("IMMUTABLE_OUTPUT_EXISTS") from error


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RunnerFailure("CHILD_REPORT_NOT_OBJECT")
    return cast(dict[str, object], value)


def _safe_command(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed local inventory commands
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
            creationflags=(
                int(subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
            ),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _git_state() -> dict[str, object]:
    head = _safe_command(["git", "rev-parse", "HEAD"])
    status = _safe_command(["git", "status", "--porcelain", "--", "demo"])
    return {
        "head": head or "unavailable",
        "demo_worktree_dirty": bool(status),
    }


def _physical_memory_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _cpu_model() -> str:
    if os.name == "nt":
        value = _safe_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
            ]
        )
        if value:
            return value
    return platform.processor() or platform.machine()


def _physical_cpu_count() -> int | None:
    if os.name == "nt":
        value = _safe_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum",
            ]
        )
        try:
            return None if value is None else int(value)
        except ValueError:
            return None
    value = _safe_command(["getconf", "_NPROCESSORS_ONLN"])
    try:
        return None if value is None else int(value)
    except ValueError:
        return None


def _power_mode() -> str:
    if os.name != "nt":
        return "UNAVAILABLE_ON_THIS_PLATFORM"
    value = _safe_command(["powercfg.exe", "/getactivescheme"])
    return value or "UNAVAILABLE"


def _source_digests() -> dict[str, str]:
    paths = (
        "demo/benchmarks/profiles.json",
        "demo/benchmarks/formal-protocol.v1.json",
        "demo/data/cnc-showcase/manifest.json",
        "demo/backend/plantnexus_demo/assets.py",
        "demo/backend/plantnexus_demo/generator.py",
        "demo/backend/plantnexus_demo/ingress.py",
        "demo/backend/plantnexus_demo/orchestration.py",
        "demo/backend/plantnexus_demo/replanning.py",
        "demo/backend/plantnexus_demo/presentation.py",
        "demo/backend/plantnexus_demo/persistence.py",
        "demo/backend/plantnexus_demo/formal_benchmark.py",
        "backend/app/planning/backends/cp_sat/backend.py",
        "backend/app/planning/backends/cp_sat/replan_backend.py",
        "backend/app/planning/problem/builder.py",
        "backend/app/planning/strategies/global_cp_sat.py",
        "backend/app/planning/strategies/lexicographic_replan.py",
        "backend/app/planning/validation/problem_schedule_validator.py",
        "backend/app/planning/reporting/change_report.py",
        "demo/scripts/run_formal_benchmark.py",
    )
    from hashlib import sha256

    return {
        path: sha256((REPOSITORY_ROOT / path).read_bytes()).hexdigest()
        for path in paths
    }


def collect_environment() -> dict[str, object]:
    value: dict[str, object] = {
        "environment_version": "cnc-demo-benchmark-environment.v1",
        "captured_at_utc": _utc_now(),
        "environment_role": "LOCAL_DEMO_REFERENCE_MACHINE",
        "target_machine_confirmation": "PENDING_D18_SITE_REPLAY",
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "cpu": {
            "model": _cpu_model(),
            "physical_cores": _physical_cpu_count(),
            "logical_cores": os.cpu_count(),
        },
        "memory": {"physical_bytes": _physical_memory_bytes()},
        "power_mode": _power_mode(),
        "runtime": {
            "python": platform.python_version(),
            "ortools": ortools.__version__,
            "node": _safe_command(["node", "--version"]),
            "npm": _safe_command(["npm.cmd" if os.name == "nt" else "npm", "--version"]),
            "browser": "RECORDED_BY_PLAYWRIGHT_BROWSER_SUITE",
        },
        "git": _git_state(),
        "source_sha256": _source_digests(),
        "boundaries": {
            "synthetic_only": True,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
            "portable_across_environment": False,
        },
    }
    value["environment_fingerprint"] = fingerprint(value)
    return value


def _windows_rss(pid: int) -> int | None:
    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    process_query_information = 0x0400
    process_vm_read = 0x0010
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(
        process_query_information | process_vm_read, False, pid
    )
    if not handle:
        return None
    try:
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        success = psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
        return int(counters.WorkingSetSize) if success else None
    finally:
        kernel32.CloseHandle(handle)


def _windows_process_tree(root_pid: int) -> tuple[int, ...]:
    class ProcessEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry32),
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry32),
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if snapshot in {None, invalid_handle}:
        return (root_pid,)
    parents: dict[int, int] = {}
    try:
        entry = ProcessEntry32()
        entry.dwSize = ctypes.sizeof(entry)
        if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    tree = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent_pid in parents.items():
            if parent_pid in tree and pid not in tree:
                tree.add(pid)
                changed = True
    return tuple(sorted(tree))


def _posix_rss(pid: int) -> int | None:
    status = Path(f"/proc/{pid}/status")
    if status.is_file():
        try:
            for line in status.read_text(encoding="utf-8").splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            return None
    completed = _safe_command(["ps", "-o", "rss=", "-p", str(pid)])
    try:
        return None if completed is None else int(completed) * 1024
    except ValueError:
        return None


def _posix_process_tree(root_pid: int) -> tuple[int, ...]:
    tree = {root_pid}
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        children_path = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            children = tuple(
                int(value)
                for value in children_path.read_text(encoding="utf-8").split()
            )
        except (OSError, ValueError):
            children = ()
        for child in children:
            if child not in tree:
                tree.add(child)
                pending.append(child)
    return tuple(sorted(tree))


def _process_tree_rss(pid: int) -> int | None:
    process_ids = (
        _windows_process_tree(pid) if os.name == "nt" else _posix_process_tree(pid)
    )
    values = [
        value
        for process_id in process_ids
        if (value := (_windows_rss(process_id) if os.name == "nt" else _posix_rss(process_id)))
        is not None
    ]
    return sum(values) if values else None


def _creation_flags() -> int:
    return int(subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0


def _child_failure_report(
    *,
    profile: str,
    role: str,
    sequence: int,
    reason: str,
    peak_rss_bytes: int,
    rss_samples: int,
) -> dict[str, object]:
    value: dict[str, object] = {
        "sample_version": FORMAL_SAMPLE_VERSION,
        "sample_id": f"{profile}-{role}-{sequence:02d}",
        "role": role,
        "sequence": sequence,
        "status": "FAIL",
        "error": {"code": reason},
        "resources": {
            "backend_peak_rss_bytes": peak_rss_bytes,
            "backend_peak_rss_method": (
                "WINDOWS_PROCESS_TREE_WORKING_SET_20MS_PARENT_SAMPLER"
                if os.name == "nt"
                else "PROC_PROCESS_TREE_RSS_20MS_PARENT_SAMPLER"
            ),
            "rss_sample_count": rss_samples,
            "rss_sampling_interval_seconds": RSS_INTERVAL_SECONDS,
        },
        "boundaries": {
            "synthetic_only": True,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
        },
    }
    value["sample_fingerprint"] = fingerprint(value)
    return value


def run_isolated_sample(
    *,
    profile: str,
    role: str,
    sequence: int,
) -> dict[str, object]:
    with TemporaryDirectory(prefix=f"plantnexus-demo09-{profile}-{role}-") as temporary:
        temporary_root = Path(temporary)
        child_report = temporary_root / "sample.json"
        runtime_root = temporary_root / "runtime"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--profile",
            profile,
            "--role",
            role,
            "--sequence",
            str(sequence),
            "--runtime-root",
            str(runtime_root),
            "--worker-report",
            str(child_report),
        ]
        process = subprocess.Popen(  # noqa: S603 - fixed self-worker command
            command,
            cwd=REPOSITORY_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
        )
        peak_rss = 0
        rss_samples = 0
        started = monotonic()
        timeout = 900.0
        while process.poll() is None:
            observed = _process_tree_rss(process.pid)
            if observed is not None:
                peak_rss = max(peak_rss, observed)
                rss_samples += 1
            if monotonic() - started > timeout:
                process.kill()
                process.wait(timeout=10)
                return _child_failure_report(
                    profile=profile,
                    role=role,
                    sequence=sequence,
                    reason="WORKER_TIMEOUT",
                    peak_rss_bytes=peak_rss,
                    rss_samples=rss_samples,
                )
            sleep(RSS_INTERVAL_SECONDS)
        stdout, stderr = process.communicate(timeout=10)
        if process.returncode != 0 or not child_report.is_file():
            safe_reason = "WORKER_FAILED"
            for candidate in (stdout, stderr):
                if candidate:
                    try:
                        parsed = json.loads(candidate.strip().splitlines()[-1])
                    except (json.JSONDecodeError, IndexError):
                        continue
                    if isinstance(parsed, dict) and isinstance(parsed.get("reason"), str):
                        safe_reason = cast(str, parsed["reason"])
                        break
            return _child_failure_report(
                profile=profile,
                role=role,
                sequence=sequence,
                reason=safe_reason,
                peak_rss_bytes=peak_rss,
                rss_samples=rss_samples,
            )
        report = _read_json(child_report)
        return attach_rss_measurement(
            report,
            peak_rss_bytes=peak_rss,
            samples=rss_samples,
            interval_seconds=RSS_INTERVAL_SECONDS,
            method=(
                "WINDOWS_PROCESS_TREE_WORKING_SET_20MS_PARENT_SAMPLER"
                if os.name == "nt"
                else "PROC_PROCESS_TREE_RSS_20MS_PARENT_SAMPLER"
            ),
        )


def _sample_file(profile: str, role: str, sequence: int) -> str:
    return f"raw/{profile}-{role}-{sequence:02d}.json"


def build_suite(output_dir: Path, profiles: tuple[str, ...]) -> dict[str, object]:
    protocol = load_formal_protocol(DEMO_ROOT)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RunnerFailure("IMMUTABLE_OUTPUT_DIRECTORY_NOT_EMPTY")
    output_dir.mkdir(parents=True, exist_ok=True)
    environment = collect_environment()
    _json_write_exclusive(output_dir / "environment.json", environment)
    inventory: list[dict[str, object]] = []
    samples_by_profile: dict[str, list[Mapping[str, object]]] = {
        profile: [] for profile in profiles
    }
    for profile in profiles:
        for role, count in (("preflight", 1), ("warmup", 1), ("measured", 5)):
            for sequence in range(1, count + 1):
                report = run_isolated_sample(
                    profile=profile,
                    role=role,
                    sequence=sequence,
                )
                relative_path = _sample_file(profile, role, sequence)
                _json_write_exclusive(output_dir / relative_path, report)
                samples_by_profile[profile].append(report)
                inventory.append(
                    {
                        "profile": profile,
                        "role": role,
                        "sequence": sequence,
                        "path": relative_path,
                        "status": report["status"],
                        "sample_fingerprint": report["sample_fingerprint"],
                    }
                )
                print(
                    json.dumps(
                        {
                            "event": "sample_completed",
                            "profile": profile,
                            "role": role,
                            "sequence": sequence,
                            "status": report["status"],
                            "peak_rss_mib": round(
                                cast(
                                    int,
                                    cast(Mapping[str, object], report["resources"])[
                                        "backend_peak_rss_bytes"
                                    ],
                                )
                                / 1024
                                / 1024,
                                1,
                            ),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    summaries: dict[str, object] = {}
    for profile, samples in samples_by_profile.items():
        try:
            summaries[profile] = summarize_profile(profile, samples)
        except (KeyError, TypeError, ValueError, FormalBenchmarkError):
            summaries[profile] = {
                "profile": profile,
                "status": "FAIL",
                "error": "SAMPLE_AGGREGATION_FAILED",
            }
    showcase = summaries.get("showcase")
    threshold_result: dict[str, object]
    if isinstance(showcase, Mapping) and showcase.get("status") == "PASS":
        threshold_result = showcase_thresholds(showcase, protocol)
    else:
        threshold_result = {
            "status": "FAIL",
            "error": "SHOWCASE_SUMMARY_UNAVAILABLE",
        }
    upper = summaries.get("upper")
    upper_gate = {
        "status": (
            "PASS"
            if isinstance(upper, Mapping) and upper.get("status") == "PASS"
            else "FAIL"
        ),
        "classification": "700_OPERATION_CHARACTERIZATION_NOT_DEFAULT_PROFILE",
    }
    all_profiles_pass = all(
        isinstance(summary, Mapping) and summary.get("status") == "PASS"
        for summary in summaries.values()
    ) and set(summaries) == set(profiles)
    full_profile_set = set(profiles) == set(PROFILE_NAMES)
    frozen = (
        full_profile_set
        and all_profiles_pass
        and threshold_result.get("status") == "PASS"
        and upper_gate["status"] == "PASS"
    )
    suite: dict[str, object] = {
        "suite_version": FORMAL_SUITE_VERSION,
        "task_id": TASK_ID,
        "generated_at_utc": _utc_now(),
        "status": "PASS" if frozen else "FAIL",
        "protocol": {
            "version": protocol.document["protocol_version"],
            "fingerprint": protocol.fingerprint,
            "baseline_version": protocol.baseline_version,
        },
        "environment": {
            "path": "environment.json",
            "fingerprint": environment["environment_fingerprint"],
            "role": environment["environment_role"],
            "target_machine_confirmation": environment[
                "target_machine_confirmation"
            ],
        },
        "sample_inventory": inventory,
        "profiles": summaries,
        "showcase_thresholds": threshold_result,
        "upper_characterization": upper_gate,
        "parameter_freeze": {
            "status": "FROZEN" if frozen else "NOT_FROZEN",
            "default_profile": "showcase",
            "profile_set_version": protocol.document["profile_set_version"],
            "initial_solve_seconds": 20,
            "replan_solve_seconds": 30,
            "urgent_fixture": protocol.document["urgent_fixture"],
            "protocol_fingerprint": protocol.fingerprint,
        },
        "boundaries": {
            "synthetic_only": True,
            "simulation_only": True,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
            "current_environment_only": True,
            "browser_first_screen": "SEPARATE_REQUIRED_EVIDENCE",
            "p7_registration": None,
        },
    }
    suite["suite_fingerprint"] = fingerprint(suite)
    _json_write_exclusive(output_dir / "backend-suite.json", suite)
    return suite


def worker_main(arguments: argparse.Namespace) -> int:
    try:
        report = run_formal_sample(
            repository_root=REPOSITORY_ROOT,
            runtime_root=arguments.runtime_root,
            profile_name=arguments.profile,
            role=arguments.role,
            sequence=arguments.sequence,
        )
        _json_write_exclusive(arguments.worker_report, report)
        print(
            json.dumps(
                {"status": report["status"], "sample_id": report["sample_id"]},
                ensure_ascii=False,
            )
        )
        return 0 if report["status"] == "PASS" else 1
    except (FormalBenchmarkError, RunnerFailure) as error:
        reason = getattr(error, "code", str(error))
    except Exception as error:  # noqa: BLE001 - child boundary is intentionally sanitized
        reason = f"UNEXPECTED_{type(error).__name__.upper()}"
    print(json.dumps({"status": "FAIL", "reason": reason}), flush=True)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--profiles",
        default="all",
        help="all or a comma-separated subset of smoke,showcase,upper",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--profile", choices=PROFILE_NAMES)
    parser.add_argument("--role", choices=("preflight", "warmup", "measured"))
    parser.add_argument("--sequence", type=int)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--worker-report", type=Path)
    arguments = parser.parse_args()
    if arguments.worker:
        required = (
            arguments.profile,
            arguments.role,
            arguments.sequence,
            arguments.runtime_root,
            arguments.worker_report,
        )
        if any(value is None for value in required):
            parser.error("worker arguments are incomplete")
        return worker_main(arguments)
    if arguments.output_dir is None:
        parser.error("--output-dir is required")
    if arguments.profiles == "all":
        profiles = PROFILE_NAMES
    else:
        profiles = tuple(part.strip() for part in arguments.profiles.split(",") if part.strip())
        if not profiles or any(profile not in PROFILE_NAMES for profile in profiles):
            parser.error("--profiles must be all or names from smoke,showcase,upper")
    try:
        suite = build_suite(arguments.output_dir.resolve(), profiles)
    except (FormalBenchmarkError, RunnerFailure, OSError, ValueError) as error:
        reason = getattr(error, "code", str(error))
        print(json.dumps({"status": "FAIL", "reason": reason}), flush=True)
        return 1
    print(
        json.dumps(
            {
                "status": suite["status"],
                "report": str((arguments.output_dir / "backend-suite.json").resolve()),
                "samples": len(cast(list[object], suite["sample_inventory"])),
                "parameter_freeze": cast(Mapping[str, object], suite["parameter_freeze"])[
                    "status"
                ],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if suite["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
