from __future__ import annotations

import unittest

from models import ProcessingOptions, SongRecord
from workers import ProcessingWorker


class ProcessingWorkerOverrideTests(unittest.TestCase):
    def test_song_processing_override_takes_precedence_over_global_defaults(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.processing_override_enabled = True
        song.processing_target_bpm = 132.0
        song.processing_target_key = "A Minor"
        song.processing_selected_stems = ["Vocals", "Bass"]

        options = ProcessingOptions(
            stem_option="Drums",
            selected_stems=["Drums"],
            target_bpm=120.0,
            target_key="C Major",
        )
        worker = ProcessingWorker([song], options, "process_all")

        self.assertEqual(worker._effective_target_bpm(song, options.target_bpm), 132.0)
        self.assertEqual(worker._effective_target_key(song, options.target_key), "A Minor")
        self.assertEqual(worker._effective_stem_settings(song), ("All stems", ["Vocals", "Bass"]))

    def test_reference_matching_keeps_reference_bpm_and_key_over_song_override(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.processing_override_enabled = True
        song.processing_target_bpm = 132.0
        song.processing_target_key = "A Minor"

        options = ProcessingOptions(match_to_reference=True)
        worker = ProcessingWorker([song], options, "process_all")

        self.assertEqual(worker._effective_target_bpm(song, 124.0), 124.0)
        self.assertEqual(worker._effective_target_key(song, "G Major"), "G Major")


if __name__ == "__main__":
    unittest.main()
