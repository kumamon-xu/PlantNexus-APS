"""TEST-PROBLEM-REPLAY-001 fixed P1 Snapshot-to-Problem hash vector."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from app.data_validation import validate_import_package
from app.normalization.order_expansion import expand_orders
from app.planning.problem import (
    PROBLEM_BUILDER_VERSION,
    build_planning_problem,
    verify_problem,
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
