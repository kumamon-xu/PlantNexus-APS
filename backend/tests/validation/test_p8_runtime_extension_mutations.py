"""Independent Validator and forged-output mutation evidence for P8-13."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

from aps_extension_sdk import (
    ConstraintContext,
    ConstraintOutput,
    FrozenJsonObject,
    ValidationContext,
    ValidationOutput,
    freeze_json,
)

from backend.tests.fixtures.p8_synthetic_extension import (
    SyntheticConstraint,
    SyntheticValidationRule,
)
from backend.tests.p8_runtime_extension_support import runtime_extension_fixture


CONSTRAINT_ID = "com.example.capacity.constraint"


def _frozen(value: object) -> FrozenJsonObject:
    return cast(FrozenJsonObject, freeze_json(value))


class MutatedConstraint(SyntheticConstraint):
    calls = 0

    def contribute(self, context: ConstraintContext) -> ConstraintOutput:
        type(self).calls += 1
        original = super().contribute(context)
        return replace(
            original,
            constraint_specification=_frozen({"mutated_solver_side": True}),
        )


class IndependentValidationRule(SyntheticValidationRule):
    calls = 0

    def validate(self, context: ValidationContext) -> ValidationOutput:
        type(self).calls += 1
        return super().validate(context)


def _common() -> dict[str, dict[str, object]]:
    return {
        "scope": {"tenant_id": "TENANT-MUTATION"},
        "facts": {"candidate": "SYNTHETIC"},
        "provenance": {"planning_run_id": "planning-run-mutation"},
    }


def test_validation_domain_does_not_call_or_reuse_constraint_implementation(
    tmp_path: Path,
) -> None:
    MutatedConstraint.calls = 0
    IndependentValidationRule.calls = 0
    fixture = runtime_extension_fixture(
        tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'validation.db').as_posix()}",
        overrides={
            CONSTRAINT_ID: MutatedConstraint,
            "com.example.capacity.validator": IndependentValidationRule,
            "com.example.sequence.validator": IndependentValidationRule,
        },
    )
    adapter = fixture.load()
    validation = adapter.invoke_validation_rules(**_common())
    assert len(validation) == 2
    assert all(item.passed for item in validation)
    assert MutatedConstraint.calls == 0
    assert IndependentValidationRule.calls == 2

    constraint = adapter.invoke_constraints(**_common())
    assert constraint[0].constraint_specification == _frozen(
        {"mutated_solver_side": True}
    )
    assert MutatedConstraint.calls == 1
    second_validation = adapter.invoke_validation_rules(**_common())
    assert second_validation == validation
    assert IndependentValidationRule.calls == 4
