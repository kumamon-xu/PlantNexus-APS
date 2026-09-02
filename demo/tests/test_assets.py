from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import shutil

import pytest

from plantnexus_demo.assets import DemoAssetError, load_demo_assets


def _copy_assets(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "data" / "cnc-showcase"
    copied = tmp_path / "cnc-showcase"
    shutil.copytree(source, copied)
    return copied


def _rewrite_asset(copied: Path, name: str, document: dict[str, object]) -> None:
    asset_path = copied / name
    asset_path.write_text(json.dumps(document), encoding="utf-8")
    manifest_path = copied / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["file_sha256"][name] = sha256(asset_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_asset_pack_has_exact_showcase_and_upper_scale() -> None:
    assets = load_demo_assets()
    showcase = assets.profile("showcase")
    upper = assets.profile("upper")

    assert (showcase.order_count, showcase.operation_count, showcase.resource_count) == (
        132,
        610,
        24,
    )
    assert dict(showcase.route_length_counts) == {3: 20, 4: 38, 5: 46, 6: 28}
    assert dict(showcase.candidate_count_targets) == {1: 92, 2: 335, 3: 183}
    assert dict(showcase.priority_class_counts) == {
        "NORMAL": 96,
        "KEY": 29,
        "URGENT": 7,
    }
    assert (upper.order_count, upper.operation_count, upper.resource_count) == (
        150,
        700,
        30,
    )
    assert len(assets.asset_digest) == 64


def test_unknown_manifest_field_fails_closed(tmp_path: Path) -> None:
    copied = _copy_assets(tmp_path)
    manifest_path = copied / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["implicit_default"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DemoAssetError, match="fields differ"):
        load_demo_assets(copied)


def test_invalid_factory_timezone_fails_closed(tmp_path: Path) -> None:
    copied = _copy_assets(tmp_path)
    factory = json.loads((copied / "factory-profile.json").read_text(encoding="utf-8"))
    factory["factory"]["timezone"] = "Mars/Olympus_Mons"
    _rewrite_asset(copied, "factory-profile.json", factory)
    manifest_path = copied / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["factory_timezone"] = "Mars/Olympus_Mons"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DemoAssetError, match="IANA timezone"):
        load_demo_assets(copied)


def test_non_tick_aligned_duration_fails_closed(tmp_path: Path) -> None:
    copied = _copy_assets(tmp_path)
    durations = json.loads(
        (copied / "duration-parameters.json").read_text(encoding="utf-8")
    )
    durations["parameters"]["TURN"]["cycle_seconds_per_unit"] = 301
    _rewrite_asset(copied, "duration-parameters.json", durations)

    with pytest.raises(DemoAssetError, match="tick-aligned"):
        load_demo_assets(copied)
