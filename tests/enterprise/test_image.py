"""Release boundary and identity rejection tests; no Docker or secrets needed."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tarfile

import pytest

from scripts import enterprise_image_build as image


def fixture_archive(tmp_path: Path, *, extra: str | None = None, link: bool = False,
                    duplicate: bool = False, bad_payload: bool = False) -> tuple[Path, dict]:
    files = {"runtime/requirements/runtime-requirements.lock": b"locked",
             "runtime/wheels/test.whl": b"wheel"}
    inputs = {"source_sha": "a" * 40,
              "requirements_sha256": image.sha256(b"locked"), "wheel_sha256": image.sha256(b"wheel")}
    manifest = {"code_commit": inputs["source_sha"], "payload_files": [
        {"path": n, "bytes": len(raw), "sha256": "sha256:" + image.sha256(raw)}
        for n, raw in sorted(files.items())]}
    fingerprint = "sha256:" + image.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    inputs["release_fingerprint"] = fingerprint
    files["metadata/release-manifest.json"] = json.dumps({**manifest, "release_fingerprint": fingerprint}).encode()
    files["metadata/checksums.sha256"] = "".join(
        f"{image.sha256(raw)}  {n}\n" for n, raw in sorted(files.items())).encode()
    if bad_payload:
        files["runtime/wheels/test.whl"] = b"wrong"
    path = tmp_path/"release.tar.gz"
    with tarfile.open(path, "w:gz") as t:
        for n, raw in files.items():
            member = tarfile.TarInfo("plantnexus-aps-runtime-0.1.0-linux-amd64/" + n)
            member.size = len(raw)
            t.addfile(member, io.BytesIO(raw))
        if extra:
            member = tarfile.TarInfo(extra)
            if link:
                member.type = tarfile.SYMTYPE
                member.linkname = "/etc/passwd"
            t.addfile(member)
        if duplicate:
            member = tarfile.TarInfo("plantnexus-aps-runtime-0.1.0-linux-amd64/runtime/wheels/test.whl")
            t.addfile(member)
    inputs["archive_sha256"] = image.sha256(path.read_bytes())
    return path, inputs


def test_valid_release_requires_exact_inventory(tmp_path):
    path, inputs = fixture_archive(tmp_path)
    assert len(image.read_release(path, inputs)) == 4


@pytest.mark.parametrize("extra,link", [
    ("/absolute", False), ("plantnexus-aps-runtime-0.1.0-linux-amd64/../escape", False),
    ("plantnexus-aps-runtime-0.1.0-linux-amd64/link", True),
    ("plantnexus-aps-runtime-0.1.0-linux-amd64/undeclared-secret", False)])
def test_rejects_unsafe_or_undeclared_archive(tmp_path, extra, link):
    path, inputs = fixture_archive(tmp_path, extra=extra, link=link)
    with pytest.raises(ValueError):
        image.read_release(path, inputs)


def test_duplicate_member_rejected(tmp_path):
    path, inputs = fixture_archive(tmp_path, duplicate=True)
    with pytest.raises(ValueError, match="DUPLICATE"):
        image.read_release(path, inputs)


def test_tamper_rejected_even_when_outer_hash_updated(tmp_path):
    path, inputs = fixture_archive(tmp_path, bad_payload=True)
    with pytest.raises(ValueError, match="PAYLOAD"):
        image.read_release(path, inputs)


@pytest.mark.parametrize("field,value", [("archive_sha256", "0"*64), ("source_sha", "b"*40),
                                       ("requirements_sha256", "0"*64), ("wheel_sha256", "0"*64)])
def test_identity_mismatch_rejected(tmp_path, field, value):
    path, inputs = fixture_archive(tmp_path)
    inputs[field] = value
    with pytest.raises(ValueError):
        image.read_release(path, inputs)


@pytest.mark.parametrize("field,value", [("base_image", "python:latest"),
                                       ("scanner_image", "aquasec/trivy:0.74.0"),
                                       ("platform", "linux/arm64"), ("source_sha", "HEAD")])
def test_floating_or_wrong_platform_inputs_rejected(tmp_path, field, value):
    inputs = image.load_inputs()
    inputs[field] = value
    p = tmp_path/"inputs.json"
    p.write_text(json.dumps(inputs))
    with pytest.raises(ValueError):
        image.load_inputs(p)


def test_context_excludes_source_checkout_and_config(tmp_path):
    files = {"runtime/wheels/test.whl": b"wheel", "runtime/requirements/runtime-requirements.lock": b"lock",
             "runtime/backend/app/leak.py": b"source", "runtime/.env": b"secret",
             "runtime/backend/migrations/env.py": b"migration", "runtime/alembic.ini": b"config",
             "metadata/release-manifest.json": b"{}"}
    target = tmp_path/"context"
    inventory = image.prepare_context(files, target)
    assert not (target/"runtime/backend/app").exists()
    assert not (target/"runtime/.env").exists()
    assert (target/"runtime/backend/migrations/env.py").read_bytes() == b"migration"
    assert "runtime/.env" not in {e["path"] for e in inventory}
    assert (target/".dockerignore").read_text().startswith("**\n")
    with pytest.raises(FileExistsError):
        image.prepare_context(files, target)


def test_dockerfile_matches_frozen_base_and_four_role_model():
    inputs = image.load_inputs()
    dockerfile = (image.ROOT/"infra/enterprise/Dockerfile").read_text()
    assert dockerfile.count("FROM " + inputs["base_image"]) == 2
    assert "--require-hashes" in dockerfile and "--only-binary=:all:" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "COPY backend" not in dockerfile and "uv sync" not in dockerfile
    assert inputs["source_sha"] in dockerfile


def test_image_user_and_revision_are_enforced(monkeypatch):
    data = [{"Os": "linux", "Architecture": "amd64", "Config": {"User": "0"}}]
    monkeypatch.setattr(image, "run", lambda *_args, **_kw: json.dumps(data).encode())
    with pytest.raises(ValueError, match="USER"):
        image.inspect_image("image", image.load_inputs(), "a"*40)


def test_unresolved_os_risk_is_not_security_approval():
    finding = {"class": "os-pkgs", "VulnerabilityID": "CVE-example", "PkgName": "lib",
               "InstalledVersion": "1", "Severity": "HIGH", "Status": "affected"}
    policy = {"unresolved_os_findings": [{"id": "CVE-example", "package": "lib", "version": "1",
                                         "severity": "HIGH", "vendor_status": "affected"}],
              "runtime_vex_assessments": []}
    result = image.assess_security({"vulnerabilities": [finding]}, policy)
    assert result["upstream_os_raw_count"] == 1
    assert result["production_security_approval"] is False
    with pytest.raises(ValueError, match="FIXABLE"):
        image.assess_security({"vulnerabilities": [{**finding, "FixedVersion": "2"}]}, policy)
    with pytest.raises(ValueError, match="NEW"):
        image.assess_security({"vulnerabilities": [{**finding, "VulnerabilityID": "CVE-new"}]}, policy)


def test_python_finding_cannot_use_os_recording_exception():
    with pytest.raises(ValueError, match="UNASSESSED_RUNTIME"):
        image.assess_security({"vulnerabilities": [{"class": "lang-pkgs", "VulnerabilityID": "CVE-new",
                                                  "PkgName": "pip", "InstalledVersion": "1"}]},
                              {"unresolved_os_findings": [], "runtime_vex_assessments": []})


def test_secret_in_deleted_or_compressed_layer_is_rejected(tmp_path):
    import gzip
    path = tmp_path/"image.tar"
    raw = gzip.compress(b"old-layer-file=" + image.CANARY)
    with tarfile.open(path, "w") as t:
        entry = tarfile.TarInfo("blobs/old-layer")
        entry.size = len(raw)
        t.addfile(entry, io.BytesIO(raw))
    with pytest.raises(ValueError, match="CANARY_LEAK"):
        image.verify_no_canary(path)
