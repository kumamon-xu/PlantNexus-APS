"""TASK-P4-12 OpenAPI and frozen P3 compatibility evidence."""

from __future__ import annotations

from typing import cast

from app.api.app import create_app
from app.api.replanning_check import P4_OPERATION_IDS, P4_PATHS
from app.api.replanning_contracts import DYNAMIC_REPLANNING_API_VERSION
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings


def _openapi() -> dict[str, object]:
    return create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        probes={},
    ).openapi()


def test_openapi_has_exact_p4_path_and_operation_inventory() -> None:
    document = _openapi()
    paths = cast(dict[str, dict[str, object]], document["paths"])
    p4_paths = {path: paths[path] for path in P4_PATHS}
    operations = {
        cast(str, operation["operationId"])
        for value in p4_paths.values()
        for method, operation in value.items()
        if method in {"get", "post"} and isinstance(operation, dict)
    }

    assert len(p4_paths) == 8
    assert operations == P4_OPERATION_IDS
    assert not any("simulator" in path or "/p5" in path for path in p4_paths)


def test_openapi_freezes_contract_authority_and_error_responses() -> None:
    document = _openapi()
    paths = cast(dict[str, dict[str, object]], document["paths"])
    for path in P4_PATHS:
        for method, raw_operation in paths[path].items():
            if method not in {"get", "post"}:
                continue
            operation = cast(dict[str, object], raw_operation)
            assert operation["x-plantnexus-api-contract"] == (
                DYNAMIC_REPLANNING_API_VERSION
            )
            assert operation["x-plantnexus-response-contract"] == (
                "dynamic-replanning-response.v1"
            )
            assert operation["x-plantnexus-production-authority"] == (
                "DEFAULT_DENY_OPEN_010_015"
            )
            assert operation["x-plantnexus-p5-capabilities"] == "NOT_ADVERTISED"
            responses = cast(dict[str, dict[str, object]], operation["responses"])
            for status in ("401", "403", "404", "409", "422", "500", "503"):
                content = cast(dict[str, object], responses[status]["content"])
                schema = cast(dict[str, object], content["application/json"])["schema"]
                assert schema == {
                    "$ref": "#/components/schemas/PlanningWorkspaceErrorEnvelope"
                }


def test_openapi_action_schema_is_strict_and_replan_request_has_no_state() -> None:
    document = _openapi()
    components = cast(dict[str, object], document["components"])
    schemas = cast(dict[str, dict[str, object]], components["schemas"])
    action = schemas["ReplanAttemptActionDocument"]

    assert action["additionalProperties"] is False
    properties = cast(dict[str, object], action["properties"])
    assert set(properties) == {
        "replan_action_version",
        "api_contract_version",
        "canonicalization_version",
        "action_id",
        "action",
        "request_id",
        "request_fingerprint",
        "expected_attempt_id",
        "expected_attempt_number",
        "expected_planning_run_state",
        "reason",
        "data_plane",
        "environment",
        "production_binding",
        "correlation_id",
        "idempotency_key_reference",
        "action_fingerprint",
    }
    assert "state" not in properties


def test_p3_frozen_operation_subset_remains_present() -> None:
    paths = cast(dict[str, dict[str, object]], _openapi()["paths"])
    operation_ids = {
        cast(str, operation["operationId"])
        for route, path in paths.items()
        for method, operation in path.items()
        if route.startswith("/api/v1/")
        and method in {"get", "post"}
        and isinstance(operation, dict)
    }
    p8_headless_operation_ids = {
        "createHeadlessPlanningRun",
        "getHeadlessPlanningRunStatus",
        "cancelHeadlessPlanningRun",
        "retryHeadlessPlanningRun",
        "getHeadlessPlanningRunResult",
    }
    present_headless = operation_ids & p8_headless_operation_ids
    assert present_headless in (set(), p8_headless_operation_ids)
    assert len(operation_ids - P4_OPERATION_IDS - p8_headless_operation_ids) == 18
    assert P4_OPERATION_IDS.issubset(operation_ids)
