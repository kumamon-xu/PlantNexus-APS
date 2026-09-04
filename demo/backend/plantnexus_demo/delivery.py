"""Safe, one-command delivery control for the standalone CNC Demo."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
from time import monotonic, sleep
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from uuid import uuid4

from .assets import load_demo_assets
from .persistence import resolve_named_runtime_root


DEMO_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = DEMO_ROOT.parent
FRONTEND_ROOT = DEMO_ROOT / "frontend"
LAUNCHER_ROOT = DEMO_ROOT / "runtime" / "launcher"
LAUNCHER_STATE_PATH = LAUNCHER_ROOT / "state.json"
BACKEND_PORT = 8765
FRONTEND_PORT = 4174
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}/demo/"
DEFAULT_RUNTIME_ID = "cnc-showcase"
LAUNCHER_STATE_VERSION = "cnc-demo-launcher-state.v1"
DOCTOR_VERSION = "cnc-demo-delivery-doctor.v1"
STATUS_VERSION = "cnc-demo-delivery-status.v1"
RESET_VERSION = "cnc-demo-delivery-reset.v1"
SMOKE_VERSION = "cnc-demo-delivery-smoke.v1"
NPM_COMMAND = "npm.cmd" if os.name == "nt" else "npm"
NPX_COMMAND = "npx.cmd" if os.name == "nt" else "npx"
_SEMVER = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
_TERMINAL_JOB_STATES = frozenset(
    {"SUCCEEDED", "FAILED", "INTERRUPTED", "CANCELLED"}
)


class DemoDeliveryError(RuntimeError):
    """Stable delivery failure safe for terminal output and persisted evidence."""

    def __init__(self, code: str, *, field: str | None = None) -> None:
        self.code = code
        self.field = field
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    role: str
    pid: int
    creation_marker: str


@dataclass(frozen=True, slots=True)
class LauncherState:
    state_version: str
    instance_id: str
    runtime_id: str
    started_at_utc: str
    source_head: str
    asset_digest: str
    baseline_fingerprint: str
    backend_url: str
    frontend_url: str
    log_directory: str
    backend: ProcessIdentity
    frontend: ProcessIdentity


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_fingerprint(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DemoDeliveryError("DELIVERY_DOCUMENT_INVALID", field=path.name) from error
    if not isinstance(document, dict):
        raise DemoDeliveryError("DELIVERY_DOCUMENT_INVALID", field=path.name)
    return cast(dict[str, Any], document)


def verify_fingerprinted_document(path: Path, field: str) -> dict[str, Any]:
    document = _read_json(path)
    observed = document.pop(field, None)
    expected = canonical_fingerprint(document)
    document[field] = observed
    if observed != expected:
        raise DemoDeliveryError("DELIVERY_FINGERPRINT_MISMATCH", field=path.name)
    return document


def _command_path(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise DemoDeliveryError("DELIVERY_DEPENDENCY_MISSING", field=name)
    return path


def _command_version(command: list[str], field: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - resolved executable and fixed args
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            creationflags=(
                int(subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
            ),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DemoDeliveryError("DELIVERY_DEPENDENCY_UNUSABLE", field=field) from error
    value = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0 or not value:
        raise DemoDeliveryError("DELIVERY_DEPENDENCY_UNUSABLE", field=field)
    return value.splitlines()[0].strip()


def _semver_at_least(value: str, minimum: tuple[int, int, int]) -> bool:
    match = _SEMVER.search(value)
    return match is not None and tuple(int(part) for part in match.groups()) >= minimum


def _git_head() -> str:
    return _command_version(
        [_command_path("git"), "rev-parse", "HEAD"],
        "git",
    )


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _runtime_write_check() -> None:
    runtime_root = (DEMO_ROOT / "runtime").resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    if runtime_root.parent != DEMO_ROOT.resolve():
        raise DemoDeliveryError("DELIVERY_RUNTIME_PATH_ESCAPE")
    probe = runtime_root / f".delivery-write-probe-{os.getpid()}-{uuid4().hex}"
    try:
        probe.write_text("probe\n", encoding="utf-8")
        if probe.read_text(encoding="utf-8") != "probe\n":
            raise DemoDeliveryError("DELIVERY_RUNTIME_NOT_WRITABLE")
    except OSError as error:
        raise DemoDeliveryError("DELIVERY_RUNTIME_NOT_WRITABLE") from error
    finally:
        probe.unlink(missing_ok=True)


def _verified_release_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = _read_json(DEMO_ROOT / "benchmarks" / "formal-protocol.v1.json")
    baseline = verify_fingerprinted_document(
        DEMO_ROOT
        / "benchmarks"
        / "baselines"
        / "cnc-demo-formal-benchmark.v1"
        / "baseline.json",
        "baseline_fingerprint",
    )
    evidence = verify_fingerprinted_document(
        DEMO_ROOT / "build" / "validation" / "benchmark-evidence-demo-09.json",
        "report_fingerprint",
    )
    if (
        protocol.get("protocol_version")
        != "cnc-demo-formal-benchmark-protocol.v1"
        or protocol.get("default_profile") != "showcase"
        or baseline.get("status") != "PASS"
        or baseline.get("parameter_freeze", {}).get("status") != "FROZEN"
        or evidence.get("status") != "PASS"
    ):
        raise DemoDeliveryError("DELIVERY_BASELINE_NOT_APPROVED")
    return protocol, baseline, evidence


def doctor_report(*, require_free_ports: bool) -> dict[str, Any]:
    uv_path = _command_path("uv")
    node_path = _command_path("node")
    npm_path = _command_path(NPM_COMMAND)
    npx_path = _command_path(NPX_COMMAND)
    git_path = _command_path("git")
    node_version = _command_version([node_path, "--version"], "node")
    npm_version = _command_version([npm_path, "--version"], "npm")
    uv_version = _command_version([uv_path, "--version"], "uv")
    git_version = _command_version([git_path, "--version"], "git")
    if sys.version_info[:2] != (3, 12):
        raise DemoDeliveryError("DELIVERY_PYTHON_VERSION_UNSUPPORTED", field="python")
    if not _semver_at_least(node_version, (24, 19, 0)):
        raise DemoDeliveryError("DELIVERY_NODE_VERSION_UNSUPPORTED", field="node")
    if not _semver_at_least(npm_version, (11, 17, 0)):
        raise DemoDeliveryError("DELIVERY_NPM_VERSION_UNSUPPORTED", field="npm")
    for required in (
        REPOSITORY_ROOT / "uv.lock",
        FRONTEND_ROOT / "package-lock.json",
        FRONTEND_ROOT / "vite.config.ts",
    ):
        if not required.is_file():
            raise DemoDeliveryError("DELIVERY_LOCKFILE_MISSING", field=required.name)
    assets = load_demo_assets()
    profile = assets.profile("showcase")
    protocol, baseline, evidence = _verified_release_inputs()
    _runtime_write_check()
    ports = {
        str(BACKEND_PORT): _port_is_free(BACKEND_PORT),
        str(FRONTEND_PORT): _port_is_free(FRONTEND_PORT),
    }
    if require_free_ports and not all(ports.values()):
        occupied = next(port for port, free in ports.items() if not free)
        raise DemoDeliveryError("DELIVERY_PORT_IN_USE", field=occupied)
    checks = {
        "python_3_12": True,
        "node_minimum": True,
        "npm_minimum": True,
        "uv_available": True,
        "npx_available": bool(npx_path),
        "git_available": True,
        "lockfiles_present": True,
        "assets_valid": True,
        "formal_baseline_valid": True,
        "formal_evidence_valid": True,
        "runtime_writable": True,
        "ports_free_if_required": not require_free_ports or all(ports.values()),
    }
    return {
        "doctor_version": DOCTOR_VERSION,
        "status": "PASS",
        "message_zh": "演示交付环境检查通过",
        "environment_role": "LOCAL_DELIVERY_CANDIDATE",
        "target_site_status": "PENDING_FINAL_SITE_REPLAY",
        "runtime": {
            "python": platform.python_version(),
            "node": node_version,
            "npm": npm_version,
            "uv": uv_version,
            "git": git_version,
        },
        "profile": {
            "name": "showcase",
            "profile_id": profile.profile_id,
            "seed": profile.seed,
            "orders": profile.order_count,
            "operations": profile.operation_count,
            "resources": profile.resource_count,
            "initial_solve_seconds": profile.initial_solve_seconds,
            "replan_solve_seconds": profile.replan_solve_seconds,
        },
        "asset_digest": assets.asset_digest,
        "protocol_version": protocol["protocol_version"],
        "baseline_fingerprint": baseline["baseline_fingerprint"],
        "evidence_fingerprint": evidence["report_fingerprint"],
        "ports": ports,
        "checks": checks,
        "boundaries": {
            "loopback_only": True,
            "simulation_only": True,
            "synthetic_only": True,
            "production_capacity_claim": "NOT_ESTABLISHED",
            "production_sla_claim": "NOT_ESTABLISHED",
        },
    }


def process_creation_marker(pid: int) -> str | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class FileTime(ctypes.Structure):
            _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            created = FileTime()
            exited = FileTime()
            kernel = FileTime()
            user = FileTime()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return None
            value = (int(created.high) << 32) | int(created.low)
            return f"windows-filetime:{value}"
        finally:
            kernel32.CloseHandle(handle)
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        try:
            suffix = proc_stat.read_text(encoding="utf-8").rsplit(")", 1)[1]
            fields = suffix.split()
            return f"linux-start-ticks:{fields[19]}"
        except (OSError, IndexError):
            return None
    return None


def _process_identity(role: str, pid: int) -> ProcessIdentity:
    marker = process_creation_marker(pid)
    if marker is None:
        raise DemoDeliveryError("DELIVERY_PROCESS_IDENTITY_UNAVAILABLE", field=role)
    return ProcessIdentity(role=role, pid=pid, creation_marker=marker)


def _identity_state(identity: ProcessIdentity) -> str:
    marker = process_creation_marker(identity.pid)
    if marker is None:
        return "STOPPED"
    return "RUNNING" if marker == identity.creation_marker else "PID_REUSED"


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return int(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)


def _start_process(command: list[str], *, cwd: Path, log: Any) -> subprocess.Popen[str]:
    return subprocess.Popen(  # noqa: S603 - fixed local executables and arguments
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
        start_new_session=os.name != "nt",
    )


def _stop_identity(identity: ProcessIdentity) -> str:
    state = _identity_state(identity)
    if state == "STOPPED":
        return "ALREADY_STOPPED"
    if state != "RUNNING":
        raise DemoDeliveryError("DELIVERY_PROCESS_IDENTITY_MISMATCH", field=identity.role)
    if os.name == "nt":
        completed = subprocess.run(  # noqa: S603 - exact verified task-owned PID
            ["taskkill", "/PID", str(identity.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            creationflags=int(subprocess.CREATE_NO_WINDOW),
        )
        if completed.returncode not in {0, 128}:
            raise DemoDeliveryError("DELIVERY_PROCESS_STOP_FAILED", field=identity.role)
    else:
        try:
            os.killpg(identity.pid, signal.SIGTERM)
        except ProcessLookupError:
            return "ALREADY_STOPPED"
    deadline = monotonic() + 15
    while monotonic() < deadline:
        if process_creation_marker(identity.pid) is None:
            return "STOPPED"
        sleep(0.1)
    raise DemoDeliveryError("DELIVERY_PROCESS_STOP_TIMEOUT", field=identity.role)


def _stop_spawned_process(process: subprocess.Popen[str]) -> None:
    """Best-effort cleanup for a process spawned before identity capture completed."""

    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(  # noqa: S603 - PID comes from this exact Popen handle
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
                creationflags=int(subprocess.CREATE_NO_WINDOW),
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass


def _wait_url(url: str, *, timeout: float, expect_html_zh: bool = False) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:  # noqa: S310 - fixed loopback URLs
                payload = response.read().decode("utf-8", errors="replace")
                if response.status == 200 and (
                    not expect_html_zh or '<html lang="zh-CN">' in payload
                ):
                    return
        except (OSError, URLError):
            pass
        sleep(0.2)
    raise DemoDeliveryError("DELIVERY_SERVICE_START_TIMEOUT")


def _run_logged(command: list[str], *, cwd: Path, log: Any, field: str) -> None:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed local executables and args
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
            creationflags=(
                int(subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
            ),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DemoDeliveryError("DELIVERY_SETUP_COMMAND_FAILED", field=field) from error
    if completed.returncode != 0:
        raise DemoDeliveryError("DELIVERY_SETUP_COMMAND_FAILED", field=field)


def _state_document(state: LauncherState) -> dict[str, Any]:
    return {
        **asdict(state),
        "backend": asdict(state.backend),
        "frontend": asdict(state.frontend),
    }


def _write_state(path: Path, state: LauncherState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(_state_document(state), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parse_identity(raw: Any, role: str) -> ProcessIdentity:
    if not isinstance(raw, dict) or set(raw) != {"role", "pid", "creation_marker"}:
        raise DemoDeliveryError("DELIVERY_STATE_INVALID", field=role)
    if (
        raw.get("role") != role
        or isinstance(raw.get("pid"), bool)
        or not isinstance(raw.get("pid"), int)
        or not isinstance(raw.get("creation_marker"), str)
    ):
        raise DemoDeliveryError("DELIVERY_STATE_INVALID", field=role)
    return ProcessIdentity(
        role=role,
        pid=raw["pid"],
        creation_marker=raw["creation_marker"],
    )


def load_launcher_state(path: Path = LAUNCHER_STATE_PATH) -> LauncherState | None:
    if not path.exists():
        return None
    raw = _read_json(path)
    expected = {
        "state_version",
        "instance_id",
        "runtime_id",
        "started_at_utc",
        "source_head",
        "asset_digest",
        "baseline_fingerprint",
        "backend_url",
        "frontend_url",
        "log_directory",
        "backend",
        "frontend",
    }
    if set(raw) != expected or raw.get("state_version") != LAUNCHER_STATE_VERSION:
        raise DemoDeliveryError("DELIVERY_STATE_INVALID")
    text_fields = expected - {"backend", "frontend"}
    if any(not isinstance(raw.get(field), str) or not raw[field] for field in text_fields):
        raise DemoDeliveryError("DELIVERY_STATE_INVALID")
    try:
        resolve_named_runtime_root(DEMO_ROOT, cast(str, raw["runtime_id"]))
    except ValueError as error:
        raise DemoDeliveryError("DELIVERY_STATE_INVALID", field="runtime_id") from error
    return LauncherState(
        state_version=LAUNCHER_STATE_VERSION,
        instance_id=raw["instance_id"],
        runtime_id=raw["runtime_id"],
        started_at_utc=raw["started_at_utc"],
        source_head=raw["source_head"],
        asset_digest=raw["asset_digest"],
        baseline_fingerprint=raw["baseline_fingerprint"],
        backend_url=raw["backend_url"],
        frontend_url=raw["frontend_url"],
        log_directory=raw["log_directory"],
        backend=_parse_identity(raw["backend"], "backend"),
        frontend=_parse_identity(raw["frontend"], "frontend"),
    )


class DeliveryController:
    """Manage exactly the two local processes owned by one launcher state file."""

    def __init__(
        self,
        *,
        state_path: Path = LAUNCHER_STATE_PATH,
        launcher_root: Path = LAUNCHER_ROOT,
    ) -> None:
        resolved = state_path.resolve()
        resolved_launcher_root = launcher_root.resolve()
        if resolved.parent != resolved_launcher_root:
            raise DemoDeliveryError("DELIVERY_STATE_PATH_ESCAPE")
        self.state_path = resolved
        self.launcher_root = resolved_launcher_root

    def doctor(self, *, require_free_ports: bool = True) -> dict[str, Any]:
        return doctor_report(require_free_ports=require_free_ports)

    def status(self) -> dict[str, Any]:
        state = load_launcher_state(self.state_path)
        if state is None:
            return {
                "status_version": STATUS_VERSION,
                "status": "STOPPED",
                "message_zh": "演示服务未启动",
                "backend": "STOPPED",
                "frontend": "STOPPED",
            }
        backend = _identity_state(state.backend)
        frontend = _identity_state(state.frontend)
        aggregate = "RUNNING" if backend == frontend == "RUNNING" else "STALE"
        return {
            "status_version": STATUS_VERSION,
            "status": aggregate,
            "message_zh": (
                "演示服务正在运行"
                if aggregate == "RUNNING"
                else "启动状态已失效，请先安全停止"
            ),
            "instance_id": state.instance_id,
            "runtime_id": state.runtime_id,
            "backend": backend,
            "frontend": frontend,
            "backend_url": state.backend_url,
            "frontend_url": state.frontend_url,
            "started_at_utc": state.started_at_utc,
        }

    def start(
        self,
        *,
        runtime_id: str = DEFAULT_RUNTIME_ID,
        install: bool = True,
        build: bool = True,
    ) -> dict[str, Any]:
        existing = load_launcher_state(self.state_path)
        if existing is not None:
            status = self.status()
            if status["status"] == "RUNNING" and existing.runtime_id == runtime_id:
                return {**status, "replayed": True}
            if status["status"] == "RUNNING":
                raise DemoDeliveryError("DELIVERY_RUNTIME_CONFLICT", field="runtime_id")
            raise DemoDeliveryError("DELIVERY_STALE_STATE_PRESENT")
        try:
            resolve_named_runtime_root(DEMO_ROOT, runtime_id)
        except ValueError as error:
            raise DemoDeliveryError(
                "DELIVERY_RUNTIME_ID_INVALID", field="runtime_id"
            ) from error
        doctor = self.doctor(require_free_ports=True)
        instance_id = "delivery-" + uuid4().hex
        log_directory = self.launcher_root / "logs" / instance_id
        log_directory.mkdir(parents=True, exist_ok=False)
        setup_path = log_directory / "setup.log"
        backend_path = log_directory / "backend.log"
        frontend_path = log_directory / "frontend.log"
        backend_process: subprocess.Popen[str] | None = None
        frontend_process: subprocess.Popen[str] | None = None
        backend_identity: ProcessIdentity | None = None
        frontend_identity: ProcessIdentity | None = None
        started = monotonic()
        try:
            with setup_path.open("w", encoding="utf-8", newline="\n") as setup_log:
                if install:
                    _run_logged(
                        [_command_path(NPM_COMMAND), "ci", "--no-audit", "--no-fund"],
                        cwd=FRONTEND_ROOT,
                        log=setup_log,
                        field="npm-ci",
                    )
                if build:
                    _run_logged(
                        [_command_path(NPM_COMMAND), "run", "build"],
                        cwd=FRONTEND_ROOT,
                        log=setup_log,
                        field="frontend-build",
                    )
            if not (FRONTEND_ROOT / "dist" / "index.html").is_file():
                raise DemoDeliveryError("DELIVERY_FRONTEND_BUILD_MISSING")
            backend_log = backend_path.open("w", encoding="utf-8", newline="\n")
            try:
                backend_process = _start_process(
                    [
                        sys.executable,
                        str(DEMO_ROOT / "scripts" / "start_demo.py"),
                        "--runtime-id",
                        runtime_id,
                        "--port",
                        str(BACKEND_PORT),
                    ],
                    cwd=REPOSITORY_ROOT,
                    log=backend_log,
                )
            finally:
                backend_log.close()
            backend_identity = _process_identity("backend", backend_process.pid)
            _wait_url(f"{BACKEND_URL}/health/ready", timeout=45)
            frontend_log = frontend_path.open("w", encoding="utf-8", newline="\n")
            try:
                frontend_process = _start_process(
                    [
                        _command_path(NPM_COMMAND),
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
            finally:
                frontend_log.close()
            frontend_identity = _process_identity("frontend", frontend_process.pid)
            _wait_url(FRONTEND_URL, timeout=45, expect_html_zh=True)
            if _identity_state(backend_identity) != "RUNNING" or _identity_state(
                frontend_identity
            ) != "RUNNING":
                raise DemoDeliveryError("DELIVERY_PROCESS_EXITED_EARLY")
            state = LauncherState(
                state_version=LAUNCHER_STATE_VERSION,
                instance_id=instance_id,
                runtime_id=runtime_id,
                started_at_utc=utc_now(),
                source_head=_git_head(),
                asset_digest=doctor["asset_digest"],
                baseline_fingerprint=doctor["baseline_fingerprint"],
                backend_url=BACKEND_URL,
                frontend_url=FRONTEND_URL,
                log_directory=log_directory.relative_to(DEMO_ROOT).as_posix(),
                backend=backend_identity,
                frontend=frontend_identity,
            )
            _write_state(self.state_path, state)
            return {
                "status_version": STATUS_VERSION,
                "status": "RUNNING",
                "message_zh": "CNC 仿真演示已启动",
                "replayed": False,
                "runtime_id": runtime_id,
                "backend_url": BACKEND_URL,
                "frontend_url": FRONTEND_URL,
                "ready_seconds": monotonic() - started,
                "profile": doctor["profile"],
                "target_site_status": doctor["target_site_status"],
            }
        except BaseException:
            process_records = (
                (frontend_process, frontend_identity),
                (backend_process, backend_identity),
            )
            for process, identity in process_records:
                if identity is not None:
                    try:
                        _stop_identity(identity)
                    except DemoDeliveryError:
                        pass
                elif process is not None:
                    _stop_spawned_process(process)
            raise

    def stop(self) -> dict[str, Any]:
        state = load_launcher_state(self.state_path)
        if state is None:
            return {
                "status_version": STATUS_VERSION,
                "status": "STOPPED",
                "message_zh": "演示服务已经停止",
                "replayed": True,
            }
        results = {
            "frontend": _stop_identity(state.frontend),
            "backend": _stop_identity(state.backend),
        }
        self.state_path.unlink(missing_ok=True)
        return {
            "status_version": STATUS_VERSION,
            "status": "STOPPED",
            "message_zh": "CNC 仿真演示已安全停止",
            "replayed": False,
            "processes": results,
        }

    def health(self) -> dict[str, Any]:
        status = self.status()
        if status["status"] != "RUNNING":
            raise DemoDeliveryError("DELIVERY_NOT_RUNNING")
        _wait_url(f"{BACKEND_URL}/health/live", timeout=5)
        _wait_url(f"{BACKEND_URL}/health/ready", timeout=5)
        _wait_url(FRONTEND_URL, timeout=5, expect_html_zh=True)
        return {
            "status_version": STATUS_VERSION,
            "status": "PASS",
            "message_zh": "后端、数据库与中文前端均健康",
            "backend_live": True,
            "backend_ready": True,
            "frontend_zh_cn": True,
            "simulation_only": True,
        }

    def reset(self, *, profile_name: str = "showcase", timeout: float = 120) -> dict[str, Any]:
        self.health()
        assets = load_demo_assets()
        profile = assets.profile(profile_name)
        jar = CookieJar()
        opener = build_opener(HTTPCookieProcessor(jar))
        _request_json(opener, "POST", f"{BACKEND_URL}/api/demo/v1/session")
        accepted = _request_json(
            opener,
            "POST",
            f"{BACKEND_URL}/api/demo/v1/resets",
            document={
                "request_version": "cnc-demo-reset-request.v1",
                "profile_name": profile_name,
            },
            headers={"Idempotency-Key": f"demo-delivery-reset-{uuid4().hex}"},
        )
        job_id = accepted.get("job_id")
        if not isinstance(job_id, str):
            raise DemoDeliveryError("DELIVERY_RESET_RESPONSE_INVALID")
        job = _wait_job(opener, job_id, timeout=timeout)
        if job.get("status") != "SUCCEEDED" or not isinstance(job.get("result"), dict):
            raise DemoDeliveryError("DELIVERY_RESET_FAILED")
        bootstrap = _request_json(
            opener,
            "GET",
            f"{BACKEND_URL}/api/demo/v1/bootstrap",
        )
        manifest = bootstrap.get("scenario_manifest")
        if not isinstance(manifest, dict):
            raise DemoDeliveryError("DELIVERY_RESET_MANIFEST_MISSING")
        source_counts = manifest.get("source_counts")
        if not isinstance(source_counts, dict):
            raise DemoDeliveryError("DELIVERY_RESET_COUNTS_INVALID")
        expected = {
            "profile_name": profile_name,
            "scenario_id": profile.profile_id,
            "seed": profile.seed,
            "orders": profile.order_count,
            "operations": profile.operation_count,
            "resources": profile.resource_count,
        }
        observed = {
            "profile_name": manifest.get("profile_name"),
            "scenario_id": manifest.get("scenario_id"),
            "seed": manifest.get("seed"),
            "orders": source_counts.get("demand_orders"),
            "operations": source_counts.get("routing_operations"),
            "resources": source_counts.get("resources"),
        }
        if (
            observed != expected
            or bootstrap.get("story_state") != "INITIALIZED"
            or bootstrap.get("simulation_only") is not True
            or bootstrap.get("production_authority") is not False
        ):
            raise DemoDeliveryError("DELIVERY_RESET_COUNTS_INVALID")
        return {
            "reset_version": RESET_VERSION,
            "status": "PASS",
            "message_zh": "固定演示工厂已重置",
            "job_id": job_id,
            "run_id": manifest.get("run_id"),
            "story_state": bootstrap.get("story_state"),
            "counts": {
                "orders": expected["orders"],
                "operations": expected["operations"],
                "resources": expected["resources"],
            },
            "profile_name": profile_name,
            "profile_id": profile.profile_id,
            "seed": profile.seed,
            "simulation_only": True,
            "production_authority": False,
        }


def _request_json(
    opener: Any,
    method: str,
    url: str,
    *,
    document: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if document is not None:
        payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=request_headers, method=method)
    try:
        with opener.open(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as error:
        raise DemoDeliveryError("DELIVERY_API_REJECTED", field=str(error.code)) from error
    except (OSError, URLError) as error:
        raise DemoDeliveryError("DELIVERY_API_UNAVAILABLE") from error
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise DemoDeliveryError("DELIVERY_API_RESPONSE_INVALID") from error
    if not isinstance(parsed, dict):
        raise DemoDeliveryError("DELIVERY_API_RESPONSE_INVALID")
    return cast(dict[str, Any], parsed)


def _wait_job(opener: Any, job_id: str, *, timeout: float) -> dict[str, Any]:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        job = _request_json(
            opener,
            "GET",
            f"{BACKEND_URL}/api/demo/v1/jobs/{job_id}",
        )
        status = job.get("status")
        if status in _TERMINAL_JOB_STATES:
            return job
        sleep(0.2)
    raise DemoDeliveryError("DELIVERY_JOB_TIMEOUT")


def run_browser_smoke(*, headed: bool) -> dict[str, Any]:
    _command_path(NPX_COMMAND)
    session = f"d18-delivery-{os.getpid()}-{uuid4().hex[:8]}"
    base = [
        _command_path(NPX_COMMAND),
        "--yes",
        "--package",
        "@playwright/cli",
        "playwright-cli",
        f"-s={session}",
    ]
    output = ""
    try:
        arguments = [*base, "open", FRONTEND_URL]
        if headed:
            arguments.append("--headed")
        opened = _run_playwright(arguments, timeout=90)
        output += opened.stdout
        snapshot = _run_playwright([*base, "snapshot"], timeout=60)
        output += snapshot.stdout
        executed = _run_playwright(
            [
                *base,
                "--json",
                "--raw",
                "run-code",
                "--filename",
                str(DEMO_ROOT / "scripts" / "browser_delivery_demo_10.js"),
            ],
            timeout=120,
        )
        output += executed.stdout
        try:
            envelope = json.loads(executed.stdout)
            result = json.loads(envelope["result"])
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise DemoDeliveryError("DELIVERY_BROWSER_RESULT_INVALID") from error
        if not isinstance(result, dict) or result.get("status") != "PASS":
            raise DemoDeliveryError("DELIVERY_BROWSER_RESULT_INVALID")
        return {
            "smoke_version": SMOKE_VERSION,
            "status": "PASS",
            "message_zh": "真实浏览器中文演示首屏检查通过",
            **cast(dict[str, Any], result),
        }
    finally:
        try:
            closed = _run_playwright([*base, "close"], timeout=30, fail=False)
            output += closed.stdout
        except DemoDeliveryError:
            pass
        if "plantnexus_demo_session" in output.lower():
            raise DemoDeliveryError("DELIVERY_BROWSER_OUTPUT_UNSAFE")


def _run_playwright(
    command: list[str], *, timeout: float, fail: bool = True
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed Playwright CLI and script
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=(
                int(subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
            ),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DemoDeliveryError("DELIVERY_BROWSER_COMMAND_FAILED") from error
    if fail and completed.returncode != 0:
        output = completed.stdout + completed.stderr
        marker = re.search(r"D18_BROWSER_ASSERTION:[A-Z0-9_]+", output)
        raise DemoDeliveryError(
            marker.group(0) if marker is not None else "DELIVERY_BROWSER_COMMAND_FAILED"
        )
    return completed


__all__ = [
    "BACKEND_PORT",
    "BACKEND_URL",
    "DEFAULT_RUNTIME_ID",
    "DEMO_ROOT",
    "DOCTOR_VERSION",
    "DeliveryController",
    "DemoDeliveryError",
    "FRONTEND_PORT",
    "FRONTEND_URL",
    "LAUNCHER_ROOT",
    "LAUNCHER_STATE_PATH",
    "LauncherState",
    "ProcessIdentity",
    "canonical_fingerprint",
    "doctor_report",
    "load_launcher_state",
    "process_creation_marker",
    "run_browser_smoke",
    "utc_now",
    "verify_fingerprinted_document",
]
