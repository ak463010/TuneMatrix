from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a"}
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CAMELOT_KEY_MAP = {
    "C Major": "8B",
    "C# Major": "3B",
    "D Major": "10B",
    "D# Major": "5B",
    "E Major": "12B",
    "F Major": "7B",
    "F# Major": "2B",
    "G Major": "9B",
    "G# Major": "4B",
    "A Major": "11B",
    "A# Major": "6B",
    "B Major": "1B",
    "C Minor": "5A",
    "C# Minor": "12A",
    "D Minor": "7A",
    "D# Minor": "2A",
    "E Minor": "9A",
    "F Minor": "4A",
    "F# Minor": "11A",
    "G Minor": "6A",
    "G# Minor": "1A",
    "A Minor": "8A",
    "A# Minor": "3A",
    "B Minor": "10A",
}
ENHARMONIC_KEY_ALIAS_MAP = {
    "C# Major": "D♭ Major",
    "D♭ Major": "C# Major",
    "D# Major": "E♭ Major",
    "E♭ Major": "D# Major",
    "F# Major": "G♭ Major",
    "G♭ Major": "F# Major",
    "G# Major": "A♭ Major",
    "A♭ Major": "G# Major",
    "A# Major": "B♭ Major",
    "B♭ Major": "A# Major",
    "C# Minor": "D♭ Minor",
    "D♭ Minor": "C# Minor",
    "D# Minor": "E♭ Minor",
    "E♭ Minor": "D# Minor",
    "F# Minor": "G♭ Minor",
    "G♭ Minor": "F# Minor",
    "G# Minor": "A♭ Minor",
    "A♭ Minor": "G# Minor",
    "A# Minor": "B♭ Minor",
    "B♭ Minor": "A# Minor",
}


def is_supported_audio_file(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def validate_audio_file(path: str) -> tuple[bool, str]:
    file_path = Path(path)
    if not file_path.exists():
        return False, f"File does not exist: {file_path}"
    if not file_path.is_file():
        return False, f"Path is not a file: {file_path}"
    if file_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        return False, f"Unsupported format for {file_path.name}. Allowed: {allowed}"
    return True, ""


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"
    total_seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def format_bpm(bpm: Optional[float]) -> str:
    if bpm is None or bpm <= 0:
        return "N/A"
    return f"{bpm:.1f}"


def format_key(key_name: Optional[str]) -> str:
    return key_name or "N/A"


def format_key_list(keys: Optional[list[str]]) -> str:
    if not keys:
        return "N/A"
    return ", ".join(keys)


def enharmonic_key_alias(key_name: Optional[str]) -> Optional[str]:
    if not key_name:
        return None
    return ENHARMONIC_KEY_ALIAS_MAP.get(key_name)


def format_key_with_alias(key_name: Optional[str]) -> str:
    formatted = format_key(key_name)
    if formatted == "N/A":
        return formatted
    alias = enharmonic_key_alias(key_name)
    if not alias:
        return formatted
    return f"{formatted} ({alias})"


def camelot_for_key(key_name: Optional[str]) -> Optional[str]:
    if not key_name:
        return None
    return CAMELOT_KEY_MAP.get(key_name)


def format_camelot(key_name: Optional[str]) -> str:
    return camelot_for_key(key_name) or "N/A"


def safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "item"


def ensure_directory(path: str | Path) -> str:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory)


def default_export_dir() -> str:
    return ensure_directory(Path.cwd() / "exports")


def application_cache_dir() -> str:
    return ensure_directory(Path(tempfile.gettempdir()) / "TuneMatrix")


def make_song_cache_dir(file_path: str, file_name: str, category: str) -> str:
    digest = hashlib.sha1(Path(file_path).as_posix().encode("utf-8")).hexdigest()[:10]
    directory_name = f"{safe_stem(Path(file_name).stem)}_{digest}"
    return ensure_directory(Path(application_cache_dir()) / category / directory_name)


def build_output_filename(file_name: str, suffix: str, extension: str = ".wav") -> str:
    ext = extension if extension.startswith(".") else f".{extension}"
    base_name = safe_stem(Path(file_name).stem)
    suffix = safe_stem(suffix)
    return f"{base_name}_{suffix}{ext}"


def unique_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        if candidate.suffix:
            test_path = candidate.with_name(f"{candidate.stem}_{counter}{candidate.suffix}")
        else:
            test_path = candidate.with_name(f"{candidate.name}_{counter}")
        if not test_path.exists():
            return test_path
        counter += 1


def copy_file_to_directory(source_file: str | Path, destination_dir: str | Path, name: Optional[str] = None) -> str:
    source_path = Path(source_file)
    destination_root = Path(ensure_directory(destination_dir))
    target_name = name or source_path.name
    target_path = unique_path(destination_root / target_name)
    shutil.copy2(source_path, target_path)
    return str(target_path)


def copy_directory_to_directory(source_dir: str | Path, destination_dir: str | Path, name: Optional[str] = None) -> str:
    source_path = Path(source_dir)
    destination_root = Path(ensure_directory(destination_dir))
    target_name = name or source_path.name
    target_path = unique_path(destination_root / target_name)
    shutil.copytree(source_path, target_path)
    return str(target_path)


def find_executable(name: str) -> Optional[str]:
    return shutil.which(name)


def format_dependency_status(name: str, available: bool, detail: Optional[str] = None) -> str:
    status = "available" if available else "missing"
    if detail:
        return f"{name}: {status} ({detail})"
    return f"{name}: {status}"
