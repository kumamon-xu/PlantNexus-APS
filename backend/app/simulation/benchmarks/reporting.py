"""Strict internal contracts for P2 synthetic benchmark profiles and evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from statistics import median
from typing import Any, Never, cast

import yaml

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat import ORTOOLS_VERSION
from app.simulation.baselines import ALGORITHM_IDENTITIES, ReferenceAlgorithm


PROFILE_SET_VERSION = "benchmark-profile-set.v1"
BENCHMARK_RUNNER_VERSION = "benchmark-runner.v1"
BENCHMARK_REPORT_VERSION = "benchmark-report.v1"
BENCHMARK_BASELINE_VERSION = "benchmark-baseline.v1"
THRESHOLD_POLICY_VERSION = "benchmark-threshold-policy.p2-development.v1"
BENCHMARK_GENERATOR_ID = "PLANTNEXUS-P2-BENCHMARK-GENERATOR"
BENCHMARK_GENERATOR_VERSION = "1.0.0"
CORRECTNESS_ASSEMBLER_ID = "PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER"
CORRECTNESS_ASSEMBLER_VERSION = "1.0.0"
TASK_ID = "TASK-P2-12"
SCHEMA_SET_VERSION = "2.5.0"

type JsonObject = dict[str, Any]

_PROFILE_NAMES = ("xs", "s", "m")
_SIZE_BY_NAME = {"xs": "XS", "s": "S", "m": "M"}
_PROFILE_SET_KEYS = {
    "profile_set_version",
    "task_id",
    "schema_set_version",
    "runner_version",
    "report_version",
    "threshold_policy_version",
    "generator",
    "assembler",
    "profiles",
}
_PROFILE_KEYS = {
    "profile_id",
    "profile_version",
    "size",
    "seed",
    "tick_seconds",
    "horizon_ticks",
    "workshop_count",
    "resource_count",
    "order_count",
    "operations_per_order",
    "candidate_resource_count",
    "calendar_fragment_count",
    "material_delay_every",
    "due_tick_base",
    "due_tick_stride",
    "max_wall_time_seconds",
    "warmup_runs",
    "measured_runs",
    "baseline_path",
}
_REFERENCE_KEYS = {algorithm.value for algorithm in ReferenceAlgorithm}
_REFERENCE_IDS = {
    algorithm.value: ALGORITHM_IDENTITIES[algorithm].algorithm_id
    for algorithm in ReferenceAlgorithm
}
COMPLEXITY_KEYS = {
    "order_count",
    "lot_count",
    "operation_count",
    "precedence_edge_count",
    "resource_count",
    "candidate_option_count",
    "average_candidate_resource_count",
    "calendar_fragment_count",
    "historical_anchor_count",
    "hard_lock_count",
    "routing_depth",
    "cross_workshop_ratio",
    "material_delay_ratio",
    "wip_ratio",
    "lock_ratio",
    "bottleneck_utilization",
    "horizon_ticks",
}


class BenchmarkContractErrorCode(StrEnum):
    INVALID_PROFILE = "INVALID_BENCHMARK_PROFILE"
    INVALID_REPORT = "INVALID_BENCHMARK_REPORT"
    INVALID_BASELINE = "INVALID_BENCHMARK_BASELINE"
    BASELINE_DRIFT = "BENCHMARK_BASELINE_DRIFT"


class BenchmarkContractError(ValueError):
    """Stable contract failure for a profile, report, or immutable baseline."""

    def __init__(
        self,
        code: BenchmarkContractErrorCode,
        *,
        field: str,
        message: str,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{code.value}: {field}: {message}")


@dataclass(frozen=True, slots=True)
class BenchmarkProfile:
    name: str
    profile_id: str
    profile_version: str
    size: str
    seed: int
    tick_seconds: int
    horizon_ticks: int
    workshop_count: int
    resource_count: int
    order_count: int
    operations_per_order: int
    candidate_resource_count: int
    calendar_fragment_count: int
    material_delay_every: int
    due_tick_base: int
    due_tick_stride: int
    max_wall_time_seconds: float
    warmup_runs: int
    measured_runs: int
    baseline_path: str

    @property
    def operation_count(self) -> int:
        return self.order_count * self.operations_per_order


@dataclass(frozen=True, slots=True)
class BenchmarkProfileSet:
    profiles: Mapping[str, BenchmarkProfile]

    def select(self, name: str) -> BenchmarkProfile:
        normalized = name.lower()
        try:
            return self.profiles[normalized]
        except KeyError as error:
            _reject(
                BenchmarkContractErrorCode.INVALID_PROFILE,
                "profile",
                "profile must be exactly one of xs, s, or m",
            )
            raise AssertionError("unreachable") from error


def _reject(
    code: BenchmarkContractErrorCode, field: str, message: str
) -> Never:
    raise BenchmarkContractError(code, field=field, message=message)


def _mapping(value: object, field: str, code: BenchmarkContractErrorCode) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _reject(code, field, "must be a JSON/YAML object with string keys")
    return cast(JsonObject, value)


def _exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    field: str,
    code: BenchmarkContractErrorCode,
) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        _reject(code, field, f"exact keys required; missing={missing}, extra={extra}")


def _text(
    value: object, field: str, code: BenchmarkContractErrorCode
) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        _reject(code, field, "must be non-empty canonical text")
    return value


def _boolean(
    value: object, field: str, code: BenchmarkContractErrorCode
) -> bool:
    if type(value) is not bool:
        _reject(code, field, "must be a boolean")
    return cast(bool, value)


def _utc_text(
    value: object, field: str, code: BenchmarkContractErrorCode
) -> str:
    text = _text(value, field, code)
    try:
        parse_utc_instant(text)
    except ValueError:
        _reject(code, field, "must be a canonical UTC instant")
    return text


def _digest(
    value: object, field: str, code: BenchmarkContractErrorCode
) -> str:
    text = _text(value, field, code)
    digest = text.removeprefix("sha256:")
    if (
        not text.startswith("sha256:")
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        _reject(code, field, "must be a lowercase sha256:<64 hex> digest")
    return text


def _text_list(
    value: object,
    field: str,
    code: BenchmarkContractErrorCode,
    *,
    minimum_items: int = 0,
) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum_items:
        _reject(code, field, f"must be a list with at least {minimum_items} items")
    return [
        _text(item, f"{field}[{index}]", code)
        for index, item in enumerate(cast(list[object], value))
    ]


def _integer(
    value: object,
    field: str,
    code: BenchmarkContractErrorCode,
    *,
    minimum: int = 0,
) -> int:
    if type(value) is not int or cast(int, value) < minimum:
        _reject(code, field, f"must be an integer >= {minimum}")
    return cast(int, value)


def _number(
    value: object,
    field: str,
    code: BenchmarkContractErrorCode,
    *,
    minimum: float = 0.0,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject(code, field, "must be a finite number")
    result = float(value)
    if result < minimum or result != result or result in {float("inf"), float("-inf")}:
        _reject(code, field, f"must be finite and >= {minimum}")
    return result


def _identity(
    value: object,
    expected: Mapping[str, str],
    field: str,
    code: BenchmarkContractErrorCode,
) -> None:
    document = _mapping(value, field, code)
    _exact_keys(document, set(expected), field, code)
    if document != expected:
        _reject(code, field, f"must equal {dict(expected)}")


def _profile_from_document(name: str, value: object) -> BenchmarkProfile:
    code = BenchmarkContractErrorCode.INVALID_PROFILE
    profile = _mapping(value, f"profiles.{name}", code)
    _exact_keys(profile, _PROFILE_KEYS, f"profiles.{name}", code)
    if profile["size"] != _SIZE_BY_NAME[name]:
        _reject(code, f"profiles.{name}.size", "size/name mismatch or L/XL requested")
    expected_baseline = f"benchmarks/baselines/p2-{name}.v1.json"
    if profile["baseline_path"] != expected_baseline:
        _reject(code, f"profiles.{name}.baseline_path", "must use the immutable v1 path")
    workshop_count = _integer(
        profile["workshop_count"], f"profiles.{name}.workshop_count", code, minimum=1
    )
    resource_count = _integer(
        profile["resource_count"], f"profiles.{name}.resource_count", code, minimum=1
    )
    candidate_count = _integer(
        profile["candidate_resource_count"],
        f"profiles.{name}.candidate_resource_count",
        code,
        minimum=1,
    )
    if resource_count % workshop_count != 0:
        _reject(code, f"profiles.{name}.resource_count", "must divide by workshops")
    if candidate_count > resource_count // workshop_count:
        _reject(
            code,
            f"profiles.{name}.candidate_resource_count",
            "must fit within every generated workshop",
        )
    warmup_runs = _integer(
        profile["warmup_runs"], f"profiles.{name}.warmup_runs", code, minimum=1
    )
    measured_runs = _integer(
        profile["measured_runs"],
        f"profiles.{name}.measured_runs",
        code,
        minimum=2,
    )
    return BenchmarkProfile(
        name=name,
        profile_id=_text(profile["profile_id"], f"profiles.{name}.profile_id", code),
        profile_version=_text(
            profile["profile_version"], f"profiles.{name}.profile_version", code
        ),
        size=cast(str, profile["size"]),
        seed=_integer(profile["seed"], f"profiles.{name}.seed", code),
        tick_seconds=_integer(
            profile["tick_seconds"], f"profiles.{name}.tick_seconds", code, minimum=1
        ),
        horizon_ticks=_integer(
            profile["horizon_ticks"], f"profiles.{name}.horizon_ticks", code, minimum=1
        ),
        workshop_count=workshop_count,
        resource_count=resource_count,
        order_count=_integer(
            profile["order_count"], f"profiles.{name}.order_count", code, minimum=1
        ),
        operations_per_order=_integer(
            profile["operations_per_order"],
            f"profiles.{name}.operations_per_order",
            code,
            minimum=1,
        ),
        candidate_resource_count=candidate_count,
        calendar_fragment_count=_integer(
            profile["calendar_fragment_count"],
            f"profiles.{name}.calendar_fragment_count",
            code,
        ),
        material_delay_every=_integer(
            profile["material_delay_every"],
            f"profiles.{name}.material_delay_every",
            code,
            minimum=1,
        ),
        due_tick_base=_integer(
            profile["due_tick_base"], f"profiles.{name}.due_tick_base", code
        ),
        due_tick_stride=_integer(
            profile["due_tick_stride"], f"profiles.{name}.due_tick_stride", code
        ),
        max_wall_time_seconds=_number(
            profile["max_wall_time_seconds"],
            f"profiles.{name}.max_wall_time_seconds",
            code,
            minimum=0.001,
        ),
        warmup_runs=warmup_runs,
        measured_runs=measured_runs,
        baseline_path=cast(str, profile["baseline_path"]),
    )


def validate_profile_set_document(document: Mapping[str, object]) -> None:
    code = BenchmarkContractErrorCode.INVALID_PROFILE
    _exact_keys(document, _PROFILE_SET_KEYS, "profile_set", code)
    expected_scalars = {
        "profile_set_version": PROFILE_SET_VERSION,
        "task_id": TASK_ID,
        "schema_set_version": SCHEMA_SET_VERSION,
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "report_version": BENCHMARK_REPORT_VERSION,
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
    }
    for field, expected in expected_scalars.items():
        if document[field] != expected:
            _reject(code, field, f"must equal {expected}")
    _identity(
        document["generator"],
        {
            "generator_id": BENCHMARK_GENERATOR_ID,
            "generator_version": BENCHMARK_GENERATOR_VERSION,
        },
        "generator",
        code,
    )
    _identity(
        document["assembler"],
        {
            "generator_id": CORRECTNESS_ASSEMBLER_ID,
            "generator_version": CORRECTNESS_ASSEMBLER_VERSION,
        },
        "assembler",
        code,
    )
    profiles = _mapping(document["profiles"], "profiles", code)
    if set(profiles) != set(_PROFILE_NAMES):
        _reject(code, "profiles", "must contain exactly xs, s, and m; L/XL are excluded")
    for name in _PROFILE_NAMES:
        _profile_from_document(name, profiles[name])


def load_profile_set(path: Path) -> BenchmarkProfileSet:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise BenchmarkContractError(
            BenchmarkContractErrorCode.INVALID_PROFILE,
            field=str(path),
            message="profile set could not be read as YAML",
        ) from error
    document = _mapping(value, "profile_set", BenchmarkContractErrorCode.INVALID_PROFILE)
    validate_profile_set_document(document)
    profiles = cast(JsonObject, document["profiles"])
    return BenchmarkProfileSet(
        profiles={name: _profile_from_document(name, profiles[name]) for name in _PROFILE_NAMES}
    )


def aggregate_samples(values: Sequence[float]) -> JsonObject:
    """Return deterministic median and nearest-rank p95 with raw samples."""

    if not values:
        _reject(
            BenchmarkContractErrorCode.INVALID_REPORT,
            "samples",
            "at least one measurement is required",
        )
    normalized = [round(_number(value, "samples", BenchmarkContractErrorCode.INVALID_REPORT), 9) for value in values]
    ordered = sorted(normalized)
    p95_index = max(0, (95 * len(ordered) + 99) // 100 - 1)
    return {
        "samples": normalized,
        "minimum": ordered[0],
        "median": round(float(median(ordered)), 9),
        "p95": ordered[p95_index],
        "maximum": ordered[-1],
    }


def capture_environment() -> JsonObject:
    """Capture non-secret hardware/runtime identity for comparability decisions."""

    basis: JsonObject = {
        "system": platform.system() or "unknown",
        "release": platform.release() or "unknown",
        "machine": platform.machine() or "unknown",
        "processor": platform.processor() or "unknown",
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "solver_name": "Google-OR-Tools-CP-SAT",
        "solver_version": ORTOOLS_VERSION,
        "timer": "time.perf_counter",
        "ci_provider": "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local",
    }
    signature_basis = json.dumps(
        basis, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        **basis,
        "environment_signature": f"sha256:{sha256(signature_basis).hexdigest()}",
    }


def generated_at_utc() -> str:
    return format_utc_instant(datetime.now(UTC))


def _validate_aggregate(value: object, field: str) -> None:
    code = BenchmarkContractErrorCode.INVALID_REPORT
    document = _mapping(value, field, code)
    _exact_keys(document, {"samples", "minimum", "median", "p95", "maximum"}, field, code)
    samples = document["samples"]
    if not isinstance(samples, list) or not samples:
        _reject(code, f"{field}.samples", "must be a non-empty list")
    expected = aggregate_samples(
        [
            _number(item, f"{field}.samples[{index}]", code)
            for index, item in enumerate(samples)
        ]
    )
    if document != expected:
        _reject(
            code,
            field,
            "minimum/median/p95/maximum must be derived from the raw samples",
        )


def _validate_complexity(
    value: object, field: str, code: BenchmarkContractErrorCode
) -> JsonObject:
    document = _mapping(value, field, code)
    _exact_keys(document, COMPLEXITY_KEYS, field, code)
    for key in COMPLEXITY_KEYS - {
        "average_candidate_resource_count",
        "cross_workshop_ratio",
        "material_delay_ratio",
        "wip_ratio",
        "lock_ratio",
        "bottleneck_utilization",
    }:
        _integer(document[key], f"{field}.{key}", code)
    for key in {
        "average_candidate_resource_count",
        "cross_workshop_ratio",
        "material_delay_ratio",
        "wip_ratio",
        "lock_ratio",
        "bottleneck_utilization",
    }:
        _number(document[key], f"{field}.{key}", code)
    return document


def validate_benchmark_report(report: Mapping[str, object]) -> None:
    """Reject missing and unknown fields throughout the internal report v1."""

    code = BenchmarkContractErrorCode.INVALID_REPORT
    top_keys = {
        "benchmark_report_version",
        "status",
        "task_id",
        "code_commit",
        "profile_set_version",
        "runner_version",
        "threshold_policy_version",
        "schema_set_version",
        "generated_at_utc",
        "profile",
        "scenario",
        "generator",
        "assembler",
        "pipeline",
        "problem",
        "environment",
        "execution",
        "global_solver",
        "reference_schedulers",
        "comparison",
        "baseline",
        "checks",
        "check_count",
        "warnings",
        "boundaries",
    }
    _exact_keys(report, top_keys, "report", code)
    for field, expected in {
        "benchmark_report_version": BENCHMARK_REPORT_VERSION,
        "task_id": TASK_ID,
        "profile_set_version": PROFILE_SET_VERSION,
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "schema_set_version": SCHEMA_SET_VERSION,
    }.items():
        if report[field] != expected:
            _reject(code, field, f"must equal {expected}")
    if report["status"] != "PASS":
        _reject(code, "status", "successful BenchmarkReport must be PASS")
    code_commit = _text(report["code_commit"], "code_commit", code)
    if code_commit != "uncommitted" and (
        len(code_commit) != 40
        or any(character not in "0123456789abcdef" for character in code_commit)
    ):
        _reject(code, "code_commit", "must be uncommitted or full lowercase SHA")
    parse_utc_instant(_text(report["generated_at_utc"], "generated_at_utc", code))

    profile = _mapping(report["profile"], "profile", code)
    _exact_keys(
        profile,
        {"profile_id", "profile_version", "size", "seed", "warmup_runs", "measured_runs", "baseline_path"},
        "profile",
        code,
    )
    size = _text(profile["size"], "profile.size", code)
    if size not in {"XS", "S", "M"}:
        _reject(code, "profile.size", "L/XL are outside TASK-P2-12")
    profile_name = size.lower()
    if profile["profile_id"] != f"P2-BENCHMARK-{size}":
        _reject(code, "profile.profile_id", "must match the registered size identity")
    if profile["profile_version"] != "1.0.0":
        _reject(code, "profile.profile_version", "report v1 requires profile 1.0.0")
    _integer(profile["seed"], "profile.seed", code)
    warmup_runs = _integer(profile["warmup_runs"], "profile.warmup_runs", code, minimum=1)
    measured_runs = _integer(
        profile["measured_runs"], "profile.measured_runs", code, minimum=2
    )
    expected_baseline_path = f"benchmarks/baselines/p2-{profile_name}.v1.json"
    if profile["baseline_path"] != expected_baseline_path:
        _reject(code, "profile.baseline_path", "must match the immutable size baseline")
    scenario = _mapping(report["scenario"], "scenario", code)
    _exact_keys(scenario, {"scenario_id", "scenario_version", "synthetic_only"}, "scenario", code)
    if scenario != {
        "scenario_id": f"P2-BENCHMARK-{size}",
        "scenario_version": "1.0.0",
        "synthetic_only": True,
    }:
        _reject(code, "scenario", "must be the registered synthetic profile scenario")
    _identity(
        report["generator"],
        {"generator_id": BENCHMARK_GENERATOR_ID, "generator_version": BENCHMARK_GENERATOR_VERSION},
        "generator",
        code,
    )

    pipeline = _mapping(report["pipeline"], "pipeline", code)
    _exact_keys(
        pipeline,
        {
            "versions",
            "case_materialization_seconds",
            "source_to_problem_seconds",
            "kpi_export_seconds",
            "kpi_version",
            "export_package_profile",
            "export_package_id",
            "export_manifest_fingerprint",
            "export_file_count",
        },
        "pipeline",
        code,
    )
    versions = _mapping(pipeline["versions"], "pipeline.versions", code)
    _exact_keys(
        versions,
        {
            "mapping_profile",
            "unit_registry",
            "normalization",
            "import_package",
            "data_quality_rules",
            "expansion",
            "snapshot",
            "problem",
            "problem_builder",
        },
        "pipeline.versions",
        code,
    )
    for field in (
        "case_materialization_seconds",
        "source_to_problem_seconds",
        "kpi_export_seconds",
    ):
        _number(pipeline[field], f"pipeline.{field}", code)
    for field in versions:
        _text(versions[field], f"pipeline.versions.{field}", code)
    if pipeline["kpi_version"] != "kpi.v2":
        _reject(code, "pipeline.kpi_version", "must preserve KPI v2")
    if pipeline["export_package_profile"] != "p2-internal-export.v1":
        _reject(
            code,
            "pipeline.export_package_profile",
            "must preserve the P2 internal export profile",
        )
    _text(pipeline["export_package_id"], "pipeline.export_package_id", code)
    _digest(
        pipeline["export_manifest_fingerprint"],
        "pipeline.export_manifest_fingerprint",
        code,
    )
    if _integer(
        pipeline["export_file_count"], "pipeline.export_file_count", code, minimum=1
    ) != 9:
        _reject(code, "pipeline.export_file_count", "P2 internal export must contain 9 files")
    _identity(
        report["assembler"],
        {"generator_id": CORRECTNESS_ASSEMBLER_ID, "generator_version": CORRECTNESS_ASSEMBLER_VERSION},
        "assembler",
        code,
    )

    problem = _mapping(report["problem"], "problem", code)
    _exact_keys(
        problem,
        {
            "problem_version",
            "problem_builder_version",
            "problem_hash_projection_version",
            "problem_hash",
            "snapshot_id",
            "snapshot_hash",
            "tick_seconds",
            "horizon_start_utc",
            "horizon_end_utc",
            "complexity",
        },
        "problem",
        code,
    )
    _validate_complexity(problem["complexity"], "problem.complexity", code)
    for field, expected in {
        "problem_version": "planning-problem.v2",
        "problem_builder_version": "planning-problem-builder.v2",
        "problem_hash_projection_version": "planning-problem-hash-projection.v2",
    }.items():
        if problem[field] != expected:
            _reject(code, f"problem.{field}", f"must equal {expected}")
    _digest(problem["problem_hash"], "problem.problem_hash", code)
    _text(problem["snapshot_id"], "problem.snapshot_id", code)
    _digest(problem["snapshot_hash"], "problem.snapshot_hash", code)
    _integer(problem["tick_seconds"], "problem.tick_seconds", code, minimum=1)
    horizon_start = parse_utc_instant(
        _utc_text(problem["horizon_start_utc"], "problem.horizon_start_utc", code)
    )
    horizon_end = parse_utc_instant(
        _utc_text(problem["horizon_end_utc"], "problem.horizon_end_utc", code)
    )
    if horizon_end <= horizon_start:
        _reject(code, "problem.horizon_end_utc", "must be after horizon_start_utc")

    environment = _mapping(report["environment"], "environment", code)
    _exact_keys(
        environment,
        {
            "system",
            "release",
            "machine",
            "processor",
            "python_implementation",
            "python_version",
            "logical_cpu_count",
            "solver_name",
            "solver_version",
            "timer",
            "ci_provider",
            "environment_signature",
        },
        "environment",
        code,
    )
    for field in set(environment) - {"logical_cpu_count"}:
        _text(environment[field], f"environment.{field}", code)
    _digest(
        environment["environment_signature"], "environment.environment_signature", code
    )
    if environment["logical_cpu_count"] is not None:
        _integer(
            environment["logical_cpu_count"],
            "environment.logical_cpu_count",
            code,
            minimum=1,
        )
    execution = _mapping(report["execution"], "execution", code)
    _exact_keys(
        execution,
        {
            "warmups_complete",
            "warmup_runs_per_scheduler",
            "measured_runs_per_scheduler",
            "global_scheduler_count",
            "reference_scheduler_count",
            "correctness_replay_verified",
            "deterministic_replays",
        },
        "execution",
        code,
    )
    if any(
        execution[field] is not True
        for field in (
            "warmups_complete",
            "correctness_replay_verified",
            "deterministic_replays",
        )
    ):
        _reject(code, "execution", "all correctness execution flags must be true")
    if (
        _integer(
            execution["warmup_runs_per_scheduler"],
            "execution.warmup_runs_per_scheduler",
            code,
            minimum=1,
        )
        != warmup_runs
        or _integer(
            execution["measured_runs_per_scheduler"],
            "execution.measured_runs_per_scheduler",
            code,
            minimum=2,
        )
        != measured_runs
        or _integer(
            execution["global_scheduler_count"],
            "execution.global_scheduler_count",
            code,
            minimum=1,
        )
        != 1
        or _integer(
            execution["reference_scheduler_count"],
            "execution.reference_scheduler_count",
            code,
            minimum=1,
        )
        != len(_REFERENCE_KEYS)
    ):
        _reject(code, "execution", "run counts must match the selected profile and scheduler set")

    global_solver = _mapping(report["global_solver"], "global_solver", code)
    _exact_keys(
        global_solver,
        {
            "strategy_id",
            "strategy_version",
            "solver",
            "parameters",
            "status",
            "model_metrics",
            "timings",
            "memory_peak_mb",
            "quality",
            "validation",
            "sample_fingerprints",
            "kpi_fingerprints",
        },
        "global_solver",
        code,
    )
    model_metrics = _mapping(global_solver["model_metrics"], "global_solver.model_metrics", code)
    _exact_keys(model_metrics, {"variables", "constraints", "optional_intervals"}, "global_solver.model_metrics", code)
    for name, value in model_metrics.items():
        _integer(value, f"global_solver.model_metrics.{name}", code)
    timings = _mapping(global_solver["timings"], "global_solver.timings", code)
    _exact_keys(
        timings,
        {"model_build_seconds", "first_solution_seconds", "solve_seconds", "validation_seconds", "total_seconds"},
        "global_solver.timings",
        code,
    )
    for name, aggregate in timings.items():
        _validate_aggregate(aggregate, f"global_solver.timings.{name}")
    _validate_aggregate(global_solver["memory_peak_mb"], "global_solver.memory_peak_mb")
    solver = _mapping(global_solver["solver"], "global_solver.solver", code)
    _exact_keys(
        solver,
        {"backend_id", "backend_version", "solver_name", "solver_version"},
        "global_solver.solver",
        code,
    )
    for name, value in solver.items():
        _text(value, f"global_solver.solver.{name}", code)
    if global_solver["status"] not in {"OPTIMAL", "FEASIBLE"}:
        _reject(code, "global_solver.status", "must contain a candidate-producing status")
    _text(global_solver["strategy_id"], "global_solver.strategy_id", code)
    _text(global_solver["strategy_version"], "global_solver.strategy_version", code)
    parameters = global_solver["parameters"]
    if not isinstance(parameters, list) or not parameters:
        _reject(code, "global_solver.parameters", "must be a non-empty list")
    for index, raw_parameter in enumerate(parameters):
        parameter = _mapping(raw_parameter, f"global_solver.parameters[{index}]", code)
        _exact_keys(
            parameter,
            {"name", "value", "source"},
            f"global_solver.parameters[{index}]",
            code,
        )
        _text(parameter["name"], f"global_solver.parameters[{index}].name", code)
        _text(parameter["source"], f"global_solver.parameters[{index}].source", code)
        if not isinstance(parameter["value"], (str, int, float, bool)):
            _reject(
                code,
                f"global_solver.parameters[{index}].value",
                "must be a JSON scalar",
            )
    global_quality = _mapping(global_solver["quality"], "global_solver.quality", code)
    _exact_keys(
        global_quality,
        {
            "objective",
            "best_bound",
            "relative_gap",
            "weighted_tardiness_seconds",
            "makespan_seconds",
            "on_time_order_ratio",
            "solver_kpi_matches",
        },
        "global_solver.quality",
        code,
    )
    for name in (
        "objective",
        "best_bound",
        "weighted_tardiness_seconds",
        "makespan_seconds",
    ):
        _integer(global_quality[name], f"global_solver.quality.{name}", code)
    _number(global_quality["relative_gap"], "global_solver.quality.relative_gap", code)
    on_time_ratio = _number(
        global_quality["on_time_order_ratio"],
        "global_solver.quality.on_time_order_ratio",
        code,
    )
    if on_time_ratio > 1.0:
        _reject(code, "global_solver.quality.on_time_order_ratio", "must be <= 1")
    if global_quality["solver_kpi_matches"] is not True:
        _reject(code, "global_solver.quality.solver_kpi_matches", "must be true")
    global_validation = _mapping(
        global_solver["validation"], "global_solver.validation", code
    )
    _exact_keys(
        global_validation,
        {"status", "validation_report_version", "pass_count", "fresh_formal"},
        "global_solver.validation",
        code,
    )
    if global_validation["status"] != "PASS" or global_validation["fresh_formal"] is not True:
        _reject(code, "global_solver.validation", "fresh formal validation must PASS")
    _text(
        global_validation["validation_report_version"],
        "global_solver.validation.validation_report_version",
        code,
    )
    if _integer(
        global_validation["pass_count"],
        "global_solver.validation.pass_count",
        code,
        minimum=1,
    ) != measured_runs:
        _reject(code, "global_solver.validation.pass_count", "must equal measured runs")
    global_fingerprints = _text_list(
        global_solver["sample_fingerprints"],
        "global_solver.sample_fingerprints",
        code,
        minimum_items=measured_runs,
    )
    if len(global_fingerprints) != measured_runs or len(set(global_fingerprints)) != 1:
        _reject(
            code,
            "global_solver.sample_fingerprints",
            "must contain one stable fingerprint per measured run",
        )
    for index, value in enumerate(global_fingerprints):
        _digest(value, f"global_solver.sample_fingerprints[{index}]", code)
    global_kpi_fingerprints = _text_list(
        global_solver["kpi_fingerprints"],
        "global_solver.kpi_fingerprints",
        code,
        minimum_items=measured_runs,
    )
    if len(global_kpi_fingerprints) != measured_runs:
        _reject(code, "global_solver.kpi_fingerprints", "must equal measured runs")
    for index, value in enumerate(global_kpi_fingerprints):
        _digest(value, f"global_solver.kpi_fingerprints[{index}]", code)

    references = report["reference_schedulers"]
    if not isinstance(references, list) or len(references) != len(_REFERENCE_KEYS):
        _reject(code, "reference_schedulers", "must contain all five algorithms")
    observed_algorithms: set[str] = set()
    for index, raw_reference in enumerate(references):
        field = f"reference_schedulers[{index}]"
        reference = _mapping(raw_reference, field, code)
        _exact_keys(
            reference,
            {
                "algorithm",
                "algorithm_id",
                "status",
                "non_production",
                "optimality_claim",
                "timings",
                "memory_peak_mb",
                "quality",
                "validation",
                "deterministic_replay",
                "sample_fingerprints",
            },
            field,
            code,
        )
        algorithm = _text(reference["algorithm"], f"{field}.algorithm", code)
        observed_algorithms.add(algorithm)
        if reference["algorithm_id"] != _REFERENCE_IDS.get(algorithm):
            _reject(code, f"{field}.algorithm_id", "must match the versioned algorithm identity")
        if (
            reference["status"] != "FEASIBLE"
            or reference["non_production"] is not True
            or reference["optimality_claim"] != "NONE"
        ):
            _reject(code, field, "Reference status and non-production boundary changed")
        reference_timings = _mapping(reference["timings"], f"{field}.timings", code)
        _exact_keys(reference_timings, {"internal_runtime_seconds", "total_seconds"}, f"{field}.timings", code)
        for name, aggregate in reference_timings.items():
            _validate_aggregate(aggregate, f"{field}.timings.{name}")
        _validate_aggregate(reference["memory_peak_mb"], f"{field}.memory_peak_mb")
        reference_quality = _mapping(reference["quality"], f"{field}.quality", code)
        _exact_keys(
            reference_quality,
            {
                "weighted_tardiness_seconds",
                "makespan_seconds",
                "on_time_order_ratio",
                "shared_kpi_matches",
            },
            f"{field}.quality",
            code,
        )
        for name in ("weighted_tardiness_seconds", "makespan_seconds"):
            _integer(reference_quality[name], f"{field}.quality.{name}", code)
        reference_on_time = _number(
            reference_quality["on_time_order_ratio"],
            f"{field}.quality.on_time_order_ratio",
            code,
        )
        if reference_on_time > 1.0:
            _reject(code, f"{field}.quality.on_time_order_ratio", "must be <= 1")
        if reference_quality["shared_kpi_matches"] is not True:
            _reject(code, f"{field}.quality.shared_kpi_matches", "must be true")
        reference_validation = _mapping(
            reference["validation"], f"{field}.validation", code
        )
        _exact_keys(
            reference_validation,
            {"status", "validation_report_version", "pass_count", "fresh_formal"},
            f"{field}.validation",
            code,
        )
        if (
            reference_validation["status"] != "PASS"
            or reference_validation["fresh_formal"] is not True
            or reference["deterministic_replay"] is not True
        ):
            _reject(code, field, "Reference correctness and determinism must PASS")
        _text(
            reference_validation["validation_report_version"],
            f"{field}.validation.validation_report_version",
            code,
        )
        if _integer(
            reference_validation["pass_count"],
            f"{field}.validation.pass_count",
            code,
            minimum=1,
        ) != measured_runs:
            _reject(code, f"{field}.validation.pass_count", "must equal measured runs")
        fingerprints = _text_list(
            reference["sample_fingerprints"],
            f"{field}.sample_fingerprints",
            code,
            minimum_items=measured_runs,
        )
        if len(fingerprints) != measured_runs or len(set(fingerprints)) != 1:
            _reject(
                code,
                f"{field}.sample_fingerprints",
                "must contain one stable fingerprint per measured run",
            )
        for fingerprint_index, value in enumerate(fingerprints):
            _digest(value, f"{field}.sample_fingerprints[{fingerprint_index}]", code)
    if observed_algorithms != _REFERENCE_KEYS:
        _reject(code, "reference_schedulers.algorithm", "algorithm set mismatch")

    comparison = _mapping(report["comparison"], "comparison", code)
    _exact_keys(
        comparison,
        {
            "same_problem_hash",
            "same_formal_validator",
            "same_schedule_kpi",
            "global_weighted_tardiness_seconds",
            "best_reference_weighted_tardiness_seconds",
            "best_reference_algorithms",
            "global_minus_best_reference_seconds",
            "global_worse_than_best_reference",
            "warning_code",
        },
        "comparison",
        code,
    )
    if (
        comparison["same_problem_hash"] is not True
        or comparison["same_formal_validator"] is not True
        or comparison["same_schedule_kpi"] != "calculate_schedule_kpi_metrics.v1"
    ):
        _reject(code, "comparison", "all schedulers must share Problem, Validator, and KPI")
    global_value = _integer(
        comparison["global_weighted_tardiness_seconds"],
        "comparison.global_weighted_tardiness_seconds",
        code,
    )
    best_reference_value = _integer(
        comparison["best_reference_weighted_tardiness_seconds"],
        "comparison.best_reference_weighted_tardiness_seconds",
        code,
    )
    difference = comparison["global_minus_best_reference_seconds"]
    if type(difference) is not int or difference != global_value - best_reference_value:
        _reject(code, "comparison.global_minus_best_reference_seconds", "must be the exact difference")
    worse = _boolean(
        comparison["global_worse_than_best_reference"],
        "comparison.global_worse_than_best_reference",
        code,
    )
    if worse != (global_value > best_reference_value):
        _reject(code, "comparison.global_worse_than_best_reference", "must match quality values")
    best_algorithms = _text_list(
        comparison["best_reference_algorithms"],
        "comparison.best_reference_algorithms",
        code,
        minimum_items=1,
    )
    if not set(best_algorithms).issubset(_REFERENCE_KEYS):
        _reject(code, "comparison.best_reference_algorithms", "contains an unknown algorithm")
    expected_warning = "BENCHMARK_WARNING" if worse else None
    if comparison["warning_code"] != expected_warning:
        _reject(code, "comparison.warning_code", "must match the comparison outcome")
    baseline = _mapping(report["baseline"], "baseline", code)
    _exact_keys(
        baseline,
        {
            "benchmark_baseline_version",
            "path",
            "status",
            "environment_comparable",
            "checks",
        },
        "baseline",
        code,
    )
    if baseline["benchmark_baseline_version"] != BENCHMARK_BASELINE_VERSION:
        _reject(code, "baseline.benchmark_baseline_version", "version mismatch")
    if baseline["path"] != expected_baseline_path:
        _reject(code, "baseline.path", "must match the selected profile")
    if baseline["status"] not in {"PASS", "PASS_WITH_WARNINGS"}:
        _reject(code, "baseline.status", "required baseline comparison must complete")
    _boolean(
        baseline["environment_comparable"], "baseline.environment_comparable", code
    )
    _text_list(baseline["checks"], "baseline.checks", code, minimum_items=4)

    checks = report["checks"]
    check_count = _integer(report["check_count"], "check_count", code, minimum=1)
    if not isinstance(checks, list) or len(checks) != check_count or check_count != 8:
        _reject(code, "checks", "check_count must match the check list")
    observed_check_names: set[str] = set()
    for index, raw_check in enumerate(checks):
        check = _mapping(raw_check, f"checks[{index}]", code)
        _exact_keys(check, {"name", "status", "details"}, f"checks[{index}]", code)
        observed_check_names.add(_text(check["name"], f"checks[{index}].name", code))
        if check["status"] != "PASS":
            _reject(code, f"checks[{index}].status", "correctness checks must PASS")
    if len(observed_check_names) != check_count:
        _reject(code, "checks.name", "check names must be unique")
    warnings = report["warnings"]
    if not isinstance(warnings, list):
        _reject(code, "warnings", "must be a list")
    for index, raw_warning in enumerate(warnings):
        warning = _mapping(raw_warning, f"warnings[{index}]", code)
        _exact_keys(warning, {"code", "severity", "message"}, f"warnings[{index}]", code)
        if warning["severity"] != "WARNING":
            _reject(code, f"warnings[{index}].severity", "must be WARNING")
        _text(warning["code"], f"warnings[{index}].code", code)
        _text(warning["message"], f"warnings[{index}].message", code)
    boundaries = _mapping(report["boundaries"], "boundaries", code)
    _exact_keys(
        boundaries,
        {
            "data_plane",
            "profiles",
            "l_xl",
            "production_capacity_sla",
            "historical_production_baseline",
            "approval_publish_external_transfer",
            "p2_13_p2_14_p3",
        },
        "boundaries",
        code,
    )
    expected_boundaries = {
        "data_plane": "SIMULATION_ONLY",
        "profiles": "XS_S_M_ONLY",
        "l_xl": "DEFERRED_RELEASE_OR_DEDICATED_ENVIRONMENT",
        "production_capacity_sla": "NOT_ESTABLISHED_OPEN_012",
        "historical_production_baseline": "NOT_AVAILABLE_OPEN_011",
        "approval_publish_external_transfer": "PROHIBITED",
        "p2_13_p2_14_p3": "NOT_STARTED",
    }
    if boundaries != expected_boundaries:
        _reject(code, "boundaries", "P2 development-only boundaries changed")


_BASELINE_KEYS = {
    "benchmark_baseline_version",
    "task_id",
    "runner_version",
    "threshold_policy_version",
    "profile",
    "generator",
    "problem",
    "environment",
    "observed",
    "ceilings",
    "boundaries",
}


def validate_baseline_document(document: Mapping[str, object]) -> None:
    code = BenchmarkContractErrorCode.INVALID_BASELINE
    _exact_keys(document, _BASELINE_KEYS, "baseline", code)
    for field, expected in {
        "benchmark_baseline_version": BENCHMARK_BASELINE_VERSION,
        "task_id": TASK_ID,
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
    }.items():
        if document[field] != expected:
            _reject(code, field, f"must equal {expected}")
    profile = _mapping(document["profile"], "profile", code)
    _exact_keys(profile, {"profile_id", "profile_version", "size"}, "profile", code)
    size = _text(profile["size"], "profile.size", code)
    if size not in {"XS", "S", "M"}:
        _reject(code, "profile.size", "must be XS, S, or M")
    if profile["profile_id"] != f"P2-BENCHMARK-{size}":
        _reject(code, "profile.profile_id", "must match the registered size identity")
    if profile["profile_version"] != "1.0.0":
        _reject(code, "profile.profile_version", "baseline v1 requires profile 1.0.0")
    _identity(
        document["generator"],
        {"generator_id": BENCHMARK_GENERATOR_ID, "generator_version": BENCHMARK_GENERATOR_VERSION},
        "generator",
        code,
    )
    problem = _mapping(document["problem"], "problem", code)
    _exact_keys(problem, {"problem_hash", "complexity"}, "problem", code)
    _digest(problem["problem_hash"], "problem.problem_hash", code)
    _validate_complexity(problem["complexity"], "problem.complexity", code)
    environment = _mapping(document["environment"], "environment", code)
    _exact_keys(
        environment,
        {"captured_at_utc", "environment_signature", "system", "machine", "python_version", "solver_version"},
        "environment",
        code,
    )
    _utc_text(environment["captured_at_utc"], "environment.captured_at_utc", code)
    _digest(
        environment["environment_signature"], "environment.environment_signature", code
    )
    for field in {"system", "machine", "python_version", "solver_version"}:
        _text(environment[field], f"environment.{field}", code)
    observed = _mapping(document["observed"], "observed", code)
    _exact_keys(observed, {"global", "reference_quality"}, "observed", code)
    global_observed = _mapping(observed["global"], "observed.global", code)
    _exact_keys(
        global_observed,
        {"objective", "best_bound", "solve_seconds_median", "total_seconds_p95", "memory_peak_mb_p95"},
        "observed.global",
        code,
    )
    for field in {"objective", "best_bound"}:
        _integer(global_observed[field], f"observed.global.{field}", code)
    for field in {
        "solve_seconds_median",
        "total_seconds_p95",
        "memory_peak_mb_p95",
    }:
        _number(global_observed[field], f"observed.global.{field}", code)
    reference_quality = _mapping(observed["reference_quality"], "observed.reference_quality", code)
    if set(reference_quality) != _REFERENCE_KEYS:
        _reject(code, "observed.reference_quality", "must contain all five algorithms")
    for algorithm, value in reference_quality.items():
        _integer(value, f"observed.reference_quality.{algorithm}", code)
    ceilings = _mapping(document["ceilings"], "ceilings", code)
    _exact_keys(
        ceilings,
        {"pipeline_seconds", "global_total_seconds_p95", "global_memory_peak_mb_p95", "reference_total_seconds_p95", "same_environment_regression_factor"},
        "ceilings",
        code,
    )
    for field, value in ceilings.items():
        _number(value, f"ceilings.{field}", code, minimum=1.0)
    boundaries = _mapping(document["boundaries"], "boundaries", code)
    _exact_keys(boundaries, {"synthetic_only", "production_sla", "overwrite_policy"}, "boundaries", code)
    if boundaries != {
        "synthetic_only": True,
        "production_sla": "NOT_ESTABLISHED_OPEN_012",
        "overwrite_policy": "IMMUTABLE_CREATE_NEW_VERSION",
    }:
        _reject(code, "boundaries", "P2 non-production and immutable boundaries changed")


def load_baseline(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BenchmarkContractError(
            BenchmarkContractErrorCode.INVALID_BASELINE,
            field=str(path),
            message="baseline could not be read as JSON",
        ) from error
    document = _mapping(value, "baseline", BenchmarkContractErrorCode.INVALID_BASELINE)
    validate_baseline_document(document)
    return document


def make_baseline_document(report: Mapping[str, object]) -> JsonObject:
    """Project a real successful run into one immutable initial baseline value."""

    validate_benchmark_report(report)
    profile = cast(JsonObject, report["profile"])
    problem = cast(JsonObject, report["problem"])
    environment = cast(JsonObject, report["environment"])
    global_solver = cast(JsonObject, report["global_solver"])
    quality = cast(JsonObject, global_solver["quality"])
    timings = cast(JsonObject, global_solver["timings"])
    memory = cast(JsonObject, global_solver["memory_peak_mb"])
    reference_quality = {
        cast(str, reference["algorithm"]): cast(JsonObject, reference["quality"])[
            "weighted_tardiness_seconds"
        ]
        for reference in cast(list[JsonObject], report["reference_schedulers"])
    }
    size = cast(str, profile["size"])
    scale = {"XS": 1.0, "S": 2.0, "M": 4.0}[size]
    baseline: JsonObject = {
        "benchmark_baseline_version": BENCHMARK_BASELINE_VERSION,
        "task_id": TASK_ID,
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "profile": {
            "profile_id": profile["profile_id"],
            "profile_version": profile["profile_version"],
            "size": size,
        },
        "generator": {
            "generator_id": BENCHMARK_GENERATOR_ID,
            "generator_version": BENCHMARK_GENERATOR_VERSION,
        },
        "problem": {
            "problem_hash": problem["problem_hash"],
            "complexity": problem["complexity"],
        },
        "environment": {
            "captured_at_utc": report["generated_at_utc"],
            "environment_signature": environment["environment_signature"],
            "system": environment["system"],
            "machine": environment["machine"],
            "python_version": environment["python_version"],
            "solver_version": environment["solver_version"],
        },
        "observed": {
            "global": {
                "objective": quality["objective"],
                "best_bound": quality["best_bound"],
                "solve_seconds_median": cast(JsonObject, timings["solve_seconds"])["median"],
                "total_seconds_p95": cast(JsonObject, timings["total_seconds"])["p95"],
                "memory_peak_mb_p95": memory["p95"],
            },
            "reference_quality": reference_quality,
        },
        "ceilings": {
            "pipeline_seconds": 30.0 * scale,
            "global_total_seconds_p95": 10.0 * scale,
            "global_memory_peak_mb_p95": 512.0 * scale,
            "reference_total_seconds_p95": 10.0 * scale,
            "same_environment_regression_factor": 2.5,
        },
        "boundaries": {
            "synthetic_only": True,
            "production_sla": "NOT_ESTABLISHED_OPEN_012",
            "overwrite_policy": "IMMUTABLE_CREATE_NEW_VERSION",
        },
    }
    validate_baseline_document(baseline)
    return baseline


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


__all__ = [
    "BENCHMARK_BASELINE_VERSION",
    "BENCHMARK_GENERATOR_ID",
    "BENCHMARK_GENERATOR_VERSION",
    "BENCHMARK_REPORT_VERSION",
    "BENCHMARK_RUNNER_VERSION",
    "COMPLEXITY_KEYS",
    "CORRECTNESS_ASSEMBLER_ID",
    "CORRECTNESS_ASSEMBLER_VERSION",
    "PROFILE_SET_VERSION",
    "SCHEMA_SET_VERSION",
    "TASK_ID",
    "THRESHOLD_POLICY_VERSION",
    "BenchmarkContractError",
    "BenchmarkContractErrorCode",
    "BenchmarkProfile",
    "BenchmarkProfileSet",
    "aggregate_samples",
    "canonical_json_bytes",
    "capture_environment",
    "generated_at_utc",
    "load_baseline",
    "load_profile_set",
    "make_baseline_document",
    "validate_baseline_document",
    "validate_benchmark_report",
    "validate_profile_set_document",
]
