from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from main_window import MainWindow, PROJECT_STATE_VERSION


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _build_window(self) -> MainWindow:
        with patch("main_window.dependency_status_lines", return_value=[]), patch(
            "main_window.action_base_requirement_message",
            side_effect=lambda action: {"separate": "Stem dependency missing.", "process_all": "Stem dependency missing."}.get(action),
        ):
            window = MainWindow()
        self.addCleanup(window.close)
        return window

    def test_action_availability_reflects_dependency_messages(self) -> None:
        window = self._build_window()

        self.assertTrue(window.analyze_button.isEnabled())
        self.assertFalse(window.separate_button.isEnabled())
        self.assertFalse(window.process_all_button.isEnabled())
        self.assertIn("Stem dependency missing.", window.separate_button.toolTip())

    def test_clickable_controls_use_pointing_hand_cursor(self) -> None:
        window = self._build_window()
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "cursor.wav"
            wav_path.write_bytes(b"test")
            window.import_songs([str(wav_path)])
            bpm_range_combo = window.song_table.cellWidget(0, 2)
            key_hint_combo = window.song_table.cellWidget(0, 3)

        self.assertEqual(window.import_button.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(window.reference_checkbox.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(bpm_range_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(key_hint_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(window.target_key_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(window.song_table.viewport().cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertTrue(window.song_table.hasMouseTracking())
        self.assertTrue(window.song_table.viewport().hasMouseTracking())

    def test_build_processing_options_parses_form_values(self) -> None:
        window = self._build_window()

        window.target_bpm_edit.setText("128.5")
        window.target_key_combo.setCurrentText("C Major")
        window.stem_option_combo.setCurrentText("Bass")
        window.reference_checkbox.setChecked(True)
        window.output_dir_edit.setText("C:/temp/export")

        options = window.build_processing_options()

        self.assertEqual(options.target_bpm, 128.5)
        self.assertEqual(options.target_key, "C Major")
        self.assertEqual(options.stem_option, "Bass")
        self.assertEqual(options.selected_stems, ["Bass"])
        self.assertTrue(options.match_to_reference)
        self.assertEqual(options.output_dir, "C:/temp/export")

    def test_import_songs_adds_one_row_and_skips_duplicate(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "demo.wav"
            wav_path.write_bytes(b"test")

            window.import_songs([str(wav_path)])
            window.import_songs([str(wav_path)])

        self.assertEqual(len(window.songs), 1)
        self.assertEqual(window.song_table.rowCount(), 1)
        self.assertEqual(window.song_table.item(0, 0).text(), "demo.wav")

    def test_start_analyze_task_blocks_when_runtime_issue_exists(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "demo.wav"
            wav_path.write_bytes(b"test")
            window.import_songs([str(wav_path)])

        with patch("main_window.action_runtime_issues", return_value=["Runtime issue"]), patch.object(
            window, "show_warning", Mock()
        ) as show_warning:
            window.start_analyze_task()

        show_warning.assert_called_once()
        self.assertIsNone(window.current_worker)

    def test_collect_project_state_serializes_songs_and_ui(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "demo.wav"
            wav_path.write_bytes(b"test")
            window.import_songs([str(wav_path)])
            bpm_range_combo = window.song_table.cellWidget(0, 2)
            key_hint_combo = window.song_table.cellWidget(0, 3)

        bpm_range_combo.setCurrentText("90 - 120 BPM")
        key_hint_combo.setCurrentText("G Major")
        window.target_bpm_edit.setText("126")
        window.target_key_combo.setCurrentText("A Minor")
        window.stem_option_combo.setCurrentText("Vocals")
        window.reference_checkbox.setChecked(True)
        window.reference_combo.setCurrentIndex(1)
        window.output_dir_edit.setText("C:/exports")

        state = window.collect_project_state()

        self.assertEqual(state["format_version"], PROJECT_STATE_VERSION)
        self.assertEqual(len(state["songs"]), 1)
        self.assertEqual(state["songs"][0]["file_name"], "demo.wav")
        self.assertEqual(state["songs"][0]["bpm_range_label"], "90 - 120 BPM")
        self.assertEqual(state["songs"][0]["analysis_key_hint"], "G Major")
        self.assertEqual(state["songs"][0]["relative_key"], None)
        self.assertEqual(state["songs"][0]["compatible_keys"], [])
        self.assertEqual(state["ui"]["target_bpm_text"], "126")
        self.assertEqual(state["ui"]["target_key"], "A Minor")
        self.assertEqual(state["ui"]["stem_option"], "Vocals")
        self.assertEqual(state["ui"]["selected_stems"], ["Vocals"])
        self.assertTrue(state["ui"]["match_to_reference"])
        self.assertEqual(state["ui"]["reference_song_path"], str(wav_path.resolve()))
        self.assertEqual(state["ui"]["output_dir"], "C:/exports")

    def test_apply_project_state_restores_songs_and_controls(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "restored.wav"
            wav_path.write_bytes(b"test")

            window.apply_project_state(
                {
                    "format_version": PROJECT_STATE_VERSION,
                    "songs": [
                        {
                            "file_path": str(wav_path),
                            "file_name": "restored.wav",
                            "bpm_range_label": "140 - 160 BPM",
                            "analysis_key_hint": "G Minor",
                            "duration": 91.2,
                            "bpm": 128.0,
                            "musical_key": "C Minor",
                            "relative_key": "D# Major",
                            "compatible_keys": ["G Minor", "A# Major", "F Minor"],
                            "status": "Analyzed",
                            "stems_dir": None,
                            "processed_path": None,
                            "last_error": None,
                        }
                    ],
                    "ui": {
                        "target_bpm_text": "128",
                        "target_key": "C Minor",
                        "stem_option": "All stems",
                        "selected_stems": ["Bass", "Drums"],
                        "match_to_reference": True,
                        "reference_song_path": str(wav_path),
                        "output_dir": "D:/processed",
                    },
                }
            )

        self.assertEqual(len(window.songs), 1)
        self.assertEqual(window.song_table.rowCount(), 1)
        self.assertEqual(window.song_table.item(0, 0).text(), "restored.wav")
        self.assertEqual(window.song_table.cellWidget(0, 2).currentText(), "140 - 160 BPM")
        self.assertEqual(window.song_table.cellWidget(0, 3).currentData(), "G Minor")
        self.assertEqual(window.target_bpm_edit.text(), "128")
        self.assertEqual(window.target_key_combo.currentData(), "C Minor")
        self.assertEqual(window.stem_option_combo.currentData(), "All stems")
        self.assertEqual(window.selected_stem_values(), ["Drums", "Bass"])
        self.assertEqual(window.song_table.item(0, 7).text(), "D# Major")
        self.assertEqual(window.song_table.item(0, 8).text(), "G Minor, A# Major, F Minor")
        self.assertTrue(window.reference_checkbox.isChecked())
        self.assertEqual(window.reference_combo.currentData(), str(wav_path))
        self.assertEqual(window.output_dir_edit.text(), "D:/processed")

    def test_project_save_and_load_round_trip(self) -> None:
        source_window = self._build_window()
        restored_window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "roundtrip.wav"
            project_path = Path(temp_dir) / "session.tunematrix.json"
            wav_path.write_bytes(b"test")

            source_window.import_songs([str(wav_path)])
            source_window.song_table.cellWidget(0, 2).setCurrentText("60 - 90 BPM")
            source_window.song_table.cellWidget(0, 3).setCurrentText("A Minor")
            source_window.target_bpm_edit.setText("110")
            source_window.target_key_combo.setCurrentText("G Major")
            source_window.stem_option_combo.setCurrentText("Drums")
            source_window.reference_combo.setCurrentIndex(1)
            source_window.reference_checkbox.setChecked(True)
            source_window.output_dir_edit.setText(str(Path(temp_dir) / "exports"))

            source_window._save_project_to_path(str(project_path))
            restored_window._load_project_from_path(str(project_path))

        self.assertEqual(len(restored_window.songs), 1)
        self.assertEqual(restored_window.songs[0].file_name, "roundtrip.wav")
        self.assertEqual(restored_window.song_table.cellWidget(0, 2).currentText(), "60 - 90 BPM")
        self.assertEqual(restored_window.song_table.cellWidget(0, 3).currentData(), "A Minor")
        self.assertEqual(restored_window.target_bpm_edit.text(), "110")
        self.assertEqual(restored_window.target_key_combo.currentData(), "G Major")
        self.assertEqual(restored_window.stem_option_combo.currentData(), "Drums")
        self.assertEqual(restored_window.selected_stem_values(), ["Drums"])
        self.assertTrue(restored_window.reference_checkbox.isChecked())
        self.assertEqual(restored_window.reference_combo.currentData(), str(wav_path.resolve()))


if __name__ == "__main__":
    unittest.main()
