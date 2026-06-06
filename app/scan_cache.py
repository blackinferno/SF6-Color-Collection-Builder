from __future__ import annotations

import json
from pathlib import Path

from app.models import ScannedMod, SourceColorFile
import app.settings as settings_module


def load_scan_cache(
    source_key: str,
    folder: str | Path,
    cache_path: Path | None = None,
) -> list[ScannedMod]:
    cache_path = cache_path or settings_module.SCAN_CACHE_PATH
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    source_payload = payload.get(source_key)
    if not isinstance(source_payload, dict):
        return []
    if source_payload.get("folder") != str(folder):
        return []

    mods_payload = source_payload.get("mods", [])
    if not isinstance(mods_payload, list):
        return []
    return [_mod_from_payload(item) for item in mods_payload if isinstance(item, dict)]


def save_scan_cache(
    source_key: str,
    folder: str | Path,
    mods: list[ScannedMod],
    cache_path: Path | None = None,
) -> None:
    cache_path = cache_path or settings_module.SCAN_CACHE_PATH
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    payload[source_key] = {
        "folder": str(folder),
        "mods": [_mod_to_payload(mod) for mod in mods],
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def clear_scan_cache(
    source_key: str,
    cache_path: Path | None = None,
) -> None:
    cache_path = cache_path or settings_module.SCAN_CACHE_PATH
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    payload.pop(source_key, None)
    try:
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def _mod_to_payload(mod: ScannedMod) -> dict:
    return {
        "zip_path": str(mod.zip_path),
        "mod_name": mod.mod_name,
        "source_kind": mod.source_kind,
        "author": mod.author,
        "description": mod.description,
        "metadata": mod.metadata,
        "preview_image_path_in_zip": mod.preview_image_path_in_zip,
        "modinfo_path_in_zip": mod.modinfo_path_in_zip,
        "source_files": [
            {
                "zip_path": str(source.zip_path),
                "mod_name": source.mod_name,
                "author": source.author,
                "preview_image_path_in_zip": source.preview_image_path_in_zip,
                "internal_file_path": source.internal_file_path,
                "character": source.character,
                "costume": source.costume,
                "type": source.type,
                "source_slot": source.source_slot,
                "source_kind": source.source_kind,
            }
            for source in mod.source_files
        ],
    }


def _mod_from_payload(payload: dict) -> ScannedMod:
    mod = ScannedMod(
        zip_path=Path(payload.get("zip_path", "")),
        mod_name=str(payload.get("mod_name", "")),
        source_kind=str(payload.get("source_kind", "zip")),
        author=str(payload.get("author", "")),
        description=str(payload.get("description", "")),
        metadata={
            str(key): str(value)
            for key, value in payload.get("metadata", {}).items()
        },
        preview_image_path_in_zip=payload.get("preview_image_path_in_zip"),
        modinfo_path_in_zip=payload.get("modinfo_path_in_zip"),
    )
    mod.source_files = [
        SourceColorFile(
            zip_path=Path(source.get("zip_path", "")),
            mod_name=str(source.get("mod_name", "")),
            author=str(source.get("author", "")),
            preview_image_path_in_zip=source.get("preview_image_path_in_zip"),
            internal_file_path=str(source.get("internal_file_path", "")),
            character=str(source.get("character", "")),
            costume=str(source.get("costume", "")),
            type=str(source.get("type", "normal")),
            source_slot=str(source.get("source_slot", "")),
            source_kind=str(source.get("source_kind", "zip")),
        )
        for source in payload.get("source_files", [])
        if isinstance(source, dict)
    ]
    return mod
