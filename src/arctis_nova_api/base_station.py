from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Protocol

from .errors import DiscoveryError, InvalidArgumentError, UnsupportedFeatureError
from .models import AncMode, AncStatus, BatteryStatus, DeviceEvent, HeadsetConnectionStatus, MicStatus, SidetoneStatus, UsbInput, VolumeKnobEvent

STEELSERIES_VENDOR_ID = 0x1038
SUPPORTED_PRODUCT_IDS = (0x12CB, 0x12CD, 0x12E0, 0x12E5, 0x225D)
INTERFACE_NUMBER = 4


@dataclass(frozen=True)
class ExperimentalCommandProfile:
    """Firmware-dependent command map for unsupported advanced controls."""

    anc_set_commands: dict[AncMode, list[int]] | None = None
    anc_status_command: list[int] | None = None
    anc_event_command_id: int | None = 0xBD
    anc_value_index: int = 2
    anc_value_map: dict[int, AncMode] | None = field(
        default_factory=lambda: {0: AncMode.OFF, 1: AncMode.TRANSPARENCY, 2: AncMode.ANC}
    )
    usb_input_commands: dict[UsbInput, list[int]] | None = None
    battery_query_command: list[int] | None = None
    sidetone_get_command: list[int] | None = None
    sidetone_set_commands: dict[int, list[int]] | None = None
    sidetone_event_command_id: int | None = 0x39
    sidetone_value_index: int = 2
    sidetone_label_map: dict[str, int] | None = field(
        default_factory=lambda: {"off": 0, "low": 1, "med": 2, "high": 3}
    )
    mic_event_command_id: int | None = 0xBB
    mic_value_index: int = 2
    mic_on_values: set[int] | None = field(default_factory=lambda: {1})


class HidDeviceLike(Protocol):
    def write(self, data: list[int]) -> int:
        ...

    def send_feature_report(self, data: list[int]) -> int:
        ...

    def read(self, length: int, timeout_ms: int = 0) -> list[int]:
        ...

    def close(self) -> None:
        ...


class HidBackendLike(Protocol):
    def enumerate(self, vendor_id: int, product_id: int) -> list[dict[str, Any]]:
        ...

    def device(self) -> Any:
        ...


