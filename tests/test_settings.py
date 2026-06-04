from __future__ import annotations

from PySide6.QtCore import QByteArray

from app.settings import AppSettings


def test_window_geometry_round_trips() -> None:
    settings = AppSettings()
    original = settings.window_geometry()
    geometry = QByteArray(b"test-geometry")

    try:
        settings.set_window_geometry(geometry)
        assert settings.window_geometry() == geometry
    finally:
        settings.set_window_geometry(original)
