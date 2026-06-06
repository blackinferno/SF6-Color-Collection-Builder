from __future__ import annotations

from pathlib import Path

from app.models import ScannedMod, SourceColorFile
from app.scan_cache import clear_scan_cache, load_scan_cache, save_scan_cache


def test_scan_cache_round_trips_scanned_mods(tmp_path: Path) -> None:
    cache_path = tmp_path / "scan_cache.json"
    folder = tmp_path / "Mods"
    mod = ScannedMod(
        zip_path=folder / "LooseMod",
        mod_name="Loose Mod",
        source_kind="folder",
        author="Creator",
        description="Description",
        metadata={"version": "1.0"},
        preview_image_path_in_zip="preview.png",
        modinfo_path_in_zip="modinfo.ini",
    )
    mod.source_files.append(
        SourceColorFile(
            zip_path=folder / "LooseMod",
            mod_name="Loose Mod",
            author="Creator",
            preview_image_path_in_zip="preview.png",
            internal_file_path="natives/stm/product/model/esf/esf001/001/esf001_001_cmd_002.user.2",
            character="esf001",
            costume="001",
            type="normal",
            source_slot="002",
            source_kind="folder",
        )
    )

    save_scan_cache("mods", folder, [mod], cache_path)

    cached = load_scan_cache("mods", folder, cache_path)
    assert len(cached) == 1
    assert cached[0].mod_name == "Loose Mod"
    assert cached[0].source_kind == "folder"
    assert cached[0].source_files[0].internal_file_path.endswith("_002.user.2")


def test_scan_cache_ignores_different_folder_and_can_clear(tmp_path: Path) -> None:
    cache_path = tmp_path / "scan_cache.json"
    folder = tmp_path / "Mods"
    save_scan_cache(
        "mods",
        folder,
        [ScannedMod(zip_path=folder / "Cached.zip", mod_name="Cached")],
        cache_path,
    )

    assert load_scan_cache("mods", tmp_path / "Other", cache_path) == []

    clear_scan_cache("mods", cache_path)
    assert load_scan_cache("mods", folder, cache_path) == []
