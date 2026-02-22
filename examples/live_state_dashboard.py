from __future__ import annotations

import argparse
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from arctis_nova_api import (
    AncStatus,
    ArctisNovaProApi,
    BatteryStatus,
    HeadsetConnectionStatus,
    MicStatus,
    OledBrightnessStatus,
    PresetChannel,
    SidetoneStatus,
    SonarChannel,
    VolumeKnobEvent,
)
from arctis_nova_api.errors import UnsupportedFeatureError


DEFAULT_STATE: dict[str, Any] = {
    "headset_battery": None,
    "base_station_battery": None,
    "headset_battery_percent": None,
    "base_station_battery_percent": None,
    "anc_mode": None,
    "mic_mute": None,
    "sidetone_level": None,
    "headset_volume": None,
    "headset_volume_percent": None,
    "headset_connected": None,
    "headset_wireless": None,
    "headset_bluetooth": None,
    "chat_mix_balance": None,
    "sonar_channel_volumes": {},
    "sonar_channel_mutes": {},
    "sonar_selected_presets": {},
    "sonar_routed_apps": {},
    "routed_app_movements": [],
    "routed_app_moves_last_utc": None,
    "active_usb_input": None,
    "oled_brightness": None,
    "sonar_last_refresh_utc": None,
    "last_update_utc": None,
}

FAST_ROUTED_APPS_REFRESH_SECONDS = 0.25
SONAR_REFRESH_SECONDS = 2.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live terminal dashboard for Arctis Nova Pro event state.")
    parser.add_argument(
        "--state-file",
        default="tools/current_headset_state.json",
        help="Path to JSON file used to persist last known state",
    )
    parser.add_argument("--interval", type=float, default=0.2, help="Refresh interval in seconds")
    return parser.parse_args()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return dict(DEFAULT_STATE)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return dict(DEFAULT_STATE)
    except Exception:
        return dict(DEFAULT_STATE)
    merged = dict(DEFAULT_STATE)
    merged.update(loaded)
    return merged


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(temp, path)


