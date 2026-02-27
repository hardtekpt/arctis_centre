from __future__ import annotations

import json
import queue
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Any

import urllib3

ROOT = Path(__file__).resolve().parents[4]
API_SRC = ROOT / "src" / "APIs" / "arctis_nova_api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep bridge output clean; Sonar local HTTPS calls are expected on localhost.
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

from arctis_nova_api import (  # type: ignore
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
from arctis_nova_api.errors import UnsupportedFeatureError  # type: ignore

CHANNELS: tuple[str, ...] = ("master", "game", "chatRender", "media", "aux", "chatCapture")

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


def extract_chat_mix_balance(payload: Any) -> float | None:
    if isinstance(payload, (int, float)):
        return float(payload)
    if not isinstance(payload, dict):
        return None
    for key in ("balance", "chatMix", "value"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def emit(event_type: str, payload: Any) -> None:
    line = json.dumps({"type": event_type, "payload": payload})
    print(line, flush=True)


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


class BridgeService:
    def __init__(self) -> None:
        self._api: ArctisNovaProApi | None = None
        self._state: dict[str, Any] = dict(DEFAULT_STATE)
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop = threading.Event()
        self._presets_cache: dict[str, list[tuple[str, str]]] = {}

    def enqueue(self, cmd: dict[str, Any]) -> None:
        self._queue.put(cmd)

    def run(self) -> None:
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
                emit("state", dict(self._state))
            time.sleep(0.02)

    def stop(self) -> None:
        self._stop.set()
        if self._api:
            try:
                self._api.base_station.close()
            except Exception:
                pass

    def _load_presets_once(self) -> None:
        if not self._api:
            return
        cache: dict[str, list[tuple[str, str]]] = {}
        for channel, preset_channel in self._preset_map().items():
            try:
                presets = self._api.sonar.list_favorite_presets(preset_channel)
                cache[channel] = [(preset.preset_id, preset.name) for preset in presets]
            except Exception:
                cache[channel] = []
        self._presets_cache = cache
        emit("presets", cache)

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
                emit("status", str(exc))
            except Exception as exc:
                emit("error", str(exc))

    def _handle_command(self, cmd: dict[str, Any]) -> None:
        assert self._api is not None
        name = str(cmd.get("name", ""))
        payload = cmd.get("payload", {}) or {}
        channel_map = self._channel_map()
        preset_map = self._preset_map()

        if name == "set_channel_volume":
            channel = channel_map[str(payload["channel"])]
            value = max(0, min(100, int(payload["value"])))
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
            suffix = " (partial mode sync)" if errors else ""
            emit("status", f"{channel.value} volume {applied}%{suffix}")
            self._refresh_sonar()
            emit("state", dict(self._state))
            return

        if name == "set_channel_mute":
            channel = channel_map[str(payload["channel"])]
            muted = bool(payload["value"])
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
            suffix = " (partial mode sync)" if errors else ""
            emit("status", f"{channel.value} {'muted' if muted else 'unmuted'}{suffix}")
            self._refresh_sonar()
            emit("state", dict(self._state))
            return

        if name == "set_preset":
            channel = str(payload["channel"])
            preset_id = str(payload["preset_id"])
            selected_name: str | None = None
            for pid, pname in self._presets_cache.get(channel, []):
                if pid == preset_id:
                    selected_name = pname
                    break
            if selected_name:
                self._api.sonar.select_preset_for_channel(preset_map[channel], selected_name)
            else:
                self._api.sonar.select_preset(preset_id)
            self._refresh_sonar()
            emit("status", f"{channel} preset set")
            emit("state", dict(self._state))

    def _refresh_all(self, force_emit: bool = False) -> None:
        changed = self._refresh_events()
        changed |= self._refresh_sonar()
        changed |= self._refresh_hw()
        if changed or force_emit:
            self._state["updated_at"] = time.strftime("%H:%M:%S")
            emit("state", dict(self._state))

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
        channel_map = self._channel_map()
        preset_map = self._preset_map()
        for channel in CHANNELS:
            try:
                channel_volume[channel] = int(round(self._api.sonar.get_channel_volume(channel_map[channel]) * 100))
            except Exception:
                pass
            try:
                channel_mute[channel] = bool(self._api.sonar.get_channel_mute(channel_map[channel]))
            except Exception:
                pass
            try:
                selected = self._api.sonar.get_selected_preset(preset_map[channel])
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
        try:
            chat_mix_payload = self._api.sonar.get_chat_mix()
            chat_mix = extract_chat_mix_balance(chat_mix_payload)
            if chat_mix is not None:
                chat_mix = max(-1.0, min(1.0, float(chat_mix)))
                changed |= self._set("chat_mix_balance", int(round((chat_mix + 1.0) * 50)))
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
        try:
            volume_pct = self._api.base_station.get_headset_volume_percentage()
            if volume_pct is not None:
                changed |= self._set("headset_volume_percent", int(round(volume_pct)))
        except Exception:
            pass
        try:
            anc = self._api.base_station.get_anc_status()
            if anc is not None:
                changed |= self._set("anc_mode", anc.mode.value)
        except Exception:
            pass
        try:
            mic = self._api.base_station.get_mic_status()
            if mic is not None:
                changed |= self._set("mic_mute", not mic.enabled)
        except Exception:
            pass
        try:
            sidetone = self._api.base_station.get_sidetone_status()
            if sidetone is not None:
                changed |= self._set("sidetone_level", sidetone.level)
        except Exception:
            pass
        try:
            battery = self._api.base_station.get_battery_status()
            if battery is not None:
                changed |= self._set("headset_battery_percent", int(round(battery.headset_percent)))
                changed |= self._set("base_battery_percent", int(round(battery.charging_percent)))
        except Exception:
            pass
        return changed

    def _set(self, key: str, value: Any) -> bool:
        if self._state.get(key) != value:
            self._state[key] = value
            return True
        return False

    @staticmethod
    def _channel_map() -> dict[str, Any]:
        from arctis_nova_api import SonarChannel  # type: ignore

        return {
            "master": SonarChannel.MASTER,
            "game": SonarChannel.GAME,
            "chatRender": SonarChannel.CHAT_RENDER,
            "media": SonarChannel.MEDIA,
            "aux": SonarChannel.AUX,
            "chatCapture": SonarChannel.CHAT_CAPTURE,
        }

    @staticmethod
    def _preset_map() -> dict[str, Any]:
        from arctis_nova_api import PresetChannel  # type: ignore

        return {
            "master": PresetChannel.MASTER,
            "game": PresetChannel.GAMING,
            "chatRender": PresetChannel.CHAT,
            "media": PresetChannel.MEDIA,
            "aux": PresetChannel.AUX,
            "chatCapture": PresetChannel.MIC,
        }


def input_loop(service: BridgeService) -> None:
    while True:
        line = sys.stdin.readline()
        if line == "":
            service.stop()
            return
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
            if isinstance(cmd, dict):
                service.enqueue(cmd)
        except Exception as exc:
            emit("error", str(exc))


def main() -> int:
    service = BridgeService()
    t = threading.Thread(target=input_loop, args=(service,), daemon=True)
    t.start()
    try:
        service.run()
    except Exception as exc:
        emit("error", str(exc))
        return 1
    finally:
        service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
