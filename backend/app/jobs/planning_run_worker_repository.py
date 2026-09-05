"""Durable lease CAS and immutable result checkpoint for the P8 Solver Worker."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.infrastructure.workspace_persistence import (
    WorkspaceDataPlane,
    integrity_savepoint,
)
from app.jobs.contracts import (
    JobRecord,
    JobStatus,
    JobTransitionError,
    claim_job,
    complete_job,
    heartbeat_job,
    mark_stalled,
    new_job,
)
from app.jobs.planning_run_worker_contracts import (
    PLANNING_RUN_SOLVER_JOB_KIND,
    PlanningRunWorkerError,
    PlanningRunWorkerErrorCode,
    PlanningRunWorkerResult,
    reject_worker,
    verify_worker_result,
    worker_job_identity,
)


_METADATA = MetaData()

_JOBS = Table(
    "engineering_job_records",
    _METADATA,
    Column("job_id", String(length=64), primary_key=True),
    Column("job_kind", String(length=80), nullable=False),
    Column("idempotency_key", String(length=160), nullable=False),
    Column("request_fingerprint", String(length=64), nullable=False),
    Column("status", String(length=16), nullable=False),
    Column("attempt", Integer(), nullable=False),
    Column("worker_id", String(length=160), nullable=True),
    Column("failure_code", String(length=80), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("heartbeat_at", DateTime(timezone=True), nullable=True),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
)

_BINDINGS = Table(
    "planning_run_worker_jobs",
    _METADATA,
    Column("job_id", String(length=64), primary_key=True),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("attempt_id", String(length=256), nullable=False),
    Column("work_item_id", String(length=256), nullable=False),
    Column("data_plane", String(length=16), nullable=False),
    Column("work_item_fingerprint", String(length=71), nullable=False),
    Column("runtime_resolution_fingerprint", String(length=71), nullable=False),
    Column("created_at_utc", String(length=32), nullable=False),
    Column("stored_at", DateTime(timezone=True), nullable=False),
)

_RESULTS = Table(
    "planning_run_worker_results",
    _METADATA,
    Column("result_id", String(length=256), primary_key=True),
    Column("job_id", String(length=64), nullable=False),
    Column("planning_run_id", String(length=256), nullable=False),
    Column("attempt_id", String(length=256), nullable=False),
    Column("work_item_id", String(length=256), nullable=False),
    Column("data_plane", String(length=16), nullable=False),
    Column("outcome_state", String(length=32), nullable=False),
    Column("work_item_fingerprint", String(length=71), nullable=False),
    Column("runtime_resolution_fingerprint", String(length=71), nullable=False),
    Column("result_fingerprint", String(length=71), nullable=False),
    Column("result_json", LargeBinary(), nullable=False),
    Column("result_sha256", String(length=64), nullable=False),
    Column("created_at_utc", String(length=32), nullable=False),
    Column("stored_at", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True, slots=True)
class WorkerJobWrite:
    record: JobRecord
    replayed: bool


@dataclass(frozen=True, slots=True)
class WorkerResultWrite:
    result: PlanningRunWorkerResult
    replayed: bool


@dataclass(frozen=True, slots=True)
class WorkerJobBinding:
    job_id: str
    planning_run_id: str
    attempt_id: str
    work_item_id: str
    data_plane: str
    work_item_fingerprint: str
    runtime_resolution_fingerprint: str


def _aware(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field=f"stored.job.{field}",
            message="Stored Worker job timestamp is invalid",
        )
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _job_from_row(row: RowMapping) -> JobRecord:
    try:
        return JobRecord(
            job_id=cast(str, row["job_id"]),
            job_kind=cast(str, row["job_kind"]),
            idempotency_key=cast(str, row["idempotency_key"]),
            request_fingerprint=cast(str, row["request_fingerprint"]),
            status=JobStatus(cast(str, row["status"])),
            attempt=cast(int, row["attempt"]),
            created_at=cast(datetime, _aware(row["created_at"], "created_at")),
            updated_at=cast(datetime, _aware(row["updated_at"], "updated_at")),
            started_at=_aware(row["started_at"], "started_at"),
            heartbeat_at=_aware(row["heartbeat_at"], "heartbeat_at"),
            lease_expires_at=_aware(row["lease_expires_at"], "lease_expires_at"),
            finished_at=_aware(row["finished_at"], "finished_at"),
            worker_id=cast(str | None, row["worker_id"]),
            failure_code=cast(str | None, row["failure_code"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlanningRunWorkerError(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="stored.job",
            message="Stored Worker job metadata is invalid",
        ) from error


def _job_values(record: JobRecord) -> dict[str, object]:
    return {
        "job_id": record.job_id,
        "job_kind": record.job_kind,
        "idempotency_key": record.idempotency_key,
        "request_fingerprint": record.request_fingerprint,
        "status": record.status.value,
        "attempt": record.attempt,
        "worker_id": record.worker_id,
        "failure_code": record.failure_code,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "started_at": record.started_at,
        "heartbeat_at": record.heartbeat_at,
        "lease_expires_at": record.lease_expires_at,
        "finished_at": record.finished_at,
    }


class SqlAlchemyPlanningRunWorkerRepository:
    """One plane-bound repository for operational leases and exact checkpoints."""

    def __init__(self, engine: Engine, *, data_plane: WorkspaceDataPlane) -> None:
        self._engine = engine
        self._data_plane = data_plane

    @property
    def data_plane(self) -> str:
        return self._data_plane.value

    @staticmethod
    def _job_row(connection: Connection, job_id: str) -> RowMapping | None:
        row = connection.execute(select(_JOBS).where(_JOBS.c.job_id == job_id)).first()
        return None if row is None else row._mapping

    def get_job(self, job_id: str) -> JobRecord | None:
        try:
            with self._engine.connect() as connection:
                row = self._job_row(connection, job_id)
                return None if row is None else _job_from_row(row)
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_job",
                message="Worker job lookup failed",
                retryable=True,
            ) from error

    def ensure_job(
        self,
        work_item: dict[str, object],
        *,
        now: datetime,
    ) -> WorkerJobWrite:
        job_id, key_reference, request_digest = worker_job_identity(
            work_item, data_plane=self.data_plane
        )
        candidate = new_job(
            job_id=job_id,
            job_kind=PLANNING_RUN_SOLVER_JOB_KIND,
            idempotency_key=key_reference,
            request_fingerprint=request_digest,
            now=now,
        )
        runtime = work_item.get("runtime_resolution")
        runtime_fingerprint = (
            runtime.get("resolution_fingerprint")
            if isinstance(runtime, Mapping)
            else None
        )
        binding_values = {
            "job_id": job_id,
            "planning_run_id": work_item.get("planning_run_id"),
            "attempt_id": work_item.get("attempt_id"),
            "work_item_id": work_item.get("work_item_id"),
            "data_plane": self.data_plane,
            "work_item_fingerprint": work_item.get("work_item_fingerprint"),
            "runtime_resolution_fingerprint": runtime_fingerprint,
            "created_at_utc": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "stored_at": now,
        }
        try:
            with self._engine.begin() as connection:
                created = False
                existing_row = self._job_row(connection, job_id)
                if existing_row is None:
                    try:
                        with integrity_savepoint(connection):
                            connection.execute(
                                insert(_JOBS).values(**_job_values(candidate))
                            )
                    except IntegrityError:
                        existing_row = self._job_row(connection, job_id)
                    else:
                        created = True
                if created:
                    existing = candidate
                elif existing_row is not None:
                    existing = _job_from_row(existing_row)
                else:
                    reject_worker(
                        PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                        field="worker_job",
                        message="Worker job insert race could not be resolved",
                        retryable=True,
                    )
                if any(
                    (
                        existing.job_kind != candidate.job_kind,
                        existing.idempotency_key != candidate.idempotency_key,
                        existing.request_fingerprint != candidate.request_fingerprint,
                    )
                ):
                    reject_worker(
                        PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                        field="worker_job",
                        message="Worker job identity has different immutable content",
                    )
                binding = connection.execute(
                    select(_BINDINGS).where(_BINDINGS.c.job_id == job_id)
                ).first()
                if binding is None:
                    try:
                        with integrity_savepoint(connection):
                            connection.execute(
                                insert(_BINDINGS).values(**binding_values)
                            )
                    except IntegrityError:
                        binding = connection.execute(
                            select(_BINDINGS).where(
                                or_(
                                    _BINDINGS.c.job_id == job_id,
                                    _BINDINGS.c.attempt_id
                                    == work_item.get("attempt_id"),
                                    _BINDINGS.c.work_item_id
                                    == work_item.get("work_item_id"),
                                )
                            )
                        ).first()
                if binding is not None:
                    stored = binding._mapping
                    for field, value in binding_values.items():
                        if (
                            field not in {"stored_at", "created_at_utc"}
                            and stored[field] != value
                        ):
                            reject_worker(
                                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                                field="worker_job.binding",
                                message=(
                                    "Worker job binding has different immutable content"
                                ),
                            )
                return WorkerJobWrite(existing, replayed=not created)
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_job",
                message="Worker job transaction failed",
                retryable=True,
            ) from error

    def _cas_job(
        self,
        connection: Connection,
        *,
        previous: JobRecord,
        candidate: JobRecord,
    ) -> None:
        values = _job_values(candidate)
        values.pop("job_id")
        values.pop("job_kind")
        values.pop("idempotency_key")
        values.pop("request_fingerprint")
        values.pop("created_at")
        result = connection.execute(
            update(_JOBS)
            .where(
                _JOBS.c.job_id == previous.job_id,
                _JOBS.c.status == previous.status.value,
                _JOBS.c.attempt == previous.attempt,
                _JOBS.c.worker_id == previous.worker_id,
                _JOBS.c.lease_expires_at == previous.lease_expires_at,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            reject_worker(
                PlanningRunWorkerErrorCode.LEASE_LOST,
                field="worker_job.lease",
                message="Worker job lease CAS lost a concurrent race",
                retryable=True,
            )

    def claim(
        self,
        job_id: str,
        *,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> JobRecord:
        try:
            with self._engine.begin() as connection:
                row = self._job_row(connection, job_id)
                if row is None:
                    reject_worker(
                        PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                        field="worker_job",
                        message="Worker job is absent",
                    )
                previous = _job_from_row(row)
                if previous.status is JobStatus.RUNNING:
                    reject_worker(
                        PlanningRunWorkerErrorCode.LEASE_BUSY,
                        field="worker_job.lease",
                        message="Worker job already has an active lease",
                        retryable=True,
                    )
                if previous.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                    reject_worker(
                        PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                        field="worker_job.status",
                        message="Terminal Worker job cannot be claimed",
                    )
                try:
                    candidate = claim_job(
                        previous,
                        worker_id=worker_id,
                        now=now,
                        lease_seconds=lease_seconds,
                    )
                except JobTransitionError as error:
                    raise PlanningRunWorkerError(
                        PlanningRunWorkerErrorCode.LEASE_LOST,
                        field="worker_job.lease",
                        message="Worker job claim was rejected",
                        retryable=True,
                    ) from error
                self._cas_job(connection, previous=previous, candidate=candidate)
                return candidate
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_job.claim",
                message="Worker job claim failed",
                retryable=True,
            ) from error

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> JobRecord:
        try:
            with self._engine.begin() as connection:
                row = self._job_row(connection, job_id)
                if row is None:
                    reject_worker(
                        PlanningRunWorkerErrorCode.LEASE_LOST,
                        field="worker_job.lease",
                        message="Worker job disappeared before heartbeat",
                        retryable=True,
                    )
                previous = _job_from_row(row)
                try:
                    candidate = heartbeat_job(
                        previous,
                        worker_id=worker_id,
                        now=now,
                        lease_seconds=lease_seconds,
                    )
                except JobTransitionError as error:
                    raise PlanningRunWorkerError(
                        PlanningRunWorkerErrorCode.LEASE_LOST,
                        field="worker_job.lease",
                        message="Worker heartbeat lost its active lease",
                        retryable=True,
                    ) from error
                self._cas_job(connection, previous=previous, candidate=candidate)
                return candidate
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_job.heartbeat",
                message="Worker heartbeat persistence failed",
                retryable=True,
            ) from error

    def complete(
        self,
        job_id: str,
        *,
        worker_id: str,
        now: datetime,
        succeeded: bool,
        failure_code: str | None = None,
    ) -> JobRecord:
        try:
            with self._engine.begin() as connection:
                row = self._job_row(connection, job_id)
                if row is None:
                    reject_worker(
                        PlanningRunWorkerErrorCode.LEASE_LOST,
                        field="worker_job.lease",
                        message="Worker job disappeared before completion",
                    )
                previous = _job_from_row(row)
                try:
                    candidate = complete_job(
                        previous,
                        worker_id=worker_id,
                        now=now,
                        succeeded=succeeded,
                        failure_code=failure_code,
                    )
                except JobTransitionError as error:
                    raise PlanningRunWorkerError(
                        PlanningRunWorkerErrorCode.LEASE_LOST,
                        field="worker_job.lease",
                        message="Worker completion lost its active lease",
                    ) from error
                self._cas_job(connection, previous=previous, candidate=candidate)
                return candidate
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_job.complete",
                message="Worker completion persistence failed",
                retryable=True,
            ) from error

    def mark_expired_stalled(self, job_id: str, *, now: datetime) -> JobRecord:
        try:
            with self._engine.begin() as connection:
                row = self._job_row(connection, job_id)
                if row is None:
                    reject_worker(
                        PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                        field="worker_job",
                        message="Worker job is absent",
                    )
                previous = _job_from_row(row)
                candidate = mark_stalled(previous, now=now)
                if candidate is previous:
                    return previous
                self._cas_job(connection, previous=previous, candidate=candidate)
                return candidate
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_job.recovery",
                message="Worker lease recovery failed",
                retryable=True,
            ) from error

    def expired_running_job_ids(self, *, now: datetime) -> tuple[str, ...]:
        try:
            with self._engine.connect() as connection:
                values = connection.scalars(
                    select(_JOBS.c.job_id)
                    .where(
                        _JOBS.c.job_kind == PLANNING_RUN_SOLVER_JOB_KIND,
                        _JOBS.c.status == JobStatus.RUNNING.value,
                        _JOBS.c.lease_expires_at.is_not(None),
                        _JOBS.c.lease_expires_at <= now,
                    )
                    .order_by(_JOBS.c.job_id)
                ).all()
            return tuple(cast(str, value) for value in values)
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_job.recovery",
                message="Expired Worker job scan failed",
                retryable=True,
            ) from error

    def get_binding(self, job_id: str) -> WorkerJobBinding | None:
        try:
            with self._engine.connect() as connection:
                row = connection.execute(
                    select(_BINDINGS).where(
                        _BINDINGS.c.job_id == job_id,
                        _BINDINGS.c.data_plane == self.data_plane,
                    )
                ).first()
            if row is None:
                return None
            values = row._mapping
            return WorkerJobBinding(
                job_id=cast(str, values["job_id"]),
                planning_run_id=cast(str, values["planning_run_id"]),
                attempt_id=cast(str, values["attempt_id"]),
                work_item_id=cast(str, values["work_item_id"]),
                data_plane=cast(str, values["data_plane"]),
                work_item_fingerprint=cast(str, values["work_item_fingerprint"]),
                runtime_resolution_fingerprint=cast(
                    str, values["runtime_resolution_fingerprint"]
                ),
            )
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_job.binding",
                message="Worker job binding lookup failed",
                retryable=True,
            ) from error

    @staticmethod
    def _result_row(
        connection: Connection,
        *,
        result_id: str | None = None,
        job_id: str | None = None,
        attempt_id: str | None = None,
        work_item_id: str | None = None,
    ) -> RowMapping | None:
        clauses = []
        if result_id is not None:
            clauses.append(_RESULTS.c.result_id == result_id)
        if job_id is not None:
            clauses.append(_RESULTS.c.job_id == job_id)
        if attempt_id is not None:
            clauses.append(_RESULTS.c.attempt_id == attempt_id)
        if work_item_id is not None:
            clauses.append(_RESULTS.c.work_item_id == work_item_id)
        if not clauses:
            raise ValueError("one Worker result identity is required")
        row = connection.execute(select(_RESULTS).where(or_(*clauses))).first()
        return None if row is None else row._mapping

    def _load_result(self, row: RowMapping) -> PlanningRunWorkerResult:
        raw = row["result_json"]
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="stored.worker_result",
                message="Stored Worker result bytes are invalid",
            )
        content = bytes(raw)
        if sha256(content).hexdigest() != row["result_sha256"]:
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="stored.worker_result.result_sha256",
                message="Stored Worker result bytes were modified",
            )
        result = PlanningRunWorkerResult(content)
        verify_worker_result(result, data_plane=self.data_plane)
        document = result.document
        for field in (
            "result_id",
            "job_id",
            "planning_run_id",
            "attempt_id",
            "work_item_id",
            "outcome_state",
            "work_item_fingerprint",
            "runtime_resolution_fingerprint",
            "result_fingerprint",
            "created_at_utc",
        ):
            if document.get(field) != row[field]:
                reject_worker(
                    PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                    field=f"stored.worker_result.{field}",
                    message="Stored Worker result metadata differs from its bytes",
                )
        return result

    def get_result_for_work_item(
        self, work_item_id: str
    ) -> PlanningRunWorkerResult | None:
        try:
            with self._engine.connect() as connection:
                row = self._result_row(connection, work_item_id=work_item_id)
                if row is None or row["data_plane"] != self.data_plane:
                    return None
                return self._load_result(row)
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_result",
                message="Worker result lookup failed",
                retryable=True,
            ) from error

    def get_latest_result_for_run(
        self, planning_run_id: str
    ) -> PlanningRunWorkerResult | None:
        try:
            with self._engine.connect() as connection:
                row = connection.execute(
                    select(_RESULTS)
                    .where(
                        _RESULTS.c.planning_run_id == planning_run_id,
                        _RESULTS.c.data_plane == self.data_plane,
                    )
                    .order_by(_RESULTS.c.stored_at.desc(), _RESULTS.c.result_id.desc())
                ).first()
                return None if row is None else self._load_result(row._mapping)
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_result",
                message="Worker result recovery lookup failed",
                retryable=True,
            ) from error

    def put_result(self, result: PlanningRunWorkerResult) -> WorkerResultWrite:
        verify_worker_result(result, data_plane=self.data_plane)
        document = result.document
        values = {
            "result_id": document["result_id"],
            "job_id": document["job_id"],
            "planning_run_id": document["planning_run_id"],
            "attempt_id": document["attempt_id"],
            "work_item_id": document["work_item_id"],
            "data_plane": document["data_plane"],
            "outcome_state": document["outcome_state"],
            "work_item_fingerprint": document["work_item_fingerprint"],
            "runtime_resolution_fingerprint": document[
                "runtime_resolution_fingerprint"
            ],
            "result_fingerprint": document["result_fingerprint"],
            "result_json": result.canonical_bytes,
            "result_sha256": sha256(result.canonical_bytes).hexdigest(),
            "created_at_utc": document["created_at_utc"],
            "stored_at": datetime.now(UTC),
        }
        try:
            with self._engine.begin() as connection:
                existing = self._result_row(
                    connection,
                    result_id=cast(str, document["result_id"]),
                    job_id=cast(str, document["job_id"]),
                    attempt_id=cast(str, document["attempt_id"]),
                    work_item_id=cast(str, document["work_item_id"]),
                )
                if existing is None:
                    try:
                        with integrity_savepoint(connection):
                            connection.execute(insert(_RESULTS).values(**values))
                    except IntegrityError:
                        existing = self._result_row(
                            connection,
                            result_id=cast(str, document["result_id"]),
                            job_id=cast(str, document["job_id"]),
                            attempt_id=cast(str, document["attempt_id"]),
                            work_item_id=cast(str, document["work_item_id"]),
                        )
                    else:
                        return WorkerResultWrite(result, replayed=False)
                if existing is None:
                    reject_worker(
                        PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                        field="worker_result",
                        message="Worker result insert race could not be resolved",
                        retryable=True,
                    )
                stored = self._load_result(existing)
                if stored.canonical_bytes != result.canonical_bytes:
                    reject_worker(
                        PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                        field="worker_result",
                        message="Worker result identity has different immutable content",
                    )
                return WorkerResultWrite(stored, replayed=True)
        except PlanningRunWorkerError:
            raise
        except SQLAlchemyError as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.PERSISTENCE_FAILED,
                field="worker_result",
                message="Worker result transaction failed",
                retryable=True,
            ) from error


__all__ = [
    "SqlAlchemyPlanningRunWorkerRepository",
    "WorkerJobBinding",
    "WorkerJobWrite",
    "WorkerResultWrite",
]
