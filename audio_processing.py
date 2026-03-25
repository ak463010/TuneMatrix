from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

try:
    import librosa
except Exception as exc:  # pragma: no cover - dependency dependent
    librosa = None
    LIBROSA_IMPORT_ERROR = str(exc)
else:
    LIBROSA_IMPORT_ERROR = None

try:
    import numpy as np
except Exception as exc:  # pragma: no cover - dependency dependent
    np = None
    NUMPY_IMPORT_ERROR = str(exc)
else:
    NUMPY_IMPORT_ERROR = None

try:
    import pyrubberband as pyrb
except Exception as exc:  # pragma: no cover - dependency dependent
    pyrb = None
    PYRUBBERBAND_IMPORT_ERROR = str(exc)
else:
    PYRUBBERBAND_IMPORT_ERROR = None

try:
    import soundfile as sf
except Exception as exc:  # pragma: no cover - dependency dependent
    sf = None
    SOUND_FILE_IMPORT_ERROR = str(exc)
else:
    SOUND_FILE_IMPORT_ERROR = None

from models import SongRecord
from utils import (
    NOTE_NAMES,
    build_output_filename,
    copy_directory_to_directory,
    copy_file_to_directory,
    ensure_directory,
    find_executable,
    format_dependency_status,
    make_song_cache_dir,
    safe_stem,
)

LogCallback = Optional[Callable[[str], None]]
CancelCallback = Optional[Callable[[], bool]]


class AudioProcessingError(Exception):
    pass


class DependencyError(AudioProcessingError):
    pass


class TaskCanceledError(AudioProcessingError):
    pass


COMPRESSED_FORMATS = {".mp3", ".m4a"}
ANALYSIS_ACTIONS = {"analyze", "match_tempo", "match_key", "process_all"}
STEM_ACTIONS = {"separate", "process_all"}
WRITE_ACTIONS = {"match_tempo", "match_key", "process_all"}


def get_dependency_report() -> dict[str, dict[str, Optional[str]]]:
    return {
        "librosa": {"available": librosa is not None, "detail": LIBROSA_IMPORT_ERROR},
        "numpy": {"available": np is not None, "detail": NUMPY_IMPORT_ERROR},
        "soundfile": {"available": sf is not None, "detail": SOUND_FILE_IMPORT_ERROR},
        "pyrubberband": {"available": pyrb is not None, "detail": PYRUBBERBAND_IMPORT_ERROR},
        "torch": {"available": importlib.util.find_spec("torch") is not None, "detail": None},
        "torchaudio": {"available": importlib.util.find_spec("torchaudio") is not None, "detail": None},
        "torchcodec": {"available": importlib.util.find_spec("torchcodec") is not None, "detail": None},
        "rubberband": {"available": find_executable("rubberband") is not None, "detail": None},
        "ffmpeg": {"available": find_executable("ffmpeg") is not None, "detail": None},
        "demucs": {"available": importlib.util.find_spec("demucs") is not None, "detail": None},
    }


def dependency_status_lines() -> list[str]:
    report = get_dependency_report()
    ordered_names = [
        "librosa",
        "numpy",
        "soundfile",
        "pyrubberband",
        "rubberband",
        "ffmpeg",
        "torch",
        "torchaudio",
        "torchcodec",
        "demucs",
    ]
    return [format_dependency_status(name, report[name]["available"], report[name]["detail"]) for name in ordered_names]


def _file_paths_need_ffmpeg(file_paths: Optional[list[str]]) -> bool:
    if not file_paths:
        return False
    return any(Path(path).suffix.lower() in COMPRESSED_FORMATS for path in file_paths)


