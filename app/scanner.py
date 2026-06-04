from __future__ import annotations

import configparser
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

from app.models import ParsedColorFile, ScannedMod, SourceColorFile
from app.parser import parse_color_filename


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
IMAGE_KEYS = ("image", "preview", "screenshot", "thumbnail", "picture")
COLOR_FILE_PATH_PARTS = ("natives", "stm", "product", "model", "esf")


def scan_mods_folder(folder: str | Path) -> list[ScannedMod]:
    """Scan top-level .zip files in a selected mods folder."""
    root = Path(folder)
    if not root.exists() or not root.is_dir():
        return []

    mods: list[ScannedMod] = []
    for zip_path in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if zip_path.is_file() and zip_path.suffix.lower() == ".zip":
            try:
                mods.extend(scan_zip_mods(zip_path))
            except zipfile.BadZipFile:
                continue
    return mods


def scan_zip(zip_path: str | Path) -> ScannedMod:
    mods = scan_zip_mods(zip_path)
    if not mods:
        return ScannedMod(zip_path=Path(zip_path), mod_name=Path(zip_path).stem)
    return mods[0]


def scan_zip_mods(zip_path: str | Path) -> list[ScannedMod]:
    zip_path = Path(zip_path)
    image_paths: list[str] = []
    parsed_files: list[tuple[str, ParsedColorFile]] = []
    modinfo_paths: list[str] = []

    with zipfile.ZipFile(zip_path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]

        for name in names:
            path = PurePosixPath(name)
            if path.name.lower() == "modinfo.ini":
                modinfo_paths.append(name)

            if path.suffix.lower() in IMAGE_SUFFIXES:
                image_paths.append(name)

            if not _has_supported_color_file_structure(path):
                continue

            parsed = parse_color_filename(path.name)
            if parsed:
                parsed_files.append((name, parsed))

    if not parsed_files:
        return []

    with zipfile.ZipFile(zip_path) as archive:
        modinfos = {
            modinfo_path: _read_modinfo(archive, modinfo_path)
            for modinfo_path in modinfo_paths
        }

    grouped_files = _group_parsed_files(zip_path, parsed_files, modinfos)
    mods: list[ScannedMod] = []
    for group_root, group_files in grouped_files.items():
        modinfo_path = _modinfo_for_group(group_root, modinfos)
        modinfo_data = modinfos.get(modinfo_path, {}) if modinfo_path else {}
        preview_path = _select_preview_image(
            modinfo_data,
            modinfo_path,
            _images_for_group(group_root, image_paths),
        )
        mod_name = _mod_name_for_group(zip_path, group_root, grouped_files, modinfo_data)
        mod = ScannedMod(
            zip_path=zip_path,
            mod_name=mod_name,
            author=modinfo_data.get("author", ""),
            description=modinfo_data.get("description", ""),
            metadata=modinfo_data,
            preview_image_path_in_zip=preview_path,
            modinfo_path_in_zip=modinfo_path,
        )
        mod.source_files = [
            SourceColorFile(
                zip_path=zip_path,
                mod_name=mod.mod_name,
                author=mod.author,
                preview_image_path_in_zip=preview_path,
                internal_file_path=internal_path,
                character=parsed.character,
                costume=parsed.costume,
                type=parsed.type,
                source_slot=parsed.slot,
            )
            for internal_path, parsed in group_files
        ]
        mods.append(mod)

    return sorted(mods, key=lambda mod: mod.mod_name.lower())


def _has_supported_color_file_structure(path: PurePosixPath) -> bool:
    parts = tuple(part.lower() for part in path.parts)
    required_length = len(COLOR_FILE_PATH_PARTS)
    return any(
        parts[index : index + required_length] == COLOR_FILE_PATH_PARTS
        for index in range(0, len(parts) - required_length + 1)
    )


def _read_modinfo(archive: zipfile.ZipFile, name: str) -> dict[str, str]:
    raw = archive.read(name).decode("utf-8-sig", errors="replace")
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str.lower

    if not raw.lstrip().startswith("["):
        raw = "[mod]\n" + raw

    parser.read_string(raw)
    data: dict[str, str] = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            data[key.strip().lower()] = value.strip()
    return data


