from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QItemSelectionModel, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QGraphicsOpacityEffect

from main_window import MainWindow, PROJECT_STATE_VERSION
from models import (
    PROCESSING_MODE_DEFAULT,
    PROCESSING_MODE_FAST_PREVIEW,
    PROCESSING_MODE_VOCAL,
    ProcessingOptions,
    SongStatus,
    STEM_SOURCE_LATEST,
    STEM_SOURCE_ORIGINAL,
)
from workers import AnalyzeWorker, ProcessingWorker


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
        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(window, "start_worker", Mock()):
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
        self.assertTrue(all(not row["checkbox"].isEnabled() for row in window.workflow_step_rows.values()))
        self.assertEqual(window.target_bpm_edit.cursor().shape(), Qt.CursorShape.ForbiddenCursor)
        self.assertIsInstance(window.song_bound_section.graphicsEffect(), QGraphicsOpacityEffect)

        window.song_table.selectRow(0)

        self.assertTrue(window.remove_button.isEnabled())
        self.assertTrue(window.analyze_button.isEnabled())
        self.assertTrue(window.export_action.isEnabled())
        self.assertTrue(all(row["checkbox"].isEnabled() for row in window.workflow_step_rows.values()))
        self.assertEqual(window.target_bpm_edit.cursor().shape(), Qt.CursorShape.IBeamCursor)
        self.assertIsNone(window.song_bound_section.graphicsEffect())

    def test_table_header_is_hidden_when_empty_and_visible_with_songs(self) -> None:
        window = self._build_window()

        self.assertTrue(window.song_table.horizontalHeader().isHidden())
        self.assertEqual(
            window.song_table.empty_state_text,
            "No songs imported yet.\nClick Import Songs or drag and drop audio files here.",
        )
        self.assertTrue(all(not checkbox.isChecked() for checkbox in window.stem_checkboxes.values()))

        self._import_files(window, ["header.wav"])
        self.assertFalse(window.song_table.horizontalHeader().isHidden())

        window.clear_songs()
        self.assertTrue(window.song_table.horizontalHeader().isHidden())

    def test_clickable_controls_use_pointing_hand_cursor(self) -> None:
        window = self._build_window()
        self._import_files(window, ["cursor.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)
        key_hint_combo = window._table_combo_at(0, 3)
        window.song_table.selectRow(0)
        self.app.processEvents()

        self.assertEqual(window.import_button.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(bpm_range_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(key_hint_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(window.target_key_combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
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

    def test_combo_boxes_ignore_mouse_wheel_changes(self) -> None:
        window = self._build_window()
        self._import_files(window, ["wheel.wav"])
        window.song_table.selectRow(0)

        bpm_range_combo = window._table_combo_at(0, 2)
        key_hint_combo = window._table_combo_at(0, 3)
        target_key_combo = window.target_key_combo

        bpm_range_combo.setCurrentIndex(0)
        key_hint_combo.setCurrentIndex(0)
        target_key_combo.setCurrentIndex(0)

        for combo in [bpm_range_combo, key_hint_combo, target_key_combo]:
            before = combo.currentIndex()
            event = QWheelEvent(
                combo.rect().center(),
                combo.mapToGlobal(combo.rect().center()),
                QPoint(0, 0),
                QPoint(0, 120),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.ScrollUpdate,
                False,
            )
            QApplication.sendEvent(combo, event)
            self.assertEqual(combo.currentIndex(), before)

    def test_build_processing_options_only_uses_global_output_dir(self) -> None:
        window = self._build_window()
        window.output_dir_edit.setText("C:/temp/export")

        options = window.build_processing_options()

        self.assertEqual(options.output_dir, "C:/temp/export")
        self.assertIsNone(options.target_bpm)
        self.assertIsNone(options.target_key)
        self.assertEqual(options.workflow_steps, ["match_key", "match_tempo", "separate"])

    def test_output_folder_field_is_read_only_display(self) -> None:
        window = self._build_window()

        self.assertTrue(window.output_dir_edit.isReadOnly())
        self.assertEqual(window.output_dir_edit.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertTrue(window.output_browse_button.isEnabled())

    def test_workflow_visualization_uses_fixed_order(self) -> None:
        window = self._build_window()

        self.assertEqual([workflow_step.step_id for workflow_step in window.workflow_steps], ["match_key", "match_tempo", "separate"])
        self.assertEqual(list(window.workflow_step_rows), ["match_key", "match_tempo", "separate"])
        self.assertEqual(window.workflow_step_rows["match_key"]["index"].text(), "1")
        self.assertEqual(window.workflow_step_rows["match_tempo"]["index"].text(), "2")
        self.assertEqual(window.workflow_step_rows["separate"]["index"].text(), "3")
        self.assertGreaterEqual(window.workflow_step_rows["match_key"]["row"].minimumHeight(), 48)

    def test_workflow_button_depends_on_enabled_steps(self) -> None:
        window = self._build_window()
        self._import_files(window, ["workflow_dependency.wav"])
        window.song_table.selectRow(0)

        with patch(
            "main_window.action_base_requirement_message",
            side_effect=lambda action: {"separate": "Stem dependency missing."}.get(action),
        ):
            window._refresh_action_availability()
            self.assertFalse(window.process_all_button.isEnabled())

            for workflow_step in window.workflow_steps:
                if workflow_step.step_id == "separate":
                    workflow_step.enabled = False
            window._populate_workflow_list()
            window._refresh_action_availability()

        self.assertTrue(window.process_all_button.isEnabled())

    def test_process_all_starts_without_order_confirmation(self) -> None:
        window = self._build_window()
        self._import_files(window, ["workflow.wav"])
        window.song_table.selectRow(0)
        window.songs[0].processing_target_bpm = 128.0
        window.songs[0].processing_target_key = "A Minor"

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(window, "start_worker", Mock()) as start_worker:
            window.start_processing_task("process_all")

        start_worker.assert_called_once()

    def test_single_selection_loads_song_bound_values_into_editor(self) -> None:
        window = self._build_window()
        self._import_files(window, ["song_a.wav", "song_b.wav"])

        song = window.songs[0]
        song.processing_target_bpm = 128.0
        song.processing_target_key = "A Minor"
        song.processing_mode = PROCESSING_MODE_VOCAL
        song.processing_tempo_source = STEM_SOURCE_ORIGINAL
        song.processing_selected_stems = ["Vocals", "Bass"]
        song.processing_stem_source = STEM_SOURCE_ORIGINAL
        window.song_table.selectRow(0)

        self.assertEqual(window.editor_scope_label.text(), "Editing Song: song_a.wav")
        self.assertEqual(window.target_bpm_edit.text(), "128")
        self.assertEqual(window.target_key_combo.currentData(), "A Minor")
        self.assertEqual(window.processing_mode_combo.currentData(), PROCESSING_MODE_VOCAL)
        self.assertEqual(window.workflow_step_rows["match_tempo"]["settings_button"].toolTip(), "Tempo Source: Original Track")
        self.assertEqual(window.workflow_step_rows["separate"]["settings_button"].toolTip(), "Stem Source: Original Track")
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
        window.songs[0].processing_mode = PROCESSING_MODE_VOCAL
        window.songs[1].processing_mode = PROCESSING_MODE_FAST_PREVIEW
        window.songs[0].processing_tempo_source = STEM_SOURCE_ORIGINAL
        window.songs[1].processing_tempo_source = STEM_SOURCE_LATEST
        window.songs[0].processing_stem_source = STEM_SOURCE_ORIGINAL
        window.songs[1].processing_stem_source = STEM_SOURCE_LATEST

        window.song_table.selectRow(0)
        self.assertEqual(window.target_bpm_edit.text(), "120")
        self.assertEqual(window.target_key_combo.currentData(), "C Major")
        self.assertEqual(window.processing_mode_combo.currentData(), PROCESSING_MODE_VOCAL)
        self.assertEqual(window.workflow_step_rows["match_tempo"]["settings_button"].toolTip(), "Tempo Source: Original Track")
        self.assertEqual(window.workflow_step_rows["separate"]["settings_button"].toolTip(), "Stem Source: Original Track")

        window.song_table.selectRow(1)
        self.assertEqual(window.target_bpm_edit.text(), "145")
        self.assertEqual(window.target_key_combo.currentData(), "F Minor")
        self.assertEqual(window.processing_mode_combo.currentData(), PROCESSING_MODE_FAST_PREVIEW)
        self.assertEqual(window.workflow_step_rows["match_tempo"]["settings_button"].toolTip(), "Tempo Source: Latest Available Audio")
        self.assertEqual(window.workflow_step_rows["separate"]["settings_button"].toolTip(), "Stem Source: Latest Available Audio")

    def test_multi_selection_shows_mixed_state(self) -> None:
        window = self._build_window()
        self._import_files(window, ["a.wav", "b.wav"])
        window.songs[0].processing_target_bpm = 120.0
        window.songs[1].processing_target_bpm = 140.0
        window.songs[0].processing_target_key = "A Minor"
        window.songs[1].processing_target_key = "C Major"
        window.songs[0].processing_mode = PROCESSING_MODE_VOCAL
        window.songs[0].processing_tempo_source = STEM_SOURCE_ORIGINAL
        window.songs[0].processing_stem_source = STEM_SOURCE_ORIGINAL

        self._select_rows(window, [0, 1])

        self.assertEqual(window.editor_scope_label.text(), "Editing Songs: 2")
        self.assertEqual(window.target_bpm_edit.text(), "")
        self.assertEqual(window.target_bpm_edit.placeholderText(), "Mixed")
        self.assertEqual(window.target_key_combo.currentText(), "Mixed")
        self.assertEqual(window.processing_mode_combo.currentText(), "Mixed")
        self.assertEqual(window.workflow_step_rows["match_tempo"]["settings_button"].toolTip(), "Tempo Source: Mixed")
        self.assertEqual(window.workflow_step_rows["separate"]["settings_button"].toolTip(), "Stem Source: Mixed")

    def test_workflow_visualization_shows_skip_and_partial_states_for_selection(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_target_key = "A Minor"
        window.songs[0].processing_target_bpm = 128.0
        window.songs[0].processing_selected_stems = list(window.stem_checkboxes)
        window.songs[1].processing_selected_stems = []
        self._select_rows(window, [0, 1])

        self.assertEqual(window.workflow_step_rows["match_key"]["summary"].text(), "Runs for 1/2 songs")
        self.assertEqual(window.workflow_step_rows["match_tempo"]["summary"].text(), "Runs for 1/2 songs")
        self.assertEqual(window.workflow_step_rows["separate"]["summary"].text(), "Runs for 1/2 songs")
        self.assertEqual(window.workflow_step_rows["match_key"]["row"].property("workflowState"), "partial")

        window.song_table.selectRow(1)
        self.assertEqual(window.workflow_step_rows["match_key"]["summary"].text(), "Skip: no Target Key")
        self.assertEqual(window.workflow_step_rows["separate"]["summary"].text(), "Skip: no stems selected")
        self.assertEqual(window.workflow_step_rows["separate"]["row"].property("workflowState"), "skipped")

    def test_workflow_visualization_shows_stem_source_for_single_song(self) -> None:
        window = self._build_window()
        self._import_files(window, ["single.wav"])
        window.songs[0].processing_selected_stems = ["Vocals", "Bass"]
        window.songs[0].processing_stem_source = STEM_SOURCE_ORIGINAL

        window.song_table.selectRow(0)

        self.assertEqual(
            window.workflow_step_rows["separate"]["summary"].text(),
            "Source: Original Track • Vocals, Bass",
        )

    def test_workflow_visualization_shows_tempo_source_for_single_song(self) -> None:
        window = self._build_window()
        self._import_files(window, ["single.wav"])
        window.songs[0].processing_target_bpm = 128.0
        window.songs[0].processing_tempo_source = STEM_SOURCE_ORIGINAL

        window.song_table.selectRow(0)

        self.assertEqual(
            window.workflow_step_rows["match_tempo"]["summary"].text(),
            "Input: Original Track • 128 BPM",
        )

    def test_editing_single_song_updates_song_processing_fields(self) -> None:
        window = self._build_window()
        self._import_files(window, ["edit.wav"])
        window.song_table.selectRow(0)

        window.target_bpm_edit.setText("128")
        window.target_bpm_edit.editingFinished.emit()
        window.target_key_combo.setCurrentText("A Minor")
        window.processing_mode_combo.setCurrentIndex(window.processing_mode_combo.findData(PROCESSING_MODE_VOCAL))
        window._apply_tempo_source_value_to_selection(STEM_SOURCE_ORIGINAL)
        window._apply_stem_source_value_to_selection(STEM_SOURCE_ORIGINAL)

        window.stem_checkboxes["Vocals"].setCheckState(Qt.CheckState.Checked)
        window.stem_checkboxes["Bass"].setCheckState(Qt.CheckState.Checked)

        song = window.songs[0]
        self.assertEqual(song.processing_target_bpm, 128.0)
        self.assertEqual(song.processing_target_key, "A Minor")
        self.assertEqual(song.processing_mode, PROCESSING_MODE_VOCAL)
        self.assertEqual(song.processing_tempo_source, STEM_SOURCE_ORIGINAL)
        self.assertEqual(song.processing_selected_stems, ["Vocals", "Bass"])
        self.assertEqual(song.processing_stem_source, STEM_SOURCE_ORIGINAL)
        self.assertTrue(song.processing_override_enabled)

    def test_unchecking_all_stems_keeps_empty_selection(self) -> None:
        window = self._build_window()
        self._import_files(window, ["stems.wav"])
        window.song_table.selectRow(0)

        for checkbox in window.stem_checkboxes.values():
            checkbox.setCheckState(Qt.CheckState.Unchecked)

        song = window.songs[0]
        self.assertEqual(song.processing_selected_stems, [])
        self.assertTrue(all(not checkbox.isChecked() for checkbox in window.stem_checkboxes.values()))

    def test_editing_multi_selection_applies_to_all_selected_songs(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        self._select_rows(window, [0, 1])

        window.target_key_combo.setCurrentText("C Major")

        self.assertEqual(window.songs[0].processing_target_key, "C Major")
        self.assertEqual(window.songs[1].processing_target_key, "C Major")

    def test_mixed_multi_selection_prompts_before_overriding_target_key(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_target_key = "A Minor"
        window.songs[1].processing_target_key = "C Major"
        self._select_rows(window, [0, 1])

        with patch.object(window, "_show_override_confirmation_dialog", return_value=False):
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

        with patch.object(window, "_show_override_confirmation_dialog", return_value=True):
            window.target_bpm_edit.setText("128")
            window.target_bpm_edit.editingFinished.emit()

        self.assertEqual(window.songs[0].processing_target_bpm, 128.0)
        self.assertEqual(window.songs[1].processing_target_bpm, 128.0)

    def test_mixed_multi_selection_can_toggle_stem_for_all_selected_songs(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_selected_stems = ["Vocals"]
        window.songs[1].processing_selected_stems = ["Bass"]
        self._select_rows(window, [0, 1])

        with patch.object(window, "_show_override_confirmation_dialog", return_value=True):
            window.stem_checkboxes["Vocals"].setCheckState(Qt.CheckState.Checked)

        self.assertEqual(window.songs[0].processing_selected_stems, ["Vocals"])
        self.assertEqual(window.songs[1].processing_selected_stems, ["Vocals", "Bass"])

    def test_mixed_multi_selection_can_override_stem_source(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_stem_source = STEM_SOURCE_ORIGINAL
        window.songs[1].processing_stem_source = STEM_SOURCE_LATEST
        self._select_rows(window, [0, 1])

        with patch.object(window, "_show_override_confirmation_dialog", return_value=True):
            window._apply_stem_source_value_to_selection(STEM_SOURCE_ORIGINAL)

        self.assertEqual(window.songs[0].processing_stem_source, STEM_SOURCE_ORIGINAL)
        self.assertEqual(window.songs[1].processing_stem_source, STEM_SOURCE_ORIGINAL)

    def test_mixed_multi_selection_can_override_tempo_source(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_tempo_source = STEM_SOURCE_ORIGINAL
        window.songs[1].processing_tempo_source = STEM_SOURCE_LATEST
        self._select_rows(window, [0, 1])

        with patch.object(window, "_show_override_confirmation_dialog", return_value=True):
            window._apply_tempo_source_value_to_selection(STEM_SOURCE_ORIGINAL)

        self.assertEqual(window.songs[0].processing_tempo_source, STEM_SOURCE_ORIGINAL)
        self.assertEqual(window.songs[1].processing_tempo_source, STEM_SOURCE_ORIGINAL)

    def test_mixed_multi_selection_can_override_processing_mode(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.songs[0].processing_mode = PROCESSING_MODE_VOCAL
        window.songs[1].processing_mode = PROCESSING_MODE_FAST_PREVIEW
        self._select_rows(window, [0, 1])

        with patch.object(window, "_show_override_confirmation_dialog", return_value=True):
            window.processing_mode_combo.setCurrentIndex(window.processing_mode_combo.findData(PROCESSING_MODE_VOCAL))

        self.assertEqual(window.songs[0].processing_mode, PROCESSING_MODE_VOCAL)
        self.assertEqual(window.songs[1].processing_mode, PROCESSING_MODE_VOCAL)

    def test_output_folder_stays_global_when_selection_changes(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        window.output_dir_edit.setText("D:/exports")

        window.song_table.selectRow(0)
        self.assertEqual(window.output_dir_edit.text(), "D:/exports")

        window.song_table.selectRow(1)
        self.assertEqual(window.output_dir_edit.text(), "D:/exports")

    def test_import_auto_analyzes_new_songs(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "auto_import.wav"
            wav_path.write_bytes(b"test")

            with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
                window, "start_worker", Mock()
            ) as start_worker:
                window.import_songs([str(wav_path)])

        start_worker.assert_called_once()
        worker, task_label = start_worker.call_args[0]
        self.assertEqual(task_label, "Auto-analyzing imported songs")
        self.assertIsInstance(worker, AnalyzeWorker)
        self.assertEqual(len(worker.songs), 1)
        self.assertEqual(worker.songs[0].file_name, "auto_import.wav")

    def test_import_queues_auto_analysis_when_task_is_running(self) -> None:
        window = self._build_window()
        window.current_worker = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "queued_import.wav"
            wav_path.write_bytes(b"test")

            with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
                window, "start_worker", Mock()
            ) as start_worker:
                window.import_songs([str(wav_path)])

        start_worker.assert_not_called()
        self.assertEqual(window.songs[0].status, SongStatus.QUEUED_ANALYSIS.value)
        self.assertIn(window.songs[0].file_path, window.pending_auto_analysis_paths)
        self.assertFalse(window.song_table.item(0, 10).icon().isNull())
        window.current_worker = None

    def test_song_table_stays_enabled_while_task_is_running(self) -> None:
        window = self._build_window()
        self._import_files(window, ["table_enabled.wav"])

        window.current_worker = Mock()
        window.set_task_running(True)

        self.assertTrue(window.song_table.isEnabled())
        window.current_worker = None

    def test_multi_selection_editor_stays_editable_during_analysis(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])
        self._select_rows(window, [0, 1])

        window.current_worker = AnalyzeWorker([window.songs[0], window.songs[1]])
        window.set_task_running(True)

        self.assertTrue(window.target_bpm_edit.isEnabled())
        self.assertTrue(window.target_key_combo.isEnabled())
        self.assertTrue(window.processing_mode_combo.isEnabled())
        self.assertTrue(all(checkbox.isEnabled() for checkbox in window.stem_checkboxes.values()))

        with patch.object(window, "_show_override_confirmation_dialog", return_value=True):
            window.target_bpm_edit.setText("128")
            window.target_bpm_edit.editingFinished.emit()

        self.assertEqual(window.songs[0].processing_target_bpm, 128.0)
        self.assertEqual(window.songs[1].processing_target_bpm, 128.0)

        window.current_worker = None

    def test_editor_stays_editable_for_queued_songs_during_other_processing(self) -> None:
        window = self._build_window()
        self._import_files(window, ["processing.wav", "queued.wav"])

        window.current_worker = ProcessingWorker([window.songs[0]], ProcessingOptions(output_dir="C:/exports"), "process_all")
        window.set_task_running(True)
        window.song_table.selectRow(1)

        self.assertTrue(window.target_bpm_edit.isEnabled())
        self.assertTrue(window.target_key_combo.isEnabled())
        self.assertTrue(window.processing_mode_combo.isEnabled())
        self.assertTrue(all(checkbox.isEnabled() for checkbox in window.stem_checkboxes.values()))
        self.assertTrue(all(row["checkbox"].isEnabled() for row in window.workflow_step_rows.values()))
        self.assertTrue(window.workflow_step_rows["match_tempo"]["settings_button"].isEnabled())
        self.assertTrue(window.workflow_step_rows["separate"]["settings_button"].isEnabled())
        self.assertIsNone(window.song_bound_section.graphicsEffect())

        window.target_bpm_edit.setText("128")
        window.target_bpm_edit.editingFinished.emit()
        self.assertEqual(window.songs[1].processing_target_bpm, 128.0)

        window.current_worker = None

    def test_editor_stays_locked_for_song_that_is_actively_processing(self) -> None:
        window = self._build_window()
        self._import_files(window, ["processing.wav", "queued.wav"])

        window.current_worker = ProcessingWorker([window.songs[0]], ProcessingOptions(output_dir="C:/exports"), "process_all")
        window.set_task_running(True)
        window.song_table.selectRow(0)

        self.assertFalse(window.target_bpm_edit.isEnabled())
        self.assertFalse(window.target_key_combo.isEnabled())
        self.assertFalse(window.processing_mode_combo.isEnabled())
        self.assertTrue(all(not checkbox.isEnabled() for checkbox in window.stem_checkboxes.values()))
        self.assertTrue(all(not row["checkbox"].isEnabled() for row in window.workflow_step_rows.values()))
        self.assertFalse(window.workflow_step_rows["match_tempo"]["settings_button"].isEnabled())
        self.assertFalse(window.workflow_step_rows["separate"]["settings_button"].isEnabled())
        self.assertEqual(window.target_bpm_edit.cursor().shape(), Qt.CursorShape.ForbiddenCursor)
        self.assertIsInstance(window.song_bound_section.graphicsEffect(), QGraphicsOpacityEffect)

        window.current_worker = None

    def test_bpm_range_change_triggers_auto_reanalysis(self) -> None:
        window = self._build_window()
        self._import_files(window, ["bpm_reanalyze.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "start_worker", Mock()
        ) as start_worker:
            bpm_range_combo.setCurrentIndex(bpm_range_combo.findText("120 - 140 BPM"))

        start_worker.assert_called_once()
        self.assertEqual(start_worker.call_args[0][1], "Auto-analyzing updated songs")

    def test_hint_change_cancels_active_analysis_and_requeues_latest_values(self) -> None:
        window = self._build_window()
        self._import_files(window, ["first.wav", "second.wav"])

        active_worker = AnalyzeWorker([window.songs[0], window.songs[1]])
        active_worker.cancel = Mock()
        window.current_worker = active_worker

        key_hint_combo = window._table_combo_at(0, 3)
        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "start_worker", Mock()
        ) as start_worker:
            key_hint_combo.setCurrentIndex(key_hint_combo.findData("C Major"))

        active_worker.cancel.assert_called_once()
        start_worker.assert_not_called()
        self.assertIn(window.songs[0].file_path, window.pending_auto_analysis_paths)
        self.assertIn(window.songs[1].file_path, window.pending_auto_analysis_paths)
        window.current_worker = None

    def test_key_hint_change_triggers_auto_reanalysis(self) -> None:
        window = self._build_window()
        self._import_files(window, ["key_reanalyze.wav"])
        key_hint_combo = window._table_combo_at(0, 3)

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "start_worker", Mock()
        ) as start_worker:
            key_hint_combo.setCurrentIndex(key_hint_combo.findData("C Major"))

        start_worker.assert_called_once()
        self.assertEqual(start_worker.call_args[0][1], "Auto-analyzing updated songs")

    def test_import_songs_adds_one_row_and_skips_duplicate(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "demo.wav"
            wav_path.write_bytes(b"test")
            with patch("main_window.action_runtime_issues", return_value=[]), patch.object(window, "start_worker", Mock()):
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

    def test_match_tempo_uses_song_bound_target(self) -> None:
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

    def test_match_key_requires_song_bound_target(self) -> None:
        window = self._build_window()
        self._import_files(window, ["match_key.wav"])
        window.song_table.selectRow(0)

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "show_warning", Mock()
        ) as show_warning:
            window.start_processing_task("match_key")

        show_warning.assert_called_once()
        self.assertIn("Target Key", show_warning.call_args[0][0])

    def test_workflow_allows_missing_target_key_and_skips_that_step(self) -> None:
        window = self._build_window()
        self._import_files(window, ["workflow_optional.wav"])
        window.song_table.selectRow(0)
        window.output_dir_edit.setText("C:/exports")

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "start_worker", Mock()
        ) as start_worker, patch.object(window, "show_warning", Mock()) as show_warning:
            window.start_processing_task("process_all")

        show_warning.assert_not_called()
        start_worker.assert_called_once()

    def test_separate_stems_requires_at_least_one_selected_stem(self) -> None:
        window = self._build_window()
        self._import_files(window, ["separate_validation.wav"])
        window.song_table.selectRow(0)
        window.songs[0].processing_selected_stems = []
        window._load_processing_editor_from_selection()

        with patch("main_window.action_runtime_issues", return_value=[]), patch.object(
            window, "show_warning", Mock()
        ) as show_warning:
            window.start_processing_task("separate")

        show_warning.assert_called_once_with("Select at least one stem before running Separate Stems.")

    def test_collect_project_state_serializes_song_bound_processing_and_global_output(self) -> None:
        window = self._build_window()
        self._import_files(window, ["demo.wav"])
        window.workflow_steps[0].enabled = False

        song = window.songs[0]
        song.bpm_range_label = "90 - 120 BPM"
        song.analysis_key_hint = "G Major"
        song.processing_target_bpm = 126.0
        song.processing_target_key = "A Minor"
        song.processing_mode = PROCESSING_MODE_VOCAL
        song.processing_tempo_source = STEM_SOURCE_ORIGINAL
        song.processing_selected_stems = ["Vocals", "Bass"]
        song.processing_stem_source = STEM_SOURCE_ORIGINAL
        window.output_dir_edit.setText("C:/exports")

        state = window.collect_project_state()

        self.assertEqual(state["format_version"], PROJECT_STATE_VERSION)
        self.assertEqual(state["songs"][0]["processing_target_bpm"], 126.0)
        self.assertEqual(state["songs"][0]["processing_target_key"], "A Minor")
        self.assertEqual(state["songs"][0]["processing_mode"], PROCESSING_MODE_VOCAL)
        self.assertEqual(state["songs"][0]["processing_tempo_source"], STEM_SOURCE_ORIGINAL)
        self.assertEqual(state["songs"][0]["processing_selected_stems"], ["Vocals", "Bass"])
        self.assertEqual(state["songs"][0]["processing_stem_source"], STEM_SOURCE_ORIGINAL)
        self.assertEqual(
            state["ui"],
            {
                "output_dir": "C:/exports",
                "key_display_preference": "auto",
                "workflow_steps": [
                    {"step_id": "match_key", "enabled": False},
                    {"step_id": "match_tempo", "enabled": True},
                    {"step_id": "separate", "enabled": True},
                ],
            },
        )

    def test_apply_project_state_restores_song_bound_processing_controls(self) -> None:
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
                            "processing_target_bpm": 132.0,
                            "processing_target_key": "A Minor",
                            "processing_mode": PROCESSING_MODE_FAST_PREVIEW,
                            "processing_tempo_source": STEM_SOURCE_ORIGINAL,
                            "processing_selected_stems": ["Vocals", "Bass"],
                            "processing_stem_source": STEM_SOURCE_ORIGINAL,
                            "status": "Imported",
                        },
                    ],
                    "ui": {
                        "output_dir": "D:/processed",
                        "key_display_preference": "prefer_flats",
                        "workflow_steps": [
                            {"step_id": "separate", "enabled": True},
                            {"step_id": "match_key", "enabled": False},
                            {"step_id": "match_tempo", "enabled": True},
                        ],
                    },
                }
            )

        window.song_table.selectRow(0)

        self.assertEqual(window.output_dir_edit.text(), "D:/processed")
        self.assertEqual(window.key_display_preference, "prefer_flats")
        self.assertEqual(window.target_bpm_edit.text(), "132")
        self.assertEqual(window.target_key_combo.currentData(), "A Minor")
        self.assertEqual(window.processing_mode_combo.currentData(), PROCESSING_MODE_FAST_PREVIEW)
        self.assertEqual(window.workflow_step_rows["match_tempo"]["settings_button"].toolTip(), "Tempo Source: Original Track")
        self.assertEqual(window.workflow_step_rows["separate"]["settings_button"].toolTip(), "Stem Source: Original Track")
        self.assertTrue(window.stem_checkboxes["Vocals"].isChecked())
        self.assertTrue(window.stem_checkboxes["Bass"].isChecked())
        self.assertEqual(
            [(step.step_id, step.enabled) for step in window.workflow_steps],
            [("match_key", False), ("match_tempo", True), ("separate", True)],
        )

    def test_apply_project_state_migrates_legacy_global_processing_settings_to_songs(self) -> None:
        window = self._build_window()

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "legacy.wav"
            wav_path.write_bytes(b"test")

            window.apply_project_state(
                {
                    "format_version": 1,
                    "songs": [
                        {
                            "file_path": str(wav_path),
                            "file_name": "legacy.wav",
                            "status": "Imported",
                        },
                    ],
                    "ui": {
                        "target_bpm_text": "128",
                        "target_key": "C Minor",
                        "selected_stems": ["Bass", "Drums"],
                        "output_dir": "D:/processed",
                    },
                }
            )

        migrated_song = window.songs[0]
        self.assertEqual(migrated_song.processing_target_bpm, 128.0)
        self.assertEqual(migrated_song.processing_target_key, "C Minor")
        self.assertEqual(migrated_song.processing_mode, PROCESSING_MODE_DEFAULT)
        self.assertEqual(migrated_song.processing_tempo_source, STEM_SOURCE_LATEST)
        self.assertEqual(migrated_song.processing_selected_stems, ["Bass", "Drums"])
        self.assertEqual(migrated_song.processing_stem_source, STEM_SOURCE_LATEST)
        self.assertEqual([step.step_id for step in window.workflow_steps], ["match_key", "match_tempo", "separate"])

    def test_manual_bpm_range_prompt_preserves_exact_decimal_text(self) -> None:
        window = self._build_window()
        self._import_files(window, ["manual_prompt.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)

        manual_index = next(index for index in range(bpm_range_combo.count()) if bpm_range_combo.itemText(index) == "Enter BPM...")
        with patch("main_window.QInputDialog.getText", return_value=("102.474", True)), patch(
            "main_window.action_runtime_issues", return_value=[]
        ), patch.object(window, "start_worker", Mock()):
            bpm_range_combo.setCurrentIndex(manual_index)

        self.assertEqual(window.songs[0].bpm_range_label, "102.474")
        self.assertEqual(window._table_combo_at(0, 2).currentText(), "102.474")

    def test_manual_bpm_range_prompt_preserves_exact_range_text(self) -> None:
        window = self._build_window()
        self._import_files(window, ["manual_range.wav"])
        bpm_range_combo = window._table_combo_at(0, 2)

        manual_index = next(index for index in range(bpm_range_combo.count()) if bpm_range_combo.itemText(index) == "Enter BPM...")
        with patch("main_window.QInputDialog.getText", return_value=("102.474-110.2", True)), patch(
            "main_window.action_runtime_issues", return_value=[]
        ), patch.object(window, "start_worker", Mock()):
            bpm_range_combo.setCurrentIndex(manual_index)

        self.assertEqual(window.songs[0].bpm_range_label, "102.474-110.2")
        self.assertEqual(window._table_combo_at(0, 2).currentText(), "102.474-110.2")


if __name__ == "__main__":
    unittest.main()