def _decode_support_required(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in COMPRESSED_FORMATS


def action_runtime_issues(action: str, file_paths: Optional[list[str]] = None) -> list[str]:
    report = get_dependency_report()
    issues: list[str] = []

    if action in ANALYSIS_ACTIONS:
        if not report["numpy"]["available"]:
            issues.append("NumPy is required for audio analysis.")
        if not report["librosa"]["available"]:
            issues.append("librosa is required for audio analysis.")

    if action in WRITE_ACTIONS and not report["soundfile"]["available"]:
        issues.append("soundfile is required to write processed audio files.")

    if action in STEM_ACTIONS:
        if not report["demucs"]["available"]:
            issues.append("Demucs is not installed.")
        if not report["torch"]["available"]:
            issues.append("PyTorch is required for stem separation.")
        if not report["torchaudio"]["available"]:
            issues.append("torchaudio is required for stem separation.")
        if not report["torchcodec"]["available"]:
            issues.append("torchcodec is required by the current Demucs/torchaudio runtime.")

    if action in ANALYSIS_ACTIONS and _file_paths_need_ffmpeg(file_paths) and not report["ffmpeg"]["available"]:
        issues.append("ffmpeg is required to decode mp3 and m4a files.")

    return issues


def action_base_requirement_message(action: str) -> Optional[str]:
    issues = action_runtime_issues(action)
    if not issues:
        return None
    return " ".join(issues)


def _log(log_callback: LogCallback, message: str) -> None:
    if log_callback:
        log_callback(message)


def _check_canceled(cancel_callback: CancelCallback) -> None:
    if cancel_callback and cancel_callback():
        raise TaskCanceledError("Task canceled by user.")


def _require_analysis_stack() -> None:
    if np is None:
        raise DependencyError("NumPy is required for audio analysis.")
    if librosa is None:
        detail = f": {LIBROSA_IMPORT_ERROR}" if LIBROSA_IMPORT_ERROR else ""
        raise DependencyError(f"librosa is not available{detail}")


def _require_audio_write_stack() -> None:
    if np is None:
        raise DependencyError("NumPy is required for audio export.")
    if sf is None:
        detail = f": {SOUND_FILE_IMPORT_ERROR}" if SOUND_FILE_IMPORT_ERROR else ""
        raise DependencyError(f"soundfile is not available{detail}")


def _require_decode_support(file_path: str) -> None:
    if _decode_support_required(file_path) and find_executable("ffmpeg") is None:
        suffix = Path(file_path).suffix.lower()
        raise DependencyError(f"ffmpeg is required to decode {suffix} files. Install ffmpeg or use wav/flac.")


def analyze_audio(file_path: str) -> dict[str, Optional[float | str]]:
    _require_analysis_stack()
    _require_decode_support(file_path)

    audio, sample_rate = librosa.load(file_path, sr=None, mono=True)
    duration = float(librosa.get_duration(y=audio, sr=sample_rate))
    tempo, _ = librosa.beat.beat_track(y=audio, sr=sample_rate)
    bpm = float(np.asarray(tempo).reshape(-1)[0]) if tempo is not None else None
    key_name = detect_key(audio, sample_rate)
    return {
        "duration": duration,
        "bpm": bpm,
        "key": key_name,
    }


def detect_key(audio: "np.ndarray", sample_rate: int) -> Optional[str]:
    _require_analysis_stack()

    if audio.size == 0:
        return None

    try:
        chroma = librosa.feature.chroma_cqt(y=audio, sr=sample_rate)
    except Exception:
        chroma = librosa.feature.chroma_stft(y=audio, sr=sample_rate)

    pitch_profile = np.mean(chroma, axis=1)
    if not np.any(pitch_profile):
        return None

    pitch_profile = pitch_profile / np.sum(pitch_profile)
    major_template = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88], dtype=float)
    minor_template = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17], dtype=float)
    major_template /= major_template.sum()
    minor_template /= minor_template.sum()

    best_score = float("-inf")
    best_key = None
    for note_index, note_name in enumerate(NOTE_NAMES):
        major_score = float(np.dot(pitch_profile, np.roll(major_template, note_index)))
        minor_score = float(np.dot(pitch_profile, np.roll(minor_template, note_index)))
        if major_score > best_score:
            best_score = major_score
            best_key = f"{note_name} Major"
        if minor_score > best_score:
            best_score = minor_score
            best_key = f"{note_name} Minor"
    return best_key


def _load_audio_for_processing(file_path: str) -> tuple["np.ndarray", int]:
    _require_analysis_stack()
    _require_decode_support(file_path)
    audio, sample_rate = librosa.load(file_path, sr=None, mono=False)
    return np.asarray(audio, dtype=np.float32), sample_rate


def _save_audio(output_path: str | Path, audio: "np.ndarray", sample_rate: int) -> str:
    _require_audio_write_stack()

    output = Path(output_path)
    ensure_directory(output.parent)
    audio_to_write = np.asarray(audio, dtype=np.float32)
    if audio_to_write.ndim == 2:
        audio_to_write = audio_to_write.T
    audio_to_write = np.clip(audio_to_write, -1.0, 1.0)
    sf.write(str(output), audio_to_write, sample_rate)
    return str(output)


def _run_per_channel(audio: "np.ndarray", processor: Callable[["np.ndarray"], "np.ndarray"]) -> "np.ndarray":
    if audio.ndim == 1:
        return np.asarray(processor(audio), dtype=np.float32)

    channels = [np.asarray(processor(channel), dtype=np.float32) for channel in audio]
    min_length = min(channel.shape[-1] for channel in channels)
    trimmed = [channel[:min_length] for channel in channels]
    return np.vstack(trimmed).astype(np.float32)


