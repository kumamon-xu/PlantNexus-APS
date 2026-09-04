"""Strict, dependency-free consumer for the frozen P8 Headless contracts.

The HTTP transport is intentionally outside this module. A Runtime supplies a
server-owned schema directory; request data can never select a schema or file
path. The small JSON Schema evaluator implements only the vocabulary used by
the checked-in APS contracts and keeps ``jsonschema`` a development dependency.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, NoReturn, cast


type JsonObject = dict[str, Any]

CANONICAL_INGRESS_REQUEST_VERSION = "canonical-ingress-request.v1"
CANONICAL_INGRESS_RESULT_VERSION = "canonical-ingress-result.v1"
PLANNING_RUN_VERSION = "planning-run.v1"
HEADLESS_SCHEMA_SET_VERSION = "2.10.0"
CANONICALIZATION_VERSION = "canonical-json.v1"

REQUEST_SCHEMA_ID = "urn:plantnexus:aps:schema:canonical-ingress-request:v1"
RESULT_SCHEMA_ID = "urn:plantnexus:aps:schema:canonical-ingress-result:v1"
PLANNING_RUN_SCHEMA_ID = "urn:plantnexus:aps:schema:planning-run:v1"
AUDIT_EVENT_SCHEMA_ID = "urn:plantnexus:aps:schema:audit-event:v1"

_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_FORBIDDEN_REQUEST_KEYS = {
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
_SCOPE_FIELDS = (
    "tenant_id",
    "factory_id",
    "planning_scope_id",
    "data_plane",
    "environment",
)


class CanonicalIngressContractCode(StrEnum):
    MALFORMED_JSON = "MALFORMED_JSON"
    DUPLICATE_JSON_KEY = "DUPLICATE_JSON_KEY"
    NON_FINITE_NUMBER = "NON_FINITE_NUMBER"
    UNKNOWN_CONTRACT_VERSION = "UNKNOWN_CONTRACT_VERSION"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    AUTHORITY_CONFLICT = "AUTHORITY_CONFLICT"
    LINEAGE_INVALID = "LINEAGE_INVALID"
    INVALID_REFERENCE = "INVALID_REFERENCE"


class CanonicalIngressContractError(ValueError):
    """Stable rejection that never includes raw request values."""

    def __init__(
        self,
        code: CanonicalIngressContractCode,
        *,
        pointer: str,
        expected_contract: str,
        message: str,
    ) -> None:
        self.code = code
        self.pointer = pointer
        self.expected_contract = expected_contract
        self.message = message
        super().__init__(f"{code.value} at {pointer}: {message}")


def _reject(
    code: CanonicalIngressContractCode,
    *,
    pointer: str,
    expected_contract: str,
    message: str,
) -> NoReturn:
    raise CanonicalIngressContractError(
        code,
        pointer=pointer,
        expected_contract=expected_contract,
        message=message,
    )


def canonical_json_bytes(value: object) -> bytes:
    """Return the exact canonical-json.v1 bytes used by P8 fingerprints."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise CanonicalIngressContractError(
            CanonicalIngressContractCode.CONTRACT_VIOLATION,
            pointer="/",
            expected_contract="canonical-json.v1 finite JSON value",
            message="Canonical serialization failed",
        ) from error


def canonical_fingerprint(value: object) -> str:
    return f"sha256:{sha256(canonical_json_bytes(value)).hexdigest()}"


def request_fingerprint(document: Mapping[str, object]) -> str:
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


def result_fingerprint(document: Mapping[str, object]) -> str:
    return canonical_fingerprint(
        {key: value for key, value in document.items() if key != "result_fingerprint"}
    )


def run_fingerprint(document: Mapping[str, object]) -> str:
    return canonical_fingerprint(
        {key: value for key, value in document.items() if key != "run_fingerprint"}
    )


def runtime_resolution_fingerprint(document: Mapping[str, object]) -> str:
    return canonical_fingerprint(
        {
            key: value
            for key, value in document.items()
            if key != "resolution_fingerprint"
        }
    )


def scope_fingerprint(document: Mapping[str, object]) -> str:
    return canonical_fingerprint(
        {key: value for key, value in document.items() if key != "scope_fingerprint"}
    )


def idempotency_key_reference(idempotency_key: str) -> str:
    return f"sha256:{sha256(idempotency_key.encode('utf-8')).hexdigest()}"


