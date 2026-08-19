"""Integer-only duration conversion using an injected versioned registry."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import NoReturn

from .contracts import NormalizationError, NormalizationErrorCode

MAX_DURATION_SECONDS = 9_223_372_036_854_775_807
_TOP_LEVEL_FIELDS = frozenset(
    {
        "unit_conversion_registry_version",
        "schema_set_version",
        "status",
        "compatibility",
        "integer_arithmetic_only",
        "implicit_defaults",
        "rules",
    }
)
_RULE_FIELDS = frozenset(
    {
        "rule_id",
        "dimension",
        "source_unit",
        "target_unit",
        "factor_numerator",
        "factor_denominator",
    }
)


@dataclass(frozen=True)
class UnitConversionRule:
    rule_id: str
    source_unit: str
    factor_numerator: int
    factor_denominator: int


@dataclass(frozen=True)
class UnitConversionRegistry:
    """Validated duration rules with exact source-unit lookup."""

    version: str
    schema_set_version: str
    rules: tuple[UnitConversionRule, ...]

    @classmethod
    def from_mapping(cls, document: Mapping[str, object]) -> UnitConversionRegistry:
        _validate_exact_fields(document, _TOP_LEVEL_FIELDS, "registry")
        version = _text(
            document.get("unit_conversion_registry_version"),
            "unit_conversion_registry_version",
        )
        schema_set_version = _text(
            document.get("schema_set_version"), "schema_set_version"
        )
        if version != "unit-conversion-registry.v1":
            _invalid(
                "unit_conversion_registry_version",
                "parser accepts only unit-conversion-registry.v1",
            )
        if schema_set_version != "2.1.0":
            _invalid("schema_set_version", "registry must belong to schema set 2.1.0")
        if document.get("status") != "active":
            _invalid("status", "registry status must be active")
        if document.get("compatibility") != "additive":
            _invalid("compatibility", "registry compatibility must be additive")
        if document.get("integer_arithmetic_only") is not True:
            _invalid(
                "integer_arithmetic_only", "registry must require integer arithmetic"
            )
        if document.get("implicit_defaults") != "forbidden":
            _invalid("implicit_defaults", "implicit defaults must be forbidden")
        raw_rules = document.get("rules")
        if (
            not isinstance(raw_rules, Sequence)
            or isinstance(raw_rules, (str, bytes))
            or not raw_rules
        ):
            _invalid("rules", "registry rules must be a non-empty sequence")
        rules: list[UnitConversionRule] = []
        rule_ids: set[str] = set()
        source_units: set[str] = set()
        for position, raw_rule in enumerate(raw_rules):
            if not isinstance(raw_rule, Mapping):
                _invalid(f"rules[{position}]", "each rule must be an object")
            _validate_exact_fields(raw_rule, _RULE_FIELDS, f"rules[{position}]")
            rule_id = _text(raw_rule.get("rule_id"), f"rules[{position}].rule_id")
            source_unit = _text(
                raw_rule.get("source_unit"), f"rules[{position}].source_unit"
            )
            if raw_rule.get("dimension") != "duration":
                _invalid(f"rules[{position}].dimension", "only duration is supported")
            if raw_rule.get("target_unit") != "second":
                _invalid(
                    f"rules[{position}].target_unit",
                    "duration rules must target second",
                )
            numerator = _positive_integer(
                raw_rule.get("factor_numerator"),
                f"rules[{position}].factor_numerator",
            )
            denominator = _positive_integer(
                raw_rule.get("factor_denominator"),
                f"rules[{position}].factor_denominator",
            )
            if rule_id in rule_ids or source_unit in source_units:
                _invalid(
                    f"rules[{position}]",
                    "rule IDs and exact source units must be unique",
                )
            rule_ids.add(rule_id)
            source_units.add(source_unit)
            rules.append(
                UnitConversionRule(rule_id, source_unit, numerator, denominator)
            )
        return cls(version, schema_set_version, tuple(rules))

    def convert_duration(
        self,
        value: object,
        unit: object,
        *,
        source_location: str,
        field: str,
        allow_zero: bool,
    ) -> int:
        """Convert one explicit integer duration without floating-point rounding."""

        if value is None:
            raise NormalizationError(
                NormalizationErrorCode.MISSING_DURATION,
                source_location=source_location,
                field=field,
                expected_contract="explicit integer duration and explicit source unit",
                message="required duration is missing",
            )
        if isinstance(value, bool) or not isinstance(value, int):
            _conversion_error(
                source_location, field, "duration must be an integer before conversion"
            )
        if value < 0 or (value == 0 and not allow_zero):
            _conversion_error(
                source_location,
                field,
                "duration must satisfy the canonical non-negative/positive rule",
            )
        if not isinstance(unit, str) or not unit:
            _conversion_error(source_location, field, "duration unit is missing")
        rule = next((item for item in self.rules if item.source_unit == unit), None)
        if rule is None:
            _conversion_error(source_location, field, "duration unit is not registered")
        product = value * rule.factor_numerator
        converted, remainder = divmod(product, rule.factor_denominator)
        if remainder:
            _conversion_error(
                source_location,
                field,
                "duration does not convert to an integral number of seconds",
            )
        if converted > MAX_DURATION_SECONDS:
            _conversion_error(source_location, field, "duration seconds overflow int64")
        return converted


def _invalid(field: str, message: str) -> NoReturn:
    raise NormalizationError(
        NormalizationErrorCode.INVALID_MAPPING_PROFILE,
        source_location="unit-conversion-registry",
        field=field,
        expected_contract="unit-conversion-registry.v1 exact contract",
        message=message,
    )


def _conversion_error(source_location: str, field: str, message: str) -> NoReturn:
    raise NormalizationError(
        NormalizationErrorCode.UNIT_CONVERSION_ERROR,
        source_location=source_location,
        field=field,
        expected_contract="registered exact integer duration-to-second conversion",
        message=message,
    )


def _validate_exact_fields(
    document: Mapping[str, object], expected: frozenset[str], field: str
) -> None:
    if set(document) != expected:
        _invalid(field, "fields must match the exact versioned contract")


def _text(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or not value.strip()
        or len(value) > 256
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _invalid(field, "value must be non-empty text")
    return value


def _positive_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _invalid(field, "factor must be a positive integer")
    return value


__all__ = [
    "MAX_DURATION_SECONDS",
    "UnitConversionRegistry",
    "UnitConversionRule",
]
