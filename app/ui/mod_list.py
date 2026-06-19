from __future__ import annotations

from PySide6.QtCore import QTimer, QSize, Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from app.archive_utils import ArchiveReadError, read_archive_file
from app.characters import character_label
from app.models import ScannedMod


class ModList(QWidget):
    selected = Signal(int)
    source_changed = Signal(str)

    SOURCES = (
        ("mods", "Mod Folder"),
        ("natives", "Natives"),
        ("rechunk", "re_chunk / Archive"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        self.mods: list[ScannedMod] = []
        self.title = QLabel("Mod List")
        self.title.setAlignment(Qt.AlignCenter)
        self.source_tabs = QTabBar()
        for source_key, label in self.SOURCES:
            index = self.source_tabs.addTab(label)
            self.source_tabs.setTabData(index, source_key)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("modListWidget")
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.list_widget.setUniformItemSizes(False)
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._placeholder_pixmap = QPixmap(112, 112)
        self._placeholder_pixmap.fill(Qt.transparent)
        self._preview_queue: list[tuple[QListWidgetItem, ScannedMod]] = []
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(0)
        self._preview_timer.timeout.connect(self._load_next_preview)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.search)
        layout.addWidget(self.source_tabs)
        layout.addWidget(self.list_widget)

        self.source_tabs.currentChanged.connect(self._emit_source_changed)
        self.search.textChanged.connect(self._render)
        self.list_widget.itemClicked.connect(self._emit_selected)

    @property
    def current_source_key(self) -> str:
        return str(self.source_tabs.tabData(self.source_tabs.currentIndex()) or "mods")

    def set_current_source(self, source_key: str) -> None:
        for index in range(self.source_tabs.count()):
            if self.source_tabs.tabData(index) == source_key:
                self.source_tabs.setCurrentIndex(index)
                return

    def set_mods(self, mods: list[ScannedMod]) -> None:
        self.mods = mods
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
        self._preview_queue.clear()
        self._preview_timer.stop()
        query = self.search.text().strip().lower()
        for index, mod in enumerate(self.mods):
            haystack = _mod_search_text(mod)
            if query and not _matches_search_query(query, haystack):
                continue
            item = QListWidgetItem()
            item.setSizeHint(QSize(360, 132))
            item.setData(256, index)
            item.setData(257, str(mod.zip_path))
            self.list_widget.addItem(item)
            row = ModRow(mod, self._cached_preview_pixmap(mod))
            self.list_widget.setItemWidget(item, row)
            if mod.preview_image_path_in_zip and not self._has_cached_preview(mod):
                self._preview_queue.append((item, mod))
            if selected_path == str(mod.zip_path):
                item.setSelected(True)
        if self._preview_queue:
            self._preview_timer.start()

    def _emit_selected(self, item: QListWidgetItem) -> None:
        self.selected.emit(item.data(256))

    def _emit_source_changed(self, _index: int) -> None:
        self.source_changed.emit(self.current_source_key)

    def _cached_preview_pixmap(self, mod: ScannedMod) -> QPixmap:
        cache_key = self._preview_cache_key(mod)
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]
        return self._placeholder_pixmap

    def _has_cached_preview(self, mod: ScannedMod) -> bool:
        return self._preview_cache_key(mod) in self._pixmap_cache

    def _preview_cache_key(self, mod: ScannedMod) -> str:
        return f"{mod.source_kind}|{mod.zip_path}|{mod.preview_image_path_in_zip}"

    def _load_next_preview(self) -> None:
        if not self._preview_queue:
            self._preview_timer.stop()
            return
        item, mod = self._preview_queue.pop(0)
        pixmap = self._preview_pixmap(mod)
        row = self.list_widget.itemWidget(item)
        if isinstance(row, ModRow):
            row.set_preview(pixmap)

    def _preview_pixmap(self, mod: ScannedMod) -> QPixmap:
        cache_key = self._preview_cache_key(mod)
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        pixmap = QPixmap(112, 112)
        pixmap.fill(Qt.transparent)
        if mod.preview_image_path_in_zip:
            try:
                if mod.source_kind == "folder":
                    image_bytes = (mod.zip_path / mod.preview_image_path_in_zip).read_bytes()
                else:
                    image_bytes = read_archive_file(
                        mod.zip_path,
                        mod.preview_image_path_in_zip,
                    )
                loaded = QPixmap()
                if loaded.loadFromData(image_bytes):
                    pixmap = loaded.scaled(
                        112,
                        112,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
            except (OSError, KeyError, ArchiveReadError):
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
        self.preview_label = preview_label
        self.preview_label.setObjectName("modRowPreview")
        self.preview_label.setFixedSize(112, 112)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setPixmap(preview)

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
        layout.addWidget(self.preview_label)
        layout.addLayout(details, 1)

    def set_preview(self, preview: QPixmap) -> None:
        self.preview_label.setPixmap(preview)

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


def _mod_search_text(mod: ScannedMod) -> str:
    tokens = [
        mod.mod_name,
        mod.author,
        mod.description,
        mod.zip_path.name,
        *mod.metadata.values(),
    ]
    for source in mod.source_files:
        tokens.extend(
            [
                source.character,
                character_label(source.character),
                source.costume,
                *costume_search_tokens(source.costume),
                source.source_slot,
                *slot_search_tokens(source.type, source.source_slot),
            ]
        )
    return " ".join(str(token) for token in tokens if token).lower()


def costume_search_tokens(costume: str) -> list[str]:
    number = int(costume)
    return [
        f"costume {number}",
        f"costume {number:02d}",
        f"costume {number:03d}",
        f"c{number}",
        f"c{number:02d}",
        f"outfit {number}",
        f"outfit {number:02d}",
        f"outfit {number:03d}",
    ]


def slot_search_tokens(color_type: str, slot: str) -> list[str]:
    number = int(slot)
    if color_type == "normal":
        return [
            f"{number:02d}",
            f"{number:03d}",
            f"slot {number}",
            f"slot {number:02d}",
            f"slot {number:03d}",
            f"normal {number}",
            f"normal {number:02d}",
            f"normal {number:03d}",
        ]
    type_label = color_type.lower()
    return [
        f"{type_label}{number}",
        f"{type_label}{number:02d}",
        f"{type_label}{number:03d}",
        f"{type_label} {number}",
        f"{type_label} {number:02d}",
        f"{type_label} {number:03d}",
        f"slot {type_label}{number}",
        f"slot {type_label}{number:02d}",
        f"slot {type_label}{number:03d}",
    ]


def _compact_search_text(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _matches_search_query(query: str, haystack: str) -> bool:
    compact_haystack = _compact_search_text(haystack)
    compact_tokens = {
        _compact_search_text(token)
        for token in haystack.split()
        if _compact_search_text(token)
    }
    for term in query.split():
        compact_term = _compact_search_text(term)
        if not compact_term:
            continue
        if compact_term.isdigit() or len(compact_term) <= 2:
            if compact_term not in compact_tokens:
                return False
        elif term not in haystack and compact_term not in compact_haystack:
            return False
    return True
