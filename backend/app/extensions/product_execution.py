"""Runtime-owned product lifecycle for verified Enterprise Extensions.

The executor projects canonical PlanningProblem/Solution documents into the
solver-neutral SDK fact view.  It never mutates Core inputs or interprets an
enterprise contract inside Core.  Feasibility-affecting contributions remain
fail-closed because their independently implemented Validation Rules must pass
before a ScheduleVersion can be created.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from aps_extension_sdk import ReplanAction, ValidationOutput

from app.application.runtime_http_adapter import RuntimeHttpPolicyCatalog
from app.data_validation.canonical_ingress import canonical_fingerprint
from app.extensions.contracts import (
    RuntimeExtensionErrorCode,
    reject_extension,
)
from app.extensions.registry import LoadedRuntimeExtensionAdapter


type JsonObject = dict[str, Any]

PLANNING_RUN_STATE_MACHINE_VERSION = "planning-run-state-machine.v1"
PRODUCT_EXECUTION_VERSION = "runtime-extension-product-execution.v1"


def _objects(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in value
    ):
        reject_extension(
            RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
            field=field,
            message="Runtime product facts are invalid",
        )
    return tuple(cast(list[Mapping[str, object]], value))


def _attributes(value: object, *, field: str) -> Mapping[str, Mapping[str, object]]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) or not isinstance(item, Mapping)
        for key, item in value.items()
    ):
        reject_extension(
            RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
            field=field,
            message="Runtime Extension attribute policy is invalid",
        )
    return cast(Mapping[str, Mapping[str, object]], value)


def _merge_attributes(
    rows: tuple[Mapping[str, object], ...],
    configured: Mapping[str, Mapping[str, object]],
    *,
    identifier_field: str,
    field: str,
    derived: Mapping[str, Mapping[str, object]] | None = None,
) -> list[JsonObject]:
    observed: set[str] = set()
    result: list[JsonObject] = []
    for row in rows:
        identifier = row.get(identifier_field)
        if not isinstance(identifier, str):
            reject_extension(
                RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
                field=field,
                message="Runtime product fact identity is invalid",
            )
        observed.add(identifier)
        base = dict(row)
        additions = {
            **dict((derived or {}).get(identifier, {})),
            **dict(configured.get(identifier, {})),
        }
        if set(base).intersection(additions):
            reject_extension(
                RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
                field=field,
                message="Runtime Extension attributes cannot replace canonical facts",
            )
        result.append({**base, **additions})
    if set(configured) - observed:
        reject_extension(
            RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
            field=field,
            message="Runtime Extension attributes reference an unknown canonical entity",
        )
    return result


class RuntimeExtensionProductExecutor:
    """Invoke one startup-resolved Extension set at approved Worker stages."""

    def __init__(
        self,
        *,
        adapter: object,
        policy: RuntimeHttpPolicyCatalog,
    ) -> None:
        self._adapter = (
            adapter if isinstance(adapter, LoadedRuntimeExtensionAdapter) else None
        )
        self._policy = policy

    @property
    def enabled(self) -> bool:
        return self._adapter is not None

    def _configured_facts(self, scope: Mapping[str, object]) -> Mapping[str, object]:
        try:
            return self._policy.extension_facts_for(
                tenant_id=cast(str, scope["tenant_id"]),
                factory_id=cast(str, scope["factory_id"]),
                planning_scope_id=cast(str, scope["planning_scope_id"]),
            )
        except (KeyError, TypeError, ValueError):
            reject_extension(
                RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
                field="extension_facts.scope",
                message="Runtime Extension facts are unavailable for the planning scope",
            )

    def _facts(
        self,
        *,
        scope: Mapping[str, object],
        problem: Mapping[str, object],
        solution: Mapping[str, object] | None,
    ) -> tuple[JsonObject, Mapping[str, object]]:
        configured = self._configured_facts(scope)
        resources = _objects(problem.get("resources"), field="problem.resources")
        operations = _objects(
            problem.get("operation_instances"), field="problem.operation_instances"
        )
        demands = _objects(
            problem.get("delivery_demands"), field="problem.delivery_demands"
        )
        priorities: dict[str, int] = {}
        for demand in demands:
            demand_id = demand.get("demand_order_id")
            priority = demand.get("priority_weight")
            if (
                not isinstance(demand_id, str)
                or isinstance(priority, bool)
                or not isinstance(priority, int)
            ):
                reject_extension(
                    RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
                    field="problem.delivery_demands",
                    message="Runtime product priority facts are invalid",
                )
            priorities[demand_id] = priority
        derived_operations: dict[str, Mapping[str, object]] = {}
        for operation in operations:
            operation_id = operation.get("operation_id")
            demand_id = operation.get("demand_order_id")
            if not isinstance(operation_id, str) or demand_id not in priorities:
                reject_extension(
                    RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
                    field="problem.operation_instances",
                    message="Runtime product operation lineage is invalid",
                )
            derived_operations[operation_id] = {
                "enterprise_priority": priorities[cast(str, demand_id)]
            }
        resource_attributes = _attributes(
            configured.get("resource_attributes"),
            field="extension_facts.resource_attributes",
        )
        operation_attributes = _attributes(
            configured.get("operation_attributes"),
            field="extension_facts.operation_attributes",
        )
        assignments: list[object] = []
        if solution is not None:
            raw_assignments = solution.get("assignments")
            if not isinstance(raw_assignments, list):
                reject_extension(
                    RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
                    field="solution.assignments",
                    message="Runtime product assignment facts are invalid",
                )
            assignments = list(raw_assignments)
        events = configured.get("events")
        if not isinstance(events, list):
            reject_extension(
                RuntimeExtensionErrorCode.CONFIGURATION_INVALID,
                field="extension_facts.events",
                message="Runtime Extension event facts are invalid",
            )
        facts: JsonObject = {
            "problem_reference": {
                "snapshot_id": problem.get("snapshot_id"),
                "problem_hash": problem.get("problem_hash"),
            },
            "resources": _merge_attributes(
                resources,
                resource_attributes,
                identifier_field="resource_id",
                field="extension_facts.resource_attributes",
            ),
            "operations": _merge_attributes(
                operations,
                operation_attributes,
                identifier_field="operation_id",
                field="extension_facts.operation_attributes",
                derived=derived_operations,
            ),
            "assignments": assignments,
            "events": list(events),
        }
        return facts, configured

    @staticmethod
    def _provenance(
        *,
        lifecycle: str,
        planning_run_id: str,
        problem: Mapping[str, object],
        solution: Mapping[str, object] | None,
        configured: Mapping[str, object],
    ) -> JsonObject:
        return {
            "product_execution_version": PRODUCT_EXECUTION_VERSION,
            "lifecycle": lifecycle,
            "planning_run_id": planning_run_id,
            "problem_fingerprint": canonical_fingerprint(problem),
            "solution_fingerprint": (
                canonical_fingerprint(solution) if solution is not None else None
            ),
            "extension_facts_fingerprint": canonical_fingerprint(configured),
        }

    def before_solve(
        self,
        *,
        scope: Mapping[str, object],
        planning_run_id: str,
        problem: Mapping[str, object],
    ) -> None:
        adapter = self._adapter
        if adapter is None:
            return
        facts, configured = self._facts(scope=scope, problem=problem, solution=None)
        provenance = self._provenance(
            lifecycle="PRODUCT_PRE_SOLVE",
            planning_run_id=planning_run_id,
            problem=problem,
            solution=None,
            configured=configured,
        )
        adapter.invoke_plugin_registry()
        adapter.invoke_planning_rules(scope=scope, facts=facts, provenance=provenance)
        adapter.invoke_constraints(scope=scope, facts=facts, provenance=provenance)
        decision = adapter.invoke_replan_policy(
            scope=scope,
            facts=facts,
            provenance=provenance,
            execution_fact_fingerprint=canonical_fingerprint(
                problem.get("historical_completion_anchors", [])
            ),
            hard_lock_fingerprint=canonical_fingerprint(
                problem.get("operation_locks", [])
            ),
            freeze_window_fingerprint=canonical_fingerprint(
                {
                    "horizon_start_utc": problem.get("horizon_start_utc"),
                    "horizon_end_utc": problem.get("horizon_end_utc"),
                }
            ),
            state_machine_version=PLANNING_RUN_STATE_MACHINE_VERSION,
            publication_authority_reference=cast(
                str, configured["publication_authority_reference"]
            ),
        )
        if decision is not None and decision.action is ReplanAction.REQUEST_REPLAN:
            reject_extension(
                RuntimeExtensionErrorCode.EXTENSION_REPLAN_REQUIRED,
                field=decision.contribution_id,
                message="Extension requested a separate authorized replanning workflow",
            )

    def after_candidate(
        self,
        *,
        scope: Mapping[str, object],
        planning_run_id: str,
        problem: Mapping[str, object],
        solution: Mapping[str, object],
    ) -> None:
        adapter = self._adapter
        if adapter is None:
            return
        facts, configured = self._facts(scope=scope, problem=problem, solution=solution)
        provenance = self._provenance(
            lifecycle="PRODUCT_CANDIDATE_VALIDATION",
            planning_run_id=planning_run_id,
            problem=problem,
            solution=solution,
            configured=configured,
        )
        adapter.invoke_objectives(scope=scope, facts=facts, provenance=provenance)
        validations = adapter.invoke_validation_rules(
            scope=scope, facts=facts, provenance=provenance
        )
        failed = tuple(
            output
            for output in cast(tuple[ValidationOutput, ...], validations)
            if not output.passed
        )
        if failed:
            reject_extension(
                RuntimeExtensionErrorCode.EXTENSION_VALIDATION_FAILED,
                field=failed[0].contribution_id,
                message="Extension Validation rejected the planning candidate",
            )


__all__ = [
    "PLANNING_RUN_STATE_MACHINE_VERSION",
    "PRODUCT_EXECUTION_VERSION",
    "RuntimeExtensionProductExecutor",
]
