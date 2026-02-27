from __future__ import annotations

from arctis_nova_api import PresetChannel, SonarChannel

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

SIDETONE_LABELS: dict[int, str] = {0: "off", 1: "low", 2: "med", 3: "high"}
