"""TEST-P1-COMMON-INGRESS ReferenceFileAdapter/Synthetic parity evidence."""

from __future__ import annotations

import ast
import csv
import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from app.application import CommonIngressPipeline
from app.application.p1_gate_report import p1_gate_configuration
from app.importers import (
    REFERENCE_FILE_ADAPTER_ID,
    REFERENCE_FILE_ADAPTER_VERSION,
    REFERENCE_HEADERS,
    ImportStagingError,
    ReferenceFileAdapter,
    SourceFileManifest,
    StagingDataPlane,
    StagingErrorCode,
)
from app.normalization import NormalizationInput, UnitConversionRegistry
from app.simulation.generators import (
    DeterministicSyntheticPackageGenerator,
    GenerationContext,
    p1_mapping_profile,
)
from app.simulation.profiles.contracts import FactoryProfileDocument
from app.simulation.scenarios.contracts import ScenarioSpecDocument


ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = ROOT / "fixtures" / "synthetic" / "SIM-P1-INGRESS-001"


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _context() -> GenerationContext:
    return GenerationContext.from_documents(
        profile=cast(
            FactoryProfileDocument, _json(SCENARIO_ROOT / "factory-profile.json")
        ),
        scenario=cast(
            ScenarioSpecDocument, _json(SCENARIO_ROOT / "scenario-spec.json")
        ),
        target="test",
    )


def _registry() -> UnitConversionRegistry:
    document = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / "schemas/rules/unit-conversion-registry.v1.yaml").read_text(
                encoding="utf-8"
            )
        ),
    )
    return UnitConversionRegistry.from_mapping(document)


def _write_reference_csv(path: Path, raw_rows: tuple[object, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(REFERENCE_HEADERS)
        for raw_row in raw_rows:
            row = cast(Any, raw_row)
            outer = cast(dict[str, str], json.loads(row.raw_payload))
            writer.writerow(
                (
                    outer["record_type"],
                    outer["source_record_id"],
                    outer["payload_json"],
                )
            )


def test_reference_adapter_and_generator_share_the_exact_staging_to_problem_chain(
    tmp_path: Path,
) -> None:
    context = _context()
    registry = _registry()
    generator = DeterministicSyntheticPackageGenerator(registry)
    generated_batch = generator.prepare_batch(context)
    reference_path = tmp_path / "p1-ingress.csv"
    _write_reference_csv(reference_path, cast(tuple[object, ...], generated_batch.rows))
    reference_batch = ReferenceFileAdapter().prepare_batch(
        source_root=tmp_path,
        source=SourceFileManifest(
            adapter_id=REFERENCE_FILE_ADAPTER_ID,
            adapter_version=REFERENCE_FILE_ADAPTER_VERSION,
            relative_path=reference_path.name,
            batch_id="reference-p1-ingress",
            idempotency_key="reference-p1-ingress",
            source_system=generated_batch.source_system,
            source_version=generated_batch.source_version,
            received_at=generated_batch.received_at,
            data_plane=generated_batch.data_plane,
            synthetic_provenance=generated_batch.synthetic_provenance,
        ),
    )
    pipeline = CommonIngressPipeline(registry)
    profile = p1_mapping_profile(context)
    generated = pipeline.run(
        (NormalizationInput(generated_batch, profile),),
        configuration=p1_gate_configuration(),
    )
    reference = pipeline.run(
        (NormalizationInput(reference_batch, profile),),
        configuration=p1_gate_configuration(),
    )

    assert generated_batch.rows != reference_batch.rows
    assert generated_batch.content_sha256 != reference_batch.content_sha256
    assert generated.normalization.canonical_bytes == reference.normalization.canonical_bytes
    assert generated.normalization.dataset_hash == reference.normalization.dataset_hash
    assert generated.quality.canonical_bytes == reference.quality.canonical_bytes
    assert generated.expansion.canonical_bytes == reference.expansion.canonical_bytes
    assert generated.snapshot == reference.snapshot
    assert generated.problem == reference.problem


def test_application_rejects_cross_plane_input_before_normalization() -> None:
    context = _context()
    registry = _registry()
    batch = DeterministicSyntheticPackageGenerator(registry).prepare_batch(context)
    configuration = p1_gate_configuration()
    production_configuration = type(configuration)(
        expected_data_plane=StagingDataPlane.PRODUCTION,
        cutoff_at_utc=configuration.cutoff_at_utc,
        horizon_end_utc=configuration.horizon_end_utc,
        tick_seconds=configuration.tick_seconds,
        problem_builder_version=configuration.problem_builder_version,
    )

    with pytest.raises(ImportStagingError) as rejected:
        CommonIngressPipeline(registry).run(
            (NormalizationInput(batch, p1_mapping_profile(context)),),
            configuration=production_configuration,
        )
    assert rejected.value.code is StagingErrorCode.DATA_PLANE_MISMATCH


def test_application_boundary_has_no_solver_validator_persistence_or_api_shortcut() -> None:
    application_root = ROOT / "backend" / "app" / "application"
    imported_modules_by_file: dict[str, set[str]] = {}
    for path in sorted(application_root.glob("*.py")):
        imported_modules: set[str] = set()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules.add(node.module)
        imported_modules_by_file[path.name] = imported_modules
    forbidden = (
        "app.api",
        "app.exporters",
        "app.infrastructure",
        "app.planning.backends",
        "app.planning.strategies",
        "app.planning.validation",
        "ortools",
        "sqlalchemy",
    )
    evidence_only_exception = {
        "p2_gate_report.py": {"app.exporters.contract_check"},
        "p3_gate_report.py": {
            "app.api.planning_workspace_check",
            "app.infrastructure.workspace_persistence_check",
        },
    }
    for filename, imported_modules in imported_modules_by_file.items():
        observed = {
            module
            for module in imported_modules
            if any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in forbidden
            )
        }
        assert observed == evidence_only_exception.get(filename, set())
