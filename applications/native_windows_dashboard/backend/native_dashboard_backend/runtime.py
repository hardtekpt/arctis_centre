from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from arctis_nova_api import (
    AncMode,
    AncStatus,
    ArctisNovaProApi,
    BatteryStatus,
    ExperimentalCommandProfile,
    HeadsetConnectionStatus,
    MicStatus,
    OledBrightnessStatus,
    PresetChannel,
    SidetoneStatus,
    SonarChannel,
    StreamerSlider,
    VolumeKnobEvent,
)

CHANNELS: tuple[str, ...] = ("master", "game", "chatRender", "media", "aux", "chatCapture")
CHANNEL_MAP: dict[str, SonarChannel] = {
    "master": SonarChannel.MASTER,
    "game": SonarChannel.GAME,
    "chatRender": SonarChannel.CHAT_RENDER,
    "media": SonarChannel.MEDIA,
    "aux": SonarChannel.AUX,
    "chatCapture": SonarChannel.CHAT_CAPTURE,
}
PRESET_CHANNEL_MAP: dict[str, PresetChannel] = {
    "master": PresetChannel.MASTER,
    "game": PresetChannel.GAMING,
    "chatRender": PresetChannel.CHAT,
    "media": PresetChannel.MEDIA,
    "aux": PresetChannel.AUX,
    "chatCapture": PresetChannel.MIC,
}
DEFAULT_STATE_FILE = Path("tools/native_windows_dashboard_state.json")
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
    "channel_preset_name": {},
    "channel_apps": {},
    "updated_at": None,
    "status": "initializing",
    "last_error": "",
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


