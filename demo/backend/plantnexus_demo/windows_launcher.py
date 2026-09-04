"""Safe command-line launcher embedded in the Windows standalone package."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from time import monotonic, sleep
from typing import Any, cast
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4
import webbrowser

import uvicorn

from .standalone import StandaloneLayout, StandaloneResourceError, create_standalone_app
from .standalone_settings import StandaloneConfigurationError, StandaloneSettings


WINDOWS_PACKAGE_VERSION = "0.2.0"
LAUNCHER_STATE_VERSION = "cnc-demo-windows-launcher-state.v1"
_START_TIMEOUT_SECONDS = 60.0


class WindowsLauncherError(RuntimeError):
    def __init__(self, code: str, *, field: str = "launcher") -> None:
        self.code = code
        self.field = field
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WindowsLauncherState:
    state_version: str
    pid: int
    creation_marker: str
    started_at_utc: str
    settings_fingerprint: str
    listen_host: str
    access_port: int
    lan_mode: bool
    local_url: str
    log_file: str


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def process_creation_marker(pid: int) -> str | None:
    if pid <= 0:
        return None
    if os.name == "nt":
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
            return f"linux-start-ticks:{suffix.split()[19]}"
        except (OSError, IndexError):
            return None
    return None


def _state_path(layout: StandaloneLayout) -> Path:
    return layout.install_root / "runtime" / "launcher-state.json"


def _write_state(path: Path, state: WindowsLauncherState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_launcher_state(path: Path) -> WindowsLauncherState | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WindowsLauncherError("LAUNCHER_STATE_INVALID", field="state") from error
    fields = set(WindowsLauncherState.__dataclass_fields__)
    if not isinstance(raw, dict) or set(raw) != fields:
        raise WindowsLauncherError("LAUNCHER_STATE_INVALID", field="state")
    document = cast(dict[str, Any], raw)
    if (
        document.get("state_version") != LAUNCHER_STATE_VERSION
        or isinstance(document.get("pid"), bool)
        or not isinstance(document.get("pid"), int)
        or not isinstance(document.get("access_port"), int)
        or not isinstance(document.get("lan_mode"), bool)
        or any(
            not isinstance(document.get(field), str) or not document[field]
            for field in (
                "creation_marker",
                "started_at_utc",
                "settings_fingerprint",
                "listen_host",
                "local_url",
                "log_file",
            )
        )
    ):
        raise WindowsLauncherError("LAUNCHER_STATE_INVALID", field="state")
    return WindowsLauncherState(**document)


def _identity_status(state: WindowsLauncherState) -> str:
    marker = process_creation_marker(state.pid)
    if marker is None:
        return "STOPPED"
    return "RUNNING" if marker == state.creation_marker else "PID_REUSED"


def _wait_ready(url: str, *, timeout: float = _START_TIMEOUT_SECONDS) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:  # noqa: S310 - validated loopback URL
                if response.status == 200:
                    return
        except (OSError, URLError):
            pass
        sleep(0.2)
    raise WindowsLauncherError("SERVICE_START_TIMEOUT", field="service")


def _port_is_free(settings: StandaloneSettings) -> bool:
    family = socket.AF_INET6 if ":" in settings.listen_host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((settings.listen_host, settings.access_port))
        except OSError:
            return False
    return True


def _child_command(layout: StandaloneLayout) -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve()), "serve"]
    entry = layout.resource_root / "demo" / "scripts" / "windows_demo_entry.py"
    return [str(Path(sys.executable).resolve()), str(entry), "serve"]


def _spawn_server(
    layout: StandaloneLayout,
    *,
    log_stream: Any,
) -> subprocess.Popen[bytes]:
    flags = 0
    if os.name == "nt":
        flags = int(
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
        )
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    return subprocess.Popen(  # noqa: S603 - fixed executable and fixed subcommand
        _child_command(layout),
        cwd=layout.install_root,
        stdin=subprocess.DEVNULL,
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        env=environment,
        creationflags=flags,
        start_new_session=os.name != "nt",
    )


def _taskkill_path() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = Path(system_root) / "System32" / "taskkill.exe"
    return str(candidate if candidate.is_file() else Path("taskkill.exe"))


def _stop_verified(state: WindowsLauncherState) -> str:
    status = _identity_status(state)
    if status == "STOPPED":
        return "ALREADY_STOPPED"
    if status != "RUNNING":
        raise WindowsLauncherError("PROCESS_IDENTITY_MISMATCH", field="pid")
    if os.name == "nt":
        completed = subprocess.run(  # noqa: S603 - exact PID and creation marker verified
            [_taskkill_path(), "/PID", str(state.pid), "/T", "/F"],
            capture_output=True,
            timeout=30,
            check=False,
            creationflags=int(subprocess.CREATE_NO_WINDOW),
        )
        if completed.returncode not in {0, 128}:
            raise WindowsLauncherError("PROCESS_STOP_FAILED", field="pid")
    else:
        try:
            os.killpg(state.pid, signal.SIGTERM)
        except ProcessLookupError:
            return "ALREADY_STOPPED"
    deadline = monotonic() + 15
    while monotonic() < deadline:
        if process_creation_marker(state.pid) is None:
            return "STOPPED"
        sleep(0.1)
    raise WindowsLauncherError("PROCESS_STOP_TIMEOUT", field="pid")


def start(layout: StandaloneLayout, settings: StandaloneSettings) -> dict[str, object]:
    layout.validate()
    state_path = _state_path(layout)
    existing = load_launcher_state(state_path)
    if existing is not None:
        status = _identity_status(existing)
        if status == "RUNNING":
            raise WindowsLauncherError("SERVICE_ALREADY_RUNNING", field="state")
        if status == "PID_REUSED":
            raise WindowsLauncherError("PROCESS_IDENTITY_MISMATCH", field="state")
        state_path.unlink()
    if not _port_is_free(settings):
        raise WindowsLauncherError("PORT_IN_USE", field="access_port")

    log_directory = layout.install_root / "runtime" / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f"server-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.log"
    process: subprocess.Popen[bytes] | None = None
    with log_path.open("ab", buffering=0) as log_stream:
        try:
            process = _spawn_server(layout, log_stream=log_stream)
            marker = process_creation_marker(process.pid)
            if marker is None:
                raise WindowsLauncherError(
                    "PROCESS_IDENTITY_UNAVAILABLE", field="pid"
                )
            _wait_ready(
                settings.local_url.removesuffix("/demo/") + "/health/ready"
            )
            state = WindowsLauncherState(
                state_version=LAUNCHER_STATE_VERSION,
                pid=process.pid,
                creation_marker=marker,
                started_at_utc=_utc_now(),
                settings_fingerprint=settings.fingerprint,
                listen_host=settings.listen_host,
                access_port=settings.access_port,
                lan_mode=settings.lan_mode,
                local_url=settings.local_url,
                log_file=str(log_path.relative_to(layout.install_root)).replace("\\", "/"),
            )
            _write_state(state_path, state)
        except BaseException:
            if process is not None and process.poll() is None:
                temporary = WindowsLauncherState(
                    state_version=LAUNCHER_STATE_VERSION,
                    pid=process.pid,
                    creation_marker=process_creation_marker(process.pid) or "unavailable",
                    started_at_utc=_utc_now(),
                    settings_fingerprint=settings.fingerprint,
                    listen_host=settings.listen_host,
                    access_port=settings.access_port,
                    lan_mode=settings.lan_mode,
                    local_url=settings.local_url,
                    log_file=str(log_path),
                )
                if temporary.creation_marker != "unavailable":
                    try:
                        _stop_verified(temporary)
                    except WindowsLauncherError:
                        pass
            raise
    if settings.open_browser:
        webbrowser.open(settings.local_url)
    return {
        "status": "RUNNING",
        "message_zh": "精密机加工排产演示已启动",
        "url": settings.local_url,
        "port": settings.access_port,
        "lan_mode": settings.lan_mode,
        "pid": state.pid,
    }


def stop(layout: StandaloneLayout) -> dict[str, object]:
    path = _state_path(layout)
    state = load_launcher_state(path)
    if state is None:
        return {"status": "STOPPED", "message_zh": "演示服务未运行"}
    outcome = _stop_verified(state)
    path.unlink(missing_ok=True)
    return {"status": "STOPPED", "message_zh": "演示服务已安全停止", "outcome": outcome}


def status(layout: StandaloneLayout) -> dict[str, object]:
    state = load_launcher_state(_state_path(layout))
    if state is None:
        return {"status": "STOPPED", "message_zh": "演示服务未运行"}
    identity = _identity_status(state)
    if identity != "RUNNING":
        return {
            "status": identity,
            "message_zh": "演示进程状态需要处理",
            "pid": state.pid,
        }
    try:
        _wait_ready(
            state.local_url.removesuffix("/demo/") + "/health/ready", timeout=3
        )
    except WindowsLauncherError:
        health = "NOT_READY"
    else:
        health = "READY"
    return {
        "status": "RUNNING",
        "health": health,
        "message_zh": "演示服务正在运行",
        "url": state.local_url,
        "port": state.access_port,
        "lan_mode": state.lan_mode,
        "pid": state.pid,
    }


_ERROR_MESSAGES_ZH = {
    "CONFIG_READ_FAILED": "无法读取配置文件",
    "CONFIG_FIELDS_INVALID": "配置字段不完整或包含未知字段",
    "CONFIG_VERSION_UNSUPPORTED": "配置版本不受支持",
    "CONFIG_VALUE_INVALID": "配置值无效",
    "CONFIG_NETWORK_NOT_PRIVATE": "允许网段必须是规范的私有局域网 CIDR",
    "CONFIG_LAN_BIND_INVALID": "局域网模式必须监听 0.0.0.0、:: 或本机私有地址",
    "CONFIG_LAN_NETWORKS_REQUIRED": "局域网模式至少需要一个允许网段",
    "CONFIG_LOOPBACK_REQUIRED": "本机模式只能监听回环地址",
    "CONFIG_LAN_DISABLED": "本机模式不得配置远端允许网段",
    "PACKAGE_RESOURCE_MISSING": "发布包资源不完整",
    "PACKAGE_RUNTIME_NOT_WRITABLE": "发布包 runtime 目录不可写",
    "LAUNCHER_STATE_INVALID": "启动状态文件损坏，请勿手工结束未知进程",
    "SERVICE_ALREADY_RUNNING": "演示服务已经运行",
    "PROCESS_IDENTITY_MISMATCH": "进程身份不匹配，已拒绝终止",
    "PROCESS_IDENTITY_UNAVAILABLE": "无法核对演示进程身份",
    "PROCESS_STOP_FAILED": "演示进程停止失败",
    "PROCESS_STOP_TIMEOUT": "等待演示进程停止超时",
    "PORT_IN_USE": "配置端口已被占用",
    "SERVICE_START_TIMEOUT": "演示服务启动超时，请查看 runtime/logs",
}


def _print_result(result: dict[str, object]) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="PlantNexus CNC 中文演示独立版")
    parser.add_argument("command", choices=("start", "serve", "stop", "status", "version"), nargs="?", default="start")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="启动后不自动打开本机浏览器",
    )
    arguments = parser.parse_args(argv)
    layout = StandaloneLayout.discover()
    try:
        if arguments.command == "version":
            _print_result({"status": "PASS", "version": WINDOWS_PACKAGE_VERSION})
            return 0
        if arguments.command == "stop":
            _print_result(stop(layout))
            return 0
        if arguments.command == "status":
            _print_result(status(layout))
            return 0
        settings = StandaloneSettings.load(layout.config_path)
        if arguments.command == "serve":
            layout.validate()
            application = create_standalone_app(layout=layout, settings=settings)
            uvicorn.run(
                application,
                host=settings.listen_host,
                port=settings.access_port,
                log_level="info",
                access_log=False,
                proxy_headers=False,
                server_header=False,
            )
            return 0
        if arguments.no_browser:
            settings = replace(settings, open_browser=False)
        _print_result(start(layout, settings))
        return 0
    except (StandaloneConfigurationError, StandaloneResourceError, WindowsLauncherError) as error:
        code = error.code
        _print_result(
            {
                "status": "FAIL",
                "code": code,
                "field": error.field,
                "message_zh": _ERROR_MESSAGES_ZH.get(code, "演示服务操作失败"),
            }
        )
        return 2


__all__ = [
    "LAUNCHER_STATE_VERSION",
    "WINDOWS_PACKAGE_VERSION",
    "WindowsLauncherError",
    "WindowsLauncherState",
    "load_launcher_state",
    "main",
    "process_creation_marker",
    "start",
    "status",
    "stop",
]
