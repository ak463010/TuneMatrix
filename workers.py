from __future__ import annotations

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
from models import ProcessingOptions, SongRecord, SongStatus, bpm_range_from_label


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
            self.update_song_status(song, SongStatus.ANALYZING.value)

            try:
                bpm_range_hint = bpm_range_from_label(song.bpm_range_label)
                if bpm_range_hint:
                    self.log.emit(
                        f"{song.file_name}: using BPM range hint {bpm_range_hint[0]:.0f}-{bpm_range_hint[1]:.0f} BPM."
                    )
                if song.analysis_key_hint:
                    self.log.emit(f"{song.file_name}: using key hint {song.analysis_key_hint}.")
                result = analyze_audio(
                    song.file_path,
                    bpm_range_hint=bpm_range_hint,
                    key_hint=song.analysis_key_hint,
                )
                self.apply_analysis_metadata(song, result)
                song.last_error = None
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
        all_songs: Optional[list[SongRecord]] = None,
    ) -> None:
        super().__init__()
        self.songs = songs
        self.options = options
        self.action = action
        self.song_lookup = {song.file_path: song for song in (all_songs or songs)}

    @Slot()
    def run(self) -> None:
        try:
            self._run_impl()
        except TaskCanceledError as exc:
            self.log.emit(str(exc))
        except Exception as exc:
            self.error.emit(str(exc))
            self.log.emit(f"{self.action.replace('_', ' ').title()} task failed: {exc}")
        finally:
            self.finished.emit()

    def _run_impl(self) -> None:
        total = len(self.songs)
        if total == 0:
            self.log.emit("No songs selected.")
            self.progress.emit(0)
            return

        self.log.emit(f"Starting {self.action.replace('_', ' ')} for {total} song(s).")
        for index, song in enumerate(self.songs, start=1):
            self.check_canceled()
            song_target_bpm = self._effective_target_bpm(song)
            song_target_key = self._effective_target_key(song)

            try:
                if self.action == "separate":
                    self._separate(song)
                elif self.action == "match_tempo":
                    self._match_tempo(song, song_target_bpm)
                elif self.action == "match_key":
                    self._match_key(song, song_target_key)
                elif self.action == "process_all":
                    self._process_all(song, song_target_bpm, song_target_key)
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
                self.log.emit(f"{self.action.replace('_', ' ').title()} failed for {song.file_name}: {exc}")

            self.progress.emit(int(index / total * 100))

        self.log.emit(f"{self.action.replace('_', ' ').title()} finished.")

    def _reference_song_for(self, song: SongRecord) -> Optional[SongRecord]:
        if not song.reference_song_path:
            return None
        return self.song_lookup.get(song.reference_song_path)

    def _effective_target_bpm(self, song: SongRecord) -> Optional[float]:
        if song.processing_target_bpm is not None:
            return song.processing_target_bpm

        reference_song = self._reference_song_for(song)
        if reference_song is None:
            return None
        self._ensure_song_analysis(reference_song)
        if not reference_song.bpm or reference_song.bpm <= 0:
            raise AudioProcessingError(f"{reference_song.file_name} does not have a usable BPM.")
        return float(reference_song.bpm)

    def _effective_target_key(self, song: SongRecord) -> Optional[str]:
        if song.processing_target_key:
            return song.processing_target_key

        reference_song = self._reference_song_for(song)
        if reference_song is None:
            return None
        self._ensure_song_analysis(reference_song)
        if not reference_song.musical_key:
            raise AudioProcessingError(f"{reference_song.file_name} does not have a usable key.")
        return reference_song.musical_key

    def _effective_stem_settings(self, song: SongRecord) -> tuple[str, Optional[list[str]]]:
        selected_stems = list(song.processing_selected_stems) if song.processing_selected_stems else None
        if not selected_stems:
            return "All stems", None
        if len(selected_stems) == 1:
            return selected_stems[0], selected_stems
        return "All stems", selected_stems

    def _ensure_song_analysis(self, song: SongRecord) -> None:
        if song.duration is not None and song.bpm is not None and song.musical_key:
            self.ensure_key_relationships(song)
            return

        self.log.emit(f"Analyzing missing metadata for {song.file_name}.")
        result = analyze_audio(
            song.processed_path or song.file_path,
            bpm_range_hint=bpm_range_from_label(song.bpm_range_label),
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

    def _is_reference_song_for_bpm(self, song: SongRecord) -> bool:
        return bool(song.processing_target_bpm is None and song.reference_song_path and song.reference_song_path == song.file_path)

    def _is_reference_song_for_key(self, song: SongRecord) -> bool:
        return bool(not song.processing_target_key and song.reference_song_path and song.reference_song_path == song.file_path)

    def _separate(self, song: SongRecord) -> None:
        stem_option, selected_stems = self._effective_stem_settings(song)
        self.update_song_status(song, SongStatus.SEPARATING.value)
        result = separate_song_stems(
            song,
            stem_option,
            selected_stems=selected_stems,
            log_callback=self.log.emit,
            cancel_callback=self.is_canceled,
        )
        song.stems_dir = str(result["stems_dir"])
        song.status = SongStatus.READY.value
        song.last_error = None
        self.song_updated.emit(song)

    def _match_tempo(self, song: SongRecord, target_bpm: Optional[float]) -> None:
        if target_bpm is None:
            raise AudioProcessingError("Tempo matching needs a target BPM.")

        if self._is_reference_song_for_bpm(song):
            self.log.emit(f"Skipping tempo match for reference song {song.file_name}.")
            self.song_updated.emit(song)
            return

        self.update_song_status(song, SongStatus.MATCHING_TEMPO.value)
        self._ensure_song_analysis(song)
        result = match_song_tempo(song, target_bpm, log_callback=self.log.emit)
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

        if self._is_reference_song_for_key(song):
            self.log.emit(f"Skipping key match for reference song {song.file_name}.")
            self.song_updated.emit(song)
            return

        self.update_song_status(song, SongStatus.MATCHING_KEY.value)
        self._ensure_song_analysis(song)
        result = match_song_key(song, target_key, log_callback=self.log.emit)
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

    def _process_all(self, song: SongRecord, target_bpm: Optional[float], target_key: Optional[str]) -> None:
        self.update_song_status(song, SongStatus.PROCESSING.value)
        self._ensure_song_analysis(song)
        stem_option, selected_stems = self._effective_stem_settings(song)

        if stem_option:
            result = separate_song_stems(
                song,
                stem_option,
                selected_stems=selected_stems,
                log_callback=self.log.emit,
                cancel_callback=self.is_canceled,
            )
            song.stems_dir = str(result["stems_dir"])
            self.song_updated.emit(song)

        if target_bpm is not None and not self._is_reference_song_for_bpm(song):
            tempo_result = match_song_tempo(song, target_bpm, log_callback=self.log.emit)
            song.processed_path = str(tempo_result["output_path"])
            song.duration = float(tempo_result["duration"])
            song.bpm = float(tempo_result["bpm"])
            self.song_updated.emit(song)
        elif target_bpm is not None:
            self.log.emit(f"Skipping tempo match for reference song {song.file_name}.")

        if target_key and not self._is_reference_song_for_key(song):
            key_result = match_song_key(song, target_key, log_callback=self.log.emit)
            song.processed_path = str(key_result["output_path"])
            song.duration = float(key_result["duration"])
            song.musical_key = str(key_result["key"])
            song.relative_key = str(key_result.get("relative_key") or "") or None
            song.compatible_keys = list(key_result.get("compatible_keys") or [])
            self.song_updated.emit(song)
        elif target_key:
            self.log.emit(f"Skipping key match for reference song {song.file_name}.")

        song.status = SongStatus.READY.value
        song.last_error = None
        self.song_updated.emit(song)
        self.log.emit(f"Full pipeline finished for {song.file_name}.")

    def _export(self, song: SongRecord) -> None:
        if not self.options.output_dir:
            raise AudioProcessingError("Choose an export folder before exporting.")

        self.update_song_status(song, SongStatus.PROCESSING.value)
        result = export_song_artifacts(song, self.options.output_dir)
        song.status = SongStatus.EXPORTED.value
        song.last_error = None
        self.song_updated.emit(song)

        if result["copied_original_only"]:
            self.log.emit(f"Exported original file for {song.file_name} because no processed output was available.")
        else:
            self.log.emit(f"Exported artifacts for {song.file_name}.")
