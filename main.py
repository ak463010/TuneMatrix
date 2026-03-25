from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from main_window import MainWindow


def excepthook(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(message, file=sys.stderr)
    QMessageBox.critical(None, "TuneMatrix", f"Unexpected error:\n\n{exc_value}")


def main() -> int:
    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    app.setApplicationName("TuneMatrix")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