class _DuplicateKey(ValueError):
    pass


class _NonFiniteNumber(ValueError):
    pass


def _object_without_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _NonFiniteNumber
    return parsed


def _reject_constant(_value: str) -> NoReturn:
    raise _NonFiniteNumber


def parse_strict_json(raw: bytes) -> JsonObject:
    """Parse one UTF-8 object while rejecting duplicates and non-finite numbers."""

    if not isinstance(raw, bytes):
        _reject(
            CanonicalIngressContractCode.MALFORMED_JSON,
            pointer="/",
            expected_contract="strict UTF-8 JSON bytes",
            message="Canonical ingress requires a byte payload",
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except _DuplicateKey as error:
        raise CanonicalIngressContractError(
            CanonicalIngressContractCode.DUPLICATE_JSON_KEY,
            pointer="/",
            expected_contract="unique JSON object member names",
            message="Duplicate JSON object member names are forbidden",
        ) from error
    except _NonFiniteNumber as error:
        raise CanonicalIngressContractError(
            CanonicalIngressContractCode.NON_FINITE_NUMBER,
            pointer="/",
            expected_contract="finite JSON numbers",
            message="Non-finite JSON numbers are forbidden",
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise CanonicalIngressContractError(
            CanonicalIngressContractCode.MALFORMED_JSON,
            pointer="/",
            expected_contract="strict UTF-8 JSON object",
            message="Canonical ingress JSON could not be parsed",
        ) from error
    if not isinstance(value, dict):
        _reject(
            CanonicalIngressContractCode.CONTRACT_VIOLATION,
            pointer="/",
            expected_contract=CANONICAL_INGRESS_REQUEST_VERSION,
            message="Canonical ingress root must be an object",
        )
    return cast(JsonObject, value)


@dataclass(frozen=True, slots=True)
class _SchemaViolation(ValueError):
    pointer: str


def _pointer(parts: Sequence[object]) -> str:
    if not parts:
        return "/"
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped)


def _json_identity_value(value: object) -> object:
    """Normalize JSON values using JSON Schema's mathematical number equality."""

    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["boolean", value]
    if isinstance(value, int):
        return ["number", str(value)]
    if isinstance(value, float):
        if not math.isfinite(value):
            return ["non-finite-number", value.hex()]
        if value.is_integer():
            return ["number", str(int(value))]
        return ["number", value.hex()]
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, list):
        return ["array", [_json_identity_value(item) for item in value]]
    if isinstance(value, Mapping):
        return [
            "object",
            [
                [key, _json_identity_value(value[key])]
                for key in sorted(value)
                if isinstance(key, str)
            ],
        ]
    return ["unsupported", type(value).__qualname__]


def _json_identity(value: object) -> bytes:
    return canonical_json_bytes(_json_identity_value(value))


def _matches_type(value: object, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and math.isfinite(value) and value.is_integer()
        )
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and (not isinstance(value, float) or math.isfinite(value))
        )
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return False


