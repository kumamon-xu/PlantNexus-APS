"""Runtime event ports backed by explicitly configured Simulation authorities.

HTTP receipt never projects facts. A trusted Runtime caller explicitly projects
one configured stream using an expected immutable Snapshot, independently of
transport retries. Replanning attempts remain a separate application owner.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
import json
from typing import Any

from app.application.execution_fact_projection import ExecutionFactProjectionService
from app.domain.execution_fact_projection import (
    ExecutionFactProjectionError,
    ProjectionScope,
    validate_execution_event,
)
from app.data_validation.canonical_ingress import canonical_fingerprint
from app.importers.urgent_demand import UrgentDemandImport
from app.snapshots import ImmutablePlanningSnapshot, SnapshotDataPlane, verify_snapshot


class RuntimeEventError(RuntimeError):
    def __init__(self, reason: str, field: str) -> None:
        self.reason, self.field = reason, field
        super().__init__(f"{reason}: {field}")


class RuntimeExecutionFactProjectionService(ExecutionFactProjectionService):
    """Adapt canonical urgent sources without changing the frozen P4 owner.

    Only source resolution differs. The inherited transaction still performs
    all fact/domain validation, immutable writes and checkpoint CAS.
    """

    def __init__(
        self,
        *,
        urgent_resolver: Callable[[str, str], ImmutablePlanningSnapshot],
        **ports: Any,
    ) -> None:
        super().__init__(**ports)
        self._urgent_resolver = urgent_resolver

    def _urgent_snapshots(
        self,
        full_prefix: tuple[dict[str, object], ...],
        *,
        after_position: int,
        base_snapshot: ImmutablePlanningSnapshot,
        urgent_imports: Mapping[str, UrgentDemandImport],
    ) -> dict[str, Mapping[str, object]]:
        if urgent_imports:
            raise RuntimeEventError("INVALID_INPUT", "urgent_imports")
        result: dict[str, Mapping[str, object]] = {}
        cutoff = str(base_snapshot.document["cutoff_at_utc"])
        for event in full_prefix[after_position:]:
            cutoff = max(cutoff, str(event["occurred_at_utc"]))
            if event["event_type"] != "URGENT_DEMAND_RECEIVED":
                continue
            event_id = str(event["event_id"])
            snapshot = self._urgent_resolver(event_id, cutoff)
            verify_snapshot(snapshot)
            if snapshot.data_plane is not SnapshotDataPlane.SIMULATION:
                raise RuntimeEventError(
                    "AUTHORIZATION_DENIED", "urgent_import.data_plane"
                )
            result[event_id] = snapshot.document
        return result


def event_bindings(document: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    """Validate deployment configuration, never a caller-supplied authority."""
    if document is None:
        return ()
    if (
        set(document) != {"version", "bindings"}
        or document["version"] != "runtime-event-bindings.v1"
    ):
        raise ValueError("invalid event configuration")
    entries = document["bindings"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("explicit bindings required")
    fields = {
        "tenant_id",
        "factory_id",
        "planning_scope_id",
        "authority_id",
        "stream_id",
        "stream_version",
        "base_planning_run_id",
        "actor_refs",
        "event_types",
        "authority_source",
        "urgent_import_runs",
    }
    scopes, streams = set(), set()
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError("invalid event binding fields")
        for name in fields - {
            "actor_refs",
            "event_types",
            "authority_source",
            "urgent_import_runs",
        }:
            if (
                not isinstance(entry[name], str)
                or not entry[name]
                or any(c.isspace() for c in entry[name])
            ):
                raise ValueError("invalid event binding identity")
        for name in ("actor_refs", "event_types"):
            if (
                not isinstance(entry[name], list)
                or not entry[name]
                or any(not isinstance(v, str) or not v or v == "*" for v in entry[name])
            ):
                raise ValueError("explicit actor and type lists required")
        known = {
            "OPERATION_STARTED",
            "OPERATION_COMPLETED",
            "MACHINE_UNAVAILABLE",
            "MACHINE_RECOVERED",
            "MATERIAL_READY",
            "MATERIAL_DELAYED",
            "PROCESSING_DURATION_CHANGED",
            "PROCESSING_REMAINING_CHANGED",
            "URGENT_DEMAND_RECEIVED",
            "LOCK_CREATED",
            "LOCK_RELEASED",
        }
        if not set(entry["event_types"]) <= known:
            raise ValueError("unsupported event type")
        source = entry["authority_source"]
        if (
            not isinstance(source, dict)
            or set(source) != {"source_system", "source_version", "source_record_id"}
            or any(not isinstance(v, str) or not v for v in source.values())
        ):
            raise ValueError("invalid authority source")
        urgent = entry["urgent_import_runs"]
        if not isinstance(urgent, dict) or any(
            not isinstance(k, str)
            or not k.startswith("execution-event-")
            or not isinstance(v, str)
            or not v
            for k, v in urgent.items()
        ):
            raise ValueError("invalid urgent import binding")
        scope = entry["planning_scope_id"]
        stream = tuple(
            entry[n] for n in ("authority_id", "stream_id", "stream_version")
        )
        if scope in scopes or stream in streams:
            raise ValueError("ambiguous scope or stream")
        scopes.add(scope)
        streams.add(stream)
        result.append(json.loads(json.dumps(entry)))
    return tuple(result)


class RuntimeDynamicReplanningApplication:
    def __init__(
        self,
        *,
        bindings: tuple[dict[str, Any], ...],
        environment: str,
        events: Any,
        checkpoints: Any,
        snapshots: Any,
        source: Callable[[dict[str, Any], str], Any],
        service: Callable[[dict[str, Any], str | None], ExecutionFactProjectionService],
    ) -> None:
        self._bindings = {v["planning_scope_id"]: v for v in bindings}
        self._environment = environment
        self._events, self._checkpoints, self._snapshots = (
            events,
            checkpoints,
            snapshots,
        )
        self._source, self._service = source, service
        self.replan: Any = None

    def _binding(self, context: Any, scope_id: str, capability: str) -> dict[str, Any]:
        if (
            not context.authenticated
            or context.production_binding
            or context.data_plane != "SIMULATION"
            or context.environment != self._environment
            or capability not in context.resolved_capabilities
            or not ({scope_id, "*"} & context.planning_scope_scope)
        ):
            raise RuntimeEventError("AUTHORIZATION_DENIED", "scope")
        binding = self._bindings.get(scope_id)
        if binding is None:
            raise RuntimeEventError("SERVICE_UNAVAILABLE", "event_authority")
        if context.actor_ref not in binding["actor_refs"]:
            raise RuntimeEventError("AUTHORIZATION_DENIED", "event_authority.actor")
        self._source(binding, binding["base_planning_run_id"])
        return binding

    def _validate(self, document: Mapping[str, Any], binding: dict[str, Any]) -> None:
        validate_execution_event(
            document,
            scope=ProjectionScope(
                **{
                    k: binding[k]
                    for k in (
                        "factory_id",
                        "planning_scope_id",
                        "authority_id",
                        "stream_id",
                        "stream_version",
                    )
                }
            ),
        )
        if (
            document["environment"] != self._environment
            or document["event_type"] not in binding["event_types"]
            or document["authority"]["source"] != binding["authority_source"]
        ):
            raise RuntimeEventError("AUTHORIZATION_DENIED", "event_authority")

    def execute(self, request: Any) -> Mapping[str, object]:
        try:
            return self._execute(request)
        except ExecutionFactProjectionError as error:
            reason = str(error.reason)
            cause_reason = str(getattr(error.__cause__, "reason", ""))
            if cause_reason == "IDEMPOTENCY_CONFLICT":
                reason = cause_reason
            else:
                reason = {
                    "INVALID_EVENT": "INVALID_INPUT",
                    "AUTHORITY_MISMATCH": "AUTHORIZATION_DENIED",
                    "ORDERING_VIOLATION": "POSITION_CONFLICT",
                    "FACT_CONFLICT": "STATE_CONFLICT",
                    "TERMINAL_REGRESSION": "IMMUTABLE_EXECUTION_FACT",
                    "URGENT_IMPORT_REQUIRED": "INVALID_REFERENCE",
                    "URGENT_IMPORT_MISMATCH": "MIXED_LINEAGE",
                    "STALE_SNAPSHOT": "STALE_SOURCE",
                }.get(reason, reason)
            raise RuntimeEventError(reason, error.field) from error

    def _execute(self, request: Any) -> Mapping[str, object]:
        operation = str(request.operation)
        if operation not in {
            "APPEND_EXECUTION_EVENT",
            "GET_EXECUTION_EVENT",
            "LIST_EXECUTION_EVENTS",
        }:
            if self.replan is not None:
                return self.replan.execute(request)
            raise RuntimeEventError("SERVICE_UNAVAILABLE", "operation")
        append = operation == "APPEND_EXECUTION_EVENT"
        binding = self._binding(
            request.context,
            request.planning_scope_id,
            "event_ingest" if append else "event_view",
        )
        replayed = False
        if append:
            document = request.document
            if (
                not isinstance(document, Mapping)
                or request.resource_id != document.get("event_id")
                or request.context.correlation_id != document.get("correlation_id")
            ):
                raise RuntimeEventError("INVALID_INPUT", "event")
            self._validate(document, binding)
            key = request.context.idempotency_key_reference
            if (
                not isinstance(key, str)
                or len(key) != 71
                or not key.startswith("sha256:")
            ):
                raise RuntimeEventError("INVALID_REQUEST", "idempotency_key_reference")
            outcome = self._service(binding, key).ingest_event(document)
            replayed = outcome.replayed
            result = {
                **asdict(outcome),
                "execution_event": self._events.get(outcome.event_id),
            }
        elif operation == "GET_EXECUTION_EVENT":
            document = self._events.get(request.resource_id)
            if document is None:
                raise RuntimeEventError("NOT_FOUND", "event_id")
            self._validate(document, binding)
            result = {"execution_event": document}
        else:
            query = request.query
            if not isinstance(query, Mapping) or any(
                query.get(k) != binding[k]
                for k in ("authority_id", "stream_id", "stream_version")
            ):
                raise RuntimeEventError("AUTHORIZATION_DENIED", "stream")
            rows = self._events.list_stream(
                **{
                    k: binding[k]
                    for k in ("authority_id", "stream_id", "stream_version")
                },
                after_position=query["from_position"] - 1,
            )
            selected = [
                v for v in rows if v["source_position"] <= query["through_position"]
            ]
            for document in selected:
                self._validate(document, binding)
            if any(
                b["source_position"] != a["source_position"] + 1
                for a, b in zip(selected, selected[1:])
            ):
                raise RuntimeEventError("STREAM_GAP", "source_position")
            size = query["page"]["size"]
            basis = {
                k: v
                for k, v in query.items()
                if k not in {"page", "correlation_id", "query_fingerprint"}
            }
            digest = canonical_fingerprint(
                {"query": basis, "page_size": size, "events": selected}
            )
            offset = 0
            cursor = query["page"]["cursor"]
            if cursor is not None:
                try:
                    number, observed = cursor.split(":", 1)
                    offset = int(number)
                    if (
                        number != str(offset)
                        or offset < 1
                        or offset >= len(selected)
                        or observed != digest
                    ):
                        raise ValueError
                except (AttributeError, ValueError):
                    raise RuntimeEventError("STALE_CURSOR", "page.cursor") from None
            page = selected[offset : offset + size]
            result = {
                "result_version": "execution-event-timeline.v1",
                "query_fingerprint": query["query_fingerprint"],
                "data_plane": "SIMULATION",
                "environment": self._environment,
                "synthetic": True,
                "production_binding": False,
                **{
                    k: query[k]
                    for k in (
                        "planning_scope_id",
                        "authority_id",
                        "stream_id",
                        "stream_version",
                        "from_position",
                        "through_position",
                    )
                },
                "events": page,
                "next_cursor": f"{offset + size}:{digest}"
                if offset + size < len(selected)
                else None,
                "allowed_actions": ["view"],
            }
            result["projection_fingerprint"] = canonical_fingerprint(result)
        return {
            "response_version": "dynamic-replanning-response.v1",
            "operation": operation,
            "resource_type": "EXECUTION_EVENT_STREAM"
            if operation == "LIST_EXECUTION_EVENTS"
            else "EXECUTION_EVENT",
            "resource_id": request.resource_id,
            "result": result,
            "replayed": replayed,
            "correlation_id": request.context.correlation_id,
        }

    def project(
        self,
        *,
        context: Any,
        planning_scope_id: str,
        expected_snapshot_id: str,
        expected_snapshot_hash: str,
    ) -> Any:
        """Trusted Runtime port; no HTTP-carried private Snapshot or solve work."""
        binding = self._binding(context, planning_scope_id, "event_ingest")
        base_record = self._source(binding, binding["base_planning_run_id"])
        base = self._snapshots.get_by_id(expected_snapshot_id)
        if base is None or base.snapshot_hash != expected_snapshot_hash:
            raise RuntimeEventError("STALE_SNAPSHOT", "base_snapshot")
        # Walk immutable predecessor hashes back to the configured ingress root.
        cursor, seen = base, set()
        while cursor.snapshot_hash != base_record.snapshot.snapshot_hash:
            if cursor.snapshot_hash in seen:
                raise RuntimeEventError("MIXED_LINEAGE", "base_snapshot")
            seen.add(cursor.snapshot_hash)
            previous = cursor.document["source_versions"].get(
                "plantnexus-previous-snapshot"
            )
            if previous is None:
                raise RuntimeEventError("MIXED_LINEAGE", "base_snapshot")
            cursor = self._snapshots.get_by_hash(previous)
            if cursor is None:
                raise RuntimeEventError("MIXED_LINEAGE", "base_snapshot")
        for event in self._events.list_stream(
            **{k: binding[k] for k in ("authority_id", "stream_id", "stream_version")}
        ):
            self._validate(event, binding)
        return self._service(binding, None).project_available(base)
