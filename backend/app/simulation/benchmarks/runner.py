"""P2 BenchmarkRunner over one formal Problem, Validator, and KPI boundary."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from copy import deepcopy
from enum import StrEnum
from hashlib import sha256
import json
import os
from pathlib import Path
from time import perf_counter
import tracemalloc
from typing import Any, Never, cast

from app.exporters import (
    EXPORT_PACKAGE_PROFILE,
    build_internal_export_package,
    verify_internal_export_package,
)
from app.planning.policy import simulation_delivery_policy, simulation_solve_limits
from app.planning.problem import PlanningProblemDocumentV2
from app.planning.reporting import (
    KPI_VERSION,
    build_kpi_v2,
    calculate_schedule_kpi_metrics,
)
from app.planning.strategies import GlobalCpSatStrategy
from app.simulation.baselines import (
    ALGORITHM_IDENTITIES,
    ReferenceAlgorithm,
    ReferenceSchedulerStatus,
)
from app.simulation.baselines.reference_schedulers import schedule_reference
from app.simulation.benchmarks.reporting import (
    BENCHMARK_BASELINE_VERSION,
    BENCHMARK_GENERATOR_ID,
    BENCHMARK_GENERATOR_VERSION,
    BENCHMARK_REPORT_VERSION,
    BENCHMARK_RUNNER_VERSION,
    CORRECTNESS_ASSEMBLER_ID,
    CORRECTNESS_ASSEMBLER_VERSION,
    PROFILE_SET_VERSION,
    SCHEMA_SET_VERSION,
    TASK_ID,
    THRESHOLD_POLICY_VERSION,
    BenchmarkContractError,
    BenchmarkContractErrorCode,
    BenchmarkProfile,
    aggregate_samples,
    capture_environment,
    generated_at_utc,
    load_baseline,
    load_profile_set,
    validate_baseline_document,
    validate_benchmark_report,
)
from app.simulation.scenarios.p2_correctness import (
    BLUEPRINT_VERSION,
    CONSTRAINT_IDS,
    EXPECTED_VERSION,
    MANIFEST_VERSION,
    CorrectnessCase,
    CorrectnessReplay,
    assignment_projection,
    execute_correctness_case,
    load_correctness_cases,
    verify_correctness_replay,
)


type JsonObject = dict[str, Any]

_UNAVAILABLE_CAPABILITIES = [
    "SECONDARY_CAPACITY",
    "SEQUENCE_DEPENDENT_SETUP",
    "BATCH_PROCESSING",
    "SPLIT_MERGE",
    "MATERIAL_COMPETITION",
    "PREEMPTIVE_OPERATION",
    "BUFFER_CAPACITY",
    "ALTERNATIVE_MATERIAL",
    "MULTI_FACTORY",
    "AI_DURATION_PREDICTION",
    "REALITY_CALIBRATION",
]


class BenchmarkExecutionErrorCode(StrEnum):
    CORRECTNESS_FAILURE = "BENCHMARK_CORRECTNESS_FAILURE"
    DETERMINISM_FAILURE = "BENCHMARK_DETERMINISM_FAILURE"
    KPI_MISMATCH = "BENCHMARK_KPI_MISMATCH"


class BenchmarkExecutionError(RuntimeError):
    """Hard failure that cannot be offset by runtime or memory improvement."""

    def __init__(
        self, code: BenchmarkExecutionErrorCode, *, field: str, message: str
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code.value}: {field}: {message}")


def _fail(code: BenchmarkExecutionErrorCode, field: str, message: str) -> Never:
    raise BenchmarkExecutionError(code, field=field, message=message)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _object_digest(value: object) -> str:
    return f"sha256:{sha256(_canonical_bytes(value)).hexdigest()}"


def _supported_capabilities(profile: BenchmarkProfile) -> list[str]:
    values = [
        "DAG_ROUTING",
        "ALTERNATIVE_RESOURCE",
        "MACHINE_CALENDAR",
        "RELEASE_AND_MATERIAL_GATE",
    ]
    if profile.workshop_count > 1:
        values.insert(0, "SINGLE_FACTORY_MULTI_WORKSHOP")
    return values


def _factory_profile(profile: BenchmarkProfile) -> JsonObject:
    supported = _supported_capabilities(profile)
    cross_ratio = 0.0 if profile.workshop_count == 1 else 1.0
    return {
        "profile_contract_version": "factory-profile.v1",
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "synthetic_only": True,
        "topology": {
            "workshop_count": {
                "minimum": profile.workshop_count,
                "maximum": profile.workshop_count,
            },
            "production_line_count": {
                "minimum": profile.workshop_count,
                "maximum": profile.workshop_count,
            },
        },
        "resources": {
            "target_count": {
                "minimum": profile.resource_count,
                "maximum": profile.resource_count,
            },
            "capacity_per_resource": 1,
            "capability_pool": supported,
        },
        "routing": {
            "operation_count": {
                "minimum": profile.operation_count,
                "maximum": profile.operation_count,
            },
            "candidate_resource_count": {
                "minimum": profile.candidate_resource_count,
                "maximum": profile.candidate_resource_count,
            },
            "routing_depth": {
                "minimum": profile.operations_per_order,
                "maximum": profile.operations_per_order,
            },
            "cross_workshop_ratio": {
                "minimum": cross_ratio,
                "maximum": cross_ratio,
            },
        },
        "calendar": {
            "pattern_ids": ["P2-BENCHMARK-DETERMINISTIC-CALENDAR"],
            "fragmentation_count": {
                "minimum": profile.calendar_fragment_count,
                "maximum": profile.calendar_fragment_count,
            },
        },
        "orders": {
            "order_count": {
                "minimum": profile.order_count,
                "maximum": profile.order_count,
            },
            "due_date_pressure_levels": ["high"],
        },
        "supported_capabilities": supported,
        "expected_rejections": list(_UNAVAILABLE_CAPABILITIES),
    }


def _scenario_spec(profile: BenchmarkProfile) -> JsonObject:
    ratio = round(1 / profile.material_delay_every, 12)
    return {
        "scenario_contract_version": "scenario-spec.v1",
        "scenario_id": f"P2-BENCHMARK-{profile.size}",
        "scenario_version": "1.0.0",
        "synthetic_only": True,
        "factory_profile": {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
        },
        "generator": {
            "generator_id": CORRECTNESS_ASSEMBLER_ID,
            "generator_version": CORRECTNESS_ASSEMBLER_VERSION,
        },
        "seed": profile.seed,
        "required_capabilities": _supported_capabilities(profile),
        "complexity": {
            "factory_size": profile.size,
            "routing_complexity": (
                "low" if profile.size == "XS" else "medium"
            ),
            "candidate_resource_density": "medium",
            "bottleneck_level": "medium",
            "due_date_pressure": "high",
            "calendar_fragmentation": (
                "low" if profile.size == "XS" else "medium"
            ),
            "material_delay_ratio": ratio,
            "wip_ratio": 0.0,
            "lock_ratio": 0.0,
            "cross_workshop_ratio": (
                0.0 if profile.workshop_count == 1 else 1.0
            ),
            "failure_frequency": "none",
        },
        "expected_behavior": {
            "allowed_results": ["OPTIMAL", "FEASIBLE"],
            "validator_status": "PASS",
        },
    }


def _resource_codes_by_workshop(profile: BenchmarkProfile) -> list[list[str]]:
    values: list[list[str]] = [[] for _ in range(profile.workshop_count)]
    for index in range(profile.resource_count):
        values[index % profile.workshop_count].append(f"R{index + 1:03d}")
    return values


def _blueprint(profile: BenchmarkProfile) -> JsonObject:
    resources_by_workshop = _resource_codes_by_workshop(profile)
    resources: list[JsonObject] = []
    for index in range(profile.resource_count):
        unavailable: list[JsonObject] = []
        if index < profile.calendar_fragment_count:
            start_tick = 20 + index * 7
            unavailable.append(
                {
                    "interval_code": f"MAINT-{index + 1:03d}",
                    "start_tick": start_tick,
                    "end_tick": start_tick + 2,
                    "reason": "P2_BENCHMARK_PLANNED_MAINTENANCE",
                }
            )
        resources.append(
            {
                "resource_code": f"R{index + 1:03d}",
                "workshop_code": f"W{index % profile.workshop_count + 1:02d}",
                "unavailable": unavailable,
            }
        )

    jobs: list[JsonObject] = []
    for job_index in range(profile.order_count):
        release_tick = job_index % 3
        material_ready_tick = (
            release_tick + 2
            if (job_index + 1) % profile.material_delay_every == 0
            else release_tick
        )
        operations: list[JsonObject] = []
        for operation_index in range(profile.operations_per_order):
            workshop_index = operation_index % profile.workshop_count
            workshop_resources = resources_by_workshop[workshop_index]
            candidates: list[JsonObject] = []
            for candidate_index in range(profile.candidate_resource_count):
                resource_index = (job_index + operation_index + candidate_index) % len(
                    workshop_resources
                )
                candidates.append(
                    {
                        "resource_code": workshop_resources[resource_index],
                        "duration_ticks": (
                            2 + (job_index + operation_index + candidate_index) % 4
                        ),
                    }
                )
            operations.append(
                {
                    "operation_code": f"O{operation_index + 1:02d}",
                    "candidates": candidates,
                }
            )
        edges: list[JsonObject] = []
        for operation_index in range(profile.operations_per_order - 1):
            predecessor_workshop = operation_index % profile.workshop_count
            successor_workshop = (operation_index + 1) % profile.workshop_count
            edges.append(
                {
                    "predecessor": f"O{operation_index + 1:02d}",
                    "successor": f"O{operation_index + 2:02d}",
                    "min_lag_ticks": 0,
                    "transport_lag_ticks": (
                        1 if predecessor_workshop != successor_workshop else 0
                    ),
                }
            )
        jobs.append(
            {
                "job_code": f"J{job_index + 1:03d}",
                "priority_weight": 1 + job_index % 4,
                "due_tick": (
                    profile.due_tick_base
                    + (job_index % 4) * profile.due_tick_stride
                ),
                "release_tick": release_tick,
                "material_ready_tick": material_ready_tick,
                "operations": operations,
                "edges": edges,
                "execution_facts": [],
                "locks": [],
            }
        )
    return {
        "blueprint_version": BLUEPRINT_VERSION,
        "scenario_id": f"P2-BENCHMARK-{profile.size}",
        "cutoff_at_utc": "2026-12-01T00:00:00Z",
        "tick_seconds": profile.tick_seconds,
        "horizon_ticks": profile.horizon_ticks,
        "resources": resources,
        "jobs": jobs,
    }


def _draft_expected(profile: BenchmarkProfile) -> JsonObject:
    return {
        "expected_outcome_version": EXPECTED_VERSION,
        "scenario_id": f"P2-BENCHMARK-{profile.size}",
        "solver_status": "FEASIBLE",
        "validator_status": "PASS",
        "objective_value": 0,
        "best_bound": 0,
        "relative_gap": 0.0,
        "assignments": [],
        "positive_constraint_ids": list(CONSTRAINT_IDS),
    }


def _manifest_template(root: Path) -> JsonObject:
    template = load_correctness_cases(root)[0].manifest
    return {
        "pipeline": deepcopy(template["pipeline"]),
        "policy": deepcopy(template["policy"]),
        "solver": deepcopy(template["solver"]),
    }


def _case(
    profile: BenchmarkProfile,
    *,
    root: Path,
    expected: JsonObject | None = None,
    expected_artifacts: JsonObject | None = None,
) -> CorrectnessCase:
    factory_profile = _factory_profile(profile)
    scenario = _scenario_spec(profile)
    blueprint = _blueprint(profile)
    outcome = _draft_expected(profile) if expected is None else expected
    template = _manifest_template(root)
    manifest: JsonObject = {
        "correctness_manifest_version": MANIFEST_VERSION,
        "scenario": {
            "scenario_id": scenario["scenario_id"],
            "scenario_version": scenario["scenario_version"],
        },
        "factory_profile": {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
        },
        "assembler": {
            "generator_id": CORRECTNESS_ASSEMBLER_ID,
            "generator_version": CORRECTNESS_ASSEMBLER_VERSION,
        },
        "seed": profile.seed,
        "asset_hashes": {
            "factory_profile": _object_digest(factory_profile),
            "scenario_spec": _object_digest(scenario),
            "scenario_blueprint": _object_digest(blueprint),
            "expected_outcome": _object_digest(outcome),
        },
        "pipeline": template["pipeline"],
        "policy": template["policy"],
        "solver": template["solver"],
        "expected_artifacts": {} if expected_artifacts is None else expected_artifacts,
    }
    return CorrectnessCase(
        profile=factory_profile,
        scenario=scenario,
        blueprint=blueprint,
        manifest=manifest,
        expected=outcome,
        asset_paths=(),
    )


def generate_benchmark_case(profile: BenchmarkProfile, *, root: Path) -> CorrectnessCase:
    """Generate one deterministic, self-hashed profile/scenario/blueprint bundle."""

    return _case(profile, root=root)


def _materialize_case(
    profile: BenchmarkProfile, *, root: Path
) -> tuple[CorrectnessReplay, float, float]:
    draft_started = perf_counter()
    draft_replay = execute_correctness_case(
        generate_benchmark_case(profile, root=root),
        root=root,
        verify_manifest_hashes=True,
    )
    draft_seconds = perf_counter() - draft_started
    stage = cast(list[JsonObject], draft_replay.solution["objective_stage_results"])[0]
    expected = {
        "expected_outcome_version": EXPECTED_VERSION,
        "scenario_id": draft_replay.case.scenario_id,
        "solver_status": draft_replay.solution["solver_status"],
        "validator_status": draft_replay.validation_report["status"],
        "objective_value": stage["objective_value"],
        "best_bound": stage["best_bound"],
        "relative_gap": stage["relative_gap"],
        "assignments": assignment_projection(draft_replay),
        "positive_constraint_ids": list(CONSTRAINT_IDS),
    }
    expected_artifacts = {
        "import_dataset_hash": draft_replay.import_dataset_hash,
        "snapshot_hash": draft_replay.snapshot_hash,
        "problem_hash": draft_replay.problem["problem_hash"],
    }
    final_case = _case(
        profile,
        root=root,
        expected=expected,
        expected_artifacts=expected_artifacts,
    )
    final_started = perf_counter()
    replay = execute_correctness_case(
        final_case,
        root=root,
        verify_manifest_hashes=True,
    )
    source_to_problem_seconds = perf_counter() - final_started
    verify_correctness_replay(replay, verify_artifact_hashes=True)
    return replay, draft_seconds, source_to_problem_seconds


def _code_commit() -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    if value == "uncommitted" or (
        len(value) == 40 and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return "uncommitted"


def _assignment_fingerprint(assignments: Sequence[Mapping[str, object]]) -> str:
    stable = sorted(
        (dict(assignment) for assignment in assignments),
        key=lambda value: cast(str, value["operation_id"]),
    )
    return _object_digest(stable)


def _require_global_candidate(result: object, field: str) -> None:
    solution = cast(Any, result).solution
    validation = cast(Any, result).validation_report
    if solution["solver_status"] not in {"OPTIMAL", "FEASIBLE"}:
        _fail(
            BenchmarkExecutionErrorCode.CORRECTNESS_FAILURE,
            field,
            f"Global status was {solution['solver_status']}",
        )
    if validation is None or validation["status"] != "PASS":
        _fail(
            BenchmarkExecutionErrorCode.CORRECTNESS_FAILURE,
            field,
            "Global candidate lacks fresh formal Validator PASS",
        )


def _global_measurements(
    replay: CorrectnessReplay, profile: BenchmarkProfile
) -> tuple[JsonObject, object]:
    problem = cast(PlanningProblemDocumentV2, replay.problem)
    policy = simulation_delivery_policy()

    def solve(run_label: str) -> object:
        limits = simulation_solve_limits(
            limits_id=f"LIMITS-P2-BENCHMARK-{profile.size}-{run_label}",
            limits_revision="1.0.0",
            source_record_id=f"LIMITS-P2-BENCHMARK-{profile.size}-{run_label}",
            max_wall_time_seconds=profile.max_wall_time_seconds,
            max_workers=1,
            random_seed=profile.seed,
        )
        result = GlobalCpSatStrategy().solve(
            problem,
            policy,
            limits,
            planning_run_id=f"RUN-P2-BENCHMARK-{profile.size}-{run_label}",
            code_commit=_code_commit(),
        )
        _require_global_candidate(result, f"global.{run_label}")
        return result

    for index in range(profile.warmup_runs):
        solve(f"WARMUP-{index + 1:02d}")

    samples: list[object] = []
    fingerprints: list[str] = []
    kpi_fingerprints: list[str] = []
    timing_samples: defaultdict[str, list[float]] = defaultdict(list)
    memory_samples: list[float] = []
    quality_values: list[tuple[object, ...]] = []
    model_values: list[JsonObject] = []
    for index in range(profile.measured_runs):
        result = solve(f"MEASURED-{index + 1:02d}")
        samples.append(result)
        solution = cast(JsonObject, cast(Any, result).solution)
        report = cast(JsonObject, cast(Any, result).solver_report)
        validation = cast(JsonObject, cast(Any, result).validation_report)
        assignments = cast(list[Mapping[str, object]], solution["assignments"])
        shared = calculate_schedule_kpi_metrics(replay.problem, assignments)
        immutable_kpi = build_kpi_v2(
            snapshot=replay.snapshot_document,
            problem=replay.problem,
            solution=solution,
            solver_report=report,
            validation_report=validation,
            import_quality_report=replay.quality_report,
        )
        kpi = immutable_kpi.document
        if (
            kpi["delivery"] != shared.delivery_document
            or kpi["planning"] != shared.planning_document
            or kpi["resources"] != shared.resource_documents
        ):
            _fail(
                BenchmarkExecutionErrorCode.KPI_MISMATCH,
                "global.kpi",
                "KPI v2 differs from the shared schedule calculation",
            )
        fingerprints.append(_assignment_fingerprint(assignments))
        kpi_fingerprints.append(immutable_kpi.fingerprint)
        timings = cast(JsonObject, report["timings"])
        for name in (
            "model_build_seconds",
            "first_feasible_seconds",
            "solve_seconds",
            "validation_seconds",
            "total_seconds",
        ):
            value = timings[name]
            if value is None:
                _fail(
                    BenchmarkExecutionErrorCode.CORRECTNESS_FAILURE,
                    f"global.timings.{name}",
                    "candidate timing cannot be null",
                )
            timing_samples[name].append(float(value))
        memory_samples.append(float(report["memory_peak_mb"]))
        stage = cast(list[JsonObject], solution["objective_stage_results"])[0]
        quality_values.append(
            (
                stage["objective_value"],
                stage["best_bound"],
                stage["relative_gap"],
                shared.priority_weighted_tardiness_seconds,
                shared.makespan_seconds,
            )
        )
        model_values.append(cast(JsonObject, report["model_metrics"]))
    if len(set(fingerprints)) != 1 or len(set(quality_values)) != 1:
        _fail(
            BenchmarkExecutionErrorCode.DETERMINISM_FAILURE,
            "global.measured_runs",
            "assignments or quality changed across measured repetitions",
        )
    if any(value != model_values[0] for value in model_values[1:]):
        _fail(
            BenchmarkExecutionErrorCode.DETERMINISM_FAILURE,
            "global.model_metrics",
            "model metrics changed across repetitions",
        )
    representative = cast(Any, samples[0])
    representative_report = cast(JsonObject, representative.solver_report)
    representative_solution = cast(JsonObject, representative.solution)
    representative_validation = cast(JsonObject, representative.validation_report)
    shared = calculate_schedule_kpi_metrics(
        replay.problem,
        cast(list[Mapping[str, object]], representative_solution["assignments"]),
    )
    stage = cast(
        list[JsonObject], representative_solution["objective_stage_results"]
    )[0]
    delivery = shared.delivery_document
    return (
        {
            "strategy_id": "global-cp-sat",
            "strategy_version": "global-cp-sat-strategy.v1",
            "solver": {
                key: cast(JsonObject, representative_report["solver"])[key]
                for key in (
                    "backend_id",
                    "backend_version",
                    "solver_name",
                    "solver_version",
                )
            },
            "parameters": cast(JsonObject, representative_report["solver"])[
                "parameters"
            ],
            "status": representative_solution["solver_status"],
            "model_metrics": model_values[0],
            "timings": {
                "model_build_seconds": aggregate_samples(
                    timing_samples["model_build_seconds"]
                ),
                "first_solution_seconds": aggregate_samples(
                    timing_samples["first_feasible_seconds"]
                ),
                "solve_seconds": aggregate_samples(timing_samples["solve_seconds"]),
                "validation_seconds": aggregate_samples(
                    timing_samples["validation_seconds"]
                ),
                "total_seconds": aggregate_samples(timing_samples["total_seconds"]),
            },
            "memory_peak_mb": aggregate_samples(memory_samples),
            "quality": {
                "objective": stage["objective_value"],
                "best_bound": stage["best_bound"],
                "relative_gap": stage["relative_gap"],
                "weighted_tardiness_seconds": (
                    shared.priority_weighted_tardiness_seconds
                ),
                "makespan_seconds": shared.makespan_seconds,
                "on_time_order_ratio": delivery["on_time_order_ratio"],
                "solver_kpi_matches": True,
            },
            "validation": {
                "status": representative_validation["status"],
                "validation_report_version": representative_validation[
                    "validation_report_version"
                ],
                "pass_count": profile.measured_runs,
                "fresh_formal": True,
            },
            "sample_fingerprints": fingerprints,
            "kpi_fingerprints": kpi_fingerprints,
        },
        representative,
    )


def _measure_reference(
    problem: PlanningProblemDocumentV2, algorithm: ReferenceAlgorithm
) -> tuple[JsonObject, float, float]:
    owns_trace = not tracemalloc.is_tracing()
    if owns_trace:
        tracemalloc.start()
    baseline_current = tracemalloc.get_traced_memory()[0]
    started = perf_counter()
    try:
        result = cast(JsonObject, schedule_reference(problem, algorithm))
        total_seconds = max(perf_counter() - started, 0.000000001)
        _, peak = tracemalloc.get_traced_memory()
        memory_peak_mb = max(peak - baseline_current, 0) / (1024 * 1024)
    finally:
        if owns_trace:
            tracemalloc.stop()
    return result, total_seconds, memory_peak_mb


def _require_reference_candidate(
    result: JsonObject, algorithm: ReferenceAlgorithm, field: str
) -> tuple[JsonObject, JsonObject]:
    if result["status"] != ReferenceSchedulerStatus.FEASIBLE:
        _fail(
            BenchmarkExecutionErrorCode.CORRECTNESS_FAILURE,
            field,
            f"{algorithm.value} returned {result['status']}",
        )
    candidate = result["candidate"]
    validation = result["validation_report"]
    if not isinstance(candidate, dict) or not isinstance(validation, dict):
        _fail(
            BenchmarkExecutionErrorCode.CORRECTNESS_FAILURE,
            field,
            "Reference candidate or validation evidence is absent",
        )
    if validation["status"] != "PASS":
        _fail(
            BenchmarkExecutionErrorCode.CORRECTNESS_FAILURE,
            field,
            "Reference candidate lacks fresh formal Validator PASS",
        )
    return cast(JsonObject, candidate), cast(JsonObject, validation)


def _reference_measurements(
    replay: CorrectnessReplay, profile: BenchmarkProfile
) -> list[JsonObject]:
    problem = cast(PlanningProblemDocumentV2, replay.problem)
    rows: list[JsonObject] = []
    for algorithm in ReferenceAlgorithm:
        for index in range(profile.warmup_runs):
            warmup, _, _ = _measure_reference(problem, algorithm)
            _require_reference_candidate(
                warmup, algorithm, f"references.{algorithm.value}.warmup[{index}]"
            )
        results: list[JsonObject] = []
        internal_samples: list[float] = []
        total_samples: list[float] = []
        memory_samples: list[float] = []
        fingerprints: list[str] = []
        quality_values: list[tuple[int, int, object]] = []
        representative_validation: JsonObject | None = None
        representative_shared = None
        for index in range(profile.measured_runs):
            result, total_seconds, memory_peak_mb = _measure_reference(
                problem, algorithm
            )
            candidate, validation = _require_reference_candidate(
                result,
                algorithm,
                f"references.{algorithm.value}.measured[{index}]",
            )
            assignments = cast(list[Mapping[str, object]], candidate["assignments"])
            shared = calculate_schedule_kpi_metrics(replay.problem, assignments)
            metrics = cast(JsonObject, result["metrics"])
            if (
                metrics["weighted_tardiness_seconds"]
                != shared.priority_weighted_tardiness_seconds
                or metrics["makespan_seconds"] != shared.makespan_seconds
            ):
                _fail(
                    BenchmarkExecutionErrorCode.KPI_MISMATCH,
                    f"references.{algorithm.value}.metrics",
                    "P2-10 carrier differs from the shared schedule KPI calculation",
                )
            results.append(result)
            internal_samples.append(float(metrics["runtime_seconds"]))
            total_samples.append(total_seconds)
            memory_samples.append(memory_peak_mb)
            fingerprints.append(_assignment_fingerprint(assignments))
            quality_values.append(
                (
                    shared.priority_weighted_tardiness_seconds,
                    shared.makespan_seconds,
                    shared.delivery_document["on_time_order_ratio"],
                )
            )
            representative_validation = validation
            representative_shared = shared
        if len(set(fingerprints)) != 1 or len(set(quality_values)) != 1:
            _fail(
                BenchmarkExecutionErrorCode.DETERMINISM_FAILURE,
                f"references.{algorithm.value}.measured_runs",
                "assignments or quality changed across measured repetitions",
            )
        assert representative_validation is not None
        assert representative_shared is not None
        rows.append(
            {
                "algorithm": algorithm.value,
                "algorithm_id": ALGORITHM_IDENTITIES[algorithm].algorithm_id,
                "status": ReferenceSchedulerStatus.FEASIBLE.value,
                "non_production": True,
                "optimality_claim": "NONE",
                "timings": {
                    "internal_runtime_seconds": aggregate_samples(internal_samples),
                    "total_seconds": aggregate_samples(total_samples),
                },
                "memory_peak_mb": aggregate_samples(memory_samples),
                "quality": {
                    "weighted_tardiness_seconds": (
                        representative_shared.priority_weighted_tardiness_seconds
                    ),
                    "makespan_seconds": representative_shared.makespan_seconds,
                    "on_time_order_ratio": representative_shared.delivery_document[
                        "on_time_order_ratio"
                    ],
                    "shared_kpi_matches": True,
                },
                "validation": {
                    "status": representative_validation["status"],
                    "validation_report_version": representative_validation[
                        "validation_report_version"
                    ],
                    "pass_count": profile.measured_runs,
                    "fresh_formal": True,
                },
                "deterministic_replay": True,
                "sample_fingerprints": fingerprints,
            }
        )
    return rows


def _routing_depth(problem: JsonObject) -> int:
    operations = cast(list[JsonObject], problem["operation_instances"])
    operation_ids = {cast(str, operation["operation_id"]) for operation in operations}
    outgoing: defaultdict[str, list[str]] = defaultdict(list)
    incoming: defaultdict[str, int] = defaultdict(int)
    for edge in cast(list[JsonObject], problem["precedence_edges"]):
        predecessor = cast(str, edge["predecessor_operation_id"])
        successor = cast(str, edge["successor_operation_id"])
        outgoing[predecessor].append(successor)
        incoming[successor] += 1
    ready = deque(sorted(operation_id for operation_id in operation_ids if incoming[operation_id] == 0))
    depths = {operation_id: 1 for operation_id in ready}
    visited = 0
    while ready:
        operation_id = ready.popleft()
        visited += 1
        for successor in sorted(outgoing[operation_id]):
            depths[successor] = max(depths.get(successor, 1), depths[operation_id] + 1)
            incoming[successor] -= 1
            if incoming[successor] == 0:
                ready.append(successor)
    if visited != len(operation_ids):
        _fail(
            BenchmarkExecutionErrorCode.CORRECTNESS_FAILURE,
            "problem.precedence_edges",
            "routing graph is cyclic",
        )
    return max(depths.values(), default=0)


def _complexity_metrics(replay: CorrectnessReplay, representative: object) -> JsonObject:
    problem = replay.problem
    operations = cast(list[JsonObject], problem["operation_instances"])
    resources = cast(list[JsonObject], problem["resources"])
    resource_workshops = {
        cast(str, resource["resource_id"]): cast(str, resource["workshop_id"])
        for resource in resources
    }
    operation_workshops = {
        cast(str, operation["operation_id"]): {
            resource_workshops[cast(str, option["resource_id"])]
            for option in cast(list[JsonObject], operation["resource_options"])
        }
        for operation in operations
    }
    edges = cast(list[JsonObject], problem["precedence_edges"])
    cross_edges = sum(
        1
        for edge in edges
        if operation_workshops[cast(str, edge["predecessor_operation_id"])]
        .isdisjoint(operation_workshops[cast(str, edge["successor_operation_id"])])
    )
    material_delayed = sum(
        1
        for operation in operations
        if cast(str, operation["material_ready_at_utc"])
        > cast(str, operation["release_at_utc"])
    )
    running = sum(1 for operation in operations if operation["status"] == "RUNNING")
    locks = cast(list[JsonObject], problem["operation_locks"])
    hard_locks = sum(1 for lock in locks if lock["lock_type"] == "HARD_LOCK")
    assignments = cast(
        list[Mapping[str, object]], cast(Any, representative).solution["assignments"]
    )
    shared = calculate_schedule_kpi_metrics(problem, assignments)
    utilizations = [
        cast(float, row["utilization"])
        for row in shared.resource_rows
        if row["utilization"] is not None
    ]
    candidate_count = sum(
        len(cast(list[object], operation["resource_options"]))
        for operation in operations
    )
    operation_count = len(operations)
    snapshot_counts = cast(JsonObject, replay.snapshot_document["entity_counts"])
    return {
        "order_count": len(cast(list[object], problem["delivery_demands"])),
        "lot_count": snapshot_counts["production_lots"],
        "operation_count": operation_count,
        "precedence_edge_count": len(edges),
        "resource_count": len(resources),
        "candidate_option_count": candidate_count,
        "average_candidate_resource_count": round(
            candidate_count / operation_count, 12
        ),
        "calendar_fragment_count": len(
            cast(list[object], problem["resource_unavailable_intervals"])
        ),
        "historical_anchor_count": len(
            cast(list[object], problem["historical_completion_anchors"])
        ),
        "hard_lock_count": hard_locks,
        "routing_depth": _routing_depth(problem),
        "cross_workshop_ratio": (
            0.0 if not edges else round(cross_edges / len(edges), 12)
        ),
        "material_delay_ratio": (
            0.0
            if not operations
            else round(material_delayed / operation_count, 12)
        ),
        "wip_ratio": 0.0 if not operations else round(running / operation_count, 12),
        "lock_ratio": (
            0.0 if not operations else round(hard_locks / operation_count, 12)
        ),
        "bottleneck_utilization": max(utilizations, default=0.0),
        "horizon_ticks": (
            profile_horizon_ticks(problem)
        ),
    }


def profile_horizon_ticks(problem: Mapping[str, object]) -> int:
    from app.domain.types import parse_utc_instant

    start = parse_utc_instant(cast(str, problem["horizon_start_utc"]))
    end = parse_utc_instant(cast(str, problem["horizon_end_utc"]))
    seconds = int((end - start).total_seconds())
    return seconds // cast(int, problem["tick_seconds"])


def _baseline_evaluation(
    *,
    profile: BenchmarkProfile,
    baseline: JsonObject | None,
    environment: JsonObject,
    problem_hash: str,
    complexity: JsonObject,
    pipeline_seconds: float,
    global_row: JsonObject,
    reference_rows: list[JsonObject],
) -> tuple[JsonObject, list[JsonObject]]:
    if baseline is None:
        return (
            {
                "benchmark_baseline_version": None,
                "path": profile.baseline_path,
                "status": "NOT_COMPARED_INITIAL_CAPTURE",
                "environment_comparable": False,
                "checks": ["initial-baseline-pending"],
            },
            [],
        )
    validate_baseline_document(baseline)
    expected_profile = {
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "size": profile.size,
    }
    if baseline["profile"] != expected_profile:
        raise BenchmarkContractError(
            BenchmarkContractErrorCode.BASELINE_DRIFT,
            field="baseline.profile",
            message="immutable baseline/profile identity differs",
        )
    baseline_problem = cast(JsonObject, baseline["problem"])
    if baseline_problem["problem_hash"] != problem_hash:
        raise BenchmarkContractError(
            BenchmarkContractErrorCode.BASELINE_DRIFT,
            field="baseline.problem.problem_hash",
            message="deterministic generator or formal pipeline drifted",
        )
    if baseline_problem["complexity"] != complexity:
        raise BenchmarkContractError(
            BenchmarkContractErrorCode.BASELINE_DRIFT,
            field="baseline.problem.complexity",
            message="complexity cardinality drifted",
        )
    baseline_environment = cast(JsonObject, baseline["environment"])
    comparable = (
        baseline_environment["environment_signature"]
        == environment["environment_signature"]
    )
    ceilings = cast(JsonObject, baseline["ceilings"])
    observed = cast(JsonObject, baseline["observed"])
    observed_global = cast(JsonObject, observed["global"])
    warnings: list[JsonObject] = []

    def warning(code: str, message: str) -> None:
        warnings.append({"code": code, "severity": "WARNING", "message": message})

    global_timings = cast(JsonObject, global_row["timings"])
    global_memory = cast(JsonObject, global_row["memory_peak_mb"])
    global_quality = cast(JsonObject, global_row["quality"])
    reference_p95 = max(
        float(cast(JsonObject, cast(JsonObject, row["timings"])["total_seconds"])["p95"])
        for row in reference_rows
    )
    ceiling_values = {
        "pipeline_seconds": pipeline_seconds,
        "global_total_seconds_p95": float(
            cast(JsonObject, global_timings["total_seconds"])["p95"]
        ),
        "global_memory_peak_mb_p95": float(global_memory["p95"]),
        "reference_total_seconds_p95": reference_p95,
    }
    for name, observed_value in ceiling_values.items():
        if observed_value > float(ceilings[name]):
            warning(
                "BENCHMARK_CEILING_EXCEEDED",
                f"{name}={observed_value} exceeded development ceiling={ceilings[name]}",
            )
    if comparable:
        factor = float(ceilings["same_environment_regression_factor"])
        comparisons = {
            "global_solve_seconds_median": (
                float(cast(JsonObject, global_timings["solve_seconds"])["median"]),
                float(observed_global["solve_seconds_median"]),
            ),
            "global_total_seconds_p95": (
                float(cast(JsonObject, global_timings["total_seconds"])["p95"]),
                float(observed_global["total_seconds_p95"]),
            ),
            "global_memory_peak_mb_p95": (
                float(global_memory["p95"]),
                float(observed_global["memory_peak_mb_p95"]),
            ),
        }
        for name, (current, previous) in comparisons.items():
            if previous > 0 and current > previous * factor:
                warning(
                    "BENCHMARK_SAME_ENVIRONMENT_REGRESSION",
                    f"{name} regressed by more than factor {factor}",
                )
    if (
        global_quality["objective"] != observed_global["objective"]
        or global_quality["best_bound"] != observed_global["best_bound"]
    ):
        warning(
            "BENCHMARK_QUALITY_DRIFT",
            "Global objective or best bound differs from the immutable same-Problem baseline",
        )
    observed_reference_quality = cast(JsonObject, observed["reference_quality"])
    current_reference_quality = {
        cast(str, row["algorithm"]): cast(JsonObject, row["quality"])[
            "weighted_tardiness_seconds"
        ]
        for row in reference_rows
    }
    if current_reference_quality != observed_reference_quality:
        warning(
            "BENCHMARK_QUALITY_DRIFT",
            "Reference quality differs from the immutable same-Problem baseline",
        )
    return (
        {
            "benchmark_baseline_version": BENCHMARK_BASELINE_VERSION,
            "path": profile.baseline_path,
            "status": "PASS" if not warnings else "PASS_WITH_WARNINGS",
            "environment_comparable": comparable,
            "checks": [
                "profile-identity",
                "problem-hash",
                "complexity-cardinality",
                "development-ceilings",
                "same-environment-relative-comparison"
                if comparable
                else "cross-environment-relative-comparison-skipped",
            ],
        },
        warnings,
    )


def compare_scheduler_quality(
    global_row: JsonObject, reference_rows: list[JsonObject]
) -> tuple[JsonObject, list[JsonObject]]:
    global_quality = cast(JsonObject, global_row["quality"])
    objectives = {
        cast(str, row["algorithm"]): cast(int, cast(JsonObject, row["quality"])["weighted_tardiness_seconds"])
        for row in reference_rows
    }
    best_value = min(objectives.values())
    best_algorithms = sorted(
        algorithm for algorithm, value in objectives.items() if value == best_value
    )
    global_value = cast(int, global_quality["weighted_tardiness_seconds"])
    worse = global_value > best_value
    warnings: list[JsonObject] = []
    if worse:
        warnings.append(
            {
                "code": "BENCHMARK_WARNING",
                "severity": "WARNING",
                "message": (
                    "Global CP-SAT weighted tardiness is worse than the best "
                    "deterministic Reference Scheduler on the same Problem"
                ),
            }
        )
    return (
        {
            "same_problem_hash": True,
            "same_formal_validator": True,
            "same_schedule_kpi": "calculate_schedule_kpi_metrics.v1",
            "global_weighted_tardiness_seconds": global_value,
            "best_reference_weighted_tardiness_seconds": best_value,
            "best_reference_algorithms": best_algorithms,
            "global_minus_best_reference_seconds": global_value - best_value,
            "global_worse_than_best_reference": worse,
            "warning_code": "BENCHMARK_WARNING" if worse else None,
        },
        warnings,
    )


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def run_benchmark_profile(
    *,
    root: Path,
    profile: BenchmarkProfile,
    baseline: JsonObject | None,
) -> JsonObject:
    """Execute one XS/S/M profile and return a strict successful report."""

    environment = capture_environment()
    replay, materialization_seconds, source_to_problem_seconds = _materialize_case(
        profile, root=root
    )
    global_row, representative = _global_measurements(replay, profile)
    reference_rows = _reference_measurements(replay, profile)
    complexity = _complexity_metrics(replay, representative)

    export_started = perf_counter()
    package = build_internal_export_package(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
        scenario_manifest=replay.case.manifest,
    )
    verify_internal_export_package(package)
    kpi_export_seconds = perf_counter() - export_started
    initial_kpi = build_kpi_v2(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
    )
    comparison, comparison_warnings = compare_scheduler_quality(
        global_row, reference_rows
    )
    baseline_summary, baseline_warnings = _baseline_evaluation(
        profile=profile,
        baseline=baseline,
        environment=environment,
        problem_hash=cast(str, replay.problem["problem_hash"]),
        complexity=complexity,
        pipeline_seconds=source_to_problem_seconds,
        global_row=global_row,
        reference_rows=reference_rows,
    )
    warnings = [*comparison_warnings, *baseline_warnings]
    checks = [
        _pass(
            "strict-versioned-xs-s-m-profile-and-generator",
            {
                "profile": profile.name,
                "profile_version": profile.profile_version,
                "generator_version": BENCHMARK_GENERATOR_VERSION,
            },
        ),
        _pass(
            "formal-source-ingress-problem-and-expected-replay",
            {
                "scenario_id": replay.case.scenario_id,
                "import_dataset_hash": replay.import_dataset_hash,
                "snapshot_hash": replay.snapshot_hash,
                "problem_hash": replay.problem["problem_hash"],
            },
        ),
        _pass("problem-complexity-and-model-cardinality", complexity),
        _pass(
            "global-cp-sat-warmup-repetition-validator-and-kpi",
            {
                "warmups": profile.warmup_runs,
                "measured": profile.measured_runs,
                "status": global_row["status"],
                "validation": global_row["validation"],
            },
        ),
        _pass(
            "five-reference-warmup-repetition-validator-and-shared-kpi",
            {
                "algorithms": [row["algorithm"] for row in reference_rows],
                "measured_per_algorithm": profile.measured_runs,
            },
        ),
        _pass(
            "deterministic-assignment-and-quality-replays",
            {
                "global": len(set(cast(list[str], global_row["sample_fingerprints"])))
                == 1,
                "references": all(row["deterministic_replay"] for row in reference_rows),
            },
        ),
        _pass(
            "kpi-v2-and-p2-internal-export-regression",
            {
                "kpi_version": KPI_VERSION,
                "kpi_fingerprint": initial_kpi.fingerprint,
                "package_profile": EXPORT_PACKAGE_PROFILE,
                "package_id": package.package_id,
                "manifest_fingerprint": package.manifest_fingerprint,
            },
        ),
        _pass(
            "immutable-baseline-warning-and-non-production-boundary",
            {
                "baseline_status": baseline_summary["status"],
                "warning_count": len(warnings),
                "production_sla": "NOT_ESTABLISHED_OPEN_012",
            },
        ),
    ]
    manifest = package.manifest
    report: JsonObject = {
        "benchmark_report_version": BENCHMARK_REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": _code_commit(),
        "profile_set_version": PROFILE_SET_VERSION,
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
        "generated_at_utc": generated_at_utc(),
        "profile": {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "size": profile.size,
            "seed": profile.seed,
            "warmup_runs": profile.warmup_runs,
            "measured_runs": profile.measured_runs,
            "baseline_path": profile.baseline_path,
        },
        "scenario": {
            "scenario_id": replay.case.scenario_id,
            "scenario_version": replay.case.scenario["scenario_version"],
            "synthetic_only": True,
        },
        "generator": {
            "generator_id": BENCHMARK_GENERATOR_ID,
            "generator_version": BENCHMARK_GENERATOR_VERSION,
        },
        "assembler": {
            "generator_id": CORRECTNESS_ASSEMBLER_ID,
            "generator_version": CORRECTNESS_ASSEMBLER_VERSION,
        },
        "pipeline": {
            "versions": replay.case.manifest["pipeline"],
            "case_materialization_seconds": round(materialization_seconds, 9),
            "source_to_problem_seconds": round(source_to_problem_seconds, 9),
            "kpi_export_seconds": round(kpi_export_seconds, 9),
            "kpi_version": KPI_VERSION,
            "export_package_profile": EXPORT_PACKAGE_PROFILE,
            "export_package_id": package.package_id,
            "export_manifest_fingerprint": package.manifest_fingerprint,
            "export_file_count": manifest["file_count"],
        },
        "problem": {
            "problem_version": replay.problem["problem_version"],
            "problem_builder_version": replay.problem["problem_builder_version"],
            "problem_hash_projection_version": replay.problem[
                "problem_hash_projection_version"
            ],
            "problem_hash": replay.problem["problem_hash"],
            "snapshot_id": replay.problem["snapshot_id"],
            "snapshot_hash": replay.snapshot_hash,
            "tick_seconds": replay.problem["tick_seconds"],
            "horizon_start_utc": replay.problem["horizon_start_utc"],
            "horizon_end_utc": replay.problem["horizon_end_utc"],
            "complexity": complexity,
        },
        "environment": environment,
        "execution": {
            "warmups_complete": True,
            "warmup_runs_per_scheduler": profile.warmup_runs,
            "measured_runs_per_scheduler": profile.measured_runs,
            "global_scheduler_count": 1,
            "reference_scheduler_count": len(reference_rows),
            "correctness_replay_verified": True,
            "deterministic_replays": True,
        },
        "global_solver": global_row,
        "reference_schedulers": reference_rows,
        "comparison": comparison,
        "baseline": baseline_summary,
        "checks": checks,
        "check_count": len(checks),
        "warnings": warnings,
        "boundaries": {
            "data_plane": "SIMULATION_ONLY",
            "profiles": "XS_S_M_ONLY",
            "l_xl": "DEFERRED_RELEASE_OR_DEDICATED_ENVIRONMENT",
            "production_capacity_sla": "NOT_ESTABLISHED_OPEN_012",
            "historical_production_baseline": "NOT_AVAILABLE_OPEN_011",
            "approval_publish_external_transfer": "PROHIBITED",
            "p2_13_p2_14_p3": "NOT_STARTED",
        },
    }
    validate_benchmark_report(report)
    return report


def run_benchmark(
    *, root: Path, profile_name: str, require_baseline: bool = True
) -> JsonObject:
    profile_set = load_profile_set(root / "benchmarks" / "profiles.yaml")
    profile = profile_set.select(profile_name)
    baseline_path = root / Path(profile.baseline_path)
    baseline = load_baseline(baseline_path) if require_baseline else None
    return run_benchmark_profile(root=root, profile=profile, baseline=baseline)


__all__ = [
    "BenchmarkExecutionError",
    "BenchmarkExecutionErrorCode",
    "compare_scheduler_quality",
    "generate_benchmark_case",
    "profile_horizon_ticks",
    "run_benchmark",
    "run_benchmark_profile",
]
