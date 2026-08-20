"""Build the machine-readable TASK-P1-11 common-ingress gate report."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, cast

import yaml

from app import SCHEMA_VERSION, SPEC_VERSION
from app.application.import_pipeline import (
    CommonIngressArtifacts,
    CommonIngressPipeline,
    DataQualityGateRejected,
    PlanningBuildConfiguration,
)
from app.data_validation import (
    DATA_QUALITY_RULE_VERSION,
    ERROR_REGISTRY_VERSION,
    IMPORT_QUALITY_REPORT_VERSION,
    REPORT_CANONICALIZATION_VERSION,
)
from app.domain.contracts import JsonValue
from app.importers import (
    REFERENCE_FILE_ADAPTER_ID,
    REFERENCE_FILE_ADAPTER_VERSION,
    REFERENCE_HEADERS,
    RawImportRow,
    ReferenceFileAdapter,
    SourceFileManifest,
    StagedImportBatch,
    StagingDataPlane,
)
from app.normalization import (
    CANONICALIZATION_VERSION,
    NORMALIZATION_CONTRACT_VERSION,
    NormalizationError,
    NormalizationInput,
    UnitConversionRegistry,
)
from app.planning.problem import (
    PLANNING_PROBLEM_VERSION,
    PROBLEM_BUILDER_VERSION,
    PROBLEM_CANONICALIZATION_VERSION,
    PROBLEM_HASH_PROJECTION_VERSION,
)
from app.simulation.generators import (
    DeterministicSyntheticPackageGenerator,
    GenerationContext,
    p1_mapping_profile,
)
from app.simulation.profiles.contracts import FactoryProfileDocument
from app.simulation.scenarios.contracts import ScenarioSpecDocument
from app.snapshots import (
    SNAPSHOT_CANONICALIZATION_VERSION,
    SNAPSHOT_HASH_PROJECTION_VERSION,
    SNAPSHOT_VERSION,
)


REPORT_VERSION = "p1-data-pipeline-report.v1"
TEST_IDS = (
    "TEST-P1-COMMON-INGRESS",
    "TEST-SCENARIO-REPLAY",
    "TEST-SNAPSHOT-REPLAY-001",
    "TEST-PROBLEM-REPLAY-001",
    "TEST-DATA-QUALITY-001",
    "TEST-SIM-ISOLATION",
)
P1_GATE_CUTOFF_AT_UTC = "2026-11-06T12:30:00Z"
P1_GATE_HORIZON_END_UTC = "2026-11-07T12:30:00Z"
P1_GATE_TICK_SECONDS = 60
_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")

type JsonObject = dict[str, Any]
type PayloadMutation = Callable[[JsonObject], None]


def _canonical_bytes(document: Mapping[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _load_context(scenario_root: Path) -> GenerationContext:
    profile = cast(
        FactoryProfileDocument,
        json.loads((scenario_root / "factory-profile.json").read_text(encoding="utf-8")),
    )
    scenario = cast(
        ScenarioSpecDocument,
        json.loads((scenario_root / "scenario-spec.json").read_text(encoding="utf-8")),
    )
    return GenerationContext.from_documents(
        profile=profile,
        scenario=scenario,
        target="test",
    )


def _load_unit_registry(root: Path) -> UnitConversionRegistry:
    path = root / "schemas" / "rules" / "unit-conversion-registry.v1.yaml"
    document = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    return UnitConversionRegistry.from_mapping(document)


def p1_gate_configuration() -> PlanningBuildConfiguration:
    """Return the explicit fixture-local horizon used by P1 replay evidence."""

    return PlanningBuildConfiguration(
        expected_data_plane=StagingDataPlane.SIMULATION,
        cutoff_at_utc=P1_GATE_CUTOFF_AT_UTC,
        horizon_end_utc=P1_GATE_HORIZON_END_UTC,
        tick_seconds=P1_GATE_TICK_SECONDS,
        problem_builder_version=PROBLEM_BUILDER_VERSION,
    )


def _run_batch(
    pipeline: CommonIngressPipeline,
    context: GenerationContext,
    batch: StagedImportBatch,
) -> CommonIngressArtifacts:
    return pipeline.run(
        (NormalizationInput(batch, p1_mapping_profile(context)),),
        configuration=p1_gate_configuration(),
    )


def _artifact_projection(artifacts: CommonIngressArtifacts) -> JsonObject:
    records = cast(Mapping[str, object], artifacts.normalization.document["records"])
    counts = {
        collection: len(cast(Sequence[object], values))
        for collection, values in records.items()
        if collection != "canonical_records_version"
    }
    return {
        "import": {
            "package_id": artifacts.normalization.document["package_id"],
            "dataset_hash": artifacts.normalization.dataset_hash,
            "canonical_bytes_sha256": _digest(
                artifacts.normalization.canonical_bytes
            ),
        },
        "quality": {
            "report_id": artifacts.quality.document["report_id"],
            "status": artifacts.quality.document["status"],
            "error_count": artifacts.quality.document["error_count"],
            "canonical_bytes_sha256": _digest(artifacts.quality.canonical_bytes),
        },
        "expansion": {
            "expansion_hash": artifacts.expansion.expansion_hash,
            "canonical_bytes_sha256": _digest(artifacts.expansion.canonical_bytes),
        },
        "snapshot": {
            "snapshot_id": artifacts.snapshot.snapshot_id,
            "snapshot_hash": artifacts.snapshot.snapshot_hash,
            "canonical_bytes_sha256": _digest(artifacts.snapshot.canonical_bytes),
        },
        "problem": {
            "problem_hash": artifacts.problem.problem_hash,
            "canonical_bytes_sha256": _digest(artifacts.problem.canonical_bytes),
        },
        "entity_counts": dict(sorted(counts.items())),
        "record_count": sum(counts.values()),
        "operation_instance_count": len(
            artifacts.expansion.document["operation_instances"]
        ),
        "precedence_edge_count": len(
            artifacts.expansion.document["operation_precedence_edges"]
        ),
    }


def _write_reference_csv(path: Path, batch: StagedImportBatch) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(REFERENCE_HEADERS)
        for row in batch.rows:
            outer = cast(JsonObject, json.loads(row.raw_payload))
            writer.writerow(
                (
                    outer["record_type"],
                    outer["source_record_id"],
                    outer["payload_json"],
                )
            )


def _reference_batch(batch: StagedImportBatch) -> StagedImportBatch:
    with TemporaryDirectory(prefix="plantnexus-p1-reference-") as temporary:
        source_root = Path(temporary)
        path = source_root / "p1-ingress-records.csv"
        _write_reference_csv(path, batch)
        manifest = SourceFileManifest(
            adapter_id=REFERENCE_FILE_ADAPTER_ID,
            adapter_version=REFERENCE_FILE_ADAPTER_VERSION,
            relative_path=path.name,
            batch_id="p1-gate-reference-batch",
            idempotency_key="p1-gate-reference-import",
            source_system=batch.source_system,
            source_version=batch.source_version,
            received_at=batch.received_at,
            data_plane=batch.data_plane,
            synthetic_provenance=batch.synthetic_provenance,
        )
        return ReferenceFileAdapter().prepare_batch(
            source_root=source_root,
            source=manifest,
        )


def _mutated_batch(
    batch: StagedImportBatch,
    *,
    label: str,
    source_record_id: str,
    mutation: PayloadMutation,
) -> StagedImportBatch:
    rows: list[RawImportRow] = []
    found = False
    for row in batch.rows:
        outer = cast(JsonObject, json.loads(row.raw_payload))
        if outer.get("source_record_id") == source_record_id:
            payload = cast(JsonObject, json.loads(cast(str, outer["payload_json"])))
            mutation(payload)
            outer["payload_json"] = _canonical_bytes(payload).decode("utf-8")
            raw_payload = _canonical_bytes(outer)
            found = True
        else:
            raw_payload = row.raw_payload
        rows.append(
            RawImportRow(
                row_identity=row.row_identity,
                source_location=row.source_location,
                raw_payload=raw_payload,
            )
        )
    if not found:
        raise ValueError(f"P1 rejection source record is missing: {source_record_id}")
    content = b"\n".join(row.raw_payload for row in rows)
    digest = sha256(content).hexdigest()
    return replace(
        batch,
        batch_id=f"p1-gate-{label}-{digest[:16]}",
        idempotency_key=f"p1-gate-{label}-{digest}",
        content_sha256=digest,
        content_length_bytes=len(content),
        rows=tuple(rows),
    )


def _set(field: str, value: JsonValue) -> PayloadMutation:
    def mutate(payload: JsonObject) -> None:
        payload[field] = value

    return mutate


def _negative_cases(batch: StagedImportBatch) -> tuple[tuple[str, str, StagedImportBatch], ...]:
    return (
        (
            "route_cycle",
            "ROUTE_CYCLE",
            _mutated_batch(
                batch,
                label="route-cycle",
                source_record_id="routing-edge-001-002",
                mutation=_set(
                    "successor_routing_operation_id", "routing-operation-001-001"
                ),
            ),
        ),
        (
            "missing_resource",
            "MISSING_RESOURCE",
            _mutated_batch(
                batch,
                label="missing-resource",
                source_record_id="routing-option-001-001-001",
                mutation=_set("resource_id", "missing-resource"),
            ),
        ),
        (
            "unit_conversion_error",
            "UNIT_CONVERSION_ERROR",
            _mutated_batch(
                batch,
                label="unit-conversion-error",
                source_record_id="routing-option-001-001-001",
                mutation=_set("cycle_unit", "unregistered-duration-unit"),
            ),
        ),
        (
            "missing_duration",
            "MISSING_DURATION",
            _mutated_batch(
                batch,
                label="missing-duration",
                source_record_id="routing-option-001-001-001",
                mutation=_set("final_duration_seconds", None),
            ),
        ),
    )


def _rejection_projection(
    pipeline: CommonIngressPipeline,
    context: GenerationContext,
    batch: StagedImportBatch,
) -> JsonObject:
    try:
        _run_batch(pipeline, context, batch)
    except NormalizationError as error:
        return {
            "stage": "normalization",
            "category": error.category,
            "code": error.code.value,
            "all_codes": [error.code.value],
        }
    except DataQualityGateRejected as error:
        return {
            "stage": error.stage,
            "category": error.category,
            "code": error.code,
            "all_codes": [item["code"] for item in error.errors],
            "quality_report_id": error.report["report_id"],
            "error_count": error.report["error_count"],
        }
    raise AssertionError("negative P1 ingress case was accepted")


def _repository_state(root: Path) -> JsonObject:
    environment_commit = os.environ.get("PLANTNEXUS_CODE_COMMIT", "").lower()
    if _COMMIT_SHA.fullmatch(environment_commit):
        commit = environment_commit
    else:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        commit = completed.stdout.strip().lower()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"commit": commit, "working_tree_dirty": bool(dirty)}


def run_p1_gate_checks(
    *,
    root: Path,
    scenario_root: Path,
    repeat: int,
) -> JsonObject:
    """Run both ingress forms, deterministic replay, and exact P1 rejections."""

    if repeat < 2:
        raise ValueError("P1 gate replay requires repeat >= 2")
    context = _load_context(scenario_root)
    unit_registry = _load_unit_registry(root)
    generator = DeterministicSyntheticPackageGenerator(unit_registry)
    pipeline = CommonIngressPipeline(unit_registry)

    synthetic_batches = tuple(generator.prepare_batch(context) for _ in range(repeat))
    synthetic_runs = tuple(
        _run_batch(pipeline, context, batch) for batch in synthetic_batches
    )
    baseline = synthetic_runs[0]
    reference_batch = _reference_batch(synthetic_batches[0])
    reference = _run_batch(pipeline, context, reference_batch)
    generated_package = generator.generate(context)

    rejections: JsonObject = {}
    rejection_checks: dict[str, bool] = {}
    for name, expected_code, batch in _negative_cases(synthetic_batches[0]):
        observed = _rejection_projection(pipeline, context, batch)
        observed["expected_code"] = expected_code
        observed["passed"] = (
            observed["category"] == "DATA_ERROR" and observed["code"] == expected_code
        )
        rejections[name] = observed
        rejection_checks[f"exact_rejection_{name}"] = cast(bool, observed["passed"])

    checks = {
        "synthetic_staging_replay": all(
            batch == synthetic_batches[0] for batch in synthetic_batches[1:]
        ),
        "same_input_same_import_bytes_hash": all(
            run.normalization.canonical_bytes == baseline.normalization.canonical_bytes
            and run.normalization.dataset_hash == baseline.normalization.dataset_hash
            for run in synthetic_runs[1:]
        ),
        "same_input_same_snapshot_bytes_hash": all(
            run.snapshot.canonical_bytes == baseline.snapshot.canonical_bytes
            and run.snapshot.snapshot_hash == baseline.snapshot.snapshot_hash
            for run in synthetic_runs[1:]
        ),
        "same_input_same_problem_bytes_hash": all(
            run.problem.canonical_bytes == baseline.problem.canonical_bytes
            and run.problem.problem_hash == baseline.problem.problem_hash
            for run in synthetic_runs[1:]
        ),
        "reference_and_synthetic_import_parity": (
            reference.normalization.canonical_bytes
            == baseline.normalization.canonical_bytes
            and reference.normalization.dataset_hash
            == baseline.normalization.dataset_hash
        ),
        "reference_and_synthetic_snapshot_parity": (
            reference.snapshot.canonical_bytes == baseline.snapshot.canonical_bytes
            and reference.snapshot.snapshot_hash == baseline.snapshot.snapshot_hash
        ),
        "reference_and_synthetic_problem_parity": (
            reference.problem.canonical_bytes == baseline.problem.canonical_bytes
            and reference.problem.problem_hash == baseline.problem.problem_hash
        ),
        "generator_generate_reuses_staging_result": (
            generated_package.canonical_dataset
            == baseline.normalization.canonical_bytes
            and generated_package.dataset_hash == baseline.normalization.dataset_hash
        ),
        "quality_gate_passed_before_expansion": (
            baseline.quality.passed
            and baseline.quality.document["error_count"] == 0
        ),
        "terminal_artifact_is_solver_neutral_problem": (
            baseline.problem.document["problem_version"] == PLANNING_PROBLEM_VERSION
        ),
        **rejection_checks,
    }
    issues = sorted(name for name, passed in checks.items() if not passed)
    return {
        "report_version": REPORT_VERSION,
        "result": "PASS" if not issues else "FAIL",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repository": _repository_state(root),
        "spec_version": SPEC_VERSION,
        "schema_set_version": SCHEMA_VERSION,
        "scenario": {
            "scenario_id": context.scenario_id,
            "scenario_version": context.scenario_version,
            "profile_id": context.profile_id,
            "profile_version": context.profile_version,
            "generator_id": context.generator_id,
            "generator_version": context.generator_version,
            "seed": context.seed,
        },
        "versions": {
            "raw_staging": "raw-staging.v1",
            "reference_adapter": REFERENCE_FILE_ADAPTER_VERSION,
            "mapping_profile": p1_mapping_profile(context).profile_version,
            "normalization": NORMALIZATION_CONTRACT_VERSION,
            "import_canonicalization": CANONICALIZATION_VERSION,
            "unit_registry": unit_registry.version,
            "data_quality_rules": DATA_QUALITY_RULE_VERSION,
            "error_registry": ERROR_REGISTRY_VERSION,
            "quality_report": IMPORT_QUALITY_REPORT_VERSION,
            "quality_report_canonicalization": REPORT_CANONICALIZATION_VERSION,
            "expansion": baseline.expansion.document["expansion_version"],
            "snapshot": SNAPSHOT_VERSION,
            "snapshot_canonicalization": SNAPSHOT_CANONICALIZATION_VERSION,
            "snapshot_hash_projection": SNAPSHOT_HASH_PROJECTION_VERSION,
            "problem": PLANNING_PROBLEM_VERSION,
            "problem_builder": PROBLEM_BUILDER_VERSION,
            "problem_canonicalization": PROBLEM_CANONICALIZATION_VERSION,
            "problem_hash_projection": PROBLEM_HASH_PROJECTION_VERSION,
        },
        "planning_configuration": {
            "cutoff_at_utc": P1_GATE_CUTOFF_AT_UTC,
            "horizon_end_utc": P1_GATE_HORIZON_END_UTC,
            "tick_seconds": P1_GATE_TICK_SECONDS,
            "data_plane": StagingDataPlane.SIMULATION.value,
        },
        "sources": {
            "synthetic_generator": {
                "repeat": repeat,
                "batch_id": synthetic_batches[0].batch_id,
                "content_sha256": synthetic_batches[0].content_sha256,
                "row_count": len(synthetic_batches[0].rows),
                "artifacts": _artifact_projection(baseline),
            },
            "reference_file_adapter": {
                "adapter_id": REFERENCE_FILE_ADAPTER_ID,
                "adapter_version": REFERENCE_FILE_ADAPTER_VERSION,
                "production_binding": False,
                "batch_id": reference_batch.batch_id,
                "content_sha256": reference_batch.content_sha256,
                "row_count": len(reference_batch.rows),
                "artifacts": _artifact_projection(reference),
            },
        },
        "rejections": rejections,
        "boundaries": {
            "terminal_artifact": "PlanningProblem",
            "solver_executed": False,
            "candidate_schedule_created": False,
            "schedule_validator_executed": False,
            "production_binding_claimed": False,
            "production_readiness_claimed": False,
            "p2_entered": False,
        },
        "test_ids": list(TEST_IDS),
        "check_count": len(checks),
        "checks": dict(sorted(checks.items())),
        "issues": issues,
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_p1_gate_checks(
            root=arguments.root.resolve(),
            scenario_root=arguments.scenario.resolve(),
            repeat=arguments.repeat,
        )
    except ValueError as error:
        parser.error(str(error))
    _write_report(arguments.report, report)
    hashes = report["sources"]["synthetic_generator"]["artifacts"]
    print(
        f"{report['result']} P1 common ingress: "
        f"import={hashes['import']['dataset_hash']} "
        f"snapshot={hashes['snapshot']['snapshot_hash']} "
        f"problem={hashes['problem']['problem_hash']} "
        f"checks={report['check_count']}"
    )
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P1_GATE_CUTOFF_AT_UTC",
    "P1_GATE_HORIZON_END_UTC",
    "P1_GATE_TICK_SECONDS",
    "REPORT_VERSION",
    "TEST_IDS",
    "main",
    "p1_gate_configuration",
    "run_p1_gate_checks",
]
