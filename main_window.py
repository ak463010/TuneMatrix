from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPoint, QSize, QThread, Qt, QTime, Signal
from PySide6.QtGui import QAction, QColor, QIcon
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
from models import KEY_OPTIONS, ProcessingOptions, SongRecord, SongStatus, STEM_OPTIONS, TABLE_HEADERS
from utils import (
    default_export_dir,
    format_bpm,
    format_duration,
    format_key,
    format_key_list,
    is_supported_audio_file,
    validate_audio_file,
)
from workers import AnalyzeWorker, ProcessingWorker

PROJECT_STATE_VERSION = 1
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

    def _update_hover_cursor(self, pos: QPoint) -> None:
        if self.indexAt(pos).isValid():
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            return
        self.viewport().unsetCursor()

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
        self.current_thread: Optional[QThread] = None
        self.current_worker = None
        self.task_cancel_requested = False
        self.action_dependency_messages: dict[str, str] = {}

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

        self.export_action = QAction("Export", self)
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

        menu_bar = self.menuBar()
        menu_bar.clear()
        menu_bar.addMenu(self.file_menu)
        menu_bar.addMenu(self.edit_menu)
        menu_bar.addMenu(self.tools_menu)
        menu_bar.addMenu(self.help_menu)

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
        toolbar_layout.addStretch(2)
        toolbar_layout.addWidget(self.remove_button)
        toolbar_layout.addStretch(1)
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
        self.song_table.verticalHeader().setDefaultSectionSize(30)
        self.song_table.setShowGrid(True)
        self.song_table.files_dropped.connect(self.import_songs)

        header = self.song_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        self.song_table.setColumnHidden(1, True)

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

        self.reference_checkbox = QCheckBox("Match to reference song")
        self.reference_checkbox.setObjectName("panelCheck")
        layout.addWidget(self.reference_checkbox)

        stem_label = QLabel("Stem Selection")
        stem_label.setObjectName("fieldLabel")
        layout.addWidget(stem_label)

        self.stem_option_combo = QComboBox()
        for stem_option in STEM_OPTIONS:
            self.stem_option_combo.addItem(stem_option, stem_option)
        self.stem_option_combo.setCurrentText("All stems")
        self.stem_option_combo.setVisible(False)

        self.stem_checkboxes: dict[str, QCheckBox] = {}
        for display_label, stem_value in STEM_CHECKBOX_OPTIONS:
            checkbox = QCheckBox(display_label)
            checkbox.setObjectName("panelCheck")
            checkbox.toggled.connect(self._sync_stem_option_from_checkboxes)
            self.stem_checkboxes[stem_value] = checkbox
            layout.addWidget(checkbox)

        self.stem_option_combo.currentIndexChanged.connect(self._sync_stem_checkboxes_from_combo)

        form_layout = QFormLayout()
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(8)

        self.target_bpm_edit = QLineEdit()
        self.target_bpm_edit.setPlaceholderText("128")
        self.target_bpm_edit.setFixedHeight(28)

        self.target_key_combo = QComboBox()
        self.target_key_combo.addItem("Unchanged", None)
        for key_name in KEY_OPTIONS:
            self.target_key_combo.addItem(key_name, key_name)
        self.target_key_combo.setFixedHeight(28)

        self.reference_combo = QComboBox()
        self.reference_combo.addItem("None", None)
        self.reference_combo.setFixedHeight(28)

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
        form_layout.addRow("Output Folder", output_row)

        layout.addLayout(form_layout)
        layout.addStretch(1)

        hint_label = QLabel("Drag and drop mp3, wav, flac, or m4a files onto the song table.")
        hint_label.setWordWrap(True)
        hint_label.setObjectName("hintLabel")
        layout.addWidget(hint_label)

        self._sync_stem_checkboxes_from_combo()
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
        self.export_button = QPushButton("Export")
        self.cancel_button = QPushButton("Cancel Task")
        self.cancel_button.setEnabled(False)

        primary_buttons = [
            (self.analyze_button, self._icon("analyze")),
            (self.separate_button, self._icon("separate")),
            (self.match_tempo_button, self._icon("tempo")),
            (self.match_key_button, self._icon("key")),
            (self.process_all_button, self._icon("process")),
            (self.export_button, self._icon("export")),
        ]
        button_widths = {
            self.analyze_button: 114,
            self.separate_button: 136,
            self.match_tempo_button: 126,
            self.match_key_button: 114,
            self.process_all_button: 116,
            self.export_button: 92,
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
        self.export_button.clicked.connect(lambda: self.start_processing_task("export"))
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
            }
            QTableWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #10161d;
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
            % (checkbox_unchecked_icon, checkbox_checked_icon)
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

    def selected_stem_values(self) -> list[str]:
        if not hasattr(self, "stem_checkboxes"):
            return []
        return [stem_name for stem_name, checkbox in self.stem_checkboxes.items() if checkbox.isChecked()]

    def _sync_stem_checkboxes_from_combo(self) -> None:
        if not hasattr(self, "stem_checkboxes"):
            return

        current_option = self.stem_option_combo.currentData() or "All stems"
        if current_option == "All stems":
            selected_values = set(self.stem_checkboxes)
        else:
            selected_values = {current_option}

        for stem_name, checkbox in self.stem_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(stem_name in selected_values)
            checkbox.blockSignals(False)

    def _sync_stem_option_from_checkboxes(self) -> None:
        if not hasattr(self, "stem_option_combo"):
            return

        selected_values = self.selected_stem_values()
        if not selected_values:
            self._set_combo_data(self.stem_option_combo, "All stems")
            self._sync_stem_checkboxes_from_combo()
            return
        if len(selected_values) == len(self.stem_checkboxes):
            self._set_combo_data(self.stem_option_combo, "All stems")
            return
        if len(selected_values) == 1:
            self._set_combo_data(self.stem_option_combo, selected_values[0])
            return

        self._set_combo_data(self.stem_option_combo, "All stems")

    def collect_project_state(self) -> dict[str, object]:
        return {
            "format_version": PROJECT_STATE_VERSION,
            "songs": [song.to_dict() for song in self.songs],
            "ui": {
                "target_bpm_text": self.target_bpm_edit.text().strip(),
                "target_key": self.target_key_combo.currentData(),
                "stem_option": self.stem_option_combo.currentData(),
                "selected_stems": self.selected_stem_values(),
                "match_to_reference": self.reference_checkbox.isChecked(),
                "reference_song_path": self.reference_combo.currentData(),
                "output_dir": self.output_dir_edit.text().strip(),
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
        self.song_table.setRowCount(0)
        for song in self.songs:
            self._append_song_row(song)

        self.target_bpm_edit.setText(str(ui_state.get("target_bpm_text") or ""))
        self._set_combo_data(self.target_key_combo, ui_state.get("target_key"))
        self._set_combo_data(self.stem_option_combo, ui_state.get("stem_option"))
        selected_stems = ui_state.get("selected_stems")
        if isinstance(selected_stems, list):
            for stem_name, checkbox in self.stem_checkboxes.items():
                checkbox.blockSignals(True)
                checkbox.setChecked(stem_name in selected_stems)
                checkbox.blockSignals(False)
            self._sync_stem_option_from_checkboxes()
        else:
            self._sync_stem_checkboxes_from_combo()
        self.reference_checkbox.setChecked(bool(ui_state.get("match_to_reference", False)))
        if "output_dir" in ui_state:
            self.output_dir_edit.setText(str(ui_state.get("output_dir") or ""))
        else:
            self.output_dir_edit.setText(default_export_dir())

        self.refresh_reference_combo()
        reference_song_path = ui_state.get("reference_song_path")
        self._set_combo_data(self.reference_combo, reference_song_path)
        if reference_song_path and self.reference_combo.currentData() != reference_song_path:
            self.append_log("Saved reference song was not found in the restored project.")

        self.progress_bar.setValue(0)
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
        if not self._can_modify_project("importing songs"):
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

        self.refresh_reference_combo()

    def clear_songs(self) -> None:
        if not self._can_modify_project("clearing the song list"):
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

        selected_stems = self.selected_stem_values()
        if not selected_stems or len(selected_stems) == len(self.stem_checkboxes):
            stem_option = "All stems"
        elif len(selected_stems) == 1:
            stem_option = selected_stems[0]
        else:
            stem_option = "All stems"

        return ProcessingOptions(
            stem_option=stem_option,
            selected_stems=selected_stems,
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

    def changeEvent(self, event) -> None:  # type: ignore[override]
        if hasattr(self, "title_bar"):
            self.title_bar.sync_window_state()
        super().changeEvent(event)

    def set_task_running(self, running: bool) -> None:
        always_available_controls = [
            self.open_project_action,
            self.save_project_action,
            self.import_button,
            self.remove_button,
            self.clear_button,
            self.reference_checkbox,
            self.reference_combo,
            self.target_bpm_edit,
            self.target_key_combo,
            self.stem_option_combo,
            self.output_dir_edit,
            self.output_browse_button,
            self.import_action,
            self.remove_action,
            self.clear_action,
        ]

        for control in always_available_controls:
            control.setEnabled(not running)

        self.cancel_button.setEnabled(running)
        self.cancel_button.setVisible(running)
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
            format_key(song.relative_key),
            format_key_list(song.compatible_keys),
            song.status,
        ]
        status_column = len(values) - 1
        key_column = 4
        relative_column = 5
        compatible_column = 6
        for column, value in enumerate(values):
            item = self.song_table.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.song_table.setItem(row, column, item)
            item.setText(str(value))
            if column == 0:
                item.setIcon(self._icon("file"))
            if column == status_column:
                item.setIcon(self._status_icon(song.status))
                item.setForeground(self._status_color(song.status))
            else:
                item.setForeground(QColor("#eef3fb"))
            if column == key_column:
                item.setToolTip(
                    f"Detected: {format_key(song.musical_key)}\n"
                    f"Relative: {format_key(song.relative_key)}\n"
                    f"Compatible: {format_key_list(song.compatible_keys)}"
                )
            elif column == relative_column:
                item.setToolTip(format_key(song.relative_key))
            elif column == compatible_column:
                item.setToolTip(format_key_list(song.compatible_keys))
            elif column == status_column and song.status == SongStatus.ERROR.value:
                item.setToolTip(song.last_error or "Task failed.")
            elif column == status_column:
                item.setToolTip("")
            else:
                item.setToolTip("")

    def _status_color(self, status: str) -> QColor:
        if status in {SongStatus.READY.value, SongStatus.ANALYZED.value, SongStatus.EXPORTED.value}:
            return QColor("#7fd78a")
        if status in {
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
