from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import py7zr

from app.scanner import (
    scan_mods_folder,
    scan_mods_folder_with_report,
    scan_rechunk_source_with_report,
    scan_zip,
    write_scan_log,
)


COLOR_ROOT = "natives/stm/product/model/esf"


def _write_zip(path: Path, files: dict[str, str | bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for internal_path, content in files.items():
            archive.writestr(internal_path, content)


def _write_7z(path: Path, files: dict[str, str | bytes]) -> None:
    source_root = path.parent / f"{path.stem}_source"
    if source_root.exists():
        shutil.rmtree(source_root)
    _write_folder(source_root, files)
    with py7zr.SevenZipFile(path, "w") as archive:
        for file_path in source_root.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(source_root).as_posix())
    shutil.rmtree(source_root)


def _write_folder(root: Path, files: dict[str, str | bytes]) -> None:
    for internal_path, content in files.items():
        output_path = root / internal_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            output_path.write_bytes(content)
        else:
            output_path.write_text(content, encoding="utf-8")


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


def test_scan_mods_folder_accepts_direct_zip_path(tmp_path: Path) -> None:
    zip_path = tmp_path / "BaseCmds.zip"
    _write_zip(
        zip_path,
        {
            "modinfo.ini": "name=Base CMDs\n",
            f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    mods = scan_mods_folder(zip_path)

    assert len(mods) == 1
    assert mods[0].mod_name == "Base CMDs"
    assert mods[0].source_kind == "zip"
    assert mods[0].source_files[0].internal_file_path == (
        f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2"
    )


def test_scan_mods_folder_accepts_7z_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "SevenZipMod.7z"
    _write_7z(
        archive_path,
        {
            "modinfo.ini": "name=Seven Zip Mod\n",
            f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    mods = scan_mods_folder(archive_path)

    assert len(mods) == 1
    assert mods[0].mod_name == "Seven Zip Mod"
    assert mods[0].source_kind == "7z"


def test_scan_mods_folder_scans_top_level_loose_folders(tmp_path: Path) -> None:
    loose = tmp_path / "LooseMod"
    _write_folder(
        loose,
        {
            "modinfo.ini": "name=Loose Mod\nauthor=Folder Creator\nimage=preview.png\n",
            "preview.png": b"fake image",
            f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    mods = scan_mods_folder(tmp_path)

    assert len(mods) == 1
    assert mods[0].mod_name == "Loose Mod"
    assert mods[0].source_kind == "folder"
    assert mods[0].preview_image_path_in_zip == "preview.png"
    assert mods[0].source_files[0].source_kind == "folder"
    assert mods[0].source_files[0].internal_file_path == (
        f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2"
    )


def test_scan_mods_folder_scans_selected_street_fighter_install_folder(
    tmp_path: Path,
) -> None:
    install_folder = tmp_path / "Street Fighter 6"
    _write_folder(
        install_folder,
        {
            f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"game color",
        },
    )

    mods = scan_mods_folder(install_folder)

    assert len(mods) == 1
    assert mods[0].mod_name == "Street Fighter 6"
    assert mods[0].source_kind == "folder"
    assert mods[0].source_files[0].internal_file_path == (
        f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2"
    )


def test_scan_mods_folder_scans_selected_natives_folder_from_stm(
    tmp_path: Path,
) -> None:
    natives_folder = tmp_path / "natives"
    _write_folder(
        natives_folder,
        {
            "stm/product/model/esf/esf001/001/esf001_001_cmd_002.user.2": b"game color",
        },
    )

    mods = scan_mods_folder(natives_folder)

    assert len(mods) == 1
    assert mods[0].mod_name == "natives"
    assert mods[0].source_files[0].internal_file_path == (
        "stm/product/model/esf/esf001/001/esf001_001_cmd_002.user.2"
    )


def test_scan_mods_folder_scans_top_level_7z_archives(tmp_path: Path) -> None:
    _write_7z(
        tmp_path / "Packed.7z",
        {
            "modinfo.ini": "name=Packed Mod\n",
            f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    mods = scan_mods_folder(tmp_path)

    assert len(mods) == 1
    assert mods[0].mod_name == "Packed Mod"
    assert mods[0].source_kind == "7z"


def test_scan_rechunk_folder_only_checks_direct_cmd_costume_folders(
    tmp_path: Path,
) -> None:
    _write_folder(
        tmp_path,
        {
            f"re_chunk_000/{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
            f"re_chunk_000/{COLOR_ROOT}/esf001/001/deeper/esf001_001_cmd_003.user.2": b"ignored",
            "somewhere_else/esf001_001_cmd_004.user.2": b"ignored",
        },
    )

    report = scan_rechunk_source_with_report(tmp_path)

    assert len(report.mods) == 1
    assert report.mods[0].mod_name == tmp_path.stem
    assert [source.source_slot for source in report.mods[0].source_files] == ["002"]
    assert report.mods[0].source_files[0].source_kind == "folder"


def test_scan_rechunk_zip_only_accepts_expected_cmd_path(tmp_path: Path) -> None:
    zip_path = tmp_path / "BaseCmds.zip"
    _write_zip(
        zip_path,
        {
            f"re_chunk_000/{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
            f"re_chunk_000/{COLOR_ROOT}/esf001/001/deeper/esf001_001_cmd_003.user.2": b"ignored",
            "unrelated/esf001_001_cmd_004.user.2": b"ignored",
        },
    )

    report = scan_rechunk_source_with_report(zip_path)

    assert len(report.mods) == 1
    assert report.mods[0].mod_name == "BaseCmds"
    assert [source.source_slot for source in report.mods[0].source_files] == ["002"]
    assert report.mods[0].source_files[0].source_kind == "zip"


def test_scan_rechunk_zip_reads_modinfo_and_preview(tmp_path: Path) -> None:
    zip_path = tmp_path / "BaseCmds.zip"
    _write_zip(
        zip_path,
        {
            "modinfo.ini": "name=Source CMD Pack\nauthor=Creator\ndescription=Base files\nimage=preview.png\n",
            "preview.png": b"fake image",
            f"re_chunk_000/{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    report = scan_rechunk_source_with_report(zip_path)

    assert len(report.mods) == 1
    assert report.mods[0].mod_name == "Source CMD Pack"
    assert report.mods[0].author == "Creator"
    assert report.mods[0].description == "Base files"
    assert report.mods[0].preview_image_path_in_zip == "preview.png"
    assert report.mods[0].source_files[0].preview_image_path_in_zip == "preview.png"


def test_scan_rechunk_7z_reads_modinfo_and_preview(tmp_path: Path) -> None:
    archive_path = tmp_path / "BaseCmds.7z"
    _write_7z(
        archive_path,
        {
            "modinfo.ini": "name=7z CMD Pack\nauthor=Creator\nimage=preview.png\n",
            "preview.png": b"fake image",
            f"re_chunk_000/{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    report = scan_rechunk_source_with_report(archive_path)

    assert len(report.mods) == 1
    assert report.mods[0].mod_name == "7z CMD Pack"
    assert report.mods[0].source_kind == "7z"
    assert report.mods[0].preview_image_path_in_zip == "preview.png"


def test_scan_rechunk_folder_reads_modinfo_and_preview(tmp_path: Path) -> None:
    _write_folder(
        tmp_path,
        {
            "modinfo.ini": "name=Loose CMD Source\nauthor=Creator\nimage=preview.png\n",
            "preview.png": b"fake image",
            f"re_chunk_000/{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    report = scan_rechunk_source_with_report(tmp_path)

    assert len(report.mods) == 1
    assert report.mods[0].mod_name == "Loose CMD Source"
    assert report.mods[0].author == "Creator"
    assert report.mods[0].preview_image_path_in_zip == "preview.png"


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


def test_scan_report_logs_loose_matching_filenames_outside_structure(tmp_path: Path) -> None:
    _write_folder(
        tmp_path / "LooseFolder",
        {
            "modinfo.ini": "name=Loose Folder\n",
            "random/esf001_001_cmd_002.user.2": b"not structured",
        },
    )

    report = scan_mods_folder_with_report(tmp_path)

    assert report.mods == []
    assert len(report.issues) == 1
    assert report.issues[0].package_path.name == "LooseFolder"
    assert report.issues[0].internal_path == "random/esf001_001_cmd_002.user.2"


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


def test_scan_report_records_malformed_modinfo(tmp_path: Path) -> None:
    _write_zip(
        tmp_path / "MalformedInfo.zip",
        {
            "modinfo.ini": "name=Bad\nThis line has no equals sign\n",
            f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2": b"ok",
        },
    )

    report = scan_mods_folder_with_report(tmp_path)

    assert len(report.mods) == 1
    assert len(report.issues) == 1
    assert report.issues[0].display_path == "MalformedInfo.zip / modinfo.ini"


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


def test_scan_mods_folder_splits_loose_folder_submods(tmp_path: Path) -> None:
    loose = tmp_path / "DXEX Colors"
    _write_folder(
        loose,
        {
            "DX/modinfo.ini": "name=DX Colors\nauthor=Creator\n",
            f"DX/{COLOR_ROOT}/esf001/001/esf001_001_cmd_dx_001.user.2": b"dx",
            "EX/modinfo.ini": "name=EX Colors\nauthor=Creator\n",
            f"EX/{COLOR_ROOT}/esf001/001/esf001_001_cmd_dx_001.user.2": b"ex package dx slot",
        },
    )

    mods = scan_mods_folder(tmp_path)

    assert [mod.mod_name for mod in mods] == ["DXEX Colors > DX", "DXEX Colors > EX"]
    assert [mod.source_kind for mod in mods] == ["folder", "folder"]


def test_scan_log_contains_issue_paths(tmp_path: Path) -> None:
    _write_folder(
        tmp_path / "LooseFolder",
        {"random/esf001_001_cmd_002.user.2": b"not structured"},
    )
    report = scan_mods_folder_with_report(tmp_path)
    log_path = tmp_path / "scan.log"

    write_scan_log(tmp_path, report, log_path)

    log_text = log_path.read_text(encoding="utf-8")
    assert "LooseFolder / random/esf001_001_cmd_002.user.2" in log_text
    assert "Issues: 1" in log_text
