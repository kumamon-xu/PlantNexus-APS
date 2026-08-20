"""Exact TASK-P1-11 DATA_ERROR rejection evidence through common ingress."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from app.application import (
    CommonIngressPipeline,
    DataQualityGateRejected,
)
from app.application.p1_gate_report import p1_gate_configuration
import app.application.import_pipeline as pipeline_module
from app.importers import RawImportRow, StagedImportBatch
from app.normalization import (
    NormalizationError,
    NormalizationInput,
    UnitConversionRegistry,
)
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


def _mutate(
    batch: StagedImportBatch,
    source_record_id: str,
    field: str,
    value: object,
) -> StagedImportBatch:
    rows: list[RawImportRow] = []
    found = False
    for row in batch.rows:
        outer = cast(dict[str, Any], json.loads(row.raw_payload))
        if outer["source_record_id"] == source_record_id:
            payload = cast(dict[str, object], json.loads(outer["payload_json"]))
            payload[field] = value
            outer["payload_json"] = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            raw_payload = json.dumps(
                outer,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            found = True
        else:
            raw_payload = row.raw_payload
        rows.append(replace(row, raw_payload=raw_payload))
    assert found
    content = b"\n".join(row.raw_payload for row in rows)
    digest = sha256(content).hexdigest()
    return replace(
        batch,
        batch_id=f"negative-{digest[:24]}",
        idempotency_key=f"negative-{digest}",
        content_sha256=digest,
        content_length_bytes=len(content),
        rows=tuple(rows),
    )


@pytest.mark.parametrize(
    ("source_record_id", "field", "value", "expected_stage", "expected_code"),
    (
        (
            "routing-edge-001-002",
            "successor_routing_operation_id",
            "routing-operation-001-001",
            "data_validation",
            "ROUTE_CYCLE",
        ),
        (
            "routing-option-001-001-001",
            "resource_id",
            "missing-resource",
            "data_validation",
            "MISSING_RESOURCE",
        ),
        (
            "routing-option-001-001-001",
            "cycle_unit",
            "unregistered-duration-unit",
            "normalization",
            "UNIT_CONVERSION_ERROR",
        ),
        (
            "routing-option-001-001-001",
            "final_duration_seconds",
            None,
            "normalization",
            "MISSING_DURATION",
        ),
    ),
)
def test_exact_p1_rejection_stops_before_the_next_stage(
    monkeypatch: pytest.MonkeyPatch,
    source_record_id: str,
    field: str,
    value: object,
    expected_stage: str,
    expected_code: str,
) -> None:
    context = _context()
    registry = _registry()
    batch = _mutate(
        DeterministicSyntheticPackageGenerator(registry).prepare_batch(context),
        source_record_id,
        field,
        value,
    )

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("a rejected stage invoked a downstream boundary")

    if expected_stage == "normalization":
        monkeypatch.setattr(pipeline_module, "validate_import_package", forbidden)
        with pytest.raises(NormalizationError) as rejected:
            CommonIngressPipeline(registry).run(
                (NormalizationInput(batch, p1_mapping_profile(context)),),
                configuration=p1_gate_configuration(),
            )
        assert rejected.value.category == "DATA_ERROR"
        assert rejected.value.code.value == expected_code
    else:
        monkeypatch.setattr(pipeline_module, "expand_orders", forbidden)
        with pytest.raises(DataQualityGateRejected) as rejected:
            CommonIngressPipeline(registry).run(
                (NormalizationInput(batch, p1_mapping_profile(context)),),
                configuration=p1_gate_configuration(),
            )
        assert rejected.value.stage == expected_stage
        assert rejected.value.category == "DATA_ERROR"
        assert rejected.value.code == expected_code
        assert {error["code"] for error in rejected.value.errors} == {expected_code}
