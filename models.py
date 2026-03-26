from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
from typing import Any, Optional

TABLE_HEADERS = [
    "File name",
    "Full path",
    "BPM Range",
    "Key Hint",
    "Duration",
    "BPM",
    "Key",
    "Relative Key",
    "Compatible Keys",
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

BPM_RANGE_OPTIONS = [
    ("Auto", None),
    ("60 - 90 BPM", (60.0, 90.0)),
    ("90 - 120 BPM", (90.0, 120.0)),
    ("120 - 140 BPM", (120.0, 140.0)),
    ("140 - 160 BPM", (140.0, 160.0)),
    ("160 - 190 BPM", (160.0, 190.0)),
]
BPM_RANGE_DEFAULT_LABEL = "Auto"
BPM_RANGE_MANUAL_LABEL = "Enter BPM..."


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
    bpm_range_label: str = BPM_RANGE_DEFAULT_LABEL
    analysis_key_hint: Optional[str] = None
    duration: Optional[float] = None
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    relative_key: Optional[str] = None
    compatible_keys: Optional[list[str]] = None
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
            "bpm_range_label": self.bpm_range_label,
            "analysis_key_hint": self.analysis_key_hint,
            "duration": self.duration,
            "bpm": self.bpm,
            "musical_key": self.musical_key,
            "relative_key": self.relative_key,
            "compatible_keys": list(self.compatible_keys or []),
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
            bpm_range_label=str(data.get("bpm_range_label") or BPM_RANGE_DEFAULT_LABEL),
            analysis_key_hint=data.get("analysis_key_hint"),
            duration=data.get("duration"),
            bpm=data.get("bpm"),
            musical_key=data.get("musical_key"),
            relative_key=data.get("relative_key"),
            compatible_keys=list(data.get("compatible_keys") or []),
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


def bpm_range_from_label(label: Optional[str]) -> Optional[tuple[float, float]]:
    normalized = str(label or BPM_RANGE_DEFAULT_LABEL).strip()
    if normalized == BPM_RANGE_MANUAL_LABEL:
        return None
    for option_label, option_range in BPM_RANGE_OPTIONS:
        if option_label == normalized:
            return option_range

    lowered = normalized.lower()
    if lowered == "auto":
        return None

    cleaned = lowered.replace("bpm", "").strip()
    range_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", cleaned)
    if range_match:
        start = float(range_match.group(1))
        end = float(range_match.group(2))
        if start > 0 and end > 0 and start != end:
            return (min(start, end), max(start, end))
        return None

    single_match = re.fullmatch(r"(\d+(?:\.\d+)?)", cleaned)
    if single_match:
        center = float(single_match.group(1))
        if center > 0:
            return (center - 0.5, center + 0.5)

    return None
