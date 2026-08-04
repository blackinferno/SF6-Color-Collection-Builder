from __future__ import annotations

import zipfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QMessageBox

from app.characters import CHARACTER_NAMES, character_label
from app.cmd_updater import CmdUpdateIssue, CmdUpdateReport
from app.models import ScannedMod, SourceColorFile
from app.settings import APP_VERSION
from app.scanner import scan_zip
from app.scanner import ScanIssue, ScanReport
from app.ui.batch_assign_dialog import BatchAssignDialog
from app.ui.main_window import MainWindow
from app.ui.mod_list import ModList


COLOR_ROOT = "natives/stm/product/model/esf"


def test_assign_target_slot(qt_app: QApplication, tmp_path: Path) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")

    assert ("esf001", "001", "normal", "004") in window.assignments


def test_assign_source_to_different_target_type(qt_app: QApplication, tmp_path: Path) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("dx", "004")

    assert ("esf001", "001", "dx", "004") in window.assignments
    assert ("esf001", "001", "normal", "004") not in window.assignments


def test_batch_assigns_selected_source_slot_across_characters(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Batch.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Batch Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"ryu")
        archive.writestr(f"{COLOR_ROOT}/esf002/001/esf002_001_cmd_002.user.2", b"luke")
        archive.writestr(f"{COLOR_ROOT}/esf003/001/esf003_001_cmd_004.user.2", b"jamie")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]

    window._batch_assign_sources(
        {"esf001", "esf002", "esf003"},
        {"001"},
        "normal",
        "002",
        "normal",
        "003",
    )

    assert ("esf001", "001", "normal", "003") in window.assignments
    assert ("esf002", "001", "normal", "003") in window.assignments
    assert ("esf003", "001", "normal", "003") not in window.assignments


def test_batch_assign_can_change_target_type(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Batch.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Batch Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]

    window._batch_assign_sources({"esf001"}, {"001"}, "normal", "002", "dx", "003")

    assignment = window.assignments[("esf001", "001", "dx", "003")]
    assert assignment.source_slot == "002"
    assert assignment.type == "dx"


def test_batch_assign_respects_selected_costumes(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Batch.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Batch Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"c1")
        archive.writestr(f"{COLOR_ROOT}/esf001/002/esf001_002_cmd_002.user.2", b"c2")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]

    window._batch_assign_sources({"esf001"}, {"002"}, "normal", "002", "normal", "003")

    assert ("esf001", "001", "normal", "003") not in window.assignments
    assert ("esf001", "002", "normal", "003") in window.assignments


def test_batch_assign_cancel_replacement_leaves_assignments_unchanged(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_zip = tmp_path / "First.zip"
    second_zip = tmp_path / "Second.zip"
    with zipfile.ZipFile(first_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=First Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"first")
    with zipfile.ZipFile(second_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Second Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"second")

    window = MainWindow()
    window.mods = [scan_zip(first_zip), scan_zip(second_zip)]
    window.selected_mod = window.mods[0]
    window._batch_assign_sources({"esf001"}, {"001"}, "normal", "002", "normal", "003")
    window.selected_mod = window.mods[1]

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.No)
    window._batch_assign_sources({"esf001"}, {"001"}, "normal", "002", "normal", "003")

    assert window.assignments[("esf001", "001", "normal", "003")].source_mod_name == "First Mod"