def mark_updated(state: dict[str, Any]) -> None:
    state["last_update_utc"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"


def apply_event(state: dict[str, Any], event: object) -> bool:
    changed = False
    if isinstance(event, BatteryStatus):
        changed |= _set(state, "headset_battery", event.headset)
        changed |= _set(state, "base_station_battery", event.charging)
        changed |= _set(state, "headset_battery_percent", round(event.headset_percent, 1))
        changed |= _set(state, "base_station_battery_percent", round(event.charging_percent, 1))
    elif isinstance(event, AncStatus):
        changed |= _set(state, "anc_mode", event.mode.value)
    elif isinstance(event, MicStatus):
        changed |= _set(state, "mic_mute", not event.enabled)
    elif isinstance(event, SidetoneStatus):
        changed |= _set(state, "sidetone_level", event.level)
    elif isinstance(event, VolumeKnobEvent):
        changed |= _set(state, "headset_volume", event.volume)
        changed |= _set(state, "headset_volume_percent", round(event.volume_percent, 1))
    elif isinstance(event, OledBrightnessStatus):
        changed |= _set(state, "oled_brightness", event.level)
    elif isinstance(event, HeadsetConnectionStatus):
        changed |= _set(state, "headset_connected", event.wireless)
        changed |= _set(state, "headset_wireless", event.wireless)
        changed |= _set(state, "headset_bluetooth", event.bluetooth)
    if changed:
        mark_updated(state)
    return changed


def _set(state: dict[str, Any], key: str, value: Any) -> bool:
    if state.get(key) != value:
        state[key] = value
        return True
    return False


def show_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else "N/A"
    if isinstance(value, (list, dict, tuple, set)) and len(value) == 0:
        return "N/A"
    return str(value)


def show_bool(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "N/A"


def show_volume(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if 0 <= v <= 1:
        return f"{v:.3f}"
    if 1 < v <= 100:
        return f"{v:.1f}%"
    return f"{v:.3f}"


def show_channel_volume_percent(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if 0 <= v <= 1:
        return f"{int(round(v * 100))}%"
    if 1 < v <= 100:
        return f"{int(round(v))}%"
    return "N/A"


def show_battery(raw_value: Any, pct_value: Any) -> str:
    _ = raw_value
    if pct_value is None:
        return "N/A"
    try:
        pct = float(pct_value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{int(round(pct))}%"


def show_headset_volume(raw_value: Any, pct_value: Any) -> str:
    _ = raw_value
    if pct_value is None:
        return "N/A"
    try:
        pct = float(pct_value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{int(round(pct))}%"


def show_sidetone(level_value: Any) -> str:
    if level_value is None:
        return "N/A"
    try:
        level = int(level_value)
    except (TypeError, ValueError):
        return "N/A"
    labels = {0: "off", 1: "low", 2: "med", 3: "high"}
    label = labels.get(level)
    if label is None:
        return str(level)
    return f"{label} ({level})"


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


def show_chat_mix(balance_value: Any) -> str:
    if balance_value is None:
        return "N/A"
    try:
        b = float(balance_value)
    except (TypeError, ValueError):
        return "N/A"
    b = max(-1.0, min(1.0, b))
    if abs(b) < 0.01:
        return "Center (0%)"
    pct = int(round(abs(b) * 100))
    side = "Chat" if b > 0 else "Game"
    return f"{side} +{pct}%"


def show_app_list(value: Any) -> str:
    if not isinstance(value, list):
        return "N/A"
    names = [str(v).strip() for v in value if str(v).strip()]
    if not names:
        return "-"
    return ", ".join(names)


def show_mute(value: Any) -> str:
    if value is True:
        return "Muted"
    if value is False:
        return "Live"
    return "N/A"


def compute_app_movements(old_routed: dict[str, list[str]], new_routed: dict[str, list[str]]) -> list[str]:
    channels = ("master", "game", "chatRender", "media", "aux", "chatCapture")
    old_map: dict[str, set[str]] = {}
    new_map: dict[str, set[str]] = {}

    for channel in channels:
        for app in old_routed.get(channel, []):
            old_map.setdefault(app, set()).add(channel)
        for app in new_routed.get(channel, []):
            new_map.setdefault(app, set()).add(channel)

    moves: list[str] = []
    for app in sorted(set(old_map.keys()) | set(new_map.keys())):
        old_channels = old_map.get(app, set())
        new_channels = new_map.get(app, set())
        if old_channels != new_channels:
            old_label = ",".join(sorted(old_channels)) if old_channels else "-"
            new_label = ",".join(sorted(new_channels)) if new_channels else "-"
            moves.append(f"{app}: {old_label} -> {new_label}")
    return moves


def hline(width: int = 74) -> str:
    return "-" * width


def row(label: str, value: str, width: int = 74) -> str:
    label_col = f"{label}:"
    return f"{label_col:<24} {value:<{max(10, width - 26)}}"


def render(state: dict[str, Any], source: str, state_file: Path) -> None:
    print("\x1b[2J\x1b[H", end="")
    print("Arctis Nova Pro Dashboard | "
          f"source={show_value(source)} | state={state_file}")
    print(hline())

    print(
        f"Battery H/B: {show_battery(state.get('headset_battery'), state.get('headset_battery_percent'))} / "
        f"{show_battery(state.get('base_station_battery'), state.get('base_station_battery_percent'))}"
    )
    print(
        f"ANC: {show_value(state.get('anc_mode'))} | "
        f"Mic mute: {show_bool(state.get('mic_mute'))} | "
        f"Sidetone: {show_sidetone(state.get('sidetone_level'))} | "
        f"Headset vol: {show_headset_volume(state.get('headset_volume'), state.get('headset_volume_percent'))} | "
        f"Chat mix: {show_chat_mix(state.get('chat_mix_balance'))}"
    )
    print(
        f"USB input: {show_value(state.get('active_usb_input'))} | "
        f"OLED brightness: {show_value(state.get('oled_brightness'))}"
    )
    print(
        f"Conn connected={show_bool(state.get('headset_connected'))}, "
        f"wireless={show_bool(state.get('headset_wireless'))}, "
        f"bluetooth={show_bool(state.get('headset_bluetooth'))}"
    )

    print(hline())
    print(f"{'Channel':<12} {'Volume %':<9} {'Mute':<8} {'Preset':<16} Routed apps")
    print(hline())
    volumes: dict[str, Any] = state.get("sonar_channel_volumes", {})
    mutes: dict[str, Any] = state.get("sonar_channel_mutes", {})
    presets: dict[str, Any] = state.get("sonar_selected_presets", {})
    routed_apps: dict[str, Any] = state.get("sonar_routed_apps", {})
    channels = ("master", "game", "chatRender", "media", "aux", "chatCapture")
    for channel in channels:
        vol = show_channel_volume_percent(volumes.get(channel))
        mute = show_mute(mutes.get(channel))
        preset = show_value(presets.get(channel))
        apps = show_app_list(routed_apps.get(channel, []))
        print(f"{channel:<12} {vol:<9} {mute:<8} {preset:<16} {apps}")

    print(hline())
    print(
        f"Updates UTC: state={show_value(state.get('last_update_utc'))} | "
        f"sonar={show_value(state.get('sonar_last_refresh_utc'))}"
    )
    print("Ctrl+C exit")

def main() -> None:
    args = parse_args()
    state_path = Path(args.state_file)
    state = load_state(state_path)

    api = ArctisNovaProApi()
    api.base_station.connect()
    lock = threading.Lock()
    stop_event = threading.Event()
    source = {"value": "state file fallback"}
    dirty = {"value": True}

    def background_refresh() -> None:
        try:
            last_sonar_refresh = 0.0
            last_routed_apps_refresh = 0.0
            while not stop_event.is_set():
                events = api.base_station.get_pending_events()
                changed = False
                with lock:
                    for event in events:
                        changed |= apply_event(state, event)

                    if changed:
                        save_state(state_path, state)
                        source["value"] = "live events"
                        dirty["value"] = True
                    elif state_path.exists() and source["value"] != "state file fallback":
                        source["value"] = "state file fallback"
                        dirty["value"] = True

                now = time.monotonic()
                if now - last_routed_apps_refresh >= FAST_ROUTED_APPS_REFRESH_SECONDS:
                    routed_changed = refresh_routed_apps_state(api, state, lock)
                    if routed_changed:
                        with lock:
                            save_state(state_path, state)
                            dirty["value"] = True
                    last_routed_apps_refresh = now

                if now - last_sonar_refresh >= SONAR_REFRESH_SECONDS:
                    sonar_changed = refresh_sonar_state(api, state, lock)
                    hw_changed = refresh_hardware_state(api, state, lock)
                    if sonar_changed or hw_changed:
                        with lock:
                            save_state(state_path, state)
                            dirty["value"] = True
                    last_sonar_refresh = now
                stop_event.wait(max(0.05, args.interval))
        finally:
            with lock:
                save_state(state_path, state)

    worker = threading.Thread(target=background_refresh, name="dashboard-refresh", daemon=True)
    worker.start()
    try:
        while True:
            should_render = False
            with lock:
                if dirty["value"]:
                    snapshot = dict(state)
                    snapshot_source = source["value"]
                    dirty["value"] = False
                    should_render = True
            if should_render:
                render(snapshot, source=snapshot_source, state_file=state_path)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        worker.join(timeout=1.0)
        with lock:
            save_state(state_path, state)
        api.base_station.close()


def refresh_sonar_state(api: ArctisNovaProApi, state: dict[str, Any], lock: threading.Lock) -> bool:
    try:
        channels = ("master", "game", "chatRender", "media", "aux", "chatCapture")
        with lock:
            old_volumes = dict(state.get("sonar_channel_volumes", {}))
            old_mutes = dict(state.get("sonar_channel_mutes", {}))
            old_presets = dict(state.get("sonar_selected_presets", {}))
            old_chat_mix = state.get("chat_mix_balance")

        new_volumes: dict[str, Any] = {}
        channel_map = {
            "master": SonarChannel.MASTER,
            "game": SonarChannel.GAME,
            "chatRender": SonarChannel.CHAT_RENDER,
            "media": SonarChannel.MEDIA,
            "aux": SonarChannel.AUX,
            "chatCapture": SonarChannel.CHAT_CAPTURE,
        }
        for channel in channels:
            try:
                new_volumes[channel] = api.sonar.get_channel_volume(channel_map[channel])
            except Exception:
                new_volumes[channel] = old_volumes.get(channel)
        new_mutes: dict[str, Any] = {}
        for channel in channels:
            try:
                new_mutes[channel] = api.sonar.get_channel_mute(channel_map[channel])
            except Exception:
                new_mutes[channel] = old_mutes.get(channel)

        preset_map = {
            "master": PresetChannel.MASTER,
            "game": PresetChannel.GAMING,
            "chatRender": PresetChannel.CHAT,
            "media": PresetChannel.MEDIA,
            "aux": PresetChannel.AUX,
            "chatCapture": PresetChannel.MIC,
        }
        new_presets: dict[str, Any] = {}
        for channel, preset_channel in preset_map.items():
            try:
                selected = api.sonar.get_selected_preset(preset_channel)
                new_presets[channel] = selected.name if selected else None
            except Exception:
                new_presets[channel] = old_presets.get(channel)

        try:
            chat_mix_payload = api.sonar.get_chat_mix()
            new_chat_mix = extract_chat_mix_balance(chat_mix_payload)
        except Exception:
            new_chat_mix = old_chat_mix

        changed = (
            new_volumes != old_volumes
            or new_mutes != old_mutes
            or new_presets != old_presets
            or new_chat_mix != old_chat_mix
        )
        if changed:
            with lock:
                state["sonar_channel_volumes"] = new_volumes
                state["sonar_channel_mutes"] = new_mutes
                state["sonar_selected_presets"] = new_presets
                state["chat_mix_balance"] = new_chat_mix
                state["sonar_last_refresh_utc"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
                mark_updated(state)
        return changed
    except Exception:
        return False


def refresh_routed_apps_state(api: ArctisNovaProApi, state: dict[str, Any], lock: threading.Lock) -> bool:
    try:
        with lock:
            old_routed_apps = dict(state.get("sonar_routed_apps", {}))
            old_movements = list(state.get("routed_app_movements", []))
            old_moves_utc = state.get("routed_app_moves_last_utc")

        try:
            new_routed_apps = api.sonar.get_routed_apps_by_channel()
        except Exception:
            new_routed_apps = old_routed_apps

        movements = compute_app_movements(old_routed_apps, new_routed_apps)
        new_movements = movements[:20] if movements else old_movements
        new_moves_utc = (
            datetime.utcnow().isoformat(timespec="seconds") + "Z"
            if movements
            else old_moves_utc
        )

        changed = (
            new_routed_apps != old_routed_apps
            or new_movements != old_movements
            or new_moves_utc != old_moves_utc
        )
        if changed:
            with lock:
                state["sonar_routed_apps"] = new_routed_apps
                state["routed_app_movements"] = new_movements
                state["routed_app_moves_last_utc"] = new_moves_utc
                mark_updated(state)
        return changed
    except Exception:
        return False


def refresh_hardware_state(api: ArctisNovaProApi, state: dict[str, Any], lock: threading.Lock) -> bool:
    with lock:
        old_usb = state.get("active_usb_input")
        old_oled = state.get("oled_brightness")

    try:
        usb = api.base_station.get_active_usb_input()
        if usb is None:
            try:
                usb = api.base_station.request_active_usb_input(timeout_seconds=0.1)
            except UnsupportedFeatureError:
                usb = None
            except Exception:
                usb = None
        new_usb = usb.value if usb else old_usb
    except Exception:
        new_usb = old_usb

    try:
        brightness = api.base_station.get_oled_brightness()
        if brightness is None:
            try:
                brightness = api.base_station.request_oled_brightness(timeout_seconds=0.1)
            except UnsupportedFeatureError:
                brightness = None
            except Exception:
                brightness = None
        new_oled = brightness if brightness is not None else old_oled
    except Exception:
        new_oled = old_oled

    changed = new_usb != old_usb or new_oled != old_oled
    if changed:
        with lock:
            state["active_usb_input"] = new_usb
            state["oled_brightness"] = new_oled
            mark_updated(state)
    return changed


if __name__ == "__main__":
    main()


