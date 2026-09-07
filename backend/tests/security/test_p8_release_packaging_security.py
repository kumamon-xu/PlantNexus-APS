"""Adversarial archive, checksum, policy, and preflight tests for P8-09."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tarfile

import pytest

from app.infrastructure.release.contracts import (
    ReleaseContractError,
    read_release_archive,
    strict_json_document,
    verify_release_files,
)
from app.infrastructure.release.preflight import preflight_release
from backend.tests.p8_release_support import (
    TEST_COMMIT,
    build_test_release,
    load_test_release_files,
)


def _malicious_archive(path: Path, *, name: str, member_type: bytes = tarfile.REGTYPE) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        info = tarfile.TarInfo(name=name)
        info.type = member_type
        info.size = 1 if member_type == tarfile.REGTYPE else 0
        if member_type == tarfile.SYMTYPE:
            info.linkname = "../../outside"
        archive.addfile(info, BytesIO(b"x") if info.size else None)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "root/../escape", "root\\escape"])
def test_archive_path_traversal_and_absolute_paths_are_rejected(tmp_path, name: str) -> None:
    archive = tmp_path / "malicious.tar.gz"
    _malicious_archive(archive, name=name)
    with pytest.raises(ReleaseContractError) as captured:
        read_release_archive(archive)
    assert captured.value.code == "UNSAFE_ARCHIVE"


def test_archive_symlink_is_rejected(tmp_path) -> None:
    archive = tmp_path / "symlink.tar.gz"
    _malicious_archive(archive, name="root/link", member_type=tarfile.SYMTYPE)
    with pytest.raises(ReleaseContractError) as captured:
        read_release_archive(archive)
    assert captured.value.code == "UNSAFE_ARCHIVE"


def test_payload_tamper_is_rejected_before_startup(tmp_path) -> None:
    _, files = load_test_release_files(tmp_path)
    files["runtime/openapi/headless-api.v1.json"] += b"\n"
    with pytest.raises(ReleaseContractError) as captured:
        verify_release_files(files)
    assert captured.value.code == "CHECKSUM_MISMATCH"


def test_missing_or_tampered_archive_sidecar_is_rejected(tmp_path) -> None:
    artifact = build_test_release(tmp_path / "source")
    copied = tmp_path / artifact.archive_path.name
    copied.write_bytes(artifact.archive_path.read_bytes())
    with pytest.raises(ReleaseContractError) as missing:
        preflight_release(
            copied,
            expected_code_commit=TEST_COMMIT,
            configured_names=set(),
        )
    assert missing.value.code == "CHECKSUM_MISSING"
    copied.with_name(f"{copied.name}.sha256").write_text(
        f"{'0' * 64}  {copied.name}\n", encoding="utf-8"
    )
    with pytest.raises(ReleaseContractError) as mismatch:
        preflight_release(
            copied,
            expected_code_commit=TEST_COMMIT,
            configured_names=set(),
        )
    assert mismatch.value.code == "CHECKSUM_MISMATCH"


def test_duplicate_json_keys_and_non_finite_values_are_rejected() -> None:
    with pytest.raises(ReleaseContractError, match="INVALID_JSON"):
        strict_json_document(b'{"version":1,"version":2}')
    with pytest.raises(ReleaseContractError, match="INVALID_JSON"):
        strict_json_document(b'{"value":NaN}')
