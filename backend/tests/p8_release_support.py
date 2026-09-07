"""Small deterministic release fixtures shared by P8-09 tests."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.release.builder import ReleaseArtifact, build_release
from app.infrastructure.release.contracts import read_release_archive


ROOT = Path(__file__).resolve().parents[2]
TEST_COMMIT = "a" * 40
TEST_EPOCH = 315_532_800


def build_test_release(directory: Path, *, commit: str = TEST_COMMIT) -> ReleaseArtifact:
    wheel = directory / "wheel/plantnexus_aps-0.0.0-py3-none-any.whl"
    wheel.parent.mkdir(parents=True, exist_ok=True)
    wheel.write_bytes(b"P8-09 deterministic test wheel\n")
    return build_release(
        ROOT,
        wheel,
        directory / "release",
        code_commit=commit,
        epoch=TEST_EPOCH,
    )


def load_test_release_files(directory: Path) -> tuple[ReleaseArtifact, dict[str, bytes]]:
    artifact = build_test_release(directory)
    _, files = read_release_archive(artifact.archive_path)
    return artifact, files


__all__ = [
    "ROOT",
    "TEST_COMMIT",
    "TEST_EPOCH",
    "build_test_release",
    "load_test_release_files",
]