def _time_stretch(audio: "np.ndarray", sample_rate: int, rate: float, log_callback: LogCallback = None) -> "np.ndarray":
    if rate <= 0:
        raise AudioProcessingError("Time-stretch rate must be greater than zero.")

    if pyrb is not None and find_executable("rubberband"):
        _log(log_callback, "Using Rubber Band for tempo matching.")
        return _run_per_channel(audio, lambda channel: pyrb.time_stretch(channel, sample_rate, rate))

    if librosa is None:
        raise DependencyError("Neither Rubber Band nor librosa are available for tempo matching.")

    _log(log_callback, "Rubber Band not found. Falling back to librosa for tempo matching.")
    return _run_per_channel(audio, lambda channel: librosa.effects.time_stretch(channel, rate=rate))


def _pitch_shift(audio: "np.ndarray", sample_rate: int, semitones: float, log_callback: LogCallback = None) -> "np.ndarray":
    if abs(semitones) < 1e-6:
        return audio

    if pyrb is not None and find_executable("rubberband"):
        _log(log_callback, "Using Rubber Band for key matching.")
        return _run_per_channel(audio, lambda channel: pyrb.pitch_shift(channel, sample_rate, semitones))

    if librosa is None:
        raise DependencyError("Neither Rubber Band nor librosa are available for key matching.")

    _log(log_callback, "Rubber Band not found. Falling back to librosa for key matching.")
    return _run_per_channel(
        audio,
        lambda channel: librosa.effects.pitch_shift(channel, sr=sample_rate, n_steps=semitones),
    )


def _split_key_name(key_name: str) -> tuple[str, str]:
    if not key_name or " " not in key_name:
        raise AudioProcessingError(f"Invalid key name: {key_name}")
    note_name, mode = key_name.rsplit(" ", 1)
    if note_name not in NOTE_NAMES:
        raise AudioProcessingError(f"Unsupported key root: {note_name}")
    if mode not in {"Major", "Minor"}:
        raise AudioProcessingError(f"Unsupported key mode: {mode}")
    return note_name, mode


def calculate_semitones(source_key: str, target_key: str) -> tuple[int, bool]:
    source_note, source_mode = _split_key_name(source_key)
    target_note, target_mode = _split_key_name(target_key)
    semitones = NOTE_NAMES.index(target_note) - NOTE_NAMES.index(source_note)
    while semitones > 6:
        semitones -= 12
    while semitones < -6:
        semitones += 12
    return semitones, source_mode == target_mode


def match_song_tempo(
    song: SongRecord,
    target_bpm: float,
    log_callback: LogCallback = None,
) -> dict[str, float | str]:
    if target_bpm <= 0:
        raise AudioProcessingError("Target BPM must be greater than zero.")

    source_bpm = song.bpm
    source_path = song.processed_path or song.file_path
    if source_bpm is None or source_bpm <= 0:
        analysis = analyze_audio(source_path)
        source_bpm = float(analysis["bpm"] or 0)
        song.duration = float(analysis["duration"] or 0)
        song.bpm = source_bpm
        if not song.musical_key:
            song.musical_key = analysis["key"]

    if source_bpm <= 0:
        raise AudioProcessingError(f"BPM detection failed for {song.file_name}.")

    if abs(source_bpm - target_bpm) < 0.01:
        _log(log_callback, f"{song.file_name} already matches the target BPM.")
        duration = song.duration or 0.0
        return {"output_path": source_path, "duration": duration, "bpm": target_bpm}

    audio, sample_rate = _load_audio_for_processing(source_path)
    rate = target_bpm / source_bpm
    stretched = _time_stretch(audio, sample_rate, rate, log_callback=log_callback)
    output_dir = make_song_cache_dir(song.file_path, song.file_name, "processed")
    suffix = f"tempo_{int(round(target_bpm))}bpm"
    output_path = Path(output_dir) / build_output_filename(song.file_name, suffix, ".wav")
    saved_path = _save_audio(output_path, stretched, sample_rate)
    duration = float(stretched.shape[-1] / sample_rate)
    return {"output_path": saved_path, "duration": duration, "bpm": target_bpm}


