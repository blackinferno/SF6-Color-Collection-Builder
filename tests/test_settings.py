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
