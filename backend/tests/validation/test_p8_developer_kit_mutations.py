"""Semantic mutation rejection matrix for TASK-P8-15."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, cast

import pytest

from aps_developer_kit.builder import deterministic_archive
from aps_developer_kit.contracts import (
    CHECKSUM_PATH,
    MANIFEST_PATH,
    DeveloperKitContractError,
    canonical_json_bytes,
    sha256_fingerprint,
    verify_kit_archive,
)
from backend.tests.p8_developer_kit_support import load_test_kit_files


def _json(files: dict[str, bytes], path: str) -> dict[str, object]:
    return json.loads(files[path])


def _write_json(files: dict[str, bytes], path: str, document: dict[str, object]) -> None:
    files[path] = canonical_json_bytes(document) + b"\n"


def _rebind(files: dict[str, bytes]) -> None:
    manifest = _json(files, MANIFEST_PATH)
    manifest["payload_files"] = [
        {"path": path, "bytes": len(raw), "sha256": sha256_fingerprint(raw)}
        for path, raw in sorted(files.items())
        if path not in {MANIFEST_PATH, CHECKSUM_PATH}
    ]
    manifest.pop("release_fingerprint", None)
    manifest["release_fingerprint"] = sha256_fingerprint(canonical_json_bytes(manifest))
    _write_json(files, MANIFEST_PATH, manifest)
    files[CHECKSUM_PATH] = "".join(
        f"{sha256(raw).hexdigest()}  {path}\n"
        for path, raw in sorted(files.items())
        if path != CHECKSUM_PATH
    ).encode("utf-8")


def _mutate_compatibility(files: dict[str, bytes]) -> None:
    document = _json(files, "metadata/compatibility-matrix.json")
    rows = cast(list[dict[str, Any]], document["supported_combinations"])
    rows[0]["runtime"] = "0.2.0"
    _write_json(files, "metadata/compatibility-matrix.json", document)


def _mutate_sdk_lock(files: dict[str, bytes]) -> None:
    document = _json(files, "metadata/developer-kit-lock.json")
    artifacts = cast(dict[str, dict[str, Any]], document["artifacts"])
    artifacts["sdk"]["sha256"] = f"sha256:{'0' * 64}"
    _write_json(files, "metadata/developer-kit-lock.json", document)


def _mutate_sbom(files: dict[str, bytes]) -> None:
    document = _json(files, "metadata/sbom.cdx.json")
    document["bomFormat"] = "unknown"
    _write_json(files, "metadata/sbom.cdx.json", document)


def _mutate_signing(files: dict[str, bytes]) -> None:
    document = _json(files, "metadata/signing-request.json")
    document["signature_present"] = True
    _write_json(files, "metadata/signing-request.json", document)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (_mutate_compatibility, "KIT_COMBINATION_UNSUPPORTED"),
        (_mutate_sdk_lock, "KIT_LOCK_DRIFT"),
        (_mutate_sbom, "KIT_SBOM_INVALID"),
        (_mutate_signing, "KIT_SIGNATURE_INVALID"),
    ],
)
def test_semantic_mutations_fail_closed(
    tmp_path: Path,
    mutation: Callable[[dict[str, bytes]], None],
    expected: str,
) -> None:
    _, archive_root, files = load_test_kit_files(tmp_path)
    mutation(files)
    _rebind(files)
    archive = tmp_path / "mutated.zip"
    archive.write_bytes(deterministic_archive(archive_root, files))
    with pytest.raises(DeveloperKitContractError) as raised:
        verify_kit_archive(archive)
    assert raised.value.code == expected
