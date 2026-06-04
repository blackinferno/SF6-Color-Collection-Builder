from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QCloseEvent, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QStatusBar,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QTabWidget,
    QToolBar,
    QWidget,
)

from app.characters import CHARACTER_NAMES, character_label
from app.exporter import export_collection_zip
from app.models import CollectionAssignment, ScannedMod
from app.project_io import load_exported_collection_zip, save_project
from app.scanner import scan_mods_folder
from app.settings import (
    APP_ICON_PATH,
    APP_NAME,
    APP_VERSION,
    GITHUB_RELEASES_API_URL,
    GITHUB_RELEASES_PAGE_URL,
    PROJECT_ROOT,
    AppSettings,
)
from app.update_checker import UpdateInfo, check_latest_release
from app.ui.collection_column import CollectionColumn
from app.ui.mod_list import ModList
from app.ui.option_column import OptionColumn
from app.ui.slot_column import SlotColumn


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.settings = AppSettings()
        self._restore_window_geometry()
        self.current_output_path: Path | None = None
        self.update_thread: QThread | None = None
        self.update_worker: UpdateCheckWorker | None = None
        self.collection_name = "Custom Collection"
        self.assignments: dict[tuple[str, str, str, str], CollectionAssignment] = {}

        self.mods: list[ScannedMod] = []
        self.selected_mod: ScannedMod | None = None
        self.selected_character: str | None = None
        self.selected_costume: str | None = None
        self.selected_source_slot: str | None = None

        self.mod_list = ModList()
        self.character_column = OptionColumn("Character", columns=2)
        self.costume_column = OptionColumn("Costume")
        self.costume_column.setMinimumWidth(116)
        self.slot_column = SlotColumn()
        self.slot_column.setMinimumWidth(190)
        self.assignment_arrow = QLabel("->")
        self.assignment_arrow.setObjectName("assignmentArrow")
        self.assignment_arrow.setAlignment(Qt.AlignCenter)
        self.assignment_arrow.setMinimumWidth(28)
        self.collection_column = CollectionColumn()

        self._build_toolbar()
        self._build_layout()
        self._connect_signals()
        self._apply_styles()
        self._refresh_columns()
        self._scan_last_mods_folder()
        self._check_for_updates_on_startup()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.set_window_geometry(self.saveGeometry())
        super().closeEvent(event)

    def _restore_window_geometry(self) -> None:
        geometry = self.settings.window_geometry()
        if geometry.isEmpty() or not self.restoreGeometry(geometry):
            self.resize(1320, 760)

    def _build_toolbar(self) -> None:
        donation_toolbar = QToolBar("Donate")
        donation_toolbar.setObjectName("donationToolbar")
        donation_toolbar.setMovable(False)
        donation_toolbar.setIconSize(QSize(28, 28))

        top_spacer = QWidget()
        top_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        donation_toolbar.addWidget(top_spacer)
        donation_toolbar.addWidget(QLabel("Support MarshialLaw"))
        donation_toolbar.addAction(
            self._icon_action(
                "Buy Me a Coffee - MarshialLaw",
                "icon_bmc.svg",
                "https://buymeacoffee.com/marshial",
            )
        )
        donation_toolbar.addAction(
            self._icon_action(
                "Patreon - MarshialLaw",
                "icon_patreon.svg",
                "https://www.patreon.com/MarshialLaw",
            )
        )
        donation_toolbar.addAction(
            self._icon_action(
                "Ko-fi - MarshialLaw",
                "icon_kofi.svg",
                "https://ko-fi.com/marshiallaw",
            )
        )
        self.addToolBar(Qt.TopToolBarArea, donation_toolbar)

        action_toolbar = QToolBar("Actions")
        action_toolbar.setObjectName("actionToolbar")
        action_toolbar.setMovable(False)
        action_toolbar.setIconSize(QSize(28, 28))

        scan_button = QPushButton("Scan Mods Folder")
        scan_button.clicked.connect(self._choose_folder)
        action_toolbar.addWidget(scan_button)

        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        action_toolbar.addWidget(left_spacer)

        for label, callback in (
            ("New", self._new_project),
            ("Open", self._open_project),
            ("Save", self._save_project),
            ("Save As", self._save_project_as),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            action_toolbar.addWidget(button)

        self.addToolBar(Qt.BottomToolBarArea, action_toolbar)
        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.addPermanentWidget(DiagonalSizeGrip(self), 0)
        self.setStatusBar(status_bar)

    def _icon_action(self, label: str, icon_name: str, url: str) -> QAction:
        action = QAction(QIcon(str(self._img_path(icon_name))), label, self)
        action.setToolTip(label)
        action.triggered.connect(
            lambda _checked=False, target=url: webbrowser.open(target)
        )
        return action

    def _img_path(self, filename: str) -> Path:
        return PROJECT_ROOT / "img" / filename

    def _build_layout(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        for widget, stretch in (
            (self.mod_list, 5),
            (self.character_column, 2),
            (self.costume_column, 1),
            (self.slot_column, 2),
            (self.assignment_arrow, 0),
            (self.collection_column, 4),
        ):
            widget.setMinimumHeight(0)
            layout.addWidget(widget, stretch)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.mod_list.selected.connect(self._select_mod)
        self.character_column.selected.connect(self._select_character)
        self.costume_column.selected.connect(self._select_costume)
        self.slot_column.type_changed.connect(self._select_type)
        self.slot_column.slot_selected.connect(self._select_source_slot)
        self.collection_column.target_slot_selected.connect(self._assign_target_slot)
        self.collection_column.assignment_clear_requested.connect(
            self._clear_assignment
        )
        self.collection_column.show_summary_requested.connect(
            self._show_current_collection
        )
        self.collection_column.character_context_changed.connect(
            self._select_collection_character
        )
        self.collection_column.costume_context_changed.connect(
            self._select_collection_costume
        )

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QMainWindow,
            QWidget {
                background: #0f0f0f;
                color: #ffffff;
            }
            QToolBar {
                background: #0f0f0f;
                border: none;
                color: #c8c8c8;
                spacing: 6px;
                padding: 3px 6px;
            }
            QToolBar#donationToolbar {
                border-bottom: 1px solid #2a2a2a;
            }
            QToolBar#actionToolbar {
                border-top: 1px solid #2a2a2a;
            }
            QStatusBar {
                background: #0f0f0f;
                border: none;
                color: #c8c8c8;
            }
            QWidget#sectionPanel {
                background: #0f0f0f;
                border: none;
                border-radius: 10px;
            }
            QLineEdit,
            QComboBox {
                border: 1px solid #383838;
                border-radius: 6px;
                background: #0c0c0c;
                color: #ffffff;
                selection-background-color: rgba(249, 115, 6, 0.20);
                selection-color: #ffffff;
            }
            QListWidget,
            QTableWidget {
                border: 1px solid #383838;
                border-radius: 0;
                background: #0c0c0c;
                color: #ffffff;
                selection-background-color: rgba(249, 115, 6, 0.20);
                selection-color: #ffffff;
            }
            QLineEdit:focus,
            QComboBox:focus,
            QListWidget:focus,
            QTableWidget:focus {
                border-color: #383838;
            }
            QComboBox {
                padding: 4px 8px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #383838;
                background: #111111;
                color: #ffffff;
                selection-background-color: rgba(249, 115, 6, 0.28);
            }
            QPushButton {
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                background: #151515;
                color: #ffffff;
                padding: 6px 12px;
                font-weight: 600;
                min-height: 20px;
            }
            QPushButton:hover {
                border-color: #f97306;
                background: #1e1e1e;
            }
            QPushButton:pressed {
                background: rgba(249, 115, 6, 0.20);
                border-color: #f97306;
            }
            QPushButton:disabled {
                color: #6f6f6f;
                border-color: #242424;
                background: #111111;
            }
            QTabWidget::pane {
                border: none;
                border-radius: 0;
                background: transparent;
                top: -1px;
            }
            QTabBar::tab {
                border: 1px solid #2a2a2a;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 18px;
                background: #141414;
                color: #c8c8c8;
            }
            QTabBar::tab:selected {
                background: rgba(249, 115, 6, 0.16);
                border-color: #f97306;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                color: #ffffff;
                border-color: #f97306;
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 4px;
            }
            QListWidget::item:enabled {
                color: #ffffff;
            }
            QListWidget::item:disabled {
                color: #6f6f6f;
            }
            QListWidget::item:selected {
                border: none;
                border-left: 3px solid #f97306;
                background: #7a3a0a;
            }
            QListWidget::item:focus {
                outline: none;
            }
            QListWidget::item:hover:enabled {
                background: #1e1e1e;
            }
            QLabel {
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#assignmentArrow {
                color: #f97306;
                font-size: 24px;
                font-weight: 600;
                background: transparent;
            }
            QTableWidget {
                background: #0c0c0c;
                gridline-color: #2a2a2a;
            }
            QTableWidget::item {
                padding: 4px;
                border-radius: 4px;
            }
            QTableWidget::item:enabled {
                color: #ffffff;
            }
            QTableWidget::item:disabled {
                color: #6f6f6f;
            }
            QTableWidget::item:selected {
                border: none;
                border-left: 3px solid #f97306;
                background: #7a3a0a;
            }
            QTableWidget::item:focus {
                outline: none;
            }
            QHeaderView::section {
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                color: #ffffff;
                padding: 4px 6px;
                font-weight: 600;
            }
            QScrollBar:vertical,
            QScrollBar:horizontal {
                background: #0c0c0c;
                border: none;
                margin: 0;
            }
            QScrollBar:vertical {
                width: 10px;
            }
            QScrollBar:horizontal {
                height: 10px;
            }
            QScrollBar::handle:vertical,
            QScrollBar::handle:horizontal {
                background: #6a6a6a;
                border-radius: 5px;
                min-height: 24px;
                min-width: 24px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: #0c0c0c;
            }
            QScrollBar::handle:vertical:hover,
            QScrollBar::handle:horizontal:hover {
                background: #8a8a8a;
            }
            QScrollBar::add-line,
            QScrollBar::sub-line,
            QScrollBar::up-arrow,
            QScrollBar::down-arrow,
            QScrollBar::left-arrow,
            QScrollBar::right-arrow {
                background: #0c0c0c;
                border: none;
                width: 0;
                height: 0;
            }
            QWidget#collectionSlotRow {
                background: transparent;
            }
            QLabel#collectionSlotLabel {
                background: transparent;
                color: #ffffff;
                font-weight: 400;
            }
            QPushButton#clearSlotButton {
                background: #151515;
                border: 1px solid #383838;
                padding: 0 6px;
                min-height: 20px;
                max-height: 22px;
            }
            QPushButton#clearSlotButton:hover {
                background: #1e1e1e;
                border-color: #f97306;
            }
            QToolTip {
                background: #222222;
                color: #eeeeee;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 6px;
            }
            QLabel#modRowPreview {
                border: 1px solid #2a2a2a;
                background: #0d0d0d;
            }
            QWidget#modRow {
                background: transparent;
            }
            QLabel#modRowField {
                color: #c8c8c8;
                font-weight: 600;
                background: transparent;
            }
            QLabel#modRowValue {
                color: #ffffff;
                font-weight: 400;
                background: transparent;
            }
            """)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select SF6 Mods Folder",
            self.settings.last_mods_folder(),
        )
        if not folder:
            return
        self.settings.set_last_mods_folder(folder)
        self._scan_folder(Path(folder))

    def _scan_last_mods_folder(self) -> None:
        last_folder = self.settings.last_mods_folder()
        if last_folder and Path(last_folder).is_dir():
            self._scan_folder(Path(last_folder))

    def _scan_folder(self, folder: Path) -> None:
        self.statusBar().showMessage("Scanning zip mods...")
        self.mods = scan_mods_folder(folder)
        self.mod_list.set_mods(self.mods)
        self.mod_list.show_preview(None)
        self.selected_mod = None
        self.selected_character = None
        self.selected_costume = None
        self.selected_source_slot = None
        self._refresh_columns()
        self.statusBar().showMessage(
            f"Found {len(self.mods)} zip mods with supported data.", 5000
        )

    def _select_mod(self, index: int) -> None:
        self.selected_mod = self.mods[index]
        self.mod_list.show_preview(self.selected_mod)
        mod_characters = self.selected_mod.characters()
        if len(mod_characters) == 1:
            self.selected_character = next(iter(mod_characters))
            if self.selected_costume not in self.selected_mod.costumes_for(
                self.selected_character
            ):
                self.selected_costume = None
        self.selected_source_slot = None
        self._auto_select_single_source_path()
        self._refresh_columns()

    def _select_character(self, character: str) -> None:
        self.selected_character = character
        self.selected_costume = None
        self.selected_source_slot = None
        self._auto_select_single_source_path()
        self._refresh_columns()

    def _select_costume(self, costume: str) -> None:
        self.selected_costume = costume
        self.selected_source_slot = None
        self._auto_select_single_source_slot()
        self._refresh_columns()

    def _select_collection_character(self, character: str) -> None:
        self.selected_character = character
        self.selected_costume = None
        self.selected_source_slot = None
        self._refresh_columns()

    def _select_collection_costume(self, costume: str) -> None:
        self.selected_costume = costume
        self.selected_source_slot = None
        self._refresh_columns()

    def _select_type(self, _color_type: str) -> None:
        self.selected_source_slot = None
        self._refresh_columns()

    def _select_source_slot(self, slot: str) -> None:
        self.selected_source_slot = slot
        self._refresh_columns()

    def _auto_select_single_source_path(self) -> None:
        if not self.selected_mod or not self.selected_character:
            return
        available_costumes = self.selected_mod.costumes_for(self.selected_character)
        if len(available_costumes) == 1:
            self.selected_costume = next(iter(available_costumes))
            self._auto_select_single_source_slot()

    def _auto_select_single_source_slot(self) -> None:
        if not self.selected_mod or not self.selected_character or not self.selected_costume:
            return
        available_sources: list[tuple[str, str]] = []
        for color_type in ("normal", "dx", "ex"):
            for slot in self.selected_mod.slots_for(
                self.selected_character,
                self.selected_costume,
                color_type,
            ):
                available_sources.append((color_type, slot))
        if len(available_sources) == 1:
            color_type, slot = available_sources[0]
            self.slot_column.set_current_type(color_type)
            self.selected_source_slot = slot

    def _assign_target_slot(self, target_type: str, target_slot: str) -> None:
        if (
            not self.selected_mod
            or not self.selected_character
            or not self.selected_costume
            or not self.selected_source_slot
        ):
            return

        source_type = self.slot_column.current_type
        if target_type != source_type:
            self.statusBar().showMessage(
                "Use the matching Custom Collection tab for the selected source type.",
                3000,
            )
            return

        source = self.selected_mod.source_for(
            self.selected_character,
            self.selected_costume,
            source_type,
            self.selected_source_slot,
        )
        if not source:
            return

        key = (source.character, source.costume, source.type, target_slot)
        existing = self.assignments.get(key)
        if existing and existing.source_mod_name != source.mod_name:
            answer = QMessageBox.question(
                self,
                "Replace Target Slot",
                (
                    f"Replace target {int(target_slot):02d} "
                    f"({existing.source_mod_name}) with {source.mod_name}?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                self.statusBar().showMessage("Assignment was not changed.", 3000)
                return

        assignment = CollectionAssignment(
            character=source.character,
            costume=source.costume,
            type=source.type,
            target_slot=target_slot,
            source_zip=source.zip_path,
            source_internal_file_path=source.internal_file_path,
            source_slot=source.source_slot,
            source_mod_name=source.mod_name,
        )
        self.assignments[assignment.key] = assignment
        self._refresh_columns()
        self.statusBar().showMessage(
            f"Assigned {source.mod_name} slot {int(source.source_slot):02d} to target {int(target_slot):02d}.",
            4000,
        )

    def _clear_assignment(self, target_type: str, target_slot: str) -> None:
        if not self.selected_character or not self.selected_costume:
            return
        key = (
            self.selected_character,
            self.selected_costume,
            target_type,
            target_slot,
        )
        removed = self.assignments.pop(key, None)
        if removed:
            self._refresh_columns()
            self.statusBar().showMessage(
                f"Cleared {removed.source_mod_name} from target {int(target_slot):02d}.",
                3000,
            )

    def _refresh_columns(self) -> None:
        character_values = self._all_known_characters()
        available_characters = (
            self.selected_mod.characters() if self.selected_mod else set()
        )
        self.character_column.set_options(
            {
                value: (
                    character_label(value)
                    if self.settings.use_character_names()
                    else value
                )
                for value in character_values
            },
            available_characters,
            self.selected_character,
        )

        costume_values = [f"{costume:03d}" for costume in range(1, 6)]
        available_costumes = (
            self.selected_mod.costumes_for(self.selected_character)
            if self.selected_mod and self.selected_character
            else set()
        )
        self.costume_column.set_options(
            {value: f"Costume {int(value)}" for value in costume_values},
            available_costumes,
            self.selected_costume,
        )

        collection_characters = self._all_collection_characters()
        collection_costumes = self._all_collection_costumes(self.selected_character)
        self.collection_column.set_context_options(
            {
                value: (
                    character_label(value)
                    if self.settings.use_character_names()
                    else value
                )
                for value in collection_characters
            },
            {value: f"Costume {int(value)}" for value in collection_costumes},
            self.selected_character,
            self.selected_costume,
        )

        for color_type in ("normal", "dx", "ex"):
            available_slots = (
                self.selected_mod.slots_for(
                    self.selected_character,
                    self.selected_costume,
                    color_type,
                )
                if self.selected_mod
                and self.selected_character
                and self.selected_costume
                else set()
            )
            selected_slot = (
                self.selected_source_slot
                if color_type == self.slot_column.current_type
                else None
            )
            self.slot_column.set_available_slots(
                color_type, available_slots, selected_slot
            )

        self.collection_column.refresh_all(
            self.assignments,
            self.slot_column.current_type,
            source_selected=self.selected_source_slot is not None,
            character=self.selected_character,
            costume=self.selected_costume,
        )

    def _all_known_characters(self) -> list[str]:
        characters = {
            source.character for mod in self.mods for source in mod.source_files
        }
        if characters:
            return self._sort_characters(characters)
        return self._sort_characters(CHARACTER_NAMES)

    def _all_collection_characters(self) -> list[str]:
        characters = set(self._all_known_characters())
        characters.update(key[0] for key in self.assignments)
        if self.selected_character:
            characters.add(self.selected_character)
        return self._sort_characters(characters)

    def _all_collection_costumes(self, character: str | None) -> list[str]:
        costumes = {f"{costume:03d}" for costume in range(1, 6)}
        if self.selected_costume:
            costumes.add(self.selected_costume)
        if character:
            costumes.update(
                assignment.costume
                for assignment in self.assignments.values()
                if assignment.character == character
            )
        return sorted(costumes)

    def _sort_characters(self, characters: set[str] | dict[str, str]) -> list[str]:
        return sorted(characters, key=lambda value: character_label(value).lower())

    def _new_project(self) -> None:
        self.current_output_path = None
        self.collection_name = "Custom Collection"
        self.assignments.clear()
        self.selected_character = None
        self.selected_costume = None
        self.selected_source_slot = None
        self._refresh_columns()
        self.statusBar().showMessage("Started a new collection project.", 3000)

    def _open_project(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Collection Zip",
            self.settings.last_project_folder(),
            "Zip Mods (*.zip)",
        )
        if not path:
            return
        project_path = Path(path)
        collection_name, mods_folder, assignments = load_exported_collection_zip(
            project_path
        )
        self.collection_name = collection_name
        self.assignments = {assignment.key: assignment for assignment in assignments}
        self.current_output_path = project_path
        self.settings.set_last_project_folder(project_path.parent)
        if mods_folder:
            self.settings.set_last_mods_folder(mods_folder)
            if Path(mods_folder).is_dir():
                self._scan_folder(Path(mods_folder))
        self._select_first_assignment_context(assignments)
        self._refresh_columns()
        self.statusBar().showMessage(f"Loaded {len(assignments)} assignments.", 4000)

    def _save_project(self) -> None:
        if self.current_output_path is None:
            self._save_project_as()
            return
        self._export_to_path(self.current_output_path)

    def _save_project_as(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            "Collection Name",
            "Collection name:",
            text=self.collection_name,
        )
        if not accepted or not name.strip():
            return
        self.collection_name = name.strip()

        default_path = Path(self.settings.last_project_folder()) / self._safe_filename(
            self.collection_name,
            ".zip",
        )
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Collection",
            str(default_path),
            "Zip Mods (*.zip)",
        )
        if not path:
            return
        output_path = Path(path)
        if output_path.suffix == "":
            output_path = output_path.with_suffix(".zip")
        self.current_output_path = output_path
        self._export_to_path(output_path)

    def _select_first_assignment_context(
        self,
        assignments: list[CollectionAssignment],
    ) -> None:
        if not assignments:
            self.selected_character = None
            self.selected_costume = None
            self.selected_source_slot = None
            return
        first = sorted(assignments, key=lambda assignment: assignment.key)[0]
        self.selected_character = first.character
        self.selected_costume = first.costume
        self.selected_source_slot = None

    def _export_to_path(self, output_path: Path) -> None:
        if output_path.suffix.lower() == ".json":
            save_project(
                output_path,
                self.collection_name,
                self.settings.last_mods_folder(),
                sorted(self.assignments.values(), key=lambda item: item.key),
            )
            self.settings.set_last_project_folder(output_path.parent)
            self.statusBar().showMessage(f"Saved {output_path.name}.", 5000)
            return

        if not self.assignments:
            QMessageBox.information(
                self,
                APP_NAME,
                "Assign at least one target slot before saving.",
            )
            return

        self.settings.set_last_project_folder(output_path.parent)
        export_collection_zip(
            output_path,
            self.collection_name,
            sorted(self.assignments.values(), key=lambda item: item.key),
        )
        self.statusBar().showMessage(f"Saved {output_path.name}.", 5000)

    def _show_current_collection(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Current Collection")
        dialog.resize(1100, 620)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.South)
        for character in self._sort_characters(CHARACTER_NAMES):
            table = self._collection_character_table(character)
            index = tabs.addTab(table, character_label(character))
            if not self._character_has_assignments(character):
                tabs.tabBar().setTabTextColor(index, QColor("#69707a"))

        layout = QVBoxLayout(dialog)
        layout.addWidget(tabs)
        dialog.exec()

    def _collection_summary_rows(self) -> list[tuple[str, str, str, str, str]]:
        rows: list[tuple[str, str, str, str, str]] = []
        for character in self._sort_characters(CHARACTER_NAMES):
            character_name = (
                character_label(character)
                if self.settings.use_character_names()
                else character
            )
            for costume in (f"{number:03d}" for number in range(1, 6)):
                for color_type in ("normal", "dx", "ex"):
                    type_label = (
                        color_type.upper() if color_type != "normal" else "Normal"
                    )
                    for slot in (f"{number:03d}" for number in range(1, 11)):
                        assignment = self.assignments.get(
                            (character, costume, color_type, slot)
                        )
                        rows.append(
                            (
                                character_name,
                                f"Costume {int(costume)}",
                                type_label,
                                f"{int(slot):02d}",
                                assignment.source_mod_name if assignment else "empty",
                            )
                        )
        return rows

    def _collection_character_table(self, character: str) -> QTableWidget:
        costumes = [f"{number:03d}" for number in range(1, 6)]
        color_types = ("normal", "dx", "ex")
        rows = [
            (color_type, f"{slot:03d}")
            for color_type in color_types
            for slot in range(1, 11)
        ]

        table = QTableWidget()
        table.setRowCount(len(rows))
        table.setColumnCount(1 + len(costumes))
        table.setHorizontalHeaderLabels(
            ["Slot"] + [f"Costume {int(costume)}" for costume in costumes]
        )
        table.setVerticalHeaderLabels(
            [self._summary_slot_label(color_type, slot) for color_type, slot in rows]
        )

        for row_index, (color_type, slot) in enumerate(rows):
            table.setItem(
                row_index,
                0,
                QTableWidgetItem(self._summary_slot_label(color_type, slot)),
            )
            for column_index, costume in enumerate(costumes, start=1):
                assignment = self.assignments.get(
                    (character, costume, color_type, slot)
                )
                table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(assignment.source_mod_name if assignment else ""),
                )

        table.resizeColumnsToContents()
        table.setColumnWidth(0, 72)
        for column in range(1, table.columnCount()):
            table.setColumnWidth(column, max(table.columnWidth(column), 180))
        table.resizeRowsToContents()
        return table

    def _character_has_assignments(self, character: str) -> bool:
        return any(
            assignment.character == character
            for assignment in self.assignments.values()
        )

    def _summary_slot_label(self, color_type: str, slot: str) -> str:
        if color_type == "normal":
            return f"{int(slot):02d}"
        return f"{color_type.upper()}{int(slot):02d}"

    def _safe_filename(self, name: str, suffix: str) -> str:
        safe_name = "".join(
            character if character not in '<>:"/\\|?*' else "_"
            for character in name.strip()
        ).strip()
        return f"{safe_name or 'Custom Collection'}{suffix}"

    def _check_for_updates_on_startup(self) -> None:
        if not self.settings.check_updates() or not GITHUB_RELEASES_API_URL:
            return

        self.update_thread = QThread(self)
        self.update_worker = UpdateCheckWorker(GITHUB_RELEASES_API_URL, APP_VERSION)
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.update_available.connect(self._show_update_available)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(self._clear_update_worker)
        self.update_thread.start()

    def _show_update_available(self, update: UpdateInfo) -> None:
        release_url = update.release_url or GITHUB_RELEASES_PAGE_URL
        message = f"Version {update.latest_version} is available."
        if release_url:
            answer = QMessageBox.question(
                self,
                "Update Available",
                f"{message}\n\nOpen the GitHub release page?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                webbrowser.open(release_url)
        else:
            QMessageBox.information(self, "Update Available", message)

    def _clear_update_worker(self) -> None:
        self.update_thread = None
        self.update_worker = None


class UpdateCheckWorker(QObject):
    update_available = Signal(object)
    finished = Signal()

    def __init__(self, api_url: str, current_version: str) -> None:
        super().__init__()
        self.api_url = api_url
        self.current_version = current_version

    def run(self) -> None:
        try:
            update = check_latest_release(self.api_url, self.current_version)
            if update:
                self.update_available.emit(update)
        finally:
            self.finished.emit()


class DiagonalSizeGrip(QSizeGrip):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(18, 18)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0f0f0f"))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        for offset in (4, 8, 12):
            painter.drawLine(self.width() - offset, self.height() - 2, self.width() - 2, self.height() - offset)
