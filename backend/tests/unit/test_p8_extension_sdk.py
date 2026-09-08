"""Unit tests for the dependency-free APS Extension SDK values and protocols."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aps_extension_sdk import (
    Constraint,
    ConstraintContext,
    ConstraintOutput,
    ExtensionContractError,
    ExtensionErrorCode,
    ExtensionInputView,
    ObjectiveOutput,
    ObjectiveSense,
    ObjectiveStage,
    ReplanAction,
    ReplanContext,
    ReplanDecision,
    SemanticVersion,
    VersionInterval,
    fingerprint_json,
    freeze_json,
    parse_compatibility_policy,
    parse_extension_manifest,
    resolve_manifest_set,
    validate_protocol_output,
)


ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "backend/aps_extension_sdk/contracts/samples"


def _json(name: str) -> dict[str, Any]:
    value = json.loads((SAMPLES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_semver_is_strict_ordered_and_half_open() -> None:
    lower = SemanticVersion.parse("1.0.0")
    upper = SemanticVersion.parse("2.0.0")
    interval = VersionInterval(lower, upper)
    assert interval.contains(lower)
    assert interval.contains(SemanticVersion.parse("1.99.999"))
    assert not interval.contains(upper)
    for invalid in ("1", "1.0", "01.0.0", "1.0.0-alpha", "latest", "^1.0.0"):
        with pytest.raises(ExtensionContractError) as captured:
            SemanticVersion.parse(invalid)
        assert captured.value.code is ExtensionErrorCode.INCOMPATIBLE_SDK_VERSION


def test_registry_resolution_is_independent_of_manifest_input_order() -> None:
    first_document = _json("extension-manifest.v1.synthetic.json")
    second_document = json.loads(json.dumps(first_document))
    second_document["extension_id"] = "com.example.additive_rules"
    second_document["contributions"] = [
        contribution
        for contribution in second_document["contributions"]
        if contribution["extension_point"] not in {"REPLAN_POLICY", "PLUGIN_REGISTRY"}
    ]
    for contribution in second_document["contributions"]:
        contribution["contribution_id"] = contribution["contribution_id"].replace(
            "com.example.", "com.example.additive_"
        )
        contribution["validation_rule_ids"] = [
            value.replace("com.example.", "com.example.additive_")
            for value in contribution["validation_rule_ids"]
        ]
        contribution["validates_contribution_ids"] = [
            value.replace("com.example.", "com.example.additive_")
            for value in contribution["validates_contribution_ids"]
        ]
    second_document.pop("manifest_fingerprint")
    second_document["manifest_fingerprint"] = fingerprint_json(second_document)
    first = parse_extension_manifest(first_document)
    second = parse_extension_manifest(second_document)
    policy = parse_compatibility_policy(
        _json("extension-compatibility.v1.synthetic.json")
    )
    forward = resolve_manifest_set((first, second), policy)
    reverse = resolve_manifest_set((second, first), policy)
    assert forward == reverse


def test_protocol_is_structural_and_returns_only_frozen_values() -> None:
    manifest = parse_extension_manifest(_json("extension-manifest.v1.synthetic.json"))
    descriptor = next(
        item for item in manifest.contributions if item.extension_point.value == "CONSTRAINT"
    )

    class SampleConstraint:
        def __init__(self) -> None:
            self.descriptor = descriptor

        def contribute(self, context: ConstraintContext) -> ConstraintOutput:
            return ConstraintOutput(
                contribution_id=self.descriptor.contribution_id,
                constraint_contract_version="com.example.capacity.constraint.v1",
                constraint_specification=freeze_json(
                    {"capacity": 2, "scope": context.input_view.scope}
                ),  # type: ignore[arg-type]
                validation_rule_ids=self.descriptor.validation_rule_ids,
            )

    input_view = ExtensionInputView.from_json(
        view_contract_version="extension-input.v1",
        extension_id="com.example.manufacturing",
        contribution_id=descriptor.contribution_id,
        input_fingerprint="sha256:" + "1" * 64,
        scope={"factory_id": "factory-001"},
        facts={"resources": []},
        provenance={"problem_fingerprint": "sha256:" + "2" * 64},
    )
    implementation = SampleConstraint()
    assert isinstance(implementation, Constraint)
    result = implementation.contribute(ConstraintContext(input_view))
    assert result.validation_rule_ids == ("com.example.capacity.validator",)


def test_objective_value_is_integer_scaled_and_in_closed_stage() -> None:
    evidence = freeze_json({"amount_minor": 25})
    assert not isinstance(evidence, dict)
    output = ObjectiveOutput(
        contribution_id="com.example.cost.objective",
        metric_id="com.example.cost.metric",
        stage=ObjectiveStage.ENTERPRISE_TIE_BREAK,
        sense=ObjectiveSense.MINIMIZE,
        integer_value=25,
        integer_scale=100,
        authority_reference="com.example.cost.authority.v1",
        evidence=evidence,  # type: ignore[arg-type]
    )
    assert output.integer_value == 25
    with pytest.raises(ExtensionContractError) as captured:
        ObjectiveOutput(
            contribution_id="com.example.cost.objective",
            metric_id="com.example.cost.metric",
            stage=ObjectiveStage.ENTERPRISE_TIE_BREAK,
            sense=ObjectiveSense.MINIMIZE,
            integer_value=True,
            integer_scale=100,
            authority_reference="com.example.cost.authority.v1",
            evidence=evidence,  # type: ignore[arg-type]
        )
    assert captured.value.code is ExtensionErrorCode.INVALID_OBJECTIVE_STAGE


def test_replan_output_must_echo_all_closed_authority_bindings() -> None:
    manifest = parse_extension_manifest(_json("extension-manifest.v1.synthetic.json"))
    descriptor = next(
        item
        for item in manifest.contributions
        if item.extension_point.value == "REPLAN_POLICY"
    )
    input_view = ExtensionInputView.from_json(
        view_contract_version="extension-replan-input.v1",
        extension_id=manifest.extension_id,
        contribution_id=descriptor.contribution_id,
        input_fingerprint="sha256:" + "1" * 64,
        scope={"factory_id": "factory-001"},
        facts={"event_refs": ["event-001"]},
        provenance={"problem_fingerprint": "sha256:" + "2" * 64},
    )
    context = ReplanContext(
        input_view=input_view,
        execution_fact_fingerprint="sha256:" + "3" * 64,
        hard_lock_fingerprint="sha256:" + "4" * 64,
        freeze_window_fingerprint="sha256:" + "5" * 64,
        state_machine_version="state-machines.v1",
        publication_authority_reference="com.example.publication.authority.v1",
    )
    valid = ReplanDecision(
        contribution_id=descriptor.contribution_id,
        action=ReplanAction.REQUEST_REPLAN,
        reason_code="com.example.machine_down",
        trigger_references=("event-001",),
        execution_fact_fingerprint=context.execution_fact_fingerprint,
        hard_lock_fingerprint=context.hard_lock_fingerprint,
        freeze_window_fingerprint=context.freeze_window_fingerprint,
        state_machine_version=context.state_machine_version,
        publication_authority_reference=context.publication_authority_reference,
    )
    validate_protocol_output(descriptor, context, valid)
    forged = ReplanDecision(
        contribution_id=descriptor.contribution_id,
        action=ReplanAction.REQUEST_REPLAN,
        reason_code="com.example.machine_down",
        trigger_references=("event-001",),
        execution_fact_fingerprint=context.execution_fact_fingerprint,
        hard_lock_fingerprint="sha256:" + "9" * 64,
        freeze_window_fingerprint=context.freeze_window_fingerprint,
        state_machine_version=context.state_machine_version,
        publication_authority_reference=context.publication_authority_reference,
    )
    with pytest.raises(ExtensionContractError) as captured:
        validate_protocol_output(descriptor, context, forged)
    assert captured.value.code is ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS
