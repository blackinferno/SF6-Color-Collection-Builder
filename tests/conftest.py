from __future__ import annotations

import os
import sys

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.settings import APP_NAME, ORG_NAME


@pytest.fixture
def qt_app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    return app


@pytest.fixture(autouse=True)
def disable_startup_update_check() -> None:
    settings = QSettings(ORG_NAME, APP_NAME)
    original = settings.value("updates/check_on_startup", None)
    settings.setValue("updates/check_on_startup", False)
    yield
    if original is None:
        settings.remove("updates/check_on_startup")
    else:
        settings.setValue("updates/check_on_startup", original)
