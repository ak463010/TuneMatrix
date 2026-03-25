from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Qt, QTime, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio_processing import action_base_requirement_message, action_runtime_issues, dependency_status_lines
from models import KEY_OPTIONS, ProcessingOptions, SongRecord, SongStatus, STEM_OPTIONS, TABLE_HEADERS
from utils import default_export_dir, format_bpm, format_duration, format_key, is_supported_audio_file, validate_audio_file
from workers import AnalyzeWorker, ProcessingWorker


class AudioTableWidget(QTableWidget):
    files_dropped = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self._extract_paths(event):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._extract_paths(event):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        paths = self._extract_paths(event)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        event.ignore()

    @staticmethod
    def _extract_paths(event) -> list[str]:
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return []

        paths = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            file_path = url.toLocalFile()
            if is_supported_audio_file(file_path):
                paths.append(file_path)
        return paths


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.songs: list[SongRecord] = []
        self.current_thread: Optional[QThread] = None
        self.current_worker = None
        self.task_cancel_requested = False
        self.action_dependency_messages: dict[str, str] = {}

        self.setWindowTitle("TuneMatrix")
        self.resize(1400, 900)

        self._create_actions()
        self._build_ui()
        self._apply_styles()
        self._log_startup_details()
        self._refresh_action_availability()

    def _create_actions(self) -> None:
        self.import_action = QAction("Import Songs", self)
        self.import_action.triggered.connect(self.import_songs)

        self.remove_action = QAction("Remove Selected", self)
        self.remove_action.triggered.connect(self.remove_selected_songs)

        self.clear_action = QAction("Clear List", self)
        self.clear_action.triggered.connect(self.clear_songs)

        self.analyze_action = QAction("Analyze", self)
        self.analyze_action.triggered.connect(self.start_analyze_task)

        self.separate_action = QAction("Separate Stems", self)
        self.separate_action.triggered.connect(lambda: self.start_processing_task("separate"))

        self.match_tempo_action = QAction("Match Tempo", self)
        self.match_tempo_action.triggered.connect(lambda: self.start_processing_task("match_tempo"))

        self.match_key_action = QAction("Match Key", self)
        self.match_key_action.triggered.connect(lambda: self.start_processing_task("match_key"))

        self.process_all_action = QAction("Process All", self)
        self.process_all_action.triggered.connect(lambda: self.start_processing_task("process_all"))

        self.export_action = QAction("Export", self)
        self.export_action.triggered.connect(lambda: self.start_processing_task("export"))

        self.cancel_action = QAction("Cancel Current Task", self)
        self.cancel_action.triggered.connect(self.cancel_current_task)
        self.cancel_action.setEnabled(False)

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.import_action)
        file_menu.addAction(self.remove_action)
        file_menu.addAction(self.clear_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        actions_menu = menu_bar.addMenu("Actions")
        actions_menu.addAction(self.analyze_action)
        actions_menu.addAction(self.separate_action)
        actions_menu.addAction(self.match_tempo_action)
        actions_menu.addAction(self.match_key_action)
        actions_menu.addAction(self.process_all_action)
        actions_menu.addSeparator()
        actions_menu.addAction(self.cancel_action)

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)

        self.song_table = AudioTableWidget()
        self.song_table.setColumnCount(len(TABLE_HEADERS))
        self.song_table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.song_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.song_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.song_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.song_table.setAlternatingRowColors(True)
        self.song_table.setSortingEnabled(False)
        self.song_table.setWordWrap(False)
        self.song_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.song_table.files_dropped.connect(self.import_songs)

        header = self.song_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        controls_panel = self._build_controls_panel()
        controls_panel.setMinimumWidth(320)
        controls_panel.setMaximumWidth(360)

        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setWidget(controls_panel)
        controls_scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        splitter.addWidget(self.song_table)
        splitter.addWidget(controls_scroll)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1180, 320])

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(32)
        main_layout.addWidget(self.progress_bar)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setPlaceholderText("Processing logs will appear here.")
        self.log_console.setFixedHeight(170)
        main_layout.addWidget(self.log_console, 0)

    def _build_controls_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        import_group = QGroupBox("Song Actions")
        import_layout = QVBoxLayout(import_group)
        import_layout.setSpacing(8)
        import_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.import_button = QPushButton("Import Songs")
        self.remove_button = QPushButton("Remove Selected")
        self.clear_button = QPushButton("Clear List")
        self.analyze_button = QPushButton("Analyze")

        for button in [self.import_button, self.remove_button, self.clear_button, self.analyze_button]:
            button.setMinimumHeight(40)
            import_layout.addWidget(button)

        self.import_button.clicked.connect(self.import_songs)
        self.remove_button.clicked.connect(self.remove_selected_songs)
        self.clear_button.clicked.connect(self.clear_songs)
        self.analyze_button.clicked.connect(self.start_analyze_task)

        processing_group = QGroupBox("Processing Options")
        processing_layout = QFormLayout(processing_group)
        processing_layout.setSpacing(10)
        processing_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.reference_checkbox = QCheckBox("Match to reference song")
        self.reference_combo = QComboBox()
        self.reference_combo.addItem("None", None)

        self.target_bpm_edit = QLineEdit()
        self.target_bpm_edit.setPlaceholderText("Example: 128")

        self.target_key_combo = QComboBox()
        self.target_key_combo.addItem("Unchanged", None)
        for key_name in KEY_OPTIONS:
            self.target_key_combo.addItem(key_name, key_name)

        self.stem_option_combo = QComboBox()
        for stem_option in STEM_OPTIONS:
            self.stem_option_combo.addItem(stem_option, stem_option)
        self.stem_option_combo.setCurrentText("All stems")

        processing_layout.addRow(self.reference_checkbox)
        processing_layout.addRow("Reference Song", self.reference_combo)
        processing_layout.addRow("Target BPM", self.target_bpm_edit)
        processing_layout.addRow("Target Key", self.target_key_combo)
        processing_layout.addRow("Stem Output", self.stem_option_combo)

        export_group = QGroupBox("Export")
        export_layout = QHBoxLayout(export_group)
        export_layout.setSpacing(8)
        export_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.output_dir_edit = QLineEdit(default_export_dir())
        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.setMinimumHeight(42)
        export_layout.addWidget(self.output_dir_edit, 1)
        export_layout.addWidget(self.output_browse_button)
        self.output_browse_button.clicked.connect(self.browse_output_folder)

        run_group = QGroupBox("Run Actions")
        run_layout = QVBoxLayout(run_group)
        run_layout.setSpacing(8)
        run_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.separate_button = QPushButton("Separate Stems")
        self.match_tempo_button = QPushButton("Match Tempo")
        self.match_key_button = QPushButton("Match Key")
        self.process_all_button = QPushButton("Process All")
        self.export_button = QPushButton("Export")
        self.cancel_button = QPushButton("Cancel Current Task")
        self.cancel_button.setEnabled(False)

        for button in [
            self.separate_button,
            self.match_tempo_button,
            self.match_key_button,
            self.process_all_button,
            self.export_button,
            self.cancel_button,
        ]:
            button.setMinimumHeight(40)
            run_layout.addWidget(button)

        self.separate_button.clicked.connect(lambda: self.start_processing_task("separate"))
        self.match_tempo_button.clicked.connect(lambda: self.start_processing_task("match_tempo"))
        self.match_key_button.clicked.connect(lambda: self.start_processing_task("match_key"))
        self.process_all_button.clicked.connect(lambda: self.start_processing_task("process_all"))
        self.export_button.clicked.connect(lambda: self.start_processing_task("export"))
        self.cancel_button.clicked.connect(self.cancel_current_task)

        hint_label = QLabel("Tip: drag and drop mp3, wav, flac, or m4a files onto the song table.")
        hint_label.setWordWrap(True)

        layout.addWidget(import_group)
        layout.addWidget(processing_group)
        layout.addWidget(export_group)
        layout.addWidget(run_group)
        layout.addWidget(hint_label)
        layout.addStretch(1)
        return panel

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background-color: #12161d;
                color: #e6edf3;
                font-size: 13px;
            }
            QMainWindow, QMenuBar, QMenu, QGroupBox {
                background-color: #12161d;
                color: #e6edf3;
            }
            QGroupBox {
                border: 1px solid #283242;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #1f6feb;
                border: none;
                border-radius: 6px;
                padding: 9px 12px;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2b7fff;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
            }
            QLineEdit, QComboBox, QPlainTextEdit, QTableWidget {
                background-color: #0d1117;
                border: 1px solid #283242;
                border-radius: 6px;
                padding: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1117;
                color: #e6edf3;
                selection-background-color: #1f6feb;
            }
            QHeaderView::section {
                background-color: #1b2430;
                color: #e6edf3;
                border: 0;
                padding: 8px;
                font-weight: 600;
            }
            QTableWidget {
                gridline-color: #243041;
                alternate-background-color: #111827;
                selection-background-color: #1f6feb;
                selection-color: white;
            }
            QProgressBar {
                border: 1px solid #283242;
                border-radius: 6px;
                background-color: #0d1117;
                text-align: center;
                min-height: 22px;
            }
            QProgressBar::chunk {
                background-color: #2ea043;
                border-radius: 5px;
            }
            """
        )

    def _log_startup_details(self) -> None:
        self.append_log("TuneMatrix ready.")
        for line in dependency_status_lines():
            self.append_log(line)
        for action_name, message in self._collect_base_action_messages().items():
            self.append_log(f"{action_name.replace('_', ' ').title()} disabled: {message}")

    def _action_controls(self) -> dict[str, list[object]]:
        return {
            "analyze": [self.analyze_button, self.analyze_action],
            "separate": [self.separate_button, self.separate_action],
            "match_tempo": [self.match_tempo_button, self.match_tempo_action],
            "match_key": [self.match_key_button, self.match_key_action],
            "process_all": [self.process_all_button, self.process_all_action],
            "export": [self.export_button, self.export_action],
        }

    def _collect_base_action_messages(self) -> dict[str, str]:
        messages: dict[str, str] = {}
        for action_name in self._action_controls():
            message = action_base_requirement_message(action_name)
            if message:
                messages[action_name] = message
        return messages

    def _apply_control_hint(self, control: object, message: str) -> None:
        if hasattr(control, "setToolTip"):
            control.setToolTip(message)
        if isinstance(control, QAction):
            control.setStatusTip(message)

    def _refresh_action_availability(self) -> None:
        self.action_dependency_messages = self._collect_base_action_messages()

        for action_name, controls in self._action_controls().items():
            message = self.action_dependency_messages.get(action_name, "")
            enabled = self.current_worker is None and not message
            for control in controls:
                control.setEnabled(enabled)
                self._apply_control_hint(control, message)

    def append_log(self, message: str) -> None:
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        self.log_console.appendPlainText(f"[{timestamp}] {message}")
        self.log_console.verticalScrollBar().setValue(self.log_console.verticalScrollBar().maximum())

    def import_songs(self, paths: Optional[list[str]] = None) -> None:
        if self.current_worker is not None:
            self.show_warning("A task is running. Import new songs after it finishes or cancel it first.")
            return

        if not isinstance(paths, list):
            selected_files, _ = QFileDialog.getOpenFileNames(
                self,
                "Import Songs",
                "",
                "Audio Files (*.mp3 *.wav *.flac *.m4a)",
            )
            paths = selected_files

        if not paths:
            return

        existing_paths = {song.file_path for song in self.songs}
        added_count = 0
        for raw_path in paths:
            resolved = str(Path(raw_path).resolve())
            valid, message = validate_audio_file(resolved)
            if not valid:
                self.append_log(message)
                continue
            if resolved in existing_paths:
                self.append_log(f"Skipped duplicate file: {Path(resolved).name}")
                continue

            song = SongRecord.from_path(resolved)
            self.songs.append(song)
            self._append_song_row(song)
            existing_paths.add(resolved)
            added_count += 1
            self.append_log(f"Imported {song.file_name}")
            file_issues = action_runtime_issues("analyze", [resolved])
            for issue in dict.fromkeys(file_issues):
                self.append_log(f"{song.file_name}: {issue}")

        if added_count:
            self.refresh_reference_combo()

    def remove_selected_songs(self) -> None:
        if self.current_worker is not None:
            self.show_warning("Cancel the current task before modifying the song list.")
            return

        rows = self.selected_rows()
        if not rows:
            self.show_warning("Select at least one song to remove.")
            return

        for row in sorted(rows, reverse=True):
            removed_song = self.songs.pop(row)
            self.song_table.removeRow(row)
            self.append_log(f"Removed {removed_song.file_name}")

        self.refresh_reference_combo()

    def clear_songs(self) -> None:
        if self.current_worker is not None:
            self.show_warning("Cancel the current task before clearing the song list.")
            return

        if not self.songs:
            return

        self.songs.clear()
        self.song_table.setRowCount(0)
        self.refresh_reference_combo()
        self.progress_bar.setValue(0)
        self.append_log("Cleared the song list.")

    def selected_rows(self) -> list[int]:
        selection_model = self.song_table.selectionModel()
        if selection_model is None:
            return []
        rows = sorted({index.row() for index in selection_model.selectedRows()})
        return rows

    def selected_or_all_songs(self) -> list[SongRecord]:
        if not self.songs:
            return []
        rows = self.selected_rows()
        if not rows:
            return list(self.songs)
        return [self.songs[row] for row in rows]

    def get_reference_song(self) -> Optional[SongRecord]:
        reference_path = self.reference_combo.currentData()
        if not reference_path:
            return None
        for song in self.songs:
            if song.file_path == reference_path:
                return song
        return None

    def start_analyze_task(self) -> None:
        if not self.songs:
            self.show_warning("Import at least one song before analyzing.")
            return
        if self.current_worker is not None:
            self.show_warning("A task is already running.")
            return

        songs = self.selected_or_all_songs()
        runtime_issues = list(dict.fromkeys(action_runtime_issues("analyze", [song.file_path for song in songs])))
        if runtime_issues:
            message = "\n".join(runtime_issues)
            self.append_log(message)
            self.show_warning(message)
            return
        worker = AnalyzeWorker(songs)
        self.start_worker(worker, "Analyzing songs")

    def start_processing_task(self, action: str) -> None:
        if not self.songs:
            self.show_warning("Import at least one song before processing.")
            return
        if self.current_worker is not None:
            self.show_warning("A task is already running.")
            return

        if action == "process_all":
            songs = list(self.songs)
        else:
            songs = self.selected_or_all_songs()

        if not songs:
            self.show_warning("Select at least one song.")
            return

        runtime_issues = list(dict.fromkeys(action_runtime_issues(action, [song.file_path for song in songs])))
        if runtime_issues:
            message = "\n".join(runtime_issues)
            self.append_log(message)
            self.show_warning(message)
            return

        options = self.build_processing_options()
        reference_song = self.get_reference_song()
        bpm_text = self.target_bpm_edit.text().strip()

        if action in {"match_tempo", "process_all"} and bpm_text:
            if options.target_bpm is None:
                self.show_warning("Target BPM must be a number.")
                return
            if options.target_bpm <= 0:
                self.show_warning("Target BPM must be greater than zero.")
                return

        if options.match_to_reference and reference_song is None:
            self.show_warning("Choose a reference song or turn off reference matching.")
            return

        if action == "match_tempo" and not options.match_to_reference and options.target_bpm is None:
            self.show_warning("Enter a target BPM or enable reference matching.")
            return

        if action == "match_key" and not options.match_to_reference and not options.target_key:
            self.show_warning("Choose a target key or enable reference matching.")
            return

        if action == "export" and not self.output_dir_edit.text().strip():
            self.show_warning("Choose an export folder before exporting.")
            return

        worker = ProcessingWorker(songs, options, action, reference_song=reference_song)
        self.start_worker(worker, action.replace("_", " ").title())

    def build_processing_options(self) -> ProcessingOptions:
        bpm_value = None
        bpm_text = self.target_bpm_edit.text().strip()
        if bpm_text:
            try:
                bpm_value = float(bpm_text)
            except ValueError:
                bpm_value = None

        return ProcessingOptions(
            stem_option=self.stem_option_combo.currentData() or "All stems",
            target_bpm=bpm_value,
            target_key=self.target_key_combo.currentData(),
            match_to_reference=self.reference_checkbox.isChecked(),
            reference_song_path=self.reference_combo.currentData(),
            output_dir=self.output_dir_edit.text().strip() or None,
        )

    def start_worker(self, worker, task_label: str) -> None:
        self.progress_bar.setValue(0)
        self.task_cancel_requested = False
        self.current_worker = worker
        self.current_thread = QThread(self)
        worker.moveToThread(self.current_thread)

        self.current_thread.started.connect(worker.run)
        worker.progress.connect(self.progress_bar.setValue)
        worker.log.connect(self.append_log)
        worker.song_updated.connect(self.on_song_updated)
        worker.error.connect(self.on_worker_error)
        worker.finished.connect(self.on_worker_finished)
        worker.finished.connect(self.current_thread.quit)
        worker.finished.connect(worker.deleteLater)
        self.current_thread.finished.connect(self.current_thread.deleteLater)

        self.set_task_running(True)
        self.append_log(f"{task_label} started.")
        self.current_thread.start()

    def cancel_current_task(self) -> None:
        if self.current_worker is None:
            self.append_log("No active task to cancel.")
            return
        self.task_cancel_requested = True
        self.current_worker.cancel()

    def on_song_updated(self, song: SongRecord) -> None:
        row = self.find_song_row(song.file_path)
        if row is None:
            return
        self._populate_song_row(row, song)
        self.refresh_reference_combo()

    def find_song_row(self, file_path: str) -> Optional[int]:
        for index, song in enumerate(self.songs):
            if song.file_path == file_path:
                return index
        return None

    def on_worker_error(self, message: str) -> None:
        self.show_error(message)

    def on_worker_finished(self) -> None:
        self.current_worker = None
        self.current_thread = None
        self.set_task_running(False)
        if not self.task_cancel_requested:
            self.progress_bar.setValue(100 if self.songs else 0)
        self.append_log("Task canceled." if self.task_cancel_requested else "Task finished.")

    def set_task_running(self, running: bool) -> None:
        always_available_controls = [
            self.import_button,
            self.remove_button,
            self.clear_button,
            self.import_action,
            self.remove_action,
            self.clear_action,
        ]

        for control in always_available_controls:
            control.setEnabled(not running)

        self.cancel_button.setEnabled(running)
        self.cancel_action.setEnabled(running)
        self._refresh_action_availability()

    def refresh_reference_combo(self) -> None:
        current_value = self.reference_combo.currentData()
        self.reference_combo.blockSignals(True)
        self.reference_combo.clear()
        self.reference_combo.addItem("None", None)
        for song in self.songs:
            label = f"{song.file_name} | {format_bpm(song.bpm)} BPM | {format_key(song.musical_key)}"
            self.reference_combo.addItem(label, song.file_path)

        if current_value:
            index = self.reference_combo.findData(current_value)
            if index >= 0:
                self.reference_combo.setCurrentIndex(index)
        self.reference_combo.blockSignals(False)

    def browse_output_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose Output Folder", self.output_dir_edit.text().strip())
        if directory:
            self.output_dir_edit.setText(directory)
            self.append_log(f"Output folder set to {directory}")

    def _append_song_row(self, song: SongRecord) -> None:
        row = self.song_table.rowCount()
        self.song_table.insertRow(row)
        self._populate_song_row(row, song)

    def _populate_song_row(self, row: int, song: SongRecord) -> None:
        values = [
            song.file_name,
            song.file_path,
            format_duration(song.duration),
            format_bpm(song.bpm),
            format_key(song.musical_key),
            song.status,
        ]
        for column, value in enumerate(values):
            item = self.song_table.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.song_table.setItem(row, column, item)
            item.setText(str(value))
            if column == 5 and song.status == SongStatus.ERROR.value:
                item.setToolTip(song.last_error or "Task failed.")
            elif column == 5:
                item.setToolTip("")

    def show_warning(self, message: str) -> None:
        QMessageBox.warning(self, "TuneMatrix", message)

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "TuneMatrix", message)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.current_worker is not None:
            self.show_warning("A task is still running. Cancel it before closing the app.")
            event.ignore()
            return
        event.accept()
