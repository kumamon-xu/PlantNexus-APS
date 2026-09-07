"""Archive and source-boundary abuse cases for TASK-P8-11."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tarfile

import pytest

from scripts.p8_frontend_distribution_check import (
    FrontendDistributionError,
    check_generated_client,
    read_frontend_archive,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("member_name", ["../escape.js", "/absolute.js", "bad\\path.js"])
def test_frontend_archive_rejects_unsafe_paths(
    tmp_path: Path,
    member_name: str,
) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    raw = b"unsafe"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo(member_name)
        info.size = len(raw)
        archive.addfile(info, BytesIO(raw))
    with pytest.raises(FrontendDistributionError, match="UNSAFE_ARCHIVE"):
        read_frontend_archive(archive_path)


def test_frontend_archive_rejects_symbolic_links(tmp_path: Path) -> None:
    archive_path = tmp_path / "symlink.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("assets/headless.js")
        info.type = tarfile.SYMTYPE
        info.linkname = "../secret"
        archive.addfile(info)
    with pytest.raises(FrontendDistributionError, match="UNSAFE_ARCHIVE"):
        read_frontend_archive(archive_path)


def test_headless_source_has_no_backend_demo_solver_or_extension_import() -> None:
    result = check_generated_client(ROOT, expected_commit="c" * 40)
    imports = result["imports"]
    assert all("backend" not in value for value in imports)
    assert all("demo" not in value for value in imports)
    assert all("solver" not in value for value in imports)
    assert result["canonical_request_transport"] == "EXACT_BROWSER_STRING_BYTES"
