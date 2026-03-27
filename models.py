from __future__ import annotations

from dataclasses import dataclass, field
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
    "Camelot",
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

WORKFLOW_STEP_OPTIONS = [
    ("match_key", "Match Key"),
    ("match_tempo", "Match Tempo"),
    ("separate", "Separate Stems"),
]
WORKFLOW_STEP_LABELS = {step_id: label for step_id, label in WORKFLOW_STEP_OPTIONS}
WORKFLOW_DEFAULT_ORDER = [step_id for step_id, _label in WORKFLOW_STEP_OPTIONS]

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

STEM_SOURCE_LATEST = "latest_available_audio"
STEM_SOURCE_ORIGINAL = "original_track"
STEM_SOURCE_OPTIONS = [
    (STEM_SOURCE_LATEST, "Latest Available Audio"),
    (STEM_SOURCE_ORIGINAL, "Original Track"),
]
STEM_SOURCE_LABELS = {value: label for value, label in STEM_SOURCE_OPTIONS}


class SongStatus(str, Enum):
    READY = "Ready"
    QUEUED_ANALYSIS = "Queued for analysis"
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
class WorkflowStep:
    step_id: str
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "enabled": self.enabled,
        }


@dataclass
class SongRecord:
    file_path: str
    file_name: str
    bpm_range_label: str = BPM_RANGE_DEFAULT_LABEL
    analysis_key_hint: Optional[str] = None
    processing_override_enabled: bool = False
    processing_target_bpm: Optional[float] = None
    processing_target_key: Optional[str] = None
    processing_tempo_source: str = STEM_SOURCE_LATEST
    processing_selected_stems: Optional[list[str]] = field(default_factory=list)
    processing_stem_source: str = STEM_SOURCE_LATEST
    duration: Optional[float] = None
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    relative_key: Optional[str] = None
    compatible_keys: Optional[list[str]] = None
    status: str = SongStatus.QUEUED_ANALYSIS.value
    stems_dir: Optional[str] = None
    processed_path: Optional[str] = None
    last_error: Optional[str] = None

    @classmethod
    def from_path(cls, file_path: str) -> "SongRecord":
        path = Path(file_path)
        return cls(file_path=str(path), file_name=path.name, processing_selected_stems=[])

    def to_dict(self) -> dict[str, Any]:
        has_song_processing = bool(
            self.processing_target_bpm is not None
            or self.processing_target_key
            or self.processing_tempo_source != STEM_SOURCE_LATEST
            or bool(self.processing_selected_stems)
            or self.processing_stem_source != STEM_SOURCE_LATEST
        )
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "bpm_range_label": self.bpm_range_label,
            "analysis_key_hint": self.analysis_key_hint,
            "processing_override_enabled": has_song_processing,
            "processing_target_bpm": self.processing_target_bpm,
            "processing_target_key": self.processing_target_key,
            "processing_tempo_source": self.processing_tempo_source,
            "processing_selected_stems": (
                list(self.processing_selected_stems)
                if self.processing_selected_stems is not None
                else None
            ),
            "processing_stem_source": self.processing_stem_source,
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
        status = str(data.get("status") or SongStatus.QUEUED_ANALYSIS.value)
        if status == "Imported":
            status = SongStatus.QUEUED_ANALYSIS.value
        return cls(
            file_path=file_path,
            file_name=file_name,
            bpm_range_label=str(data.get("bpm_range_label") or BPM_RANGE_DEFAULT_LABEL),
            analysis_key_hint=data.get("analysis_key_hint"),
            processing_override_enabled=bool(data.get("processing_override_enabled", False)),
            processing_target_bpm=data.get("processing_target_bpm"),
            processing_target_key=data.get("processing_target_key"),
            processing_tempo_source=normalize_stem_source(data.get("processing_tempo_source")),
            processing_selected_stems=(
                list(data.get("processing_selected_stems"))
                if isinstance(data.get("processing_selected_stems"), list)
                else []
            ),
            processing_stem_source=normalize_stem_source(data.get("processing_stem_source")),
            duration=data.get("duration"),
            bpm=data.get("bpm"),
            musical_key=data.get("musical_key"),
            relative_key=data.get("relative_key"),
            compatible_keys=list(data.get("compatible_keys") or []),
            status=status,
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
    output_dir: Optional[str] = None
    key_display_preference: Optional[str] = None
    workflow_steps: Optional[list[str]] = None


def normalize_stem_source(raw_value: Any) -> str:
    if isinstance(raw_value, str) and raw_value in STEM_SOURCE_LABELS:
        return raw_value
    return STEM_SOURCE_LATEST


def normalize_workflow_steps(raw_steps: Any) -> list[WorkflowStep]:
    enabled_by_id = {step_id: True for step_id in WORKFLOW_DEFAULT_ORDER}

    if isinstance(raw_steps, list):
        for raw_step in raw_steps:
            step_id: Optional[str] = None
            enabled = True
            if isinstance(raw_step, str):
                step_id = raw_step
            elif isinstance(raw_step, dict):
                candidate = raw_step.get("step_id")
                if isinstance(candidate, str):
                    step_id = candidate
                    enabled = bool(raw_step.get("enabled", True))

            if not step_id or step_id not in WORKFLOW_STEP_LABELS:
                continue
            enabled_by_id[step_id] = enabled

    return [WorkflowStep(step_id=step_id, enabled=enabled_by_id[step_id]) for step_id in WORKFLOW_DEFAULT_ORDER]


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
