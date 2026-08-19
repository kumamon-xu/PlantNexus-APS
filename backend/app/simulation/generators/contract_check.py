"""Machine-readable P0 Simulation determinism and isolation smoke check."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import SCHEMA_VERSION, SPEC_VERSION
from app.domain.capabilities import CapabilityContractError
from app.simulation.generators.contracts import GenerationContext
from app.simulation.generators.determinism import SeedMaterial
from app.simulation.generators.package_contract import build_empty_import_package
from app.simulation.scenarios.contracts import (
    SimulationContractCode,
    SimulationContractError,
)


REPORT_VERSION = "simulation-contract-report.v1"
TEST_IDS = ("TEST-SCENARIO-REPLAY", "TEST-SIM-ISOLATION")


def _context(**overrides: object) -> GenerationContext:
    values: dict[str, Any] = {
        "scenario_id": "SCHEMA-SCENARIO-P0-05",
        "scenario_version": "1.0.0",
        "profile_id": "SCHEMA-PROFILE-P0-05",
        "profile_version": "1.0.0",
        "generator_id": "P0-EMPTY-IMPORT-GENERATOR",
        "generator_version": "1.0.0",
        "seed": 20260819,
        "target": "test",
        "required_capabilities": ("DAG_ROUTING", "MACHINE_CALENDAR"),
    }
    values.update(overrides)
    return GenerationContext.create(**values)


def run_contract_checks() -> dict[str, object]:
    checks: dict[str, bool] = {}
    first = build_empty_import_package(
        _context(), generated_at=datetime(2026, 8, 19, 0, 0, tzinfo=UTC)
    )
    replay = build_empty_import_package(
        _context(), generated_at=datetime(2026, 8, 19, 1, 0, tzinfo=UTC)
    )
    checks["same_input_same_canonical_dataset"] = (
        first.canonical_dataset == replay.canonical_dataset
    )
    checks["same_input_same_dataset_hash"] = first.dataset_hash == replay.dataset_hash
    checks["generated_at_excluded_from_dataset_hash"] = (
        first.manifest["generated_at"] != replay.manifest["generated_at"]
        and first.dataset_hash == replay.dataset_hash
    )
    reversed_capabilities = build_empty_import_package(
        _context(required_capabilities=("MACHINE_CALENDAR", "DAG_ROUTING")),
        generated_at=datetime(2026, 8, 19, 0, 0, tzinfo=UTC),
    )
    checks["capability_set_order_is_canonical"] = (
        first.canonical_dataset == reversed_capabilities.canonical_dataset
        and first.dataset_hash == reversed_capabilities.dataset_hash
    )

    version_change = build_empty_import_package(
        _context(generator_version="1.0.1"),
        generated_at=datetime(2026, 8, 19, 0, 0, tzinfo=UTC),
    )
    checks["generator_version_changes_provenance_and_hash"] = (
        version_change.manifest["generator"]["generator_version"] == "1.0.1"
        and version_change.dataset_hash != first.dataset_hash
    )

    seed_material = SeedMaterial(
        root_seed=20260819,
        generator_id="P0-EMPTY-IMPORT-GENERATOR",
        generator_version="1.0.0",
    )
    topology_first = seed_material.child("topology").derive_seed("resource", index=0)
    _ = seed_material.child("orders").derive_seed("order", index=0)
    topology_after = seed_material.child("topology").derive_seed("resource", index=0)
    checks["named_layer_seed_is_order_independent"] = topology_first == topology_after

    try:
        _context(target="production")
    except SimulationContractError as error:
        checks["production_target_rejected"] = (
            error.code is SimulationContractCode.PRODUCTION_TARGET_FORBIDDEN
        )
    else:
        checks["production_target_rejected"] = False

    try:
        _context(required_capabilities=("SECONDARY_CAPACITY",))
    except CapabilityContractError as error:
        checks["unsupported_capability_rejected"] = (
            error.code.value == "UNSUPPORTED_CAPABILITY"
        )
    else:
        checks["unsupported_capability_rejected"] = False

    issues = sorted(name for name, passed in checks.items() if not passed)
    return {
        "report_version": REPORT_VERSION,
        "result": "PASS" if not issues else "FAIL",
        "generated_at": datetime.now(UTC).isoformat(),
        "spec_version": SPEC_VERSION,
        "schema_set_version": SCHEMA_VERSION,
        "simulation_contract_versions": {
            "factory_profile": "factory-profile.v1",
            "scenario_spec": "scenario-spec.v1",
            "scenario_manifest": "scenario-manifest.v1",
            "canonicalization": "canonical-json.v1",
            "generator": "1.0.0",
        },
        "test_ids": list(TEST_IDS),
        "dataset_hash": first.dataset_hash,
        "record_collections": len(first.import_package["records"]),
        "check_count": len(checks),
        "checks": checks,
        "issues": issues,
    }


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args(argv)
    report = run_contract_checks()
    if arguments.report is not None:
        _write_report(arguments.report, report)
    print(
        f"{report['result']} Simulation contracts: "
        f"hash={report['dataset_hash']} checks={report['check_count']}"
    )
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "TEST_IDS", "main", "run_contract_checks"]
