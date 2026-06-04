from __future__ import annotations

from app.update_checker import _release_zip_download_url, is_newer_version


def test_is_newer_version_accepts_github_v_prefix() -> None:
    assert is_newer_version("v0.1.1", "0.1.0")


def test_is_newer_version_rejects_same_version() -> None:
    assert not is_newer_version("v0.1.0", "0.1.0")


def test_is_newer_version_compares_numeric_parts() -> None:
    assert is_newer_version("v0.10.0", "0.9.9")
    assert not is_newer_version("v0.2.0", "0.10.0")


def test_release_zip_download_url_selects_zip_asset() -> None:
    payload = {
        "assets": [
            {"name": "notes.txt", "browser_download_url": "https://example.test/notes"},
            {
                "name": "SF6-Color-Collection-Builder-v0.1.1-windows.zip",
                "browser_download_url": "https://example.test/app.zip",
            },
        ]
    }

    assert _release_zip_download_url(payload) == "https://example.test/app.zip"
