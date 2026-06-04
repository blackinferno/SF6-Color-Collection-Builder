from __future__ import annotations

import zipfile
from pathlib import Path

from app.scanner import scan_mods_folder, scan_zip


COLOR_ROOT = "natives/stm/product/model/esf"


def _write_zip(path: Path, files: dict[str, str | bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for internal_path, content in files.items():
            archive.writestr(internal_path, content)


def test_scan_zip_detects_modinfo_preview_and_color_files(tmp_path: Path) -> None:
    zip_path = tmp_path / "CoolMod.zip"
    _write_zip(
        zip_path,
        {
            "CoolMod/modinfo.ini": "name=Cool Mod\nauthor=Creator\nimage=preview.png\n",
            "CoolMod/preview.png": b"fake image",
            f"CoolMod/{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"normal",
            f"CoolMod/{COLOR_ROOT}/esf001/001/esf001_001_cmd_dx_003.user.2": b"dx",
            f"CoolMod/{COLOR_ROOT}/esf001/001/esf001_001_cmd_ex_011.user.2": b"invalid slot",
        },
    )

    mod = scan_zip(zip_path)

    assert mod.mod_name == "Cool Mod"
    assert mod.author == "Creator"
    assert mod.metadata["image"] == "preview.png"
    assert mod.preview_image_path_in_zip == "CoolMod/preview.png"
    assert mod.detected_file_count == 2
    assert {source.type for source in mod.source_files} == {"normal", "dx"}


def test_scan_mods_folder_only_scans_top_level_zips(tmp_path: Path) -> None:
    _write_zip(
        tmp_path / "Valid.zip",
        {"modinfo.ini": "name=Valid\n", f"{COLOR_ROOT}/esf002/003/esf002_003_cmd_010.user.2": b"ok"},
    )
    (tmp_path / "NotAZip.txt").write_text("ignored", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    _write_zip(
        nested / "Nested.zip",
        {"modinfo.ini": "name=Nested\n", f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_001.user.2": b"ignored"},
    )

    mods = scan_mods_folder(tmp_path)

    assert len(mods) == 1
    assert mods[0].mod_name == "Valid"
    assert mods[0].source_files[0].source_slot == "010"


def test_scan_mods_folder_excludes_zips_without_supported_color_files(tmp_path: Path) -> None:
    _write_zip(
        tmp_path / "InfoOnly.zip",
        {"modinfo.ini": "name=Info Only\npercent=50% Transparency\n", "preview.png": b"image"},
    )

    assert scan_mods_folder(tmp_path) == []


def test_scan_mods_folder_excludes_loose_matching_filenames(tmp_path: Path) -> None:
    _write_zip(
        tmp_path / "LooseColor.zip",
        {
            "modinfo.ini": "name=Loose Color\n",
            "random/esf001_001_cmd_002.user.2": b"not a structured color mod",
        },
    )

    assert scan_mods_folder(tmp_path) == []


def test_scan_zip_reads_modinfo_percent_values_without_interpolation(tmp_path: Path) -> None:
    zip_path = tmp_path / "PercentMod.zip"
    _write_zip(
        zip_path,
        {
            "modinfo.ini": "name=Percent Mod\ndescription=50% Transparency\n",
            f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    mod = scan_zip(zip_path)

    assert mod.mod_name == "Percent Mod"
    assert mod.description == "50% Transparency"


def test_scan_zip_ignores_malformed_modinfo_lines(tmp_path: Path) -> None:
    zip_path = tmp_path / "MalformedInfo.zip"
    _write_zip(
        zip_path,
        {
            "modinfo.ini": (
                "name=Malformed Info\n"
                "To display this info in Fluffy Mod Manager, please rename this file from .txt to .ini.\n"
            ),
            f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    mod = scan_zip(zip_path)

    assert mod.mod_name == "MalformedInfo"
    assert mod.detected_file_count == 1


def test_scan_mods_folder_splits_submods_with_overlapping_slots(tmp_path: Path) -> None:
    _write_zip(
        tmp_path / "DXEX Colors.zip",
        {
            "DX/modinfo.ini": "name=DX Colors\nauthor=Creator\n",
            f"DX/{COLOR_ROOT}/esf001/001/esf001_001_cmd_dx_001.user.2": b"dx",
            "EX/modinfo.ini": "name=EX Colors\nauthor=Creator\n",
            f"EX/{COLOR_ROOT}/esf001/001/esf001_001_cmd_dx_001.user.2": b"ex package dx slot",
        },
    )

    mods = scan_mods_folder(tmp_path)

    assert [mod.mod_name for mod in mods] == ["DXEX Colors > DX", "DXEX Colors > EX"]
    assert [mod.detected_file_count for mod in mods] == [1, 1]
    assert mods[0].source_for("esf001", "001", "dx", "001").internal_file_path == (
        f"DX/{COLOR_ROOT}/esf001/001/esf001_001_cmd_dx_001.user.2"
    )
    assert mods[1].source_for("esf001", "001", "dx", "001").internal_file_path == (
        f"EX/{COLOR_ROOT}/esf001/001/esf001_001_cmd_dx_001.user.2"
    )