def test_batch_assign_confirm_replacement_updates_assignment(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_zip = tmp_path / "First.zip"
    second_zip = tmp_path / "Second.zip"
    with zipfile.ZipFile(first_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=First Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"first")
    with zipfile.ZipFile(second_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Second Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"second")

    window = MainWindow()
    window.mods = [scan_zip(first_zip), scan_zip(second_zip)]
    window.selected_mod = window.mods[0]
    window._batch_assign_sources({"esf001"}, {"001"}, "normal", "002", "normal", "003")
    window.selected_mod = window.mods[1]

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    window._batch_assign_sources({"esf001"}, {"001"}, "normal", "002", "normal", "003")

    assert window.assignments[("esf001", "001", "normal", "003")].source_mod_name == "Second Mod"


def test_batch_dialog_defaults_characters_unchecked(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Batch.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Batch Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"ryu")
        archive.writestr(f"{COLOR_ROOT}/esf002/001/esf002_001_cmd_002.user.2", b"luke")

    dialog = BatchAssignDialog(scan_zip(source_zip), "normal", "002", "normal")

    assert dialog.selected_characters == set()
    assert dialog.selected_costumes == set()
    assert dialog.costume_list.count() == 1


def test_batch_dialog_text_click_and_select_all_toggle_characters(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Batch.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Batch Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"ryu")
        archive.writestr(f"{COLOR_ROOT}/esf002/001/esf002_001_cmd_002.user.2", b"luke")

    dialog = BatchAssignDialog(scan_zip(source_zip), "normal", "002", "normal")
    first_item = dialog.character_table.item(0, 0)

    dialog._toggle_table_check(first_item)

    assert first_item.data(256) in dialog.selected_characters
    assert dialog.selected_costumes == set()

    costume_item = dialog.costume_list.item(0)
    dialog._toggle_list_check(costume_item)
    assert dialog.selected_costumes == {"001"}

    dialog._set_all_characters(Qt.Checked)
    assert dialog.selected_characters == {"esf001", "esf002"}

    dialog._set_all_characters(Qt.Unchecked)
    assert dialog.selected_characters == set()
    assert dialog.selected_costumes == {"001"}


def test_batch_dialog_source_slots_filter_by_selected_character(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Batch.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Batch Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"ryu")
        archive.writestr(f"{COLOR_ROOT}/esf002/001/esf002_001_cmd_004.user.2", b"luke")

    dialog = BatchAssignDialog(scan_zip(source_zip), "normal", "002", "normal")
    normal_slot_02 = dialog.source_table.item(1, 0)
    normal_slot_04 = dialog.source_table.item(3, 0)

    assert normal_slot_02.flags() & Qt.ItemIsEnabled
    assert normal_slot_04.flags() & Qt.ItemIsEnabled

    luke_item = next(
        dialog.character_table.item(row, column)
        for row in range(dialog.character_table.rowCount())
        for column in range(dialog.character_table.columnCount())
        if dialog.character_table.item(row, column)
        and dialog.character_table.item(row, column).data(256) == "esf002"
    )
    dialog._toggle_table_check(luke_item)

    normal_slot_02 = dialog.source_table.item(1, 0)
    normal_slot_04 = dialog.source_table.item(3, 0)
    assert not (normal_slot_02.flags() & Qt.ItemIsEnabled)
    assert normal_slot_04.flags() & Qt.ItemIsEnabled


def test_clear_assignment(qt_app: QApplication, tmp_path: Path) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")
    window._clear_assignment("normal", "004")

    assert ("esf001", "001", "normal", "004") not in window.assignments


def test_assigned_collection_row_uses_widget_without_duplicate_item_text(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")

    item = window.collection_column.slot_lists["normal"].item(3)
    row_widget = window.collection_column.slot_lists["normal"].itemWidget(item)

    assert item.text() == ""
    assert "Source Mod (Slot 2)" in row_widget.findChildren(
        type(window.collection_column.title)
    )[0].text()


def test_switching_mod_keeps_collection_context(qt_app: QApplication, tmp_path: Path) -> None:
    first_zip = tmp_path / "First.zip"
    second_zip = tmp_path / "Second.zip"
    for zip_path, name in ((first_zip, "First Mod"), (second_zip, "Second Mod")):
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("modinfo.ini", f"name={name}\n")
            archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(first_zip), scan_zip(second_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")

    window._select_mod(1)

    assert window.selected_character == "esf001"
    assert window.selected_costume == "001"
    row_widget = window.collection_column.slot_lists["normal"].itemWidget(
        window.collection_column.slot_lists["normal"].item(3)
    )
    assert "First Mod" in row_widget.findChildren(type(window.collection_column.title))[0].text()


def test_selecting_single_path_mod_auto_selects_character_costume_and_slot(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "SingleCharacter.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Single Character\n")
        archive.writestr(f"{COLOR_ROOT}/esf002/003/esf002_003_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_character = "esf001"
    window.selected_costume = "001"

    window._select_mod(0)

    assert window.selected_character == "esf002"
    assert window.selected_costume == "003"
    assert window.selected_source_slot == "002"
    assert window.slot_column.current_type == "normal"


def test_scan_folder_failure_clears_remembered_mods_folder(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    window.settings.set_scan_source_folder("natives", tmp_path)

    def fail_scan(_folder):
        raise RuntimeError("bad zip")

    monkeypatch.setattr("app.ui.main_window.scan_mods_folder_with_report", fail_scan)

    window._scan_folder(tmp_path, "natives")

    assert window.settings.scan_source_folder("natives") == ""
    assert window.mods == []


def test_scan_folder_reports_scan_issues_in_status(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    issue = ScanIssue(
        package_path=tmp_path / "Broken.zip",
        internal_path="modinfo.ini",
        message="Malformed modinfo.ini",
    )

    monkeypatch.setattr(
        "app.ui.main_window.scan_mods_folder_with_report",
        lambda _folder: ScanReport([], [issue]),
    )

    window._scan_folder(tmp_path, "mods")

    assert "1 scan issues written to scan.log" in window.statusBar().currentMessage()
    assert "Broken.zip / modinfo.ini" in window.statusBar().currentMessage()


def test_cmd_update_report_message_includes_log_and_counts(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    log_path = tmp_path / "cmd_update.log"
    monkeypatch.setattr("app.ui.main_window.CMD_UPDATE_LOG_PATH", log_path)
    report = CmdUpdateReport(
        packages_checked=2,
        color_files_checked=3,
        files_updated=1,
        issues=[
            CmdUpdateIssue(
                tmp_path / "Broken.rar",
                None,
                "Could not write updated archive.",
                "RAR command failed.",
            )
        ],
    )

    message = window._cmd_update_report_message(report)

    assert "Packages checked: 2" in message
    assert "CMD files checked: 3" in message
    assert "CMD files updated: 1" in message
    assert "Issues: 1" in message
    assert str(log_path) in message
    assert "Broken.rar" in message
    assert "RAR command failed." in message


def test_cmd_update_finished_shows_popup(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    calls: list[tuple[str, str]] = []

    def record_message(_parent, title, message):
        calls.append((title, message))
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "information", record_message)
    report = CmdUpdateReport(
        packages_checked=1,
        color_files_checked=2,
        files_updated=2,
        issues=[],
    )

    window._cmd_update_finished("mods", tmp_path, report)

    assert calls == [("CMD Update Complete", window._cmd_update_report_message(report))]


def test_cmd_update_prompts_for_rar_tool_when_needed(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    rar_path = tmp_path / "Mod.rar"
    rar_path.write_bytes(b"rar")
    rar_tool = tmp_path / "WinRAR.exe"
    rar_tool.write_bytes(b"")

    monkeypatch.setattr("app.ui.main_window.can_write_rar", lambda: False)
    monkeypatch.setattr(window, "_ask_for_rar_tool_action", lambda: "select")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(rar_tool), ""),
    )

    assert window._ensure_rar_writer_for_cmd_update(tmp_path)
    assert window.settings.rar_tool_path() == str(rar_tool)


def test_cmd_update_can_open_winrar_download_when_rar_tool_is_missing(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    rar_path = tmp_path / "Mod.rar"
    rar_path.write_bytes(b"rar")
    opened_urls: list[str] = []

    monkeypatch.setattr("app.ui.main_window.can_write_rar", lambda: False)
    monkeypatch.setattr(window, "_ask_for_rar_tool_action", lambda: "download")
    monkeypatch.setattr(
        "app.ui.main_window.webbrowser.open",
        lambda url: opened_urls.append(url),
    )

    assert not window._ensure_rar_writer_for_cmd_update(tmp_path)
    assert opened_urls == ["https://www.win-rar.com/download.html"]


def test_cmd_update_can_skip_rar_when_rar_tool_is_missing(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    rar_path = tmp_path / "Mod.rar"
    rar_path.write_bytes(b"rar")

    monkeypatch.setattr("app.ui.main_window.can_write_rar", lambda: False)
    monkeypatch.setattr(window, "_ask_for_rar_tool_action", lambda: "skip")

    assert window._ensure_rar_writer_for_cmd_update(tmp_path)


def test_cmd_update_does_not_prompt_for_rar_tool_without_rars(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    (tmp_path / "esf001_001_cmd_001.user.2").write_bytes(b"cmd")
    calls: list[str] = []

    monkeypatch.setattr("app.ui.main_window.can_write_rar", lambda: False)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: calls.append("question") or QMessageBox.No,
    )

    assert window._ensure_rar_writer_for_cmd_update(tmp_path)
    assert calls == []


def test_natives_and_rechunk_scan_results_auto_select_first_mod(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    for source_key in ("natives", "rechunk"):
        window = MainWindow()
        first_mod = ScannedMod(zip_path=tmp_path / f"{source_key}.zip", mod_name="First")
        second_mod = ScannedMod(zip_path=tmp_path / f"{source_key}2.zip", mod_name="Second")
        window.scan_source_key = source_key

        window._apply_scan_report(source_key, tmp_path, ScanReport([first_mod, second_mod], []))

        assert window.selected_mod == first_mod
        assert window.mod_list.list_widget.currentRow() == 0


def test_mod_folder_scan_results_do_not_auto_select_first_mod(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    first_mod = ScannedMod(zip_path=tmp_path / "Mod.zip", mod_name="First")
    window.scan_source_key = "mods"

    window._apply_scan_report("mods", tmp_path, ScanReport([first_mod], []))

    assert window.selected_mod is None


def test_switching_mod_source_tabs_uses_cached_mods(qt_app: QApplication) -> None:
    window = MainWindow()
    first_mod = ScannedMod(zip_path=Path("Cached.zip"), mod_name="Cached Mod")
    window.mods_by_source["natives"] = [first_mod]

    window.mod_list.set_current_source("natives")

    assert window.scan_source_key == "natives"
    assert window.settings.selected_scan_source() == "natives"
    assert window.mods == [first_mod]
    assert window.mod_list.source_tabs.count() == 3


def test_switching_source_tab_autoscans_first_visit(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    window.settings.set_scan_source_folder("rechunk", tmp_path)
    calls: list[tuple[Path, str]] = []

    monkeypatch.setattr(
        window,
        "_start_scan_folder",
        lambda folder, source_key: calls.append((folder, source_key)),
    )

    window.mod_list.set_current_source("rechunk")

    assert calls == [(tmp_path, "rechunk")]


def test_rechunk_source_tab_autoscans_remembered_zip(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    zip_path = tmp_path / "BaseCmds.zip"
    zip_path.write_bytes(b"not read in this test")
    window = MainWindow()
    window.settings.set_scan_source_folder("rechunk", zip_path)
    calls: list[tuple[Path, str]] = []

    monkeypatch.setattr(
        window,
        "_start_scan_folder",
        lambda folder, source_key: calls.append((folder, source_key)),
    )

    window.mod_list.set_current_source("rechunk")

    assert calls == [(zip_path, "rechunk")]


def test_switching_source_tab_shows_disk_cache_then_autoscans_first_visit(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    cached_mod = ScannedMod(zip_path=tmp_path / "Cached.zip", mod_name="Cached Mod")
    window.settings.set_scan_source_folder("rechunk", tmp_path)
    calls: list[tuple[Path, str]] = []

    monkeypatch.setattr(
        "app.ui.main_window.load_scan_cache",
        lambda source_key, folder: [cached_mod],
    )
    monkeypatch.setattr(
        window,
        "_start_scan_folder",
        lambda folder, source_key: calls.append((folder, source_key)),
    )

    window.mod_list.set_current_source("rechunk")

    assert window.mods == [cached_mod]
    assert calls == [(tmp_path, "rechunk")]
    assert "Showing cached re_chunk / Archive data" in window.statusBar().currentMessage()


def test_switching_source_tab_does_not_rescan_after_session_refresh(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow()
    window.settings.set_scan_source_folder("rechunk", tmp_path)
    window.scanned_sources_this_session.add("rechunk")
    calls: list[tuple[Path, str]] = []

    monkeypatch.setattr(
        window,
        "_start_scan_folder",
        lambda folder, source_key: calls.append((folder, source_key)),
    )

    window.mod_list.set_current_source("rechunk")

    assert calls == []
    assert "Press Scan to load" in window.statusBar().currentMessage()


def test_mod_list_queues_preview_loading_without_blocking(qt_app: QApplication) -> None:
    mod_list = ModList()
    mod = ScannedMod(
        zip_path=Path("Preview.zip"),
        mod_name="Preview Mod",
        preview_image_path_in_zip="preview.png",
    )

    mod_list.set_mods([mod])

    assert mod_list.list_widget.count() == 1
    assert len(mod_list._preview_queue) == 1
    assert not mod_list._has_cached_preview(mod)


def test_mod_list_search_matches_character_costume_and_slot_tokens(
    qt_app: QApplication,
) -> None:
    mod_list = ModList()
    aki_mod = ScannedMod(zip_path=Path("BaseCmds.zip"), mod_name="Base CMDs")
    aki_mod.source_files = [
        SourceColorFile(
            zip_path=Path("BaseCmds.zip"),
            mod_name="Base CMDs",
            author="",
            preview_image_path_in_zip=None,
            internal_file_path="natives/stm/product/model/esf/esf013/001/esf013_001_cmd_dx_001.user.2",
            character="esf013",
            costume="001",
            type="dx",
            source_slot="001",
        )
    ]
    ryu_mod = ScannedMod(zip_path=Path("Ryu.zip"), mod_name="Ryu CMDs")
    ryu_mod.source_files = [
        SourceColorFile(
            zip_path=Path("Ryu.zip"),
            mod_name="Ryu CMDs",
            author="",
            preview_image_path_in_zip=None,
            internal_file_path="natives/stm/product/model/esf/esf001/002/esf001_002_cmd_ex_003.user.2",
            character="esf001",
            costume="002",
            type="ex",
            source_slot="003",
        )
    ]
    mod_list.set_mods([aki_mod, ryu_mod])

    for query in ("AKI", "A.K.I.", "costume 1", "c1", "outfit 1", "dx1", "aki 01"):
        mod_list.search.setText(query)
        assert mod_list.list_widget.count() == 1
        row = mod_list.list_widget.itemWidget(mod_list.list_widget.item(0))
        assert any("Base CMDs" in label.text() for label in row.findChildren(QLabel))

    mod_list.search.setText("ex3")
    assert mod_list.list_widget.count() == 1
    row = mod_list.list_widget.itemWidget(mod_list.list_widget.item(0))
    assert any("Ryu CMDs" in label.text() for label in row.findChildren(QLabel))


def test_selecting_character_auto_selects_single_costume_and_dx_slot(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "SingleDx.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Single DX\n")
        archive.writestr(f"{COLOR_ROOT}/esf002/003/esf002_003_cmd_dx_004.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]

    window._select_character("esf002")

    assert window.selected_costume == "003"
    assert window.selected_source_slot == "004"
    assert window.slot_column.current_type == "dx"


def test_collection_context_controls_select_assignment_context(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf002/003/esf002_003_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf002"
    window.selected_costume = "003"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")

    window.selected_character = "esf001"
    window.selected_costume = "001"
    window._refresh_columns()
    character_index = window.collection_column.character_combo.findData("esf002")
    costume_index = window.collection_column.costume_combo.findData("003")

    window.collection_column.character_combo.setCurrentIndex(character_index)
    window.collection_column.costume_combo.setCurrentIndex(costume_index)

    assert window.selected_character == "esf002"
    assert window.selected_costume == "003"
    row_widget = window.collection_column.slot_lists["normal"].itemWidget(
        window.collection_column.slot_lists["normal"].item(3)
    )
    assert "Source Mod" in row_widget.findChildren(type(window.collection_column.title))[0].text()


def test_characters_sort_by_display_name(qt_app: QApplication) -> None:
    window = MainWindow()
    assert window._sort_characters({"esf010", "esf001", "esf003"}) == [
        "esf010",
        "esf003",
        "esf001",
    ]


def test_character_label_includes_esf_id() -> None:
    assert character_label("esf002") == "Luke (002)"


def test_unavailable_source_slot_is_disabled(qt_app: QApplication) -> None:
    window = MainWindow()
    window.slot_column.set_available_slots("normal", set())
    item = window.slot_column.table_widget.item(0, 0)

    assert not item.flags().value & 1


def test_source_slots_render_as_three_column_table(qt_app: QApplication) -> None:
    window = MainWindow()

    assert window.slot_column.table_widget.columnCount() == 3
    assert window.slot_column.table_widget.item(0, 0).text() == "01"
    assert window.slot_column.table_widget.item(0, 1).text() == "DX1"
    assert window.slot_column.table_widget.item(0, 2).text() == "EX1"


def test_option_and_slot_selection_use_native_selection(qt_app: QApplication) -> None:
    window = MainWindow()
    window.character_column.set_options({"esf001": "Ryu"}, {"esf001"}, "esf001")
    window.costume_column.set_options({"001": "Costume 1"}, {"001"}, "001")
    window.slot_column.set_available_slots("normal", {"002"}, "002")

    character_item = window.character_column.table_widget.item(0, 0)
    costume_item = window.costume_column.list_widget.item(0)
    slot_item = window.slot_column.table_widget.item(1, 0)

    assert character_item.isSelected()
    assert costume_item.isSelected()
    assert slot_item.isSelected()


def test_collection_target_selection_does_not_survive_refresh(qt_app: QApplication) -> None:
    window = MainWindow()
    item = window.collection_column.slot_lists["normal"].item(2)

    window.collection_column._emit_target_slot_selected(item)
    window.collection_column.refresh_all(
        {},
        source_type="normal",
        source_selected=True,
        character="esf001",
        costume="001",
    )

    assert not window.collection_column.slot_lists["normal"].item(2).isSelected()


def test_unavailable_character_and_costume_are_disabled(qt_app: QApplication) -> None:
    window = MainWindow()
    window.character_column.set_options({"esf001": "Ryu"}, set())
    window.costume_column.set_options({"001": "Costume 1"}, set())

    character_item = window.character_column.table_widget.item(0, 0)
    costume_item = window.costume_column.list_widget.item(0)

    assert not character_item.flags().value & 1
    assert not costume_item.flags().value & 1


def test_collection_summary_rows_include_assignments(qt_app: QApplication, tmp_path: Path) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")

    rows = window._collection_summary_rows()
    table = window._collection_character_table("esf001")

    assert len(rows) == len(CHARACTER_NAMES) * 5 * 3 * 10
    assert ("Ryu (001)", "Costume 1", "Normal", "04", "Source Mod (Slot 2)") in rows
    assert table.rowCount() == 30
    assert table.columnCount() == 6
    assert table.item(3, 1).text() == "Source Mod (Slot 2)"
    assert table.verticalHeaderItem(0).text() == "01"
    assert table.columnWidth(1) >= 180
    assert window._character_has_assignments("esf001")
    assert not window._character_has_assignments("esf002")


def test_collection_summary_disables_empty_character_tabs(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr(f"{COLOR_ROOT}/esf001/001/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")

    summary = window._build_collection_summary_tabs()
    buttons = summary.character_tab_buttons
    stack = summary.character_stack
    ryu_index = next(
        index for index, button in enumerate(buttons) if button.text() == "Ryu (001)"
    )
    luke_index = next(
        index for index, button in enumerate(buttons) if button.text() == "Luke (002)"
    )

    assert len(buttons) == len(CHARACTER_NAMES)
    assert buttons[ryu_index].isEnabled()
    assert buttons[ryu_index].isChecked()
    assert not buttons[luke_index].isEnabled()
    assert stack.currentIndex() == ryu_index


def test_safe_filename_replaces_windows_invalid_characters(qt_app: QApplication) -> None:
    window = MainWindow()

    assert window._safe_filename('My:Bad/Name', ".zip") == "My_Bad_Name.zip"


def test_version_changes_dialog_only_shows_once(
    qt_app: QApplication,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    window.settings.set_last_shown_changes_version("")
    calls: list[tuple[str, str]] = []
    update_log_path = tmp_path / "update_log.txt"
    update_log_path.write_text(
        "SF6 Color Collection Builder v0.1.8\nCurrent changes\n\n"
        "SF6 Color Collection Builder v0.1.7\nOlder changes",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.ui.main_window.UPDATE_LOG_PATH", update_log_path)

    def record_message(_parent, title, message):
        calls.append((title, message))
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "information", record_message)

    window._show_version_changes_once()
    window._show_version_changes_once()

    assert len(calls) == 1
    assert APP_VERSION in calls[0][0]
    assert calls[0][1] == "SF6 Color Collection Builder v0.1.8\nCurrent changes"
    assert window.settings.last_shown_changes_version() == APP_VERSION


def test_version_changes_dialog_falls_back_to_default_message(
    qt_app: QApplication,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    monkeypatch.setattr(
        "app.ui.main_window.UPDATE_LOG_PATH",
        tmp_path / "missing_update_log.txt",
    )

    assert "Recent changes:" in window._release_notes_message()


def test_update_log_reads_local_file(
    qt_app: QApplication,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    update_log_path = tmp_path / "update_log.txt"
    update_log_path.write_text("v0.1.8\n- Source tabs", encoding="utf-8")
    monkeypatch.setattr("app.ui.main_window.UPDATE_LOG_PATH", update_log_path)

    assert window._update_log_message() == "v0.1.8\n- Source tabs"


def test_release_notes_use_first_update_log_entry(
    qt_app: QApplication,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    update_log_path = tmp_path / "update_log.txt"
    update_log_path.write_text(
        "SF6 Color Collection Builder v0.1.8\nNew changes\n\n"
        "SF6 Color Collection Builder v0.1.7\nOld changes",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.ui.main_window.UPDATE_LOG_PATH", update_log_path)

    assert window._release_notes_message() == (
        "SF6 Color Collection Builder v0.1.8\nNew changes"
    )
