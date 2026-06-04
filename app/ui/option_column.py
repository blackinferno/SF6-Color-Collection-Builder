from __future__ import annotations

from math import ceil

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class OptionColumn(QWidget):
    selected = Signal(str)
    AVAILABLE_COLOR = QColor("#1f3347")
    SELECTED_COLOR = QColor("#7a3a0a")
    DISABLED_COLOR = QColor("#69707a")

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        columns: int = 1,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        self.columns = columns
        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignCenter)
        self.list_widget: QListWidget | None = None
        self.table_widget: QTableWidget | None = None

        if columns > 1:
            self.table_widget = QTableWidget()
            self.table_widget.setFocusPolicy(Qt.NoFocus)
            self.table_widget.setColumnCount(columns)
            self.table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.table_widget.horizontalHeader().hide()
            self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.table_widget.verticalHeader().hide()
            self.table_widget.setShowGrid(False)
            self.table_widget.setSelectionBehavior(QTableWidget.SelectItems)
            self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
            self.table_widget.itemClicked.connect(self._emit_table_selected)
        else:
            self.list_widget = QListWidget()
            self.list_widget.setFocusPolicy(Qt.NoFocus)
            self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
            self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.list_widget.itemClicked.connect(self._emit_list_selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.table_widget or self.list_widget)

    def set_options(
        self,
        labels_by_value: dict[str, str],
        available_values: set[str],
        selected_value: str | None = None,
    ) -> None:
        if self.table_widget:
            self._set_table_options(labels_by_value, available_values, selected_value)
            return

        assert self.list_widget is not None
        self.list_widget.clear()
        for value, label in labels_by_value.items():
            item = QListWidgetItem(label)
            item.setData(256, value)
            available = value in available_values
            if not available:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable)
                item.setForeground(QBrush(self.DISABLED_COLOR))
                item.setToolTip("No source file detected in the selected mod")
            else:
                item.setBackground(QBrush(self.AVAILABLE_COLOR))
                item.setToolTip("Available")
            self.list_widget.addItem(item)
            if value == selected_value:
                item.setSelected(True)
                self.list_widget.setCurrentItem(item)

    def _set_table_options(
        self,
        labels_by_value: dict[str, str],
        available_values: set[str],
        selected_value: str | None,
    ) -> None:
        assert self.table_widget is not None
        values = list(labels_by_value.items())
        self.table_widget.clear()
        self.table_widget.setRowCount(ceil(len(values) / self.columns))

        for index, (value, label) in enumerate(values):
            row = index // self.columns
            column = index % self.columns
            item = QTableWidgetItem(label)
            item.setData(256, value)
            available = value in available_values
            if not available:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable)
                item.setForeground(QBrush(self.DISABLED_COLOR))
                item.setToolTip("No source file detected in the selected mod")
            else:
                item.setBackground(QBrush(self.AVAILABLE_COLOR))
                item.setToolTip("Available")
            self.table_widget.setItem(row, column, item)
            if value == selected_value:
                item.setSelected(True)

        self.table_widget.resizeColumnsToContents()
        self.table_widget.resizeRowsToContents()

    def _emit_list_selected(self, item: QListWidgetItem) -> None:
        if item.flags() & Qt.ItemIsEnabled:
            self.selected.emit(item.data(256))

    def _emit_table_selected(self, item: QTableWidgetItem) -> None:
        if item.flags() & Qt.ItemIsEnabled:
            self.selected.emit(item.data(256))
