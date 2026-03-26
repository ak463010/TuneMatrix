from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
import torch as th

from audio_processing import (
    action_base_requirement_message,
    action_runtime_issues,
    analyze_audio,
    export_song_artifacts,
    match_song_key,
    match_song_tempo,
    separate_song_stems,
)
from models import SongRecord


def create_test_wave(path: Path, frequency: float = 440.0, duration: float = 2.0, sample_rate: int = 22050) -> None:
    samples = np.arange(int(sample_rate * duration), dtype=np.float32)
    audio = 0.2 * np.sin(2 * math.pi * frequency * samples / sample_rate)
    sf.write(path, audio, sample_rate)


class AudioProcessingTests(unittest.TestCase):
    def test_analyze_audio_returns_metadata_for_wav(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "tone.wav"
            create_test_wave(wav_path)

            result = analyze_audio(str(wav_path))

            self.assertGreater(result["duration"], 1.5)
            self.assertIsInstance(result["bpm"], float)
            self.assertTrue(result["key"])

    def test_action_runtime_issues_flags_missing_ffmpeg_for_mp3(self) -> None:
        fake_report = {
            "librosa": {"available": True, "detail": None},
            "numpy": {"available": True, "detail": None},
            "soundfile": {"available": True, "detail": None},
            "pyrubberband": {"available": True, "detail": None},
            "torch": {"available": True, "detail": None},
            "torchaudio": {"available": True, "detail": None},
            "torchcodec": {"available": True, "detail": None},
            "rubberband": {"available": False, "detail": None},
            "ffmpeg": {"available": False, "detail": None},
            "demucs": {"available": True, "detail": None},
        }

        with patch("audio_processing.get_dependency_report", return_value=fake_report):
            issues = action_runtime_issues("analyze", ["track.mp3"])
            no_issues = action_runtime_issues("analyze", ["track.wav"])

        self.assertIn("ffmpeg is required to decode mp3 and m4a files.", issues)
        self.assertEqual(no_issues, [])

    def test_action_base_requirement_message_for_separate_only_requires_demucs_stack(self) -> None:
        fake_report = {
            "librosa": {"available": True, "detail": None},
            "numpy": {"available": True, "detail": None},
            "soundfile": {"available": True, "detail": None},
            "pyrubberband": {"available": True, "detail": None},
            "torch": {"available": True, "detail": None},
            "torchaudio": {"available": False, "detail": None},
            "torchcodec": {"available": False, "detail": None},
            "rubberband": {"available": False, "detail": None},
            "ffmpeg": {"available": True, "detail": None},
            "demucs": {"available": True, "detail": None},
        }

        with patch("audio_processing.get_dependency_report", return_value=fake_report):
            message = action_base_requirement_message("separate")

        self.assertIsNone(message)

    def test_separate_song_stems_writes_requested_stems(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            wav_path = temp_root / "tone.wav"
            stems_root = temp_root / "stems"
            create_test_wave(wav_path)

            song = SongRecord.from_path(str(wav_path))
            fake_sources = th.tensor(
                [
                    [[0.1, 0.1, 0.1], [0.1, 0.1, 0.1]],
                    [[0.2, 0.2, 0.2], [0.2, 0.2, 0.2]],
                    [[0.3, 0.3, 0.3], [0.3, 0.3, 0.3]],
                    [[0.4, 0.4, 0.4], [0.4, 0.4, 0.4]],
                ],
                dtype=th.float32,
            )

            class FakeModel:
                samplerate = 44100
                audio_channels = 2
                sources = ["drums", "bass", "other", "vocals"]

            with patch("audio_processing.make_song_cache_dir", return_value=str(stems_root)), patch(
                "audio_processing.action_runtime_issues", return_value=[]
            ), patch("audio_processing._load_demucs_model", return_value=FakeModel()), patch(
                "audio_processing.librosa.load",
                return_value=(np.vstack([np.ones(100, dtype=np.float32), np.ones(100, dtype=np.float32)]), 44100),
            ), patch("audio_processing.th.cuda.is_available", return_value=False), patch(
                "audio_processing._check_canceled"
            ), patch("audio_processing._log"), patch(
                "demucs.apply.apply_model", return_value=fake_sources.unsqueeze(0)
            ):
                result = separate_song_stems(song, "Vocals")

            stem_dir = Path(result["stems_dir"])
            self.assertTrue((stem_dir / "vocals.wav").exists())
            self.assertFalse((stem_dir / "no_vocals.wav").exists())

    def test_separate_song_stems_filters_multiple_selected_stems(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            wav_path = temp_root / "tone.wav"
            stems_root = temp_root / "multi_stems"
            create_test_wave(wav_path)

            song = SongRecord.from_path(str(wav_path))
            fake_sources = th.tensor(
                [
                    [[0.1, 0.1, 0.1], [0.1, 0.1, 0.1]],
                    [[0.2, 0.2, 0.2], [0.2, 0.2, 0.2]],
                    [[0.3, 0.3, 0.3], [0.3, 0.3, 0.3]],
                    [[0.4, 0.4, 0.4], [0.4, 0.4, 0.4]],
                ],
                dtype=th.float32,
            )

            class FakeModel:
                samplerate = 44100
                audio_channels = 2
                sources = ["drums", "bass", "other", "vocals"]

            with patch("audio_processing.make_song_cache_dir", return_value=str(stems_root)), patch(
                "audio_processing.action_runtime_issues", return_value=[]
            ), patch("audio_processing._load_demucs_model", return_value=FakeModel()), patch(
                "audio_processing.librosa.load",
                return_value=(np.vstack([np.ones(100, dtype=np.float32), np.ones(100, dtype=np.float32)]), 44100),
            ), patch("audio_processing.th.cuda.is_available", return_value=False), patch(
                "audio_processing._check_canceled"
            ), patch("audio_processing._log"), patch(
                "demucs.apply.apply_model", return_value=fake_sources.unsqueeze(0)
            ):
                result = separate_song_stems(song, "All stems", selected_stems=["Vocals", "Bass"])

            stem_dir = Path(result["stems_dir"])
            self.assertTrue((stem_dir / "vocals.wav").exists())
            self.assertTrue((stem_dir / "bass.wav").exists())
            self.assertFalse((stem_dir / "drums.wav").exists())

    def test_match_tempo_key_and_export_processed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            wav_path = temp_root / "tone.wav"
            cache_dir = temp_root / "cache"
            export_dir = temp_root / "exports"
            create_test_wave(wav_path)

            song = SongRecord.from_path(str(wav_path))
            song.duration = 2.0
            song.bpm = 120.0
            song.musical_key = "A Major"

            with patch("audio_processing.make_song_cache_dir", return_value=str(cache_dir)):
                tempo_result = match_song_tempo(song, 100.0)
                self.assertTrue(Path(tempo_result["output_path"]).exists())

                song.processed_path = str(tempo_result["output_path"])
                key_result = match_song_key(song, "C Major")
                self.assertTrue(Path(key_result["output_path"]).exists())

            song.processed_path = str(key_result["output_path"])
            export_result = export_song_artifacts(song, str(export_dir))

            self.assertFalse(export_result["copied_original_only"])
            self.assertEqual(len(export_result["paths"]), 1)
            self.assertTrue(Path(export_result["paths"][0]).exists())

    def test_export_song_artifacts_copies_original_when_no_processed_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            wav_path = temp_root / "tone.wav"
            export_dir = temp_root / "exports"
            create_test_wave(wav_path)

            song = SongRecord.from_path(str(wav_path))
            result = export_song_artifacts(song, str(export_dir))

            self.assertTrue(result["copied_original_only"])
            self.assertEqual(len(result["paths"]), 1)
            self.assertTrue(Path(result["paths"][0]).exists())


if __name__ == "__main__":
    unittest.main()
