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


if __name__ == "__main__":
    unittest.main()
