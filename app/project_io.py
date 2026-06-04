from __future__ import annotations

import configparser
import json
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

from app.exporter import COLLECTION_MANIFEST_NAME
from app.models import CollectionAssignment
from app.parser import parse_color_filename


def save_project(
    path: str | Path,
    collection_name: str,
    mods_folder: str,
    assignments: list[CollectionAssignment],
) -> None:
    payload = {
        "collection_name": collection_name,
        "mods_folder": mods_folder,
        "assignments": [
            {
                "character": assignment.character,
                "costume": assignment.costume,
                "type": assignment.type,
                "target_slot": assignment.target_slot,
                "source_zip": str(assignment.source_zip),
                "source_internal_file_path": assignment.source_internal_file_path,
                "source_slot": assignment.source_slot,
                "source_mod_name": assignment.source_mod_name,
            }
            for assignment in assignments
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_project(path: str | Path) -> tuple[str, str, list[CollectionAssignment]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assignments = [
        CollectionAssignment(
            character=item["character"],
            costume=item["costume"],
            type=item["type"],
            target_slot=item["target_slot"],
            source_zip=Path(item["source_zip"]),
            source_internal_file_path=item["source_internal_file_path"],
            source_slot=item["source_slot"],
            source_mod_name=item["source_mod_name"],
        )
        for item in payload.get("assignments", [])
    ]
    return payload.get("collection_name", "Custom Collection"), payload.get("mods_folder", ""), assignments


def load_exported_collection_zip(path: str | Path) -> tuple[str, str, list[CollectionAssignment]]:
    zip_path = Path(path)
    collection_name = zip_path.stem
    assignments: list[CollectionAssignment] = []

    with zipfile.ZipFile(zip_path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        for name in names:
            if PurePosixPath(name).name.lower() == "modinfo.ini":
                collection_name = _read_collection_name(archive, name) or collection_name
                break

        manifest_name = _find_collection_manifest(names)
        if manifest_name:
            manifest_collection_name, manifest_assignments = _load_manifest_assignments(
                archive,
                manifest_name,
                zip_path,
            )
            return (
                manifest_collection_name or collection_name,
                str(zip_path.parent),
                manifest_assignments,
            )

        for name in names:
            parsed = parse_color_filename(PurePosixPath(name).name)
            if not parsed:
                continue
            assignments.append(
                CollectionAssignment(
                    character=parsed.character,
                    costume=parsed.costume,
                    type=parsed.type,
                    target_slot=parsed.slot,
                    source_zip=zip_path,
                    source_internal_file_path=name,
                    source_slot=parsed.slot,
                    source_mod_name=collection_name,
                )
            )

    return collection_name, str(zip_path.parent), assignments


def _find_collection_manifest(names: list[str]) -> str | None:
    for name in names:
        if PurePosixPath(name).name == COLLECTION_MANIFEST_NAME:
            return name
    return None


def _load_manifest_assignments(
    archive: zipfile.ZipFile,
    manifest_name: str,
    zip_path: Path,
) -> tuple[str, list[CollectionAssignment]]:
    payload = json.loads(archive.read(manifest_name).decode("utf-8"))
    existing_files = set(archive.namelist())
    assignments = []
    for item in payload.get("assignments", []):
        internal_path = item["exported_internal_file_path"]
        if internal_path not in existing_files:
            continue
        assignments.append(
            CollectionAssignment(
                character=item["character"],
                costume=item["costume"],
                type=item["type"],
                target_slot=item["target_slot"],
                source_zip=zip_path,
                source_internal_file_path=internal_path,
                source_slot=item["source_slot"],
                source_mod_name=item["source_mod_name"],
            )
        )
    return payload.get("collection_name", "").strip(), assignments


def _read_collection_name(archive: zipfile.ZipFile, name: str) -> str:
    raw = archive.read(name).decode("utf-8-sig", errors="replace")
    parser = configparser.ConfigParser()
    if not raw.lstrip().startswith("["):
        raw = "[mod]\n" + raw
    parser.read_string(raw)
    return parser.get("mod", "name", fallback="").strip()
