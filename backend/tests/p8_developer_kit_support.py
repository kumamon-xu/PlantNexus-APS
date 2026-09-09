"""Small deterministic fixtures for TEST-P8-DEVELOPER-KIT-COMPATIBILITY-001."""

from __future__ import annotations

from pathlib import Path

from aps_developer_kit.builder import DeveloperKitArtifact, build_developer_kit
from aps_developer_kit.contracts import read_kit_archive
from backend.tests.p8_release_support import TEST_COMMIT, TEST_EPOCH, build_test_release


ROOT = Path(__file__).resolve().parents[2]


def build_test_kit(directory: Path) -> DeveloperKitArtifact:
    runtime = build_test_release(directory / "runtime")
    return build_developer_kit(
        ROOT,
        runtime.archive_path,
        directory / "kit",
        code_commit=TEST_COMMIT,
        epoch=TEST_EPOCH,
    )


def load_test_kit_files(
    directory: Path,
) -> tuple[DeveloperKitArtifact, str, dict[str, bytes]]:
    artifact = build_test_kit(directory)
    archive_root, files = read_kit_archive(artifact.archive_path)
    return artifact, archive_root, files


__all__ = [
    "ROOT",
    "TEST_COMMIT",
    "TEST_EPOCH",
    "build_test_kit",
    "load_test_kit_files",
]
