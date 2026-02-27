from __future__ import annotations

import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

from PySide6 import QtCore

from arctis_nova_api import (
    AncMode,
    AncStatus,
    ArctisNovaProApi,
    BatteryStatus,
    ExperimentalCommandProfile,
    HeadsetConnectionStatus,
    MicStatus,
    OledBrightnessStatus,
    SidetoneStatus,
    StreamerSlider,
    VolumeKnobEvent,
)
from arctis_nova_api.errors import UnsupportedFeatureError

from ..constants import CHANNELS, CHANNEL_MAP, PRESET_CHANNEL_MAP
from ..models import WorkerCommand

DEFAULT_STATE_FILE = Path("src/APIs/arctis_nova_api/tools/tray_dashboard_state.json")
DEFAULT_STATE: dict[str, Any] = {
    "headset_battery_percent": None,
    "base_battery_percent": None,
    "headset_volume_percent": None,
    "anc_mode": None,
    "mic_mute": None,
    "sidetone_level": None,
    "connected": None,
    "wireless": None,
    "bluetooth": None,
    "chat_mix_balance": None,
    "oled_brightness": None,
    "channel_volume": {},
    "channel_mute": {},
    "channel_preset": {},
    "channel_apps": {},
    "updated_at": None,
}


def build_command_profile() -> ExperimentalCommandProfile:
    return ExperimentalCommandProfile(
        anc_event_command_id=0xBD,
        anc_value_index=2,
        anc_value_map={0: AncMode.OFF, 1: AncMode.TRANSPARENCY, 2: AncMode.ANC},
        mic_event_command_id=0xBB,
        mic_value_index=2,
        mic_muted_values={1},
        sidetone_event_command_id=0x39,
        sidetone_value_index=2,
        sidetone_label_map={"off": 0, "low": 1, "med": 2, "high": 3},
    )


