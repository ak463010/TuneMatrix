from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPoint, QSize, QThread, Qt, QTime, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QMenu,
)

from audio_processing import action_base_requirement_message, action_runtime_issues, dependency_status_lines
from models import (
    BPM_RANGE_DEFAULT_LABEL,
    BPM_RANGE_MANUAL_LABEL,
    BPM_RANGE_OPTIONS,
    KEY_OPTIONS,
    ProcessingOptions,
    SongRecord,
    SongStatus,
    STEM_OPTIONS,
    TABLE_HEADERS,
)
from utils import (
    KEY_DISPLAY_AUTO,
    KEY_DISPLAY_PREFERENCE_OPTIONS,
    alternate_key_notation,
    camelot_for_key,
    default_export_dir,
    format_bpm,
    format_camelot,
    format_duration,
    format_key,
    format_key_list,
    is_supported_audio_file,
    normalize_key_display_preference,
    validate_audio_file,
)
from workers import AnalyzeWorker, ProcessingWorker

PROJECT_STATE_VERSION = 2
PROJECT_FILE_SUFFIX = ".tunematrix.json"
PROJECT_FILE_FILTER = "TuneMatrix Project (*.tunematrix.json);;JSON Files (*.json)"
ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"
STEM_CHECKBOX_OPTIONS = [
    ("Vocals", "Vocals"),
    ("Instrumental", "Instrumental / No vocals"),
    ("Drums", "Drums"),
    ("Bass", "Bass"),
    ("Other", "Other"),
]


class AudioTableWidget(QTableWidget):
    files_dropped = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.empty_state_text = ""

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

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        self._update_hover_cursor(event.position().toPoint())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self.viewport().unsetCursor()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self.rowCount() != 0 or not self.empty_state_text:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(QColor("#7f8ba0"))
        painter.drawText(
            self.viewport().rect().adjusted(24, 24, -24, -24),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.empty_state_text,
        )
        painter.end()

    def _update_hover_cursor(self, pos: QPoint) -> None:
        if self.indexAt(pos).isValid():
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            return
        self.viewport().unsetCursor()

    def set_empty_state_text(self, text: str) -> None:
        self.empty_state_text = text
        self.viewport().update()

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


class MixedStateCheckBox(QCheckBox):
    def nextCheckState(self) -> None:  # type: ignore[override]
        if self.checkState() == Qt.CheckState.Checked:
            self.setCheckState(Qt.CheckState.Unchecked)
            return
        self.setCheckState(Qt.CheckState.Checked)


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()


