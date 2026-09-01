"""Default-off P6 duration selection at the PlanningProblem ingress boundary.

The adapter first builds the frozen standard ``planning-problem.v2`` and may
then consume strict P6 Prediction carriers for NOT_STARTED resource options.
Only the three existing duration projection fields may differ.  Snapshot
bytes, routing, resource compatibility, hard facts, operation state, demand
weights, Solver behavior, and Validator behavior remain owned elsewhere.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Never, Protocol, cast

from app.domain.types import duration_to_ticks, parse_utc_instant
from app.duration_prediction.runtime import (
    DurationPredictionRequest,
    LoadedRuntimePolicy,
    P6RuntimeError,
    validate_duration_prediction,
)
from app.planning.problem import (
    ImmutablePlanningProblemV2,
    PlanningProblemError,
    build_planning_problem_v2,
    canonical_problem_document_v2,
    canonical_problem_v2_bytes,
    problem_v2_hash_for,
    verify_problem_v2,
)
from app.snapshots import ImmutablePlanningSnapshot, SnapshotError, verify_snapshot


type JsonObject = dict[str, Any]

PLANNING_DURATION_INGRESS_VERSION = "planning-duration-ingress.v1"
MODEL_DURATION_SOURCE = "MODEL_CANDIDATE"


class PlanningDurationIngressErrorCode(StrEnum):
    """Stable fail-closed outcomes before a selected Problem is returned."""

    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    FEATURE_COVERAGE_MISMATCH = "FEATURE_COVERAGE_MISMATCH"
    STANDARD_AUTHORITY_MISMATCH = "STANDARD_AUTHORITY_MISMATCH"
    PREDICTION_CONTRACT_INVALID = "PREDICTION_CONTRACT_INVALID"
    PREDICTION_LINEAGE_MISMATCH = "PREDICTION_LINEAGE_MISMATCH"
    PROBLEM_PROJECTION_INVALID = "PROBLEM_PROJECTION_INVALID"
    AUTHORITY_INVARIANT_VIOLATION = "AUTHORITY_INVARIANT_VIOLATION"


class PlanningDurationIngressError(ValueError):
    """Sanitized integration rejection with no schedule or state side effect."""

    def __init__(
        self, code: PlanningDurationIngressErrorCode, *, field: str, detail: str
    ) -> None:
        self.code = code
        self.field = field
        self.detail = detail
        super().__init__(f"{code.value} at {field}: {detail}")


def _fail(
    code: PlanningDurationIngressErrorCode, *, field: str, detail: str
) -> Never:
    raise PlanningDurationIngressError(code, field=field, detail=detail)


class DurationPredictionProviderPort(Protocol):
    """The narrow, in-process P6-06 surface consumed by this adapter."""

    @property
    def policy(self) -> LoadedRuntimePolicy: ...

    def predict(self, request: DurationPredictionRequest) -> JsonObject: ...


@dataclass(frozen=True, order=True)
class DurationOptionKey:
    """Exact Snapshot identity for one resource-specific duration candidate."""

    operation_id: str
    resource_option_id: str
    resource_id: str


@dataclass(frozen=True)
class PlanningDurationIngressConfig:
    """Explicit configuration; the default carries no provider or feature data."""

    enabled: bool = False
    provider: DurationPredictionProviderPort | None = None
    predicted_at_utc: str | None = None
    feature_records: Mapping[DurationOptionKey, Mapping[str, Any]] = field(
        default_factory=dict
    )

    @classmethod
    def enabled_for_simulation(
        cls,
        *,
        provider: DurationPredictionProviderPort,
        predicted_at_utc: str,
        feature_records: Mapping[DurationOptionKey, Mapping[str, Any]],
    ) -> PlanningDurationIngressConfig:
        return cls(
            enabled=True,
            provider=provider,
            predicted_at_utc=predicted_at_utc,
            feature_records=feature_records,
        )


class PlanningDurationDecision(StrEnum):
    DEFAULT_OFF_STANDARD = "DEFAULT_OFF_STANDARD"
    RUNNING_REMAINDER_AUTHORITY = "RUNNING_REMAINDER_AUTHORITY"
    STANDARD_FALLBACK = "STANDARD_FALLBACK"
    MODEL_CANDIDATE = "MODEL_CANDIDATE"


@dataclass(frozen=True)
class PlanningDurationLineage:
    """Immutable standard/selection/carrier lineage for one Problem option."""

    key: DurationOptionKey
    operation_status: str
    decision: PlanningDurationDecision
    standard_duration_seconds: int
    standard_duration_source: str
    standard_source_version: str
    standard_source_record_id: str
    standard_source_record_fingerprint: str
    selected_duration_seconds: int
    selected_duration_source: str
    selected_source_version: str
    fallback_reason: str | None
    prediction_id: str | None
    prediction_fingerprint: str | None
    model_version: str | None
    feature_schema_version: str | None
    prediction_policy_fingerprint: str | None
    prediction_canonical_bytes: bytes | None
    standard_problem_hash: str = ""
    selected_problem_hash: str = ""

    @property
    def prediction_document(self) -> JsonObject | None:
        if self.prediction_canonical_bytes is None:
            return None
        return cast(JsonObject, json.loads(self.prediction_canonical_bytes))

    def as_document(self) -> JsonObject:
        """Return lineage references without embedding the FeatureRecord carrier."""

        return {
            "operation_id": self.key.operation_id,
            "resource_option_id": self.key.resource_option_id,
            "resource_id": self.key.resource_id,
            "operation_status": self.operation_status,
            "decision": self.decision.value,
            "standard_duration": {
                "seconds": self.standard_duration_seconds,
                "duration_source": self.standard_duration_source,
                "source_version": self.standard_source_version,
                "source_record_id": self.standard_source_record_id,
                "source_record_fingerprint": (
                    self.standard_source_record_fingerprint
                ),
            },
            "selected_duration": {
                "seconds": self.selected_duration_seconds,
                "duration_source": self.selected_duration_source,
                "source_version": self.selected_source_version,
            },
            "fallback_reason": self.fallback_reason,
            "prediction_id": self.prediction_id,
            "prediction_fingerprint": self.prediction_fingerprint,
            "model_version": self.model_version,
            "feature_schema_version": self.feature_schema_version,
            "prediction_policy_fingerprint": self.prediction_policy_fingerprint,
            "standard_problem_hash": self.standard_problem_hash,
            "selected_problem_hash": self.selected_problem_hash,
        }


@dataclass(frozen=True)
class PlanningAuthorityInvariants:
    """Independent comparison of every authority that P6 may not change."""

    problem_identity: bool
    routing: bool
    resource_compatibility: bool
    hard_constraints: bool
    operation_state: bool
    business_weights: bool
    duration_fields_only: bool

    @property
    def all_passed(self) -> bool:
        return all(self.as_document().values())

    def as_document(self) -> dict[str, bool]:
        return {
            "problem_identity": self.problem_identity,
            "routing": self.routing,
            "resource_compatibility": self.resource_compatibility,
            "hard_constraints": self.hard_constraints,
            "operation_state": self.operation_state,
            "business_weights": self.business_weights,
            "duration_fields_only": self.duration_fields_only,
        }


@dataclass(frozen=True)
class PlanningDurationIngressResult:
    """The selected immutable Problem plus its independent standard replay."""

    standard_problem: ImmutablePlanningProblemV2
    problem: ImmutablePlanningProblemV2
    ingress_enabled: bool
    lineage: tuple[PlanningDurationLineage, ...]
    invariants: PlanningAuthorityInvariants

    def lineage_documents(self) -> list[JsonObject]:
        return [item.as_document() for item in self.lineage]


@dataclass(frozen=True)
class _StandardOption:
    key: DurationOptionKey
    operation_status: str
    seconds: int
    setup_seconds: int
    cycle_seconds_per_unit: int
    duration_source: str
    source_version: str
    source_record_id: str
    source_record_fingerprint: str

    def authority(self) -> JsonObject:
        return {
            "seconds": self.seconds,
            "duration_source": self.duration_source,
            "source_version": self.source_version,
            "source_record_id": self.source_record_id,
            "source_record_fingerprint": self.source_record_fingerprint,
        }


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _fingerprint(value: object) -> str:
    return f"sha256:{sha256(_canonical_json_bytes(value)).hexdigest()}"


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(
            PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
            field=field_name,
            detail="expected a non-empty authority identifier",
        )
    return value


def _require_positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail(
            PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
            field=field_name,
            detail="expected positive integer seconds",
        )
    return value


def _standard_options(
    snapshot: ImmutablePlanningSnapshot,
) -> dict[DurationOptionKey, _StandardOption]:
    try:
        verify_snapshot(snapshot)
    except SnapshotError as error:
        _fail(
            PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
            field="snapshot",
            detail=error.code.value,
        )
    document = snapshot.document
    canonical_options = {
        str(option["routing_resource_option_id"]): cast(Mapping[str, Any], option)
        for option in document["records"]["routing_resource_options"]
    }
    result: dict[DurationOptionKey, _StandardOption] = {}
    for raw_instance in document["operation_instances"]:
        instance = cast(Mapping[str, Any], raw_instance)
        status = str(instance["status"])
        if status == "COMPLETED":
            continue
        operation_id = str(instance["operation_instance_id"])
        routing_operation_id = str(instance["routing_operation_id"])
        for raw_option in cast(
            list[Mapping[str, Any]], instance["resource_options"]
        ):
            option_id = str(raw_option["routing_resource_option_id"])
            resource_id = str(raw_option["resource_id"])
            canonical = canonical_options.get(option_id)
            if canonical is None:
                _fail(
                    PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
                    field=f"operation_instances.{operation_id}.resource_options",
                    detail="canonical routing option is missing",
                )
            expected = {
                "routing_operation_id": routing_operation_id,
                "resource_id": resource_id,
                "setup_seconds": raw_option["setup_seconds"],
                "cycle_seconds_per_unit": raw_option["cycle_seconds_per_unit"],
                "final_duration_seconds": raw_option["final_duration_seconds"],
                "duration_source": raw_option["duration_source"],
                "duration_source_version": raw_option["source_version"],
            }
            if any(canonical.get(name) != value for name, value in expected.items()):
                _fail(
                    PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
                    field=f"records.routing_resource_options.{option_id}",
                    detail="Snapshot instance and canonical option authority differ",
                )
            source = canonical.get("source")
            if not isinstance(source, dict):
                _fail(
                    PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
                    field=f"records.routing_resource_options.{option_id}.source",
                    detail="canonical source reference is missing",
                )
            key = DurationOptionKey(operation_id, option_id, resource_id)
            if key in result:
                _fail(
                    PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
                    field="operation_instances.resource_options",
                    detail="duplicate operation/resource-option/resource identity",
                )
            result[key] = _StandardOption(
                key=key,
                operation_status=status,
                seconds=_require_positive_int(
                    raw_option["final_duration_seconds"],
                    f"resource_options.{option_id}.final_duration_seconds",
                ),
                setup_seconds=cast(int, raw_option["setup_seconds"]),
                cycle_seconds_per_unit=cast(
                    int, raw_option["cycle_seconds_per_unit"]
                ),
                duration_source=_require_text(
                    raw_option["duration_source"],
                    f"resource_options.{option_id}.duration_source",
                ),
                source_version=_require_text(
                    raw_option["source_version"],
                    f"resource_options.{option_id}.source_version",
                ),
                source_record_id=_require_text(
                    source.get("source_record_id"),
                    f"records.routing_resource_options.{option_id}.source_record_id",
                ),
                source_record_fingerprint=_fingerprint(canonical),
            )
    return result


def standard_duration_authority_for_snapshot_option(
    snapshot: ImmutablePlanningSnapshot, key: DurationOptionKey
) -> JsonObject:
    """Derive caller-owned authority from verified immutable Snapshot facts."""

    option = _standard_options(snapshot).get(key)
    if option is None:
        _fail(
            PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
            field="duration_option_key",
            detail="option is not an active Snapshot resource option",
        )
    return deepcopy(option.authority())


def _operation_by_id(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(operation["operation_id"]): operation
        for operation in cast(
            list[Mapping[str, Any]], document["operation_instances"]
        )
    }


def _routing_projection(
    document: Mapping[str, Any],
) -> list[tuple[str, str, tuple[str, ...], tuple[str, ...]]]:
    return sorted(
        (
            str(operation["operation_id"]),
            str(operation["demand_order_id"]),
            tuple(sorted(cast(list[str], operation["required_capabilities"]))),
            tuple(
                sorted(
                    str(option["resource_id"])
                    for option in cast(
                        list[Mapping[str, Any]], operation["resource_options"]
                    )
                )
            ),
        )
        for operation in cast(
            list[Mapping[str, Any]], document["operation_instances"]
        )
    )


def _resource_projection(document: Mapping[str, Any]) -> JsonObject:
    options: list[tuple[str, str, int, int]] = []
    for operation in cast(
        list[Mapping[str, Any]], document["operation_instances"]
    ):
        for option in cast(
            list[Mapping[str, Any]], operation["resource_options"]
        ):
            options.append(
                (
                    str(operation["operation_id"]),
                    str(option["resource_id"]),
                    cast(int, option["setup_seconds"]),
                    cast(int, option["cycle_seconds_per_unit"]),
                )
            )
    return {
        "resources": deepcopy(document["resources"]),
        "operation_resource_options": sorted(options),
    }


def _hard_constraint_projection(document: Mapping[str, Any]) -> JsonObject:
    operations: list[JsonObject] = []
    for operation in cast(
        list[Mapping[str, Any]], document["operation_instances"]
    ):
        value: JsonObject = {
            "operation_id": operation["operation_id"],
            "release_at_utc": operation["release_at_utc"],
            "material_ready_at_utc": operation["material_ready_at_utc"],
        }
        for name in (
            "actual_start_at_utc",
            "assigned_resource_id",
            "remaining_seconds",
        ):
            if name in operation:
                value[name] = operation[name]
        operations.append(value)
    operations.sort(key=lambda value: str(value["operation_id"]))
    return {
        "tick_seconds": document["tick_seconds"],
        "horizon_start_utc": document["horizon_start_utc"],
        "horizon_end_utc": document["horizon_end_utc"],
        "operations": operations,
        "historical_completion_anchors": deepcopy(
            document["historical_completion_anchors"]
        ),
        "precedence_edges": deepcopy(document["precedence_edges"]),
        "operation_locks": deepcopy(document["operation_locks"]),
        "resource_unavailable_intervals": deepcopy(
            document["resource_unavailable_intervals"]
        ),
        "required_capabilities": deepcopy(document["required_capabilities"]),
    }


def _without_duration_fields(document: Mapping[str, Any]) -> JsonObject:
    projection = deepcopy(dict(document))
    projection.pop("problem_hash", None)
    for operation in cast(
        list[JsonObject], projection["operation_instances"]
    ):
        for option in cast(list[JsonObject], operation["resource_options"]):
            option.pop("final_duration_seconds", None)
            option.pop("duration_source", None)
            option.pop("source_version", None)
    return projection


def evaluate_planning_authority_invariants(
    standard_problem: Mapping[str, Any], selected_problem: Mapping[str, Any]
) -> PlanningAuthorityInvariants:
    """Compare standard/selected Problems without trusting the P6 adapter."""

    identity_fields = (
        "problem_version",
        "schema_set_version",
        "snapshot_id",
        "problem_builder_version",
        "canonicalization_version",
        "problem_hash_projection_version",
    )
    standard_operations = _operation_by_id(standard_problem)
    selected_operations = _operation_by_id(selected_problem)
    return PlanningAuthorityInvariants(
        problem_identity=all(
            standard_problem.get(name) == selected_problem.get(name)
            for name in identity_fields
        ),
        routing=(
            _routing_projection(standard_problem)
            == _routing_projection(selected_problem)
        ),
        resource_compatibility=(
            _resource_projection(standard_problem)
            == _resource_projection(selected_problem)
        ),
        hard_constraints=(
            _hard_constraint_projection(standard_problem)
            == _hard_constraint_projection(selected_problem)
        ),
        operation_state=(
            {
                operation_id: operation["status"]
                for operation_id, operation in standard_operations.items()
            }
            == {
                operation_id: operation["status"]
                for operation_id, operation in selected_operations.items()
            }
        ),
        business_weights=(
            standard_problem.get("delivery_demands")
            == selected_problem.get("delivery_demands")
        ),
        duration_fields_only=(
            _without_duration_fields(standard_problem)
            == _without_duration_fields(selected_problem)
        ),
    )


def _validate_config(
    config: PlanningDurationIngressConfig,
) -> dict[DurationOptionKey, JsonObject]:
    if type(config.enabled) is not bool:
        _fail(
            PlanningDurationIngressErrorCode.INVALID_CONFIGURATION,
            field="enabled",
            detail="enabled must be an explicit boolean",
        )
    features: dict[DurationOptionKey, JsonObject] = {}
    for key, value in config.feature_records.items():
        if not isinstance(key, DurationOptionKey) or not isinstance(value, Mapping):
            _fail(
                PlanningDurationIngressErrorCode.INVALID_CONFIGURATION,
                field="feature_records",
                detail="feature mapping must use exact DurationOptionKey objects",
            )
        features[key] = deepcopy(dict(value))
    if not config.enabled:
        if (
            config.provider is not None
            or config.predicted_at_utc is not None
            or features
        ):
            _fail(
                PlanningDurationIngressErrorCode.INVALID_CONFIGURATION,
                field="duration_ingress",
                detail="disabled ingress cannot silently ignore provider inputs",
            )
        return features
    if config.provider is None:
        _fail(
            PlanningDurationIngressErrorCode.INVALID_CONFIGURATION,
            field="provider",
            detail="enabled ingress requires the P6-06 provider",
        )
    if not isinstance(config.predicted_at_utc, str) or not config.predicted_at_utc:
        _fail(
            PlanningDurationIngressErrorCode.INVALID_CONFIGURATION,
            field="predicted_at_utc",
            detail="enabled ingress requires an explicit UTC decision time",
        )
    return features


def _carrier_for(
    *,
    provider: DurationPredictionProviderPort,
    predicted_at_utc: str,
    as_of_cutoff_utc: str,
    factory_id: str,
    option: _StandardOption,
    feature_record: Mapping[str, Any],
) -> JsonObject:
    request = DurationPredictionRequest(
        factory_id=factory_id,
        operation_id=option.key.operation_id,
        resource_option_id=option.key.resource_option_id,
        resource_id=option.key.resource_id,
        predicted_at_utc=predicted_at_utc,
        as_of_cutoff_utc=as_of_cutoff_utc,
        standard_duration=option.authority(),
        feature_record=deepcopy(dict(feature_record)),
    )
    try:
        carrier = provider.predict(request)
        validate_duration_prediction(carrier, provider.policy)
    except (P6RuntimeError, AttributeError, KeyError, TypeError, ValueError) as error:
        _fail(
            PlanningDurationIngressErrorCode.PREDICTION_CONTRACT_INVALID,
            field=f"prediction.{option.key.operation_id}.{option.key.resource_id}",
            detail=type(error).__name__,
        )
    expected_identity = {
        "factory_id": factory_id,
        "operation_id": option.key.operation_id,
        "resource_option_id": option.key.resource_option_id,
        "resource_id": option.key.resource_id,
        "as_of_cutoff_utc": as_of_cutoff_utc,
        "standard_duration": option.authority(),
    }
    if any(carrier.get(name) != value for name, value in expected_identity.items()):
        _fail(
            PlanningDurationIngressErrorCode.PREDICTION_LINEAGE_MISMATCH,
            field=f"prediction.{option.key.operation_id}.{option.key.resource_id}",
            detail="carrier identity or standard authority differs from Snapshot",
        )
    return deepcopy(carrier)


def _lineage_from_carrier(
    option: _StandardOption, carrier: Mapping[str, Any]
) -> PlanningDurationLineage:
    reason = str(carrier["fallback_reason"])
    if reason == "NONE":
        decision = PlanningDurationDecision.MODEL_CANDIDATE
        selected_seconds = cast(int, carrier["selected_duration_seconds"])
        selected_source = MODEL_DURATION_SOURCE
        selected_version = str(carrier["model_version"])
    else:
        decision = PlanningDurationDecision.STANDARD_FALLBACK
        selected_seconds = option.seconds
        selected_source = option.duration_source
        selected_version = option.source_version
    if selected_seconds <= 0:
        _fail(
            PlanningDurationIngressErrorCode.PREDICTION_LINEAGE_MISMATCH,
            field="selected_duration_seconds",
            detail="selected duration must remain positive",
        )
    policy_reference = cast(Mapping[str, Any], carrier["prediction_policy_reference"])
    return PlanningDurationLineage(
        key=option.key,
        operation_status=option.operation_status,
        decision=decision,
        standard_duration_seconds=option.seconds,
        standard_duration_source=option.duration_source,
        standard_source_version=option.source_version,
        standard_source_record_id=option.source_record_id,
        standard_source_record_fingerprint=option.source_record_fingerprint,
        selected_duration_seconds=selected_seconds,
        selected_duration_source=selected_source,
        selected_source_version=selected_version,
        fallback_reason=reason,
        prediction_id=str(carrier["prediction_id"]),
        prediction_fingerprint=str(carrier["prediction_fingerprint"]),
        model_version=str(carrier["model_version"]),
        feature_schema_version=str(carrier["feature_schema_version"]),
        prediction_policy_fingerprint=str(policy_reference["fingerprint"]),
        prediction_canonical_bytes=_canonical_json_bytes(carrier),
    )


def _standard_lineage(
    option: _StandardOption, decision: PlanningDurationDecision
) -> PlanningDurationLineage:
    return PlanningDurationLineage(
        key=option.key,
        operation_status=option.operation_status,
        decision=decision,
        standard_duration_seconds=option.seconds,
        standard_duration_source=option.duration_source,
        standard_source_version=option.source_version,
        standard_source_record_id=option.source_record_id,
        standard_source_record_fingerprint=option.source_record_fingerprint,
        selected_duration_seconds=option.seconds,
        selected_duration_source=option.duration_source,
        selected_source_version=option.source_version,
        fallback_reason=None,
        prediction_id=None,
        prediction_fingerprint=None,
        model_version=None,
        feature_schema_version=None,
        prediction_policy_fingerprint=None,
        prediction_canonical_bytes=None,
    )


def _validate_selected_horizon(document: Mapping[str, Any]) -> None:
    horizon_start = parse_utc_instant(str(document["horizon_start_utc"]))
    horizon_end = parse_utc_instant(str(document["horizon_end_utc"]))
    tick_seconds = cast(int, document["tick_seconds"])
    for operation in cast(
        list[Mapping[str, Any]], document["operation_instances"]
    ):
        if operation["status"] != "NOT_STARTED":
            continue
        earliest = max(
            horizon_start,
            parse_utc_instant(str(operation["release_at_utc"])),
            parse_utc_instant(str(operation["material_ready_at_utc"])),
        )
        available_seconds = int((horizon_end - earliest).total_seconds())
        option_ticks = [
            duration_to_ticks(cast(int, option["final_duration_seconds"]), tick_seconds)
            for option in cast(
                list[Mapping[str, Any]], operation["resource_options"]
            )
        ]
        if (
            available_seconds <= 0
            or not option_ticks
            or min(option_ticks) * tick_seconds > available_seconds
        ):
            _fail(
                PlanningDurationIngressErrorCode.PROBLEM_PROJECTION_INVALID,
                field=f"operation_instances.{operation['operation_id']}",
                detail="selected durations do not fit the existing horizon",
            )


def _materialize_selected_problem(
    standard_problem: ImmutablePlanningProblemV2,
    lineage: tuple[PlanningDurationLineage, ...],
) -> ImmutablePlanningProblemV2:
    accepted = {
        (item.key.operation_id, item.key.resource_id): item
        for item in lineage
        if item.decision is PlanningDurationDecision.MODEL_CANDIDATE
    }
    if not accepted:
        return standard_problem
    document = cast(JsonObject, standard_problem.document)
    consumed: set[tuple[str, str]] = set()
    for operation in cast(
        list[JsonObject], document["operation_instances"]
    ):
        operation_id = str(operation["operation_id"])
        for option in cast(list[JsonObject], operation["resource_options"]):
            key = (operation_id, str(option["resource_id"]))
            selection = accepted.get(key)
            if selection is None:
                continue
            option["final_duration_seconds"] = selection.selected_duration_seconds
            option["duration_source"] = selection.selected_duration_source
            option["source_version"] = selection.selected_source_version
            consumed.add(key)
    if consumed != set(accepted):
        _fail(
            PlanningDurationIngressErrorCode.PROBLEM_PROJECTION_INVALID,
            field="operation_instances.resource_options",
            detail="accepted carrier does not map to one standard Problem option",
        )
    _validate_selected_horizon(document)
    try:
        canonical = cast(
            JsonObject,
            canonical_problem_document_v2(cast(Mapping[str, object], document)),
        )
        canonical["problem_hash"] = problem_v2_hash_for(canonical)
        problem = ImmutablePlanningProblemV2(
            canonical_bytes=canonical_problem_v2_bytes(canonical),
            problem_hash=str(canonical["problem_hash"]),
            snapshot_id=str(canonical["snapshot_id"]),
            problem_builder_version=str(canonical["problem_builder_version"]),
        )
        verify_problem_v2(problem)
    except (PlanningProblemError, KeyError, TypeError, ValueError) as error:
        _fail(
            PlanningDurationIngressErrorCode.PROBLEM_PROJECTION_INVALID,
            field="planning_problem",
            detail=type(error).__name__,
        )
    return problem


def build_planning_problem_with_duration_predictions(
    snapshot: ImmutablePlanningSnapshot,
    *,
    priority_facts: Mapping[str, Mapping[str, object]],
    problem_builder_version: str,
    tick_seconds: int,
    horizon_start_utc: str,
    horizon_end_utc: str,
    duration_ingress: PlanningDurationIngressConfig | None = None,
) -> PlanningDurationIngressResult:
    """Build standard Problem first, then optionally consume exact P6 carriers."""

    config = duration_ingress or PlanningDurationIngressConfig()
    features = _validate_config(config)
    standard_problem = build_planning_problem_v2(
        snapshot,
        priority_facts=priority_facts,
        problem_builder_version=problem_builder_version,
        tick_seconds=tick_seconds,
        horizon_start_utc=horizon_start_utc,
        horizon_end_utc=horizon_end_utc,
    )
    options = _standard_options(snapshot)
    required_feature_keys = {
        key for key, option in options.items() if option.operation_status == "NOT_STARTED"
    }
    if config.enabled and set(features) != required_feature_keys:
        _fail(
            PlanningDurationIngressErrorCode.FEATURE_COVERAGE_MISMATCH,
            field="feature_records",
            detail=(
                f"expected={len(required_feature_keys)} observed={len(features)}"
            ),
        )
    snapshot_document = snapshot.document
    factories = snapshot_document["records"]["factories"]
    if len(factories) != 1:
        _fail(
            PlanningDurationIngressErrorCode.STANDARD_AUTHORITY_MISMATCH,
            field="records.factories",
            detail="P6 ingress requires the same single-factory v2 boundary",
        )
    factory_id = str(factories[0]["factory_id"])
    lineage_items: list[PlanningDurationLineage] = []
    for key in sorted(options):
        option = options[key]
        if option.operation_status == "RUNNING":
            lineage_items.append(
                _standard_lineage(
                    option, PlanningDurationDecision.RUNNING_REMAINDER_AUTHORITY
                )
            )
        elif not config.enabled:
            lineage_items.append(
                _standard_lineage(
                    option, PlanningDurationDecision.DEFAULT_OFF_STANDARD
                )
            )
        else:
            assert config.provider is not None
            assert config.predicted_at_utc is not None
            carrier = _carrier_for(
                provider=config.provider,
                predicted_at_utc=config.predicted_at_utc,
                as_of_cutoff_utc=snapshot_document["cutoff_at_utc"],
                factory_id=factory_id,
                option=option,
                feature_record=features[key],
            )
            lineage_items.append(_lineage_from_carrier(option, carrier))
    lineage = tuple(lineage_items)
    selected_problem = _materialize_selected_problem(standard_problem, lineage)
    invariants = evaluate_planning_authority_invariants(
        cast(Mapping[str, Any], standard_problem.document),
        cast(Mapping[str, Any], selected_problem.document),
    )
    if not invariants.all_passed:
        failed = sorted(
            name for name, passed in invariants.as_document().items() if not passed
        )
        _fail(
            PlanningDurationIngressErrorCode.AUTHORITY_INVARIANT_VIOLATION,
            field="planning_problem",
            detail=",".join(failed),
        )
    finalized = tuple(
        replace(
            item,
            standard_problem_hash=standard_problem.problem_hash,
            selected_problem_hash=selected_problem.problem_hash,
        )
        for item in lineage
    )
    return PlanningDurationIngressResult(
        standard_problem=standard_problem,
        problem=selected_problem,
        ingress_enabled=config.enabled,
        lineage=finalized,
        invariants=invariants,
    )


__all__ = [
    "MODEL_DURATION_SOURCE",
    "PLANNING_DURATION_INGRESS_VERSION",
    "DurationOptionKey",
    "DurationPredictionProviderPort",
    "PlanningAuthorityInvariants",
    "PlanningDurationDecision",
    "PlanningDurationIngressConfig",
    "PlanningDurationIngressError",
    "PlanningDurationIngressErrorCode",
    "PlanningDurationIngressResult",
    "PlanningDurationLineage",
    "build_planning_problem_with_duration_predictions",
    "evaluate_planning_authority_invariants",
    "standard_duration_authority_for_snapshot_option",
]
