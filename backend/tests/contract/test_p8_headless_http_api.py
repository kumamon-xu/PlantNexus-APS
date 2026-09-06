"""Public contract and compatibility checks for TEST-P8-HEADLESS-API-001."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
import pytest
import yaml

from app.api.app import create_app
from app.api.headless_api_check import run_checks
from app.api.headless_contracts import (
    PlanningRunCancelAction,
    PlanningRunRetryAction,
    headless_error_document,
)
from app.api.headless_openapi import HEADLESS_OPERATION_INVENTORY


ROOT = Path(__file__).resolve().parents[3]
BASELINE = (
    ROOT
    / "backend"
    / "app"
    / "api"
    / "openapi"
    / "pre-p8-07-operation-baseline.v1.json"
)


def _operation_hash(operation: dict[str, Any]) -> str:
    raw = json.dumps(
        operation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(raw).hexdigest()}"


def _openapi() -> dict[str, Any]:
    return cast(dict[str, Any], create_app(probes={}).openapi())


def test_openapi_is_exactly_additive_and_preserves_all_29_operations() -> None:
    schema = _openapi()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    paths = cast(dict[str, Any], schema["paths"])
    operations = {
        (method.upper(), path): operation
        for path, item in paths.items()
        for method, operation in item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert len(operations) == 34
    assert baseline["operation_count"] == 29
    for expected in baseline["operations"]:
        operation = operations[(expected["method"], expected["path"])]
        assert operation["operationId"] == expected["operation_id"]
        assert _operation_hash(operation) == expected["operation_sha256"]
    for method, path, operation_id, success_status in HEADLESS_OPERATION_INVENTORY:
        operation = operations[(method, path)]
        assert operation["operationId"] == operation_id
        assert str(success_status) in operation["responses"]
        assert operation.get("deprecated") is not True
    operation_ids = [value["operationId"] for value in operations.values()]
    assert len(operation_ids) == len(set(operation_ids))
    create_responses = operations[("POST", "/api/v1/planning-runs")]["responses"]
    for status in ("403", "409", "422", "500", "503"):
        assert "CanonicalIngressResult" in json.dumps(create_responses[status])


def test_machine_report_diff_and_engineering_benchmark_are_complete() -> None:
    report, diff_report, benchmark = run_checks(ROOT)
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P8-07"
    assert report["check_count"] == 11
    assert report["issues"] == []
    assert diff_report["status"] == "PASS"
    assert diff_report["baseline_operation_count"] == 29
    assert diff_report["final_operation_count"] == 34
    assert diff_report["breaking_changes"] == []
    assert benchmark["status"] == "PASS"
    assert benchmark["profile"] == "SYNTHETIC_ENGINEERING_NOT_PRODUCTION_SLA"
    assert benchmark["http_transport_probe"]["all_statuses_expected"] is True


def test_openapi_bundles_machine_carriers_and_transport_envelope() -> None:
    schema = _openapi()
    components = schema["components"]["schemas"]
    assert {
        "CanonicalIngressRequest",
        "CanonicalIngressResult",
        "PlanningRun",
        "HeadlessError",
        "PlanningRunCancelAction",
        "PlanningRunRetryAction",
    }.issubset(components)
    assert components["CanonicalIngressRequest"]["additionalProperties"] is False
    assert components["CanonicalIngressResult"]["additionalProperties"] is False
    assert components["PlanningRun"]["additionalProperties"] is False
    metadata = schema["x-aps-headless-contract"]
    assert metadata == {
        "http_contract_version": "headless-http.v1",
        "compatibility_policy": "V1_ADDITIVE_ONLY",
        "preexisting_operation_count": 29,
        "headless_operation_count": 5,
        "total_operation_count": 34,
        "transport_envelope": {
            "canonical_request_max_bytes": 8_388_608,
            "action_request_max_bytes": 16_384,
            "json_max_depth": 64,
            "canonical_record_max_count": 100_000,
            "content_encoding": "FORBIDDEN",
            "media_type": "application/json",
        },
        "production_authority": "UNAVAILABLE_UNTIL_P8_08",
    }
    headless_paths = [item[1] for item in HEADLESS_OPERATION_INVENTORY]
    rendered = json.dumps({path: schema["paths"][path] for path in headless_paths})
    for forbidden in ("multipart/form-data", "application/zip", "plugin upload"):
        assert forbidden not in rendered
    assert not any(
        "extension" in path.lower() or "plugin" in path.lower()
        for path in schema["paths"]
    )


def test_public_headless_error_tuples_match_the_frozen_registry() -> None:
    registry = yaml.safe_load(
        (ROOT / "schemas" / "rules" / "headless-error-code-registry.v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    for row in registry["codes"]:
        document = headless_error_document(
            row["code"], correlation_id="CORRELATION-P8-HEADLESS-CONTRACT"
        )
        assert (
            document["category"],
            document["code"],
            document["stage"],
            document["retryability"],
            document["action"],
        ) == (
            row["category"],
            row["code"],
            row["stage"],
            row["retryability"],
            row["action"],
        )
        assert document["namespace"] == "HEADLESS_RUNTIME"
        assert document["registry_version"] == registry["error_registry_version"]
    sanitized = headless_error_document(
        "INVALID_REFERENCE",
        correlation_id="不可放入响应头",
        pointer="not-a-json-pointer",
        entity_reference="invalid entity reference",
    )
    assert cast(str, sanitized["correlation_id"]).isascii()
    assert cast(str, sanitized["correlation_id"]).startswith("correlation-headless-")
    assert sanitized["pointer"] is None
    assert sanitized["entity_reference"] is None


@pytest.mark.parametrize(
    ("model", "document"),
    [
        (
            PlanningRunCancelAction,
            {
                "action_version": "planning-run-cancel-action.v1",
                "expected_revision": 1,
                "expected_state": "CREATED",
                "expected_run_fingerprint": f"sha256:{'1' * 64}",
                "reason": "cancel",
                "extension_id": "request-owned-extension-is-forbidden",
            },
        ),
        (
            PlanningRunRetryAction,
            {
                "action_version": "planning-run-retry-action.v1",
                "expected_revision": True,
                "expected_state": "CREATED",
                "expected_run_fingerprint": f"sha256:{'1' * 64}",
                "failed_attempt_id": "attempt-1",
                "failed_attempt_number": 1,
                "reason": "retry",
            },
        ),
    ],
)
def test_action_carriers_are_strict_and_cannot_select_extensions(
    model: type[PlanningRunCancelAction] | type[PlanningRunRetryAction],
    document: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(document)
