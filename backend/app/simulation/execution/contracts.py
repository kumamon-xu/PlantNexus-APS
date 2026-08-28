"""Immutable contracts for deterministic Simulation execution streams.

These values bind one PUBLISHED ScheduleVersion reference, versioned synthetic
provenance, a virtual clock, and a versioned event schedule.  They do not own a
business state machine, persistence, Solver, Replan, API, or Production source.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import re
from typing import NoReturn, cast

from app.domain.capabilities import CapabilityContractError, require_v1_capability_contract
from app.domain.execution_contracts import canonical_contract_bytes, contract_fingerprint
from app.domain.types import ContractValueError, canonical_id, parse_utc_instant
from app.simulation.scenarios.contracts import MAX_SEED, require_semver


EXECUTION_EVENT_SCHEDULE_VERSION = "execution-event-schedule.v1"
EXECUTION_SIMULATOR_RUN_VERSION = "execution-simulator-run.v1"
VIRTUAL_CLOCK_VERSION = "virtual-clock.v1"
CHILD_SEED_DERIVATION_VERSION = "named-child-seed.v1"
SUPPORTED_ENVIRONMENTS = frozenset({"DEVELOPMENT", "TEST", "BENCHMARK"})
SUPPORTED_EVENT_TYPES = frozenset(
    {
        "OPERATION_STARTED",
        "OPERATION_COMPLETED",
        "MACHINE_UNAVAILABLE",
        "MACHINE_RECOVERED",
        "MATERIAL_READY",
        "MATERIAL_DELAYED",
        "PROCESSING_DURATION_CHANGED",
        "PROCESSING_REMAINING_CHANGED",
        "URGENT_DEMAND_RECEIVED",
        "LOCK_CREATED",
        "LOCK_RELEASED",
    }
)
_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^(?:uncommitted|[0-9a-f]{40})$")


class ExecutionSimulatorFailure(StrEnum):
    """Stable fail-closed reasons owned by the Simulation core."""

    INVALID_CONFIG = "INVALID_CONFIG"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    PRODUCTION_FORBIDDEN = "PRODUCTION_FORBIDDEN"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    ORDERING_VIOLATION = "ORDERING_VIOLATION"
    CHECKPOINT_MISMATCH = "CHECKPOINT_MISMATCH"
    INGRESS_REJECTED = "INGRESS_REJECTED"


class ExecutionSimulatorError(ValueError):
    """Sanitized deterministic rejection before an invalid run can continue."""

    def __init__(
        self,
        reason: ExecutionSimulatorFailure,
        *,
        field: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.message = message
        super().__init__(f"{reason.value} at {field}: {message}")


def reject(
    reason: ExecutionSimulatorFailure, field: str, message: str
) -> NoReturn:
    raise ExecutionSimulatorError(reason, field=field, message=message)


def require_identity(value: object, field: str) -> str:
    if not isinstance(value, str):
        reject(ExecutionSimulatorFailure.INVALID_CONFIG, field, "must be text")
    try:
        return str(canonical_id(value))
    except ContractValueError as error:
        raise ExecutionSimulatorError(
            ExecutionSimulatorFailure.INVALID_CONFIG,
            field=field,
            message="must be a canonical identifier",
        ) from error


def require_version(value: object, field: str) -> str:
    if not isinstance(value, str):
        reject(ExecutionSimulatorFailure.VERSION_MISMATCH, field, "must be text")
    try:
        return require_semver(value, field)
    except ValueError as error:
        raise ExecutionSimulatorError(
            ExecutionSimulatorFailure.VERSION_MISMATCH,
            field=field,
            message="must be a semantic version",
        ) from error


def require_fingerprint(value: object, field: str) -> str:
    if not isinstance(value, str) or _FINGERPRINT_RE.fullmatch(value) is None:
        reject(
            ExecutionSimulatorFailure.INVALID_CONFIG,
            field,
            "must be a lowercase algorithm-qualified SHA-256 fingerprint",
        )
    return value


def require_non_negative_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        reject(
            ExecutionSimulatorFailure.INVALID_CONFIG,
            field,
            "must be a non-negative integer",
        )
    return value


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Exact immutable artifact reference used by the P4 machine carriers."""

    document_version: str
    artifact_id: str
    fingerprint: str

    def __post_init__(self) -> None:
        require_identity(self.document_version, "artifact.document_version")
        require_identity(self.artifact_id, "artifact.artifact_id")
        require_fingerprint(self.fingerprint, "artifact.fingerprint")

    def as_document(self) -> dict[str, object]:
        return {
            "document_version": self.document_version,
            "artifact_id": self.artifact_id,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class VersionedAssetReference:
    """Versioned Scenario/Profile/Generator/Simulator identity."""

    asset_id: str
    asset_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        require_identity(self.asset_id, "asset.asset_id")
        require_version(self.asset_version, "asset.asset_version")
        require_fingerprint(self.fingerprint, "asset.fingerprint")

    def as_document(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "asset_version": self.asset_version,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class PublishedScheduleReference:
    """P3/P4 immutable PUBLISHED base required before Simulation starts."""

    schedule_version_version: str
    schedule_version_id: str
    state: str
    content_fingerprint: str

    def __post_init__(self) -> None:
        if self.schedule_version_version not in {
            "schedule-version.v1",
            "schedule-version.v2",
        }:
            reject(
                ExecutionSimulatorFailure.VERSION_MISMATCH,
                "base_schedule_version.schedule_version_version",
                "unsupported ScheduleVersion carrier",
            )
        require_identity(
            self.schedule_version_id, "base_schedule_version.schedule_version_id"
        )
        if self.state != "PUBLISHED":
            reject(
                ExecutionSimulatorFailure.SOURCE_MISMATCH,
                "base_schedule_version.state",
                "Execution Simulator requires an exact PUBLISHED base",
            )
        require_fingerprint(
            self.content_fingerprint,
            "base_schedule_version.content_fingerprint",
        )

    def as_document(self) -> dict[str, object]:
        return {
            "schedule_version_version": self.schedule_version_version,
            "schedule_version_id": self.schedule_version_id,
            "state": self.state,
            "content_fingerprint": self.content_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class PlanningPolicyReference:
    planning_policy_version: str
    policy_id: str
    policy_revision: str
    policy_fingerprint: str

    def __post_init__(self) -> None:
        if self.planning_policy_version != "planning-policy.v2":
            reject(
                ExecutionSimulatorFailure.VERSION_MISMATCH,
                "planning_policy.planning_policy_version",
                "unsupported PlanningPolicy carrier",
            )
        require_identity(self.policy_id, "planning_policy.policy_id")
        require_version(self.policy_revision, "planning_policy.policy_revision")
        require_fingerprint(
            self.policy_fingerprint, "planning_policy.policy_fingerprint"
        )

    def as_document(self) -> dict[str, object]:
        return {
            "planning_policy_version": self.planning_policy_version,
            "policy_id": self.policy_id,
            "policy_revision": self.policy_revision,
            "policy_fingerprint": self.policy_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class SolveLimitsReference:
    solve_limits_version: str
    limits_id: str
    limits_revision: str
    limits_fingerprint: str
    max_wall_time_seconds: int
    max_workers: int
    random_seed: int

    def __post_init__(self) -> None:
        if self.solve_limits_version != "solve-limits.v1":
            reject(
                ExecutionSimulatorFailure.VERSION_MISMATCH,
                "solve_limits.solve_limits_version",
                "unsupported SolveLimits carrier",
            )
        require_identity(self.limits_id, "solve_limits.limits_id")
        require_version(self.limits_revision, "solve_limits.limits_revision")
        require_fingerprint(self.limits_fingerprint, "solve_limits.limits_fingerprint")
        if (
            isinstance(self.max_wall_time_seconds, bool)
            or not isinstance(self.max_wall_time_seconds, int)
            or self.max_wall_time_seconds <= 0
        ):
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "solve_limits.max_wall_time_seconds",
                "must be a positive integer",
            )
        if (
            isinstance(self.max_workers, bool)
            or not isinstance(self.max_workers, int)
            or self.max_workers <= 0
        ):
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "solve_limits.max_workers",
                "must be a positive integer",
            )
        require_non_negative_integer(self.random_seed, "solve_limits.random_seed")

    def as_document(self) -> dict[str, object]:
        return {
            "solve_limits_version": self.solve_limits_version,
            "limits_id": self.limits_id,
            "limits_revision": self.limits_revision,
            "limits_fingerprint": self.limits_fingerprint,
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "max_workers": self.max_workers,
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True, slots=True)
class VirtualClock:
    """Wall-clock-free, second-precision Simulation time projection."""

    clock_version: str
    origin_at_utc: str
    resolution_seconds: int

    def __post_init__(self) -> None:
        if self.clock_version != VIRTUAL_CLOCK_VERSION:
            reject(
                ExecutionSimulatorFailure.VERSION_MISMATCH,
                "virtual_clock.clock_version",
                "unsupported virtual-clock version",
            )
        try:
            origin = parse_utc_instant(self.origin_at_utc)
        except ContractValueError as error:
            raise ExecutionSimulatorError(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                field="virtual_clock.origin_at_utc",
                message="must be an RFC3339 UTC instant",
            ) from error
        if origin.microsecond:
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "virtual_clock.origin_at_utc",
                "must use whole-second precision",
            )
        if (
            isinstance(self.resolution_seconds, bool)
            or not isinstance(self.resolution_seconds, int)
            or self.resolution_seconds <= 0
        ):
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "virtual_clock.resolution_seconds",
                "must be a positive integer",
            )

    def as_document(self, *, schedule_fingerprint: str) -> dict[str, object]:
        return {
            "clock_version": self.clock_version,
            "origin_at_utc": self.origin_at_utc,
            "resolution_seconds": self.resolution_seconds,
            "schedule_fingerprint": require_fingerprint(
                schedule_fingerprint, "virtual_clock.schedule_fingerprint"
            ),
        }