def _valid_datetime(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


class FrozenSchemaCatalog:
    """Server-owned registry for the checked-in APS JSON Schema documents."""

    def __init__(self, documents: Mapping[str, Mapping[str, object]]) -> None:
        self._documents = {
            schema_id: cast(JsonObject, json.loads(canonical_json_bytes(document)))
            for schema_id, document in documents.items()
        }
        required = {REQUEST_SCHEMA_ID, RESULT_SCHEMA_ID, PLANNING_RUN_SCHEMA_ID}
        if not required.issubset(self._documents):
            missing = sorted(required - self._documents.keys())
            raise ValueError(f"required P8 schemas are absent: {missing}")

    @classmethod
    def from_directory(cls, schema_directory: Path) -> FrozenSchemaCatalog:
        """Load schemas only from a trusted Runtime configuration directory."""

        documents: dict[str, Mapping[str, object]] = {}
        for path in sorted(schema_directory.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or not isinstance(value.get("$id"), str):
                continue
            documents[cast(str, value["$id"])] = cast(Mapping[str, object], value)
        return cls(documents)

    def validate(self, schema_id: str, value: object) -> None:
        try:
            root = self._documents[schema_id]
        except KeyError as error:
            raise ValueError(f"unknown server schema identity: {schema_id}") from error
        self._validate(root, value, root=root, path=())

    def validate_reference(self, reference: str, value: object) -> None:
        schema, root = self._resolve(reference, current_root={})
        self._validate(schema, value, root=root, path=())

    def _resolve(
        self,
        reference: str,
        *,
        current_root: Mapping[str, object],
    ) -> tuple[Mapping[str, object], Mapping[str, object]]:
        if reference.startswith("#"):
            root = current_root
            fragment = reference[1:]
        else:
            schema_id, marker, suffix = reference.partition("#")
            try:
                root = self._documents[schema_id]
            except KeyError as error:
                raise ValueError(
                    f"unregistered schema reference: {schema_id}"
                ) from error
            fragment = suffix if marker else ""
        target: object = root
        if fragment:
            if not fragment.startswith("/"):
                raise ValueError(f"unsupported schema fragment: {reference}")
            for raw_part in fragment.removeprefix("/").split("/"):
                part = raw_part.replace("~1", "/").replace("~0", "~")
                if not isinstance(target, Mapping) or part not in target:
                    raise ValueError(f"unresolved schema reference: {reference}")
                target = target[part]
        if not isinstance(target, Mapping):
            raise ValueError(f"schema reference is not an object: {reference}")
        return cast(Mapping[str, object], target), root

    def _validate(
        self,
        schema: object,
        value: object,
        *,
        root: Mapping[str, object],
        path: tuple[object, ...],
    ) -> None:
        if schema is True:
            return
        if schema is False or not isinstance(schema, Mapping):
            raise _SchemaViolation(_pointer(path))

        reference = schema.get("$ref")
        if isinstance(reference, str):
            resolved, resolved_root = self._resolve(reference, current_root=root)
            self._validate(resolved, value, root=resolved_root, path=path)

        const = schema.get("const", cast(object, ...))
        if const is not ... and _json_identity(value) != _json_identity(const):
            raise _SchemaViolation(_pointer(path))
        enum = schema.get("enum")
        if isinstance(enum, list) and all(
            _json_identity(value) != _json_identity(candidate) for candidate in enum
        ):
            raise _SchemaViolation(_pointer(path))

        expected_type = schema.get("type")
        if isinstance(expected_type, str):
            if not _matches_type(value, expected_type):
                raise _SchemaViolation(_pointer(path))
        elif isinstance(expected_type, list):
            if not any(
                isinstance(item, str) and _matches_type(value, item)
                for item in expected_type
            ):
                raise _SchemaViolation(_pointer(path))

        all_of = schema.get("allOf")
        if isinstance(all_of, list):
            for child in all_of:
                self._validate(child, value, root=root, path=path)

        any_of = schema.get("anyOf")
        if isinstance(any_of, list) and not self._matching(any_of, value, root, path):
            raise _SchemaViolation(_pointer(path))
        one_of = schema.get("oneOf")
        if isinstance(one_of, list):
            matches = self._matching(one_of, value, root, path)
            if len(matches) != 1:
                raise _SchemaViolation(_pointer(path))
        negated = schema.get("not")
        if negated is not None:
            try:
                self._validate(negated, value, root=root, path=path)
            except _SchemaViolation:
                pass
            else:
                raise _SchemaViolation(_pointer(path))
        conditional = schema.get("if")
        if conditional is not None:
            try:
                self._validate(conditional, value, root=root, path=path)
            except _SchemaViolation:
                branch = schema.get("else")
            else:
                branch = schema.get("then")
            if branch is not None:
                self._validate(branch, value, root=root, path=path)

        if isinstance(value, dict):
            required = schema.get("required")
            if isinstance(required, list):
                for field in required:
                    if isinstance(field, str) and field not in value:
                        raise _SchemaViolation(_pointer((*path, field)))
            minimum_properties = schema.get("minProperties")
            if isinstance(minimum_properties, int) and len(value) < minimum_properties:
                raise _SchemaViolation(_pointer(path))
            maximum_properties = schema.get("maxProperties")
            if isinstance(maximum_properties, int) and len(value) > maximum_properties:
                raise _SchemaViolation(_pointer(path))
            property_names = schema.get("propertyNames")
            if property_names is not None:
                for field in value:
                    self._validate(
                        property_names, field, root=root, path=(*path, field)
                    )
            properties_value = schema.get("properties")
            properties = (
                cast(Mapping[str, object], properties_value)
                if isinstance(properties_value, Mapping)
                else {}
            )
            for field, child in properties.items():
                if field in value:
                    self._validate(child, value[field], root=root, path=(*path, field))
            additional = schema.get("additionalProperties", True)
            extras = sorted(set(value) - set(properties))
            if additional is False and extras:
                raise _SchemaViolation(_pointer((*path, extras[0])))
            if isinstance(additional, Mapping):
                for field in extras:
                    self._validate(
                        additional, value[field], root=root, path=(*path, field)
                    )

        if isinstance(value, list):
            minimum_items = schema.get("minItems")
            if isinstance(minimum_items, int) and len(value) < minimum_items:
                raise _SchemaViolation(_pointer(path))
            maximum_items = schema.get("maxItems")
            if isinstance(maximum_items, int) and len(value) > maximum_items:
                raise _SchemaViolation(_pointer(path))
            if schema.get("uniqueItems") is True:
                identities = [_json_identity(item) for item in value]
                if len(identities) != len(set(identities)):
                    raise _SchemaViolation(_pointer(path))
            prefix_value = schema.get("prefixItems")
            prefix = prefix_value if isinstance(prefix_value, list) else []
            for index, child in enumerate(prefix):
                if index < len(value):
                    self._validate(child, value[index], root=root, path=(*path, index))
            items = schema.get("items")
            if items is False and len(value) > len(prefix):
                raise _SchemaViolation(_pointer((*path, len(prefix))))
            if items not in (None, False, True):
                start = len(prefix) if prefix else 0
                for index in range(start, len(value)):
                    self._validate(items, value[index], root=root, path=(*path, index))

        if isinstance(value, str):
            minimum_length = schema.get("minLength")
            if isinstance(minimum_length, int) and len(value) < minimum_length:
                raise _SchemaViolation(_pointer(path))
            maximum_length = schema.get("maxLength")
            if isinstance(maximum_length, int) and len(value) > maximum_length:
                raise _SchemaViolation(_pointer(path))
            pattern = schema.get("pattern")
            if isinstance(pattern, str) and re.search(pattern, value) is None:
                raise _SchemaViolation(_pointer(path))
            if schema.get("format") == "date-time" and not _valid_datetime(value):
                raise _SchemaViolation(_pointer(path))

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = schema.get("minimum")
            if isinstance(minimum, (int, float)) and value < minimum:
                raise _SchemaViolation(_pointer(path))
            maximum = schema.get("maximum")
            if isinstance(maximum, (int, float)) and value > maximum:
                raise _SchemaViolation(_pointer(path))
            exclusive_minimum = schema.get("exclusiveMinimum")
            if (
                isinstance(exclusive_minimum, (int, float))
                and value <= exclusive_minimum
            ):
                raise _SchemaViolation(_pointer(path))
            exclusive_maximum = schema.get("exclusiveMaximum")
            if (
                isinstance(exclusive_maximum, (int, float))
                and value >= exclusive_maximum
            ):
                raise _SchemaViolation(_pointer(path))

    def _matching(
        self,
        schemas: Iterable[object],
        value: object,
        root: Mapping[str, object],
        path: tuple[object, ...],
    ) -> list[object]:
        matches: list[object] = []
        for child in schemas:
            try:
                self._validate(child, value, root=root, path=path)
            except _SchemaViolation:
                continue
            matches.append(child)
        return matches


def _walk(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        yield cast(Mapping[str, object], value)
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _source_triples(document: Mapping[str, object]) -> set[tuple[str, str, str]]:
    triples: set[tuple[str, str, str]] = set()
    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        return triples
    records = payload.get("records")
    if not isinstance(records, Mapping):
        return triples
    for collection_name, collection in records.items():
        if collection_name == "canonical_records_version" or not isinstance(
            collection, list
        ):
            continue
        for record in collection:
            if not isinstance(record, Mapping) or not isinstance(
                record.get("source"), Mapping
            ):
                continue
            source = cast(Mapping[str, object], record["source"])
            system = source.get("source_system")
            version = source.get("source_version")
            if isinstance(system, str) and isinstance(version, str):
                triples.add((collection_name, system, version))
    return triples


def _authority_items(
    document: Mapping[str, object], field: str
) -> list[Mapping[str, object]]:
    source_authority = document.get("source_authority")
    if not isinstance(source_authority, Mapping):
        return []
    values = source_authority.get(field)
    if not isinstance(values, list):
        return []
    return [
        cast(Mapping[str, object], item) for item in values if isinstance(item, Mapping)
    ]


class CanonicalIngressContract:
    """Strict parser and cross-document validator for P8 v1 carriers."""

    def __init__(self, schemas: FrozenSchemaCatalog) -> None:
        self._schemas = schemas

    @classmethod
    def from_schema_directory(cls, schema_directory: Path) -> CanonicalIngressContract:
        return cls(FrozenSchemaCatalog.from_directory(schema_directory))

    def parse_request(self, raw: bytes) -> JsonObject:
        document = parse_strict_json(raw)
        self.validate_request(document)
        return cast(JsonObject, json.loads(canonical_json_bytes(document)))

    def _validate_schema(self, schema_id: str, document: object) -> None:
        try:
            self._schemas.validate(schema_id, document)
        except _SchemaViolation as error:
            raise CanonicalIngressContractError(
                CanonicalIngressContractCode.CONTRACT_VIOLATION,
                pointer=error.pointer,
                expected_contract=schema_id,
                message="Document violates the frozen JSON Schema",
            ) from error

    def validate_request(self, document: Mapping[str, object]) -> None:
        if document.get("canonical_ingress_request_version") != (
            CANONICAL_INGRESS_REQUEST_VERSION
        ):
            _reject(
                CanonicalIngressContractCode.UNKNOWN_CONTRACT_VERSION,
                pointer="/canonical_ingress_request_version",
                expected_contract=CANONICAL_INGRESS_REQUEST_VERSION,
                message="Canonical ingress request version is unsupported",
            )

        scope = document.get("requested_scope")
        payload = document.get("payload")
        if isinstance(scope, Mapping) and isinstance(payload, Mapping):
            plane = scope.get("data_plane")
            synthetic = payload.get("synthetic")
            if (plane == "SIMULATION" and synthetic is not True) or (
                plane == "PRODUCTION" and synthetic is not False
            ):
                _reject(
                    CanonicalIngressContractCode.DATA_PLANE_MISMATCH,
                    pointer="/payload/synthetic",
                    expected_contract="requested scope data plane",
                    message="Payload and requested data plane differ",
                )
            factory_id = scope.get("factory_id")
            records = payload.get("records")
            factories = (
                records.get("factories", []) if isinstance(records, Mapping) else []
            )
            if isinstance(factory_id, str) and isinstance(factories, list):
                factory_ids = {
                    item.get("factory_id")
                    for item in factories
                    if isinstance(item, Mapping)
                }
                if factory_id not in factory_ids:
                    _reject(
                        CanonicalIngressContractCode.SCOPE_MISMATCH,
                        pointer="/requested_scope/factory_id",
                        expected_contract="factory contained in canonical payload",
                        message="Requested factory is outside the payload",
                    )

            declared = payload.get("source_versions")
            if isinstance(declared, Mapping):
                declared_pairs = {
                    (system, version)
                    for system, version in declared.items()
                    if isinstance(system, str) and isinstance(version, str)
                }
                record_triples = _source_triples(document)
                record_pairs = {
                    (system, version) for _, system, version in record_triples
                }
                bindings = _authority_items(document, "bindings")
                mappings = _authority_items(document, "mapping_provenance")
                binding_pairs = {
                    (item.get("source_system"), item.get("source_version"))
                    for item in bindings
                    if isinstance(item.get("source_system"), str)
                    and isinstance(item.get("source_version"), str)
                }
                mapping_sequence = [
                    (item.get("source_system"), item.get("source_version"))
                    for item in mappings
                    if isinstance(item.get("source_system"), str)
                    and isinstance(item.get("source_version"), str)
                ]
                mapping_pairs = set(mapping_sequence)
                claims: list[tuple[str, str, str]] = []
                for item in bindings:
                    system = item.get("source_system")
                    version = item.get("source_version")
                    collections = item.get("canonical_collections")
                    if (
                        isinstance(system, str)
                        and isinstance(version, str)
                        and isinstance(collections, list)
                    ):
                        claims.extend(
                            (collection, system, version)
                            for collection in collections
                            if isinstance(collection, str)
                        )
                if not record_pairs.issubset(declared_pairs):
                    _reject(
                        CanonicalIngressContractCode.LINEAGE_INVALID,
                        pointer="/payload/source_versions",
                        expected_contract="all record sources declared",
                        message="A canonical record source is undeclared",
                    )
                if declared_pairs != binding_pairs or declared_pairs != mapping_pairs:
                    _reject(
                        CanonicalIngressContractCode.AUTHORITY_CONFLICT,
                        pointer="/source_authority",
                        expected_contract="equal source, authority, and mapping sets",
                        message="Source authority and mapping sets differ",
                    )
                if len(mapping_sequence) != len(mapping_pairs):
                    _reject(
                        CanonicalIngressContractCode.AUTHORITY_CONFLICT,
                        pointer="/source_authority/mapping_provenance",
                        expected_contract="one mapping per source version",
                        message="Source mapping is ambiguous",
                    )
                if len(claims) != len(set(claims)):
                    _reject(
                        CanonicalIngressContractCode.AUTHORITY_CONFLICT,
                        pointer="/source_authority/bindings",
                        expected_contract="unique canonical collection claims",
                        message="A canonical collection claim is duplicated",
                    )
                owners: dict[str, set[tuple[str, str]]] = {}
                for collection, system, version in claims:
                    owners.setdefault(collection, set()).add((system, version))
                if any(len(values) != 1 for values in owners.values()):
                    _reject(
                        CanonicalIngressContractCode.AUTHORITY_CONFLICT,
                        pointer="/source_authority/bindings",
                        expected_contract="one authority per canonical collection",
                        message="A canonical collection has multiple authorities",
                    )
                if not record_triples.issubset(set(claims)):
                    _reject(
                        CanonicalIngressContractCode.AUTHORITY_CONFLICT,
                        pointer="/source_authority/bindings",
                        expected_contract="authority for every populated collection",
                        message="A populated collection is outside source authority",
                    )

        planning_inputs = document.get("planning_inputs")
        if isinstance(planning_inputs, Mapping):
            for field, reference in planning_inputs.items():
                if isinstance(reference, Mapping):
                    fingerprint = reference.get("fingerprint")
                    if (
                        not isinstance(fingerprint, str)
                        or _FINGERPRINT.fullmatch(fingerprint) is None
                    ):
                        _reject(
                            CanonicalIngressContractCode.INVALID_REFERENCE,
                            pointer=f"/planning_inputs/{field}/fingerprint",
                            expected_contract="sha256:<64 lowercase hex>",
                            message="Planning input fingerprint is invalid",
                        )

        self._validate_schema(REQUEST_SCHEMA_ID, document)
        for node in _walk(document):
            forbidden = sorted(_FORBIDDEN_REQUEST_KEYS.intersection(node))
            if forbidden:
                _reject(
                    CanonicalIngressContractCode.CONTRACT_VIOLATION,
                    pointer=f"/{forbidden[0]}",
                    expected_contract="server-owned Runtime and Extension resolution",
                    message="Client-owned code or Extension selection is forbidden",
                )
        payload = cast(Mapping[str, object], document["payload"])
        if document.get("payload_fingerprint") != canonical_fingerprint(payload):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/payload_fingerprint",
                expected_contract="SHA-256 of canonical payload bytes",
                message="Payload fingerprint does not match canonical content",
            )
        if document.get("request_fingerprint") != request_fingerprint(document):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/request_fingerprint",
                expected_contract="canonical-ingress request fingerprint projection v1",
                message="Request fingerprint does not match canonical content",
            )

    def validate_effective_scope(
        self,
        effective_scope: Mapping[str, object],
        *,
        requested_scope: Mapping[str, object],
    ) -> None:
        try:
            self._schemas.validate_reference(
                f"{RESULT_SCHEMA_ID}#/$defs/effectiveScope", effective_scope
            )
        except _SchemaViolation as error:
            raise CanonicalIngressContractError(
                CanonicalIngressContractCode.SCOPE_MISMATCH,
                pointer=error.pointer,
                expected_contract="server-resolved effective scope v1",
                message="Effective scope is invalid",
            ) from error
        if effective_scope.get("scope_fingerprint") != scope_fingerprint(
            effective_scope
        ):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/effective_scope/scope_fingerprint",
                expected_contract="effective scope fingerprint projection v1",
                message="Effective scope fingerprint is invalid",
            )
        if {field: effective_scope.get(field) for field in _SCOPE_FIELDS} != {
            field: requested_scope.get(field) for field in _SCOPE_FIELDS
        }:
            _reject(
                CanonicalIngressContractCode.SCOPE_MISMATCH,
                pointer="/effective_scope",
                expected_contract="intersection equal to requested business scope",
                message="Effective scope differs from the request",
            )

    def validate_runtime_resolution(self, document: Mapping[str, object]) -> None:
        try:
            self._schemas.validate_reference(
                f"{RESULT_SCHEMA_ID}#/$defs/runtimeResolution", document
            )
        except _SchemaViolation as error:
            raise CanonicalIngressContractError(
                CanonicalIngressContractCode.CONTRACT_VIOLATION,
                pointer=error.pointer,
                expected_contract="runtime-resolution.v1",
                message="Server Runtime resolution violates its frozen carrier",
            ) from error
        if document.get("resolution_fingerprint") != runtime_resolution_fingerprint(
            document
        ):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/runtime_resolution/resolution_fingerprint",
                expected_contract="runtime resolution fingerprint projection v1",
                message="Runtime resolution fingerprint is invalid",
            )

    def validate_audit_event(self, document: Mapping[str, object]) -> None:
        self._validate_schema(AUDIT_EVENT_SCHEMA_ID, document)

    def validate_planning_run(
        self,
        document: Mapping[str, object],
        *,
        request: Mapping[str, object],
    ) -> None:
        transition = document.get("last_transition")
        state = document.get("state")
        if isinstance(transition, Mapping) and (
            state != "CREATED"
            or transition.get("from_state") is not None
            or transition.get("to_state") != "CREATED"
            or transition.get("sequence") != 0
        ):
            _reject(
                CanonicalIngressContractCode.CONTRACT_VIOLATION,
                pointer="/last_transition",
                expected_contract="initial CREATED transition",
                message="P8-03 can only create the initial PlanningRun state",
            )
        self._validate_schema(PLANNING_RUN_SCHEMA_ID, document)
        transition = cast(Mapping[str, object], transition)
        sequence = transition.get("sequence")
        if not isinstance(sequence, int) or document.get("revision") != sequence + 1:
            _reject(
                CanonicalIngressContractCode.CONTRACT_VIOLATION,
                pointer="/revision",
                expected_contract="last transition sequence + 1",
                message="PlanningRun revision is invalid",
            )
        if document.get("updated_at_utc") != transition.get("occurred_at_utc"):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/updated_at_utc",
                expected_contract="last transition time",
                message="PlanningRun transition time is inconsistent",
            )
        self.validate_effective_scope(
            cast(Mapping[str, object], document["effective_scope"]),
            requested_scope=cast(Mapping[str, object], request["requested_scope"]),
        )
        self.validate_runtime_resolution(
            cast(Mapping[str, object], document["runtime_resolution"])
        )
        if document.get("run_fingerprint") != run_fingerprint(document):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/run_fingerprint",
                expected_contract="PlanningRun fingerprint projection v1",
                message="PlanningRun fingerprint is invalid",
            )
        audit = transition.get("audit")
        if audit not in cast(list[object], document["audit_references"]):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/audit_references",
                expected_contract="contains last transition audit",
                message="PlanningRun transition audit is absent",
            )
        ingress = cast(Mapping[str, object], document["ingress"])
        payload = cast(Mapping[str, object], request["payload"])
        payload_reference = cast(Mapping[str, object], ingress["payload"])
        if (
            ingress.get("request_id") != request.get("request_id")
            or ingress.get("request_fingerprint") != request.get("request_fingerprint")
            or payload_reference.get("artifact_id") != payload.get("package_id")
            or payload_reference.get("fingerprint")
            != request.get("payload_fingerprint")
            or ingress.get("idempotency_key_reference")
            != idempotency_key_reference(cast(str, request["idempotency_key"]))
            or document.get("inputs") != request.get("planning_inputs")
        ):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/ingress",
                expected_contract="exact accepted request lineage",
                message="PlanningRun ingress lineage is inconsistent",
            )

    def validate_result(
        self,
        document: Mapping[str, object],
        *,
        request: Mapping[str, object],
        planning_run: Mapping[str, object] | None = None,
    ) -> None:
        self._validate_schema(RESULT_SCHEMA_ID, document)
        if document.get("result_fingerprint") != result_fingerprint(document):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/result_fingerprint",
                expected_contract="canonical ingress result fingerprint projection v1",
                message="Result fingerprint is invalid",
            )
        if (
            document.get("request_id") != request.get("request_id")
            or document.get("request_fingerprint") != request.get("request_fingerprint")
            or document.get("correlation_id") != request.get("correlation_id")
        ):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/request_id",
                expected_contract="exact request and correlation reference",
                message="Result request lineage is inconsistent",
            )
        idempotency = cast(Mapping[str, object], document["idempotency"])
        if idempotency.get("outcome") != "NOT_RECORDED" and idempotency.get(
            "key_reference"
        ) != idempotency_key_reference(cast(str, request["idempotency_key"])):
            _reject(
                CanonicalIngressContractCode.LINEAGE_INVALID,
                pointer="/idempotency/key_reference",
                expected_contract="hash reference of the request idempotency key",
                message="Result idempotency lineage is inconsistent",
            )
        effective_scope = document.get("effective_scope")
        if isinstance(effective_scope, Mapping):
            self.validate_effective_scope(
                cast(Mapping[str, object], effective_scope),
                requested_scope=cast(Mapping[str, object], request["requested_scope"]),
            )
        accepted = document.get("accepted")
        if isinstance(accepted, Mapping):
            self.validate_runtime_resolution(
                cast(Mapping[str, object], accepted["runtime_resolution"])
            )
            payload_reference = cast(Mapping[str, object], accepted["payload"])
            payload = cast(Mapping[str, object], request["payload"])
            if payload_reference.get("artifact_id") != payload.get(
                "package_id"
            ) or payload_reference.get("fingerprint") != request.get(
                "payload_fingerprint"
            ):
                _reject(
                    CanonicalIngressContractCode.LINEAGE_INVALID,
                    pointer="/accepted/payload",
                    expected_contract="exact accepted payload reference",
                    message="Accepted payload lineage is inconsistent",
                )
        if planning_run is not None and isinstance(accepted, Mapping):
            reference = cast(Mapping[str, object], accepted["planning_run"])
            for field in (
                "planning_run_id",
                "revision",
                "state",
                "run_fingerprint",
            ):
                if reference.get(field) != planning_run.get(field):
                    _reject(
                        CanonicalIngressContractCode.LINEAGE_INVALID,
                        pointer="/accepted/planning_run",
                        expected_contract="exact PlanningRun reference",
                        message="Accepted PlanningRun reference is inconsistent",
                    )
            run_ingress = cast(Mapping[str, object], planning_run["ingress"])
            if (
                accepted.get("ingress_id") != run_ingress.get("ingress_id")
                or accepted.get("payload") != run_ingress.get("payload")
                or accepted.get("runtime_resolution")
                != planning_run.get("runtime_resolution")
                or document.get("effective_scope")
                != planning_run.get("effective_scope")
                or idempotency.get("key_reference")
                != run_ingress.get("idempotency_key_reference")
                or idempotency.get("scope_fingerprint")
                != run_ingress.get("idempotency_scope_fingerprint")
                or accepted.get("audit")
                != cast(Mapping[str, object], planning_run["last_transition"]).get(
                    "audit"
                )
            ):
                _reject(
                    CanonicalIngressContractCode.LINEAGE_INVALID,
                    pointer="/accepted",
                    expected_contract="request-result-PlanningRun lineage",
                    message="Accepted result lineage is inconsistent",
                )


__all__ = [
    "AUDIT_EVENT_SCHEMA_ID",
    "CANONICALIZATION_VERSION",
    "CANONICAL_INGRESS_REQUEST_VERSION",
    "CANONICAL_INGRESS_RESULT_VERSION",
    "CanonicalIngressContract",
    "CanonicalIngressContractCode",
    "CanonicalIngressContractError",
    "FrozenSchemaCatalog",
    "HEADLESS_SCHEMA_SET_VERSION",
    "PLANNING_RUN_VERSION",
    "canonical_fingerprint",
    "canonical_json_bytes",
    "idempotency_key_reference",
    "parse_strict_json",
    "request_fingerprint",
    "result_fingerprint",
    "run_fingerprint",
    "runtime_resolution_fingerprint",
    "scope_fingerprint",
]
