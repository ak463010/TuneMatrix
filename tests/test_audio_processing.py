from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf
import torch as th

from audio_processing import (
    TaskCanceledError,
    _apply_demucs_model_with_cancel,
    _export_processed_filename,
    _parse_madmom_key_name,
    _pitch_shift,
    detect_key,
    detect_key_for_file,
    _score_keys_from_pitch_profile,
    _rubberband_args_for_processing_mode,
    _time_stretch,
    action_base_requirement_message,
    action_runtime_issues,
    apply_bpm_analysis_hint,
    analyze_audio,
    export_song_artifacts,
    get_compatible_keys,
    get_relative_key,
    match_song_key,
    match_song_tempo,
    normalize_bpm_to_range_hint,
    separate_song_stems,
)
from models import (
    BPMAnalysisHint,
    PROCESSING_MODE_BALANCED,
    PROCESSING_MODE_FAST_PREVIEW,
    PROCESSING_MODE_HIGH_QUALITY_MIX,
    PROCESSING_MODE_PERCUSSIVE,
    PROCESSING_MODE_VOCAL,
    SongRecord,
    bpm_hint_from_label,
    bpm_range_from_label,
)


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
            self.assertEqual(result["relative_key"], get_relative_key(result["key"]))
            self.assertEqual(result["compatible_keys"], get_compatible_keys(result["key"]))

    def test_analyze_audio_uses_middle_excerpt_for_long_tracks(self) -> None:
        fake_audio = np.ones(2048, dtype=np.float32)
        with patch("audio_processing._get_audio_file_duration", return_value=300.0), patch(
            "audio_processing.librosa.load",
            return_value=(fake_audio, 22050),
        ) as load_mock, patch(
            "audio_processing.librosa.beat.beat_track",
            return_value=(np.array([128.0], dtype=np.float32), None),
        ), patch(
            "audio_processing.detect_key",
            return_value="C Major",
        ):
            result = analyze_audio("long_track.wav")

        load_mock.assert_called_once_with(
            "long_track.wav",
            sr=None,
            mono=True,
            offset=120.0,
            duration=60.0,
        )
        self.assertEqual(result["duration"], 300.0)
        self.assertEqual(result["bpm"], 128.0)
        self.assertEqual(result["key"], "C Major")

    def test_key_relationship_helpers_return_relative_and_compatible_keys(self) -> None:
        self.assertEqual(get_relative_key("C Major"), "A Minor")
        self.assertEqual(get_relative_key("A Minor"), "C Major")
        self.assertEqual(
            get_compatible_keys("C Major"),
            ["A Minor", "G Major", "E Minor", "F Major", "D Minor"],
        )
        self.assertEqual(
            get_compatible_keys("A Minor"),
            ["C Major", "E Minor", "G Major", "D Minor", "F Major"],
        )

    def test_key_scoring_prefers_major_tonic_over_relative_minor(self) -> None:
        profile = np.array(
            [
                0.23, 0.01, 0.06, 0.01, 0.17, 0.07,
                0.01, 0.14, 0.01, 0.10, 0.01, 0.18,
            ],
            dtype=float,
        )

        scored = _score_keys_from_pitch_profile(profile)

        self.assertGreater(scored["C Major"], scored["A Minor"])

    def test_key_scoring_prefers_minor_tonic_over_relative_major(self) -> None:
        profile = np.array(
            [
                0.16, 0.01, 0.05, 0.01, 0.09, 0.04,
                0.01, 0.08, 0.01, 0.24, 0.01, 0.29,
            ],
            dtype=float,
        )

        scored = _score_keys_from_pitch_profile(profile)

        self.assertGreater(scored["A Minor"], scored["C Major"])

    def test_normalize_bpm_to_range_hint_prefers_value_inside_selected_band(self) -> None:
        self.assertEqual(normalize_bpm_to_range_hint(75.0, (140.0, 160.0)), 150.0)
        self.assertEqual(normalize_bpm_to_range_hint(128.0, None), 128.0)

    def test_bpm_hint_from_label_supports_exact_value_and_range(self) -> None:
        self.assertEqual(bpm_hint_from_label("128"), BPMAnalysisHint(exact_bpm=128.0))
        self.assertEqual(bpm_hint_from_label("102.474 BPM"), BPMAnalysisHint(exact_bpm=102.474))
        self.assertEqual(bpm_hint_from_label("120-130"), BPMAnalysisHint(bpm_range=(120.0, 130.0)))
        self.assertEqual(bpm_hint_from_label("130 to 120 BPM"), BPMAnalysisHint(bpm_range=(120.0, 130.0)))
        self.assertIsNone(bpm_hint_from_label("not-a-range"))

    def test_bpm_range_from_label_only_returns_ranges(self) -> None:
        self.assertIsNone(bpm_range_from_label("128"))
        self.assertEqual(bpm_range_from_label("120-130"), (120.0, 130.0))

    def test_apply_bpm_analysis_hint_uses_exact_manual_bpm(self) -> None:
        self.assertEqual(apply_bpm_analysis_hint(51.237, BPMAnalysisHint(exact_bpm=102.474)), 102.474)
        self.assertEqual(apply_bpm_analysis_hint(None, BPMAnalysisHint(exact_bpm=102.0)), 102.0)
        self.assertEqual(
            apply_bpm_analysis_hint(75.0, BPMAnalysisHint(bpm_range=(140.0, 160.0))),
            150.0,
        )

    def test_detect_key_prefers_audioflux_backend_when_available(self) -> None:
        profile = np.array(
            [
                0.23, 0.01, 0.06, 0.01, 0.17, 0.07,
                0.01, 0.14, 0.01, 0.10, 0.01, 0.18,
            ],
            dtype=np.float32,
        )
        chroma = np.expand_dims(profile, axis=-1)
        fake_audioflux = SimpleNamespace(
            chroma_cqt=Mock(return_value=chroma),
            chroma_linear=Mock(return_value=chroma),
            resample=Mock(side_effect=AssertionError("audioFlux resample should not be used for 22.05 kHz audio")),
        )
        audio = np.linspace(-0.5, 0.5, 4096, dtype=np.float32)

        with patch("audio_processing.audioflux", fake_audioflux), patch(
            "audio_processing.librosa.effects.harmonic",
            return_value=audio,
        ), patch(
            "audio_processing.librosa.feature.chroma_cqt",
            Mock(side_effect=AssertionError("legacy chroma backend should not run when audioFlux succeeds")),
        ), patch(
            "audio_processing.librosa.feature.chroma_stft",
            Mock(side_effect=AssertionError("legacy chroma backend should not run when audioFlux succeeds")),
        ):
            detected = detect_key(audio, 22050)

        self.assertEqual(detected, "C Major")
        fake_audioflux.chroma_cqt.assert_called_once()
        fake_audioflux.chroma_linear.assert_not_called()

    def test_parse_madmom_key_name_supports_major_and_minor_forms(self) -> None:
        self.assertEqual(_parse_madmom_key_name("A major"), "A Major")
        self.assertEqual(_parse_madmom_key_name("A minor"), "A Minor")
        self.assertEqual(_parse_madmom_key_name("Bb minor"), "A# Minor")
        self.assertEqual(_parse_madmom_key_name("Db major"), "C# Major")

    def test_detect_key_for_file_prefers_madmom_backend_when_available(self) -> None:
        audio = np.linspace(-0.5, 0.5, 4096, dtype=np.float32)

        with patch(
            "audio_processing._detect_key_with_madmom",
            return_value="A Major",
        ) as madmom_mock, patch(
            "audio_processing.detect_key",
            Mock(side_effect=AssertionError("fallback detector should not run when madmom succeeds")),
        ):
            detected = detect_key_for_file("song.wav", audio, 22050)

        self.assertEqual(detected, "A Major")
        madmom_mock.assert_called_once_with(audio, 22050, file_path="song.wav")

    def test_rubberband_args_vary_by_processing_mode(self) -> None:
        self.assertEqual(
            _rubberband_args_for_processing_mode(PROCESSING_MODE_BALANCED, "tempo"),
            {"--fast": "", "--centre-focus": "", "--crisp": "5"},
        )
        self.assertEqual(
            _rubberband_args_for_processing_mode(PROCESSING_MODE_HIGH_QUALITY_MIX, "pitch"),
            {"--fine": "", "--realtime": "", "--pitch-hq": ""},
        )
        self.assertEqual(
            _rubberband_args_for_processing_mode(PROCESSING_MODE_VOCAL, "pitch"),
            {"--fine": "", "--centre-focus": "", "--realtime": "", "--pitch-hq": "", "--formant": ""},
        )
        self.assertEqual(
            _rubberband_args_for_processing_mode(PROCESSING_MODE_PERCUSSIVE, "tempo"),
            {"--fast": "", "--centre-focus": "", "--crisp": "6"},
        )
        self.assertEqual(
            _rubberband_args_for_processing_mode(PROCESSING_MODE_FAST_PREVIEW, "tempo"),
            {"--fast": "", "--crisp": "4"},
        )

    def test_time_stretch_uses_multichannel_rubberband_path(self) -> None:
        stereo_audio = np.array(
            [
                [0.1, 0.2, 0.3, 0.4],
                [1.1, 1.2, 1.3, 1.4],
            ],
            dtype=np.float32,
        )

        def fake_time_stretch(y, sr, rate, rbargs=None):
            self.assertEqual(sr, 44100)
            self.assertEqual(rate, 1.25)
            self.assertEqual(rbargs, {"--fine": ""})
            self.assertEqual(y.shape, (4, 2))
            np.testing.assert_allclose(y[:, 0], stereo_audio[0])
            np.testing.assert_allclose(y[:, 1], stereo_audio[1])
            return y + 2.0

        fake_pyrb = SimpleNamespace(time_stretch=fake_time_stretch)

        with patch("audio_processing.find_executable", return_value="rubberband"), patch(
            "audio_processing.pyrb",
            fake_pyrb,
        ):
            result = _time_stretch(
                stereo_audio,
                44100,
                1.25,
                processing_mode=PROCESSING_MODE_HIGH_QUALITY_MIX,
            )

        self.assertEqual(result.shape, stereo_audio.shape)
        np.testing.assert_allclose(result, stereo_audio + 2.0)

    def test_pitch_shift_uses_multichannel_rubberband_path(self) -> None:
        stereo_audio = np.array(
            [
                [0.5, 0.6, 0.7],
                [1.5, 1.6, 1.7],
            ],
            dtype=np.float32,
        )

        def fake_pitch_shift(y, sr, n_steps, rbargs=None):
            self.assertEqual(sr, 48000)
            self.assertEqual(n_steps, 3.0)
            self.assertEqual(
                rbargs,
                {"--fine": "", "--centre-focus": "", "--realtime": "", "--pitch-hq": "", "--formant": ""},
            )
            self.assertEqual(y.shape, (3, 2))
            np.testing.assert_allclose(y[:, 0], stereo_audio[0])
            np.testing.assert_allclose(y[:, 1], stereo_audio[1])
            return y * 0.5

        fake_pyrb = SimpleNamespace(pitch_shift=fake_pitch_shift)

        with patch("audio_processing.find_executable", return_value="rubberband"), patch(
            "audio_processing.pyrb",
            fake_pyrb,
        ):
            result = _pitch_shift(
                stereo_audio,
                48000,
                3.0,
                processing_mode=PROCESSING_MODE_VOCAL,
            )

        self.assertEqual(result.shape, stereo_audio.shape)
        np.testing.assert_allclose(result, stereo_audio * 0.5)

    def test_action_runtime_issues_flags_missing_ffmpeg_for_mp3(self) -> None:
        fake_report = {
            "librosa": {"available": True, "detail": None},
            "madmom": {"available": True, "detail": None},
            "audioflux": {"available": True, "detail": None},
            "numpy": {"available": True, "detail": None},
            "soundfile": {"available": True, "detail": None},
            "pyrubberband": {"available": True, "detail": None},
            "torch": {"available": True, "detail": None},
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
            "madmom": {"available": True, "detail": None},
            "audioflux": {"available": True, "detail": None},
            "numpy": {"available": True, "detail": None},
            "soundfile": {"available": True, "detail": None},
            "pyrubberband": {"available": True, "detail": None},
            "torch": {"available": True, "detail": None},
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
            ), patch("audio_processing._log"), patch(
                "audio_processing._apply_demucs_model_with_cancel", return_value=fake_sources.unsqueeze(0)
            ):
                result = separate_song_stems(song, "Vocals")

            stem_dir = Path(result["stems_dir"])
            self.assertTrue((stem_dir / "vocals.wav").exists())
            self.assertFalse((stem_dir / "karaoke_no_vocals.wav").exists())

    def test_separate_song_stems_writes_karaoke_no_vocals_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            wav_path = temp_root / "tone.wav"
            stems_root = temp_root / "karaoke_stems"
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
            ), patch("audio_processing._log"), patch(
                "audio_processing._apply_demucs_model_with_cancel", return_value=fake_sources.unsqueeze(0)
            ):
                result = separate_song_stems(song, "Karaoke / No vocals")

            stem_dir = Path(result["stems_dir"])
            self.assertTrue((stem_dir / "karaoke_no_vocals.wav").exists())

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
            ), patch("audio_processing._log"), patch(
                "audio_processing._apply_demucs_model_with_cancel", return_value=fake_sources.unsqueeze(0)
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

    def test_match_song_key_logs_clear_message_when_mode_conversion_is_not_possible(self) -> None:
        song = SongRecord.from_path("demo.wav")
        song.duration = 10.0
        song.musical_key = "E Minor"

        logs: list[str] = []
        result = match_song_key(song, "E Major", log_callback=logs.append)

        self.assertEqual(result["key"], "E Minor")
        self.assertEqual(
            logs,
            [
                "demo.wav already has the target root note. TuneMatrix cannot convert Minor to Major, so no pitch shift was applied."
            ],
        )

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

    def test_export_processed_filename_uses_display_preference_for_key_suffix(self) -> None:
        song = SongRecord.from_path("demo.wav")
        song.processed_path = str(Path("cache") / "demo_key_D_Minor.wav")
        song.musical_key = "D# Minor"

        self.assertEqual(_export_processed_filename(song), "demo_key_Dsharp_Minor.wav")
        self.assertEqual(
            _export_processed_filename(song, "prefer_flats"),
            "demo_key_Eb_Minor.wav",
        )

    def test_export_song_artifacts_renames_key_based_exports_using_display_preference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            processed_path = temp_root / "demo_key_D_Minor.wav"
            export_dir = temp_root / "exports"
            create_test_wave(processed_path)

            song = SongRecord.from_path(str(temp_root / "demo.wav"))
            song.processed_path = str(processed_path)
            song.musical_key = "D# Minor"

            result = export_song_artifacts(song, str(export_dir), key_display_preference="prefer_flats")

            exported_path = Path(result["paths"][0])
            self.assertEqual(exported_path.name, "demo_key_Eb_Minor.wav")
            self.assertTrue(exported_path.exists())

    def test_apply_demucs_model_with_cancel_stops_between_chunks(self) -> None:
        class FakeDemucs(th.nn.Module):
            samplerate = 10
            audio_channels = 2
            sources = ["drums", "vocals"]
            segment = 0.5

            def forward(self, x):
                return th.stack([x, x], dim=1)

        mix = th.ones(1, 2, 20, dtype=th.float32)
        cancel_checks = {"count": 0}

        def cancel_callback() -> bool:
            cancel_checks["count"] += 1
            return cancel_checks["count"] >= 3

        with self.assertRaises(TaskCanceledError):
            _apply_demucs_model_with_cancel(FakeDemucs(), mix, cancel_callback=cancel_callback, device="cpu")


if __name__ == "__main__":
    unittest.main()
