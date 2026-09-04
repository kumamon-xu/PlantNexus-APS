"""D18 delivery controller and command-surface contract tests."""

from __future__ import annotations

from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from plantnexus_demo import delivery
from plantnexus_demo.delivery import (
    DeliveryController,
    DemoDeliveryError,
    LAUNCHER_STATE_VERSION,
    LauncherState,
    ProcessIdentity,
    canonical_fingerprint,
    doctor_report,
    load_launcher_state,
    process_creation_marker,
    verify_fingerprinted_document,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = REPOSITORY_ROOT / "demo"


def _launcher_state() -> LauncherState:
    return LauncherState(
        state_version=LAUNCHER_STATE_VERSION,
        instance_id="delivery-test-instance",
        runtime_id="delivery-test-runtime",
        started_at_utc="2026-09-04T00:00:00Z",
        source_head="a" * 40,
        asset_digest="b" * 64,
        baseline_fingerprint="sha256:" + "c" * 64,
        backend_url="http://127.0.0.1:8765",
        frontend_url="http://127.0.0.1:4174/demo/",
        log_directory="runtime/launcher/logs/delivery-test-instance",
        backend=ProcessIdentity("backend", 101, "created-backend"),
        frontend=ProcessIdentity("frontend", 102, "created-frontend"),
    )


def _state_document(state: LauncherState) -> dict[str, Any]:
    return {
        "state_version": state.state_version,
        "instance_id": state.instance_id,
        "runtime_id": state.runtime_id,
        "started_at_utc": state.started_at_utc,
        "source_head": state.source_head,
        "asset_digest": state.asset_digest,
        "baseline_fingerprint": state.baseline_fingerprint,
        "backend_url": state.backend_url,
        "frontend_url": state.frontend_url,
        "log_directory": state.log_directory,
        "backend": {
            "role": state.backend.role,
            "pid": state.backend.pid,
            "creation_marker": state.backend.creation_marker,
        },
        "frontend": {
            "role": state.frontend.role,
            "pid": state.frontend.pid,
            "creation_marker": state.frontend.creation_marker,
        },
    }


def test_delivery_doctor_verifies_frozen_showcase_inputs() -> None:
    """DEMO-DELIVERY-001/002/003: dependency, asset and baseline gate."""

    report = doctor_report(require_free_ports=False)

    assert report["status"] == "PASS"
    assert report["profile"] == {
        "name": "showcase",
        "profile_id": "CNC-DEMO-SHOWCASE",
        "seed": 20260902,
        "orders": 132,
        "operations": 610,
        "resources": 24,
        "initial_solve_seconds": 20,
        "replan_solve_seconds": 30,
    }
    assert all(report["checks"].values())
    assert report["boundaries"]["simulation_only"] is True


def test_fingerprinted_document_rejects_mutation(tmp_path: Path) -> None:
    """DEMO-DELIVERY-004: sealed delivery input is fail-closed."""

    path = tmp_path / "sealed.json"
    document: dict[str, Any] = {"status": "PASS", "count": 132}
    document["fingerprint"] = canonical_fingerprint(document)
    path.write_text(json.dumps(document), encoding="utf-8")
    assert verify_fingerprinted_document(path, "fingerprint")["count"] == 132

    document["count"] = 133
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(DemoDeliveryError, match="DELIVERY_FINGERPRINT_MISMATCH"):
        verify_fingerprinted_document(path, "fingerprint")


def test_current_process_creation_marker_is_stable() -> None:
    """DEMO-DELIVERY-005: PID is paired with an OS creation marker."""

    first = process_creation_marker(os.getpid())
    second = process_creation_marker(os.getpid())
    assert first is not None
    assert first == second


def test_launcher_state_is_strict_and_round_trips(tmp_path: Path) -> None:
    """DEMO-DELIVERY-006/007: strict launcher state and atomic writer."""

    launcher_root = tmp_path / "launcher"
    state_path = launcher_root / "state.json"
    controller = DeliveryController(
        state_path=state_path,
        launcher_root=launcher_root,
    )
    assert controller.status()["status"] == "STOPPED"

    delivery._write_state(state_path, _launcher_state())
    observed = load_launcher_state(state_path)
    assert observed is not None
    assert observed.runtime_id == "delivery-test-runtime"
    assert not list(launcher_root.glob("*.tmp"))

    malformed = _state_document(_launcher_state())
    malformed["unexpected"] = True
    state_path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(DemoDeliveryError, match="DELIVERY_STATE_INVALID"):
        load_launcher_state(state_path)

    escaped_runtime = _state_document(_launcher_state())
    escaped_runtime["runtime_id"] = "../outside"
    state_path.write_text(json.dumps(escaped_runtime), encoding="utf-8")
    with pytest.raises(DemoDeliveryError, match="DELIVERY_STATE_INVALID"):
        load_launcher_state(state_path)


def test_controller_rejects_state_path_escape(tmp_path: Path) -> None:
    """DEMO-DELIVERY-008: state cannot escape its exact launcher directory."""

    with pytest.raises(DemoDeliveryError, match="DELIVERY_STATE_PATH_ESCAPE"):
        DeliveryController(
            state_path=tmp_path / "outside" / "state.json",
            launcher_root=tmp_path / "launcher",
        )


def test_status_and_start_are_idempotent_for_matching_processes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEMO-DELIVERY-009/010: matching state is RUNNING and start replays."""

    launcher_root = tmp_path / "launcher"
    state_path = launcher_root / "state.json"
    delivery._write_state(state_path, _launcher_state())
    markers = {101: "created-backend", 102: "created-frontend"}
    monkeypatch.setattr(delivery, "process_creation_marker", markers.get)
    controller = DeliveryController(
        state_path=state_path,
        launcher_root=launcher_root,
    )

    assert controller.status()["status"] == "RUNNING"
    replay = controller.start(runtime_id="delivery-test-runtime")
    assert replay["status"] == "RUNNING"
    assert replay["replayed"] is True
    with pytest.raises(DemoDeliveryError, match="DELIVERY_RUNTIME_CONFLICT"):
        controller.start(runtime_id="different-runtime")


def test_invalid_runtime_id_is_sanitized() -> None:
    """DEMO-DELIVERY-010A: a path-like runtime id never escapes as ValueError."""

    with pytest.raises(DemoDeliveryError, match="DELIVERY_RUNTIME_ID_INVALID"):
        DeliveryController().start(runtime_id="../outside", install=False, build=False)


def test_stop_refuses_pid_reuse_and_preserves_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEMO-DELIVERY-011: PID reuse never kills an unknown process."""

    launcher_root = tmp_path / "launcher"
    state_path = launcher_root / "state.json"
    state = replace(
        _launcher_state(),
        frontend=ProcessIdentity("frontend", 102, "old-marker"),
    )
    delivery._write_state(state_path, state)
    markers = {101: "created-backend", 102: "new-marker"}
    monkeypatch.setattr(delivery, "process_creation_marker", markers.get)
    controller = DeliveryController(
        state_path=state_path,
        launcher_root=launcher_root,
    )

    with pytest.raises(DemoDeliveryError, match="DELIVERY_PROCESS_IDENTITY_MISMATCH"):
        controller.stop()
    assert state_path.exists()


def test_partial_start_cleans_exact_spawned_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEMO-DELIVERY-012: failure before identity capture cleans the Popen child."""

    class FakeProcess:
        pid = 99123

        def poll(self) -> None:
            return None

    frontend_root = tmp_path / "frontend"
    (frontend_root / "dist").mkdir(parents=True)
    (frontend_root / "dist" / "index.html").write_text("<html lang=\"zh-CN\">")
    launcher_root = tmp_path / "launcher"
    controller = DeliveryController(
        state_path=launcher_root / "state.json",
        launcher_root=launcher_root,
    )
    cleaned: list[int] = []
    monkeypatch.setattr(delivery, "FRONTEND_ROOT", frontend_root)
    monkeypatch.setattr(delivery, "resolve_named_runtime_root", lambda *_: tmp_path / "runtime")
    monkeypatch.setattr(
        controller,
        "doctor",
        lambda **_: {
            "asset_digest": "asset",
            "baseline_fingerprint": "baseline",
            "profile": {},
            "target_site_status": "PENDING_FINAL_SITE_REPLAY",
        },
    )
    monkeypatch.setattr(delivery, "_run_logged", lambda *_, **__: None)
    monkeypatch.setattr(delivery, "_start_process", lambda *_, **__: FakeProcess())
    monkeypatch.setattr(
        delivery,
        "_process_identity",
        lambda *_: (_ for _ in ()).throw(
            DemoDeliveryError("DELIVERY_PROCESS_IDENTITY_UNAVAILABLE")
        ),
    )
    monkeypatch.setattr(
        delivery,
        "_stop_spawned_process",
        lambda process: cleaned.append(process.pid),
    )

    with pytest.raises(DemoDeliveryError, match="DELIVERY_PROCESS_IDENTITY_UNAVAILABLE"):
        controller.start(install=False, build=False)
    assert cleaned == [99123]
    assert not controller.state_path.exists()


def test_delivery_cli_and_wrappers_expose_only_supported_commands() -> None:
    """DEMO-DELIVERY-013/014/015: CLI and both one-command wrappers stay bounded."""

    completed = subprocess.run(  # noqa: S603 - repository-owned script
        [sys.executable, str(DEMO_ROOT / "scripts" / "democtl.py"), "--help"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0
    for command in ("doctor", "start", "stop", "status", "health", "reset", "smoke"):
        assert command in completed.stdout
    assert "中文命令行入口" in completed.stdout

    powershell = (DEMO_ROOT / "demo.ps1").read_text(encoding="utf-8")
    portable = (DEMO_ROOT / "demo.sh").read_text(encoding="utf-8")
    assert "uv run python" in powershell
    assert "democtl.py" in powershell
    assert "uv run python" in portable
    assert "democtl.py" in portable
    assert "0.0.0.0" not in powershell + portable


def test_browser_smoke_contract_is_chinese_showcase_and_simulation_only() -> None:
    """DEMO-DELIVERY-BROWSER-001..008: static executable smoke contract."""

    script = (DEMO_ROOT / "scripts" / "browser_delivery_demo_10.js").read_text(
        encoding="utf-8"
    )
    for marker in (
        "工厂已初始化",
        "CNC 精密机加工演示",
        "仿真环境 · 非生产",
        "固定种子 20260902",
        'bootstrap.story_state === "INITIALIZED"',
        "bootstrap.simulation_only === true",
        "bootstrap.production_authority === false",
        "localSessionCookies.length === 1",
    ):
        assert marker in script
    assert '"snapshot"' in inspect.getsource(delivery.run_browser_smoke)
