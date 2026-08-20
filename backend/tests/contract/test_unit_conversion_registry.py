"""TEST-CONTRACT-001 evidence for the additive P1 unit-rule release."""

from __future__ import annotations

import copy
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from app import SCHEMA_VERSION
from app.normalization import (
    COLLECTION_ID_FIELDS,
    MAX_DURATION_SECONDS,
    NormalizationError,
    NormalizationErrorCode,
    UnitConversionRegistry,
)
from app.normalization.contracts import (
    COLLECTION_OPTIONAL_FIELDS,
    COLLECTION_REQUIRED_FIELDS,
)

ROOT = Path(__file__).resolve().parents[3]
RULE_PATH = ROOT / "schemas" / "rules" / "unit-conversion-registry.v1.yaml"
DICTIONARY_PATH = ROOT / "schemas" / "data_dictionary.yaml"
SCHEMA_ROOT = ROOT / "schemas" / "json"
PRESERVED_SCHEMA_SHA256 = {
    "canonical-records.v1.schema.json": (
        "fd13b188b7317eb92f14489fdc6c7976cc24b5b03cfcb2fa9d9f1eabdd4b3f9e"
    ),
    "import-package.v2.schema.json": (
        "166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56"
    ),
}


def load_registry_document() -> dict[str, object]:
    return cast(
        dict[str, object], yaml.safe_load(RULE_PATH.read_text(encoding="utf-8"))
    )


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_additive_schema_set_metadata_and_immutable_v2_contracts() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dictionary = cast(
        dict[str, Any], yaml.safe_load(DICTIONARY_PATH.read_text(encoding="utf-8"))
    )
    import_schema = load_json(SCHEMA_ROOT / "import-package.v2.schema.json")

    assert SCHEMA_VERSION == "2.3.0"
    assert pyproject["tool"]["plantnexus-aps"]["versions"]["schema"] == "2.3.0"
    assert dictionary["schema_set_version"] == "2.3.0"
    assert "unit-conversion-registry.v1" in dictionary["schemas"]
    assert import_schema["properties"]["schema_set_version"]["const"] == "2.0.0"
    for filename, expected in PRESERVED_SCHEMA_SHA256.items():
        assert (
            hashlib.sha256((SCHEMA_ROOT / filename).read_bytes()).hexdigest()
            == expected
        )


def test_registry_has_exact_versioned_integer_duration_rules() -> None:
    document = load_registry_document()
    registry = UnitConversionRegistry.from_mapping(document)

    assert registry.version == "unit-conversion-registry.v1"
    assert registry.schema_set_version == "2.1.0"
    assert document["implicit_defaults"] == "forbidden"
    assert document["integer_arithmetic_only"] is True
    assert [
        (rule.source_unit, rule.factor_numerator, rule.factor_denominator)
        for rule in registry.rules
    ] == [
        ("s", 1, 1),
        ("min", 60, 1),
        ("h", 3600, 1),
    ]
    assert (
        registry.convert_duration(
            9, "s", source_location="test", field="duration", allow_zero=False
        )
        == 9
    )
    assert (
        registry.convert_duration(
            2, "min", source_location="test", field="duration", allow_zero=False
        )
        == 120
    )
    assert (
        registry.convert_duration(
            3, "h", source_location="test", field="duration", allow_zero=False
        )
        == 10_800
    )


