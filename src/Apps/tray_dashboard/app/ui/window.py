from __future__ import annotations

import ctypes
import sys
import time
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from ..backend.service import HeadsetBackendService
from ..constants import CHANNELS, SIDETONE_LABELS
from ..models import WorkerCommand
from .widgets import BatteryLineWidget


class TrayDashboardWindow(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Arctis Nova Control")
        self.setWindowFlag(QtCore.Qt.Tool, True)
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint, True)
        self.setMinimumSize(740, 420)
        self.setMaximumSize(860, 560)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self._updating_ui = False
        self._channel_edit_until: dict[str, float] = {channel: 0.0 for channel in CHANNELS}
        self._channel_widgets: dict[str, dict[str, Any]] = {}

        self._build_ui()
        self._build_backend()
        self._build_tray()

    def _build_ui(self) -> None:
        font = self.font()
        font.setFamily("Segoe UI")
        font.setPointSize(9)
        self.setFont(font)

        root_outer = QtWidgets.QVBoxLayout(self)
        root_outer.setContentsMargins(0, 0, 0, 0)
        root_outer.setSpacing(0)
        panel = QtWidgets.QWidget()
        panel.setObjectName("rootPanel")
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(6)
        root_outer.addWidget(panel)

        self.setStyleSheet(
            """
            QWidget#rootPanel {
                background-color: rgba(24, 26, 31, 208);
                color: rgba(230, 235, 242, 235);
                border: 1px solid rgba(255, 255, 255, 24);
                border-radius: 14px;
            }
            QGroupBox {
                font-weight: 600;
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 6px;
                background: rgba(34, 38, 45, 170);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QLabel { color: rgba(228, 233, 240, 232); }
            QComboBox, QCheckBox { color: rgba(230, 235, 242, 235); }
            QComboBox {
                background: rgba(18, 21, 26, 190);
                border: 1px solid rgba(255, 255, 255, 26);
                border-radius: 7px;
                padding: 3px 8px;
            }
            QComboBox::drop-down { border: none; width: 18px; }
            QScrollArea { background: transparent; border: none; }
            QWidget#sonarContainer { background: transparent; }
            QWidget#sonarRow {
                background: rgba(255, 255, 255, 8);
                border: 1px solid rgba(255, 255, 255, 12);
                border-radius: 8px;
            }
            QWidget#sonarRow QLabel { color: rgba(235, 239, 245, 232); }
            """
        )

        top = QtWidgets.QGroupBox("Status")
        top_layout = QtWidgets.QGridLayout(top)
        top_layout.setHorizontalSpacing(10)
        top_layout.setVerticalSpacing(4)

        self.lbl_conn = QtWidgets.QLabel("connected: N/A  wireless: N/A  bluetooth: N/A")
        self.lbl_modes = QtWidgets.QLabel("ANC: N/A  mute: N/A  sidetone: N/A")
        self.lbl_live = QtWidgets.QLabel("chat mix: N/A   OLED brightness: N/A")
        self.battery_line = BatteryLineWidget()
        self.pb_headset_volume = QtWidgets.QProgressBar()
        self.pb_headset_volume.setRange(0, 100)
        self.pb_headset_volume.setValue(0)
        self.pb_headset_volume.setTextVisible(False)
        self.pb_headset_volume.setFixedHeight(10)
        self.lbl_headset_volume = QtWidgets.QLabel("Headset volume: N/A")
        self.lbl_updated = QtWidgets.QLabel("updated: --:--:--")

        top_layout.addWidget(self.lbl_conn, 0, 0, 1, 2)
        top_layout.addWidget(self.lbl_modes, 1, 0, 1, 2)
        top_layout.addWidget(self.lbl_live, 2, 0, 1, 2)
        top_layout.addWidget(self.battery_line, 3, 0, 1, 2)
        top_layout.addWidget(self.lbl_headset_volume, 4, 0, 1, 2)
        top_layout.addWidget(self.pb_headset_volume, 5, 0, 1, 2)
        top_layout.addWidget(self.lbl_updated, 6, 0, 1, 2)

        channels_group = QtWidgets.QGroupBox("Sonar Channels")
        channels_layout = QtWidgets.QVBoxLayout(channels_group)
        channels_layout.setSpacing(4)
        channels_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        container = QtWidgets.QWidget()
        container.setObjectName("sonarContainer")
        rows = QtWidgets.QVBoxLayout(container)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(4)

        for channel in CHANNELS:
            row = QtWidgets.QWidget()
            row.setObjectName("sonarRow")
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(6)

            title = QtWidgets.QLabel(channel)
            title.setMinimumWidth(80)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setFixedWidth(130)
            vol_label = QtWidgets.QLabel("0%")
            vol_label.setFixedWidth(34)
            mute = QtWidgets.QCheckBox("mute")
            preset = QtWidgets.QComboBox()
            preset.setMinimumWidth(120)
            apps = QtWidgets.QLabel("-")
            apps.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            apps.setMinimumWidth(240)

            slider.sliderPressed.connect(self._make_slider_press_handler(channel))
            slider.sliderReleased.connect(self._make_volume_handler(channel, slider, vol_label))
            slider.valueChanged.connect(lambda value, lbl=vol_label: lbl.setText(f"{value}%"))
            mute.stateChanged.connect(self._make_mute_handler(channel, mute))
            preset.currentIndexChanged.connect(self._make_preset_handler(channel, preset))

            row_layout.addWidget(title)
            row_layout.addWidget(slider)
            row_layout.addWidget(vol_label)
            row_layout.addWidget(mute)
            row_layout.addWidget(preset)
            row_layout.addWidget(apps, 1)
            rows.addWidget(row)

            self._channel_widgets[channel] = {
                "slider": slider,
                "vol_label": vol_label,
                "mute": mute,
                "preset": preset,
                "apps": apps,
            }

        rows.addStretch(1)
        scroll.setWidget(container)
        channels_layout.addWidget(scroll)

        self.lbl_status = QtWidgets.QLabel("ready")
        self.lbl_status.setStyleSheet("color: rgba(190, 196, 205, 220);")

        panel_layout.addWidget(top)
        panel_layout.addWidget(channels_group, 1)
        panel_layout.addWidget(self.lbl_status)

    def _build_backend(self) -> None:
        self._thread = QtCore.QThread(self)
        self._service = HeadsetBackendService()
        self._service.moveToThread(self._thread)
        self._thread.started.connect(self._service.run)
        self._service.state_updated.connect(self._apply_state)
        self._service.presets_loaded.connect(self._apply_presets)
        self._service.status.connect(self._set_status)
        self._service.error.connect(self._set_error)
        self._thread.start()

    def _build_tray(self) -> None:
        self._tray = QtWidgets.QSystemTrayIcon(self)
        self._tray.setIcon(self._build_icon())
        self._tray.setToolTip("Arctis Nova Control")
        menu = QtWidgets.QMenu()
        act_open = menu.addAction("Open")
        act_quit = menu.addAction("Quit")
        act_open.triggered.connect(self.show_window)
        act_quit.triggered.connect(self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()
        self._apply_windows_effects()

    def _build_icon(self) -> QtGui.QIcon:
        pix = QtGui.QPixmap(64, 64)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QColor("#0078D4"))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        painter.setPen(QtGui.QPen(QtGui.QColor("white"), 4))
        painter.drawArc(14, 16, 36, 32, 0 * 16, 180 * 16)
        painter.drawLine(18, 44, 18, 52)
        painter.drawLine(46, 44, 46, 52)
        painter.end()
        return QtGui.QIcon(pix)

    def event(self, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.WindowDeactivate and self.isVisible():
            QtCore.QTimer.singleShot(0, self._hide_if_same_monitor_cursor)
        return super().event(event)

    def _hide_if_same_monitor_cursor(self) -> None:
        pos = QtGui.QCursor.pos()
        own_screen = self.windowHandle().screen() if self.windowHandle() else QtGui.QGuiApplication.primaryScreen()
        cursor_screen = QtGui.QGuiApplication.screenAt(pos)
        if own_screen is None or cursor_screen is None or cursor_screen == own_screen:
            self.hide()

    @QtCore.Slot(dict)
    def _apply_presets(self, presets: dict[str, list[tuple[str, str]]]) -> None:
        self._updating_ui = True
        try:
            for channel, values in presets.items():
                combo: QtWidgets.QComboBox = self._channel_widgets[channel]["preset"]
                combo.blockSignals(True)
                combo.clear()
                for preset_id, name in values:
                    combo.addItem(name, preset_id)
                combo.blockSignals(False)
        finally:
            self._updating_ui = False

    @QtCore.Slot(dict)
    def _apply_state(self, state: dict[str, Any]) -> None:
        self._updating_ui = True
        try:
            headset_batt = int(state.get("headset_battery_percent") or 0)
            base_batt = int(state.get("base_battery_percent") or 0)
            self.battery_line.set_values(headset_batt, base_batt)
            self.lbl_conn.setText(
                f"connected={_yn(state.get('connected'))}  wireless={_yn(state.get('wireless'))}  bluetooth={_yn(state.get('bluetooth'))}"
            )
            sidetone = state.get("sidetone_level")
            sidetone_label = SIDETONE_LABELS.get(int(sidetone), str(sidetone)) if sidetone is not None else "N/A"
            self.lbl_modes.setText(
                f"ANC: {state.get('anc_mode') or 'N/A'}  mute: {_yn(state.get('mic_mute'))}  sidetone: {sidetone_label}"
            )
            self.lbl_updated.setText(f"updated: {state.get('updated_at') or '--:--:--'}")
            chat_mix = state.get("chat_mix_balance")
            brightness = state.get("oled_brightness")
            self.lbl_live.setText(
                f"chat mix: {chat_mix if isinstance(chat_mix, int) else 'N/A'}%   OLED brightness: {brightness if isinstance(brightness, int) else 'N/A'}"
            )
            headset_volume = state.get("headset_volume_percent")
            if isinstance(headset_volume, int):
                self.pb_headset_volume.setValue(max(0, min(100, headset_volume)))
                self.lbl_headset_volume.setText(f"Headset volume: {headset_volume}%")
            else:
                self.pb_headset_volume.setValue(0)
                self.lbl_headset_volume.setText("Headset volume: N/A")

            channel_volume = state.get("channel_volume", {})
            channel_mute = state.get("channel_mute", {})
            channel_preset = state.get("channel_preset", {})
            channel_apps = state.get("channel_apps", {})

            for channel in CHANNELS:
                widgets = self._channel_widgets[channel]
                slider: QtWidgets.QSlider = widgets["slider"]
                mute: QtWidgets.QCheckBox = widgets["mute"]
                preset: QtWidgets.QComboBox = widgets["preset"]
                apps: QtWidgets.QLabel = widgets["apps"]

                vol = channel_volume.get(channel)
                if isinstance(vol, int) and not slider.isSliderDown() and not self._is_channel_locked(channel):
                    slider.blockSignals(True)
                    slider.setValue(max(0, min(100, vol)))
                    widgets["vol_label"].setText(f"{max(0, min(100, vol))}%")
                    slider.blockSignals(False)
                muted = channel_mute.get(channel)
                if isinstance(muted, bool) and not self._is_channel_locked(channel):
                    mute.blockSignals(True)
                    mute.setChecked(muted)
                    mute.blockSignals(False)
                preset_id = channel_preset.get(channel)
                if preset_id and not self._is_channel_locked(channel):
                    idx = preset.findData(preset_id)
                    if idx >= 0:
                        preset.blockSignals(True)
                        preset.setCurrentIndex(idx)
                        preset.blockSignals(False)
                routed = channel_apps.get(channel, [])
                apps.setText(", ".join(routed) if isinstance(routed, list) and routed else "-")
        finally:
            self._updating_ui = False

    def _make_slider_press_handler(self, channel: str):
        def handler() -> None:
            self._channel_edit_until[channel] = time.monotonic() + 2.0

        return handler

    def _make_volume_handler(self, channel: str, slider: QtWidgets.QSlider, vol_label: QtWidgets.QLabel):
        def handler() -> None:
            if self._updating_ui:
                return
            self._channel_edit_until[channel] = time.monotonic() + 1.0
            vol_label.setText(f"{slider.value()}%")
            self._service.submit(WorkerCommand("set_channel_volume", {"channel": channel, "value": slider.value()}))

        return handler

    def _make_mute_handler(self, channel: str, checkbox: QtWidgets.QCheckBox):
        def handler(_state: int) -> None:
            if self._updating_ui:
                return
            self._channel_edit_until[channel] = time.monotonic() + 1.0
            self._service.submit(WorkerCommand("set_channel_mute", {"channel": channel, "value": checkbox.isChecked()}))

        return handler

    def _make_preset_handler(self, channel: str, combo: QtWidgets.QComboBox):
        def handler(_idx: int) -> None:
            if self._updating_ui:
                return
            preset_id = combo.currentData()
            if not preset_id:
                return
            self._channel_edit_until[channel] = time.monotonic() + 1.2
            self._service.submit(WorkerCommand("set_preset", {"channel": channel, "preset_id": preset_id}))

        return handler

    def _set_status(self, text: str) -> None:
        self.lbl_status.setStyleSheet("color: rgba(190, 196, 205, 220);")
        self.lbl_status.setText(text)

    def _set_error(self, text: str) -> None:
        self.lbl_status.setStyleSheet("color: rgba(255, 120, 120, 235);")
        self.lbl_status.setText(text)

    def _on_tray_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick):
            self.show_window()

    def show_window(self) -> None:
        self.adjustSize()
        self.show()
        QtCore.QTimer.singleShot(0, self._move_bottom_right)
        self.raise_()
        self.activateWindow()
        self._apply_windows_effects()

    def _move_bottom_right(self) -> None:
        screen = QtGui.QGuiApplication.primaryScreen()
        if not screen:
            return
        geom = screen.availableGeometry()
        frame = self.frameGeometry()
        x = geom.right() - frame.width() - 20
        y = geom.bottom() - frame.height() - 28
        self.move(max(0, x), max(0, y))

    def _is_channel_locked(self, channel: str) -> bool:
        return time.monotonic() < self._channel_edit_until.get(channel, 0.0)

    def _apply_windows_effects(self) -> None:
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            pref = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE),
                ctypes.byref(pref),
                ctypes.sizeof(pref),
            )
            DWMWA_SYSTEMBACKDROP_TYPE = 38
            DWMSBT_MAINWINDOW = 2
            backdrop = ctypes.c_int(DWMSBT_MAINWINDOW)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE),
                ctypes.byref(backdrop),
                ctypes.sizeof(backdrop),
            )
        except Exception:
            pass

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        event.ignore()
        self.hide()

    def _quit_app(self) -> None:
        self._service.stop()
        self._thread.quit()
        self._thread.wait(1500)
        QtWidgets.QApplication.quit()


def _yn(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "N/A"
