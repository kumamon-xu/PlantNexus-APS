"""TASK-P0-08 health behavior plus TASK-P3-10 route compatibility evidence."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.api.app import create_app
from app.infrastructure.config import (
    ConfigurationError,
    DataPlane,
    RuntimeEnvironment,
    Settings,
    load_settings,
)


def test_settings_do_not_implicitly_load_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text(
        "PLANTNEXUS_RUNTIME_ENVIRONMENT=production\nPLANTNEXUS_DATA_PLANE=production\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PLANTNEXUS_RUNTIME_ENVIRONMENT", raising=False)
    monkeypatch.delenv("PLANTNEXUS_DATA_PLANE", raising=False)
    monkeypatch.delenv("PLANTNEXUS_CODE_COMMIT", raising=False)
    settings = Settings()
    assert settings.runtime_environment is RuntimeEnvironment.DEVELOPMENT
    assert settings.data_plane is DataPlane.DEVELOPMENT


def test_production_configuration_is_fail_closed_and_secret_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLANTNEXUS_RUNTIME_ENVIRONMENT", "production")
    monkeypatch.setenv("PLANTNEXUS_DATA_PLANE", "production")
    monkeypatch.setenv("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    monkeypatch.setenv("PLANTNEXUS_SIMULATION_API_ENABLED", "true")
    monkeypatch.setenv(
        "PLANTNEXUS_DATABASE_URL",
        "postgresql+psycopg://operator:do-not-leak@database/production",
    )

    with pytest.raises(ConfigurationError) as error:
        load_settings()
    assert str(error.value) == "invalid PLANTNEXUS_ configuration"
    assert "do-not-leak" not in str(error.value)

    with pytest.raises(ValidationError):
        Settings(
            runtime_environment=RuntimeEnvironment.PRODUCTION,
            data_plane=DataPlane.PRODUCTION,
            code_commit="a" * 40,
            simulation_api_enabled=True,
        )

    valid = Settings(
        runtime_environment=RuntimeEnvironment.PRODUCTION,
        data_plane=DataPlane.PRODUCTION,
        code_commit="a" * 40,
        simulation_api_enabled=False,
        database_url=SecretStr(
            "postgresql+psycopg://operator:do-not-leak@database/production"
        ),
    )
    assert valid.safe_summary()["data_plane"] == "production"
    assert "do-not-leak" not in repr(valid)
    assert "database_url" not in valid.safe_summary()


def test_environment_and_lease_invariants_reject_ambiguous_values() -> None:
    with pytest.raises(ValidationError):
        Settings(
            runtime_environment=RuntimeEnvironment.PRODUCTION,
            data_plane=DataPlane.SIMULATION,
            code_commit="a" * 40,
        )
    with pytest.raises(ValidationError):
        Settings(job_heartbeat_seconds=30, job_lease_seconds=30)
    with pytest.raises(ValidationError):
        Settings(code_commit="moving-branch")


def test_malformed_environment_value_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLANTNEXUS_SIMULATION_API_ENABLED", "not-a-boolean")
    with pytest.raises(ConfigurationError) as error:
        load_settings()
    assert str(error.value) == "invalid PLANTNEXUS_ configuration"
    assert "not-a-boolean" not in str(error.value)


def test_health_endpoints_separate_liveness_from_readiness() -> None:
    settings = Settings(
        runtime_environment=RuntimeEnvironment.TEST,
        data_plane=DataPlane.DEVELOPMENT,
        code_commit="b" * 40,
    )

    def database_unavailable() -> None:
        raise RuntimeError(
            "postgresql://operator:do-not-leak@database/plantnexus_production"
        )

    application = create_app(
        settings,
        probes={"database": database_unavailable, "redis": lambda: None},
    )
    with TestClient(application) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        unknown = client.get("/orders")

    assert live.status_code == 200
    assert live.json()["status"] == "UP"
    assert live.json()["checks"] == [{"name": "process", "status": "UP"}]
    assert live.json()["build"]["code_commit"] == "b" * 40

    assert ready.status_code == 503
    assert ready.json()["status"] == "DOWN"
    assert ready.json()["checks"] == [
        {
            "name": "database",
            "status": "DOWN",
            "code": "DATABASE_UNAVAILABLE",
        },
        {"name": "redis", "status": "UP"},
    ]
    assert "do-not-leak" not in ready.text
    assert "RuntimeError" not in ready.text
    assert unknown.status_code == 404
    route_paths = {getattr(route, "path", None) for route in application.routes}
    assert {"/health/live", "/health/ready", "/openapi.json"} <= route_paths
    assert len({path for path in route_paths if str(path).startswith("/api/v1/")}) == 26


def test_readiness_is_up_when_all_dependencies_pass() -> None:
    application = create_app(
        Settings(runtime_environment=RuntimeEnvironment.TEST),
        probes={"database": lambda: None, "redis": lambda: None},
    )
    with TestClient(application) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"
    assert all(check["status"] == "UP" for check in response.json()["checks"])
