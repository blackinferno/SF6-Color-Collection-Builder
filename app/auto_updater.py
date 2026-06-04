from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.settings import APP_DATA_ROOT, APP_NAME
from app.update_checker import UpdateInfo


@dataclass(frozen=True)
class PreparedUpdate:
    script_path: Path


def can_auto_update(update: UpdateInfo) -> bool:
    return bool(update.download_url and getattr(sys, "frozen", False))


def prepare_update(update: UpdateInfo) -> PreparedUpdate:
    if not update.download_url:
        raise ValueError("Update release does not include a downloadable zip asset.")

    work_dir = Path(tempfile.mkdtemp(prefix="sf6_color_collection_update_"))
    zip_path = work_dir / "update.zip"
    script_path = work_dir / "apply_update.ps1"

    request = urllib.request.Request(
        update.download_url,
        headers={"User-Agent": "SF6-Color-Collection-Builder"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        zip_path.write_bytes(response.read())

    script_path.write_text(
        _updater_script(
            process_id=os.getpid(),
            app_dir=APP_DATA_ROOT,
            zip_path=zip_path,
            exe_path=Path(sys.executable),
            temp_dir=work_dir,
        ),
        encoding="utf-8",
    )
    return PreparedUpdate(script_path=script_path)


def launch_prepared_update(update: PreparedUpdate) -> None:
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(update.script_path),
        ],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _updater_script(
    process_id: int,
    app_dir: Path,
    zip_path: Path,
    exe_path: Path,
    temp_dir: Path,
) -> str:
    exe_name = f"{APP_NAME}.exe"
    return f"""$ErrorActionPreference = 'Stop'
$ProcessIdToWait = {process_id}
$AppDir = {_ps_string(app_dir)}
$ZipPath = {_ps_string(zip_path)}
$ExePath = {_ps_string(exe_path)}
$TempDir = {_ps_string(temp_dir)}
$ExeName = {_ps_string(exe_name)}

Start-Sleep -Milliseconds 750
try {{
    Wait-Process -Id $ProcessIdToWait -Timeout 30
}} catch {{}}

$ExtractDir = Join-Path $TempDir 'extracted'
New-Item -ItemType Directory -Path $ExtractDir -Force | Out-Null
Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractDir -Force

$SourceDir = $ExtractDir
if (-not (Test-Path (Join-Path $SourceDir $ExeName))) {{
    $Candidate = Get-ChildItem -LiteralPath $ExtractDir -Directory |
        Where-Object {{ Test-Path (Join-Path $_.FullName $ExeName) }} |
        Select-Object -First 1
    if ($Candidate) {{
        $SourceDir = $Candidate.FullName
    }}
}}

if (-not (Test-Path (Join-Path $SourceDir $ExeName))) {{
    throw 'Downloaded update package does not contain the application executable.'
}}

Get-ChildItem -LiteralPath $SourceDir -Force |
    Where-Object {{ $_.Name -ne 'settings.ini' }} |
    ForEach-Object {{
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $AppDir $_.Name) -Recurse -Force
    }}

Start-Process -FilePath $ExePath -WorkingDirectory $AppDir
Start-Sleep -Seconds 2
Remove-Item -LiteralPath $TempDir -Recurse -Force -ErrorAction SilentlyContinue
"""


def _ps_string(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"
