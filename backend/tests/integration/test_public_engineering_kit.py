"""A successor Kit retains its exact Runtime and predecessor registry entry."""

from hashlib import sha256
import json
from typing import Any, cast

import pytest

from aps_developer_kit.builder import build_developer_kit
from aps_developer_kit.contracts import DeveloperKitContractError, verify_kit_archive
from app.infrastructure.release.contracts import verify_release_archive
from backend.tests.p8_developer_kit_support import ROOT, TEST_COMMIT, TEST_EPOCH
from backend.tests.p8_release_support import build_test_release
from scripts.github_release import digest, public_files


def test_successor_separates_source_identity_and_retains_immutable_predecessor(tmp_path):
    runtime = build_test_release(tmp_path / "runtime")
    verified_runtime = verify_release_archive(runtime.archive_path)
    old = build_developer_kit(
        ROOT, runtime.archive_path, tmp_path / "registry",
        code_commit=TEST_COMMIT, epoch=TEST_EPOCH,
    )
    old_bytes = old.archive_path.read_bytes()
    policy = json.loads((ROOT / "infra/release/developer-kit-release-policy-1.0.1.v1.json").read_bytes())
    policy["runtime_input"] = {
        "code_commit": TEST_COMMIT,
        "release_fingerprint": verified_runtime.release_fingerprint,
        "archive_sha256": "sha256:" + sha256(runtime.archive_path.read_bytes()).hexdigest(),
    }
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    options: dict[str, Any] = dict(
        code_commit="c" * 40, epoch=TEST_EPOCH, kit_version="1.0.1",
        policy_path=policy_path, runtime_code_commit=TEST_COMMIT,
    )
    new = build_developer_kit(ROOT, runtime.archive_path, tmp_path / "registry", **options)
    repeat = build_developer_kit(ROOT, runtime.archive_path, tmp_path / "repeat", **options)
    assert repeat.archive_path.read_bytes() == new.archive_path.read_bytes()
    verified = verify_kit_archive(new.archive_path, channel="public-engineering")
    for channel in ("public", "production", "unknown"):
        with pytest.raises(DeveloperKitContractError, match="KIT_SIGNATURE_REQUIRED"):
            verify_kit_archive(new.archive_path, channel=channel)
    with pytest.raises(DeveloperKitContractError, match="KIT_SIGNATURE_REQUIRED"):
        verify_kit_archive(old.archive_path, channel="public-engineering")
    assert verified.code_commit == "c" * 40
    assert cast(Any, verified.lock["runtime_identity"])["code_commit"] == TEST_COMMIT
    assert verified.files[cast(Any, verified.lock["artifacts"])["runtime"]["path"]] == runtime.archive_path.read_bytes()
    assert old.archive_path.read_bytes() == old_bytes
    assert len(json.loads(new.registry_path.read_bytes())["entries"]) == 2
    with pytest.raises(DeveloperKitContractError, match="KIT_REGISTRY_CONFLICT"):
        build_developer_kit(
            ROOT, runtime.archive_path, tmp_path / "registry", **{**options, "epoch": TEST_EPOCH + 1}
        )
    policy["runtime_input"]["archive_sha256"] = "sha256:" + "0" * 64
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(DeveloperKitContractError, match="KIT_RUNTIME_IDENTITY_MISMATCH"):
        build_developer_kit(ROOT, runtime.archive_path, tmp_path / "bad", **options)


def test_legacy_kit_cannot_embed_a_different_source_runtime(tmp_path):
    runtime = build_test_release(tmp_path / "runtime")
    with pytest.raises(DeveloperKitContractError, match="KIT_RUNTIME_IDENTITY_MISMATCH"):
        build_developer_kit(
            ROOT, runtime.archive_path, tmp_path / "kit", code_commit="b" * 40,
            epoch=TEST_EPOCH, runtime_code_commit=TEST_COMMIT,
        )


def test_public_package_uses_tracked_interfaces_and_excludes_private_workspace():
    files = public_files(ROOT)
    assert "README.md" in files
    assert any(name.startswith("schemas/") for name in files)
    assert any(name.startswith("backend/aps_extension_sdk/") for name in files)
    assert not any(name.startswith((
        "docs/tasks/", "docs/governance/", "docs/agents/", "build/", "deliverables/",
        "backend/app/", ".env",
    )) for name in files)
    assert "docs/core/APS_IMPLEMENTATION_SPEC.md" not in files
    assert digest(ROOT / "README.md") == sha256((ROOT / "README.md").read_bytes()).hexdigest()
