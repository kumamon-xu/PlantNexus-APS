"""TEST-SCENARIO-REPLAY evidence for the P1 common-ingress pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml

from app.application import CommonIngressPipeline
from app.application.p1_gate_report import (
    p1_gate_configuration,
    run_p1_gate_checks,
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
UNIT_REGISTRY = ROOT / "schemas" / "rules" / "unit-conversion-registry.v1.yaml"


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
        dict[str, object], yaml.safe_load(UNIT_REGISTRY.read_text(encoding="utf-8"))
    )
    return UnitConversionRegistry.from_mapping(document)


def test_public_synthetic_staging_replays_import_snapshot_and_problem() -> None:
    context = _context()
    registry = _registry()
    generator = DeterministicSyntheticPackageGenerator(registry)
    pipeline = CommonIngressPipeline(registry)
    first_batch = generator.prepare_batch(context)
    replay_batch = generator.prepare_batch(context)

    first = pipeline.run(
        (NormalizationInput(first_batch, p1_mapping_profile(context)),),
        configuration=p1_gate_configuration(),
    )
    replay = pipeline.run(
        (NormalizationInput(replay_batch, p1_mapping_profile(context)),),
        configuration=p1_gate_configuration(),
    )

    assert first_batch == replay_batch
    assert first.normalization.canonical_bytes == replay.normalization.canonical_bytes
    assert first.normalization.dataset_hash == (
        "sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4"
    )
    assert first.snapshot.canonical_bytes == replay.snapshot.canonical_bytes
    assert first.snapshot.snapshot_hash == (
        "sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409"
    )
    assert first.problem.canonical_bytes == replay.problem.canonical_bytes
    assert first.problem.problem_hash == (
        "sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da"
    )
    generated = generator.generate(context)
    assert generated.canonical_dataset == first.normalization.canonical_bytes
    assert generated.dataset_hash == first.normalization.dataset_hash


def test_machine_report_records_replay_rejections_and_p1_boundaries() -> None:
    report = run_p1_gate_checks(
        root=ROOT,
        scenario_root=SCENARIO_ROOT,
        repeat=2,
    )

    assert report["report_version"] == "p1-data-pipeline-report.v1"
    assert report["result"] == "PASS"
    assert report["check_count"] == 14
    assert all(cast(dict[str, bool], report["checks"]).values())
    assert report["issues"] == []
    assert report["boundaries"] == {
        "terminal_artifact": "PlanningProblem",
        "solver_executed": False,
        "candidate_schedule_created": False,
        "schedule_validator_executed": False,
        "production_binding_claimed": False,
        "production_readiness_claimed": False,
        "p2_entered": False,
    }
    rejections = cast(dict[str, dict[str, object]], report["rejections"])
    assert {name: evidence["code"] for name, evidence in rejections.items()} == {
        "route_cycle": "ROUTE_CYCLE",
        "missing_resource": "MISSING_RESOURCE",
        "unit_conversion_error": "UNIT_CONVERSION_ERROR",
        "missing_duration": "MISSING_DURATION",
    }
    assert all(evidence["category"] == "DATA_ERROR" for evidence in rejections.values())
    assert all(evidence["passed"] is True for evidence in rejections.values())
