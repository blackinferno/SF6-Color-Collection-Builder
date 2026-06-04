from __future__ import annotations

from app.update_checker import is_newer_version


def test_is_newer_version_accepts_github_v_prefix() -> None:
    assert is_newer_version("v0.1.1", "0.1.0")


def test_is_newer_version_rejects_same_version() -> None:
    assert not is_newer_version("v0.1.0", "0.1.0")


def test_is_newer_version_compares_numeric_parts() -> None:
    assert is_newer_version("v0.10.0", "0.9.9")
    assert not is_newer_version("v0.2.0", "0.10.0")
