from __future__ import annotations

from pathlib import Path

from app.models import CollectionAssignment
from app.exporter import export_collection_zip
from app.project_io import load_exported_collection_zip, load_project, save_project


def test_save_and_load_project(tmp_path: Path) -> None:
    project_path = tmp_path / "project.json"
    assignment = CollectionAssignment(
        character="esf001",
        costume="001",
        type="normal",
        target_slot="003",
        source_zip=tmp_path / "Source.zip",
        source_internal_file_path="x/esf001_001_cmd_002.user.2",
        source_slot="002",
        source_mod_name="Source Mod",
    )

    save_project(project_path, "My Collection", "C:/Mods", [assignment])
    collection_name, mods_folder, assignments = load_project(project_path)

    assert collection_name == "My Collection"
    assert mods_folder == "C:/Mods"
    assert assignments == [assignment]


def test_load_exported_collection_zip(tmp_path: Path) -> None:
    source_zip = tmp_path / "Source.zip"
    source_internal = "x/esf001_001_cmd_002.user.2"
    import zipfile

    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr(source_internal, b"data")

    assignment = CollectionAssignment(
        character="esf001",
        costume="001",
        type="normal",
        target_slot="004",
        source_zip=source_zip,
        source_internal_file_path=source_internal,
        source_slot="002",
        source_mod_name="Source Mod",
    )
    output_zip = tmp_path / "Loaded Collection.zip"
    export_collection_zip(output_zip, "Loaded Collection", [assignment])

    collection_name, mods_folder, assignments = load_exported_collection_zip(output_zip)

    assert collection_name == "Loaded Collection"
    assert mods_folder == str(tmp_path)
    assert assignments[0].target_slot == "004"
    assert assignments[0].source_slot == "002"
    assert assignments[0].source_mod_name == "Source Mod"


def test_load_legacy_exported_collection_zip_without_manifest(tmp_path: Path) -> None:
    output_zip = tmp_path / "Legacy Collection.zip"
    import zipfile

    with zipfile.ZipFile(output_zip, "w") as archive:
        archive.writestr("Legacy Collection/modinfo.ini", "name=Legacy Collection\n")
        archive.writestr(
            "Legacy Collection/natives/stm/product/model/esf/esf001/001/esf001_001_cmd_004.user.2",
            b"data",
        )

    collection_name, mods_folder, assignments = load_exported_collection_zip(output_zip)

    assert collection_name == "Legacy Collection"
    assert mods_folder == str(tmp_path)
    assert assignments[0].target_slot == "004"
    assert assignments[0].source_slot == "004"
    assert assignments[0].source_mod_name == "Legacy Collection"
