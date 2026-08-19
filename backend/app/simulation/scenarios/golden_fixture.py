"""Load and replay the immutable SIM-MINIMAL-001 artifact bundle.

This module checks artifact shape, provenance references, and canonical Import
bytes/hash.  It deliberately does not evaluate C-001 through C-011; the P0
Golden test recomputes those rules independently, and TASK-P0-07 owns the
first reusable rule evaluator.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app import SCHEMA_VERSION, SPEC_VERSION
from app.domain.contracts import ImportPackageDocument
from app.simulation.generators.contracts import (
    GeneratedScenarioPackage,
    GenerationContext,
)
from app.simulation.generators.determinism import (
    canonical_json_bytes,
    dataset_sha256,
)
from app.simulation.generators.package_contract import (
    validate_generated_scenario_package,
)
from app.simulation.profiles.contracts import (
    FactoryProfileDocument,
    validate_factory_profile_contract,
)
from app.simulation.scenarios.contracts import (
    ScenarioManifestDocument,
    ScenarioSpecDocument,
    validate_scenario_manifest_contract,
    validate_scenario_spec_contract,
)


REPORT_VERSION = "golden-fixture-replay-report.v1"
TEST_IDS = (
    "TEST-GOLDEN-FJSP",
    "TEST-SCENARIO-REPLAY",
    "TEST-CALENDAR",
    "TEST-MATERIAL",
    "TEST-CROSS-WORKSHOP",
    "TEST-MAX-LAG",
)
CONSTRAINT_IDS = tuple(f"C-{index:03d}" for index in range(1, 12))
ARTIFACT_FILENAMES = (
    "calculation-note.md",
    "expected-kpis.json",
    "expected-validation.json",
    "factory-profile.json",
    "golden-schedule.json",
    "import-package.json",
    "scenario-manifest.json",
    "scenario-spec.json",
)
JSON_ARTIFACT_FILENAMES = tuple(
    name for name in ARTIFACT_FILENAMES if name.endswith(".json")
)

type JsonObject = dict[str, Any]


class GoldenFixtureError(ValueError):
    """The committed Golden fixture cannot be safely replayed."""


@dataclass(frozen=True, slots=True)
class GoldenFixtureBundle:
    """The seven JSON documents in one strict Golden fixture directory."""

    root: Path
    factory_profile: JsonObject
    scenario_spec: JsonObject
    scenario_manifest: JsonObject
    import_package: JsonObject
    golden_schedule: JsonObject
    expected_validation: JsonObject
    expected_kpis: JsonObject


def _load_json_object(path: Path) -> JsonObject:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise GoldenFixtureError(f"cannot read {path.name}: {error}") from error
    except json.JSONDecodeError as error:
        raise GoldenFixtureError(
            f"{path.name} is not valid JSON at line {error.lineno}, column {error.colno}"
        ) from error
    if not isinstance(payload, dict):
        raise GoldenFixtureError(f"{path.name} root must be a JSON object")
    return cast(JsonObject, payload)


def load_golden_fixture(root: Path) -> GoldenFixtureBundle:
    """Load exactly the versioned artifacts declared by the P0 fixture."""

    if not root.is_dir():
        raise GoldenFixtureError(f"fixture directory does not exist: {root}")
    observed = {path.name for path in root.iterdir()}
    expected = set(ARTIFACT_FILENAMES)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    if missing or unexpected:
        parts = []
        if missing:
            parts.append(f"missing artifacts: {', '.join(missing)}")
        if unexpected:
            parts.append(f"unexpected artifacts: {', '.join(unexpected)}")
        raise GoldenFixtureError("; ".join(parts))

    documents = {
        name: _load_json_object(root / name) for name in JSON_ARTIFACT_FILENAMES
    }
    return GoldenFixtureBundle(
        root=root,
        factory_profile=documents["factory-profile.json"],
        scenario_spec=documents["scenario-spec.json"],
        scenario_manifest=documents["scenario-manifest.json"],
        import_package=documents["import-package.json"],
        golden_schedule=documents["golden-schedule.json"],
        expected_validation=documents["expected-validation.json"],
        expected_kpis=documents["expected-kpis.json"],
    )


def _require_equal(actual: object, expected: object, location: str) -> None:
    if actual != expected:
        raise GoldenFixtureError(
            f"{location} mismatch: observed={actual!r}, expected={expected!r}"
        )


def _require_mapping(value: object, location: str) -> JsonObject:
    if not isinstance(value, dict):
        raise GoldenFixtureError(f"{location} must be a JSON object")
    return cast(JsonObject, value)


def _require_list(value: object, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise GoldenFixtureError(f"{location} must be a JSON array")
    return cast(list[Any], value)


def verify_golden_fixture(bundle: GoldenFixtureBundle) -> dict[str, object]:
    """Verify contracts, identity joins, and canonical non-empty Import replay."""

    profile = cast(FactoryProfileDocument, bundle.factory_profile)
    scenario = cast(ScenarioSpecDocument, bundle.scenario_spec)
    manifest = cast(ScenarioManifestDocument, bundle.scenario_manifest)
    import_package = cast(ImportPackageDocument, bundle.import_package)

    try:
        validate_factory_profile_contract(profile)
        validate_scenario_spec_contract(scenario)
        validate_scenario_manifest_contract(manifest)

        profile_reference = {
            "profile_id": profile["profile_id"],
            "profile_version": profile["profile_version"],
        }
        scenario_reference = {
            "scenario_id": scenario["scenario_id"],
            "scenario_version": scenario["scenario_version"],
        }
        _require_equal(
            scenario["factory_profile"], profile_reference, "Scenario profile reference"
        )
        _require_equal(
            manifest["factory_profile"], profile_reference, "manifest profile reference"
        )
        _require_equal(
            manifest["scenario"], scenario_reference, "manifest Scenario reference"
        )
        _require_equal(
            manifest["generator"], scenario["generator"], "manifest Generator reference"
        )
        _require_equal(manifest["seed"], scenario["seed"], "manifest seed")
        _require_equal(
            manifest["required_capabilities"],
            scenario["required_capabilities"],
            "manifest capabilities",
        )

        context = GenerationContext.create(
            scenario_id=scenario["scenario_id"],
            scenario_version=scenario["scenario_version"],
            profile_id=profile["profile_id"],
            profile_version=profile["profile_version"],
            generator_id=scenario["generator"]["generator_id"],
            generator_version=scenario["generator"]["generator_version"],
            seed=scenario["seed"],
            target=manifest["target_environment"],
            required_capabilities=scenario["required_capabilities"],
        )
        _require_equal(import_package["synthetic"], True, "Import synthetic flag")
        _require_equal(
            import_package.get("scenario_id"), context.scenario_id, "Import scenario_id"
        )
        _require_equal(
            import_package["source_versions"],
            {
                "factory_profile": context.profile_version,
                "scenario": context.scenario_version,
                "synthetic_generator": context.generator_version,
            },
            "Import source_versions",
        )

        canonical_dataset = canonical_json_bytes(bundle.import_package)
        digest = dataset_sha256(canonical_dataset)
        generated = GeneratedScenarioPackage(
            import_package=import_package,
            manifest=manifest,
            canonical_dataset=canonical_dataset,
            dataset_hash=digest,
        )
        validate_generated_scenario_package(generated)

        schedule_scenario = _require_mapping(
            bundle.golden_schedule.get("scenario"), "Golden Schedule scenario"
        )
        _require_equal(schedule_scenario, scenario_reference, "Golden Schedule scenario")
        validation_scenario = _require_mapping(
            bundle.expected_validation.get("scenario"), "expected validation scenario"
        )
        kpi_scenario = _require_mapping(
            bundle.expected_kpis.get("scenario"), "expected KPI scenario"
        )
        _require_equal(validation_scenario, scenario_reference, "expected validation scenario")
        _require_equal(kpi_scenario, scenario_reference, "expected KPI scenario")
        schedule_id = bundle.golden_schedule.get("schedule_id")
        _require_equal(
            bundle.expected_validation.get("schedule_id"),
            schedule_id,
            "expected validation schedule_id",
        )
        _require_equal(
            bundle.expected_kpis.get("schedule_id"),
            schedule_id,
            "expected KPI schedule_id",
        )

        checks = _require_list(
            bundle.expected_validation.get("checks"), "expected validation checks"
        )
        check_documents = [
            _require_mapping(value, f"expected validation checks[{index}]")
            for index, value in enumerate(checks)
        ]
        constraint_ids = tuple(
            str(check.get("constraint_id")) for check in check_documents
        )
        _require_equal(constraint_ids, CONSTRAINT_IDS, "expected validation C-ID order")
        _require_equal(
            bundle.expected_validation.get("status"), "PASS", "expected validation status"
        )
        _require_equal(
            bundle.expected_validation.get("hard_violation_count"),
            0,
            "expected hard violation count",
        )
        not_applicable = tuple(
            str(check["constraint_id"])
            for check in check_documents
            if check.get("result") == "NOT_APPLICABLE"
        )
        _require_equal(not_applicable, ("C-007", "C-008"), "N/A constraint set")

        records = _require_mapping(import_package["records"], "Import records")
        if not records:
            raise GoldenFixtureError("Import records must be non-empty")
        record_count = sum(
            len(_require_list(collection, f"Import records.{name}"))
            for name, collection in records.items()
        )
        assignments = _require_list(
            bundle.golden_schedule.get("assignments"), "Golden Schedule assignments"
        )
    except GoldenFixtureError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise GoldenFixtureError(f"fixture contract validation failed: {error}") from error

    return {
        "scenario_id": context.scenario_id,
        "scenario_version": context.scenario_version,
        "profile_id": context.profile_id,
        "profile_version": context.profile_version,
        "generator_id": context.generator_id,
        "generator_version": context.generator_version,
        "seed": context.seed,
        "dataset_hash": digest,
        "canonical_dataset_bytes": len(canonical_dataset),
        "artifact_count": len(ARTIFACT_FILENAMES),
        "record_collection_count": len(records),
        "record_count": record_count,
        "assignment_count": len(assignments),
        "constraint_expectation_count": len(checks),
        "not_applicable_constraints": list(not_applicable),
    }


def run_replay_checks(fixture: Path) -> dict[str, object]:
    """Return a machine-readable replay report without claiming rule evaluation."""

    issues: list[str] = []
    summary: dict[str, object] = {}
    try:
        summary = verify_golden_fixture(load_golden_fixture(fixture))
    except GoldenFixtureError as error:
        issues.append(str(error))
    return {
        "report_version": REPORT_VERSION,
        "result": "PASS" if not issues else "FAIL",
        "generated_at": datetime.now(UTC).isoformat(),
        "spec_version": SPEC_VERSION,
        "schema_set_version": SCHEMA_VERSION,
        "fixture_path": fixture.as_posix(),
        "scope": "artifact-integrity-and-replay-only",
        "test_ids": list(TEST_IDS),
        **summary,
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
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args(argv)
    report = run_replay_checks(arguments.fixture)
    if arguments.report is not None:
        _write_report(arguments.report, report)
    print(
        f"{report['result']} Golden fixture replay: "
        f"hash={report.get('dataset_hash', '<unavailable>')} "
        f"issues={len(cast(list[object], report['issues']))}"
    )
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ARTIFACT_FILENAMES",
    "CONSTRAINT_IDS",
    "GoldenFixtureBundle",
    "GoldenFixtureError",
    "REPORT_VERSION",
    "TEST_IDS",
    "load_golden_fixture",
    "main",
    "run_replay_checks",
    "verify_golden_fixture",
]
