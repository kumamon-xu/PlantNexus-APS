"""TEST-EXECUTION-EVENT-CONTRACT-001 P4-09 carrier consumption evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.domain.execution_contracts import require_p4_document
from app.simulation.execution import ArtifactReference, ExecutionSimulator
from app.simulation.execution.simulator_check import build_execution_simulator_fixture


ROOT = Path(__file__).resolve().parents[3]


class _Ingress:
    def ingest_event(self, document: object) -> object:
        return document


def _validator(name: str) -> Draft202012Validator:
    schemas: dict[str, dict[str, object]] = {}
    resources: list[tuple[str, Resource[object]]] = []
    for path in sorted((ROOT / "schemas/json").glob("*.json")):
        schema = cast(
            dict[str, object], json.loads(path.read_text(encoding="utf-8"))
        )
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    return Draft202012Validator(
        schemas[name],
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


def test_core_outputs_only_existing_execution_event_and_manifest_contracts() -> None:
    fixture = build_execution_simulator_fixture()
    result = ExecutionSimulator().run(fixture.config, fixture.schedule, _Ingress())
    event_validator = _validator("execution-event.schema.json")
    for event in result.events:
        assert require_p4_document(event) == "execution-event.v1"
        event_validator.validate(event)

    manifest = result.build_manifest(fact_checkpoint=fixture.fact_checkpoint)
    assert require_p4_document(manifest) == "execution-simulation-manifest.v1"
    _validator("execution-simulation-manifest.schema.json").validate(manifest)
    assert manifest["event_stream"] == {
        "event_count": 3,
        "first_position": 1,
        "last_position": 3,
        "ordered_event_ids": list(result.event_ids),
        "ordered_event_fingerprints": list(result.event_fingerprints),
        "stream_fingerprint": result.stream_fingerprint,
    }


def test_manifest_requires_explicit_downstream_fact_checkpoint_reference() -> None:
    fixture = build_execution_simulator_fixture()
    result = ExecutionSimulator().run(fixture.config, fixture.schedule, _Ingress())
    explicit = ArtifactReference(
        document_version="execution-fact-checkpoint.v1",
        artifact_id="fact-checkpoint-contract-test",
        fingerprint=f"sha256:{'c' * 64}",
    )

    manifest = result.build_manifest(fact_checkpoint=explicit)

    checkpoint = cast(dict[str, object], manifest["checkpoint"])
    assert checkpoint["fact_checkpoint"] == explicit.as_document()
    assert checkpoint["last_applied_position"] == 3
