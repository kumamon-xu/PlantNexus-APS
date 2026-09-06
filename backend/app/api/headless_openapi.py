"""OpenAPI schema bundling for the additive P8 Headless HTTP surface."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, cast

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.headless_contracts import (
    HEADLESS_HTTP_VERSION,
    MAX_ACTION_REQUEST_BYTES,
    MAX_CANONICAL_RECORDS,
    MAX_CANONICAL_REQUEST_BYTES,
    MAX_JSON_DEPTH,
    PlanningRunCancelAction,
    PlanningRunRetryAction,
)


type JsonObject = dict[str, Any]

_REQUEST_SCHEMA_ID = "urn:plantnexus:aps:schema:canonical-ingress-request:v1"
_RESULT_SCHEMA_ID = "urn:plantnexus:aps:schema:canonical-ingress-result:v1"
_RUN_SCHEMA_ID = "urn:plantnexus:aps:schema:planning-run:v1"
_ROOT_COMPONENTS = {
    _REQUEST_SCHEMA_ID: "CanonicalIngressRequest",
    _RESULT_SCHEMA_ID: "CanonicalIngressResult",
    _RUN_SCHEMA_ID: "PlanningRun",
}
_COMPONENT_PART = re.compile(r"[^A-Za-z0-9]+")

HEADLESS_OPERATION_INVENTORY = (
    ("POST", "/api/v1/planning-runs", "createHeadlessPlanningRun", 202),
    (
        "GET",
        "/api/v1/planning-runs/{planning_run_id}/status",
        "getHeadlessPlanningRunStatus",
        200,
    ),
    (
        "POST",
        "/api/v1/planning-runs/{planning_run_id}/cancel",
        "cancelHeadlessPlanningRun",
        200,
    ),
    (
        "POST",
        "/api/v1/planning-runs/{planning_run_id}/retry",
        "retryHeadlessPlanningRun",
        202,
    ),
    (
        "GET",
        "/api/v1/planning-runs/{planning_run_id}/result",
        "getHeadlessPlanningRunResult",
        200,
    ),
)


def _component_name(schema_id: str) -> str:
    explicit = _ROOT_COMPONENTS.get(schema_id)
    if explicit is not None:
        return explicit
    parts = [
        part
        for part in _COMPONENT_PART.split(
            schema_id.removeprefix("urn:plantnexus:aps:schema:")
        )
        if part
    ]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _schema_documents(schema_directory: Path) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for path in sorted(schema_directory.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and isinstance(value.get("$id"), str):
            result[cast(str, value["$id"])] = cast(JsonObject, value)
    missing = sorted(set(_ROOT_COMPONENTS) - set(result))
    if missing:
        raise RuntimeError("Headless OpenAPI schema catalog is incomplete")
    return result


def _references(value: object) -> set[str]:
    found: set[str] = set()
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            reference = current.get("$ref")
            if isinstance(reference, str) and not reference.startswith("#"):
                found.add(reference.partition("#")[0])
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return found


def _dependency_closure(documents: Mapping[str, JsonObject]) -> set[str]:
    selected = set(_ROOT_COMPONENTS)
    pending = list(selected)
    while pending:
        schema_id = pending.pop()
        for reference in _references(documents[schema_id]):
            if reference in documents and reference not in selected:
                selected.add(reference)
                pending.append(reference)
    return selected


def _rewrite_references(
    value: object, names: Mapping[str, str], *, current_component: str
) -> object:
    if isinstance(value, dict):
        result: JsonObject = {}
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                if item.startswith("#/"):
                    result[key] = f"#/components/schemas/{current_component}{item[1:]}"
                    continue
                schema_id, marker, fragment = item.partition("#")
                component = names.get(schema_id)
                if component is not None:
                    result[key] = f"#/components/schemas/{component}"
                    if marker and fragment:
                        result[key] += fragment
                    continue
            result[key] = _rewrite_references(
                item, names, current_component=current_component
            )
        return result
    if isinstance(value, list):
        return [
            _rewrite_references(item, names, current_component=current_component)
            for item in value
        ]
    return value


def _bundled_components(schema_directory: Path) -> dict[str, object]:
    documents = _schema_documents(schema_directory)
    selected = _dependency_closure(documents)
    names = {schema_id: _component_name(schema_id) for schema_id in selected}
    if len(set(names.values())) != len(names):
        raise RuntimeError("Headless OpenAPI component names are not unique")
    result: dict[str, object] = {}
    for schema_id in sorted(selected):
        name = names[schema_id]
        result[name] = _rewrite_references(
            deepcopy(documents[schema_id]),
            names,
            current_component=name,
        )
    result["HeadlessError"] = {
        "$ref": "#/components/schemas/CanonicalIngressResult/$defs/headlessError"
    }
    result["PlanningRunCancelAction"] = PlanningRunCancelAction.model_json_schema()
    result["PlanningRunRetryAction"] = PlanningRunRetryAction.model_json_schema()
    return result


def install_headless_openapi(application: FastAPI, schema_directory: Path) -> None:
    """Install a deterministic OpenAPI 3.1 generator after every router is bound."""

    def custom_openapi() -> JsonObject:
        if application.openapi_schema is not None:
            return cast(JsonObject, application.openapi_schema)
        schema = cast(
            JsonObject,
            get_openapi(
                title=application.title,
                version=application.version,
                openapi_version=application.openapi_version,
                summary=application.summary,
                description=application.description,
                routes=application.routes,
            ),
        )
        components = cast(JsonObject, schema.setdefault("components", {}))
        schemas = cast(JsonObject, components.setdefault("schemas", {}))
        for name, document in _bundled_components(schema_directory).items():
            if name in schemas:
                raise RuntimeError(
                    "Headless OpenAPI component collides with existing API"
                )
            schemas[name] = document
        schema["jsonSchemaDialect"] = "https://json-schema.org/draft/2020-12/schema"
        schema["x-aps-headless-contract"] = {
            "http_contract_version": HEADLESS_HTTP_VERSION,
            "compatibility_policy": "V1_ADDITIVE_ONLY",
            "preexisting_operation_count": 29,
            "headless_operation_count": len(HEADLESS_OPERATION_INVENTORY),
            "total_operation_count": 34,
            "transport_envelope": {
                "canonical_request_max_bytes": MAX_CANONICAL_REQUEST_BYTES,
                "action_request_max_bytes": MAX_ACTION_REQUEST_BYTES,
                "json_max_depth": MAX_JSON_DEPTH,
                "canonical_record_max_count": MAX_CANONICAL_RECORDS,
                "content_encoding": "FORBIDDEN",
                "media_type": "application/json",
            },
            "production_authority": "UNAVAILABLE_UNTIL_P8_08",
        }
        application.openapi_schema = schema
        return schema

    application.openapi = custom_openapi


__all__ = [
    "HEADLESS_OPERATION_INVENTORY",
    "install_headless_openapi",
]
