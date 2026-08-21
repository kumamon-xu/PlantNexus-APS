"""TASK-P2-11 deterministic package, lineage, and atomic-write integration."""

from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
from pathlib import Path

import pytest

from app.exporters import (
    ExportPackageError,
    ExportPackageErrorCode,
    InternalExportPackage,
    build_internal_export_package,
    verify_internal_export_package,
    write_internal_export_package,
)
from app.planning.reporting import ReportingContractError
from app.simulation.scenarios.p2_correctness import (
    CorrectnessReplay,
    execute_correctness_case,
    load_correctness_cases,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def replays() -> tuple[CorrectnessReplay, CorrectnessReplay]:
    cases = load_correctness_cases(ROOT)
    return (
        execute_correctness_case(cases[0], root=ROOT),
        execute_correctness_case(cases[1], root=ROOT),
    )


def _package(replay: CorrectnessReplay) -> InternalExportPackage:
    return build_internal_export_package(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
        scenario_manifest=replay.case.manifest,
    )


def _csv_rows(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8"), newline="")))


def test_same_input_produces_byte_identical_internal_package(
    replays: tuple[CorrectnessReplay, CorrectnessReplay],
) -> None:
    first = _package(replays[0])
    second = _package(replays[0])
    assert first == second
    assert first.package_id.startswith("export-package-")
    assert first.files == second.files
    verify_internal_export_package(first)


def test_manifest_hashes_counts_and_csv_lineage_are_exact(
    replays: tuple[CorrectnessReplay, CorrectnessReplay],
) -> None:
    replay = replays[0]
    package = _package(replay)
    manifest = package.manifest
    operation_rows = _csv_rows(package.read_bytes("schedule_operations.csv"))
    order_rows = _csv_rows(package.read_bytes("order_summary.csv"))
    resource_rows = _csv_rows(package.read_bytes("resource_load.csv"))

    assert manifest["publishable"] is False
    assert manifest["state_boundary"] == {
        "schedule_version": "NOT_CREATED",
        "export_job": "NOT_CREATED",
        "approval": "NOT_STARTED",
        "publication": "NOT_STARTED",
    }
    assert manifest["deferred_artifacts"] == [
        {"path": "benchmark_report.json", "status": "DEFERRED_P2_12"},
        {"path": "change_report.json", "status": "DEFERRED_P4_DYNAMIC_REPLAN"},
    ]
    assert len(operation_rows) == len(replay.solution["assignments"])
    assert len(order_rows) == len(replay.problem["delivery_demands"])
    assert len(resource_rows) == len(replay.problem["resources"])
    assert {
        row["planning_run_id"] for row in operation_rows + order_rows + resource_rows
    } == {replay.solver_report["planning_run_id"]}
    assert {
        row["problem_hash"] for row in operation_rows + order_rows + resource_rows
    } == {replay.problem["problem_hash"]}
    assert b"\r" not in package.read_bytes("schedule_operations.csv")


def test_mixed_run_and_scenario_provenance_are_rejected(
    replays: tuple[CorrectnessReplay, CorrectnessReplay],
) -> None:
    first, second = replays
    with pytest.raises(ReportingContractError):
        _ = build_internal_export_package(
            snapshot=first.snapshot_document,
            problem=first.problem,
            solution=first.solution,
            solver_report=second.solver_report,
            validation_report=first.validation_report,
            import_quality_report=first.quality_report,
            scenario_manifest=first.case.manifest,
        )
    with pytest.raises(ExportPackageError) as scenario:
        _ = build_internal_export_package(
            snapshot=first.snapshot_document,
            problem=first.problem,
            solution=first.solution,
            solver_report=first.solver_report,
            validation_report=first.validation_report,
            import_quality_report=first.quality_report,
            scenario_manifest=second.case.manifest,
        )
    assert scenario.value.code is ExportPackageErrorCode.MIXED_LINEAGE

    wrong_assembler = deepcopy(first.case.manifest)
    wrong_assembler["assembler"]["generator_version"] = "9.9.9"
    with pytest.raises(ExportPackageError) as assembler:
        _ = build_internal_export_package(
            snapshot=first.snapshot_document,
            problem=first.problem,
            solution=first.solution,
            solver_report=first.solver_report,
            validation_report=first.validation_report,
            import_quality_report=first.quality_report,
            scenario_manifest=wrong_assembler,
        )
    assert assembler.value.code is ExportPackageErrorCode.MIXED_LINEAGE


def test_tamper_and_missing_file_are_rejected(
    replays: tuple[CorrectnessReplay, CorrectnessReplay],
) -> None:
    package = _package(replays[0])
    tampered_files = package.files
    tampered_files["kpi.json"] += b" "
    tampered = InternalExportPackage(
        package_id=package.package_id,
        manifest_fingerprint=package.manifest_fingerprint,
        _files=tuple(sorted(tampered_files.items())),
    )
    with pytest.raises(ExportPackageError) as hash_error:
        verify_internal_export_package(tampered)
    assert hash_error.value.code is ExportPackageErrorCode.HASH_MISMATCH

    missing_files = package.files
    del missing_files["resource_load.csv"]
    missing = InternalExportPackage(
        package_id=package.package_id,
        manifest_fingerprint=package.manifest_fingerprint,
        _files=tuple(sorted(missing_files.items())),
    )
    with pytest.raises(ExportPackageError) as missing_error:
        verify_internal_export_package(missing)
    assert missing_error.value.code is ExportPackageErrorCode.MISSING_FILE

    malformed_files = package.files
    malformed_files["manifest.json"] = b"[]"
    malformed = InternalExportPackage(
        package_id=package.package_id,
        manifest_fingerprint=package.manifest_fingerprint,
        _files=tuple(sorted(malformed_files.items())),
    )
    with pytest.raises(ExportPackageError) as malformed_error:
        verify_internal_export_package(malformed)
    assert malformed_error.value.code is ExportPackageErrorCode.INVALID_PACKAGE


def test_atomic_write_is_idempotent_and_conflict_safe(
    tmp_path: Path,
    replays: tuple[CorrectnessReplay, CorrectnessReplay],
) -> None:
    package = _package(replays[0])
    destination = tmp_path / "export-package"
    assert write_internal_export_package(package, destination) == destination.resolve()
    assert write_internal_export_package(package, destination) == destination.resolve()
    assert {path.name for path in destination.iterdir()} == set(package.files)

    (destination / "kpi.json").write_bytes(b"tampered")
    with pytest.raises(ExportPackageError) as conflict:
        write_internal_export_package(package, destination)
    assert conflict.value.code is ExportPackageErrorCode.DESTINATION_CONFLICT


def test_partial_write_leaves_no_success_manifest_or_destination(
    tmp_path: Path,
    replays: tuple[CorrectnessReplay, CorrectnessReplay],
) -> None:
    package = _package(replays[0])
    destination = tmp_path / "partial-export"
    writes = 0

    def fail_after_one(path: Path, content: bytes) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("test-only injected write failure")
        path.write_bytes(content)

    with pytest.raises(ExportPackageError) as failure:
        write_internal_export_package(
            package,
            destination,
            file_writer=fail_after_one,
        )
    assert failure.value.code is ExportPackageErrorCode.IO_ERROR
    assert not destination.exists()
    assert not list(tmp_path.glob(".partial-export.tmp-*"))


def test_package_json_payloads_are_canonical_and_no_p3_artifact_exists(
    replays: tuple[CorrectnessReplay, CorrectnessReplay],
) -> None:
    package = _package(replays[0])
    assert "change_report.json" not in package.files
    assert "benchmark_report.json" not in package.files
    for path, content in package.files.items():
        if path.endswith(".json"):
            value = json.loads(content)
            assert (
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                == content
            )
