"""Deterministic TASK-P8-02 canonical ingress and PlanningRun contract checker."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

JsonObject = dict[str, Any]

REPORT_VERSION = "p8-machine-contract-report.v1"
TASK_ID = "TASK-P8-02"
TEST_ID = "TEST-P8-CANONICAL-CONTRACT-001"
DIFF_BASE = "43ff13429b2bb79854f976c0a1f5a72b1b069607"
SCHEMA_SET_VERSION = "2.10.0"
HISTORICAL_SCHEMA_COUNT = 98
IMMUTABLE_HISTORICAL_COUNT = 97
ACTIVATION_SCHEMA_MANIFEST_SHA256 = (
    "sha256:0936f1e4a19af2aa31f71808a3b56ddda6105a8089a0f6c7c5ce87c30e6543ef"
)
IMMUTABLE_HISTORICAL_MANIFEST_SHA256 = (
    "sha256:3c5ff508ec857f010c9f1211623cbceb44ec9ab2dcf45424566a921aa9a7f3dd"
)
UV_LOCK_SHA256 = (
    "sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82"
)
DEPENDENCY_PROJECTION_SHA256 = (
    "sha256:2b9c344936b57d46b279067300c22c6cf74fc87281a624944a3ce492a6251d2e"
)

SCHEMAS: Mapping[str, str] = {
    "canonical-ingress-request.v1": "canonical-ingress-request.schema.json",
    "canonical-ingress-result.v1": "canonical-ingress-result.schema.json",
    "planning-run.v1": "planning-run.schema.json",
}
SCHEMA_IDS: Mapping[str, str] = {
    "canonical-ingress-request.v1": "urn:plantnexus:aps:schema:canonical-ingress-request:v1",
    "canonical-ingress-result.v1": "urn:plantnexus:aps:schema:canonical-ingress-result:v1",
    "planning-run.v1": "urn:plantnexus:aps:schema:planning-run:v1",
}
POSITIVE_SAMPLES: tuple[str, ...] = (
    "canonical-ingress-request.v1.synthetic.json",
    "canonical-ingress-result.v1.accepted.synthetic.json",
    "canonical-ingress-result.v1.rejected.synthetic.json",
    "planning-run.v1.created.synthetic.json",
    "planning-run.v1.completed.synthetic.json",
)
NEGATIVE_SAMPLES: tuple[str, ...] = (
    "canonical-ingress.v1.invalid-unknown-field.synthetic.json",
    "canonical-ingress.v1.invalid-version.synthetic.json",
    "canonical-ingress.v1.invalid-type.synthetic.json",
    "canonical-ingress.v1.invalid-plane.synthetic.json",
    "canonical-ingress.v1.invalid-scope.synthetic.json",
    "canonical-ingress.v1.invalid-authority.synthetic.json",
    "canonical-ingress.v1.invalid-reference.synthetic.json",
    "canonical-ingress.v1.invalid-idempotency.synthetic.json",
    "canonical-ingress.v1.invalid-fingerprint.synthetic.json",
    "planning-run.v1.invalid-transition.synthetic.json",
)
NEW_SCHEMA_PATHS = {
    *(f"schemas/json/{name}" for name in SCHEMAS.values()),
    "schemas/rules/headless-error-code-registry.v1.yaml",
    *(f"schemas/samples/{name}" for name in POSITIVE_SAMPLES),
    *(f"schemas/samples/{name}" for name in NEGATIVE_SAMPLES),
}
MUTABLE_SCHEMA_METADATA_PATHS = {"schemas/data_dictionary.yaml"}
FORBIDDEN_REQUEST_KEYS = {
    "artifact_path",
    "class_name",
    "entry_point",
    "extension_artifact",
    "extension_id",
    "extension_set_id",
    "module",
    "plugin_id",
    "registry_selection",
}
FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}")


class P8ContractError(ValueError):
    """Stable P8 contract rejection with a registry code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _load_json(path: Path) -> JsonObject:
    return cast(JsonObject, json.loads(path.read_text(encoding="utf-8")))


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_fingerprint(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_bytes(value)).hexdigest()}"


