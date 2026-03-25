from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


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


if __name__ == "__main__":
    unittest.main()