class DashboardRuntime:
    def __init__(self, state_file: Path | None = None) -> None:
        self._state_file = state_file or DEFAULT_STATE_FILE
        self._state = self._load_state()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._api: ArctisNovaProApi | None = None
        self._presets_cache: dict[str, list[dict[str, str]]] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="native-dashboard-runtime", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        with self._lock:
            self._save_state()

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def get_presets(self) -> dict[str, list[dict[str, str]]]:
        with self._lock:
            return dict(self._presets_cache)

    def set_channel_volume(self, channel: str, value: int) -> None:
        api = self._require_api()
        sonar_channel = CHANNEL_MAP[channel]
        target = max(0, min(100, value)) / 100.0
        for kwargs in (
            {"streamer": False},
            {"streamer": True, "streamer_slider": StreamerSlider.STREAMING},
            {"streamer": True, "streamer_slider": StreamerSlider.MONITORING},
        ):
            try:
                api.sonar.set_channel_volume(sonar_channel, target, **kwargs)
            except Exception:
                continue

    def set_channel_mute(self, channel: str, muted: bool) -> None:
        api = self._require_api()
        sonar_channel = CHANNEL_MAP[channel]
        for kwargs in (
            {"streamer": False},
            {"streamer": True, "streamer_slider": StreamerSlider.STREAMING},
            {"streamer": True, "streamer_slider": StreamerSlider.MONITORING},
        ):
            try:
                api.sonar.set_channel_mute(sonar_channel, muted, **kwargs)
            except Exception:
                continue

    def set_channel_preset(self, channel: str, preset_id: str) -> None:
        api = self._require_api()
        channel_presets = self._presets_cache.get(channel, [])
        selected_name: str | None = None
        for item in channel_presets:
            if item["id"] == preset_id:
                selected_name = item["name"]
                break
        if selected_name:
            api.sonar.select_preset_for_channel(PRESET_CHANNEL_MAP[channel], selected_name)
        else:
            api.sonar.select_preset(preset_id)

    def _require_api(self) -> ArctisNovaProApi:
        if self._api is None:
            raise RuntimeError("Backend service not initialized yet.")
        return self._api

    def _run(self) -> None:
        try:
            self._api = ArctisNovaProApi(command_profile=build_command_profile())
            self._api.base_station.connect()
            self._load_presets()
            self._set_status("running", "")
        except Exception as exc:
            self._set_status("error", str(exc))
            return

        last_sonar = 0.0
        last_hw = 0.0
        last_presets = 0.0
        while not self._stop.is_set():
            changed = self._refresh_events()
            now = time.monotonic()
            if now - last_sonar >= 0.45:
                changed |= self._refresh_sonar()
                last_sonar = now
            if now - last_hw >= 0.25:
                changed |= self._refresh_hw()
                last_hw = now
            if now - last_presets >= 4.0:
                changed |= self._refresh_presets_cache()
                last_presets = now
            if changed:
                with self._lock:
                    self._state["updated_at"] = time.strftime("%H:%M:%S")
                    self._save_state()
            time.sleep(0.04)

        if self._api is not None:
            try:
                self._api.base_station.close()
            except Exception:
                pass

    def _refresh_events(self) -> bool:
        api = self._require_api()
        changed = False
        for event in api.base_station.get_pending_events():
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
        api = self._require_api()
        changed = False
        channel_volume = dict(self._state.get("channel_volume", {}))
        channel_mute = dict(self._state.get("channel_mute", {}))
        channel_preset = dict(self._state.get("channel_preset", {}))
        channel_preset_name = dict(self._state.get("channel_preset_name", {}))
        for channel in CHANNELS:
            try:
                channel_volume[channel] = int(round(api.sonar.get_channel_volume(CHANNEL_MAP[channel]) * 100))
            except Exception:
                pass
            try:
                channel_mute[channel] = bool(api.sonar.get_channel_mute(CHANNEL_MAP[channel]))
            except Exception:
                pass
            try:
                selected = api.sonar.get_selected_preset(PRESET_CHANNEL_MAP[channel])
                channel_preset[channel] = selected.preset_id if selected else None
                channel_preset_name[channel] = selected.name if selected else None
            except Exception:
                pass
        changed |= self._set("channel_volume", channel_volume)
        changed |= self._set("channel_mute", channel_mute)
        changed |= self._set("channel_preset", channel_preset)
        changed |= self._set("channel_preset_name", channel_preset_name)
        try:
            changed |= self._set("channel_apps", api.sonar.get_routed_apps_by_channel())
        except Exception:
            pass
        try:
            payload = api.sonar.get_chat_mix()
            balance = float(payload.get("balance", 0.0))
            changed |= self._set("chat_mix_balance", int(round((balance + 1.0) * 50)))
        except Exception:
            pass
        return changed

    def _refresh_hw(self) -> bool:
        api = self._require_api()
        changed = False
        try:
            brightness = api.base_station.get_oled_brightness()
            if brightness is not None:
                changed |= self._set("oled_brightness", int(brightness))
        except Exception:
            pass
        try:
            # Keep headset volume visible even when no fresh events arrive.
            volume_pct = api.base_station.get_headset_volume_percentage()
            if volume_pct is not None:
                changed |= self._set("headset_volume_percent", int(round(volume_pct)))
        except Exception:
            pass
        try:
            anc = api.base_station.get_anc_status()
            if anc is not None:
                changed |= self._set("anc_mode", anc.mode.value)
        except Exception:
            pass
        try:
            mic = api.base_station.get_mic_status()
            if mic is not None:
                changed |= self._set("mic_mute", not mic.enabled)
        except Exception:
            pass
        try:
            sidetone = api.base_station.get_sidetone_status()
            if sidetone is not None:
                changed |= self._set("sidetone_level", sidetone.level)
        except Exception:
            pass
        try:
            battery = api.base_station.get_battery_status()
            if battery is not None:
                changed |= self._set("headset_battery_percent", int(round(battery.headset_percent)))
                changed |= self._set("base_battery_percent", int(round(battery.charging_percent)))
        except Exception:
            pass
        return changed

    def _load_presets(self) -> None:
        self._refresh_presets_cache()

    def _refresh_presets_cache(self) -> bool:
        api = self._require_api()
        cache: dict[str, list[dict[str, str]]] = {}
        for channel, preset_channel in PRESET_CHANNEL_MAP.items():
            try:
                favorites = api.sonar.list_favorite_presets(preset_channel)
                presets = favorites or api.sonar.list_presets(preset_channel)
                cache[channel] = [{"id": preset.preset_id, "name": preset.name} for preset in presets]
            except Exception:
                cache[channel] = []

        changed = False
        with self._lock:
            if self._presets_cache != cache:
                self._presets_cache = cache
                changed = True
        return changed

    def _set_status(self, status: str, error: str) -> None:
        with self._lock:
            self._state["status"] = status
            self._state["last_error"] = error
            self._save_state()

    def _set(self, key: str, value: Any) -> bool:
        with self._lock:
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
            return