@dataclass(frozen=True, slots=True)
class ScheduledExecutionEvent:
    """One declarative event at a non-negative virtual-clock offset."""

    event_key: str
    offset_seconds: int
    event_type: str
    payload_bytes: bytes

    def __post_init__(self) -> None:
        require_identity(self.event_key, "event.event_key")
        require_non_negative_integer(self.offset_seconds, "event.offset_seconds")
        if self.event_type not in SUPPORTED_EVENT_TYPES:
            reject(
                ExecutionSimulatorFailure.VERSION_MISMATCH,
                "event.event_type",
                "unsupported ExecutionEvent type",
            )
        try:
            payload = json.loads(self.payload_bytes)
        except (TypeError, ValueError) as error:
            raise ExecutionSimulatorError(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                field="event.payload",
                message="must be canonical JSON object bytes",
            ) from error
        if not isinstance(payload, dict) or payload.get("kind") != self.event_type:
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "event.payload.kind",
                "must equal event_type",
            )
        if canonical_contract_bytes(payload) != self.payload_bytes:
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "event.payload",
                "must use canonical-json.v1 bytes",
            )

    @classmethod
    def create(
        cls,
        *,
        event_key: str,
        offset_seconds: int,
        event_type: str,
        payload: dict[str, object],
    ) -> ScheduledExecutionEvent:
        return cls(
            event_key=event_key,
            offset_seconds=offset_seconds,
            event_type=event_type,
            payload_bytes=canonical_contract_bytes(payload),
        )

    def payload_document(self) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self.payload_bytes))

    def as_document(self) -> dict[str, object]:
        return {
            "event_key": self.event_key,
            "offset_seconds": self.offset_seconds,
            "event_type": self.event_type,
            "payload": self.payload_document(),
        }


