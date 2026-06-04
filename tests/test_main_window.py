from __future__ import annotations

import zipfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.scanner import scan_zip
from app.ui.main_window import MainWindow


def test_assign_target_slot(qt_app: QApplication, tmp_path: Path) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr("x/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")

    assert ("esf001", "001", "normal", "004") in window.assignments


def test_clear_assignment(qt_app: QApplication, tmp_path: Path) -> None:
    source_zip = tmp_path / "Source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Source Mod\n")
        archive.writestr("x/esf001_001_cmd_002.user.2", b"data")

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
        archive.writestr("x/esf001_001_cmd_002.user.2", b"data")

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
            archive.writestr("x/esf001_001_cmd_002.user.2", b"data")

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
        archive.writestr("x/esf002_003_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_character = "esf001"
    window.selected_costume = "001"

    window._select_mod(0)

    assert window.selected_character == "esf002"
    assert window.selected_costume == "003"
    assert window.selected_source_slot == "002"
    assert window.slot_column.current_type == "normal"


def test_selecting_character_auto_selects_single_costume_and_dx_slot(
    qt_app: QApplication,
    tmp_path: Path,
) -> None:
    source_zip = tmp_path / "SingleDx.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("modinfo.ini", "name=Single DX\n")
        archive.writestr("x/esf002_003_cmd_dx_004.user.2", b"data")

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
        archive.writestr("x/esf002_003_cmd_002.user.2", b"data")

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
        archive.writestr("x/esf001_001_cmd_002.user.2", b"data")

    window = MainWindow()
    window.mods = [scan_zip(source_zip)]
    window.selected_mod = window.mods[0]
    window.selected_character = "esf001"
    window.selected_costume = "001"
    window.selected_source_slot = "002"
    window._assign_target_slot("normal", "004")

    rows = window._collection_summary_rows()
    table = window._collection_character_table("esf001")

    assert len(rows) == 30 * 5 * 3 * 10
    assert ("Ryu", "Costume 1", "Normal", "04", "Source Mod (Slot 2)") in rows
    assert table.rowCount() == 30
    assert table.columnCount() == 6
    assert table.item(3, 1).text() == "Source Mod (Slot 2)"
    assert table.verticalHeaderItem(0).text() == "01"
    assert table.columnWidth(1) >= 180
    assert window._character_has_assignments("esf001")
    assert not window._character_has_assignments("esf002")


def test_safe_filename_replaces_windows_invalid_characters(qt_app: QApplication) -> None:
    window = MainWindow()

    assert window._safe_filename('My:Bad/Name', ".zip") == "My_Bad_Name.zip"
