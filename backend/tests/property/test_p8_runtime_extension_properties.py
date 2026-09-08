"""Property evidence for deterministic P8-13 loading and invocation."""

from __future__ import annotations

from pathlib import Path

from hypothesis import HealthCheck, given, settings, strategies as st

from backend.tests.p8_runtime_extension_support import runtime_extension_fixture


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(seed=st.integers(min_value=0, max_value=1_000_000))
def test_same_catalog_and_artifact_always_resolve_byte_identically(
    tmp_path: Path,
    seed: int,
) -> None:
    fixture = runtime_extension_fixture(
        tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'property.db').as_posix()}",
        configuration_values={"seed": seed, "enabled": True},
    )
    first = fixture.load()
    second = fixture.load()
    assert first.canonical_bytes == second.canonical_bytes
    assert first.extension_set_reference_bytes == second.extension_set_reference_bytes


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    pairs=st.dictionaries(
        keys=st.sampled_from(["alpha", "beta", "gamma", "delta"]),
        values=st.integers(min_value=-100, max_value=100),
        min_size=1,
        max_size=4,
    )
)
def test_json_key_order_does_not_change_spi_output(
    tmp_path: Path,
    pairs: dict[str, int],
) -> None:
    fixture = runtime_extension_fixture(
        tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'invoke.db').as_posix()}",
    )
    adapter = fixture.load()
    reversed_pairs = dict(reversed(tuple(pairs.items())))
    common = {
        "scope": {"tenant_id": "TENANT-PROPERTY"},
        "provenance": {"planning_run_id": "planning-run-property"},
    }
    first = adapter.invoke_objectives(facts=pairs, **common)
    second = adapter.invoke_objectives(facts=reversed_pairs, **common)
    assert first == second


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(seed=st.integers(min_value=0, max_value=1_000_000))
def test_configuration_change_always_changes_extension_set_fingerprint(
    tmp_path: Path,
    seed: int,
) -> None:
    first = runtime_extension_fixture(
        tmp_path / "first",
        database_url=f"sqlite:///{(tmp_path / 'first.db').as_posix()}",
        configuration_values={"seed": seed},
    ).load()
    second = runtime_extension_fixture(
        tmp_path / "second",
        database_url=f"sqlite:///{(tmp_path / 'second.db').as_posix()}",
        configuration_values={"seed": seed + 1},
    ).load()
    assert first.extension_set_reference["extension_set_fingerprint"] != (
        second.extension_set_reference["extension_set_fingerprint"]
    )
