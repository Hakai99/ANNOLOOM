"""Entry point for the `annoloom` console command."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from annoloom.ui.main_window import MainWindow

LOGO_PATH = Path(__file__).parent / "resources" / "logo.png"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AnnoLoom")
    if LOGO_PATH.exists():
        app.setWindowIcon(QIcon(str(LOGO_PATH)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
