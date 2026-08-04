from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QByteArray, QSettings


APP_NAME = "SF6 Color Collection Builder"
APP_VERSION = "0.2.6"
ORG_NAME = "MarshialLaw"
PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
APP_DATA_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[1]
)
SETTINGS_PATH = APP_DATA_ROOT / "settings.ini"
SCAN_LOG_PATH = APP_DATA_ROOT / "scan.log"
CMD_UPDATE_LOG_PATH = APP_DATA_ROOT / "cmd_update.log"
SCAN_CACHE_PATH = APP_DATA_ROOT / "scan_cache.json"
UPDATE_LOG_PATH = APP_DATA_ROOT / "update_log.txt"
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

    def scan_source_folder(self, source_key: str) -> str:
        if source_key == "mods":
            return self.last_mods_folder()
        return str(self._settings.value(f"paths/{source_key}_folder", "", str))

    def set_scan_source_folder(self, source_key: str, folder: str | Path) -> None:
        if source_key == "mods":
            self.set_last_mods_folder(folder)
            return
        self._settings.setValue(f"paths/{source_key}_folder", str(folder))

    def selected_scan_source(self) -> str:
        return str(self._settings.value("scan/selected_source", "mods", str))

    def set_selected_scan_source(self, source_key: str) -> None:
        self._settings.setValue("scan/selected_source", source_key)

    def last_project_folder(self) -> str:
        return str(self._settings.value("paths/last_project_folder", "", str))

    def set_last_project_folder(self, folder: str | Path) -> None:
        self._settings.setValue("paths/last_project_folder", str(folder))

    def rar_tool_path(self) -> str:
        return str(self._settings.value("paths/rar_tool_path", "", str))

    def set_rar_tool_path(self, path: str | Path) -> None:
        self._settings.setValue("paths/rar_tool_path", str(path))

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

    def last_shown_changes_version(self) -> str:
        return str(self._settings.value("updates/last_shown_changes_version", "", str))

    def set_last_shown_changes_version(self, version: str) -> None:
        self._settings.setValue("updates/last_shown_changes_version", version)

    def _bool_value(self, key: str, default: bool) -> bool:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}
