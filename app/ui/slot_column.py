from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models import VALID_SLOTS
from app.parser import format_slot_label


class SlotColumn(QWidget):
    type_changed = Signal(str)
    slot_selected = Signal(str)

    COLUMNS = (("normal", ""), ("dx", "DX"), ("ex", "EX"))
    AVAILABLE_COLOR = QColor("#1f3347")
    SELECTED_COLOR = QColor("#7a3a0a")
    DISABLED_COLOR = QColor("#69707a")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        self.title = QLabel("Slot")
        self.title.setAlignment(Qt.AlignCenter)
        self._current_type = "normal"
        self._available_slots: dict[str, set[str]] = {
            "normal": set(),
            "dx": set(),
            "ex": set(),
        }
        self._selected_slots: dict[str, str | None] = {
            "normal": None,
            "dx": None,
            "ex": None,
        }

        self.table_widget = QTableWidget()
        self.table_widget.setFocusPolicy(Qt.NoFocus)
        self.table_widget.setColumnCount(len(self.COLUMNS))
        self.table_widget.setRowCount(len(VALID_SLOTS))
        self.table_widget.horizontalHeader().hide()
        self.table_widget.verticalHeader().hide()
        self.table_widget.setShowGrid(False)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.itemClicked.connect(self._emit_slot_selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.table_widget, 1)

        self._render_table()

    @property
    def current_type(self) -> str:
        return self._current_type

    def set_current_type(self, color_type: str) -> None:
        self._current_type = color_type

    def set_available_slots(
        self,
        color_type: str,
        available_slots: set[str],
        selected_slot: str | None = None,
    ) -> None:
        self._available_slots[color_type] = set(available_slots)
        self._selected_slots[color_type] = selected_slot
        self._render_table()

    def _render_table(self) -> None:
        self.table_widget.blockSignals(True)
        self.table_widget.clear()
        self.table_widget.setRowCount(len(VALID_SLOTS))
        for row, slot in enumerate(VALID_SLOTS):
            for column, (color_type, prefix) in enumerate(self.COLUMNS):
                item = QTableWidgetItem(self._slot_label(prefix, slot))
                item.setData(256, slot)
                item.setData(257, color_type)
                available = slot in self._available_slots[color_type]
                if not available:
                    item.setFlags(
                        item.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable
                    )
                    item.setForeground(QBrush(self.DISABLED_COLOR))
                else:
                    item.setBackground(QBrush(self.AVAILABLE_COLOR))
                item.setToolTip(
                    "Available source slot" if available else "No source file detected"
                )
                self.table_widget.setItem(row, column, item)
                if slot == self._selected_slots[color_type]:
                    item.setSelected(True)
        self.table_widget.blockSignals(False)

    def _slot_label(self, prefix: str, slot: str) -> str:
        if not prefix:
            return format_slot_label(slot)
        return f"{prefix}{int(slot)}"

    def _emit_slot_selected(self, item: QTableWidgetItem) -> None:
        if not item.flags() & Qt.ItemIsEnabled:
            return
        color_type = item.data(257)
        slot = item.data(256)
        if color_type != self._current_type:
            self._current_type = color_type
            self.type_changed.emit(color_type)
        self.slot_selected.emit(slot)