def match_song_key(
    song: SongRecord,
    target_key: str,
    log_callback: LogCallback = None,
) -> dict[str, float | str | bool]:
    if not target_key:
        raise AudioProcessingError("Target key is required.")

    source_key = song.musical_key
    source_path = song.processed_path or song.file_path
    if not source_key:
        analysis = analyze_audio(source_path)
        source_key = str(analysis["key"] or "")
        song.duration = float(analysis["duration"] or 0)
        if not song.bpm:
            song.bpm = float(analysis["bpm"] or 0)
        song.musical_key = source_key

    if not source_key:
        raise AudioProcessingError(f"Key detection failed for {song.file_name}.")

    _, source_mode = _split_key_name(source_key)
    target_note, _ = _split_key_name(target_key)
    semitones, same_mode = calculate_semitones(source_key, target_key)
    resolved_key = target_key if same_mode else f"{target_note} {source_mode}"
    if semitones == 0:
        if not same_mode:
            _log(
                log_callback,
                f"{song.file_name} already shares the target tonic, but pitch shifting cannot change the mode from {source_mode}.",
            )
        else:
            _log(log_callback, f"{song.file_name} already matches the target key.")
        duration = song.duration or 0.0
        return {"output_path": source_path, "duration": duration, "key": resolved_key, "mode_matched": same_mode}

    audio, sample_rate = _load_audio_for_processing(source_path)
    shifted = _pitch_shift(audio, sample_rate, semitones, log_callback=log_callback)
    output_dir = make_song_cache_dir(song.file_path, song.file_name, "processed")
    suffix = f"key_{safe_stem(target_key)}"
    output_path = Path(output_dir) / build_output_filename(song.file_name, suffix, ".wav")
    saved_path = _save_audio(output_path, shifted, sample_rate)
    duration = float(shifted.shape[-1] / sample_rate)
    if not same_mode:
        _log(
            log_callback,
            f"{song.file_name} was shifted to the target tonic, but the mode remains {source_mode}.",
        )
    return {"output_path": saved_path, "duration": duration, "key": resolved_key, "mode_matched": same_mode}


def _find_stem_directory(search_root: str | Path) -> Path:
    root = Path(search_root)
    stem_files = ["vocals.wav", "no_vocals.wav", "drums.wav", "bass.wav", "other.wav"]
    for stem_name in stem_files:
        candidates = list(root.rglob(stem_name))
        if candidates:
            return candidates[-1].parent
    raise AudioProcessingError("Demucs finished without producing any expected stem files.")


def separate_song_stems(
    song: SongRecord,
    stem_option: str,
    log_callback: LogCallback = None,
    cancel_callback: CancelCallback = None,
) -> dict[str, str]:
    issues = action_runtime_issues("separate")
    if issues:
        raise DependencyError(" ".join(issues))

    stem_root = Path(make_song_cache_dir(song.file_path, song.file_name, "stems"))
    run_root = stem_root / safe_stem(stem_option.lower())
    ensure_directory(run_root)

    command = [sys.executable, "-m", "demucs.separate", "-o", str(run_root)]
    if stem_option in {"Vocals", "Instrumental / No vocals"}:
        command.extend(["--two-stems", "vocals"])
    command.append(song.file_path)

    _log(log_callback, f"Running Demucs for {song.file_name}...")
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        while process.poll() is None:
            if cancel_callback and cancel_callback():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                raise TaskCanceledError("Task canceled by user.")
            time.sleep(0.25)
        _, error_text = process.communicate()
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        raise

    if process.returncode != 0:
        message = (error_text or "").strip() or "Demucs failed without an error message."
        raise AudioProcessingError(f"Demucs failed for {song.file_name}: {message}")

    stem_dir = _find_stem_directory(run_root)
    selected_files = {
        "Vocals": ["vocals.wav"],
        "Instrumental / No vocals": ["no_vocals.wav"],
        "Drums": ["drums.wav"],
        "Bass": ["bass.wav"],
        "Other": ["other.wav"],
        "All stems": ["vocals.wav", "no_vocals.wav", "drums.wav", "bass.wav", "other.wav"],
    }

    if stem_option == "All stems":
        _log(log_callback, f"Stem separation finished for {song.file_name}.")
        return {"stems_dir": str(stem_dir)}

    filtered_dir = stem_root / "selected" / safe_stem(stem_option)
    ensure_directory(filtered_dir)
    copied_any = False
    for stem_name in selected_files[stem_option]:
        source = stem_dir / stem_name
        if source.exists():
            shutil.copy2(source, filtered_dir / stem_name)
            copied_any = True

    if not copied_any:
        raise AudioProcessingError(f"Requested stem output was not found for {song.file_name}.")

    _log(log_callback, f"Stem separation finished for {song.file_name}.")
    return {"stems_dir": str(filtered_dir)}


def export_song_artifacts(song: SongRecord, output_dir: str) -> dict[str, object]:
    export_root = ensure_directory(output_dir)
    exported_paths: list[str] = []
    copied_original_only = False

    if song.processed_path and Path(song.processed_path).exists():
        exported_paths.append(copy_file_to_directory(song.processed_path, export_root))

    if song.stems_dir and Path(song.stems_dir).exists():
        folder_name = f"{safe_stem(Path(song.file_name).stem)}_stems"
        exported_paths.append(copy_directory_to_directory(song.stems_dir, export_root, name=folder_name))

    if not exported_paths:
        copied_original_only = True
        exported_paths.append(copy_file_to_directory(song.file_path, export_root))

    return {
        "paths": exported_paths,
        "copied_original_only": copied_original_only,
    }
