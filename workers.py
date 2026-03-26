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
from models import ProcessingOptions, SongRecord, SongStatus


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
                result = analyze_audio(song.file_path)
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
        reference_song: Optional[SongRecord] = None,
    ) -> None:
        super().__init__()
        self.songs = songs
        self.options = options
        self.action = action
        self.reference_song = reference_song

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

        target_bpm = self._resolve_target_bpm()
        target_key = self._resolve_target_key()

        self.log.emit(f"Starting {self.action.replace('_', ' ')} for {total} song(s).")
        for index, song in enumerate(self.songs, start=1):
            self.check_canceled()

            try:
                if self.action == "separate":
                    self._separate(song)
                elif self.action == "match_tempo":
                    self._match_tempo(song, target_bpm)
                elif self.action == "match_key":
                    self._match_key(song, target_key)
                elif self.action == "process_all":
                    self._process_all(song, target_bpm, target_key)
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

    def _resolve_target_bpm(self) -> Optional[float]:
        if self.action not in {"match_tempo", "process_all"}:
            return None

        if self.options.match_to_reference:
            if not self.reference_song:
                raise AudioProcessingError("Reference song matching is enabled, but no reference song is selected.")
            self._ensure_song_analysis(self.reference_song)
            if not self.reference_song.bpm or self.reference_song.bpm <= 0:
                raise AudioProcessingError("The selected reference song does not have a usable BPM.")
            return float(self.reference_song.bpm)

        if self.action == "match_tempo" and (self.options.target_bpm is None or self.options.target_bpm <= 0):
            raise AudioProcessingError("Set a target BPM or enable reference matching before running tempo matching.")

        return self.options.target_bpm

    def _resolve_target_key(self) -> Optional[str]:
        if self.action not in {"match_key", "process_all"}:
            return None

        if self.options.match_to_reference:
            if not self.reference_song:
                raise AudioProcessingError("Reference song matching is enabled, but no reference song is selected.")
            self._ensure_song_analysis(self.reference_song)
            if not self.reference_song.musical_key:
                raise AudioProcessingError("The selected reference song does not have a usable key.")
            return self.reference_song.musical_key

        if self.action == "match_key" and not self.options.target_key:
            raise AudioProcessingError("Choose a target key or enable reference matching before running key matching.")

        return self.options.target_key

    def _ensure_song_analysis(self, song: SongRecord) -> None:
        if song.duration is not None and song.bpm is not None and song.musical_key:
            self.ensure_key_relationships(song)
            return

        self.log.emit(f"Analyzing missing metadata for {song.file_name}.")
        result = analyze_audio(song.processed_path or song.file_path)
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

    def _is_reference_song(self, song: SongRecord) -> bool:
        return bool(self.reference_song and song.file_path == self.reference_song.file_path)

    def _separate(self, song: SongRecord) -> None:
        self.update_song_status(song, SongStatus.SEPARATING.value)
        result = separate_song_stems(
            song,
            self.options.stem_option,
            selected_stems=self.options.selected_stems,
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

        if self.options.match_to_reference and self._is_reference_song(song):
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

        if self.options.match_to_reference and self._is_reference_song(song):
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

        if self.options.stem_option:
            result = separate_song_stems(
                song,
                self.options.stem_option,
                selected_stems=self.options.selected_stems,
                log_callback=self.log.emit,
                cancel_callback=self.is_canceled,
            )
            song.stems_dir = str(result["stems_dir"])
            self.song_updated.emit(song)

        if target_bpm is not None and not (self.options.match_to_reference and self._is_reference_song(song)):
            tempo_result = match_song_tempo(song, target_bpm, log_callback=self.log.emit)
            song.processed_path = str(tempo_result["output_path"])
            song.duration = float(tempo_result["duration"])
            song.bpm = float(tempo_result["bpm"])
            self.song_updated.emit(song)
        elif target_bpm is not None:
            self.log.emit(f"Skipping tempo match for reference song {song.file_name}.")

        if target_key and not (self.options.match_to_reference and self._is_reference_song(song)):
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
