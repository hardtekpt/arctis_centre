from __future__ import annotations

import sys

from PySide6 import QtWidgets

from app import TrayDashboardWindow


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("windowsvista")
    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        raise RuntimeError("System tray is not available on this system.")
    window = TrayDashboardWindow()
    window.show_window()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
