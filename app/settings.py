from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QByteArray, QSettings


APP_NAME = "SF6 Color Collection Builder"
APP_VERSION = "0.1.1"
ORG_NAME = "MarshialLaw"
PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
APP_DATA_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[1]
)
SETTINGS_PATH = APP_DATA_ROOT / "settings.ini"
APP_ICON_PATH = PROJECT_ROOT / "img" / "colormixer.png"
GITHUB_RELEASES_API_URL = (
    "https://api.github.com/repos/blackinferno/SF6-Color-Collection-Builder/releases/latest"
)
GITHUB_RELEASES_PAGE_URL = (
    "https://github.com/blackinferno/SF6-Color-Collection-Builder/releases"
)

REPLACE_OCCUPIED_SLOT_DEFAULT = True
CHECK_UPDATES_DEFAULT = True
USE_CHARACTER_NAMES_DEFAULT = True


class AppSettings:
    def __init__(self) -> None:
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.touch(exist_ok=True)
        except OSError:
            pass
        self._settings = QSettings(str(SETTINGS_PATH), QSettings.IniFormat)

    def last_mods_folder(self) -> str:
        return str(self._settings.value("paths/last_mods_folder", "", str))

    def set_last_mods_folder(self, folder: str | Path) -> None:
        self._settings.setValue("paths/last_mods_folder", str(folder))

    def last_project_folder(self) -> str:
        return str(self._settings.value("paths/last_project_folder", "", str))

    def set_last_project_folder(self, folder: str | Path) -> None:
        self._settings.setValue("paths/last_project_folder", str(folder))

    def window_geometry(self) -> QByteArray:
        value = self._settings.value("window/geometry", QByteArray())
        if isinstance(value, QByteArray):
            return value
        if isinstance(value, bytes):
            return QByteArray(value)
        return QByteArray()

    def set_window_geometry(self, geometry: QByteArray) -> None:
        self._settings.setValue("window/geometry", geometry)

    def replace_occupied_slot(self) -> bool:
        return self._bool_value(
            "behavior/replace_occupied_slot",
            REPLACE_OCCUPIED_SLOT_DEFAULT,
        )

    def check_updates(self) -> bool:
        return self._bool_value("updates/check_on_startup", CHECK_UPDATES_DEFAULT)

    def use_character_names(self) -> bool:
        return self._bool_value(
            "display/use_character_names",
            USE_CHARACTER_NAMES_DEFAULT,
        )

    def _bool_value(self, key: str, default: bool) -> bool:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}