def _group_parsed_files(
    zip_path: Path,
    parsed_files: list[tuple[str, ParsedColorFile]],
    modinfos: dict[str, dict[str, str]],
) -> dict[str, list[tuple[str, ParsedColorFile]]]:
    modinfo_roots = {
        _parent_key(modinfo_path): modinfo_path
        for modinfo_path in modinfos
    }
    grouped: dict[str, list[tuple[str, ParsedColorFile]]] = defaultdict(list)
    for internal_path, parsed in parsed_files:
        group_root = _nearest_modinfo_root(internal_path, modinfo_roots)
        if group_root is None:
            group_root = _fallback_group_root(zip_path, internal_path, parsed_files)
        grouped[group_root].append((internal_path, parsed))
    return dict(grouped)


def _parent_key(internal_path: str) -> str:
    parent = PurePosixPath(internal_path).parent
    value = str(parent)
    return "" if value == "." else value


def _nearest_modinfo_root(
    internal_path: str,
    modinfo_roots: dict[str, str],
) -> str | None:
    parent = PurePosixPath(internal_path).parent
    for candidate in (str(parent), *(str(ancestor) for ancestor in parent.parents)):
        normalized = "" if candidate == "." else candidate
        if normalized in modinfo_roots:
            return normalized
    return None


def _fallback_group_root(
    zip_path: Path,
    internal_path: str,
    parsed_files: list[tuple[str, ParsedColorFile]],
) -> str:
    if not _has_overlapping_sources(parsed_files):
        return ""
    parts = PurePosixPath(internal_path).parts
    return parts[0] if len(parts) > 1 else zip_path.stem


def _has_overlapping_sources(
    parsed_files: list[tuple[str, ParsedColorFile]],
) -> bool:
    seen: set[tuple[str, str, str, str]] = set()
    for _internal_path, parsed in parsed_files:
        key = (parsed.character, parsed.costume, parsed.type, parsed.slot)
        if key in seen:
            return True
        seen.add(key)
    return False


def _modinfo_for_group(group_root: str, modinfos: dict[str, dict[str, str]]) -> str | None:
    candidate = f"{group_root}/modinfo.ini" if group_root else "modinfo.ini"
    if candidate in modinfos:
        return candidate
    for modinfo_path in sorted(modinfos, key=len, reverse=True):
        if group_root and modinfo_path.startswith(f"{group_root}/"):
            return modinfo_path
    if len(modinfos) == 1:
        return next(iter(modinfos))
    return None


def _images_for_group(group_root: str, image_paths: list[str]) -> list[str]:
    if not group_root:
        return image_paths
    nearby = [
        path for path in image_paths if path == group_root or path.startswith(f"{group_root}/")
    ]
    return nearby or image_paths


def _mod_name_for_group(
    zip_path: Path,
    group_root: str,
    grouped_files: dict[str, list[tuple[str, ParsedColorFile]]],
    modinfo_data: dict[str, str],
) -> str:
    if len(grouped_files) == 1:
        return modinfo_data.get("name") or zip_path.stem
    group_label = PurePosixPath(group_root).name if group_root else "Root"
    return f"{zip_path.stem} > {group_label}"


def _select_preview_image(
    modinfo_data: dict[str, str],
    modinfo_path: str | None,
    image_paths: list[str],
) -> str | None:
    images_by_lower = {path.lower(): path for path in image_paths}

    for key in IMAGE_KEYS:
        candidate = modinfo_data.get(key)
        if not candidate:
            continue
        normalized = candidate.replace("\\", "/").lower()
        if normalized in images_by_lower:
            return images_by_lower[normalized]
        basename_matches = [
            path for path in image_paths if PurePosixPath(path).name.lower() == normalized
        ]
        if basename_matches:
            return basename_matches[0]

    if modinfo_path:
        modinfo_parent = PurePosixPath(modinfo_path).parent
        nearby = [
            path
            for path in image_paths
            if PurePosixPath(path).parent == modinfo_parent
        ]
        if nearby:
            return sorted(nearby, key=lambda path: path.lower())[0]

    return sorted(image_paths, key=lambda path: path.lower())[0] if image_paths else None
