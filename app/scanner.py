from __future__ import annotations

import configparser
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from app.models import ParsedColorFile, ScannedMod, SourceColorFile
from app.parser import parse_color_filename
from app.settings import SCAN_LOG_PATH


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
IMAGE_KEYS = ("image", "preview", "screenshot", "thumbnail", "picture")
COLOR_FILE_PATH_PARTS = ("natives", "stm", "product", "model", "esf")
NATIVES_COLOR_FILE_PATH_PARTS = ("stm", "product", "model", "esf")
RECHUNK_COLOR_ROOT_PARTS = ("natives", "stm", "product", "model", "esf")


@dataclass(frozen=True)
class ScanIssue:
    package_path: Path
    internal_path: str | None
    message: str
    detail: str = ""

    @property
    def display_path(self) -> str:
        if self.internal_path:
            return f"{self.package_path.name} / {self.internal_path}"
        return self.package_path.name


@dataclass(frozen=True)
class ScanReport:
    mods: list[ScannedMod]
    issues: list[ScanIssue]


def scan_mods_folder(folder: str | Path) -> list[ScannedMod]:
    return scan_mods_folder_with_report(folder).mods


def scan_rechunk_source_with_report(source: str | Path) -> ScanReport:
    """Fast scan for base CMD sources under natives/stm/product/model/esf only."""
    root = Path(source)
    if root.is_file() and root.suffix.lower() == ".zip":
        try:
            mods = _scan_rechunk_zip(root)
            report = ScanReport(mods, [])
        except zipfile.BadZipFile as error:
            report = ScanReport(
                [],
                [ScanIssue(root, None, "Bad or unreadable zip file", str(error))],
            )
        write_scan_log(root, report)
        return report

    if not root.exists() or not root.is_dir():
        report = ScanReport([], [])
        write_scan_log(root, report)
        return report

    report = ScanReport(_scan_rechunk_folder(root), [])
    write_scan_log(root, report)
    return report


def scan_mods_folder_with_report(folder: str | Path) -> ScanReport:
    """Scan a zip, top-level mod packages, or a selected SF6 data folder."""
    root = Path(folder)
    if root.is_file() and root.suffix.lower() == ".zip":
        try:
            mods, issues = scan_zip_mods_with_issues(root)
        except zipfile.BadZipFile as error:
            report = ScanReport(
                [],
                [ScanIssue(root, None, "Bad or unreadable zip file", str(error))],
            )
            write_scan_log(root, report)
            return report
        report = ScanReport(sorted(mods, key=lambda mod: mod.mod_name.lower()), issues)
        write_scan_log(root, report)
        return report

    if not root.exists() or not root.is_dir():
        report = ScanReport([], [])
        write_scan_log(root, report)
        return report

    mods: list[ScannedMod] = []
    issues: list[ScanIssue] = []
    if _contains_direct_sf6_color_root(root) or _contains_direct_natives_color_root(root):
        mods, issues = scan_folder_mods_with_issues(root)
        report = ScanReport(sorted(mods, key=lambda mod: mod.mod_name.lower()), issues)
        write_scan_log(root, report)
        return report

    for package_path in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if package_path.is_file() and package_path.suffix.lower() == ".zip":
            try:
                package_mods, package_issues = scan_zip_mods_with_issues(package_path)
            except zipfile.BadZipFile as error:
                issues.append(
                    ScanIssue(package_path, None, "Bad or unreadable zip file", str(error))
                )
                continue
            mods.extend(package_mods)
            issues.extend(package_issues)
        elif package_path.is_dir():
            package_mods, package_issues = scan_folder_mods_with_issues(package_path)
            mods.extend(package_mods)
            issues.extend(package_issues)

    report = ScanReport(sorted(mods, key=lambda mod: mod.mod_name.lower()), issues)
    write_scan_log(root, report)
    return report


def _scan_rechunk_zip(zip_path: Path) -> list[ScannedMod]:
    with zipfile.ZipFile(zip_path) as archive:
        entries = [
            name.replace("\\", "/")
            for name in archive.namelist()
            if _is_rechunk_color_entry(name)
        ]
    return _mods_from_rechunk_color_entries(zip_path, "zip", entries)


def _scan_rechunk_folder(folder_path: Path) -> list[ScannedMod]:
    color_roots = _rechunk_folder_color_roots(folder_path)
    entries: list[str] = []
    for color_root in color_roots:
        try:
            character_dirs = [
                path
                for path in color_root.iterdir()
                if path.is_dir() and path.name.lower().startswith("esf")
            ]
        except OSError:
            continue
        for character_dir in character_dirs:
            try:
                costume_dirs = [
                    path
                    for path in character_dir.iterdir()
                    if path.is_dir() and path.name.isdigit()
                ]
            except OSError:
                continue
            for costume_dir in costume_dirs:
                try:
                    for file_path in costume_dir.iterdir():
                        if file_path.is_file() and parse_color_filename(file_path.name):
                            entries.append(file_path.relative_to(folder_path).as_posix())
                except OSError:
                    continue
    return _mods_from_rechunk_color_entries(folder_path, "folder", entries)


