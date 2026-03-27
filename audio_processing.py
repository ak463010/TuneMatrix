from __future__ import annotations

from functools import lru_cache
import importlib.util
import shutil
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

try:
    import torch as th
except Exception as exc:  # pragma: no cover - dependency dependent
    th = None
    TORCH_IMPORT_ERROR = str(exc)
else:
    TORCH_IMPORT_ERROR = None

from models import SongRecord
from utils import (
    NOTE_NAMES,
    build_output_filename,
    copy_directory_to_directory,
    copy_file_to_directory,
    ensure_directory,
    find_executable,
    format_dependency_status,
    key_filename_fragment,
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
STEM_OUTPUT_FILES = {
    "Vocals": "vocals.wav",
    "Instrumental / No vocals": "no_vocals.wav",
    "Drums": "drums.wav",
    "Bass": "bass.wav",
    "Other": "other.wav",
}


def get_dependency_report() -> dict[str, dict[str, Optional[str]]]:
    return {
        "librosa": {"available": librosa is not None, "detail": LIBROSA_IMPORT_ERROR},
        "numpy": {"available": np is not None, "detail": NUMPY_IMPORT_ERROR},
        "soundfile": {"available": sf is not None, "detail": SOUND_FILE_IMPORT_ERROR},
        "pyrubberband": {"available": pyrb is not None, "detail": PYRUBBERBAND_IMPORT_ERROR},
        "torch": {"available": importlib.util.find_spec("torch") is not None, "detail": None},
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
        if not report["numpy"]["available"]:
            issues.append("NumPy is required for stem separation.")
        if not report["librosa"]["available"]:
            issues.append("librosa is required for stem separation.")
        if not report["soundfile"]["available"]:
            issues.append("soundfile is required to write separated stems.")

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


def _require_torch_stack() -> None:
    if th is None:
        detail = f": {TORCH_IMPORT_ERROR}" if TORCH_IMPORT_ERROR else ""
        raise DependencyError(f"PyTorch is not available{detail}")


def _require_decode_support(file_path: str) -> None:
    if _decode_support_required(file_path) and find_executable("ffmpeg") is None:
        suffix = Path(file_path).suffix.lower()
        raise DependencyError(f"ffmpeg is required to decode {suffix} files. Install ffmpeg or use wav/flac.")


def normalize_bpm_to_range_hint(
    bpm: Optional[float],
    bpm_range_hint: Optional[tuple[float, float]],
) -> Optional[float]:
    if bpm is None or bpm <= 0 or bpm_range_hint is None:
        return bpm

    min_bpm, max_bpm = bpm_range_hint
    if min_bpm <= 0 or max_bpm <= 0 or min_bpm >= max_bpm:
        return bpm

    candidates = [float(bpm * (2**shift)) for shift in range(-3, 4)]
    in_range = [candidate for candidate in candidates if min_bpm <= candidate <= max_bpm]
    if in_range:
        return min(in_range, key=lambda candidate: abs(candidate - bpm))

    def distance_to_range(candidate: float) -> float:
        if candidate < min_bpm:
            return min_bpm - candidate
        if candidate > max_bpm:
            return candidate - max_bpm
        return 0.0

    return min(candidates, key=lambda candidate: (distance_to_range(candidate), abs(candidate - bpm)))


def analyze_audio(
    file_path: str,
    bpm_range_hint: Optional[tuple[float, float]] = None,
    key_hint: Optional[str] = None,
) -> dict[str, object]:
    _require_analysis_stack()
    _require_decode_support(file_path)

    audio, sample_rate = librosa.load(file_path, sr=None, mono=True)
    duration = float(librosa.get_duration(y=audio, sr=sample_rate))
    tempo, _ = librosa.beat.beat_track(y=audio, sr=sample_rate)
    bpm = float(np.asarray(tempo).reshape(-1)[0]) if tempo is not None else None
    bpm = normalize_bpm_to_range_hint(bpm, bpm_range_hint)
    key_name = detect_key(audio, sample_rate, key_hint=key_hint)
    relative_key = get_relative_key(key_name)
    compatible_keys = get_compatible_keys(key_name)
    return {
        "duration": duration,
        "bpm": bpm,
        "key": key_name,
        "relative_key": relative_key,
        "compatible_keys": compatible_keys,
    }


def detect_key(audio: "np.ndarray", sample_rate: int, key_hint: Optional[str] = None) -> Optional[str]:
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

    scored_keys: dict[str, float] = {}
    for note_index, note_name in enumerate(NOTE_NAMES):
        major_score = float(np.dot(pitch_profile, np.roll(major_template, note_index)))
        minor_score = float(np.dot(pitch_profile, np.roll(minor_template, note_index)))
        scored_keys[f"{note_name} Major"] = major_score
        scored_keys[f"{note_name} Minor"] = minor_score

    best_key = max(scored_keys, key=scored_keys.get)
    best_score = scored_keys[best_key]

    if key_hint and key_hint in scored_keys:
        key_hint_score = scored_keys[key_hint]
        margin = max(0.0025, abs(best_score) * 0.02)
        if best_score - key_hint_score <= margin:
            return key_hint
    return best_key


def _load_audio_for_processing(file_path: str) -> tuple["np.ndarray", int]:
    _require_analysis_stack()
    _require_decode_support(file_path)
    audio, sample_rate = librosa.load(file_path, sr=None, mono=False)
    return np.asarray(audio, dtype=np.float32), sample_rate


def _prepare_audio_channels(audio: "np.ndarray", target_channels: int) -> "np.ndarray":
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        audio = np.expand_dims(audio, axis=0)

    if audio.shape[0] == target_channels:
        return audio
    if target_channels == 1:
        return np.mean(audio, axis=0, keepdims=True, dtype=np.float32)
    if audio.shape[0] == 1:
        return np.repeat(audio, target_channels, axis=0).astype(np.float32)
    if audio.shape[0] > target_channels:
        return audio[:target_channels].astype(np.float32)

    repeats = int(np.ceil(target_channels / audio.shape[0]))
    tiled = np.tile(audio, (repeats, 1))
    return tiled[:target_channels].astype(np.float32)


@lru_cache(maxsize=2)
def _load_demucs_model(model_name: str = "htdemucs"):
    _require_torch_stack()
    if importlib.util.find_spec("demucs") is None:
        raise DependencyError("Demucs is not installed.")

    try:
        from demucs.pretrained import get_model
    except Exception as exc:  # pragma: no cover - dependency dependent
        raise DependencyError(f"Could not import Demucs pretrained loader: {exc}") from exc

    try:
        model = get_model(model_name)
    except Exception as exc:
        raise AudioProcessingError(
            f"Could not load the Demucs model `{model_name}`. Ensure the model files are available. {exc}"
        ) from exc

    model.cpu()
    model.eval()
    return model


def _apply_demucs_chunk(model, mix_chunk, device, segment: Optional[float] = None):
    from demucs.apply import TensorChunk, tensor_chunk
    from demucs.htdemucs import HTDemucs
    from demucs.utils import center_trim

    chunk = tensor_chunk(mix_chunk)
    assert isinstance(chunk, TensorChunk)
    length = chunk.length

    valid_length: int
    if isinstance(model, HTDemucs) and segment is not None:
        valid_length = int(segment * model.samplerate)
    elif hasattr(model, "valid_length"):
        valid_length = model.valid_length(length)  # type: ignore[attr-defined]
    else:
        valid_length = length

    padded_mix = chunk.padded(valid_length).to(device)
    with th.no_grad():
        out = model(padded_mix)
    assert isinstance(out, th.Tensor)
    return center_trim(out, length)


def _apply_demucs_model_with_cancel(
    model,
    mix: "th.Tensor",
    cancel_callback: CancelCallback = None,
    device=None,
    overlap: float = 0.25,
    transition_power: float = 1.0,
    segment: Optional[float] = None,
) -> "th.Tensor":
    from demucs.apply import BagOfModels, TensorChunk, tensor_chunk

    if device is None:
        device = mix.device
    else:
        device = th.device(device)

    _check_canceled(cancel_callback)

    if isinstance(model, BagOfModels):
        estimates: th.Tensor | float = 0.0
        totals = [0.0] * len(model.sources)
        for sub_model, model_weights in zip(model.models, model.weights):
            _check_canceled(cancel_callback)
            try:
                original_device = next(iter(sub_model.parameters())).device
            except StopIteration:
                original_device = device
            sub_model.to(device)
            out = _apply_demucs_model_with_cancel(
                sub_model,
                mix,
                cancel_callback=cancel_callback,
                device=device,
                overlap=overlap,
                transition_power=transition_power,
                segment=segment,
            )
            sub_model.to(original_device)
            for source_index, instrument_weight in enumerate(model_weights):
                out[:, source_index, :, :] *= instrument_weight
                totals[source_index] += instrument_weight
            estimates += out

        assert isinstance(estimates, th.Tensor)
        for source_index in range(estimates.shape[1]):
            estimates[:, source_index, :, :] /= totals[source_index]
        return estimates

    model.to(device)
    model.eval()
    assert transition_power >= 1.0, "transition_power < 1 leads to weird behavior."

    batch, channels, length = mix.shape
    if segment is None:
        segment = model.segment
    assert segment is not None and segment > 0.0

    segment_length = int(model.samplerate * segment)
    stride = max(1, int((1 - overlap) * segment_length))
    offsets = range(0, length, stride)
    weight = th.cat(
        [
            th.arange(1, segment_length // 2 + 1, device=device),
            th.arange(segment_length - segment_length // 2, 0, -1, device=device),
        ]
    )
    weight = (weight / weight.max()) ** transition_power

    mix_chunk = tensor_chunk(mix)
    assert isinstance(mix_chunk, TensorChunk)
    out = th.zeros(batch, len(model.sources), channels, length, device=mix.device)
    sum_weight = th.zeros(length, device=mix.device)

    for offset in offsets:
        _check_canceled(cancel_callback)
        chunk = TensorChunk(mix_chunk, offset, segment_length)
        chunk_out = _apply_demucs_chunk(model, chunk, device=device, segment=segment)
        chunk_length = chunk_out.shape[-1]
        out[..., offset : offset + segment_length] += (weight[:chunk_length] * chunk_out).to(mix.device)
        sum_weight[offset : offset + segment_length] += weight[:chunk_length].to(mix.device)

    assert sum_weight.min() > 0
    out /= sum_weight
    return out


def _run_demucs_in_process(
    file_path: str,
    log_callback: LogCallback = None,
    cancel_callback: CancelCallback = None,
    model_name: str = "htdemucs",
) -> tuple[dict[str, "np.ndarray"], int]:
    _require_analysis_stack()
    _require_audio_write_stack()
    _require_torch_stack()
    _require_decode_support(file_path)
    _check_canceled(cancel_callback)

    model = _load_demucs_model(model_name)
    _log(log_callback, f"Loaded Demucs model `{model_name}`.")
    _check_canceled(cancel_callback)

    audio, _ = librosa.load(file_path, sr=model.samplerate, mono=False)
    prepared_audio = _prepare_audio_channels(audio, model.audio_channels)
    mix = th.from_numpy(prepared_audio)

    ref = mix.mean(0)
    ref_mean = ref.mean()
    mix = mix - ref_mean
    ref_std = ref.std()
    scale = float(ref_std.item()) if ref_std.numel() else 0.0
    if scale > 1e-8:
        mix = mix / scale

    device = "cuda" if th.cuda.is_available() else "cpu"
    _log(log_callback, f"Running Demucs on {device.upper()} for {Path(file_path).name}.")
    sources = _apply_demucs_model_with_cancel(
        model,
        mix[None],
        cancel_callback=cancel_callback,
        device=device,
        overlap=0.25,
    )[0]

    _check_canceled(cancel_callback)
    if scale > 1e-8:
        sources = sources * scale
    sources = sources + ref_mean

    source_arrays = sources.detach().cpu().numpy().astype(np.float32)
    stems: dict[str, np.ndarray] = {}
    for index, source_name in enumerate(model.sources):
        stems[source_name] = source_arrays[index]

    if "vocals" in stems:
        non_vocal_names = [name for name in model.sources if name != "vocals"]
        if non_vocal_names:
            stems["no_vocals"] = np.sum([stems[name] for name in non_vocal_names], axis=0, dtype=np.float32)

    return stems, int(model.samplerate)


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


def _run_per_channel(
    audio: "np.ndarray",
    processor: Callable[["np.ndarray"], "np.ndarray"],
    cancel_callback: CancelCallback = None,
) -> "np.ndarray":
    if audio.ndim == 1:
        _check_canceled(cancel_callback)
        return np.asarray(processor(audio), dtype=np.float32)

    channels = []
    for channel in audio:
        _check_canceled(cancel_callback)
        channels.append(np.asarray(processor(channel), dtype=np.float32))
    _check_canceled(cancel_callback)
    min_length = min(channel.shape[-1] for channel in channels)
    trimmed = [channel[:min_length] for channel in channels]
    return np.vstack(trimmed).astype(np.float32)


def _time_stretch(
    audio: "np.ndarray",
    sample_rate: int,
    rate: float,
    log_callback: LogCallback = None,
    cancel_callback: CancelCallback = None,
) -> "np.ndarray":
    if rate <= 0:
        raise AudioProcessingError("Time-stretch rate must be greater than zero.")

    if pyrb is not None and find_executable("rubberband"):
        _log(log_callback, "Using Rubber Band for tempo matching.")
        return _run_per_channel(
            audio,
            lambda channel: pyrb.time_stretch(channel, sample_rate, rate),
            cancel_callback=cancel_callback,
        )

    if librosa is None:
        raise DependencyError("Neither Rubber Band nor librosa are available for tempo matching.")

    _log(log_callback, "Rubber Band not found. Falling back to librosa for tempo matching.")
    return _run_per_channel(
        audio,
        lambda channel: librosa.effects.time_stretch(channel, rate=rate),
        cancel_callback=cancel_callback,
    )


def _pitch_shift(
    audio: "np.ndarray",
    sample_rate: int,
    semitones: float,
    log_callback: LogCallback = None,
    cancel_callback: CancelCallback = None,
) -> "np.ndarray":
    if abs(semitones) < 1e-6:
        return audio

    if pyrb is not None and find_executable("rubberband"):
        _log(log_callback, "Using Rubber Band for key matching.")
        return _run_per_channel(
            audio,
            lambda channel: pyrb.pitch_shift(channel, sample_rate, semitones),
            cancel_callback=cancel_callback,
        )

    if librosa is None:
        raise DependencyError("Neither Rubber Band nor librosa are available for key matching.")

    _log(log_callback, "Rubber Band not found. Falling back to librosa for key matching.")
    return _run_per_channel(
        audio,
        lambda channel: librosa.effects.pitch_shift(channel, sr=sample_rate, n_steps=semitones),
        cancel_callback=cancel_callback,
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


def _build_key_name(note_index: int, mode: str) -> str:
    return f"{NOTE_NAMES[note_index % len(NOTE_NAMES)]} {mode}"


def get_relative_key(key_name: Optional[str]) -> Optional[str]:
    if not key_name:
        return None
    note_name, mode = _split_key_name(key_name)
    note_index = NOTE_NAMES.index(note_name)
    if mode == "Major":
        return _build_key_name(note_index + 9, "Minor")
    return _build_key_name(note_index + 3, "Major")


def get_compatible_keys(key_name: Optional[str]) -> list[str]:
    if not key_name:
        return []

    note_name, mode = _split_key_name(key_name)
    note_index = NOTE_NAMES.index(note_name)
    relative_key = get_relative_key(key_name)
    clockwise_index = note_index + 7
    counterclockwise_index = note_index - 7
    clockwise_same_mode = _build_key_name(clockwise_index, mode)
    counterclockwise_same_mode = _build_key_name(counterclockwise_index, mode)
    clockwise_relative = get_relative_key(clockwise_same_mode)
    counterclockwise_relative = get_relative_key(counterclockwise_same_mode)

    ordered_candidates = [
        relative_key,
        clockwise_same_mode,
        clockwise_relative,
        counterclockwise_same_mode,
        counterclockwise_relative,
    ]
    compatible_keys: list[str] = []
    for candidate in ordered_candidates:
        if not candidate or candidate == key_name or candidate in compatible_keys:
            continue
        compatible_keys.append(candidate)
    return compatible_keys


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
    cancel_callback: CancelCallback = None,
) -> dict[str, float | str]:
    _check_canceled(cancel_callback)
    if target_bpm <= 0:
        raise AudioProcessingError("Target BPM must be greater than zero.")

    source_bpm = song.bpm
    source_path = song.processed_path or song.file_path
    if source_bpm is None or source_bpm <= 0:
        _check_canceled(cancel_callback)
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

    _check_canceled(cancel_callback)
    audio, sample_rate = _load_audio_for_processing(source_path)
    rate = target_bpm / source_bpm
    stretched = _time_stretch(audio, sample_rate, rate, log_callback=log_callback, cancel_callback=cancel_callback)
    output_dir = make_song_cache_dir(song.file_path, song.file_name, "processed")
    suffix = f"tempo_{int(round(target_bpm))}bpm"
    output_path = Path(output_dir) / build_output_filename(song.file_name, suffix, ".wav")
    _check_canceled(cancel_callback)
    saved_path = _save_audio(output_path, stretched, sample_rate)
    _check_canceled(cancel_callback)
    duration = float(stretched.shape[-1] / sample_rate)
    return {"output_path": saved_path, "duration": duration, "bpm": target_bpm}


def match_song_key(
    song: SongRecord,
    target_key: str,
    log_callback: LogCallback = None,
    cancel_callback: CancelCallback = None,
) -> dict[str, float | str | bool]:
    _check_canceled(cancel_callback)
    if not target_key:
        raise AudioProcessingError("Target key is required.")

    source_key = song.musical_key
    source_path = song.processed_path or song.file_path
    if not source_key:
        _check_canceled(cancel_callback)
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
        relative_key = get_relative_key(resolved_key)
        compatible_keys = get_compatible_keys(resolved_key)
        if not same_mode:
            _log(
                log_callback,
                f"{song.file_name} already shares the target tonic, but pitch shifting cannot change the mode from {source_mode}.",
            )
        else:
            _log(log_callback, f"{song.file_name} already matches the target key.")
        duration = song.duration or 0.0
        return {
            "output_path": source_path,
            "duration": duration,
            "key": resolved_key,
            "relative_key": relative_key,
            "compatible_keys": compatible_keys,
            "mode_matched": same_mode,
        }

    _check_canceled(cancel_callback)
    audio, sample_rate = _load_audio_for_processing(source_path)
    shifted = _pitch_shift(
        audio,
        sample_rate,
        semitones,
        log_callback=log_callback,
        cancel_callback=cancel_callback,
    )
    output_dir = make_song_cache_dir(song.file_path, song.file_name, "processed")
    suffix = f"key_{safe_stem(target_key)}"
    output_path = Path(output_dir) / build_output_filename(song.file_name, suffix, ".wav")
    _check_canceled(cancel_callback)
    saved_path = _save_audio(output_path, shifted, sample_rate)
    _check_canceled(cancel_callback)
    duration = float(shifted.shape[-1] / sample_rate)
    if not same_mode:
        _log(
            log_callback,
            f"{song.file_name} was shifted to the target tonic, but the mode remains {source_mode}.",
        )
    return {
        "output_path": saved_path,
        "duration": duration,
        "key": resolved_key,
        "relative_key": get_relative_key(resolved_key),
        "compatible_keys": get_compatible_keys(resolved_key),
        "mode_matched": same_mode,
    }


def separate_song_stems(
    song: SongRecord,
    stem_option: str,
    selected_stems: Optional[list[str]] = None,
    log_callback: LogCallback = None,
    cancel_callback: CancelCallback = None,
) -> dict[str, str]:
    source_path = song.processed_path or song.file_path
    issues = action_runtime_issues("separate", [source_path])
    if issues:
        raise DependencyError(" ".join(issues))

    stem_root = Path(make_song_cache_dir(song.file_path, song.file_name, "stems"))
    run_root = stem_root / safe_stem(stem_option.lower())
    stem_dir = run_root / safe_stem(Path(song.file_name).stem)
    ensure_directory(stem_dir)

    _log(log_callback, f"Running Demucs for {song.file_name}...")
    stems, sample_rate = _run_demucs_in_process(
        source_path,
        log_callback=log_callback,
        cancel_callback=cancel_callback,
    )

    for stem_name, audio_data in stems.items():
        _save_audio(stem_dir / f"{stem_name}.wav", audio_data, sample_rate)

    if selected_stems is not None:
        normalized_selection = [stem_name for stem_name in selected_stems if stem_name in STEM_OUTPUT_FILES]
    elif stem_option == "All stems":
        normalized_selection = list(STEM_OUTPUT_FILES)
    else:
        normalized_selection = [stem_option] if stem_option in STEM_OUTPUT_FILES else []

    if selected_stems is not None and not normalized_selection:
        raise AudioProcessingError(f"No valid stem outputs were selected for {song.file_name}.")

    if set(normalized_selection) == set(STEM_OUTPUT_FILES):
        _log(log_callback, f"Stem separation finished for {song.file_name}.")
        return {"stems_dir": str(stem_dir)}

    filter_name = "_".join(safe_stem(stem_name) for stem_name in normalized_selection)
    filtered_dir = stem_root / "selected" / safe_stem(filter_name)
    ensure_directory(filtered_dir)
    copied_any = False
    for stem_name in normalized_selection:
        source = stem_dir / STEM_OUTPUT_FILES[stem_name]
        if source.exists():
            shutil.copy2(source, filtered_dir / source.name)
            copied_any = True

    if not copied_any:
        raise AudioProcessingError(f"Requested stem output was not found for {song.file_name}.")

    _log(log_callback, f"Stem separation finished for {song.file_name}.")
    return {"stems_dir": str(filtered_dir)}


def _export_processed_filename(song: SongRecord, key_display_preference: Optional[str] = None) -> Optional[str]:
    if not song.processed_path:
        return None

    source_path = Path(song.processed_path)
    file_name = source_path.name
    if "_key_" not in source_path.stem:
        return file_name

    resolved_key = song.musical_key or song.processing_target_key
    if not resolved_key:
        return file_name

    suffix = f"key_{key_filename_fragment(resolved_key, key_display_preference)}"
    return build_output_filename(song.file_name, suffix, source_path.suffix or ".wav")


def export_song_artifacts(song: SongRecord, output_dir: str, key_display_preference: Optional[str] = None) -> dict[str, object]:
    export_root = ensure_directory(output_dir)
    exported_paths: list[str] = []
    copied_original_only = False

    if song.processed_path and Path(song.processed_path).exists():
        export_name = _export_processed_filename(song, key_display_preference)
        exported_paths.append(copy_file_to_directory(song.processed_path, export_root, name=export_name))

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
