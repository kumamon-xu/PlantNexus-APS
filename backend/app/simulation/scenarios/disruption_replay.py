"""Versioned five-step P4 disruption library and continuous replay orchestration.

The module owns scenario configuration and chain composition only.  It emits
standard events through the P4-09 simulator and requires a downstream port to
return exact Event -> Snapshot -> Replan -> Validator -> DRAFT/ChangeReport
evidence.  It does not implement facts, Solver formulas, persistence, approval,
publication, API, Production authority, or P5 capabilities.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import NoReturn, Protocol, cast

from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
)
from app.simulation.execution import (
    ArtifactReference,
    ExecutionEventIngressPort,
    ExecutionSimulator,
    ExecutionSimulatorConfig,
    PlanningPolicyReference,
    PublishedScheduleReference,
    ScheduledExecutionEvent,
    SolveLimitsReference,
    VersionedAssetReference,
    VersionedExecutionSchedule,
    VirtualClock,
)
from app.simulation.scenarios.contracts import MAX_SEED, require_semver


LIBRARY_VERSION = "p4-disruption-scenario-library.v1"
STEP_EVIDENCE_VERSION = "p4-disruption-step-evidence.v1"
REPLAY_REPORT_VERSION = "p4-disruption-continuous-replay.v1"
BASELINE_ADVANCE_MODE = "SIMULATION_NON_PRODUCTION"


class DisruptionKind(StrEnum):
    URGENT_ORDER = "URGENT_ORDER"
    MACHINE_FAILURE_RECOVERY = "MACHINE_FAILURE_RECOVERY"
    MATERIAL_DELAY = "MATERIAL_DELAY"
    PROCESSING_DELAY = "PROCESSING_DELAY"
    EARLY_COMPLETION = "EARLY_COMPLETION"


EXPECTED_STEP_EVENTS: tuple[tuple[DisruptionKind, tuple[str, ...]], ...] = (
    (DisruptionKind.URGENT_ORDER, ("URGENT_DEMAND_RECEIVED",)),
    (
        DisruptionKind.MACHINE_FAILURE_RECOVERY,
        ("MACHINE_UNAVAILABLE", "MACHINE_RECOVERED"),
    ),
    (DisruptionKind.MATERIAL_DELAY, ("MATERIAL_DELAYED", "MATERIAL_READY")),
    (
        DisruptionKind.PROCESSING_DELAY,
        ("PROCESSING_DURATION_CHANGED", "PROCESSING_REMAINING_CHANGED"),
    ),
    (DisruptionKind.EARLY_COMPLETION, ("OPERATION_COMPLETED",)),
)

EXPECTED_INVARIANTS = (
    "COMPLETED_OPERATION_PRESERVED",
    "RUNNING_RESOURCE_PRESERVED",
    "EXPLICIT_HARD_LOCKS_PRESERVED",
    "FREEZE_LOCKS_PRESERVED",
    "FRESH_VALIDATOR_PASS",
    "CHANGE_REPORT_COMPLETE",
)

_ROOT_KEYS = frozenset(
    {
        "library_version",
        "asset_id",
        "asset_version",
        "seed",
        "target_environment",
        "synthetic",
        "production_binding",
        "factory_id",
        "planning_scope_id",
        "base_schedule",
        "base_snapshot",
        "base_problem",
        "factory_profile",
        "generator",
        "simulator",
        "virtual_clock",
        "planning_policy",
        "solve_limits",
        "steps",
        "expected_invariants",
        "boundaries",
    }
)
_BOUNDARY_KEYS = frozenset(
    {
        "baseline_advance_mode",
        "p5_capabilities",
        "production_authority",
        "external_integration",
        "capacity_sla",
    }
)
_EVIDENCE_KEYS = frozenset(
    {
        "evidence_version",
        "step_id",
        "disruption_kind",
        "base_schedule_version",
        "base_snapshot",
        "trigger_event_ids",
        "new_snapshot",
        "new_problem",
        "replan_request",
        "planning_run",
        "validation_report",
        "new_schedule_version",
        "change_report",
        "fact_lock_invariants",
        "tardiness",
        "stability",
        "baseline_advance",
        "production_binding",
        "raw_events",
        "raw_replan_request",
        "raw_solver_report",
        "raw_validation_report",
        "raw_schedule_version",
        "raw_change_report",
    }
)


class DisruptionReplayFailure(StrEnum):
    INVALID_ASSET = "INVALID_ASSET"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    COVERAGE_MISMATCH = "COVERAGE_MISMATCH"
    ORDERING_VIOLATION = "ORDERING_VIOLATION"
    PRODUCTION_FORBIDDEN = "PRODUCTION_FORBIDDEN"
    CHAIN_MISMATCH = "CHAIN_MISMATCH"
    DOWNSTREAM_REJECTED = "DOWNSTREAM_REJECTED"


class DisruptionReplayError(ValueError):
    """Sanitized fail-closed scenario or continuous-chain rejection."""

    def __init__(
        self,
        reason: DisruptionReplayFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value} at {field}: {message}")


def _reject(reason: DisruptionReplayFailure, field: str, message: str) -> NoReturn:
    raise DisruptionReplayError(reason, field=field, message=message)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject(DisruptionReplayFailure.INVALID_ASSET, field, "must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _reject(DisruptionReplayFailure.INVALID_ASSET, field, "must be an array")
    return cast(Sequence[object], value)


def _text(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or any(character.isspace() for character in value)
    ):
        _reject(
            DisruptionReplayFailure.INVALID_ASSET,
            field,
            "must be non-empty canonical text without whitespace",
        )
    return value


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _reject(
            DisruptionReplayFailure.INVALID_ASSET,
            field,
            f"must be an integer greater than or equal to {minimum}",
        )
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], field: str
) -> None:
    observed = frozenset(value)
    if observed != expected:
        _reject(
            DisruptionReplayFailure.INVALID_ASSET,
            field,
            "has missing or unknown fields",
        )


def _artifact(value: object, field: str) -> ArtifactReference:
    document = _mapping(value, field)
    _exact_keys(
        document,
        frozenset({"document_version", "artifact_id", "fingerprint"}),
        field,
    )
    return ArtifactReference(
        document_version=_text(
            document.get("document_version"), f"{field}.document_version"
        ),
        artifact_id=_text(document.get("artifact_id"), f"{field}.artifact_id"),
        fingerprint=_text(document.get("fingerprint"), f"{field}.fingerprint"),
    )


def _asset(value: object, field: str) -> VersionedAssetReference:
    document = _mapping(value, field)
    _exact_keys(document, frozenset({"asset_id", "asset_version"}), field)
    asset_id = _text(document.get("asset_id"), f"{field}.asset_id")
    version = _text(document.get("asset_version"), f"{field}.asset_version")
    try:
        require_semver(version, f"{field}.asset_version")
    except ValueError as error:
        raise DisruptionReplayError(
            DisruptionReplayFailure.VERSION_MISMATCH,
            field=f"{field}.asset_version",
            message="must be a semantic version",
        ) from error
    return VersionedAssetReference(
        asset_id=asset_id,
        asset_version=version,
        fingerprint=contract_fingerprint(
            {"asset_kind": field, "asset_id": asset_id, "asset_version": version}
        ),
    )


@dataclass(frozen=True, slots=True)
class DisruptionStep:
    step_index: int
    step_id: str
    disruption_kind: DisruptionKind
    events: tuple[ScheduledExecutionEvent, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "step_index": self.step_index,
            "step_id": self.step_id,
            "disruption_kind": self.disruption_kind.value,
            "events": [event.as_document() for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class DisruptionScenarioLibrary:
    library_version: str
    asset_id: str
    asset_version: str
    seed: int
    target_environment: str
    factory_id: str
    planning_scope_id: str
    base_schedule: PublishedScheduleReference
    base_snapshot: ArtifactReference
    base_problem: ArtifactReference
    scenario: VersionedAssetReference
    factory_profile: VersionedAssetReference
    generator: VersionedAssetReference
    simulator: VersionedAssetReference
    virtual_clock: VirtualClock
    planning_policy: PlanningPolicyReference
    solve_limits: SolveLimitsReference
    freeze_window_seconds: int
    steps: tuple[DisruptionStep, ...]
    expected_invariants: tuple[str, ...]
    boundaries: tuple[tuple[str, str], ...]
    canonical_bytes: bytes

    @property
    def fingerprint(self) -> str:
        return contract_fingerprint(
            cast(Mapping[str, object], json.loads(self.canonical_bytes))
        )

    def as_document(self) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self.canonical_bytes))


@dataclass(frozen=True, slots=True)
class ReplayBaseline:
    schedule_version: PublishedScheduleReference
    snapshot: ArtifactReference
    problem: ArtifactReference
    source_draft_id: str | None = None
    advance_mode: str = BASELINE_ADVANCE_MODE

    def as_document(self) -> dict[str, object]:
        return {
            "schedule_version": self.schedule_version.as_document(),
            "snapshot": self.snapshot.as_document(),
            "problem": self.problem.as_document(),
            "source_draft_id": self.source_draft_id,
            "advance_mode": self.advance_mode,
            "production_binding": False,
        }


@dataclass(frozen=True, slots=True)
class ContinuousReplayStepRequest:
    step: DisruptionStep
    event_documents: tuple[dict[str, object], ...]
    baseline: ReplayBaseline
    stream_fingerprint: str


class ContinuousReplanPort(Protocol):
    """Public composition port for the already-owned P4 downstream chain."""

    def replay_step(self, request: ContinuousReplayStepRequest) -> Mapping[str, object]:
        """Return complete immutable evidence for exactly one disruption step."""
        ...


@dataclass(frozen=True, slots=True)
class ContinuousReplayStepRecord:
    step_index: int
    step_id: str
    disruption_kind: str
    from_position: int
    through_position: int
    event_ids: tuple[str, ...]
    evidence_bytes: bytes

    @property
    def evidence(self) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self.evidence_bytes))

    def as_document(self) -> dict[str, object]:
        return {
            "step_index": self.step_index,
            "step_id": self.step_id,
            "disruption_kind": self.disruption_kind,
            "from_position": self.from_position,
            "through_position": self.through_position,
            "event_ids": list(self.event_ids),
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class ContinuousReplayResult:
    library_fingerprint: str
    run_fingerprint: str
    event_stream_fingerprint: str
    event_ids: tuple[str, ...]
    steps: tuple[ContinuousReplayStepRecord, ...]
    final_baseline: ReplayBaseline

    def as_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "replay_version": REPLAY_REPORT_VERSION,
            "library_fingerprint": self.library_fingerprint,
            "run_fingerprint": self.run_fingerprint,
            "event_stream_fingerprint": self.event_stream_fingerprint,
            "event_ids": list(self.event_ids),
            "steps": [step.as_document() for step in self.steps],
            "final_baseline": self.final_baseline.as_document(),
            "production_binding": False,
            "p5_capabilities": "UNSUPPORTED",
        }
        document["replay_fingerprint"] = contract_fingerprint(document)
        return document

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_contract_bytes(self.as_document())


def load_disruption_scenario_library(path: Path) -> DisruptionScenarioLibrary:
    """Load one strict, versioned, Simulation-only five-disruption asset."""

    try:
        raw = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        raise DisruptionReplayError(
            DisruptionReplayFailure.INVALID_ASSET,
            field="scenario_library",
            message="cannot load a JSON object",
        ) from error
    document = _mapping(raw, "scenario_library")
    _exact_keys(document, _ROOT_KEYS, "scenario_library")
    if document.get("library_version") != LIBRARY_VERSION:
        _reject(
            DisruptionReplayFailure.VERSION_MISMATCH,
            "library_version",
            "unsupported disruption library version",
        )
    if (
        document.get("target_environment") not in {"DEVELOPMENT", "TEST", "BENCHMARK"}
        or document.get("synthetic") is not True
        or document.get("production_binding") is not False
    ):
        _reject(
            DisruptionReplayFailure.PRODUCTION_FORBIDDEN,
            "target_environment/synthetic/production_binding",
            "disruption replay is Simulation-only",
        )
    asset_id = _text(document.get("asset_id"), "asset_id")
    asset_version = _text(document.get("asset_version"), "asset_version")
    try:
        require_semver(asset_version, "asset_version")
    except ValueError as error:
        raise DisruptionReplayError(
            DisruptionReplayFailure.VERSION_MISMATCH,
            field="asset_version",
            message="must be a semantic version",
        ) from error
    seed = _integer(document.get("seed"), "seed")
    if seed > MAX_SEED:
        _reject(DisruptionReplayFailure.INVALID_ASSET, "seed", "exceeds MAX_SEED")

    base_document = _mapping(document.get("base_schedule"), "base_schedule")
    _exact_keys(
        base_document,
        frozenset(
            {
                "schedule_version_version",
                "schedule_version_id",
                "state",
                "content_fingerprint",
            }
        ),
        "base_schedule",
    )
    base_schedule = PublishedScheduleReference(
        schedule_version_version=_text(
            base_document.get("schedule_version_version"),
            "base_schedule.schedule_version_version",
        ),
        schedule_version_id=_text(
            base_document.get("schedule_version_id"),
            "base_schedule.schedule_version_id",
        ),
        state=_text(base_document.get("state"), "base_schedule.state"),
        content_fingerprint=_text(
            base_document.get("content_fingerprint"),
            "base_schedule.content_fingerprint",
        ),
    )
    base_snapshot = _artifact(document.get("base_snapshot"), "base_snapshot")
    base_problem = _artifact(document.get("base_problem"), "base_problem")
    factory_profile = _asset(document.get("factory_profile"), "factory_profile")
    generator = _asset(document.get("generator"), "generator")
    simulator = _asset(document.get("simulator"), "simulator")
    scenario = VersionedAssetReference(
        asset_id=asset_id,
        asset_version=asset_version,
        fingerprint=contract_fingerprint(document),
    )

    clock = _mapping(document.get("virtual_clock"), "virtual_clock")
    _exact_keys(
        clock,
        frozenset({"clock_version", "origin_at_utc", "resolution_seconds"}),
        "virtual_clock",
    )
    virtual_clock = VirtualClock(
        clock_version=_text(clock.get("clock_version"), "virtual_clock.clock_version"),
        origin_at_utc=_text(clock.get("origin_at_utc"), "virtual_clock.origin_at_utc"),
        resolution_seconds=_integer(
            clock.get("resolution_seconds"),
            "virtual_clock.resolution_seconds",
            minimum=1,
        ),
    )

    policy = _mapping(document.get("planning_policy"), "planning_policy")
    _exact_keys(
        policy,
        frozenset(
            {
                "planning_policy_version",
                "policy_id",
                "policy_revision",
                "policy_fingerprint",
                "freeze_window_seconds",
            }
        ),
        "planning_policy",
    )
    planning_policy = PlanningPolicyReference(
        planning_policy_version=_text(
            policy.get("planning_policy_version"),
            "planning_policy.planning_policy_version",
        ),
        policy_id=_text(policy.get("policy_id"), "planning_policy.policy_id"),
        policy_revision=_text(
            policy.get("policy_revision"), "planning_policy.policy_revision"
        ),
        policy_fingerprint=_text(
            policy.get("policy_fingerprint"), "planning_policy.policy_fingerprint"
        ),
    )
    freeze_window_seconds = _integer(
        policy.get("freeze_window_seconds"),
        "planning_policy.freeze_window_seconds",
        minimum=1,
    )

    limits = _mapping(document.get("solve_limits"), "solve_limits")
    _exact_keys(
        limits,
        frozenset(
            {
                "solve_limits_version",
                "limits_id",
                "limits_revision",
                "limits_fingerprint",
                "max_wall_time_seconds",
                "max_workers",
                "random_seed",
            }
        ),
        "solve_limits",
    )
    solve_limits = SolveLimitsReference(
        solve_limits_version=_text(
            limits.get("solve_limits_version"), "solve_limits.solve_limits_version"
        ),
        limits_id=_text(limits.get("limits_id"), "solve_limits.limits_id"),
        limits_revision=_text(
            limits.get("limits_revision"), "solve_limits.limits_revision"
        ),
        limits_fingerprint=_text(
            limits.get("limits_fingerprint"), "solve_limits.limits_fingerprint"
        ),
        max_wall_time_seconds=_integer(
            limits.get("max_wall_time_seconds"),
            "solve_limits.max_wall_time_seconds",
            minimum=1,
        ),
        max_workers=_integer(
            limits.get("max_workers"), "solve_limits.max_workers", minimum=1
        ),
        random_seed=_integer(limits.get("random_seed"), "solve_limits.random_seed"),
    )

    step_values = _sequence(document.get("steps"), "steps")
    if len(step_values) != len(EXPECTED_STEP_EVENTS):
        _reject(
            DisruptionReplayFailure.COVERAGE_MISMATCH,
            "steps",
            "must contain exactly the five P4 disruption steps",
        )
    steps: list[DisruptionStep] = []
    offsets: list[int] = []
    event_keys: list[str] = []
    for index, (raw_step, expected) in enumerate(
        zip(step_values, EXPECTED_STEP_EVENTS, strict=True), start=1
    ):
        step = _mapping(raw_step, f"steps[{index - 1}]")
        _exact_keys(
            step,
            frozenset({"step_index", "step_id", "disruption_kind", "events"}),
            f"steps[{index - 1}]",
        )
        if (
            _integer(
                step.get("step_index"), f"steps[{index - 1}].step_index", minimum=1
            )
            != index
        ):
            _reject(
                DisruptionReplayFailure.ORDERING_VIOLATION,
                f"steps[{index - 1}].step_index",
                "must be continuous and one-based",
            )
        try:
            kind = DisruptionKind(step.get("disruption_kind"))
        except (TypeError, ValueError) as error:
            raise DisruptionReplayError(
                DisruptionReplayFailure.COVERAGE_MISMATCH,
                field=f"steps[{index - 1}].disruption_kind",
                message="is not a supported P4 disruption",
            ) from error
        if kind is not expected[0]:
            _reject(
                DisruptionReplayFailure.COVERAGE_MISMATCH,
                f"steps[{index - 1}].disruption_kind",
                "does not match the required five-step order",
            )
        raw_events = _sequence(step.get("events"), f"steps[{index - 1}].events")
        events: list[ScheduledExecutionEvent] = []
        for event_index, raw_event in enumerate(raw_events):
            event = _mapping(raw_event, f"steps[{index - 1}].events[{event_index}]")
            _exact_keys(
                event,
                frozenset({"event_key", "offset_seconds", "event_type", "payload"}),
                f"steps[{index - 1}].events[{event_index}]",
            )
            payload = dict(
                _mapping(
                    event.get("payload"),
                    f"steps[{index - 1}].events[{event_index}].payload",
                )
            )
            built = ScheduledExecutionEvent.create(
                event_key=_text(
                    event.get("event_key"),
                    f"steps[{index - 1}].events[{event_index}].event_key",
                ),
                offset_seconds=_integer(
                    event.get("offset_seconds"),
                    f"steps[{index - 1}].events[{event_index}].offset_seconds",
                ),
                event_type=_text(
                    event.get("event_type"),
                    f"steps[{index - 1}].events[{event_index}].event_type",
                ),
                payload=payload,
            )
            offsets.append(built.offset_seconds)
            event_keys.append(built.event_key)
            events.append(built)
        if tuple(event.event_type for event in events) != expected[1]:
            _reject(
                DisruptionReplayFailure.COVERAGE_MISMATCH,
                f"steps[{index - 1}].events",
                "does not contain the exact standard event sequence",
            )
        steps.append(
            DisruptionStep(
                step_index=index,
                step_id=_text(step.get("step_id"), f"steps[{index - 1}].step_id"),
                disruption_kind=kind,
                events=tuple(events),
            )
        )
    if offsets != sorted(set(offsets)) or len(event_keys) != len(set(event_keys)):
        _reject(
            DisruptionReplayFailure.ORDERING_VIOLATION,
            "steps[].events",
            "event offsets must be strictly increasing and keys unique",
        )

    invariants = tuple(
        _text(value, "expected_invariants[]")
        for value in _sequence(
            document.get("expected_invariants"), "expected_invariants"
        )
    )
    if invariants != EXPECTED_INVARIANTS:
        _reject(
            DisruptionReplayFailure.COVERAGE_MISMATCH,
            "expected_invariants",
            "must contain the exact fact/lock/Validator/ChangeReport set",
        )
    boundaries = _mapping(document.get("boundaries"), "boundaries")
    _exact_keys(boundaries, _BOUNDARY_KEYS, "boundaries")
    expected_boundaries = {
        "baseline_advance_mode": BASELINE_ADVANCE_MODE,
        "p5_capabilities": "UNSUPPORTED",
        "production_authority": "NOT_ESTABLISHED",
        "external_integration": "NOT_ESTABLISHED",
        "capacity_sla": "NOT_ESTABLISHED",
    }
    if dict(boundaries) != expected_boundaries:
        _reject(
            DisruptionReplayFailure.PRODUCTION_FORBIDDEN,
            "boundaries",
            "must preserve the P4/P5/Production boundary",
        )

    return DisruptionScenarioLibrary(
        library_version=LIBRARY_VERSION,
        asset_id=asset_id,
        asset_version=asset_version,
        seed=seed,
        target_environment=cast(str, document["target_environment"]),
        factory_id=_text(document.get("factory_id"), "factory_id"),
        planning_scope_id=_text(document.get("planning_scope_id"), "planning_scope_id"),
        base_schedule=base_schedule,
        base_snapshot=base_snapshot,
        base_problem=base_problem,
        scenario=scenario,
        factory_profile=factory_profile,
        generator=generator,
        simulator=simulator,
        virtual_clock=virtual_clock,
        planning_policy=planning_policy,
        solve_limits=solve_limits,
        freeze_window_seconds=freeze_window_seconds,
        steps=tuple(steps),
        expected_invariants=invariants,
        boundaries=tuple(sorted(expected_boundaries.items())),
        canonical_bytes=canonical_contract_bytes(document),
    )


def build_execution_schedule(
    library: DisruptionScenarioLibrary,
) -> VersionedExecutionSchedule:
    return VersionedExecutionSchedule(
        schedule_version="execution-event-schedule.v1",
        config_id=f"{library.asset_id}-CONFIG",
        config_version=library.asset_version,
        base_schedule_content_fingerprint=(library.base_schedule.content_fingerprint),
        scenario_fingerprint=library.scenario.fingerprint,
        factory_profile_fingerprint=library.factory_profile.fingerprint,
        generator_fingerprint=library.generator.fingerprint,
        events=tuple(event for step in library.steps for event in step.events),
    )


def build_execution_config(
    library: DisruptionScenarioLibrary, *, code_commit: str = "uncommitted"
) -> ExecutionSimulatorConfig:
    return ExecutionSimulatorConfig(
        data_plane="SIMULATION",
        environment=library.target_environment,
        production_binding=False,
        synthetic=True,
        factory_id=library.factory_id,
        planning_scope_id=library.planning_scope_id,
        base_schedule_version=library.base_schedule,
        base_snapshot=library.base_snapshot,
        base_problem=library.base_problem,
        scenario=library.scenario,
        factory_profile=library.factory_profile,
        generator=library.generator,
        simulator=library.simulator,
        seed=library.seed,
        required_capabilities=(
            "DYNAMIC_REPLANNING",
            "SINGLE_FACTORY_MULTI_WORKSHOP",
        ),
        virtual_clock=library.virtual_clock,
        planning_policy=library.planning_policy,
        solve_limits=library.solve_limits,
        code_commit=code_commit,
    )


def _validate_step_evidence(
    value: Mapping[str, object],
    request: ContinuousReplayStepRequest,
) -> ReplayBaseline:
    _exact_keys(value, _EVIDENCE_KEYS, "step_evidence")
    if (
        value.get("evidence_version") != STEP_EVIDENCE_VERSION
        or value.get("step_id") != request.step.step_id
        or value.get("disruption_kind") != request.step.disruption_kind.value
        or value.get("production_binding") is not False
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.identity",
            "does not match the exact Simulation step",
        )
    if (
        value.get("base_schedule_version")
        != request.baseline.schedule_version.as_document()
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.base_schedule_version",
            "does not consume the previous explicit baseline",
        )
    if value.get("base_snapshot") != request.baseline.snapshot.as_document():
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.base_snapshot",
            "does not consume the previous immutable Snapshot",
        )
    event_ids = [cast(str, event["event_id"]) for event in request.event_documents]
    if value.get("trigger_event_ids") != event_ids:
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.trigger_event_ids",
            "does not bind the exact Simulator prefix delta",
        )
    new_snapshot = _artifact(value.get("new_snapshot"), "step_evidence.new_snapshot")
    new_problem = _artifact(value.get("new_problem"), "step_evidence.new_problem")
    request_reference = _artifact(
        value.get("replan_request"), "step_evidence.replan_request"
    )
    if request_reference.document_version != "replan-request.v1":
        _reject(
            DisruptionReplayFailure.VERSION_MISMATCH,
            "step_evidence.replan_request.document_version",
            "must use the frozen ReplanRequest contract",
        )
    raw_events = _sequence(value.get("raw_events"), "step_evidence.raw_events")
    if list(raw_events) != list(request.event_documents):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.raw_events",
            "must preserve the exact standard event delta",
        )
    raw_request = _mapping(
        value.get("raw_replan_request"), "step_evidence.raw_replan_request"
    )
    if (
        raw_request.get("replan_request_version") != "replan-request.v1"
        or raw_request.get("request_id") != request_reference.artifact_id
        or raw_request.get("request_fingerprint") != request_reference.fingerprint
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.raw_replan_request",
            "does not match the exact ReplanRequest reference",
        )
    planning_run = _mapping(value.get("planning_run"), "step_evidence.planning_run")
    if set(planning_run) != {"planning_run_id", "state", "fresh_validator_run"} or (
        planning_run.get("state") != "COMPLETED"
        or planning_run.get("fresh_validator_run") is not True
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.planning_run",
            "must complete with a fresh Validator run",
        )
    validation = _mapping(
        value.get("validation_report"), "step_evidence.validation_report"
    )
    if (
        set(validation)
        != {
            "document_version",
            "artifact_id",
            "fingerprint",
            "status",
            "hard_violation_count",
        }
        or validation.get("status") != "PASS"
        or validation.get("hard_violation_count") != 0
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.validation_report",
            "fresh independent Validator must PASS with zero hard violations",
        )
    _artifact(
        {
            key: validation[key]
            for key in ("document_version", "artifact_id", "fingerprint")
        },
        "step_evidence.validation_report.reference",
    )
    raw_validation = _mapping(
        value.get("raw_validation_report"),
        "step_evidence.raw_validation_report",
    )
    formal_validation = _mapping(
        raw_validation.get("formal_validation"),
        "step_evidence.raw_validation_report.formal_validation",
    )
    formal_fingerprint = contract_fingerprint(formal_validation)
    if (
        raw_validation.get("status") != "PASS"
        or raw_validation.get("hard_violation_count") != 0
        or formal_validation.get("validation_report_version")
        != "validation-report.v2"
        or formal_validation.get("status") != "PASS"
        or formal_validation.get("hard_violation_count") != 0
        or validation.get("artifact_id")
        != "validation-report-" + formal_fingerprint.removeprefix("sha256:")
        or validation.get("fingerprint") != formal_fingerprint
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.raw_validation_report",
            "does not contain the exact fresh independent Validator PASS",
        )
    draft = _mapping(
        value.get("new_schedule_version"), "step_evidence.new_schedule_version"
    )
    if (
        set(draft)
        != {
            "schedule_version_version",
            "schedule_version_id",
            "state",
            "content_fingerprint",
        }
        or draft.get("schedule_version_version") != "schedule-version.v2"
        or draft.get("state") != "DRAFT"
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.new_schedule_version",
            "must be one new immutable DRAFT",
        )
    draft_id = _text(
        draft.get("schedule_version_id"),
        "step_evidence.new_schedule_version.schedule_version_id",
    )
    draft_fingerprint = _text(
        draft.get("content_fingerprint"),
        "step_evidence.new_schedule_version.content_fingerprint",
    )
    raw_draft = _mapping(
        value.get("raw_schedule_version"), "step_evidence.raw_schedule_version"
    )
    if (
        raw_draft.get("schedule_version_version") != "schedule-version.v2"
        or raw_draft.get("schedule_version_id") != draft_id
        or raw_draft.get("state") != "DRAFT"
        or raw_draft.get("content_fingerprint") != draft_fingerprint
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.raw_schedule_version",
            "does not match the exact immutable DRAFT",
        )
    change = _mapping(value.get("change_report"), "step_evidence.change_report")
    if (
        set(change)
        != {
            "document_version",
            "artifact_id",
            "fingerprint",
            "complete",
            "trigger_event_ids",
        }
        or change.get("document_version") != "change-report.v1"
        or change.get("complete") is not True
        or change.get("trigger_event_ids") != event_ids
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.change_report",
            "must be complete and bind the exact triggering events",
        )
    _artifact(
        {
            key: change[key]
            for key in ("document_version", "artifact_id", "fingerprint")
        },
        "step_evidence.change_report.reference",
    )
    raw_change = _mapping(
        value.get("raw_change_report"), "step_evidence.raw_change_report"
    )
    raw_operations = _sequence(
        raw_change.get("operations"), "step_evidence.raw_change_report.operations"
    )
    if (
        raw_change.get("change_report_version") != "change-report.v1"
        or raw_change.get("report_id") != change.get("artifact_id")
        or raw_change.get("report_fingerprint") != change.get("fingerprint")
        or raw_change.get("operation_universe_count") != len(raw_operations)
        or raw_change.get("production_binding") is not False
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.raw_change_report",
            "does not match the complete ChangeReport reference",
        )
    raw_solver = _mapping(
        value.get("raw_solver_report"), "step_evidence.raw_solver_report"
    )
    if (
        raw_solver.get("solver_report_version") != "solver-report.v2"
        or raw_solver.get("planning_run_id") != planning_run.get("planning_run_id")
        or raw_solver.get("candidate") is None
        or raw_solver.get("solver_status") not in {"OPTIMAL", "FEASIBLE"}
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.raw_solver_report",
            "does not contain the successful owner Solver result",
        )
    invariants = _mapping(
        value.get("fact_lock_invariants"), "step_evidence.fact_lock_invariants"
    )
    if set(invariants) != set(EXPECTED_INVARIANTS) or any(
        invariants.get(name) is not True for name in EXPECTED_INVARIANTS
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.fact_lock_invariants",
            "all registered invariants must PASS",
        )
    tardiness = _mapping(value.get("tardiness"), "step_evidence.tardiness")
    if set(tardiness) != {"before_seconds", "after_seconds"}:
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.tardiness",
            "must contain exact before/after values",
        )
    _integer(tardiness.get("before_seconds"), "step_evidence.tardiness.before_seconds")
    _integer(tardiness.get("after_seconds"), "step_evidence.tardiness.after_seconds")
    stability = _mapping(value.get("stability"), "step_evidence.stability")
    expected_stability = {
        "soft_lock_violation_count",
        "changed_existing_operation_count",
        "resource_changed_count",
        "total_absolute_start_shift_seconds",
    }
    if set(stability) != expected_stability:
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.stability",
            "must contain the complete OBJ-002 vector",
        )
    for name in expected_stability:
        _integer(stability.get(name), f"step_evidence.stability.{name}")

    advance = _mapping(value.get("baseline_advance"), "step_evidence.baseline_advance")
    if set(advance) != {
        "mode",
        "production_binding",
        "authority_claim",
        "source_draft_id",
        "next_schedule_version",
        "next_snapshot",
        "next_problem",
    } or (
        advance.get("mode") != BASELINE_ADVANCE_MODE
        or advance.get("production_binding") is not False
        or advance.get("authority_claim") != "NONE"
        or advance.get("source_draft_id") != draft_id
    ):
        _reject(
            DisruptionReplayFailure.PRODUCTION_FORBIDDEN,
            "step_evidence.baseline_advance",
            "may only advance a non-Production test baseline without authority",
        )
    next_schedule_document = _mapping(
        advance.get("next_schedule_version"),
        "step_evidence.baseline_advance.next_schedule_version",
    )
    if set(next_schedule_document) != {
        "schedule_version_version",
        "schedule_version_id",
        "state",
        "content_fingerprint",
    } or (
        next_schedule_document.get("schedule_version_version")
        not in {"schedule-version.v1", "schedule-version.v2"}
        or next_schedule_document.get("state") != "PUBLISHED"
        or next_schedule_document.get("content_fingerprint") != draft_fingerprint
        or next_schedule_document.get("schedule_version_id") == draft_id
    ):
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.baseline_advance.next_schedule_version",
            "must re-bind the exact DRAFT content to a distinct test-only baseline",
        )
    next_snapshot = _artifact(
        advance.get("next_snapshot"), "step_evidence.baseline_advance.next_snapshot"
    )
    next_problem = _artifact(
        advance.get("next_problem"), "step_evidence.baseline_advance.next_problem"
    )
    if next_snapshot != new_snapshot or next_problem != new_problem:
        _reject(
            DisruptionReplayFailure.CHAIN_MISMATCH,
            "step_evidence.baseline_advance",
            "must carry forward the exact new Snapshot and Problem",
        )
    return ReplayBaseline(
        schedule_version=PublishedScheduleReference(
            schedule_version_version=cast(
                str, next_schedule_document["schedule_version_version"]
            ),
            schedule_version_id=cast(
                str, next_schedule_document["schedule_version_id"]
            ),
            state="PUBLISHED",
            content_fingerprint=draft_fingerprint,
        ),
        snapshot=next_snapshot,
        problem=next_problem,
        source_draft_id=draft_id,
    )


class DisruptionReplayOrchestrator:
    """Advance all five scenarios while preserving exact step lineage."""

    def __init__(self, simulator: ExecutionSimulator | None = None) -> None:
        self._simulator = simulator or ExecutionSimulator()

    def run(
        self,
        library: DisruptionScenarioLibrary,
        ingress: ExecutionEventIngressPort,
        downstream: ContinuousReplanPort,
        *,
        code_commit: str = "uncommitted",
    ) -> ContinuousReplayResult:
        config = build_execution_config(library, code_commit=code_commit)
        schedule = build_execution_schedule(library)
        compiled = self._simulator.compile(config, schedule)
        declared_keys = tuple(
            event.event_key for step in library.steps for event in step.events
        )
        if compiled.event_keys != declared_keys:
            _reject(
                DisruptionReplayFailure.ORDERING_VIOLATION,
                "compiled.event_keys",
                "does not preserve the strict five-step event order",
            )
        baseline = ReplayBaseline(
            schedule_version=library.base_schedule,
            snapshot=library.base_snapshot,
            problem=library.base_problem,
        )
        checkpoint = compiled.initial_checkpoint()
        records: list[ContinuousReplayStepRecord] = []
        for step in library.steps:
            from_position = checkpoint.last_emitted_position + 1
            emitted = self._simulator.run(
                config,
                schedule,
                ingress,
                checkpoint=checkpoint,
                max_events=len(step.events),
            )
            checkpoint = emitted.checkpoint
            through_position = checkpoint.last_emitted_position
            event_documents = compiled.events[from_position - 1 : through_position]
            request = ContinuousReplayStepRequest(
                step=step,
                event_documents=event_documents,
                baseline=baseline,
                stream_fingerprint=emitted.stream_fingerprint,
            )
            try:
                evidence_value = downstream.replay_step(request)
            except DisruptionReplayError:
                raise
            except Exception as error:
                raise DisruptionReplayError(
                    DisruptionReplayFailure.DOWNSTREAM_REJECTED,
                    field=f"steps[{step.step_index - 1}]",
                    message="the common downstream replay chain rejected the step",
                ) from error
            evidence = dict(evidence_value)
            baseline = _validate_step_evidence(evidence, request)
            event_ids = tuple(
                cast(str, document["event_id"]) for document in event_documents
            )
            records.append(
                ContinuousReplayStepRecord(
                    step_index=step.step_index,
                    step_id=step.step_id,
                    disruption_kind=step.disruption_kind.value,
                    from_position=from_position,
                    through_position=through_position,
                    event_ids=event_ids,
                    evidence_bytes=canonical_contract_bytes(evidence),
                )
            )
        if checkpoint.last_emitted_position != len(compiled.events):
            _reject(
                DisruptionReplayFailure.ORDERING_VIOLATION,
                "checkpoint.last_emitted_position",
                "did not consume the complete disruption stream",
            )
        return ContinuousReplayResult(
            library_fingerprint=library.fingerprint,
            run_fingerprint=compiled.run_fingerprint,
            event_stream_fingerprint=compiled.stream_fingerprint,
            event_ids=compiled.event_ids,
            steps=tuple(records),
            final_baseline=baseline,
        )


__all__ = [
    "BASELINE_ADVANCE_MODE",
    "ContinuousReplanPort",
    "ContinuousReplayResult",
    "ContinuousReplayStepRequest",
    "DisruptionKind",
    "DisruptionReplayError",
    "DisruptionReplayFailure",
    "DisruptionReplayOrchestrator",
    "DisruptionScenarioLibrary",
    "DisruptionStep",
    "EXPECTED_INVARIANTS",
    "EXPECTED_STEP_EVENTS",
    "LIBRARY_VERSION",
    "ReplayBaseline",
    "STEP_EVIDENCE_VERSION",
    "build_execution_config",
    "build_execution_schedule",
    "load_disruption_scenario_library",
]
