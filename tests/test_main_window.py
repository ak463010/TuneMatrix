from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

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

    def _import_files(self, window: MainWindow, names: list[str]) -> list[Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        paths: list[Path] = []
        for name in names:
            path = Path(temp_dir.name) / name
            path.write_bytes(b"test")
            paths.append(path)
        window.import_songs([str(path) for path in paths])
        return paths

    def _select_rows(self, window: MainWindow, rows: list[int]) -> None:
        selection_model = window.song_table.selectionModel()
        selection_model.clearSelection()
        for row in rows:
            selection_model.select(
                window.song_table.model().index(row, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )

    def test_action_availability_reflects_dependency_messages(self) -> None:
        window = self._build_window()
        self._import_files(window, ["availability.wav"])
        window.song_table.selectRow(0)

        with patch(
            "main_window.action_base_requirement_message",
            side_effect=lambda action: {"separate": "Stem dependency missing.", "process_all": "Stem dependency missing."}.get(action),
        ):
            window._refresh_action_availability()

        self.assertTrue(window.analyze_button.isEnabled())
        self.assertFalse(window.separate_button.isEnabled())
        self.assertFalse(window.process_all_button.isEnabled())
        self.assertIn("Stem dependency missing.", window.separate_button.toolTip())

    def test_song_actions_stay_disabled_without_selection(self) -> None:
        window = self._build_window()
        self._import_files(window, ["selection.wav"])

        self.assertFalse(window.remove_button.isEnabled())
        self.assertFalse(window.analyze_button.isEnabled())
        self.assertFalse(window.export_action.isEnabled())
        self.assertEqual(window.analyze_button.toolTip(), "Select at least one song.")

        window.song_table.selectRow(0)

        self.assertTrue(window.remove_button.isEnabled())
        self.assertTrue(window.analyze_button.isEnabled())
        self.assertTrue(window.export_action.isEnabled())

    def test_table_header_is_hidden_when_empty_and_visible_with_songs(self) -> None:
        window = self._build_window()

        self.assertTrue(window.song_table.horizontalHeader().isHidden())
        self.assertEqual(
            window.song_table.empty_state_text,
            "No songs imported yet.\nClick Import Songs or drag and drop audio files here.",
        )

        self._import_files(window, ["header.wav"])
        self.assertFalse(window.song_table.horizontalHeader().isHidden())

        window.clear_songs()
        self.assertTrue(window.song_table.horizontalHeader().isHidden())

    def test_clickable_controls_use_pointing_hand_cursor(self) -> None:
        window = self._build_window()
        self._import_files(window, ["cursor.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)
        key_hint_combo = window._table_combo_at(0, 3)

        self.assertEqual(window.import_button.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(bpm_range_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(key_hint_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(window.target_key_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(window.reference_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(window.song_table.viewport().cursor().shape(), Qt.CursorShape.ArrowCursor)

    def test_bpm_range_combo_keeps_dropdown_options_and_manual_entry_item(self) -> None:
        window = self._build_window()
        self._import_files(window, ["dropdown.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)

        self.assertFalse(bpm_range_combo.isEditable())
        dropdown_items = [bpm_range_combo.itemText(index) for index in range(bpm_range_combo.count())]
        self.assertIn("60 - 90 BPM", dropdown_items)
        self.assertIn("Enter BPM...", dropdown_items)

    def test_table_combos_use_compact_fixed_height(self) -> None:
        window = self._build_window()
        self._import_files(window, ["rowfill.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)
        key_hint_combo = window._table_combo_at(0, 3)

        self.assertEqual(window.song_table.verticalHeader().defaultSectionSize(), 28)
        self.assertEqual(bpm_range_combo.minimumHeight(), 20)
        self.assertEqual(key_hint_combo.minimumHeight(), 20)
        self.assertEqual(window.song_table.columnWidth(2), 136)
        self.assertEqual(window.song_table.columnWidth(3), 136)

    def test_table_combos_do_not_take_focus_or_propagate_mouse_events(self) -> None:
        window = self._build_window()
        self._import_files(window, ["table_combo_focus.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)
        key_hint_combo = window._table_combo_at(0, 3)

        self.assertEqual(bpm_range_combo.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(key_hint_combo.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertTrue(bpm_range_combo.testAttribute(Qt.WidgetAttribute.WA_NoMousePropagation))
        self.assertTrue(key_hint_combo.testAttribute(Qt.WidgetAttribute.WA_NoMousePropagation))

    def test_build_processing_options_only_uses_global_output_dir(self) -> None:
        window = self._build_window()
        window.output_dir_edit.setText("C:/temp/export")

        options = window.build_processing_options()

        self.assertEqual(options.output_dir, "C:/temp/export")
        self.assertIsNone(options.target_bpm)
        self.assertIsNone(options.target_key)

    def test_single_selection_loads_song_bound_values_into_editor(self) -> None:
        window = self._build_window()
        paths = self._import_files(window, ["song_a.wav", "song_b.wav"])

        song = window.songs[0]
        song.processing_target_bpm = 128.0
        song.processing_target_key = "A Minor"
        song.processing_selected_stems = ["Vocals", "Bass"]
        song.reference_song_path = str(paths[1].resolve())
        window.refresh_reference_combo()
        window.song_table.selectRow(0)

        self.assertEqual(window.editor_scope_label.text(), "Editing Song: song_a.wav")
        self.assertEqual(window.target_bpm_edit.text(), "128")
        self.assertEqual(window.target_key_combo.currentData(), "A Minor")
        self.assertEqual(window.reference_combo.currentData(), str(paths[1].resolve()))
        self.assertTrue(window.stem_checkboxes["Vocals"].isChecked())
        self.assertTrue(window.stem_checkboxes["Bass"].isChecked())
        self.assertFalse(window.stem_checkboxes["Drums"].isChecked())

    def test_switching_selected_song_reloads_editor_values(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_target_bpm = 120.0
        window.songs[1].processing_target_bpm = 145.0
        window.songs[0].processing_target_key = "C Major"
        window.songs[1].processing_target_key = "F Minor"

        window.song_table.selectRow(0)
        self.assertEqual(window.target_bpm_edit.text(), "120")
        self.assertEqual(window.target_key_combo.currentData(), "C Major")

        window.song_table.selectRow(1)
        self.assertEqual(window.target_bpm_edit.text(), "145")
        self.assertEqual(window.target_key_combo.currentData(), "F Minor")

    def test_multi_selection_shows_mixed_state(self) -> None:
        window = self._build_window()
        self._import_files(window, ["a.wav", "b.wav"])
        window.songs[0].processing_target_bpm = 120.0
        window.songs[1].processing_target_bpm = 140.0
        window.songs[0].processing_target_key = "A Minor"
        window.songs[1].processing_target_key = "C Major"
        window.songs[0].reference_song_path = "ref_a.wav"
        window.songs[1].reference_song_path = "ref_b.wav"

        self._select_rows(window, [0, 1])

        self.assertEqual(window.editor_scope_label.text(), "Editing Songs: 2")
        self.assertEqual(window.target_bpm_edit.text(), "")
        self.assertEqual(window.target_bpm_edit.placeholderText(), "Mixed")
        self.assertEqual(window.target_key_combo.currentText(), "Mixed")
        self.assertEqual(window.reference_combo.currentText(), "Mixed")

    def test_editing_single_song_updates_song_processing_fields(self) -> None:
        window = self._build_window()
        paths = self._import_files(window, ["edit.wav", "reference.wav"])
        window.song_table.selectRow(0)

        window.target_bpm_edit.setText("128")
        window.target_bpm_edit.editingFinished.emit()
        window.target_key_combo.setCurrentText("A Minor")
        reference_index = window.reference_combo.findData(str(paths[1].resolve()))
        window.reference_combo.setCurrentIndex(reference_index)

        window.stem_checkboxes["Instrumental / No vocals"].setCheckState(Qt.CheckState.Unchecked)
        window.stem_checkboxes["Drums"].setCheckState(Qt.CheckState.Unchecked)
        window.stem_checkboxes["Other"].setCheckState(Qt.CheckState.Unchecked)

        song = window.songs[0]
        self.assertEqual(song.processing_target_bpm, 128.0)
        self.assertEqual(song.processing_target_key, "A Minor")
        self.assertEqual(song.reference_song_path, str(paths[1].resolve()))
        self.assertEqual(song.processing_selected_stems, ["Vocals", "Bass"])
        self.assertTrue(song.processing_override_enabled)

    def test_editing_multi_selection_applies_to_all_selected_songs(self) -> None:
        window = self._build_window()
        paths = self._import_files(window, ["first.wav", "second.wav", "reference.wav"])
        self._select_rows(window, [0, 1])

        window.target_key_combo.setCurrentText("C Major")
        reference_index = window.reference_combo.findData(str(paths[2].resolve()))
        window.reference_combo.setCurrentIndex(reference_index)

        self.assertEqual(window.songs[0].processing_target_key, "C Major")
        self.assertEqual(window.songs[1].processing_target_key, "C Major")
        self.assertEqual(window.songs[0].reference_song_path, str(paths[2].resolve()))
        self.assertEqual(window.songs[1].reference_song_path, str(paths[2].resolve()))

    def test_mixed_multi_selection_prompts_before_overriding_target_key(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_target_key = "A Minor"
        window.songs[1].processing_target_key = "C Major"
        self._select_rows(window, [0, 1])

        with patch("main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            window.target_key_combo.setCurrentText("G Major")

        self.assertEqual(window.songs[0].processing_target_key, "A Minor")
        self.assertEqual(window.songs[1].processing_target_key, "C Major")
        self.assertEqual(window.target_key_combo.currentText(), "Mixed")

    def test_mixed_multi_selection_can_confirm_override(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_target_bpm = 120.0
        window.songs[1].processing_target_bpm = 140.0
        self._select_rows(window, [0, 1])

        with patch("main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            window.target_bpm_edit.setText("128")
            window.target_bpm_edit.editingFinished.emit()

        self.assertEqual(window.songs[0].processing_target_bpm, 128.0)
        self.assertEqual(window.songs[1].processing_target_bpm, 128.0)

    def test_output_folder_stays_global_when_selection_changes(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.output_dir_edit.setText("D:/exports")

        window.song_table.selectRow(0)
        self.assertEqual(window.output_dir_edit.text(), "D:/exports")

        window.song_table.selectRow(1)
        self.assertEqual(window.output_dir_edit.text(), "D:/exports")

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

    def test_compatible_keys_tooltip_includes_camelot_values(self) -> None:
        window = self._build_window()
        self._import_files(window, ["camelot.wav"])

        song = window.songs[0]
        song.musical_key = "D# Minor"
        song.relative_key = "F# Major"
        song.compatible_keys = ["G# Minor", "C# Major"]
        window._populate_song_row(0, song)

        self.assertEqual(window.song_table.item(0, 7).text(), "2A")
        self.assertEqual(
            window.song_table.item(0, 9).toolTip(),
            "Compatible Keys: G# Minor (1A, A♭ Minor), C# Major (3B, D♭ Major)",
        )
        self.assertIn("Alternate: E♭ Minor", window.song_table.item(0, 6).toolTip())

    def test_key_display_preference_updates_visible_key_labels(self) -> None:
        window = self._build_window()
        self._import_files(window, ["display_pref.wav"])

        song = window.songs[0]
        song.musical_key = "D# Minor"
        song.relative_key = "F# Major"
        song.compatible_keys = ["G# Minor", "C# Major"]
        window._populate_song_row(0, song)

        window.set_key_display_preference("prefer_flats")

        self.assertEqual(window.song_table.item(0, 6).text(), "E♭ Minor")
        self.assertEqual(window.song_table.item(0, 8).text(), "G♭ Major")
        self.assertEqual(window.song_table.item(0, 9).text(), "A♭ Minor, D♭ Major")
        self.assertEqual(window.target_key_combo.itemText(window.target_key_combo.findData("C# Major")), "D♭ Major")
        self.assertIn("E♭ Minor", window.reference_combo.itemText(1))

    def test_start_analyze_task_blocks_when_runtime_issue_exists(self) -> None:
        window = self._build_window()
        self._import_files(window, ["demo.wav"])
        window.song_table.selectRow(0)

        with patch("main_window.action_runtime_issues", return_value=["Runtime issue"]), patch.object(
            window, "show_warning", Mock()
        ) as show_warning:
            window.start_analyze_task()

        show_warning.assert_called_once()
        self.assertIsNone(window.current_worker)

    def test_match_tempo_uses_song_bound_target_without_reference(self) -> None:
        window = self._build_window()
        self._import_files(window, ["override_match.wav"])
        window.song_table.selectRow(0)
        window.songs[0].processing_target_bpm = 128.0

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "start_worker", Mock()
        ) as start_worker, patch.object(window, "show_warning", Mock()) as show_warning:
            window.start_processing_task("match_tempo")

        show_warning.assert_not_called()
        start_worker.assert_called_once()

    def test_processing_requires_output_folder_for_auto_export(self) -> None:
        window = self._build_window()
        self._import_files(window, ["auto_export_required.wav"])
        window.song_table.selectRow(0)
        window.songs[0].processing_target_bpm = 128.0
        window.output_dir_edit.clear()

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "start_worker", Mock()
        ) as start_worker, patch.object(window, "show_warning", Mock()) as show_warning:
            window.start_processing_task("match_tempo")

        start_worker.assert_not_called()
        show_warning.assert_called_once_with(
            "Choose an output folder before processing. TuneMatrix exports processed results automatically."
        )

    def test_match_key_requires_song_bound_target_or_reference(self) -> None:
        window = self._build_window()
        self._import_files(window, ["match_key.wav"])
        window.song_table.selectRow(0)

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "show_warning", Mock()
        ) as show_warning:
            window.start_processing_task("match_key")

        show_warning.assert_called_once()
        self.assertIn("Target Key", show_warning.call_args[0][0])

    def test_collect_project_state_serializes_song_bound_processing_and_global_output(self) -> None:
        window = self._build_window()
        paths = self._import_files(window, ["demo.wav"])

        song = window.songs[0]
        song.bpm_range_label = "90 - 120 BPM"
        song.analysis_key_hint = "G Major"
        song.processing_target_bpm = 126.0
        song.processing_target_key = "A Minor"
        song.processing_selected_stems = ["Vocals", "Bass"]
        song.reference_song_path = str(paths[0].resolve())
        window.output_dir_edit.setText("C:/exports")

        state = window.collect_project_state()

        self.assertEqual(state["format_version"], PROJECT_STATE_VERSION)
        self.assertEqual(state["songs"][0]["processing_target_bpm"], 126.0)
        self.assertEqual(state["songs"][0]["processing_target_key"], "A Minor")
        self.assertEqual(state["songs"][0]["processing_selected_stems"], ["Vocals", "Bass"])
        self.assertEqual(state["songs"][0]["reference_song_path"], str(paths[0].resolve()))
        self.assertEqual(state["ui"], {"output_dir": "C:/exports", "key_display_preference": "auto"})

    def test_apply_project_state_restores_song_bound_processing_controls(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "restored.wav"
            ref_path = Path(temp_dir) / "reference.wav"
            wav_path.write_bytes(b"test")
            ref_path.write_bytes(b"test")

            window.apply_project_state(
                {
                    "format_version": PROJECT_STATE_VERSION,
                    "songs": [
                        {
                            "file_path": str(wav_path),
                            "file_name": "restored.wav",
                            "processing_target_bpm": 132.0,
                            "processing_target_key": "A Minor",
                            "processing_selected_stems": ["Vocals", "Bass"],
                            "reference_song_path": str(ref_path),
                            "status": "Imported",
                        },
                        {
                            "file_path": str(ref_path),
                            "file_name": "reference.wav",
                            "status": "Imported",
                        },
                    ],
                    "ui": {
                        "output_dir": "D:/processed",
                        "key_display_preference": "prefer_flats",
                    },
                }
            )

        window.song_table.selectRow(0)

        self.assertEqual(window.output_dir_edit.text(), "D:/processed")
        self.assertEqual(window.key_display_preference, "prefer_flats")
        self.assertEqual(window.target_bpm_edit.text(), "132")
        self.assertEqual(window.target_key_combo.currentData(), "A Minor")
        self.assertEqual(window.reference_combo.currentData(), str(ref_path))
        self.assertTrue(window.stem_checkboxes["Vocals"].isChecked())
        self.assertTrue(window.stem_checkboxes["Bass"].isChecked())

    def test_apply_project_state_migrates_legacy_global_processing_settings_to_songs(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "legacy.wav"
            ref_path = Path(temp_dir) / "reference.wav"
            wav_path.write_bytes(b"test")
            ref_path.write_bytes(b"test")

            window.apply_project_state(
                {
                    "format_version": 1,
                    "songs": [
                        {
                            "file_path": str(wav_path),
                            "file_name": "legacy.wav",
                            "status": "Imported",
                        },
                        {
                            "file_path": str(ref_path),
                            "file_name": "reference.wav",
                            "status": "Imported",
                        },
                    ],
                    "ui": {
                        "target_bpm_text": "128",
                        "target_key": "C Minor",
                        "selected_stems": ["Bass", "Drums"],
                        "use_reference_bpm": True,
                        "reference_song_path": str(ref_path),
                        "output_dir": "D:/processed",
                    },
                }
            )

        migrated_song = window.songs[0]
        self.assertEqual(migrated_song.processing_target_bpm, 128.0)
        self.assertEqual(migrated_song.processing_target_key, "C Minor")
        self.assertEqual(migrated_song.processing_selected_stems, ["Bass", "Drums"])
        self.assertEqual(migrated_song.reference_song_path, str(ref_path))

    def test_manual_bpm_range_prompt_updates_song_value(self) -> None:
        window = self._build_window()
        self._import_files(window, ["manual_prompt.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)

        manual_index = next(index for index in range(bpm_range_combo.count()) if bpm_range_combo.itemText(index) == "Enter BPM...")
        with patch("main_window.QInputDialog.getText", return_value=("128", True)):
            bpm_range_combo.setCurrentIndex(manual_index)

        self.assertEqual(window.songs[0].bpm_range_label, "128")
        self.assertEqual(window._table_combo_at(0, 2).currentText(), "128")


if __name__ == "__main__":
    unittest.main()
