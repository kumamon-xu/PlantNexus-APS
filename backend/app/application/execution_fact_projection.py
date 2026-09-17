"""P4 ExecutionEvent ingress and atomic fact/Snapshot projection services."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol, cast

from app.data_validation import validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.domain.execution_fact_projection import (
    BASE_SNAPSHOT_SOURCE,
    EVENT_AUTHORITY_SOURCE,
    EVENT_STREAM_SOURCE,
    ExecutionFactProjectionError,
    ProjectedFactBatch,
    ProjectionFailure,
    ProjectionScope,
    UrgentPriorityFact,
    project_execution_event_batch,
    validate_event_prefix,
    validate_execution_event,
)
from app.domain.execution_contracts import event_stream_fingerprint
from app.importers.urgent_demand import UrgentDemandImport
from app.normalization import UnitConversionRegistry, expand_orders, normalize_import
from app.snapshots import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    build_planning_snapshot,
    verify_snapshot,
)
from app.snapshots.projection import build_projected_snapshot


class WriteResultPort(Protocol):
    @property
    def replayed(self) -> bool: ...


class ArtifactReferencePort(Protocol):
    @property
    def document_version(self) -> str: ...

    @property
    def artifact_id(self) -> str: ...

    @property
    def fingerprint(self) -> str: ...


class ProjectionCheckpointPort(Protocol):
    @property
    def factory_id(self) -> str: ...

    @property
    def planning_scope_id(self) -> str: ...

    @property
    def authority_id(self) -> str: ...

    @property
    def stream_id(self) -> str: ...

    @property
    def stream_version(self) -> str: ...

    @property
    def last_applied_position(self) -> int: ...

    @property
    def prefix_fingerprint(self) -> str: ...

    @property
    def fact_checkpoint(self) -> ArtifactReferencePort: ...

    @property
    def updated_at_utc(self) -> str: ...


class StoredProjectionCheckpointPort(Protocol):
    @property
    def checkpoint(self) -> ProjectionCheckpointPort: ...

    @property
    def state_revision(self) -> int: ...


class CheckpointWriteResultPort(Protocol):
    @property
    def checkpoint(self) -> ProjectionCheckpointPort: ...

    @property
    def replayed(self) -> bool: ...

    @property
    def state_revision(self) -> int: ...


class AuditRecordPort(Protocol):
    @property
    def audit_record_id(self) -> str: ...


class ExecutionEventRepositoryPort(Protocol):
    def append_in_transaction(
        self, connection: Any, document: Mapping[str, object]
    ) -> WriteResultPort: ...

    def list_stream_in_transaction(
        self,
        connection: Any,
        *,
        authority_id: str,
        stream_id: str,
        stream_version: str,
        after_position: int = 0,
    ) -> tuple[dict[str, object], ...]: ...


class ProjectionCheckpointRepositoryPort(Protocol):
    def get_scope_in_transaction(
        self,
        connection: Any,
        *,
        factory_id: str,
        planning_scope_id: str,
        authority_id: str,
        stream_id: str,
        stream_version: str,
    ) -> StoredProjectionCheckpointPort | None: ...

    def put_initial_in_transaction(
        self, connection: Any, checkpoint: Any
    ) -> CheckpointWriteResultPort: ...

    def advance_in_transaction(
        self,
        connection: Any,
        *,
        expected_position: int,
        expected_state_revision: int,
        checkpoint: Any,
    ) -> CheckpointWriteResultPort: ...


class AuditRepositoryPort(Protocol):
    def append_in_transaction(
        self, connection: Any, record: Any
    ) -> WriteResultPort: ...


class SnapshotRepositoryPort(Protocol):
    def put_in_transaction(
        self, connection: Any, snapshot: ImmutablePlanningSnapshot
    ) -> WriteResultPort: ...

    def get_by_id_in_transaction(
        self, connection: Any, snapshot_id: str
    ) -> ImmutablePlanningSnapshot | None: ...


class CheckpointFactory(Protocol):
    def __call__(
        self,
        *,
        factory_id: str,
        planning_scope_id: str,
        authority_id: str,
        stream_id: str,
        stream_version: str,
        last_applied_position: int,
        prefix_fingerprint: str,
        fact_document_version: str,
        fact_artifact_id: str,
        fact_fingerprint: str,
        updated_at_utc: str,
    ) -> ProjectionCheckpointPort: ...


class AuditFactory(Protocol):
    def __call__(
        self,
        *,
        action: str,
        aggregate_type: str,
        aggregate_id: str,
        correlation_id: str,
        idempotency_scope: str,
        idempotency_key_reference: str,
        request_fingerprint: str | None,
        occurred_at_utc: str,
    ) -> AuditRecordPort: ...


TransactionFactory = Callable[[], AbstractContextManager[Any]]


@dataclass(frozen=True, slots=True)
class ExecutionEventIngressResult:
    event_id: str
    event_fingerprint: str
    replayed: bool
    audit_record_id: str
    audit_replayed: bool


@dataclass(frozen=True, slots=True)
class FactProjectionCommitResult:
    snapshot: ImmutablePlanningSnapshot
    checkpoint: ProjectionCheckpointPort
    replayed: bool
    checkpoint_state_revision: int
    event_ids: tuple[str, ...]
    priority_facts: tuple[UrgentPriorityFact, ...]
    audit_record_id: str | None


def _projection_error(
    reason: ProjectionFailure, *, field: str, message: str
) -> ExecutionFactProjectionError:
    return ExecutionFactProjectionError(reason, field=field, message=message)


class ExecutionFactProjectionService:
    """Compose the two ADR-0013 transactions without Solver or Version work."""

    def __init__(
        self,
        *,
        transaction_factory: TransactionFactory,
        scope: ProjectionScope,
        events: ExecutionEventRepositoryPort,
        checkpoints: ProjectionCheckpointRepositoryPort,
        audits: AuditRepositoryPort,
        snapshots: SnapshotRepositoryPort,
        checkpoint_factory: CheckpointFactory,
        audit_factory: AuditFactory,
        persistence_error_types: tuple[type[Exception], ...],
        unit_registry: UnitConversionRegistry | None = None,
    ) -> None:
        if not persistence_error_types:
            raise ValueError("persistence_error_types cannot be empty")
        self._transaction_factory = transaction_factory
        self._scope = scope
        self._unit_registry = unit_registry
        self._events = events
        self._checkpoints = checkpoints
        self._audits = audits
        self._snapshots = snapshots
        self._checkpoint_factory = checkpoint_factory
        self._audit_factory = audit_factory
        self._persistence_error_types = persistence_error_types

    @property
    def scope(self) -> ProjectionScope:
        return self._scope

    def ingest_event(
        self, document: Mapping[str, object]
    ) -> ExecutionEventIngressResult:
        """Atomically append one exact ledger event and its durable disposition."""

        validate_execution_event(document, scope=self._scope)
        event_id = cast(str, document["event_id"])
        fingerprint = cast(str, document["event_fingerprint"])
        audit = self._audit_factory(
            action="EXECUTION_EVENT_APPENDED",
            aggregate_type="EXECUTION_EVENT",
            aggregate_id=event_id,
            correlation_id=cast(str, document["correlation_id"]),
            idempotency_scope=(
                "SIMULATION/EXECUTION_EVENT_APPEND/"
                f"{self._scope.factory_id}/{self._scope.planning_scope_id}/{event_id}"
            ),
            idempotency_key_reference=fingerprint,
            request_fingerprint=fingerprint,
            occurred_at_utc=cast(str, document["received_at_utc"]),
        )
        try:
            with self._transaction_factory() as connection:
                event_write = self._events.append_in_transaction(connection, document)
                audit_write = self._audits.append_in_transaction(connection, audit)
        except ExecutionFactProjectionError:
            raise
        except self._persistence_error_types as error:
            raise _projection_error(
                ProjectionFailure.PERSISTENCE_FAILED,
                field="event_ingress_transaction",
                message="ExecutionEvent ingress transaction failed",
            ) from error
        return ExecutionEventIngressResult(
            event_id=event_id,
            event_fingerprint=fingerprint,
            replayed=event_write.replayed,
            audit_record_id=audit.audit_record_id,
            audit_replayed=audit_write.replayed,
        )

    def _standard_urgent_snapshot(
        self,
        urgent_import: UrgentDemandImport,
        *,
        cutoff_at_utc: str,
    ) -> ImmutablePlanningSnapshot:
        if self._unit_registry is None:
            raise _projection_error(
                ProjectionFailure.URGENT_IMPORT_REQUIRED,
                field="unit_registry",
                message="Urgent Demand requires the versioned standard unit registry",
            )
        try:
            normalization = normalize_import(
                urgent_import.inputs,
                unit_registry=self._unit_registry,
            )
            import_document = cast(ImportPackageDocumentV2, normalization.document)
            quality = validate_import_package(import_document)
            if not quality.passed:
                raise _projection_error(
                    ProjectionFailure.URGENT_IMPORT_MISMATCH,
                    field="import_quality_report",
                    message="Urgent Demand standard Data Validation did not PASS",
                )
            expansion = expand_orders(import_document, quality.document)
            snapshot = build_planning_snapshot(
                import_document,
                quality.document,
                expansion,
                cutoff_at_utc=cutoff_at_utc,
            )
        except ExecutionFactProjectionError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise _projection_error(
                ProjectionFailure.URGENT_IMPORT_MISMATCH,
                field=getattr(error, "field", "urgent_import"),
                message="Urgent Demand failed the standard Import/Validation chain",
            ) from error
        if snapshot.data_plane is not SnapshotDataPlane.SIMULATION:
            raise _projection_error(
                ProjectionFailure.AUTHORITY_MISMATCH,
                field="urgent_import.data_plane",
                message="P4 urgent projection is Simulation-only",
            )
        return snapshot

    def _stored_base(
        self,
        connection: Any,
        base_snapshot: ImmutablePlanningSnapshot,
    ) -> ImmutablePlanningSnapshot:
        stored = self._snapshots.get_by_id_in_transaction(
            connection, base_snapshot.snapshot_id
        )
        if stored is None or stored != base_snapshot:
            raise _projection_error(
                ProjectionFailure.STALE_SNAPSHOT,
                field="base_snapshot",
                message="base Snapshot is absent or differs from immutable storage",
            )
        return stored

    def _checkpoint(self, connection: Any) -> StoredProjectionCheckpointPort | None:
        return self._checkpoints.get_scope_in_transaction(
            connection,
            factory_id=self._scope.factory_id,
            planning_scope_id=self._scope.planning_scope_id,
            authority_id=self._scope.authority_id,
            stream_id=self._scope.stream_id,
            stream_version=self._scope.stream_version,
        )

    def _checkpoint_snapshot(
        self,
        connection: Any,
        checkpoint: StoredProjectionCheckpointPort,
    ) -> ImmutablePlanningSnapshot:
        fact = checkpoint.checkpoint.fact_checkpoint
        if fact.document_version != "planning-snapshot.v2":
            raise _projection_error(
                ProjectionFailure.STALE_SNAPSHOT,
                field="projection_checkpoint.fact_checkpoint",
                message="checkpoint does not reference a PlanningSnapshot v2",
            )
        snapshot = self._snapshots.get_by_id_in_transaction(
            connection, fact.artifact_id
        )
        if snapshot is None or snapshot.snapshot_hash != fact.fingerprint:
            raise _projection_error(
                ProjectionFailure.STALE_SNAPSHOT,
                field="projection_checkpoint.fact_checkpoint",
                message="checkpoint Snapshot is absent or has different content",
            )
        return snapshot

    def _snapshot_stream_position(
        self,
        snapshot: ImmutablePlanningSnapshot,
        fingerprints: tuple[str, ...],
    ) -> int:
        source_versions = cast(Mapping[str, str], snapshot.document["source_versions"])
        stream_lineage = source_versions.get(EVENT_STREAM_SOURCE)
        authority_lineage = source_versions.get(EVENT_AUTHORITY_SOURCE)
        if stream_lineage is None:
            if authority_lineage is not None:
                raise _projection_error(
                    ProjectionFailure.STALE_SNAPSHOT,
                    field="base_snapshot.source_versions",
                    message="Snapshot has incomplete execution stream lineage",
                )
            return 0
        expected_prefix = (
            f"{self._scope.stream_id}@{self._scope.stream_version}#position="
        )
        position_text, separator, prefix_fingerprint = stream_lineage.removeprefix(
            expected_prefix
        ).partition("#")
        try:
            position = int(position_text)
        except ValueError as error:
            raise _projection_error(
                ProjectionFailure.STALE_SNAPSHOT,
                field="base_snapshot.source_versions",
                message="Snapshot execution stream position is invalid",
            ) from error
        if (
            not stream_lineage.startswith(expected_prefix)
            or separator != "#"
            or authority_lineage != self._scope.authority_id
            or position < 1
            or position > len(fingerprints)
            or prefix_fingerprint != event_stream_fingerprint(fingerprints[:position])
        ):
            raise _projection_error(
                ProjectionFailure.STALE_SNAPSHOT,
                field="base_snapshot.source_versions",
                message="Snapshot execution stream lineage differs from durable prefix",
            )
        return position

    def _urgent_snapshots(
        self,
        full_prefix: tuple[dict[str, object], ...],
        *,
        after_position: int,
        base_snapshot: ImmutablePlanningSnapshot,
        urgent_imports: Mapping[str, UrgentDemandImport],
    ) -> dict[str, Mapping[str, object]]:
        tail = full_prefix[after_position:]
        tail_ids = {cast(str, event["event_id"]) for event in tail}
        if set(urgent_imports).difference(tail_ids):
            raise _projection_error(
                ProjectionFailure.URGENT_IMPORT_MISMATCH,
                field="urgent_imports",
                message="contains an event outside the unprojected stream tail",
            )
        result: dict[str, Mapping[str, object]] = {}
        current_cutoff = cast(str, base_snapshot.document["cutoff_at_utc"])
        for event in tail:
            occurred = cast(str, event["occurred_at_utc"])
            current_cutoff = max(current_cutoff, occurred)
            if event.get("event_type") != "URGENT_DEMAND_RECEIVED":
                continue
            event_id = cast(str, event["event_id"])
            urgent = urgent_imports.get(event_id)
            if urgent is None or urgent.event_id != event_id:
                raise _projection_error(
                    ProjectionFailure.URGENT_IMPORT_REQUIRED,
                    field="urgent_imports",
                    message="each urgent event requires exact standard Import inputs",
                )
            result[event_id] = self._standard_urgent_snapshot(
                urgent,
                cutoff_at_utc=current_cutoff,
            ).document
        return result

    def project_available(
        self,
        base_snapshot: ImmutablePlanningSnapshot,
        *,
        urgent_imports: Mapping[str, UrgentDemandImport] | None = None,
    ) -> FactProjectionCommitResult:
        """Atomically commit the continuous ledger tail as a new Snapshot."""

        verify_snapshot(base_snapshot)
        if base_snapshot.data_plane is not SnapshotDataPlane.SIMULATION:
            raise _projection_error(
                ProjectionFailure.AUTHORITY_MISMATCH,
                field="base_snapshot.data_plane",
                message="P4 Production projection authority is not established",
            )
        supplied_urgent = urgent_imports or {}
        try:
            with self._transaction_factory() as connection:
                self._stored_base(connection, base_snapshot)
                stored_checkpoint = self._checkpoint(connection)
                after_position = 0
                if stored_checkpoint is not None:
                    after_position = stored_checkpoint.checkpoint.last_applied_position
                full_prefix = self._events.list_stream_in_transaction(
                    connection,
                    authority_id=self._scope.authority_id,
                    stream_id=self._scope.stream_id,
                    stream_version=self._scope.stream_version,
                    after_position=0,
                )
                fingerprints = validate_event_prefix(full_prefix, scope=self._scope)
                base_position = self._snapshot_stream_position(
                    base_snapshot, fingerprints
                )
                if after_position > len(full_prefix):
                    raise _projection_error(
                        ProjectionFailure.ORDERING_VIOLATION,
                        field="projection_checkpoint.last_applied_position",
                        message="checkpoint is beyond the durable event prefix",
                    )
                checkpoint_snapshot: ImmutablePlanningSnapshot | None = None
                if stored_checkpoint is not None:
                    checkpoint_snapshot = self._checkpoint_snapshot(
                        connection, stored_checkpoint
                    )
                    checkpoint_position = self._snapshot_stream_position(
                        checkpoint_snapshot, fingerprints
                    )
                    if checkpoint_position != after_position:
                        raise _projection_error(
                            ProjectionFailure.STALE_SNAPSHOT,
                            field="projection_checkpoint.fact_checkpoint",
                            message="checkpoint Snapshot lineage position is inconsistent",
                        )
                    if checkpoint_snapshot != base_snapshot:
                        checkpoint_sources = cast(
                            Mapping[str, str],
                            checkpoint_snapshot.document["source_versions"],
                        )
                        if (
                            after_position == len(full_prefix)
                            and checkpoint_sources.get(BASE_SNAPSHOT_SOURCE)
                            == base_snapshot.snapshot_hash
                        ):
                            replay_urgent = self._urgent_snapshots(
                                full_prefix,
                                after_position=base_position,
                                base_snapshot=base_snapshot,
                                urgent_imports=supplied_urgent,
                            )
                            replay_projection = project_execution_event_batch(
                                base_snapshot.document,
                                full_prefix=full_prefix,
                                after_position=base_position,
                                scope=self._scope,
                                urgent_snapshots=replay_urgent,
                            )
                            replay_snapshot = build_projected_snapshot(
                                replay_projection.document
                            )
                            if replay_snapshot == checkpoint_snapshot:
                                return FactProjectionCommitResult(
                                    snapshot=checkpoint_snapshot,
                                    checkpoint=stored_checkpoint.checkpoint,
                                    replayed=True,
                                    checkpoint_state_revision=(
                                        stored_checkpoint.state_revision
                                    ),
                                    event_ids=(),
                                    priority_facts=(),
                                    audit_record_id=None,
                                )
                        raise _projection_error(
                            ProjectionFailure.STALE_SNAPSHOT,
                            field="base_snapshot",
                            message=(
                                "caller base is not the current projected Snapshot"
                            ),
                        )
                    if base_position != after_position:
                        raise _projection_error(
                            ProjectionFailure.STALE_SNAPSHOT,
                            field="base_snapshot.source_versions",
                            message="current Snapshot lineage position is inconsistent",
                        )
                elif base_position != 0:
                    raise _projection_error(
                        ProjectionFailure.STALE_SNAPSHOT,
                        field="base_snapshot.source_versions",
                        message="projected Snapshot has no matching durable checkpoint",
                    )
                if after_position == len(full_prefix):
                    if stored_checkpoint is None:
                        raise _projection_error(
                            ProjectionFailure.ORDERING_VIOLATION,
                            field="event_stream",
                            message="no event is available for initial projection",
                        )
                    if supplied_urgent:
                        raise _projection_error(
                            ProjectionFailure.URGENT_IMPORT_MISMATCH,
                            field="urgent_imports",
                            message="no unprojected urgent event exists",
                        )
                    return FactProjectionCommitResult(
                        snapshot=cast(ImmutablePlanningSnapshot, checkpoint_snapshot),
                        checkpoint=stored_checkpoint.checkpoint,
                        replayed=True,
                        checkpoint_state_revision=(stored_checkpoint.state_revision),
                        event_ids=(),
                        priority_facts=(),
                        audit_record_id=None,
                    )
                if stored_checkpoint is not None:
                    expected_prefix = stored_checkpoint.checkpoint.prefix_fingerprint
                    observed_prefix = event_stream_fingerprint(
                        fingerprints[:after_position]
                    )
                    if observed_prefix != expected_prefix:
                        raise _projection_error(
                            ProjectionFailure.ORDERING_VIOLATION,
                            field="projection_checkpoint.prefix_fingerprint",
                            message="durable event prefix no longer matches checkpoint",
                        )
                urgent_snapshots = self._urgent_snapshots(
                    full_prefix,
                    after_position=after_position,
                    base_snapshot=base_snapshot,
                    urgent_imports=supplied_urgent,
                )
                projected: ProjectedFactBatch = project_execution_event_batch(
                    base_snapshot.document,
                    full_prefix=full_prefix,
                    after_position=after_position,
                    scope=self._scope,
                    urgent_snapshots=urgent_snapshots,
                )
                new_snapshot = build_projected_snapshot(projected.document)
                snapshot_write = self._snapshots.put_in_transaction(
                    connection, new_snapshot
                )
                checkpoint = self._checkpoint_factory(
                    factory_id=self._scope.factory_id,
                    planning_scope_id=self._scope.planning_scope_id,
                    authority_id=self._scope.authority_id,
                    stream_id=self._scope.stream_id,
                    stream_version=self._scope.stream_version,
                    last_applied_position=projected.through_position,
                    prefix_fingerprint=projected.stream_fingerprint,
                    fact_document_version="planning-snapshot.v2",
                    fact_artifact_id=new_snapshot.snapshot_id,
                    fact_fingerprint=new_snapshot.snapshot_hash,
                    updated_at_utc=cast(
                        str,
                        full_prefix[projected.through_position - 1]["occurred_at_utc"],
                    ),
                )
                if stored_checkpoint is None:
                    checkpoint_write = self._checkpoints.put_initial_in_transaction(
                        connection, checkpoint
                    )
                else:
                    checkpoint_write = self._checkpoints.advance_in_transaction(
                        connection,
                        expected_position=after_position,
                        expected_state_revision=stored_checkpoint.state_revision,
                        checkpoint=checkpoint,
                    )
                last_event = full_prefix[projected.through_position - 1]
                audit = self._audit_factory(
                    action="PROJECTION_CHECKPOINT_COMMITTED",
                    aggregate_type="PLANNING_SNAPSHOT",
                    aggregate_id=new_snapshot.snapshot_id,
                    correlation_id=cast(str, last_event["correlation_id"]),
                    idempotency_scope=(
                        "SIMULATION/PROJECTION_CHECKPOINT/"
                        f"{self._scope.factory_id}/{self._scope.planning_scope_id}/"
                        f"{self._scope.authority_id}/{self._scope.stream_id}/"
                        f"{self._scope.stream_version}/{projected.through_position}"
                    ),
                    idempotency_key_reference=projected.stream_fingerprint,
                    request_fingerprint=new_snapshot.snapshot_hash,
                    occurred_at_utc=checkpoint.updated_at_utc,
                )
                audit_write = self._audits.append_in_transaction(connection, audit)
                if snapshot_write.replayed != checkpoint_write.replayed or (
                    checkpoint_write.replayed != audit_write.replayed
                ):
                    raise _projection_error(
                        ProjectionFailure.PERSISTENCE_FAILED,
                        field="projection_transaction",
                        message="atomic write replay dispositions diverged",
                    )
        except ExecutionFactProjectionError:
            raise
        except self._persistence_error_types as error:
            raise _projection_error(
                ProjectionFailure.PERSISTENCE_FAILED,
                field="projection_transaction",
                message="fact projection transaction failed",
            ) from error
        return FactProjectionCommitResult(
            snapshot=new_snapshot,
            checkpoint=checkpoint_write.checkpoint,
            replayed=checkpoint_write.replayed,
            checkpoint_state_revision=checkpoint_write.state_revision,
            event_ids=projected.event_ids,
            priority_facts=projected.priority_facts,
            audit_record_id=audit.audit_record_id,
        )


__all__ = [
    "AuditFactory",
    "AuditRecordPort",
    "AuditRepositoryPort",
    "CheckpointFactory",
    "CheckpointWriteResultPort",
    "ExecutionEventRepositoryPort",
    "ExecutionEventIngressResult",
    "ExecutionFactProjectionService",
    "FactProjectionCommitResult",
    "ProjectionCheckpointPort",
    "ProjectionCheckpointRepositoryPort",
    "SnapshotRepositoryPort",
    "StoredProjectionCheckpointPort",
    "TransactionFactory",
    "WriteResultPort",
]
