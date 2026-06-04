from __future__ import annotations

from pathlib import Path

from app.auto_updater import _updater_script


def test_updater_script_preserves_settings_file(tmp_path: Path) -> None:
    script = _updater_script(
        process_id=123,
        app_dir=tmp_path / "app",
        zip_path=tmp_path / "update.zip",
        exe_path=tmp_path / "app" / "SF6 Color Collection Builder.exe",
        temp_dir=tmp_path,
    )

    assert "$ExeName = 'SF6 Color Collection Builder.exe'" in script
    assert "$_.Name -ne 'settings.ini'" in script
    assert "Expand-Archive" in script
    assert "Start-Process -FilePath $ExePath" in script
