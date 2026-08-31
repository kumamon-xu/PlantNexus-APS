"""Collect repository-level P5 evidence tests with the existing Backend suite."""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
P5_TESTS = (
    ROOT / "tests/p5/test_p5_capability_qualification_unit.py",
    ROOT / "tests/p5/test_p5_capability_qualification_integration.py",
)
FULL_BACKEND_SUITES = tuple(
    ROOT / f"backend/tests/{name}"
    for name in (
        "unit",
        "contract",
        "simulation",
        "golden",
        "validation",
        "integration",
        "property",
        "security",
    )
)


def _contains(target: Path, candidate: Path) -> bool:
    return target == candidate or (target.is_dir() and candidate.is_relative_to(target))


def pytest_configure(config: pytest.Config) -> None:
    """Append bounded P5 tests only to the repository's complete Backend suite."""

    targets = [
        (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
        for value in config.args
    ]
    if not all(suite in targets for suite in FULL_BACKEND_SUITES):
        return
    for test_path in P5_TESTS:
        if not any(_contains(target, test_path) for target in targets):
            config.args.append(str(test_path))
            targets.append(test_path)
