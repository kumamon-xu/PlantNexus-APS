"""TEST-P8-EXTENSION-CONTRACT-001: public SDK carriers and machine report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from aps_extension_sdk import (
    EXTENSION_COMPATIBILITY_VERSION,
    EXTENSION_MANIFEST_VERSION,
    REGISTRY_PROTOCOL_VERSION,
    SDK_API_VERSION,
    ExtensionPoint,
    parse_compatibility_policy,
    parse_extension_manifest,
    resolve_manifest_set,
)
from scripts.p8_extension_sdk_contract_check import (
    DIFF_BASE,
    REPORT_VERSION,
    TASK_ID,
    TEST_ID,
    run_contract_checks,
)


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = ROOT / "backend/aps_extension_sdk/contracts"
SAMPLES = CONTRACT_ROOT / "samples"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_manifest_and_compatibility_carriers_are_strict_offline_v1() -> None:
    manifest_schema = _json(CONTRACT_ROOT / "extension-manifest.v1.schema.json")
    compatibility_schema = _json(
        CONTRACT_ROOT / "extension-compatibility.v1.schema.json"
    )
    manifest_document = _json(SAMPLES / "extension-manifest.v1.synthetic.json")
    compatibility_document = _json(
        SAMPLES / "extension-compatibility.v1.synthetic.json"
    )

    Draft202012Validator.check_schema(manifest_schema)
    Draft202012Validator.check_schema(compatibility_schema)
    Draft202012Validator(manifest_schema).validate(manifest_document)
    Draft202012Validator(compatibility_schema).validate(compatibility_document)

    assert manifest_schema["$id"] == (
        "urn:plantnexus:aps:extension-sdk:extension-manifest:v1"
    )
    assert compatibility_schema["$id"] == (
        "urn:plantnexus:aps:extension-sdk:extension-compatibility:v1"
    )
    assert manifest_schema["additionalProperties"] is False
    assert compatibility_schema["additionalProperties"] is False
    assert "default" not in json.dumps(manifest_schema)
    assert "default" not in json.dumps(compatibility_schema)


def test_positive_manifest_covers_all_six_spi_and_resolves_deterministically() -> None:
    manifest = parse_extension_manifest(
        _json(SAMPLES / "extension-manifest.v1.synthetic.json")
    )
    policy = parse_compatibility_policy(
        _json(SAMPLES / "extension-compatibility.v1.synthetic.json")
    )
    first = resolve_manifest_set((manifest,), policy)
    second = resolve_manifest_set((manifest,), policy)

    assert str(manifest.sdk_api_version) == SDK_API_VERSION
    assert manifest.manifest_version == EXTENSION_MANIFEST_VERSION
    assert manifest.registry_protocol_version == REGISTRY_PROTOCOL_VERSION
    assert policy.compatibility_version == EXTENSION_COMPATIBILITY_VERSION
    assert {item.extension_point for item in manifest.contributions} == set(
        ExtensionPoint
    )
    assert first == second
    assert first.resolution_fingerprint.startswith("sha256:")
    assert [item.contribution_id for item in first.contributions] == [
        item.contribution_id
        for item in sorted(
            first.contributions,
            key=lambda contribution: (
                contribution.order,
                contribution.contribution_id,
            ),
        )
    ]


def test_compatibility_policy_prevents_implicit_upgrade_claims() -> None:
    document = _json(SAMPLES / "extension-compatibility.v1.synthetic.json")
    policy = parse_compatibility_policy(document)
    assert str(policy.sdk_api_version) == "1.0.0"
    assert document["release_policy"] == {
        "patch": "NO_BUSINESS_SEMANTIC_CHANGE",
        "minor": "ADDITIVE_OPTIONAL",
        "major": "BREAKING_REQUIRES_NEW_DEVELOPER_KIT",
        "exact_lock_required": True,
        "automatic_upgrade": False,
    }
    assert document["runtime_loader_status"] == "NOT_IMPLEMENTED_UNTIL_P8_13"
    assert document["developer_kit_status"] == "NOT_IMPLEMENTED_UNTIL_P8_15"


def test_machine_report_binds_base_scope_history_and_closed_boundaries() -> None:
    report = run_contract_checks(ROOT)
    assert report["result"] == "PASS"
    assert report["report_version"] == REPORT_VERSION
    assert report["task_id"] == TASK_ID == "TASK-P8-12"
    assert report["test_id"] == TEST_ID == "TEST-P8-EXTENSION-CONTRACT-001"
    assert report["diff_base"] == DIFF_BASE
    assert report["validation_profile"] == "HIGH_RISK"
    assert report["check_count"] == 7
    assert report["issues"] == []
    assert report["boundaries"] == {
        "runtime_loader": "NOT_IMPLEMENTED_UNTIL_P8_13",
        "enterprise_extension_template": "NOT_IMPLEMENTED_UNTIL_P8_14",
        "developer_kit": "NOT_IMPLEMENTED_UNTIL_P8_15",
        "core_semantics": "PRESERVED",
        "external_http_api": "UNCHANGED",
        "migration": "NONE",
        "production_authority": "NOT_CLAIMED",
        "demo": "EXCLUDED",
    }
