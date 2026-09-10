"""Trust-boundary, timeout, redaction, and no-partial-result tests for P8-13."""

from __future__ import annotations

import ast
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import cast

from celery import Celery
import pytest
from sqlalchemy import text

from aps_extension_sdk import (
    ContributionManifest,
    FrozenJsonObject,
    ValidationContext,
    ValidationOutput,
    ValidationViolation,
    freeze_json,
)

from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.extensions.contracts import RuntimeExtensionError
from app.extensions.registry import LoadedRuntimeExtensionAdapter
from app.jobs.planning_run_worker_contracts import PlanningRunWorkerError
from app.runtime_composition import (
    RuntimeCompositionError,
    RuntimeProcess,
    compose_runtime,
)
from backend.tests.fixtures.p8_synthetic_extension import (
    CrashingObjective,
    ForgedObjective,
    SlowObjective,
    SyntheticValidationRule,
)
from backend.tests.p8_runtime_extension_support import runtime_extension_fixture
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    FixedRuntimeClock,
    RecordingCelery,
    command_context,
    dispatch_window,
    dispatched_message,
    ingress_context,
)
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request


ROOT = Path(__file__).resolve().parents[3]
OBJECTIVE_ID = "com.example.cost.objective"
VALIDATION_ID = "com.example.capacity.validator"


class _RejectingValidationRule(SyntheticValidationRule):
    def validate(self, context: ValidationContext) -> ValidationOutput:
        del context
        observed = freeze_json({"resource_id": "RESOURCE-001"})
        expected = freeze_json({"eligible": True})
        assert isinstance(observed, FrozenJsonObject)
        assert isinstance(expected, FrozenJsonObject)
        return ValidationOutput(
            contribution_id=self.descriptor.contribution_id,
            validated_contribution_ids=self.descriptor.validates_contribution_ids,
            passed=False,
            violations=(
                ValidationViolation(
                    violation_code="com.example.product.rejected",
                    entity_ids=("operation.synthetic",),
                    path="$.assignments",
                    observed=observed,
                    expected=expected,
                    message_key="com.example.product.rejected",
                ),
            ),
        )


def _fixture(tmp_path: Path, **kwargs):
    return runtime_extension_fixture(
        tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
        **kwargs,
    )


def _common() -> dict[str, dict[str, object]]:
    return {
        "scope": {"tenant_id": "TENANT-SECURITY"},
        "facts": {"candidate": "SYNTHETIC"},
        "provenance": {"planning_run_id": "planning-run-security"},
    }


@pytest.mark.parametrize(
    ("implementation", "expected_code"),
    [
        (CrashingObjective, "EXTENSION_EXECUTION_FAILED"),
        (ForgedObjective, "EXTENSION_OUTPUT_INVALID"),
    ],
)
def test_crash_and_invalid_output_are_redacted_and_discarded(
    tmp_path: Path,
    implementation,
    expected_code: str,
) -> None:
    fixture = _fixture(tmp_path, overrides={OBJECTIVE_ID: implementation})
    adapter = fixture.load()
    with pytest.raises(RuntimeExtensionError) as captured:
        adapter.invoke_objectives(**_common())
    assert captured.value.code == expected_code
    assert "do-not-leak" not in str(captured.value)
    metrics = adapter.safe_metrics()
    objective = next(
        row
        for row in metrics["contributions"]
        if row["contribution_id"] == OBJECTIVE_ID
    )
    assert objective["success_count"] == 0
    assert objective["failure_count"] == 1
    with pytest.raises(RuntimeExtensionError) as readiness:
        adapter.probe()
    assert readiness.value.code == "EXTENSION_UNHEALTHY"
    with pytest.raises(RuntimeExtensionError) as subsequent_call:
        adapter.invoke_objectives(**_common())
    assert subsequent_call.value.code == "EXTENSION_UNHEALTHY"


def test_timeout_rejects_complete_call_and_marks_readiness_down(tmp_path: Path) -> None:
    fixture = _fixture(
        tmp_path,
        overrides={OBJECTIVE_ID: SlowObjective},
        invocation_timeout_ms=30,
    )
    adapter = fixture.load()
    with pytest.raises(RuntimeExtensionError) as captured:
        adapter.invoke_objectives(**_common())
    assert captured.value.code == "EXTENSION_TIMEOUT"
    metrics = adapter.safe_metrics()
    objective = next(
        row
        for row in metrics["contributions"]
        if row["contribution_id"] == OBJECTIVE_ID
    )
    assert objective["timeout_count"] == 1
    assert objective["success_count"] == 0
    with pytest.raises(RuntimeExtensionError):
        adapter.probe()


