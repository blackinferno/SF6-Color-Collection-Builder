from __future__ import annotations

from PySide6.QtCore import QByteArray

import app.settings as settings_module
from app.settings import AppSettings


def test_window_geometry_round_trips() -> None:
    settings = AppSettings()
    geometry = QByteArray(b"test-geometry")

    settings.set_window_geometry(geometry)

    assert settings.window_geometry() == geometry


def test_settings_are_written_to_local_ini_file() -> None:
    settings = AppSettings()

    assert settings_module.SETTINGS_PATH.exists()
    settings.set_last_mods_folder("C:/Mods")
    settings._settings.sync()

    assert "last_mods_folder" in settings_module.SETTINGS_PATH.read_text(
        encoding="utf-8"
    )


def test_last_shown_changes_version_round_trips() -> None:
    settings = AppSettings()

    settings.set_last_shown_changes_version("0.1.3")

    assert settings.last_shown_changes_version() == "0.1.3"


def test_scan_source_folders_round_trip() -> None:
    settings = AppSettings()

    settings.set_scan_source_folder("mods", "C:/Mods")
    settings.set_scan_source_folder("natives", "C:/Game/natives")
    settings.set_selected_scan_source("rechunk")

    assert settings.scan_source_folder("mods") == "C:/Mods"
    assert settings.last_mods_folder() == "C:/Mods"
    assert settings.scan_source_folder("natives") == "C:/Game/natives"
    assert settings.selected_scan_source() == "rechunk"
