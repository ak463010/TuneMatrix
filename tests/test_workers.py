from __future__ import annotations

import unittest

from models import ProcessingOptions, SongRecord
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


if __name__ == "__main__":
    unittest.main()