def test_private_path_and_configuration_values_never_enter_safe_identity(
    tmp_path: Path,
) -> None:
    fixture = _fixture(
        tmp_path,
        configuration_values={"customer_token": "do-not-leak"},
    )
    adapter = fixture.load()
    rendered = str(adapter.document) + str(adapter.safe_metrics())
    assert "do-not-leak" not in rendered
    assert str(tmp_path) not in rendered

    catalog = deepcopy(fixture.catalog)
    catalog["extensions"][0]["manifest_path"] = str(
        tmp_path / "private" / "customer-secret.json"
    )
    projection = dict(catalog)
    projection.pop("catalog_fingerprint")
    catalog["catalog_fingerprint"] = canonical_fingerprint(projection)
    fixture.catalog_path.write_bytes(canonical_json_bytes(catalog) + b"\n")
    with pytest.raises(RuntimeExtensionError) as captured:
        fixture.load()
    assert str(tmp_path) not in str(captured.value)
    assert "customer-secret" not in str(captured.value)


def test_rejected_startup_has_no_database_or_business_side_effect(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "must-not-exist.db"
    fixture = runtime_extension_fixture(
        tmp_path,
        database_url=f"sqlite:///{database_path.as_posix()}",
    )
    catalog = deepcopy(fixture.catalog)
    catalog["extensions"][0]["signature"] = f"hmac-sha256:{'0' * 64}"
    projection = dict(catalog)
    projection.pop("catalog_fingerprint")
    catalog["catalog_fingerprint"] = canonical_fingerprint(projection)
    fixture.catalog_path.write_bytes(canonical_json_bytes(catalog) + b"\n")

    assert not database_path.exists()
    with pytest.raises(RuntimeCompositionError) as captured:
        compose_runtime(
            fixture.settings,
            process=RuntimeProcess.WORKER,
            extension_artifacts=(fixture.artifact,),
        )
    assert captured.value.code == "EXTENSION_ARTIFACT_SIGNATURE_INVALID"
    assert not database_path.exists()


@pytest.mark.parametrize(
    ("contribution_id", "implementation", "expected_extension_code"),
    [
        (OBJECTIVE_ID, CrashingObjective, "EXTENSION_EXECUTION_FAILED"),
        (VALIDATION_ID, _RejectingValidationRule, "EXTENSION_VALIDATION_FAILED"),
    ],
)
def test_product_extension_failure_is_terminal_before_schedule_version(
    tmp_path: Path,
    contribution_id: str,
    implementation: Callable[[ContributionManifest], object],
    expected_extension_code: str,
) -> None:
    database_path = tmp_path / "product-failure.db"
    engine, _ = migrated_engine(database_path)
    engine.dispose()
    database_url = f"sqlite:///{database_path.as_posix()}"
    fixture = runtime_extension_fixture(
        tmp_path,
        database_url=database_url,
        overrides={contribution_id: implementation},
    )
    publisher = RecordingCelery()
    api = compose_runtime(
        fixture.settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("extension-product-failure-001"),
        extension_artifacts=(fixture.artifact,),
    )
    worker = compose_runtime(
        fixture.settings,
        process=RuntimeProcess.WORKER,
        clock=FixedRuntimeClock(),
        extension_artifacts=(fixture.artifact,),
    )
    try:
        assert api.application is not None
        assert worker.worker is not None
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
        assert captured.value.code.value == "EXECUTION_FAILED"
        assert captured.value.field == "runtime_extension"
        assert isinstance(captured.value.__cause__, RuntimeExtensionError)
        assert captured.value.__cause__.code == expected_extension_code
        final = api.application.read_planning_run(
            cast(str, message["planning_run_id"]),
            context=command_context(request),
        )
        assert final.aggregate.document["state"] == "FAILED"
        with api.database.engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT count(*) FROM schedule_versions")) == 0
            )
        assert isinstance(worker.extension_adapter, LoadedRuntimeExtensionAdapter)
        rendered = str(captured.value) + str(worker.extension_adapter.safe_metrics())
        assert "do-not-leak" not in rendered
    finally:
        worker.close()
        api.close()


def test_core_and_formal_validator_have_no_extension_reverse_import() -> None:
    forbidden = ("app.extensions", "aps_extension_sdk", "enterprise_extension")
    violations: list[str] = []
    roots = (
        ROOT / "backend/app/domain",
        ROOT / "backend/app/planning",
        ROOT / "backend/app/snapshots",
    )
    for directory in roots:
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules: tuple[str, ...] = ()
                if isinstance(node, ast.Import):
                    modules = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    modules = (node.module,)
                if any(module.startswith(forbidden) for module in modules):
                    violations.append(path.relative_to(ROOT).as_posix())
    assert violations == []
