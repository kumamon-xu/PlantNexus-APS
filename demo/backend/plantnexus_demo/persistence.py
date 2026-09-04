"""Durable, Demo-only control state and per-run SQLite composition.

The control database owns orchestration metadata only.  Every run database is
created from the repository Alembic history before Demo auxiliary tables are
added; formal PlantNexus repositories remain the authority for core records.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sqlite3
from typing import cast

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect


CONTROL_SCHEMA_VERSION = "cnc-demo-control.v1"
RUN_SCHEMA_VERSION = "cnc-demo-run.v1"
ACTIVE_JOB_STATUSES = ("QUEUED", "RUNNING", "CANCELLING")
TERMINAL_JOB_STATUSES = ("SUCCEEDED", "FAILED", "INTERRUPTED", "CANCELLED")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_RUNTIME_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


class DemoPersistenceError(RuntimeError):
    """Stable Demo persistence failure without SQL or filesystem disclosure."""

    def __init__(self, code: str, *, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code}: {field}: {message}")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_bytes(document: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise DemoPersistenceError(
            "INVALID_DOCUMENT",
            field="document",
            message="document is not canonical JSON",
        ) from error


def fingerprint(document: Mapping[str, object]) -> str:
    return f"sha256:{sha256(canonical_bytes(document)).hexdigest()}"


def key_reference(value: str) -> str:
    if not value or len(value) > 256 or any(character.isspace() for character in value):
        raise DemoPersistenceError(
            "INVALID_IDEMPOTENCY_KEY",
            field="Idempotency-Key",
            message="idempotency key is invalid",
        )
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


def _require_identifier(value: str, field: str) -> str:
    if _IDENTIFIER.fullmatch(value) is None:
        raise DemoPersistenceError(
            "INVALID_IDENTIFIER",
            field=field,
            message="identifier is invalid",
        )
    return value


def _require_fingerprint(value: str, field: str) -> str:
    if _FINGERPRINT.fullmatch(value) is None:
        raise DemoPersistenceError(
            "INVALID_FINGERPRINT",
            field=field,
            message="fingerprint is invalid",
        )
    return value


def resolve_named_runtime_root(demo_root: Path, runtime_id: str | None) -> Path:
    """Resolve a CLI runtime name below demo/runtime without accepting paths."""

    root = (demo_root / "runtime").resolve()
    if runtime_id is None:
        return root
    if _RUNTIME_ID.fullmatch(runtime_id) is None:
        raise ValueError(
            "--runtime-id must contain only lowercase letters, digits, and hyphens"
        )
    candidate = (root / runtime_id).resolve()
    if candidate.parent != root:
        raise ValueError("--runtime-id escaped the Demo runtime directory")
    return candidate


@dataclass(frozen=True, slots=True)
class DemoRuntimePaths:
    """Resolve every write below one explicit runtime root."""

    root: Path

    def __post_init__(self) -> None:
        resolved = self.root.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "root", resolved)
        self.runs_root.mkdir(parents=True, exist_ok=True)

    @property
    def control_database(self) -> Path:
        return self._inside(self.root / "control.db")

    @property
    def token_file(self) -> Path:
        return self._inside(self.root / "session.token")

    @property
    def runs_root(self) -> Path:
        return self._inside(self.root / "runs")

    def run_directory(self, run_id: str) -> Path:
        _require_identifier(run_id, "run_id")
        return self._inside(self.runs_root / run_id)

    def run_database(self, run_id: str) -> Path:
        return self._inside(self.run_directory(run_id) / "plantnexus.db")

    def relative_run_database(self, run_id: str) -> str:
        return self.run_database(run_id).relative_to(self.root).as_posix()

    def resolve_relative_database(self, relative_path: str) -> Path:
        if Path(relative_path).is_absolute():
            raise DemoPersistenceError(
                "PATH_ESCAPE",
                field="database_relative_path",
                message="absolute paths are forbidden",
            )
        return self._inside(self.root / relative_path)

    def _inside(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as error:
            raise DemoPersistenceError(
                "PATH_ESCAPE",
                field="runtime_path",
                message="path escaped the Demo runtime root",
            ) from error
        return resolved

    def remove_run_directory(self, run_id: str) -> None:
        target = self.run_directory(run_id)
        if target == self.root or target == self.runs_root:
            raise DemoPersistenceError(
                "PATH_ESCAPE",
                field="run_id",
                message="broad runtime deletion is forbidden",
            )
        if target.exists():
            shutil.rmtree(target)


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    scenario_id: str
    seed: int
    status: str
    database_relative_path: str
    created_at_utc: str
    activated_at_utc: str | None


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: str
    job_kind: str
    run_id: str | None
    request_fingerprint: str
    key_reference: str
    status: str
    stage: str | None
    attempt: int
    correlation_id: str
    request: dict[str, object]
    result: dict[str, object] | None
    error_code: str | None
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class JobRegistration:
    job: JobRecord
    replayed: bool


@dataclass(frozen=True, slots=True)
class CommandClaim:
    scope: str
    key_reference: str
    request_fingerprint: str
    status: str
    result: dict[str, object] | None
    replayed: bool


class ControlStore:
    """SQLite orchestration registry with transaction-scoped CAS checks."""

    def __init__(self, paths: DemoRuntimePaths) -> None:
        self.paths = paths
        self._initialize()

    @contextmanager
    def _connection(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.paths.control_database,
            timeout=30,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection(immediate=True) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS demo_control_state (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    schema_version TEXT NOT NULL,
                    active_run_id TEXT,
                    revision INTEGER NOT NULL CHECK (revision >= 0)
                );
                CREATE TABLE IF NOT EXISTS demo_runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    database_relative_path TEXT NOT NULL UNIQUE,
                    created_at_utc TEXT NOT NULL,
                    activated_at_utc TEXT
                );
                CREATE TABLE IF NOT EXISTS demo_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_kind TEXT NOT NULL,
                    run_id TEXT,
                    request_fingerprint TEXT NOT NULL,
                    key_reference TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT,
                    attempt INTEGER NOT NULL CHECK (attempt >= 0),
                    worker_id TEXT,
                    correlation_id TEXT NOT NULL,
                    request_json BLOB,
                    result_json BLOB,
                    error_code TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    started_at_utc TEXT,
                    finished_at_utc TEXT,
                    UNIQUE(job_kind, key_reference)
                );
                CREATE INDEX IF NOT EXISTS ix_demo_jobs_active
                    ON demo_jobs(status, created_at_utc);
                CREATE TABLE IF NOT EXISTS demo_job_stages (
                    job_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    finished_at_utc TEXT,
                    elapsed_seconds REAL,
                    evidence_ref TEXT,
                    PRIMARY KEY(job_id, attempt, sequence),
                    FOREIGN KEY(job_id) REFERENCES demo_jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS demo_command_idempotency (
                    scope TEXT NOT NULL,
                    key_reference TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json BLOB,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY(scope, key_reference)
                );
                CREATE TABLE IF NOT EXISTS demo_authorization_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT NOT NULL,
                    actor_ref TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    outcome TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at_utc TEXT NOT NULL
                );
                """
            )
            job_columns = {
                cast(str, row[1])
                for row in connection.execute("PRAGMA table_info(demo_jobs)").fetchall()
            }
            if "request_json" not in job_columns:
                connection.execute("ALTER TABLE demo_jobs ADD COLUMN request_json BLOB")
            connection.execute(
                """
                INSERT INTO demo_control_state(singleton_id, schema_version, active_run_id, revision)
                VALUES(1, ?, NULL, 0)
                ON CONFLICT(singleton_id) DO NOTHING
                """,
                (CONTROL_SCHEMA_VERSION,),
            )
            row = connection.execute(
                "SELECT schema_version FROM demo_control_state WHERE singleton_id = 1"
            ).fetchone()
            if row is None or row["schema_version"] != CONTROL_SCHEMA_VERSION:
                raise DemoPersistenceError(
                    "MIGRATION_FAILED",
                    field="control.schema_version",
                    message="unsupported control database schema",
                )

    @staticmethod
    def _json(value: object) -> bytes:
        if not isinstance(value, Mapping):
            raise DemoPersistenceError(
                "INVALID_DOCUMENT", field="result", message="result must be an object"
            )
        return canonical_bytes(cast(Mapping[str, object], value))

    @staticmethod
    def _decode(value: object) -> dict[str, object] | None:
        if value is None:
            return None
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise DemoPersistenceError(
                "PERSISTENCE_FAILED",
                field="stored.result_json",
                message="stored result is invalid",
            )
        parsed = json.loads(bytes(value).decode("utf-8"))
        if not isinstance(parsed, dict):
            raise DemoPersistenceError(
                "PERSISTENCE_FAILED",
                field="stored.result_json",
                message="stored result is invalid",
            )
        return cast(dict[str, object], parsed)

    @classmethod
    def _job(cls, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=cast(str, row["job_id"]),
            job_kind=cast(str, row["job_kind"]),
            run_id=cast(str | None, row["run_id"]),
            request_fingerprint=cast(str, row["request_fingerprint"]),
            key_reference=cast(str, row["key_reference"]),
            status=cast(str, row["status"]),
            stage=cast(str | None, row["stage"]),
            attempt=cast(int, row["attempt"]),
            correlation_id=cast(str, row["correlation_id"]),
            request=cls._decode(row["request_json"]) or {},
            result=cls._decode(row["result_json"]),
            error_code=cast(str | None, row["error_code"]),
            created_at_utc=cast(str, row["created_at_utc"]),
            updated_at_utc=cast(str, row["updated_at_utc"]),
        )

    @staticmethod
    def _run(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=cast(str, row["run_id"]),
            scenario_id=cast(str, row["scenario_id"]),
            seed=cast(int, row["seed"]),
            status=cast(str, row["status"]),
            database_relative_path=cast(str, row["database_relative_path"]),
            created_at_utc=cast(str, row["created_at_utc"]),
            activated_at_utc=cast(str | None, row["activated_at_utc"]),
        )

    def active_run(self) -> RunRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT r.* FROM demo_control_state c
                JOIN demo_runs r ON r.run_id = c.active_run_id
                WHERE c.singleton_id = 1
                """
            ).fetchone()
            return None if row is None else self._run(row)

    def get_run(self, run_id: str) -> RunRecord | None:
        _require_identifier(run_id, "run_id")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM demo_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            return None if row is None else self._run(row)

    def register_run(
        self,
        *,
        run_id: str,
        scenario_id: str,
        seed: int,
        database_relative_path: str,
        created_at_utc: str,
    ) -> RunRecord:
        _require_identifier(run_id, "run_id")
        self.paths.resolve_relative_database(database_relative_path)
        with self._connection(immediate=True) as connection:
            existing = connection.execute(
                "SELECT * FROM demo_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing is not None:
                record = self._run(existing)
                expected = (scenario_id, seed, database_relative_path)
                if (
                    record.scenario_id,
                    record.seed,
                    record.database_relative_path,
                ) != expected:
                    raise DemoPersistenceError(
                        "IDEMPOTENCY_CONFLICT",
                        field="run_id",
                        message="run identity is bound to different input",
                    )
                return record
            connection.execute(
                """
                INSERT INTO demo_runs(
                    run_id, scenario_id, seed, status, database_relative_path,
                    created_at_utc, activated_at_utc
                ) VALUES(?, ?, ?, 'INITIALIZING', ?, ?, NULL)
                """,
                (run_id, scenario_id, seed, database_relative_path, created_at_utc),
            )
        record = self.get_run(run_id)
        assert record is not None
        return record

    def mark_run_failed(self, run_id: str) -> None:
        with self._connection(immediate=True) as connection:
            connection.execute(
                "UPDATE demo_runs SET status = 'FAILED' WHERE run_id = ? AND status != 'ACTIVE'",
                (run_id,),
            )

    def activate_run(self, *, run_id: str, expected_active_run_id: str | None) -> RunRecord:
        occurred_at = utc_now()
        with self._connection(immediate=True) as connection:
            candidate = connection.execute(
                "SELECT * FROM demo_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if candidate is None or candidate["status"] != "INITIALIZING":
                raise DemoPersistenceError(
                    "STALE_RUN",
                    field="run_id",
                    message="candidate run is not switchable",
                )
            state = connection.execute(
                "SELECT active_run_id, revision FROM demo_control_state WHERE singleton_id = 1"
            ).fetchone()
            assert state is not None
            if state["active_run_id"] != expected_active_run_id:
                raise DemoPersistenceError(
                    "STALE_RUN",
                    field="expected_active_run_id",
                    message="active run changed before switch",
                )
            if expected_active_run_id is not None:
                connection.execute(
                    "UPDATE demo_runs SET status = 'INACTIVE' WHERE run_id = ?",
                    (expected_active_run_id,),
                )
            connection.execute(
                "UPDATE demo_runs SET status = 'ACTIVE', activated_at_utc = ? WHERE run_id = ?",
                (occurred_at, run_id),
            )
            changed = connection.execute(
                """
                UPDATE demo_control_state
                SET active_run_id = ?, revision = revision + 1
                WHERE singleton_id = 1 AND revision = ?
                """,
                (run_id, state["revision"]),
            ).rowcount
            if changed != 1:
                raise DemoPersistenceError(
                    "STALE_RUN",
                    field="control.revision",
                    message="active run CAS failed",
                )
        record = self.get_run(run_id)
        assert record is not None
        return record

    def inactive_runs(self) -> tuple[RunRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM demo_runs
                WHERE status IN ('INACTIVE', 'FAILED')
                ORDER BY created_at_utc DESC, run_id DESC
                """
            ).fetchall()
            return tuple(self._run(row) for row in rows)

    def forget_run(self, run_id: str) -> None:
        with self._connection(immediate=True) as connection:
            active = connection.execute(
                "SELECT active_run_id FROM demo_control_state WHERE singleton_id = 1"
            ).fetchone()
            if active is not None and active["active_run_id"] == run_id:
                raise DemoPersistenceError(
                    "ACTIVE_RUN_DELETE_FORBIDDEN",
                    field="run_id",
                    message="active run cannot be removed",
                )
            connection.execute("DELETE FROM demo_runs WHERE run_id = ?", (run_id,))

    def register_job(
        self,
        *,
        job_kind: str,
        run_id: str | None,
        expected_active_run_id: str | None,
        request_fingerprint: str,
        key_reference: str,
        correlation_id: str,
        request_document: Mapping[str, object],
        created_at_utc: str | None = None,
    ) -> JobRegistration:
        _require_identifier(job_kind, "job_kind")
        if run_id is not None:
            _require_identifier(run_id, "run_id")
        _require_fingerprint(request_fingerprint, "request_fingerprint")
        _require_fingerprint(key_reference, "key_reference")
        created_at = utc_now() if created_at_utc is None else created_at_utc
        job_id = "job-" + sha256(
            canonical_bytes(
                {
                    "job_kind": job_kind,
                    "key_reference": key_reference,
                }
            )
        ).hexdigest()
        with self._connection(immediate=True) as connection:
            existing = connection.execute(
                "SELECT * FROM demo_jobs WHERE job_kind = ? AND key_reference = ?",
                (job_kind, key_reference),
            ).fetchone()
            if existing is not None:
                record = self._job(existing)
                if record.request_fingerprint != request_fingerprint:
                    raise DemoPersistenceError(
                        "IDEMPOTENCY_CONFLICT",
                        field="Idempotency-Key",
                        message="same key is bound to different input",
                    )
                return JobRegistration(record, replayed=True)
            state = connection.execute(
                "SELECT active_run_id FROM demo_control_state WHERE singleton_id = 1"
            ).fetchone()
            assert state is not None
            if expected_active_run_id is not None and (
                state["active_run_id"] != expected_active_run_id
            ):
                raise DemoPersistenceError(
                    "STALE_RUN",
                    field="expected_run_id",
                    message="active run changed before job registration",
                )
            active_job = connection.execute(
                "SELECT job_id FROM demo_jobs WHERE status IN ('QUEUED','RUNNING','CANCELLING') LIMIT 1"
            ).fetchone()
            if active_job is not None:
                raise DemoPersistenceError(
                    "ACTIVE_JOB_CONFLICT",
                    field="job",
                    message="another mutating Demo job is active",
                )
            connection.execute(
                """
                INSERT INTO demo_jobs(
                    job_id, job_kind, run_id, request_fingerprint, key_reference,
                    status, stage, attempt, worker_id, correlation_id, request_json, result_json,
                    error_code, created_at_utc, updated_at_utc, started_at_utc,
                    finished_at_utc
                ) VALUES(?, ?, ?, ?, ?, 'QUEUED', NULL, 0, NULL, ?, ?, NULL, NULL, ?, ?, NULL, NULL)
                """,
                (
                    job_id,
                    job_kind,
                    run_id,
                    request_fingerprint,
                    key_reference,
                    correlation_id,
                    self._json(request_document),
                    created_at,
                    created_at,
                ),
            )
        record = self.get_job(job_id)
        assert record is not None
        return JobRegistration(record, replayed=False)

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM demo_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return None if row is None else self._job(row)

    def get_job_by_idempotency(
        self, *, job_kind: str, key_reference: str
    ) -> JobRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM demo_jobs WHERE job_kind = ? AND key_reference = ?",
                (job_kind, key_reference),
            ).fetchone()
            return None if row is None else self._job(row)

    def start_job(self, job_id: str, *, worker_id: str) -> JobRecord:
        _require_identifier(worker_id, "worker_id")
        now = utc_now()
        with self._connection(immediate=True) as connection:
            changed = connection.execute(
                """
                UPDATE demo_jobs
                SET status = 'RUNNING', attempt = attempt + 1, worker_id = ?,
                    started_at_utc = ?, finished_at_utc = NULL, error_code = NULL,
                    updated_at_utc = ?
                WHERE job_id = ? AND status IN ('QUEUED', 'INTERRUPTED')
                """,
                (worker_id, now, now, job_id),
            ).rowcount
            if changed != 1:
                raise DemoPersistenceError(
                    "JOB_STATE_CONFLICT",
                    field="job.status",
                    message="job cannot enter RUNNING",
                )
        record = self.get_job(job_id)
        assert record is not None
        return record

    def start_stage(self, job_id: str, *, sequence: int, stage: str) -> None:
        _require_identifier(stage, "stage")
        # Performance evidence needs sub-second stage boundaries.  Business
        # identity timestamps remain whole-second UTC; stage observations are
        # diagnostic-only and therefore retain microseconds.
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._connection(immediate=True) as connection:
            row = connection.execute(
                "SELECT attempt, status FROM demo_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None or row["status"] != "RUNNING":
                raise DemoPersistenceError(
                    "JOB_STATE_CONFLICT",
                    field="job.status",
                    message="only a running job may start a stage",
                )
            connection.execute(
                """
                INSERT INTO demo_job_stages(
                    job_id, attempt, sequence, stage, status, started_at_utc,
                    finished_at_utc, elapsed_seconds, evidence_ref
                ) VALUES(?, ?, ?, ?, 'RUNNING', ?, NULL, NULL, NULL)
                """,
                (job_id, row["attempt"], sequence, stage, now),
            )
            connection.execute(
                "UPDATE demo_jobs SET stage = ?, updated_at_utc = ? WHERE job_id = ?",
                (stage, now, job_id),
            )

    def finish_stage(
        self, job_id: str, *, sequence: int, evidence_ref: str | None = None
    ) -> None:
        finished = datetime.now(UTC)
        finished_text = finished.isoformat().replace("+00:00", "Z")
        with self._connection(immediate=True) as connection:
            row = connection.execute(
                "SELECT attempt FROM demo_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise DemoPersistenceError(
                    "JOB_NOT_FOUND", field="job_id", message="job does not exist"
                )
            stage = connection.execute(
                """
                SELECT started_at_utc FROM demo_job_stages
                WHERE job_id = ? AND attempt = ? AND sequence = ? AND status = 'RUNNING'
                """,
                (job_id, row["attempt"], sequence),
            ).fetchone()
            if stage is None:
                raise DemoPersistenceError(
                    "JOB_STATE_CONFLICT",
                    field="stage",
                    message="stage is not running",
                )
            started = datetime.fromisoformat(
                cast(str, stage["started_at_utc"]).replace("Z", "+00:00")
            )
            connection.execute(
                """
                UPDATE demo_job_stages
                SET status = 'SUCCEEDED', finished_at_utc = ?, elapsed_seconds = ?, evidence_ref = ?
                WHERE job_id = ? AND attempt = ? AND sequence = ? AND status = 'RUNNING'
                """,
                (
                    finished_text,
                    (finished - started).total_seconds(),
                    evidence_ref,
                    job_id,
                    row["attempt"],
                    sequence,
                ),
            )

    def complete_job(self, job_id: str, result: Mapping[str, object]) -> JobRecord:
        now = utc_now()
        payload = self._json(result)
        with self._connection(immediate=True) as connection:
            changed = connection.execute(
                """
                UPDATE demo_jobs
                SET status = 'SUCCEEDED', stage = 'COMPLETE', result_json = ?,
                    error_code = NULL, finished_at_utc = ?, updated_at_utc = ?
                WHERE job_id = ? AND status = 'RUNNING'
                """,
                (payload, now, now, job_id),
            ).rowcount
            if changed != 1:
                raise DemoPersistenceError(
                    "JOB_STATE_CONFLICT",
                    field="job.status",
                    message="job cannot complete",
                )
        record = self.get_job(job_id)
        assert record is not None
        return record

    def fail_job(self, job_id: str, *, error_code: str) -> JobRecord:
        _require_identifier(error_code, "error_code")
        now = utc_now()
        with self._connection(immediate=True) as connection:
            row = connection.execute(
                "SELECT attempt FROM demo_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise DemoPersistenceError(
                    "JOB_NOT_FOUND", field="job_id", message="job does not exist"
                )
            connection.execute(
                """
                UPDATE demo_job_stages
                SET status = 'FAILED', finished_at_utc = ?
                WHERE job_id = ? AND attempt = ? AND status = 'RUNNING'
                """,
                (now, job_id, row["attempt"]),
            )
            connection.execute(
                """
                UPDATE demo_jobs SET status = 'FAILED', error_code = ?,
                    finished_at_utc = ?, updated_at_utc = ?
                WHERE job_id = ? AND status = 'RUNNING'
                """,
                (error_code, now, now, job_id),
            )
        record = self.get_job(job_id)
        assert record is not None
        return record

    def recover_interrupted(self) -> int:
        now = utc_now()
        with self._connection(immediate=True) as connection:
            running = connection.execute(
                "SELECT job_id, attempt FROM demo_jobs WHERE status IN ('RUNNING','CANCELLING')"
            ).fetchall()
            for row in running:
                connection.execute(
                    """
                    UPDATE demo_job_stages SET status = 'INTERRUPTED', finished_at_utc = ?
                    WHERE job_id = ? AND attempt = ? AND status = 'RUNNING'
                    """,
                    (now, row["job_id"], row["attempt"]),
                )
            changed = connection.execute(
                """
                UPDATE demo_jobs SET status = 'INTERRUPTED', error_code = 'PROCESS_INTERRUPTED',
                    finished_at_utc = ?, updated_at_utc = ?
                WHERE status IN ('RUNNING','CANCELLING')
                """,
                (now, now),
            ).rowcount
            return int(changed)

    def queued_jobs(self) -> tuple[JobRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM demo_jobs WHERE status = 'QUEUED' ORDER BY created_at_utc, job_id"
            ).fetchall()
            return tuple(self._job(row) for row in rows)

    def active_job(self) -> JobRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM demo_jobs
                WHERE status IN ('QUEUED', 'RUNNING', 'CANCELLING')
                ORDER BY created_at_utc, job_id LIMIT 1
                """
            ).fetchone()
            return None if row is None else self._job(row)

    def latest_succeeded_job(
        self, *, job_kind: str, run_id: str
    ) -> JobRecord | None:
        """Return the newest durable successful job for one active Demo run."""

        _require_identifier(job_kind, "job_kind")
        _require_identifier(run_id, "run_id")
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM demo_jobs
                WHERE job_kind = ? AND run_id = ? AND status = 'SUCCEEDED'
                ORDER BY finished_at_utc DESC, created_at_utc DESC, job_id DESC
                LIMIT 1
                """,
                (job_kind, run_id),
            ).fetchone()
            return None if row is None else self._job(row)

    def job_stages(self, job_id: str) -> tuple[dict[str, object], ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT attempt, sequence, stage, status, started_at_utc,
                       finished_at_utc, elapsed_seconds, evidence_ref
                FROM demo_job_stages WHERE job_id = ?
                ORDER BY attempt, sequence
                """,
                (job_id,),
            ).fetchall()
            return tuple(dict(row) for row in rows)

    def claim_command(
        self,
        *,
        scope: str,
        key_reference: str,
        request_fingerprint: str,
        created_at_utc: str | None = None,
    ) -> CommandClaim:
        _require_identifier(scope, "scope")
        _require_fingerprint(key_reference, "key_reference")
        _require_fingerprint(request_fingerprint, "request_fingerprint")
        now = utc_now() if created_at_utc is None else created_at_utc
        with self._connection(immediate=True) as connection:
            row = connection.execute(
                """
                SELECT * FROM demo_command_idempotency
                WHERE scope = ? AND key_reference = ?
                """,
                (scope, key_reference),
            ).fetchone()
            if row is not None:
                if row["request_fingerprint"] != request_fingerprint:
                    raise DemoPersistenceError(
                        "IDEMPOTENCY_CONFLICT",
                        field="Idempotency-Key",
                        message="same key is bound to different input",
                    )
                return CommandClaim(
                    scope=scope,
                    key_reference=key_reference,
                    request_fingerprint=request_fingerprint,
                    status=cast(str, row["status"]),
                    result=self._decode(row["result_json"]),
                    replayed=True,
                )
            connection.execute(
                """
                INSERT INTO demo_command_idempotency(
                    scope, key_reference, request_fingerprint, status, result_json,
                    created_at_utc, updated_at_utc
                ) VALUES(?, ?, ?, 'PENDING', NULL, ?, ?)
                """,
                (scope, key_reference, request_fingerprint, now, now),
            )
        return CommandClaim(
            scope=scope,
            key_reference=key_reference,
            request_fingerprint=request_fingerprint,
            status="PENDING",
            result=None,
            replayed=False,
        )

    def complete_command(
        self,
        *,
        scope: str,
        key_reference: str,
        request_fingerprint: str,
        result: Mapping[str, object],
    ) -> None:
        now = utc_now()
        with self._connection(immediate=True) as connection:
            changed = connection.execute(
                """
                UPDATE demo_command_idempotency
                SET status = 'SUCCEEDED', result_json = ?, updated_at_utc = ?
                WHERE scope = ? AND key_reference = ? AND request_fingerprint = ?
                """,
                (
                    self._json(result),
                    now,
                    scope,
                    key_reference,
                    request_fingerprint,
                ),
            ).rowcount
            if changed != 1:
                raise DemoPersistenceError(
                    "IDEMPOTENCY_CONFLICT",
                    field="command",
                    message="command claim changed before completion",
                )

    def append_authorization_audit(
        self,
        *,
        correlation_id: str,
        actor_ref: str,
        capability: str,
        resource_type: str,
        resource_id: str | None,
        outcome: str,
        reason: str,
    ) -> None:
        with self._connection(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO demo_authorization_audit(
                    correlation_id, actor_ref, capability, resource_type,
                    resource_id, outcome, reason, occurred_at_utc
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    correlation_id,
                    actor_ref,
                    capability,
                    resource_type,
                    resource_id,
                    outcome,
                    reason,
                    utc_now(),
                ),
            )


class RunDatabase:
    """Per-run database initialized by the repository's migration chain."""

    REQUIRED_CORE_TABLES = frozenset(
        {
            "raw_import_batches",
            "raw_import_rows",
            "planning_snapshots",
            "schedule_versions",
            "audit_events",
            "publication_results",
            "publication_current_references",
            "execution_event_ledger",
            "replan_projection_checkpoints",
            "replan_requests",
            "replan_attempts",
            "replan_results",
        }
    )
    DEMO_TABLES = frozenset(
        {"demo_run_schema", "demo_artifacts", "demo_scenario_manifest", "demo_command_audit"}
    )

    def __init__(self, *, repository_root: Path, database_path: Path) -> None:
        self.repository_root = repository_root.resolve()
        self.database_path = database_path.resolve()
        self.database_url = f"sqlite:///{self.database_path.as_posix()}"
        self.engine: Engine = create_engine(
            self.database_url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

    @classmethod
    def migrate(cls, *, repository_root: Path, database_path: Path) -> RunDatabase:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{database_path.resolve().as_posix()}"
        configuration = Config(str(repository_root / "alembic.ini"))
        configuration.set_main_option(
            "script_location", str(repository_root / "backend" / "migrations")
        )
        configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
        try:
            command.upgrade(configuration, "head")
            database = cls(repository_root=repository_root, database_path=database_path)
            database._migrate_demo_tables()
            database.self_check()
            return database
        except DemoPersistenceError:
            raise
        except Exception as error:  # noqa: BLE001 - stable Demo error boundary
            raise DemoPersistenceError(
                "MIGRATION_FAILED",
                field="run_database",
                message="run database migration failed",
            ) from error

    def close(self) -> None:
        self.engine.dispose()

    def _migrate_demo_tables(self) -> None:
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS demo_run_schema (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    schema_version TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS demo_artifacts (
                    artifact_kind TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    document_version TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    canonical_json BLOB NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY(artifact_kind, artifact_id)
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS demo_scenario_manifest (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    scenario_id TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    manifest_fingerprint TEXT NOT NULL,
                    canonical_json BLOB NOT NULL,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS demo_command_audit (
                    audit_id TEXT PRIMARY KEY,
                    command_type TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    actor_ref TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    result_reference_json BLOB NOT NULL,
                    occurred_at_utc TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO demo_run_schema(singleton_id, schema_version)
                VALUES(1, ?)
                ON CONFLICT(singleton_id) DO NOTHING
                """,
                (RUN_SCHEMA_VERSION,),
            )

    def self_check(self) -> dict[str, object]:
        tables = set(inspect(self.engine).get_table_names())
        missing = sorted((self.REQUIRED_CORE_TABLES | self.DEMO_TABLES).difference(tables))
        if missing:
            raise DemoPersistenceError(
                "MIGRATION_FAILED",
                field="run_database.tables",
                message="run database is missing required tables",
            )
        with self.engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT schema_version FROM demo_run_schema WHERE singleton_id = 1"
            ).first()
            if row is None or row[0] != RUN_SCHEMA_VERSION:
                raise DemoPersistenceError(
                    "MIGRATION_FAILED",
                    field="run_database.schema_version",
                    message="run database Demo schema is incompatible",
                )
        return {
            "status": "PASS",
            "core_table_count": len(self.REQUIRED_CORE_TABLES),
            "demo_table_count": len(self.DEMO_TABLES),
            "schema_version": RUN_SCHEMA_VERSION,
        }

    def put_manifest(self, document: Mapping[str, object]) -> bool:
        payload = canonical_bytes(document)
        observed_fingerprint = f"sha256:{sha256(payload).hexdigest()}"
        scenario_id = document.get("scenario_id")
        profile_name = document.get("profile_name")
        seed = document.get("seed")
        if (
            not isinstance(scenario_id, str)
            or not isinstance(profile_name, str)
            or isinstance(seed, bool)
            or not isinstance(seed, int)
        ):
            raise DemoPersistenceError(
                "INVALID_DOCUMENT",
                field="scenario_manifest",
                message="scenario manifest identity is invalid",
            )
        with self.engine.begin() as connection:
            row = connection.exec_driver_sql(
                "SELECT canonical_json FROM demo_scenario_manifest WHERE singleton_id = 1"
            ).first()
            if row is not None:
                if bytes(row[0]) != payload:
                    raise DemoPersistenceError(
                        "IDEMPOTENCY_CONFLICT",
                        field="scenario_manifest",
                        message="manifest is immutable",
                    )
                return True
            connection.exec_driver_sql(
                """
                INSERT INTO demo_scenario_manifest(
                    singleton_id, scenario_id, profile_name, seed,
                    manifest_fingerprint, canonical_json, created_at_utc
                ) VALUES(1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scenario_id,
                    profile_name,
                    seed,
                    observed_fingerprint,
                    payload,
                    utc_now(),
                ),
            )
        return False

    def get_manifest(self) -> dict[str, object] | None:
        with self.engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT canonical_json, manifest_fingerprint FROM demo_scenario_manifest WHERE singleton_id = 1"
            ).first()
            if row is None:
                return None
            payload = bytes(row[0])
            if f"sha256:{sha256(payload).hexdigest()}" != row[1]:
                raise DemoPersistenceError(
                    "PERSISTENCE_FAILED",
                    field="scenario_manifest.fingerprint",
                    message="stored manifest failed integrity verification",
                )
            parsed = json.loads(payload.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise DemoPersistenceError(
                    "PERSISTENCE_FAILED",
                    field="scenario_manifest",
                    message="stored manifest is invalid",
                )
            return cast(dict[str, object], parsed)

    def put_artifact(
        self,
        *,
        artifact_kind: str,
        artifact_id: str,
        document_version: str,
        document: Mapping[str, object],
    ) -> bool:
        _require_identifier(artifact_kind, "artifact_kind")
        _require_identifier(artifact_id, "artifact_id")
        payload = canonical_bytes(document)
        observed_fingerprint = f"sha256:{sha256(payload).hexdigest()}"
        with self.engine.begin() as connection:
            row = connection.exec_driver_sql(
                """
                SELECT canonical_json FROM demo_artifacts
                WHERE artifact_kind = ? AND artifact_id = ?
                """,
                (artifact_kind, artifact_id),
            ).first()
            if row is not None:
                if bytes(row[0]) != payload:
                    raise DemoPersistenceError(
                        "IDEMPOTENCY_CONFLICT",
                        field=f"artifact.{artifact_kind}",
                        message="artifact identity is immutable",
                    )
                return True
            connection.exec_driver_sql(
                """
                INSERT INTO demo_artifacts(
                    artifact_kind, artifact_id, document_version, fingerprint,
                    canonical_json, created_at_utc
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_kind,
                    artifact_id,
                    document_version,
                    observed_fingerprint,
                    payload,
                    utc_now(),
                ),
            )
        return False

    def get_artifact(
        self, *, artifact_kind: str, artifact_id: str
    ) -> dict[str, object] | None:
        with self.engine.connect() as connection:
            row = connection.exec_driver_sql(
                """
                SELECT canonical_json, fingerprint FROM demo_artifacts
                WHERE artifact_kind = ? AND artifact_id = ?
                """,
                (artifact_kind, artifact_id),
            ).first()
            if row is None:
                return None
            payload = bytes(row[0])
            if f"sha256:{sha256(payload).hexdigest()}" != row[1]:
                raise DemoPersistenceError(
                    "PERSISTENCE_FAILED",
                    field=f"artifact.{artifact_kind}.fingerprint",
                    message="stored artifact failed integrity verification",
                )
            parsed = json.loads(payload.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise DemoPersistenceError(
                    "PERSISTENCE_FAILED",
                    field=f"artifact.{artifact_kind}",
                    message="stored artifact is invalid",
                )
            return cast(dict[str, object], parsed)

    def list_artifacts(self) -> tuple[dict[str, object], ...]:
        with self.engine.connect() as connection:
            rows = connection.exec_driver_sql(
                """
                SELECT artifact_kind, artifact_id, document_version, fingerprint,
                       created_at_utc FROM demo_artifacts
                ORDER BY artifact_kind, artifact_id
                """
            ).mappings().all()
            return tuple(dict(row) for row in rows)

    def append_command_audit(
        self,
        *,
        audit_id: str,
        command_type: str,
        request_fingerprint: str,
        actor_ref: str,
        correlation_id: str,
        result_reference: Mapping[str, object],
        occurred_at_utc: str,
    ) -> bool:
        payload = canonical_bytes(result_reference)
        with self.engine.begin() as connection:
            row = connection.exec_driver_sql(
                "SELECT result_reference_json FROM demo_command_audit WHERE audit_id = ?",
                (audit_id,),
            ).first()
            if row is not None:
                if bytes(row[0]) != payload:
                    raise DemoPersistenceError(
                        "IDEMPOTENCY_CONFLICT",
                        field="demo_command_audit",
                        message="audit identity is immutable",
                    )
                return True
            connection.exec_driver_sql(
                """
                INSERT INTO demo_command_audit(
                    audit_id, command_type, request_fingerprint, actor_ref,
                    correlation_id, result_reference_json, occurred_at_utc
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    command_type,
                    request_fingerprint,
                    actor_ref,
                    correlation_id,
                    payload,
                    occurred_at_utc,
                ),
            )
        return False


def prune_inactive_runs(
    *, control: ControlStore, paths: DemoRuntimePaths, retain: int = 3
) -> tuple[str, ...]:
    if retain < 0:
        raise ValueError("retain must be non-negative")
    candidates = control.inactive_runs()[retain:]
    removed: list[str] = []
    for record in candidates:
        database = paths.resolve_relative_database(record.database_relative_path)
        if database.parent != paths.run_directory(record.run_id):
            raise DemoPersistenceError(
                "PATH_ESCAPE",
                field="database_relative_path",
                message="stored run path is inconsistent",
            )
        paths.remove_run_directory(record.run_id)
        control.forget_run(record.run_id)
        removed.append(record.run_id)
    return tuple(removed)


def artifact_version(document: Mapping[str, object]) -> str:
    formal_validation = document.get("formal_validation")
    if isinstance(formal_validation, Mapping):
        nested_version = formal_validation.get("validation_report_version")
        if isinstance(nested_version, str):
            return nested_version
    semantic_version_fields = (
        "import_quality_report_version",
        "snapshot_version",
        "planning_snapshot_version",
        "problem_version",
        "planning_problem_version",
        "planning_solution_version",
        "solver_report_version",
        "validation_report_version",
        "kpi_version",
        "schedule_version_version",
        "change_report_version",
    )
    for field in semantic_version_fields:
        value = document.get(field)
        if isinstance(value, str):
            return value
    versions = [
        value
        for key, value in document.items()
        if key.endswith("_version")
        and key not in {"schema_set_version", "canonicalization_version"}
        and isinstance(value, str)
    ]
    return versions[0] if versions else "demo-json.v1"


def require_artifact_set(
    database: RunDatabase, expected_kinds: Sequence[str]
) -> None:
    observed = {str(item["artifact_kind"]) for item in database.list_artifacts()}
    missing = sorted(set(expected_kinds).difference(observed))
    if missing:
        raise DemoPersistenceError(
            "PERSISTENCE_FAILED",
            field="demo_artifacts",
            message="required planning artifacts are missing",
        )


__all__ = [
    "ACTIVE_JOB_STATUSES",
    "CONTROL_SCHEMA_VERSION",
    "CommandClaim",
    "ControlStore",
    "DemoPersistenceError",
    "DemoRuntimePaths",
    "JobRecord",
    "JobRegistration",
    "RUN_SCHEMA_VERSION",
    "RunDatabase",
    "RunRecord",
    "artifact_version",
    "canonical_bytes",
    "fingerprint",
    "key_reference",
    "prune_inactive_runs",
    "resolve_named_runtime_root",
    "require_artifact_set",
    "utc_now",
]
