from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


COLOR_TYPES = ("normal", "dx", "ex")
VALID_SLOTS = tuple(f"{slot:03d}" for slot in range(1, 11))


@dataclass(frozen=True)
class ParsedColorFile:
    character: str
    costume: str
    type: str
    slot: str


@dataclass(frozen=True)
class SourceColorFile:
    zip_path: Path
    mod_name: str
    author: str
    preview_image_path_in_zip: str | None
    internal_file_path: str
    character: str
    costume: str
    type: str
    source_slot: str


@dataclass(frozen=True)
class CollectionAssignment:
    character: str
    costume: str
    type: str
    target_slot: str
    source_zip: Path
    source_internal_file_path: str
    source_slot: str
    source_mod_name: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.character, self.costume, self.type, self.target_slot)


@dataclass
class ScannedMod:
    zip_path: Path
    mod_name: str
    author: str = ""
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    preview_image_path_in_zip: str | None = None
    modinfo_path_in_zip: str | None = None
    source_files: list[SourceColorFile] = field(default_factory=list)

    @property
    def detected_file_count(self) -> int:
        return len(self.source_files)

    def characters(self) -> set[str]:
        return {source.character for source in self.source_files}

    def costumes_for(self, character: str) -> set[str]:
        return {
            source.costume
            for source in self.source_files
            if source.character == character
        }

    def slots_for(self, character: str, costume: str, color_type: str) -> set[str]:
        return {
            source.source_slot
            for source in self.source_files
            if source.character == character
            and source.costume == costume
            and source.type == color_type
        }

    def source_for(
        self,
        character: str,
        costume: str,
        color_type: str,
        source_slot: str,
    ) -> SourceColorFile | None:
        for source in self.source_files:
            if (
                source.character == character
                and source.costume == costume
                and source.type == color_type
                and source.source_slot == source_slot
            ):
                return source
        return None
