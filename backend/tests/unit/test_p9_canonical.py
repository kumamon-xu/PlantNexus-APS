"""TEST-P9-CANONICAL-001: frozen v1 bytes, ingress failures and legacy replay."""

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from app.data_validation.canonical_ingress import (
    CanonicalIngressContractCode,
    CanonicalIngressContractError,
    canonical_json_bytes,
    parse_strict_json,
)
from app.domain.workspace_contracts import canonical_workspace_bytes
from app.snapshots.canonical import canonical_json_bytes as snapshot_bytes

ROOT = Path(__file__).resolve().parents[3]
VECTORS = json.loads((ROOT / "frontend/tests/p9CanonicalVectors.json").read_text())


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda item: item["id"])
def test_frozen_cross_language_bytes_and_legacy_serializers(vector: dict[str, Any]) -> None:
    if "source_path" in vector:
        assert sha256((ROOT / vector["source_path"]).read_bytes()).hexdigest() == vector["source_sha256"]
    value = parse_strict_json(vector["raw"].encode())
    expected = vector["canonical"].encode()
    for serialize in (canonical_json_bytes, canonical_workspace_bytes, snapshot_bytes):
        actual = serialize(value)
        assert actual == expected
        assert f"sha256:{sha256(actual).hexdigest()}" == vector["fingerprint"]
        assert serialize(parse_strict_json(actual)) == actual


@pytest.mark.parametrize("raw", VECTORS["rejections"])
def test_strict_ingress_rejects_invalid_json_or_utf8_serialization(raw: str) -> None:
    with pytest.raises(CanonicalIngressContractError):
        canonical_json_bytes(parse_strict_json(raw.encode()))


@pytest.mark.parametrize("raw", VECTORS["unsupported_in_browser"])
def test_legacy_large_integers_are_not_rounded_or_restricted_in_python(raw: str) -> None:
    assert canonical_json_bytes(parse_strict_json(raw.encode())) == raw.encode()


def test_overlong_integer_and_invalid_utf8_are_sanitized_contract_failures() -> None:
    for raw in (b'{"n":' + b"9" * 5000 + b"}", b'{"s":"\xff"}'):
        with pytest.raises(CanonicalIngressContractError) as error:
            parse_strict_json(raw)
        assert error.value.code is CanonicalIngressContractCode.MALFORMED_JSON
        assert "99999" not in str(error.value)
