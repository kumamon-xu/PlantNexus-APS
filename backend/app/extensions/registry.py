"""Deterministic Runtime Plugin Registry and atomic six-SPI invocation adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import json
from queue import Empty, Queue
from threading import Lock, Thread
from time import monotonic
from typing import Any, TypeVar, cast

from aps_extension_sdk import (
    REGISTRY_PROTOCOL_VERSION,
    SDK_API_VERSION,
    CompatibilityPolicy,
    ConstraintContext,
    ConstraintOutput,
    ContributionManifest,
    ExtensionContractError,
    ExtensionInputView,
    ExtensionManifest,
    ExtensionPoint,
    ObjectiveContext,
    ObjectiveOutput,
    PlanningRuleContext,
    PlanningRuleOutput,
    RegistryResolution,
    ReplanContext,
    ReplanDecision,
    ValidationContext,
    ValidationOutput,
    fingerprint_json,
    validate_protocol_output,
)

from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.extensions.contracts import (
    RUNTIME_EXTENSION_ADAPTER_VERSION,
    RUNTIME_EXTENSION_INPUT_VIEW_VERSION,
    RUNTIME_EXTENSION_METRICS_VERSION,
    RuntimeExtensionError,
    RuntimeExtensionErrorCode,
    RuntimeExtensionLimits,
    reject_extension,
)


type JsonObject = dict[str, Any]
OutputT = TypeVar("OutputT")


@dataclass(frozen=True, slots=True)
class RuntimeExtensionBinding:
    """One manifest contribution bound to one verified implementation object."""

    extension_id: str
    extension_version: str
    artifact_digest: str
    manifest_fingerprint: str
    configuration_fingerprint: str
    signature_key_id: str
    descriptor: ContributionManifest
    configuration_bytes: bytes
    implementation: object

    @property
    def configuration(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.configuration_bytes))

    @property
    def safe_reference(self) -> JsonObject:
        return {
            "extension_id": self.extension_id,
            "extension_version": self.extension_version,
            "artifact_digest": self.artifact_digest,
            "manifest_fingerprint": self.manifest_fingerprint,
            "configuration_fingerprint": self.configuration_fingerprint,
            "signature_key_id": self.signature_key_id,
        }


class RuntimeExtensionMetrics:
    """Process-local safe counters and fingerprints; never retains payloads."""

    def __init__(self, extension_set_fingerprint: str) -> None:
        self._extension_set_fingerprint = extension_set_fingerprint
        self._lock = Lock()
        self._rows: dict[str, dict[str, int | float | str | None]] = {}
        self._unhealthy: set[str] = set()

    def record(
        self,
        descriptor: ContributionManifest,
        *,
        elapsed_ms: float,
        outcome: str,
        lifecycle: str | None = None,
        input_fingerprint: str | None = None,
        output_fingerprint: str | None = None,
    ) -> None:
        with self._lock:
            row = self._rows.setdefault(
                descriptor.contribution_id,
                {
                    "extension_point": descriptor.extension_point.value,
                    "call_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "timeout_count": 0,
                    "last_elapsed_ms": None,
                    "max_elapsed_ms": 0.0,
                    "last_lifecycle": None,
                    "last_input_fingerprint": None,
                    "last_output_fingerprint": None,
                },
            )
            row["call_count"] = cast(int, row["call_count"]) + 1
            if outcome == "SUCCESS":
                row["success_count"] = cast(int, row["success_count"]) + 1
            else:
                row["failure_count"] = cast(int, row["failure_count"]) + 1
                self._unhealthy.add(descriptor.contribution_id)
                if outcome == "TIMEOUT":
                    row["timeout_count"] = cast(int, row["timeout_count"]) + 1
            rounded = round(elapsed_ms, 3)
            row["last_elapsed_ms"] = rounded
            row["max_elapsed_ms"] = max(cast(float, row["max_elapsed_ms"]), rounded)
            row["last_lifecycle"] = lifecycle
            row["last_input_fingerprint"] = input_fingerprint
            row["last_output_fingerprint"] = output_fingerprint

    def assert_healthy(self) -> None:
        with self._lock:
            if self._unhealthy:
                reject_extension(
                    RuntimeExtensionErrorCode.EXTENSION_UNHEALTHY,
                    field="extension_registry",
                    message="one or more Extension contributions failed closed",
                )

    def safe_snapshot(self) -> JsonObject:
        with self._lock:
            rows = [
                {"contribution_id": contribution_id, **dict(values)}
                for contribution_id, values in sorted(self._rows.items())
            ]
            unhealthy = sorted(self._unhealthy)
        return {
            "metrics_version": RUNTIME_EXTENSION_METRICS_VERSION,
            "extension_set_fingerprint": self._extension_set_fingerprint,
            "contributions": rows,
            "unhealthy_contribution_ids": unhealthy,
            "payloads_recorded": False,
            "exception_details_recorded": False,
        }


def _safe_output_projection(value: object) -> object:
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _safe_output_projection(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, (tuple, list)):
        return [_safe_output_projection(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _safe_output_projection(getattr(value, field.name))
            for field in fields(value)
        }
    raise TypeError("Extension output cannot be fingerprinted")


def invoke_trusted_extension(
    binding: RuntimeExtensionBinding,
    operation: Callable[[], OutputT],
    *,
    timeout_ms: int,
    metrics: RuntimeExtensionMetrics,
    validate: Callable[[OutputT], None] | None = None,
    lifecycle: str | None = None,
    input_fingerprint: str | None = None,
) -> OutputT:
    """Run trusted code behind a bounded, discard-on-failure daemon call.

    Python threads are not a malicious-code sandbox. On timeout the complete
    attempt is rejected, the contribution is marked unhealthy, and late output
    is discarded. P8 conformance forbids privileged services and import-time
    side effects; untrusted isolation remains a separate ADR.
    """

    queue: Queue[tuple[bool, object]] = Queue(maxsize=1)

    def target() -> None:
        try:
            queue.put((True, operation()))
        except Exception as error:  # noqa: BLE001 - raw plugin detail is never rendered
            queue.put((False, error))

    started = monotonic()
    thread = Thread(
        target=target,
        name=f"aps-extension-{binding.descriptor.extension_point.value.lower()}",
        daemon=True,
    )
    try:
        thread.start()
        thread.join(timeout_ms / 1_000)
    except Exception as error:  # noqa: BLE001 - runtime thread detail is private
        elapsed_ms = (monotonic() - started) * 1_000
        metrics.record(
            binding.descriptor,
            elapsed_ms=elapsed_ms,
            outcome="FAILURE",
            lifecycle=lifecycle,
            input_fingerprint=input_fingerprint,
        )
        raise RuntimeExtensionError(
            RuntimeExtensionErrorCode.EXTENSION_EXECUTION_FAILED.value,
            field=binding.descriptor.contribution_id,
            message="Extension invocation failed",
        ) from error
    elapsed_ms = (monotonic() - started) * 1_000
    if thread.is_alive():
        metrics.record(
            binding.descriptor,
            elapsed_ms=elapsed_ms,
            outcome="TIMEOUT",
            lifecycle=lifecycle,
            input_fingerprint=input_fingerprint,
        )
        reject_extension(
            RuntimeExtensionErrorCode.EXTENSION_TIMEOUT,
            field=binding.descriptor.contribution_id,
            message="Extension invocation exceeded its configured budget",
        )
    try:
        succeeded, value = queue.get_nowait()
    except Empty:
        succeeded, value = False, None
    if not succeeded:
        elapsed_ms = (monotonic() - started) * 1_000
        metrics.record(
            binding.descriptor,
            elapsed_ms=elapsed_ms,
            outcome="FAILURE",
            lifecycle=lifecycle,
            input_fingerprint=input_fingerprint,
        )
        reject_extension(
            RuntimeExtensionErrorCode.EXTENSION_EXECUTION_FAILED,
            field=binding.descriptor.contribution_id,
            message="Extension invocation failed",
        )
    result = cast(OutputT, value)
    try:
        if validate is not None:
            validate(result)
    except RuntimeExtensionError:
        elapsed_ms = (monotonic() - started) * 1_000
        metrics.record(
            binding.descriptor,
            elapsed_ms=elapsed_ms,
            outcome="FAILURE",
            lifecycle=lifecycle,
            input_fingerprint=input_fingerprint,
        )
        raise
    except ExtensionContractError as error:
        elapsed_ms = (monotonic() - started) * 1_000
        metrics.record(
            binding.descriptor,
            elapsed_ms=elapsed_ms,
            outcome="FAILURE",
            lifecycle=lifecycle,
            input_fingerprint=input_fingerprint,
        )
        raise RuntimeExtensionError(
            RuntimeExtensionErrorCode.EXTENSION_OUTPUT_INVALID.value,
            field=binding.descriptor.contribution_id,
            message="Extension output violated the SDK contract",
        ) from error
    except Exception as error:  # noqa: BLE001 - validation detail is never rendered
        elapsed_ms = (monotonic() - started) * 1_000
        metrics.record(
            binding.descriptor,
            elapsed_ms=elapsed_ms,
            outcome="FAILURE",
            lifecycle=lifecycle,
            input_fingerprint=input_fingerprint,
        )
        raise RuntimeExtensionError(
            RuntimeExtensionErrorCode.EXTENSION_OUTPUT_INVALID.value,
            field=binding.descriptor.contribution_id,
            message="Extension output violated the SDK contract",
        ) from error
    elapsed_ms = (monotonic() - started) * 1_000
    if elapsed_ms > timeout_ms:
        metrics.record(
            binding.descriptor,
            elapsed_ms=elapsed_ms,
            outcome="TIMEOUT",
            lifecycle=lifecycle,
            input_fingerprint=input_fingerprint,
        )
        reject_extension(
            RuntimeExtensionErrorCode.EXTENSION_TIMEOUT,
            field=binding.descriptor.contribution_id,
            message="Extension invocation exceeded its configured budget",
        )
    try:
        output_fingerprint = canonical_fingerprint(_safe_output_projection(result))
    except Exception as error:  # noqa: BLE001 - output detail is never rendered
        metrics.record(
            binding.descriptor,
            elapsed_ms=elapsed_ms,
            outcome="FAILURE",
            lifecycle=lifecycle,
            input_fingerprint=input_fingerprint,
        )
        raise RuntimeExtensionError(
            RuntimeExtensionErrorCode.EXTENSION_OUTPUT_INVALID.value,
            field=binding.descriptor.contribution_id,
            message="Extension output violated the SDK contract",
        ) from error
    metrics.record(
        binding.descriptor,
        elapsed_ms=elapsed_ms,
        outcome="SUCCESS",
        lifecycle=lifecycle,
        input_fingerprint=input_fingerprint,
        output_fingerprint=output_fingerprint,
    )
    return result


@dataclass(frozen=True, slots=True)
class RuntimeExtensionRegistry:
    """Immutable bindings ordered by the SDK Registry resolution."""

    resolution: RegistryResolution
    bindings: tuple[RuntimeExtensionBinding, ...]

    def __post_init__(self) -> None:
        expected = tuple(item.contribution_id for item in self.resolution.contributions)
        observed = tuple(
            binding.descriptor.contribution_id for binding in self.bindings
        )
        if observed != expected:
            reject_extension(
                RuntimeExtensionErrorCode.REGISTRY_RESOLUTION_MISMATCH,
                field="registry.bindings",
                message="implementation bindings differ from deterministic resolution",
            )

    def for_point(self, point: ExtensionPoint) -> tuple[RuntimeExtensionBinding, ...]:
        return tuple(
            binding
            for binding in self.bindings
            if binding.descriptor.extension_point is point
        )


@dataclass(frozen=True, slots=True)
class LoadedRuntimeExtensionAdapter:
    """Runtime-owned invocation surface for one verified Extension set."""

    canonical_bytes: bytes
    extension_set_reference_bytes: bytes
    registry: RuntimeExtensionRegistry
    policy: CompatibilityPolicy
    manifests: tuple[ExtensionManifest, ...]
    limits: RuntimeExtensionLimits
    metrics: RuntimeExtensionMetrics

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_bytes))

    @property
    def extension_set_reference(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.extension_set_reference_bytes))

    @property
    def contributions(self) -> tuple[ContributionManifest, ...]:
        return self.registry.resolution.contributions

    @property
    def sdk_api_version(self) -> str:
        return SDK_API_VERSION

    @property
    def registry_protocol_version(self) -> str:
        return REGISTRY_PROTOCOL_VERSION

    @property
    def readiness_probe(self) -> Callable[[], None]:
        return self.probe

    def probe(self) -> None:
        self.metrics.assert_healthy()
        document = self.document
        expected = cast(str, self.extension_set_reference["extension_set_fingerprint"])
        if document.get("extension_set_fingerprint") != expected:
            reject_extension(
                RuntimeExtensionErrorCode.EXTENSION_UNHEALTHY,
                field="extension_registry",
                message="Extension Registry identity changed after startup",
            )

    def safe_metrics(self) -> JsonObject:
        return self.metrics.safe_snapshot()

    @staticmethod
    def _input_view(
        binding: RuntimeExtensionBinding,
        *,
        scope: Mapping[str, object],
        facts: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> ExtensionInputView:
        frozen_scope = {
            "authorized_scope": dict(scope),
            "extension_configuration": binding.configuration,
        }
        frozen_provenance = {
            "caller": dict(provenance),
            "runtime_extension": binding.safe_reference,
        }
        basis = {
            "view_contract_version": RUNTIME_EXTENSION_INPUT_VIEW_VERSION,
            "extension_id": binding.extension_id,
            "contribution_id": binding.descriptor.contribution_id,
            "scope": frozen_scope,
            "facts": dict(facts),
            "provenance": frozen_provenance,
        }
        return ExtensionInputView.from_json(
            view_contract_version=RUNTIME_EXTENSION_INPUT_VIEW_VERSION,
            extension_id=binding.extension_id,
            contribution_id=binding.descriptor.contribution_id,
            input_fingerprint=fingerprint_json(basis),
            scope=frozen_scope,
            facts=facts,
            provenance=frozen_provenance,
        )

    def _contexts(
        self,
        point: ExtensionPoint,
        context_type: type[ConstraintContext]
        | type[ObjectiveContext]
        | type[PlanningRuleContext]
        | type[ValidationContext],
        *,
        scope: Mapping[str, object],
        facts: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> tuple[tuple[RuntimeExtensionBinding, object], ...]:
        self.metrics.assert_healthy()
        return tuple(
            (
                binding,
                context_type(
                    self._input_view(
                        binding,
                        scope=scope,
                        facts=facts,
                        provenance=provenance,
                    )
                ),
            )
            for binding in self.registry.for_point(point)
        )

    def _invoke_many(
        self,
        prepared: tuple[tuple[RuntimeExtensionBinding, object], ...],
        *,
        method_name: str,
        lifecycle: str | None,
    ) -> tuple[object, ...]:
        outputs: list[object] = []
        for binding, context in prepared:
            self.metrics.assert_healthy()
            input_view = getattr(context, "input_view", None)
            input_fingerprint = getattr(input_view, "input_fingerprint", None)
            outputs.append(
                invoke_trusted_extension(
                    binding,
                    lambda binding=binding, context=context: cast(
                        Callable[[object], object],
                        getattr(binding.implementation, method_name),
                    )(context),
                    timeout_ms=self.limits.invocation_timeout_ms,
                    metrics=self.metrics,
                    validate=lambda output, binding=binding, context=context: (
                        validate_protocol_output(binding.descriptor, context, output)
                    ),
                    lifecycle=lifecycle,
                    input_fingerprint=(
                        input_fingerprint
                        if isinstance(input_fingerprint, str)
                        else None
                    ),
                )
            )
        return tuple(outputs)

    def invoke_constraints(
        self,
        *,
        scope: Mapping[str, object],
        facts: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> tuple[ConstraintOutput, ...]:
        return cast(
            tuple[ConstraintOutput, ...],
            self._invoke_many(
                self._contexts(
                    ExtensionPoint.CONSTRAINT,
                    ConstraintContext,
                    scope=scope,
                    facts=facts,
                    provenance=provenance,
                ),
                method_name="contribute",
                lifecycle=cast(str | None, provenance.get("lifecycle")),
            ),
        )

    def invoke_objectives(
        self,
        *,
        scope: Mapping[str, object],
        facts: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> tuple[ObjectiveOutput, ...]:
        return cast(
            tuple[ObjectiveOutput, ...],
            self._invoke_many(
                self._contexts(
                    ExtensionPoint.OBJECTIVE,
                    ObjectiveContext,
                    scope=scope,
                    facts=facts,
                    provenance=provenance,
                ),
                method_name="evaluate",
                lifecycle=cast(str | None, provenance.get("lifecycle")),
            ),
        )

    def invoke_planning_rules(
        self,
        *,
        scope: Mapping[str, object],
        facts: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> tuple[PlanningRuleOutput, ...]:
        return cast(
            tuple[PlanningRuleOutput, ...],
            self._invoke_many(
                self._contexts(
                    ExtensionPoint.PLANNING_RULE,
                    PlanningRuleContext,
                    scope=scope,
                    facts=facts,
                    provenance=provenance,
                ),
                method_name="apply",
                lifecycle=cast(str | None, provenance.get("lifecycle")),
            ),
        )

    def invoke_validation_rules(
        self,
        *,
        scope: Mapping[str, object],
        facts: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> tuple[ValidationOutput, ...]:
        return cast(
            tuple[ValidationOutput, ...],
            self._invoke_many(
                self._contexts(
                    ExtensionPoint.VALIDATION_RULE,
                    ValidationContext,
                    scope=scope,
                    facts=facts,
                    provenance=provenance,
                ),
                method_name="validate",
                lifecycle=cast(str | None, provenance.get("lifecycle")),
            ),
        )

    def invoke_replan_policy(
        self,
        *,
        scope: Mapping[str, object],
        facts: Mapping[str, object],
        provenance: Mapping[str, object],
        execution_fact_fingerprint: str,
        hard_lock_fingerprint: str,
        freeze_window_fingerprint: str,
        state_machine_version: str,
        publication_authority_reference: str,
    ) -> ReplanDecision | None:
        self.metrics.assert_healthy()
        bindings = self.registry.for_point(ExtensionPoint.REPLAN_POLICY)
        if not bindings:
            return None
        binding = bindings[0]
        context = ReplanContext(
            input_view=self._input_view(
                binding,
                scope=scope,
                facts=facts,
                provenance=provenance,
            ),
            execution_fact_fingerprint=execution_fact_fingerprint,
            hard_lock_fingerprint=hard_lock_fingerprint,
            freeze_window_fingerprint=freeze_window_fingerprint,
            state_machine_version=state_machine_version,
            publication_authority_reference=publication_authority_reference,
        )
        return invoke_trusted_extension(
            binding,
            lambda: cast(
                Callable[[ReplanContext], ReplanDecision],
                getattr(binding.implementation, "decide"),
            )(context),
            timeout_ms=self.limits.invocation_timeout_ms,
            metrics=self.metrics,
            validate=lambda output: validate_protocol_output(
                binding.descriptor, context, output
            ),
            lifecycle=cast(str | None, provenance.get("lifecycle")),
            input_fingerprint=context.input_view.input_fingerprint,
        )

    def invoke_plugin_registry(self) -> RegistryResolution:
        """Re-run the optional Registry SPI and require Runtime-equivalent output."""

        self.metrics.assert_healthy()
        bindings = self.registry.for_point(ExtensionPoint.PLUGIN_REGISTRY)
        if not bindings:
            return self.registry.resolution
        binding = bindings[0]

        def validate_registry(output: object) -> None:
            validate_protocol_output(
                binding.descriptor, (self.manifests, self.policy), output
            )
            if output != self.registry.resolution:
                reject_extension(
                    RuntimeExtensionErrorCode.REGISTRY_RESOLUTION_MISMATCH,
                    field=binding.descriptor.contribution_id,
                    message="Extension Registry resolution differs from Runtime authority",
                )

        result = invoke_trusted_extension(
            binding,
            lambda: cast(Any, getattr(binding.implementation, "resolve"))(
                self.manifests, self.policy
            ),
            timeout_ms=self.limits.invocation_timeout_ms,
            metrics=self.metrics,
            validate=validate_registry,
            lifecycle="PRODUCT_REGISTRY_RESOLUTION",
            input_fingerprint=canonical_fingerprint(
                _safe_output_projection((self.manifests, self.policy))
            ),
        )
        return cast(RegistryResolution, result)


def build_loaded_adapter(
    *,
    catalog_fingerprint: str,
    policy: CompatibilityPolicy,
    manifests: tuple[ExtensionManifest, ...],
    resolution: RegistryResolution,
    bindings: tuple[RuntimeExtensionBinding, ...],
    limits: RuntimeExtensionLimits,
    signature_key_id: str,
) -> LoadedRuntimeExtensionAdapter:
    """Commit one fully verified Registry only after every startup check passes."""

    extension_references: list[JsonObject] = []
    bindings_by_extension: dict[str, RuntimeExtensionBinding] = {}
    for binding in bindings:
        bindings_by_extension.setdefault(binding.extension_id, binding)
    for extension_id in resolution.extension_ids:
        extension_references.append(bindings_by_extension[extension_id].safe_reference)
    extension_set_basis: JsonObject = {
        "extension_set_version": "runtime-extension-set.v1",
        "sdk_api_version": SDK_API_VERSION,
        "registry_protocol_version": REGISTRY_PROTOCOL_VERSION,
        "registry_resolution_fingerprint": resolution.resolution_fingerprint,
        "catalog_fingerprint": catalog_fingerprint,
        "extensions": extension_references,
    }
    extension_set_fingerprint = canonical_fingerprint(extension_set_basis)
    extension_set_reference: JsonObject = {
        "extension_set_id": (
            "extension-set-" + extension_set_fingerprint.removeprefix("sha256:")[:24]
        ),
        "extension_set_fingerprint": extension_set_fingerprint,
        "configuration_fingerprint": catalog_fingerprint,
    }
    document: JsonObject = {
        "adapter_version": RUNTIME_EXTENSION_ADAPTER_VERSION,
        "mode": "LOADED",
        "load_policy": "BUILD_DEPLOY_STARTUP_ONLY",
        "trusted_in_process": True,
        "sandboxed": False,
        "sdk_api_version": SDK_API_VERSION,
        "registry_protocol_version": REGISTRY_PROTOCOL_VERSION,
        "catalog_fingerprint": catalog_fingerprint,
        "registry_resolution_fingerprint": resolution.resolution_fingerprint,
        "extension_set_fingerprint": extension_set_fingerprint,
        "extension_count": len(extension_references),
        "contribution_count": len(bindings),
        "extensions": extension_references,
        "resource_budget": {
            "invocation_timeout_ms": limits.invocation_timeout_ms,
            "startup_timeout_ms": limits.startup_timeout_ms,
        },
        "signature": {
            "algorithm": "HMAC-SHA256",
            "key_id": signature_key_id,
            "secret_embedded": False,
        },
    }
    registry = RuntimeExtensionRegistry(resolution=resolution, bindings=bindings)
    metrics = RuntimeExtensionMetrics(extension_set_fingerprint)
    return LoadedRuntimeExtensionAdapter(
        canonical_bytes=canonical_json_bytes(document),
        extension_set_reference_bytes=canonical_json_bytes(extension_set_reference),
        registry=registry,
        policy=policy,
        manifests=manifests,
        limits=limits,
        metrics=metrics,
    )


__all__ = [
    "LoadedRuntimeExtensionAdapter",
    "RuntimeExtensionBinding",
    "RuntimeExtensionMetrics",
    "RuntimeExtensionRegistry",
    "build_loaded_adapter",
    "invoke_trusted_extension",
]
