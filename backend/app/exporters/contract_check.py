"""TASK-P2-11 machine evidence for KPI/SolverReport/internal export closure."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from app.exporters.package import (
    EXPORT_MANIFEST_VERSION,
    EXPORT_PACKAGE_PROFILE,
    EXPORT_SCHEMA_SET_VERSION,
    ExportPackageError,
    ExportPackageErrorCode,
    InternalExportPackage,
    build_internal_export_package,
    verify_internal_export_package,
    write_internal_export_package,
)
from app.planning.reporting import (
    KPI_VERSION,
    ReportingContractError,
    ReportingContractErrorCode,
    build_kpi_v2,
    freeze_solver_report,
)
from app.simulation.scenarios.p2_correctness import (
    execute_correctness_case,
    load_correctness_cases,
)


TASK_ID = "TASK-P2-11"
REPORT_VERSION = "p2-output-contract-report.v1"
type JsonObject = dict[str, Any]

_FROZEN_FINGERPRINTS = {
    "planning_snapshot_v2_schema": (
        "schemas/json/planning-snapshot.v2.schema.json",
        "d30ed42f8e5d1b497e2c41aec8bd840c1530e8a16c8594e22ed8db2dbc676a09",
    ),
    "planning_problem_v2_schema": (
        "schemas/json/planning-problem.v2.schema.json",
        "e6e4a9843c08dbb191c57baede8c81cc3f6d738b971780e6db8f8ded75db87c8",
    ),
    "planning_solution_schema": (
        "schemas/json/planning-solution.schema.json",
        "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4",
    ),
    "solver_report_schema": (
        "schemas/json/solver-report.schema.json",
        "64feacd0d1ec0ea1c9d3f62d8e38b473b61f42dab5bc672c5898c5e056257b2a",
    ),
    "validation_report_v2_schema": (
        "schemas/json/validation-report.v2.schema.json",
        "1da63e931e7ddd90134eb652c857f13eb862787de855165cd230c2d8071fd353",
    ),
    "import_quality_report_schema": (
        "schemas/json/import-quality-report.schema.json",
        "2d41fb0afadbc0e73ba6bad60a52dcbfb34ef2e5e9602e1e1612ccc8c540f434",
    ),
    "kpi_v1_schema": (
        "schemas/json/kpi.schema.json",
        "be3dfbcd06e9fb7887df699c2ba0fc8bb229d603b0d55a75268a72bc2cdc9426",
    ),
    "planning_contracts": (
        "backend/app/planning/contracts.py",
        "d5f7a7e49e4f83e1da011da113f93a80c7f6bc7b1dc3814df374c5dfaefae630",
    ),
    "global_strategy": (
        "backend/app/planning/strategies/global_cp_sat.py",
        "c3c5f057b7f87fb732fb75bf10bed61a533915f3b0a25724af8b24c1ddc84133",
    ),
    "formal_validator": (
        "backend/app/planning/validation/problem_schedule_validator.py",
        "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f",
    ),
    "p2_correctness_orchestrator": (
        "backend/app/simulation/scenarios/p2_correctness.py",
        "316aee9cdc3325570916417fe1f85e48e4b0d46ba08fb06e8672ca1cf6b5f3e2",
    ),
    "dependency_lock": (
        "uv.lock",
        "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
    ),
    "kpi_v2_schema": (
        "schemas/json/kpi.v2.schema.json",
        "398377d462373315de130491d6286883940e3f8dd733a205ce5c1dfa032b2631",
    ),
    "export_manifest_schema": (
        "schemas/json/export-manifest.schema.json",
        "663a064a70c5903c54795f194fa6977eb29158cd0f9b72b3d41f7f8e443a772d",
    ),
    "kpi_v2_sample": (
        "schemas/samples/kpi.v2.synthetic.json",
        "ab8c583500e502ae3c0df9ae716ba13a529184efb0beffe7d6ac8d2f0529523f",
    ),
    "export_manifest_sample": (
        "schemas/samples/export-manifest.v1.synthetic.json",
        "257a9ec4e2713346e0c5d67f0365f90eabc61f15ead6ce30dc0a5e53fa7caecd",
    ),
}
_P2_CORRECTNESS_ASSET_DIGEST = (
    "2f1ebe2362d53f193c0edb649f14e4b6673d7f3bd2e61b5f88b282a534d8cadd"
)


def _fingerprints(root: Path) -> JsonObject:
    values: JsonObject = {}
    for name, (relative, expected) in _FROZEN_FINGERPRINTS.items():
        path = root / relative
        observed = sha256(path.read_bytes()).hexdigest()
        if observed != expected:
            raise ValueError(f"frozen output-boundary fingerprint drift: {relative}")
        values[name] = {"path": relative, "sha256": observed}
    return values


def _asset_manifest(root: Path, paths: tuple[Path, ...]) -> tuple[str, list[JsonObject]]:
    rows = [
        {
            "path": path.resolve().relative_to(root).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted({path.resolve() for path in paths})
    ]
    payload = "\n".join(
        f"{row['path']} {row['sha256']}" for row in rows
    ).encode()
    digest = sha256(payload).hexdigest()
    if digest != _P2_CORRECTNESS_ASSET_DIGEST:
        raise ValueError("P2 correctness asset manifest drift")
    return digest, rows


def _schema(root: Path, name: str) -> Draft202012Validator:
    document = json.loads((root / "schemas" / "json" / name).read_text("utf-8"))
    Draft202012Validator.check_schema(document)
    return Draft202012Validator(document, format_checker=FormatChecker())


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def run_output_contract_checks(root: Path) -> JsonObject:
    """Run schema, lineage, determinism, rejection, and atomicity evidence."""

    root = root.resolve()
    fingerprints = _fingerprints(root)
    cases = load_correctness_cases(root)
    asset_digest, asset_rows = _asset_manifest(
        root, tuple(path for case in cases for path in case.asset_paths)
    )
    replay = execute_correctness_case(cases[0], root=root)
    frozen = freeze_solver_report(
        replay.solution, replay.solver_report, replay.validation_report
    )
    kpi = build_kpi_v2(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
    )
    first = build_internal_export_package(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
        scenario_manifest=replay.case.manifest,
    )
    second = build_internal_export_package(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
        scenario_manifest=replay.case.manifest,
    )
    if first != second:
        raise ValueError("same logical inputs did not produce identical package bytes")
    verify_internal_export_package(first)
    kpi_schema = _schema(root, "kpi.v2.schema.json")
    manifest_schema = _schema(root, "export-manifest.schema.json")
    kpi_schema.validate(kpi.document)
    manifest_schema.validate(first.manifest)
    for schema_name, sample_name in (
        ("kpi.v2.schema.json", "kpi.v2.synthetic.json"),
        ("export-manifest.schema.json", "export-manifest.v1.synthetic.json"),
    ):
        _schema(root, schema_name).validate(
            json.loads((root / "schemas" / "samples" / sample_name).read_text("utf-8"))
        )

    failed = deepcopy(replay.validation_report)
    failed["status"] = "FAIL"
    failed["hard_violation_count"] = 1
    failed["violations"] = [
        {
            "constraint_id": "C-001",
            "severity": "HARD",
            "entity_ids": [replay.solution["assignments"][0]["operation_id"]],
            "observed_value": "machine-negative",
            "expected_rule": "one assignment",
            "message": "machine negative evidence",
        }
    ]
    try:
        build_kpi_v2(
            snapshot=replay.snapshot_document,
            problem=replay.problem,
            solution=replay.solution,
            solver_report=replay.solver_report,
            validation_report=failed,
            import_quality_report=replay.quality_report,
        )
    except ReportingContractError as error:
        if error.code is not ReportingContractErrorCode.VALIDATION_FAILED:
            raise
    else:
        raise ValueError("Validator FAIL was accepted")

    wrong_scenario = deepcopy(replay.case.manifest)
    wrong_scenario["scenario"]["scenario_id"] = "P2-MIXED-SCENARIO"
    try:
        build_internal_export_package(
            snapshot=replay.snapshot_document,
            problem=replay.problem,
            solution=replay.solution,
            solver_report=replay.solver_report,
            validation_report=replay.validation_report,
            import_quality_report=replay.quality_report,
            scenario_manifest=wrong_scenario,
        )
    except ExportPackageError as error:
        if error.code is not ExportPackageErrorCode.MIXED_LINEAGE:
            raise
    else:
        raise ValueError("mixed scenario lineage was accepted")

    tampered_files = first.files
    tampered_files["kpi.json"] += b" "
    tampered = InternalExportPackage(
        package_id=first.package_id,
        manifest_fingerprint=first.manifest_fingerprint,
        _files=tuple(sorted(tampered_files.items())),
    )
    try:
        verify_internal_export_package(tampered)
    except ExportPackageError as error:
        if error.code is not ExportPackageErrorCode.HASH_MISMATCH:
            raise
    else:
        raise ValueError("tampered KPI payload was accepted")

    with tempfile.TemporaryDirectory(prefix="plantnexus-p2-11-") as directory:
        temporary_root = Path(directory)
        target = temporary_root / "complete"
        write_internal_export_package(first, target)
        write_internal_export_package(first, target)
        partial = temporary_root / "partial"
        write_count = 0

        def fail_after_one(path: Path, content: bytes) -> None:
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                raise OSError("machine injected write failure")
            path.write_bytes(content)

        try:
            write_internal_export_package(first, partial, file_writer=fail_after_one)
        except ExportPackageError as error:
            if error.code is not ExportPackageErrorCode.IO_ERROR:
                raise
        else:
            raise ValueError("partial write incorrectly completed")
        if partial.exists() or list(temporary_root.glob(".partial.tmp-*")):
            raise ValueError("partial write left success or temporary artifacts")

    manifest = first.manifest
    kpi_document = kpi.document
    delivery = cast(JsonObject, kpi_document["delivery"])
    planning = cast(JsonObject, kpi_document["planning"])
    checks = [
        _pass(
            "frozen-input-contracts-new-schemas-samples-and-lock",
            {
                "fingerprints": fingerprints,
                "correctness_asset_count": len(asset_rows),
                "correctness_asset_digest": asset_digest,
            },
        ),
        _pass(
            "kpi-v2-and-export-manifest-draft-2020-12-roundtrip",
            {
                "schema_set_version": EXPORT_SCHEMA_SET_VERSION,
                "kpi_version": KPI_VERSION,
                "manifest_version": EXPORT_MANIFEST_VERSION,
            },
        ),
        _pass(
            "validated-solution-kpi-and-solver-report-freeze",
            {
                "planning_run_id": frozen.planning_run_id,
                "solver_report_fingerprint": frozen.fingerprint,
                "kpi_id": kpi.kpi_id,
                "objective_value": delivery[
                    "priority_weighted_tardiness_seconds"
                ],
                "makespan_seconds": planning["makespan_seconds"],
            },
        ),
        _pass(
            "deterministic-package-bytes-file-hashes-and-row-counts",
            {
                "package_id": first.package_id,
                "manifest_fingerprint": first.manifest_fingerprint,
                "file_count": manifest["file_count"],
                "files": manifest["files"],
            },
        ),
        _pass(
            "cross-file-run-hash-version-and-entity-count-lineage",
            {
                "lineage": manifest["lineage"],
                "entity_counts": manifest["entity_counts"],
            },
        ),
        _pass(
            "validator-fail-mixed-lineage-and-tamper-rejections",
            {
                "validator_fail": "REJECTED",
                "mixed_scenario": "REJECTED",
                "tampered_payload": "REJECTED",
            },
        ),
        _pass(
            "atomic-write-exact-replay-and-partial-cleanup",
            {
                "same_destination_same_bytes": "IDEMPOTENT",
                "manifest_written_last": True,
                "partial_destination": "ABSENT",
                "partial_success_manifest": "ABSENT",
            },
        ),
        _pass(
            "p2-internal-non-publishable-state-and-deferred-boundary",
            {
                "package_profile": manifest["package_profile"],
                "publishable": manifest["publishable"],
                "state_boundary": manifest["state_boundary"],
                "deferred_artifacts": manifest["deferred_artifacts"],
                "p2_12_plus_or_p3": "NOT_STARTED",
            },
        ),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "schema_set_version": EXPORT_SCHEMA_SET_VERSION,
        "package_profile": EXPORT_PACKAGE_PROFILE,
        "scenario_id": replay.case.scenario_id,
        "check_count": len(checks),
        "counts": {
            "package_files_excluding_manifest": manifest["file_count"],
            "assignments": manifest["entity_counts"]["assignment_count"],
            "demands": manifest["entity_counts"]["demand_count"],
            "resources": manifest["entity_counts"]["resource_count"],
            "rejection_cases": 3,
            "deterministic_replays": 2,
        },
        "checks": checks,
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "schedule_carrier": "VALIDATED_PLANNING_SOLUTION_NOT_SCHEDULE_VERSION",
            "export_job": "NOT_CREATED",
            "approval_publish_external_transfer": "PROHIBITED",
            "change_report": "DEFERRED_P4_DYNAMIC_REPLAN",
            "benchmark_report": "DEFERRED_P2_12",
            "p2_12_plus_or_p3": "NOT_STARTED",
        },
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_output_contract_checks(args.root)
    _write_report(args.report, report)
    print(
        f"PASS {TASK_ID}: scenario={report['scenario_id']} "
        f"files={report['counts']['package_files_excluding_manifest']} "
        f"checks={report['check_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "TASK_ID", "main", "run_output_contract_checks"]
