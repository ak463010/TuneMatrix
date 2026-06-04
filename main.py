from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from main_window import MainWindow


def excepthook(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(message, file=sys.stderr)
    QMessageBox.critical(None, "TuneMatrix", f"Unexpected error:\n\n{exc_value}")


def _prepare_argv(argv: list[str]) -> tuple[list[str], bool]:
    smoke_from_env = os.environ.get("TUNEMATRIX_SMOKE_TEST", "").strip().lower()
    smoke_test = smoke_from_env in {"1", "true", "yes", "on"}
    prepared = [argv[0]]
    for argument in argv[1:]:
        if argument == "--smoke-test":
            smoke_test = True
            continue
        prepared.append(argument)
    return prepared, smoke_test


def main() -> int:
    sys.excepthook = excepthook
    qt_argv, smoke_test = _prepare_argv(sys.argv)
    app = QApplication(qt_argv)
    app.setApplicationName("TuneMatrix")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    if smoke_test:
        QTimer.singleShot(100, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
