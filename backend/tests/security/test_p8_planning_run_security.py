"""TEST-P8-PLANNING-RUN-001 scope, capability, and disclosure controls."""

from __future__ import annotations

from typing import cast

import pytest

from app.application.planning_runs import (
    PlanningRunAttemptFailureCommand,
    PlanningRunCommandContext,
    PlanningRunOrchestrationService,
)
from app.domain.planning_run import (
    PlanningRunAttemptStatus,
    PlanningRunErrorCode,
    PlanningRunOrchestrationError,
)
from backend.tests.contract.p8_planning_run_support import (
    InMemoryPlanningRunRepository,
    canonical_ingress_record,
    command_context,
    schemas,
)


def _service(
    repository: InMemoryPlanningRunRepository,
) -> PlanningRunOrchestrationService:
    return PlanningRunOrchestrationService(schemas=schemas(), repository=repository)


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (
            command_context(tenant_id="TENANT-CROSS-SCOPE"),
            PlanningRunErrorCode.SCOPE_MISMATCH,
        ),
        (
            command_context(data_plane="PRODUCTION"),
            PlanningRunErrorCode.DATA_PLANE_MISMATCH,
        ),
        (
            command_context(capabilities=("view",)),
            PlanningRunErrorCode.AUTHORITY_CONFLICT,
        ),
        (
            command_context(capabilities=()),
            PlanningRunErrorCode.AUTHORITY_CONFLICT,
        ),
    ],
)
def test_materialize_fails_closed_before_any_repository_write(
    context: PlanningRunCommandContext,
    expected: PlanningRunErrorCode,
) -> None:
    repository = InMemoryPlanningRunRepository()
    with pytest.raises(PlanningRunOrchestrationError) as captured:
        _service(repository).materialize(
            canonical_ingress_record(),
            context=context,
            available_at_utc="2026-09-05T00:00:01Z",
            timeout_at_utc="2026-09-05T01:00:00Z",
        )
    assert captured.value.code is expected
    assert repository.audit_count == repository.transition_count == 0


def test_cross_tenant_read_and_write_are_rejected() -> None:
    repository = InMemoryPlanningRunRepository()
    service = _service(repository)
    created = service.materialize(
        canonical_ingress_record(),
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )
    run_id = cast(str, created.aggregate.document["planning_run_id"])

    for capabilities in (("view",), ("edit",)):
        with pytest.raises(PlanningRunOrchestrationError) as captured:
            service.read(
                run_id,
                context=command_context(
                    tenant_id="TENANT-CROSS-SCOPE", capabilities=capabilities
                ),
            )
        assert captured.value.code is PlanningRunErrorCode.SCOPE_MISMATCH


def test_production_requires_server_owned_production_binding() -> None:
    repository = InMemoryPlanningRunRepository(data_plane="PRODUCTION")
    record = canonical_ingress_record(data_plane="PRODUCTION", environment="PRODUCTION")

    with pytest.raises(PlanningRunOrchestrationError) as captured:
        _service(repository).materialize(
            record,
            context=command_context(
                data_plane="PRODUCTION",
                environment="PRODUCTION",
                production_binding=False,
            ),
            available_at_utc="2026-09-05T00:00:01Z",
            timeout_at_utc="2026-09-05T01:00:00Z",
        )
    assert captured.value.code is PlanningRunErrorCode.DATA_PLANE_MISMATCH
    assert repository.audit_count == 0


def test_raw_idempotency_key_and_executable_client_selectors_are_not_persisted() -> (
    None
):
    repository = InMemoryPlanningRunRepository()
    created = _service(repository).materialize(
        canonical_ingress_record(),
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )
    assert created.attempt is not None
    assert created.work_item is not None
    durable = b"\n".join(
        (
            created.aggregate.canonical_bytes,
            created.attempt.canonical_bytes,
            created.work_item.canonical_bytes,
        )
    ).lower()

    assert b"p8-canonical-key-0001" not in durable
    assert b'"idempotency_key"' not in durable
    for forbidden in (
        b'"module"',
        b'"class"',
        b'"entry_point"',
        b'"artifact_path"',
        b'"plugin_id"',
        b'"callable"',
        b"postgresql+psycopg",
        b"redis://",
    ):
        assert forbidden not in durable


def test_errors_are_stable_and_do_not_echo_raw_key_or_payload() -> None:
    repository = InMemoryPlanningRunRepository()
    service = _service(repository)
    secret_key = "never-echo-this-idempotency-secret"
    with pytest.raises(PlanningRunOrchestrationError) as captured:
        service.materialize(
            canonical_ingress_record(),
            context=command_context(tenant_id="TENANT-CROSS-SCOPE"),
            available_at_utc="2026-09-05T00:00:01Z",
            timeout_at_utc="2026-09-05T01:00:00Z",
        )

    rendered = str(captured.value)
    assert captured.value.code is PlanningRunErrorCode.SCOPE_MISMATCH
    assert secret_key not in rendered
    assert "canonical_request" not in rendered
    assert "synthetic_provenance" not in rendered


def test_attempt_failure_code_rejects_sensitive_or_executable_content() -> None:
    repository = InMemoryPlanningRunRepository()
    service = _service(repository)
    created = service.materialize(
        canonical_ingress_record(),
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )
    assert created.attempt is not None
    run = created.aggregate.document
    attempt = created.attempt.document
    unsafe = "queue failed: redis://credential@example"

    with pytest.raises(PlanningRunOrchestrationError) as captured:
        service.record_attempt_failure(
            PlanningRunAttemptFailureCommand(
                planning_run_id=cast(str, run["planning_run_id"]),
                expected_revision=1,
                expected_state="CREATED",
                expected_run_fingerprint=cast(str, run["run_fingerprint"]),
                attempt_id=cast(str, attempt["attempt_id"]),
                attempt_number=1,
                expected_attempt_revision=1,
                outcome=PlanningRunAttemptStatus.DISPATCH_FAILED,
                failure_code=unsafe,
                idempotency_key="p8-unsafe-failure-code-0001",
                reason="Reject unbounded failure details before persistence.",
            ),
            context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
        )

    assert captured.value.code is PlanningRunErrorCode.LINEAGE_INVALID
    assert unsafe not in str(captured.value)
    assert repository.audit_count == 1
