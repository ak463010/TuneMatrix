from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from audio_processing import (
    AudioProcessingError,
    TaskCanceledError,
    analyze_audio,
    export_song_artifacts,
    get_compatible_keys,
    get_relative_key,
    match_song_key,
    match_song_tempo,
    separate_song_stems,
)
from models import (
    ProcessingOptions,
    SongRecord,
    SongStatus,
    WORKFLOW_STEP_LABELS,
    bpm_hint_from_label,
    normalize_processing_mode,
)
from models import STEM_SOURCE_LATEST, STEM_SOURCE_ORIGINAL, normalize_stem_source
from utils import ensure_directory, make_song_cache_dir


class BaseWorker(QObject):
    progress = Signal(int)
    log = Signal(str)
    song_updated = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._cancel_requested = False

    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True
        self.log.emit("Cancellation requested.")

    def is_canceled(self) -> bool:
        return self._cancel_requested

    def check_canceled(self) -> None:
        if self._cancel_requested:
            raise TaskCanceledError("Task canceled by user.")

    def update_song_status(self, song: SongRecord, status: str, last_error: Optional[str] = None) -> None:
        song.status = status
        song.last_error = last_error
        self.song_updated.emit(song)

    def apply_analysis_metadata(self, song: SongRecord, result: dict[str, object]) -> None:
        song.duration = float(result.get("duration") or 0.0)
        song.bpm = float(result.get("bpm") or 0.0)
        song.musical_key = str(result.get("key") or "")
        song.relative_key = str(result.get("relative_key") or "") or None
        song.compatible_keys = list(result.get("compatible_keys") or [])

    def ensure_key_relationships(self, song: SongRecord) -> None:
        if not song.musical_key:
            song.relative_key = None
            song.compatible_keys = []
            return
        song.relative_key = get_relative_key(song.musical_key)
        song.compatible_keys = get_compatible_keys(song.musical_key)


class AnalyzeWorker(BaseWorker):
    def __init__(self, songs: list[SongRecord]) -> None:
        super().__init__()
        self.songs = songs

    @Slot()
    def run(self) -> None:
        try:
            self._run_impl()
        except TaskCanceledError as exc:
            self.log.emit(str(exc))
        except Exception as exc:
            self.error.emit(str(exc))
            self.log.emit(f"Analyze task failed: {exc}")
        finally:
            self.finished.emit()

    def _run_impl(self) -> None:
        total = len(self.songs)
        if total == 0:
            self.log.emit("No songs available for analysis.")
            self.progress.emit(0)
            return

        self.log.emit(f"Starting analysis for {total} song(s).")
        successful = 0
        for index, song in enumerate(self.songs, start=1):
            self.check_canceled()
            previous_status = song.status
            self.update_song_status(song, SongStatus.ANALYZING.value)

            try:
                bpm_hint = bpm_hint_from_label(song.bpm_range_label)
                if bpm_hint and bpm_hint.exact_bpm is not None:
                    self.log.emit(f"{song.file_name}: using exact BPM hint {bpm_hint.exact_bpm:g} BPM.")
                elif bpm_hint and bpm_hint.bpm_range is not None:
                    self.log.emit(
                        f"{song.file_name}: using BPM range hint {bpm_hint.bpm_range[0]:g}-{bpm_hint.bpm_range[1]:g} BPM."
                    )
                if song.analysis_key_hint:
                    self.log.emit(f"{song.file_name}: using key hint {song.analysis_key_hint}.")
                result = analyze_audio(
                    song.file_path,
                    bpm_hint=bpm_hint,
                    key_hint=song.analysis_key_hint,
                )
                self.apply_analysis_metadata(song, result)
                song.last_error = None
                if previous_status == SongStatus.EXPORTED.value:
                    song.status = SongStatus.EXPORTED.value
                else:
                    song.status = SongStatus.ANALYZED.value
                successful += 1
                self.log.emit(
                    f"Analyzed {song.file_name}: {song.duration:.1f}s, {song.bpm:.1f} BPM, {song.musical_key or 'unknown key'}."
                )
            except Exception as exc:
                song.status = SongStatus.ERROR.value
                song.last_error = str(exc)
                self.log.emit(f"Analyze failed for {song.file_name}: {exc}")

            self.song_updated.emit(song)
            self.progress.emit(int(index / total * 100))

        self.log.emit(f"Analysis finished. Updated {successful}/{total} song(s).")


