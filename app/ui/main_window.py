from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QCloseEvent, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QStackedWidget,
    QToolBar,
    QWidget,
    QApplication,
)

from app.archive_utils import ArchiveWriteError, is_supported_archive
from app.auto_updater import can_auto_update, launch_prepared_update, prepare_update
from app.characters import CHARACTER_NAMES, character_label
from app.cmd_updater import CmdUpdateReport, update_cmds_in_source
from app.exporter import can_write_collection_archive, export_collection_archive
from app.models import CollectionAssignment, ScannedMod
from app.project_io import load_exported_collection_zip
from app.scanner import (
    ScanReport,
    scan_mods_folder_with_report,
    scan_rechunk_source_with_report,
)
from app.scan_cache import clear_scan_cache, load_scan_cache, save_scan_cache
from app.settings import (
    APP_ICON_PATH,
    APP_NAME,
    APP_VERSION,
    GITHUB_RELEASES_API_URL,
    GITHUB_RELEASES_PAGE_URL,
    PROJECT_ROOT,
    UPDATE_LOG_PATH,
    AppSettings,
)
from app.update_checker import UpdateInfo, check_latest_release
from app.ui.batch_assign_dialog import BatchAssignDialog
from app.ui.collection_column import CollectionColumn
from app.ui.mod_list import ModList
from app.ui.option_column import OptionColumn
from app.ui.slot_column import SlotColumn


