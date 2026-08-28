"""Deterministic virtual clock, queue, replay, and common-ingress simulator core."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
import json
from typing import Protocol, cast, runtime_checkable

from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    event_stream_fingerprint,
    execution_event_fingerprint,
    require_p4_document,
    simulation_manifest_fingerprint,
)
from app.domain.execution_fact_projection import ProjectionScope, validate_event_prefix
from app.domain.types import format_utc_instant, parse_utc_instant
from app.simulation.generators.determinism import SeedMaterial

from .contracts import (
    CHILD_SEED_DERIVATION_VERSION,
    ExecutionSimulatorCheckpoint,
    ExecutionSimulatorConfig,
    ExecutionSimulatorError,
    ExecutionSimulatorFailure,
    ScheduledExecutionEvent,
    VersionedExecutionSchedule,
    reject,
)


@runtime_checkable
class ExecutionEventIngressPort(Protocol):
    """The only side-effect boundary used by the simulator core.

    ``ExecutionFactProjectionService`` from P4-04 implements this public shape.
    The return value remains owned by that service and is intentionally opaque.
    """

    def ingest_event(self, document: Mapping[str, object]) -> object:
        """Append one already prechecked standard ExecutionEvent."""


@dataclass(frozen=True, slots=True)
class CompiledExecutionStream:
    """Pure, fully prevalidated stream; compiling performs no ingress call."""

    config: ExecutionSimulatorConfig
    schedule: VersionedExecutionSchedule
    run_fingerprint: str
    scope: ProjectionScope
    authority: dict[str, object]
    source_stream: dict[str, object]
    event_keys: tuple[str, ...]
    tie_break_ranks: tuple[int, ...]
    event_bytes: tuple[bytes, ...]

    @property
    def events(self) -> tuple[dict[str, object], ...]:
        return tuple(
            cast(dict[str, object], json.loads(document))
            for document in self.event_bytes
        )

    @property
    def event_ids(self) -> tuple[str, ...]:
        return tuple(cast(str, document["event_id"]) for document in self.events)

    @property
    def event_fingerprints(self) -> tuple[str, ...]:
        return tuple(
            cast(str, document["event_fingerprint"]) for document in self.events
        )

    @property
    def stream_fingerprint(self) -> str:
        return event_stream_fingerprint(self.event_fingerprints)

    def initial_checkpoint(self) -> ExecutionSimulatorCheckpoint:
        return ExecutionSimulatorCheckpoint(
            checkpoint_version="execution-simulator-checkpoint.v1",
            run_fingerprint=self.run_fingerprint,
            last_emitted_position=0,
            prefix_fingerprint=event_stream_fingerprint(()),
        )


@dataclass(frozen=True, slots=True)
class ExecutionSimulationResult:
    """One completed prefix and its restart/manifest evidence."""

    compiled: CompiledExecutionStream
    through_position: int
    emitted_positions: tuple[int, ...]
    checkpoint: ExecutionSimulatorCheckpoint

    @property
    def event_bytes(self) -> tuple[bytes, ...]:
        return self.compiled.event_bytes[: self.through_position]

    @property
    def events(self) -> tuple[dict[str, object], ...]:
        return tuple(
            cast(dict[str, object], json.loads(document))
            for document in self.event_bytes
        )

    @property
    def event_ids(self) -> tuple[str, ...]:
        return tuple(cast(str, event["event_id"]) for event in self.events)

    @property
    def event_fingerprints(self) -> tuple[str, ...]:
        return tuple(
            cast(str, event["event_fingerprint"]) for event in self.events
        )

    @property
    def stream_fingerprint(self) -> str:
        return event_stream_fingerprint(self.event_fingerprints)

    def build_manifest(self, *, fact_checkpoint: object) -> dict[str, object]:
        """Build the existing P4-02 carrier from an explicit downstream checkpoint.

        The simulator never reads or writes fact storage.  Its caller must supply
        a validated ``ArtifactReference`` after the P4-04 projection handoff.
        """

        from .contracts import ArtifactReference

        if not isinstance(fact_checkpoint, ArtifactReference):
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "fact_checkpoint",
                "must be an explicit ArtifactReference",
            )
        config = self.compiled.config
        manifest: dict[str, object] = {
            "execution_simulation_manifest_version": (
                "execution-simulation-manifest.v1"
            ),
            "schema_set_version": "2.8.0",
            "canonicalization_version": "canonical-json.v1",
            "manifest_id": "pending",
            "manifest_fingerprint": "pending",
            "data_plane": config.data_plane,
            "environment": config.environment,
            "factory_id": config.factory_id,
            "planning_scope_id": config.planning_scope_id,
            "production_binding": config.production_binding,
            "synthetic": config.synthetic,
            "synthetic_provenance": _synthetic_provenance(config),
            "base_schedule_version": config.base_schedule_version.as_document(),
            "base_snapshot": config.base_snapshot.as_document(),
            "base_problem": config.base_problem.as_document(),
            "scenario": config.scenario.as_document(),
            "factory_profile": config.factory_profile.as_document(),
            "generator": config.generator.as_document(),
            "simulator": config.simulator.as_document(),
            "seed": config.seed,
            "child_seed_derivation_version": CHILD_SEED_DERIVATION_VERSION,
            "virtual_clock": config.virtual_clock.as_document(
                schedule_fingerprint=self.compiled.schedule.fingerprint
            ),
            "authority": dict(self.compiled.authority),
            "source_stream": dict(self.compiled.source_stream),
            "planning_policy": config.planning_policy.as_document(),
            "solve_limits": config.solve_limits.as_document(),
            "event_stream": {
                "event_count": self.through_position,
                "first_position": 1,
                "last_position": self.through_position,
                "ordered_event_ids": list(self.event_ids),
                "ordered_event_fingerprints": list(self.event_fingerprints),
                "stream_fingerprint": self.stream_fingerprint,
            },
            "checkpoint": {
                "checkpoint_version": "execution-checkpoint.v1",
                "last_applied_position": self.through_position,
                "prefix_fingerprint": self.stream_fingerprint,
                "fact_checkpoint": fact_checkpoint.as_document(),
            },
            "code_commit": config.code_commit,
        }
        fingerprint = simulation_manifest_fingerprint(manifest)
        manifest["manifest_fingerprint"] = fingerprint
        manifest["manifest_id"] = (
            "execution-simulation-" + fingerprint.removeprefix("sha256:")
        )
        require_p4_document(manifest)
        return manifest


def _synthetic_provenance(config: ExecutionSimulatorConfig) -> dict[str, object]:
    return {
        "scenario_id": config.scenario.asset_id,
        "scenario_version": config.scenario.asset_version,
        "factory_profile_id": config.factory_profile.asset_id,
        "profile_version": config.factory_profile.asset_version,
        "generator_id": config.generator.asset_id,
        "generator_version": config.generator.asset_version,
        "simulator_id": config.simulator.asset_id,
        "simulator_version": config.simulator.asset_version,
        "seed": config.seed,
    }


def _entity_references(
    event_type: str, payload: Mapping[str, object]
) -> list[dict[str, object]]:
    def reference(entity_type: str, field: str) -> tuple[str, str]:
        value = payload.get(field)
        if not isinstance(value, str):
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                f"payload.{field}",
                "must be a canonical identifier",
            )
        return entity_type, value

    if event_type in {"OPERATION_STARTED", "OPERATION_COMPLETED"}:
        values = {
            reference("OPERATION", "operation_id"),
            reference("RESOURCE", "resource_id"),
        }
    elif event_type in {
        "PROCESSING_DURATION_CHANGED",
        "PROCESSING_REMAINING_CHANGED",
    }:
        values = {reference("OPERATION", "operation_id")}
    elif event_type in {"MACHINE_UNAVAILABLE", "MACHINE_RECOVERED"}:
        values = {reference("RESOURCE", "resource_id")}
    elif event_type in {"MATERIAL_READY", "MATERIAL_DELAYED"}:
        values = {reference("MATERIAL", "material_id")}
    elif event_type == "URGENT_DEMAND_RECEIVED":
        values = {reference("DEMAND_ORDER", "demand_order_id")}
    elif event_type == "LOCK_CREATED":
        values = {
            reference("OPERATION", "operation_id"),
            reference("RESOURCE", "resource_id"),
            reference("OPERATION_LOCK", "lock_id"),
        }
    else:
        values = {reference("OPERATION_LOCK", "lock_id")}
    return [
        {"entity_type": entity_type, "entity_id": entity_id}
        for entity_type, entity_id in sorted(values)
    ]


def _binding_guard(
    config: ExecutionSimulatorConfig, schedule: VersionedExecutionSchedule
) -> None:
    bindings = {
        "base_schedule_content_fingerprint": (
            config.base_schedule_version.content_fingerprint,
            schedule.base_schedule_content_fingerprint,
        ),
        "scenario_fingerprint": (
            config.scenario.fingerprint,
            schedule.scenario_fingerprint,
        ),
        "factory_profile_fingerprint": (
            config.factory_profile.fingerprint,
            schedule.factory_profile_fingerprint,
        ),
        "generator_fingerprint": (
            config.generator.fingerprint,
            schedule.generator_fingerprint,
        ),
    }
    for field, (expected, observed) in bindings.items():
        if observed != expected:
            reject(
                ExecutionSimulatorFailure.SOURCE_MISMATCH,
                f"event_schedule.{field}",
                "does not match the exact run input",
            )
    for event in schedule.events:
        if event.offset_seconds % config.virtual_clock.resolution_seconds:
            reject(
                ExecutionSimulatorFailure.ORDERING_VIOLATION,
                f"event_schedule.events[{event.event_key}].offset_seconds",
                "must align to the virtual-clock resolution",
            )


def _run_fingerprint(
    config: ExecutionSimulatorConfig, schedule: VersionedExecutionSchedule
) -> str:
    return contract_fingerprint(
        {
            "execution_simulator_run_version": "execution-simulator-run.v1",
            "config": config.as_document(),
            "event_schedule_fingerprint": schedule.fingerprint,
        }
    )


def _run_authority(
    config: ExecutionSimulatorConfig, run_fingerprint: str
) -> tuple[ProjectionScope, dict[str, object], dict[str, object]]:
    suffix = run_fingerprint.removeprefix("sha256:")
    authority_id = f"authority-execution-simulator-{suffix}"
    stream_id = f"execution-stream-{suffix}"
    authority: dict[str, object] = {
        "authority_version": "execution-event-authority.v1",
        "authority_id": authority_id,
        "authority_scope": (
            f"SIMULATION/{config.factory_id}/{config.planning_scope_id}"
        ),
        "source": {
            "source_system": "plantnexus-execution-simulator",
            "source_version": config.simulator.asset_version,
            "source_record_id": stream_id,
        },
        "decision": "AUTHORIZED_SIMULATION_SOURCE",
        "production_binding": False,
    }
    source_stream: dict[str, object] = {
        "stream_id": stream_id,
        "stream_version": config.simulator.asset_version,
        "authority_id": authority_id,
    }
    scope = ProjectionScope(
        factory_id=config.factory_id,
        planning_scope_id=config.planning_scope_id,
        authority_id=authority_id,
        stream_id=stream_id,
        stream_version=config.simulator.asset_version,
    )
    return scope, authority, source_stream


def _event_document(
    *,
    config: ExecutionSimulatorConfig,
    scheduled: ScheduledExecutionEvent,
    position: int,
    occurred_at_utc: str,
    authority: Mapping[str, object],
    source_stream: Mapping[str, object],
    run_fingerprint: str,
) -> dict[str, object]:
    event_key_hash = sha256(scheduled.event_key.encode("utf-8")).hexdigest()[:16]
    payload = scheduled.payload_document()
    document: dict[str, object] = {
        "execution_event_version": "execution-event.v1",
        "schema_set_version": "2.8.0",
        "canonicalization_version": "canonical-json.v1",
        "event_id": "pending",
        "event_type": scheduled.event_type,
        "data_plane": config.data_plane,
        "environment": config.environment,
        "factory_id": config.factory_id,
        "planning_scope_id": config.planning_scope_id,
        "authority": dict(authority),
        "source_stream": dict(source_stream),
        "source_position": position,
        "occurred_at_utc": occurred_at_utc,
        "received_at_utc": occurred_at_utc,
        "entity_refs": _entity_references(scheduled.event_type, payload),
        "payload": payload,
        "synthetic": config.synthetic,
        "synthetic_provenance": _synthetic_provenance(config),
        "production_binding": config.production_binding,
        "correlation_id": (
            "execution-simulation-"
            f"{run_fingerprint.removeprefix('sha256:')[:32]}-{event_key_hash}"
        ),
        "event_fingerprint": "pending",
    }
    fingerprint = execution_event_fingerprint(document)
    document["event_fingerprint"] = fingerprint
    document["event_id"] = "execution-event-" + fingerprint.removeprefix("sha256:")
    return document


class ExecutionSimulator:
    """Compile and dispatch deterministic standard events through one port."""

    def compile(
        self,
        config: ExecutionSimulatorConfig,
        schedule: VersionedExecutionSchedule,
    ) -> CompiledExecutionStream:
        """Prevalidate the complete stream before any downstream side effect."""

        _binding_guard(config, schedule)
        run_fingerprint = _run_fingerprint(config, schedule)
        scope, authority, source_stream = _run_authority(config, run_fingerprint)
        queue_seed = SeedMaterial(
            root_seed=config.seed,
            generator_id=config.simulator.asset_id,
            generator_version=config.simulator.asset_version,
        ).child("execution-event-queue")
        queue = sorted(
            (
                (
                    event.offset_seconds,
                    queue_seed.child(event.event_key).derive_uint64("tie-break"),
                    event.event_key,
                    event,
                )
                for event in schedule.events
            ),
            key=lambda item: (item[0], item[1], item[2]),
        )
        origin = parse_utc_instant(config.virtual_clock.origin_at_utc)
        documents = tuple(
            _event_document(
                config=config,
                scheduled=item[3],
                position=position,
                occurred_at_utc=format_utc_instant(
                    origin + timedelta(seconds=item[0])
                ),
                authority=authority,
                source_stream=source_stream,
                run_fingerprint=run_fingerprint,
            )
            for position, item in enumerate(queue, start=1)
        )
        try:
            validate_event_prefix(documents, scope=scope)
        except ValueError as error:
            raise ExecutionSimulatorError(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                field="event_schedule.events",
                message="compiled stream failed the P4-04 event contract",
            ) from error
        return CompiledExecutionStream(
            config=config,
            schedule=schedule,
            run_fingerprint=run_fingerprint,
            scope=scope,
            authority=authority,
            source_stream=source_stream,
            event_keys=tuple(item[2] for item in queue),
            tie_break_ranks=tuple(item[1] for item in queue),
            event_bytes=tuple(canonical_contract_bytes(document) for document in documents),
        )

    def run(
        self,
        config: ExecutionSimulatorConfig,
        schedule: VersionedExecutionSchedule,
        ingress: ExecutionEventIngressPort,
        *,
        checkpoint: ExecutionSimulatorCheckpoint | None = None,
        max_events: int | None = None,
    ) -> ExecutionSimulationResult:
        """Dispatch one deterministic prefix only through ``ingress.ingest_event``."""

        compiled = self.compile(config, schedule)
        current = checkpoint or compiled.initial_checkpoint()
        expected_prefix = event_stream_fingerprint(
            compiled.event_fingerprints[: current.last_emitted_position]
        )
        if (
            current.run_fingerprint != compiled.run_fingerprint
            or current.last_emitted_position > len(compiled.event_bytes)
            or current.prefix_fingerprint != expected_prefix
        ):
            reject(
                ExecutionSimulatorFailure.CHECKPOINT_MISMATCH,
                "checkpoint",
                "does not match the exact run prefix",
            )
        if (
            max_events is not None
            and (
                isinstance(max_events, bool)
                or not isinstance(max_events, int)
                or max_events <= 0
            )
        ):
            reject(
                ExecutionSimulatorFailure.INVALID_CONFIG,
                "max_events",
                "must be a positive integer when provided",
            )
        stop = len(compiled.event_bytes)
        if max_events is not None:
            stop = min(stop, current.last_emitted_position + max_events)
        emitted_positions: list[int] = []
        for index in range(current.last_emitted_position, stop):
            document = cast(dict[str, object], json.loads(compiled.event_bytes[index]))
            try:
                ingress.ingest_event(document)
            except Exception as error:
                raise ExecutionSimulatorError(
                    ExecutionSimulatorFailure.INGRESS_REJECTED,
                    field=f"event_stream.position[{index + 1}]",
                    message="the common ExecutionEvent ingress rejected the event",
                ) from error
            emitted_positions.append(index + 1)
        prefix_fingerprint = event_stream_fingerprint(
            compiled.event_fingerprints[:stop]
        )
        next_checkpoint = ExecutionSimulatorCheckpoint(
            checkpoint_version="execution-simulator-checkpoint.v1",
            run_fingerprint=compiled.run_fingerprint,
            last_emitted_position=stop,
            prefix_fingerprint=prefix_fingerprint,
        )
        return ExecutionSimulationResult(
            compiled=compiled,
            through_position=stop,
            emitted_positions=tuple(emitted_positions),
            checkpoint=next_checkpoint,
        )


__all__ = [
    "CompiledExecutionStream",
    "ExecutionEventIngressPort",
    "ExecutionSimulationResult",
    "ExecutionSimulator",
]
