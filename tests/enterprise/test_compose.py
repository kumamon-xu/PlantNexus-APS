from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest
import yaml

from infra.enterprise.bootstrap import services, preflight
from infra.enterprise.compose import control
from tests.enterprise.configuration_fixtures import write_env

HERE = Path(__file__).resolve().parents[2] / "infra/enterprise/compose"
IMAGE = "sha256:" + "1" * 64
SHA = "2" * 40
TAG = "plantnexus-aps-runtime:0.1.0-" + SHA


@pytest.fixture
def approved(monkeypatch):
    report = {
        "status": "PASS",
        "issues": [],
        "candidate": False,
        "dirty": False,
        "image_id": IMAGE,
        "tag": TAG,
        "code_commit": SHA,
    }
    image = {
        "Id": IMAGE,
        "Os": "linux",
        "Architecture": "amd64",
        "RepoDigests": ["registry.invalid/aps@sha256:" + "3" * 64],
        "Config": {
            "User": "10001:10001",
            "Labels": {
                "org.opencontainers.image.revision": SHA,
                "io.plantnexus.aps.source-runtime-revision": control.SOURCE,
            },
        },
    }
    spy = Mock(return_value=image)
    monkeypatch.setattr(control, "inspect_image", spy)
    return report, image, spy


def test_offline_id_tag_and_registry_digest_mapping(approved):
    report, image, spy = approved
    for reference in (
        IMAGE,
        TAG,
        image["RepoDigests"][0],
        "registry.invalid/aps:0.1.0@sha256:" + "3" * 64,
    ):
        assert control.image_identity(report, reference) == IMAGE
    assert spy.call_count == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("candidate", True),
        ("dirty", True),
        ("status", "FAIL"),
        ("issues", ["unresolved"]),
        ("image_id", "latest"),
    ],
)
def test_unapproved_evidence_fails_before_docker(approved, field, value):
    report, _, spy = approved
    report[field] = value
    with pytest.raises(control.DeploymentError, match="IMAGE_EVIDENCE_INVALID"):
        control.image_identity(report, TAG)
    spy.assert_not_called()


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("Id", "sha256:" + "0" * 64, "IMAGE_ID_MISMATCH"),
        ("Os", "windows", "IMAGE_PLATFORM_MISMATCH"),
        ("Architecture", "arm64", "IMAGE_PLATFORM_MISMATCH"),
    ],
)
def test_wrong_loaded_image_refused(approved, field, value, code):
    report, image, _ = approved
    image[field] = value
    with pytest.raises(control.DeploymentError, match=code):
        control.image_identity(report, TAG)


def test_wrong_label_and_unmapped_registry_refused(approved):
    report, image, _ = approved
    with pytest.raises(control.DeploymentError, match="REGISTRY_MAPPING_MISMATCH"):
        control.image_identity(report, "wrong.invalid/aps@sha256:" + "3" * 64)
    image["Config"]["Labels"]["org.opencontainers.image.revision"] = "0" * 40
    with pytest.raises(control.DeploymentError, match="IMAGE_LABEL_MISMATCH"):
        control.image_identity(report, TAG)


@pytest.mark.parametrize(
    "reference", ["aps:latest", "aps:1.0.0", "sha256:bad", "$(echo secret)"]
)
def test_mutable_or_shell_reference_rejected_without_inspect(approved, reference):
    report, _, spy = approved
    with pytest.raises(control.DeploymentError, match="IMMUTABLE_REFERENCE_REQUIRED"):
        control.image_identity(report, reference)
    spy.assert_not_called()


