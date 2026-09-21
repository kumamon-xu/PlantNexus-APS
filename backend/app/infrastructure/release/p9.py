"""Explicit, reproducible P9 engineering candidate assembly.

The checkout retains its historical default version. The candidate build writes
only the declared Runtime metadata constant, retaining a hash of its source
wheel and regenerating RECORD. This is a recorded build transformation, never
an in-place replacement of a released Runtime or Kit.
"""

from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from typing import Any
from zipfile import BadZipFile, ZipFile

from aps_extension_tooling.packaging import deterministic_zip
from app.infrastructure.release.builder import build_release, build_wheel
from app.infrastructure.release.contracts import (
    ReleaseContractError, canonical_json_bytes, sha256_fingerprint, strict_json_document,
)


RUNTIME = "0.2.0"
KIT = "1.1.0"
RUNTIME_POLICY = Path("infra/release/runtime-release-policy-0.2.0.v1.json")
KIT_POLICY = Path("infra/release/developer-kit-release-policy-1.1.0.v1.json")
BUILD_METADATA = "app/p9-build-provenance.json"


def candidate_wheel(raw: bytes, *, code_commit: str, policy_bytes: bytes) -> bytes:
    """Apply the sole declared generated-source change and rebuild wheel RECORD."""
    if re.fullmatch(r"[0-9a-f]{40}", code_commit) is None:
        raise ReleaseContractError("PROVENANCE_INVALID", "candidate commit must be exact")
    policy = strict_json_document(policy_bytes)
    if policy.get("compatibility", {}).get("runtime_version") != RUNTIME:
        raise ReleaseContractError("VERSION_MISMATCH", "candidate policy version differs")
    with ZipFile(BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or BUILD_METADATA in names:
            raise ReleaseContractError("BUILD_INPUT_INVALID", "wheel was already transformed or duplicated")
        files = {name: archive.read(name) for name in names}
    before = files["app/__init__.py"]
    old = b'RUNTIME_VERSION = "0.1.0"'
    if before.count(old) != 1:
        raise ReleaseContractError("VERSION_MISMATCH", "source Runtime metadata is not the declared baseline")
    after = before.replace(old, f'RUNTIME_VERSION = "{RUNTIME}"'.encode())
    files["app/__init__.py"] = after
    files[BUILD_METADATA] = canonical_json_bytes({
        "build_contract": "p9-runtime-version-materialization.v1",
        "code_commit": code_commit,
        "runtime_version": RUNTIME,
        "source_wheel_sha256": sha256_fingerprint(raw),
        "policy_sha256": sha256_fingerprint(policy_bytes),
        "generated_source": "app/__init__.py",
        "source_sha256": sha256_fingerprint(before),
        "generated_sha256": sha256_fingerprint(after),
        "other_source_changes": [],
    }) + b"\n"
    records = [name for name in files if name.endswith(".dist-info/RECORD")]
    if len(records) != 1:
        raise ReleaseContractError("BUILD_INPUT_INVALID", "wheel RECORD inventory is not exact")
    record = records[0]
    del files[record]
    lines = [
        f"{name},sha256={urlsafe_b64encode(sha256(value).digest()).rstrip(b'=').decode()},{len(value)}"
        for name, value in sorted(files.items())
    ]
    files[record] = ("\n".join([*lines, f"{record},,"]) + "\n").encode()
    return deterministic_zip(files)


def verify_candidate_wheel(raw: bytes, *, code_commit: str, policy_bytes: bytes) -> None:
    """Reject a relabeled source wheel or generated metadata from another build."""
    try:
        with ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or not {BUILD_METADATA, "app/__init__.py"} <= set(names):
                raise ReleaseContractError("PROVENANCE_INVALID", "generated build provenance is absent or duplicated")
            if any(archive.getinfo(name).file_size > 1_048_576 for name in (BUILD_METADATA, "app/__init__.py")):
                raise ReleaseContractError("PROVENANCE_INVALID", "generated metadata exceeds its bound")
            metadata = strict_json_document(archive.read(BUILD_METADATA))
            generated = archive.read("app/__init__.py")
    except (BadZipFile, OSError, RuntimeError) as error:
        raise ReleaseContractError("PROVENANCE_INVALID", "candidate wheel cannot be decoded") from error
    policy = strict_json_document(policy_bytes)
    if (
        metadata.get("code_commit") != code_commit
        or metadata.get("runtime_version") != RUNTIME
        or metadata.get("policy_sha256") != sha256_fingerprint(policy_bytes)
        or metadata.get("generated_sha256") != sha256_fingerprint(generated)
        or generated.count(f'RUNTIME_VERSION = "{RUNTIME}"'.encode()) != 1
        or metadata.get("other_source_changes") != []
        or metadata.get("build_contract") != "p9-runtime-version-materialization.v1"
        or policy.get("compatibility", {}).get("runtime_version") != RUNTIME
    ):
        raise ReleaseContractError("PROVENANCE_INVALID", "generated Runtime identity differs")


def build_candidate(root: Path, output: Path, *, code_commit: str, epoch: int) -> dict[str, Any]:
    """Assemble one candidate from explicit source, policy, and generated version."""
    from aps_developer_kit.builder import build_developer_kit

    wheel = build_wheel(root, output / "wheel", epoch=epoch)
    wheel.write_bytes(candidate_wheel(
        wheel.read_bytes(), code_commit=code_commit,
        policy_bytes=(root / RUNTIME_POLICY).read_bytes(),
    ))
    runtime = build_release(
        root, wheel, output / "runtime", code_commit=code_commit, epoch=epoch,
        policy_path=RUNTIME_POLICY, runtime_version=RUNTIME,
    )
    kit = build_developer_kit(
        root, runtime.archive_path, output / "kit", code_commit=code_commit,
        epoch=epoch, kit_version=KIT, policy_path=KIT_POLICY, runtime_version=RUNTIME,
    )
    return {"runtime": runtime, "kit": kit, "wheel": wheel}
