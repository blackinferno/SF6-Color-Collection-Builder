from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import app.settings as settings_module


@pytest.fixture
def qt_app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    return app


@pytest.fixture(autouse=True)
def isolated_settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", tmp_path / "settings.ini")
    settings = settings_module.AppSettings()
    settings._settings.setValue("updates/check_on_startup", False)
    settings.set_last_shown_changes_version(settings_module.APP_VERSION)
    yield
