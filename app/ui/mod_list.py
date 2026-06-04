from __future__ import annotations

import zipfile

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models import ScannedMod


class ModList(QWidget):
    selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        self.mods: list[ScannedMod] = []
        self.title = QLabel("Mod List")
        self.title.setAlignment(Qt.AlignCenter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter mods")
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("modListWidget")
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.list_widget.setUniformItemSizes(False)
        self._pixmap_cache: dict[str, QPixmap] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.search)
        layout.addWidget(self.list_widget)

        self.search.textChanged.connect(self._render)
        self.list_widget.itemClicked.connect(self._emit_selected)

    def set_mods(self, mods: list[ScannedMod]) -> None:
        self.mods = mods
        self._pixmap_cache.clear()
        self._render()

    def show_preview(self, mod: ScannedMod | None) -> None:
        # Kept for MainWindow compatibility; previews are now shown per mod row.
        return

    def _render(self) -> None:
        selected_path = None
        current = self.list_widget.currentItem()
        if current:
            selected_path = current.data(257)

        self.list_widget.clear()
        query = self.search.text().strip().lower()
        for index, mod in enumerate(self.mods):
            haystack = f"{mod.mod_name} {mod.author} {mod.zip_path.name}".lower()
            if query and query not in haystack:
                continue
            item = QListWidgetItem()
            item.setSizeHint(QSize(360, 132))
            item.setData(256, index)
            item.setData(257, str(mod.zip_path))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, ModRow(mod, self._preview_pixmap(mod)))
            if selected_path == str(mod.zip_path):
                item.setSelected(True)

    def _emit_selected(self, item: QListWidgetItem) -> None:
        self.selected.emit(item.data(256))

    def _preview_pixmap(self, mod: ScannedMod) -> QPixmap:
        cache_key = f"{mod.zip_path}|{mod.preview_image_path_in_zip}"
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        pixmap = QPixmap(112, 112)
        pixmap.fill(Qt.transparent)
        if mod.preview_image_path_in_zip:
            try:
                if mod.source_kind == "folder":
                    image_bytes = (mod.zip_path / mod.preview_image_path_in_zip).read_bytes()
                else:
                    with zipfile.ZipFile(mod.zip_path) as archive:
                        image_bytes = archive.read(mod.preview_image_path_in_zip)
                loaded = QPixmap()
                if loaded.loadFromData(image_bytes):
                    pixmap = loaded.scaled(
                        112,
                        112,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
            except (OSError, KeyError, zipfile.BadZipFile):
                pass

        self._pixmap_cache[cache_key] = pixmap
        return pixmap


class ModRow(QWidget):
    EXTRA_KEYS = ("version", "url")

    def __init__(self, mod: ScannedMod, preview: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("modRow")
        self.setAttribute(Qt.WA_TranslucentBackground)

        preview_label = QLabel()
        preview_label.setObjectName("modRowPreview")
        preview_label.setFixedSize(112, 112)
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setPixmap(preview)

        details = QGridLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setHorizontalSpacing(6)
        details.setVerticalSpacing(2)
        details.setColumnStretch(1, 1)

        rows = self._metadata_rows(mod)
        for row, (label, value) in enumerate(rows):
            name_label = QLabel(label)
            name_label.setObjectName("modRowField")
            name_label.setAttribute(Qt.WA_TranslucentBackground)
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            value_label.setObjectName("modRowValue")
            value_label.setAttribute(Qt.WA_TranslucentBackground)
            details.addWidget(name_label, row, 0, alignment=Qt.AlignTop)
            details.addWidget(value_label, row, 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        layout.addWidget(preview_label)
        layout.addLayout(details, 1)

    def _metadata_rows(self, mod: ScannedMod) -> list[tuple[str, str]]:
        rows = [
            ("Name", mod.mod_name),
            ("Author", mod.author or "Unknown"),
            ("Description", mod.description or "No description"),
            ("Files", f"{mod.detected_file_count} color files"),
        ]
        for key in self.EXTRA_KEYS:
            value = mod.metadata.get(key)
            if value:
                rows.append((key.title(), value))
        return rows
