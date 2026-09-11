from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from infra.enterprise.bootstrap import preflight, run
from tests.enterprise.configuration_fixtures import add_extension, write_env


def test_complete_configuration_and_ambient_settings_are_not_authority(
    configured, monkeypatch
):
    directory, env = configured
    monkeypatch.setenv("PLANTNEXUS_RUNTIME_EXTENSION_ARTIFACT_PROVIDER", "evil:factory")
    value = preflight.prepare(write_env(directory, env))
    assert value.settings.runtime_extension_artifact_provider is None
    assert value.settings.code_commit == preflight.SOURCE_SHA
    assert value.report()["production_ready"] is False
    provider = run.LocalTestIdentity(value)
    assert provider.verify("wrong") is None
    identity = provider.verify(value.token)
    assert identity is not None and identity.subject_ref == env["IDENTITY_SUBJECT"]


@pytest.mark.parametrize("name", sorted(preflight.REQUIRED))
def test_each_required_field_missing_stops_before_launch(
    configured, monkeypatch, name, capsys
):
    directory, env = configured
    del env[name]
    spy = Mock(side_effect=AssertionError("business entry must not run"))
    monkeypatch.setattr(run, "launch", spy)
    assert run.main(["--config", str(write_env(directory, env))]) == 1
    spy.assert_not_called()
    result = json.loads(capsys.readouterr().out)
    assert result["field"] == name


@pytest.mark.parametrize(
    "name,value",
    [
        ("DB_HOST", ""),
        ("DB_PORT", "__REQUIRED__"),
        ("ENVIRONMENT", "production"),
        ("DATA_PLANE", "production"),
        ("KIT_VERSION", "latest"),
        ("KIT_FINGERPRINT", "sha256:" + "0" * 64),
        ("RUNTIME_SOURCE_SHA", "0" * 40),
        ("IDENTITY_PROVIDER", "OIDC"),
        ("BROKER_INDEX", "0"),
        ("LEASE_SECONDS", "1"),
        ("WORKER_CONCURRENCY", "0"),
        ("CPU_LIMIT", "NaN"),
        ("DB_HOST", "host/secret"),
        ("EXTENSION_MODE", "local"),
    ],
)
def test_invalid_config_never_constructs_database_client(
    configured, monkeypatch, name, value
):
    directory, env = configured
    env[name] = value
    import app.infrastructure.database as database

    spy = Mock(side_effect=AssertionError("connection created"))
    monkeypatch.setattr(database, "create_database_client", spy)
    with pytest.raises(preflight.BootstrapError):
        preflight.prepare(write_env(directory, env))
    spy.assert_not_called()


def test_strict_configuration_and_policy(configured):
    directory, env = configured
    raw = write_env(directory, env).read_bytes()
    for suffix in (b"DB_HOST=other\n", b"UNKNOWN=private\n", b"export DB_HOST=other\n"):
        with pytest.raises(preflight.BootstrapError):
            preflight.parse_env(raw + suffix)
    with pytest.raises(preflight.BootstrapError):
        preflight.strict_json(b'{"a":1,"a":2}', "configuration")
    policy = Path(env["AUTHORIZATION_POLICY_FILE"])
    data = json.loads(policy.read_text(encoding="utf-8"))
    data["audience"] = "other"
    policy.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(preflight.BootstrapError):
        preflight.prepare(directory / "deployment.env")


def test_empty_extension_mode_rejects_partial_identity(configured):
    directory, env = configured
    env["EXTENSION_KEY_ID"] = "extra.key"
    with pytest.raises(preflight.BootstrapError, match="ATOMIC_GROUP"):
        preflight.prepare(write_env(directory, env))


def test_template_and_matrix_cover_exact_fields():
    root = Path(__file__).resolve().parents[2] / "infra/enterprise/config"
    matrix = json.loads(
        (root / "configuration-matrix.v1.json").read_text(encoding="utf-8")
    )
    assert {row["name"] for row in matrix["fields"]} == preflight.FIELDS
    template = (root / ".env.example").read_bytes()
    names = {
        line.split(b"=", 1)[0].decode()
        for line in template.splitlines()
        if line and not line.startswith(b"#")
    }
    assert names == preflight.FIELDS
    with pytest.raises(preflight.BootstrapError):
        preflight.parse_env(template)


def test_shared_ci_requires_real_container_check_and_sealed_report():
    import yaml

    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
    )
    for job in ("solver_validation", "full_validation"):
        steps = workflow["jobs"][job]["steps"]
        step = next(
            s
            for s in steps
            if s.get("name") == "Build and verify immutable enterprise Runtime image"
        )
        assert (
            "uv run python infra/enterprise/bootstrap/verify_container.py"
            in step["run"]
        )
        assert (
            "--report build/validation/ci-enterprise-image-bootstrap.json"
            in step["run"]
        )
        assert "if" not in step and not step.get("continue-on-error")
        seal = next(s for s in steps if s.get("name") == f"Seal {job} evidence")
        assert (
            "ci-enterprise-image*.json" in seal["run"]
            or "build/validation/*.json" in seal["run"]
        )


@pytest.mark.parametrize(
    "mutation", [None, "wheel", "signature", "kit", "set", "configuration"]
)
def test_local_extension_uses_verified_wheel_and_original_loader(
    configured, monkeypatch, mutation
):
    import sys

    directory, env = configured
    add_extension(directory, env)
    for name in list(sys.modules):
        if name.split(".")[0] == "example_alpha_extension":
            monkeypatch.delitem(sys.modules, name)
    if mutation == "wheel":
        next(directory.glob("*.whl")).write_bytes(b"tampered")
    elif mutation in ("kit", "set"):
        path = directory / "extension-lock.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "kit":
            data["kit_fingerprint"] = "sha256:" + "0" * 64
        else:
            data["artifacts"] = []
        path.write_text(json.dumps(data), encoding="utf-8")
    elif mutation == "signature":
        (directory / "extension-key").write_text("wrong-key-" * 8, encoding="utf-8")
    elif mutation == "configuration":
        (directory / "extension-config.json").write_text("{}", encoding="utf-8")
    if mutation is None:
        value = preflight.prepare(directory / "deployment.env")
        assert value.report()["extension_count"] == 1
        assert value.settings.runtime_extension_verification_key is not None
    else:
        with pytest.raises(preflight.BootstrapError):
            preflight.prepare(directory / "deployment.env")


def test_extension_timeout_and_provider_exception_are_closed(monkeypatch):
    from infra.enterprise.bootstrap import extensions
    from threading import Event

    finished = Event()
    monkeypatch.setattr(extensions, "STARTUP_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(extensions, "_load", lambda *_: finished.wait(0.1))
    with pytest.raises(preflight.BootstrapError, match="EXTENSION_STARTUP_TIMEOUT"):
        extensions.load_local_extensions({}, "test")
    finished.set()

    def crash(*_):
        raise RuntimeError("private-detail")

    monkeypatch.setattr(extensions, "_load", crash)
    with pytest.raises(preflight.BootstrapError, match="EXTENSION_INVALID") as error:
        extensions.load_local_extensions({}, "test")
    assert "private-detail" not in str(error.value)