class ProcessingWorker(BaseWorker):
    def __init__(
        self,
        songs: list[SongRecord],
        options: ProcessingOptions,
        action: str,
    ) -> None:
        super().__init__()
        self.songs = songs
        self.options = options
        self.action = action

    def _action_label(self) -> str:
        if self.action == "process_all":
            return "Workflow"
        return self.action.replace("_", " ").title()

    @Slot()
    def run(self) -> None:
        try:
            self._run_impl()
        except TaskCanceledError as exc:
            self.log.emit(str(exc))
        except Exception as exc:
            self.error.emit(str(exc))
            self.log.emit(f"{self._action_label()} task failed: {exc}")
        finally:
            self.finished.emit()

    def _run_impl(self) -> None:
        total = len(self.songs)
        if total == 0:
            self.log.emit("No songs selected.")
            self.progress.emit(0)
            return

        self.log.emit(f"Starting {self._action_label().lower()} for {total} song(s).")
        for index, song in enumerate(self.songs, start=1):
            self.check_canceled()
            song_target_bpm = self._effective_target_bpm(song)
            song_target_key = self._effective_target_key(song)

            try:
                if self.action == "separate":
                    self._separate(song)
                    self._auto_export(song)
                elif self.action == "match_tempo":
                    self._match_tempo(song, song_target_bpm)
                    self._auto_export(song)
                elif self.action == "match_key":
                    self._match_key(song, song_target_key)
                    self._auto_export(song)
                elif self.action == "process_all":
                    self._run_workflow(song, song_target_bpm, song_target_key)
                    self._auto_export(song)
                elif self.action == "export":
                    self._export(song)
                else:
                    raise AudioProcessingError(f"Unknown worker action: {self.action}")
            except TaskCanceledError:
                song.status = SongStatus.CANCELED.value
                self.song_updated.emit(song)
                raise
            except Exception as exc:
                song.status = SongStatus.ERROR.value
                song.last_error = str(exc)
                self.song_updated.emit(song)
                self.log.emit(f"{self._action_label()} failed for {song.file_name}: {exc}")

            self.progress.emit(int(index / total * 100))

        self.log.emit(f"{self._action_label()} finished.")

    def _effective_target_bpm(self, song: SongRecord) -> Optional[float]:
        return song.processing_target_bpm

    def _effective_target_key(self, song: SongRecord) -> Optional[str]:
        return song.processing_target_key

    def _effective_processing_mode(self, song: SongRecord) -> str:
        return normalize_processing_mode(song.processing_mode)

    def _effective_stem_settings(self, song: SongRecord) -> tuple[Optional[str], Optional[list[str]]]:
        if not song.processing_selected_stems:
            return None, []
        selected_stems = list(song.processing_selected_stems)
        if len(selected_stems) == 1:
            return selected_stems[0], selected_stems
        return "All stems", selected_stems

    def _effective_stem_source(self, song: SongRecord) -> str:
        return normalize_stem_source(song.processing_stem_source)

    def _effective_tempo_source(self, song: SongRecord) -> str:
        return normalize_stem_source(song.processing_tempo_source)

    def _separation_source_path(self, song: SongRecord, latest_available_path: Optional[str] = None) -> str:
        if self._effective_stem_source(song) == STEM_SOURCE_ORIGINAL:
            return song.file_path
        return latest_available_path or song.processed_path or song.file_path

    def _tempo_source_path(self, song: SongRecord, latest_available_path: Optional[str] = None) -> str:
        if self._effective_tempo_source(song) == STEM_SOURCE_ORIGINAL:
            return song.file_path
        return latest_available_path or song.processed_path or song.file_path

    def _workflow_steps(self) -> list[str]:
        return list(self.options.workflow_steps or [])

    def _ensure_song_analysis(self, song: SongRecord) -> None:
        if song.duration is not None and song.bpm is not None and song.musical_key:
            self.ensure_key_relationships(song)
            return

        self.log.emit(f"Analyzing missing metadata for {song.file_name}.")
        result = analyze_audio(
            song.processed_path or song.file_path,
            bpm_hint=bpm_hint_from_label(song.bpm_range_label),
            key_hint=song.analysis_key_hint,
        )
        if song.duration is None:
            song.duration = float(result.get("duration") or 0.0)
        if song.bpm is None or song.bpm <= 0:
            song.bpm = float(result.get("bpm") or 0.0)
        if not song.musical_key:
            song.musical_key = str(result.get("key") or "")
        song.relative_key = str(result.get("relative_key") or "") or None
        song.compatible_keys = list(result.get("compatible_keys") or [])
        if song.status != SongStatus.ERROR.value:
            song.status = SongStatus.ANALYZED.value
            song.last_error = None
        self.song_updated.emit(song)

    def _separate(self, song: SongRecord, source_path: Optional[str] = None) -> None:
        stem_option, selected_stems = self._effective_stem_settings(song)
        if stem_option is None:
            raise AudioProcessingError("Select at least one stem before running Separate Stems.")
        self.update_song_status(song, SongStatus.SEPARATING.value)
        result = separate_song_stems(
            song,
            stem_option,
            source_path=source_path or self._separation_source_path(song),
            selected_stems=selected_stems,
            log_callback=self.log.emit,
            cancel_callback=self.is_canceled,
        )
        song.stems_dir = str(result["stems_dir"])
        song.status = SongStatus.READY.value
        song.last_error = None
        self.song_updated.emit(song)

    def _match_tempo(self, song: SongRecord, target_bpm: Optional[float], source_path: Optional[str] = None) -> None:
        if target_bpm is None:
            raise AudioProcessingError("Tempo matching needs a target BPM.")

        self.check_canceled()
        self.update_song_status(song, SongStatus.MATCHING_TEMPO.value)
        self._ensure_song_analysis(song)
        resolved_source_path = source_path or self._tempo_source_path(song)
        current_song_source_path = song.processed_path or song.file_path
        working_bpm = song.bpm if resolved_source_path == current_song_source_path else None
        working_song = self._make_temporary_song(resolved_source_path, song.file_name, working_bpm, song.musical_key)
        result = match_song_tempo(
            working_song,
            target_bpm,
            processing_mode=self._effective_processing_mode(song),
            log_callback=self.log.emit,
            cancel_callback=self.is_canceled,
        )
        song.processed_path = str(result["output_path"])
        song.duration = float(result["duration"])
        song.bpm = float(result["bpm"])
        song.status = SongStatus.READY.value
        song.last_error = None
        self.song_updated.emit(song)
        self.log.emit(f"Tempo matched for {song.file_name} -> {song.bpm:.1f} BPM.")

    def _match_key(self, song: SongRecord, target_key: Optional[str]) -> None:
        if not target_key:
            raise AudioProcessingError("Key matching needs a target key.")

        self.check_canceled()
        self.update_song_status(song, SongStatus.MATCHING_KEY.value)
        self._ensure_song_analysis(song)
        result = match_song_key(
            song,
            target_key,
            processing_mode=self._effective_processing_mode(song),
            log_callback=self.log.emit,
            cancel_callback=self.is_canceled,
        )
        song.processed_path = str(result["output_path"])
        song.duration = float(result["duration"])
        song.musical_key = str(result["key"])
        song.relative_key = str(result.get("relative_key") or "") or None
        song.compatible_keys = list(result.get("compatible_keys") or [])
        song.status = SongStatus.READY.value
        song.last_error = None
        self.song_updated.emit(song)
        if result.get("mode_matched", True):
            self.log.emit(f"Key matched for {song.file_name} -> {song.musical_key}.")
        else:
            self.log.emit(
                f"Pitch shifted {song.file_name} to {song.musical_key}; the requested mode could not be matched exactly."
            )

    def _make_temporary_song(
        self,
        source_path: str,
        display_name: str,
        bpm: Optional[float],
        musical_key: Optional[str],
    ) -> SongRecord:
        temp_song = SongRecord.from_path(source_path)
        temp_song.file_name = display_name
        temp_song.bpm = bpm
        temp_song.musical_key = musical_key
        return temp_song

    def _stem_paths_from_directory(self, stems_dir: str) -> dict[str, str]:
        stem_paths: dict[str, str] = {}
        for stem_path in sorted(Path(stems_dir).glob("*.wav")):
            stem_paths[stem_path.stem] = str(stem_path)
        return stem_paths

    def _processed_stem_output_dir(self, song: SongRecord, step_id: str) -> Path:
        workflow_root = Path(make_song_cache_dir(song.file_path, song.file_name, "workflow_stems"))
        step_root = workflow_root / step_id
        ensure_directory(step_root)
        existing_indices = [
            int(path.name.split("_")[-1])
            for path in step_root.iterdir()
            if path.is_dir() and path.name.startswith("run_") and path.name.split("_")[-1].isdigit()
        ]
        next_index = max(existing_indices, default=0) + 1
        run_dir = step_root / f"run_{next_index:02d}"
        ensure_directory(run_dir)
        return run_dir

    def _process_stems_for_tempo(
        self,
        song: SongRecord,
        current_stem_paths: dict[str, str],
        current_bpm: Optional[float],
        current_key: Optional[str],
        target_bpm: float,
    ) -> tuple[dict[str, str], float]:
        self.update_song_status(song, SongStatus.MATCHING_TEMPO.value)
        output_dir = self._processed_stem_output_dir(song, "match_tempo")
        processed_stem_paths: dict[str, str] = {}
        duration: Optional[float] = None

        for stem_name, stem_path in current_stem_paths.items():
            self.check_canceled()
            temp_song = self._make_temporary_song(stem_path, Path(stem_path).name, current_bpm, current_key)
            result = match_song_tempo(
                temp_song,
                target_bpm,
                processing_mode=self._effective_processing_mode(song),
                log_callback=self.log.emit,
                cancel_callback=self.is_canceled,
            )
            destination = output_dir / Path(stem_path).name
            shutil.copy2(result["output_path"], destination)
            processed_stem_paths[stem_name] = str(destination)
            if duration is None:
                duration = float(result["duration"])

        if duration is None:
            duration = song.duration or 0.0
        return processed_stem_paths, duration

    def _process_stems_for_key(
        self,
        song: SongRecord,
        current_stem_paths: dict[str, str],
        current_bpm: Optional[float],
        current_key: Optional[str],
        target_key: str,
    ) -> tuple[dict[str, str], float, str, Optional[str], list[str]]:
        self.update_song_status(song, SongStatus.MATCHING_KEY.value)
        output_dir = self._processed_stem_output_dir(song, "match_key")
        processed_stem_paths: dict[str, str] = {}
        duration: Optional[float] = None
        resolved_key = current_key or target_key
        relative_key: Optional[str] = None
        compatible_keys: list[str] = []

        for stem_name, stem_path in current_stem_paths.items():
            self.check_canceled()
            temp_song = self._make_temporary_song(stem_path, Path(stem_path).name, current_bpm, current_key)
            result = match_song_key(
                temp_song,
                target_key,
                processing_mode=self._effective_processing_mode(song),
                log_callback=self.log.emit,
                cancel_callback=self.is_canceled,
            )
            destination = output_dir / Path(stem_path).name
            shutil.copy2(result["output_path"], destination)
            processed_stem_paths[stem_name] = str(destination)
            if duration is None:
                duration = float(result["duration"])
                resolved_key = str(result["key"])
                relative_key = str(result.get("relative_key") or "") or None
                compatible_keys = list(result.get("compatible_keys") or [])

        if duration is None:
            duration = song.duration or 0.0
        return processed_stem_paths, duration, resolved_key, relative_key, compatible_keys

    def _run_workflow(self, song: SongRecord, target_bpm: Optional[float], target_key: Optional[str]) -> None:
        workflow_steps = self._workflow_steps()
        if not workflow_steps:
            raise AudioProcessingError("Enable at least one workflow step before running the workflow.")

        self.update_song_status(song, SongStatus.PROCESSING.value)
        self._ensure_song_analysis(song)

        current_mix_path = song.processed_path or song.file_path
        current_stem_paths: Optional[dict[str, str]] = None
        current_bpm = song.bpm
        current_key = song.musical_key

        for step_index, step_id in enumerate(workflow_steps, start=1):
            self.check_canceled()
            step_label = WORKFLOW_STEP_LABELS.get(step_id, step_id.replace("_", " ").title())
            self.log.emit(f"{song.file_name}: workflow step {step_index}/{len(workflow_steps)} - {step_label}.")

            if step_id == "match_key":
                if not target_key:
                    self.log.emit(f"{song.file_name}: skipping Match Key because no Target Key is set.")
                    continue
                if current_stem_paths is None:
                    working_song = self._make_temporary_song(current_mix_path, song.file_name, current_bpm, current_key)
                    self.update_song_status(song, SongStatus.MATCHING_KEY.value)
                    result = match_song_key(
                        working_song,
                        target_key,
                        processing_mode=self._effective_processing_mode(song),
                        log_callback=self.log.emit,
                        cancel_callback=self.is_canceled,
                    )
                    current_mix_path = str(result["output_path"])
                    song.processed_path = current_mix_path
                    song.duration = float(result["duration"])
                    current_key = str(result["key"])
                    song.musical_key = current_key
                    song.relative_key = str(result.get("relative_key") or "") or None
                    song.compatible_keys = list(result.get("compatible_keys") or [])
                    self.song_updated.emit(song)
                else:
                    processed_stem_paths, duration, resolved_key, relative_key, compatible_keys = self._process_stems_for_key(
                        song,
                        current_stem_paths,
                        current_bpm,
                        current_key,
                        target_key,
                    )
                    current_stem_paths = processed_stem_paths
                    song.stems_dir = str(Path(next(iter(processed_stem_paths.values()))).parent)
                    song.duration = duration
                    current_key = resolved_key
                    song.musical_key = resolved_key
                    song.relative_key = relative_key
                    song.compatible_keys = compatible_keys
                    self.song_updated.emit(song)
                continue

            if step_id == "match_tempo":
                if target_bpm is None:
                    self.log.emit(f"{song.file_name}: skipping Match Tempo because no Target BPM is set.")
                    continue
                if current_stem_paths is None:
                    tempo_source_path = self._tempo_source_path(song, current_mix_path)
                    working_bpm = current_bpm if tempo_source_path == current_mix_path else None
                    working_song = self._make_temporary_song(tempo_source_path, song.file_name, working_bpm, current_key)
                    self.update_song_status(song, SongStatus.MATCHING_TEMPO.value)
                    result = match_song_tempo(
                        working_song,
                        target_bpm,
                        processing_mode=self._effective_processing_mode(song),
                        log_callback=self.log.emit,
                        cancel_callback=self.is_canceled,
                    )
                    current_mix_path = str(result["output_path"])
                    song.processed_path = current_mix_path
                    song.duration = float(result["duration"])
                    current_bpm = float(result["bpm"])
                    song.bpm = current_bpm
                    self.song_updated.emit(song)
                else:
                    processed_stem_paths, duration = self._process_stems_for_tempo(
                        song,
                        current_stem_paths,
                        current_bpm,
                        current_key,
                        target_bpm,
                    )
                    current_stem_paths = processed_stem_paths
                    song.stems_dir = str(Path(next(iter(processed_stem_paths.values()))).parent)
                    song.duration = duration
                    current_bpm = target_bpm
                    song.bpm = current_bpm
                    self.song_updated.emit(song)
                continue

            if step_id == "separate":
                stem_option, _selected_stems = self._effective_stem_settings(song)
                if stem_option is None:
                    self.log.emit(f"{song.file_name}: skipping Separate Stems because no stems are selected.")
                    continue
                self._separate(song, source_path=self._separation_source_path(song, current_mix_path))
                current_stem_paths = self._stem_paths_from_directory(song.stems_dir or "")
                if not current_stem_paths:
                    raise AudioProcessingError(f"No stems were produced for {song.file_name}.")
                continue

            raise AudioProcessingError(f"Unsupported workflow step: {step_id}")

        song.status = SongStatus.READY.value
        song.last_error = None
        self.song_updated.emit(song)
        self.log.emit(f"Workflow finished for {song.file_name}.")

    def _has_exportable_artifacts(self, song: SongRecord) -> bool:
        return bool(
            (song.processed_path and Path(song.processed_path).exists())
            or (song.stems_dir and Path(song.stems_dir).exists())
        )

    def _auto_export(self, song: SongRecord) -> None:
        if not self.options.output_dir:
            raise AudioProcessingError("Choose an export folder before processing.")

        if not self._has_exportable_artifacts(song):
            return

        self.check_canceled()
        result = export_song_artifacts(song, self.options.output_dir, self.options.key_display_preference)
        song.status = SongStatus.EXPORTED.value
        song.last_error = None
        self.song_updated.emit(song)

        if result["copied_original_only"]:
            self.log.emit(f"Auto-export skipped for {song.file_name}: no processed artifacts were available.")
        else:
            self.log.emit(f"Auto-exported results for {song.file_name}.")

    def _export(self, song: SongRecord) -> None:
        if not self.options.output_dir:
            raise AudioProcessingError("Choose an export folder before exporting cached results.")

        self.check_canceled()
        self.update_song_status(song, SongStatus.PROCESSING.value)
        result = export_song_artifacts(song, self.options.output_dir, self.options.key_display_preference)
        song.status = SongStatus.EXPORTED.value
        song.last_error = None
        self.song_updated.emit(song)

        if result["copied_original_only"]:
            self.log.emit(f"Exported original file for {song.file_name} because no processed output was available.")
        else:
            self.log.emit(f"Exported artifacts for {song.file_name}.")