class HeadsetBackendService(QtCore.QObject):
    state_updated = QtCore.Signal(dict)
    presets_loaded = QtCore.Signal(dict)
    status = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, state_file: Path | None = None) -> None:
        super().__init__()
        self._stop = threading.Event()
        self._queue: queue.Queue[WorkerCommand] = queue.Queue()
        self._state_file = state_file or DEFAULT_STATE_FILE
        self._state: dict[str, Any] = self._load_state()
        self._api: ArctisNovaProApi | None = None
        self._presets_cache: dict[str, list[tuple[str, str]]] = {}

    def submit(self, cmd: WorkerCommand) -> None:
        self._queue.put(cmd)

    def stop(self) -> None:
        self._stop.set()

    @QtCore.Slot()
    def run(self) -> None:
        try:
            self._api = ArctisNovaProApi(command_profile=build_command_profile())
            self._api.base_station.connect()
            self._load_presets_once()
            self._refresh_all(force_emit=True)
            last_fast = 0.0
            last_sonar = 0.0
            last_hw = 0.0
            while not self._stop.is_set():
                self._drain_commands()
                now = time.monotonic()
                changed = False
                if now - last_fast >= 0.12:
                    changed |= self._refresh_events()
                    last_fast = now
                if now - last_sonar >= 0.6:
                    changed |= self._refresh_sonar()
                    last_sonar = now
                if now - last_hw >= 0.8:
                    changed |= self._refresh_hw()
                    last_hw = now
                if changed:
                    self._state["updated_at"] = time.strftime("%H:%M:%S")
                    self._save_state()
                    self.state_updated.emit(dict(self._state))
                time.sleep(0.02)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            try:
                if self._api:
                    self._api.base_station.close()
            except Exception:
                pass
            self._save_state()

    def _load_presets_once(self) -> None:
        if not self._api:
            return
        cache: dict[str, list[tuple[str, str]]] = {}
        for channel, preset_channel in PRESET_CHANNEL_MAP.items():
            try:
                presets = self._api.sonar.list_favorite_presets(preset_channel)
                cache[channel] = [(preset.preset_id, preset.name) for preset in presets]
            except Exception:
                cache[channel] = []
        self._presets_cache = cache
        self.presets_loaded.emit(cache)

    def _drain_commands(self) -> None:
        if not self._api:
            return
        while True:
            try:
                cmd = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._handle_command(cmd)
            except UnsupportedFeatureError as exc:
                self.status.emit(str(exc))
            except Exception as exc:
                self.error.emit(str(exc))

    def _handle_command(self, cmd: WorkerCommand) -> None:
        assert self._api is not None
        if cmd.name == "set_channel_volume":
            channel = CHANNEL_MAP[str(cmd.payload["channel"])]
            value = max(0, min(100, int(cmd.payload["value"])))
            errors: list[str] = []
            for kwargs in (
                {"streamer": False},
                {"streamer": True, "streamer_slider": StreamerSlider.STREAMING},
                {"streamer": True, "streamer_slider": StreamerSlider.MONITORING},
            ):
                try:
                    self._api.sonar.set_channel_volume(channel, value / 100.0, **kwargs)
                except Exception as exc:
                    errors.append(str(exc))
            applied = int(round(self._api.sonar.get_channel_volume(channel) * 100))
            if abs(applied - value) > 2:
                self.status.emit(f"{channel.value} write mismatch (wanted {value}%, got {applied}%)")
            else:
                suffix = " (partial mode sync)" if errors else ""
                self.status.emit(f"{channel.value} volume {applied}%{suffix}")
            self._refresh_sonar()
            self._save_state()
            self.state_updated.emit(dict(self._state))
            return

        if cmd.name == "set_channel_mute":
            channel = CHANNEL_MAP[str(cmd.payload["channel"])]
            muted = bool(cmd.payload["value"])
            errors: list[str] = []
            for kwargs in (
                {"streamer": False},
                {"streamer": True, "streamer_slider": StreamerSlider.STREAMING},
                {"streamer": True, "streamer_slider": StreamerSlider.MONITORING},
            ):
                try:
                    self._api.sonar.set_channel_mute(channel, muted, **kwargs)
                except Exception as exc:
                    errors.append(str(exc))
            applied = self._api.sonar.get_channel_mute(channel)
            if applied != muted:
                self.status.emit(f"{channel.value} mute mismatch (wanted {muted}, got {applied})")
            else:
                suffix = " (partial mode sync)" if errors else ""
                self.status.emit(f"{channel.value} {'muted' if applied else 'unmuted'}{suffix}")
            self._refresh_sonar()
            self._save_state()
            self.state_updated.emit(dict(self._state))
            return

        if cmd.name == "set_preset":
            preset_id = str(cmd.payload["preset_id"])
            channel = str(cmd.payload["channel"])
            selected_name: str | None = None
            for pid, pname in self._presets_cache.get(channel, []):
                if pid == preset_id:
                    selected_name = pname
                    break
            if selected_name:
                self._api.sonar.select_preset_for_channel(PRESET_CHANNEL_MAP[channel], selected_name)
            else:
                self._api.sonar.select_preset(preset_id)
            verify = self._api.sonar.get_selected_preset(PRESET_CHANNEL_MAP[channel])
            if verify and verify.preset_id == preset_id:
                self.status.emit(f"{channel} preset set to {verify.name}")
            else:
                self.status.emit(f"{channel} preset write may not have applied")
            self._refresh_sonar()
            self._save_state()
            self.state_updated.emit(dict(self._state))
            return

    def _refresh_all(self, force_emit: bool = False) -> None:
        changed = self._refresh_events()
        changed |= self._refresh_sonar()
        changed |= self._refresh_hw()
        if changed or force_emit:
            self._state["updated_at"] = time.strftime("%H:%M:%S")
            self._save_state()
            self.state_updated.emit(dict(self._state))

    def _refresh_events(self) -> bool:
        if not self._api:
            return False
        changed = False
        events = self._api.base_station.get_pending_events()
        for event in events:
            if isinstance(event, BatteryStatus):
                changed |= self._set("headset_battery_percent", int(round(event.headset_percent)))
                changed |= self._set("base_battery_percent", int(round(event.charging_percent)))
            elif isinstance(event, VolumeKnobEvent):
                changed |= self._set("headset_volume_percent", int(round(event.volume_percent)))
            elif isinstance(event, AncStatus):
                changed |= self._set("anc_mode", event.mode.value)
            elif isinstance(event, MicStatus):
                changed |= self._set("mic_mute", not event.enabled)
            elif isinstance(event, SidetoneStatus):
                changed |= self._set("sidetone_level", event.level)
            elif isinstance(event, OledBrightnessStatus):
                changed |= self._set("oled_brightness", event.level)
            elif isinstance(event, HeadsetConnectionStatus):
                changed |= self._set("connected", event.wireless)
                changed |= self._set("wireless", event.wireless)
                changed |= self._set("bluetooth", event.bluetooth)
                if event.wireless:
                    changed |= self._set("anc_mode", "off")
        return changed

    def _refresh_sonar(self) -> bool:
        if not self._api:
            return False
        changed = False
        channel_volume = dict(self._state.get("channel_volume", {}))
        channel_mute = dict(self._state.get("channel_mute", {}))
        channel_preset = dict(self._state.get("channel_preset", {}))
        for channel in CHANNELS:
            try:
                channel_volume[channel] = int(round(self._api.sonar.get_channel_volume(CHANNEL_MAP[channel]) * 100))
            except Exception:
                pass
            try:
                channel_mute[channel] = bool(self._api.sonar.get_channel_mute(CHANNEL_MAP[channel]))
            except Exception:
                pass
            try:
                selected = self._api.sonar.get_selected_preset(PRESET_CHANNEL_MAP[channel])
                channel_preset[channel] = selected.preset_id if selected else None
            except Exception:
                pass
        changed |= self._set("channel_volume", channel_volume)
        changed |= self._set("channel_mute", channel_mute)
        changed |= self._set("channel_preset", channel_preset)

        try:
            apps = self._api.sonar.get_routed_apps_by_channel()
            changed |= self._set("channel_apps", apps)
        except Exception:
            pass
        return changed

    def _refresh_hw(self) -> bool:
        if not self._api:
            return False
        changed = False
        try:
            brightness = self._api.base_station.get_oled_brightness()
            if brightness is not None:
                changed |= self._set("oled_brightness", int(brightness))
        except Exception:
            pass
        return changed

    def _set(self, key: str, value: Any) -> bool:
        if self._state.get(key) != value:
            self._state[key] = value
            return True
        return False

    def _load_state(self) -> dict[str, Any]:
        if not self._state_file.exists():
            return dict(DEFAULT_STATE)
        try:
            loaded = json.loads(self._state_file.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                return dict(DEFAULT_STATE)
        except Exception:
            return dict(DEFAULT_STATE)
        merged = dict(DEFAULT_STATE)
        merged.update(loaded)
        return merged

    def _save_state(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            temp = self._state_file.with_suffix(self._state_file.suffix + ".tmp")
            temp.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
            os.replace(temp, self._state_file)
        except Exception:
            # State persistence should not stop live service.
            return
