from __future__ import annotations

import configparser
import json
from pathlib import Path
from pathlib import PurePosixPath

from app.archive_utils import archive_kind, list_archive_files, read_archive_file
from app.exporter import COLLECTION_MANIFEST_NAME
from app.models import CollectionAssignment
from app.parser import parse_color_filename


def load_exported_collection_zip(path: str | Path) -> tuple[str, str, list[CollectionAssignment]]:
    archive_path = Path(path)
    collection_name = archive_path.stem
    assignments: list[CollectionAssignment] = []

    names = list_archive_files(archive_path)
    for name in names:
        if PurePosixPath(name).name.lower() == "modinfo.ini":
            collection_name = _read_collection_name(archive_path, name) or collection_name
            break

    manifest_name = _find_collection_manifest(names)
    if manifest_name:
        manifest_collection_name, manifest_assignments = _load_manifest_assignments(
            archive_path,
            manifest_name,
            names,
        )
        return (
            manifest_collection_name or collection_name,
            str(archive_path.parent),
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
                source_zip=archive_path,
                source_kind=archive_kind(archive_path),
                source_internal_file_path=name,
                source_slot=parsed.slot,
                source_mod_name=collection_name,
            )
        )

    return collection_name, str(archive_path.parent), assignments


def _find_collection_manifest(names: list[str]) -> str | None:
    for name in names:
        if PurePosixPath(name).name == COLLECTION_MANIFEST_NAME:
            return name
    return None


def _load_manifest_assignments(
    archive_path: Path,
    manifest_name: str,
    names: list[str],
) -> tuple[str, list[CollectionAssignment]]:
    payload = json.loads(read_archive_file(archive_path, manifest_name).decode("utf-8"))
    existing_files = set(names)
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
                source_zip=archive_path,
                source_kind=archive_kind(archive_path),
                source_internal_file_path=internal_path,
                source_slot=item["source_slot"],
                source_mod_name=item["source_mod_name"],
            )
        )
    return payload.get("collection_name", "").strip(), assignments


def _read_collection_name(archive_path: Path, name: str) -> str:
    raw = read_archive_file(archive_path, name).decode("utf-8-sig", errors="replace")
    parser = configparser.ConfigParser()
    if not raw.lstrip().startswith("["):
        raw = "[mod]\n" + raw
    parser.read_string(raw)
    return parser.get("mod", "name", fallback="").strip()
