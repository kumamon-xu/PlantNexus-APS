"""Emit machine-checkable TASK-P4-09 Execution Simulator core evidence."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.application.execution_fact_projection import ExecutionFactProjectionService
from app.domain.execution_contracts import canonical_contract_bytes

from .contracts import (
    ArtifactReference,
    ExecutionSimulatorCheckpoint,
    ExecutionSimulatorConfig,
    ExecutionSimulatorError,
    ExecutionSimulatorFailure,
    PlanningPolicyReference,
    PublishedScheduleReference,
    ScheduledExecutionEvent,
    SolveLimitsReference,
    VersionedAssetReference,
    VersionedExecutionSchedule,
    VirtualClock,
)
from .simulator import (
    CompiledExecutionStream,
    ExecutionEventIngressPort,
    ExecutionSimulator,
)


REPORT_VERSION = "p4-execution-simulator-report.v1"
TASK_ID = "TASK-P4-09"
DIFF_BASE = "e4874735166be93473ccaebaf1090980db957552"
IMPACT_RULES = (
    "IMPACT-DOCS",
    "IMPACT-INFRA",
    "IMPACT-SIM-EXECUTION",
    "IMPACT-TESTS",
)
_ORIGIN = "2026-08-28T08:00:00Z"
_FROZEN_SHA256 = {
    "schemas/json/execution-event.schema.json": (
        "90e62fce67b28baf1ba7f2a5e987702437828affce5d94911d9cc6ac55f73d8e"
    ),
    "schemas/json/execution-simulation-manifest.schema.json": (
        "14194d4b1c3c84c1883ef88c9e30e7f8b03d9ddb3d1323ca72521af775e4231c"
    ),
    "docs/adr/ADR-0015-deterministic-execution-simulator-common-path.md": (
        "efaece8431f12bbc48a9ae94dd2ad3112544645fcec035065ad0e4d26d841eae"
    ),
    "backend/app/application/execution_fact_projection.py": (
        "f7f3c9aefdf9bb7d2a16c3cb5866b0ae25815bbafb7ffa41f812d777cc6ba995"
    ),
    "backend/app/domain/execution_contracts.py": (
        "a0eef35b163216a66436ce9326c9fa2e92d7d01f4e0197ed97cca7b5cec5d7f6"
    ),
    "schemas/rules/state-machines.v1.yaml": (
        "6a8c32137a681c6c96defd0dcdd3e580490ec82b81b6494b9b3ba4bf2144ddd7"
    ),
    "pyproject.toml": (
        "327b705255dc9792139aa690351601a1e6a6cba019920142adfa656d6902fe5e"
    ),
    "uv.lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}


@dataclass(frozen=True, slots=True)
class ExecutionSimulatorFixture:
    config: ExecutionSimulatorConfig
    schedule: VersionedExecutionSchedule
    fact_checkpoint: ArtifactReference


@dataclass(frozen=True, slots=True)
class _WriteResult:
    replayed: bool


@dataclass(frozen=True, slots=True)
class _AuditRecord:
    audit_record_id: str


class _EventRepository:
    def __init__(self) -> None:
        self.documents_by_id: dict[str, bytes] = {}
        self.ids_by_position: dict[int, str] = {}
        self.append_calls = 0
        self.replay_calls = 0

    def append_in_transaction(
        self, _connection: object, document: Mapping[str, object]
    ) -> _WriteResult:
        self.append_calls += 1
        event_id = cast(str, document["event_id"])
        position = cast(int, document["source_position"])
        content = canonical_contract_bytes(document)
        existing = self.documents_by_id.get(event_id)
        if existing is not None:
            if existing != content:
                raise RuntimeError("same event identity has different bytes")
            self.replay_calls += 1
            return _WriteResult(replayed=True)
        occupied = self.ids_by_position.get(position)
        if occupied is not None and occupied != event_id:
            raise RuntimeError("source position already contains another event")
        self.documents_by_id[event_id] = content
        self.ids_by_position[position] = event_id
        return _WriteResult(replayed=False)


class _AuditRepository:
    def __init__(self) -> None:
        self.identities: set[str] = set()

    def append_in_transaction(
        self, _connection: object, record: _AuditRecord
    ) -> _WriteResult:
        replayed = record.audit_record_id in self.identities
        self.identities.add(record.audit_record_id)
        return _WriteResult(replayed=replayed)


def _fingerprint(character: str) -> str:
    return f"sha256:{character * 64}"


def build_execution_simulator_fixture(
    *, code_commit: str = "uncommitted"
) -> ExecutionSimulatorFixture:
    """Build the bounded SIM-ASSUMPTION-018 core correctness vector."""

    base_schedule = PublishedScheduleReference(
        schedule_version_version="schedule-version.v2",
        schedule_version_id="schedule-version-p4-simulator-base-001",
        state="PUBLISHED",
        content_fingerprint=_fingerprint("1"),
    )
    scenario = VersionedAssetReference(
        asset_id="SIM-P4-EXECUTION-CORE-001",
        asset_version="1.0.0",
        fingerprint=_fingerprint("4"),
    )
    factory_profile = VersionedAssetReference(
        asset_id="PROFILE-P4-EXECUTION-CORE-001",
        asset_version="1.0.0",
        fingerprint=_fingerprint("5"),
    )
    generator = VersionedAssetReference(
        asset_id="PLANTNEXUS-P4-EXECUTION-CORE-CONFIG",
        asset_version="1.0.0",
        fingerprint=_fingerprint("6"),
    )
    config = ExecutionSimulatorConfig(
        data_plane="SIMULATION",
        environment="TEST",
        production_binding=False,
        synthetic=True,
        factory_id="factory-p4-simulator-001",
        planning_scope_id="planning-scope-p4-simulator-001",
        base_schedule_version=base_schedule,
        base_snapshot=ArtifactReference(
            "planning-snapshot.v2",
            "snapshot-p4-simulator-base-001",
            _fingerprint("2"),
        ),
        base_problem=ArtifactReference(
            "planning-problem.v2",
            "problem-p4-simulator-base-001",
            _fingerprint("3"),
        ),
        scenario=scenario,
        factory_profile=factory_profile,
        generator=generator,
        simulator=VersionedAssetReference(
            asset_id="PLANTNEXUS-EXECUTION-SIMULATOR",
            asset_version="1.0.0",
            fingerprint=_fingerprint("7"),
        ),
        seed=20260828,
        required_capabilities=(
            "DYNAMIC_REPLANNING",
            "SINGLE_FACTORY_MULTI_WORKSHOP",
        ),
        virtual_clock=VirtualClock(
            clock_version="virtual-clock.v1",
            origin_at_utc=_ORIGIN,
            resolution_seconds=1,
        ),
        planning_policy=PlanningPolicyReference(
            planning_policy_version="planning-policy.v2",
            policy_id="POLICY-P4-SIM-DYNAMIC-001",
            policy_revision="1.0.0",
            policy_fingerprint=_fingerprint("8"),
        ),
        solve_limits=SolveLimitsReference(
            solve_limits_version="solve-limits.v1",
            limits_id="LIMITS-SAMPLE-P2-02-001",
            limits_revision="1.0.0",
            limits_fingerprint=_fingerprint("9"),
            max_wall_time_seconds=30,
            max_workers=1,
            random_seed=20260820,
        ),
        code_commit=code_commit,
    )
    events = (
        ScheduledExecutionEvent.create(
            event_key="operation-started-core-001",
            offset_seconds=20,
            event_type="OPERATION_STARTED",
            payload={
                "kind": "OPERATION_STARTED",
                "operation_id": "operation-p4-simulator-001",
                "resource_id": "resource-p4-simulator-001",
                "actual_start_at_utc": "2026-08-28T08:00:20Z",
            },
        ),
        ScheduledExecutionEvent.create(
            event_key="material-ready-core-001",
            offset_seconds=10,
            event_type="MATERIAL_READY",
            payload={
                "kind": "MATERIAL_READY",
                "material_id": "material-p4-simulator-001",
                "available_at_utc": "2026-08-28T08:00:10Z",
            },
        ),
        ScheduledExecutionEvent.create(
            event_key="duration-observed-core-001",
            offset_seconds=10,
            event_type="PROCESSING_DURATION_CHANGED",
            payload={
                "kind": "PROCESSING_DURATION_CHANGED",
                "operation_id": "operation-p4-simulator-001",
                "final_duration_seconds": 333,
                "duration_source": "p4-simulator-core-observation",
                "source_version": "1.0.0",
            },
        ),
    )
    schedule = VersionedExecutionSchedule(
        schedule_version="execution-event-schedule.v1",
        config_id="SIM-P4-EXECUTION-CORE-CONFIG-001",
        config_version="1.0.0",
        base_schedule_content_fingerprint=base_schedule.content_fingerprint,
        scenario_fingerprint=scenario.fingerprint,
        factory_profile_fingerprint=factory_profile.fingerprint,
        generator_fingerprint=generator.fingerprint,
        events=events,
    )
    return ExecutionSimulatorFixture(
        config=config,
        schedule=schedule,
        fact_checkpoint=ArtifactReference(
            document_version="execution-fact-checkpoint.v1",
            artifact_id="fact-checkpoint-p4-simulator-core-001",
            fingerprint=_fingerprint("a"),
        ),
    )


@contextmanager
def _transaction() -> Iterator[object]:
    yield object()


def _audit_factory(**values: object) -> _AuditRecord:
    fingerprint = sha256(canonical_contract_bytes(values)).hexdigest()
    return _AuditRecord(audit_record_id=f"audit-record-{fingerprint}")


def _common_ingress(
    compiled: CompiledExecutionStream,
    events: _EventRepository,
    audits: _AuditRepository,
) -> ExecutionFactProjectionService:
    return ExecutionFactProjectionService(
        transaction_factory=_transaction,
        scope=compiled.scope,
        events=cast(Any, events),
        checkpoints=cast(Any, object()),
        audits=cast(Any, audits),
        snapshots=cast(Any, object()),
        checkpoint_factory=cast(Any, lambda **_values: object()),
        audit_factory=cast(Any, _audit_factory),
        persistence_error_types=(RuntimeError,),
    )


def _schema_validator(root: Path, name: str) -> Draft202012Validator:
    schemas: dict[str, dict[str, object]] = {}
    resources: list[tuple[str, Resource[object]]] = []
    for path in sorted((root / "schemas/json").glob("*.json")):
        schema = cast(
            dict[str, object], json.loads(path.read_text(encoding="utf-8"))
        )
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    return Draft202012Validator(
        schemas[name],
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _expect_failure(
    reason: ExecutionSimulatorFailure, operation: object
) -> ExecutionSimulatorError:
    if not callable(operation):
        raise TypeError("operation must be callable")
    try:
        cast(Any, operation)()
    except ExecutionSimulatorError as error:
        if error.reason is reason:
            return error
        raise ValueError(
            f"expected {reason.value}, observed {error.reason.value}"
        ) from error
    raise ValueError(f"expected {reason.value} rejection")


def _frozen_boundaries(root: Path) -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative, expected in _FROZEN_SHA256.items():
        digest = sha256((root / relative).read_bytes()).hexdigest()
        _ensure(digest == expected, f"frozen boundary changed: {relative}")
        observed[relative] = digest
    return observed


def _source_boundary(root: Path) -> dict[str, object]:
    core_paths = (
        root / "backend/app/simulation/execution/contracts.py",
        root / "backend/app/simulation/execution/simulator.py",
    )
    forbidden = (
        "app.infrastructure",
        "app.planning",
        "app.api",
        "app.application",
        "sqlalchemy",
        "ortools",
        "datetime.now",
        "datetime.utcnow",
        "random.",
    )
    import_roots: set[str] = set()
    ingress_calls = 0
    for path in core_paths:
        text = path.read_text(encoding="utf-8")
        _ensure(
            not any(token in text for token in forbidden),
            f"core shortcut/wall-clock token found in {path.name}",
        )
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_roots.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                import_roots.add(node.module)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "ingress"
            ):
                _ensure(
                    node.func.attr == "ingest_event",
                    "simulator called an unapproved ingress method",
                )
                ingress_calls += 1
    _ensure(ingress_calls == 1, "core must contain exactly one common-ingress call")
    return {
        "core_files": [path.relative_to(root).as_posix() for path in core_paths],
        "import_roots": sorted(import_roots),
        "ingress_method": "ingest_event",
        "ingress_call_sites": ingress_calls,
        "forbidden_shortcuts": [],
    }


def run_execution_simulator_checks(root: Path) -> dict[str, object]:
    """Run all deterministic, contract, restart, isolation, and boundary checks."""

    code_commit = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    fixture = build_execution_simulator_fixture(code_commit=code_commit)
    simulator = ExecutionSimulator()
    compiled = simulator.compile(fixture.config, fixture.schedule)

    events = _EventRepository()
    audits = _AuditRepository()
    ingress = _common_ingress(compiled, events, audits)
    _ensure(
        isinstance(ingress, ExecutionEventIngressPort),
        "P4-04 public ingress does not satisfy the simulator port",
    )
    first = simulator.run(fixture.config, fixture.schedule, ingress)
    replay = simulator.run(fixture.config, fixture.schedule, ingress)
    _ensure(first.event_bytes == replay.event_bytes, "same input changed event bytes")
    _ensure(
        first.stream_fingerprint == replay.stream_fingerprint,
        "same input changed the event stream fingerprint",
    )
    _ensure(events.append_calls == 6, "two full runs did not use ingress per event")
    _ensure(events.replay_calls == 3, "second full run was not an exact replay")

    permuted = replace(fixture.schedule, events=tuple(reversed(fixture.schedule.events)))
    permuted_compiled = simulator.compile(fixture.config, permuted)
    _ensure(
        compiled.event_bytes == permuted_compiled.event_bytes
        and compiled.run_fingerprint == permuted_compiled.run_fingerprint,
        "declaration order changed canonical queue output",
    )

    restart_events = _EventRepository()
    restart_audits = _AuditRepository()
    restart_ingress = _common_ingress(compiled, restart_events, restart_audits)
    first_batch = simulator.run(
        fixture.config,
        fixture.schedule,
        restart_ingress,
        max_events=1,
    )
    second_batch = simulator.run(
        fixture.config,
        fixture.schedule,
        restart_ingress,
        checkpoint=first_batch.checkpoint,
    )
    _ensure(
        first_batch.emitted_positions == (1,)
        and second_batch.emitted_positions == (2, 3),
        "checkpoint restart emitted the wrong positions",
    )
    _ensure(
        second_batch.event_bytes == first.event_bytes,
        "checkpoint restart changed the complete prefix",
    )
    calls_before_rejection = restart_events.append_calls
    bad_checkpoint = ExecutionSimulatorCheckpoint(
        checkpoint_version="execution-simulator-checkpoint.v1",
        run_fingerprint=compiled.run_fingerprint,
        last_emitted_position=1,
        prefix_fingerprint=_fingerprint("0"),
    )
    _expect_failure(
        ExecutionSimulatorFailure.CHECKPOINT_MISMATCH,
        lambda: simulator.run(
            fixture.config,
            fixture.schedule,
            restart_ingress,
            checkpoint=bad_checkpoint,
        ),
    )
    _ensure(
        restart_events.append_calls == calls_before_rejection,
        "bad checkpoint reached ingress",
    )

    event_validator = _schema_validator(root, "execution-event.schema.json")
    for event in first.events:
        event_validator.validate(event)
    manifest = first.build_manifest(fact_checkpoint=fixture.fact_checkpoint)
    _schema_validator(root, "execution-simulation-manifest.schema.json").validate(
        manifest
    )

    boundary_calls = restart_events.append_calls
    _expect_failure(
        ExecutionSimulatorFailure.PRODUCTION_FORBIDDEN,
        lambda: replace(fixture.config, environment="PRODUCTION"),
    )
    _expect_failure(
        ExecutionSimulatorFailure.VERSION_MISMATCH,
        lambda: replace(
            fixture.config, required_capabilities=("REALITY_CALIBRATION",)
        ),
    )
    stale_schedule = replace(
        fixture.schedule, scenario_fingerprint=_fingerprint("b")
    )
    _expect_failure(
        ExecutionSimulatorFailure.SOURCE_MISMATCH,
        lambda: simulator.run(fixture.config, stale_schedule, restart_ingress),
    )
    _ensure(
        restart_events.append_calls == boundary_calls,
        "Production/P5/stale-source rejection reached ingress",
    )

    frozen = _frozen_boundaries(root)
    source_boundary = _source_boundary(root)
    event_times = [cast(str, event["occurred_at_utc"]) for event in first.events]
    _ensure(
        event_times.count("2026-08-28T08:00:10Z") == 2
        and event_times[-1] == "2026-08-28T08:00:20Z",
        "virtual clock did not project declared offsets",
    )
    boundaries = {
        "data_plane": "SIMULATION_ONLY",
        "time_source": "VERSIONED_VIRTUAL_CLOCK_ONLY",
        "event_output": "STANDARD_EXECUTION_EVENT_V1_ONLY",
        "common_ingress": "P4_04_EXECUTION_FACT_PROJECTION_SERVICE_INGEST_EVENT",
        "database_solver_replan_schedule_write": "NONE_IN_SIMULATOR_CORE",
        "fact_checkpoint": "EXPLICIT_CALLER_SUPPLIED_REFERENCE_ONLY",
        "five_disruption_continuous_replay": "P4_10_NOT_IMPLEMENTED",
        "business_state_transition": "NONE",
        "p5_plus": "EXPLICITLY_REJECTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }
    checks = [
        _pass(
            "published-base-versioned-provenance-and-source-binding",
            {
                "base_schedule_version_id": (
                    fixture.config.base_schedule_version.schedule_version_id
                ),
                "scenario": fixture.config.scenario.as_document(),
                "event_schedule_fingerprint": fixture.schedule.fingerprint,
                "run_fingerprint": compiled.run_fingerprint,
            },
        ),
        _pass(
            "virtual-clock-queue-and-named-child-seed-tie-break",
            {
                "origin_at_utc": _ORIGIN,
                "resolution_seconds": fixture.config.virtual_clock.resolution_seconds,
                "event_keys": list(compiled.event_keys),
                "tie_break_ranks": list(compiled.tie_break_ranks),
                "occurred_at_utc": event_times,
            },
        ),
        _pass(
            "canonical-standard-execution-event-stream",
            {
                "event_ids": list(first.event_ids),
                "event_fingerprints": list(first.event_fingerprints),
                "stream_fingerprint": first.stream_fingerprint,
            },
        ),
        _pass(
            "same-input-and-declaration-order-byte-exact-replay",
            {
                "full_replay_count": events.replay_calls,
                "event_bytes_sha256": [
                    sha256(document).hexdigest() for document in first.event_bytes
                ],
                "permuted_declaration_equal": True,
            },
        ),
        _pass(
            "prefix-checkpoint-restart-and-corruption-rejection",
            {
                "first_batch_positions": list(first_batch.emitted_positions),
                "restart_positions": list(second_batch.emitted_positions),
                "final_checkpoint": {
                    "last_emitted_position": (
                        second_batch.checkpoint.last_emitted_position
                    ),
                    "prefix_fingerprint": (
                        second_batch.checkpoint.prefix_fingerprint
                    ),
                },
            },
        ),
        _pass(
            "p4-04-public-common-ingress-and-no-shortcut",
            {
                "service": "ExecutionFactProjectionService",
                "first_and_replay_ingress_calls": events.append_calls,
                "source_boundary": source_boundary,
            },
        ),
        _pass(
            "p4-02-manifest-contract-and-frozen-carriers",
            {
                "manifest_id": manifest["manifest_id"],
                "manifest_fingerprint": manifest["manifest_fingerprint"],
                "frozen_files": frozen,
            },
        ),
        _pass("p4-p5-production-capability-boundary", boundaries),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "counts": {
            "scheduled_events": len(fixture.schedule.events),
            "same_offset_events": 2,
            "event_types": len({event.event_type for event in fixture.schedule.events}),
            "same_input_full_runs": 2,
            "checkpoint_batches": 2,
            "public_ingress_calls": events.append_calls,
            "frozen_boundary_files": len(frozen),
            "machine_checks": len(checks),
        },
        "stream_manifest": {
            "event_schedule_fingerprint": fixture.schedule.fingerprint,
            "run_fingerprint": compiled.run_fingerprint,
            "event_keys": list(compiled.event_keys),
            "event_ids": list(first.event_ids),
            "event_fingerprints": list(first.event_fingerprints),
            "stream_fingerprint": first.stream_fingerprint,
            "manifest_id": manifest["manifest_id"],
            "manifest_fingerprint": manifest["manifest_fingerprint"],
        },
        "boundaries": boundaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_execution_simulator_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "diff_base": DIFF_BASE,
            "impact_rule_count": len(IMPACT_RULES),
            "impact_rules": list(IMPACT_RULES),
            "error_type": type(error).__name__,
            "error_message": "Execution Simulator evidence check failed",
            "issues": ["machine-check-failed"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "IMPACT_RULES",
    "REPORT_VERSION",
    "TASK_ID",
    "ExecutionSimulatorFixture",
    "build_execution_simulator_fixture",
    "main",
    "run_execution_simulator_checks",
]