@dataclass(frozen=True, slots=True)
class VersionedExecutionSchedule:
    """Generic core schedule; P4-10 owns quantitative disruption generation."""

    schedule_version: str
    config_id: str
    config_version: str
    base_schedule_content_fingerprint: str
    scenario_fingerprint: str
    factory_profile_fingerprint: str
    generator_fingerprint: str
    events: tuple[ScheduledExecutionEvent, ...]

    def __post_init__(self) -> None:
        if self.schedule_version != EXECUTION_EVENT_SCHEDULE_VERSION:
            reject(
                ExecutionSimulatorFailure.VERSION_MISMATCH,
                "event_schedule.schedule_version",
                "unsupported execution event schedule",
            )
        require_identity(self.config_id, "event_schedule.config_id")
        require_version(self.config_version, "event_schedule.config_version")
        for field, value in (
            (
                "event_schedule.base_schedule_content_fingerprint",
                self.base_schedule_content_fingerprint,
            ),
            ("event_schedule.scenario_fingerprint", self.scenario_fingerprint),
            (
                "event_schedule.factory_profile_fingerprint",
                self.factory_profile_fingerprint,
            ),
            ("event_schedule.generator_fingerprint", self.generator_fingerprint),
        ):
            require_fingerprint(value, field)
        if not self.events:
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "event_schedule.events",
                "at least one event is required",
            )
        keys = tuple(event.event_key for event in self.events)
        if len(keys) != len(set(keys)):
            reject(
                ExecutionSimulatorFailure.ORDERING_VIOLATION,
                "event_schedule.events[].event_key",
                "must be unique",
            )

    def as_document(self) -> dict[str, object]:
        return {
            "schedule_version": self.schedule_version,
            "config_id": self.config_id,
            "config_version": self.config_version,
            "base_schedule_content_fingerprint": (
                self.base_schedule_content_fingerprint
            ),
            "scenario_fingerprint": self.scenario_fingerprint,
            "factory_profile_fingerprint": self.factory_profile_fingerprint,
            "generator_fingerprint": self.generator_fingerprint,
            "events": [
                event.as_document()
                for event in sorted(self.events, key=lambda item: item.event_key)
            ],
        }

    @property
    def fingerprint(self) -> str:
        return contract_fingerprint(self.as_document())


