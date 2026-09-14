"""Prepare immutable public engineering assets; publication is a separate action."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, cast

from aps_developer_kit.builder import build_developer_kit
from aps_developer_kit.check import _clean_install_and_cli, _security
from aps_developer_kit.contracts import (
    DeveloperKitContractError,
    plan_upgrade,
    verify_kit_archive,
)
from aps_extension_tooling.packaging import deterministic_zip
from app.infrastructure.release.contracts import verify_release_archive
from infra.enterprise.bundle.verify import verify as verify_offline


KIT_VERSION = "1.0.1"
POLICY = Path("infra/release/developer-kit-release-policy-1.0.1.v1.json")
OLD_KIT_SHA = "483550d240522af41175e29e4cd5847f32423643fc1763175ccbb77d52f732cb"
OFFLINE_SHA = "b9cc5305c7fe8a53eef071f7a9b3665ee823934b6c3a87e4ffbc3a9a41b28273"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return __import__("hashlib").file_digest(stream, "sha256").hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, encoding="utf-8"
    ).strip()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def public_files(root: Path) -> dict[str, bytes]:
    """Only tracked public docs, canonical carriers and the public SDK surface."""
    result = {}
    for name in git(root, "ls-files", "-z").split("\0"):
        if name == "README.md" or (
            name.startswith("docs/") and name.endswith(".md")
        ) or name.startswith("schemas/") or (
            name.startswith("backend/aps_extension_sdk/") and name.endswith((".py", ".json"))
        ):
            path = root / name
            if path.is_symlink():
                raise ValueError("public file must not be a symlink")
            result[name] = path.read_bytes().replace(b"\r\n", b"\n")
    if not result or "README.md" not in result:
        raise ValueError("public documentation inventory is empty")
    return result


def prepare(root: Path, runtime: Path, old_kit: Path, offline: Path, output: Path) -> dict:
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("release preparation requires clean tracked input")
    commit = git(root, "rev-parse", "HEAD")
    epoch = int(git(root, "show", "-s", "--format=%ct", "HEAD"))
    policy = json.loads((root / POLICY).read_bytes())
    runtime_pin = policy["runtime_input"]
    verified_runtime = verify_release_archive(
        runtime, expected_code_commit=runtime_pin["code_commit"], expected_runtime_version="0.1.0"
    )
    if "sha256:" + digest(runtime) != runtime_pin["archive_sha256"]:
        raise ValueError("Runtime archive differs from exact release input")
    if git(
        root, "diff", "--name-only", runtime_pin["code_commit"], commit, "--",
        "backend/app", "backend/aps_extension_sdk", "backend/aps_extension_tooling",
        "templates", "examples", "uv.lock",
    ):
        raise ValueError("Runtime source, SDK or conformance input changed since frozen Runtime")
    if digest(old_kit) != OLD_KIT_SHA:
        raise ValueError("predecessor Kit bytes differ")
    predecessor = verify_kit_archive(old_kit, expected_kit_version="1.0.0")
    verify_offline(offline, OFFLINE_SHA)
    output.mkdir(parents=True, exist_ok=True)
    assets = output / "assets"
    if assets.exists():
        raise ValueError("asset destination already exists; retain immutable previous attempt")
    assets.mkdir()
    options = {
        "code_commit": commit, "epoch": epoch, "kit_version": KIT_VERSION,
        "policy_path": POLICY, "runtime_code_commit": runtime_pin["code_commit"],
    }
    with TemporaryDirectory(prefix="aps-public-kit-repeat-") as temporary:
        first = build_developer_kit(root, runtime, Path(temporary), **options)
        second = build_developer_kit(root, runtime, output / "developer-kit", **options)
        if first.archive_path.read_bytes() != second.archive_path.read_bytes():
            raise ValueError("Kit build is not reproducible")
    kit = verify_kit_archive(second.archive_path, channel="public-engineering")
    if kit.files[cast(Any, kit.lock["artifacts"])["runtime"]["path"]] != runtime.read_bytes():
        raise ValueError("nested and standalone Runtime differ")
    print("Kit reproducibility and nested Runtime: PASS", flush=True)
    installed, elapsed = _clean_install_and_cli(second.archive_path)
    print("New Kit clean install and two Extension CLI: PASS", flush=True)
    security = _security(root, kit)
    write_json(output / "kit-security.json", security)
    if security["status"] != "PASS":
        raise ValueError("Kit supply-chain checks failed")
    target = {key: cast(Any, kit.lock["versions"])[key] for key in (
        "developer_kit", "runtime", "extension_sdk", "extension_tooling", "enterprise_template"
    )}
    current = {key: cast(Any, predecessor.lock["versions"])[key] for key in target}
    try:
        plan_upgrade(kit.compatibility, current, target, explicit_opt_in=False)
    except DeveloperKitContractError as error:
        if error.code != "KIT_IMPLICIT_UPGRADE_FORBIDDEN":
            raise
    else:
        raise ValueError("implicit upgrade was accepted")
    upgrade = plan_upgrade(kit.compatibility, current, target, explicit_opt_in=True)
    # Restore the retained old artifact into a separate clean installation. Its
    # packaged project locks and old Runtime, rather than today's source, run here.
    restored, rollback_elapsed = _clean_install_and_cli(old_kit)
    if digest(old_kit) != OLD_KIT_SHA:
        raise ValueError("predecessor changed during replay")
    print("Retained predecessor clean install/rollback replay: PASS", flush=True)
    registry = json.loads(second.registry_path.read_bytes())
    old_name = old_kit.name
    old_destination = second.registry_path.parent / "versions/1.0.0/sha256" / OLD_KIT_SHA / old_name
    old_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(old_kit, old_destination)
    registry["entries"].insert(0, {
        "kit_version": "1.0.0", "archive_sha256": "sha256:" + OLD_KIT_SHA,
        "release_fingerprint": predecessor.release_fingerprint,
        "relative_path": old_destination.relative_to(second.registry_path.parent).as_posix(),
        "code_commit": predecessor.code_commit, "channel": "UNSIGNED_ENGINEERING_CANDIDATE",
    })
    write_json(second.registry_path, registry)
    files = public_files(root)
    files["PUBLIC-PACKAGE.json"] = (json.dumps({
        "source_commit": commit, "channel": "UNSIGNED_PUBLIC_ENGINEERING",
        "files": {name: sha256(raw).hexdigest() for name, raw in sorted(files.items())},
    }, indent=2) + "\n").encode()
    docs_archive = assets / "plantnexus-aps-public-interfaces-and-docs-v0.1.0.zip"
    docs_archive.write_bytes(deterministic_zip({
        "plantnexus-aps-public-interfaces-and-docs/" + name: raw for name, raw in files.items()
    }))
    for path in (offline, runtime, second.archive_path):
        shutil.copyfile(path, assets / path.name)
    report = {
        "status": "PASS", "source_commit": commit, "kit_version": KIT_VERSION,
        "kit_fingerprint": kit.release_fingerprint,
        "runtime_fingerprint": verified_runtime.release_fingerprint,
        "runtime_source_commit": verified_runtime.code_commit,
        "checks": {
            "reproducible": True, "nested_runtime_exact": True,
            "new_clean_install_and_two_extensions": installed,
            "predecessor_clean_install_and_rollback": restored,
            "old_kit_bytes_retained": True, "implicit_upgrade_rejected": True,
            "supply_chain": security["status"] == "PASS", "offline_integrity": True,
        },
        "explicit_upgrade": upgrade,
        "observations_ms": {"new_install": elapsed, "rollback_install": rollback_elapsed},
        "issues": [],
    }
    write_json(output / "validation.json", report)
    manifest = {
        "manifest_version": "plantnexus-github-release.v1", "tag": "v0.1.0",
        "source_commit": commit, "channel": "UNSIGNED_PUBLIC_ENGINEERING",
        "signature_present": False, "production_authorized": False,
        "versions": kit.lock["versions"],
        "runtime_input": runtime_pin, "kit_fingerprint": kit.release_fingerprint,
        "offline_compatibility_kit": "1.0.0",
        "offline_source_commit": "e2a50e631b2a52a6cff5b5260cf0284f2a743887",
        "assets": [{"name": p.name, "bytes": p.stat().st_size, "sha256": digest(p)}
                   for p in sorted(assets.iterdir())],
    }
    write_json(assets / "RELEASE-MANIFEST.json", manifest)
    (assets / "SHA256SUMS.txt").write_text("".join(
        f"{digest(p)}  {p.name}\n" for p in sorted(assets.iterdir()) if p.is_file()
    ), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "runtime", "old-kit", "offline", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(
        args.root.resolve(), args.runtime.resolve(), args.old_kit.resolve(),
        args.offline.resolve(), args.output.resolve(),
    ), ensure_ascii=False))


if __name__ == "__main__":
    main()