def _rechunk_folder_color_roots(folder_path: Path) -> list[Path]:
    direct_root = folder_path.joinpath(*RECHUNK_COLOR_ROOT_PARTS)
    if direct_root.is_dir():
        return [direct_root]

    roots: list[Path] = []
    try:
        for child in folder_path.iterdir():
            if child.is_dir() and child.name.lower().startswith("re_chunk"):
                color_root = child.joinpath(*RECHUNK_COLOR_ROOT_PARTS)
                if color_root.is_dir():
                    roots.append(color_root)
    except OSError:
        return []
    return roots


def _is_rechunk_color_entry(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not parse_color_filename(path.name):
        return False
    parts = tuple(part.lower() for part in path.parts)
    root_index = _path_parts_index(parts, RECHUNK_COLOR_ROOT_PARTS)
    if root_index is None:
        return False
    suffix = parts[root_index + len(RECHUNK_COLOR_ROOT_PARTS) :]
    return (
        len(suffix) == 3
        and suffix[0].startswith("esf")
        and suffix[1].isdigit()
    )


def _mods_from_rechunk_color_entries(
    source_path: Path,
    source_kind: str,
    entries: list[str],
) -> list[ScannedMod]:
    parsed_files: list[tuple[str, ParsedColorFile]] = []
    for entry in entries:
        parsed = parse_color_filename(PurePosixPath(entry).name)
        if parsed:
            parsed_files.append((entry, parsed))
    if not parsed_files:
        return []

    mod = ScannedMod(
        zip_path=source_path,
        mod_name=source_path.stem,
        source_kind=source_kind,
        description="Base CMD source",
    )
    mod.source_files = [
        SourceColorFile(
            zip_path=source_path,
            mod_name=mod.mod_name,
            author="",
            preview_image_path_in_zip=None,
            internal_file_path=entry,
            character=parsed.character,
            costume=parsed.costume,
            type=parsed.type,
            source_slot=parsed.slot,
            source_kind=source_kind,
        )
        for entry, parsed in sorted(parsed_files, key=lambda item: item[0].lower())
    ]
    return [mod]


def scan_zip(zip_path: str | Path) -> ScannedMod:
    mods = scan_zip_mods(zip_path)
    if not mods:
        return ScannedMod(zip_path=Path(zip_path), mod_name=Path(zip_path).stem)
    return mods[0]


def scan_zip_mods(zip_path: str | Path) -> list[ScannedMod]:
    return scan_zip_mods_with_issues(zip_path)[0]


def scan_zip_mods_with_issues(zip_path: str | Path) -> tuple[list[ScannedMod], list[ScanIssue]]:
    package_path = Path(zip_path)
    with zipfile.ZipFile(package_path) as archive:
        entries = [
            name.replace("\\", "/")
            for name in archive.namelist()
            if not name.endswith("/")
        ]
    return _scan_package_entries(
        package_path=package_path,
        source_kind="zip",
        entries=entries,
        read_modinfo=lambda path: _read_zip_modinfo(package_path, path),
    )


def scan_folder_mods_with_issues(folder_path: str | Path) -> tuple[list[ScannedMod], list[ScanIssue]]:
    package_path = Path(folder_path)
    entries: list[str] = []
    issues: list[ScanIssue] = []
    try:
        files = [path for path in package_path.rglob("*") if path.is_file()]
    except OSError as error:
        return [], [ScanIssue(package_path, None, "Could not read folder", str(error))]

    for file_path in files:
        try:
            entries.append(file_path.relative_to(package_path).as_posix())
        except ValueError as error:
            issues.append(
                ScanIssue(package_path, str(file_path), "Could not resolve file path", str(error))
            )

    mods, scan_issues = _scan_package_entries(
        package_path=package_path,
        source_kind="folder",
        entries=entries,
        read_modinfo=lambda path: _read_folder_modinfo(package_path, path),
    )
    return mods, [*issues, *scan_issues]


def _contains_direct_sf6_color_root(folder_path: Path) -> bool:
    color_root = folder_path.joinpath(*COLOR_FILE_PATH_PARTS)
    return color_root.is_dir()


def _contains_direct_natives_color_root(folder_path: Path) -> bool:
    color_root = folder_path.joinpath(*NATIVES_COLOR_FILE_PATH_PARTS)
    return color_root.is_dir()


def write_scan_log(folder: Path, report: ScanReport, log_path: Path = SCAN_LOG_PATH) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{datetime.now().isoformat(timespec='seconds')}]\n")
            log_file.write(f"Folder: {folder}\n")
            log_file.write(f"Mods found: {len(report.mods)}\n")
            log_file.write(f"Issues: {len(report.issues)}\n")
            for issue in report.issues:
                detail = f" - {issue.detail}" if issue.detail else ""
                log_file.write(f"- {issue.display_path}: {issue.message}{detail}\n")
            log_file.write("\n")
    except OSError:
        return