@dataclass(frozen=True, slots=True)
class ExecutionSimulatorConfig:
    """Complete version/plane/provenance input for one deterministic run."""

    data_plane: str
    environment: str
    production_binding: bool
    synthetic: bool
    factory_id: str
    planning_scope_id: str
    base_schedule_version: PublishedScheduleReference
    base_snapshot: ArtifactReference
    base_problem: ArtifactReference
    scenario: VersionedAssetReference
    factory_profile: VersionedAssetReference
    generator: VersionedAssetReference
    simulator: VersionedAssetReference
    seed: int
    required_capabilities: tuple[str, ...]
    virtual_clock: VirtualClock
    planning_policy: PlanningPolicyReference
    solve_limits: SolveLimitsReference
    code_commit: str

    def __post_init__(self) -> None:
        if (
            self.data_plane != "SIMULATION"
            or self.production_binding is not False
            or self.synthetic is not True
            or self.environment == "PRODUCTION"
        ):
            reject(
                ExecutionSimulatorFailure.PRODUCTION_FORBIDDEN,
                "data_plane/environment/production_binding/synthetic",
                "Execution Simulator is Simulation-only",
            )
        if self.environment not in SUPPORTED_ENVIRONMENTS:
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "environment",
                "unsupported Simulation environment",
            )
        require_identity(self.factory_id, "factory_id")
        require_identity(self.planning_scope_id, "planning_scope_id")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not 0 <= self.seed <= MAX_SEED:
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "seed",
                f"must be an integer from 0 through {MAX_SEED}",
            )
        if self.required_capabilities != tuple(sorted(set(self.required_capabilities))):
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "required_capabilities",
                "must be sorted and unique",
            )
        try:
            require_v1_capability_contract(self.required_capabilities)
        except CapabilityContractError as error:
            raise ExecutionSimulatorError(
                ExecutionSimulatorFailure.VERSION_MISMATCH,
                field="required_capabilities",
                message="contains an unsupported or deferred capability",
            ) from error
        if _COMMIT_RE.fullmatch(self.code_commit) is None:
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "code_commit",
                "must be uncommitted or an exact lowercase Git SHA",
            )

    def as_document(self) -> dict[str, object]:
        return {
            "run_version": EXECUTION_SIMULATOR_RUN_VERSION,
            "data_plane": self.data_plane,
            "environment": self.environment,
            "production_binding": self.production_binding,
            "synthetic": self.synthetic,
            "factory_id": self.factory_id,
            "planning_scope_id": self.planning_scope_id,
            "base_schedule_version": self.base_schedule_version.as_document(),
            "base_snapshot": self.base_snapshot.as_document(),
            "base_problem": self.base_problem.as_document(),
            "scenario": self.scenario.as_document(),
            "factory_profile": self.factory_profile.as_document(),
            "generator": self.generator.as_document(),
            "simulator": self.simulator.as_document(),
            "seed": self.seed,
            "required_capabilities": list(self.required_capabilities),
            "child_seed_derivation_version": CHILD_SEED_DERIVATION_VERSION,
            "virtual_clock": {
                "clock_version": self.virtual_clock.clock_version,
                "origin_at_utc": self.virtual_clock.origin_at_utc,
                "resolution_seconds": self.virtual_clock.resolution_seconds,
            },
            "planning_policy": self.planning_policy.as_document(),
            "solve_limits": self.solve_limits.as_document(),
            "code_commit": self.code_commit,
        }


@dataclass(frozen=True, slots=True)
class ExecutionSimulatorCheckpoint:
    """Restart evidence for one exact run prefix; not a business state."""

    checkpoint_version: str
    run_fingerprint: str
    last_emitted_position: int
    prefix_fingerprint: str

    def __post_init__(self) -> None:
        if self.checkpoint_version != "execution-simulator-checkpoint.v1":
            reject(
                ExecutionSimulatorFailure.VERSION_MISMATCH,
                "checkpoint.checkpoint_version",
                "unsupported Simulator checkpoint version",
            )
        require_fingerprint(self.run_fingerprint, "checkpoint.run_fingerprint")
        require_non_negative_integer(
            self.last_emitted_position, "checkpoint.last_emitted_position"
        )
        require_fingerprint(self.prefix_fingerprint, "checkpoint.prefix_fingerprint")


__all__ = [
    "ArtifactReference",
    "CHILD_SEED_DERIVATION_VERSION",
    "EXECUTION_EVENT_SCHEDULE_VERSION",
    "EXECUTION_SIMULATOR_RUN_VERSION",
    "ExecutionSimulatorCheckpoint",
    "ExecutionSimulatorConfig",
    "ExecutionSimulatorError",
    "ExecutionSimulatorFailure",
    "PlanningPolicyReference",
    "PublishedScheduleReference",
    "ScheduledExecutionEvent",
    "SolveLimitsReference",
    "SUPPORTED_ENVIRONMENTS",
    "SUPPORTED_EVENT_TYPES",
    "VIRTUAL_CLOCK_VERSION",
    "VersionedAssetReference",
    "VersionedExecutionSchedule",
    "VirtualClock",
    "reject",
    "require_fingerprint",
]
