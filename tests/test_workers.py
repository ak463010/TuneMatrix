from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models import ProcessingOptions, SongRecord, SongStatus
from workers import AnalyzeWorker, ProcessingWorker


class ProcessingWorkerSongBoundTests(unittest.TestCase):
    def test_analyze_worker_preserves_exported_status_after_successful_reanalysis(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.status = SongStatus.EXPORTED.value

        worker = AnalyzeWorker([song])

        with patch(
            "workers.analyze_audio",
            return_value={
                "duration": 60.0,
                "bpm": 128.0,
                "key": "A Minor",
                "relative_key": "C Major",
                "compatible_keys": ["E Minor"],
            },
        ):
            worker._run_impl()

        self.assertEqual(song.status, SongStatus.EXPORTED.value)
        self.assertEqual(song.bpm, 128.0)
        self.assertEqual(song.musical_key, "A Minor")

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

    def test_match_key_and_tempo_pass_cancel_callback(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.processing_target_bpm = 128.0
        song.processing_target_key = "A Minor"

        worker = ProcessingWorker([song], ProcessingOptions(), "process_all")

        with patch.object(worker, "_ensure_song_analysis"), patch(
            "workers.match_song_tempo",
            return_value={"output_path": "tempo.wav", "duration": 10.0, "bpm": 128.0},
        ) as tempo_mock, patch(
            "workers.match_song_key",
            return_value={
                "output_path": "key.wav",
                "duration": 10.0,
                "key": "A Minor",
                "relative_key": "C Major",
                "compatible_keys": ["E Minor"],
                "mode_matched": True,
            },
        ) as key_mock:
            worker._match_tempo(song, 128.0)
            worker._match_key(song, "A Minor")

        tempo_cancel = tempo_mock.call_args.kwargs["cancel_callback"]
        key_cancel = key_mock.call_args.kwargs["cancel_callback"]
        self.assertIs(tempo_cancel.__self__, worker)
        self.assertIs(key_cancel.__self__, worker)
        self.assertIs(tempo_cancel.__func__, worker.is_canceled.__func__)
        self.assertIs(key_cancel.__func__, worker.is_canceled.__func__)

    def test_run_workflow_executes_mix_steps_in_configured_order(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.processing_target_bpm = 128.0
        song.processing_target_key = "A Minor"
        song.duration = 60.0
        song.bpm = 120.0
        song.musical_key = "C Major"

        worker = ProcessingWorker(
            [song],
            ProcessingOptions(output_dir="C:/exports", workflow_steps=["match_key", "match_tempo"]),
            "process_all",
        )

        events: list[tuple[str, str, object]] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            key_output = Path(temp_dir) / "key.wav"
            tempo_output = Path(temp_dir) / "tempo.wav"
            key_output.write_bytes(b"key")
            tempo_output.write_bytes(b"tempo")

            def fake_key(temp_song: SongRecord, target_key: str, log_callback=None, cancel_callback=None):
                events.append(("match_key", Path(temp_song.file_path).name, target_key))
                return {
                    "output_path": str(key_output),
                    "duration": 60.0,
                    "key": target_key,
                    "relative_key": "C Major",
                    "compatible_keys": ["E Minor"],
                    "mode_matched": True,
                }

            def fake_tempo(temp_song: SongRecord, target_bpm: float, log_callback=None, cancel_callback=None):
                events.append(("match_tempo", Path(temp_song.file_path).name, target_bpm))
                return {
                    "output_path": str(tempo_output),
                    "duration": 56.0,
                    "bpm": target_bpm,
                }

            with patch("workers.match_song_key", side_effect=fake_key), patch(
                "workers.match_song_tempo",
                side_effect=fake_tempo,
            ), patch(
                "workers.export_song_artifacts",
                return_value={"copied_original_only": False, "paths": ["C:/exports/final.wav"]},
            ):
                worker._run_impl()

        self.assertEqual(
            events,
            [
                ("match_key", "song.wav", "A Minor"),
                ("match_tempo", "key.wav", 128.0),
            ],
        )
        self.assertEqual(song.processed_path, str(tempo_output))
        self.assertEqual(song.status, SongStatus.EXPORTED.value)

    def test_run_workflow_can_process_stems_after_separation(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.processing_target_key = "A Minor"
        song.processing_selected_stems = ["Vocals", "Bass"]
        song.duration = 60.0
        song.bpm = 120.0
        song.musical_key = "C Major"

        worker = ProcessingWorker(
            [song],
            ProcessingOptions(output_dir="C:/exports", workflow_steps=["separate", "match_key"]),
            "process_all",
        )

        events: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            stems_dir = Path(temp_dir) / "stems"
            stems_dir.mkdir(parents=True, exist_ok=True)
            vocals = stems_dir / "vocals.wav"
            drums = stems_dir / "drums.wav"
            vocals.write_bytes(b"vocals")
            drums.write_bytes(b"drums")

            workflow_cache_root = Path(temp_dir) / "workflow_cache"
            workflow_cache_root.mkdir(parents=True, exist_ok=True)

            def fake_separate(song_record: SongRecord, stem_option: str, selected_stems=None, log_callback=None, cancel_callback=None):
                events.append(("separate", stem_option))
                return {"stems_dir": str(stems_dir)}

            def fake_key(temp_song: SongRecord, target_key: str, log_callback=None, cancel_callback=None):
                events.append(("match_key", Path(temp_song.file_path).name))
                output_path = Path(temp_dir) / f"processed_{Path(temp_song.file_path).name}"
                output_path.write_bytes(b"processed")
                return {
                    "output_path": str(output_path),
                    "duration": 60.0,
                    "key": target_key,
                    "relative_key": "C Major",
                    "compatible_keys": ["E Minor"],
                    "mode_matched": True,
                }

            with patch("workers.separate_song_stems", side_effect=fake_separate), patch(
                "workers.match_song_key",
                side_effect=fake_key,
            ), patch(
                "workers.make_song_cache_dir",
                return_value=str(workflow_cache_root),
            ), patch(
                "workers.export_song_artifacts",
                return_value={"copied_original_only": False, "paths": ["C:/exports/stems"]},
            ):
                worker._run_impl()

            self.assertTrue(song.stems_dir is not None)
            self.assertTrue(Path(song.stems_dir).exists())

        self.assertEqual(events[0], ("separate", "All stems"))
        self.assertEqual(events[1:], [("match_key", "drums.wav"), ("match_key", "vocals.wav")])
        self.assertEqual(song.status, SongStatus.EXPORTED.value)

    def test_run_workflow_skips_missing_song_targets_instead_of_failing(self) -> None:
        song = SongRecord.from_path("song.wav")
        song.duration = 60.0
        song.bpm = 120.0
        song.musical_key = "C Major"

        worker = ProcessingWorker(
            [song],
            ProcessingOptions(output_dir="C:/exports", workflow_steps=["match_key", "match_tempo", "separate"]),
            "process_all",
        )

        logs: list[str] = []
        worker.log.connect(logs.append)

        with patch.object(worker, "_separate", side_effect=lambda target_song: setattr(target_song, "stems_dir", "C:/tmp/stems")), patch(
            "workers.export_song_artifacts",
            return_value={"copied_original_only": False, "paths": ["C:/exports/stems"]},
        ), patch.object(worker, "_has_exportable_artifacts", return_value=True):
            worker._run_impl()

        self.assertIn("song.wav: skipping Match Key because no Target Key is set.", logs)
        self.assertIn("song.wav: skipping Match Tempo because no Target BPM is set.", logs)


if __name__ == "__main__":
    unittest.main()
