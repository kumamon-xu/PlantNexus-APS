"""Replan source binding over the existing PlanningRun persistence owner."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from hashlib import sha256
import json
from typing import Any

from sqlalchemy import (
    select,
    insert,
    text,
    Table,
    Column,
    String,
    LargeBinary,
    MetaData,
)
from sqlalchemy.engine import Connection, Engine

from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.domain.planning_run import PlanningRunAggregate, PlanningRunErrorCode, reject
from app.infrastructure.planning_run_repository import (
    SqlAlchemyPlanningRunRepository,
    _PLANNING_RUNS,
)
from app.infrastructure.replan_repository import SqlAlchemyReplanRequestRepository
from app.infrastructure.workspace_persistence import WorkspaceDataPlane

_CHECKPOINTS = Table(
    "runtime_replan_checkpoints",
    MetaData(),
    Column("work_item_id", String(256), primary_key=True),
    Column("planning_run_id", String(256)),
    Column("data_plane", String(16)),
    Column("document_json", LargeBinary),
    Column("document_sha256", String(64)),
)
_REPLAN_RUNS = _PLANNING_RUNS.to_metadata(MetaData())
_REPLAN_RUNS.append_column(Column("replan_request_id", String(256), nullable=True))


class ReplanCheckpointRepository:
    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def get(self, work_item_id: str) -> Any:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(_CHECKPOINTS).where(
                        _CHECKPOINTS.c.work_item_id == work_item_id,
                        _CHECKPOINTS.c.data_plane == "SIMULATION",
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        raw = bytes(row["document_json"])
        doc = json.loads(raw)
        if (
            sha256(raw).hexdigest() != row["document_sha256"]
            or doc["work_item_id"] != work_item_id
            or doc["planning_run_id"] != row["planning_run_id"]
            or canonical_json_bytes(doc) != raw
            or canonical_fingerprint(
                {k: v for k, v in doc.items() if k != "fingerprint"}
            )
            != doc["fingerprint"]
        ):
            raise ValueError("Stored replan checkpoint integrity failed")
        return doc

    def put(self, document: Any) -> Any:
        document = {**document, "fingerprint": canonical_fingerprint(document)}
        previous = self.get(document["work_item_id"])
        if previous is not None:
            if previous != document:
                raise ValueError("Replan checkpoint conflicts with existing evidence")
            return previous
        raw = canonical_json_bytes(document)
        with self.engine.begin() as connection:
            connection.execute(
                insert(_CHECKPOINTS).values(
                    work_item_id=document["work_item_id"],
                    planning_run_id=document["planning_run_id"],
                    data_plane="SIMULATION",
                    document_json=raw,
                    document_sha256=sha256(raw).hexdigest(),
                )
            )
        return document


class TransactionEngine:
    """Let existing repository ports participate in a caller-owned transaction."""

    def __init__(self, engine: Engine, connection: Connection) -> None:
        self.engine, self.connection = engine, connection

    @contextmanager
    def begin(self) -> Iterator[Connection]:
        yield self.connection

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        yield self.connection

    def __getattr__(self, name: str) -> Any:
        return getattr(self.engine, name)


class RuntimeReplanRunRepository(SqlAlchemyPlanningRunRepository):
    """Only the explicit replan branch may share an ingress with another run."""

    _run_table = _REPLAN_RUNS

    def _aggregate(self, row: Any) -> PlanningRunAggregate:
        aggregate = super()._aggregate(row)
        frozen = aggregate.prepared_artifacts.get("runtime_replan")
        expected = frozen["request"]["request_id"] if frozen is not None else None
        if row["replan_request_id"] != expected:
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="stored.replan_request_id",
                message="Replan source index differs from immutable input",
            )
        return aggregate

    def __init__(
        self,
        engine: Any,
        *,
        data_plane: WorkspaceDataPlane,
        verify_source: Callable[[Connection, PlanningRunAggregate], None],
    ) -> None:
        super().__init__(engine, data_plane=data_plane)
        self._verify_replan_source = verify_source

    @contextmanager
    def _consistent_read_connection(self) -> Iterator[Connection]:
        if isinstance(self._engine, TransactionEngine):
            yield self._engine.connection
        else:
            with super()._consistent_read_connection() as connection:
                yield connection

    @staticmethod
    def _run_values(aggregate: PlanningRunAggregate) -> dict[str, object]:
        values = SqlAlchemyPlanningRunRepository._run_values(aggregate)
        frozen = aggregate.prepared_artifacts.get("runtime_replan")
        if frozen is not None:
            values["replan_request_id"] = frozen["request"]["request_id"]
        return values

    def _source_matches(
        self, connection: Connection, aggregate: PlanningRunAggregate
    ) -> None:
        frozen = aggregate.prepared_artifacts.get("runtime_replan")
        if frozen is None:
            return super()._source_matches(connection, aggregate)
        request = frozen["request"]
        stored = SqlAlchemyReplanRequestRepository(
            self._engine, data_plane=WorkspaceDataPlane(self.data_plane)
        ).get_in_transaction(connection, request["request_id"])
        if (
            stored != request
            or frozen.get("version") != "runtime-replan-input.v1"
            or frozen.get("fingerprint")
            != canonical_fingerprint(
                {k: v for k, v in frozen.items() if k != "fingerprint"}
            )
        ):
            reject(
                PlanningRunErrorCode.LINEAGE_INVALID,
                field="runtime_replan",
                message="Immutable replan input differs from its durable source",
            )
        self._verify_replan_source(connection, aggregate)


def lock_run(
    connection: Connection,
    *,
    run_id: str,
    revision: int,
    fingerprint: str,
    data_plane: str,
) -> None:
    """Acquire the run write lock with the same expected revision used by CAS."""
    if connection.dialect.name == "sqlite":
        # SQLite has no row locks. This is the first statement of the result
        # transaction; acquire its write reservation without a fake state update.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    result = connection.execute(
        select(_PLANNING_RUNS.c.planning_run_id)
        .where(
            _PLANNING_RUNS.c.planning_run_id == run_id,
            _PLANNING_RUNS.c.data_plane == data_plane,
            _PLANNING_RUNS.c.revision == revision,
            _PLANNING_RUNS.c.run_fingerprint == fingerprint,
            _PLANNING_RUNS.c.terminal.is_(False),
        )
        .with_for_update()
    ).first()
    if result is None:
        reject(
            PlanningRunErrorCode.STALE_RUN,
            field="replan.result",
            message="Run changed before atomic replan result application",
        )


def serialize_creation(connection: Connection, ingress_id: str) -> None:
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.execute(
            text(
                "SELECT ingress_id FROM canonical_ingress_records WHERE ingress_id=:ingress_id FOR UPDATE"
            ),
            {"ingress_id": ingress_id},
        )
