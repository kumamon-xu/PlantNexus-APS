"""Pure manifest and archive tests for TASK-P8-11."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tarfile

import pytest

from scripts.p8_frontend_distribution_check import (
    FrontendDistributionError,
    inspect_frontend_distribution,
    read_frontend_archive,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_COMMIT = "a" * 40


def _fingerprint(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _build_frontend_fixture(directory: Path) -> Path:
    payload = {
        "headless.html": b'<script type="module" src="./assets/headless.js"></script>\n',
        "assets/headless.js": b"export const api = '/api/v1';\n",
    }
    manifest = {
        "manifest_version": "frontend-distribution-manifest.v1",
        "task_id": "TASK-P8-11",
        "code_commit": TEST_COMMIT,
        "frontend_version": "0.1.0",
        "entrypoint": "headless.html",
        "api_contract": "headless-http.v1",
        "openapi_sha256": _fingerprint(
            (ROOT / "backend/app/api/openapi/headless-api.v1.json").read_bytes()
        ),
        "source_date_epoch": 0,
        "reproducibility": {"assemblies": 2, "byte_identical": True},
        "files": [
            {"bytes": len(raw), "path": path, "sha256": _fingerprint(raw)}
            for path, raw in sorted(payload.items())
        ],
        "configuration": {
            "api_base_url": "VITE_PLANTNEXUS_API_BASE_URL_OR_SAME_ORIGIN_/api/v1",
            "auth": "IN_MEMORY_SESSION_PROVIDER_INJECTION",
            "credentials_mode": "omit",
            "cache_mode": "no-store",
        },
        "deployment_modes": [
            "SAME_ORIGIN_REVERSE_PROXY",
            "SEPARATE_STATIC_HOST_WITH_APPROVED_SAME_ORIGIN_GATEWAY",
        ],
        "boundaries": {
            "backend_bundled": False,
            "core_or_solver_logic_bundled": False,
            "demo_bundled": False,
            "enterprise_extension_code_bundled": False,
            "production_ready": False,
        },
        "issues": [],
        "status": "PASS",
    }
    manifest_raw = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    directory.mkdir(parents=True)
    manifest_path = directory / "frontend-distribution-manifest.v1.json"
    manifest_path.write_bytes(manifest_raw)
    archive_path = directory / "plantnexus-aps-frontend-0.1.0.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, raw in (
            *sorted(payload.items()),
            ("frontend-distribution-manifest.v1.json", manifest_raw),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, fileobj=BytesIO(raw))
    digest = sha256(archive_path.read_bytes()).hexdigest()
    directory.joinpath(f"{archive_path.name}.sha256").write_text(
        f"{digest}  {archive_path.name}\n", encoding="utf-8"
    )
    return manifest_path


def test_frontend_manifest_archive_and_sidecar_are_bound_to_one_candidate(
    tmp_path: Path,
) -> None:
    manifest = _build_frontend_fixture(tmp_path / "frontend")
    result = inspect_frontend_distribution(ROOT, manifest, expected_commit=TEST_COMMIT)
    assert result["payload_file_count"] == 2
    assert result["entrypoint"] == "headless.html"
    assert result["production_ready"] is False
    archive = manifest.parent / "plantnexus-aps-frontend-0.1.0.tar.gz"
    assert set(read_frontend_archive(archive)) == {
        "assets/headless.js",
        "frontend-distribution-manifest.v1.json",
        "headless.html",
    }


def test_frontend_sidecar_tamper_fails_closed(tmp_path: Path) -> None:
    manifest = _build_frontend_fixture(tmp_path / "frontend")
    sidecar = manifest.parent / "plantnexus-aps-frontend-0.1.0.tar.gz.sha256"
    sidecar.write_text(f"{'0' * 64}  plantnexus-aps-frontend-0.1.0.tar.gz\n")
    with pytest.raises(FrontendDistributionError, match="CHECKSUM_MISMATCH"):
        inspect_frontend_distribution(ROOT, manifest, expected_commit=TEST_COMMIT)
