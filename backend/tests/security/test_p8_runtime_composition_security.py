"""Fail-closed isolation and redaction evidence for P8-06."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from typing import cast

from celery import Celery
from pydantic import SecretStr, ValidationError
import pytest
from sqlalchemy import text

from app.application.runtime_facade import RuntimeFacadeError
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings
from app.jobs.planning_run_worker_contracts import (
    PlanningRunWorkerError,
    PlanningRunWorkerErrorCode,
)
from app.runtime_composition import (
    RuntimeCompositionError,
    RuntimeProcess,
    compose_runtime,
)
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    FixedRuntimeClock,
    RecordingCelery,
    dispatch_window,
    dispatched_message,
    ingress_context,
    runtime_settings,
)
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request


ROOT = Path(__file__).resolve().parents[3]


def _settings(tmp_path: Path):
    database_path = tmp_path / "security.db"
    engine, _ = migrated_engine(database_path)
    engine.dispose()
    return runtime_settings(
        tmp_path, database_url=f"sqlite:///{database_path.as_posix()}"
    )


def test_runtime_profile_rejects_implicit_plane_and_production_provider_gap(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.DEVELOPMENT,
            runtime_composition_enabled=True,
            runtime_planning_policy_path=tmp_path / "policy.json",
            runtime_solve_limits_path=tmp_path / "limits.json",
        )

    production = Settings(
        runtime_environment=RuntimeEnvironment.PRODUCTION,
        data_plane=DataPlane.PRODUCTION,
        code_commit="a" * 40,
        runtime_composition_enabled=True,
        runtime_planning_policy_path=tmp_path / "operator-secret-policy.json",
        runtime_solve_limits_path=tmp_path / "operator-secret-limits.json",
        database_url=SecretStr(
            "postgresql+psycopg://operator:do-not-leak@database/production"
        ),
    )
    with pytest.raises(RuntimeCompositionError) as captured:
        compose_runtime(production, process=RuntimeProcess.API)
    assert captured.value.code == "PRODUCTION_RUNTIME_UNAVAILABLE"
    assert str(tmp_path) not in str(captured.value)
    assert "do-not-leak" not in str(captured.value)


def test_unknown_environment_and_private_path_failure_are_sanitized(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    staging = settings.model_copy(
        update={"runtime_environment": RuntimeEnvironment.STAGING}
    )
    with pytest.raises(RuntimeCompositionError) as environment_error:
        compose_runtime(staging, process=RuntimeProcess.API)
    assert environment_error.value.code == "UNKNOWN_ENVIRONMENT"

    private_path = tmp_path / "customer-password-do-not-leak.json"
    invalid = settings.model_copy(
        update={"runtime_planning_policy_path": private_path}
    )
    with pytest.raises(RuntimeCompositionError) as path_error:
        compose_runtime(invalid, process=RuntimeProcess.API)
    assert path_error.value.code == "CONFIGURATION_INVALID"
    assert "customer-password-do-not-leak" not in str(path_error.value)


def test_descriptor_and_safe_manifests_exclude_secrets_and_paths(
    tmp_path: Path,
) -> None:
    base = _settings(tmp_path)
    settings = base.model_copy(
        update={
            "redis_url": SecretStr(
                "redis://operator:do-not-leak@redis/private-runtime"
            ),
            "celery_broker_url": SecretStr(
                "redis://operator:do-not-leak@broker/private-runtime"
            ),
        }
    )
    composition = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, RecordingCelery()),
    )
    try:
        rendered = str(composition.descriptor.document) + str(
            composition.safe_manifest()
        )
        assert "do-not-leak" not in rendered
        assert str(tmp_path) not in rendered
        assert "redis://" not in rendered
        assert "sqlite://" not in rendered
        assert settings.runtime_planning_policy_path is not None
        assert "runtime_planning_policy_path" not in settings.safe_summary()
    finally:
        composition.close()


def test_api_worker_descriptor_mismatch_rejects_before_solver_result(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    publisher = RecordingCelery()
    api = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("mismatch-dispatch"),
    )
    worker_settings = settings.model_copy(
        update={"runtime_artifact_fingerprint": f"sha256:{'f' * 64}"}
    )
    worker = compose_runtime(
        worker_settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(),
    )
    try:
        assert api.application is not None
        assert worker.worker is not None
        assert api.descriptor.fingerprint != worker.descriptor.fingerprint
        request = worker_request()
        api.application.submit_canonical(
            canonical_json_bytes(request),
            context=ingress_context(request, api.descriptor),
            dispatch_window=dispatch_window(),
        )
        message = dispatched_message(publisher.messages[0])
        with pytest.raises(PlanningRunWorkerError) as captured:
            worker.worker.execute(
                planning_run_id=cast(str, message["planning_run_id"]),
                work_item_id=cast(str, message["work_item_id"]),
                worker_id=cast(str, message["worker_id"]),
            )
        assert captured.value.code is PlanningRunWorkerErrorCode.RUNTIME_MISMATCH
        with worker.database.engine.connect() as connection:
            result_count = connection.scalar(
                text("SELECT count(*) FROM planning_run_worker_results")
            )
        assert result_count == 0
    finally:
        worker.close()
        api.close()


def test_context_cannot_select_another_runtime(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    composition = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, RecordingCelery()),
    )
    try:
        assert composition.application is not None
        request = worker_request()
        context = ingress_context(request, composition.descriptor)
        forged_commit_context = replace(context, code_commit="f" * 40)
        with pytest.raises(RuntimeFacadeError) as commit_error:
            composition.application.submit_canonical(
                canonical_json_bytes(request),
                context=forged_commit_context,
                dispatch_window=dispatch_window(),
            )
        assert commit_error.value.code == "RUNTIME_RESOLUTION_FAILED"
        assert commit_error.value.field == "context.code_commit"
        forged = context.runtime_resolution
        forged["runtime_version"] = "9.9.9"
        forged_context = replace(
            context,
            runtime_resolution_bytes=canonical_json_bytes(forged),
        )
        with pytest.raises(RuntimeFacadeError) as captured:
            composition.application.submit_canonical(
                canonical_json_bytes(request),
                context=forged_context,
                dispatch_window=dispatch_window(),
            )
        assert captured.value.code == "RUNTIME_RESOLUTION_FAILED"
        with composition.database.engine.connect() as connection:
            ingress_count = connection.scalar(
                text("SELECT count(*) FROM canonical_ingress_records")
            )
        assert ingress_count == 0
    finally:
        composition.close()


def test_core_has_no_runtime_or_extension_reverse_import() -> None:
    forbidden_prefixes = (
        "app.runtime_composition",
        "app.jobs.runtime_adapters",
        "app.extension_sdk",
        "enterprise_extension",
    )
    violations: list[str] = []
    for root in (ROOT / "backend" / "app" / "domain", ROOT / "backend" / "app" / "planning"):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules: tuple[str, ...] = ()
                if isinstance(node, ast.Import):
                    modules = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    modules = (node.module,)
                for module in modules:
                    if module.startswith(forbidden_prefixes):
                        violations.append(f"{path.relative_to(ROOT)}:{module}")
    assert violations == []
