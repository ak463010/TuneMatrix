from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from utils import (
    build_output_filename,
    camelot_for_key,
    enharmonic_key_alias,
    format_bpm,
    format_camelot,
    format_duration,
    format_key,
    format_key_with_alias,
    safe_stem,
    unique_path,
    validate_audio_file,
)


class UtilsTests(unittest.TestCase):
    def test_format_helpers(self) -> None:
        self.assertEqual(format_duration(None), "N/A")
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(3661), "1:01:01")
        self.assertEqual(format_bpm(None), "N/A")
        self.assertEqual(format_bpm(128.456), "128.5")
        self.assertEqual(format_key(None), "N/A")
        self.assertEqual(format_key("A Minor"), "A Minor")

    def test_safe_stem_and_build_output_filename(self) -> None:
        self.assertEqual(safe_stem(" A song / name "), "A_song_name")
        self.assertEqual(build_output_filename("Track One.wav", "tempo 128", ".wav"), "Track_One_tempo_128.wav")

    def test_camelot_helpers(self) -> None:
        self.assertEqual(camelot_for_key("A Minor"), "8A")
        self.assertEqual(camelot_for_key("C Major"), "8B")
        self.assertEqual(camelot_for_key("G# Minor"), "1A")
        self.assertEqual(format_camelot("E Major"), "12B")
        self.assertEqual(format_camelot(None), "N/A")
        self.assertEqual(enharmonic_key_alias("D# Minor"), "E♭ Minor")
        self.assertEqual(format_key_with_alias("D# Minor"), "D# Minor (E♭ Minor)")
        self.assertEqual(format_key_with_alias("E Minor"), "E Minor")

    def test_validate_audio_file_accepts_supported_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "demo.wav"
            wav_path.write_bytes(b"test")

            valid, message = validate_audio_file(str(wav_path))

            self.assertTrue(valid)
            self.assertEqual(message, "")

    def test_validate_audio_file_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            txt_path = Path(temp_dir) / "demo.txt"
            txt_path.write_text("test", encoding="utf-8")

            valid, message = validate_audio_file(str(txt_path))

            self.assertFalse(valid)
            self.assertIn("Unsupported format", message)

    def test_unique_path_adds_suffix_when_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "mix.wav"
            existing.write_bytes(b"test")

            candidate = unique_path(existing)

            self.assertEqual(candidate.name, "mix_1.wav")


if __name__ == "__main__":
    unittest.main()