CHANGE_LOG_MESSAGE = (
    "Recent changes:\n"
    "- Added batch assignment for selected characters and costumes.\n"
    "- Batch assignment can move one source slot to one target slot across Normal, DX, and EX.\n"
    "- Added character select controls in the batch assignment dialog."
)


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
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.cmd_update_thread: QThread | None = None
        self.cmd_update_worker: CmdUpdateWorker | None = None
        self.scan_source_key = "mods"
        self.mods_by_source: dict[str, list[ScannedMod]] = {
            key: [] for key, _label in ModList.SOURCES
        }
        self.scanned_sources_this_session: set[str] = set()
        self.collection_name = "Custom Collection"
        self.collection_info_fields = self._default_collection_info_fields(
            self.collection_name
        )
        self.collection_preview_path: Path | None = None
        self.assignments: dict[tuple[str, str, str, str], CollectionAssignment] = {}

        self.mods: list[ScannedMod] = []
        self.selected_mod: ScannedMod | None = None
        self.selected_character: str | None = None
        self.selected_costume: str | None = None
        self.selected_source_slot: str | None = None

        self.mod_list = ModList()
        self.character_column = OptionColumn("Character", columns=2)
        self.character_column.setMinimumWidth(250)
        self.costume_column = OptionColumn("Costume")
        self.costume_column.setMinimumWidth(116)
        self.slot_column = SlotColumn()
        self.slot_column.setMinimumWidth(190)
        self.batch_assign_button = QPushButton("Batch Assign")
        self.batch_assign_button.clicked.connect(self._open_batch_assign_dialog)
        self.batch_assign_button.setEnabled(False)
        self.slot_column.layout().addWidget(self.batch_assign_button)
        self.assignment_arrow = QLabel("->")
        self.assignment_arrow.setObjectName("assignmentArrow")
        self.assignment_arrow.setAlignment(Qt.AlignCenter)
        self.assignment_arrow.setMinimumWidth(28)
        self.collection_column = CollectionColumn()

        self._build_toolbar()
        self._build_layout()
        self._connect_signals()
        self._apply_styles()
        self.mod_list.set_current_source(self.settings.selected_scan_source())
        self.scan_source_key = self.mod_list.current_source_key
        self._refresh_columns()
        QTimer.singleShot(0, self._scan_current_source_on_startup)
        self._show_version_changes_once()
        self._check_for_updates_on_startup()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.set_window_geometry(self.saveGeometry())
        super().closeEvent(event)

    def _restore_window_geometry(self) -> None:
        geometry = self.settings.window_geometry()
        if geometry.isEmpty() or not self.restoreGeometry(geometry):
            self.resize(1415, 760)
        elif self.width() < 1415:
            self.resize(1415, self.height())

    def _build_toolbar(self) -> None:
        donation_toolbar = QToolBar("Donate")
        donation_toolbar.setObjectName("donationToolbar")
        donation_toolbar.setMovable(False)
        donation_toolbar.setIconSize(QSize(28, 28))

        update_log_button = QPushButton("Update Log")
        update_log_button.clicked.connect(self._show_update_log)
        donation_toolbar.addWidget(update_log_button)

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

        select_folder_button = QPushButton("Select Folder")
        select_folder_button.clicked.connect(self._choose_folder)
        action_toolbar.addWidget(select_folder_button)

        scan_button = QPushButton("Scan")
        scan_button.clicked.connect(self._rescan_current_folder)
        action_toolbar.addWidget(scan_button)

        update_cmds_button = QPushButton("Update CMDs")
        update_cmds_button.clicked.connect(self._update_cmds_current_folder)
        action_toolbar.addWidget(update_cmds_button)

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
            (self.character_column, 3),
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
        self.mod_list.source_changed.connect(self._select_scan_source)
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
        self.collection_column.edit_info_requested.connect(self._edit_collection_info)
        self.collection_column.character_context_changed.connect(
            self._select_collection_character
        )
        self.collection_column.costume_context_changed.connect(
            self._select_collection_costume
        )

    def _apply_styles(self) -> None:
        combo_arrow_path = (PROJECT_ROOT / "img" / "combo_down_arrow.svg").as_posix()
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
                padding: 4px 28px 4px 8px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
                subcontrol-origin: padding;
                subcontrol-position: top right;
            }
            QComboBox::down-arrow {
                image: url(__COMBO_ARROW_PATH__);
                width: 12px;
                height: 8px;
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
            QTabBar::tab:disabled {
                color: #555555;
                background: #0f0f0f;
                border-color: #202020;
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
            QPushButton#summaryTabButton {
                border: 1px solid #2a2a2a;
                border-radius: 0;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                background: #141414;
                color: #c8c8c8;
                padding: 6px 12px;
                font-weight: 400;
                min-height: 20px;
            }
            QPushButton#summaryTabButton:checked {
                background: rgba(249, 115, 6, 0.16);
                border-color: #f97306;
                color: #ffffff;
            }
            QPushButton#summaryTabButton:hover:enabled {
                color: #ffffff;
                border-color: #f97306;
            }
            QPushButton#summaryTabButton:disabled {
                color: #555555;
                background: #0f0f0f;
                border-color: #202020;
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
            """.replace("__COMBO_ARROW_PATH__", combo_arrow_path))

    def _choose_folder(self) -> None:
        source_key = self.mod_list.current_source_key
        selected_path = self._choose_scan_path(source_key)
        if not selected_path:
            return
        self.settings.set_scan_source_folder(source_key, selected_path)
        self.scanned_sources_this_session.discard(source_key)
        clear_scan_cache(source_key)
        self._start_scan_folder(Path(selected_path), source_key)

    def _rescan_current_folder(self) -> None:
        source_key = self.mod_list.current_source_key
        folder = self.settings.scan_source_folder(source_key)
        if not folder or not self._is_valid_scan_path(source_key, Path(folder)):
            self.statusBar().showMessage(
                f"Select a {self._scan_source_label(source_key)} source first.",
                4000,
            )
            return
        self._start_scan_folder(Path(folder), source_key)

    def _update_cmds_current_folder(self) -> None:
        source_key = self.mod_list.current_source_key
        folder = self.settings.scan_source_folder(source_key)
        if not folder or not self._is_valid_scan_path(source_key, Path(folder)):
            self.statusBar().showMessage(
                f"Select a {self._scan_source_label(source_key)} source first.",
                4000,
            )
            return
        if self.scan_thread is not None:
            self.statusBar().showMessage("Already scanning. Please wait.", 3000)
            return
        if self.cmd_update_thread is not None:
            self.statusBar().showMessage("Already updating CMDs. Please wait.", 3000)
            return

        path = Path(folder)
        response = QMessageBox.question(
            self,
            "Update CMDs",
            (
                "Update supported CMD files in the selected source?\n\n"
                f"{path}\n\n"
                "This replaces the old game CMD byte pattern with the current one."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return
        self._start_cmd_update(path, source_key)

    def _scan_last_mods_folder(self) -> None:
        last_folder = self.settings.scan_source_folder(self.scan_source_key)
        if last_folder and self._is_valid_scan_path(self.scan_source_key, Path(last_folder)):
            self._scan_folder(Path(last_folder), self.scan_source_key)

    def _scan_current_source_on_startup(self) -> None:
        self._load_source_from_cache_then_scan_once(self.scan_source_key)

    def _start_scan_folder(self, folder: Path, source_key: str) -> None:
        if self.scan_thread is not None:
            self.statusBar().showMessage("Already scanning. Please wait.", 3000)
            return
        self.statusBar().showMessage(f"Loading {self._scan_source_label(source_key)}...")
        QApplication.processEvents()
        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(folder, source_key)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.succeeded.connect(self._scan_finished)
        self.scan_worker.failed.connect(self._scan_failed)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self._clear_scan_worker)
        self.scan_thread.start()

    def _start_cmd_update(self, folder: Path, source_key: str) -> None:
        self.statusBar().showMessage(f"Updating CMDs in {self._scan_source_label(source_key)}...")
        QApplication.processEvents()
        self.cmd_update_thread = QThread(self)
        self.cmd_update_worker = CmdUpdateWorker(folder, source_key)
        self.cmd_update_worker.moveToThread(self.cmd_update_thread)
        self.cmd_update_thread.started.connect(self.cmd_update_worker.run)
        self.cmd_update_worker.succeeded.connect(self._cmd_update_finished)
        self.cmd_update_worker.failed.connect(self._cmd_update_failed)
        self.cmd_update_worker.finished.connect(self.cmd_update_thread.quit)
        self.cmd_update_worker.finished.connect(self.cmd_update_worker.deleteLater)
        self.cmd_update_thread.finished.connect(self.cmd_update_thread.deleteLater)
        self.cmd_update_thread.finished.connect(self._clear_cmd_update_worker)
        self.cmd_update_thread.start()

    def _scan_folder(self, folder: Path, source_key: str = "mods") -> None:
        self.statusBar().showMessage(f"Loading {self._scan_source_label(source_key)}...")
        try:
            report = self._scan_source_with_report(folder, source_key)
        except Exception as error:
            self._handle_scan_failure(source_key, str(error))
            return
        self._apply_scan_report(source_key, folder, report)

    def _scan_source_with_report(self, folder: Path, source_key: str) -> ScanReport:
        if source_key == "rechunk":
            return scan_rechunk_source_with_report(folder)
        return scan_mods_folder_with_report(folder)

    def _scan_finished(self, source_key: str, folder: Path, report: ScanReport) -> None:
        self._apply_scan_report(source_key, folder, report)

    def _scan_failed(self, source_key: str, error: str) -> None:
        self._handle_scan_failure(source_key, error)

    def _apply_scan_report(self, source_key: str, folder: Path, report: ScanReport) -> None:
        self.mods_by_source[source_key] = report.mods
        self.scanned_sources_this_session.add(source_key)
        save_scan_cache(source_key, folder, report.mods)
        if source_key != self.scan_source_key:
            return
        self.mods = report.mods
        self.mod_list.set_mods(self.mods)
        self.mod_list.show_preview(None)
        self.selected_mod = None
        self.selected_character = None
        self.selected_costume = None
        self.selected_source_slot = None
        if self._should_auto_select_source_mod(source_key):
            self.mod_list.list_widget.setCurrentRow(0)
            self._select_mod(0)
        else:
            self._refresh_columns()
        if report.issues:
            self.statusBar().showMessage(
                (
                    f"Found {len(self.mods)} mods. {len(report.issues)} scan issues "
                    f"written to scan.log. First: {report.issues[0].display_path}"
                ),
                8000,
            )
        else:
            self.statusBar().showMessage(
                f"Found {len(self.mods)} mods with supported data.", 5000
            )

    def _handle_scan_failure(self, source_key: str, error: str) -> None:
        self.settings.set_scan_source_folder(source_key, "")
        self.mods_by_source[source_key] = []
        self.scanned_sources_this_session.discard(source_key)
        clear_scan_cache(source_key)
        if source_key == self.scan_source_key:
            self.mods = []
            self.mod_list.set_mods(self.mods)
            self.mod_list.show_preview(None)
            self.selected_mod = None
            self.selected_character = None
            self.selected_costume = None
            self.selected_source_slot = None
            self._refresh_columns()
        self.statusBar().showMessage(
            f"Scan failed. Cleared remembered {self._scan_source_label(source_key)} folder: {error}",
            8000,
        )

    def _clear_scan_worker(self) -> None:
        self.scan_thread = None
        self.scan_worker = None

    def _cmd_update_finished(
        self,
        source_key: str,
        folder: Path,
        report: CmdUpdateReport,
    ) -> None:
        if report.issues:
            self.statusBar().showMessage(
                (
                    f"Updated {report.files_updated} CMD files. "
                    f"{len(report.issues)} issues. First: {report.issues[0].display_path}"
                ),
                8000,
            )
        else:
            self.statusBar().showMessage(
                (
                    f"Updated {report.files_updated} CMD files "
                    f"out of {report.color_files_checked} supported CMD files."
                ),
                6000,
            )

    def _cmd_update_failed(self, source_key: str, error: str) -> None:
        self.statusBar().showMessage(
            f"CMD update failed for {self._scan_source_label(source_key)}: {error}",
            8000,
        )

    def _clear_cmd_update_worker(self) -> None:
        self.cmd_update_thread = None
        self.cmd_update_worker = None

    def _select_scan_source(self, source_key: str) -> None:
        self.scan_source_key = source_key
        self.settings.set_selected_scan_source(source_key)
        self._load_source_from_cache_then_scan_once(source_key)

    def _load_source_from_cache_then_scan_once(self, source_key: str) -> None:
        folder_text = self.settings.scan_source_folder(source_key)
        folder = Path(folder_text) if folder_text else None
        if (
            folder
            and self._is_valid_scan_path(source_key, folder)
            and not self.mods_by_source.get(source_key)
        ):
            cached_mods = load_scan_cache(source_key, folder)
            if cached_mods:
                self.mods_by_source[source_key] = cached_mods

        self.mods = self.mods_by_source.get(source_key, [])
        self.mod_list.set_mods(self.mods)
        self.mod_list.show_preview(None)
        self.selected_mod = None
        self.selected_character = None
        self.selected_costume = None
        self.selected_source_slot = None
        if self._should_auto_select_source_mod(source_key):
            self.mod_list.list_widget.setCurrentRow(0)
            self._select_mod(0)
        else:
            self._refresh_columns()

        if (
            folder
            and self._is_valid_scan_path(source_key, folder)
            and source_key not in self.scanned_sources_this_session
        ):
            if self.mods:
                self.statusBar().showMessage(
                    (
                        f"Showing cached {self._scan_source_label(source_key)} data. "
                        "Refreshing..."
                    ),
                    4000,
                )
            self._start_scan_folder(folder, source_key)
        elif self.mods:
            self.statusBar().showMessage(
                f"Showing {len(self.mods)} mods from {self._scan_source_label(source_key)}.",
                3000,
            )
        elif folder and self._is_valid_scan_path(source_key, folder):
            self.statusBar().showMessage(
                f"{self._scan_source_label(source_key)} folder selected. Press Scan to load.",
                4000,
            )

    def _choose_scan_path(self, source_key: str) -> str:
        if source_key == "rechunk":
            return self._choose_rechunk_path()
        return QFileDialog.getExistingDirectory(
            self,
            self._scan_folder_dialog_title(source_key),
            self.settings.scan_source_folder(source_key),
        )

    def _choose_rechunk_path(self) -> str:
        dialog = QDialog(self)
        dialog.setWindowTitle(self._scan_folder_dialog_title("rechunk"))
        dialog.resize(560, 120)

        path_input = QLineEdit(self.settings.scan_source_folder("rechunk"))
        path_input.setPlaceholderText("Select a re_chunk folder or Source CMD archive")

        def browse_folder() -> None:
            folder = QFileDialog.getExistingDirectory(
                dialog,
                "Select re_chunk Folder",
                path_input.text(),
            )
            if folder:
                path_input.setText(folder)

        def browse_zip() -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                dialog,
                "Select re_chunk Archive",
                path_input.text(),
                "Archive Files (*.zip *.7z *.rar)",
            )
            if path:
                path_input.setText(path)

        folder_button = QPushButton("Folder")
        folder_button.clicked.connect(browse_folder)
        zip_button = QPushButton("Archive")
        zip_button.clicked.connect(browse_zip)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        path_layout = QHBoxLayout()
        path_layout.addWidget(path_input, 1)
        path_layout.addWidget(folder_button)
        path_layout.addWidget(zip_button)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("re_chunk folder / Source CMD archive:"))
        layout.addLayout(path_layout)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.Accepted:
            return ""

        selected_path = path_input.text().strip()
        if not selected_path:
            return ""
        path = Path(selected_path)
        if self._is_valid_scan_path("rechunk", path):
            return str(path)
        QMessageBox.warning(
            self,
            APP_NAME,
            "Select a re_chunk folder or Source CMD archive.",
        )
        return ""

    def _is_valid_scan_path(self, source_key: str, path: Path) -> bool:
        if path.is_dir():
            return True
        return source_key == "rechunk" and is_supported_archive(path)

    def _should_auto_select_source_mod(self, source_key: str) -> bool:
        return source_key in {"natives", "rechunk"} and bool(self.mods)

    def _scan_source_label(self, source_key: str) -> str:
        return dict(ModList.SOURCES).get(source_key, "Mod Folder")

    def _scan_folder_dialog_title(self, source_key: str) -> str:
        return f"Select {self._scan_source_label(source_key)}"

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
        source = self.selected_mod.source_for(
            self.selected_character,
            self.selected_costume,
            source_type,
            self.selected_source_slot,
        )
        if not source:
            return

        key = (source.character, source.costume, target_type, target_slot)
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
            type=target_type,
            target_slot=target_slot,
            source_zip=source.zip_path,
            source_kind=source.source_kind,
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

    def _open_batch_assign_dialog(self) -> None:
        if not self.selected_mod:
            self.statusBar().showMessage("Select a mod before batch assigning.", 3000)
            return

        dialog = BatchAssignDialog(
            self.selected_mod,
            self.slot_column.current_type,
            self.selected_source_slot,
            self.collection_column.current_type,
            self.settings.use_character_names(),
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        self._batch_assign_sources(
            dialog.selected_characters,
            dialog.selected_costumes,
            dialog.source_type,
            dialog.source_slot,
            dialog.target_type,
            dialog.target_slot,
        )

    def _batch_assign_sources(
        self,
        characters: set[str],
        costumes: set[str],
        source_type: str,
        source_slot: str,
        target_type: str,
        target_slot: str,
    ) -> None:
        if not self.selected_mod:
            return
        if not characters or not costumes:
            self.statusBar().showMessage(
                "Choose at least one character and costume for batch assignment.",
                4000,
            )
            return

        assignments_to_apply: list[CollectionAssignment] = []
        for source in sorted(
            self.selected_mod.source_files,
            key=lambda item: (item.character, item.costume, item.type, item.source_slot),
        ):
            if (
                source.character not in characters
                or source.costume not in costumes
                or source.type != source_type
                or source.source_slot != source_slot
            ):
                continue
            assignments_to_apply.append(
                CollectionAssignment(
                    character=source.character,
                    costume=source.costume,
                    type=target_type,
                    target_slot=target_slot,
                    source_zip=source.zip_path,
                    source_kind=source.source_kind,
                    source_internal_file_path=source.internal_file_path,
                    source_slot=source.source_slot,
                    source_mod_name=source.mod_name,
                )
            )

        if not assignments_to_apply:
            self.statusBar().showMessage(
                "No matching source files found for batch assignment.",
                4000,
            )
            return

        replacements = [
            assignment
            for assignment in assignments_to_apply
            if self.assignments.get(assignment.key)
            and self.assignments[assignment.key] != assignment
        ]
        if replacements:
            answer = QMessageBox.question(
                self,
                "Replace Target Slots",
                (
                    f"Replace {len(replacements)} occupied target slot"
                    f"{'s' if len(replacements) != 1 else ''}?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                self.statusBar().showMessage("Batch assignment was not changed.", 3000)
                return

        for assignment in assignments_to_apply:
            self.assignments[assignment.key] = assignment

        self._refresh_columns()
        self.statusBar().showMessage(
            (
                f"Batch assigned {len(assignments_to_apply)} color files from "
                f"{self._type_slot_label(source_type, source_slot)} to "
                f"{self._type_slot_label(target_type, target_slot)}."
            ),
            5000,
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
        self.batch_assign_button.setEnabled(self.selected_mod is not None)

    def _all_known_characters(self) -> list[str]:
        characters = {
            source.character for mod in self.mods for source in mod.source_files
        }
        characters.update(CHARACTER_NAMES)
        return self._sort_characters(characters)

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
        self.collection_info_fields = self._default_collection_info_fields(
            self.collection_name
        )
        self.collection_preview_path = None
        self.assignments.clear()
        self.selected_character = None
        self.selected_costume = None
        self.selected_source_slot = None
        self._refresh_columns()
        self.statusBar().showMessage("Started a new collection project.", 3000)

    def _open_project(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Collection Archive",
            self.settings.last_project_folder(),
            "Archives (*.zip *.7z *.rar)",
        )
        if not path:
            return
        project_path = Path(path)
        collection_name, mods_folder, assignments = load_exported_collection_zip(
            project_path
        )
        self.collection_name = collection_name
        self.collection_info_fields = self._default_collection_info_fields(
            self.collection_name
        )
        self.collection_preview_path = None
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
        default_path = Path(self.settings.last_project_folder()) / self._safe_filename(
            self.collection_name,
            ".zip",
        )
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Collection",
            str(default_path),
            "ZIP Archive (*.zip);;7Z Archive (*.7z);;RAR Archive (*.rar)",
        )
        if not path:
            return
        output_path = self._archive_save_path(Path(path), selected_filter)
        if not self._ensure_writable_archive(output_path):
            return
        if self._export_to_path(output_path):
            self.current_output_path = output_path

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

    def _export_to_path(self, output_path: Path) -> bool:
        if not self.assignments:
            QMessageBox.information(
                self,
                APP_NAME,
                "Assign at least one target slot before saving.",
            )
            return False

        if not self._ensure_writable_archive(output_path):
            return False
        self.settings.set_last_project_folder(output_path.parent)
        try:
            export_collection_archive(
                output_path,
                self.collection_name,
                sorted(self.assignments.values(), key=lambda item: item.key),
                preserve_existing_metadata=output_path.exists(),
                modinfo_fields=self.collection_info_fields,
                preview_image_path=self.collection_preview_path,
            )
        except ArchiveWriteError as error:
            QMessageBox.warning(
                self,
                APP_NAME,
                f"Could not save {output_path.name}:\n{error}",
            )
            self.statusBar().showMessage("Save failed.", 5000)
            return False
        self.statusBar().showMessage(f"Saved {output_path.name}.", 5000)
        return True

    def _archive_save_path(self, path: Path, selected_filter: str) -> Path:
        suffix = path.suffix.lower()
        if suffix in {".zip", ".7z", ".rar"}:
            return path
        if "*.7z" in selected_filter:
            return path.with_suffix(".7z")
        if "*.rar" in selected_filter:
            return path.with_suffix(".rar")
        return path.with_suffix(".zip")

    def _ensure_writable_archive(self, output_path: Path) -> bool:
        if can_write_collection_archive(output_path):
            return True
        if output_path.suffix.lower() == ".rar":
            message = (
                "Saving RAR archives requires WinRAR/RAR command-line tools.\n\n"
                "Use Save As and choose ZIP or 7Z, or install WinRAR/RAR to save RAR."
            )
        else:
            message = f"Unsupported archive format: {output_path.suffix}"
        QMessageBox.warning(self, APP_NAME, message)
        self.statusBar().showMessage("Save format is not available.", 5000)
        return False

    def _edit_collection_info(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Collection Info")
        dialog.resize(620, 460)

        name_input = QLineEdit(self.collection_name)
        preview_input = QLineEdit(
            str(self.collection_preview_path) if self.collection_preview_path else ""
        )
        preview_input.setPlaceholderText("Leave empty to use the default image")
        fields_input = QPlainTextEdit(
            self._format_collection_info_fields(self.collection_info_fields)
        )
        fields_input.setPlaceholderText("name=Custom Collection\nauthor=Marshial\nversion=1.0")

        def browse_preview() -> None:
            path, _selected_filter = QFileDialog.getOpenFileName(
                dialog,
                "Select Preview Image",
                preview_input.text() or self.settings.last_project_folder(),
                "Images (*.png *.jpg *.jpeg *.webp)",
            )
            if path:
                preview_input.setText(path)

        preview_button = QPushButton("Image")
        preview_button.clicked.connect(browse_preview)

        preview_layout = QHBoxLayout()
        preview_layout.addWidget(preview_input, 1)
        preview_layout.addWidget(preview_button)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Zip / mod name:"))
        layout.addWidget(name_input)
        layout.addWidget(QLabel("Preview image:"))
        layout.addLayout(preview_layout)
        layout.addWidget(QLabel("modinfo.ini fields:"))
        layout.addWidget(fields_input, 1)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.Accepted:
            return

        name = name_input.text().strip()
        if not name:
            QMessageBox.warning(self, APP_NAME, "Enter a zip / mod name.")
            return

        fields = self._parse_collection_info_fields(fields_input.toPlainText())
        fields["name"] = name
        preview_path = preview_input.text().strip()
        if preview_path and not Path(preview_path).is_file():
            QMessageBox.warning(self, APP_NAME, "Select an existing preview image.")
            return

        self.collection_name = name
        self.collection_info_fields = fields
        self.collection_preview_path = Path(preview_path) if preview_path else None
        self.statusBar().showMessage("Updated collection info.", 3000)

    def _default_collection_info_fields(self, collection_name: str) -> dict[str, str]:
        return {
            "name": collection_name,
            "version": "1.0",
            "description": "Generated by SF6 Color Collection Builder",
            "screenshot": "MyCustomCollection.png",
            "author": "Marshial",
        }

    def _format_collection_info_fields(self, fields: dict[str, str]) -> str:
        return "\n".join(f"{key}={value}" for key, value in fields.items())

    def _parse_collection_info_fields(self, text: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, separator, value = stripped.partition("=")
            if separator and key.strip():
                fields[key.strip().lower()] = value.strip()
        return fields

    def _show_current_collection(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Current Collection")
        dialog.resize(1100, 620)

        summary = self._build_collection_summary_tabs()

        layout = QVBoxLayout(dialog)
        layout.addWidget(summary)
        dialog.exec()

    def _build_collection_summary_tabs(self) -> QWidget:
        view = QWidget()
        stack = QStackedWidget()
        tab_layout = QGridLayout()
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(4)

        first_assigned_index: int | None = None
        tab_buttons: list[QPushButton] = []
        columns = 8
        for index, character in enumerate(self._sort_characters(CHARACTER_NAMES)):
            table = self._collection_character_table(character)
            has_assignments = self._character_has_assignments(character)
            stack.addWidget(table)
            button = QPushButton(character_label(character))
            button.setObjectName("summaryTabButton")
            button.setCheckable(True)
            button.setEnabled(has_assignments)
            button.clicked.connect(
                lambda _checked=False, current_index=index: self._select_summary_tab(
                    stack,
                    tab_buttons,
                    current_index,
                )
            )
            tab_layout.addWidget(button, index // columns, index % columns)
            tab_buttons.append(button)
            if has_assignments and first_assigned_index is None:
                first_assigned_index = index

        if first_assigned_index is not None:
            self._select_summary_tab(stack, tab_buttons, first_assigned_index)

        layout = QVBoxLayout(view)
        layout.addWidget(stack, 1)
        layout.addLayout(tab_layout)

        view.character_stack = stack  # type: ignore[attr-defined]
        view.character_tab_buttons = tab_buttons  # type: ignore[attr-defined]
        return view

    def _select_summary_tab(
        self,
        stack: QStackedWidget,
        tab_buttons: list[QPushButton],
        index: int,
    ) -> None:
        stack.setCurrentIndex(index)
        for button_index, button in enumerate(tab_buttons):
            button.setChecked(button_index == index)

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
                                self._assignment_summary_label(assignment)
                                if assignment
                                else "empty",
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
                    QTableWidgetItem(
                        self._assignment_summary_label(assignment)
                        if assignment
                        else ""
                    ),
                )

        table.resizeColumnsToContents()
        table.setColumnWidth(0, 72)
        for column in range(1, table.columnCount()):
            table.setColumnWidth(column, max(table.columnWidth(column), 180))
        table.resizeRowsToContents()
        return table

    def _assignment_summary_label(self, assignment: CollectionAssignment) -> str:
        return f"{assignment.source_mod_name} (Slot {int(assignment.source_slot)})"

    def _character_has_assignments(self, character: str) -> bool:
        return any(
            assignment.character == character
            for assignment in self.assignments.values()
        )

    def _summary_slot_label(self, color_type: str, slot: str) -> str:
        if color_type == "normal":
            return f"{int(slot):02d}"
        return f"{color_type.upper()}{int(slot):02d}"

    def _type_slot_label(self, color_type: str, slot: str) -> str:
        if color_type == "normal":
            return f"Normal {int(slot):02d}"
        return f"{color_type.upper()}{int(slot):02d}"

    def _safe_filename(self, name: str, suffix: str) -> str:
        safe_name = "".join(
            character if character not in '<>:"/\\|?*' else "_"
            for character in name.strip()
        ).strip()
        return f"{safe_name or 'Custom Collection'}{suffix}"

    def _show_version_changes_once(self) -> None:
        if self.settings.last_shown_changes_version() == APP_VERSION:
            return
        QMessageBox.information(
            self,
            f"What's New in {APP_VERSION}",
            self._release_notes_message(),
        )
        self.settings.set_last_shown_changes_version(APP_VERSION)

    def _release_notes_message(self) -> str:
        return self._latest_update_log_entry() or CHANGE_LOG_MESSAGE

    def _show_update_log(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Update Log")
        dialog.resize(760, 620)

        log_view = QPlainTextEdit(self._update_log_message())
        log_view.setReadOnly(True)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(dialog.reject)

        layout = QVBoxLayout(dialog)
        layout.addWidget(log_view, 1)
        layout.addWidget(button_box)
        dialog.exec()

    def _update_log_message(self) -> str:
        try:
            message = UPDATE_LOG_PATH.read_text(encoding="utf-8-sig").strip()
        except OSError:
            message = ""
        return message or CHANGE_LOG_MESSAGE

    def _latest_update_log_entry(self) -> str:
        message = self._update_log_message()
        marker = "\nSF6 Color Collection Builder v"
        if marker not in message:
            return message
        return message.split(marker, 1)[0].strip()

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
        if can_auto_update(update):
            answer = QMessageBox.question(
                self,
                "Update Available",
                (
                    f"{message}\n\n"
                    "Download and install the update now?\n\n"
                    "The app will close during the update and reopen automatically."
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self._download_and_install_update(update)
            return

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

    def _download_and_install_update(self, update: UpdateInfo) -> None:
        self.statusBar().showMessage("Downloading update...")
        QApplication.processEvents()
        try:
            prepared_update = prepare_update(update)
            launch_prepared_update(prepared_update)
        except Exception as error:
            release_url = update.release_url or GITHUB_RELEASES_PAGE_URL
            answer = QMessageBox.warning(
                self,
                "Update Failed",
                (
                    f"Automatic update failed:\n{error}\n\n"
                    "Open the GitHub release page instead?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes and release_url:
                webbrowser.open(release_url)
            self.statusBar().showMessage("Automatic update failed.", 5000)
            return

        self.statusBar().showMessage("Applying update. The app will restart...")
        self.close()
        QApplication.quit()

    def _clear_update_worker(self) -> None:
        self.update_thread = None
        self.update_worker = None


class ScanWorker(QObject):
    succeeded = Signal(str, Path, object)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, folder: Path, source_key: str) -> None:
        super().__init__()
        self.folder = folder
        self.source_key = source_key

    def run(self) -> None:
        try:
            if self.source_key == "rechunk":
                report = scan_rechunk_source_with_report(self.folder)
            else:
                report = scan_mods_folder_with_report(self.folder)
            self.succeeded.emit(self.source_key, self.folder, report)
        except Exception as error:
            self.failed.emit(self.source_key, str(error))
        finally:
            self.finished.emit()


class CmdUpdateWorker(QObject):
    succeeded = Signal(str, Path, object)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, folder: Path, source_key: str) -> None:
        super().__init__()
        self.folder = folder
        self.source_key = source_key

    def run(self) -> None:
        try:
            report = update_cmds_in_source(self.folder)
            self.succeeded.emit(self.source_key, self.folder, report)
        except Exception as error:
            self.failed.emit(self.source_key, str(error))
        finally:
            self.finished.emit()


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