def _file_fingerprint(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _walk(value: object):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _schema_registry(root: Path) -> Registry:
    registry = Registry()
    for path in sorted((root / "schemas/json").glob("*.json")):
        schema = _load_json(path)
        registry = registry.with_resource(
            cast(str, schema["$id"]), Resource.from_contents(schema)
        )
    return registry


def _validator(root: Path, document_version: str) -> Draft202012Validator:
    try:
        filename = SCHEMAS[document_version]
    except KeyError as error:
        raise P8ContractError(
            "UNKNOWN_CONTRACT_VERSION", f"unsupported document {document_version!r}"
        ) from error
    return Draft202012Validator(
        _load_json(root / "schemas/json" / filename),
        registry=_schema_registry(root),
        format_checker=FormatChecker(),
    )


def _document_version(document: Mapping[str, Any]) -> str:
    for field in (
        "canonical_ingress_request_version",
        "canonical_ingress_result_version",
        "planning_run_version",
    ):
        value = document.get(field)
        if isinstance(value, str):
            return value
    raise P8ContractError("UNKNOWN_CONTRACT_VERSION", "missing P8 document version")


def _validate_schema(root: Path, document: Mapping[str, Any]) -> None:
    version = _document_version(document)
    if version not in SCHEMAS:
        raise P8ContractError("UNKNOWN_CONTRACT_VERSION", version)
    try:
        _validator(root, version).validate(document)
    except ValidationError as error:
        pointer = "/" + "/".join(str(part) for part in error.absolute_path)
        raise P8ContractError(
            "CONTRACT_VIOLATION", f"{pointer or '/'}: {error.message}"
        ) from error


def request_fingerprint(document: Mapping[str, Any]) -> str:
    projection = {
        key: value
        for key, value in document.items()
        if key
        not in {
            "request_id",
            "correlation_id",
            "idempotency_key",
            "request_fingerprint",
        }
    }
    return canonical_fingerprint(projection)


def result_fingerprint(document: Mapping[str, Any]) -> str:
    return canonical_fingerprint(
        {key: value for key, value in document.items() if key != "result_fingerprint"}
    )


def run_fingerprint(document: Mapping[str, Any]) -> str:
    return canonical_fingerprint(
        {key: value for key, value in document.items() if key != "run_fingerprint"}
    )


def runtime_resolution_fingerprint(document: Mapping[str, Any]) -> str:
    return canonical_fingerprint(
        {
            key: value
            for key, value in document.items()
            if key != "resolution_fingerprint"
        }
    )


def scope_fingerprint(document: Mapping[str, Any]) -> str:
    return canonical_fingerprint(
        {key: value for key, value in document.items() if key != "scope_fingerprint"}
    )


def idempotency_key_reference(idempotency_key: str) -> str:
    return f"sha256:{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}"


SCOPE_FIELDS = (
    "tenant_id",
    "factory_id",
    "planning_scope_id",
    "data_plane",
    "environment",
)


def _scope_projection(document: Mapping[str, Any]) -> JsonObject:
    return {field: document.get(field) for field in SCOPE_FIELDS}


def _validate_effective_scope(
    effective_scope: Mapping[str, Any],
    *,
    requested_scope: Mapping[str, Any] | None = None,
) -> None:
    if effective_scope.get("scope_fingerprint") != scope_fingerprint(effective_scope):
        raise P8ContractError("LINEAGE_INVALID", "effective scope fingerprint")
    if requested_scope is not None and _scope_projection(
        effective_scope
    ) != _scope_projection(requested_scope):
        raise P8ContractError("SCOPE_MISMATCH", "effective scope differs from request")


def _source_triples(document: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    triples: set[tuple[str, str, str]] = set()
    payload = document.get("payload")
    if not isinstance(payload, dict):
        return triples
    records = payload.get("records")
    if not isinstance(records, dict):
        return triples
    for collection_name, collection in records.items():
        if collection_name == "canonical_records_version" or not isinstance(
            collection, list
        ):
            continue
        for record in collection:
            if not isinstance(record, dict) or not isinstance(
                record.get("source"), dict
            ):
                continue
            source = record["source"]
            system = source.get("source_system")
            version = source.get("source_version")
            if isinstance(system, str) and isinstance(version, str):
                triples.add((collection_name, system, version))
    return triples


def _source_pairs(document: Mapping[str, Any]) -> set[tuple[str, str]]:
    return {(system, version) for _, system, version in _source_triples(document)}


def _authority_pairs(document: Mapping[str, Any], field: str) -> set[tuple[str, str]]:
    source_authority = document.get("source_authority")
    if not isinstance(source_authority, dict):
        return set()
    values = source_authority.get(field)
    if not isinstance(values, list):
        return set()
    return {
        (cast(str, item.get("source_system")), cast(str, item.get("source_version")))
        for item in values
        if isinstance(item, dict)
        and isinstance(item.get("source_system"), str)
        and isinstance(item.get("source_version"), str)
    }


def _mapping_pair_sequence(document: Mapping[str, Any]) -> list[tuple[str, str]]:
    source_authority = document.get("source_authority")
    if not isinstance(source_authority, dict):
        return []
    values = source_authority.get("mapping_provenance")
    if not isinstance(values, list):
        return []
    return [
        (cast(str, item["source_system"]), cast(str, item["source_version"]))
        for item in values
        if isinstance(item, dict)
        and isinstance(item.get("source_system"), str)
        and isinstance(item.get("source_version"), str)
    ]


def _authority_collection_claims(
    document: Mapping[str, Any],
) -> list[tuple[str, str, str]]:
    source_authority = document.get("source_authority")
    if not isinstance(source_authority, dict):
        return []
    bindings = source_authority.get("bindings")
    if not isinstance(bindings, list):
        return []
    claims: list[tuple[str, str, str]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        system = binding.get("source_system")
        version = binding.get("source_version")
        collections = binding.get("canonical_collections")
        if not (
            isinstance(system, str)
            and isinstance(version, str)
            and isinstance(collections, list)
        ):
            continue
        claims.extend(
            (collection, system, version)
            for collection in collections
            if isinstance(collection, str)
        )
    return claims


def _validate_request_semantics(root: Path, document: Mapping[str, Any]) -> None:
    if document.get("canonical_ingress_request_version") != (
        "canonical-ingress-request.v1"
    ):
        raise P8ContractError("UNKNOWN_CONTRACT_VERSION", "request version")

    scope = document.get("requested_scope")
    payload = document.get("payload")
    if isinstance(scope, dict) and isinstance(payload, dict):
        plane = scope.get("data_plane")
        synthetic = payload.get("synthetic")
        if (plane == "SIMULATION" and synthetic is not True) or (
            plane == "PRODUCTION" and synthetic is not False
        ):
            raise P8ContractError("DATA_PLANE_MISMATCH", "scope and payload")
        factory_id = scope.get("factory_id")
        factories = payload.get("records", {}).get("factories", [])
        if isinstance(factory_id, str) and isinstance(factories, list):
            factory_ids = {
                item.get("factory_id") for item in factories if isinstance(item, dict)
            }
            if factory_id not in factory_ids:
                raise P8ContractError("SCOPE_MISMATCH", "factory is outside payload")

        declared = payload.get("source_versions")
        if isinstance(declared, dict):
            declared_pairs = {
                (system, version)
                for system, version in declared.items()
                if isinstance(system, str) and isinstance(version, str)
            }
            record_pairs = _source_pairs(document)
            binding_pairs = _authority_pairs(document, "bindings")
            mapping_pairs = _authority_pairs(document, "mapping_provenance")
            mapping_pair_sequence = _mapping_pair_sequence(document)
            collection_claims = _authority_collection_claims(document)
            if not record_pairs.issubset(declared_pairs):
                raise P8ContractError("LINEAGE_INVALID", "record source is undeclared")
            if declared_pairs != binding_pairs or declared_pairs != mapping_pairs:
                raise P8ContractError(
                    "AUTHORITY_CONFLICT", "source, authority and mapping sets differ"
                )
            if len(mapping_pair_sequence) != len(set(mapping_pair_sequence)):
                raise P8ContractError(
                    "AUTHORITY_CONFLICT", "source mapping is ambiguous"
                )
            if len(collection_claims) != len(set(collection_claims)):
                raise P8ContractError(
                    "AUTHORITY_CONFLICT", "canonical collection claim is duplicated"
                )
            collection_owners: dict[str, set[tuple[str, str]]] = {}
            for collection, system, version in collection_claims:
                collection_owners.setdefault(collection, set()).add((system, version))
            if any(len(owners) != 1 for owners in collection_owners.values()):
                raise P8ContractError(
                    "AUTHORITY_CONFLICT",
                    "canonical collection has multiple authorities",
                )
            if not _source_triples(document).issubset(set(collection_claims)):
                raise P8ContractError(
                    "AUTHORITY_CONFLICT",
                    "record collection is outside source authority",
                )

    planning_inputs = document.get("planning_inputs")
    if isinstance(planning_inputs, dict):
        for reference in planning_inputs.values():
            if isinstance(reference, dict):
                fingerprint = reference.get("fingerprint")
                if (
                    not isinstance(fingerprint, str)
                    or FINGERPRINT_RE.fullmatch(fingerprint) is None
                ):
                    raise P8ContractError("INVALID_REFERENCE", "planning input")

    _validate_schema(root, document)
    for node in _walk(document):
        if isinstance(node, dict) and FORBIDDEN_REQUEST_KEYS.intersection(node):
            raise P8ContractError(
                "CONTRACT_VIOLATION", "client-owned Extension selection is forbidden"
            )
    payload = cast(Mapping[str, Any], document["payload"])
    if document.get("payload_fingerprint") != canonical_fingerprint(payload):
        raise P8ContractError("LINEAGE_INVALID", "payload fingerprint")
    if document.get("request_fingerprint") != request_fingerprint(document):
        raise P8ContractError("LINEAGE_INVALID", "request fingerprint")


def validate_request(root: Path, document: Mapping[str, Any]) -> None:
    _validate_request_semantics(root, document)


def _load_error_registry(root: Path) -> dict[str, JsonObject]:
    registry = cast(
        JsonObject,
        yaml.safe_load(
            (root / "schemas/rules/headless-error-code-registry.v1.yaml").read_text(
                encoding="utf-8"
            )
        ),
    )
    codes = cast(list[JsonObject], registry["codes"])
    by_code = {cast(str, item["code"]): item for item in codes}
    if len(by_code) != len(codes):
        raise P8ContractError("CONTRACT_VIOLATION", "duplicate error code")
    return by_code


def validate_error(root: Path, error: Mapping[str, Any]) -> None:
    code = error.get("code")
    registered = _load_error_registry(root).get(cast(str, code))
    if registered is None:
        raise P8ContractError("CONTRACT_VIOLATION", "unknown headless error code")
    for field in ("category", "stage", "retryability", "action"):
        if error.get(field) != registered[field]:
            raise P8ContractError(
                "CONTRACT_VIOLATION", f"error {code!r} has invalid {field}"
            )


def validate_result(
    root: Path,
    document: Mapping[str, Any],
    *,
    request: Mapping[str, Any] | None = None,
    planning_run: Mapping[str, Any] | None = None,
) -> None:
    _validate_schema(root, document)
    if document.get("result_fingerprint") != result_fingerprint(document):
        raise P8ContractError("LINEAGE_INVALID", "result fingerprint")
    effective_scope = document.get("effective_scope")
    requested_scope = request.get("requested_scope") if request is not None else None
    if isinstance(effective_scope, dict):
        _validate_effective_scope(
            effective_scope,
            requested_scope=(
                requested_scope if isinstance(requested_scope, dict) else None
            ),
        )
    rejection = document.get("rejection")
    if isinstance(rejection, dict):
        validate_error(root, rejection)
        if rejection.get("correlation_id") != document.get("correlation_id"):
            raise P8ContractError("LINEAGE_INVALID", "rejection correlation")
    accepted = document.get("accepted")
    if isinstance(accepted, dict):
        runtime = cast(Mapping[str, Any], accepted["runtime_resolution"])
        if runtime.get("resolution_fingerprint") != runtime_resolution_fingerprint(
            runtime
        ):
            raise P8ContractError("LINEAGE_INVALID", "runtime resolution fingerprint")
    if request is not None:
        if document.get("request_id") != request.get("request_id") or document.get(
            "request_fingerprint"
        ) != request.get("request_fingerprint"):
            raise P8ContractError("LINEAGE_INVALID", "result request reference")
        if document.get("correlation_id") != request.get("correlation_id"):
            raise P8ContractError("LINEAGE_INVALID", "result correlation reference")
        idempotency = cast(Mapping[str, Any], document["idempotency"])
        if idempotency.get("outcome") != "NOT_RECORDED" and idempotency.get(
            "key_reference"
        ) != idempotency_key_reference(cast(str, request["idempotency_key"])):
            raise P8ContractError("LINEAGE_INVALID", "idempotency key reference")
        if isinstance(accepted, dict):
            payload_ref = cast(Mapping[str, Any], accepted["payload"])
            if payload_ref.get("artifact_id") != cast(
                Mapping[str, Any], request["payload"]
            ).get("package_id") or payload_ref.get("fingerprint") != request.get(
                "payload_fingerprint"
            ):
                raise P8ContractError("LINEAGE_INVALID", "accepted payload reference")
    if planning_run is not None and isinstance(accepted, dict):
        reference = cast(Mapping[str, Any], accepted["planning_run"])
        for target, source in (
            ("planning_run_id", "planning_run_id"),
            ("revision", "revision"),
            ("state", "state"),
            ("run_fingerprint", "run_fingerprint"),
        ):
            if reference.get(target) != planning_run.get(source):
                raise P8ContractError("LINEAGE_INVALID", "PlanningRun result reference")
        run_ingress = cast(Mapping[str, Any], planning_run["ingress"])
        result_idempotency = cast(Mapping[str, Any], document["idempotency"])
        if accepted.get("ingress_id") != run_ingress.get("ingress_id") or accepted.get(
            "payload"
        ) != run_ingress.get("payload"):
            raise P8ContractError("LINEAGE_INVALID", "accepted ingress lineage")
        if accepted.get("runtime_resolution") != planning_run.get("runtime_resolution"):
            raise P8ContractError("EXTENSION_SET_MISMATCH", "result/runtime resolution")
        if document.get("effective_scope") != planning_run.get("effective_scope"):
            raise P8ContractError(
                "SCOPE_MISMATCH", "result/PlanningRun effective scope"
            )
        if result_idempotency.get("key_reference") != run_ingress.get(
            "idempotency_key_reference"
        ) or result_idempotency.get("scope_fingerprint") != run_ingress.get(
            "idempotency_scope_fingerprint"
        ):
            raise P8ContractError("LINEAGE_INVALID", "result/PlanningRun idempotency")
        if accepted.get("audit") != cast(
            Mapping[str, Any], planning_run["last_transition"]
        ).get("audit"):
            raise P8ContractError("LINEAGE_INVALID", "accepted transition audit")


def _planning_machine(root: Path) -> JsonObject:
    registry = cast(
        JsonObject,
        yaml.safe_load(
            (root / "schemas/rules/state-machines.v1.yaml").read_text(encoding="utf-8")
        ),
    )
    return next(
        cast(JsonObject, machine)
        for machine in cast(list[JsonObject], registry["machines"])
        if machine["machine"] == "PLANNING_RUN"
    )


def validate_planning_run(
    root: Path, document: Mapping[str, Any], *, request: Mapping[str, Any] | None = None
) -> None:
    machine = _planning_machine(root)
    state = document.get("state")
    transition = document.get("last_transition")
    valid_pairs = {
        (item["from"], item["to"])
        for item in cast(list[JsonObject], machine["transitions"])
    }
    if isinstance(transition, dict) and isinstance(state, str):
        source = transition.get("from_state")
        target = transition.get("to_state")
        if (
            target != state
            or (
                state == "CREATED"
                and (source is not None or transition.get("sequence") != 0)
            )
            or (state != "CREATED" and (source, target) not in valid_pairs)
        ):
            raise P8ContractError("INVALID_STATE_TRANSITION", f"{source}->{target}")
    _validate_schema(root, document)
    transition = cast(Mapping[str, Any], transition)
    if document.get("revision") != cast(int, transition["sequence"]) + 1:
        raise P8ContractError("INVALID_STATE_TRANSITION", "revision/sequence")
    if document.get("updated_at_utc") != transition.get("occurred_at_utc"):
        raise P8ContractError("LINEAGE_INVALID", "transition/update timestamp")
    effective_scope = cast(Mapping[str, Any], document["effective_scope"])
    requested_scope = request.get("requested_scope") if request is not None else None
    _validate_effective_scope(
        effective_scope,
        requested_scope=requested_scope if isinstance(requested_scope, dict) else None,
    )
    terminals = set(cast(list[str], machine["terminal_states"]))
    if document.get("terminal") is not (state in terminals):
        raise P8ContractError("INVALID_STATE_TRANSITION", "terminal projection")
    expected_actions = ["READ"] if state in terminals else ["READ", "CANCEL"]
    if document.get("allowed_actions") != expected_actions:
        raise P8ContractError("INVALID_STATE_TRANSITION", "allowed actions")
    runtime = cast(Mapping[str, Any], document["runtime_resolution"])
    runtime_fingerprint = runtime_resolution_fingerprint(runtime)
    if runtime.get("resolution_fingerprint") != runtime_fingerprint:
        raise P8ContractError("LINEAGE_INVALID", "runtime resolution fingerprint")
    attempt = document.get("attempt")
    if isinstance(attempt, dict) and attempt.get(
        "runtime_resolution_fingerprint"
    ) != runtime.get("resolution_fingerprint"):
        raise P8ContractError("EXTENSION_SET_MISMATCH", "attempt/runtime resolution")
    error = document.get("error")
    if isinstance(error, dict):
        validate_error(root, error)
    if document.get("run_fingerprint") != run_fingerprint(document):
        raise P8ContractError("LINEAGE_INVALID", "PlanningRun fingerprint")
    last_audit = transition["audit"]
    audit_references = cast(list[JsonObject], document["audit_references"])
    if last_audit not in audit_references:
        raise P8ContractError("LINEAGE_INVALID", "transition audit reference")
    cancellation = document.get("cancellation")
    if (
        isinstance(cancellation, dict)
        and cancellation.get("audit") not in audit_references
    ):
        raise P8ContractError("LINEAGE_INVALID", "cancellation audit reference")
    if request is not None:
        ingress = cast(Mapping[str, Any], document["ingress"])
        if ingress.get("request_id") != request.get("request_id") or ingress.get(
            "request_fingerprint"
        ) != request.get("request_fingerprint"):
            raise P8ContractError("LINEAGE_INVALID", "PlanningRun ingress request")
        payload = cast(Mapping[str, Any], request["payload"])
        payload_reference = cast(Mapping[str, Any], ingress["payload"])
        if payload_reference.get("artifact_id") != payload.get(
            "package_id"
        ) or payload_reference.get("fingerprint") != request.get("payload_fingerprint"):
            raise P8ContractError("LINEAGE_INVALID", "PlanningRun ingress payload")
        if ingress.get("idempotency_key_reference") != idempotency_key_reference(
            cast(str, request["idempotency_key"])
        ):
            raise P8ContractError("LINEAGE_INVALID", "PlanningRun idempotency key")
        if document.get("inputs") != request.get("planning_inputs"):
            raise P8ContractError("LINEAGE_INVALID", "PlanningRun input references")
        if isinstance(error, dict) and error.get("correlation_id") != request.get(
            "correlation_id"
        ):
            raise P8ContractError("LINEAGE_INVALID", "PlanningRun error correlation")


def validate_document(root: Path, document: Mapping[str, Any]) -> None:
    version = _document_version(document)
    if version == "canonical-ingress-request.v1":
        validate_request(root, document)
    elif version == "canonical-ingress-result.v1":
        validate_result(root, document)
    elif version == "planning-run.v1":
        validate_planning_run(root, document)
    else:
        raise P8ContractError("UNKNOWN_CONTRACT_VERSION", version)


def _pointer_parent(document: JsonObject, pointer: str) -> tuple[Any, str | int]:
    parts = [
        part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]
    ]
    if not parts:
        raise ValueError("root mutation is forbidden")
    target: Any = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    leaf: str | int = int(parts[-1]) if isinstance(target, list) else parts[-1]
    return target, leaf


def apply_negative_vector(
    document: Mapping[str, Any], vector: Mapping[str, Any]
) -> JsonObject:
    mutated = copy.deepcopy(dict(document))
    mutation = cast(Mapping[str, Any], vector["mutation"])
    parent, leaf = _pointer_parent(mutated, cast(str, mutation["pointer"]))
    operation = mutation["operation"]
    if operation in {"ADD", "REPLACE", "IDEMPOTENCY_REUSE"}:
        parent[leaf] = copy.deepcopy(mutation.get("value"))
    elif operation == "REMOVE":
        del parent[leaf]
    else:
        raise ValueError(f"unsupported mutation {operation!r}")
    if operation == "IDEMPOTENCY_REUSE":
        mutated["payload_fingerprint"] = canonical_fingerprint(mutated["payload"])
        mutated["request_fingerprint"] = request_fingerprint(mutated)
    return mutated


def _immutable_schema_manifest(root: Path) -> tuple[int, str]:
    paths = sorted(
        path
        for path in (root / "schemas").rglob("*")
        if path.is_file()
        and path.relative_to(root).as_posix() not in NEW_SCHEMA_PATHS
        and path.relative_to(root).as_posix() not in MUTABLE_SCHEMA_METADATA_PATHS
    )
    payload = "".join(
        f"{path.relative_to(root).as_posix()}={hashlib.sha256(path.read_bytes()).hexdigest()}\n"
        for path in paths
    ).encode("utf-8")
    return len(paths), f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _check_schema_package(root: Path) -> JsonObject:
    schema_fingerprints: dict[str, str] = {}
    registry_ids = set()
    for version, filename in SCHEMAS.items():
        path = root / "schemas/json" / filename
        schema = _load_json(path)
        Draft202012Validator.check_schema(schema)
        if schema.get("$id") != SCHEMA_IDS[version]:
            raise ValueError(f"unexpected schema id for {filename}")
        if schema["$id"] in registry_ids:
            raise ValueError(f"duplicate schema id {schema['$id']}")
        registry_ids.add(schema["$id"])
        for node in _walk(schema):
            if not isinstance(node, dict):
                continue
            if (
                node.get("type") == "object"
                and node.get("additionalProperties") is not False
            ):
                raise ValueError(f"non-strict object in {filename}")
            if "default" in node:
                raise ValueError(f"implicit default in {filename}")
            reference = node.get("$ref")
            if isinstance(reference, str) and not (
                reference.startswith("#/")
                or reference.startswith("urn:plantnexus:aps:schema:")
            ):
                raise ValueError(f"non-offline ref {reference}")
        schema_fingerprints[filename] = _file_fingerprint(path)
    return {"schemas": len(SCHEMAS), "fingerprints": schema_fingerprints}


def _check_positive_bundle(root: Path) -> JsonObject:
    samples = {
        name: _load_json(root / "schemas/samples" / name) for name in POSITIVE_SAMPLES
    }
    request = samples[POSITIVE_SAMPLES[0]]
    created = samples[POSITIVE_SAMPLES[3]]
    completed = samples[POSITIVE_SAMPLES[4]]
    validate_request(root, request)
    validate_planning_run(root, created, request=request)
    validate_planning_run(root, completed, request=request)
    validate_result(
        root, samples[POSITIVE_SAMPLES[1]], request=request, planning_run=created
    )
    validate_result(root, samples[POSITIVE_SAMPLES[2]], request=request)
    for sample in samples.values():
        if json.loads(_canonical_bytes(sample)) != sample:
            raise ValueError("sample canonical round-trip failed")
    if completed["runtime_resolution"] != created["runtime_resolution"]:
        raise P8ContractError("EXTENSION_SET_MISMATCH", "run revisions")
    return {
        "positive_samples": len(samples),
        "request_fingerprint": request["request_fingerprint"],
        "accepted_result_fingerprint": samples[POSITIVE_SAMPLES[1]][
            "result_fingerprint"
        ],
        "effective_scope_fingerprint": created["effective_scope"]["scope_fingerprint"],
        "idempotency_key_reference": created["ingress"]["idempotency_key_reference"],
        "runtime_resolution_fingerprint": created["runtime_resolution"][
            "resolution_fingerprint"
        ],
        "created_run_fingerprint": created["run_fingerprint"],
        "completed_run_fingerprint": completed["run_fingerprint"],
    }


def _check_negative_vectors(root: Path) -> JsonObject:
    observed: list[str] = []
    for name in NEGATIVE_SAMPLES:
        vector = _load_json(root / "schemas/samples" / name)
        base = _load_json(root / "schemas/samples" / cast(str, vector["base_sample"]))
        mutated = apply_negative_vector(base, vector)
        expected = cast(str, vector["expected_rejection"])
        if (
            cast(Mapping[str, Any], vector["mutation"])["operation"]
            == "IDEMPOTENCY_REUSE"
        ):
            validate_request(root, base)
            validate_request(root, mutated)
            if (
                base["idempotency_key"] != mutated["idempotency_key"]
                or base["requested_scope"] != mutated["requested_scope"]
                or base["request_fingerprint"] == mutated["request_fingerprint"]
            ):
                raise ValueError("idempotency conflict vector is not exact")
            code = "IDEMPOTENCY_CONFLICT"
        else:
            try:
                validate_document(root, mutated)
            except P8ContractError as error:
                code = error.code
            else:
                raise ValueError(f"negative vector unexpectedly passed: {name}")
        if code != expected:
            raise ValueError(f"{name}: expected {expected}, observed {code}")
        observed.append(code)
    return {"negative_samples": len(observed), "stable_codes": observed}


def _check_required_field_mutations(root: Path) -> JsonObject:
    samples = {
        "canonical-ingress-request.v1": _load_json(
            root / "schemas/samples" / POSITIVE_SAMPLES[0]
        ),
        "canonical-ingress-result.v1": _load_json(
            root / "schemas/samples" / POSITIVE_SAMPLES[1]
        ),
        "planning-run.v1": _load_json(root / "schemas/samples" / POSITIVE_SAMPLES[3]),
    }
    rejected = 0
    for version, sample in samples.items():
        schema = _load_json(root / "schemas/json" / SCHEMAS[version])
        for field in cast(list[str], schema["required"]):
            mutation = copy.deepcopy(sample)
            del mutation[field]
            try:
                _validator(root, version).validate(mutation)
            except ValidationError:
                rejected += 1
            else:
                raise ValueError(f"missing required field passed: {version}.{field}")
    return {"required_field_rejections": rejected}


def _check_registries_and_metadata(root: Path) -> JsonObject:
    errors = _load_error_registry(root)
    machine = _planning_machine(root)
    if set(machine["states"]) != {
        "CREATED",
        "INGESTING",
        "VALIDATING",
        "SNAPSHOTTED",
        "BUILDING",
        "SOLVING",
        "SOLVED",
        "VERIFYING",
        "COMPLETED",
        "DATA_REJECTED",
        "MODEL_INVALID",
        "INFEASIBLE",
        "NO_SOLUTION_WITHIN_LIMIT",
        "VALIDATION_FAILED",
        "CANCELLED",
        "FAILED",
    }:
        raise ValueError("PlanningRun state vocabulary drifted")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if project["tool"]["plantnexus-aps"]["versions"]["schema"] != SCHEMA_SET_VERSION:
        raise ValueError("pyproject schema metadata mismatch")
    dictionary = cast(
        JsonObject,
        yaml.safe_load(
            (root / "schemas/data_dictionary.yaml").read_text(encoding="utf-8")
        ),
    )
    if dictionary.get("schema_set_version") != SCHEMA_SET_VERSION:
        raise ValueError("data dictionary schema metadata mismatch")
    expected = {*SCHEMAS, "headless-error-code-registry.v1"}
    if not expected.issubset(set(cast(Mapping[str, Any], dictionary["schemas"]))):
        raise ValueError("data dictionary omits P8 contracts")
    return {
        "error_codes": len(errors),
        "planning_run_states": len(machine["states"]),
        "planning_run_transitions": len(machine["transitions"]),
    }


def _check_preservation(root: Path) -> JsonObject:
    count, digest = _immutable_schema_manifest(root)
    if (
        count != IMMUTABLE_HISTORICAL_COUNT
        or digest != IMMUTABLE_HISTORICAL_MANIFEST_SHA256
    ):
        raise ValueError(f"historical schema bytes changed: {count} {digest}")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependency_projection = {
        "runtime": project["project"]["dependencies"],
        "groups": project.get("dependency-groups", {}),
    }
    dependency_digest = canonical_fingerprint(dependency_projection)
    if dependency_digest != DEPENDENCY_PROJECTION_SHA256:
        raise ValueError("dependency projection changed")
    if _file_fingerprint(root / "uv.lock") != UV_LOCK_SHA256:
        raise ValueError("uv.lock changed")
    return {
        "activation_schema_count": HISTORICAL_SCHEMA_COUNT,
        "activation_manifest_sha256": ACTIVATION_SCHEMA_MANIFEST_SHA256,
        "immutable_historical_count": count,
        "immutable_historical_manifest_sha256": digest,
        "dependency_projection_sha256": dependency_digest,
        "uv_lock_sha256": UV_LOCK_SHA256,
    }


def run_contract_checks(root: Path) -> JsonObject:
    root = root.resolve()
    checks = [
        {
            "name": "historical-byte-and-dependency-preservation",
            "evidence": _check_preservation(root),
        },
        {
            "name": "strict-offline-schema-package",
            "evidence": _check_schema_package(root),
        },
        {
            "name": "positive-round-trip-lineage",
            "evidence": _check_positive_bundle(root),
        },
        {
            "name": "stable-negative-rejections",
            "evidence": _check_negative_vectors(root),
        },
        {
            "name": "required-field-mutation",
            "evidence": _check_required_field_mutations(root),
        },
        {
            "name": "state-error-and-version-registries",
            "evidence": _check_registries_and_metadata(root),
        },
    ]
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "schema_set_version": SCHEMA_SET_VERSION,
        "status": "PASS",
        "result": "PASS",
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "new_schemas": len(SCHEMAS),
            "new_rule_registries": 1,
            "positive_samples": len(POSITIVE_SAMPLES),
            "negative_samples": len(NEGATIVE_SAMPLES),
            "immutable_historical_artifacts": IMMUTABLE_HISTORICAL_COUNT,
        },
        "boundaries": {
            "external_input": "VERSIONED_CANONICAL_JSON_ONLY",
            "operation": "CREATE_PLANNING_RUN",
            "runtime_resolution_owner": "SERVER",
            "client_extension_selection": "FORBIDDEN",
            "state_registry": "state-machines.v1-UNCHANGED",
            "api_database_worker_extension_sdk": "NOT_IMPLEMENTED",
            "third_party_adapter": "EXCLUDED",
            "demo": "EXCLUDED",
            "production_readiness": "NOT_CLAIMED",
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p8-machine-contracts.json"),
    )
    args = parser.parse_args(argv)
    try:
        report = run_contract_checks(args.root)
    except Exception as error:  # deterministic CI failure envelope
        report = {
            "report_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "test_id": TEST_ID,
            "diff_base": DIFF_BASE,
            "schema_set_version": SCHEMA_SET_VERSION,
            "status": "FAIL",
            "result": "FAIL",
            "check_count": 0,
            "checks": [],
            "issues": [{"type": type(error).__name__, "message": str(error)}],
        }
        _write_report(args.report, report)
        return 1
    _write_report(args.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
