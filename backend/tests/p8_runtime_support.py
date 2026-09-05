"""Shared explicit composition for TEST-P8-APPLICATION-COMPOSITION-001."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Mapping, cast

from pydantic import SecretStr
from app.application.canonical_ingress import (
    CanonicalIngressBuildPlan,
    TrustedCanonicalIngressContext,
)
from app.application.planning_runs import PlanningRunCommandContext
from app.application.runtime_facade import RuntimeDispatchWindow
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings
from app.runtime_composition import RuntimeCompositionDescriptor
from backend.tests.contract.p8_canonical_ingress_support import (
    AUTHORITY_REFERENCE,
    MAPPING_FINGERPRINT,
    ROOT,
)
from backend.tests.p8_solver_worker_support import planning_policy, solve_limits


RUNTIME_CODE_COMMIT = "c69fbe3b21e0e782a293675b523c41f31898d0da"
RUNTIME_NOW = datetime(2026, 9, 5, 2, 0, 0, tzinfo=UTC)


class RecordingCelery:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[dict[str, object]] = []

    def send_task(
        self,
        name: str,
        *,
        args: tuple[object, ...],
        task_id: str,
    ) -> object:
        if self.fail:
            raise RuntimeError(
                "redis://operator:do-not-leak@broker/private dispatch failure"
            )
        self.messages.append({"name": name, "args": args, "task_id": task_id})
        return object()


class FixedIdentityFactory:
    def __init__(self, *values: str) -> None:
        self._values = list(values or ("runtime-dispatch-001",))

    def __call__(self) -> str:
        if not self._values:
            raise RuntimeError("no test identity remains")
        return self._values.pop(0)


class FixedRuntimeClock:
    def __init__(self, value: datetime = RUNTIME_NOW) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def runtime_settings(
    tmp_path: Path,
    *,
    database_url: str,
    runtime_artifact_fingerprint: str | None = None,
) -> Settings:
    policy_path = tmp_path / "planning-policy.runtime.json"
    limits_path = tmp_path / "solve-limits.runtime.json"
    policy_path.write_text(
        json.dumps(planning_policy(), ensure_ascii=False), encoding="utf-8"
    )
    limits_path.write_text(
        json.dumps(solve_limits(), ensure_ascii=False), encoding="utf-8"
    )
    return Settings(
        runtime_environment=RuntimeEnvironment.TEST,
        data_plane=DataPlane.SIMULATION,
        code_commit=RUNTIME_CODE_COMMIT,
        simulation_api_enabled=True,
        runtime_composition_enabled=True,
        runtime_schema_directory=ROOT / "schemas" / "json",
        runtime_planning_policy_path=policy_path,
        runtime_solve_limits_path=limits_path,
        runtime_artifact_fingerprint=runtime_artifact_fingerprint,
        database_url=SecretStr(database_url),
    )


def ingress_context(
    request: Mapping[str, object],
    descriptor: RuntimeCompositionDescriptor,
) -> TrustedCanonicalIngressContext:
    scope = cast(Mapping[str, object], request["requested_scope"])
    planning_inputs = cast(Mapping[str, object], request["planning_inputs"])
    return TrustedCanonicalIngressContext.create(
        actor_reference="actor:p8-runtime-test",
        auth_policy_version="headless-auth-policy.v1",
        tenant_id=cast(str, scope["tenant_id"]),
        factory_id=cast(str, scope["factory_id"]),
        planning_scope_id=cast(str, scope["planning_scope_id"]),
        data_plane=cast(str, scope["data_plane"]),
        environment=cast(str, scope["environment"]),
        production_binding=False,
        authorized_authority_references=(AUTHORITY_REFERENCE,),
        authorized_mapping_fingerprints=(MAPPING_FINGERPRINT,),
        runtime_resolution=descriptor.runtime_resolution,
        build_plan=CanonicalIngressBuildPlan.create(
            planning_inputs=planning_inputs,
            cutoff_at_utc="2026-08-20T00:00:00Z",
            tick_seconds=60,
            horizon_start_utc="2026-08-20T00:00:00Z",
            horizon_end_utc="2026-08-21T00:00:00Z",
            priority_facts={
                "DEMAND-001": {
                    "priority_weight": 2,
                    "source_system": "plantnexus-synthetic-policy",
                    "source_version": "1.0.0",
                    "source_record_id": "P8-RUNTIME-DEMAND-001",
                }
            },
        ),
        occurred_at_utc="2026-09-05T01:59:00Z",
        code_commit=RUNTIME_CODE_COMMIT,
    )


def command_context(
    request: Mapping[str, object],
    *,
    occurred_at_utc: str = "2026-09-05T02:00:30Z",
) -> PlanningRunCommandContext:
    scope = cast(Mapping[str, object], request["requested_scope"])
    return PlanningRunCommandContext.create(
        actor_reference="actor:p8-runtime-test",
        capabilities=("view", "edit"),
        auth_policy_version="headless-auth-policy.v1",
        tenant_id=cast(str, scope["tenant_id"]),
        factory_id=cast(str, scope["factory_id"]),
        planning_scope_id=cast(str, scope["planning_scope_id"]),
        data_plane=cast(str, scope["data_plane"]),
        environment=cast(str, scope["environment"]),
        production_binding=False,
        correlation_id=cast(str, request["correlation_id"]),
        occurred_at_utc=occurred_at_utc,
        code_commit=RUNTIME_CODE_COMMIT,
    )


def dispatch_window() -> RuntimeDispatchWindow:
    return RuntimeDispatchWindow(
        available_at_utc="2026-09-05T01:59:30Z",
        timeout_at_utc="2026-09-05T03:00:00Z",
    )


def dispatched_message(record: Mapping[str, object]) -> dict[str, object]:
    args = record.get("args")
    if not isinstance(args, tuple) or len(args) != 1 or not isinstance(args[0], dict):
        raise AssertionError("recorded Celery carrier is invalid")
    return cast(dict[str, object], args[0])


__all__ = [
    "FixedIdentityFactory",
    "FixedRuntimeClock",
    "RUNTIME_CODE_COMMIT",
    "RUNTIME_NOW",
    "RecordingCelery",
    "command_context",
    "dispatch_window",
    "dispatched_message",
    "ingress_context",
    "runtime_settings",
]