class WindowTitleBar(QFrame):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self._window = window
        self._drag_offset: Optional[QPoint] = None
        self.setObjectName("windowTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        lights = QHBoxLayout()
        lights.setSpacing(8)
        lights.setContentsMargins(0, 0, 0, 0)
        for color_name in ["#ff6157", "#f7c64d", "#64ce5c"]:
            dot = QLabel()
            dot.setObjectName("trafficLight")
            dot.setStyleSheet(f"background-color: {color_name}; border-radius: 7px;")
            dot.setFixedSize(14, 14)
            lights.addWidget(dot)

        lights_widget = QWidget()
        lights_widget.setLayout(lights)
        layout.addWidget(lights_widget, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("TuneMatrix")
        title.setObjectName("windowTitleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title, 1)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(2)

        self.minimize_button = QPushButton("−")
        self.maximize_button = QPushButton("□")
        self.close_button = QPushButton("×")

        for button, handler in [
            (self.minimize_button, self._window.showMinimized),
            (self.maximize_button, self.toggle_maximized),
            (self.close_button, self._window.close),
        ]:
            button.setObjectName("windowControlButton")
            button.setFixedSize(28, 22)
            button.clicked.connect(handler)
            controls.addWidget(button)

        controls_widget = QWidget()
        controls_widget.setLayout(controls)
        layout.addWidget(controls_widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self.sync_window_state()

    def sync_window_state(self) -> None:
        self.maximize_button.setText("❐" if self._window.isMaximized() else "□")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton and not self._window.isMaximized():
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.songs: list[SongRecord] = []
        self.pending_auto_analysis_paths: list[str] = []
        self.current_thread: Optional[QThread] = None
        self.current_worker = None
        self.task_cancel_requested = False
        self.action_dependency_messages: dict[str, str] = {}
        self._sidebar_binding_in_progress = False
        self.key_display_preference = KEY_DISPLAY_AUTO

        self.setWindowTitle("TuneMatrix")
        self.resize(1400, 900)

        self._create_actions()
        self._build_ui()
        self._apply_interaction_cursors()
        self._apply_styles()
        self._log_startup_details()
        self._refresh_action_availability()

    def _create_actions(self) -> None:
        self.open_project_action = QAction("Open Project", self)
        self.open_project_action.triggered.connect(self.open_project)

        self.save_project_action = QAction("Save Project", self)
        self.save_project_action.triggered.connect(self.save_project)

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

        self.export_action = QAction("Export Cached Results", self)
        self.export_action.triggered.connect(lambda: self.start_processing_task("export"))

        self.cancel_action = QAction("Cancel Current Task", self)
        self.cancel_action.triggered.connect(self.cancel_current_task)
        self.cancel_action.setEnabled(False)

        self.about_action = QAction("About TuneMatrix", self)
        self.about_action.triggered.connect(
            lambda: QMessageBox.information(self, "TuneMatrix", "TuneMatrix\nDesktop music processing app")
        )

        self.file_menu = QMenu("File", self)
        self.file_menu.addAction(self.open_project_action)
        self.file_menu.addAction(self.save_project_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.import_action)
        self.file_menu.addAction(self.export_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction("Exit", self.close)

        self.edit_menu = QMenu("Edit", self)
        self.edit_menu.addAction(self.remove_action)
        self.edit_menu.addAction(self.clear_action)

        self.tools_menu = QMenu("Tools", self)
        self.tools_menu.addAction(self.analyze_action)
        self.tools_menu.addAction(self.separate_action)
        self.tools_menu.addAction(self.match_tempo_action)
        self.tools_menu.addAction(self.match_key_action)
        self.tools_menu.addAction(self.process_all_action)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.cancel_action)

        self.help_menu = QMenu("Help", self)
        self.help_menu.addAction(self.about_action)

        self.key_display_menu = QMenu("Key Display", self)
        self.key_display_action_group = QActionGroup(self)
        self.key_display_action_group.setExclusive(True)
        self.key_display_actions: dict[str, QAction] = {}
        for label, preference in KEY_DISPLAY_PREFERENCE_OPTIONS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, value=preference: self.set_key_display_preference(value)
            )
            self.key_display_action_group.addAction(action)
            self.key_display_menu.addAction(action)
            self.key_display_actions[preference] = action

        menu_bar = self.menuBar()
        menu_bar.clear()
        menu_bar.addMenu(self.file_menu)
        menu_bar.addMenu(self.edit_menu)
        menu_bar.addMenu(self.tools_menu)
        menu_bar.addMenu(self.help_menu)

        self.tools_menu.addSeparator()
        self.tools_menu.addMenu(self.key_display_menu)
        self._sync_key_display_menu_actions()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setObjectName("centralSurface")

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 8, 10, 10)
        main_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("workspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        splitter.addWidget(self._build_song_workspace())
        splitter.addWidget(self._build_processing_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1120, 312])
        main_layout.addWidget(splitter, 1)

        main_layout.addWidget(self._build_action_bar())
        main_layout.addWidget(self._build_log_panel(), 0)

    def _build_window_chrome(self) -> QWidget:
        chrome = QWidget()
        chrome.setObjectName("windowChrome")

        layout = QVBoxLayout(chrome)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = WindowTitleBar(self)
        layout.addWidget(self.title_bar)

        menu_strip = QFrame()
        menu_strip.setObjectName("menuStrip")
        menu_layout = QHBoxLayout(menu_strip)
        menu_layout.setContentsMargins(14, 0, 14, 0)
        menu_layout.setSpacing(2)

        for label, menu in [
            ("File", self.file_menu),
            ("Edit", self.edit_menu),
            ("Tools", self.tools_menu),
            ("Help", self.help_menu),
        ]:
            button = QToolButton()
            button.setText(label)
            button.setObjectName("menuStripButton")
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(menu)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            menu_layout.addWidget(button)

        menu_layout.addStretch(1)
        layout.addWidget(menu_strip)
        return chrome

    def _icon(self, name: str) -> QIcon:
        icon_path = ICON_DIR / f"{name}.svg"
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

    def _build_song_workspace(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("workspaceCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        toolbar = QFrame()
        toolbar.setObjectName("toolbarCard")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 8, 8, 8)
        toolbar_layout.setSpacing(8)

        self.import_button = QPushButton("Import Songs")
        self.remove_button = QPushButton("Remove Selected")
        self.clear_button = QPushButton("Clear List")

        self.import_button.clicked.connect(self.import_songs)
        self.remove_button.clicked.connect(self.remove_selected_songs)
        self.clear_button.clicked.connect(self.clear_songs)

        self.import_button.setIcon(self._icon("import"))
        self.remove_button.setIcon(self._icon("remove"))
        self.clear_button.setIcon(self._icon("clear"))

        self.import_button.setObjectName("topActionButton")
        self.remove_button.setObjectName("topActionButton")
        self.clear_button.setObjectName("ghostButton")

        for button in [self.import_button, self.remove_button, self.clear_button]:
            button.setFixedHeight(34)
            button.setIconSize(QSize(16, 16))

        toolbar_layout.addWidget(self.import_button)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.remove_button)
        layout.addWidget(toolbar)

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
        self.song_table.setObjectName("songTable")
        self.song_table.verticalHeader().setVisible(False)
        self.song_table.verticalHeader().setDefaultSectionSize(28)
        self.song_table.setShowGrid(True)
        self.song_table.set_empty_state_text("No songs imported yet.\nClick Import Songs or drag and drop audio files here.")
        self.song_table.files_dropped.connect(self.import_songs)
        self.song_table.itemSelectionChanged.connect(self._refresh_action_availability)
        self.song_table.itemSelectionChanged.connect(self._load_processing_editor_from_selection)

        header = self.song_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents)
        header.setVisible(False)

        self.song_table.setColumnHidden(1, True)
        self.song_table.setColumnWidth(2, 136)
        self.song_table.setColumnWidth(3, 136)

        layout.addWidget(self.song_table, 1)
        return panel

    def _build_processing_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sideCard")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(320)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Processing Options")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("sectionDivider")
        layout.addWidget(divider)

        self.editor_scope_label = QLabel("No song selected")
        self.editor_scope_label.setObjectName("sectionTitle")
        layout.addWidget(self.editor_scope_label)

        self.editor_note_label = QLabel("Select one or more songs to edit their processing settings.")
        self.editor_note_label.setObjectName("hintLabel")
        self.editor_note_label.setWordWrap(True)
        layout.addWidget(self.editor_note_label)

        stem_label = QLabel("Stem Selection")
        stem_label.setObjectName("fieldLabel")
        layout.addWidget(stem_label)

        self.stem_checkboxes: dict[str, QCheckBox] = {}
        for display_label, stem_value in STEM_CHECKBOX_OPTIONS:
            checkbox = MixedStateCheckBox(display_label)
            checkbox.setObjectName("panelCheck")
            checkbox.setTristate(True)
            checkbox.stateChanged.connect(self._apply_stem_selection_to_selected_songs)
            self.stem_checkboxes[stem_value] = checkbox
            layout.addWidget(checkbox)

        form_layout = QFormLayout()
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(8)

        self.target_bpm_edit = QLineEdit()
        self.target_bpm_edit.setPlaceholderText("128")
        self.target_bpm_edit.setFixedHeight(28)
        self.target_bpm_edit.editingFinished.connect(self._apply_target_bpm_to_selection)

        self.target_key_combo = NoWheelComboBox()
        self.target_key_combo.addItem("Unchanged", None)
        for key_name in KEY_OPTIONS:
            self.target_key_combo.addItem(format_key(key_name, self.key_display_preference), key_name)
        self.target_key_combo.setFixedHeight(28)
        self.target_key_combo.currentIndexChanged.connect(self._apply_target_key_to_selection)

        self.reference_combo = NoWheelComboBox()
        self.reference_combo.addItem("None", None)
        self.reference_combo.setFixedHeight(28)
        self.reference_combo.currentIndexChanged.connect(self._update_reference_mode_ui)
        self.reference_combo.currentIndexChanged.connect(self._apply_reference_song_to_selection)

        self.output_dir_edit = QLineEdit(default_export_dir())
        self.output_dir_edit.setFixedHeight(28)
        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.setObjectName("inlineButton")
        self.output_browse_button.setFixedWidth(72)
        self.output_browse_button.setFixedHeight(28)
        self.output_browse_button.clicked.connect(self.browse_output_folder)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(8)
        output_layout.addWidget(self.output_dir_edit, 1)
        output_layout.addWidget(self.output_browse_button)

        form_layout.addRow("Target BPM", self.target_bpm_edit)
        form_layout.addRow("Target Key", self.target_key_combo)
        form_layout.addRow("Reference Song", self.reference_combo)
        layout.addLayout(form_layout)

        self.reference_note_label = QLabel("Reference song is used as the target source and will not be modified for the enabled dimensions.")
        self.reference_note_label.setObjectName("hintLabel")
        self.reference_note_label.setWordWrap(True)
        self.reference_note_label.setVisible(False)
        layout.addWidget(self.reference_note_label)

        layout.addStretch(1)

        output_label = QLabel("Output Folder")
        output_label.setObjectName("fieldLabel")
        layout.addWidget(output_label)
        layout.addWidget(output_row)

        hint_label = QLabel("Drag and drop mp3, wav, flac, or m4a files onto the song table.")
        hint_label.setWordWrap(True)
        hint_label.setObjectName("hintLabel")
        layout.addWidget(hint_label)

        self.refresh_reference_combo()
        self._update_reference_mode_ui()
        self._load_processing_editor_from_selection()
        return panel

    def _build_action_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("actionBarCard")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(7)

        self.analyze_button = QPushButton("Analyze")
        self.separate_button = QPushButton("Separate Stems")
        self.match_tempo_button = QPushButton("Match Tempo")
        self.match_key_button = QPushButton("Match Key")
        self.process_all_button = QPushButton("Process All")
        self.cancel_button = QPushButton("Cancel Task")
        self.cancel_button.setEnabled(False)

        primary_buttons = [
            (self.analyze_button, self._icon("analyze")),
            (self.separate_button, self._icon("separate")),
            (self.match_tempo_button, self._icon("tempo")),
            (self.match_key_button, self._icon("key")),
            (self.process_all_button, self._icon("process")),
        ]
        button_widths = {
            self.analyze_button: 114,
            self.separate_button: 136,
            self.match_tempo_button: 126,
            self.match_key_button: 114,
            self.process_all_button: 116,
            self.cancel_button: 112,
        }

        for button, icon in primary_buttons:
            button.setIcon(icon)
            button.setObjectName("runActionButton")
            button.setIconSize(QSize(14, 14))
            button.setFixedSize(button_widths[button], 32)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addWidget(button)

        layout.addStretch(1)

        self.cancel_button.setIcon(self._icon("cancel"))
        self.cancel_button.setObjectName("runActionButton")
        self.cancel_button.setProperty("cancelAction", True)
        self.cancel_button.setIconSize(QSize(14, 14))
        self.cancel_button.setFixedSize(button_widths[self.cancel_button], 32)
        self.cancel_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.cancel_button.setVisible(False)
        layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignRight)

        self.analyze_button.clicked.connect(self.start_analyze_task)
        self.separate_button.clicked.connect(lambda: self.start_processing_task("separate"))
        self.match_tempo_button.clicked.connect(lambda: self.start_processing_task("match_tempo"))
        self.match_key_button.clicked.connect(lambda: self.start_processing_task("match_key"))
        self.process_all_button.clicked.connect(lambda: self.start_processing_task("process_all"))
        self.cancel_button.clicked.connect(self.cancel_current_task)

        return panel

    def _build_log_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("logCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Log Output")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setPlaceholderText("Processing logs will appear here.")
        self.log_console.setObjectName("logConsole")
        self.log_console.setFixedHeight(128)
        layout.addWidget(self.log_console)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(16)
        progress_row.addWidget(self.progress_bar, 1)

        layout.addLayout(progress_row)
        return panel

    def _apply_interaction_cursors(self) -> None:
        clickable_widgets = (
            QPushButton,
            QToolButton,
            QCheckBox,
            QComboBox,
        )
        for widget_type in clickable_widgets:
            for widget in self.findChildren(widget_type):
                widget.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_styles(self) -> None:
        checkbox_checked_icon = (ICON_DIR / "checkbox_checked.svg").as_posix()
        checkbox_unchecked_icon = (ICON_DIR / "checkbox_unchecked.svg").as_posix()
        combo_chevron_icon = (ICON_DIR / "chevron_down.svg").as_posix()
        self.setStyleSheet(
            """
            QWidget {
                color: #d5dbe5;
                font-size: 12px;
                font-family: "Segoe UI";
            }
            QMainWindow, #centralSurface {
                background-color: #0f1319;
            }
            QMenuBar {
                background-color: #1b212a;
                color: #edf1f7;
                border-bottom: 1px solid #0a0e13;
                padding: 2px 4px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 5px 8px;
                border-radius: 3px;
            }
            QMenuBar::item:selected,
            QMenuBar::item:pressed {
                background-color: #2a3340;
            }
            QMenu {
                background-color: #151a21;
                color: #e6ebf3;
                border: 1px solid #080b0f;
                padding: 3px;
            }
            QMenu::item {
                padding: 5px 16px 5px 14px;
            }
            QMenu::item:selected {
                background-color: #283240;
            }
            #workspaceCard, #sideCard, #actionBarCard, #logCard, #toolbarCard {
                background-color: #1b222c;
                border: 1px solid #121821;
                border-radius: 8px;
            }
            #toolbarCard {
                background-color: #202833;
            }
            #sectionTitle {
                font-size: 13px;
                font-weight: 700;
                color: #f0f4fa;
            }
            #sectionDivider {
                color: #11161e;
                background-color: #11161e;
                min-height: 1px;
                max-height: 1px;
            }
            #fieldLabel {
                font-size: 11px;
                font-weight: 600;
                color: #94a0b1;
                margin-top: 1px;
            }
            #hintLabel {
                color: #8995a7;
                font-size: 11px;
                line-height: 1.4;
            }
            QPushButton {
                background-color: #323c4b;
                border: 1px solid #0f141b;
                border-radius: 6px;
                padding: 4px 9px;
                color: #eff3f9;
                font-weight: 600;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #425166;
                border-color: #4c6487;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #27303b;
                border-color: #324860;
            }
            QPushButton:disabled {
                background-color: #252b35;
                color: #707b8d;
                border-color: #151b23;
            }
            #topActionButton {
                min-width: 140px;
            }
            #runActionButton {
                background-color: #333d4c;
                min-height: 32px;
                max-height: 32px;
                padding: 3px 9px;
                font-size: 11px;
            }
            #runActionButton:hover {
                background-color: #47566d;
                border-color: #5674a0;
            }
            #runActionButton[cancelAction="true"] {
                min-width: 112px;
            }
            #inlineButton, #ghostButton {
                background-color: #2d3643;
            }
            #inlineButton:hover, #ghostButton:hover, #topActionButton:hover {
                background-color: #435166;
                border-color: #4f6a90;
            }
            QLineEdit, QComboBox, QPlainTextEdit, QTableWidget {
                background-color: #131920;
                border: 1px solid #0c1016;
                border-radius: 6px;
                padding: 5px 7px;
                selection-background-color: #2f568e;
                selection-color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
                border: 1px solid #4068a3;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox::down-arrow {
                image: url("%s");
                width: 10px;
                height: 6px;
            }
            #tableCombo {
                padding: 0px 6px;
                margin: 0px;
            }
            #tableCombo QLineEdit {
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                color: #eef3fb;
            }
            #tableCombo::drop-down {
                width: 18px;
            }
            QComboBox QAbstractItemView {
                background-color: #131920;
                color: #eef3fb;
                selection-background-color: #2f568e;
                border: 1px solid #0c1016;
            }
            QHeaderView::section {
                background-color: #242c37;
                color: #eef2f8;
                border: 0;
                border-right: 1px solid #141a22;
                padding: 7px 10px;
                font-weight: 700;
            }
            #songTable {
                gridline-color: #11161d;
                alternate-background-color: #171e27;
                background-color: #181f28;
                border-radius: 7px;
                selection-background-color: #28415d;
                selection-color: #f4f7fc;
            }
            QTableWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #10161d;
            }
            QTableWidget::item:selected {
                background-color: #28415d;
                color: #f4f7fc;
            }
            QTableWidget::item:selected:active,
            QTableWidget::item:selected:!active {
                background-color: #28415d;
                color: #f4f7fc;
            }
            QProgressBar {
                border: 1px solid #0c1016;
                border-radius: 5px;
                background-color: #10151b;
                text-align: center;
                color: #eef3fb;
                font-weight: 700;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #2a63bc;
                border-radius: 4px;
            }
            QCheckBox {
                spacing: 8px;
                color: #eef2f8;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                image: url("%s");
            }
            QCheckBox::indicator:checked {
                image: url("%s");
            }
            QScrollBar:vertical {
                background: #12171d;
                width: 8px;
                border-radius: 4px;
                margin: 2px 1px 2px 1px;
            }
            QScrollBar::handle:vertical {
                background: #414c5c;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            #workspaceSplitter::handle {
                background-color: #0f1319;
            }
            #logConsole {
                font-family: "Consolas";
                font-size: 11px;
            }
            """
            % (combo_chevron_icon, checkbox_unchecked_icon, checkbox_checked_icon)
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
            "export": [self.export_action],
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

    def _has_song_selection(self) -> bool:
        return bool(self.selected_rows())

    def _update_song_table_header_visibility(self) -> None:
        if not hasattr(self, "song_table"):
            return
        self.song_table.horizontalHeader().setVisible(bool(self.songs))

    def _refresh_action_availability(self) -> None:
        self.action_dependency_messages = self._collect_base_action_messages()
        selection_required_message = "Select at least one song."

        selection_controls = [
            self.remove_button,
            self.remove_action,
            *[control for controls in self._action_controls().values() for control in controls],
        ]
        has_selection = self.current_worker is None and self._has_song_selection()

        for control in selection_controls:
            control.setEnabled(has_selection)
            self._apply_control_hint(control, "" if has_selection else selection_required_message)

        for action_name, controls in self._action_controls().items():
            message = self.action_dependency_messages.get(action_name, "")
            enabled = has_selection and not message
            for control in controls:
                control.setEnabled(enabled)
                self._apply_control_hint(control, message or ("" if has_selection else selection_required_message))

    def append_log(self, message: str) -> None:
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        self.log_console.appendPlainText(f"[{timestamp}] {message}")
        self.log_console.verticalScrollBar().setValue(self.log_console.verticalScrollBar().maximum())

    def _can_modify_project(self, action_description: str) -> bool:
        if self.current_worker is None:
            return True
        self.show_warning(f"Cancel the current task before {action_description}.")
        return False

    def _confirm_project_replace(self) -> bool:
        if not self.songs:
            return True

        result = QMessageBox.question(
            self,
            "TuneMatrix",
            "Open a saved project and replace the current song list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _set_combo_data(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _sync_key_display_menu_actions(self) -> None:
        for preference, action in self.key_display_actions.items():
            action.blockSignals(True)
            action.setChecked(preference == self.key_display_preference)
            action.blockSignals(False)

    def _refresh_key_option_combo_labels(self, combo: QComboBox, none_label: str) -> None:
        combo.blockSignals(True)
        for index in range(combo.count()):
            data = combo.itemData(index)
            if data is None:
                combo.setItemText(index, none_label)
            elif data == "__mixed__":
                combo.setItemText(index, "Mixed")
            elif isinstance(data, str):
                combo.setItemText(index, format_key(data, self.key_display_preference))
        combo.blockSignals(False)

    def set_key_display_preference(self, preference: str) -> None:
        normalized_preference = normalize_key_display_preference(preference)
        if normalized_preference == self.key_display_preference:
            self._sync_key_display_menu_actions()
            return

        self.key_display_preference = normalized_preference
        self._sync_key_display_menu_actions()
        self._refresh_key_display_preference_ui()

    def _refresh_key_display_preference_ui(self) -> None:
        if hasattr(self, "target_key_combo"):
            self._refresh_key_option_combo_labels(self.target_key_combo, "Unchanged")

        if hasattr(self, "song_table"):
            for row in range(self.song_table.rowCount()):
                key_hint_combo = self._table_combo_at(row, 3)
                if isinstance(key_hint_combo, QComboBox):
                    self._refresh_key_option_combo_labels(key_hint_combo, "Auto")
                if row < len(self.songs):
                    self._populate_song_row(row, self.songs[row])

        if hasattr(self, "reference_combo"):
            self.refresh_reference_combo()

    def _set_combo_text(self, combo: QComboBox, value: object) -> None:
        text_value = str(value or "").strip()
        index = combo.findText(text_value)
        if index >= 0:
            combo.setCurrentIndex(index)
            return
        if combo.isEditable():
            combo.setEditText(text_value or BPM_RANGE_DEFAULT_LABEL)
            return
        combo.setCurrentIndex(0)

    def _song_for_path(self, file_path: str) -> Optional[SongRecord]:
        for song in self.songs:
            if song.file_path == file_path:
                return song
        return None

    def _find_combo_index_by_data(self, combo: QComboBox, target: object) -> int:
        for index in range(combo.count()):
            if combo.itemData(index) == target:
                return index
        return -1

    def _set_song_bpm_range_combo_value(self, combo: QComboBox, label: object) -> None:
        normalized = str(label or BPM_RANGE_DEFAULT_LABEL).strip() or BPM_RANGE_DEFAULT_LABEL
        direct_index = combo.findText(normalized)
        custom_index = self._find_combo_index_by_data(combo, "__custom__")
        manual_index = self._find_combo_index_by_data(combo, "__manual__")

        if direct_index >= 0:
            if custom_index >= 0:
                combo.removeItem(custom_index)
            combo.setCurrentIndex(direct_index)
            return

        insert_index = manual_index if manual_index >= 0 else combo.count()
        if custom_index >= 0:
            combo.setItemText(custom_index, normalized)
        else:
            combo.insertItem(insert_index, normalized, "__custom__")
            custom_index = insert_index
        combo.setCurrentIndex(custom_index)

    def _table_combo_at(self, row: int, column: int) -> Optional[QComboBox]:
        widget = self.song_table.cellWidget(row, column)
        if isinstance(widget, QComboBox):
            return widget
        if isinstance(widget, QWidget):
            return widget.findChild(QComboBox)
        return None

    def _create_song_bpm_range_combo(self, song: SongRecord) -> QComboBox:
        combo = NoWheelComboBox()
        combo.setObjectName("tableCombo")
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        combo.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        combo.setFixedHeight(20)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setMaxVisibleItems(len(BPM_RANGE_OPTIONS) + 2)
        combo.setToolTip("Choose a preset or use Enter BPM... for a manual value like 128 or 120-130.")
        for label, bpm_range in BPM_RANGE_OPTIONS:
            combo.addItem(label, bpm_range)
        combo.insertSeparator(combo.count())
        combo.addItem(BPM_RANGE_MANUAL_LABEL, "__manual__")
        self._set_song_bpm_range_combo_value(combo, song.bpm_range_label)
        combo.currentIndexChanged.connect(
            lambda _index, path=song.file_path, widget=combo: self._on_song_bpm_range_selection_changed(path, widget)
        )
        return combo

    def _create_song_key_hint_combo(self, song: SongRecord) -> QComboBox:
        combo = NoWheelComboBox()
        combo.setObjectName("tableCombo")
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        combo.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        combo.setFixedHeight(20)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.addItem("Auto", None)
        for key_name in KEY_OPTIONS:
            combo.addItem(format_key(key_name, self.key_display_preference), key_name)
        self._set_combo_data(combo, song.analysis_key_hint)
        combo.currentIndexChanged.connect(
            lambda _index, path=song.file_path, widget=combo: self._on_song_key_hint_changed(path, widget.currentData())
        )
        return combo

    def _on_song_bpm_range_selection_changed(self, file_path: str, combo: QComboBox) -> None:
        song = self._song_for_path(file_path)
        if song is None:
            return
        current_data = combo.currentData()
        if current_data == "__manual__":
            current_text = song.bpm_range_label if song.bpm_range_label not in {BPM_RANGE_DEFAULT_LABEL, BPM_RANGE_MANUAL_LABEL} else ""
            value, accepted = QInputDialog.getText(
                self,
                "Enter BPM Range",
                "Enter a BPM like 128 or a range like 120-130:",
                text=current_text,
            )
            if accepted:
                normalized = str(value or "").strip()
                if normalized:
                    song.bpm_range_label = normalized
            combo.blockSignals(True)
            self._set_song_bpm_range_combo_value(combo, song.bpm_range_label)
            combo.blockSignals(False)
            self._schedule_auto_analysis([song], "hint change")
            return

        selected_text = str(combo.currentText() or BPM_RANGE_DEFAULT_LABEL).strip() or BPM_RANGE_DEFAULT_LABEL
        song.bpm_range_label = selected_text
        self._schedule_auto_analysis([song], "hint change")

    def _on_song_key_hint_changed(self, file_path: str, key_hint: object) -> None:
        song = self._song_for_path(file_path)
        if song is None:
            return
        song.analysis_key_hint = str(key_hint or "").strip() or None
        self._schedule_auto_analysis([song], "hint change")

    def _display_stem_list(self, stems: Optional[list[str]]) -> str:
        if stems is None or len(stems) == len(self.stem_checkboxes):
            return "All stems"
        if len(stems) == 0:
            return "None"
        return ", ".join(stems)

    def _song_selected_stem_values(self, song: SongRecord) -> list[str]:
        if song.processing_selected_stems is None:
            return list(self.stem_checkboxes)
        return list(song.processing_selected_stems)

    def _song_has_processing_settings(self, song: SongRecord) -> bool:
        return bool(
            song.processing_target_bpm is not None
            or song.processing_target_key
            or song.processing_selected_stems is not None
            or song.reference_song_path
        )

    def _sync_song_processing_flag(self, song: SongRecord) -> None:
        song.processing_override_enabled = self._song_has_processing_settings(song)

    def _song_reference_name(self, reference_path: Optional[str]) -> str:
        if not reference_path:
            return "None"
        song = self._song_for_path(reference_path)
        return song.file_name if song else Path(reference_path).name

    def _song_processing_override_tooltip(self, song: SongRecord) -> str:
        if not self._song_has_processing_settings(song):
            return ""

        stems_label = self._display_stem_list(song.processing_selected_stems)
        bpm_label = f"{song.processing_target_bpm:g}" if song.processing_target_bpm is not None else "Not set"
        key_label = format_key(song.processing_target_key, self.key_display_preference) if song.processing_target_key else "Unchanged"
        return (
            "Song processing\n"
            f"Reference Song: {self._song_reference_name(song.reference_song_path)}\n"
            f"Target BPM: {bpm_label}\n"
            f"Target Key: {key_label}\n"
            f"Stems: {stems_label}"
        )

    def selected_stem_values(self) -> list[str]:
        if not hasattr(self, "stem_checkboxes"):
            return []
        return [
            stem_name
            for stem_name, checkbox in self.stem_checkboxes.items()
            if checkbox.checkState() == Qt.CheckState.Checked
        ]

    def _clear_special_combo_item(self, combo: QComboBox, token: str) -> None:
        index = self._find_combo_index_by_data(combo, token)
        if index >= 0:
            combo.removeItem(index)

    def _set_combo_mixed_state(self, combo: QComboBox, token: str) -> None:
        index = self._find_combo_index_by_data(combo, token)
        if index < 0:
            combo.insertItem(0, "Mixed", token)
            index = 0
        combo.setCurrentIndex(index)

    def _set_checkbox_state(self, checkbox: QCheckBox, state: Qt.CheckState) -> None:
        checkbox.blockSignals(True)
        checkbox.setCheckState(state)
        checkbox.blockSignals(False)

    def _set_song_bound_controls_enabled(self, enabled: bool) -> None:
        for control in [
            self.target_bpm_edit,
            self.target_key_combo,
            self.reference_combo,
            *self.stem_checkboxes.values(),
        ]:
            control.setEnabled(enabled and self.current_worker is None)

    def _load_processing_editor_from_selection(self) -> None:
        if not hasattr(self, "editor_scope_label"):
            return

        selected_songs = self.selected_songs()
        self._sidebar_binding_in_progress = True
        try:
            self._clear_special_combo_item(self.target_key_combo, "__mixed__")
            self._clear_special_combo_item(self.reference_combo, "__mixed__")

            if not selected_songs:
                self.editor_scope_label.setText("No song selected")
                self.editor_note_label.setText("Select one or more songs to edit their processing settings.")
                self._set_song_bound_controls_enabled(False)
                self.target_bpm_edit.clear()
                self.target_bpm_edit.setPlaceholderText("Select a song")
                self._set_combo_data(self.target_key_combo, None)
                self._set_combo_data(self.reference_combo, None)
                for checkbox in self.stem_checkboxes.values():
                    self._set_checkbox_state(checkbox, Qt.CheckState.Unchecked)
                self.reference_note_label.setVisible(False)
            elif len(selected_songs) == 1:
                song = selected_songs[0]
                self.editor_scope_label.setText(f"Editing Song: {song.file_name}")
                self.editor_note_label.setText("Changes in this panel update the selected song directly.")
                self._set_song_bound_controls_enabled(True)
                self.target_bpm_edit.setText("" if song.processing_target_bpm is None else f"{song.processing_target_bpm:g}")
                self.target_bpm_edit.setPlaceholderText("Not set")
                self._set_combo_data(self.target_key_combo, song.processing_target_key)
                self._set_combo_data(self.reference_combo, song.reference_song_path)

                selected_stems = set(self._song_selected_stem_values(song))
                for stem_name, checkbox in self.stem_checkboxes.items():
                    self._set_checkbox_state(
                        checkbox,
                        Qt.CheckState.Checked if stem_name in selected_stems else Qt.CheckState.Unchecked,
                    )
            else:
                self.editor_scope_label.setText(f"Editing Songs: {len(selected_songs)}")
                self.editor_note_label.setText("Changes in this panel apply to all selected songs. Mixed means values differ.")
                self._set_song_bound_controls_enabled(True)

                bpm_values = {song.processing_target_bpm for song in selected_songs}
                if len(bpm_values) == 1:
                    only_bpm = next(iter(bpm_values))
                    self.target_bpm_edit.setText("" if only_bpm is None else f"{only_bpm:g}")
                    self.target_bpm_edit.setPlaceholderText("Not set")
                else:
                    self.target_bpm_edit.clear()
                    self.target_bpm_edit.setPlaceholderText("Mixed")

                key_values = {song.processing_target_key for song in selected_songs}
                if len(key_values) == 1:
                    self._set_combo_data(self.target_key_combo, next(iter(key_values)))
                else:
                    self._set_combo_mixed_state(self.target_key_combo, "__mixed__")

                reference_values = {song.reference_song_path for song in selected_songs}
                if len(reference_values) == 1:
                    self._set_combo_data(self.reference_combo, next(iter(reference_values)))
                else:
                    self._set_combo_mixed_state(self.reference_combo, "__mixed__")

                stem_sets = [set(self._song_selected_stem_values(song)) for song in selected_songs]
                for stem_name, checkbox in self.stem_checkboxes.items():
                    checked_count = sum(1 for stem_set in stem_sets if stem_name in stem_set)
                    if checked_count == 0:
                        state = Qt.CheckState.Unchecked
                    elif checked_count == len(stem_sets):
                        state = Qt.CheckState.Checked
                    else:
                        state = Qt.CheckState.PartiallyChecked
                    self._set_checkbox_state(checkbox, state)
        finally:
            self._sidebar_binding_in_progress = False
            self._update_reference_mode_ui()

    def _update_reference_mode_ui(self) -> None:
        has_selection = bool(self.selected_songs())
        self.target_bpm_edit.setEnabled(has_selection and self.current_worker is None)
        self.target_key_combo.setEnabled(has_selection and self.current_worker is None)
        self.reference_combo.setEnabled(has_selection and self.current_worker is None)
        self.target_bpm_edit.setToolTip("")
        self.target_key_combo.setToolTip("")

        if not has_selection:
            self.reference_note_label.setVisible(False)
            return

        reference_path = self.reference_combo.currentData()
        if not reference_path or reference_path == "__mixed__":
            self.reference_note_label.setVisible(False)
            return

        reference_name = "the selected reference song"
        if reference_path:
            reference_name = self._song_reference_name(reference_path)

        self.reference_note_label.setVisible(True)
        self.reference_note_label.setText(
            f"{reference_name} is used as the fallback source for BPM and Key when the selected song does not have explicit targets."
        )

    def _parse_target_bpm_value(self) -> Optional[float]:
        bpm_text = self.target_bpm_edit.text().strip()
        if not bpm_text:
            return None
        try:
            return float(bpm_text)
        except ValueError:
            return None

    def _apply_processing_field_to_selected_songs(self, updater) -> list[SongRecord]:
        if self._sidebar_binding_in_progress or self.current_worker is not None:
            return []

        songs = self.selected_songs()
        if not songs:
            return []

        for song in songs:
            updater(song)
            self._sync_song_processing_flag(song)
            row = self.find_song_row(song.file_path)
            if row is not None:
                self._populate_song_row(row, song)
        return songs

    @staticmethod
    def _normalize_selection_value(value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        if isinstance(value, set):
            return tuple(sorted(value))
        return value

    def _selection_has_mixed_values(self, extractor) -> bool:
        songs = self.selected_songs()
        if len(songs) <= 1:
            return False

        normalized_values = {
            self._normalize_selection_value(extractor(song))
            for song in songs
        }
        return len(normalized_values) > 1

    def _confirm_override_for_mixed_selection(self, field_label: str, extractor) -> bool:
        songs = self.selected_songs()
        if len(songs) <= 1 or not self._selection_has_mixed_values(extractor):
            return True

        result = QMessageBox.question(
            self,
            "TuneMatrix",
            (
                f"The selected songs currently have different {field_label} values.\n\n"
                f"Apply this change to all {len(songs)} selected songs?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _apply_target_bpm_to_selection(self) -> None:
        if self._sidebar_binding_in_progress or self.current_worker is not None:
            return

        bpm_text = self.target_bpm_edit.text().strip()
        bpm_value = self._parse_target_bpm_value()
        if bpm_text and bpm_value is None:
            self.show_warning("Target BPM must be a number.")
            self._load_processing_editor_from_selection()
            return
        if bpm_value is not None and bpm_value <= 0:
            self.show_warning("Target BPM must be greater than zero.")
            self._load_processing_editor_from_selection()
            return

        if not self._confirm_override_for_mixed_selection("Target BPM", lambda song: song.processing_target_bpm):
            self._load_processing_editor_from_selection()
            return

        songs = self._apply_processing_field_to_selected_songs(lambda song: setattr(song, "processing_target_bpm", bpm_value))
        if songs:
            self._load_processing_editor_from_selection()

    def _apply_target_key_to_selection(self) -> None:
        if self._sidebar_binding_in_progress or self.current_worker is not None:
            return

        target_key = self.target_key_combo.currentData()
        if target_key == "__mixed__":
            return

        if not self._confirm_override_for_mixed_selection("Target Key", lambda song: song.processing_target_key):
            self._load_processing_editor_from_selection()
            return

        songs = self._apply_processing_field_to_selected_songs(lambda song: setattr(song, "processing_target_key", target_key))
        if songs:
            self._load_processing_editor_from_selection()

    def _apply_reference_song_to_selection(self) -> None:
        if self._sidebar_binding_in_progress or self.current_worker is not None:
            return

        reference_path = self.reference_combo.currentData()
        if reference_path == "__mixed__":
            return

        if not self._confirm_override_for_mixed_selection("Reference Song", lambda song: song.reference_song_path):
            self._load_processing_editor_from_selection()
            return

        songs = self._apply_processing_field_to_selected_songs(lambda song: setattr(song, "reference_song_path", reference_path))
        if songs:
            self._load_processing_editor_from_selection()

    def _apply_stem_selection_to_selected_songs(self) -> None:
        if self._sidebar_binding_in_progress:
            return

        selected_states = {
            stem_name: checkbox.checkState()
            for stem_name, checkbox in self.stem_checkboxes.items()
        }
        if any(state == Qt.CheckState.PartiallyChecked for state in selected_states.values()):
            return

        selected_stems = [stem_name for stem_name, state in selected_states.items() if state == Qt.CheckState.Checked]
        normalized_stems = None if len(selected_stems) == len(self.stem_checkboxes) else selected_stems

        if not self._confirm_override_for_mixed_selection(
            "Stem Selection",
            lambda song: self._song_selected_stem_values(song),
        ):
            self._load_processing_editor_from_selection()
            return

        songs = self._apply_processing_field_to_selected_songs(
            lambda song: setattr(song, "processing_selected_stems", list(normalized_stems) if normalized_stems is not None else None)
        )
        if songs:
            self._load_processing_editor_from_selection()

    def collect_project_state(self) -> dict[str, object]:
        return {
            "format_version": PROJECT_STATE_VERSION,
            "songs": [song.to_dict() for song in self.songs],
            "ui": {
                "output_dir": self.output_dir_edit.text().strip(),
                "key_display_preference": self.key_display_preference,
            },
        }

    def apply_project_state(self, state: dict[str, object]) -> None:
        if not isinstance(state, dict):
            raise ValueError("Project file is invalid.")

        format_version = state.get("format_version", PROJECT_STATE_VERSION)
        if not isinstance(format_version, int) or format_version > PROJECT_STATE_VERSION:
            raise ValueError(f"Unsupported project format version: {format_version}")

        songs_data = state.get("songs", [])
        ui_state = state.get("ui", {})
        if not isinstance(songs_data, list):
            raise ValueError("Project file has an invalid songs list.")
        if not isinstance(ui_state, dict):
            raise ValueError("Project file has invalid UI settings.")

        restored_songs: list[SongRecord] = []
        missing_files: list[str] = []
        for index, song_data in enumerate(songs_data, start=1):
            if not isinstance(song_data, dict):
                raise ValueError(f"Song entry {index} is invalid.")

            song = SongRecord.from_dict(song_data)
            if not song.file_path:
                raise ValueError(f"Song entry {index} is missing a file path.")

            if not Path(song.file_path).exists():
                song.status = SongStatus.ERROR.value
                song.last_error = f"File does not exist: {song.file_path}"
                missing_files.append(song.file_name or song.file_path)

            restored_songs.append(song)

        self.songs = restored_songs
        legacy_target_bpm_text = str(ui_state.get("target_bpm_text") or "").strip()
        legacy_target_bpm: Optional[float]
        try:
            legacy_target_bpm = float(legacy_target_bpm_text) if legacy_target_bpm_text else None
        except ValueError:
            legacy_target_bpm = None
        legacy_target_key = ui_state.get("target_key")
        legacy_selected_stems_raw = ui_state.get("selected_stems")
        legacy_selected_stems = (
            list(legacy_selected_stems_raw)
            if isinstance(legacy_selected_stems_raw, list)
            and 0 < len(legacy_selected_stems_raw) < len(self.stem_checkboxes)
            else None
        )
        legacy_match_to_reference = bool(ui_state.get("match_to_reference", False))
        legacy_use_reference_bpm = bool(ui_state.get("use_reference_bpm", legacy_match_to_reference))
        legacy_use_reference_key = bool(ui_state.get("use_reference_key", legacy_match_to_reference))
        legacy_reference_song_path = ui_state.get("reference_song_path")
        legacy_bpm_range_label = str(ui_state.get("bpm_range_label") or BPM_RANGE_DEFAULT_LABEL)
        legacy_key_hint = str(ui_state.get("analysis_key_hint") or "").strip() or None
        for song in self.songs:
            if not song.bpm_range_label:
                song.bpm_range_label = legacy_bpm_range_label
            if not song.analysis_key_hint and legacy_key_hint:
                song.analysis_key_hint = legacy_key_hint
            if song.processing_target_bpm is None and legacy_target_bpm is not None:
                song.processing_target_bpm = legacy_target_bpm
            if not song.processing_target_key and legacy_target_key:
                song.processing_target_key = str(legacy_target_key)
            if song.processing_selected_stems is None and legacy_selected_stems is not None:
                song.processing_selected_stems = list(legacy_selected_stems)
            if not song.use_reference_bpm and legacy_use_reference_bpm:
                song.use_reference_bpm = True
            if not song.use_reference_key and legacy_use_reference_key:
                song.use_reference_key = True
            if not song.reference_song_path and legacy_reference_song_path:
                song.reference_song_path = str(legacy_reference_song_path)
            self._sync_song_processing_flag(song)
        self.song_table.setRowCount(0)
        for song in self.songs:
            self._append_song_row(song)
        self._update_song_table_header_visibility()

        if "output_dir" in ui_state:
            self.output_dir_edit.setText(str(ui_state.get("output_dir") or ""))
        else:
            self.output_dir_edit.setText(default_export_dir())

        self.key_display_preference = normalize_key_display_preference(ui_state.get("key_display_preference"))
        self._sync_key_display_menu_actions()
        self._refresh_key_display_preference_ui()

        self.progress_bar.setValue(0)
        self._load_processing_editor_from_selection()
        self._refresh_action_availability()
        self.append_log(f"Loaded project with {len(self.songs)} song(s).")
        for file_name in missing_files:
            self.append_log(f"{file_name}: file not found on disk.")

    def _normalize_project_save_path(self, file_path: str) -> str:
        path = Path(file_path)
        if path.suffix.lower() != ".json":
            return str(path.with_name(f"{path.name}{PROJECT_FILE_SUFFIX}"))
        return str(path)

    def _save_project_to_path(self, file_path: str) -> None:
        target_path = Path(self._normalize_project_save_path(file_path))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("w", encoding="utf-8") as handle:
            json.dump(self.collect_project_state(), handle, indent=2)
        self.append_log(f"Saved project to {target_path}")

    def save_project(self) -> None:
        if not self._can_modify_project("saving the project"):
            return

        suggested_path = Path.cwd() / f"project{PROJECT_FILE_SUFFIX}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(suggested_path),
            PROJECT_FILE_FILTER,
        )
        if not file_path:
            return

        try:
            self._save_project_to_path(file_path)
        except OSError as exc:
            self.show_error(f"Could not save the project:\n\n{exc}")

    def _load_project_from_path(self, file_path: str) -> None:
        with Path(file_path).open("r", encoding="utf-8") as handle:
            state = json.load(handle)

        self.apply_project_state(state)
        self.append_log(f"Opened project file {file_path}")

    def open_project(self) -> None:
        if not self._can_modify_project("opening a project"):
            return
        if not self._confirm_project_replace():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(Path.cwd()),
            PROJECT_FILE_FILTER,
        )
        if not file_path:
            return

        try:
            self._load_project_from_path(file_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.show_error(f"Could not open the project:\n\n{exc}")

    def import_songs(self, paths: Optional[list[str]] = None) -> None:
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
        added_songs: list[SongRecord] = []
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
            added_songs.append(song)
            existing_paths.add(resolved)
            added_count += 1
            self.append_log(f"Imported {song.file_name}")

        if added_count:
            self._update_song_table_header_visibility()
            self.refresh_reference_combo()
            self._load_processing_editor_from_selection()
            self._schedule_auto_analysis(added_songs, "import")

    def remove_selected_songs(self) -> None:
        if not self._can_modify_project("removing songs"):
            return

        rows = self.selected_rows()
        if not rows:
            self.show_warning("Select at least one song to remove.")
            return

        for row in sorted(rows, reverse=True):
            removed_song = self.songs.pop(row)
            self.song_table.removeRow(row)
            self.append_log(f"Removed {removed_song.file_name}")

        self._update_song_table_header_visibility()
        self.refresh_reference_combo()
        self._load_processing_editor_from_selection()

    def clear_songs(self) -> None:
        if not self._can_modify_project("clearing the song list"):
            return

        if not self.songs:
            return

        self.songs.clear()
        self.song_table.setRowCount(0)
        self._update_song_table_header_visibility()
        self.refresh_reference_combo()
        self.progress_bar.setValue(0)
        self.append_log("Cleared the song list.")
        self._load_processing_editor_from_selection()

    def selected_rows(self) -> list[int]:
        selection_model = self.song_table.selectionModel()
        if selection_model is None:
            return []
        rows = sorted({index.row() for index in selection_model.selectedRows()})
        return rows

    def selected_songs(self) -> list[SongRecord]:
        rows = self.selected_rows()
        return [self.songs[row] for row in rows]

    def get_reference_song(self, song: SongRecord) -> Optional[SongRecord]:
        reference_path = song.reference_song_path
        if not reference_path:
            return None
        return self._song_for_path(reference_path)

    def _validate_selected_song_processing(self, action: str, songs: list[SongRecord]) -> Optional[str]:
        for song in songs:
            if song.processing_target_bpm is not None and song.processing_target_bpm <= 0:
                return f"{song.file_name}: Target BPM must be greater than zero."
            if song.reference_song_path and self.get_reference_song(song) is None:
                return f"{song.file_name}: Choose a valid reference song."

        if action == "match_tempo":
            missing_bpm_songs = [
                song.file_name
                for song in songs
                if song.processing_target_bpm is None and not song.reference_song_path
            ]
            if missing_bpm_songs:
                return "Each selected song needs a Target BPM or Reference Song."

        if action == "match_key":
            missing_key_songs = [
                song.file_name
                for song in songs
                if not song.processing_target_key and not song.reference_song_path
            ]
            if missing_key_songs:
                return "Each selected song needs a Target Key or Reference Song."

        if action == "separate":
            empty_stem_songs = [song.file_name for song in songs if song.processing_selected_stems == []]
            if empty_stem_songs:
                return "Select at least one stem before running Separate Stems."

        return None

    def _auto_analysis_candidates(self, songs: list[SongRecord]) -> list[SongRecord]:
        candidates: list[SongRecord] = []
        for song in songs:
            issues = list(dict.fromkeys(action_runtime_issues("analyze", [song.file_path])))
            if issues:
                for issue in issues:
                    self.append_log(f"{song.file_name}: {issue}")
                continue
            candidates.append(song)
        return candidates

    def _queue_auto_analysis(self, songs: list[SongRecord], reason: str) -> None:
        queued_count = 0
        for song in songs:
            if song.file_path in self.pending_auto_analysis_paths:
                continue
            self.pending_auto_analysis_paths.append(song.file_path)
            if song.status != SongStatus.ANALYZING.value:
                song.status = SongStatus.QUEUED_ANALYSIS.value
                song.last_error = None
                row = self.find_song_row(song.file_path)
                if row is not None:
                    self._populate_song_row(row, song)
            queued_count += 1

        if queued_count:
            self.append_log(
                f"Queued {queued_count} song(s) for automatic analysis after the current task ({reason})."
            )

    def _dequeue_auto_analysis_songs(self) -> list[SongRecord]:
        if not self.pending_auto_analysis_paths:
            return []

        queued_paths = list(dict.fromkeys(self.pending_auto_analysis_paths))
        self.pending_auto_analysis_paths.clear()
        songs: list[SongRecord] = []
        for file_path in queued_paths:
            song = self._song_for_path(file_path)
            if song is not None:
                songs.append(song)
        return songs

    def _start_auto_analysis(self, songs: list[SongRecord], reason: str) -> bool:
        if self.current_worker is not None:
            return False

        candidates = self._auto_analysis_candidates(songs)
        if not candidates:
            return False

        task_label = "Auto-analyzing imported songs" if reason == "import" else "Auto-analyzing updated songs"
        worker = AnalyzeWorker(candidates)
        self.start_worker(worker, task_label)
        return True

    def _schedule_auto_analysis(self, songs: list[SongRecord], reason: str) -> None:
        unique_songs = list(dict.fromkeys(song.file_path for song in songs if song is not None))
        resolved_songs = [self._song_for_path(path) for path in unique_songs]
        candidates = [song for song in resolved_songs if song is not None]
        if not candidates:
            return

        if self.current_worker is None:
            self._start_auto_analysis(candidates, reason)
            return

        if (
            reason == "hint change"
            and isinstance(self.current_worker, AnalyzeWorker)
            and any(song.file_path in {active_song.file_path for active_song in self.current_worker.songs} for song in candidates)
        ):
            self.append_log("Analysis hints changed. Restarting the current analysis queue with the latest values.")
            active_songs = list(self.current_worker.songs)
            self.current_worker.cancel()
            self._queue_auto_analysis(active_songs, reason)
            self._queue_auto_analysis(candidates, reason)
            return

        self._queue_auto_analysis(candidates, reason)

    def start_analyze_task(self) -> None:
        if not self.songs:
            self.show_warning("Import at least one song before analyzing.")
            return
        if self.current_worker is not None:
            self.show_warning("A task is already running.")
            return

        songs = self.selected_songs()
        if not songs:
            self.show_warning("Select at least one song before analyzing.")
            return
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

        songs = self.selected_songs()
        if not songs:
            self.show_warning("Select at least one song.")
            return

        runtime_issues = list(dict.fromkeys(action_runtime_issues(action, [song.file_path for song in songs])))
        if runtime_issues:
            message = "\n".join(runtime_issues)
            self.append_log(message)
            self.show_warning(message)
            return

        validation_error = self._validate_selected_song_processing(action, songs)
        if validation_error:
            self.show_warning(validation_error)
            return

        options = self.build_processing_options()

        if action in {"separate", "match_tempo", "match_key", "process_all"} and not options.output_dir:
            self.show_warning("Choose an output folder before processing. TuneMatrix exports processed results automatically.")
            return

        if action == "export" and not options.output_dir:
            self.show_warning("Choose an export folder before exporting cached results.")
            return

        worker = ProcessingWorker(songs, options, action, all_songs=self.songs)
        self.start_worker(worker, action.replace("_", " ").title())

    def build_processing_options(self) -> ProcessingOptions:
        return ProcessingOptions(
            output_dir=self.output_dir_edit.text().strip() or None,
            key_display_preference=self.key_display_preference,
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
        self._load_processing_editor_from_selection()

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
        queued_songs = self._dequeue_auto_analysis_songs()
        if queued_songs:
            self._start_auto_analysis(queued_songs, "queue")

    def changeEvent(self, event) -> None:  # type: ignore[override]
        if hasattr(self, "title_bar"):
            self.title_bar.sync_window_state()
        super().changeEvent(event)

    def set_task_running(self, running: bool) -> None:
        locked_controls = [
            self.open_project_action,
            self.save_project_action,
            self.remove_button,
            self.clear_button,
            self.output_dir_edit,
            self.output_browse_button,
            self.remove_action,
            self.clear_action,
        ]

        for control in locked_controls:
            control.setEnabled(not running)

        self.import_button.setEnabled(True)
        self.import_action.setEnabled(True)

        self.song_table.setEnabled(True)
        self.cancel_button.setEnabled(running)
        self.cancel_button.setVisible(running)
        self.cancel_action.setEnabled(running)
        self._load_processing_editor_from_selection()
        self._refresh_action_availability()

    def refresh_reference_combo(self) -> None:
        self.reference_combo.blockSignals(True)
        self.reference_combo.clear()
        self.reference_combo.addItem("None", None)
        for song in self.songs:
            label = (
                f"{song.file_name} | "
                f"{format_bpm(song.bpm)} BPM | "
                f"{format_key(song.musical_key, self.key_display_preference)}"
            )
            self.reference_combo.addItem(label, song.file_path)
        self.reference_combo.blockSignals(False)
        self._load_processing_editor_from_selection()

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
        bpm_range_column = 2
        key_hint_column = 3
        bpm_range_combo = self._table_combo_at(row, bpm_range_column)
        if not isinstance(bpm_range_combo, QComboBox):
            bpm_range_combo = self._create_song_bpm_range_combo(song)
            self.song_table.setCellWidget(row, bpm_range_column, bpm_range_combo)
        else:
            bpm_range_combo.blockSignals(True)
            self._set_song_bpm_range_combo_value(bpm_range_combo, song.bpm_range_label)
            bpm_range_combo.blockSignals(False)

        key_hint_combo = self._table_combo_at(row, key_hint_column)
        if not isinstance(key_hint_combo, QComboBox):
            key_hint_combo = self._create_song_key_hint_combo(song)
            self.song_table.setCellWidget(row, key_hint_column, key_hint_combo)
        else:
            key_hint_combo.blockSignals(True)
            self._set_combo_data(key_hint_combo, song.analysis_key_hint)
            key_hint_combo.blockSignals(False)

        values = [
            song.file_name,
            song.file_path,
            "",
            "",
            format_duration(song.duration),
            format_bpm(song.bpm),
            format_key(song.musical_key, self.key_display_preference),
            format_camelot(song.musical_key),
            format_key(song.relative_key, self.key_display_preference),
            format_key_list(song.compatible_keys, self.key_display_preference),
            song.status,
        ]
        status_column = len(values) - 1
        key_column = 6
        camelot_column = 7
        relative_column = 8
        compatible_column = 9
        override_tooltip = self._song_processing_override_tooltip(song)
        compatible_camelot = [
            (
                f"{format_key(compatible_key, self.key_display_preference)} "
                f"({camelot_for_key(compatible_key) or 'N/A'}, {alternate_key_notation(compatible_key, self.key_display_preference)})"
                if alternate_key_notation(compatible_key, self.key_display_preference)
                else f"{format_key(compatible_key, self.key_display_preference)} ({camelot_for_key(compatible_key) or 'N/A'})"
            )
            for compatible_key in (song.compatible_keys or [])
        ]
        for column, value in enumerate(values):
            if column in {bpm_range_column, key_hint_column}:
                continue
            item = self.song_table.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.song_table.setItem(row, column, item)
            item.setText(str(value))
            if column == 0:
                item.setIcon(self._icon("file"))
                file_tooltip = song.file_path
                if override_tooltip:
                    file_tooltip = f"{file_tooltip}\n\n{override_tooltip}"
                item.setToolTip(file_tooltip)
            if column == status_column:
                item.setIcon(self._status_icon(song.status))
                item.setForeground(self._status_color(song.status))
            else:
                item.setForeground(QColor("#eef3fb"))
            if column == key_column:
                key_alias = alternate_key_notation(song.musical_key, self.key_display_preference)
                relative_alias = alternate_key_notation(song.relative_key, self.key_display_preference)
                key_tooltip_lines = [
                    f"Detected: {format_key(song.musical_key, self.key_display_preference)}",
                ]
                if key_alias:
                    key_tooltip_lines.append(f"Alternate: {key_alias}")
                key_tooltip_lines.append(f"Camelot: {format_camelot(song.musical_key)}")
                key_tooltip_lines.append(f"Relative Key: {format_key(song.relative_key, self.key_display_preference)}")
                if relative_alias:
                    key_tooltip_lines.append(f"Relative Alternate: {relative_alias}")
                key_tooltip_lines.append(f"Compatible Keys: {format_key_list(song.compatible_keys, self.key_display_preference)}")
                item.setToolTip("\n".join(key_tooltip_lines))
            elif column == relative_column:
                relative_alias = alternate_key_notation(song.relative_key, self.key_display_preference)
                item.setToolTip(
                    f"Relative Key: {format_key(song.relative_key, self.key_display_preference)}"
                    + (f"\nAlternate: {relative_alias}" if relative_alias else "")
                )
            elif column == compatible_column:
                item.setToolTip(
                    f"Compatible Keys: {', '.join(compatible_camelot) if compatible_camelot else 'N/A'}"
                )
            elif column == camelot_column:
                relative_alias = alternate_key_notation(song.relative_key, self.key_display_preference)
                item.setToolTip(
                    f"Camelot: {format_camelot(song.musical_key)}\n"
                    f"Relative Key: {format_key(song.relative_key, self.key_display_preference)} ({camelot_for_key(song.relative_key) or 'N/A'})"
                    + (f" [{relative_alias}]" if relative_alias else "")
                    + "\n"
                    f"Compatible Keys: {', '.join(compatible_camelot) if compatible_camelot else 'N/A'}"
                )
            elif column == status_column and song.status == SongStatus.ERROR.value:
                status_tooltip = song.last_error or "Task failed."
                if override_tooltip:
                    status_tooltip = f"{status_tooltip}\n\n{override_tooltip}"
                item.setToolTip(status_tooltip)
            elif column == status_column and override_tooltip:
                item.setToolTip(override_tooltip)
            elif column == status_column:
                item.setToolTip("")
            elif column != 0:
                item.setToolTip("")

    def _status_color(self, status: str) -> QColor:
        if status in {SongStatus.READY.value, SongStatus.ANALYZED.value, SongStatus.EXPORTED.value}:
            return QColor("#7fd78a")
        if status in {
            SongStatus.QUEUED_ANALYSIS.value,
            SongStatus.ANALYZING.value,
            SongStatus.SEPARATING.value,
            SongStatus.MATCHING_TEMPO.value,
            SongStatus.MATCHING_KEY.value,
            SongStatus.PROCESSING.value,
        }:
            return QColor("#f1c46c")
        if status in {SongStatus.ERROR.value, SongStatus.CANCELED.value}:
            return QColor("#f07178")
        return QColor("#dfe5ee")

    def _status_icon(self, status: str) -> QIcon:
        if status in {SongStatus.READY.value, SongStatus.ANALYZED.value, SongStatus.EXPORTED.value}:
            return self._icon("status_ready")
        if status in {
            SongStatus.QUEUED_ANALYSIS.value,
            SongStatus.ANALYZING.value,
            SongStatus.SEPARATING.value,
            SongStatus.MATCHING_TEMPO.value,
            SongStatus.MATCHING_KEY.value,
            SongStatus.PROCESSING.value,
        }:
            return self._icon("status_working")
        if status in {SongStatus.ERROR.value, SongStatus.CANCELED.value}:
            return self._icon("status_error")
        return QIcon()

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
