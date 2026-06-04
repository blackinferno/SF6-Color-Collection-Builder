from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateInfo:
    latest_version: str
    release_url: str


def check_latest_release(
    api_url: str,
    current_version: str,
    timeout_seconds: float = 5.0,
) -> UpdateInfo | None:
    if not api_url:
        return None

    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "SF6-Color-Collection-Builder",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None

    latest_version = str(payload.get("tag_name") or "").strip()
    release_url = str(payload.get("html_url") or "").strip()
    if not latest_version or not is_newer_version(latest_version, current_version):
        return None
    return UpdateInfo(latest_version=latest_version, release_url=release_url)


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_parts = _version_parts(candidate)
    current_parts = _version_parts(current)
    max_length = max(len(candidate_parts), len(current_parts))
    candidate_parts.extend([0] * (max_length - len(candidate_parts)))
    current_parts.extend([0] * (max_length - len(current_parts)))
    return candidate_parts > current_parts


def _version_parts(version: str) -> list[int]:
    cleaned = version.strip().lower()
    if cleaned.startswith("v"):
        cleaned = cleaned[1:]
    return [int(part) for part in re.findall(r"\d+", cleaned)]
