"""TEST-P9-DELIVERY-001: build identity, exact locks and source rejection."""

from base64 import urlsafe_b64encode
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from aps_developer_kit.builder import load_policy
from aps_developer_kit.contracts import DeveloperKitContractError, plan_upgrade
from aps_extension_tooling.packaging import deterministic_zip
from app.infrastructure.release.contracts import ReleaseContractError
from app.infrastructure.release.p9 import (
    BUILD_METADATA, KIT, KIT_POLICY, RUNTIME, RUNTIME_POLICY,
    candidate_wheel, verify_candidate_wheel,
)


ROOT = Path(__file__).resolve().parents[3]
COMMIT = "a" * 40


def source_wheel() -> bytes:
    return deterministic_zip({
        "app/__init__.py": b'RUNTIME_VERSION = "0.1.0"\nCORE_VERSION = "0.0.0"\n',
        "app/unchanged.py": b"# unchanged source\n",
        "plantnexus_aps-0.0.0.dist-info/RECORD": b"",
    })


@pytest.mark.parametrize("version", ["0.2.0", "0.2.1"])
def test_generated_version_is_reproducible_and_records_all_changed_bytes(version: str) -> None:
    policy = (ROOT / f"infra/release/runtime-release-policy-{version}.v1.json").read_bytes()
    original = source_wheel()
    candidate = candidate_wheel(original, code_commit=COMMIT, policy_bytes=policy)
    assert candidate == candidate_wheel(original, code_commit=COMMIT, policy_bytes=policy)
    verify_candidate_wheel(candidate, code_commit=COMMIT, policy_bytes=policy)
    with ZipFile(BytesIO(candidate)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    assert files["app/unchanged.py"] == b"# unchanged source\n"
    assert f'RUNTIME_VERSION = "{version}"'.encode() in files["app/__init__.py"]
    provenance = json.loads(files[BUILD_METADATA])
    assert provenance["source_wheel_sha256"] == "sha256:" + sha256(original).hexdigest()
    assert provenance["other_source_changes"] == []
    for line in files["plantnexus_aps-0.0.0.dist-info/RECORD"].decode().splitlines():
        name, digest, size = line.split(",")
        if digest:
            assert digest == "sha256=" + urlsafe_b64encode(sha256(files[name]).digest()).rstrip(b"=").decode()
            assert int(size) == len(files[name])


@pytest.mark.parametrize("fault", ["commit", "policy", "source", "untransformed"])
def test_candidate_rejects_wrong_build_identity(fault: str) -> None:
    policy = (ROOT / RUNTIME_POLICY).read_bytes()
    candidate = candidate_wheel(source_wheel(), code_commit=COMMIT, policy_bytes=policy)
    commit = COMMIT
    if fault == "commit":
        commit = "b" * 40
    elif fault == "policy":
        policy += b" "
    elif fault == "source":
        with ZipFile(BytesIO(candidate)) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        files["app/__init__.py"] += b"# undeclared change\n"
        candidate = deterministic_zip(files)
    else:
        candidate = source_wheel()
    with pytest.raises(ReleaseContractError, match="PROVENANCE_INVALID"):
        verify_candidate_wheel(candidate, code_commit=commit, policy_bytes=policy)


def test_p9_upgrade_requires_exact_predecessor_tools_and_backup_restore() -> None:
    policy = load_policy(ROOT, kit_version=KIT, policy_path=KIT_POLICY, runtime_version=RUNTIME)
    matrix = policy["compatibility"]
    target = {key: policy["versions"][key] for key in (
        "developer_kit", "runtime", "extension_sdk", "extension_tooling", "enterprise_template"
    )}
    current = {**target, "developer_kit": "1.0.1", "runtime": "0.1.0"}
    with pytest.raises(DeveloperKitContractError, match="KIT_IMPLICIT_UPGRADE_FORBIDDEN"):
        plan_upgrade(matrix, current, target, explicit_opt_in=False)
    for field in ("extension_tooling", "enterprise_template"):
        with pytest.raises(DeveloperKitContractError, match="KIT_UPGRADE_PATH_UNSUPPORTED"):
            plan_upgrade(matrix, {**current, field: "latest"}, target, explicit_opt_in=True)
    plan = plan_upgrade(matrix, current, target, explicit_opt_in=True)
    assert plan["project_mutated"] is False
    assert plan["configuration_migration_required"] is True
    assert plan["rollback"] == "RESTORE_PRE_UPGRADE_DATABASE_AND_RETAINED_PREDECESSOR_COMBINATION"