def _scan_package_entries(
    package_path: Path,
    source_kind: str,
    entries: list[str],
    read_modinfo,
) -> tuple[list[ScannedMod], list[ScanIssue]]:
    image_paths: list[str] = []
    parsed_files: list[tuple[str, ParsedColorFile]] = []
    modinfo_paths: list[str] = []
    issues: list[ScanIssue] = []

    for name in entries:
        path = PurePosixPath(name)
        if path.name.lower() == "modinfo.ini":
            modinfo_paths.append(name)

        if path.suffix.lower() in IMAGE_SUFFIXES:
            image_paths.append(name)

        parsed = parse_color_filename(path.name)
        if not parsed:
            continue
        if not _has_supported_color_file_structure(path):
            issues.append(
                ScanIssue(
                    package_path,
                    name,
                    "Supported color filename is outside the SF6 color folder structure",
                )
            )
            continue
        parsed_files.append((name, parsed))

    if not parsed_files:
        return [], issues

    modinfos: dict[str, dict[str, str]] = {}
    for modinfo_path in modinfo_paths:
        try:
            data, parse_error = read_modinfo(modinfo_path)
        except OSError as error:
            issues.append(
                ScanIssue(package_path, modinfo_path, "Could not read modinfo.ini", str(error))
            )
            continue
        if parse_error:
            issues.append(
                ScanIssue(package_path, modinfo_path, "Malformed modinfo.ini", parse_error)
            )
        else:
            modinfos[modinfo_path] = data

    grouped_files = _group_parsed_files(package_path, parsed_files, modinfos)
    mods: list[ScannedMod] = []
    for group_root, group_files in grouped_files.items():
        modinfo_path = _modinfo_for_group(group_root, modinfos)
        modinfo_data = modinfos.get(modinfo_path, {}) if modinfo_path else {}
        preview_path = _select_preview_image(
            modinfo_data,
            modinfo_path,
            _images_for_group(group_root, image_paths),
        )
        mod_name = _mod_name_for_group(package_path, group_root, grouped_files, modinfo_data)
        mod = ScannedMod(
            zip_path=package_path,
            mod_name=mod_name,
            source_kind=source_kind,
            author=modinfo_data.get("author", ""),
            description=modinfo_data.get("description", ""),
            metadata=modinfo_data,
            preview_image_path_in_zip=preview_path,
            modinfo_path_in_zip=modinfo_path,
        )
        mod.source_files = [
            SourceColorFile(
                zip_path=package_path,
                mod_name=mod.mod_name,
                author=mod.author,
                preview_image_path_in_zip=preview_path,
                internal_file_path=internal_path,
                character=parsed.character,
                costume=parsed.costume,
                type=parsed.type,
                source_slot=parsed.slot,
                source_kind=source_kind,
            )
            for internal_path, parsed in group_files
        ]
        mods.append(mod)

    return sorted(mods, key=lambda mod: mod.mod_name.lower()), issues


def _has_supported_color_file_structure(path: PurePosixPath) -> bool:
    parts = tuple(part.lower() for part in path.parts)
    return _contains_path_parts(parts, COLOR_FILE_PATH_PARTS) or _contains_path_parts(
        parts,
        NATIVES_COLOR_FILE_PATH_PARTS,
    )


def _contains_path_parts(parts: tuple[str, ...], required_parts: tuple[str, ...]) -> bool:
    return _path_parts_index(parts, required_parts) is not None


def _path_parts_index(
    parts: tuple[str, ...],
    required_parts: tuple[str, ...],
) -> int | None:
    required_length = len(required_parts)
    for index in range(0, len(parts) - required_length + 1):
        if parts[index : index + required_length] == required_parts:
            return index
    return None


def _read_zip_modinfo(package_path: Path, name: str) -> tuple[dict[str, str], str]:
    with zipfile.ZipFile(package_path) as archive:
        raw = archive.read(name).decode("utf-8-sig", errors="replace")
    return _parse_modinfo(raw)


def _read_folder_modinfo(package_path: Path, name: str) -> tuple[dict[str, str], str]:
    raw = (package_path / name).read_text(encoding="utf-8-sig", errors="replace")
    return _parse_modinfo(raw)


def _parse_modinfo(raw: str) -> tuple[dict[str, str], str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str.lower

    if not raw.lstrip().startswith("["):
        raw = "[mod]\n" + raw

    try:
        parser.read_string(raw)
    except configparser.Error as error:
        return {}, str(error)
    data: dict[str, str] = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            data[key.strip().lower()] = value.strip()
    return data, ""


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
