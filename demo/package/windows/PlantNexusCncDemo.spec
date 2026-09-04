# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir definition; run from the repository root."""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)


repository_root = Path.cwd().resolve()
if not (repository_root / "demo" / "scripts" / "windows_demo_entry.py").is_file():
    raise SystemExit("run the Windows package build from the repository root")


def tree_data(source_relative, destination, *, excluded_suffixes=()):
    source = repository_root / source_relative
    values = []
    for path in sorted(candidate for candidate in source.rglob("*") if candidate.is_file()):
        if path.suffix.lower() in excluded_suffixes:
            continue
        relative_parent = path.relative_to(source).parent
        target = Path(destination) / relative_parent
        values.append((str(path), target.as_posix()))
    return values


datas = [
    (str(repository_root / "alembic.ini"), "repository"),
    (
        str(repository_root / "demo" / "benchmarks" / "profiles.json"),
        "repository/demo/benchmarks",
    ),
    *tree_data("backend/migrations", "repository/backend/migrations"),
    *tree_data("schemas", "repository/schemas"),
    *tree_data("demo/data/cnc-showcase", "repository/demo/data/cnc-showcase"),
    *tree_data(
        "demo/frontend/dist",
        "repository/demo/frontend/dist",
        excluded_suffixes=(".map",),
    ),
    *collect_data_files("tzdata"),
]

hiddenimports = [
    *collect_submodules("sqlalchemy.dialects.sqlite"),
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

a = Analysis(
    [str(repository_root / "demo" / "scripts" / "windows_demo_entry.py")],
    pathex=[
        str(repository_root / "backend"),
        str(repository_root / "demo" / "backend"),
    ],
    binaries=collect_dynamic_libs("ortools"),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PlantNexusCncDemo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PlantNexusCncDemo",
)
