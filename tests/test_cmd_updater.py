from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.archive_utils import (
    ArchiveWriteError,
    can_write_rar,
    read_archive_file,
    write_archive_files,
)
from app.cmd_updater import NEW_CMD_BYTES, OLD_CMD_BYTES, update_cmds_in_source


COLOR_ROOT = "natives/stm/product/model/esf"


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for internal_path, content in files.items():
            archive.writestr(internal_path, content)


def _write_archive_or_skip(path: Path, files: dict[str, bytes]) -> None:
    try:
        write_archive_files(path, files)
    except ArchiveWriteError as error:
        pytest.skip(str(error))


def test_update_cmds_in_selected_folder_patches_loose_cmd_files_recursively(
    tmp_path: Path,
) -> None:
    color_file = (
        tmp_path
        / "Loose Mod"
        / "esf001"
        / "001"
        / "esf001_001_cmd_002.user.2"
    )
    color_file.parent.mkdir(parents=True)
    color_file.write_bytes(b"before" + OLD_CMD_BYTES + b"after")

    report = update_cmds_in_source(tmp_path)

    assert report.packages_checked == 1
    assert report.color_files_checked == 1
    assert report.files_updated == 1
    assert color_file.read_bytes() == b"before" + NEW_CMD_BYTES + b"after"


def test_update_cmds_in_zip_patches_supported_color_files(tmp_path: Path) -> None:
    zip_path = tmp_path / "Color Mod.zip"
    color_path = f"{COLOR_ROOT}/esf002/001/esf002_001_cmd_dx_003.user.2"
    _write_zip(
        zip_path,
        {
            "modinfo.ini": b"name=Color Mod\n",
            "preview.png": b"image",
            color_path: OLD_CMD_BYTES + b"cmd",
        },
    )

    report = update_cmds_in_source(tmp_path)

    assert report.packages_checked == 1
    assert report.color_files_checked == 1
    assert report.files_updated == 1
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.read(color_path) == NEW_CMD_BYTES + b"cmd"
        assert archive.read("modinfo.ini") == b"name=Color Mod\n"
        assert archive.read("preview.png") == b"image"


def test_update_cmds_finds_archives_in_subfolders(tmp_path: Path) -> None:
    zip_path = tmp_path / "Nested" / "Color Mod.zip"
    zip_path.parent.mkdir()
    color_path = f"{COLOR_ROOT}/esf002/001/esf002_001_cmd_003.user.2"
    _write_zip(zip_path, {color_path: OLD_CMD_BYTES + b"cmd"})

    report = update_cmds_in_source(tmp_path)

    assert report.packages_checked == 1
    assert report.color_files_checked == 1
    assert report.files_updated == 1
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.read(color_path) == NEW_CMD_BYTES + b"cmd"


def test_update_cmds_in_7z_patches_supported_color_files(tmp_path: Path) -> None:
    archive_path = tmp_path / "Color Mod.7z"
    color_path = f"{COLOR_ROOT}/esf003/001/esf003_001_cmd_ex_004.user.2"
    _write_archive_or_skip(archive_path, {color_path: OLD_CMD_BYTES + b"cmd"})

    report = update_cmds_in_source(tmp_path)

    assert report.packages_checked == 1
    assert report.color_files_checked == 1
    assert report.files_updated == 1
    assert read_archive_file(archive_path, color_path) == NEW_CMD_BYTES + b"cmd"


def test_update_cmds_in_rar_patches_supported_color_files_when_rar_is_available(
    tmp_path: Path,
) -> None:
    if not can_write_rar():
        pytest.skip("RAR command-line tools are not available.")
    archive_path = tmp_path / "Color Mod.rar"
    color_path = f"{COLOR_ROOT}/esf004/001/esf004_001_cmd_005.user.2"
    _write_archive_or_skip(archive_path, {color_path: OLD_CMD_BYTES + b"cmd"})

    report = update_cmds_in_source(tmp_path)

    assert report.packages_checked == 1
    assert report.color_files_checked == 1
    assert report.files_updated == 1
    assert read_archive_file(archive_path, color_path) == NEW_CMD_BYTES + b"cmd"


def test_update_cmds_reports_rar_writer_requirement_without_reading_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "Needs Writer.rar"
    archive_path.write_bytes(b"not actually a rar")
    monkeypatch.setattr("app.cmd_updater.can_write_rar", lambda: False)

    report = update_cmds_in_source(tmp_path)

    assert report.packages_checked == 1
    assert report.color_files_checked == 0
    assert report.files_updated == 0
    assert len(report.issues) == 1
    assert "WinRAR/RAR" in report.issues[0].message
