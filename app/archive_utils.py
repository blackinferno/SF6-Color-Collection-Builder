from __future__ import annotations

import subprocess
import shutil
import tempfile
import zipfile
from pathlib import Path
import winreg

import rarfile


SUPPORTED_ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar"}
_CUSTOM_RAR_TOOL_PATH: Path | None = None


class ArchiveReadError(Exception):
    pass


class ArchiveWriteError(Exception):
    pass


def is_supported_archive(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_ARCHIVE_SUFFIXES


def archive_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return "zip"
    if suffix == ".7z":
        return "7z"
    if suffix == ".rar":
        return "rar"
    return "archive"


def can_write_rar() -> bool:
    return _rar_write_tool() is not None


def set_custom_rar_tool_path(path: str | Path | None) -> None:
    global _CUSTOM_RAR_TOOL_PATH
    candidate = Path(path) if path else None
    _CUSTOM_RAR_TOOL_PATH = candidate if candidate and _is_rar_write_tool(candidate) else None


def is_rar_write_tool(path: str | Path) -> bool:
    return _is_rar_write_tool(Path(path))


def list_archive_files(path: str | Path) -> list[str]:
    archive_path = Path(path)
    suffix = archive_path.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(archive_path) as archive:
                return [
                    name.replace("\\", "/")
                    for name in archive.namelist()
                    if not name.endswith("/")
                ]
        if suffix == ".7z":
            return _list_7z_files(archive_path)
        if suffix == ".rar":
            with rarfile.RarFile(archive_path) as archive:
                return [
                    info.filename.replace("\\", "/")
                    for info in archive.infolist()
                    if not info.isdir()
                ]
    except (
        OSError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
        rarfile.Error,
    ) as error:
        raise ArchiveReadError(str(error)) from error
    raise ArchiveReadError(f"Unsupported archive type: {archive_path.suffix}")


def read_archive_file(path: str | Path, internal_path: str) -> bytes:
    archive_path = Path(path)
    suffix = archive_path.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(archive_path) as archive:
                return archive.read(
                    _resolve_archive_member_name(archive.namelist(), internal_path)
                )
        if suffix == ".7z":
            return _read_7z_file(archive_path, internal_path)
        if suffix == ".rar":
            with rarfile.RarFile(archive_path) as archive:
                member_name = _resolve_archive_member_name(
                    [info.filename for info in archive.infolist()],
                    internal_path,
                )
                try:
                    return archive.read(member_name)
                except rarfile.RarCannotExec:
                    return _read_file_with_archive_tool(archive_path, member_name)
    except (
        OSError,
        KeyError,
        zipfile.BadZipFile,
        rarfile.Error,
    ) as error:
        raise ArchiveReadError(str(error)) from error
    raise ArchiveReadError(f"Unsupported archive type: {archive_path.suffix}")


def write_archive_files(path: str | Path, files: dict[str, bytes]) -> None:
    archive_path = Path(path)
    suffix = archive_path.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(
                archive_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                for internal_path, data in files.items():
                    archive.writestr(internal_path, data)
            return
        if suffix == ".7z":
            temp_path = _temporary_archive_path(archive_path)
            try:
                _write_7z_files(temp_path, files)
                temp_path.replace(archive_path)
            finally:
                temp_path.unlink(missing_ok=True)
            return
        if suffix == ".rar":
            temp_path = _temporary_archive_path(archive_path)
            try:
                _write_rar_files(temp_path, files)
                temp_path.replace(archive_path)
            finally:
                temp_path.unlink(missing_ok=True)
            return
    except (OSError, zipfile.BadZipFile, rarfile.Error) as error:
        raise ArchiveWriteError(str(error)) from error
    raise ArchiveWriteError(f"Unsupported archive type: {archive_path.suffix}")


def _read_7z_file(path: Path, internal_path: str) -> bytes:
    member_name = _resolve_archive_member_name(
        _list_7z_member_names(path),
        internal_path,
    )
    return _read_file_with_archive_tool(path, member_name)


def _list_7z_files(path: Path) -> list[str]:
    return [
        _normalize_archive_member_name(name)
        for name in _list_7z_member_names(path)
        if not name.endswith(("/", "\\"))
    ]


def _list_7z_member_names(path: Path) -> list[str]:
    tar_executable = _tar_executable()
    if tar_executable is None:
        raise ArchiveReadError("Windows tar.exe is required for 7Z support.")
    result = subprocess.run(
        [str(tar_executable), "-tf", str(path)],
        capture_output=True,
        check=False,
        creationflags=_subprocess_creation_flags(),
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ArchiveReadError(detail or "Could not list the 7Z archive.")
    return [
        line.strip()
        for line in result.stdout.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def _normalize_archive_member_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _resolve_archive_member_name(names: list[str], requested_name: str) -> str:
    requested = _normalize_archive_member_name(requested_name)
    for name in names:
        if _normalize_archive_member_name(name) == requested:
            return name

    requested_lower = requested.lower()
    for name in names:
        if _normalize_archive_member_name(name).lower() == requested_lower:
            return name
    return requested_name


def _read_file_with_archive_tool(path: Path, internal_path: str) -> bytes:
    attempts: list[str] = []
    for command in _archive_tool_commands(path, internal_path):
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            creationflags=_subprocess_creation_flags(),
        )
        if result.returncode == 0:
            return result.stdout
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        attempts.append(detail or f"{Path(command[0]).name} returned {result.returncode}")
    raise ArchiveReadError("; ".join(attempts) or "No archive extraction tool found.")


def _archive_tool_commands(path: Path, internal_path: str) -> list[list[str]]:
    commands: list[list[str]] = []
    for executable in _archive_extract_tools():
        name = executable.name.lower()
        if name in {"7z.exe", "7za.exe", "7zr.exe", "7z", "7za", "7zr"}:
            commands.append(
                [str(executable), "e", "-so", "-bd", str(path), internal_path]
            )
        elif name in {"unrar.exe", "rar.exe", "winrar.exe", "unrar", "rar", "winrar"}:
            commands.append([str(executable), "p", "-inul", str(path), internal_path])
        elif name in {"tar.exe", "bsdtar.exe", "tar", "bsdtar"}:
            commands.append([str(executable), "-xOf", str(path), internal_path])
    return commands


def _archive_extract_tools() -> list[Path]:
    candidates = [
        "unrar",
        "unar",
        "bsdtar",
        "tar",
        "7z",
        "7za",
        "7zr",
        "WinRAR",
        "rar",
    ]
    paths: list[Path] = []
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            paths.append(Path(resolved))

    for candidate in (
        Path("C:/Program Files/7-Zip/7z.exe"),
        Path("C:/Program Files (x86)/7-Zip/7z.exe"),
        Path("C:/Program Files/WinRAR/UnRAR.exe"),
        Path("C:/Program Files/WinRAR/WinRAR.exe"),
        Path("C:/Program Files (x86)/WinRAR/UnRAR.exe"),
        Path("C:/Program Files (x86)/WinRAR/WinRAR.exe"),
    ):
        if candidate.exists():
            paths.append(candidate)
    for folder in _winrar_install_folders():
        for executable_name in ("UnRAR.exe", "WinRAR.exe", "rar.exe"):
            candidate = folder / executable_name
            if candidate.exists():
                paths.append(candidate)

    unique_paths: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique_paths.append(path)
    return unique_paths


def _write_7z_files(path: Path, files: dict[str, bytes]) -> None:
    tar_executable = _tar_executable()
    if tar_executable is None:
        raise ArchiveWriteError("Windows tar.exe is required for 7Z support.")
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        for internal_path, data in files.items():
            output_path = root / internal_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(data)
        path.unlink(missing_ok=True)
        result = subprocess.run(
            [
                str(tar_executable),
                "-cf",
                str(path.resolve()),
                "--format=7zip",
                "-C",
                str(root),
                ".",
            ],
            capture_output=True,
            check=False,
            creationflags=_subprocess_creation_flags(),
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise ArchiveWriteError(detail or "Could not create the 7Z archive.")


def _tar_executable() -> Path | None:
    resolved = shutil.which("tar") or shutil.which("bsdtar")
    if resolved:
        return Path(resolved)
    system_tar = Path("C:/Windows/System32/tar.exe")
    return system_tar if system_tar.exists() else None


def _temporary_archive_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False,
        dir=path.parent,
        prefix=f".{path.stem}.",
        suffix=path.suffix,
    ) as temp_file:
        return Path(temp_file.name)


def _write_rar_files(path: Path, files: dict[str, bytes]) -> None:
    rar_exe = _rar_write_tool()
    if not rar_exe:
        raise ArchiveWriteError(
            "Saving RAR archives requires WinRAR/RAR command-line tools."
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        for internal_path, data in files.items():
            output_path = root / internal_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(data)
        path.unlink(missing_ok=True)
        relative_files = [
            file_path.relative_to(root).as_posix()
            for file_path in root.rglob("*")
            if file_path.is_file()
        ]
        result = subprocess.run(
            [rar_exe, "a", "-idq", str(path), *relative_files],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            creationflags=_subprocess_creation_flags(),
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise ArchiveWriteError(detail or "RAR command failed.")


def _rar_write_tool() -> str | None:
    if _CUSTOM_RAR_TOOL_PATH and _is_rar_write_tool(_CUSTOM_RAR_TOOL_PATH):
        return str(_CUSTOM_RAR_TOOL_PATH)
    for candidate in ("rar", "WinRAR"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    for folder in _winrar_install_folders():
        for executable_name in ("rar.exe", "WinRAR.exe"):
            executable = folder / executable_name
            if executable.exists():
                return str(executable)
    return None


def _is_rar_write_tool(path: Path) -> bool:
    return path.is_file() and path.name.lower() in {"rar.exe", "winrar.exe"}


def _winrar_install_folders() -> list[Path]:
    folders: list[Path] = []
    for root, subkey in (
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ):
        try:
            with winreg.OpenKey(root, subkey) as parent:
                for index in range(winreg.QueryInfoKey(parent)[0]):
                    try:
                        child_name = winreg.EnumKey(parent, index)
                        with winreg.OpenKey(parent, child_name) as child:
                            display_name = str(winreg.QueryValueEx(child, "DisplayName")[0])
                            if "winrar" not in display_name.lower():
                                continue
                            install_location = str(
                                winreg.QueryValueEx(child, "InstallLocation")[0]
                            )
                            if install_location:
                                folders.append(Path(install_location))
                    except OSError:
                        continue
        except OSError:
            continue

    for candidate in (
        Path("C:/Program Files/WinRAR"),
        Path("C:/Program Files (x86)/WinRAR"),
        Path("D:/Program Files/WinRAR"),
        Path("D:/Program Files (x86)/WinRAR"),
    ):
        folders.append(candidate)

    unique_folders: list[Path] = []
    seen: set[str] = set()
    for folder in folders:
        key = str(folder).lower()
        if key not in seen:
            seen.add(key)
            unique_folders.append(folder)
    return unique_folders


def _subprocess_creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)
