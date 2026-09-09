"""Deterministic assembly and registry tests for TASK-P8-15."""

from __future__ import annotations

from aps_developer_kit.builder import build_developer_kit, load_policy
from aps_developer_kit.contracts import strict_json_document
from backend.tests.p8_developer_kit_support import (
    ROOT,
    TEST_COMMIT,
    TEST_EPOCH,
    build_test_kit,
)
from backend.tests.p8_release_support import build_test_release


def test_same_inputs_build_byte_identical_content_addressed_kit(tmp_path) -> None:
    runtime = build_test_release(tmp_path / "runtime")
    first = build_developer_kit(
        ROOT,
        runtime.archive_path,
        tmp_path / "first",
        code_commit=TEST_COMMIT,
        epoch=TEST_EPOCH,
    )
    second = build_developer_kit(
        ROOT,
        runtime.archive_path,
        tmp_path / "second",
        code_commit=TEST_COMMIT,
        epoch=TEST_EPOCH,
    )
    assert first.archive_sha256 == second.archive_sha256
    assert first.archive_path.read_bytes() == second.archive_path.read_bytes()
    assert first.release_fingerprint == second.release_fingerprint


def test_registry_is_append_only_and_idempotent_for_same_bytes(tmp_path) -> None:
    first = build_test_kit(tmp_path)
    runtime_archive = next((tmp_path / "runtime/release").rglob("*.tar.gz"))
    second = build_developer_kit(
        ROOT,
        runtime_archive,
        tmp_path / "kit",
        code_commit=TEST_COMMIT,
        epoch=TEST_EPOCH,
    )
    registry = strict_json_document(first.registry_path.read_bytes())
    assert first.archive_path == second.archive_path
    assert registry["append_only"] is True
    assert len(registry["entries"]) == 1


def test_policy_locks_tool_dependencies_and_disallows_remote_publication() -> None:
    policy = load_policy(ROOT)
    assert policy["artifact"]["remote_publication"] is False
    assert policy["compatibility"]["automatic_upgrade"] is False
    assert set(policy["tool_dependencies"]) == {
        "attrs",
        "jsonschema",
        "jsonschema-specifications",
        "referencing",
        "rpds-py",
    }
