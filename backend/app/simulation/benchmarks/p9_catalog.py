"""Versioned P9 synthetic inputs and fail-closed qualification identities.

The existing source assembler is reused before normalization. No Problem or
candidate is synthesized here; the resulting package enters the Runtime API.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

from app.data_validation import validate_import_package
from app.data_validation.canonical_ingress import canonical_fingerprint
from app.normalization import NormalizationInput, normalize_import
from app.simulation.benchmarks.reporting import BenchmarkProfile
from app.simulation.benchmarks.runner import generate_benchmark_case
from app.simulation.generators import p1_mapping_profile
from app.simulation.scenarios import p2_correctness as assembler

CATALOG_PATH = "fixtures/synthetic/P9-QUALIFICATION/catalog.v1.json"
SEAL_PATH = "fixtures/synthetic/P9-QUALIFICATION/holdout-seal.v1.json"


def catalog_path(version: str) -> str:
    if version not in ("v1", "v2"):
        raise ValueError("P9_CATALOG_VERSION")
    return f"fixtures/synthetic/P9-QUALIFICATION/catalog.{version}.json"


def read_catalog(root: Path, version: str = "v1") -> dict[str, Any]:
    raw = (root / catalog_path(version)).read_bytes()
    value = json.loads(raw)
    seal = json.loads(
        (
            root / f"fixtures/synthetic/P9-QUALIFICATION/holdout-seal.{version}.json"
        ).read_bytes()
    )
    if sha256(raw).hexdigest() != seal["catalog_sha256"]:
        raise ValueError("P9_CATALOG_SEAL_MISMATCH")
    if value["catalog_version"] != f"p9-qualification-catalog.{version}":
        raise ValueError("P9_CATALOG_VERSION")
    development = set(value["splits"]["development"].values())
    holdout = set(value["splits"]["holdout"].values())
    if development & holdout or seal["holdout"] != value["splits"]["holdout"]:
        raise ValueError("P9_HOLDOUT_LEAKAGE")
    if value["synthetic"] is not True or value["production_binding"] is not False:
        raise ValueError("P9_NON_PRODUCTION_ONLY")
    return value


def child_value(seed: int, label: str, width: int) -> int:
    material = f"p9-qualification-catalog.v1|B01|{seed}|{label}".encode()
    return int.from_bytes(sha256(material).digest()[:8], "big") % width


def generate_input(
    root: Path,
    split: str,
    size: str,
    *,
    holdout_authorization: dict[str, Any] | None = None,
    version: str = "v1",
) -> dict[str, Any]:
    catalog = read_catalog(root, version)
    if split not in ("development", "holdout") or size not in ("xs", "s", "m"):
        raise ValueError("P9_UNKNOWN_SPLIT_OR_PROFILE")
    if split == "holdout" and (
        holdout_authorization is None
        or holdout_authorization.get("catalog_sha256")
        != sha256((root / catalog_path(version)).read_bytes()).hexdigest()
        or holdout_authorization.get("purpose")
        != (
            "EXPOSED_V1_FAILURE_REGRESSION"
            if version == "v1"
            else "FIRST_QUALIFICATION_AFTER_FROZEN_BUDGET"
        )
        or not holdout_authorization.get("baseline_sha256")
    ):
        raise ValueError("P9_HOLDOUT_ACCESS_NOT_RECORDED")
    seed = catalog["splits"][split][size]
    profile = BenchmarkProfile(name=size, **catalog["profiles"][size])
    profile = replace(
        profile, seed=seed, profile_id=f"P9-{split.upper()}-{size.upper()}"
    )
    case = generate_benchmark_case(profile, root=root)
    scenario_id = f"P9-{split.upper()}-{size.upper()}"
    case.scenario["scenario_id"] = scenario_id
    case.blueprint["scenario_id"] = scenario_id
    for job in case.blueprint["jobs"]:
        job["due_tick"] += child_value(seed, f"{job['job_code']}/due", 4)
        for operation in job["operations"]:
            for candidate in operation["candidates"]:
                label = f"{job['job_code']}/{operation['operation_code']}/{candidate['resource_code']}/duration"
                candidate["duration_ticks"] += child_value(seed, label, 3)
    # Reuse the frozen source vocabulary and mapping, not its Solver replay.
    context = assembler._context(case)
    normalization = normalize_import(
        (
            NormalizationInput(
                assembler._staged_batch(case, reverse_rows=False),
                p1_mapping_profile(context),
            ),
        ),
        unit_registry=assembler._unit_registry(root),
    )
    package = deepcopy(normalization.document)
    quality = validate_import_package(package)
    if not quality.passed:
        raise ValueError("P9_GENERATED_PACKAGE_INVALID")
    blueprint = case.blueprint
    return {
        "scenario_id": scenario_id,
        "generator": catalog["generator"],
        "catalog_sha256": sha256(
            (root / catalog_path(version)).read_bytes()
        ).hexdigest(),
        "seed": seed,
        "split": split,
        "size": size,
        "blueprint": blueprint,
        "input_fingerprint": canonical_fingerprint(package),
        "package": package,
        "profile": catalog["profiles"][size],
        "build_plan": {
            "cutoff_at_utc": blueprint["cutoff_at_utc"],
            "tick_seconds": blueprint["tick_seconds"],
            "horizon_start_utc": blueprint["cutoff_at_utc"],
            "horizon_end_utc": assembler._instant(
                blueprint, blueprint["horizon_ticks"]
            ),
            "priority_facts": assembler._priority_facts(package, blueprint),
        },
    }


def freeze_budget(
    calibration: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    if calibration["split"] != "development" or calibration["result"] != "PASS":
        raise ValueError("P9_BASELINE_REQUIRES_SUCCESSFUL_DEVELOPMENT")
    policy = catalog["budget_policy"]
    if set(calibration["samples"]) != {"xs", "s", "m"}:
        raise ValueError("P9_BASELINE_PROFILE_COVERAGE")
    budgets = {}
    for size, rows in calibration["samples"].items():
        if len(rows) != catalog["measured_runs"]:
            raise ValueError("P9_BASELINE_SAMPLE_COUNT")
        metrics = rows[0]["measurements"]
        if not metrics or any(
            set(row["measurements"]) != set(metrics)
            or any(
                type(value) not in (int, float) or not math.isfinite(value) or value < 0
                for value in row["measurements"].values()
            )
            for row in rows
        ):
            raise ValueError("P9_BASELINE_INVALID_MEASUREMENTS")
        budgets[size] = {
            key: max(
                max(row["measurements"][key] for row in rows) * policy["factor"],
                policy["end_to_end_floor_seconds"]
                if key == "end_to_end_seconds"
                else policy["stage_floor_seconds"]
                if key.endswith("seconds")
                else 1,
            )
            for key in rows[0]["measurements"]
        }
    return {
        "baseline_version": "p9-runtime-baseline."
        + catalog["catalog_version"].rsplit(".", 1)[1],
        "environment": calibration["environment"],
        "catalog_sha256": calibration["catalog_sha256"],
        "calibration_fingerprint": canonical_fingerprint(calibration),
        "budget_policy": policy,
        "budgets": budgets,
        "synthetic_only": True,
    }


def evaluate_budget(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    issues = []
    if report["environment"] != baseline["environment"]:
        return ["P9_ENVIRONMENT_MISMATCH"]
    if report["catalog_sha256"] != baseline["catalog_sha256"]:
        return ["P9_CATALOG_BASELINE_MISMATCH"]
    if set(report["samples"]) != {"xs", "s", "m"} or set(baseline["budgets"]) != {
        "xs",
        "s",
        "m",
    }:
        return ["P9_PROFILE_COVERAGE_MISSING"]
    for size, rows in report["samples"].items():
        limits = baseline["budgets"][size]
        if not limits or any(
            type(value) not in (int, float) or not math.isfinite(value) or value <= 0
            for value in limits.values()
        ):
            issues.append(f"{size}: P9_INVALID_BUDGET")
            continue
        if len(rows) != 3:
            issues.append(f"{size}: P9_SAMPLE_COUNT")
        for index, row in enumerate(rows):
            for metric, maximum in baseline["budgets"][size].items():
                observed = row["measurements"].get(metric)
                if (
                    type(observed) not in (int, float)
                    or not math.isfinite(observed)
                    or observed < 0
                    or observed > maximum
                ):
                    issues.append(
                        f"{size}/{index}/{metric}: BUDGET_EXCEEDED_OR_MISSING"
                    )
    return issues
