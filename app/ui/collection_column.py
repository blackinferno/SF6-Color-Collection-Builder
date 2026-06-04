from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.models import CollectionAssignment, VALID_SLOTS
from app.parser import format_slot_label


class CollectionColumn(QWidget):
    target_slot_selected = Signal(str, str)
    assignment_clear_requested = Signal(str, str)
    character_context_changed = Signal(str)
    costume_context_changed = Signal(str)
    show_summary_requested = Signal()

    TYPE_BY_INDEX = {0: "normal", 1: "dx", 2: "ex"}
    INDEX_BY_TYPE = {value: key for key, value in TYPE_BY_INDEX.items()}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        self.title = QLabel("Custom Collection")
        self.title.setAlignment(Qt.AlignCenter)
        self.character_combo = QComboBox()
        self.costume_combo = QComboBox()
        self.character_combo.setMinimumWidth(120)
        self.costume_combo.setMinimumWidth(124)
        self.tabs = QTabWidget()
        self.slot_lists: dict[str, QListWidget] = {}
        self.summary_button = QPushButton("Show Current Collection")

        for label, color_type in (("Normal", "normal"), ("DX", "dx"), ("EX", "ex")):
            slot_list = QListWidget()
            slot_list.itemClicked.connect(self._emit_target_slot_selected)
            self.slot_lists[color_type] = slot_list
            self.tabs.addTab(slot_list, label)

        context_layout = QHBoxLayout()
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(6)
        context_layout.addWidget(QLabel("Character"))
        context_layout.addWidget(self.character_combo, 1)
        context_layout.addWidget(QLabel("Costume"))
        context_layout.addWidget(self.costume_combo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addLayout(context_layout)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.summary_button)

        self.character_combo.currentIndexChanged.connect(self._emit_character_context)
        self.costume_combo.currentIndexChanged.connect(self._emit_costume_context)
        self.summary_button.clicked.connect(self.show_summary_requested)
        self.refresh_all({}, source_type="normal", source_selected=False)

    def set_current_type(self, color_type: str) -> None:
        self.tabs.setCurrentIndex(self.INDEX_BY_TYPE[color_type])

    @property
    def current_type(self) -> str:
        return self.TYPE_BY_INDEX[self.tabs.currentIndex()]

    def refresh_all(
        self,
        assignments: dict[tuple[str, str, str, str], CollectionAssignment],
        source_type: str,
        source_selected: bool,
        character: str | None = None,
        costume: str | None = None,
    ) -> None:
        self.title.setText("Custom Collection")
        for color_type, slot_list in self.slot_lists.items():
            self._refresh_list(
                slot_list,
                assignments=assignments,
                character=character,
                costume=costume,
                color_type=color_type,
                ready=source_selected,
            )

    def set_context_options(
        self,
        character_labels_by_value: dict[str, str],
        costume_labels_by_value: dict[str, str],
        selected_character: str | None,
        selected_costume: str | None,
    ) -> None:
        self._set_combo_options(
            self.character_combo,
            character_labels_by_value,
            selected_character,
        )
        self._set_combo_options(
            self.costume_combo,
            costume_labels_by_value,
            selected_costume,
        )

    def _refresh_list(
        self,
        slot_list: QListWidget,
        assignments: dict[tuple[str, str, str, str], CollectionAssignment],
        character: str | None,
        costume: str | None,
        color_type: str,
        ready: bool,
    ) -> None:
        slot_list.clear()
        for slot in VALID_SLOTS:
            assignment = (
                assignments.get((character, costume, color_type, slot))
                if character and costume
                else None
            )
            suffix = assignment.source_mod_name if assignment else ("ready" if ready else "empty")
            item_text = "" if assignment else f"{format_slot_label(slot)}  {suffix}"
            item = QListWidgetItem(item_text)
            item.setData(256, slot)
            slot_list.addItem(item)
            if assignment:
                row = CollectionSlotRow(
                    format_slot_label(slot),
                    assignment.source_mod_name,
                    assignment.source_slot,
                )
                row.clear_clicked.connect(
                    lambda checked=False, current_type=color_type, current_slot=slot: (
                        self.assignment_clear_requested.emit(current_type, current_slot)
                    )
                )
                size_hint = row.sizeHint()
                size_hint.setHeight(31)
                item.setSizeHint(size_hint)
                slot_list.setItemWidget(item, row)

    def _emit_target_slot_selected(self, item: QListWidgetItem) -> None:
        slot = item.data(256)
        self.target_slot_selected.emit(self.current_type, slot)

    def _emit_character_context(self) -> None:
        value = self.character_combo.currentData()
        if value:
            self.character_context_changed.emit(value)

    def _emit_costume_context(self) -> None:
        value = self.costume_combo.currentData()
        if value:
            self.costume_context_changed.emit(value)

    def _set_combo_options(
        self,
        combo: QComboBox,
        labels_by_value: dict[str, str],
        selected_value: str | None,
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        for value, label in labels_by_value.items():
            combo.addItem(label, value)
        if selected_value:
            index = combo.findData(selected_value)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)


class CollectionSlotRow(QWidget):
    clear_clicked = Signal()

    def __init__(
        self,
        slot_label: str,
        mod_name: str,
        source_slot: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("collectionSlotRow")
        self.setAttribute(Qt.WA_TranslucentBackground)
        label = QLabel(f"{slot_label}  {mod_name} (Slot {int(source_slot)})")
        label.setObjectName("collectionSlotLabel")
        label.setAttribute(Qt.WA_TranslucentBackground)
        clear_button = QPushButton("Clear")
        clear_button.setObjectName("clearSlotButton")
        clear_button.setFixedSize(52, 22)
        clear_button.clicked.connect(self.clear_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(6)
        layout.addWidget(label, 1)
        layout.addWidget(clear_button)