def test_compose_gates_ports_mounts_and_no_build():
    base = yaml.safe_load(
        (HERE / "docker-compose.enterprise.yml").read_text(encoding="utf-8")
    )
    standalone = yaml.safe_load(
        (HERE / "docker-compose.standalone.yml").read_text(encoding="utf-8")
    )
    locked = json.loads((HERE / "dependencies.v1.json").read_text(encoding="utf-8"))[
        "images"
    ]
    assert set(base["services"]) == control.ROLES
    for role, service in base["services"].items():
        assert service["image"] == base["services"]["migrate"]["image"]
        assert service["pull_policy"] == "never" and "build" not in service
        assert service["read_only"] and service["cap_drop"] == ["ALL"]
        assert not service.get("environment") and not service.get("env_file")
        for mount in service["volumes"]:
            if isinstance(mount, dict):
                assert mount["read_only"] and not mount["bind"]["create_host_path"]
        if role in {"api", "worker"}:
            assert (
                service["depends_on"]["migrate"]["condition"]
                == "service_completed_successfully"
            )
    assert (
        base["services"]["api"]["depends_on"]["worker"]["condition"]
        == "service_healthy"
    )
    assert base["services"]["api"]["ports"][0].startswith("127.0.0.1:")
    validator = base["services"]["validator"]
    assert validator["network_mode"] == "none" and validator["profiles"] == [
        "validator"
    ]
    assert "networks" not in validator and all(
        v["read_only"] for v in validator["volumes"]
    )
    for service, reference in locked.items():
        assert standalone["services"][service]["image"] == reference
        assert "@sha256:" in reference and ":latest" not in reference
        assert standalone["services"][service]["pull_policy"] == "never"
        assert (
            standalone["services"]["migrate"]["depends_on"][service]["condition"]
            == "service_healthy"
        )
        assert "ports" not in standalone["services"][service]
    assert standalone["networks"]["runtime"]["internal"] is True
    assert {"postgres_data", "redis_data"} <= standalone["volumes"].keys()


@pytest.mark.parametrize(
    "role", ["migrate", "api", "worker", "validator", "health-api", "health-worker"]
)
def test_bad_preflight_blocks_every_role_without_dependency_access(
    monkeypatch, role, capsys
):
    def refuse(_):
        raise preflight.BootstrapError("MISSING_OR_PLACEHOLDER", "DB_HOST")

    monkeypatch.setattr(services, "prepare", refuse)
    spy = Mock(side_effect=AssertionError("dependency accessed"))
    monkeypatch.setattr(services, "database", spy)
    monkeypatch.setattr(services, "launch", spy)
    assert services.main([role]) == 1
    spy.assert_not_called()
    assert json.loads(capsys.readouterr().out)["code"] == "MISSING_OR_PLACEHOLDER"


@pytest.mark.parametrize(
    "field,value",
    [
        ("API_BIND", "127.0.0.1"),
        ("API_PORT", "443"),
        ("DATA_VOLUME", "/unmounted"),
        ("BACKUP_VOLUME", "/wrong"),
    ],
)
def test_compose_mount_port_layout_not_silently_ignored(field, value):
    env = {
        "API_BIND": "0.0.0.0",
        "API_PORT": "8000",
        "DATA_VOLUME": "/var/lib/plantnexus",
        "BACKUP_VOLUME": "/var/backups/plantnexus",
    }
    env[field] = value
    with pytest.raises(preflight.BootstrapError, match="COMPOSE_LAYOUT_INVALID"):
        services.deployment_layout(preflight.Prepared(env, None, None, "", ()))


@pytest.mark.parametrize("revisions", [[], ["old_head"], [services.HEAD, "other"]])
def test_wrong_database_head_blocks_before_redis(configured, monkeypatch, revisions):
    directory, env = configured
    p = preflight.prepare(write_env(directory, env))
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = 1
    connection.execute.return_value.scalars.return_value.all.return_value = revisions
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(services, "database", lambda _: engine)
    import redis

    spy = Mock(side_effect=AssertionError("Redis accessed before migration gate"))
    monkeypatch.setattr(redis.Redis, "from_url", spy)
    with pytest.raises(preflight.BootstrapError, match="MIGRATION_HEAD_MISMATCH"):
        services.dependencies(p)
    spy.assert_not_called()
    engine.dispose.assert_called_once()


@pytest.mark.parametrize(
    "reply",
    [
        [],
        [{"other-worker": {"ok": "pong"}}],
        [{"aps@aps-worker": {"ok": "not-pong"}}],
        [{"aps@aps-worker": {"ok": "pong"}}, {"aps@aps-worker": {"ok": "pong"}}],
    ],
)
def test_worker_health_requires_exact_named_pong(configured, monkeypatch, reply):
    directory, env = configured
    p = preflight.prepare(write_env(directory, env))
    import celery

    app = Mock()
    app.control.ping.return_value = reply
    monkeypatch.setattr(celery, "Celery", lambda *a, **kw: app)
    with pytest.raises(preflight.BootstrapError, match="NAMED_WORKER_UNREADY"):
        services.worker_health(p)
    app.control.ping.assert_called_once_with(destination=["aps@aps-worker"], timeout=3)
    app.close.assert_called_once()


