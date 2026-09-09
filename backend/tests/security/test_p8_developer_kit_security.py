"""Archive, signature, and Core-copy security tests for TASK-P8-15."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from aps_developer_kit.contracts import (
    DeveloperKitContractError,
    read_kit_archive,
    verify_kit_archive,
)
from backend.tests.p8_developer_kit_support import build_test_kit


def test_unsigned_engineering_candidate_is_rejected_for_production(tmp_path) -> None:
    artifact = build_test_kit(tmp_path)
    with pytest.raises(DeveloperKitContractError) as raised:
        verify_kit_archive(artifact.archive_path, channel="production")
    assert raised.value.code == "KIT_SIGNATURE_REQUIRED"


def test_archive_traversal_member_is_rejected_without_extraction(tmp_path) -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("kit/../escape.txt", b"forbidden")
    path = tmp_path / "unsafe.zip"
    path.write_bytes(buffer.getvalue())
    with pytest.raises(DeveloperKitContractError) as raised:
        read_kit_archive(path)
    assert raised.value.code == "KIT_ARCHIVE_UNSAFE"


def test_kit_contains_no_demo_or_private_signing_material(tmp_path) -> None:
    artifact = build_test_kit(tmp_path)
    _, files = read_kit_archive(artifact.archive_path)
    assert not any("demo" in path.lower().split("/") for path in files)
    joined = b"\n".join(files.values()).lower()
    assert b"private key" not in joined
    assert b"signature_present\":true" not in joined.replace(b" ", b"")