@pytest.mark.parametrize(
    ("value", "unit", "expected_code"),
    [
        (None, "s", NormalizationErrorCode.MISSING_DURATION),
        (1, None, NormalizationErrorCode.UNIT_CONVERSION_ERROR),
        (1, "day", NormalizationErrorCode.UNIT_CONVERSION_ERROR),
        (1.5, "s", NormalizationErrorCode.UNIT_CONVERSION_ERROR),
        (True, "s", NormalizationErrorCode.UNIT_CONVERSION_ERROR),
        (-1, "s", NormalizationErrorCode.UNIT_CONVERSION_ERROR),
        (0, "s", NormalizationErrorCode.UNIT_CONVERSION_ERROR),
        (MAX_DURATION_SECONDS + 1, "s", NormalizationErrorCode.UNIT_CONVERSION_ERROR),
    ],
)
def test_duration_conversion_rejects_missing_unknown_float_and_overflow(
    value: object, unit: object, expected_code: NormalizationErrorCode
) -> None:
    registry = UnitConversionRegistry.from_mapping(load_registry_document())
    with pytest.raises(NormalizationError) as rejected:
        registry.convert_duration(
            value,
            unit,
            source_location="reference.csv:2",
            field="duration",
            allow_zero=False,
        )
    assert rejected.value.category == "DATA_ERROR"
    assert rejected.value.code is expected_code
    assert rejected.value.source_location == "reference.csv:2"


def test_fractional_second_rule_is_rejected_without_rounding() -> None:
    document = load_registry_document()
    rules = cast(list[dict[str, object]], document["rules"])
    rules[0] = {
        **rules[0],
        "source_unit": "half-second",
        "factor_numerator": 1,
        "factor_denominator": 2,
    }
    registry = UnitConversionRegistry.from_mapping(document)
    with pytest.raises(NormalizationError) as rejected:
        registry.convert_duration(
            1,
            "half-second",
            source_location="reference.csv:3",
            field="duration",
            allow_zero=True,
        )
    assert rejected.value.code is NormalizationErrorCode.UNIT_CONVERSION_ERROR
    assert "integral" in rejected.value.message


@pytest.mark.parametrize(
    "mutation",
    [
        "top_level_default",
        "rule_alias",
        "duplicate_source_unit",
        "zero_factor",
        "wrong_target",
        "allow_defaults",
        "wrong_registry_version",
        "wrong_schema_set",
    ],
)
def test_registry_rejects_unknown_fields_duplicates_and_defaults(mutation: str) -> None:
    document = copy.deepcopy(load_registry_document())
    rules = cast(list[dict[str, object]], document["rules"])
    if mutation == "top_level_default":
        document["default_unit"] = "s"
    elif mutation == "rule_alias":
        rules[0]["aliases"] = ["sec"]
    elif mutation == "duplicate_source_unit":
        rules[1]["source_unit"] = "s"
    elif mutation == "zero_factor":
        rules[0]["factor_numerator"] = 0
    elif mutation == "wrong_target":
        rules[0]["target_unit"] = "minute"
    elif mutation == "wrong_registry_version":
        document["unit_conversion_registry_version"] = "unit-conversion-registry.v2"
    elif mutation == "wrong_schema_set":
        document["schema_set_version"] = "2.0.0"
    else:
        document["implicit_defaults"] = "allowed"

    with pytest.raises(NormalizationError) as rejected:
        UnitConversionRegistry.from_mapping(document)
    assert rejected.value.code is NormalizationErrorCode.INVALID_MAPPING_PROFILE
    assert rejected.value.source_location == "unit-conversion-registry"


def test_mapping_field_contract_stays_exactly_aligned_with_canonical_schema() -> None:
    schema = load_json(SCHEMA_ROOT / "canonical-records.v1.schema.json")
    assert set(COLLECTION_ID_FIELDS) == set(schema["properties"]) - {
        "canonical_records_version"
    }
    for collection in COLLECTION_ID_FIELDS:
        collection_reference = schema["properties"][collection]["$ref"]
        collection_definition = schema["$defs"][
            collection_reference.rsplit("/", maxsplit=1)[-1]
        ]
        record_reference = collection_definition["items"]["$ref"]
        definition = schema["$defs"][record_reference.rsplit("/", maxsplit=1)[-1]]
        required = set(definition["required"]) - {"source"}
        allowed = set(definition["properties"]) - {"source"}
        assert COLLECTION_REQUIRED_FIELDS[collection] == required
        assert (
            COLLECTION_REQUIRED_FIELDS[collection]
            | COLLECTION_OPTIONAL_FIELDS[collection]
        ) == allowed
