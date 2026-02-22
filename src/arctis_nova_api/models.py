from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SonarChannel(str, Enum):
    MASTER = "master"
    GAME = "game"
    CHAT_RENDER = "chatRender"
    MEDIA = "media"
    AUX = "aux"
    CHAT_CAPTURE = "chatCapture"


class StreamerSlider(str, Enum):
    STREAMING = "streaming"
    MONITORING = "monitoring"


class PresetChannel(Enum):
    GAMING = 1
    CHAT = 2
    MIC = 3
    MEDIA = 4
    AUX = 5
    MASTER = 6


class AncMode(str, Enum):
    OFF = "off"
    ANC = "anc"
    TRANSPARENCY = "transparency"


class UsbInput(str, Enum):
    USB1 = "usb1"
    USB2 = "usb2"


@dataclass(frozen=True)
class SonarPreset:
    preset_id: str
    name: str
    channel: PresetChannel


@dataclass(frozen=True)
class BatteryStatus:
    headset: int
    charging: int


@dataclass(frozen=True)
class HeadsetConnectionStatus:
    wireless: bool
    bluetooth: bool
    bluetooth_on: bool


@dataclass(frozen=True)
class VolumeKnobEvent:
    volume: int


@dataclass(frozen=True)
class SidetoneStatus:
    level: int


@dataclass(frozen=True)
class AncStatus:
    mode: AncMode


@dataclass(frozen=True)
class MicStatus:
    enabled: bool


DeviceEvent = VolumeKnobEvent | BatteryStatus | HeadsetConnectionStatus | SidetoneStatus | AncStatus | MicStatus


@dataclass(frozen=True)
class OledLine:
    text: str
    bold: bool = False
    wrap: int = 0
    context_frame_key: str | None = None


@dataclass(frozen=True)
class OledFrame:
    lines: list[OledLine]
    length_millis: int = 0
    icon_id: int = 0
    repeats: bool | int = False


def to_event_data(value: int, frame: dict[str, Any] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"value": int(value)}
    if frame is not None:
        data["frame"] = frame
    return data
