"""Build and seal the Windows x64 standalone Demo package."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
BUILD_ROOT = DEMO_ROOT / "build" / "windows-package"
OUTPUT_ROOT = DEMO_ROOT / "dist"
TEMPLATE_ROOT = DEMO_ROOT / "package" / "windows"
SPEC_PATH = TEMPLATE_ROOT / "PlantNexusCncDemo.spec"
PACKAGE_VERSION = "0.2.0"
PYINSTALLER_VERSION = "6.22.2"
PACKAGE_NAME = f"PlantNexus-CNC-Demo-Windows-x64-{PACKAGE_VERSION}"
MANIFEST_VERSION = "cnc-demo-windows-package-manifest.v1"


class PackageBuildError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, timeout: int = 900) -> None:
    completed = subprocess.run(  # noqa: S603 - fixed local build tools and arguments
        command,
        cwd=REPOSITORY_ROOT,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise PackageBuildError(f"build command failed: {Path(command[0]).name}")


def _safe_clean(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != (DEMO_ROOT / "build").resolve():
        raise PackageBuildError("unsafe build path")
    if resolved.exists():
        shutil.rmtree(resolved)


def _git_head() -> str:
    completed = subprocess.run(  # noqa: S603 - fixed git read
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def _copy_templates(package_root: Path) -> None:
    for source in sorted(TEMPLATE_ROOT.rglob("*")):
        if not source.is_file() or source.suffix == ".spec":
            continue
        relative = source.relative_to(TEMPLATE_ROOT)
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _payload_inventory(package_root: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in sorted(candidate for candidate in package_root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(package_root).as_posix()
        if relative == "package-manifest.json":
            continue
        if relative.startswith("runtime/"):
            raise PackageBuildError("runtime data must not be sealed into the package")
        if path.suffix.lower() == ".map" or "node_modules" in path.parts:
            raise PackageBuildError("development frontend artifact found in package")
        inventory.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return inventory


def _write_manifest(package_root: Path, pyinstaller_version: str) -> dict[str, Any]:
    inventory = _payload_inventory(package_root)
    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "package_name": PACKAGE_NAME,
        "package_version": PACKAGE_VERSION,
        "built_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_head": _git_head(),
        "platform": "Windows-x64",
        "build_environment": {
            "python": platform.python_version(),
            "pyinstaller": pyinstaller_version,
            "machine": platform.machine(),
        },
        "runtime_dependencies": {
            "python_required": False,
            "node_required": False,
            "npm_required": False,
            "uv_required": False,
            "network_required": False,
        },
        "entrypoint": "PlantNexusCncDemo.exe",
        "settings_path": "config/demo-settings.json",
        "frontend_api_topology": "SAME_ORIGIN_SINGLE_PORT",
        "default_access": "LOOPBACK_ONLY",
        "lan_access": "EXPLICIT_PRIVATE_CIDR_ALLOWLIST",
        "simulation_only": True,
        "synthetic_only": True,
        "inventory_scope": "PAYLOAD_EXCLUDING_MANIFEST",
        "file_count": len(inventory),
        "payload_bytes": sum(item["bytes"] for item in inventory),
        "files": inventory,
    }
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    manifest["manifest_fingerprint"] = f"sha256:{sha256(payload).hexdigest()}"
    (package_root / "package-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_zip(package_root: Path) -> tuple[Path, Path]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_ROOT / f"{PACKAGE_NAME}.zip"
    zip_path.unlink(missing_ok=True)
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(candidate for candidate in package_root.rglob("*") if candidate.is_file()):
            archive.write(path, (Path(PACKAGE_NAME) / path.relative_to(package_root)).as_posix())
    digest_path = zip_path.with_suffix(".zip.sha256")
    digest_path.write_text(f"{_sha256(zip_path)}  {zip_path.name}\n", encoding="ascii")
    return zip_path, digest_path


def build(*, skip_frontend: bool) -> dict[str, Any]:
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise PackageBuildError("Windows x64 is required")
    try:
        pyinstaller = importlib.import_module("PyInstaller")
        pyinstaller_main = importlib.import_module("PyInstaller.__main__")
    except ImportError as error:
        raise PackageBuildError(
            f"run with: uv run --with pyinstaller=={PYINSTALLER_VERSION} python {__file__}"
        ) from error
    pyinstaller_version = getattr(pyinstaller, "__version__", None)
    if pyinstaller_version != PYINSTALLER_VERSION:
        raise PackageBuildError("unexpected PyInstaller version")
    if not skip_frontend:
        npm = "npm.cmd"
        _run([npm, "--prefix", str(DEMO_ROOT / "frontend"), "ci"])
        _run([npm, "--prefix", str(DEMO_ROOT / "frontend"), "run", "build"])
    if not (DEMO_ROOT / "frontend" / "dist" / "index.html").is_file():
        raise PackageBuildError("frontend production bundle is missing")

    _safe_clean(BUILD_ROOT)
    work_path = BUILD_ROOT / "work"
    pyinstaller_dist = BUILD_ROOT / "pyinstaller-dist"
    run_pyinstaller = getattr(pyinstaller_main, "run")
    run_pyinstaller(
        [
            "--noconfirm",
            "--clean",
            f"--workpath={work_path}",
            f"--distpath={pyinstaller_dist}",
            str(SPEC_PATH),
        ]
    )
    built_root = pyinstaller_dist / "PlantNexusCncDemo"
    if not (built_root / "PlantNexusCncDemo.exe").is_file():
        raise PackageBuildError("PyInstaller executable is missing")
    package_root = BUILD_ROOT / "package" / PACKAGE_NAME
    package_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(built_root, package_root)
    _copy_templates(package_root)
    manifest = _write_manifest(package_root, pyinstaller_version)
    zip_path, digest_path = _write_zip(package_root)
    result = {
        "status": "PASS",
        "package_version": PACKAGE_VERSION,
        "package_root": str(package_root.resolve()),
        "zip_path": str(zip_path.resolve()),
        "sha256_path": str(digest_path.resolve()),
        "zip_sha256": _sha256(zip_path),
        "file_count": manifest["file_count"],
        "payload_bytes": manifest["payload_bytes"],
        "simulation_only": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="reuse an existing production frontend bundle",
    )
    arguments = parser.parse_args()
    try:
        build(skip_frontend=arguments.skip_frontend)
    except (OSError, subprocess.TimeoutExpired, PackageBuildError) as error:
        print(json.dumps({"status": "FAIL", "code": str(error)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
