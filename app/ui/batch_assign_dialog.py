from __future__ import annotations

from math import ceil

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.characters import character_label
from app.models import ScannedMod, VALID_SLOTS
from app.parser import format_slot_label


class BatchAssignDialog(QDialog):
    COLUMNS = (("normal", ""), ("dx", "DX"), ("ex", "EX"))
    ENABLED_COLOR = QColor("#ffffff")
    DISABLED_COLOR = QColor("#69707a")

    def __init__(
        self,
        mod: ScannedMod,
        selected_source_type: str,
        selected_source_slot: str | None,
        selected_target_type: str,
        use_character_names: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Batch Assign")
        self.resize(860, 520)
        self.mod = mod
        self.use_character_names = use_character_names
        self._source_selection: tuple[str, str] | None = None
        self._target_selection: tuple[str, str] | None = None
        self._default_source_type = selected_source_type
        self._default_source_slot = selected_source_slot

        self.character_table = QTableWidget()
        self.character_table.setColumnCount(2)
        self.character_table.horizontalHeader().hide()
        self.character_table.verticalHeader().hide()
        self.character_table.setShowGrid(False)
        self.character_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.character_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.character_table.setMaximumWidth(310)
        self.character_table.itemClicked.connect(self._toggle_table_check)
        self.costume_list = QListWidget()
        self.costume_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.costume_list.setMinimumWidth(132)
        self.costume_list.setMaximumWidth(160)
        self.costume_list.itemClicked.connect(self._toggle_list_check)
        self.source_table = self._build_slot_table()
        self.target_table = self._build_slot_table()
        self.source_table.setMaximumWidth(210)
        self.target_table.setMaximumWidth(210)

        self._build_layout()
        self._populate_characters()
        self._refresh_costumes()
        self._refresh_source_slots(selected_source_type, selected_source_slot)
        default_target_slot = selected_source_slot or self._first_available_source_slot()
        self._populate_slot_table(
            self.target_table,
            enabled_slots={(color_type, slot) for color_type, _prefix in self.COLUMNS for slot in VALID_SLOTS},
            selected_type=selected_target_type,
            selected_slot=default_target_slot,
        )

        self.character_table.itemChanged.connect(self._refresh_after_character_change)
        self.costume_list.itemChanged.connect(self._refresh_after_costume_change)
        self.source_table.itemClicked.connect(self._select_source_item)
        self.target_table.itemClicked.connect(self._select_target_item)

    @property
    def selected_characters(self) -> set[str]:
        return self._checked_table_values(self.character_table)

    @property
    def selected_costumes(self) -> set[str]:
        return self._checked_values(self.costume_list)

    @property
    def source_type(self) -> str:
        assert self._source_selection is not None
        return self._source_selection[0]

    @property
    def source_slot(self) -> str:
        assert self._source_selection is not None
        return self._source_selection[1]

    @property
    def target_type(self) -> str:
        assert self._target_selection is not None
        return self._target_selection[0]

    @property
    def target_slot(self) -> str:
        assert self._target_selection is not None
        return self._target_selection[1]

    def _build_layout(self) -> None:
        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)
        content_layout.addWidget(self._group_box("Characters", self._character_panel()), 2)
        content_layout.addWidget(self._group_box("Costumes", self.costume_list), 1)
        content_layout.addWidget(self._group_box("Source Slot", self.source_table), 2)
        arrow = QLabel("->")
        arrow.setObjectName("assignmentArrow")
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setMinimumWidth(24)
        content_layout.addWidget(arrow)
        content_layout.addWidget(self._group_box("Target Slot", self.target_table), 2)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose source characters, costumes, and one source/target slot pair."))
        layout.addLayout(content_layout, 1)
        layout.addWidget(button_box)

    def _group_box(self, title: str, widget: QWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(widget)
        return group

    def _character_panel(self) -> QWidget:
        panel = QWidget()
        select_all_button = QPushButton("Select All")
        unselect_all_button = QPushButton("Unselect All")
        select_all_button.clicked.connect(lambda: self._set_all_characters(Qt.Checked))
        unselect_all_button.clicked.connect(lambda: self._set_all_characters(Qt.Unchecked))

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(select_all_button)
        button_layout.addWidget(unselect_all_button)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(button_layout)
        layout.addWidget(self.character_table, 1)
        return panel

    def _build_slot_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(self.COLUMNS))
        table.setRowCount(len(VALID_SLOTS))
        table.horizontalHeader().hide()
        table.verticalHeader().hide()
        table.setShowGrid(False)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMaximumWidth(190)
        return table

    def _populate_characters(self) -> None:
        self.character_table.blockSignals(True)
        self.character_table.clear()
        characters = sorted(
            self.mod.characters(), key=lambda value: character_label(value).lower()
        )
        self.character_table.setRowCount(ceil(len(characters) / 2))
        for index, character in enumerate(characters):
            item = QTableWidgetItem(self._character_label(character))
            item.setData(256, character)
            item.setCheckState(Qt.Unchecked)
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            self.character_table.setItem(index // 2, index % 2, item)
        self.character_table.resizeRowsToContents()
        self.character_table.blockSignals(False)

    def _refresh_costumes(self) -> None:
        checked_costumes = self.selected_costumes
        selected_characters = self.selected_characters
        available_costumes = sorted(
            {
                source.costume
                for source in self.mod.source_files
                if not selected_characters or source.character in selected_characters
            }
        )
        self.costume_list.blockSignals(True)
        self.costume_list.clear()
        for costume in available_costumes:
            item = QListWidgetItem(f"Costume {int(costume)}")
            item.setData(256, costume)
            item.setCheckState(
                Qt.Checked if costume in checked_costumes else Qt.Unchecked
            )
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            self.costume_list.addItem(item)
        self.costume_list.blockSignals(False)

    def _toggle_table_check(self, item: QTableWidgetItem) -> None:
        item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def _toggle_list_check(self, item: QListWidgetItem) -> None:
        item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def _refresh_after_character_change(self) -> None:
        self._refresh_costumes()
        self._refresh_source_slots()

    def _refresh_after_costume_change(self) -> None:
        self._refresh_source_slots()

    def _set_all_characters(self, check_state: Qt.CheckState) -> None:
        self.character_table.blockSignals(True)
        for row in range(self.character_table.rowCount()):
            for column in range(self.character_table.columnCount()):
                item = self.character_table.item(row, column)
                if item:
                    item.setCheckState(check_state)
        self.character_table.blockSignals(False)
        self._refresh_costumes()
        self._refresh_source_slots()

    def _refresh_source_slots(
        self,
        selected_type: str | None = None,
        selected_slot: str | None = None,
    ) -> None:
        current_type, current_slot = self._source_selection or (
            self._default_source_type,
            self._default_source_slot,
        )
        self._populate_slot_table(
            self.source_table,
            enabled_slots=self._available_source_slots_for_selection(),
            selected_type=selected_type or current_type,
            selected_slot=selected_slot or current_slot,
        )

    def _populate_slot_table(
        self,
        table: QTableWidget,
        enabled_slots: set[tuple[str, str]],
        selected_type: str,
        selected_slot: str | None,
    ) -> None:
        fallback: QTableWidgetItem | None = None
        table.blockSignals(True)
        table.clear()
        for row, slot in enumerate(VALID_SLOTS):
            for column, (color_type, prefix) in enumerate(self.COLUMNS):
                item = QTableWidgetItem(self._slot_label(prefix, slot))
                item.setData(256, color_type)
                item.setData(257, slot)
                enabled = (color_type, slot) in enabled_slots
                if not enabled:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable)
                    item.setForeground(QBrush(self.DISABLED_COLOR))
                else:
                    item.setForeground(QBrush(self.ENABLED_COLOR))
                table.setItem(row, column, item)
                if enabled and fallback is None:
                    fallback = item
                if enabled and color_type == selected_type and slot == selected_slot:
                    self._select_table_item(table, item)
        if not table.selectedItems() and fallback is not None:
            self._select_table_item(table, fallback)
        table.resizeColumnsToContents()
        table.blockSignals(False)

    def _select_source_item(self, item: QTableWidgetItem) -> None:
        if item.flags() & Qt.ItemIsEnabled:
            self._select_table_item(self.source_table, item)

    def _select_target_item(self, item: QTableWidgetItem) -> None:
        if item.flags() & Qt.ItemIsEnabled:
            self._select_table_item(self.target_table, item)

    def _select_table_item(self, table: QTableWidget, item: QTableWidgetItem) -> None:
        table.clearSelection()
        item.setSelected(True)
        selection = (item.data(256), item.data(257))
        if table is self.source_table:
            self._source_selection = selection
        else:
            self._target_selection = selection

    def _available_source_slots(self) -> set[tuple[str, str]]:
        return {(source.type, source.source_slot) for source in self.mod.source_files}

    def _available_source_slots_for_selection(self) -> set[tuple[str, str]]:
        selected_characters = self.selected_characters
        selected_costumes = self.selected_costumes
        return {
            (source.type, source.source_slot)
            for source in self.mod.source_files
            if (not selected_characters or source.character in selected_characters)
            and (not selected_costumes or source.costume in selected_costumes)
        }

    def _first_available_source_slot(self) -> str | None:
        available = sorted(
            self._available_source_slots(),
            key=lambda item: (VALID_SLOTS.index(item[1]), item[0]),
        )
        return available[0][1] if available else None

    def _checked_values(self, list_widget: QListWidget) -> set[str]:
        return {
            item.data(256)
            for index in range(list_widget.count())
            if (item := list_widget.item(index)).checkState() == Qt.Checked
        }

    def _checked_table_values(self, table: QTableWidget) -> set[str]:
        values: set[str] = set()
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item and item.checkState() == Qt.Checked:
                    values.add(item.data(256))
        return values

    def _slot_label(self, prefix: str, slot: str) -> str:
        if not prefix:
            return format_slot_label(slot)
        return f"{prefix}{int(slot)}"

    def _character_label(self, character: str) -> str:
        if self.use_character_names:
            return character_label(character)
        return character
