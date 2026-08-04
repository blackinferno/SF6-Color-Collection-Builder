from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.archive_utils import (
    ArchiveReadError,
    ArchiveWriteError,
    can_write_rar,
    is_supported_archive,
    list_archive_files,
    read_archive_file,
    write_archive_files,
)
from app.parser import parse_color_filename
from app.settings import CMD_UPDATE_LOG_PATH


OLD_CMD_BYTES = bytes.fromhex("61 2A 53 4D")
NEW_CMD_BYTES = bytes.fromhex("7A 6E C8 66")


@dataclass(frozen=True)
class CmdUpdateIssue:
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
class CmdUpdateReport:
    packages_checked: int
    color_files_checked: int
    files_updated: int
    issues: list[CmdUpdateIssue]


def update_cmds_in_source(source: str | Path) -> CmdUpdateReport:
    root = Path(source)
    report = _update_cmds_in_source(root)
    write_cmd_update_log(root, report)
    return report


def write_cmd_update_log(
    source: Path,
    report: CmdUpdateReport,
    log_path: Path | None = None,
) -> None:
    log_path = log_path or CMD_UPDATE_LOG_PATH
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{datetime.now().isoformat(timespec='seconds')}]\n")
            log_file.write(f"Source: {source}\n")
            log_file.write(f"Packages checked: {report.packages_checked}\n")
            log_file.write(f"CMD files checked: {report.color_files_checked}\n")
            log_file.write(f"CMD files updated: {report.files_updated}\n")
            log_file.write(f"Issues: {len(report.issues)}\n")
            for issue in report.issues:
                detail = f" - {issue.detail}" if issue.detail else ""
                log_file.write(f"- {issue.display_path}: {issue.message}{detail}\n")
            log_file.write("\n")
    except OSError:
        return


def _update_cmds_in_source(source: Path) -> CmdUpdateReport:
    root = Path(source)
    if is_supported_archive(root):
        return _update_archive(root)
    if root.is_file() and _is_color_file_name(root.name):
        return _update_loose_file(root)
    if not root.exists() or not root.is_dir():
        return CmdUpdateReport(
            0,
            0,
            0,
            [CmdUpdateIssue(root, None, "Selected source does not exist.")],
        )

    totals = _MutableReport()
    try:
        files = [path for path in root.rglob("*") if path.is_file()]
    except OSError as error:
        return CmdUpdateReport(
            1,
            0,
            0,
            [CmdUpdateIssue(root, None, "Could not read folder.", str(error))],
        )

    for file_path in sorted(files, key=lambda path: str(path).lower()):
        if is_supported_archive(file_path):
            totals.add(_update_archive(file_path))
        elif _is_color_file_name(file_path.name):
            totals.add(_update_loose_file(file_path))
    return totals.freeze()


def _update_archive(archive_path: Path) -> CmdUpdateReport:
    if archive_path.suffix.lower() == ".rar" and not can_write_rar():
        return CmdUpdateReport(
            1,
            0,
            0,
            [
                CmdUpdateIssue(
                    archive_path,
                    None,
                    "RAR update requires WinRAR/RAR command-line tools.",
                    "Install WinRAR or extract this RAR to a loose folder before updating CMDs.",
                )
            ],
        )

    try:
        names = list_archive_files(archive_path)
    except ArchiveReadError as error:
        return CmdUpdateReport(
            1,
            0,
            0,
            [CmdUpdateIssue(archive_path, None, "Could not read archive.", str(error))],
        )

    files: dict[str, bytes] = {}
    color_files_checked = 0
    files_updated = 0
    changed = False
    issues: list[CmdUpdateIssue] = []
    try:
        for name in names:
            data = read_archive_file(archive_path, name)
            if _is_color_file_name(name):
                color_files_checked += 1
                patched = data.replace(OLD_CMD_BYTES, NEW_CMD_BYTES)
                if patched != data:
                    data = patched
                    changed = True
                    files_updated += 1
            files[name] = data
    except ArchiveReadError as error:
        return CmdUpdateReport(
            1,
            color_files_checked,
            files_updated,
            [CmdUpdateIssue(archive_path, name, "Could not read archive file.", str(error))],
        )

    if changed:
        try:
            write_archive_files(archive_path, files)
        except ArchiveWriteError as error:
            issues.append(
                CmdUpdateIssue(archive_path, None, "Could not write updated archive.", str(error))
            )
            files_updated = 0

    return CmdUpdateReport(1, color_files_checked, files_updated, issues)


def _update_loose_file(file_path: Path) -> CmdUpdateReport:
    issues: list[CmdUpdateIssue] = []
    files_updated = 0
    try:
        data = file_path.read_bytes()
        patched = data.replace(OLD_CMD_BYTES, NEW_CMD_BYTES)
        if patched != data:
            file_path.write_bytes(patched)
            files_updated = 1
    except OSError as error:
        issues.append(
            CmdUpdateIssue(file_path, None, "Could not update loose CMD file.", str(error))
        )
    return CmdUpdateReport(1, 1, files_updated, issues)


def _is_color_file_name(path_text: str) -> bool:
    return parse_color_filename(Path(path_text.replace("\\", "/")).name) is not None


@dataclass
class _MutableReport:
    packages_checked: int = 0
    color_files_checked: int = 0
    files_updated: int = 0
    issues: list[CmdUpdateIssue] | None = None

    def add(self, report: CmdUpdateReport) -> None:
        self.packages_checked += report.packages_checked
        self.color_files_checked += report.color_files_checked
        self.files_updated += report.files_updated
        if report.issues:
            if self.issues is None:
                self.issues = []
            self.issues.extend(report.issues)

    def freeze(self) -> CmdUpdateReport:
        return CmdUpdateReport(
            self.packages_checked,
            self.color_files_checked,
            self.files_updated,
            self.issues or [],
        )
