"""TEST-P8-PLANNING-RUN-001 exhaustive and mutation properties."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

import pytest

from app.application.planning_runs import (
    PlanningRunOrchestrationService,
    PlanningRunTransitionCommand,
)
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.domain.planning_run import (
    PLANNING_RUN_STATES,
    PLANNING_RUN_TRANSITIONS,
    PlanningRunAggregate,
    PlanningRunAttempt,
    PlanningRunAttemptStatus,
    PlanningRunErrorCode,
    PlanningRunOrchestrationError,
    PlanningRunWorkItem,
    require_planning_run_transition,
    verify_attempt,
    verify_planning_run,
    verify_work_item,
)
from app.jobs.planning_run_work_item import transition_attempt
from backend.tests.contract.p8_planning_run_support import (
    InMemoryPlanningRunRepository,
    canonical_ingress_record,
    command_context,
    schemas,
)


def _materialized() -> tuple[
    PlanningRunOrchestrationService,
    PlanningRunAggregate,
    PlanningRunAttempt,
    PlanningRunWorkItem,
]:
    service = PlanningRunOrchestrationService(
        schemas=schemas(), repository=InMemoryPlanningRunRepository()
    )
    result = service.materialize(
        canonical_ingress_record(),
        context=command_context(),
        available_at_utc="2026-09-05T00:00:01Z",
        timeout_at_utc="2026-09-05T01:00:00Z",
    )
    assert result.attempt is not None
    assert result.work_item is not None
    return service, result.aggregate, result.attempt, result.work_item


def _refingerprint(document: dict[str, Any], field: str) -> None:
    document[field] = canonical_fingerprint(
        {key: value for key, value in document.items() if key != field}
    )


def test_every_state_pair_has_exactly_the_frozen_acceptance_result() -> None:
    for source in sorted(PLANNING_RUN_STATES):
        for target in sorted(PLANNING_RUN_STATES):
            if (source, target) in PLANNING_RUN_TRANSITIONS:
                require_planning_run_transition(source, target)
            else:
                with pytest.raises(PlanningRunOrchestrationError) as captured:
                    require_planning_run_transition(source, target)
                assert (
                    captured.value.code is PlanningRunErrorCode.INVALID_STATE_TRANSITION
                )

    for unknown in ("", "created", "UNKNOWN", "COMPLETED "):
        with pytest.raises(PlanningRunOrchestrationError):
            require_planning_run_transition(unknown, "CREATED")
        with pytest.raises(PlanningRunOrchestrationError):
            require_planning_run_transition("CREATED", unknown)


def test_attempt_runtime_and_extension_fingerprint_drift_fail_closed() -> None:
    _service, aggregate, attempt, _work_item = _materialized()
    for field in ("runtime_resolution_fingerprint", "extension_set_fingerprint"):
        mutated = deepcopy(attempt.document)
        mutated[field] = f"sha256:{'f' * 64}"
        _refingerprint(mutated, "attempt_fingerprint")
        with pytest.raises(PlanningRunOrchestrationError) as captured:
            verify_attempt(
                PlanningRunAttempt(canonical_json_bytes(mutated)),
                aggregate=aggregate,
            )
        assert captured.value.code is PlanningRunErrorCode.RUNTIME_RESOLUTION_FAILED


def test_work_item_input_runtime_and_fingerprint_drift_fail_closed() -> None:
    _service, aggregate, attempt, work_item = _materialized()
    mutations = (
        ("inputs", {"planning_policy": None, "solve_limits": None}),
        ("prepared_artifacts", {}),
        ("expected_run_fingerprint", f"sha256:{'e' * 64}"),
    )
    for field, value in mutations:
        mutated = deepcopy(work_item.document)
        mutated[field] = value
        _refingerprint(mutated, "work_item_fingerprint")
        with pytest.raises(PlanningRunOrchestrationError) as captured:
            verify_work_item(
                PlanningRunWorkItem(canonical_json_bytes(mutated)),
                aggregate=aggregate,
                attempt=attempt,
            )
        assert captured.value.code is PlanningRunErrorCode.LINEAGE_INVALID

    runtime_mutation = deepcopy(work_item.document)
    runtime = cast(dict[str, Any], runtime_mutation["runtime_resolution"])
    runtime["runtime_version"] = "untrusted-runtime"
    _refingerprint(runtime_mutation, "work_item_fingerprint")
    with pytest.raises(PlanningRunOrchestrationError):
        verify_work_item(
            PlanningRunWorkItem(canonical_json_bytes(runtime_mutation)),
            aggregate=aggregate,
            attempt=attempt,
        )


def test_run_immutable_runtime_and_prepared_artifact_drift_fail_closed() -> None:
    _service, aggregate, _attempt, _work_item = _materialized()
    runtime_mutation = deepcopy(aggregate.document)
    runtime = cast(dict[str, Any], runtime_mutation["runtime_resolution"])
    runtime["runtime_version"] = "changed-runtime"
    runtime["resolution_fingerprint"] = canonical_fingerprint(
        {
            key: value
            for key, value in runtime.items()
            if key != "resolution_fingerprint"
        }
    )
    _refingerprint(runtime_mutation, "run_fingerprint")
    mutated_aggregate = PlanningRunAggregate(
        canonical_bytes=canonical_json_bytes(runtime_mutation),
        initial_run_bytes=aggregate.initial_run_bytes,
        prepared_artifacts_bytes=aggregate.prepared_artifacts_bytes,
        source_ingress_id=aggregate.source_ingress_id,
        source_record_fingerprint=aggregate.source_record_fingerprint,
    )
    with pytest.raises(PlanningRunOrchestrationError) as runtime_error:
        verify_planning_run(mutated_aggregate, schemas=schemas())
    assert runtime_error.value.code is PlanningRunErrorCode.LINEAGE_INVALID

    prepared_mutation = deepcopy(aggregate.prepared_artifacts)
    prepared_mutation["snapshot"] = {
        "document_version": "planning-snapshot.v2",
        "artifact_id": "P8-TAMPERED-SNAPSHOT",
        "fingerprint": f"sha256:{'d' * 64}",
    }
    tampered_source = PlanningRunAggregate(
        canonical_bytes=aggregate.canonical_bytes,
        initial_run_bytes=aggregate.initial_run_bytes,
        prepared_artifacts_bytes=canonical_json_bytes(prepared_mutation),
        source_ingress_id=aggregate.source_ingress_id,
        source_record_fingerprint=aggregate.source_record_fingerprint,
    )
    # CREATED has no published artifact, so source drift is caught when the
    # queue-ready work item is verified against the immutable prepared set.
    with pytest.raises(PlanningRunOrchestrationError):
        verify_work_item(
            _work_item,
            aggregate=tampered_source,
            attempt=_attempt,
        )


def test_run_audit_history_is_revision_bound_and_append_only() -> None:
    service, aggregate, _attempt, _work_item = _materialized()
    current = aggregate.document
    transitioned = service.transition(
        PlanningRunTransitionCommand(
            planning_run_id=cast(str, current["planning_run_id"]),
            expected_revision=1,
            expected_state="CREATED",
            expected_run_fingerprint=cast(str, current["run_fingerprint"]),
            to_state="INGESTING",
            idempotency_key="p8-audit-history-transition-0001",
            reason="Append one public transition audit reference.",
            artifacts=cast(dict[str, object], current["artifacts"]),
        ),
        context=command_context(occurred_at_utc="2026-09-05T00:00:02Z"),
    )
    mutated = deepcopy(transitioned.aggregate.document)
    mutated["audit_references"] = [mutated["audit_references"][-1]]
    _refingerprint(mutated, "run_fingerprint")
    candidate = PlanningRunAggregate(
        canonical_bytes=canonical_json_bytes(mutated),
        initial_run_bytes=aggregate.initial_run_bytes,
        prepared_artifacts_bytes=aggregate.prepared_artifacts_bytes,
        source_ingress_id=aggregate.source_ingress_id,
        source_record_fingerprint=aggregate.source_record_fingerprint,
    )

    with pytest.raises(PlanningRunOrchestrationError) as captured:
        verify_planning_run(candidate, schemas=schemas(), previous=current)
    assert captured.value.code is PlanningRunErrorCode.LINEAGE_INVALID


def test_attempt_expected_run_and_transition_audit_are_immutable() -> None:
    _service, aggregate, attempt, _work_item = _materialized()
    active = transition_attempt(
        attempt,
        aggregate=aggregate,
        to_status=PlanningRunAttemptStatus.ACTIVE,
        occurred_at_utc="2026-09-05T00:00:02Z",
        audit_reference={
            "document_version": "audit-event.v1",
            "artifact_id": "AUDIT-P8-ACTIVE",
            "fingerprint": f"sha256:{'a' * 64}",
        },
        failure_code=None,
        result_references=cast(dict[str, object], aggregate.document["artifacts"]),
    )

    for field, value in (
        ("expected_run_state", "VALIDATING"),
        ("expected_run_fingerprint", f"sha256:{'b' * 64}"),
        ("audit", attempt.document["audit"]),
    ):
        mutated = deepcopy(active.document)
        mutated[field] = value
        _refingerprint(mutated, "attempt_fingerprint")
        with pytest.raises(PlanningRunOrchestrationError) as captured:
            verify_attempt(
                PlanningRunAttempt(canonical_json_bytes(mutated)),
                aggregate=aggregate,
                previous=attempt.document,
            )
        assert captured.value.code is PlanningRunErrorCode.LINEAGE_INVALID
