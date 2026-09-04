from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from plantnexus_demo.composition import create_demo_app
from plantnexus_demo.security import DemoClientAccessPolicy
from plantnexus_demo.standalone import DemoSpaStaticFiles
from plantnexus_demo.standalone_settings import (
    DEFAULT_SETTINGS_DOCUMENT,
    STANDALONE_SETTINGS_VERSION,
    StandaloneConfigurationError,
    StandaloneSettings,
)
from plantnexus_demo.windows_launcher import (
    WindowsLauncherError,
    load_launcher_state,
    process_creation_marker,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _lan_document(**changes: object) -> dict[str, object]:
    document: dict[str, object] = {
        "settings_version": STANDALONE_SETTINGS_VERSION,
        "listen_host": "0.0.0.0",
        "access_port": 52174,
        "lan_mode": True,
        "allowed_networks": ["192.168.40.0/24", "fd12:3456::/48"],
        "open_browser": False,
    }
    document.update(changes)
    return document


def test_settings_default_and_private_lan_contract() -> None:
    local = StandaloneSettings.from_document(dict(DEFAULT_SETTINGS_DOCUMENT))
    assert local.local_url == "http://127.0.0.1:4174/demo/"
    assert local.lan_mode is False
    assert local.allowed_networks == ()
    assert local.fingerprint.startswith("sha256:")

    lan = StandaloneSettings.from_document(_lan_document())
    assert lan.local_url == "http://127.0.0.1:52174/demo/"
    assert [str(network) for network in lan.allowed_networks] == [
        "192.168.40.0/24",
        "fd12:3456::/48",
    ]
    assert lan.to_document() == _lan_document()


@pytest.mark.parametrize(
    ("changes", "code", "field"),
    [
        ({"extra": True}, "CONFIG_FIELDS_INVALID", "config"),
        ({"settings_version": "v0"}, "CONFIG_VERSION_UNSUPPORTED", "settings_version"),
        ({"access_port": True}, "CONFIG_VALUE_INVALID", "access_port"),
        ({"access_port": 0}, "CONFIG_VALUE_INVALID", "access_port"),
        ({"listen_host": "0.0.0.0"}, "CONFIG_LOOPBACK_REQUIRED", "listen_host"),
        ({"allowed_networks": ["192.168.1.0/24"]}, "CONFIG_LAN_DISABLED", "allowed_networks"),
    ],
)
def test_local_settings_fail_closed(
    changes: dict[str, object], code: str, field: str
) -> None:
    document = dict(DEFAULT_SETTINGS_DOCUMENT)
    document.update(changes)
    with pytest.raises(StandaloneConfigurationError) as captured:
        StandaloneSettings.from_document(document)
    assert captured.value.code == code
    assert captured.value.field == field


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"listen_host": "127.0.0.1"}, "CONFIG_LAN_BIND_INVALID"),
        ({"listen_host": "198.18.0.1"}, "CONFIG_LAN_BIND_INVALID"),
        ({"allowed_networks": []}, "CONFIG_LAN_NETWORKS_REQUIRED"),
        ({"allowed_networks": ["8.8.8.0/24"]}, "CONFIG_NETWORK_NOT_PRIVATE"),
        ({"allowed_networks": ["192.168.40.1/24"]}, "CONFIG_VALUE_INVALID"),
        ({"allowed_networks": ["192.168.40.0/24", "192.168.40.0/24"]}, "CONFIG_NETWORK_NOT_PRIVATE"),
    ],
)
def test_lan_settings_fail_closed(changes: dict[str, object], code: str) -> None:
    with pytest.raises(StandaloneConfigurationError) as captured:
        StandaloneSettings.from_document(_lan_document(**changes))
    assert captured.value.code == code


def test_client_policy_uses_socket_peer_and_ignores_proxy_headers(tmp_path: Path) -> None:
    application = create_demo_app(
        repository_root=REPOSITORY_ROOT,
        runtime_root=tmp_path / "local",
        auto_resume_queued=False,
    )
    with TestClient(application, client=("203.0.113.8", 443)) as client:
        denied = client.post(
            "/api/demo/v1/session",
            headers={
                "X-Forwarded-For": "127.0.0.1",
                "Forwarded": "for=127.0.0.1",
            },
        )
    assert denied.status_code == 403
    assert denied.json()["code"] == "AUTHORIZATION_DENIED"


def test_lan_policy_allows_only_configured_private_peer(tmp_path: Path) -> None:
    settings = StandaloneSettings.from_document(_lan_document())
    policy = DemoClientAccessPolicy(True, settings.allowed_networks)
    application = create_demo_app(
        repository_root=REPOSITORY_ROOT,
        runtime_root=tmp_path / "lan",
        auto_resume_queued=False,
        client_access_policy=policy,
    )
    with TestClient(application, client=("192.168.40.55", 443)) as client:
        session = client.post("/api/demo/v1/session")
        bootstrap = client.get("/api/demo/v1/bootstrap")
    assert session.status_code == 200
    assert bootstrap.status_code == 200
    assert bootstrap.json()["simulation_only"] is True

    with TestClient(application, client=("10.20.30.40", 443)) as client:
        denied = client.get("/health/live")
    assert denied.status_code == 403
    assert denied.json()["field"] == "client"


def test_static_frontend_has_safe_spa_fallback_and_cache_policy(tmp_path: Path) -> None:
    frontend = tmp_path / "dist"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    (frontend / "index.html").write_text(
        '<html lang="zh-CN"><body>精密机加工排产演示</body></html>',
        encoding="utf-8",
    )
    (assets / "app-123.js").write_text("console.log('ok')", encoding="utf-8")
    application = FastAPI()
    application.mount(
        "/demo", DemoSpaStaticFiles(directory=frontend, html=True), name="demo"
    )
    with TestClient(application) as client:
        home = client.get("/demo/")
        fallback = client.get("/demo/schedule/current")
        asset = client.get("/demo/assets/app-123.js")
        missing = client.get("/demo/assets/missing.js")
    assert home.status_code == 200
    assert home.headers["Cache-Control"] == "no-store"
    assert "精密机加工排产演示" in fallback.text
    assert asset.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert missing.status_code == 404


def test_package_settings_template_is_strict_and_chinese_launchers_exist() -> None:
    template_root = REPOSITORY_ROOT / "demo" / "package" / "windows"
    settings = StandaloneSettings.load(template_root / "config" / "demo-settings.json")
    assert settings.to_document() == DEFAULT_SETTINGS_DOCUMENT
    for name in ("启动演示.cmd", "停止演示.cmd", "查看状态.cmd", "配置演示.ps1", "README-启动说明.txt"):
        assert (template_root / name).is_file()
    assert "可信局域网" in (template_root / "README-启动说明.txt").read_text(
        encoding="utf-8"
    )


def test_launcher_state_rejects_unknown_fields_and_current_pid_has_marker(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"unexpected": True}), encoding="utf-8")
    with pytest.raises(WindowsLauncherError) as captured:
        load_launcher_state(path)
    assert captured.value.code == "LAUNCHER_STATE_INVALID"
    assert process_creation_marker(__import__("os").getpid()) is not None
