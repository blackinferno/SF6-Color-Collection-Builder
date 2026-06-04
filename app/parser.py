from __future__ import annotations

import re
from pathlib import PurePath

from app.models import ParsedColorFile, VALID_SLOTS


COLOR_FILE_RE = re.compile(
    r"^(esf\d{3})_(\d{3})_cmd(?:_(dx|ex))?_(\d{3})\.user\.2$",
    re.IGNORECASE,
)


def parse_color_filename(filename: str) -> ParsedColorFile | None:
    """Parse a supported SF6 color-slot filename.

    Only slots 001 through 010 are valid for v0.1.
    """
    basename = PurePath(filename).name
    match = COLOR_FILE_RE.match(basename)
    if not match:
        return None

    character, costume, variant, slot = match.groups()
    if slot not in VALID_SLOTS:
        return None

    return ParsedColorFile(
        character=character.lower(),
        costume=costume,
        type=(variant or "normal").lower(),
        slot=slot,
    )


def format_slot_label(slot: str) -> str:
    return f"{int(slot):02d}"

