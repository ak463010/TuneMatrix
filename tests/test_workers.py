from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models import ProcessingOptions, SongRecord, SongStatus
from workers import ProcessingWorker


class ProcessingWorkerSongBoundTests(unittest.TestCase):
    def test_song_processing_targets_are_used_directly(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.processing_target_bpm = 132.0
        song.processing_target_key = "A Minor"
        song.processing_selected_stems = ["Vocals", "Bass"]

        worker = ProcessingWorker([song], ProcessingOptions(), "process_all")

        self.assertEqual(worker._effective_target_bpm(song), 132.0)
        self.assertEqual(worker._effective_target_key(song), "A Minor")
        self.assertEqual(worker._effective_stem_settings(song), ("All stems", ["Vocals", "Bass"]))

    def test_empty_stem_selection_stays_empty(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.processing_selected_stems = []

        worker = ProcessingWorker([song], ProcessingOptions(), "process_all")

        self.assertEqual(worker._effective_stem_settings(song), (None, []))

    def test_reference_song_is_used_when_explicit_targets_are_missing(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.reference_song_path = "reference.wav"

        reference = SongRecord.from_path("reference.wav")
        reference.bpm = 124.0
        reference.musical_key = "G Major"
        reference.duration = 60.0

        worker = ProcessingWorker([song], ProcessingOptions(), "process_all", all_songs=[song, reference])

        self.assertEqual(worker._effective_target_bpm(song), 124.0)
        self.assertEqual(worker._effective_target_key(song), "G Major")

    def test_self_reference_detection_applies_to_missing_targets(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.reference_song_path = song.file_path

        worker = ProcessingWorker([song], ProcessingOptions(), "process_all")

        self.assertTrue(worker._is_reference_song_for_bpm(song))
        self.assertTrue(worker._is_reference_song_for_key(song))

    def test_match_tempo_auto_exports_processed_results(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.processing_target_bpm = 128.0
        options = ProcessingOptions(output_dir="C:/exports")
        worker = ProcessingWorker([song], options, "match_tempo")

        with tempfile.TemporaryDirectory() as temp_dir:
            processed_path = Path(temp_dir) / "processed.wav"
            processed_path.write_bytes(b"processed")

            with patch.object(worker, "_match_tempo", side_effect=lambda target_song, _bpm: setattr(target_song, "processed_path", str(processed_path))), patch(
                "workers.export_song_artifacts",
                return_value={"copied_original_only": False, "paths": ["C:/exports/processed.wav"]},
            ) as export_mock:
                worker._run_impl()

        export_mock.assert_called_once_with(song, "C:/exports", None)
        self.assertEqual(song.status, SongStatus.EXPORTED.value)

    def test_reference_song_skips_auto_export_when_no_artifacts_were_created(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.reference_song_path = song.file_path
        song.duration = 60.0
        song.bpm = 124.0
        song.musical_key = "G Major"

        worker = ProcessingWorker([song], ProcessingOptions(output_dir="C:/exports"), "match_tempo", all_songs=[song])

        with patch("workers.export_song_artifacts") as export_mock:
            worker._run_impl()

        export_mock.assert_not_called()
        self.assertNotEqual(song.status, SongStatus.EXPORTED.value)


if __name__ == "__main__":
    unittest.main()
