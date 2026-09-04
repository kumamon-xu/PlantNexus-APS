"""Shared synthetic builders for TEST-P8-CANONICAL-INGRESS-001."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from threading import Lock
from typing import Any, cast

from app.application.canonical_ingress import (
    CanonicalIngressBuildPlan,
    CanonicalIngressRecord,
    CanonicalIngressWriteResult,
    TrustedCanonicalIngressContext,
)
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
    request_fingerprint,
)
from app.snapshots import import_package_id_for


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIRECTORY = ROOT / "schemas" / "json"
MAPPING_FINGERPRINT = f"sha256:{'2' * 64}"
AUTHORITY_REFERENCE = "authority:p8-canonical-synthetic"
CODE_COMMIT = "c9efc2e8d35e29c139b9c819368047625f31724c"


def request_document(
    *,
    request_id: str = "REQUEST-P8-APPLICATION-001",
    correlation_id: str = "CORRELATION-P8-APPLICATION-001",
    idempotency_key: str = "p8-canonical-key-0001",
    data_plane: str = "SIMULATION",
    environment: str = "TEST",
) -> dict[str, Any]:
    payload = cast(
        dict[str, Any],
        json.loads(
            (
                ROOT / "schemas" / "samples" / "import-package.v2.synthetic.json"
            ).read_text(encoding="utf-8")
        ),
    )
    if data_plane == "PRODUCTION":
        payload["synthetic"] = False
        payload.pop("synthetic_provenance")
    payload["package_id"] = import_package_id_for(payload)
    collections = sorted(
        field
        for field, records in payload["records"].items()
        if isinstance(records, list) and records
    )
    planning_inputs = {
        "planning_policy": {
            "document_version": "planning-policy.v1",
            "artifact_id": "POLICY-P8-APPLICATION-001",
            "fingerprint": f"sha256:{'3' * 64}",
        },
        "solve_limits": {
            "document_version": "solve-limits.v1",
            "artifact_id": "LIMITS-P8-APPLICATION-001",
            "fingerprint": f"sha256:{'4' * 64}",
        },
    }
    base: dict[str, Any] = {
        "canonical_ingress_request_version": "canonical-ingress-request.v1",
        "schema_set_version": "2.10.0",
        "ingress_policy_version": "canonical-ingress-policy.v1",
        "canonicalization_version": "canonical-json.v1",
        "operation": "CREATE_PLANNING_RUN",
        "request_id": request_id,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "request_fingerprint": "",
        "requested_scope": {
            "tenant_id": "TENANT-P8-APPLICATION",
            "factory_id": "FACTORY-001",
            "planning_scope_id": "PLANNING-P8-APPLICATION",
            "data_plane": data_plane,
            "environment": environment,
        },
        "source_authority": {
            "authority_policy_version": "canonical-authority-policy.v1",
            "bindings": [
                {
                    "source_system": "schema_sample",
                    "source_version": "1.0.0",
                    "authority_reference": AUTHORITY_REFERENCE,
                    "canonical_collections": collections,
                }
            ],
            "mapping_provenance": [
                {
                    "source_system": "schema_sample",
                    "source_version": "1.0.0",
                    "mapping_profile_id": "MAPPING-P8-APPLICATION-001",
                    "mapping_profile_version": "1.0.0",
                    "mapping_profile_fingerprint": MAPPING_FINGERPRINT,
                }
            ],
        },
        "planning_inputs": planning_inputs,
        "payload_fingerprint": canonical_fingerprint(payload),
        "payload": payload,
    }
    base["request_fingerprint"] = request_fingerprint(base)
    return base


def request_bytes(
    *,
    request_id: str = "REQUEST-P8-APPLICATION-001",
    correlation_id: str = "CORRELATION-P8-APPLICATION-001",
    idempotency_key: str = "p8-canonical-key-0001",
    data_plane: str = "SIMULATION",
    environment: str = "TEST",
) -> bytes:
    return canonical_json_bytes(
        request_document(
            request_id=request_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            data_plane=data_plane,
            environment=environment,
        )
    )


def runtime_resolution() -> dict[str, Any]:
    accepted = cast(
        dict[str, Any],
        json.loads(
            (
                ROOT
                / "schemas"
                / "samples"
                / "canonical-ingress-result.v1.accepted.synthetic.json"
            ).read_text(encoding="utf-8")
        ),
    )
    return deepcopy(accepted["accepted"]["runtime_resolution"])


def build_plan(request: dict[str, Any]) -> CanonicalIngressBuildPlan:
    return CanonicalIngressBuildPlan.create(
        planning_inputs=request["planning_inputs"],
        cutoff_at_utc="2026-08-20T00:00:00Z",
        tick_seconds=60,
        horizon_start_utc="2026-08-20T00:00:00Z",
        horizon_end_utc="2026-08-21T00:00:00Z",
        priority_facts={
            "DEMAND-001": {
                "priority_weight": 2,
                "source_system": "plantnexus-synthetic-policy",
                "source_version": "1.0.0",
                "source_record_id": "P8-PRIORITY-DEMAND-001",
            }
        },
    )


def trusted_context(
    request: dict[str, Any],
    *,
    production_binding: bool | None = None,
    occurred_at_utc: str = "2026-09-04T00:00:00Z",
) -> TrustedCanonicalIngressContext:
    scope = request["requested_scope"]
    plane = cast(str, scope["data_plane"])
    return TrustedCanonicalIngressContext.create(
        actor_reference="actor:p8-application-test",
        auth_policy_version="headless-auth-policy.v1",
        tenant_id=cast(str, scope["tenant_id"]),
        factory_id=cast(str, scope["factory_id"]),
        planning_scope_id=cast(str, scope["planning_scope_id"]),
        data_plane=plane,
        environment=cast(str, scope["environment"]),
        production_binding=(
            plane == "PRODUCTION" if production_binding is None else production_binding
        ),
        authorized_authority_references=(AUTHORITY_REFERENCE,),
        authorized_mapping_fingerprints=(MAPPING_FINGERPRINT,),
        runtime_resolution=runtime_resolution(),
        build_plan=build_plan(request),
        occurred_at_utc=occurred_at_utc,
        code_commit=CODE_COMMIT,
    )


class InMemoryCanonicalIngressRepository:
    """Thread-safe port double that preserves idempotency semantics."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], CanonicalIngressRecord] = {}
        self._lock = Lock()

    def get_by_idempotency(
        self, *, scope_fingerprint: str, key_reference: str
    ) -> CanonicalIngressRecord | None:
        with self._lock:
            return self._records.get((scope_fingerprint, key_reference))

    def commit(self, record: CanonicalIngressRecord) -> CanonicalIngressWriteResult:
        document = record.document
        identity = cast(dict[str, str], document["idempotency"])
        key = (identity["scope_fingerprint"], identity["key_reference"])
        with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                return CanonicalIngressWriteResult(record=existing, replayed=True)
            self._records[key] = record
        return CanonicalIngressWriteResult(record=record, replayed=False)

    @property
    def count(self) -> int:
        return len(self._records)


__all__ = [
    "AUTHORITY_REFERENCE",
    "CODE_COMMIT",
    "InMemoryCanonicalIngressRepository",
    "MAPPING_FINGERPRINT",
    "ROOT",
    "SCHEMA_DIRECTORY",
    "build_plan",
    "request_bytes",
    "request_document",
    "runtime_resolution",
    "trusted_context",
]
