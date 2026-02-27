from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


class BatteryLineWidget(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._headset = 0
        self._base = 0
        self.setMinimumHeight(28)

    def set_values(self, headset_percent: int, base_percent: int) -> None:
        self._headset = max(0, min(100, int(headset_percent)))
        self._base = max(0, min(100, int(base_percent)))
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QtCore.Qt.transparent)

        headset_area = QtCore.QRect(8, 5, (rect.width() // 2) - 12, rect.height() - 10)
        base_area = QtCore.QRect((rect.width() // 2) + 4, 5, (rect.width() // 2) - 12, rect.height() - 10)
        self._draw_battery(painter, headset_area, self._headset, "H")
        self._draw_battery(painter, base_area, self._base, "B")
        painter.end()

    def _draw_battery(self, painter: QtGui.QPainter, area: QtCore.QRect, value: int, tag: str) -> None:
        body = QtCore.QRect(area.x() + 18, area.y() + 2, area.width() - 58, area.height() - 4)
        cap = QtCore.QRect(body.right() + 1, body.y() + body.height() // 3, 5, body.height() // 3)
        fill_width = max(0, int((body.width() - 4) * (value / 100.0)))
        fill_rect = QtCore.QRect(body.x() + 2, body.y() + 2, fill_width, body.height() - 4)

        painter.setPen(QtGui.QPen(QtGui.QColor(150, 160, 175, 220), 1))
        painter.setBrush(QtGui.QColor(25, 28, 34, 180))
        painter.drawRoundedRect(body, 4, 4)
        painter.drawRoundedRect(cap, 1, 1)

        color = QtGui.QColor(0, 180, 120, 230) if value >= 20 else QtGui.QColor(220, 80, 80, 230)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(fill_rect, 3, 3)

        painter.setPen(QtGui.QColor(220, 225, 232, 230))
        painter.drawText(QtCore.QRect(area.x(), area.y(), 14, area.height()), QtCore.Qt.AlignCenter, tag)
        painter.drawText(QtCore.QRect(body.right() + 10, area.y(), 36, area.height()), QtCore.Qt.AlignVCenter, f"{value}%")