def test_running_target_requires_controlled_stop(
    approved, tmp_path, monkeypatch, capsys
):
    report, _, _ = approved
    path = tmp_path / "image.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(control, "render", lambda **kw: {"services": {}})
    spy = Mock(return_value=SimpleNamespace(returncode=0, stdout=b"api\nworker\n"))
    monkeypatch.setattr(control, "execute", spy)
    assert (
        control.main(
            [
                "up",
                "--mode",
                "enterprise",
                "--image-report",
                str(path),
                "--reference",
                TAG,
                "--config-dir",
                str(tmp_path),
                "--secrets-dir",
                str(tmp_path),
                "--project",
                "p825-unit",
                "--port",
                "18000",
            ]
        )
        == 1
    )
    assert spy.call_count == 1
    assert (
        json.loads(capsys.readouterr().out)["code"]
        == "RUNNING_TARGET_REQUIRES_CONTROLLED_STOP"
    )


def test_ci_dual_mode_replay_is_required_and_sealed():
    workflow = yaml.safe_load(
        (HERE.parents[2] / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    for job in ("full_validation", "solver_validation"):
        steps = workflow["jobs"][job]["steps"]
        steps = [
            s
            for s in steps
            if "infra/enterprise/compose/verify_container.py" in s.get("run", "")
        ]
        assert len(steps) == 1
        assert not steps[0].get("continue-on-error") and not steps[0].get("if")
        assert "ci-enterprise-image-compose.json" in steps[0]["run"]
        assert (
            "--image-report build/validation/ci-enterprise-image.json"
            in steps[0]["run"]
        )


@pytest.mark.parametrize(
    "stage,code",
    [("preflight", "CONFIGURATION_PREFLIGHT_FAILED"), ("up", "COMPOSE_START_FAILED")],
)
def test_control_nonzero_preflight_or_start_never_reports_pass(
    approved, tmp_path, monkeypatch, capsys, stage, code
):
    report, _, _ = approved
    path = tmp_path / "image.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(control, "render", lambda **kw: {"services": {}})
    calls = []

    def execute(command, **kw):
        calls.append(command)
        failed = "preflight" in command if stage == "preflight" else "up" in command
        return SimpleNamespace(returncode=int(failed), stdout=b"")

    monkeypatch.setattr(control, "execute", execute)
    assert (
        control.main(
            [
                "up",
                "--mode",
                "enterprise",
                "--image-report",
                str(path),
                "--reference",
                TAG,
                "--config-dir",
                str(tmp_path),
                "--secrets-dir",
                str(tmp_path),
                "--project",
                "p825-unit",
                "--port",
                "18000",
            ]
        )
        == 1
    )
    assert len(calls) == (2 if stage == "preflight" else 3)
    assert json.loads(capsys.readouterr().out)["code"] == code


@pytest.mark.parametrize(
    "name,value",
    [
        ("DB_HOST", "external.invalid"),
        ("REDIS_PORT", "6380"),
        ("BROKER_HOST", "external.invalid"),
        ("RESULT_HOST", "external.invalid"),
    ],
)
def test_standalone_wrong_endpoint_stops_before_compose(
    tmp_path, monkeypatch, name, value
):
    from infra.enterprise.compose.verify_container import fixture

    config, secrets, values = fixture(tmp_path)
    values[name] = value
    write_env(config, values)
    monkeypatch.setattr(control, "image_identity", lambda *a: IMAGE)
    spy = Mock(side_effect=AssertionError("Compose invoked"))
    monkeypatch.setattr(control, "execute", spy)
    with pytest.raises(control.DeploymentError, match="STANDALONE_ENDPOINT_MISMATCH"):
        control.render(
            report={},
            reference=IMAGE,
            mode="standalone",
            config_dir=config,
            secrets_dir=secrets,
            project="p825-unit",
            port=18000,
        )
    spy.assert_not_called()


@pytest.mark.parametrize("name", ["broker_user", "result_password"])
def test_standalone_unequal_acl_rejected_without_secret_in_error(
    tmp_path, monkeypatch, name
):
    from infra.enterprise.compose.verify_container import fixture

    config, secrets, _ = fixture(tmp_path)
    (secrets / name).write_text("mismatched-synthetic-value", encoding="utf-8")
    monkeypatch.setattr(control, "image_identity", lambda *a: IMAGE)
    spy = Mock(side_effect=AssertionError("Compose invoked"))
    monkeypatch.setattr(control, "execute", spy)
    with pytest.raises(control.DeploymentError, match="^STANDALONE_ACL_MISMATCH$"):
        control.render(
            report={},
            reference=IMAGE,
            mode="standalone",
            config_dir=config,
            secrets_dir=secrets,
            project="p825-unit",
            port=18000,
        )
    spy.assert_not_called()
