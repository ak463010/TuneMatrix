from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

TABLE_HEADERS = [
    "File name",
    "Full path",
    "Duration",
    "BPM",
    "Key",
    "Status",
]

STEM_OPTIONS = [
    "Vocals",
    "Instrumental / No vocals",
    "Drums",
    "Bass",
    "Other",
    "All stems",
]

KEY_OPTIONS = [
    "C Major",
    "C# Major",
    "D Major",
    "D# Major",
    "E Major",
    "F Major",
    "F# Major",
    "G Major",
    "G# Major",
    "A Major",
    "A# Major",
    "B Major",
    "C Minor",
    "C# Minor",
    "D Minor",
    "D# Minor",
    "E Minor",
    "F Minor",
    "F# Minor",
    "G Minor",
    "G# Minor",
    "A Minor",
    "A# Minor",
    "B Minor",
]


class SongStatus(str, Enum):
    IMPORTED = "Imported"
    READY = "Ready"
    ANALYZING = "Analyzing"
    ANALYZED = "Analyzed"
    SEPARATING = "Separating stems"
    MATCHING_TEMPO = "Matching tempo"
    MATCHING_KEY = "Matching key"
    PROCESSING = "Processing"
    EXPORTED = "Exported"
    ERROR = "Error"
    CANCELED = "Canceled"


@dataclass
class SongRecord:
    file_path: str
    file_name: str
    duration: Optional[float] = None
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    status: str = SongStatus.IMPORTED.value
    stems_dir: Optional[str] = None
    processed_path: Optional[str] = None
    last_error: Optional[str] = None

    @classmethod
    def from_path(cls, file_path: str) -> "SongRecord":
        path = Path(file_path)
        return cls(file_path=str(path), file_name=path.name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "duration": self.duration,
            "bpm": self.bpm,
            "musical_key": self.musical_key,
            "status": self.status,
            "stems_dir": self.stems_dir,
            "processed_path": self.processed_path,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongRecord":
        file_path = str(data.get("file_path", "")).strip()
        file_name = str(data.get("file_name", "")).strip() or Path(file_path).name
        return cls(
            file_path=file_path,
            file_name=file_name,
            duration=data.get("duration"),
            bpm=data.get("bpm"),
            musical_key=data.get("musical_key"),
            status=str(data.get("status") or SongStatus.IMPORTED.value),
            stems_dir=data.get("stems_dir"),
            processed_path=data.get("processed_path"),
            last_error=data.get("last_error"),
        )


@dataclass
class ProcessingOptions:
    stem_option: str = "All stems"
    selected_stems: Optional[list[str]] = None
    target_bpm: Optional[float] = None
    target_key: Optional[str] = None
    match_to_reference: bool = False
    reference_song_path: Optional[str] = None
    output_dir: Optional[str] = None
