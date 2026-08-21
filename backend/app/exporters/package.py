"""Deterministic, immutable P2 internal export package construction."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import csv
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Never, cast

from app.planning.contracts import canonical_contract_bytes, contract_fingerprint
from app.planning.reporting import build_kpi_v2, freeze_solver_report


EXPORT_MANIFEST_VERSION = "export-manifest.v1"
EXPORT_SCHEMA_SET_VERSION = "2.5.0"
EXPORT_PACKAGE_PROFILE = "p2-internal-export.v1"
EXPORT_CANONICALIZATION_VERSION = "canonical-json.v1"
CSV_DIALECT_VERSION = "rfc4180-lf.v1"

_PAYLOAD_ROLES = {
    "schedule.json": "VALIDATED_PLANNING_SOLUTION",
    "schedule_operations.csv": "SCHEDULE_OPERATIONS",
    "order_summary.csv": "ORDER_SUMMARY",
    "resource_load.csv": "RESOURCE_LOAD",
    "kpi.json": "KPI",
    "validation_report.json": "VALIDATION_REPORT",
    "solver_report.json": "SOLVER_REPORT",
    "import_quality_report.json": "IMPORT_QUALITY_REPORT",
    "scenario_manifest.json": "P2_CORRECTNESS_SCENARIO_MANIFEST",
}
_STATE_BOUNDARY = {
    "schedule_version": "NOT_CREATED",
    "export_job": "NOT_CREATED",
    "approval": "NOT_STARTED",
    "publication": "NOT_STARTED",
}
_DEFERRED_ARTIFACTS = [
    {"path": "benchmark_report.json", "status": "DEFERRED_P2_12"},
    {"path": "change_report.json", "status": "DEFERRED_P4_DYNAMIC_REPLAN"},
]

type JsonObject = dict[str, Any]


class ExportPackageErrorCode(StrEnum):
    """Stable P2 internal export rejection categories."""

    INVALID_PACKAGE = "INVALID_PACKAGE"
    MIXED_LINEAGE = "MIXED_LINEAGE"
    HASH_MISMATCH = "HASH_MISMATCH"
    COUNT_MISMATCH = "COUNT_MISMATCH"
    MISSING_FILE = "MISSING_FILE"
    SYNTHETIC_PROVENANCE_REQUIRED = "SYNTHETIC_PROVENANCE_REQUIRED"
    DESTINATION_CONFLICT = "DESTINATION_CONFLICT"
    IO_ERROR = "IO_ERROR"


class ExportPackageError(ValueError):
    """A deterministic package or filesystem-boundary rejection."""

    def __init__(
        self,
        code: ExportPackageErrorCode,
        *,
        field: str,
        message: str,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code.value} at {field}: {message}")


@dataclass(frozen=True, slots=True)
class InternalExportPackage:
    """An internal export represented as an immutable ordered byte collection."""

    package_id: str
    manifest_fingerprint: str
    _files: tuple[tuple[str, bytes], ...]

    @property
    def files(self) -> dict[str, bytes]:
        return dict(self._files)

    @property
    def manifest(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.files["manifest.json"]))

    def read_bytes(self, path: str) -> bytes:
        try:
            return self.files[path]
        except KeyError as error:
            raise ExportPackageError(
                ExportPackageErrorCode.MISSING_FILE,
                field=path,
                message="package file does not exist",
            ) from error


def _reject(code: ExportPackageErrorCode, field: str, message: str) -> Never:
    raise ExportPackageError(code, field=field, message=message)


def _sha256(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_contract_bytes(value)


def _csv_bytes(headers: tuple[str, ...], rows: Sequence[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(headers),
        extrasaction="raise",
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row[field] for field in headers})
    return stream.getvalue().encode("utf-8")


def _scenario_manifest(
    snapshot: Mapping[str, object],
    problem: Mapping[str, object],
    scenario_manifest: Mapping[str, object] | None,
) -> bytes:
    if snapshot.get("synthetic") is not True:
        if scenario_manifest is not None:
            _reject(
                ExportPackageErrorCode.MIXED_LINEAGE,
                "scenario_manifest",
                "non-synthetic Snapshot cannot carry synthetic provenance",
            )
        _reject(
            ExportPackageErrorCode.SYNTHETIC_PROVENANCE_REQUIRED,
            "snapshot.synthetic",
            "TASK-P2-11 is limited to validated synthetic exports",
        )
    if scenario_manifest is None:
        _reject(
            ExportPackageErrorCode.SYNTHETIC_PROVENANCE_REQUIRED,
            "scenario_manifest",
            "synthetic package requires its P2 correctness manifest",
        )
    provenance = cast(Mapping[str, object], snapshot["synthetic_provenance"])
    scenario = cast(Mapping[str, object], scenario_manifest.get("scenario", {}))
    profile = cast(Mapping[str, object], scenario_manifest.get("factory_profile", {}))
    assembler = cast(Mapping[str, object], scenario_manifest.get("assembler", {}))
    expected = cast(
        Mapping[str, object], scenario_manifest.get("expected_artifacts", {})
    )
    snapshot_import = cast(Mapping[str, object], snapshot["import_package"])
    if (
        scenario_manifest.get("correctness_manifest_version")
        != "p2-correctness-manifest.v1"
        or scenario.get("scenario_id") != provenance.get("scenario_id")
        or scenario.get("scenario_version") != provenance.get("scenario_version")
        or profile.get("profile_id") != provenance.get("factory_profile_id")
        or profile.get("profile_version") != provenance.get("profile_version")
        or assembler.get("generator_id") != provenance.get("generator_id")
        or assembler.get("generator_version") != provenance.get("generator_version")
        or scenario_manifest.get("seed") != provenance.get("seed")
        or expected.get("import_dataset_hash") != snapshot_import.get("dataset_hash")
        or expected.get("snapshot_hash") != snapshot.get("snapshot_hash")
        or expected.get("problem_hash") != problem.get("problem_hash")
    ):
        _reject(
            ExportPackageErrorCode.MIXED_LINEAGE,
            "scenario_manifest",
            "scenario manifest does not exactly bind Snapshot/Problem provenance",
        )
    return _json_bytes(scenario_manifest)


def _operation_rows(
    *,
    planning_run_id: str,
    problem: Mapping[str, object],
    solution: Mapping[str, object],
) -> list[JsonObject]:
    operations = {
        cast(str, item["operation_id"]): cast(Mapping[str, object], item)
        for item in cast(list[Mapping[str, object]], problem["operation_instances"])
    }
    rows: list[JsonObject] = []
    for assignment in cast(list[Mapping[str, object]], solution["assignments"]):
        operation_id = cast(str, assignment["operation_id"])
        operation = operations[operation_id]
        rows.append(
            {
                "planning_run_id": planning_run_id,
                "problem_hash": problem["problem_hash"],
                "solution_id": solution["solution_id"],
                "operation_id": operation_id,
                "demand_order_id": operation["demand_order_id"],
                "resource_id": assignment["resource_id"],
                "start_tick": assignment["start_tick"],
                "end_tick": assignment["end_tick"],
                "duration_ticks": assignment["duration_ticks"],
                "start_at_utc": assignment["start_at_utc"],
                "end_at_utc": assignment["end_at_utc"],
                "duration_seconds": assignment["duration_seconds"],
                "lock_ids": "|".join(cast(list[str], assignment["lock_ids"])),
                "execution_fact_ids": "|".join(
                    cast(list[str], assignment["execution_fact_ids"])
                ),
            }
        )
    rows.sort(key=lambda row: cast(str, row["operation_id"]))
    return rows


def _order_rows(
    planning_run_id: str, problem_hash: str, kpi: JsonObject
) -> list[JsonObject]:
    delivery = cast(JsonObject, kpi["delivery"])
    rows: list[JsonObject] = []
    for demand in cast(list[JsonObject], delivery["demands"]):
        rows.append(
            {
                "planning_run_id": planning_run_id,
                "problem_hash": problem_hash,
                "demand_order_id": demand["demand_order_id"],
                "due_at_utc": demand["due_at_utc"],
                "priority_weight": demand["priority_weight"],
                "completion_tick": demand["completion_tick"],
                "completion_at_utc": demand["completion_at_utc"],
                "tardiness_seconds": demand["tardiness_seconds"],
                "priority_weighted_tardiness_seconds": demand[
                    "priority_weighted_tardiness_seconds"
                ],
                "on_time": str(demand["on_time"]).lower(),
            }
        )
    return rows


def _resource_rows(
    planning_run_id: str, problem_hash: str, kpi: JsonObject
) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for resource in cast(list[JsonObject], kpi["resources"]):
        utilization = resource["utilization"]
        rows.append(
            {
                "planning_run_id": planning_run_id,
                "problem_hash": problem_hash,
                "resource_id": resource["resource_id"],
                "resource_code": resource["resource_code"],
                "calendar_id": resource["calendar_id"],
                "available_seconds": resource["available_seconds"],
                "planned_busy_seconds": resource["planned_busy_seconds"],
                "utilization": "" if utilization is None else utilization,
            }
        )
    return rows


_OPERATION_HEADERS = (
    "planning_run_id",
    "problem_hash",
    "solution_id",
    "operation_id",
    "demand_order_id",
    "resource_id",
    "start_tick",
    "end_tick",
    "duration_ticks",
    "start_at_utc",
    "end_at_utc",
    "duration_seconds",
    "lock_ids",
    "execution_fact_ids",
)
_ORDER_HEADERS = (
    "planning_run_id",
    "problem_hash",
    "demand_order_id",
    "due_at_utc",
    "priority_weight",
    "completion_tick",
    "completion_at_utc",
    "tardiness_seconds",
    "priority_weighted_tardiness_seconds",
    "on_time",
)
_RESOURCE_HEADERS = (
    "planning_run_id",
    "problem_hash",
    "resource_id",
    "resource_code",
    "calendar_id",
    "available_seconds",
    "planned_busy_seconds",
    "utilization",
)


def _file_record(
    path: str,
    role: str,
    media_type: str,
    content: bytes,
    row_count: int | None,
) -> JsonObject:
    return {
        "path": path,
        "role": role,
        "media_type": media_type,
        "sha256": _sha256(content),
        "size_bytes": len(content),
        "row_count": row_count,
    }


def _package_id_for(manifest: Mapping[str, object]) -> str:
    basis = {key: value for key, value in manifest.items() if key != "package_id"}
    return f"export-package-{sha256(_json_bytes(basis)).hexdigest()}"


def _kpi_id_for(kpi: Mapping[str, object]) -> str:
    basis = {key: value for key, value in kpi.items() if key != "kpi_id"}
    return f"kpi-{sha256(_json_bytes(basis)).hexdigest()}"


def build_internal_export_package(
    *,
    snapshot: Mapping[str, object],
    problem: Mapping[str, object],
    solution: Mapping[str, object],
    solver_report: Mapping[str, object],
    validation_report: Mapping[str, object],
    import_quality_report: Mapping[str, object],
    scenario_manifest: Mapping[str, object] | None,
) -> InternalExportPackage:
    """Build the complete, non-publishable P2 internal package in memory."""

    frozen_report = freeze_solver_report(solution, solver_report, validation_report)
    kpi = build_kpi_v2(
        snapshot=snapshot,
        problem=problem,
        solution=solution,
        solver_report=solver_report,
        validation_report=validation_report,
        import_quality_report=import_quality_report,
    )
    kpi_document = kpi.document
    scenario_bytes = _scenario_manifest(snapshot, problem, scenario_manifest)
    operation_rows = _operation_rows(
        planning_run_id=frozen_report.planning_run_id,
        problem=problem,
        solution=solution,
    )
    order_rows = _order_rows(
        frozen_report.planning_run_id,
        cast(str, problem["problem_hash"]),
        kpi_document,
    )
    resource_rows = _resource_rows(
        frozen_report.planning_run_id,
        cast(str, problem["problem_hash"]),
        kpi_document,
    )
    payloads: dict[str, bytes] = {
        "schedule.json": _json_bytes(solution),
        "schedule_operations.csv": _csv_bytes(_OPERATION_HEADERS, operation_rows),
        "order_summary.csv": _csv_bytes(_ORDER_HEADERS, order_rows),
        "resource_load.csv": _csv_bytes(_RESOURCE_HEADERS, resource_rows),
        "kpi.json": kpi.canonical_bytes,
        "validation_report.json": _json_bytes(validation_report),
        "solver_report.json": frozen_report.canonical_bytes,
        "import_quality_report.json": _json_bytes(import_quality_report),
        "scenario_manifest.json": scenario_bytes,
    }
    row_counts = {
        "schedule.json": None,
        "schedule_operations.csv": len(operation_rows),
        "order_summary.csv": len(order_rows),
        "resource_load.csv": len(resource_rows),
        "kpi.json": None,
        "validation_report.json": None,
        "solver_report.json": None,
        "import_quality_report.json": None,
        "scenario_manifest.json": None,
    }
    file_records = [
        _file_record(
            path,
            _PAYLOAD_ROLES[path],
            "text/csv; charset=utf-8" if path.endswith(".csv") else "application/json",
            payloads[path],
            row_counts[path],
        )
        for path in sorted(payloads)
    ]
    snapshot_provenance = cast(Mapping[str, object], snapshot["synthetic_provenance"])
    manifest_basis: JsonObject = {
        "export_manifest_version": EXPORT_MANIFEST_VERSION,
        "schema_set_version": EXPORT_SCHEMA_SET_VERSION,
        "package_profile": EXPORT_PACKAGE_PROFILE,
        "canonicalization_version": EXPORT_CANONICALIZATION_VERSION,
        "csv_dialect_version": CSV_DIALECT_VERSION,
        "planning_run_id": frozen_report.planning_run_id,
        "generated_at_utc": solver_report["finished_at_utc"],
        "publishable": False,
        "state_boundary": _STATE_BOUNDARY,
        "lineage": {
            "snapshot": {
                "snapshot_version": snapshot["snapshot_version"],
                "snapshot_id": snapshot["snapshot_id"],
                "snapshot_hash": snapshot["snapshot_hash"],
            },
            "problem": {
                "problem_version": problem["problem_version"],
                "problem_hash": problem["problem_hash"],
            },
            "solution": {
                "planning_solution_version": solution["planning_solution_version"],
                "solution_id": solution["solution_id"],
                "solution_fingerprint": contract_fingerprint(solution),
            },
            "validation_report": {
                "validation_report_version": validation_report[
                    "validation_report_version"
                ],
                "validation_report_fingerprint": contract_fingerprint(
                    validation_report
                ),
                "status": validation_report["status"],
            },
            "solver_report": {
                "solver_report_version": solver_report["solver_report_version"],
                "report_id": solver_report["report_id"],
                "solver_report_fingerprint": frozen_report.fingerprint,
            },
            "import_quality_report": {
                "report_version": import_quality_report["report_version"],
                "report_id": import_quality_report["report_id"],
                "import_quality_report_fingerprint": contract_fingerprint(
                    import_quality_report
                ),
                "status": import_quality_report["status"],
            },
            "kpi": {
                "kpi_version": kpi_document["kpi_version"],
                "kpi_id": kpi.kpi_id,
                "kpi_fingerprint": kpi.fingerprint,
            },
        },
        "entity_counts": {
            "snapshot_operation_count": cast(
                Mapping[str, int], snapshot["entity_counts"]
            )["operation_instances"],
            "problem_operation_count": len(
                cast(list[object], problem["operation_instances"])
            ),
            "assignment_count": len(cast(list[object], solution["assignments"])),
            "demand_count": len(cast(list[object], problem["delivery_demands"])),
            "resource_count": len(cast(list[object], problem["resources"])),
        },
        "file_count": len(file_records),
        "files": file_records,
        "deferred_artifacts": _DEFERRED_ARTIFACTS,
        "synthetic": True,
        "synthetic_provenance": snapshot_provenance,
    }
    package_id = _package_id_for(manifest_basis)
    manifest = {"package_id": package_id, **manifest_basis}
    manifest_bytes = _json_bytes(manifest)
    all_files = {"manifest.json": manifest_bytes, **payloads}
    package = InternalExportPackage(
        package_id=package_id,
        manifest_fingerprint=_sha256(manifest_bytes),
        _files=tuple(sorted(all_files.items())),
    )
    verify_internal_export_package(package)
    return package


def _csv_row_count(content: bytes, path: str) -> int:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ExportPackageError(
            ExportPackageErrorCode.INVALID_PACKAGE,
            field=path,
            message="CSV is not valid UTF-8",
        ) from error
    if "\r" in text:
        _reject(
            ExportPackageErrorCode.INVALID_PACKAGE,
            path,
            "CSV must use the frozen LF dialect",
        )
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        _reject(ExportPackageErrorCode.INVALID_PACKAGE, path, "CSV has no header")
    return len(rows) - 1


def _verify_internal_export_package(package: InternalExportPackage) -> None:
    """Recompute package identity, hashes, row counts, and cross-file lineage."""

    files = package.files
    expected_paths = {
        "manifest.json",
        "schedule.json",
        "schedule_operations.csv",
        "order_summary.csv",
        "resource_load.csv",
        "kpi.json",
        "validation_report.json",
        "solver_report.json",
        "import_quality_report.json",
        "scenario_manifest.json",
    }
    if set(files) != expected_paths:
        _reject(
            ExportPackageErrorCode.MISSING_FILE,
            "files",
            "package paths differ from the complete P2 internal profile",
        )
    json_paths = sorted(path for path in files if path.endswith(".json"))
    try:
        documents = {
            path: cast(JsonObject, json.loads(files[path])) for path in json_paths
        }
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExportPackageError(
            ExportPackageErrorCode.INVALID_PACKAGE,
            field="json",
            message="package JSON is not canonical-decodable UTF-8",
        ) from error
    manifest = documents["manifest.json"]
    schedule = documents["schedule.json"]
    kpi = documents["kpi.json"]
    validation = documents["validation_report.json"]
    solver = documents["solver_report.json"]
    quality = documents["import_quality_report.json"]
    scenario = documents["scenario_manifest.json"]
    if _json_bytes(manifest) != files["manifest.json"]:
        _reject(
            ExportPackageErrorCode.INVALID_PACKAGE,
            "manifest.json",
            "JSON bytes are not canonical-json.v1",
        )
    if (
        manifest.get("package_id") != package.package_id
        or _package_id_for(manifest) != package.package_id
    ):
        _reject(
            ExportPackageErrorCode.HASH_MISMATCH,
            "manifest.package_id",
            "package ID does not match canonical manifest content",
        )
    if _sha256(files["manifest.json"]) != package.manifest_fingerprint:
        _reject(
            ExportPackageErrorCode.HASH_MISMATCH,
            "manifest.json",
            "manifest fingerprint differs from exact bytes",
        )

    records = cast(list[JsonObject], manifest.get("files"))
    if manifest.get("file_count") != len(records):
        _reject(
            ExportPackageErrorCode.COUNT_MISMATCH,
            "manifest.file_count",
            "file_count must equal the file records array length",
        )
    record_paths = [cast(str, record["path"]) for record in records]
    if record_paths != sorted(expected_paths - {"manifest.json"}):
        _reject(
            ExportPackageErrorCode.INVALID_PACKAGE,
            "manifest.files",
            "file records must be sorted and cover every payload exactly once",
        )
    for record in records:
        path = cast(str, record["path"])
        content = files[path]
        if record["sha256"] != _sha256(content) or record["size_bytes"] != len(content):
            _reject(
                ExportPackageErrorCode.HASH_MISMATCH,
                path,
                "manifest hash/size differs from payload bytes",
            )
        expected_rows = _csv_row_count(content, path) if path.endswith(".csv") else None
        if record["row_count"] != expected_rows:
            _reject(
                ExportPackageErrorCode.COUNT_MISMATCH,
                path,
                "manifest row_count differs from decoded payload",
            )
        expected_media_type = (
            "text/csv; charset=utf-8" if path.endswith(".csv") else "application/json"
        )
        if (
            record.get("role") != _PAYLOAD_ROLES[path]
            or record.get("media_type") != expected_media_type
        ):
            _reject(
                ExportPackageErrorCode.INVALID_PACKAGE,
                path,
                "manifest role/media_type differs from the frozen profile",
            )
    for path in json_paths:
        if path != "manifest.json" and _json_bytes(documents[path]) != files[path]:
            _reject(
                ExportPackageErrorCode.INVALID_PACKAGE,
                path,
                "JSON bytes are not canonical-json.v1",
            )

    lineage = cast(JsonObject, manifest["lineage"])
    solution_ref = cast(JsonObject, lineage["solution"])
    validation_ref = cast(JsonObject, lineage["validation_report"])
    solver_ref = cast(JsonObject, lineage["solver_report"])
    quality_ref = cast(JsonObject, lineage["import_quality_report"])
    kpi_ref = cast(JsonObject, lineage["kpi"])
    kpi_inputs = cast(JsonObject, kpi["inputs"])
    snapshot_ref = cast(JsonObject, lineage["snapshot"])
    problem_ref = cast(JsonObject, lineage["problem"])
    kpi_snapshot = cast(JsonObject, kpi_inputs["snapshot"])
    kpi_problem = cast(JsonObject, kpi_inputs["problem"])
    kpi_solution = cast(JsonObject, kpi_inputs["solution"])
    kpi_validation = cast(JsonObject, kpi_inputs["validation_report"])
    kpi_solver = cast(JsonObject, kpi_inputs["solver_report"])
    kpi_quality = cast(JsonObject, kpi_inputs["import_quality_report"])
    schedule_problem = cast(JsonObject, schedule["problem"])
    if (
        manifest.get("planning_run_id") != solver.get("planning_run_id")
        or manifest.get("planning_run_id") != kpi.get("planning_run_id")
        or manifest.get("generated_at_utc") != solver.get("finished_at_utc")
        or snapshot_ref != kpi_snapshot
        or problem_ref != kpi_problem
        or problem_ref.get("problem_version") != schedule_problem.get("problem_version")
        or problem_ref.get("problem_hash") != schedule_problem.get("problem_hash")
        or validation.get("problem_hash") != problem_ref.get("problem_hash")
        or solution_ref["solution_id"] != schedule.get("solution_id")
        or solution_ref["solution_fingerprint"] != contract_fingerprint(schedule)
        or kpi_solution != solution_ref
        or validation_ref["validation_report_fingerprint"]
        != contract_fingerprint(validation)
        or validation_ref["status"] != "PASS"
        or kpi_validation != validation_ref
        or solver_ref["report_id"] != solver.get("report_id")
        or solver_ref["solver_report_fingerprint"] != contract_fingerprint(solver)
        or kpi_solver != solver_ref
        or quality_ref["report_id"] != quality.get("report_id")
        or quality_ref["import_quality_report_fingerprint"]
        != contract_fingerprint(quality)
        or quality_ref["status"] != "PASS"
        or kpi_quality != quality_ref
        or kpi_ref["kpi_id"] != kpi.get("kpi_id")
        or kpi_ref["kpi_id"] != _kpi_id_for(kpi)
        or kpi_ref["kpi_fingerprint"] != contract_fingerprint(kpi)
    ):
        _reject(
            ExportPackageErrorCode.MIXED_LINEAGE,
            "manifest.lineage",
            "JSON payloads do not share one exact run lineage",
        )
    try:
        freeze_solver_report(schedule, solver, validation)
    except ValueError as error:
        raise ExportPackageError(
            ExportPackageErrorCode.MIXED_LINEAGE,
            field="schedule/solver_report/validation_report",
            message="formal output contracts do not share one valid run lineage",
        ) from error

    csv_headers = {
        "schedule_operations.csv": _OPERATION_HEADERS,
        "order_summary.csv": _ORDER_HEADERS,
        "resource_load.csv": _RESOURCE_HEADERS,
    }
    csv_rows: dict[str, list[dict[str, str]]] = {}
    for path, expected_headers in csv_headers.items():
        reader = csv.DictReader(io.StringIO(files[path].decode("utf-8"), newline=""))
        rows = list(reader)
        if tuple(reader.fieldnames or ()) != expected_headers:
            _reject(
                ExportPackageErrorCode.INVALID_PACKAGE,
                path,
                "CSV headers differ from the frozen profile",
            )
        csv_rows[path] = rows
        if any(
            row.get("planning_run_id") != manifest["planning_run_id"]
            or row.get("problem_hash") != problem_ref["problem_hash"]
            for row in rows
        ):
            _reject(
                ExportPackageErrorCode.MIXED_LINEAGE,
                path,
                "CSV rows do not bind the manifest planning run and problem",
            )
    if any(
        row.get("solution_id") != schedule["solution_id"]
        for row in csv_rows["schedule_operations.csv"]
    ):
        _reject(
            ExportPackageErrorCode.MIXED_LINEAGE,
            "schedule_operations.csv",
            "operation rows do not bind the validated PlanningSolution",
        )

    assignment_by_operation = {
        cast(str, assignment["operation_id"]): assignment
        for assignment in cast(list[JsonObject], schedule["assignments"])
    }
    demand_ids = {
        cast(str, demand["demand_order_id"])
        for demand in cast(
            list[JsonObject], cast(JsonObject, kpi["delivery"])["demands"]
        )
    }
    for row in csv_rows["schedule_operations.csv"]:
        assignment = assignment_by_operation.get(cast(str, row["operation_id"]))
        if assignment is None or row["demand_order_id"] not in demand_ids:
            _reject(
                ExportPackageErrorCode.MIXED_LINEAGE,
                "schedule_operations.csv",
                "operation rows contain an unknown operation or demand",
            )
        expected_assignment_fields = {
            "resource_id": str(assignment["resource_id"]),
            "start_tick": str(assignment["start_tick"]),
            "end_tick": str(assignment["end_tick"]),
            "duration_ticks": str(assignment["duration_ticks"]),
            "start_at_utc": str(assignment["start_at_utc"]),
            "end_at_utc": str(assignment["end_at_utc"]),
            "duration_seconds": str(assignment["duration_seconds"]),
            "lock_ids": "|".join(cast(list[str], assignment["lock_ids"])),
            "execution_fact_ids": "|".join(
                cast(list[str], assignment["execution_fact_ids"])
            ),
        }
        if any(
            row[field] != value for field, value in expected_assignment_fields.items()
        ):
            _reject(
                ExportPackageErrorCode.MIXED_LINEAGE,
                "schedule_operations.csv",
                "operation row values differ from the validated PlanningSolution",
            )
    if files["order_summary.csv"] != _csv_bytes(
        _ORDER_HEADERS,
        _order_rows(
            cast(str, manifest["planning_run_id"]),
            cast(str, problem_ref["problem_hash"]),
            kpi,
        ),
    ) or files["resource_load.csv"] != _csv_bytes(
        _RESOURCE_HEADERS,
        _resource_rows(
            cast(str, manifest["planning_run_id"]),
            cast(str, problem_ref["problem_hash"]),
            kpi,
        ),
    ):
        _reject(
            ExportPackageErrorCode.MIXED_LINEAGE,
            "summary CSV",
            "order/resource rows differ from the immutable KPI",
        )

    counts = cast(JsonObject, manifest["entity_counts"])
    planning = cast(JsonObject, kpi["planning"])
    delivery = cast(JsonObject, kpi["delivery"])
    if (
        counts["assignment_count"] != len(cast(list[object], schedule["assignments"]))
        or counts["assignment_count"] != len(csv_rows["schedule_operations.csv"])
        or counts["assignment_count"] != planning["scheduled_operation_count"]
        or counts["problem_operation_count"] != counts["assignment_count"]
        or counts["demand_count"] != delivery["order_count"]
        or counts["demand_count"] != len(csv_rows["order_summary.csv"])
        or counts["resource_count"] != len(cast(list[object], kpi["resources"]))
        or counts["resource_count"] != len(csv_rows["resource_load.csv"])
    ):
        _reject(
            ExportPackageErrorCode.COUNT_MISMATCH,
            "manifest.entity_counts",
            "manifest, schedule, and KPI entity counts differ",
        )
    scenario_metadata = cast(JsonObject, scenario["scenario"])
    scenario_profile = cast(JsonObject, scenario["factory_profile"])
    scenario_assembler = cast(JsonObject, scenario["assembler"])
    scenario_expected = cast(JsonObject, scenario["expected_artifacts"])
    provenance = cast(JsonObject, manifest["synthetic_provenance"])
    if (
        manifest.get("export_manifest_version") != EXPORT_MANIFEST_VERSION
        or manifest.get("schema_set_version") != EXPORT_SCHEMA_SET_VERSION
        or manifest.get("canonicalization_version") != EXPORT_CANONICALIZATION_VERSION
        or manifest.get("csv_dialect_version") != CSV_DIALECT_VERSION
        or manifest.get("publishable") is not False
        or manifest.get("package_profile") != EXPORT_PACKAGE_PROFILE
        or manifest.get("synthetic") is not True
        or manifest.get("state_boundary") != _STATE_BOUNDARY
        or manifest.get("deferred_artifacts") != _DEFERRED_ARTIFACTS
        or scenario.get("correctness_manifest_version") != "p2-correctness-manifest.v1"
        or scenario_metadata.get("scenario_id") != provenance.get("scenario_id")
        or scenario_metadata.get("scenario_version")
        != provenance.get("scenario_version")
        or scenario_profile.get("profile_id") != provenance.get("factory_profile_id")
        or scenario_profile.get("profile_version") != provenance.get("profile_version")
        or scenario_assembler.get("generator_id") != provenance.get("generator_id")
        or scenario_assembler.get("generator_version")
        != provenance.get("generator_version")
        or scenario.get("seed") != provenance.get("seed")
        or scenario_expected.get("snapshot_hash") != snapshot_ref.get("snapshot_hash")
        or scenario_expected.get("problem_hash") != problem_ref.get("problem_hash")
    ):
        _reject(
            ExportPackageErrorCode.INVALID_PACKAGE,
            "manifest.boundary",
            "P2 package must remain synthetic, non-publishable, and explicitly deferred",
        )


def verify_internal_export_package(package: InternalExportPackage) -> None:
    """Reject malformed packages through the stable output error surface."""

    try:
        _verify_internal_export_package(package)
    except ExportPackageError:
        raise
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
        raise ExportPackageError(
            ExportPackageErrorCode.INVALID_PACKAGE,
            field="package",
            message="package structure does not match the frozen internal profile",
        ) from error


def _write_file(path: Path, content: bytes) -> None:
    path.write_bytes(content)


def _directory_matches(destination: Path, package: InternalExportPackage) -> bool:
    if not destination.is_dir():
        return False
    observed = {
        path.name: path.read_bytes() for path in destination.iterdir() if path.is_file()
    }
    return observed == package.files and len(list(destination.iterdir())) == len(
        observed
    )


def write_internal_export_package(
    package: InternalExportPackage,
    destination: Path,
    *,
    file_writer: Callable[[Path, bytes], None] = _write_file,
) -> Path:
    """Atomically materialize an internal package with exact-replay idempotency."""

    verify_internal_export_package(package)
    try:
        destination = destination.resolve()
        parent = destination.parent
        if not parent.is_dir():
            _reject(
                ExportPackageErrorCode.IO_ERROR,
                str(parent),
                "destination parent must already exist",
            )
        if destination.exists():
            if _directory_matches(destination, package):
                return destination
            _reject(
                ExportPackageErrorCode.DESTINATION_CONFLICT,
                str(destination),
                "existing destination is not the same immutable package",
            )

        temporary = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.tmp-", dir=str(parent))
        ).resolve()
    except ExportPackageError:
        raise
    except OSError as error:
        raise ExportPackageError(
            ExportPackageErrorCode.IO_ERROR,
            field=str(destination),
            message="could not prepare the atomic package destination",
        ) from error
    if temporary.parent != parent:
        _reject(
            ExportPackageErrorCode.IO_ERROR,
            str(temporary),
            "temporary directory escaped the destination parent",
        )
    try:
        for path, content in sorted(package.files.items()):
            if path != "manifest.json":
                file_writer(temporary / path, content)
        file_writer(temporary / "manifest.json", package.files["manifest.json"])
        os.replace(temporary, destination)
    except Exception as error:
        try:
            if temporary.exists() and temporary.parent == parent:
                shutil.rmtree(temporary)
        except OSError:
            pass
        if isinstance(error, ExportPackageError):
            raise
        try:
            if destination.exists() and _directory_matches(destination, package):
                return destination
        except OSError:
            pass
        raise ExportPackageError(
            ExportPackageErrorCode.IO_ERROR,
            field=str(destination),
            message="atomic package materialization failed",
        ) from error
    return destination


__all__ = [
    "CSV_DIALECT_VERSION",
    "EXPORT_CANONICALIZATION_VERSION",
    "EXPORT_MANIFEST_VERSION",
    "EXPORT_PACKAGE_PROFILE",
    "EXPORT_SCHEMA_SET_VERSION",
    "ExportPackageError",
    "ExportPackageErrorCode",
    "InternalExportPackage",
    "build_internal_export_package",
    "verify_internal_export_package",
    "write_internal_export_package",
]
