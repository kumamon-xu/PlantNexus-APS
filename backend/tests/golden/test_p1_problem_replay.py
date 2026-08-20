"""TEST-PROBLEM-REPLAY-001 fixed P1 Snapshot-to-Problem hash vector."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from app.data_validation import validate_import_package
from app.normalization.order_expansion import expand_orders
from app.planning.problem import (
    PROBLEM_BUILDER_VERSION,
    PROBLEM_BUILDER_VERSION_V2,
    build_planning_problem,
    build_planning_problem_v2,
    verify_problem,
    verify_problem_v2,
)
from app.snapshots import build_planning_snapshot, import_package_id_for

TEST_ID = "TEST-PROBLEM-REPLAY-001"
ROOT = Path(__file__).resolve().parents[3]
CUTOFF = "2026-08-20T00:00:00Z"
HORIZON_END = "2026-08-21T00:00:00Z"
EXPECTED_SNAPSHOT_HASH = (
    "sha256:44f422f81490159c4b0343a52aadd7991191684fa3b25394a0dd8b8a1b7e591a"
)
EXPECTED_PROBLEM_HASH = (
    "sha256:6e4afffebf464de5c156094c894dccb5fe3efc712449f8583bcd91e1694dff72"
)
EXPECTED_CANONICAL_BYTES_SHA256 = (
    "1f00ad7a856395328e9eb2c70afe8fe5878d69c3d8618ae7ef45bca34ef08645"
)
EXPECTED_V2_SNAPSHOT_HASH = (
    "sha256:902955a43b9e80f272138980b5d42b7df1fc1024a624dd451e1f131d39e2bb5f"
)
EXPECTED_V2_PROBLEM_HASH = (
    "sha256:9927418a446dd046ddd1d835643da03fbf5cdcf8ca246ba22c3700563a17e9e8"
)
EXPECTED_V2_CANONICAL_BYTES_SHA256 = (
    "2dbe06907952d6aba303977d67a7f5d7a6ef89c4be5ac5a6ac8d74e3f95d720a"
)


def _replay():  # type: ignore[no-untyped-def]
    import_document = cast(
        dict[str, Any],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    import_document["package_id"] = import_package_id_for(import_document)
    quality = cast(
        dict[str, object], validate_import_package(import_document).document
    )
    expansion = expand_orders(import_document, quality)  # type: ignore[arg-type]
    snapshot = build_planning_snapshot(
        import_document,
        quality,
        expansion,
        cutoff_at_utc=CUTOFF,
    )
    problem = build_planning_problem(
        snapshot,
        problem_builder_version=PROBLEM_BUILDER_VERSION,
        tick_seconds=60,
        horizon_start_utc=CUTOFF,
        horizon_end_utc=HORIZON_END,
    )
    return snapshot, problem


def _replay_v2():  # type: ignore[no-untyped-def]
    import_document = cast(
        dict[str, Any],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    fact = import_document["records"]["execution_facts"][0]
    fact["status"] = "COMPLETED"
    fact.pop("remaining_quantity")
    fact.pop("remaining_seconds")
    fact["actual_end_at_utc"] = "2026-08-19T00:05:00Z"
    fact["completed_quantity"] = 10
    lock = import_document["records"]["operation_locks"][0]
    lock["routing_operation_id"] = "ROUTING-OP-002"
    lock["start_at_utc"] = CUTOFF
    lock["end_at_utc"] = "2026-08-20T02:00:00Z"
    soft_lock = deepcopy(lock)
    soft_lock["lock_id"] = "LOCK-002"
    soft_lock["lock_type"] = "SOFT_LOCK"
    soft_lock["start_at_utc"] = "2026-08-20T03:00:00Z"
    soft_lock["end_at_utc"] = "2026-08-22T02:00:00Z"
    soft_lock["source"]["source_record_id"] = "SRC-LOCK-002"
    import_document["records"]["operation_locks"].append(soft_lock)
    import_document["package_id"] = import_package_id_for(import_document)
    quality = cast(
        dict[str, object], validate_import_package(import_document).document
    )
    expansion = expand_orders(import_document, quality)  # type: ignore[arg-type]
    snapshot = build_planning_snapshot(
        import_document,
        quality,
        expansion,
        cutoff_at_utc=CUTOFF,
    )
    problem = build_planning_problem_v2(
        snapshot,
        priority_facts={
            "DEMAND-001": {
                "priority_weight": 2,
                "source_system": "plantnexus-synthetic-policy",
                "source_version": "1.0.0",
                "source_record_id": "SIM-P2-DELIVERY-PRIORITY-001",
            }
        },
        problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
        tick_seconds=60,
        horizon_start_utc=CUTOFF,
        horizon_end_utc=HORIZON_END,
    )
    return snapshot, problem


def test_p1_canonical_snapshot_replays_to_fixed_problem_hash_and_bytes() -> None:
    first_snapshot, first_problem = _replay()
    second_snapshot, second_problem = _replay()

    assert first_snapshot.snapshot_hash == EXPECTED_SNAPSHOT_HASH
    assert first_problem.problem_hash == EXPECTED_PROBLEM_HASH
    assert sha256(first_problem.canonical_bytes).hexdigest() == (
        EXPECTED_CANONICAL_BYTES_SHA256
    )
    assert len(first_problem.canonical_bytes) == 1827
    assert first_snapshot == second_snapshot
    assert first_problem == second_problem
    assert first_problem.document["snapshot_id"] == first_snapshot.snapshot_id
    assert len(first_problem.document["resource_ids"]) == 1
    assert len(first_problem.document["operation_instances"]) == 2
    assert len(first_problem.document["precedence_edges"]) == 1
    assert len(first_problem.document["resource_unavailable_intervals"]) == 0
    assert "generated_at_utc" not in first_problem.document
    verify_problem(first_problem)


def test_fixed_problem_vector_round_trips_through_published_v1_schema() -> None:
    _snapshot, problem = _replay()
    schema = json.loads(
        (ROOT / "schemas/json/planning-problem.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    validator.validate(problem.document)
    assert json.loads(problem.canonical_bytes) == problem.document


def test_p2_v2_problem_replays_to_fixed_hash_bytes_and_published_sample() -> None:
    first_snapshot, first_problem = _replay_v2()
    second_snapshot, second_problem = _replay_v2()
    sample = json.loads(
        (ROOT / "schemas/samples/planning-problem.v2.synthetic.json").read_text(
            encoding="utf-8"
        )
    )

    assert first_snapshot.snapshot_hash == EXPECTED_V2_SNAPSHOT_HASH
    assert first_problem.problem_hash == EXPECTED_V2_PROBLEM_HASH
    assert sha256(first_problem.canonical_bytes).hexdigest() == (
        EXPECTED_V2_CANONICAL_BYTES_SHA256
    )
    assert len(first_problem.canonical_bytes) == 3366
    assert first_snapshot == second_snapshot
    assert first_problem == second_problem
    assert first_problem.document == sample
    assert len(first_problem.document["historical_completion_anchors"]) == 1
    assert len(first_problem.document["operation_locks"]) == 2
    verify_problem_v2(first_problem)


def test_fixed_v2_problem_vector_round_trips_through_published_v2_schema() -> None:
    _snapshot, problem = _replay_v2()
    schema = json.loads(
        (ROOT / "schemas/json/planning-problem.v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    validator.validate(problem.document)
    assert json.loads(problem.canonical_bytes) == problem.document