class BaseStationClient:
    """Direct USB control for Arctis Nova Pro base station."""

    def __init__(
        self,
        hid_backend: HidBackendLike | None = None,
        command_profile: ExperimentalCommandProfile | None = None,
    ) -> None:
        self._hid_backend = hid_backend or _load_hid_backend()
        self._command_profile = command_profile or ExperimentalCommandProfile()
        self._oled_device: HidDeviceLike | None = None
        self._info_device: HidDeviceLike | None = None
        self._event_devices: list[HidDeviceLike] = []
        self._last_battery_status: BatteryStatus | None = None
        self._last_sidetone_status: SidetoneStatus | None = None
        self._last_anc_status: AncStatus | None = None
        self._last_mic_status: MicStatus | None = None

    def connect(self) -> None:
        interfaces: list[dict[str, Any]] = []
        for pid in SUPPORTED_PRODUCT_IDS:
            interfaces.extend(self._hid_backend.enumerate(STEELSERIES_VENDOR_ID, pid))

        candidates = [d for d in interfaces if int(d.get("interface_number", -1)) == INTERFACE_NUMBER]
        if len(candidates) < 1:
            raise DiscoveryError("No supported SteelSeries base station found on interface 4")

        path_a = candidates[0]["path"]
        path_b = candidates[1]["path"] if len(candidates) > 1 else candidates[0]["path"]
        self._oled_device = self._open(path_a)
        self._info_device = self._open(path_b)
        self._event_devices = [self._info_device]
        if self._oled_device is not self._info_device:
            self._event_devices.append(self._oled_device)

    def close(self) -> None:
        if self._oled_device:
            self._oled_device.close()
        if self._info_device:
            self._info_device.close()
        self._oled_device = None
        self._info_device = None
        self._event_devices = []

    def set_brightness(self, value: int) -> None:
        if value < 1 or value > 10:
            raise InvalidArgumentError("Brightness must be between 1 and 10")
        report = [0] * 64
        report[0] = 0x06
        report[1] = 0x85
        report[2] = value
        self._require_oled().write(report)

    def return_to_steelseries_ui(self) -> None:
        report = [0] * 64
        report[0] = 0x06
        report[1] = 0x95
        self._require_oled().write(report)

    def draw_oled_bitmap_chunk(self, payload: bytes, dst_x: int, dst_y: int, width: int, height: int) -> None:
        """
        Draw one already packed OLED bitmap chunk.

        The data format matches the ggoled protocol for report id 0x06, command 0x93.
        """
        if len(payload) > 1018:
            raise InvalidArgumentError("Bitmap payload too large for a single report")
        report = [0] * 1024
        report[0] = 0x06
        report[1] = 0x93
        report[2] = dst_x
        report[3] = dst_y
        report[4] = width
        report[5] = height
        report[6 : 6 + len(payload)] = payload
        self._require_oled().send_feature_report(report)

    def get_pending_events(self) -> list[DeviceEvent]:
        events: list[DeviceEvent] = []
        while True:
            polled = self._poll_event_devices_once(timeout_ms=1)
            if not polled:
                break
            for parsed in polled:
                self._update_cached_state(parsed)
                events.append(parsed)
        return events

    def get_battery_status(self, refresh_timeout_seconds: float = 0.0) -> BatteryStatus | None:
        """
        Return the latest battery status.

        If `refresh_timeout_seconds` > 0, poll device events up to that duration and
        return as soon as a fresh battery event is observed.
        """
        if refresh_timeout_seconds <= 0:
            return self._last_battery_status

        deadline = time.monotonic() + refresh_timeout_seconds
        while time.monotonic() < deadline:
            for parsed in self._poll_event_devices_once(timeout_ms=20):
                self._update_cached_state(parsed)
                if isinstance(parsed, BatteryStatus):
                    return parsed
        return self._last_battery_status

    def request_battery_status(self, timeout_seconds: float = 0.5) -> BatteryStatus | None:
        """
        Actively request battery status when a battery query command is known.
        """
        if not self._command_profile.battery_query_command:
            raise UnsupportedFeatureError(
                "Battery query command is not configured. Provide ExperimentalCommandProfile.battery_query_command."
            )
        self._require_info().write(self._pad_64(self._command_profile.battery_query_command))
        return self.get_battery_status(refresh_timeout_seconds=timeout_seconds)

    def get_headset_battery(self, refresh_timeout_seconds: float = 0.0) -> int | None:
        status = self.get_battery_status(refresh_timeout_seconds=refresh_timeout_seconds)
        return status.headset if status else None

    def get_charging_station_battery(self, refresh_timeout_seconds: float = 0.0) -> int | None:
        status = self.get_battery_status(refresh_timeout_seconds=refresh_timeout_seconds)
        return status.charging if status else None

    def get_sidetone_status(self, refresh_timeout_seconds: float = 0.0) -> SidetoneStatus | None:
        if refresh_timeout_seconds <= 0:
            return self._last_sidetone_status

        deadline = time.monotonic() + refresh_timeout_seconds
        while time.monotonic() < deadline:
            for parsed in self._poll_event_devices_once(timeout_ms=20):
                self._update_cached_state(parsed)
                if isinstance(parsed, SidetoneStatus):
                    return parsed
        return self._last_sidetone_status

    def get_sidetone_label(self) -> str | None:
        if self._last_sidetone_status is None:
            return None
        if not self._command_profile.sidetone_label_map:
            return str(self._last_sidetone_status.level)
        inverse = {v: k for k, v in self._command_profile.sidetone_label_map.items()}
        return inverse.get(self._last_sidetone_status.level, str(self._last_sidetone_status.level))

    def get_anc_status(self, refresh_timeout_seconds: float = 0.0) -> AncStatus | None:
        if refresh_timeout_seconds <= 0:
            return self._last_anc_status

        deadline = time.monotonic() + refresh_timeout_seconds
        while time.monotonic() < deadline:
            for parsed in self._poll_event_devices_once(timeout_ms=20):
                self._update_cached_state(parsed)
                if isinstance(parsed, AncStatus):
                    return parsed
        return self._last_anc_status

    def get_mic_status(self, refresh_timeout_seconds: float = 0.0) -> MicStatus | None:
        if refresh_timeout_seconds <= 0:
            return self._last_mic_status

        deadline = time.monotonic() + refresh_timeout_seconds
        while time.monotonic() < deadline:
            for parsed in self._poll_event_devices_once(timeout_ms=20):
                self._update_cached_state(parsed)
                if isinstance(parsed, MicStatus):
                    return parsed
        return self._last_mic_status

    def request_sidetone_status(self, timeout_seconds: float = 0.5) -> SidetoneStatus | None:
        if not self._command_profile.sidetone_get_command:
            raise UnsupportedFeatureError(
                "Sidetone get command is not configured. Provide ExperimentalCommandProfile.sidetone_get_command."
            )
        self._require_info().write(self._pad_64(self._command_profile.sidetone_get_command))
        return self.get_sidetone_status(refresh_timeout_seconds=timeout_seconds)

    def set_sidetone_level(self, level: int) -> None:
        if level < 0:
            raise InvalidArgumentError("Sidetone level must be >= 0")
        if not self._command_profile.sidetone_set_commands:
            raise UnsupportedFeatureError(
                "Sidetone set commands are not configured. Provide ExperimentalCommandProfile.sidetone_set_commands."
            )
        if level not in self._command_profile.sidetone_set_commands:
            raise UnsupportedFeatureError(f"No sidetone command configured for level {level}.")
        self._require_oled().write(self._pad_64(self._command_profile.sidetone_set_commands[level]))

    def set_anc_mode(self, mode: AncMode) -> None:
        if not self._command_profile.anc_set_commands or mode not in self._command_profile.anc_set_commands:
            raise UnsupportedFeatureError(
                "ANC command profile is not configured. Provide ExperimentalCommandProfile with ANC command bytes."
            )
        self._require_oled().write(self._pad_64(self._command_profile.anc_set_commands[mode]))

    def get_anc_status_raw(self) -> bytes:
        if not self._command_profile.anc_status_command:
            raise UnsupportedFeatureError(
                "ANC status command is not configured. Provide ExperimentalCommandProfile with anc_status_command."
            )
        dev = self._require_info()
        dev.write(self._pad_64(self._command_profile.anc_status_command))
        return bytes(dev.read(64, timeout_ms=100))

    def set_usb_input(self, input_source: UsbInput) -> None:
        if not self._command_profile.usb_input_commands or input_source not in self._command_profile.usb_input_commands:
            raise UnsupportedFeatureError(
                "USB input command profile is not configured. Provide ExperimentalCommandProfile with USB command bytes."
            )
        self._require_oled().write(self._pad_64(self._command_profile.usb_input_commands[input_source]))

    def _open(self, path: Any) -> HidDeviceLike:
        dev = self._hid_backend.device()
        dev.open_path(path)
        return dev

    @staticmethod
    def _parse_event(data: list[int], profile: ExperimentalCommandProfile | None = None) -> DeviceEvent | None:
        if len(data) < 5 or data[0] not in (0x06, 0x07):
            return None
        if data[1] == 0x25:
            return VolumeKnobEvent(volume=max(0, 0x38 - data[2]))
        if data[1] == 0xB5:
            return HeadsetConnectionStatus(wireless=data[4] == 8, bluetooth=data[3] == 1, bluetooth_on=data[2] == 4)
        if data[1] == 0xB7:
            return BatteryStatus(headset=data[2], charging=data[3])
        if profile and profile.sidetone_event_command_id is not None and data[1] == profile.sidetone_event_command_id:
            idx = profile.sidetone_value_index
            if 0 <= idx < len(data):
                return SidetoneStatus(level=int(data[idx]))
        if profile and profile.anc_event_command_id is not None and data[1] == profile.anc_event_command_id:
            idx = profile.anc_value_index
            if 0 <= idx < len(data):
                value = int(data[idx])
                value_map = profile.anc_value_map or {0: AncMode.OFF, 1: AncMode.TRANSPARENCY, 2: AncMode.ANC}
                if value in value_map:
                    return AncStatus(mode=value_map[value])
        if profile and profile.mic_event_command_id is not None and data[1] == profile.mic_event_command_id:
            idx = profile.mic_value_index
            if 0 <= idx < len(data):
                value = int(data[idx])
                on_values = profile.mic_on_values or {1}
                return MicStatus(enabled=value in on_values)
        return None

    def _update_cached_state(self, event: DeviceEvent) -> None:
        if isinstance(event, BatteryStatus):
            self._last_battery_status = event
        if isinstance(event, SidetoneStatus):
            self._last_sidetone_status = event
        if isinstance(event, AncStatus):
            self._last_anc_status = event
        if isinstance(event, MicStatus):
            self._last_mic_status = event

    def _require_oled(self) -> HidDeviceLike:
        if self._oled_device is None:
            raise DiscoveryError("Device not connected. Call connect() first.")
        return self._oled_device

    def _require_info(self) -> HidDeviceLike:
        if self._info_device is None:
            raise DiscoveryError("Device not connected. Call connect() first.")
        return self._info_device

    def _poll_event_devices_once(self, timeout_ms: int) -> list[DeviceEvent]:
        if not self._event_devices:
            self._require_info()
            self._event_devices = [self._info_device] if self._info_device else []
        events: list[DeviceEvent] = []
        for dev in self._event_devices:
            data = dev.read(64, timeout_ms=timeout_ms)
            if not data:
                continue
            parsed = self._parse_event(data, self._command_profile)
            if parsed:
                events.append(parsed)
        return events

    @staticmethod
    def _pad_64(command: list[int]) -> list[int]:
        if len(command) > 64:
            raise InvalidArgumentError("HID command cannot exceed 64 bytes")
        return command + [0] * (64 - len(command))


def _load_hid_backend() -> HidBackendLike:
    try:
        import hid  # type: ignore
    except ImportError as exc:
        raise DiscoveryError("Install optional dependency: pip install 'arctis-nova-api[usb]'") from exc
    return hid
